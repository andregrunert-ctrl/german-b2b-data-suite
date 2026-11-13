import sys
from datetime import date
from pathlib import Path

import openpyxl

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import refresh_live_samples as rls  # noqa: E402


def test_decode_zvg_html_and_market_value_edge_cases():
    mixed = b"Einfamilienhaus \xe2\x80\x93 160,000,00 \x80 &#128;"
    decoded = rls.decode_zvg_html(mixed)
    assert "–" in decoded
    assert "â€“" not in decoded
    assert decoded.count("€") == 2

    assert rls.parse_market_value("160,000,00 €") == 160000.0
    assert (
        rls.parse_market_value(
            "A. für den ursprünglichen Zustand: 10.000,00 EUR "
            "B: für den bereinigten Zustand: 120.000,00 EUR"
        )
        == 120000.0
    )


def test_write_sample_50_xlsx_restores_bundesland_and_objektart_stats(tmp_path):
    rows = [
        {
            "zvg_id": "101",
            "state_code": "SN",
            "state_name": "Sachsen",
            "court": "Amtsgericht Dresden",
            "case_number": "0001 K 0010/2026",
            "property_type": "Einfamilienhaus, Garage",
            "title": "Einfamilienhaus, Garage: Musterweg 1, 01067 Dresden",
            "address": "Musterweg 1, 01067 Dresden",
            "postal_code": "01067",
            "city": "Dresden",
            "market_value_eur": 300000.0,
            "auction_date": "Montag, 30. November 2026, 10:00 Uhr",
            "auction_location": "Saal 1",
            "land_register": "Blatt 1",
            "creditor_info": "Bank AG",
            "pdf_primary_url": "https://www.zvg-portal.de/index.php?button=showAnhang&land_abk=sn&file_id=1&zvg_id=101",
            "pdf_urls_count": 1,
            "all_pdf_urls": "https://www.zvg-portal.de/index.php?button=showAnhang&land_abk=sn&file_id=1&zvg_id=101",
            "detail_url": "https://www.zvg-portal.de/index.php?button=showZvg&zvg_id=101&land_abk=sn",
            "description": "Gepflegtes Einfamilienhaus mit Garage",
        },
        {
            "zvg_id": "102",
            "state_code": "BY",
            "state_name": "Bayern",
            "court": "Amtsgericht München",
            "case_number": "0002 K 0020/2026",
            "property_type": "Eigentumswohnung",
            "title": "Eigentumswohnung: Teststr. 2, 80331 München",
            "address": "Teststr. 2, 80331 München",
            "postal_code": "80331",
            "city": "München",
            "market_value_eur": 450000.0,
            "auction_date": "Dienstag, 01. Dezember 2026, 09:00 Uhr",
            "auction_location": "Saal 2",
            "land_register": "Blatt 2",
            "creditor_info": "",
            "pdf_primary_url": "https://www.zvg-portal.de/index.php?button=showAnhang&land_abk=by&file_id=2&zvg_id=102",
            "pdf_urls_count": 1,
            "all_pdf_urls": "https://www.zvg-portal.de/index.php?button=showAnhang&land_abk=by&file_id=2&zvg_id=102",
            "detail_url": "https://www.zvg-portal.de/index.php?button=showZvg&zvg_id=102&land_abk=by",
            "description": "3-Zimmer Wohnung",
        },
    ]
    out_xlsx = tmp_path / "sample.xlsx"
    rls.write_sample_50_xlsx(rows, out_xlsx)

    wb = openpyxl.load_workbook(out_xlsx, data_only=True)
    assert "Statistik nach Bundesland & Art" in wb.sheetnames
    ws2 = wb["Statistik nach Bundesland & Art"]
    all_cells = [str(v) for row in ws2.iter_rows(values_only=True) for v in row if v is not None]
    joined = "\n".join(all_cells)
    assert "Bundesland" in joined
    assert "Objektart" in joined
    assert "Einfamilien- / Zweifamilienhaus" in joined
    assert "Garage" not in joined
    assert "Eigentumswohnung" in joined
    assert "GESAMT" in joined


def test_parse_tender_detail_html_extracts_non_pre_div_text_cpv_and_links():
    sample_html = """
    <html><body>
      <main>
        <section>
          <dl>
            <dt>Leistungen und Erzeugnisse</dt><dd>IT-Dienstleistungen</dd>
            <dt>Vergabeart</dt><dd>Offenes Verfahren</dd>
            <dt>Angebotsfrist</dt><dd>15.12.2026 12:00 Uhr</dd>
            <dt>Erfüllungsort</dt><dd>10117 Berlin Berlin</dd>
            <dt>CPV-Code</dt><dd>72260000-5, 48000000-8</dd>
          </dl>
          <div class="text">
            <p>Beschaffung einer modernen Cloud-Software-Plattform inkl. Betrieb und Support.</p>
            <p>Vertragslaufzeit 48 Monate mit Verlängerungsoption.</p>
          </div>
          <div class="linklist">
            <ul>
              <li><a href="https://www.subreport-elvis.de/download/bund/E999/bekanntmachung.pdf">Bekanntmachung</a></li>
              <li><a href="Content/DE/Service/Impressum/impressum.html">Impressum</a></li>
            </ul>
          </div>
        </section>
      </main>
    </body></html>
    """
    cand = {
        "tender_id": "E999",
        "title": "Cloud Software Plattform",
        "contracting_authority": "Bundesamt für IT",
        "published_at": "12.11.2026",
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
        "detail_url": "https://www.service.bund.de/IMPORTE/Ausschreibungen/subreport/2026/11/E999.html",
        "matched_keyword": "Cloud",
        "scraped_at": "2026-11-13T08:00:00+00:00",
    }
    enriched = rls.extract_tender_detail_fields(cand, sample_html)
    assert "Cloud-Software-Plattform" in enriched["description"]
    assert "Vertragslaufzeit 48 Monate" in enriched["description"]
    assert enriched["cpv_codes"] == ["72260000-5", "48000000-8"]
    assert enriched["tender_document_urls"] == [
        "https://www.subreport-elvis.de/download/bund/E999/bekanntmachung.pdf"
    ]
    assert enriched["submission_deadline"] == "15.12.2026 12:00 Uhr"
    assert enriched["postal_code"] == "10117"
    assert enriched["city"] == "Berlin"
