# How we built a zero-Playwright German B2B & Public Procurement Scraper suite (95%+ lighter, 10x faster)

**Target Subreddits:** r/webscraping, r/n8n, r/selfhosted, r/datascience  
**Flair:** Engineering / Project Showcase / Guide  

---

### The TL;DR
When extracting B2B and public sector data in Germany (Commercial Register, Foreclosures, Public Tenders, Business Directories), 90% of developers default to headless browsers like Playwright or Puppeteer. The result? 1.5 GB RAM per container, frequent cloud IP blocks, and slow pipelines (45-60s per batch).

We re-engineered the entire pipeline across 6 German core registries using **zero headless browsers**—relying purely on reverse-engineered HTTP protocols, streaming HTML/XML parsers (`httpx` + `selectolax` + `lxml`), and async concurrency.

The result: **3.8s execution time for 50 enriched leads, under 65MB RAM footprint, and 100% automated CI/CD.**

Here is the engineering breakdown of what we learned and how we solved the quirks of Germany's public portals.

---

### 1. Why Headless Browsers Are an Anti-Pattern for Enterprise Scraping
When running scrapers at scale or inside automated workflow engines (like self-hosted n8n, Airflow, or Docker clusters), browsers cause three critical bottlenecks:
1. **Memory & CPU Bloat:** A single Chromium instance consumes 800MB–1.5GB of RAM. If you run 5 concurrent jobs, small VPS nodes crash.
2. **Cold-Start Latency:** Launching a browser context, navigating SPAs, and waiting for network idle takes 5–15 seconds before the first byte of data is extracted.
3. **Bot Fingerprints:** CDPs (Chrome DevTools Protocol) leak automation flags (`navigator.webdriver`, WebGL fingerprints), making them easy targets for Cloudflare/Akamai bot detection.

By inspecting network traffic, session cookies, and API contracts, we found that nearly every German enterprise portal can be queried via lightweight HTTP requests.

---

### 2. Solving Portal Quirks Across 6 German Domain Portals

| Registry / Portal | Traditional Approach | Our Pure-Protocol Solution | Key Quirk Solved |
| :--- | :--- | :--- | :--- |
| **11880 & Gelbe Seiten** (B2B Directories) | Playwright click on "Show Website" | Reverse-engineered POST `/ajaxsuche` & `?page=n` with Base64 URL decoding | External links are Base64-encoded inside `data-webseitelink` attributes to prevent simple `href` scraping. |
| **Corporate Impressum (§ 5 DDG)** | Puppeteer full-page crawl | Async `httpx` crawler + regex de-obfuscation pipeline | German websites obfuscate emails (`name [at] domain.de`, CSS `direction: rtl`, HTML entities `&#64;`). |
| **Handelsregister (XJustiz 3.5.1)** | Manual PDF download / OCR | Structured XML parser + XJustiz schema mapping | German registry filings follow official justice XML schemas (`XJustiz`), which can be extracted directly without PDF OCR. |
| **ZVG-Portal (Foreclosures)** | Headless click on ASP.NET form | Multipart POST state-machine with `__VIEWSTATE` & session cookies | ZVG is built on legacy ASP.NET WebForms. Simulating the exact state machine allows bulk scraping all 16 federal states in seconds. |
| **service.bund.de (Public Tenders)** | Browser navigation across paginated tables | Direct HTTP queries with CPV code taxonomy & search token rotation | Bypasses UI pagination limits and extracts tender notices with attached tender dossier links. |
| **E-Invoicing (ZUGFeRD / XRechnung)** | Heavy Java/Saxon validator | Pure Python XML/CII + PDF/A-3 Factur-X injector | Embeds and validates machine-readable XML compliant with EU EN 16931 & KoSIT standards. |

---

### 3. Concurrency & Performance Benchmarks

Running a batch of 50 B2B company leads through the complete enrichment chain (Search -> § 5 DDG Legal Extraction -> Handelsregister KYB Check):

| Metric | Playwright / Headless Chrome | Our Async HTTP Architecture | Improvement |
| :--- | :--- | :--- | :--- |
| **Execution Time (50 Leads)** | ~52.4 seconds | **3.78 seconds** | **~14x faster** |
| **RAM Consumption** | ~1,280 MB | **58 MB** | **95.5% reduction** |
| **Failure Rate** | ~12% (timeouts / crashes) | **< 0.5%** | **Rock-solid stability** |
| **Cost per Lead** | High compute bill | **~$0.038 USD (PPE)** | **Pay-Per-Event only** |

---

### 4. How the Lead-to-KYB Chain Works in Practice

We chained the directory scraper, impressum extractor, and KYB auditor into an automated pipeline:

```
[B2B Directory Query]
       │
       ▼ (Company Name, Domain, E.164 Phone)
[§ 5 DDG Impressum Crawl]
       │
       ▼ (Statutory Directors, Amtsgericht, HRB Number, USt-IdNr.)
[Official Handelsregister & Insolvency Audit]
       │
       ▼ (Legal Entity, Share Capital, Solvency Risk: SOLVENT)
[CRM / Database / Webhook Output]
```

---

### 5. Open Source Repository & Ready-to-Use Templates

We packaged everything into an open showcase repository with pre-built workflow templates:
- **n8n Workflow:** Importable JSON pipeline linking the 3 micro-services.
- **Make.com Blueprint:** Pre-built scenario with webhook trigger and data mapper.
- **MCP Server Config:** Native integration for Claude Desktop & Cursor IDE.
- **SDK Examples:** Ready-to-run Curl, Node.js (`esm`), and Python scripts.

Check out the code, sample datasets, and workflows here:  
👉 **GitHub:** [https://github.com/andregrunert-ctrl/german-b2b-data-suite](https://github.com/andregrunert-ctrl/german-b2b-data-suite)

What are your experiences scraping German public portals or dealing with ASP.NET viewstates and German character encodings? Happy to discuss in the comments! 💬
