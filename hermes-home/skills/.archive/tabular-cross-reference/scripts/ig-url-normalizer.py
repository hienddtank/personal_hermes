#!/usr/bin/env python3
"""Fix broken Instagram URLs to proper https://www.instagram.com/... format.

Handles these broken patterns:
  - https://bare_handle (missing domain)
  - https://@handle (has @ prefix)
  - https://@handle.com (has @ + stray TLD on handle)
  - https://instagram.com/short (normalize to full www form)
  - https://dorislanghouseoftravel.net (non-IG URL stored as IG — extract handle, strip TLD)
  - https://Www.ourwholevillage.com (malformed "www" prefix on non-IG URL)
  - https://www.instagram.com/handle/profilecard/?igsh=... (profile card redirect — extract username)
  - https://www.instagram.com/reel/xxx (content link — extract profile handle from path)
  - https://www.instagram.com/p/xxx or /tv/xxx (post/tv links — extract profile handle)
  - Query params: ?igsh=..., ?hl=en, ?utm_source=... — always stripped

Usage: python ig-url-normalizer.py <csv_file> [output_file]
"""

import csv
import re


def fix_ig_url(ig):
    if not ig or not ig.strip():
        return ig
    ig = ig.strip()

    # Full IG URL with www — extract handle, strip ALL query params and trailing slashes
    m = re.match(r'^https://www\.instagram\.com/(.+)$', ig)
    if m:
        path_part = m.group(1)

        # Strip query params first (handles ?igsh=..., ?hl=en, ?utm_source=...)
        handle = path_part.split('?')[0]

        # Remove trailing slash
        handle = handle.rstrip('/')

        # Profile card redirect: /handle/profilecard/ → extract username before /profilecard/
        profile_card_match = re.match(r'^([^/]+)/profilecard(/.*)?$', handle)
        if profile_card_match:
            handle = profile_card_match.group(1)

        # Content links: /handle/reel/..., /handle/p/..., /handle/tv/... → extract username
        content_match = re.match(r'^([^/]+)/(?:reel|p|tv)/.*$', handle)
        if content_match:
            handle = content_match.group(1)

        return 'https://www.instagram.com/' + handle

    # Short form without www — normalize to full www form
    m = re.match(r'^https://instagram\.com/([^\s]+?)(?:\?.*)?$', ig)
    if m:
        handle = m.group(1).rstrip('./ ')
        return 'https://www.instagram.com/' + handle

    # @ prefix — strip it and any stray TLD
    m = re.match(r'^https://@([a-zA-Z0-9_.]+)', ig)
    if m:
        handle = m.group(1)
        handle = re.sub(r'\.(com|travel|net|org)$', '', handle).rstrip('./ ')
        return 'https://www.instagram.com/' + handle

    # Non-instagram bare URL — likely a data-entry mistake where company name was typed as the "URL"
    # e.g. "https://dorislanghouseoftravel.net" or "https://Www.ourwholevillage.com"
    if ig.startswith('https://') and 'instagram' not in ig.lower():
        rest = ig[len('https://'):].split('/')[0]
        rest = re.sub(r'^[Ww][Ww][Ww]\.', '', rest)
        handle = re.sub(r'\.(com|net|org|io|travel)$', '', rest, flags=re.IGNORECASE)
        if len(handle) > 2:
            return 'https://www.instagram.com/' + handle

    # Bare https:// with handle — insert domain
    m = re.match(r'^https://([a-zA-Z0-9_.@]+?)(?:\?.*)?$', ig)
    if m:
        handle = m.group(1).lstrip('@').rstrip('./ ')
        return 'https://www.instagram.com/' + handle

    return ig


def process_csv(input_path, output_path=None):
    """Fix IG URLs in a CSV and write the result. Outputs to same file if no output_path given."""
    if output_path is None:
        output_path = input_path

    with open(input_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    fixed_count = 0
    for r in rows:
        for col_name in reader.fieldnames:
            old_val = r.get(col_name, '').strip()
            new_val = fix_ig_url(old_val)
            if new_val != old_val and 'instagram' in (new_val + old_val).lower():
                fixed_count += 1
                r[col_name] = new_val

    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=reader.fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Fixed {fixed_count} Instagram URLs in {len(rows)} rows")


if __name__ == '__main__':
    import sys
    if len(sys.argv) < 2:
        print("Usage: python ig-url-normalizer.py <csv_file> [output_file]")
        sys.exit(1)
    process_csv(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
