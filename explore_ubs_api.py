#!/usr/bin/env python3
"""
Helper script to discover the API endpoint used by ubslifestyle.com
when clicking the historical date range buttons.

Run once:
    python -m playwright install chromium
    python explore_ubs_api.py

It will print every intercepted network request and save the full
JSON responses to data/raw/ubs_api_responses/ so you can inspect them.
"""

import json
import os
from playwright.sync_api import sync_playwright

OUTPUT_DIR = "data/raw/ubs_api_responses"
os.makedirs(OUTPUT_DIR, exist_ok=True)

TARGET_URL   = "https://ubslifestyle.com/harga-buyback-hari-ini/"
RANGE_BUTTON = "3 Tahun"


def run():
    captured = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)  # headless=False so you can watch
        context = browser.new_context()
        page    = context.new_page()

        def on_response(response):
            content_type = response.headers.get("content-type", "")
            if "json" in content_type or "javascript" in content_type:
                try:
                    body = response.json()
                    captured.append({
                        "url":    response.url,
                        "status": response.status,
                        "body":   body,
                    })
                    print(f"[JSON] {response.status} {response.url}")
                except Exception:
                    pass

        page.on("response", on_response)

        print(f"Loading {TARGET_URL} ...")
        page.goto(TARGET_URL, wait_until="networkidle", timeout=30000)

        print(f"Clicking '{RANGE_BUTTON}' button...")
        try:
            page.get_by_text(RANGE_BUTTON, exact=True).first.click()
        except Exception:
            page.get_by_text(RANGE_BUTTON).first.click()

        page.wait_for_timeout(5000)

        browser.close()

    print(f"\n{len(captured)} JSON response(s) intercepted.\n")

    for i, item in enumerate(captured):
        out_path = os.path.join(OUTPUT_DIR, f"response_{i}.json")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(item, f, indent=2, ensure_ascii=False)
        print(f"  Saved: {out_path}")
        print(f"  URL  : {item['url']}")
        print(f"  Keys : {list(item['body'].keys()) if isinstance(item['body'], dict) else type(item['body']).__name__}")
        print()

    if not captured:
        print("Nothing intercepted. The data may be embedded in the page HTML.")
        print("Check data/raw/ubs_api_responses/ and also inspect manually via browser DevTools.")


if __name__ == "__main__":
    run()
