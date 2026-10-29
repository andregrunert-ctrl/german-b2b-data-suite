#!/usr/bin/env python3
"""
Automated Upload Script for RapidAPI
Uploads 00_unified_german_b2b_suite_openapi.json to RapidAPI Hub via the Provisioning / Platform API.
"""

import os
import sys
import json
import requests

SPEC_PATH = os.path.join(os.path.dirname(__file__), "00_unified_german_b2b_suite_openapi.json")

def upload_to_rapidapi(api_key=None, api_id=None):
    key = api_key or os.environ.get("RAPIDAPI_KEY")
    if not key:
        print("[ERROR] No RAPIDAPI_KEY provided.")
        print("Usage:")
        print("  python upload_to_rapidapi.py <RAPIDAPI_KEY> [RAPIDAPI_API_ID]")
        print("Or set RAPIDAPI_KEY=<your-key> in .env")
        return False

    if not os.path.exists(SPEC_PATH):
        print(f"[ERROR] Specification file not found: {SPEC_PATH}")
        return False

    with open(SPEC_PATH, "r", encoding="utf-8") as f:
        spec_content = f.read()

    print(f"[*] Loaded specification from {SPEC_PATH} ({len(spec_content)} bytes)")

    # If an API ID already exists, update its specification via OpenAPI provisioning API
    if api_id:
        url = f"https://openapi-provisioning.p.rapidapi.com/v1/apis/{api_id}"
        headers = {
            "x-rapidapi-host": "openapi-provisioning.p.rapidapi.com",
            "x-rapidapi-key": key
        }
        files = {
            "file": ("00_unified_german_b2b_suite_openapi.json", open(SPEC_PATH, "rb"), "application/json")
        }
        print(f"[*] Updating existing RapidAPI project {api_id}...")
        resp = requests.put(url, headers=headers, files=files)
        print(f"[*] Response [{resp.status_code}]: {resp.text}")
        return resp.status_code in (200, 201, 204)
    else:
        # Create a new API project via RapidAPI Platform API
        url = "https://platform.p.rapidapi.com/v1/apis/rapidapi-file/admin"
        headers = {
            "x-rapidapi-host": "platform.p.rapidapi.com",
            "x-rapidapi-key": key
        }
        files = {
            "file": ("00_unified_german_b2b_suite_openapi.json", open(SPEC_PATH, "rb"), "application/json")
        }
        print("[*] Creating new API project on RapidAPI...")
        resp = requests.post(url, headers=headers, files=files)
        print(f"[*] Response [{resp.status_code}]: {resp.text}")
        return resp.status_code in (200, 201)

if __name__ == "__main__":
    api_key_arg = sys.argv[1] if len(sys.argv) > 1 else None
    api_id_arg = sys.argv[2] if len(sys.argv) > 2 else None
    success = upload_to_rapidapi(api_key_arg, api_id_arg)
    sys.exit(0 if success else 1)
