#!/usr/bin/env python3
"""
Automated Live Sample Refresher for german-b2b-data-suite.

Fetches fresh, non-cancelled, strictly future-dated listings directly from:
  1. https://www.zvg-portal.de (all 16 German federal states)
  2. https://www.service.bund.de (German public procurement tenders)

Outputs updated sample files in samples/:
  - DE_Zwangsversteigerungen_Sample_50.{csv,json,xlsx}
  - 03_zvg_foreclosures_sample.{json,csv}
  - 04_public_tenders_sample.{json,csv}

Optional hub synchronization (--sync-hubs):
  - Hugging Face Hub (HF_TOKEN) -> AGrunert/german-real-estate-foreclosures-zvg-sample
  - Kaggle Datasets (KAGGLE_API_TOKEN) -> andrgrunert/german-real-estate-foreclosures-zvg-sample
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import os
import re
import shutil
import tempfile
from collections import defaultdict
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
from urllib.parse import parse_qs, urlencode, urljoin, urlparse
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import httpx
import openpyxl
from lxml import html
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

ROOT_DIR = Path(__file__).resolve().parent.parent
SAMPLES_DIR = ROOT_DIR / "samples"
GATEWAY_BASE_URL = "https://andregrunert-ctrl.github.io/german-b2b-data-suite/zvg.html"

ALL_STATES = [
    "bw", "by", "be", "br", "hb", "hh", "he", "mv",
    "ni", "nw", "rp", "sl", "sn", "st", "sh", "th",
]

STATE_NAMES: Dict[str, str] = {
    "bw": "Baden-Württemberg", "by": "Bayern", "be": "Berlin",
    "br": "Brandenburg", "hb": "Bremen", "hh": "Hamburg",
    "he": "Hessen", "mv": "Mecklenburg-Vorpommern", "ni": "Niedersachsen",
    "nw": "Nordrhein-Westfalen", "rp": "Rheinland-Pfalz", "sl": "Saarland",
    "sn": "Sachsen", "st": "Sachsen-Anhalt", "sh": "Schleswig-Holstein",
    "th": "Thüringen",
}

GERMAN_STATES_LONG = list(STATE_NAMES.values())

GERMAN_MONTHS: Dict[str, int] = {
    "januar": 1, "jänner": 1, "februar": 2, "märz": 3, "maerz": 3, "april": 4,
    "mai": 5, "juni": 6, "juli": 7, "august": 8, "september": 9,
    "oktober": 10, "november": 11, "dezember": 12,
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "de-DE,de;q=0.9,en;q=0.7",
}


def berlin_now() -> datetime:
    try:
        return datetime.now(ZoneInfo("Europe/Berlin"))
    except ZoneInfoNotFoundError:
        return datetime.now(timezone(timedelta(hours=1)))


def clean_ws(text: Optional[str]) -> str:
    if not text:
        return ""
    s = re.sub(r"[\xad\u00ad]\s*", "", text)
    s = s.replace("\xa0", " ").replace("\u200b", "")
    return re.sub(r"\s+", " ", s).strip()


def decode_zvg_html(content: bytes) -> str:
    """Safely decode ZVG-Portal HTML (UTF-8 with charset hint or CP1252 fallback)."""
    head_ascii = content[:2048].decode("ascii", errors="ignore").lower()
    if "charset=iso-8859" in head_ascii or "charset=windows-1252" in head_ascii:
        text = content.decode("cp1252", errors="replace")
    else:
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError:
            text = content.decode("cp1252", errors="replace")
    return text.replace("\x80", "€").replace("&#128;", "€")


def parse_german_date(date_str: Optional[str]) -> Optional[date]:
    if not date_str:
        return None
    text = str(date_str).strip()
    m_named = re.search(r"\b(\d{1,2})\.\s*([A-Za-zäöüÄÖÜß]+)\s*(\d{4})\b", text)
    if m_named:
        month = GERMAN_MONTHS.get(m_named.group(2).lower())
        if month:
            try:
                return date(int(m_named.group(3)), month, int(m_named.group(1)))
            except ValueError:
                pass
    m_num = re.search(r"\b(\d{1,2})\.(\d{1,2})\.(\d{2,4})\b", text)
    if m_num:
        yr = int(m_num.group(3))
        if yr < 100:
            yr += 2000
        try:
            return date(yr, int(m_num.group(2)), int(m_num.group(1)))
        except ValueError:
            pass
    m_iso = re.search(r"\b(\d{4})-(\d{2})-(\d{2})\b", text)
    if m_iso:
        try:
            return date(int(m_iso.group(1)), int(m_iso.group(2)), int(m_iso.group(3)))
        except ValueError:
            pass
    return None


def parse_market_value(raw: Optional[str]) -> Optional[float]:
    if not raw:
        return None
    text = clean_ws(raw)
    if not text or any(k in text.lower() for k in ["wird noch festgesetzt", "keine angabe", "unbekannt", "entfällt"]):
        return None

    # Handle adjusted Flurbereinigung / explicit Gesamt totals first
    sec_b = re.search(r"B:\s*für den bereinigten Zustand.*", text, re.IGNORECASE | re.DOTALL)
    if sec_b:
        text = sec_b.group(0)

    gesamt_m = re.findall(
        r"(?:Gesamtverkehrswert|Gesamtwert|Gesamt)\s*:?\s*([\d\.,]+)\s*(?:€|EUR|,-|--)?",
        text,
        re.IGNORECASE,
    )
    if gesamt_m:
        text = gesamt_m[-1]

    # Remove Zubehör clauses in parentheses or after davon
    text = re.sub(r"\([^)]*zubehör[^)]*\)", "", text, flags=re.IGNORECASE)
    text = re.split(r",?\s*davon\s+entfällt", text, flags=re.IGNORECASE)[0]

    # Parse German/typo currency tokens
    amounts: List[float] = []
    for m in re.finditer(r"(\d{1,3}(?:[.,]\d{3})+|\d+)(?:[.,](\d{2})|,-|--)?", text):
        full = m.group(0)
        # Skip likely plot/parcel integers lacking currency context when summing multiple chunks
        int_part, dec_part = m.group(1), m.group(2)
        num_str = re.sub(r"[.,]", "", int_part)
        if dec_part:
            val = float(f"{num_str}.{dec_part}")
        else:
            val = float(num_str)
        if 1.0 <= val <= 500_000_000.0:
            # Avoid accidentally summing years like 2026 inside explanatory prose if clear EUR amounts exist
            if not dec_part and ",-" not in full and "--" not in full and "." not in int_part and "," not in int_part:
                # Plain integer: accept only when preceded/followed by € or EUR or entire string is numeric
                ctx_slice = text[max(0, m.start() - 10):min(len(text), m.end() + 10)].lower()
                if "€" not in ctx_slice and "eur" not in ctx_slice and len(text) > 15:
                    continue
            amounts.append(val)

    if not amounts:
        return None
    if len(gesamt_m) > 0:
        return round(amounts[-1], 2)
    return round(sum(amounts) if len(amounts) > 1 and ("lfd" in text.lower() or "nr." in text.lower() or "flurstück" in text.lower()) else amounts[0], 2)


def clean_case_number(raw: Optional[str]) -> str:
    if not raw:
        return ""
    s = clean_ws(raw)
    s = re.sub(r"\(Detailansicht\)", "", s, flags=re.IGNORECASE).strip()
    # Deduplicate adjacent register letters (e.g. '0006 K K 0005/2025')
    s = re.sub(r"\b([KLM])\s+\1\b", r"\1", s)
    return clean_ws(s)


def parse_objekt_lage(raw_text: Optional[str]) -> Dict[str, Optional[str]]:
    if not raw_text:
        return {"property_type": None, "address": None, "postal_code": None, "city": None}
    text = clean_ws(raw_text)
    prop_type: Optional[str] = None
    addr_part = text

    if ":" in text:
        left, right = text.split(":", 1)
        if len(left.strip()) <= 80:
            prop_type = clean_ws(left).strip(" ,;:-") or None
            addr_part = clean_ws(right)

    addr_clean = re.sub(r"\s+,", ",", addr_part)
    addr_clean = re.sub(r",\s*;", ", ", addr_clean)
    addr_clean = re.sub(r"\b00000\b\s*", "", addr_clean)
    addr_clean = clean_ws(addr_clean).strip(" ,;")

    plz: Optional[str] = None
    city: Optional[str] = None
    m_plz = re.search(r"\b([0-9]{5})\b\s*([^,;]+)?", addr_part)
    if m_plz:
        cand_plz = m_plz.group(1)
        if cand_plz != "00000":
            plz = cand_plz
        if m_plz.group(2):
            c_raw = m_plz.group(2).split(",")[0].split(";")[0]
            c_raw = re.sub(r"\bGemarkung\b.*$", "", c_raw, flags=re.IGNORECASE).strip(" ,;-")
            if c_raw:
                city = c_raw
    return {
        "property_type": prop_type,
        "address": addr_clean or None,
        "postal_code": plz,
        "city": city,
    }


def make_gateway_url(row: Dict[str, Any]) -> str:
    state = (row.get("state_code") or row.get("state") or "").lower()
    case_no = row.get("case_number") or ""
    zvg_id = str(row.get("zvg_id") or "")
    m = re.search(r"[KLM]\s*(\d{1,5})\s*/\s*(\d{2,4})", case_no, re.IGNORECASE)
    if m and state and zvg_id:
        az3, az4 = m.group(1), m.group(2)
        if len(az4) == 2:
            az4 = f"20{az4}"
        q = urlencode({"land_abk": state, "az3": az3, "az4": az4, "az": case_no, "zvg_id": zvg_id})
        return f"{GATEWAY_BASE_URL}?{q}"
    return row.get("detail_url") or row.get("pdf_primary_url") or ""


async def fetch_zvg_state(client: httpx.AsyncClient, state: str) -> List[Dict[str, Any]]:
    search_url = "https://www.zvg-portal.de/index.php?button=Suchen&all=1"
    referer_url = "https://www.zvg-portal.de/index.php?button=Termine%20suchen"
    payload = {
        "ger_name": "-- Alle Amtsgerichte --",
        "land_abk": state,
        "ger_id": "0",
        "order_by": "2",
        "az1": "", "az2": "", "az3": "", "az4": "",
        "art": "", "obj": "", "str": "", "hnr": "",
        "plz": "", "ort": "", "ortsteil": "",
        "vtermin": "", "btermin": "",
    }
    try:
        r = await client.post(
            search_url,
            data=payload,
            headers={**HEADERS, "Referer": referer_url, "Origin": "https://www.zvg-portal.de"},
        )
        if r.status_code != 200:
            return []
        tree = html.fromstring(decode_zvg_html(r.content))
    except Exception as exc:
        print(f"  [WARN] ZVG state {state.upper()} failed: {exc}")
        return []

    target_table = None
    for t in tree.xpath("//table"):
        if t.xpath("./tr/td[contains(., 'Aktenzeichen')] | ./tbody/tr/td[contains(., 'Aktenzeichen')]"):
            target_table = t
            break
    if target_table is None:
        return []

    rows = target_table.xpath("./tr | ./tbody/tr")
    listings: List[Dict[str, Any]] = []
    current: Optional[Dict[str, Any]] = None

    for tr in rows:
        tds = tr.xpath("./td | ./th")
        if not tds:
            continue
        c0_text = clean_ws(tds[0].text_content())

        if "Aktenzeichen" in c0_text:
            if current and current.get("zvg_id"):
                listings.append(current)
            detail_links = tr.xpath(".//a[contains(@href, 'showZvg')]")
            if not detail_links:
                current = None
                continue
            href = detail_links[0].get("href", "")
            abs_detail = urljoin("https://www.zvg-portal.de/", href)
            qs = parse_qs(urlparse(abs_detail).query)
            zvg_id = (qs.get("zvg_id") or [""])[0]
            case_no = clean_case_number(detail_links[0].text_content())
            current = {
                "zvg_id": zvg_id,
                "case_number": case_no,
                "state": state,
                "court": None,
                "property_type": None,
                "title": None,
                "address": None,
                "postal_code": None,
                "city": None,
                "market_value_eur": None,
                "currency": "EUR",
                "auction_date": None,
                "auction_location": None,
                "land_register": None,
                "status_notes": None,
                "is_cancelled": False,
                "description": None,
                "creditor_info": None,
                "pdf_urls": [],
                "documents": [],
                "detail_url": abs_detail,
                "scraped_at": datetime.now(timezone.utc).isoformat(),
            }
            continue

        if current is None:
            continue

        val_text = clean_ws(tds[1].text_content()) if len(tds) > 1 else ""
        if "Amtsgericht" in c0_text:
            court_val = val_text
            if court_val.startswith("in "):
                court_val = f"Amtsgericht {court_val}"
            elif court_val and not court_val.startswith("Amtsgericht"):
                court_val = f"Amtsgericht {court_val}"
            current["court"] = court_val or current.get("court")
        elif "Objekt/Lage" in c0_text:
            parsed = parse_objekt_lage(val_text)
            current.update({
                "property_type": parsed["property_type"],
                "title": val_text,
                "address": parsed["address"],
                "postal_code": parsed["postal_code"],
                "city": parsed["city"],
            })
        elif "Verkehrswert" in c0_text:
            current["market_value_eur"] = parse_market_value(val_text)
        elif "Termin" in c0_text:
            current["auction_date"] = val_text
            if any(k in val_text.lower() for k in ["aufgehoben", "eingestellt", "fällt aus"]):
                current["is_cancelled"] = True

        for a in tr.xpath(".//a[contains(@href, 'showAnhang')]"):
            href = a.get("href", "").strip()
            if not href:
                continue
            abs_pdf = urljoin("https://www.zvg-portal.de/index.php", href)
            if abs_pdf not in current["pdf_urls"]:
                current["pdf_urls"].append(abs_pdf)
                size_sp = tr.xpath(".//span[contains(@class, 'kleinereSchrift')]/text()")
                fsize = f" file_size='{clean_ws(size_sp[0])}'" if size_sp and clean_ws(size_sp[0]) else ""
                current["documents"].append(f"title='{c0_text or 'Amtliche Bekanntmachung'}' url='{abs_pdf}' file_type='pdf'{fsize}")

    if current and current.get("zvg_id"):
        listings.append(current)

    seen: Set[str] = set()
    uniq: List[Dict[str, Any]] = []
    for item in listings:
        zid = item.get("zvg_id")
        if zid and zid not in seen:
            seen.add(zid)
            uniq.append(item)
    return uniq


async def enrich_zvg_detail(client: httpx.AsyncClient, sem: asyncio.Semaphore, item: Dict[str, Any]) -> Dict[str, Any]:
    url = item.get("detail_url")
    if not url:
        return item
    async with sem:
        try:
            r = await client.get(
                url,
                headers={**HEADERS, "Referer": "https://www.zvg-portal.de/index.php?button=Suchen"},
            )
            if r.status_code != 200:
                return item
            tree = html.fromstring(decode_zvg_html(r.content))
        except Exception:
            return item

    for tr in tree.xpath("//table//tr"):
        tds = tr.xpath("./td")
        if len(tds) < 2:
            continue
        label = clean_ws(tds[0].text_content()).rstrip(":").strip()
        label_low = label.lower()
        val = clean_ws(tds[1].text_content())
        if val:
            if label == "Beschreibung":
                item["description"] = val
            elif label == "Grundbuch":
                item["land_register"] = val
            elif label == "Ort der Versteigerung":
                item["auction_location"] = val
            elif label == "Informationen zum Gläubiger" or "gläubiger" in label_low:
                item["creditor_info"] = val
            elif "objekt/lage" in label_low and not item.get("title"):
                parsed = parse_objekt_lage(val)
                item["title"] = val
                item["property_type"] = parsed["property_type"]
                item["address"] = parsed["address"]
                item["postal_code"] = parsed["postal_code"]
                item["city"] = parsed["city"]
            elif "verkehrswert" in label_low and item.get("market_value_eur") is None:
                item["market_value_eur"] = parse_market_value(val)
            elif "termin" in label_low and not item.get("auction_date"):
                item["auction_date"] = val
                if any(k in val.lower() for k in ["aufgehoben", "eingestellt", "fällt aus"]):
                    item["is_cancelled"] = True

        for a in tr.xpath(".//a[contains(@href, 'showAnhang')]"):
            href = a.get("href", "").strip()
            if not href:
                continue
            abs_pdf = urljoin("https://www.zvg-portal.de/index.php", href)
            if abs_pdf not in item["pdf_urls"]:
                item["pdf_urls"].append(abs_pdf)
                anchor_txt = clean_ws(a.text_content()) or label or "Amtliche Bekanntmachung"
                size_sp = tr.xpath(".//span[contains(@class, 'kleinereSchrift')]/text()")
                fsize = f" file_size='{clean_ws(size_sp[0])}'" if size_sp and clean_ws(size_sp[0]) else ""
                item["documents"].append(f"title='{anchor_txt}' url='{abs_pdf}' file_type='pdf'{fsize}")

    return item


def build_clean_export_row(r: Dict[str, Any]) -> Dict[str, Any]:
    st = (r.get("state") or "").lower()
    pdfs = r.get("pdf_urls") or []
    return {
        "zvg_id": str(r.get("zvg_id") or ""),
        "state_code": st.upper(),
        "state_name": STATE_NAMES.get(st, st.upper()),
        "court": clean_ws(r.get("court")),
        "case_number": clean_ws(r.get("case_number")),
        "property_type": clean_ws(r.get("property_type")) or "Immobilie / Sonstiges",
        "title": clean_ws(r.get("title")),
        "address": clean_ws(r.get("address")),
        "postal_code": clean_ws(r.get("postal_code")),
        "city": clean_ws(r.get("city")),
        "market_value_eur": r.get("market_value_eur"),
        "auction_date": clean_ws(r.get("auction_date")),
        "auction_location": clean_ws(r.get("auction_location")),
        "land_register": clean_ws(r.get("land_register")),
        "creditor_info": clean_ws(r.get("creditor_info")),
        "pdf_primary_url": pdfs[0] if pdfs else "",
        "pdf_urls_count": len(pdfs),
        "all_pdf_urls": " ; ".join(pdfs),
        "detail_url": clean_ws(r.get("detail_url")),
        "description": clean_ws(r.get("description")),
    }


def write_sample_50_xlsx(rows: List[Dict[str, Any]], out_path: Path) -> None:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Zwangsversteigerungen 2026"

    headers = [
        ("ZVG-ID", "zvg_id", 10),
        ("Bundesland-Code", "state_code", 14),
        ("Bundesland", "state_name", 22),
        ("Amtsgericht", "court", 34),
        ("Aktenzeichen", "case_number", 20),
        ("Objektart", "property_type", 26),
        ("Objektbezeichnung / Titel", "title", 44),
        ("Adresse / Straße", "address", 38),
        ("PLZ", "postal_code", 8),
        ("Ort", "city", 20),
        ("Verkehrswert (€)", "market_value_eur", 18),
        ("Versteigerungstermin", "auction_date", 34),
        ("Versteigerungsort", "auction_location", 38),
        ("Grundbuch", "land_register", 30),
        ("Gläubiger / Kontakt", "creditor_info", 28),
        ("PDF-Gutachten / Bekanntmachung", "pdf_primary_url", 32),
        ("PDF-Anzahl", "pdf_urls_count", 11),
        ("Alle PDF-Dokumente", "all_pdf_urls", 42),
        ("ZVG-Portal Link", "detail_url", 26),
        ("Vollständige Objektbeschreibung", "description", 65),
    ]

    hdr_fill = PatternFill(start_color="0F2C59", end_color="0F2C59", fill_type="solid")
    hdr_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    zebra_fill = PatternFill(start_color="F5F8FC", end_color="F5F8FC", fill_type="solid")
    link_font = Font(name="Calibri", size=10, color="0563C1", underline="single")
    body_font = Font(name="Calibri", size=10)
    thin = Side(style="thin", color="D9E1EC")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)

    for col_idx, (label, _, width) in enumerate(headers, start=1):
        c = ws.cell(row=1, column=col_idx, value=label)
        c.fill = hdr_fill
        c.font = hdr_font
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        ws.column_dimensions[get_column_letter(col_idx)].width = width
    ws.row_dimensions[1].height = 28

    for r_idx, row in enumerate(rows, start=2):
        gw_url = make_gateway_url(row)
        for col_idx, (_, key, _) in enumerate(headers, start=1):
            val = row.get(key)
            cell = ws.cell(row=r_idx, column=col_idx)
            cell.font = body_font
            cell.border = border
            if r_idx % 2 == 1:
                cell.fill = zebra_fill

            if key == "market_value_eur":
                cell.value = float(val) if val is not None else None
                cell.number_format = "#,##0.00 €"
                cell.alignment = Alignment(horizontal="right", vertical="top")
            elif key == "pdf_primary_url" and row.get("pdf_primary_url"):
                cell.value = "PDF via ZVG-Portal öffnen (1-Klick)"
                cell.hyperlink = gw_url
                cell.font = link_font
                cell.alignment = Alignment(vertical="top")
            elif key == "detail_url" and row.get("detail_url"):
                cell.value = "Verfahren öffnen (1-Klick)"
                cell.hyperlink = gw_url
                cell.font = link_font
                cell.alignment = Alignment(vertical="top")
            else:
                cell.value = val if val != "" else None
                cell.alignment = Alignment(vertical="top", wrap_text=(key in ("title", "description", "address")))

    ws.freeze_panes = "A2"
    ws.auto_filter.ref = f"A1:{get_column_letter(len(headers))}{len(rows) + 1}"

    # Sheet 2: Market statistics
    ws2 = wb.create_sheet("Statistik nach Bundesland & Art")
    ws2["A1"] = "GERMAN REAL ESTATE FORECLOSURE INTELLIGENCE - MARKTÜBERSICHT"
    ws2["A1"].font = Font(name="Calibri", size=14, bold=True, color="0F2C59")

    ws2["A3"] = "Bundesland"
    ws2["B3"] = "Auktionen"
    ws2["C3"] = "Gesamtverkehrswert (€)"
    ws2["D3"] = "Ø Verkehrswert (€)"
    for col in range(1, 5):
        ws2.cell(3, col).fill = hdr_fill
        ws2.cell(3, col).font = hdr_font

    by_state: Dict[str, List[float]] = defaultdict(list)
    for row in rows:
        mv = row.get("market_value_eur")
        by_state[row["state_name"]].append(float(mv) if mv else 0.0)

    r_ptr = 4
    for st_name, vals in sorted(by_state.items(), key=lambda kv: -len(kv[1])):
        non_zero = [v for v in vals if v > 0]
        ws2.cell(r_ptr, 1, st_name)
        ws2.cell(r_ptr, 2, len(vals))
        c_sum = ws2.cell(r_ptr, 3, round(sum(non_zero), 2))
        c_avg = ws2.cell(r_ptr, 4, round(sum(non_zero) / len(non_zero), 2) if non_zero else 0.0)
        c_sum.number_format = "#,##0.00 €"
        c_avg.number_format = "#,##0.00 €"
        r_ptr += 1

    for col_idx, w in enumerate([28, 14, 24, 22], start=1):
        ws2.column_dimensions[get_column_letter(col_idx)].width = w

    wb.save(out_path)


async def refresh_zvg_samples(tomorrow: date) -> Tuple[int, int]:
    """Scrape active future ZVG auctions nationwide & verify PDFs, write Sample_50 and 03_zvg_foreclosures_sample."""
    print(f"[ZVG] Refreshing nationwide live auctions (cutoff >= {tomorrow.isoformat()})...")
    timeout = httpx.Timeout(connect=10.0, read=25.0, write=10.0, pool=30.0)
    async with httpx.AsyncClient(headers=HEADERS, timeout=timeout, follow_redirects=True) as client:
        state_lists = await asyncio.gather(*(fetch_zvg_state(client, st) for st in ALL_STATES))
        raw_by_state: Dict[str, List[Dict[str, Any]]] = {}
        for st, items in zip(ALL_STATES, state_lists):
            future_active = []
            for it in items:
                if it.get("is_cancelled"):
                    continue
                dt = parse_german_date(it.get("auction_date"))
                if dt is not None and dt >= tomorrow:
                    future_active.append(it)
            raw_by_state[st] = future_active
            print(f"  {st.upper()}: {len(future_active)} future active (raw={len(items)})")

        # Round-robin pick candidates across states to ensure geographic diversity (~96 detail fetches)
        candidates: List[Dict[str, Any]] = []
        round_idx = 0
        while len(candidates) < 100:
            added_any = False
            for st in ALL_STATES:
                bucket = raw_by_state.get(st, [])
                if round_idx < len(bucket):
                    candidates.append(bucket[round_idx])
                    added_any = True
            if not added_any:
                break
            round_idx += 1

        sem = asyncio.Semaphore(8)
        enriched = await asyncio.gather(*(enrich_zvg_detail(client, sem, it) for it in candidates))

        # Keep clean future records with PDFs & valuation
        valid: List[Dict[str, Any]] = []
        for it in enriched:
            if it.get("is_cancelled"):
                continue
            dt = parse_german_date(it.get("auction_date"))
            if dt is None or dt < tomorrow:
                continue
            if not it.get("pdf_urls"):
                continue
            if not it.get("market_value_eur") or float(it["market_value_eur"]) <= 0:
                continue
            valid.append(it)

        if len(valid) < 10:
            raise RuntimeError(f"Too few valid future ZVG records extracted ({len(valid)}); aborting sample overwrite.")

        # Verify PDF endpoint returns real %PDF header on first 5 records (for 03_zvg sample guarantee)
        verified_pdf_top: List[Dict[str, Any]] = []
        for it in valid:
            if len(verified_pdf_top) >= 5:
                break
            try:
                resp = await client.get(
                    it["pdf_urls"][0],
                    headers={**HEADERS, "Referer": it["detail_url"]},
                )
                if resp.status_code == 200 and resp.content.startswith(b"%PDF"):
                    verified_pdf_top.append(it)
            except Exception:
                continue

        if not verified_pdf_top:
            raise RuntimeError("Failed to verify %PDF response on candidate ZVG sample records.")

    # Select balanced 50 for Sample_50
    sample_50_raw = valid[:50]
    sample_50_clean = [build_clean_export_row(it) for it in sample_50_raw]

    (SAMPLES_DIR / "DE_Zwangsversteigerungen_Sample_50.json").write_text(
        json.dumps(sample_50_clean, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    csv50_fields = list(sample_50_clean[0].keys())
    with (SAMPLES_DIR / "DE_Zwangsversteigerungen_Sample_50.csv").open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=csv50_fields)
        w.writeheader()
        w.writerows(sample_50_clean)
    write_sample_50_xlsx(sample_50_clean, SAMPLES_DIR / "DE_Zwangsversteigerungen_Sample_50.xlsx")

    # Save 03_zvg_foreclosures_sample.{json,csv}
    top5 = verified_pdf_top[:5]
    (SAMPLES_DIR / "03_zvg_foreclosures_sample.json").write_text(
        json.dumps(top5, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    csv03_fields = list(top5[0].keys())
    with (SAMPLES_DIR / "03_zvg_foreclosures_sample.csv").open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=csv03_fields)
        w.writeheader()
        for item in top5:
            row = {k: (json.dumps(v, ensure_ascii=False) if isinstance(v, list) else v) for k, v in item.items()}
            w.writerow(row)

    print(f"[ZVG] ✓ Wrote DE_Zwangsversteigerungen_Sample_50 ({len(sample_50_clean)} rows) & 03_zvg_foreclosures_sample ({len(top5)} rows).")
    return len(sample_50_clean), len(top5)


# ---------------------------------------------------------------------------
# Public Tenders (service.bund.de) Refresher
# ---------------------------------------------------------------------------

def infer_state_from_plz(plz: Optional[str]) -> Optional[str]:
    if not plz or len(plz) != 5 or not plz.isdigit() or plz == "00000":
        return None
    p2, p3 = int(plz[:2]), int(plz[:3])
    if p2 in (1, 2, 4, 8, 9): return "Sachsen"
    if p2 == 3 or p2 in (15, 16) or p2 == 14: return "Brandenburg"
    if p2 == 6 or (388 <= p3 <= 399): return "Sachsen-Anhalt"
    if p2 in (7, 98, 99): return "Thüringen"
    if 10 <= p2 <= 13: return "Berlin"
    if 17 <= p2 <= 19: return "Mecklenburg-Vorpommern"
    if p2 == 20 or p2 == 22: return "Hamburg"
    if 23 <= p2 <= 25: return "Schleswig-Holstein"
    if p2 == 28: return "Bremen"
    if p2 in (21, 26, 27, 29, 30, 31, 37, 38): return "Niedersachsen"
    if p2 in (32, 33, 40, 41, 42, 44, 45, 46, 47, 48, 50, 51, 52, 53, 57, 58, 59): return "Nordrhein-Westfalen"
    if p2 in (34, 35, 36, 60, 61, 63, 64, 65): return "Hessen"
    if p2 in (54, 55, 56, 67): return "Rheinland-Pfalz"
    if p2 == 66: return "Saarland"
    if 68 <= p2 <= 79 or (88 <= p2 <= 89): return "Baden-Württemberg"
    if (80 <= p2 <= 87) or (90 <= p2 <= 97): return "Bayern"
    return None


def parse_tender_location(raw_loc: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    clean_loc = clean_ws(re.sub(r"Karte anschauen", "", raw_loc, flags=re.IGNORECASE))
    clean_loc = re.sub(r"^00000\s*", "", clean_loc).strip()
    if not clean_loc:
        return None, None, None
    plz_m = re.search(r"\b(\d{5})\b", clean_loc)
    plz = plz_m.group(1) if plz_m and plz_m.group(1) != "00000" else None
    rem = clean_loc[plz_m.end():].strip() if plz_m else clean_loc
    state = None
    for st in sorted(GERMAN_STATES_LONG, key=len, reverse=True):
        if rem.lower().endswith(st.lower()):
            state = st
            rem = rem[:-len(st)].strip()
            break
    city = re.sub(r",\s*(?:Stadt|Landeshauptstadt|Kreisfreie Stadt|Hansestadt)\s*$", "", rem, flags=re.I).strip(",- ")
    if not city and state:
        city = state
    if not state and plz:
        state = infer_state_from_plz(plz)
    return plz, city or None, state


def normalize_tender_date(val: Optional[str]) -> Optional[str]:
    if not val:
        return None
    m = re.search(r"(\d{2})\.(\d{2})\.(\d{2,4})", val)
    if not m:
        return clean_ws(val)
    d, mo, y = m.groups()
    if len(y) == 2:
        y = f"20{y}"
    base = f"{d}.{mo}.{y}"
    tm = re.search(r"\b(\d{1,2}:\d{2}(?:\s*Uhr)?)\b", val, re.IGNORECASE)
    return f"{base} {tm.group(1).strip()}" if tm else base


def is_software_boilerplate(item: Dict[str, Any], kw: str) -> bool:
    if kw.lower() != "software":
        return False
    if "software" in (item.get("title") or "").lower():
        return False
    if any(str(c).startswith(("48", "72", "302")) for c in (item.get("cpv_codes") or [])):
        return False
    desc = re.sub(
        r"(?:unter\s+Nutzung\s+der\s+)?(?:AI\s*[-_]?\s*)?Software\s*[\"“'„]?(?:AI[-_ ]?)?Bietercockpit[\"“'„]?|Bieter-?Software|Vergabesoftware",
        "",
        item.get("description") or "",
        flags=re.IGNORECASE,
    )
    return "software" not in desc.lower()


async def refresh_tender_samples(tomorrow: date) -> int:
    print(f"[TENDERS] Refreshing live tenders from service.bund.de (deadline >= {tomorrow.isoformat()})...")
    base_url = "https://www.service.bund.de"
    search_url = f"{base_url}/Content/DE/Ausschreibungen/Suche/Formular.html"
    keywords = ["Software", "Cloud", "IT"]

    timeout = httpx.Timeout(connect=10.0, read=25.0, write=10.0, pool=25.0)
    candidates: List[Dict[str, Any]] = []
    seen_ids: Set[str] = set()

    async with httpx.AsyncClient(headers=HEADERS, timeout=timeout, follow_redirects=True) as client:
        for kw in keywords:
            if len(candidates) >= 24:
                break
            resp = await client.get(search_url, params={"nn": "4641482", "type": "0", "submit": "Finden", "resultsPerPage": "40", "templateQueryString": kw})
            if resp.status_code != 200:
                continue
            tree = html.fromstring(resp.content)
            for card in tree.xpath("//div[@aria-labelledby='title']/ancestor::a[1]"):
                href = (card.get("href") or "").split(";")[0]
                if not href:
                    continue
                detail_url = urljoin(base_url, href)
                tid_m = re.search(r"/([^/]+?)\.html", detail_url)
                tid = tid_m.group(1) if tid_m else detail_url
                if tid in seen_ids:
                    continue
                seen_ids.add(tid)

                h3 = card.xpath(".//div[@aria-labelledby='title']//h3")
                title = clean_ws(h3[0].text_content()) if h3 else f"Tender {tid}"
                title = re.sub(r"^Ausschreibung\s*", "", title, flags=re.I).strip("'\"„“ ")
                auth_el = card.xpath(".//div[@aria-labelledby='title']//p")
                auth = re.sub(r"^Vergabestelle\s*", "", clean_ws(auth_el[0].text_content()), flags=re.I).strip() if auth_el else ""
                pub_el = card.xpath(".//div[@aria-labelledby='date']//p")
                pub = normalize_tender_date(clean_ws(pub_el[0].text_content())) if pub_el else None

                candidates.append({
                    "tender_id": tid,
                    "title": title,
                    "contracting_authority": auth,
                    "published_at": pub,
                    "submission_deadline": None,
                    "location": None,
                    "postal_code": None,
                    "city": None,
                    "state": None,
                    "service_type": None,
                    "procedure_type": None,
                    "cpv_codes": [],
                    "description": "",
                    "tender_document_urls": [],
                    "detail_url": detail_url,
                    "matched_keyword": kw,
                    "scraped_at": datetime.now(timezone.utc).isoformat(),
                })
                if len(candidates) >= 24:
                    break

        verified: List[Dict[str, Any]] = []
        for cand in candidates:
            if len(verified) >= 5:
                break
            try:
                dr = await client.get(cand["detail_url"])
                if dr.status_code != 200:
                    continue
                dtree = html.fromstring(dr.text)
                dl_items: Dict[str, str] = {}
                for dt_el in dtree.xpath("//dl//dt"):
                    dd = dt_el.xpath("./following-sibling::dd[1]")
                    if dd:
                        dl_items[clean_ws(dt_el.text_content()).lower()] = clean_ws(dd[0].text_content())

                cand["service_type"] = dl_items.get("leistungen und erzeugnisse")
                proc = dl_items.get("vergabeart")
                if proc and dl_items.get("vergabeverfahren"):
                    proc = f"{proc} ({dl_items['vergabeverfahren']})"
                cand["procedure_type"] = proc or dl_items.get("vergabeverfahren")
                if dl_items.get("angebotsfrist"):
                    cand["submission_deadline"] = normalize_tender_date(dl_items["angebotsfrist"])
                if dl_items.get("erfüllungsort"):
                    loc = re.sub(r"^00000\s*", "", clean_ws(re.sub(r"Karte anschauen", "", dl_items["erfüllungsort"], flags=re.I)))
                    cand["location"] = loc
                    plz, city, state = parse_tender_location(loc)
                    cand["postal_code"], cand["city"], cand["state"] = plz, city, state

                pre_el = dtree.xpath("//pre")
                if pre_el:
                    pre_txt = pre_el[0].text_content()
                    cand["description"] = clean_ws(pre_txt)
                    if dl_items.get("cpv-code"):
                        cand["cpv_codes"] = [clean_ws(c) for c in re.split(r"[,;]+", dl_items["cpv-code"]) if clean_ws(c)]
                    else:
                        cand["cpv_codes"] = list(dict.fromkeys(re.findall(r"\b(\d{8}(?:-\d)?)\b", pre_txt)))
                    dl_m = re.search(r"Frist für den Eingang der (?:Angebote|Teilnahmeanträge)\s*:\s*(\d{2}\.\d{2}\.\d{2,4}(?:\s+\d{1,2}:\d{2}(?:\s*Uhr)?)?)", pre_txt, re.I)
                    if dl_m:
                        cand["submission_deadline"] = normalize_tender_date(dl_m.group(1)) or cand["submission_deadline"]
                    raw_urls = re.findall(r"https?://[^\s<>\"']+", pre_txt)
                    cand["tender_document_urls"] = list(dict.fromkeys(
                        re.sub(r";jsessionid=[^/?#]+", "", u.rstrip(".,;:)\"'>"))
                        for u in raw_urls
                        if any(p in u.lower() for p in ["/unterlagen", "/notice", "/tenderdetails", "/subproject", ".pdf"])
                    ))

                if not cand["description"]:
                    cand["description"] = f"{cand['title']} | Vergabestelle: {cand['contracting_authority']}"

                # Skip revoked/cancelled tenders & expired deadlines
                desc_low = cand["description"].lower()
                if any(w in desc_low for w in ["aufgehoben wurde", "verfahren eingestellt", "annulliert"]):
                    continue
                if is_software_boilerplate(cand, cand["matched_keyword"]):
                    continue
                dl_date = parse_german_date(cand.get("submission_deadline"))
                if dl_date is None or dl_date < tomorrow:
                    continue
                verified.append(cand)
            except Exception:
                continue

    if not verified:
        raise RuntimeError("No active future tenders extracted from service.bund.de.")

    (SAMPLES_DIR / "04_public_tenders_sample.json").write_text(
        json.dumps(verified, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    fields = list(verified[0].keys())
    with (SAMPLES_DIR / "04_public_tenders_sample.csv").open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for item in verified:
            w.writerow({k: (json.dumps(v, ensure_ascii=False) if isinstance(v, list) else v) for k, v in item.items()})

    print(f"[TENDERS] ✓ Wrote 04_public_tenders_sample ({len(verified)} active future rows).")
    return len(verified)


# ---------------------------------------------------------------------------
# External Hub Sync (Hugging Face & Kaggle)
# ---------------------------------------------------------------------------

def sync_external_hubs(today_str: str) -> None:
    hf_token = os.environ.get("HF_TOKEN", "").strip()
    if hf_token:
        from huggingface_hub import CommitOperationAdd, HfApi

        api = HfApi(token=hf_token)
        ops = []
        for fn in ["DE_Zwangsversteigerungen_Sample_50.csv", "DE_Zwangsversteigerungen_Sample_50.xlsx", "DE_Zwangsversteigerungen_Sample_50.json"]:
            ops.append(CommitOperationAdd(path_in_repo=fn, path_or_fileobj=str(SAMPLES_DIR / fn)))
        api.create_commit(
            repo_id="AGrunert/german-real-estate-foreclosures-zvg-sample",
            repo_type="dataset",
            operations=ops,
            commit_message=f"chore(auto-refresh): weekly active future ZVG Sample 50 ({today_str})",
        )
        print("[HUB] ✓ Updated Hugging Face Hub dataset (atomic commit).")
    else:
        print("[HUB] Skipping Hugging Face sync (HF_TOKEN not set).")

    kaggle_token = os.environ.get("KAGGLE_API_TOKEN", "").strip()
    if kaggle_token:
        from kaggle.api.kaggle_api_extended import KaggleApi

        k_api = KaggleApi()
        k_api.authenticate()
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            for fn in ["DE_Zwangsversteigerungen_Sample_50.csv", "DE_Zwangsversteigerungen_Sample_50.xlsx", "DE_Zwangsversteigerungen_Sample_50.json"]:
                shutil.copy2(SAMPLES_DIR / fn, tmp_dir / fn)
            shutil.copy2(Path(__file__).resolve().parent / "kaggle_dataset_metadata.json", tmp_dir / "dataset-metadata.json")
            k_api.dataset_metadata_update("andrgrunert/german-real-estate-foreclosures-zvg-sample", str(tmp_dir))
            k_api.dataset_create_version(
                folder=str(tmp_dir),
                version_notes=f"Automated weekly refresh: 50 verified future ZVG auctions ({today_str})",
                dir_mode="skip",
            )
        print("[HUB] ✓ Published new Kaggle Dataset version.")
    else:
        print("[HUB] Skipping Kaggle sync (KAGGLE_API_TOKEN not set).")


def main() -> None:
    parser = argparse.ArgumentParser(description="Refresh live B2B samples in german-b2b-data-suite.")
    parser.add_argument("--sync-hubs", action="store_true", help="Also push Sample 50 to Hugging Face & Kaggle when tokens are set.")
    args = parser.parse_args()

    today_berlin = berlin_now().date()
    tomorrow_berlin = today_berlin + timedelta(days=1)

    asyncio.run(refresh_zvg_samples(tomorrow_berlin))
    asyncio.run(refresh_tender_samples(tomorrow_berlin))

    if args.sync_hubs:
        sync_external_hubs(today_berlin.isoformat())


if __name__ == "__main__":
    main()
