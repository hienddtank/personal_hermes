---
name: travelleaders-crawler
description: Crawl all travel agents from TravelLeaders.com (Internova Travel Group). Extracts 23,500+ agents with contacts, agencies, specializations, ratings, destinations via the hidden internal API.
---

# TravelLeaders.com Agent Crawler

TravelLeaders.com is a React SPA. The server returns only a 28KB HTML shell — all agent data is fetched client-side via an internal API. Direct HTTP without browser headers returns 403.

## API Endpoint

```
GET /agent/getAgents?AgentSort=&CurrentPage={page}&PageSize={size}
```

Full URL: `https://www.travelleaders.com/agent/getAgents?AgentSort=&CurrentPage=0&PageSize=10000`

## Required Headers

```python
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json",
    "Referer": "https://www.travelleaders.com/agents",
}
```

## Parameters

| Param | Description |
|---|---|
| CurrentPage | 0-indexed page |
| PageSize | Max 10,000 per page |
| AgentSort | Sort field (empty = default) |
| Name | Agent name filter |
| ZIP, AgentState, AgentCity | Location filters |
| AgentDestination, AgentInterest | Specialization filters |
| AgentId, AgencyId | Specific ID filters |

## Response Structure

```json
{
  "responseStatus": 1,
  "data": {
    "agent": [/* array of agent objects */],
    "totalAgents": 23582,
    "currentAgentCount": "1-10000"
  }
}
```

Each agent object contains: `agentId`, `firstName`, `lastName`, `city`, `state`, `hostAgency`, `agencyName`, `agencyLevel`, `yearsActive`, `agentType`, `externalWebsite`, `connect[]` (phone/email/Facebook), `interest[]` (interestName), `destination[]` (regionName, areaName, localeName), `agentRating` (rating, totalReviews), `bioId`, `agentHash`.

## Crawling All Agents

```python
import requests
import csv
import time

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json",
    "Referer": "https://www.travelleaders.com/agents",
}

all_agents = []
for page in range(3):  # ceil(23582/10000)
    url = f"https://www.travelleaders.com/agent/getAgents?AgentSort=&CurrentPage={page}&PageSize=10000"
    r = requests.get(url, headers=headers, timeout=120)
    data = r.json()
    if "data" in data:
        all_agents.extend(data["data"]["agent"])
    time.sleep(1)

# totalAgents = data["data"]["totalAgents"]  # check for current total
```

## CSV Export

```python
def safe_list(agent, key):
    val = agent.get(key, [])
    return [x for x in val if x is not None] if val else []

def get_rating(agent):
    ar = agent.get("agentRating")
    if isinstance(ar, dict):
        return ar.get("rating", ""), ar.get("totalReviews", "")
    if isinstance(ar, list) and ar:
        item = ar[0] if isinstance(ar[0], dict) else {}
        return item.get("rating", ""), item.get("totalReviews", "")
    return "", ""

with open("travelleaders_agents.csv", "w", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(["agentId", "fullName", "city", "state", "agencyName",
                     "agencyLevel", "phone", "email", "facebook",
                     "interests", "destinations", "rating", "totalReviews",
                     "yearsActive", "externalWebsite", "agentType", "bioUrl"])
    for a in all_agents:
        phone = email = facebook = ""
        for c in safe_list(a, "connect"):
            m, v = c.get("contactMethod", ""), c.get("contactValue", "")
            if "Phone" in m: phone = v
            elif "Email" in m: email = v
            elif "Facebook" in m: facebook = v
        interests = "; ".join(i.get("interestName", "") for i in safe_list(a, "interest"))
        dests = "; ".join(sorted(set(
            d.get("regionName", "") or d.get("areaName", "")
            for d in safe_list(a, "destination")
        )))
        rating, reviews = get_rating(a)
        fn = (a.get("firstName") or "") + " " + (a.get("lastName") or "")
        writer.writerow([
            a.get("agentId", ""), fn, a.get("city", "") or "", a.get("state", "") or "",
            a.get("agencyName", "") or "", a.get("agencyLevel", "") or "",
            phone, email, facebook, interests, dests, rating, reviews,
            a.get("yearsActive", "") or "", a.get("externalWebsite", "") or "",
            a.get("agentType", "") or "",
            f"https://www.travelleaders.com/agent/{a.get('agentId', '')}"
        ])
```

## Other API Endpoints

| Endpoint | Method | Purpose |
|---|---|---|
| `/agent/getAgentFullBio?agentId={id}` | GET | Full biography |
| `/lookup/getInterests` | GET | Available interests list |
| `/lookup/getStates` | GET | Available states list |
| `/lookup/{name}` | POST | Generic lookup (destinations, cities, etc.) |
| `/customer/SendEmail` | POST | Contact agent via email |

## Pitfalls

1. **agentRating can be a dict OR a list** — always check `isinstance(ar, dict)` first, then handle list case.
2. **interest/destination/connect arrays can contain None elements** — always filter: `[x for x in val if x is not None]`.
3. **Individual fields can be None** — use `or ''` when writing to CSV/JSON.
4. **PageSize > 10,000 returns empty response** — cap at 10,000 and paginate.
5. **JS bundle filename rotates** — the hash in `/assets/index-*.js` changes per deploy. To discover: load the page, find the `src` of the largest JS script from `travelleaders.com`.
6. **No User-Agent = 403** — always send browser headers.
7. **Raw HTML has zero agent data** — the `/agents` page returns only a React app shell. You must use the `/agent/getAgents` API.
8. **The site is owned by Internova Travel Group** (formerly Travel Leaders Group).

## How the API Was Discovered

1. Navigate to the site in a headless browser
2. Find the main JS bundle: `/assets/index-*.js`
3. Search the bundle for `getAgents` — the fetch URL is embedded as a template literal
4. The base URL variable `po` is `""` (same domain root)
5. The API uses the same domain, not a separate backend
