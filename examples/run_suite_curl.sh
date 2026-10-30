#!/usr/bin/env bash
# ==============================================================================
# German & DACH B2B Data Suite - cURL Quickstart
# 1-Click synchronous REST API calls for all 6 Apify Actors
# ==============================================================================

if [ -z "$APIFY_TOKEN" ]; then
    echo "❌ ERROR: APIFY_TOKEN is not set!"
    echo "Usage: export APIFY_TOKEN=\"your_apify_token\" && bash run_suite_curl.sh"
    exit 1
fi

BASE_URL="https://api.apify.com/v2/acts"

echo "=============================================================================="
echo "🚀 1. German E-Invoice (ZUGFeRD & XRechnung) Generator"
echo "=============================================================================="
curl -s -X POST "${BASE_URL}/AGrunert~german-e-invoice-zugferd-xrechnung-suite/run-sync-get-dataset-items?token=${APIFY_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "operation": "generate",
    "profile": "EN16931",
    "invoice_data": {
      "invoice_number": "INV-2026-001",
      "issue_date": "2026-10-29",
      "due_date": "2026-11-28",
      "buyer_reference": "991-12345-56",
      "currency": "EUR",
      "seller": {
        "name": "Cloud Solutions GmbH",
        "street": "Friedrichstr. 10",
        "city": "Berlin",
        "zip_code": "10117",
        "country": "DE",
        "vat_id": "DE123456789",
        "iban": "DE02120300000000202020",
        "bic": "BYLADEM1001",
        "contact_name": "Max Mustermann",
        "phone": "+49 30 12345678",
        "email": "billing@cloud-solutions.de"
      },
      "buyer": {
        "name": "Kunde AG",
        "street": "Hauptstr. 1",
        "city": "München",
        "zip_code": "80331",
        "country": "DE",
        "vat_id": "DE987654321",
        "email": "rechnungseingang@kunde.de"
      },
      "line_items": [
        {
          "description": "IT Architecture Consulting",
          "quantity": 10.0,
          "unit_code": "HUR",
          "unit_price": 150.0,
          "tax_rate_percent": 19.0
        }
      ]
    }
  }' | jq '.'

echo ""
echo "=============================================================================="
echo "🚀 2. German Company KYB & Insolvency Scraper"
echo "=============================================================================="
curl -s -X POST "${BASE_URL}/AGrunert~german-company-kyb-insolvency-scraper/run-sync-get-dataset-items?token=${APIFY_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "company_name": "BioNTech SE",
    "city": "Mainz",
    "register_number": "HRB 48720",
    "include_insolvency_check": true,
    "include_financial_details": true
  }' | jq '.'

echo ""
echo "=============================================================================="
echo "🚀 3. German Real Estate Foreclosures (ZVG-Portal) Scraper"
echo "=============================================================================="
curl -s -X POST "${BASE_URL}/AGrunert~german-real-estate-foreclosure-zvg-scraper/run-sync-get-dataset-items?token=${APIFY_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "states": ["by", "be", "sn"],
    "property_type": "ALL",
    "min_market_value": 100000,
    "max_items": 3,
    "include_details": true
  }' | jq '.'

echo ""
echo "=============================================================================="
echo "🚀 4. German Public Tenders & Procurement Scraper (Bund.de)"
echo "=============================================================================="
curl -s -X POST "${BASE_URL}/AGrunert~german-public-tenders-vergabe-scraper/run-sync-get-dataset-items?token=${APIFY_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "keywords": ["Software", "Cloud", "KI"],
    "states": ["bund", "by", "nw"],
    "max_items": 3,
    "include_details": true
  }' | jq '.'

echo ""
echo "=============================================================================="
echo "🚀 5. German & DACH B2B Impressum & Contact Enricher (§ 5 DDG)"
echo "=============================================================================="
curl -s -X POST "${BASE_URL}/AGrunert~german-impressum-b2b-lead-enricher/run-sync-get-dataset-items?token=${APIFY_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "domains": ["biontech.de", "deepl.com"],
    "extract_contact_page": true,
    "max_concurrency": 2
  }' | jq '.'

echo ""
echo "=============================================================================="
echo "🚀 6. German B2B Leads & Directory Scraper (Gelbe Seiten & 11880)"
echo "=============================================================================="
curl -s -X POST "${BASE_URL}/AGrunert~german-b2b-leads-directory-scraper/run-sync-get-dataset-items?token=${APIFY_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "search_terms": ["Elektroinstallation"],
    "locations": ["München"],
    "max_items": 3,
    "require_website": true,
    "require_phone": true
  }' | jq '.'

echo ""
echo "🎉 Done! All 6 tools queried successfully."
