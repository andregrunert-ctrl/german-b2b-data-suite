#!/usr/bin/env python3
"""
German & DACH B2B Data Suite - Python Quickstart
Demonstrates synchronous execution of all 6 Apify Actors via REST API.

Prerequisites:
    pip install httpx

Usage:
    export APIFY_TOKEN="your_token_here"
    python run_suite_python.py
"""
import os
import sys
import json
import httpx

# Ensure UTF-8 output on Windows console
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

APIFY_TOKEN = os.environ.get("APIFY_TOKEN")
if not APIFY_TOKEN:
    print("❌ ERROR: APIFY_TOKEN environment variable is not set!")
    print("Please set your Apify API token:")
    print("  Linux/macOS: export APIFY_TOKEN=\"your_token_here\"")
    print("  Windows:     $env:APIFY_TOKEN=\"your_token_here\"")
    sys.exit(1)

BASE_URL = "https://api.apify.com/v2"

ACTORS = [
    {
        "id": "1. German E-Invoice (ZUGFeRD & XRechnung) Suite",
        "actor": "AGrunert~german-e-invoice-zugferd-xrechnung-suite",
        "input": {
            "operation": "generate",
            "profile": "EN16931",
            "invoice_data": {
                "invoice_number": "INV-2026-001",
                "issue_date": "2026-10-29",
                "due_date": "2026-11-28",
                "currency": "EUR",
                "seller": {
                    "name": "Muster Consulting GmbH",
                    "street": "Hauptstraße 42",
                    "city": "Berlin",
                    "zip_code": "10115",
                    "country": "DE",
                    "vat_id": "DE123456789",
                    "iban": "DE02120300000000202020",
                    "email": "billing@muster-consulting.de"
                },
                "buyer": {
                    "name": "Kunde AG",
                    "street": "Kundenweg 10",
                    "city": "München",
                    "zip_code": "80331",
                    "country": "DE",
                    "vat_id": "DE987654321",
                    "email": "invoices@kunde.de"
                },
                "line_items": [
                    {
                        "description": "Cloud Architecture & Integration Consulting",
                        "quantity": 5.0,
                        "unit_code": "HUR",
                        "unit_price": 160.0,
                        "tax_rate_percent": 19.0
                    }
                ]
            }
        }
    },
    {
        "id": "2. German Company KYB & Insolvency Scraper",
        "actor": "AGrunert~german-company-kyb-insolvency-scraper",
        "input": {
            "company_name": "BioNTech SE",
            "city": "Mainz",
            "register_number": "HRB 48720",
            "include_insolvency_check": True,
            "include_financial_details": True
        }
    },
    {
        "id": "3. German Real Estate Foreclosures (ZVG-Portal) Scraper",
        "actor": "AGrunert~german-real-estate-foreclosure-zvg-scraper",
        "input": {
            "states": ["by", "be", "sn"],
            "property_type": "ALL",
            "min_market_value": 100000,
            "max_items": 3,
            "include_details": True
        }
    },
    {
        "id": "4. German Public Tenders & Procurement Scraper (Bund.de)",
        "actor": "AGrunert~german-public-tenders-vergabe-scraper",
        "input": {
            "keywords": ["Software", "Cloud", "KI"],
            "states": ["bund", "by", "nw"],
            "max_items": 3,
            "include_details": True
        }
    },
    {
        "id": "5. German & DACH B2B Impressum & Contact Enricher (§ 5 DDG)",
        "actor": "AGrunert~german-impressum-b2b-lead-enricher",
        "input": {
            "domains": ["biontech.de", "deepl.com"],
            "extract_contact_page": True,
            "max_concurrency": 2
        }
    },
    {
        "id": "6. German B2B Company Leads & Crafts Directory Scraper",
        "actor": "AGrunert~german-b2b-leads-directory-scraper",
        "input": {
            "search_terms": ["Elektroinstallation"],
            "locations": ["München"],
            "max_items": 3,
            "require_website": True,
            "require_phone": True
        }
    }
]

def run_suite():
    print("=" * 80)
    print("🚀 Running German & DACH B2B Data Suite via Apify REST API")
    print("=" * 80)

    client = httpx.Client(timeout=180.0)
    failed = 0

    for item in ACTORS:
        name = item["id"]
        actor_slug = item["actor"]
        payload = item["input"]

        print(f"\n[Calling] {name} ({actor_slug})...")
        endpoint = f"{BASE_URL}/acts/{actor_slug}/run-sync-get-dataset-items?token={APIFY_TOKEN}"

        try:
            response = client.post(endpoint, json=payload)
            if response.status_code in (200, 201):
                results = response.json()
                print(f"  ✓ Succeeded! Returned {len(results)} items.")
                if results:
                    first = results[0]
                    # Print preview keys
                    preview = {k: first[k] for k in list(first.keys())[:5]}
                    print(f"  Preview: {json.dumps(preview, ensure_ascii=False)}")
            else:
                failed += 1
                print(f"  ❌ API Error ({response.status_code}): {response.text[:200]}")
        except Exception as e:
            failed += 1
            print(f"  ❌ Request Failed: {e}")

    print("\n" + "=" * 80)
    if failed == 0:
        print("🎉 All 6 actors executed successfully!")
    else:
        print(f"⚠️ Suite finished with {failed} failure(s).")
        sys.exit(1)
    print("=" * 80)

if __name__ == "__main__":
    run_suite()
