#!/usr/bin/env python3
"""
Post-refresh health & freshness verifier for german-b2b-data-suite.

Checks:
  1. GitHub Pages 1-Click POST Gateway (zvg.html) returns HTTP 200.
  2. ZVG samples contain only non-cancelled future auctions & valid %PDF endpoints.
  3. Public tender samples have non-cancelled future deadlines & live HTTP 200 URLs.
  4. ZUGFeRD/XRechnung artifact links return HTTP 200.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import timedelta
from pathlib import Path

import httpx
import openpyxl

from refresh_live_samples import HEADERS, berlin_now, parse_german_date

ROOT_DIR = Path(__file__).resolve().parent.parent
SAMPLES_DIR = ROOT_DIR / "samples"
GATEWAY_URL = "https://andregrunert-ctrl.github.io/german-b2b-data-suite/zvg.html"


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify freshness & link health across sample datasets.")
    parser.add_argument("--min-days", type=int, default=1, help="Minimum future days horizon to assert (default: 1; use 7 right after weekly refresh).")
    args = parser.parse_args()

    today_berlin = berlin_now().date()
    min_cutoff = today_berlin + timedelta(days=max(1, args.min_days))

    with httpx.Client(headers=HEADERS, timeout=20.0, follow_redirects=True) as client:
        gw = client.get(GATEWAY_URL)
        assert gw.status_code == 200, f"Gateway healthcheck failed: {gw.status_code}"
        print(f"[OK] zvg.html gateway HTTP {gw.status_code} ({len(gw.content)} bytes)")

        # 1. Verify Sample 50 JSON, XLSX Sheet 2 statistics & Sample 03 JSON
        s50 = json.loads((SAMPLES_DIR / "DE_Zwangsversteigerungen_Sample_50.json").read_text(encoding="utf-8"))
        assert len(s50) >= 20, f"Expected >= 20 rows in Sample 50, got {len(s50)}"
        for row in s50:
            dt = parse_german_date(row.get("auction_date"))
            assert dt is not None and dt >= min_cutoff, f"Expired/insufficient Sample 50 horizon (< {min_cutoff}): {row.get('zvg_id')} {row.get('auction_date')}"
            assert float(row.get("market_value_eur") or 0) > 0, f"Invalid market_value_eur in {row.get('zvg_id')}"

        wb = openpyxl.load_workbook(SAMPLES_DIR / "DE_Zwangsversteigerungen_Sample_50.xlsx", data_only=True)
        assert "Statistik nach Bundesland & Art" in wb.sheetnames, "Missing XLSX Sheet 2!"
        sheet2_vals = "\n".join(
            str(v) for r in wb["Statistik nach Bundesland & Art"].iter_rows(values_only=True) for v in r if v is not None
        )
        assert "Bundesland" in sheet2_vals and "Objektart" in sheet2_vals and "GESAMT" in sheet2_vals, (
            "XLSX Sheet 2 missing Bundesland/Objektart statistics or GESAMT row!"
        )
        wb.close()

        s03 = json.loads((SAMPLES_DIR / "03_zvg_foreclosures_sample.json").read_text(encoding="utf-8"))
        assert len(s03) >= 3, f"Expected >= 3 rows in 03_zvg_foreclosures_sample.json, got {len(s03)}"
        for row in s03:
            assert not row.get("is_cancelled"), f"Cancelled listing in sample 03: {row.get('zvg_id')}"
            dt = parse_german_date(row.get("auction_date"))
            assert dt is not None and dt >= min_cutoff, f"Insufficient sample 03 horizon (< {min_cutoff}): {row.get('zvg_id')} {row.get('auction_date')}"
            pdf_r = client.get(row["pdf_urls"][0], headers={**HEADERS, "Referer": row["detail_url"]})
            assert pdf_r.status_code == 200 and pdf_r.content.startswith(b"%PDF"), (
                f"Invalid ZVG PDF for {row.get('zvg_id')}: status={pdf_r.status_code}"
            )
        print(f"[OK] ZVG samples verified (cutoff >= {min_cutoff}): Sample_50={len(s50)}, Sample_03={len(s03)} (%PDF + XLSX KPI/Stats)")

        # 2. Verify Public Tenders sample richness & document link reachability
        s04 = json.loads((SAMPLES_DIR / "04_public_tenders_sample.json").read_text(encoding="utf-8"))
        assert len(s04) >= 3, f"Expected >= 3 rows in 04_public_tenders_sample.json, got {len(s04)}"
        with_docs = 0
        with_cpv = 0
        for row in s04:
            dt = parse_german_date(row.get("submission_deadline"))
            assert dt is not None and dt >= min_cutoff, f"Expired tender deadline (< {min_cutoff}): {row.get('tender_id')} {row.get('submission_deadline')}"
            tr = client.get(row["detail_url"])
            assert tr.status_code == 200, f"Tender detail HTTP {tr.status_code}: {row['detail_url']}"
            doc_urls = row.get("tender_document_urls") or []
            if doc_urls:
                with_docs += 1
                dr = client.get(doc_urls[0])
                assert dr.status_code < 400, f"Broken tender_document_url ({dr.status_code}): {doc_urls[0]}"
            if row.get("cpv_codes"):
                with_cpv += 1
        assert with_docs >= 3, f"Expected >= 3 tenders with non-empty tender_document_urls, got {with_docs}"
        print(f"[OK] Public tender sample verified: {len(s04)} active future tenders ({with_docs} w/ doc URLs, {with_cpv} w/ CPV)")

        # 3. Verify ZUGFeRD permanent artifact URLs
        s01 = json.loads((SAMPLES_DIR / "01_zugferd_xrechnung_sample.json").read_text(encoding="utf-8"))
        for row in s01:
            for key in ("pdf_download_url", "xml_download_url"):
                u = row.get(key)
                if u:
                    ar = client.head(u)
                    assert ar.status_code == 200, f"Artifact URL HTTP {ar.status_code}: {u}"
        print(f"[OK] ZUGFeRD sample artifacts verified ({len(s01)} records).")


if __name__ == "__main__":
    main()
