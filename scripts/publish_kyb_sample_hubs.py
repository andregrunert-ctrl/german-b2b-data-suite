#!/usr/bin/env python3
"""
Publish the 50-row German Handelsregister & KYB Sample Dataset to
Hugging Face Hub (AGrunert/german-company-handelsregister-kyb-sample)
and Kaggle Datasets (andrgrunert/german-company-handelsregister-kyb-sample).
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
import sys
import tempfile
import time as _time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List

SUITE_DIR = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = Path(__file__).resolve().parent
SAMPLES_DIR = SUITE_DIR / "samples"
ENV_PATHS = [
    SUITE_DIR / ".env",
    SUITE_DIR.parent / ".env",
    Path(r"C:\Users\andre\ai-money\.env"),
]
KAGGLE_META_PATH = SCRIPTS_DIR / "kaggle_kyb_dataset_metadata.json"

if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

HF_REPO_ID = "AGrunert/german-company-handelsregister-kyb-sample"
KAGGLE_DATASET_ID = "andrgrunert/german-company-handelsregister-kyb-sample"

DATA_FILES = [
    "DE_Handelsregister_KYB_Sample_50.csv",
    "DE_Handelsregister_KYB_Sample_50.xlsx",
    "DE_Handelsregister_KYB_Sample_50.json",
]

HF_README = """---
language:
- de
license: cc0-1.0
multilinguality:
- monolingual
size_categories:
- n<1K
task_categories:
- tabular-classification
tags:
- handelsregister
- kyb
- germany
- b2b
- insolvency
- corporate-registry
- compliance
- dach
pretty_name: German Company Handelsregister & KYB Sample (50 Companies)
---

# German Company Handelsregister & KYB Sample (50 Verified Companies)

[![License: CC0-1.0](https://img.shields.io/badge/License-CC0_1.0-lightgrey.svg)](https://creativecommons.org/publicdomain/zero/1.0/)
[![Apify KYB Actor](https://img.shields.io/badge/Apify-German%20KYB%20Actor-FF7626?logo=apify&logoColor=white)](https://apify.com/AGrunert/german-company-kyb-insolvency-scraper)
[![Fiverr KYB Gig](https://img.shields.io/badge/Fiverr-Custom%20KYB%20Audit-1DBF73?logo=fiverr&logoColor=white)](https://www.fiverr.com/s/yeWblEA)
[![GitHub Suite](https://img.shields.io/badge/GitHub-German%20B2B%20Suite-blue?logo=github)](https://github.com/andregrunert-ctrl/german-b2b-data-suite)

A curated, live-verified 50-company Know-Your-Business (KYB) dataset of German corporations (`AG`, `SE`, `KGaA`, `GmbH`) extracted directly from the official German Federal Judicial Portals (`handelsregister.de` XJustiz 3.5.1 XML & `insolvenzbekanntmachungen.de`).

---

## Dataset Summary

- **Sources:** Official Common Register Portal (`www.handelsregister.de`) & Official German Insolvency Announcements (`www.insolvenzbekanntmachungen.de`).
- **Rows:** 50 unique verified German companies across federal states and district courts (*Amtsgerichte*), including blue-chip corporations, tech firms, and active/historical insolvency examples.
- **Included Files:**
  - `DE_Handelsregister_KYB_Sample_50.csv` (RFC 4180 UTF-8 CSV for Pandas & Hugging Face Dataset Viewer)
  - `DE_Handelsregister_KYB_Sample_50.xlsx` (Styled 2-sheet Excel workbook with freeze panes, currency formatting, risk status highlighting & state/legal-form pivot stats)
  - `DE_Handelsregister_KYB_Sample_50.json` (Flat JSON records array)

---

## Data Dictionary

| Column | Type | Description |
|---|---|---|
| `company_name` | string | Official registered corporate name |
| `kyb_risk_status` | string | `CLEAR` or `WARNING_INSOLVENCY_FOUND` |
| `state` | string | German federal state (*Bundesland*) |
| `register_court` | string | Competent district court (*Amtsgericht*) |
| `register_type` | string | Register section (`HRB`, `HRA`, `GnR`, `PR`, `VR`) |
| `register_number` | string | Official registration number |
| `register_id` | string | Combined ID (e.g. `HRB 48720`) |
| `legal_form` | string | Corporate legal form (`SE`, `Aktiengesellschaft`, `GmbH`, `KGaA`) |
| `status` | string | Current status (`aktuell`, `in Liquidation`, etc.) |
| `seat` | string | Registered corporate seat (*Sitz*) |
| `address` | string | Registered street address (*Geschäftsanschrift*) |
| `share_capital` | float | Registered share/nominal capital (`Stammkapital` / `Grundkapital`) |
| `currency` | string | Currency code (`EUR`) |
| `officers_count` | int | Total extracted directors, board members & *Prokuristen* |
| `managing_directors_sample` | string | Top managing directors / board / *Prokuristen* summary |
| `business_purpose` | string | Official registered business purpose (*Unternehmensgegenstand*) |
| `has_insolvency_record` | bool | Official insolvency match flag |
| `insolvency_cases_count` | int | Number of matched official insolvency publications |
| `insolvency_details` | string | Publication dates, courts & file numbers |
| `handelsregister_url` | string | Source portal URL |
| `scraped_at` | string | UTC extraction timestamp |

---

## Live API, Cloud Automation & Custom KYB Audits

- **Apify Cloud KYB Actor (Pay-Per-Event API):** [German Company KYB & Insolvency Scraper](https://apify.com/AGrunert/german-company-kyb-insolvency-scraper)
- **Order Bespoke KYB Bulk Lists & Due Diligence (Fiverr):** [Custom German Handelsregister & KYB Audit](https://www.fiverr.com/s/yeWblEA)
- **Open-Source Integration Suite (Python, n8n, Make.com, MCP):** [GitHub: german-b2b-data-suite](https://github.com/andregrunert-ctrl/german-b2b-data-suite)
"""


def load_env_file(path: Path) -> Dict[str, str]:
    loaded: Dict[str, str] = {}
    if not path.exists():
        return loaded
    for line in path.read_text(encoding="utf-8").splitlines():
        raw = line.strip()
        if not raw or raw.startswith("#") or "=" not in raw:
            continue
        k, v = raw.split("=", 1)
        key = k.strip()
        val = v.strip().strip('"').strip("'")
        if key and val and key not in os.environ:
            os.environ[key] = val
            loaded[key] = "***"
    return loaded


def refresh_local_kyb_timestamps() -> int:
    """Update `scraped_at` in 02_handelsregister_kyb_sample.json and rebuild CSV/JSON/XLSX artifacts."""
    from generate_kyb_sample_50 import save_outputs  # noqa: E402

    nested_path = SAMPLES_DIR / "02_handelsregister_kyb_sample.json"
    if not nested_path.is_file():
        raise FileNotFoundError(f"Missing nested KYB sample JSON: {nested_path}")

    nested_items: List[Dict[str, object]] = json.loads(nested_path.read_text(encoding="utf-8"))
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    for item in nested_items:
        item["scraped_at"] = now_iso

    save_outputs(nested_items)
    print(f"[REFRESH] ✓ Updated scraped_at={now_iso} and rebuilt 50-row KYB CSV/JSON/XLSX artifacts.")
    return len(nested_items)


def validate_local_sample() -> int:
    csv_path = SAMPLES_DIR / "DE_Handelsregister_KYB_Sample_50.csv"
    for fn in DATA_FILES:
        p = SAMPLES_DIR / fn
        if not p.exists() or p.stat().st_size == 0:
            raise FileNotFoundError(f"Missing or empty sample file: {p}")

    with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    if len(rows) != 50:
        raise ValueError(f"Expected 50 rows in {csv_path}, found {len(rows)}")
    missing_reg = [r.get("company_name") for r in rows if not (r.get("register_number") or "").strip()]
    if missing_reg:
        raise ValueError(f"Rows missing register_number: {missing_reg[:5]}")
    return len(rows)


def publish_huggingface(today_str: str) -> str:
    hf_token = os.environ.get("HF_TOKEN", "").strip()
    if not hf_token:
        print("[HF] Skipping Hugging Face sync (HF_TOKEN not set).")
        return ""

    from huggingface_hub import CommitOperationAdd, HfApi

    api = HfApi(token=hf_token)
    api.create_repo(
        repo_id=HF_REPO_ID,
        repo_type="dataset",
        private=False,
        exist_ok=True,
    )

    with tempfile.TemporaryDirectory() as tmp:
        readme_path = Path(tmp) / "README.md"
        readme_path.write_text(HF_README, encoding="utf-8")

        ops = [CommitOperationAdd(path_in_repo="README.md", path_or_fileobj=str(readme_path))]
        for fn in DATA_FILES:
            ops.append(CommitOperationAdd(path_in_repo=fn, path_or_fileobj=str(SAMPLES_DIR / fn)))

        api.create_commit(
            repo_id=HF_REPO_ID,
            repo_type="dataset",
            operations=ops,
            commit_message=f"feat(dataset): publish 50 verified German Handelsregister & KYB companies ({today_str})",
        )
    url = f"https://huggingface.co/datasets/{HF_REPO_ID}"
    print(f"[HF] ✓ Published public dataset: {url}")
    return url


def publish_kaggle(today_str: str) -> str:
    kaggle_token = os.environ.get("KAGGLE_API_TOKEN", "").strip()
    if not kaggle_token:
        print("[KAGGLE] Skipping Kaggle sync (KAGGLE_API_TOKEN not set).")
        return ""

    from kaggle.api.kaggle_api_extended import KaggleApi

    k_api = KaggleApi()
    k_api.authenticate()

    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        for fn in DATA_FILES:
            shutil.copy2(SAMPLES_DIR / fn, tmp_dir / fn)
        shutil.copy2(KAGGLE_META_PATH, tmp_dir / "dataset-metadata.json")

        exists = False
        try:
            status = k_api.dataset_status(KAGGLE_DATASET_ID)
            if status:
                exists = True
        except Exception:
            exists = False

        if exists:
            k_api.dataset_metadata_update(KAGGLE_DATASET_ID, str(tmp_dir))
            k_api.dataset_create_version(
                folder=str(tmp_dir),
                version_notes=f"Published 50 verified German Handelsregister & KYB companies ({today_str})",
                convert_to_csv=False,
                dir_mode="skip",
            )
            print(f"[KAGGLE] ✓ Updated existing dataset: {KAGGLE_DATASET_ID}")
        else:
            resp = k_api.dataset_create_new(
                folder=str(tmp_dir),
                public=True,
                quiet=False,
                convert_to_csv=False,
                dir_mode="skip",
            )
            print(f"[KAGGLE] ✓ Created new public dataset: {resp}")

    url = f"https://www.kaggle.com/datasets/{KAGGLE_DATASET_ID}"
    print(f"[KAGGLE] ✓ URL: {url}")
    return url


def _cc_record(task_id: str, status: str, duration_ms: float, msg: str, err: str = "") -> None:
    try:
        cc_dir = r"C:\Users\andre\command-center"
        if os.path.isdir(cc_dir):
            if cc_dir not in sys.path:
                sys.path.insert(0, cc_dir)
            import heartbeat as _hb
            _hb.record_heartbeat(task_id, status=status, duration_ms=duration_ms, message=msg, error_log=err)
    except Exception:
        pass


def main() -> None:
    t0 = _time.perf_counter()
    parser = argparse.ArgumentParser(description="Refresh & publish KYB Sample 50 to Hugging Face and Kaggle.")
    parser.add_argument(
        "--refresh-timestamps",
        action="store_true",
        help="Update scraped_at in 02_handelsregister_kyb_sample.json and rebuild CSV/JSON/XLSX before publishing.",
    )
    parser.add_argument(
        "--local-only",
        action="store_true",
        help="Rebuild/validate local KYB samples without pushing to external hubs.",
    )
    args = parser.parse_args()

    try:
        for env_p in ENV_PATHS:
            load_env_file(env_p)

        if args.refresh_timestamps:
            refresh_local_kyb_timestamps()

        row_count = validate_local_sample()
        today_str = datetime.now(timezone.utc).date().isoformat()
        print(f"[PRECHECK] ✓ Verified {row_count} local KYB sample rows.")

        hf_url = ""
        kaggle_url = ""
        if not args.local_only:
            hf_url = publish_huggingface(today_str)
            kaggle_url = publish_kaggle(today_str)
        print(f"[DONE] HF={hf_url or 'skipped'} | KAGGLE={kaggle_url or 'skipped'}")
    except Exception as exc:
        _cc_record("kyb_sample_hub_sync", "FAILED", (_time.perf_counter() - t0) * 1000.0, str(exc), str(exc))
        raise
    else:
        _cc_record(
            "kyb_sample_hub_sync",
            "OK",
            (_time.perf_counter() - t0) * 1000.0,
            f"KYB Sample 50 synced (refresh_timestamps={args.refresh_timestamps}, hf={bool(hf_url)}, kaggle={bool(kaggle_url)})",
        )


if __name__ == "__main__":
    main()
