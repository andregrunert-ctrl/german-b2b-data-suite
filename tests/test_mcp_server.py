import json
import os
import sys
from pathlib import Path

import httpx
import pytest
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

ROOT_DIR = Path(__file__).resolve().parent.parent
SRC_DIR = ROOT_DIR / "src"
sys.path.insert(0, str(SRC_DIR))

import german_b2b_mcp.server as srv  # noqa: E402

EXPECTED_TOOLS = {
    "find_german_b2b_leads": "german-b2b-leads-directory-scraper",
    "enrich_german_impressum": "german-impressum-b2b-lead-enricher",
    "check_german_company_kyb": "german-company-kyb-insolvency-scraper",
    "search_german_public_tenders": "german-public-tenders-vergabe-scraper",
    "search_german_zvg_foreclosures": "german-real-estate-foreclosure-zvg-scraper",
    "process_german_einvoice": "german-e-invoice-zugferd-xrechnung-suite",
}


@pytest.mark.anyio
async def test_stdio_protocol_tools_list_and_missing_token_without_env(monkeypatch):
    """Spawn the real MCP server over stdio with no APIFY_TOKEN and verify tools/list + safe error."""
    monkeypatch.delenv("APIFY_TOKEN", raising=False)
    clean_env = {k: v for k, v in os.environ.items() if k != "APIFY_TOKEN"}
    existing_pp = clean_env.get("PYTHONPATH", "")
    clean_env["PYTHONPATH"] = f"{SRC_DIR}{os.pathsep}{existing_pp}" if existing_pp else str(SRC_DIR)

    server_params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "german_b2b_mcp.server"],
        env=clean_env,
        cwd=str(ROOT_DIR),
    )

    async with stdio_client(server_params) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            init_result = await session.initialize()
            assert init_result.server_info.name == "german-b2b-data-suite"

            tools_result = await session.list_tools()
            names = {tool.name for tool in tools_result.tools}
            assert names == set(EXPECTED_TOOLS)
            for tool in tools_result.tools:
                assert tool.description
                assert tool.input_schema.get("type") == "object"

            call_result = await session.call_tool(
                "check_german_company_kyb",
                {"company_name": "BioNTech SE"},
            )
            assert not call_result.is_error
            text_payload = json.loads(call_result.content[0].text)
            assert text_payload["status"] == "error"
            assert text_payload["error"] == "MISSING_APIFY_TOKEN"
            assert "APIFY_TOKEN" in text_payload["message"]
            assert call_result.structured_content == text_payload


@pytest.mark.anyio
async def test_all_six_tools_route_to_correct_actor_with_mock_http(monkeypatch):
    """Verify all 6 MCP tools hit the expected Apify Actor endpoint using Bearer auth."""
    monkeypatch.setenv("APIFY_TOKEN", "apify_api_test_secret_token")
    captured: list[dict[str, object]] = []

    async def fake_run(actor_slug: str, payload: dict, **_kwargs):
        captured.append({"actor_slug": actor_slug, "payload": payload})
        return {
            "status": "success",
            "actor": f"AGrunert/{actor_slug}",
            "count": 1,
            "items": [{"ok": True, "actor": actor_slug}],
        }

    monkeypatch.setattr(srv, "run_apify_actor", fake_run)

    await srv.find_german_b2b_leads(search_terms=["Elektroinstallation"], locations=["München"], max_items=5)
    await srv.enrich_german_impressum(domains=["biontech.de"])
    await srv.check_german_company_kyb(company_name="BioNTech SE", city="Mainz")
    await srv.search_german_public_tenders(keywords=["Software"], max_items=5)
    await srv.search_german_zvg_foreclosures(states=["sn"], min_market_value=100000, max_items=5)
    await srv.process_german_einvoice(operation="generate", invoice_data={"invoice_number": "RE-1"})

    assert [c["actor_slug"] for c in captured] == list(EXPECTED_TOOLS.values())
    assert captured[0]["payload"]["search_terms"] == ["Elektroinstallation"]
    assert "query" not in captured[0]["payload"]
    assert captured[2]["payload"]["company_name"] == "BioNTech SE"
    assert captured[4]["payload"]["min_market_value"] == 100000
    assert captured[5]["payload"]["operation"] == "generate"


@pytest.mark.anyio
async def test_run_apify_actor_uses_bearer_header_and_handles_http_errors():
    """Ensure APIFY_TOKEN is sent in Authorization header (never query string) and errors don't crash."""
    seen_requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_requests.append(request)
        if "unauthorized" in str(request.url):
            return httpx.Response(401, json={"error": {"message": "Invalid token"}})
        return httpx.Response(200, json=[{"company_name": "BioNTech SE"}])

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        ok = await srv.run_apify_actor(
            "german-company-kyb-insolvency-scraper",
            {"company_name": "BioNTech SE"},
            token="apify_api_dummy_token",
            http_client=client,
        )
        assert ok["status"] == "success"
        assert ok["count"] == 1
        assert ok["items"][0]["company_name"] == "BioNTech SE"
        assert "token=" not in str(seen_requests[0].url)
        assert seen_requests[0].headers["Authorization"] == "Bearer apify_api_dummy_token"

        unauth = await srv.run_apify_actor(
            "unauthorized-actor",
            {"company_name": "BioNTech SE"},
            token="apify_api_bad",
            http_client=client,
        )
        assert unauth["status"] == "error"
        assert unauth["error"] == "INVALID_APIFY_TOKEN"
        assert unauth["http_status"] == 401


@pytest.mark.anyio
async def test_input_validation_guards_when_token_is_present(monkeypatch):
    """Validate logical input guards block empty calls before making Apify HTTP calls."""
    monkeypatch.setenv("APIFY_TOKEN", "apify_api_test")

    r1 = await srv.find_german_b2b_leads()
    r2 = await srv.enrich_german_impressum()
    r3 = await srv.check_german_company_kyb()
    r4 = await srv.process_german_einvoice(operation="extract")

    for res in (r1, r2, r3, r4):
        assert res["status"] == "error"
        assert res["error"] == "INVALID_INPUT"


def test_manifests_and_glama_schema():
    """Verify glama.json and smithery.yaml point to the local Python MCP server & Dockerfile."""
    glama = json.loads((ROOT_DIR / "glama.json").read_text(encoding="utf-8"))
    assert glama["$schema"] == "https://glama.ai/mcp/schemas/server.json"
    assert "andregrunert-ctrl" in glama["maintainers"]
    assert glama["server"]["command"] == "python"
    assert glama["server"]["args"] == ["-m", "german_b2b_mcp.server"]
    assert "APIFY_TOKEN" in glama["server"]["env"]

    smithery = (ROOT_DIR / "smithery.yaml").read_text(encoding="utf-8")
    assert 'runtime: "container"' in smithery
    assert 'dockerfile: "Dockerfile"' in smithery
    assert "python" in smithery and "german_b2b_mcp.server" in smithery
    assert (ROOT_DIR / "Dockerfile").exists()
