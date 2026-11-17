import sys
from pathlib import Path

import openpyxl

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import generate_kyb_sample_50 as gks  # noqa: E402


def test_to_flat_row_and_xlsx_workbook(tmp_path):
    nested = {
        "company_name": "BioNTech SE",
        "kyb_risk_status": "CLEAR",
        "register_court": "Amtsgericht Mainz",
        "register_type": "HRB",
        "register_number": "48720",
        "legal_form": "SE",
        "status": "aktuell",
        "seat": "Mainz",
        "address": "An der Goldgrube 12, 55131 Mainz",
        "share_capital": 259027487.0,
        "currency": "EUR",
        "officers_count": 2,
        "officers": [
            {"full_name": "Prof. Dr. Ugur Sahin", "role": "Vorstand"},
            {"full_name": "Dr. Özlem Türeci", "role": "Vorstand"},
        ],
        "business_purpose": "Forschung und Entwicklung im Bereich Immuntherapie.",
        "has_insolvency_record": False,
        "insolvency_cases_count": 0,
        "insolvency": {"announcements": []},
        "handelsregister": {"state": None, "seat": "Mainz"},
        "scraped_at": "2026-11-16T08:00:00+00:00",
    }

    flat = gks.to_flat_row(nested)
    assert flat["state"] == "Rheinland-Pfalz"
    assert flat["register_id"] == "HRB 48720"
    assert "Prof. Dr. Ugur Sahin (Vorstand)" in flat["managing_directors_sample"]

    out_xlsx = tmp_path / "DE_Handelsregister_KYB_Sample_50.xlsx"
    gks.write_kyb_sample_xlsx([flat], out_xlsx)

    wb = openpyxl.load_workbook(out_xlsx, data_only=True)
    assert wb.sheetnames == ["Handelsregister KYB 2026", "KYB Statistik nach Land & Form"]
    ws1 = wb["Handelsregister KYB 2026"]
    assert ws1.freeze_panes == "A4"
    assert "https://grunertandre.gumroad.com/l/qklpqn" in str(ws1["A1"].value)
    assert ws1.cell(3, 1).value == "Unternehmen"
    assert ws1.cell(4, 1).value == "BioNTech SE"
    assert ws1.cell(4, 10).value == 259027487.0
    ws2 = wb["KYB Statistik nach Land & Form"]
    cells = "\n".join(str(v) for r in ws2.iter_rows(values_only=True) for v in r if v is not None)
    assert "Rheinland-Pfalz" in cells
    assert "https://grunertandre.gumroad.com/l/qklpqn" in cells
    wb.close()


def test_generated_sample_50_artifacts_integrity():
    import csv
    import json

    samples_dir = Path(__file__).resolve().parent.parent / "samples"
    for csv_name in ("DE_Handelsregister_KYB_Sample_50.csv", "02_handelsregister_kyb_sample.csv"):
        with (samples_dir / csv_name).open("r", encoding="utf-8-sig", newline="") as f:
            rows = list(csv.DictReader(f))
        assert len(rows) == 50, f"{csv_name} expected 50 rows, got {len(rows)}"
        assert all((r.get("register_number") or "").strip() for r in rows)
        assert all(int(r.get("officers_count") or 0) > 0 for r in rows)
        assert all(float(r.get("share_capital") or 0) > 0 for r in rows)
        assert any(r.get("kyb_risk_status") == "WARNING_INSOLVENCY_FOUND" for r in rows)

    json_rows = json.loads((samples_dir / "02_handelsregister_kyb_sample.json").read_text(encoding="utf-8"))
    assert len(json_rows) == 50

    kyb_sample_json = json.loads((samples_dir / "DE_Handelsregister_KYB_Sample_50.json").read_text(encoding="utf-8"))
    assert kyb_sample_json.get("_meta_full_dataset_download") == "https://grunertandre.gumroad.com/l/qklpqn"
    assert len(kyb_sample_json.get("records") or []) == 50
    assert (samples_dir / "00_GET_FULL_2965_RECORDS.txt").is_file()

    wb = openpyxl.load_workbook(samples_dir / "DE_Handelsregister_KYB_Sample_50.xlsx", data_only=True)
    assert wb.sheetnames == ["Handelsregister KYB 2026", "KYB Statistik nach Land & Form"]
    ws1 = wb["Handelsregister KYB 2026"]
    assert ws1.max_row == 53
    wb.close()
