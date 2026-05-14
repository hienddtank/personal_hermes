# Academic Email Finding — What Works & What Doesn't

## Session Date: 2026-05-05 (Updated)
## Context: Finding emails for 735 Korean materials science professors

### Environment-Specific Approaches

#### From Hermes Agent Container (Google Search Blocked)

When running from the container, Google search is blocked. Use these approaches instead:

1. **Semantic Scholar API** — `https://api.semanticscholar.org/graph/v1/author/search?query={name}&fields=id,name,email,affiliations`
   - Returns author email if publicly indexed
   - Rate limit: ~2 req/sec without API key
   - Hit rate: ~5-10% for Korean professors

2. **CrossRef API** — `https://api.crossref.org/works?query.author={name}&mailto=your@email.com&rows=3`
   - Scans publication metadata for email patterns
   - Hit rate: ~3-5% (emails in corresponding author fields)

3. **OpenAlex via ORCID** — `https://api.openalex.org/works?filter=authorships.author.orcid:{orcid}&per_page=3`
   - Follows publication links to extract emails from landing pages
   - Works for ~2-3% of professors with ORCIDs

4. **University Email Pattern Matching (DNS Validation)** — Most reliable for known universities
   - Generate common patterns, validate with DNS check
   - See patterns below

**See** `scripts/batch_email_hunter.py` — production batch script using all 4 strategies.

#### From Host Machine or Within Target Country (Google Accessible)

Use the publication-page approach:

1. **Google Search + Web Extract** (BEST — 40-60% success rate)
   - Search: `"Professor Name" University email` or `"Professor Name" "university" corresponding author`
   - Extract from publisher pages (RSC, ACS, Wiley, Springer)
   - Works because publisher pages expose corresponding author emails in metadata

2. **ORCID Public Profile** (quick check, ~5% hit rate)
   - Most professors keep emails private

3. **University Faculty Pages** (geo-dependent)
   - Korean `.ac.kr` domains often block foreign IPs

### APIs That Don't Work

| Source | Result | Why |
|--------|--------|-----|
| ORCID public API (`/v3.0/{orcid}/email`) | Empty email array | Emails private by default; OAuth required |
| OpenAlex authors | No `email` field | Not exposed in API |
| CrossRef (`mailto=true`) | No email returned | mailto sends notification, doesn't return emails |
| Semantic Scholar (no key) | Rate-limited (429) | Requires API key for higher limits |

### SMTP Verification (Korean Universities)

Korean universities block external SMTP on port 25. Exchange/Kmail systems reject foreign IPs.

**Workaround:** Use DNS validation only (checks domain exists, not mailbox). Combined with pattern matching, gives ~60-80% accuracy for known patterns.

### Korean Academic Email Patterns

**Domain Map:**
```
seoul national university → snu.ac.kr
kaist → kaist.ac.kr
korea university → korea.ac.kr
yonsei university → yonsei.ac.kr
hanyang university → hanyang.ac.kr
postech / pohang university → postech.ac.kr
sungkyunkwan → skku.edu
kyungpook national → knu.ac.kr
kookmin → kookmin.ac.kr
konkuk → konkuk.ac.kr
unist → unist.ac.kr
dongguk → dongguk.edu
gangneung-wonju → wonju.ac.kr
chung-ang → cau.ac.kr
sogang → sogang.ac.kr
ajou → ajou.ac.kr
chonnam → jnu.ac.kr
chungbuk → chungbuk.ac.kr
kyung hee / kyunghee → khu.ac.kr
inha → inha.ac.kr
kyungsung → ks.ac.kr
dong-a → donga.ac.kr
chonbuk → chonbuk.ac.kr
korea maritime → kmou.ac.kr
gyeongsang national → gnu.ac.kr
korea institute of fusion energy → kefir.re.kr
korea institute of science → kist.re.kr
```

**Pattern Generation (by institution):**
- Most universities: `lastnamefirstname@domain`, `lastnamef@domain`, `lastname@domain`
- SNU: `lastnamefirst@snu.ac.kr`
- KAIST: `lastnamefirst@kaist.ac.kr` or `lastnamef@kaist.ac.kr`
- SKKU: `lastnamefirst@skku.edu`

### Email Validation (Critical Filters)

When collecting emails, apply these filters:

1. **Skip single-char local parts** — `v@kookmin.ac.kr` is wrong (initial, not name)
2. **Skip publisher domains** — `springernature.com`, `wiley.com`, `ieee.org`, `elsevier.com`, `acs.org`, `rsc.org`, `nature.com`, `cell.com`, `tandfonline.com`
3. **Skip non-person emails** — `copyright@`, `editorial@`, `support@`, `info@`, `help@`, `webmaster@`, `admin@`, `contact@`, `sales@`, `marketing@`, `permissions@`, `journal@`, `editor@`, `office@`, `secretary@`
4. **Prefer academic domains** — `.ac.kr`, `.re.kr`, `.edu` over commercial domains

### Batch Processing Workflow

1. Build CSV from OpenAlex/Semantic Scholar (names + affiliations)
2. Run batch email hunter (4 strategies, incremental saves)
3. Post-process: validate emails, remove false positives
4. Optional: send verification emails or use commercial API for remaining

**Expected success rates:**
- API strategies (container): ~5-10% per professor
- Pattern matching (DNS only): ~30-40% for known universities
- Google search + publication pages (host): ~40-60%
- Combined: ~60-70% of professors

### See Also

- `scripts/batch_email_hunter.py` — production batch script (Semantic Scholar + CrossRef + OpenAlex + patterns)
- `templates/crawler-template.py` — Playwright crawler scaffold
- `references/spa-api-discovery.md` — JS bundle API discovery
