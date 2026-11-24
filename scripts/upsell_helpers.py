#!/usr/bin/env python3
"""Shared in-file upsell builders (Excel banners, Info-Boxes, JSON meta, 00_GET_FULL_2965_RECORDS.txt)."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import openpyxl
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

GUMROAD_ZVG_URL = "https://grunertandre.gumroad.com/l/qklpqn"
APIFY_PROFILE_URL = "https://apify.com/AGrunert"
APIFY_ZVG_URL = "https://apify.com/AGrunert/german-real-estate-foreclosure-zvg-scraper"
APIFY_KYB_URL = "https://apify.com/AGrunert/german-company-kyb-insolvency-scraper"
APIFY_ZUGFERD_URL = "https://apify.com/AGrunert/german-e-invoice-zugferd-xrechnung-suite"
FIVERR_ZVG_URL = "https://de.fiverr.com/s/NeWDpEy"
FIVERR_KYB_URL = "https://www.fiverr.com/s/yeWblEA"
GITHUB_SUITE_URL = "https://github.com/andregrunert-ctrl/german-b2b-data-suite"
FULL_RECORDS_FILENAME = "00_GET_FULL_2965_RECORDS.txt"


def build_full_records_txt() -> str:
    """Return the content of 00_GET_FULL_2965_RECORDS.txt for GitHub, Hugging Face, and Kaggle."""
    return (
        "================================================================================\n"
        "  GET THE FULL NATIONWIDE DATASET (2,965+ ACTIVE RECORDS) & LIVE APIFY ACTORS\n"
        "================================================================================\n\n"
        "You downloaded the free 50-row curated preview sample.\n"
        "Need the complete daily-updated dataset or automated live API access?\n\n"
        "1. COMPLETE ZVG FORECLOSURE MASTER DATASET (2,965+ Active Auctions, All 16 States)\n"
        "   - Formats: Formatted Excel (.xlsx), CSV, JSON, Interactive HTML Explorer,\n"
        "     plus 1-click PDF Appraisal Batch Downloader (download_gutachten_pdfs.py)\n"
        "   - Zero expired or cancelled auctions (verified >= today)\n"
        f"   -> Instant Download on Gumroad: {GUMROAD_ZVG_URL}\n\n"
        "2. LIVE APIFY CLOUD ACTORS (6 Specialized DACH B2B & PropTech APIs, 13 Public Tasks)\n"
        "   - Free $5/month Apify Starter credits included for external accounts!\n"
        f"   - All 6 Actors Overview:           {APIFY_PROFILE_URL}\n"
        f"   - ZVG Foreclosure Scraper API:     {APIFY_ZVG_URL}\n"
        f"   - Handelsregister & KYB Audit API: {APIFY_KYB_URL}\n"
        f"   - ZUGFeRD / XRechnung E-Invoice:   {APIFY_ZUGFERD_URL}\n\n"
        "3. CUSTOM BULK EXTRACTS, AI AGENT MCP & n8n AUTOMATION\n"
        f"   - Custom ZVG Excel Delivery (Fiverr):       {FIVERR_ZVG_URL}\n"
        f"   - Custom KYB / Due Diligence (Fiverr):      {FIVERR_KYB_URL}\n"
        "   - Standalone Python MCP Server (PyPI):      pip install german-b2b-mcp / uvx german-b2b-mcp\n"
        "   - Official n8n Community Node (npm):        npm install n8n-nodes-german-b2b\n"
        f"   - Open-Source Integration Suite (GitHub):   {GITHUB_SUITE_URL}\n"
    )


def write_full_records_txt(target_dir: Path) -> Path:
    """Write 00_GET_FULL_2965_RECORDS.txt into `target_dir` using UTF-8 without BOM."""
    target_dir.mkdir(parents=True, exist_ok=True)
    out_path = target_dir / FULL_RECORDS_FILENAME
    out_path.write_text(build_full_records_txt(), encoding="utf-8")
    return out_path


def apply_sheet1_upsell_banner(
    ws: openpyxl.worksheet.worksheet.Worksheet,
    *,
    col_count: int,
    primary_text: str,
    primary_url: str,
    secondary_text: str,
    secondary_url: str,
) -> int:
    """Write a 2-row prominent hyperlinked upsell banner at the top of Sheet 1 and return header row index (3)."""
    last_col = get_column_letter(col_count)
    gold_fill = PatternFill(start_color="FEF3C7", end_color="FEF3C7", fill_type="solid")
    sub_fill = PatternFill(start_color="E8EEF7", end_color="E8EEF7", fill_type="solid")
    amber_side = Side(style="medium", color="D97706")
    thin_blue = Side(style="thin", color="93C5FD")

    ws.merge_cells(f"A1:{last_col}1")
    banner_text = (
        primary_text
        if primary_text.startswith("UPGRADE_TO_FULL_DATABASE:")
        else f'UPGRADE_TO_FULL_DATABASE: "{primary_url}" — {primary_text}'
    )
    c1 = ws.cell(row=1, column=1, value=banner_text)
    c1.hyperlink = primary_url
    c1.fill = gold_fill
    c1.font = Font(name="Calibri", size=11, bold=True, color="0F2C59", underline="single")
    c1.alignment = Alignment(horizontal="left", vertical="center", wrap_text=True)
    for col_idx in range(1, col_count + 1):
        cell = ws.cell(row=1, column=col_idx)
        cell.fill = gold_fill
        cell.border = Border(top=amber_side, bottom=amber_side, left=amber_side if col_idx == 1 else None, right=amber_side if col_idx == col_count else None)
    ws.row_dimensions[1].height = 30

    ws.merge_cells(f"A2:{last_col}2")
    c2 = ws.cell(row=2, column=1, value=secondary_text)
    c2.hyperlink = secondary_url
    c2.fill = sub_fill
    c2.font = Font(name="Calibri", size=10, bold=True, color="0563C1", underline="single")
    c2.alignment = Alignment(horizontal="left", vertical="center", wrap_text=True)
    for col_idx in range(1, col_count + 1):
        cell = ws.cell(row=2, column=col_idx)
        cell.fill = sub_fill
        cell.border = Border(bottom=thin_blue)
    ws.row_dimensions[2].height = 22

    return 3


def apply_sheet2_upsell_infobox(
    ws2: openpyxl.worksheet.worksheet.Worksheet,
    *,
    start_row: int,
    col_span: int,
    title: str,
    rows_spec: Sequence[Tuple[str, str]],
) -> int:
    """Write a framed hyperlinked Info-Box on Sheet 2 and return the next free row index."""
    last_col = get_column_letter(col_span)
    hdr_fill = PatternFill(start_color="B45309", end_color="B45309", fill_type="solid")
    box_fill = PatternFill(start_color="FFFBEB", end_color="FFFBEB", fill_type="solid")
    hdr_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    link_font = Font(name="Calibri", size=10, bold=True, color="0563C1", underline="single")
    edge = Side(style="medium", color="D97706")
    inner = Side(style="thin", color="FCD34D")

    ws2.merge_cells(f"A{start_row}:{last_col}{start_row}")
    ch = ws2.cell(row=start_row, column=1, value=title)
    ch.fill = hdr_fill
    ch.font = hdr_font
    ch.alignment = Alignment(horizontal="left", vertical="center")
    for ci in range(1, col_span + 1):
        c = ws2.cell(row=start_row, column=ci)
        c.fill = hdr_fill
        c.border = Border(top=edge, bottom=inner, left=edge if ci == 1 else None, right=edge if ci == col_span else None)
    ws2.row_dimensions[start_row].height = 24

    cur = start_row + 1
    for idx, (label, url) in enumerate(rows_spec):
        is_last = idx == len(rows_spec) - 1
        ws2.merge_cells(f"A{cur}:{last_col}{cur}")
        cell = ws2.cell(row=cur, column=1, value=label)
        cell.hyperlink = url
        cell.fill = box_fill
        cell.font = link_font
        cell.alignment = Alignment(horizontal="left", vertical="center", wrap_text=True)
        for ci in range(1, col_span + 1):
            c = ws2.cell(row=cur, column=ci)
            c.fill = box_fill
            c.border = Border(
                top=inner,
                bottom=edge if is_last else inner,
                left=edge if ci == 1 else None,
                right=edge if ci == col_span else None,
            )
        ws2.row_dimensions[cur].height = 22
        cur += 1

    return cur + 1


def add_upgrade_column_to_csv_rows(
    rows: Sequence[Dict[str, Any]],
    *,
    upgrade_url: str = GUMROAD_ZVG_URL,
) -> Tuple[List[str], List[Dict[str, Any]]]:
    """Prepend `UPGRADE_TO_FULL_DATABASE` as the first CSV column so Python/pandas users see it immediately."""
    if not rows:
        return ["UPGRADE_TO_FULL_DATABASE"], []
    base_fields = [k for k in rows[0].keys() if k != "UPGRADE_TO_FULL_DATABASE"]
    fieldnames = ["UPGRADE_TO_FULL_DATABASE", *base_fields]
    enriched = [{"UPGRADE_TO_FULL_DATABASE": upgrade_url, **r} for r in rows]
    return fieldnames, enriched


def wrap_sample_json_with_meta(
    records: List[Dict[str, Any]],
    *,
    dataset_kind: str,
    actor_url: str,
    fiverr_url: str,
    note: str,
    extra_meta: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Wrap sample records with explicit `UPGRADE_TO_FULL_DATABASE` & `_meta_full_dataset_download` metadata."""
    payload: Dict[str, Any] = {
        "UPGRADE_TO_FULL_DATABASE": GUMROAD_ZVG_URL,
        "_meta_dataset_type": dataset_kind,
        "_meta_sample_records": len(records),
        "_meta_full_dataset_active_records": "2,965+",
        "_meta_full_dataset_download": GUMROAD_ZVG_URL,
        "_meta_apify_actor": actor_url,
        "_meta_apify_suite": APIFY_PROFILE_URL,
        "_meta_fiverr_gig": fiverr_url,
        "_meta_github_repo": GITHUB_SUITE_URL,
        "_meta_note": note,
        "_meta_generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    if extra_meta:
        payload.update(extra_meta)
    payload["records"] = records
    return payload
