"""Standalone MCP server exposing all 6 German & DACH B2B Apify Cloud Actors."""

from __future__ import annotations

import os
from typing import Annotated, Any, Literal

import httpx
from pydantic import Field

try:
    from mcp.server.mcpserver import MCPServer
except ImportError:  # Compatibility fallback for mcp 1.x
    from mcp.server.fastmcp import FastMCP as MCPServer  # type: ignore[no-redef]

APIFY_API_BASE_URL = os.environ.get("APIFY_API_BASE_URL", "https://api.apify.com/v2").rstrip("/")
APIFY_NAMESPACE = "AGrunert"
DEFAULT_TIMEOUT_SECONDS = 180.0

ACTOR_SLUGS: dict[str, str] = {
    "find_german_b2b_leads": "german-b2b-leads-directory-scraper",
    "enrich_german_impressum": "german-impressum-b2b-lead-enricher",
    "check_german_company_kyb": "german-company-kyb-insolvency-scraper",
    "search_german_public_tenders": "german-public-tenders-vergabe-scraper",
    "search_german_zvg_foreclosures": "german-real-estate-foreclosure-zvg-scraper",
    "process_german_einvoice": "german-e-invoice-zugferd-xrechnung-suite",
}

mcp = MCPServer(
    "german-b2b-data-suite",
    instructions=(
        "German & DACH B2B Data, Compliance & PropTech API Suite powered by Apify Cloud Actors. "
        "Provides Handelsregister KYB audits, official insolvency checks, § 5 DDG Impressum "
        "contact enrichment, service.bund.de public tenders, zvg-portal.de real estate "
        "foreclosures, Gelbe Seiten/11880 business leads, and ZUGFeRD/XRechnung e-invoicing. "
        "Set the APIFY_TOKEN environment variable before executing tools."
    ),
)


def _clean_payload(values: dict[str, Any]) -> dict[str, Any]:
    """Return payload copy omitting keys set to None."""
    return {key: value for key, value in values.items() if value is not None}


def _error_response(error_code: str, message: str, *, actor_slug: str, **extra: Any) -> dict[str, Any]:
    """Build a consistent non-crashing error payload for MCP callers."""
    payload: dict[str, Any] = {
        "status": "error",
        "error": error_code,
        "actor": f"{APIFY_NAMESPACE}/{actor_slug}",
        "message": message,
    }
    payload.update(extra)
    return payload


async def run_apify_actor(
    actor_slug: str,
    payload: dict[str, Any],
    *,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    token: str | None = None,
    http_client: httpx.AsyncClient | None = None,
) -> dict[str, Any]:
    """Execute an Apify Actor synchronously and return dataset items as structured output."""
    api_token = (token if token is not None else os.environ.get("APIFY_TOKEN", "")).strip()
    if not api_token:
        return _error_response(
            "MISSING_APIFY_TOKEN",
            (
                "APIFY_TOKEN environment variable is missing or empty. "
                "Create a free personal token ($5/month starter credits) at "
                "https://console.apify.com/account/integrations, explore all 6 actors & 13 public tasks at "
                "https://apify.com/AGrunert, and configure APIFY_TOKEN when launching german-b2b-mcp."
            ),
            actor_slug=actor_slug,
        )

    endpoint = f"{APIFY_API_BASE_URL}/acts/{APIFY_NAMESPACE}~{actor_slug}/run-sync-get-dataset-items"
    headers = {
        "Authorization": f"Bearer {api_token}",
        "Content-Type": "application/json",
    }

    try:
        if http_client is not None:
            response = await http_client.post(endpoint, json=payload, headers=headers)
        else:
            async with httpx.AsyncClient(timeout=timeout_seconds) as client:
                response = await client.post(endpoint, json=payload, headers=headers)
    except httpx.TimeoutException:
        return _error_response(
            "APIFY_TIMEOUT",
            f"Apify synchronous Actor call timed out after {timeout_seconds:.0f}s.",
            actor_slug=actor_slug,
        )
    except httpx.RequestError as exc:
        return _error_response(
            "APIFY_NETWORK_ERROR",
            f"Network error while contacting Apify API ({type(exc).__name__}).",
            actor_slug=actor_slug,
        )

    if response.status_code == 401:
        return _error_response(
            "INVALID_APIFY_TOKEN",
            "Apify rejected APIFY_TOKEN (HTTP 401 Unauthorized). Verify your token.",
            actor_slug=actor_slug,
            http_status=401,
        )

    if response.status_code not in (200, 201):
        detail = response.text[:400].strip()
        return _error_response(
            "APIFY_API_ERROR",
            f"Apify API returned HTTP {response.status_code}: {detail}",
            actor_slug=actor_slug,
            http_status=response.status_code,
        )

    try:
        data = response.json()
    except ValueError:
        return _error_response(
            "INVALID_APIFY_RESPONSE",
            "Apify API returned non-JSON content.",
            actor_slug=actor_slug,
            http_status=response.status_code,
        )

    items = data if isinstance(data, list) else [data]
    return {
        "status": "success",
        "actor": f"{APIFY_NAMESPACE}/{actor_slug}",
        "count": len(items),
        "items": items,
    }


async def _dispatch_actor_tool(
    actor_slug: str,
    payload: dict[str, Any],
    *,
    validation_error: str | None = None,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    """Check APIFY_TOKEN first, then validate inputs, then execute the Apify Actor."""
    if not os.environ.get("APIFY_TOKEN", "").strip():
        return await run_apify_actor(actor_slug, {}, timeout_seconds=timeout_seconds)
    if validation_error:
        return _error_response("INVALID_INPUT", validation_error, actor_slug=actor_slug)
    return await run_apify_actor(actor_slug, payload, timeout_seconds=timeout_seconds)


@mcp.tool()
async def find_german_b2b_leads(
    search_terms: Annotated[
        list[str] | None,
        Field(description="Trades, crafts, or industry keywords, e.g. ['Elektroinstallation', 'Solaranlagen']."),
    ] = None,
    locations: Annotated[
        list[str] | None,
        Field(description="German cities, regions, or 5-digit postal codes, e.g. ['München', 'Leipzig']."),
    ] = None,
    query: Annotated[
        str | None,
        Field(description="Single search keyword alternative when 'search_terms' is omitted."),
    ] = None,
    location: Annotated[
        str | None,
        Field(description="Single city or postal code alternative when 'locations' is omitted."),
    ] = None,
    require_website: Annotated[
        bool,
        Field(description="Only return businesses that have a corporate website/domain."),
    ] = False,
    require_phone: Annotated[
        bool,
        Field(description="Only return businesses that have a verified phone number."),
    ] = False,
    include_details: Annotated[
        bool,
        Field(description="Fetch directory detail pages for corporate emails and full descriptions."),
    ] = True,
    max_items: Annotated[
        int,
        Field(ge=1, le=5000, description="Maximum number of B2B leads to extract (1-5000)."),
    ] = 20,
) -> dict[str, Any]:
    """Search German B2B companies, crafts (Handwerker), and local businesses via 11880 & Gelbe Seiten."""
    actor_slug = ACTOR_SLUGS["find_german_b2b_leads"]
    validation_error = (
        "Provide at least 'search_terms' or 'query' to search German B2B directory leads."
        if not search_terms and not (query and query.strip())
        else None
    )
    payload = _clean_payload(
        {
            "search_terms": search_terms,
            "locations": locations,
            "query": query,
            "location": location,
            "require_website": require_website,
            "require_phone": require_phone,
            "include_details": include_details,
            "max_items": max_items,
        }
    )
    return await _dispatch_actor_tool(actor_slug, payload, validation_error=validation_error)


@mcp.tool()
async def enrich_german_impressum(
    domains: Annotated[
        list[str] | None,
        Field(description="List of DACH company domains or URLs, e.g. ['biontech.de', 'celonis.com']."),
    ] = None,
    url: Annotated[
        str | None,
        Field(description="Single company domain or website URL to enrich."),
    ] = None,
    extract_contact_page: Annotated[
        bool,
        Field(description="Also inspect /kontakt or /contact pages if email/phone is missing in Impressum."),
    ] = True,
    max_concurrency: Annotated[
        int,
        Field(ge=1, le=20, description="Number of concurrent domain lookups (1-20)."),
    ] = 5,
) -> dict[str, Any]:
    """Extract § 5 DDG / Impressum legal data, CEOs, de-obfuscated emails, phones, HRB & VAT IDs from DACH domains."""
    actor_slug = ACTOR_SLUGS["enrich_german_impressum"]
    validation_error = (
        "Provide either 'domains' (list) or 'url' (single domain/URL) for Impressum enrichment."
        if not domains and not (url and url.strip())
        else None
    )
    payload = _clean_payload(
        {
            "domains": domains,
            "url": url,
            "extract_contact_page": extract_contact_page,
            "max_concurrency": max_concurrency,
        }
    )
    return await _dispatch_actor_tool(actor_slug, payload, validation_error=validation_error)


@mcp.tool()
async def check_german_company_kyb(
    company_name: Annotated[
        str | None,
        Field(description="Full or partial legal name of a German company, e.g. 'BioNTech SE'."),
    ] = None,
    companies: Annotated[
        list[str | dict[str, Any]] | None,
        Field(description="Batch list of companies (names, 'Name | City | HRB' strings, or dicts)."),
    ] = None,
    city: Annotated[
        str | None,
        Field(description="Registered city / seat to narrow Handelsregister results, e.g. 'Mainz'."),
    ] = None,
    register_number: Annotated[
        str | None,
        Field(description="Commercial register number with or without prefix, e.g. 'HRB 48720'."),
    ] = None,
    register_type: Annotated[
        Literal["ALL", "HRB", "HRA", "GnR", "PR", "VR"],
        Field(description="Official German register type filter."),
    ] = "ALL",
    include_insolvency_check: Annotated[
        bool,
        Field(description="Cross-check against official insolvenzbekanntmachungen.de announcements."),
    ] = True,
    include_financial_details: Annotated[
        bool,
        Field(description="Parse XJustiz/SI XML filings for share capital, officers, and corporate purpose."),
    ] = True,
    request_delay_seconds: Annotated[
        int,
        Field(ge=0, le=10, description="Polite delay in seconds between sequential batch checks (0-10)."),
    ] = 1,
) -> dict[str, Any]:
    """Run a German KYB audit against official Handelsregister (XJustiz) and Insolvenzbekanntmachungen."""
    actor_slug = ACTOR_SLUGS["check_german_company_kyb"]
    validation_error = (
        "Provide either 'company_name' or 'companies' to run a German KYB check."
        if not (company_name and company_name.strip()) and not companies
        else None
    )
    payload = _clean_payload(
        {
            "company_name": company_name,
            "companies": companies,
            "city": city,
            "register_number": register_number,
            "register_type": register_type,
            "include_insolvency_check": include_insolvency_check,
            "include_financial_details": include_financial_details,
            "request_delay_seconds": request_delay_seconds,
        }
    )
    return await _dispatch_actor_tool(
        actor_slug,
        payload,
        validation_error=validation_error,
        timeout_seconds=300.0,
    )


@mcp.tool()
async def search_german_public_tenders(
    keywords: Annotated[
        list[str] | None,
        Field(description="Search keywords or topics, e.g. ['Software', 'Cloud', 'KI']."),
    ] = None,
    states: Annotated[
        list[str] | None,
        Field(description="Filter by German federal states (e.g. ['Bayern', 'Berlin']) or ['ALL']."),
    ] = None,
    service_type: Annotated[
        Literal[
            "ALL",
            "Dienstleistungen",
            "Bauleistungen",
            "Lieferleistungen",
            "Informationstechnik",
            "Forschung und Entwicklung",
        ],
        Field(description="Official German procurement category (Leistungsart)."),
    ] = "ALL",
    city: Annotated[
        str | None,
        Field(description="City name or 5-digit postal code of performance, e.g. 'München'."),
    ] = None,
    max_items: Annotated[
        int,
        Field(ge=1, le=5000, description="Maximum number of tender notices to retrieve (1-5000)."),
    ] = 20,
    include_details: Annotated[
        bool,
        Field(description="Retrieve deadlines, CPV codes, full descriptions, and document URLs."),
    ] = True,
) -> dict[str, Any]:
    """Search official German public procurement tenders (Ausschreibungen) on service.bund.de."""
    payload = _clean_payload(
        {
            "keywords": keywords,
            "states": states,
            "service_type": service_type,
            "city": city,
            "max_items": max_items,
            "include_details": include_details,
        }
    )
    return await _dispatch_actor_tool(ACTOR_SLUGS["search_german_public_tenders"], payload)


@mcp.tool()
async def search_german_zvg_foreclosures(
    states: Annotated[
        list[str] | None,
        Field(description="Federal state codes or names, e.g. ['by', 'be', 'sn'] or ['ALL']."),
    ] = None,
    city: Annotated[
        str | None,
        Field(description="Filter auctions by city name, e.g. 'Leipzig' or 'Berlin'."),
    ] = None,
    postal_code: Annotated[
        str | None,
        Field(description="Filter by 5-digit German postal code, e.g. '04109'."),
    ] = None,
    property_type: Annotated[
        Literal[
            "ALL",
            "Eigentumswohnung",
            "Einfamilienhaus",
            "Mehrfamilienhaus",
            "Doppelhaushälfte",
            "Reihenhaus",
            "Gewerbe",
            "Grundstück",
            "Garage",
        ],
        Field(description="Property category filter."),
    ] = "ALL",
    min_market_value: Annotated[
        int | None,
        Field(ge=0, description="Minimum judicial market valuation (Verkehrswert) in EUR."),
    ] = None,
    max_market_value: Annotated[
        int | None,
        Field(ge=0, description="Maximum judicial market valuation (Verkehrswert) in EUR."),
    ] = None,
    max_items: Annotated[
        int,
        Field(ge=1, le=5000, description="Maximum number of foreclosure properties to return (1-5000)."),
    ] = 20,
    include_details: Annotated[
        bool,
        Field(description="Fetch full descriptions, auction location, land register, and appraisal PDF URLs."),
    ] = True,
    include_cancelled: Annotated[
        bool,
        Field(description="Include cancelled foreclosure auctions."),
    ] = False,
    exclude_expired: Annotated[
        bool,
        Field(description="Exclude auctions whose scheduled date/time has already passed."),
    ] = True,
) -> dict[str, Any]:
    """Search German real estate foreclosure auctions (Zwangsversteigerungen) on zvg-portal.de."""
    payload = _clean_payload(
        {
            "states": states,
            "city": city,
            "postal_code": postal_code,
            "property_type": property_type,
            "min_market_value": min_market_value,
            "max_market_value": max_market_value,
            "max_items": max_items,
            "include_details": include_details,
            "include_cancelled": include_cancelled,
            "exclude_expired": exclude_expired,
        }
    )
    return await _dispatch_actor_tool(ACTOR_SLUGS["search_german_zvg_foreclosures"], payload)


@mcp.tool()
async def process_german_einvoice(
    operation: Annotated[
        Literal["generate", "embed", "extract"],
        Field(description="Operation mode: 'generate' (PDF/A-3 + XML), 'embed' (XML into PDF), or 'extract' (validate & parse)."),
    ] = "generate",
    profile: Annotated[
        Literal["EN16931", "EXTENDED", "BASIC", "XRECHNUNG_3_0"],
        Field(description="Target EN 16931 / ZUGFeRD / Factur-X / XRechnung profile."),
    ] = "EN16931",
    invoice_data: Annotated[
        dict[str, Any] | None,
        Field(description="Structured invoice JSON payload for 'generate' or 'embed' mode."),
    ] = None,
    file_url: Annotated[
        str | None,
        Field(description="Public HTTP/HTTPS URL of PDF or XML input for 'embed' or 'extract' mode."),
    ] = None,
    file_base64: Annotated[
        str | None,
        Field(description="Base64-encoded PDF or XML input alternative to 'file_url'."),
    ] = None,
    xml_url: Annotated[
        str | None,
        Field(description="Optional HTTP/HTTPS URL of existing ZUGFeRD/XRechnung XML for 'embed' mode."),
    ] = None,
    xml_base64: Annotated[
        str | None,
        Field(description="Optional Base64-encoded XML string for 'embed' mode."),
    ] = None,
) -> dict[str, Any]:
    """Generate PDF/A-3 invoices, embed ZUGFeRD/Factur-X XML, or validate/extract XRechnung 3.0 & EN 16931 e-invoices."""
    actor_slug = ACTOR_SLUGS["process_german_einvoice"]
    validation_error: str | None = None
    if operation == "generate" and not invoice_data:
        validation_error = "Provide 'invoice_data' JSON when operation='generate'."
    elif operation == "extract" and not file_url and not file_base64:
        validation_error = "Provide 'file_url' or 'file_base64' when operation='extract'."
    elif operation == "embed" and not file_url and not file_base64:
        validation_error = "Provide source PDF via 'file_url' or 'file_base64' when operation='embed'."

    payload = _clean_payload(
        {
            "operation": operation,
            "profile": profile,
            "invoice_data": invoice_data,
            "file_url": file_url,
            "file_base64": file_base64,
            "xml_url": xml_url,
            "xml_base64": xml_base64,
        }
    )
    return await _dispatch_actor_tool(actor_slug, payload, validation_error=validation_error)


def main() -> None:
    """Start the MCP server using stdio transport by default."""
    transport = os.environ.get("MCP_TRANSPORT", "stdio").strip().lower()
    if transport not in ("stdio", "sse", "streamable-http"):
        transport = "stdio"
    mcp.run(transport=transport)  # type: ignore[arg-type]


if __name__ == "__main__":
    main()
