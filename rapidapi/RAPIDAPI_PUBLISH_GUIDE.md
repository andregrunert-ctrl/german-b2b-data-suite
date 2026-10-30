# RapidAPI Studio Publish Guide 🚀⚡

Befolge diese 5 Schritte, um die Suite oder beliebige Einzel-APIs in 60 Sekunden auf RapidAPI zu veröffentlichen:

1. **API Importieren:** Öffne [RapidAPI Studio](https://rapidapi.com/studio) und klicke auf **"Add New API"** -> **"OpenAPI Document"** -> Wähle `rapidapi/00_unified_german_b2b_suite_openapi.json` (oder eine der Einzel-Dateien `01_*` bis `06_*`).
2. **Gateway-URL prüfen:** Bestätige die Base-URL `https://api.apify.com` unter **API Settings -> Target URL**.
3. **Secret Header / Transformation konfigurieren:**
   - Navigiere zu **Gateway -> Transformations** und klicke auf **"+ Add transformation"**.
   - **For:** `Request`
   - **Action:** `Add key`
   - **Key:** `request.header.Authorization`
   - **Key value type:** `Static`
   - **Key value:** `Bearer <DEIN_APIFY_TOKEN>` (z. B. `Bearer apify_api_...`)
   - **Overwrite value if exists:** `Aktiviert (Häkchen setzen)`
   - **Scope:** `All Endpoints`
   - **Plans:** `All Plans`
   - Klicke auf **"Save"**.
4. **Preise & Pläne einstellen:** Unter **Plans & Pricing** wählst du Freemium (z. B. 20 Free Requests/Monat, danach 0.05 $ / Call für KYB/Rechnungen).
5. **Veröffentlichen:** Klicke oben rechts auf **"Publish"** – deine API ist sofort im weltweiten RapidAPI-Marktplatz live, und RapidAPI handhabt Kreditkarten und Billing vollautomatisch!
