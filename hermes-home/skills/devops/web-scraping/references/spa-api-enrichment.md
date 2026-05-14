# SPA API Enrichment — Post-Crawl Field Completion

**Pattern**: An SPA's list endpoint returns bulk data quickly but omits verbose fields (bios, social URLs, images). A separate detail endpoint exists per-record for enrichment.

## When to Use
- You already scraped a large batch via the list API (`/getAgents`-style)
- The list response is missing specific fields: `bioText`, LinkedIn/Instagram URLs, certifications, image URLs
- Each record has a stable `agentId` (or equivalent ID) that works as a lookup key for the detail endpoint
- You need to add columns to an existing CSV without re-crawling everything

## Technique: List + Detail Endpoint

Many SPAs separate concerns — fast list queries vs. per-record detail lookups.

### Example: TravelLeaders.com

**List endpoint** (`/agent/getAgents?PageSize=10000`):
- Returns 23,582 agents in ~35 seconds (3 page calls)
- Fields: name, city, state, agency, email, phone, interests, destinations, rating, etc.
- **Already included**: `connect[]` array with social links — see below for extraction

⚠️ **Critical Discovery (2024)**: The list API's `connect[]` field already contains ALL social links:
  - `{contactMethod: "LinkedIn", contactValue: "https://..."}` 
  - `{contactMethod: "Instagram", contactValue: "http://instagram.com/..."}`
  - `{contactMethod: "Facebook", contactValue: "https://www.facebook.com/..."}`
  - `{contactMethod: "My Blog", contactValue: "https://blog.example.com/..."}`
  - Methods seen: `LinkedIn`, `Instagram`, `Facebook`, `My Blog`, `Pinterest`, `YouTube`

- **Still missing from list**: bioText, expertiseOverview (require per-agent detail call)

**Detail endpoint** (`/agent/getAgentFullBio?agentId=X`):
- Returns per-agent object with `responseStatus: 1` on success
- New fields available (only these require individual calls):
  - `bioText` — full biography HTML (500–2800+ chars). **Coverage: ~100%**
  - `expertiseOverview` — short expert summary text (300–900 chars). **Coverage: ~100%**
  - `cert1`–`cert5` — certification/award strings
  - Image URLs: `agentPhotoFileName`, `travelPhotoFileName`
- Note: `agentConnections[]` here has the same social data as list endpoint's `connect[]` (no new info)

**Performance shortcut**: Extract all social URLs from the list API's `connect[]` — no detail calls needed for LinkedIn/Instagram/Facebook/Blog. Only call `/agent/getAgentFullBio?agentId=X` when you actually need `bioText` or `expertiseOverview`.

### Enrichment Script Pattern

```python
import requests, json, random

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json",
    "Referer": "https://www.travelleaders.com/agents",
}

def fetch_full_bio(agent_id):
    """Return enriched fields for a single agent, or None on failure."""
    resp = requests.get(
        f"https://www.travelleaders.com/agent/getAgentFullBio?agentId={agent_id}",
        headers=headers, timeout=10
    )
    data = resp.json()
    if data['responseStatus'] != 1:
        return None
    
    bio_text = data['data'].get('bioText', '')
    expertise = data['data'].get('expertiseOverview', '')
    
    # Extract social URLs from connections array
    linkedin = instagram = facebook = ''
    for conn in data['data'].get('agentConnections', []):
        method = conn.get('contactMethod', '').lower()
        if 'linkedin' in method:
            linkedin = conn['contactValue']
        elif 'instagram' in method:
            instagram = conn['contactValue']
        elif 'facebook' in method:
            facebook = conn['contactValue']
    
    return {
        'bioText': bio_text,
        'expertiseOverview': expertise,
        'linkedinUrl': linkedin,
        'instagramUrl': instagram,
        'facebookUrl': facebook,
    }

# Usage: call per agent ID from existing CSV
```

### Performance Considerations
- **No browser needed** — both endpoints are plain HTTP JSON
- **Rate limit**: 10–30 seconds between requests to be safe (23K agents = 6–19 hours)
- **Error handling**: `responseStatus != 1` means invalid/expired ID — skip gracefully
- **Timeouts**: set `timeout=10` to avoid hanging on slow responses

## Generalization

This pattern appears in many SPAs. Look for:
- Endpoints with singular names: `/getAgentFullBio`, `/getUserProfile`, `/getItemDetail`
- Endpoints requiring a single ID parameter vs. list endpoints accepting filters/pagination
- Response structures that wrap the detail in `data: {...}` (single object) vs. `data: {items: [...]}` (list)

**Lesson**: Always check the full JS bundle for ALL endpoint patterns — not just the one used by the list view. The detail endpoint often contains richer data you'll need later.
