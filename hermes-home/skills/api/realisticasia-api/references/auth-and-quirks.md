# RealisticAsia API — Auth Details and Quirks

Discovered: 2026-05-13

## Auth Response Format

The login endpoint returns a dict, NOT a raw string:
```json
{"access_token": "748|b94PBbdhD9007TY2CmXuA4Xefk...", "token_type": "Bearer"}
```

Extract via: `response['access_token']`

Previous documentation incorrectly stated it returns a raw token string.

## All Endpoints Require Auth

Even endpoints documented as "public" (like `GET /v1/travel/tour?per_page=5`) return `{"Hello": "World"}` without a valid Bearer token. **Always include auth headers for all requests.**

```python
headers = {
    "Authorization": f"Bearer {token}",
    "Accept": "application/json",
    "Content-Type": "application/json"
}
```

## POST Update — Itinerary Auto-Creation

When POSTing a tour update with new itinerary items that have no `id` field, the server auto-assigns IDs. Verified working:

```python
# Existing itineraries (keep their ids)
tour['itineraries'][0] = {"id": 6235, "day_from": 1, ...}

# New itinerary (no id — server assigns one)
tour['itineraries'].append({"day_from": 4, "title": "...", ...})
```

Server returns the updated tour with new IDs assigned to previously-idless items.

## 500 Error on Partial Commits

A POST update that returns HTTP 500 can still partially commit — some fields may be saved while the response fails. Always GET the tour again after a failed POST to check actual state before retrying.

## City Lookup

No dedicated `GET /v1/travel/city` endpoint exists (returns 404). To find city IDs:
1. GET multiple tours individually
2. Collect cities from `tour['cities']` array
3. Myanmar cities are NOT in the database — system currently covers Vietnam, Cambodia, Laos, Thailand, China, Japan, South Korea, India, Sri Lanka, Nepal, Taiwan, Bali

## Pagination

Tours list supports `?per_page=N&page=M`. Default per_page may be 5. Use `per_page=100` for bulk operations.
