#!/usr/bin/env python3
"""
Web Crawler Template — Playwright-based authenticated crawler.

Adapt this scaffold for any JS-rendered site that requires login.
Key features already baked in: persistent session, checkpointing,
rate limiting, error handling, and incremental CSV output.

Usage:
    python crawler_template.py --first-run      # interactive login
    python crawler_template.py                  # resume batch mode
    python crawler_template.py --headless       # headless (after first login)
"""

import argparse
import asyncio
import csv
import json
import os
import random
import sys
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import quote_plus

try:
    from playwright.async_api import async_playwright
except ImportError:
    print("ERROR: pip install playwright && playwright install chromium")
    sys.exit(1)

# ─── CONFIG — override these for your target site ──────────────────────────
SCRIPT_DIR = Path(__file__).parent

# Input data file (CSV with rows to search for)
INPUT_CSV = SCRIPT_DIR / "input_data.csv"

# Output directory and prefix
OUTPUT_DIR = SCRIPT_DIR / "output"
OUTPUT_PREFIX = "crawl_results"

# Browser session persistence directory
SESSION_DIR = SCRIPT_DIR / ".browser_session"

# Rate limits (seconds)
MIN_DELAY = 4.0
MAX_DELAY = 9.0

# Page timeout
PAGE_TIMEOUT = 30_000  # ms

# Checkpoint file
CHECKPOINT_FILE = SCRIPT_DIR / ".crawl_checkpoint.json"


def build_search_url(name: str, extra: str = "") -> str:
    """
    Build the search URL for your target site.
    Override this function to match your site's URL format.
    """
    query = name.strip()
    if extra:
        query += f" {extra.strip()}"
    params = f"keywords={quote_plus(query)}&origin=GLOBAL_SEARCH_HEADER"
    return f"https://TARGET_SITE/search?{params}"


def build_profile_url(raw_href: str) -> str | None:
    """
    Clean and validate a profile URL from search results.
    Override to match your site's URL pattern.
    """
    if not raw_href:
        return None
    # Remove query params, ensure absolute URL
    url = raw_href.split('?')[0]
    if not url.startswith('http'):
        url = 'https://TARGET_SITE' + url
    return url.rstrip('/')


# ─── CHECKPOINT SYSTEM ─────────────────────────────────────────────────────

def load_checkpoint() -> dict:
    if CHECKPOINT_FILE.exists():
        with open(CHECKPOINT_FILE) as f:
            return json.load(f)
    return {"processed": [], "failed": [], "last_run": None}


def save_checkpoint(state: dict):
    tmp = CHECKPOINT_FILE.with_suffix(".tmp")
    with open(tmp, "w") as f:
        json.dump(state, f, indent=2)
    os.replace(tmp, CHECKPOINT_FILE)


# ─── DATA LOADER ───────────────────────────────────────────────────────────

def load_data(csv_path: Path) -> list[dict]:
    with open(csv_path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return [{k.strip(): v.strip() if v else "" for k, v in row.items()} for row in reader]


# ─── CRAWLER CLASS ─────────────────────────────────────────────────────────

class WebCrawler:
    """Generic Playwright-based crawler with session persistence."""

    def __init__(self, headless: bool = False):
        self.headless = headless
        self.browser = None
        self.page = None
        self.playwright = None

    async def launch(self):
        pw = await async_playwright().start()
        self.browser = await pw.chromium.launch_persistent_context(
            user_data_dir=str(SESSION_DIR),
            headless=self.headless,
            viewport={"width": 1280, "height": 900},
            locale="en-US",
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 Chrome/125.0.0.0 Safari/537.36"
            ),
        )
        self.playwright = pw
        pages = self.browser.pages
        self.page = pages[0] if pages else await self.browser.new_page()

    async def login(self, login_url: str, feed_url: str):
        """Handle login — auto-detect session or force interactive login."""
        # Test if already logged in
        try:
            await self.page.goto(feed_url, timeout=10000)
            if "login" not in self.page.url.lower():
                print("Existing session detected.")
                return
        except Exception:
            pass

        # Force login
        print(f"Logging in to {login_url}...")
        await self.page.goto(login_url, timeout=30000)

        # Wait for user to complete login (headed mode required for first run)
        while True:
            await asyncio.sleep(1)
            if feed_url.split('?')[0] in self.page.url or "/feed" in self.page.url or "/home" in self.page.url:
                print("Login complete.")
                # Dismiss any popups
                try:
                    for btn in await self.page.query_selector_all(".modal__dismiss, .close-btn"):
                        await btn.click()
                except Exception:
                    pass
                break

    async def search_and_extract(self, name: str, company: str = "") -> dict | None:
        """
        Search and extract data for one entity.
        Override this method for your site-specific selectors.
        Returns a dict with extracted fields or error status.
        """
        url = build_search_url(name, company)
        
        try:
            await self.page.goto(url, timeout=PAGE_TIMEOUT)
        except Exception as e:
            return {"name": name, "status": f"error_navigate: {str(e)[:80]}"}

        # Check for captcha block
        if "captcha" in self.page.url or "checkpoint" in self.page.url:
            return {"name": name, "status": "captcha_blocked"}

        # Wait for results
        try:
            await self.page.wait_for_selector("a[href*='/profile/']", timeout=15000)
        except Exception:
            return {"name": name, "status": "no_results"}

        # Extract data via JS evaluation
        result = await self.page.evaluate("""() => {
            const link = document.querySelector('a[href*="/profile/"]');
            if (!link) return null;
            
            let href = link.getAttribute('href') || '';
            let profileUrl = href.split('?')[0];
            if (!profileUrl.startsWith('http')) profileUrl = 'https://TARGET_SITE' + profileUrl;
            profileUrl = profileUrl.replace(/\\/+$/, '');
            
            const card = link.closest('[data-entity-urn]');
            let title = '', company = '';
            if (card) {
                const items = Array.from(card.querySelectorAll('.text-body-small, .title'))
                    .map(e => e.innerText.trim())
                    .filter(t => t);
                title = items[0] || '';
                company = items[1] || '';
            }
            
            return { profileUrl, title, company };
        }""")

        if not result or not result.get("profileUrl"):
            return {"name": name, "status": "no_match"}

        # Visit profile for richer data (optional — increases detection risk)
        try:
            await self.page.goto(result["profileUrl"], timeout=PAGE_TIMEOUT)
            await asyncio.sleep(2)
            
            profile_data = await self.page.evaluate("""() => {
                const headline = document.querySelector('.headline')?.innerText.trim() || '';
                return { headline };
            }""")
            if profile_data.get("headline"):
                result["title"] = profile_data["headline"]
        except Exception:
            pass

        result["name"] = name
        result["status"] = "found"
        return result

    async def close(self):
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()


# ─── MAIN CRAWL LOOP ──────────────────────────────────────────────────────

async def crawl(data: list[dict], crawler: WebCrawler, output_file: Path):
    state = load_checkpoint()
    processed_ids = set(state.get("processed", []))
    failed = state.get("failed", [])

    queue = [(i, person) for i, person in enumerate(data) if str(i) not in processed_ids]
    
    if not queue:
        print("All records processed. Done.")
        return

    print(f"Crawl starting: {len(queue)} records remaining ({len(processed_ids)} done)")

    # Define fieldnames once
    fieldnames = ["Name", "Company", "linkedin_url", "status"]  # extend as needed
    file_exists = output_file.exists() and output_file.stat().st_size > 0
    
    start_time = time.time()
    success = errors = 0

    for idx, (i, person) in enumerate(queue):
        name = person.get("Name", "")
        company = person.get("Company", "")
        
        done = len(processed_ids) + idx
        pct = round((done / max(len(data), 1)) * 100, 1)
        eta = ""
        try:
            elapsed = time.time() - start_time
            avg = elapsed / max(done, 1)
            remaining = (len(queue) - idx) * avg
            eta = f" ETA: {int(remaining//60)}m{int(remaining%60)}s"
        except Exception:
            pass
        
        print(f"[{done}/{len(data)}] {pct}%{eta} - {name} @ {company}")

        result = await crawler.search_and_extract(name, company)

        output_row = dict(person)
        if result:
            for k in ("status", "linkedin_url", "title", "company_source", "name"):
                output_row[k] = result.get(k, "")
            if result.get("status") == "found":
                success += 1
            else:
                errors += 1
        else:
            output_row["status"] = "error_no_response"
            errors += 1

        # Write incrementally (safety net)
        with open(output_file, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames + [k for k in output_row if k not in fieldnames])
            if not file_exists:
                writer.writeheader()
                file_exists = True
            writer.writerow({k: output_row.get(k, "") for k in fieldnames})

        # Update checkpoint
        processed_ids.add(str(i))
        if result and result.get("status") not in ("found",):
            failed.append(str(i))
        save_checkpoint({"processed": list(processed_ids), "failed": failed, "last_run": datetime.now().isoformat()})

        # Rate limiting
        await asyncio.sleep(random.uniform(MIN_DELAY, MAX_DELAY))

    print(f"\nDone! Found: {success}, Errors: {errors}, Total processed: {len(processed_ids)}")


# ─── CLI ───────────────────────────────────────────────────────────────────

async def main():
    parser = argparse.ArgumentParser(description="Web Crawler Template")
    parser.add_argument("--csv", type=Path, default=INPUT_CSV)
    parser.add_argument("--login-url", default="https://TARGET_SITE/login")
    parser.add_argument("--feed-url", default="https://TARGET_SITE/feed/")
    parser.add_argument("--first-run", action="store_true")
    parser.add_argument("--force-login", action="store_true")
    parser.add_argument("--headless", action="store_true")
    args = parser.parse_args()

    # Setup output
    OUTPUT_DIR.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = OUTPUT_DIR / f"{OUTPUT_PREFIX}_{timestamp}.csv"

    if args.force_login and SESSION_DIR.exists():
        import shutil
        shutil.rmtree(SESSION_DIR)

    data = load_data(args.csv)
    print(f"Loaded {len(data)} records from {args.csv}")

    crawler = WebCrawler(headless=args.headless)
    await crawler.launch()
    await crawler.login(args.login_url, args.feed_url)
    await crawl(data, crawler, output_file)
    await crawler.close()


if __name__ == "__main__":
    asyncio.run(main())
