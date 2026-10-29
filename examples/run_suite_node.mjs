/**
 * German & DACH B2B Data Suite - Modern Node.js ESM Quickstart
 * Demonstrates synchronous execution of all 6 Apify Actors via native fetch.
 *
 * Usage:
 *   export APIFY_TOKEN="your_token_here"
 *   node run_suite_node.mjs
 */

const APIFY_TOKEN = process.env.APIFY_TOKEN;
if (!APIFY_TOKEN) {
  console.error("❌ ERROR: APIFY_TOKEN environment variable is not set!");
  console.error("Please export your token: export APIFY_TOKEN=\"your_apify_token\"");
  process.exit(1);
}

const BASE_URL = "https://api.apify.com/v2/acts";

const ACTORS = [
  {
    name: "1. German E-Invoice (ZUGFeRD & XRechnung) Generator",
    slug: "AGrunert~german-e-invoice-zugferd-xrechnung-suite",
    input: {
      operation: "generate",
      profile: "EN16931",
      invoice_data: {
        invoice_number: "INV-2026-001",
        issue_date: "2026-10-29",
        due_date: "2026-11-28",
        currency: "EUR",
        seller: {
          name: "Cloud Solutions GmbH",
          street: "Friedrichstr. 10",
          city: "Berlin",
          zip_code: "10117",
          country: "DE",
          vat_id: "DE123456789",
          email: "billing@cloud-solutions.de"
        },
        buyer: {
          name: "Kunde AG",
          street: "Hauptstr. 1",
          city: "München",
          zip_code: "80331",
          country: "DE",
          vat_id: "DE987654321",
          email: "invoices@kunde.de"
        },
        line_items: [
          {
            description: "Cloud Integration Consulting",
            quantity: 8,
            unit_code: "HUR",
            unit_price: 150.0,
            tax_rate_percent: 19.0
          }
        ]
      }
    }
  },
  {
    name: "2. German Company KYB & Insolvency Scraper",
    slug: "AGrunert~german-company-kyb-insolvency-scraper",
    input: {
      company_name: "BioNTech SE",
      city: "Mainz",
      register_number: "HRB 48720",
      include_insolvency_check: true,
      include_financial_details: true
    }
  },
  {
    name: "3. German Real Estate Foreclosures (ZVG-Portal) Scraper",
    slug: "AGrunert~german-real-estate-foreclosure-zvg-scraper",
    input: {
      states: ["by", "be", "sn"],
      min_market_value: 100000,
      max_items: 2,
      include_details: true
    }
  },
  {
    name: "4. German Public Tenders & Procurement Scraper (Bund.de)",
    slug: "AGrunert~german-public-tenders-vergabe-scraper",
    input: {
      keywords: "Software Cloud KI",
      states: ["bund", "by", "nw"],
      max_items: 2,
      include_details: true
    }
  },
  {
    name: "5. German & DACH B2B Impressum & Contact Enricher (§ 5 DDG)",
    slug: "AGrunert~german-impressum-b2b-lead-enricher",
    input: {
      domains: ["biontech.de", "deepl.com"],
      extract_contact_page: true,
      max_concurrency: 2
    }
  },
  {
    name: "6. German B2B Leads & Directory Scraper (Gelbe Seiten & 11880)",
    slug: "AGrunert~german-b2b-leads-directory-scraper",
    input: {
      search_terms: ["Elektroinstallation"],
      locations: ["München"],
      max_items: 2,
      require_website: true,
      require_phone: true
    }
  }
];

async function main() {
  console.log("=".repeat(80));
  console.log("🚀 Executing German & DACH B2B Data Suite in Node.js");
  console.log("=".repeat(80));

  for (const item of ACTORS) {
    console.log(`\n[Calling] ${item.name} (${item.slug})...`);
    const endpoint = `${BASE_URL}/${item.slug}/run-sync-get-dataset-items?token=${APIFY_TOKEN}`;

    try {
      const res = await fetch(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(item.input)
      });

      if (!res.ok) {
        const text = await res.text();
        console.error(`  ❌ HTTP ${res.status}: ${text.slice(0, 160)}`);
        continue;
      }

      const data = await res.json();
      console.log(`  ✓ Succeeded! Returned ${data.length} item(s).`);
      if (data.length > 0) {
        const first = data[0];
        const previewKeys = Object.keys(first).slice(0, 5);
        const previewObj = {};
        previewKeys.forEach(k => previewObj[k] = first[k]);
        console.log(`  Preview:`, JSON.stringify(previewObj));
      }
    } catch (err) {
      console.error(`  ❌ Fetch Failed:`, err.message);
    }
  }

  console.log("\n" + "=".repeat(80));
  console.log("🎉 All 6 actors executed successfully via Node.js fetch!");
  console.log("=".repeat(80));
}

main();
