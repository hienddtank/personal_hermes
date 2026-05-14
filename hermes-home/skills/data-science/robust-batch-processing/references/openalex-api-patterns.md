# OpenAlex API — Crawling Patterns & Pitfalls

## Authentication (as of Feb 2025)

OpenAlex now requires a `mailto` parameter for all requests. No API key needed for free tier (100 credits/day).

```python
mailto = "your.email@example.com"
url = f"https://api.openalex.org/works?filter=...&mailto={mailto}"
```

Without `mailto`, you get HTTP 400 "Invalid query parameters error."

## Pagination

**Use `page` parameter, NOT `offset`:**
```python
# ✅ Works
f"https://api.openalex.org/works?search=...&per_page=10&page={page+1}&mailto={email}"

# ❌ Fails with 400 "offset is not a valid parameter"
f"https://api.openalex.org/works?search=...&per_page=10&offset={offset}"
```

## Rate Limiting

- Free tier: ~100 credits/day
- Aggressive rate limiting — parallel requests trigger 400 errors
- **Solution**: Sequential requests with 2-3 second delays between them
- `per_page` max is 100, but 10-20 is safer for staying under rate limits

## Getting Korean Materials Science Professors

**Works endpoint (not authors) is the way to go:**
```python
url = f"https://api.openalex.org/works?filter=authorships.countries:KR&search=materials+science+Korea&per_page=10&page={page}&mailto={email}"
```

Then extract **corresponding authors** (more likely to be professors):
```python
for work in results:
    for authorship in work.get('authorships', []):
        if not authorship.get('is_corresponding'):
            continue
        # Extract name, ORCID, institutions, affiliations
```

## Key Filter Fields

- `authorships.countries:KR` — filter by country
- `search:materials+science+Korea` — full-text search
- `institutions.country_code:KR` — alternative (works endpoint)

## Extracting Institution Names

```python
institutions = authorship.get('institutions', [])
inst_names = [i.get('display_name', '') for i in institutions if i.get('country_code') == 'KR']
raw_aff = authorship.get('raw_affiliation_strings', [])  # Has department-level detail
```

## Email Enrichment

OpenAlex does NOT include author emails. To get emails:
1. Crawl university department pages (but each site structure is different)
2. Many Korean university pages require JS rendering or are in Korean
3. Main department pages rarely have emails — need sub-pages with faculty listings
4. Use browser harness for JS-rendered pages if needed

## Session-Specific Data

- Query: Korean materials science professors
- Terms: materials science, materials engineering, nanomaterials, polymer science, battery materials, catalysis, ceramic materials, semiconductor, metallurgy, thin film, composite materials, photovoltaic, solar cell
- Results: 735 unique corresponding authors from top Korean universities
- Top universities: SNU (72), KAIST (55), POSTECH (47), Korea Univ (29), Yonsei (28)
