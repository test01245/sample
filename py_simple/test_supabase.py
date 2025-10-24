#!/usr/bin/env python3
"""
Minimal Supabase connectivity test using PostgREST.

Reads SUPABASE_URL and SUPABASE_ANON_KEY from environment; falls back to the
project defaults from test_supabase.html for convenience. Performs a HEAD/COUNT
style query against the device_keys table and prints the result.

Usage:
  python py_simple/test_supabase.py

Optionally override:
  set SUPABASE_URL, SUPABASE_ANON_KEY
"""
import os
import sys
import json
import requests

SUPABASE_URL = os.getenv("SUPABASE_URL", "https://mawhbwogynurfbacxnyh.supabase.co")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im1hd2hid29neW51cmZiYWN4bnloIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjA2NDY2MjEsImV4cCI6MjA3NjIyMjYyMX0.KX1MKm74NRMC9Nb1yg4FyDxWFChboD796hFyTz92q_k")

REST_ENDPOINT = f"{SUPABASE_URL}/rest/v1/device_keys?select=id&limit=1"
HEADERS = {
    "apikey": SUPABASE_ANON_KEY,
    "Authorization": f"Bearer {SUPABASE_ANON_KEY}",
    "Accept": "application/json",
    "Prefer": "count=exact",
}

def main():
    try:
        r = requests.get(REST_ENDPOINT, headers=HEADERS, timeout=15)
        ok = r.ok
        count = r.headers.get("content-range")
        try:
            data = r.json()
        except Exception:
            data = None
        print(json.dumps({
            "ok": ok,
            "status": r.status_code,
            "content_range": count,
            "sample_row": data[0] if isinstance(data, list) and data else None,
        }, indent=2))
        sys.exit(0 if ok else 1)
    except Exception as e:
        print(json.dumps({"ok": False, "error": str(e)}))
        sys.exit(2)

if __name__ == "__main__":
    main()
