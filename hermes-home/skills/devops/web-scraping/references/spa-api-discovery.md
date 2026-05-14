# SPA API Discovery — TravelLeaders.com Case Study (Updated)

**Problem**: Scrape all 23,582 travel agents from `https://www.travelleaders.com/agents`

**Site Type**: React SPA (`<div id="root">` + `<noscript>You need to enable JavaScript</noscript>`)

## Discovery Process

### 1. Initial Probing
- `requests.get()` with browser User-Agent → 28KB HTML shell, zero agent data
- Confirmed: pure client-side rendering, no server-side content

### 2. JS Bundle Extraction
- Found bundle: `https://www.travelleaders.com/assets/index-B1XJ_KDs.js` (2.6MB)
- Downloaded via `http_get()` (browser harness helper) or `requests.get()` with browser UA
- Also check for smaller bundles like `/traveller.xxx.js` (27KB, fewer endpoints)

### 3. Pattern Search (search the bundle text)
```python
import re
# Find fetch/axios calls with URL strings
fetch_calls = re.findall(r'fetch\(["\']([^"\'`]+)["\'\)]', bundle)
# Find function names
functions = re.findall(r'(getAgents|getAdvisors|searchAdvisors|findAgents)', bundle)
# Find URL paths
paths = re.findall(r'["\'](/[a-z_]+(?:/[a-z_]*)?)[\'"]', bundle)
# Find template literal patterns (common in React SPAs)
template_paths = re.findall(r'\$\{[^}]+\}/([a-zA-Z_]+)', bundle)
```

**Key patterns found**:
- Function: `getAgents`
- Paths: `/agent/getAgents`, `/agent/getAgentFullBio`, `/lookup/getInterests`, `/customer/SendEmail`
- Route patterns: `/agent/:id/bio/:bioId`, `/agent/:id/bio/:bioId/itinerary/:itineraryId`

### 4. API Base URL Discovery
Searched for the template literal prefix (`po` in the minified bundle):
```javascript
const po=""  // Empty = same-origin root
```
This means the API lives at the domain root, not a subdomain or `/api/` prefix.

### 5. API Endpoint (List)
```
GET https://www.travelleaders.com/agent/getAgents?
  AgentSort=&
  AgentDestination=&
  AgentState=&
  AgentMetroRegion=&
  AgentLanguage=&
  AgentCity=&
  AgentSupplier=&
  AgentId=&
  AgencyId=&
  Locality=&
  CurrentPage=0&
  PageSize=10000
```

### 6. Required Headers
```python
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json",
    "Referer": "https://www.travelleaders.com/agents",  # Often required
}
```

### 7. Response Structure (List)
```json
{
  "responseStatus": 1,
  "error": {"message": null},
  "data": {
    "agent": [...],
    "totalAgents": 23582,
    "currentAgentCount": "1-10000"
  }
}
```

**⚠️ Each agent in the list includes `connect[]`** with social links:
```json
"connect": [
  {"contactMethod": "by Phone", "contactValue": "1-715-629-1868"},
  {"contactMethod": "by Email", "contactValue": "Melissa@tvlleaders.com"},
  {"contactMethod": "Facebook", "contactValue": "https://www.facebook.com/melissa.guttingtvl"}
]
```
This means **LinkedIn, Instagram, Blog, YouTube are FREE** from the list API. No detail calls needed for social data.

### 8. Response Structure (Detail — only if needed)
`/agent/getAgentFullBio?agentId=X` returns:
- `bioText` (full bio HTML, ~100% coverage)
- `expertiseOverview` (short summary, ~100%)
- `agentConnections[]` (same social data as list's `connect[]`)
- `cert1`–`cert5`, image URLs

## Execution Results
| Phase | Calls | Time | Data |
|---|---|---|---|
| List API (3 pages) | 3 | ~45s | All agents + social links + interests |
| Detail endpoint (optional) | ~23K | ~1-2 hrs | bioText only |

## Key Lessons
1. **Always check for hidden APIs before full browser crawling** — 3 HTTP calls vs. 23,582 page loads
2. **Empty API base URL** (`const po=""`) is common in SPAs — means same-origin
3. **Minified variable names** like `po` are just the API base — search near fetch calls
4. **Referer/Origin headers** may be required for API requests
5. **Large page sizes may be capped at 10,000** — test incrementally
6. **⚠️ Always check `connect[]` or similar in list response before writing detail calls** — social URLs are often included free
7. **No batch bio endpoint exists** — even if the SPA has route patterns like `/agent/:id/bio/:bioId`, the backend only supports per-agent calls

## Performance Comparison (TravelLeaders)
| Approach | Calls | Time | Social URLs? | BioText? |
|---|---|---|---|---|
| List API only | 3 | ~45s | ✅ Yes | ❌ No |
| Full detail calls | 23K+ | ~1-2 hrs | ✅ Yes (redundant) | ✅ Yes |
| **Recommended: list + optional detail** | 3+N | ~50s to ~1hr | ✅ Yes (free) | ✅ If needed |

## See Also
- `spa-api-enrichment.md` — When to use the detail endpoint vs. just list API data
- `templates/spa-bulk-crawler.py` — Reusable crawler implementing this pattern
