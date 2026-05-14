"""
SPA Bulk Crawler Template — Fast list API + per-record enrichment.

Pattern for SPAs that have:
1. A paginated list endpoint returning N items in few requests
2. Optional detail endpoint for richer fields per item

Usage:
  python spa-bulk-crawler.py --list-endpoint URL --id-field FIELD [--bio-endpoint URL] [--output FILE]

Adapt the extract_connect() and extract_socials() functions per SPA's response format.
"""
import requests
import csv
import json
import os
import argparse
from html import unescape

# ============================================================
# CONFIG — customize these for your target SPA
# ============================================================

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json",
    "Referer": "https://TARGET_DOMAIN/",
}

LIST_ENDPOINT = "https://TARGET_DOMAIN/api/endpoint"
DETAIL_ENDPOINT = None  # Set if per-record detail API exists
PAGE_SIZE = 10000
MAX_PAGES = None  # None = auto-detect based on totalAgents


# ============================================================
# EXTRACTORS — customize per SPA response shape
# ============================================================

def extract_socials(connect_list, social_type):
    """Extract a specific social URL from connect[]-style list."""
    if not isinstance(connect_list, list):
        return ""
    for c in connect_list:
        if isinstance(c, dict):
            method = (c.get("contactMethod", "") or "").lower()
            value = c.get("contactValue", "") or ""
            if social_type in method and "http" in value:
                return value
    return ""


def extract_field(agent, field_name):
    """Safely extract a nested field from an agent dict."""
    val = agent.get(field_name)
    if isinstance(val, str):
        try:
            parsed = json.loads(val)
            return "; ".join(parsed) if isinstance(parsed, list) else parsed
        except (json.JSONDecodeError, TypeError):
            return val if len(val) < 500 else val[:497] + "..."
    elif isinstance(val, list):
        items = []
        for v in val:
            if isinstance(v, dict):
                k = next(iter(v))  # {name: value} pattern
                items.append(str(v[k]) if v[k] else "")
            elif isinstance(v, str):
                items.append(v)
        return "; ".join(items[:20])
    elif val is not None:
        return str(val)[:500]
    return ""


# ============================================================
# CORE LOGIC
# ============================================================

def download_list_page(url, headers, page, page_size):
    """Download one page of list results. Returns (agents_list, total_count)."""
    resp = requests.get(
        url,
        params={"CurrentPage": page, "PageSize": page_size},
        headers=headers,
        timeout=60,
    )
    data = resp.json()
    agents = data["data"]["agent"] if isinstance(data.get("data"), dict) else []
    total = data["data"].get("totalAgents", len(agents))
    return agents, total


def fetch_detail(agent_id, detail_endpoint, headers):
    """Fetch per-record detail. Returns enriched dict or None."""
    if not detail_endpoint:
        return None
    try:
        resp = requests.get(
            f"{detail_endpoint}?agentId={agent_id}",
            headers=headers,
            timeout=10,
        )
        data = resp.json()
        if data.get("responseStatus") != 1:
            return None
        detail = data["data"]
        # Customize these field names per SPA
        return {
            "bioText": detail.get("bioText", ""),
            "expertiseOverview": detail.get("expertiseOverview", ""),
            "certifications": "; ".join(
                f for k, f in detail.items() if k.startswith("cert") and f
            ),
        }
    except Exception:
        return None


def save_checkpoint(state, path):
    """Atomic checkpoint save."""
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(state, f)
    os.replace(tmp, path)


def load_checkpoint(path):
    """Load checkpoint or return empty set."""
    try:
        with open(path) as f:
            return set(json.load(f))
    except (FileNotFoundError, json.JSONDecodeError):
        return set()


# ============================================================
# MAIN WORKFLOW
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="SPA Bulk Crawler")
    parser.add_argument("--list-endpoint", required=True, help="List API URL")
    parser.add_argument("--detail-endpoint", default=None, help="Detail API URL (optional)")
    parser.add_argument("--output", default="./output.csv", help="Output CSV path")
    parser.add_argument("--checkpoint", default=None, help="Checkpoint file path")
    parser.add_argument("--page-size", type=int, default=PAGE_SIZE)
    args = parser.parse_args()

    checkpoint_path = args.checkpoint or (args.output + ".checkpoint.json")

    print(f"Downloading from: {args.list_endpoint}")
    
    # Phase 1: Download ALL items via list API (fast)
    all_agents = []
    page = 0
    
    while True:
        agents, total = download_list_page(args.list_endpoint, HEADERS, page, args.page_size)
        if not agents:
            break
        all_agents.extend(agents)
        print(f"  Page {page}: {len(agents)} agents (total so far: {len(all_agents)})")
        
        if MAX_PAGES and page >= MAX_PAGES - 1:
            break
        if len(agents) < args.page_size // 2:  # Last partial page
            break
        page += 1

    print(f"\nTotal agents from list API: {len(all_agents)}")

    # Phase 2: Extract all fields that come from the list response
    fieldnames = ["agentId"]  # Will be populated dynamically
    seen_ids = set()
    enriched_rows = []

    for agent in all_agents:
        aid = str(agent.get("agentId", ""))
        row = {"agentId": aid}
        
        # Extract flat fields from list response
        for key in ["firstName", "lastName", "city", "state", "zip",
                     "agencyName", "hostAgency", "email", "phone",
                     "websiteDisplayTitle", "yearsActive", "agentRating"]:
            row[key] = extract_field(agent, key)

        # Extract social links from connect[] — this is the FREE data!
        connects = agent.get("connect", [])
        row["linkedin_url"] = extract_socials(connects, "linkedin")
        row["instagram_url"] = extract_socials(connects, "instagram")
        row["facebook_url"] = extract_socials(connects, "facebook")
        row["blog_url"] = extract_socials(connects, "blog")
        row["youtube_url"] = extract_socials(connects, "youtube")
        row["pinterest_url"] = extract_socials(connects, "pinterest")

        # Extract nested lists as semicolon-separated strings
        row["interests_full"] = extract_field(agent, "interest")
        row["destinations_full"] = extract_field(agent, "destination")
        row["specialties_full"] = extract_field(agent, "specialtyGroup")

        enriched_rows.append(row)
        seen_ids.add(aid)

    # Phase 3: Optional — fetch detail endpoint for bioText/etc.
    if args.detail_endpoint:
        print(f"Phase 3: Enriching with detail endpoint ({args.detail_endpoint})...")
        processed = load_checkpoint(checkpoint_path)
        
        for i, agent in enumerate(all_agents):
            aid = str(agent.get("agentId", ""))
            if aid in processed:
                # Restore from checkpoint (no re-fetch)
                continue
            
            detail = fetch_detail(aid, args.detail_endpoint, HEADERS)
            if detail:
                row_idx = next(
                    (j for j, r in enumerate(enriched_rows) if r["agentId"] == aid), None
                )
                if row_idx is not None:
                    enriched_rows[row_idx].update(detail)
            
            processed.add(aid)
            if i % 500 == 0:
                pct = len(processed) / len(all_agents) * 100
                print(f"  {len(processed):,}/{len(all_agents):,} ({pct:.1f}%)")
            
            # Save checkpoint every iteration for crash safety
            if i % 10 == 0:
                save_checkpoint(list(processed), checkpoint_path)

    # Phase 4: Write output CSV
    fieldnames = set()
    for row in enriched_rows:
        fieldnames.update(row.keys())
    fieldnames = sorted(fieldnames)

    with open(args.output, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(enriched_rows)

    print(f"\n✅ Wrote {args.output}")
    print(f"   Columns: {len(fieldnames)}")
    print(f"   Records: {len(enriched_rows):,}")
    
    # Summary stats for social links
    linkedin = sum(1 for r in enriched_rows if r.get("linkedin_url"))
    instagram = sum(1 for r in enriched_rows if r.get("instagram_url"))
    print(f"\n📊 Social link coverage:")
    print(f"   LinkedIn:      {linkedin:,}")
    print(f"   Instagram:     {instagram:,}")


if __name__ == "__main__":
    main()
