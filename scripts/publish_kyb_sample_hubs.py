#!/usr/bin/env python3
"""
Publish the 50-row German Handelsregister & KYB Sample Dataset to
Hugging Face Hub (AGrunert/german-company-handelsregister-kyb-sample)
and Kaggle Datasets (andrgrunert/german-company-handelsregister-kyb-sample).
"""

from __future__ import annotations

import csv
import os
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict

SUITE_DIR = Path(__file__).resolve().parent.parent
SAMPLES_DIR = SUITE_DIR / "samples"
ENV_PATH = SUITE_DIR.parent / ".env"
KAGGLE_META_PATH = Path(__file__).resolve().parent / "kaggle_kyb_dataset_metadata.json"

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
        raise RuntimeError("HF_TOKEN missing in environment / .env")

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
        raise RuntimeError("KAGGLE_API_TOKEN missing in environment / .env")

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


def main() -> None:
    load_env_file(ENV_PATH)
    row_count = validate_local_sample()
    today_str = datetime.now(timezone.utc).date().isoformat()
    print(f"[PRECHECK] ✓ Verified {row_count} local KYB sample rows.")
    hf_url = publish_huggingface(today_str)
    kaggle_url = publish_kaggle(today_str)
    print(f"[DONE] HF={hf_url} | KAGGLE={kaggle_url}")


if __name__ == "__main__":
    main()
