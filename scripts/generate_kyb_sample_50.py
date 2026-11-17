#!/usr/bin/env python3
"""
Generate a 50-row live-verified German Handelsregister & KYB Sample Dataset
using the local KYB engine in C:\\Users\\andre\\apify\\apify-german-kyb-actor.

Outputs in C:\\Users\\andre\\apify\\german-b2b-data-suite\\samples\\:
  - DE_Handelsregister_KYB_Sample_50.csv (RFC 4180 flat tabular CSV)
  - 02_handelsregister_kyb_sample.csv    (50-row replacement in showcase samples/)
  - DE_Handelsregister_KYB_Sample_50.xlsx (Formatted 2-sheet Excel workbook)
  - DE_Handelsregister_KYB_Sample_50.json (Clean flat JSON array)
  - 02_handelsregister_kyb_sample.json   (Full KybCheckResult nested JSON array)
"""

from __future__ import annotations

import asyncio
import csv
import json
import os
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import openpyxl
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from upsell_helpers import (  # noqa: E402
    APIFY_KYB_URL,
    APIFY_PROFILE_URL,
    FIVERR_KYB_URL,
    GUMROAD_ZVG_URL,
    apply_sheet1_upsell_banner,
    apply_sheet2_upsell_infobox,
    wrap_sample_json_with_meta,
    write_full_records_txt,
)

SUITE_DIR = Path(__file__).resolve().parent.parent
SAMPLES_DIR = SUITE_DIR / "samples"
KYB_ACTOR_DIR = SUITE_DIR.parent / "apify-german-kyb-actor"
CACHE_PATH = Path(
    os.environ.get("KYB_CACHE_PATH", str(SAMPLES_DIR / ".kyb_sample_cache.json"))
)

if str(KYB_ACTOR_DIR) not in sys.path:
    sys.path.insert(0, str(KYB_ACTOR_DIR))

try:
    from src.core.handelsregister import HandelsregisterClient  # type: ignore # noqa: E402
    from src.core.insolvenz import InsolvenzClient  # type: ignore # noqa: E402
    from src.core.models import KybCheckResult  # type: ignore # noqa: E402
except ImportError:
    HandelsregisterClient = None  # type: ignore[assignment,misc]
    InsolvenzClient = None  # type: ignore[assignment,misc]
    KybCheckResult = None  # type: ignore[assignment,misc]


CANDIDATE_COMPANIES: List[Tuple[str, Optional[str], Optional[str]]] = [
    ("BioNTech SE", "Mainz", "48720"),
    ("SAP SE", "Walldorf", None),
    ("Siemens Aktiengesellschaft", "Berlin", "12300"),
    ("Deutsche Börse Aktiengesellschaft", "Frankfurt am Main", "32232"),
    ("BASF SE", "Ludwigshafen", None),
    ("Zalando SE", "Berlin", None),
    ("Delivery Hero SE", "Berlin", None),
    ("HelloFresh SE", "Berlin", None),
    ("AUTO1 Group SE", "Berlin", None),
    ("N26 Bank AG", "Berlin", None),
    ("Deutsche Telekom AG", "Bonn", None),
    ("Deutsche Post AG", "Bonn", None),
    ("Deutsche Bank Aktiengesellschaft", "Frankfurt am Main", None),
    ("COMMERZBANK Aktiengesellschaft", "Frankfurt am Main", None),
    ("Mercedes-Benz Group AG", "Stuttgart", None),
    ("VOLKSWAGEN AKTIENGESELLSCHAFT", "Wolfsburg", None),
    ("Bayer Aktiengesellschaft", "Leverkusen", None),
    ("Covestro AG", "Leverkusen", None),
    ("LANXESS Aktiengesellschaft", "Köln", None),
    ("Deutsche Lufthansa Aktiengesellschaft", "Köln", None),
    ("DeepL SE", "Köln", None),
    ("Ströer SE & Co. KGaA", "Köln", None),
    ("adidas AG", "Herzogenaurach", None),
    ("PUMA SE", "Herzogenaurach", None),
    ("Merck KGaA", "Darmstadt", None),
    ("Henkel AG & Co. KGaA", "Düsseldorf", None),
    ("GEA Group Aktiengesellschaft", "Düsseldorf", None),
    ("Rheinmetall Aktiengesellschaft", "Düsseldorf", None),
    ("Beiersdorf Aktiengesellschaft", "Hamburg", None),
    ("Fielmann Group AG", "Hamburg", None),
    ("Aurubis AG", "Hamburg", None),
    ("Heidelberg Materials AG", "Heidelberg", None),
    ("RWE Aktiengesellschaft", "Essen", None),
    ("E.ON SE", "Essen", None),
    ("Brenntag SE", "Essen", None),
    ("Evonik Industries AG", "Essen", None),
    ("HOCHTIEF Aktiengesellschaft", "Essen", None),
    ("GALERIA Karstadt Kaufhof GmbH", "Essen", None),
    ("Esprit Europe GmbH", "Ratingen", None),
    ("Vonovia SE", "Bochum", None),
    ("Fresenius SE & Co. KGaA", "Bad Homburg", None),
    ("Sartorius Aktiengesellschaft", "Göttingen", None),
    ("Symrise AG", "Holzminden", None),
    ("Continental Aktiengesellschaft", "Hannover", None),
    ("Hannover Rück SE", "Hannover", None),
    ("TUI AG", "Hannover", None),
    ("Talanx AG", "Hannover", None),
    ("Salzgitter Aktiengesellschaft", "Salzgitter", None),
    ("TeamViewer SE", "Göppingen", None),
    ("Carl Zeiss Meditec AG", "Jena", None),
    ("FUCHS SE", "Mannheim", None),
    ("Bilfinger SE", "Mannheim", None),
    ("K+S Aktiengesellschaft", "Kassel", None),
    ("Bechtle AG", "Neckarsulm", None),
    ("AIXTRON SE", "Herzogenrath", None),
    ("KION GROUP AG", "Frankfurt am Main", None),
    ("flatexDEGIRO AG", "Frankfurt am Main", None),
    ("Hugo Boss AG", "Metzingen", None),
    ("Robert Bosch Gesellschaft mit beschränkter Haftung", "Stuttgart", None),
    ("Dürr Aktiengesellschaft", "Bietigheim-Bissingen", None),
    ("United Internet AG", "Montabaur", None),
    ("1&1 AG", "Montabaur", None),
    ("IONOS Group SE", "Montabaur", None),
    ("Aareal Bank AG", "Wiesbaden", None),
    ("Heidelberger Druckmaschinen Aktiengesellschaft", "Heidelberg", None),
    ("VARTA Aktiengesellschaft", "Ellwangen", None),
    ("Jungheinrich Aktiengesellschaft", "Hamburg", None),
    ("Tag Immobilien AG", "Hamburg", None),
    ("Fraport AG Frankfurt Airport Services Worldwide", "Frankfurt am Main", None),
    ("Infineon Technologies AG", "Neubiberg", None),
    ("SIXT SE", "Pullach", None),
    ("Celonis SE", "München", None),
    ("Siemens Energy AG", "München", None),
    ("Siemens Healthineers AG", "München", None),
    ("NEMETSCHEK SE", "München", None),
    ("Scout24 SE", "München", None),
    ("Knorr-Bremse Aktiengesellschaft", "München", None),
    ("MTU Aero Engines AG", "München", None),
    ("Personio SE", "München", None),
    ("Flix SE", "München", None),
    ("RATIONAL Aktiengesellschaft", "Landsberg am Lech", None),
    ("TRATON SE", "München", None),
    ("Wacker Chemie AG", "München", None),
    ("CTS Eventim AG & Co. KGaA", "München", None),
    ("Elektro Bleumortier GmbH", "München", "64526"),
]


STATE_NAME_MAP = {
    "Bayern": "Bayern",
    "Berlin": "Berlin",
    "Baden-Württemberg": "Baden-Württemberg",
    "Nordrhein-Westfalen": "Nordrhein-Westfalen",
    "Hessen": "Hessen",
    "Niedersachsen": "Niedersachsen",
    "Rheinland-Pfalz": "Rheinland-Pfalz",
    "Hamburg": "Hamburg",
    "Sachsen": "Sachsen",
    "Thüringen": "Thüringen",
    "Bremen": "Bremen",
    "Schleswig-Holstein": "Schleswig-Holstein",
    "Brandenburg": "Brandenburg",
    "Saarland": "Saarland",
    "Sachsen-Anhalt": "Sachsen-Anhalt",
    "Mecklenburg-Vorpommern": "Mecklenburg-Vorpommern",
}

CITY_TO_STATE = {
    "münchen": "Bayern", "herzogenaurach": "Bayern", "neubiberg": "Bayern",
    "landsberg": "Bayern", "pullach": "Bayern", "fürth": "Bayern", "augsburg": "Bayern",
    "mainz": "Rheinland-Pfalz", "ludwigshafen": "Rheinland-Pfalz",
    "walldorf": "Baden-Württemberg", "stuttgart": "Baden-Württemberg", "heidelberg": "Baden-Württemberg",
    "göppingen": "Baden-Württemberg", "mannheim": "Baden-Württemberg", "neckarsulm": "Baden-Württemberg",
    "metzingen": "Baden-Württemberg", "karlsruhe": "Baden-Württemberg",
    "berlin": "Berlin", "charlottenburg": "Berlin",
    "frankfurt": "Hessen", "darmstadt": "Hessen", "bad homburg": "Hessen", "kassel": "Hessen", "eschborn": "Hessen",
    "leverkusen": "Nordrhein-Westfalen", "bonn": "Nordrhein-Westfalen", "düsseldorf": "Nordrhein-Westfalen",
    "essen": "Nordrhein-Westfalen", "bochum": "Nordrhein-Westfalen", "köln": "Nordrhein-Westfalen",
    "ratingen": "Nordrhein-Westfalen", "herzogenrath": "Nordrhein-Westfalen", "siegburg": "Nordrhein-Westfalen",
    "kleve": "Nordrhein-Westfalen", "aachen": "Nordrhein-Westfalen", "montabaur": "Rheinland-Pfalz",
    "wolfsburg": "Niedersachsen", "göttingen": "Niedersachsen", "holzminden": "Niedersachsen",
    "hannover": "Niedersachsen", "hildesheim": "Niedersachsen", "braunschweig": "Niedersachsen",
    "salzgitter": "Niedersachsen",
    "hamburg": "Hamburg",
    "jena": "Thüringen",
    "wiesbaden": "Hessen",
    "bietigheim": "Baden-Württemberg", "ellwangen": "Baden-Württemberg",
    "bremen": "Bremen", "dresden": "Sachsen", "leipzig": "Sachsen",
}


def resolve_state(raw_state: Optional[str], court: Optional[str], seat: Optional[str]) -> str:
    if raw_state:
        for k, v in STATE_NAME_MAP.items():
            if k.lower() in raw_state.lower():
                return v
    blob = f"{court or ''} {seat or ''}".lower()
    for city_kw, st in CITY_TO_STATE.items():
        if city_kw in blob:
            return st
    return raw_state or "Deutschland (Sonstige)"


def clean_text(val: Optional[str], max_len: int = 0) -> str:
    if not val:
        return ""
    s = re.sub(r"\s+", " ", str(val)).strip()
    if max_len > 0 and len(s) > max_len:
        return s[: max_len - 3].rstrip() + "..."
    return s


def summarize_officers(officers: List[Dict[str, Any]], limit: int = 6) -> str:
    if not officers:
        return ""

    def priority(o: Dict[str, Any]) -> int:
        role = (o.get("role") or "").lower()
        if any(k in role for k in ("vorstand", "geschäftsführer", "persönlich haftend", "inhaber", "liquidator")):
            return 0
        if "prokurist" in role:
            return 1
        return 2

    ranked = sorted(officers, key=priority)
    parts: List[str] = []
    seen = set()
    for o in ranked:
        name = clean_text(o.get("full_name"))
        role = clean_text(o.get("role"))
        if not name or (name, role) in seen:
            continue
        seen.add((name, role))
        parts.append(f"{name} ({role})" if role else name)
        if len(parts) >= limit:
            break
    if len(officers) > len(parts):
        parts.append(f"+{len(officers) - len(parts)} weitere")
    return " ; ".join(parts)


def to_flat_row(nested_item: Dict[str, Any]) -> Dict[str, Any]:
    hr = nested_item.get("handelsregister") or {}
    ins = nested_item.get("insolvency") or {}
    officers = nested_item.get("officers") or hr.get("officers") or []
    anns = ins.get("announcements") or []
    ins_details = " | ".join(
        f"{a.get('publication_date', '')} {a.get('court', '')} {a.get('file_number', '')}".strip()
        for a in anns[:3]
    )
    reg_type = nested_item.get("register_type") or hr.get("register_type") or ""
    reg_num = nested_item.get("register_number") or hr.get("register_number") or ""
    court = nested_item.get("register_court") or hr.get("court") or ""
    seat = nested_item.get("seat") or hr.get("seat") or ""
    state = resolve_state(hr.get("state"), court, seat)
    cap = nested_item.get("share_capital")
    return {
        "company_name": clean_text(nested_item.get("company_name")),
        "kyb_risk_status": clean_text(nested_item.get("kyb_risk_status")),
        "state": state,
        "register_court": clean_text(court),
        "register_type": clean_text(reg_type),
        "register_number": clean_text(reg_num),
        "register_id": f"{reg_type} {reg_num}".strip(),
        "legal_form": clean_text(nested_item.get("legal_form") or hr.get("legal_form")),
        "status": clean_text(nested_item.get("status") or hr.get("status") or "aktuell"),
        "seat": clean_text(seat),
        "address": clean_text(nested_item.get("address") or hr.get("address")),
        "share_capital": float(cap) if cap is not None else None,
        "currency": clean_text(nested_item.get("currency") or hr.get("currency") or "EUR"),
        "officers_count": int(nested_item.get("officers_count") or len(officers)),
        "managing_directors_sample": summarize_officers(officers, limit=6),
        "business_purpose": clean_text(nested_item.get("business_purpose") or hr.get("business_purpose"), max_len=600),
        "has_insolvency_record": bool(nested_item.get("has_insolvency_record")),
        "insolvency_cases_count": int(nested_item.get("insolvency_cases_count") or 0),
        "insolvency_details": clean_text(ins_details),
        "handelsregister_url": "https://www.handelsregister.de/rp_web/welcome.xhtml",
        "scraped_at": clean_text(nested_item.get("scraped_at")),
    }


def write_kyb_sample_xlsx(
    rows: List[Dict[str, Any]],
    out_path: Path,
    *,
    include_upsell: bool = True,
) -> None:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Handelsregister KYB 2026"

    headers = [
        ("Unternehmen", "company_name", 38),
        ("KYB Risiko-Status", "kyb_risk_status", 24),
        ("Bundesland", "state", 22),
        ("Registergericht", "register_court", 30),
        ("Register-Nr.", "register_id", 15),
        ("Rechtsform", "legal_form", 34),
        ("Status", "status", 12),
        ("Sitz", "seat", 20),
        ("Geschäftsanschrift", "address", 38),
        ("Stamm-/Grundkapital", "share_capital", 20),
        ("Währung", "currency", 10),
        ("Organe / Prokuristen", "officers_count", 16),
        ("Geschäftsführung & Vorstand (Auszug)", "managing_directors_sample", 48),
        ("Insolvenz-Treffer", "has_insolvency_record", 16),
        ("Insolvenz-Verfahren", "insolvency_cases_count", 16),
        ("Insolvenz-Details", "insolvency_details", 38),
        ("Unternehmensgegenstand", "business_purpose", 60),
        ("Abrufzeitpunkt (UTC)", "scraped_at", 24),
    ]

    hdr_fill = PatternFill(start_color="0F2C59", end_color="0F2C59", fill_type="solid")
    hdr_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    zebra_fill = PatternFill(start_color="F5F8FC", end_color="F5F8FC", fill_type="solid")
    warn_fill = PatternFill(start_color="FEE2E2", end_color="FEE2E2", fill_type="solid")
    warn_font = Font(name="Calibri", size=10, bold=True, color="991B1B")
    ok_fill = PatternFill(start_color="DCFCE7", end_color="DCFCE7", fill_type="solid")
    ok_font = Font(name="Calibri", size=10, bold=True, color="166534")
    body_font = Font(name="Calibri", size=10)
    thin = Side(style="thin", color="D9E1EC")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)

    header_row = 1
    if include_upsell:
        header_row = apply_sheet1_upsell_banner(
            ws,
            col_count=len(headers),
            primary_text=(
                f"⚡ KOSTENLOSES 50er-KYB-SAMPLE — Live Handelsregister & Insolvenz-API ($5 Free Credits): {APIFY_KYB_URL} "
                f"| ZVG-Masterpaket (2.965+ Termine): {GUMROAD_ZVG_URL}"
            ),
            primary_url=APIFY_KYB_URL,
            secondary_text=(
                f"🚀 Komplettpaket (2.965+ Termine) auf Gumroad: {GUMROAD_ZVG_URL} | "
                f"Alle 6 German B2B Actors: {APIFY_PROFILE_URL} | Fiverr Audit: {FIVERR_KYB_URL}"
            ),
            secondary_url=GUMROAD_ZVG_URL,
        )

    for col_idx, (label, _, width) in enumerate(headers, start=1):
        c = ws.cell(row=header_row, column=col_idx, value=label)
        c.fill = hdr_fill
        c.font = hdr_font
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        ws.column_dimensions[get_column_letter(col_idx)].width = width
    ws.row_dimensions[header_row].height = 28

    data_start = header_row + 1
    for r_idx, row in enumerate(rows, start=data_start):
        for col_idx, (_, key, _) in enumerate(headers, start=1):
            val = row.get(key)
            cell = ws.cell(row=r_idx, column=col_idx)
            cell.font = body_font
            cell.border = border
            if r_idx % 2 == 1:
                cell.fill = zebra_fill

            if key == "share_capital":
                cell.value = float(val) if val is not None else None
                cell.number_format = "#,##0.00"
                cell.alignment = Alignment(horizontal="right", vertical="top")
            elif key in ("officers_count", "insolvency_cases_count"):
                cell.value = int(val) if val is not None else 0
                cell.number_format = "#,##0"
                cell.alignment = Alignment(horizontal="right", vertical="top")
            elif key == "kyb_risk_status":
                cell.value = val
                cell.alignment = Alignment(horizontal="center", vertical="top")
                if val == "WARNING_INSOLVENCY_FOUND":
                    cell.fill = warn_fill
                    cell.font = warn_font
                elif val == "CLEAR":
                    cell.fill = ok_fill
                    cell.font = ok_font
            elif key == "has_insolvency_record":
                cell.value = "JA" if val else "Nein"
                cell.alignment = Alignment(horizontal="center", vertical="top")
            else:
                cell.value = val if val != "" else None
                cell.alignment = Alignment(
                    vertical="top",
                    wrap_text=(key in ("company_name", "address", "managing_directors_sample", "business_purpose")),
                )

    ws.freeze_panes = f"A{data_start}"
    ws.auto_filter.ref = f"A{header_row}:{get_column_letter(len(headers))}{len(rows) + header_row}"

    # Sheet 2: Market & Compliance Overview
    ws2 = wb.create_sheet("KYB Statistik nach Land & Form")
    ws2["A1"] = "GERMAN COMPANY KYB & HANDELSREGISTER INTELLIGENCE - STATISTIK"
    ws2["A1"].font = Font(name="Calibri", size=14, bold=True, color="0F2C59")

    by_state: Dict[str, int] = defaultdict(int)
    by_form: Dict[str, int] = defaultdict(int)
    eur_capitals: List[float] = []
    total_officers = 0
    insolvency_hits = 0

    for row in rows:
        by_state[row["state"] or "Sonstige"] += 1
        by_form[row["legal_form"] or "Sonstige"] += 1
        if row.get("share_capital") and (row.get("currency") or "EUR") == "EUR":
            eur_capitals.append(float(row["share_capital"]))
        total_officers += int(row.get("officers_count") or 0)
        if row.get("has_insolvency_record"):
            insolvency_hits += 1

    kpis = [
        ("Verifizierte Unternehmen (Sample)", len(rows), "0"),
        ("Abgedeckte Bundesländer", len(by_state), "0"),
        ("Unternehmen mit Kapitalangabe (EUR)", len(eur_capitals), "0"),
        ("Summiertes Grund-/Stammkapital (€)", round(sum(eur_capitals), 2), "#,##0.00 €"),
        ("Erfasste Organe & Prokuristen gesamt", total_officers, "#,##0"),
        ("Live-Insolvenztreffer (WARNING)", insolvency_hits, "0"),
    ]
    for col_idx, label in enumerate(["Kennzahl (Live-Snapshot)", "Wert"], start=1):
        c = ws2.cell(3, col_idx, label)
        c.fill = hdr_fill
        c.font = hdr_font
        c.border = border
    for idx, (label, val, num_fmt) in enumerate(kpis, start=4):
        c1 = ws2.cell(idx, 1, label)
        c2 = ws2.cell(idx, 2, val)
        c1.border = border
        c2.border = border
        c2.number_format = num_fmt
        c2.alignment = Alignment(horizontal="right")

    def write_group_table(start_row: int, title: str, counts: Dict[str, int]) -> int:
        for col_idx, col_label in enumerate([title, "Unternehmen", "Anteil"], start=1):
            c = ws2.cell(start_row, col_idx, col_label)
            c.fill = hdr_fill
            c.font = hdr_font
            c.border = border
        r_ptr = start_row + 1
        total = max(1, sum(counts.values()))
        for k, cnt in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])):
            c1 = ws2.cell(r_ptr, 1, k)
            c2 = ws2.cell(r_ptr, 2, cnt)
            c3 = ws2.cell(r_ptr, 3, cnt / total)
            c2.alignment = Alignment(horizontal="right")
            c3.alignment = Alignment(horizontal="right")
            c3.number_format = "0.0%"
            for ci in range(1, 4):
                cell = ws2.cell(r_ptr, ci)
                cell.border = border
                if r_ptr % 2 == 1:
                    cell.fill = zebra_fill
            r_ptr += 1
        return r_ptr + 2

    tables_start = 11
    if include_upsell:
        tables_start = apply_sheet2_upsell_infobox(
            ws2,
            start_row=11,
            col_span=3,
            title="LIVE KYB-AUTOMATION & DATEN-KOMPLETTPAKETE",
            rows_spec=[
                (
                    f"🚀 Apify KYB & Insolvenz-Actor ($0.015/Audit, $5 Free Credits): {APIFY_KYB_URL}",
                    APIFY_KYB_URL,
                ),
                (
                    f"🛒 ZVG Komplettpaket auf Gumroad (2.965+ aktive Termine): {GUMROAD_ZVG_URL}",
                    GUMROAD_ZVG_URL,
                ),
                (
                    f"💼 Alle 6 German B2B Actors ({APIFY_PROFILE_URL}) | Individueller Fiverr KYB-Audit ({FIVERR_KYB_URL})",
                    FIVERR_KYB_URL,
                ),
            ],
        )

    next_r = write_group_table(tables_start, "Bundesland", by_state)
    write_group_table(next_r, "Rechtsform", by_form)
    for col_idx, w in enumerate([44, 18, 14], start=1):
        ws2.column_dimensions[get_column_letter(col_idx)].width = w

    wb.save(out_path)


async def fetch_50_companies(target_count: int = 50) -> List[Dict[str, Any]]:
    if HandelsregisterClient is None or InsolvenzClient is None or KybCheckResult is None:
        raise RuntimeError(
            f"apify-german-kyb-actor package not found at {KYB_ACTOR_DIR}; live Handelsregister scraping requires the actor repo."
        )
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    cached: Dict[str, Dict[str, Any]] = {}
    if CACHE_PATH.exists():
        try:
            cached = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
        except Exception:
            cached = {}

    hr_client = HandelsregisterClient(timeout=25.0, max_retries=2)
    ins_client = InsolvenzClient(timeout=20.0)
    results: List[Dict[str, Any]] = []
    seen_regs = set()
    pending_candidates: List[Tuple[int, str, Optional[str], Optional[str], str]] = []

    for idx, (c_name, c_city, c_reg) in enumerate(CANDIDATE_COMPANIES, start=1):
        if len(results) >= target_count:
            break

        cache_key = f"{c_name}|{c_city or ''}|{c_reg or ''}"
        if cache_key in cached:
            item = cached[cache_key]
            reg_sig = (item.get("register_court"), item.get("register_number"))
            if reg_sig not in seen_regs and item.get("register_number"):
                seen_regs.add(reg_sig)
                results.append(item)
                print(
                    f"[{len(results):02d}/{target_count}] (CACHED) {item['company_name']} -> "
                    f"{item['register_type']} {item['register_number']} | {item['kyb_risk_status']}",
                    flush=True,
                )
        else:
            pending_candidates.append((idx, c_name, c_city, c_reg, cache_key))

    if len(results) >= target_count:
        return results[:target_count]

    queue: asyncio.Queue[Tuple[int, str, Optional[str], Optional[str], str]] = asyncio.Queue()
    for cand in pending_candidates:
        queue.put_nowait(cand)

    state_lock = asyncio.Lock()

    async def process_one(
        idx: int, c_name: str, c_city: Optional[str], c_reg: Optional[str], cache_key: str
    ) -> None:
        print(f"[Query {idx}/{len(CANDIDATE_COMPANIES)}] {c_name} ({c_city})...", flush=True)
        try:
            async def _run_lookup():
                recs = await hr_client.search(
                    company_name=c_name,
                    city=c_city,
                    register_number=c_reg,
                    register_type="HRB",
                    include_details=True,
                    max_details=1,
                )
                if not recs:
                    return None
                primary = recs[0]
                stem_tokens = [
                    tok.lower()
                    for tok in re.split(r"[^a-zA-ZäöüÄÖÜß0-9]+", c_name)
                    if len(tok) >= 3 and tok.lower() not in {"ag", "se", "gmbh", "kgaa", "aktiengesellschaft", "gesellschaft", "beschränkter", "haftung", "und", "mit"}
                ]
                pname_low = primary.company_name.lower()
                if stem_tokens and not any(tok in pname_low for tok in stem_tokens):
                    return ("MISMATCH", primary, None)
                if not primary.register_number or primary.share_capital is None or len(primary.officers) == 0 or not primary.business_purpose:
                    return ("INCOMPLETE", primary, None)
                ins = await ins_client.check_insolvency(
                    company_name=primary.company_name,
                    city=primary.seat or c_city,
                    fetch_decree_details=False,
                )
                return ("OK", primary, ins)

            outcome = await asyncio.wait_for(_run_lookup(), timeout=45.0)
            if not outcome:
                print(f"   -> Skipped ({c_name}): not found on handelsregister.de", flush=True)
                return
            status_tag, primary, ins = outcome
            if status_tag in ("INCOMPLETE", "MISMATCH"):
                print(f"   -> Skipped ({c_name} -> {primary.company_name}): {status_tag}", flush=True)
                return

            risk = "WARNING_INSOLVENCY_FOUND" if ins.has_insolvency_record else "CLEAR"
            now_iso = datetime.now(timezone.utc).isoformat()
            kyb_res = KybCheckResult(
                company_name=primary.company_name,
                kyb_risk_status=risk,
                handelsregister=primary,
                insolvency=ins,
                scraped_at=now_iso,
            )
            item = kyb_res.model_dump()
            item["register_court"] = primary.court
            item["register_type"] = primary.register_type
            item["register_number"] = primary.register_number
            item["legal_form"] = primary.legal_form
            item["status"] = primary.status
            item["seat"] = primary.seat
            item["address"] = primary.address
            item["share_capital"] = primary.share_capital
            item["currency"] = primary.currency
            item["business_purpose"] = primary.business_purpose
            item["officers_count"] = len(primary.officers)
            item["officers"] = [o.model_dump() for o in primary.officers]
            item["has_insolvency_record"] = ins.has_insolvency_record
            item["insolvency_cases_count"] = ins.cases_count

            async with state_lock:
                if len(results) >= target_count:
                    return
                reg_sig = (primary.court, primary.register_number)
                if reg_sig in seen_regs:
                    print(f"   -> Skipped duplicate ({primary.company_name})", flush=True)
                    return
                seen_regs.add(reg_sig)
                results.append(item)
                cached[cache_key] = item
                CACHE_PATH.write_text(json.dumps(cached, indent=2, ensure_ascii=False), encoding="utf-8")
                print(
                    f"[{len(results):02d}/{target_count}] ✓ {primary.company_name} | {primary.register_type} {primary.register_number} "
                    f"| Cap={primary.share_capital} {primary.currency} | Officers={len(primary.officers)} | {risk}",
                    flush=True,
                )
        except asyncio.TimeoutError:
            print(f"   -> Timeout (>45s) on {c_name}; skipping fast.", flush=True)
        except Exception as exc:
            print(f"   -> Error on {c_name}: {type(exc).__name__}: {exc}", flush=True)

    async def worker(worker_id: int) -> None:
        if worker_id > 0:
            await asyncio.sleep(0.8 * worker_id)
        while not queue.empty():
            async with state_lock:
                if len(results) >= target_count:
                    break
            try:
                cand = queue.get_nowait()
            except asyncio.QueueEmpty:
                break
            try:
                await process_one(*cand)
            finally:
                queue.task_done()
            await asyncio.sleep(0.9)

    await asyncio.gather(*(worker(i) for i in range(2)))
    return results[:target_count]


def save_outputs(nested_items: List[Dict[str, Any]]) -> None:
    SAMPLES_DIR.mkdir(parents=True, exist_ok=True)
    flat_rows = [to_flat_row(it) for it in nested_items]

    # 1. DE_Handelsregister_KYB_Sample_50.csv + 02_handelsregister_kyb_sample.csv
    fields = list(flat_rows[0].keys())
    for csv_name in ("DE_Handelsregister_KYB_Sample_50.csv", "02_handelsregister_kyb_sample.csv"):
        with (SAMPLES_DIR / csv_name).open("w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            w.writerows(flat_rows)

    # 2. DE_Handelsregister_KYB_Sample_50.json (with upsell meta) + 02_handelsregister_kyb_sample.json
    kyb_json_payload = wrap_sample_json_with_meta(
        flat_rows,
        dataset_kind="DE_Handelsregister_KYB_Sample_50",
        actor_url=APIFY_KYB_URL,
        fiverr_url=FIVERR_KYB_URL,
        note=(
            "Curated 50-company German Handelsregister & Insolvency KYB sample. "
            f"Run unlimited live KYB checks at {APIFY_KYB_URL} or get the 2,965+ ZVG Foreclosures Master Dataset at {GUMROAD_ZVG_URL}"
        ),
    )
    (SAMPLES_DIR / "DE_Handelsregister_KYB_Sample_50.json").write_text(
        json.dumps(kyb_json_payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    (SAMPLES_DIR / "02_handelsregister_kyb_sample.json").write_text(
        json.dumps(nested_items, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    # 3. DE_Handelsregister_KYB_Sample_50.xlsx + 00_GET_FULL_2965_RECORDS.txt
    write_kyb_sample_xlsx(flat_rows, SAMPLES_DIR / "DE_Handelsregister_KYB_Sample_50.xlsx", include_upsell=True)
    write_full_records_txt(SAMPLES_DIR)
    print(f"\n✓ Wrote 50-row Handelsregister KYB datasets to {SAMPLES_DIR}", flush=True)


def main() -> None:
    items = asyncio.run(fetch_50_companies(50))
    if len(items) < 50:
        raise RuntimeError(f"Only collected {len(items)} verified companies; need 50.")
    save_outputs(items)


if __name__ == "__main__":
    main()
