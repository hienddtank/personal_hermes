#!/usr/bin/env python3
"""
SPA API Crawler Template
For sites where the API is hidden inside a JS bundle.
Adapted from TravelLeaders.com crawl (23,582 agents in 3 API calls).

Steps:
1. Find JS bundle (script src="/assets/index-*.js")
2. Search bundle for fetch/axios calls → API endpoints
3. Find API base URL variable (const po="", const base="...")
4. Call API directly with Referer/Origin headers
"""
import requests
import re
import csv
import time
from pathlib import Path

BASE_URL = "https://example.com"
API_ENDPOINT = "/agent/getItems"
OUTPUT = Path("/tmp/scraped.csv")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Accept": "application/json",
    "Referer": f"{BASE_URL}/",
}

def discover_api(bundle_url):
    """Download JS bundle and search for API patterns."""
    r = requests.get(bundle_url, headers=HEADERS, timeout=30)
    bundle = r.text
    print(f"Bundle: {len(bundle)} bytes")
    fetches = re.findall(r'fetch\(["\']([^"\']+)["\']', bundle)
    for p in sorted(set(fetches))[:20]:
        print(f"  {p}")
    return bundle

def fetch_page(page=0, page_size=100):
    url = f"{BASE_URL}{API_ENDPOINT}?CurrentPage={page}&PageSize={page_size}"
    r = requests.get(url, headers=HEADERS, timeout=60)
    r.raise_for_status()
    return r.json()

def main():
    all_items = []
    for page in range(10):  # Safety limit
        data = fetch_page(page=page, page_size=10000)
        items = data.get('data', {}).get('agent', [])  # Adapt
        if not items:
            break
        all_items.extend(items)
        print(f"Page {page}: {len(items)} items (total: {len(all_items)})")
        if len(items) < 10000:
            break
        time.sleep(0.5)

    with open(OUTPUT, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['id', 'name', 'city', 'state', 'email'])
        writer.writeheader()
        for item in all_items:
            writer.writerow({
                'id': item.get('id', ''),
                'name': item.get('name', ''),
                'city': item.get('city', ''),
                'state': item.get('state', ''),
                'email': item.get('email', ''),
            })
    print(f"Saved {len(all_items)} items to {OUTPUT}")
