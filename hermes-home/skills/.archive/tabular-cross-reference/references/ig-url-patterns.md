# IG URL Patterns Found in Business Data

Session-specific reference for broken IG handle patterns encountered across datasets.

## Source Column Conventions

| File Type | Common Header Name | Typical Column Index |
|---|---|---|
| Exhibitor lists | Ig, Instagram, Social Media | Usually near end (29-31) |
| Host agency lists | Ig, IG, Social Media | Usually near end (28-30) |
| Contact databases | Instagram URL, IG Handle, Social Links | Varies widely |

**Always verify by scanning headers, never assume column position.**

## Broken Patterns Observed

### Pattern: Profile Card Redirect
```
https://www.instagram.com/deniseistraveling/profilecard/?igsh=MTA4bmQwajVpNGhpZA==
→ https://www.instagram.com/deniseistraveling
```
Source: Excel exports sometimes generate `/profilecard/` URLs instead of direct profile links.

### Pattern: Content/Post Links
```
https://www.instagram.com/reel/ABC123/
https://www.instagram.com/p/XYZ789/
https://www.instagram.com/tv/DEF456/
→ https://www.instagram.com/{username}
```
These are individual post URLs — extract the username from path segment 0.

### Pattern: Query Parameter Tracking
```
https://www.instagram.com/luxamatravel/?hl=en
https://www.instagram.com/travelatelierae?igsh=MWdlYzN5YjZvdnRydQ&utm_source=qr
→ https://www.instagram.com/{handle} (strip all query params)
```

### Pattern: Bare Domain as IG Handle (Data Entry Error)
```
https://dorislanghouseoftravel.net
https://Www.ourwholevillage.com
→ https://www.instagram.com/dorislanghouseoftravel
→ https://www.instagram.com/ourwholevillage
```
User typed their website URL into the IG field. Strip the TLD (.com/.net/.org) and use remainder as handle.

### Pattern: Non-Standard Capitalization
```
https://Www.ourwholevillage.com
→ lowercase everything after https://www.instagram.com/
```

## Matching Strategy Reference

When two files share contact data but have different column counts or structures:

1. **Scan for header row** — look for distinctive column name (e.g., "Contact Name") rather than assuming row 1
2. **Compare headers** — list divergences between files before matching
3. **Map by name, not position** — use `dict(zip(headers, row))` approach
4. **Normalize names** — strip common words (the, of, inc, llc), collapse whitespace, lowercase
5. **Multi-strategy match** — HIGH (name+company), MEDIUM (name only), LOW (substring)
6. **Report unmatched** — list them with company for manual review
