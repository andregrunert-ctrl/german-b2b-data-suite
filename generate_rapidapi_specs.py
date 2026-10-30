#!/usr/bin/env python3
"""
Generate valid OpenAPI 3.0.3 specifications for RapidAPI Studio:
- 00_unified_german_b2b_suite_openapi.json (All 6 synchronized endpoints)
- 01_zugferd_openapi.json
- 02_kyb_openapi.json
- 03_zvg_openapi.json
- 04_tenders_openapi.json
- 05_impressum_openapi.json
- 06_b2b_leads_openapi.json
- copy existing zugferd rapidapi-spec.json
- generate RAPIDAPI_PUBLISH_GUIDE.md
"""

import json
import os
import shutil

BASE_APIFY = r"C:\Users\andre\apify"
SUITE_DIR = os.path.join(BASE_APIFY, "german-b2b-data-suite")
RAPIDAPI_DIR = os.path.join(SUITE_DIR, "rapidapi")
SAMPLES_DIR = os.path.join(SUITE_DIR, "samples")
ZUGFERD_STANDALONE = r"C:\Users\andre\zugferd-api\integrations\rapidapi-spec.json"

os.makedirs(RAPIDAPI_DIR, exist_ok=True)

# Load real sample items for schema responses and examples
def load_sample(filename):
    path = os.path.join(SAMPLES_DIR, filename)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

zugferd_samples = load_sample("01_zugferd_xrechnung_sample.json")
kyb_samples = load_sample("02_handelsregister_kyb_sample.json")
zvg_samples = load_sample("03_zvg_foreclosures_sample.json")
tenders_samples = load_sample("04_public_tenders_sample.json")
impressum_samples = load_sample("05_impressum_leads_sample.json")
leads_samples = load_sample("06_b2b_crafts_directory_sample.json")

# Define tools metadata
TOOLS = [
    {
        "id": "zugferd",
        "file_prefix": "01_zugferd",
        "title": "German E-Invoice (ZUGFeRD & XRechnung) Suite",
        "tag": "1. E-Invoice Suite (ZUGFeRD & XRechnung)",
        "summary": "Generate, extract and validate compliant EN 16931 & Factur-X e-invoices",
        "actor_slug": "AGrunert~german-e-invoice-zugferd-xrechnung-suite",
        "description": "Generates PDF/A-3 documents with embedded Factur-X/ZUGFeRD 2.2 CII XML and official German XRechnung 3.0.2 syntax according to EU Directive EN 16931. Also extracts embedded XML and validates against official KoSIT Schematron rules.",
        "request_schema": {
            "type": "object",
            "required": ["operation"],
            "properties": {
                "operation": {
                    "type": "string",
                    "enum": ["generate", "embed", "extract"],
                    "default": "generate",
                    "description": "E-invoicing operation to execute (generate, embed, extract)"
                },
                "profile": {
                    "type": "string",
                    "enum": ["EN16931", "XRECHNUNG_3_0", "EXTENDED", "BASIC"],
                    "default": "EN16931",
                    "description": "ZUGFeRD / Factur-X profile level"
                },
                "invoice_data": {
                    "type": "object",
                    "description": "Complete invoice structure with seller, buyer, line items and payment means"
                },
                "file_url": {
                    "type": "string",
                    "description": "Public URL to PDF invoice for extraction or validation"
                },
                "file_base64": {
                    "type": "string",
                    "description": "Base64-encoded PDF or XML string"
                },
                "xml_url": {
                    "type": "string",
                    "description": "URL to raw CII or UBL XML file"
                },
                "xml_base64": {
                    "type": "string",
                    "description": "Base64-encoded CII or UBL XML"
                }
            }
        },
        "sample_input": {
            "operation": "generate",
            "profile": "EN16931",
            "invoice_data": {
                "invoice_number": "INV-2026-001",
                "issue_date": "2026-10-30",
                "due_date": "2026-11-30",
                "currency": "EUR",
                "seller": {
                    "name": "Muster Consulting GmbH",
                    "street": "Hauptstraße 42",
                    "postal_code": "10115",
                    "city": "Berlin",
                    "country_code": "DE",
                    "vat_id": "DE123456789",
                    "iban": "DE02120300000000202020",
                    "bic": "BYLADEM1001",
                    "email": "billing@muster-consulting.de"
                },
                "buyer": {
                    "name": "Kunde AG",
                    "street": "Kundenweg 10",
                    "postal_code": "80331",
                    "city": "München",
                    "country_code": "DE",
                    "vat_id": "DE987654321"
                },
                "line_items": [
                    {
                        "name": "Cloud Architecture & Integration Consulting",
                        "quantity": 10.0,
                        "unit_code": "HUR",
                        "unit_price": 150.0,
                        "tax_rate": 19.0
                    }
                ],
                "payment_means": {
                    "code": "30",
                    "iban": "DE02120300000000202020",
                    "bic": "BYLADEM1001"
                }
            }
        },
        "samples": zugferd_samples
    },
    {
        "id": "kyb",
        "file_prefix": "02_kyb",
        "title": "German Company KYB, Handelsregister & Insolvency Scraper",
        "tag": "2. Handelsregister & Insolvency KYB",
        "summary": "Check German commercial register (Handelsregister) and federal insolvency filings",
        "actor_slug": "AGrunert~german-company-kyb-insolvency-scraper",
        "description": "Performs official German commercial register (Handelsregister) audit across all 16 federal states and cross-checks active liquidation and insolvency proceedings on insolvenzbekanntmachungen.de.",
        "request_schema": {
            "type": "object",
            "required": ["company_name"],
            "properties": {
                "company_name": {
                    "type": "string",
                    "description": "Company name or search term (e.g. BioNTech SE, Siemens AG)"
                },
                "city": {
                    "type": "string",
                    "description": "Registered city / court location"
                },
                "register_number": {
                    "type": "string",
                    "description": "Commercial register number (e.g. HRB 48720)"
                },
                "register_type": {
                    "type": "string",
                    "enum": ["ALL", "HRB", "HRA", "GnR", "PR", "VR"],
                    "default": "HRB",
                    "description": "Court register department"
                },
                "include_insolvency_check": {
                    "type": "boolean",
                    "default": True,
                    "description": "Check live against insolvenzbekanntmachungen.de"
                },
                "include_financial_details": {
                    "type": "boolean",
                    "default": True,
                    "description": "Extract registered share capital (Stammkapital) and corporate filings"
                }
            }
        },
        "sample_input": {
            "company_name": "BioNTech SE",
            "city": "Mainz",
            "register_type": "HRB",
            "include_insolvency_check": True,
            "include_financial_details": True
        },
        "samples": kyb_samples
    },
    {
        "id": "zvg",
        "file_prefix": "03_zvg",
        "title": "German Real Estate Foreclosure & ZVG-Portal Scraper",
        "tag": "3. Real Estate Foreclosures (ZVG-Portal)",
        "summary": "Search official judicial foreclosure auctions, appraisals and property values",
        "actor_slug": "AGrunert~german-real-estate-foreclosure-zvg-scraper",
        "description": "Monitors all official German judicial foreclosure auctions from zvg-portal.de across all 16 federal states with market appraisals, court file numbers, land registry details and auction dates.",
        "request_schema": {
            "type": "object",
            "properties": {
                "states": {
                    "type": "array",
                    "items": {"type": "string"},
                    "default": ["nw"],
                    "description": "German state codes (e.g. nw, by, be, bw, he, sn)"
                },
                "city": {
                    "type": "string",
                    "description": "City or court name filter"
                },
                "property_type": {
                    "type": "string",
                    "enum": ["ALL", "Eigentumswohnung", "Einfamilienhaus", "Mehrfamilienhaus", "Doppelhaushälfte", "Reihenhaus", "Gewerbe", "Grundstück", "Garage"],
                    "default": "ALL",
                    "description": "Category of property"
                },
                "min_market_value": {
                    "type": "number",
                    "description": "Minimum property value in EUR"
                },
                "max_market_value": {
                    "type": "number",
                    "description": "Maximum property value in EUR"
                },
                "max_items": {
                    "type": "integer",
                    "default": 25,
                    "description": "Maximum auction records to return"
                },
                "include_details": {
                    "type": "boolean",
                    "default": True,
                    "description": "Fetch deep details including appraisal PDF links"
                }
            }
        },
        "sample_input": {
            "states": ["nw"],
            "property_type": "Einfamilienhaus",
            "max_items": 10,
            "include_details": True
        },
        "samples": zvg_samples
    },
    {
        "id": "tenders",
        "file_prefix": "04_tenders",
        "title": "German Public Tenders & Procurement Scraper (service.bund.de)",
        "tag": "4. Public Tenders (Bund.de)",
        "summary": "Scrape official German public procurement tenders, notices and tender documents",
        "actor_slug": "AGrunert~german-public-tenders-vergabe-scraper",
        "description": "Extracts federal, state, and municipal public procurement notices from service.bund.de with submission deadlines, contracting authority addresses, and direct document download links.",
        "request_schema": {
            "type": "object",
            "required": ["keywords"],
            "properties": {
                "keywords": {
                    "type": "array",
                    "items": {"type": "string"},
                    "default": ["IT-Dienstleistungen", "Software"],
                    "description": "Search keywords array (e.g. ['IT-Dienstleistungen', 'Software'])"
                },
                "states": {
                    "type": "array",
                    "items": {"type": "string"},
                    "default": ["Berlin"],
                    "description": "Target federal states"
                },
                "service_type": {
                    "type": "string",
                    "enum": ["ALL", "Dienstleistungen", "Bauleistungen", "Lieferleistungen", "Informationstechnik", "Forschung und Entwicklung"],
                    "default": "ALL",
                    "description": "Category of tender procurement"
                },
                "max_items": {
                    "type": "integer",
                    "default": 25,
                    "description": "Maximum notices to extract"
                },
                "include_details": {
                    "type": "boolean",
                    "default": True,
                    "description": "Fetch deep tender specification details"
                }
            }
        },
        "sample_input": {
            "keywords": ["IT-Dienstleistungen", "Software"],
            "states": ["Berlin", "Bayern"],
            "service_type": "Dienstleistungen",
            "max_items": 10,
            "include_details": True
        },
        "samples": tenders_samples
    },
    {
        "id": "impressum",
        "file_prefix": "05_impressum",
        "title": "German & DACH B2B Impressum, Contact & Legal Enricher (§ 5 DDG)",
        "tag": "5. Impressum & CEO Enricher (§ 5 DDG)",
        "summary": "Enrich German corporate websites with CEO, legal entity, HRB and VAT ID",
        "actor_slug": "AGrunert~german-impressum-b2b-lead-enricher",
        "description": "Crawls German and DACH business domains, resolves required § 5 DDG legal notices (Impressum), and extracts Managing Directors (Geschäftsführer/Vorstand), Commercial Register HRB numbers, court, and VAT IDs (USt-IdNr.).",
        "request_schema": {
            "type": "object",
            "required": ["domains"],
            "properties": {
                "domains": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of domains to enrich (e.g. ['personio.de', 'celonis.com'])"
                },
                "extract_contact_page": {
                    "type": "boolean",
                    "default": True,
                    "description": "Fallback scan of contact/about pages"
                },
                "max_concurrency": {
                    "type": "integer",
                    "default": 5,
                    "description": "Concurrent web workers"
                }
            }
        },
        "sample_input": {
            "domains": ["personio.de", "celonis.com"],
            "extract_contact_page": True,
            "max_concurrency": 5
        },
        "samples": impressum_samples
    },
    {
        "id": "leads",
        "file_prefix": "06_b2b_leads",
        "title": "German B2B Leads, Crafts & Business Directory Scraper",
        "tag": "6. B2B Directory Leads (11880 & Gelbe Seiten)",
        "summary": "Scrape verified German local businesses and crafts with phone, address and domain",
        "actor_slug": "AGrunert~german-b2b-leads-directory-scraper",
        "description": "Extracts verified German B2B company leads and local crafts (Handwerker) from leading directories with E.164 phone numbers, physical addresses, postal codes, and verified corporate domains.",
        "request_schema": {
            "type": "object",
            "required": ["query", "location"],
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Industry or trade keyword (e.g. Dachdecker, Steuerberater, Elektriker)"
                },
                "location": {
                    "type": "string",
                    "description": "City or postal code in Germany (e.g. Berlin, München, 50667)"
                },
                "require_website": {
                    "type": "boolean",
                    "default": False,
                    "description": "Filter only companies with website"
                },
                "require_phone": {
                    "type": "boolean",
                    "default": False,
                    "description": "Filter only companies with telephone"
                },
                "max_items": {
                    "type": "integer",
                    "default": 20,
                    "description": "Maximum lead records"
                },
                "include_details": {
                    "type": "boolean",
                    "default": True,
                    "description": "Extract full contact profiles"
                }
            }
        },
        "sample_input": {
            "query": "Dachdecker",
            "location": "Berlin",
            "require_website": True,
            "require_phone": True,
            "max_items": 10,
            "include_details": True
        },
        "samples": leads_samples
    }
]

def make_path_item(tool):
    return {
        "post": {
            "tags": [tool["tag"]],
            "summary": tool["summary"],
            "description": tool["description"],
            "operationId": f"run_{tool['id']}_sync",
            "requestBody": {
                "required": True,
                "content": {
                    "application/json": {
                        "schema": tool["request_schema"],
                        "example": tool["sample_input"]
                    }
                }
            },
            "responses": {
                "200": {
                    "description": "Synchronous run completed successfully. Returns dataset items array directly.",
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "array",
                                "items": {
                                    "type": "object"
                                }
                            },
                            "example": tool["samples"][:3] if tool["samples"] else [{"status": "success"}]
                        }
                    }
                },
                "400": {
                    "description": "Invalid input parameters",
                    "content": {
                        "application/json": {
                            "example": {"error": "Invalid request parameters"}
                        }
                    }
                },
                "401": {
                    "description": "Unauthorized - Missing or invalid Apify API token",
                    "content": {
                        "application/json": {
                            "example": {"error": "Invalid token"}
                        }
                    }
                },
                "402": {
                    "description": "Payment Required - Insufficient Apify usage credits",
                    "content": {
                        "application/json": {
                            "example": {"error": "Account out of credits"}
                        }
                    }
                }
            }
        }
    }

# 1. BUILD UNIFIED SPEC
unified_paths = {}
for t in TOOLS:
    endpoint_path = f"/v2/acts/{t['actor_slug']}/run-sync-get-dataset-items"
    unified_paths[endpoint_path] = make_path_item(t)

unified_spec = {
    "openapi": "3.0.3",
    "info": {
        "title": "German & DACH B2B Data, Compliance & KYB Suite",
        "description": "The unified German enterprise API suite covering commercial registers (Handelsregister), corporate legal notices (§ 5 DDG Impressum & CEO discovery), federal insolvency court filings, public tenders (service.bund.de), real estate foreclosures (ZVG-Portal), B2B crafts directory leads (11880/Gelbe Seiten), and compliant European e-invoicing (ZUGFeRD 2.2 & XRechnung 3.0).\n\nAll endpoints execute synchronously and return clean, structured JSON datasets directly.",
        "version": "1.0.0",
        "contact": {
            "name": "Andre Grunert - Enterprise API Integrations",
            "url": "https://github.com/andregrunert-ctrl/german-b2b-data-suite",
            "email": "kontakt@e-rechnung-cloud.de"
        }
    },
    "servers": [
        {
            "url": "https://api.apify.com",
            "description": "Apify Production Cloud Gateway"
        }
    ],
    "security": [
        {"ApifyAuth": []}
    ],
    "components": {
        "securitySchemes": {
            "ApifyAuth": {
                "type": "http",
                "scheme": "bearer",
                "bearerFormat": "Apify API Token",
                "description": "Personal Apify API token (starts with apify_api_...)"
            }
        }
    },
    "paths": unified_paths
}

unified_file = os.path.join(RAPIDAPI_DIR, "00_unified_german_b2b_suite_openapi.json")
with open(unified_file, "w", encoding="utf-8") as f:
    json.dump(unified_spec, f, indent=2, ensure_ascii=False)
print(f"[OK] Generated {unified_file}")

# 2. BUILD INDIVIDUAL SPECS
for t in TOOLS:
    single_path = f"/v2/acts/{t['actor_slug']}/run-sync-get-dataset-items"
    single_spec = {
        "openapi": "3.0.3",
        "info": {
            "title": t["title"],
            "description": f"{t['description']}\n\nSynchronous API endpoint returning structured dataset items directly.",
            "version": "1.0.0",
            "contact": {
                "name": "Andre Grunert - Enterprise API Integrations",
                "url": "https://github.com/andregrunert-ctrl/german-b2b-data-suite"
            }
        },
        "servers": [
            {
                "url": "https://api.apify.com",
                "description": "Apify Production Cloud Gateway"
            }
        ],
        "security": [
            {"ApifyAuth": []}
        ],
        "components": {
            "securitySchemes": {
                "ApifyAuth": {
                    "type": "http",
                    "scheme": "bearer",
                    "bearerFormat": "Apify API Token"
                }
            }
        },
        "paths": {
            single_path: make_path_item(t)
        }
    }

    single_file = os.path.join(RAPIDAPI_DIR, f"{t['file_prefix']}_openapi.json")
    with open(single_file, "w", encoding="utf-8") as f:
        json.dump(single_spec, f, indent=2, ensure_ascii=False)
    print(f"[OK] Generated {single_file}")

# 3. COPY EXISTING ZUGFERD STANDALONE SPEC IF PRESENT
if os.path.exists(ZUGFERD_STANDALONE):
    dest = os.path.join(RAPIDAPI_DIR, "01_zugferd_fastapi_legacy_spec.json")
    shutil.copyfile(ZUGFERD_STANDALONE, dest)
    print(f"[OK] Copied existing FastAPI spec: {dest}")

# 4. GENERATE RAPIDAPI PUBLISH GUIDE
guide_content = """# RapidAPI Studio Publish Guide 🚀⚡

Befolge diese 5 Schritte, um die Suite oder beliebige Einzel-APIs in 60 Sekunden auf RapidAPI zu veröffentlichen:

1. **API Importieren:** Öffne [RapidAPI Studio](https://rapidapi.com/studio) und klicke auf **"Add New API"** -> **"OpenAPI Document"** -> Wähle `rapidapi/00_unified_german_b2b_suite_openapi.json` (oder eine der Einzel-Dateien `01_*` bis `06_*`).
2. **Gateway-URL prüfen:** Bestätige die Base-URL `https://api.apify.com` unter **API Settings -> Target URL**.
3. **Secret Header konfigurieren:** Navigiere zu **Gateway -> Transformations / Secret Headers** und füge folgenden Header hinzu:
   - **Header Name:** `Authorization`
   - **Header Value:** `Bearer <DEIN_APIFY_TOKEN>` (z. B. `Bearer apify_api_...`)
4. **Preise & Pläne einstellen:** Unter **Plans & Pricing** wählst du Freemium (z. B. 20 Free Requests/Monat, danach 0.05 $ / Call für KYB/Rechnungen).
5. **Veröffentlichen:** Klicke oben rechts auf **"Publish"** – deine API ist sofort im weltweiten RapidAPI-Marktplatz live, und RapidAPI handhabt Kreditkarten und Billing vollautomatisch!
"""

guide_file = os.path.join(RAPIDAPI_DIR, "RAPIDAPI_PUBLISH_GUIDE.md")
with open(guide_file, "w", encoding="utf-8") as f:
    f.write(guide_content)
print(f"[OK] Generated {guide_file}")
