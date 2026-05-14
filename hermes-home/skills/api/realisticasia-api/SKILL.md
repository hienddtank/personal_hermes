---
name: RealisticAsia API
description: Access the RealisticAsia travel/tourism management platform API and admin UI. Covers tour CRUD, itineraries, accommodations, authentication, DOCX content import, browser harness fallback, and established workflows.
category: api
parameters:
  - name: token
    type: string
    description: Authentication bearer token (required for ALL operations)
---

**API Base URL:** `https://api.realisticasia.com/v1`
**Admin UI:** `https://admin.realisticasia.com`
**Public Site:** `https://realisticasia.com`
**Tour DOCX source:** `/host/d/mkt/python/hermes/workspace/tours/` (Windows D: drive)

## Platforms

Both RA and VTF share the same Laravel backend — identical endpoints, response format, and pitfalls. Only the base URL and credentials differ.

| Platform | API Base | Admin UI | Credentials |
|---|---|---|---|
| RA | `https://api.realisticasia.com/v1` | `admin.realisticasia.com/travel/tour/{id}` | `/tmp/cred.json` |
| VTF | *TBD — pending from user* | *TBD* | *TBD — pending from user* |

**Upload tracking:** `tour_upload_tracking.xlsx` in `/host/d/mkt/python/hermes/workspace/tours/` — tracks DOCX source, platform Tour ID, admin link, status (Pending/Done/Failed), upload date, notes per platform.

## Quick Reference

| Operation | Method | Endpoint | Auth? |
|-----------|--------|----------|-------|
| Login | POST | `/v1/auth/login` | No |
| List tours | GET | `/v1/travel/tour` | **Yes** |
| Get tour | GET | `/v1/travel/tour/{id}` | **Yes** |
| Create tour | POST | `/v1/travel/tour` | Yes |
| **Update tour** | **POST** | `/v1/travel/tour/{id}` | Yes |
| Delete tour | DELETE | `/v1/travel/tour/{id}` | Yes |
| List accommodations | GET | `/v1/travel/accommodation` | **Yes** |
| Get accommodation | GET | `/v1/travel/accommodation/{id}` | **Yes** |
| Create accommodation | POST | `/v1/travel/accommodation` | Yes |
| ~~Delete accommodation~~ | ❌ 405 | Use admin UI | — |
| Accommodation types | GET | `/v1/travel/accommodation-type` | **Yes** |
| Current user | GET | `/v1/auth/user` | Yes |

## Upload Rules (MANDATORY — user-corrected)

### Name & Slug
- Format: `hermes - {original_name}` (test tour prefix)
- Slug: `hermes-{slugified-name}`
- Example: `hermes - Gems of Myanmar Tour - 6 Days` → slug `hermes-gems-of-myanmar-tour-6-days`

### Itineraries
- **Each day must be a separate itinerary item** — NOT dumped into the `introduction` field
- Use the `itineraries` array on the tour object, one entry per day
- Required fields per itinerary item:
  - `day_from`, `day_to` (integers)
  - `title` (day header string, e.g. "DAY 01: ARRIVE YANGON (-)")
  - `description` (HTML content for that day)
  - `order` (integer, sequential starting at 1)
  - **MUST include these empty arrays or POST returns 500:**
    - `image: []`
    - `city_ids: []`
    - `accommodation_ids: []`
    - `meal_ids: []`
- The `introduction` field = brief tour overview/highlight text only (from first DOCX table)

### Accommodation Pivot Fields
- **Only populate accommodation IDs 1 and 2** in the tour's accommodations pivot
- If ID 2 does not exist on the platform for this tour, skip it — only fill ID 1
- Do NOT populate all service pivots (Guide, Meals, Transport, Insurance, etc.) unless explicitly asked
- `pivot.description` = HTML hotel list grouped by star tier (3*, 4*, 5*)
- `pivot.included` = 1

### Field mapping summary
| Tour field | Content |
|---|---|
| `name` | `hermes - {tour name}` |
| `slug` | `hermes-{tour-name-slugified}` |
| `introduction` | Brief tour overview (NOT full itinerary) |
| `itineraries` | One object per day with all required fields including empty arrays |
| `accommodations` | Only IDs 1 and 2 pivots, hotel list HTML in description |
| `duration` | Integer (days) |

## Authentication

```python
import urllib.request, json

creds = {"email": "<email>", "password": "<password>"}
req = urllib.request.Request(
    "https://api.realisticasia.com/v1/auth/login",
    data=json.dumps(creds).encode(),
    headers={"Content-Type": "application/json"},
    method="POST"
)
login_data = json.loads(urllib.request.urlopen(req).read())
token = login_data['access_token']  # {"access_token": "748|b94...", "token_type": "Bearer"}
headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
```

**Auth response:** `{"access_token": "<token>", "token_type": "Bearer"}` — NOT wrapped in `{"data": ...}`. Extract via `response['access_token']`.
**Token format:** `{number}|{hash}` (e.g., `748|b94PBbd...`)
**Stored credentials:** `/tmp/cred.json` (JSON with `email` and `password` keys)

## Response Format

All responses wrapped in `{"data": ...}` (except login which returns the token dict):
```json
{"data": {...}}      // single resource
{"data": [...]}      // list
{"error": "..."}     // error
```
Status codes: `200` (success), `401` (unauthorized), `404` (not found), `405` (method not allowed), `500` (server error)

## Tour Operations

### GET Tour (Full Object)
```python
req = urllib.request.Request(f"https://api.realisticasia.com/v1/travel/tour/{tour_id}")
resp = urllib.request.urlopen(req)
tour = json.loads(resp.read())['data']
```

### Update Tour — ⚠️ Use POST, NOT PUT/PATCH

**CRITICAL:** The Laravel API rejects PUT and PATCH with `405 Method Not Allowed`. Always use POST to update.

```python
# 1. GET the current tour first
req = urllib.request.Request(f"https://api.realisticasia.com/v1/travel/tour/{tour_id}")
resp = urllib.request.urlopen(req)
tour = json.loads(resp.read())['data']

# 2. Modify what you need — itineraries, accommodations, etc.
for it in tour['itineraries']:
    it['title'] = f'Updated day {it["day_from"]}'

# Update accommodation pivot descriptions (hotels, meals, etc.)
for acc in tour['accommodations']:
    if acc['id'] == 1:  # "Accommodation" category
        acc['pivot']['description'] = '<p><strong>HOTEL</strong><br>My Hotel</p>'
        acc['pivot']['included'] = 1

# 3. POST to update (send FULL tour object)
req = urllib.request.Request(
    f"https://api.realisticasia.com/v1/travel/tour/{tour_id}",
    data=json.dumps(tour).encode(),
    headers=headers,
    method="POST"
)
resp = urllib.request.urlopen(req)
result = json.loads(resp.read())['data']
```

### Required Fields on POST Update

When updating, include ALL fields (GET them first):
- `name`, `slug`, `duration`
- `introduction` (HTML)
- `start_city_id`, `end_city_id`
- `group_type_id`, `guide_type_id`
- `budget_class_id`, `travel_style_id`
- `status`, `is_ready_to_book`
- `traveller_type_ids`
- `itineraries` (array — updates inline)
- `min_group_size`, `max_group_size`

### Itinerary Fields

Each itinerary: `id`, `day_from`, `day_to`, `tour_id`, `title`, `description`, `order`, `image`, `city_ids`, `cities`, `accommodation_ids`, `accommodations`, `meal_ids`, `meals`

- `title`: plain text; `description`: HTML (`<p>...</p>`)
- **Adding new:** Omit `id` — server auto-assigns
- **Removing:** Filter from array before POSTing
- **Updating existing:** Preserve `id` to update in place

### Itinerary Title Meal Convention

Itinerary titles include meal tags `(B/L/D)` based on these rules:

1. **Breakfast (B):** If the previous night involved a hotel stay ("overnight", "staying hotel" in description), the next morning includes breakfast → append `(B)`
2. **Lunch (L) / Dinner (D):** Optional by default — only add if explicitly stated as included/provided in the description
3. **Format:** Append to title as `(B/L/D)` — e.g., `"YANGON SIGHTSEEING (B)"` or `"DAY 3 (B/L/D)"`

```python
# Two-pass approach:
# Pass 1: Determine which days have overnight stays
overnight = {}
for day in sorted(days):
    full = ' '.join(days[day]['content']).lower()
    overnight[day] = bool(re.search(r'(overnight|staying\s+hotel|hotel)', full))

# Pass 2: Apply meal rules
has_hotel = False
for it in tour['itineraries']:
    day = it['day_from']
    meals = []
    if has_hotel:
        meals.append('B')
    # L/D only if explicitly stated as included
    full = ' '.join(days[day]['content']).lower()
    if re.search(r'(lunch|l\s*=)\s*(included|provided)', full):
        meals.append('L')
    if re.search(r'(dinner|d\s*=)\s*(included|provided)', full):
        meals.append('D')
    has_hotel = overnight.get(day, False)
    
    # Clean old tags, apply new
    clean_title = re.sub(r'\s*\([BLD]+\)\s*$', '', it['title']).strip()
    it['title'] = f"{clean_title} ({'/'.join(meals)})" if meals else clean_title
```

### Status Codes

- `status`: `0` = Draft, `1` = Published
- `is_ready_to_book`: `1` = bookable, `0` = not ready

## Accommodation System

### Two Concepts

**1. Category Accommodations** (IDs 1-10): Generic "included/excluded" categories shown on the tour page:
| ID | Name | Purpose |
|----|------|---------|
| 1 | Accommodation | Hotels listed here in pivot.description |
| 2 | Flights | Flight info |
| 3 | Guide | Guide details |
| 4 | Meals | Meal plan details |
| 5 | Insurance | Insurance info |
| 6 | Transport | Transport details |
| 7 | Optional | Optional extras |
| 8 | Other included | Additional inclusions |
| 9 | Other not included | Exclusions |
| 10 | COVID-19 | Health measures |

**2. Hotel Records** (IDs 11+): Specific hotel names stored as accommodation records. Created via `POST /v1/travel/accommodation`. Not directly linked to itineraries — hotel info goes in the pivot.description of category ID 1.

### Pivot Structure

```json
{
  "id": 1,
  "name": "Accommodation",
  "pivot": {
    "description": "<p>Hotel Name ***</p>",   // name + star rating only — NO URLs, NO links
    "included": 1   // 0=not included, 1=included, 2=N/A (neutral)
  }
}
```

**Pivot descriptions CAN be updated** via tour POST — modify `accommodations[i].pivot.description` and `pivot.included` before POSTing. Verified on tour 561 (2026-05-14).

### Template Convention (Updated 2026-05-14)

Standard accommodation template stored at `/host/d/mkt/python/hermes/workspace/tours/tour_accommodation.json`. Contains all 10 category pivots (IDs 1–10). **When uploading hotels, you typically only need to update:**

- **ID 1 (Accommodation/Hotels):** Hotel name + star rating spelled out (e.g., "Grand United Ahlone Hotel - 3 Stars (Yangon)"). No URLs, no room types — grouped by star category.
- **ID 2 (Flights):** Flight details. No URLs, no links — just airline/route names.

IDs 3–10 are pre-configured in the template (Guide, Meals, Insurance, Transport, Optional, Other included, Other not included, COVID-19) and do not need to be re-uploaded unless explicitly changed.

### Workflow: Apply Accommodation Template
1. GET tour → extract `accommodations` array
2. Load `/host/d/mkt/python/hermes/workspace/tours/tour_accommodation.json`
3. Fill ID 1 pivot.description from DOCX hotel data (name + rating only)
4. Replace tour's `accommodations` with template (or merge IDs 1-2 into existing array)
5. POST full tour object
6. Verify pivots persisted

### Accommodation CRUD

```python
# Create
req = urllib.request.Request(
    "https://api.realisticasia.com/v1/travel/accommodation",
    data=json.dumps({"name": "Hotel Name", "type": "hotel"}).encode(),
    headers=headers, method="POST"
)

# ⚠️ DELETE returns 405 Method Not Allowed — use admin UI to remove hotels
# Types list: GET /v1/travel/accommodation-type
# Returns: Hotel(40), Lodge(44), Villa(53), Yurt(54), etc.
```

## Import Tour from DOCX

**Two DOCX formats observed:**

**Format A: Itinerary in paragraphs** (e.g. tour 562 - Gems of Myanmar)
Day headers as paragraphs (`DAY \d+:`), content in subsequent paragraphs. Stop parsing at non-itinerary keywords.

```python
current_day = None
day_sections = []
for p in doc.paragraphs:
    txt = p.text.strip()
    if not txt or len(txt) < 5:
        continue
    if any(skip in txt.upper() for skip in ['QUOTATION', 'ACCOMODATION', 'BOOKING POLICY', 'PASSPORT']):
        break
    day_match = re.match(r'(DAY\s+\d+:\s+.+)', txt.strip(), re.IGNORECASE)
    if day_match and len(txt.strip()) < 120:
        current_day = txt.strip()
        day_sections.append({'title': current_day, 'paras': []})
    elif current_day:
        day_sections[-1]['paras'].append(txt.replace('\n', '<br>'))

# Build itineraries array (ONE PER DAY — NOT introduction)
itineraries = []
for idx, section in enumerate(day_sections):
    desc_html = ''.join(f'<p>{para}</p>' for para in section['paras'])
    itineraries.append({
        'day_from': idx + 1,
        'day_to': idx + 1,
        'title': section['title'],
        'description': desc_html,
        'order': idx + 1,
        'image': [],       # REQUIRED empty arrays or POST returns 500
        'city_ids': [],
        'accommodation_ids': [],
        'meal_ids': [],
    })
# tour['itineraries'] = itineraries
# tour['introduction'] = brief_overview_html  # NOT the full itinerary
```

**Format B: Itinerary from first table row** (e.g. tour 561)

```python
import docx, re

doc = docx.Document("/host/d/mkt/python/hermes/workspace/tours/your_tour.docx")

# Introduction from first table row
intro = "".join(cell.text.strip() + " " for cell in doc.tables[0].rows[1].cells)

# Parse day headers: "DAY 01: TITLE (B)" or "DAY 5: TITLE"
days_data = {}
current_day = None
for p in doc.paragraphs:
    text = p.text.strip()
    if any(s in text for s in ["QUOTATION", "ACCOMODATION", "BOOKING"]):
        break  # Stop at pricing/hotel sections
    m = re.match(r'DAY\s*0*(\d+):\s*(.*)', text)
    if m:
        current_day = int(m.group(1))
        title = re.sub(r'\s*\(.*?\)\s*$', '', m.group(2)).strip()  # Remove (B), (-)
        days_data[current_day] = {'title': title, 'content': []}
    elif current_day and text:
        days_data[current_day]['content'].append(text)

# Build itineraries
itineraries = []
for d in sorted(days_data):
    dd = days_data[d]
    itineraries.append({
        "day_from": d, "day_to": d, "tour_id": tour['id'],
        "title": dd['title'],
        "description": ''.join(f"<p>{c}</p>" for c in dd['content']),
        "order": d,
        "image": [], "city_ids": [], "cities": [],
        "accommodation_ids": [], "accommodations": [],
        "meal_ids": [], "meals": []
    })
```

### DOCX Hotel Table Extraction

**Pricing tables** (4 tables: 2 seasons × supplier/retail, each 6×9):
```python
# Tables 1-4 are pricing: Low Supplier, Low Retail, High Supplier, High Retail
def parse_price_table(table):
    rows = []
    for row in table.rows[1:]:
        cells = [c.text.strip().replace(',', '').replace('\n', '') for c in row.cells]
        label, prices = cells[0], cells[1:]
        if prices and prices[0].isdigit():
            rows.append((label, [int(p) if p.isdigit() else 0 for p in prices]))
    return rows
# Columns: 01 Pax, 02 Pax, 03-05 Pax, 06-09 Pax, 10-14 Pax, 15-19 Pax, 20+ Pax, Single Supplement
# Rows: 03*/04*/05* Star Hotel + Surcharge for Language Speaking Guide
```

**Hotel tables** (after pricing, before policy sections):

Hotels are typically in tables after the itinerary section. Pattern:
- `table.rows[0]`: Header row with star rating (e.g., "03* Star Hotel")
- `table.rows[1:]`: City | Hotel details

**CRITICAL CLEANUP — DOCX hotel cells contain embedded URLs and trailing notes:**
```python
import re
for table in doc.tables:
    if len(table.rows) >= 2 and 'Star Hotel' in table.rows[0].cells[-1].text:
        for row in table.rows[1:]:
            city = row.cells[0].text.strip()
            raw = row.cells[1].text.strip().replace('\n', ' ')
            # 1. Remove URLs
            clean = re.sub(r'\s*https?://\S+', '', raw).strip()
            # 2. Split by comma, keep first part (name + rating)
            clean = clean.split(',')[0].strip()
            # 3. Stop at trailing notes ("only ...", "available ...")
            words = clean.split()
            result = []
            for w in words:
                if w == 'only': break
                result.append(w)
            clean = ' '.join(result).strip()
            hotels.append(f"{clean} ({city})")
# Deduplicate: hotels = list(dict.fromkeys(hotels))
```

**Pitfalls discovered (2026-05-14):**
- Raw DOCX hotel text: `"KyaikHto Hotel *** Deluxe Room  http://www.hotelkyaikhto.com/ only 3-star hotel available on the mountain top."`
- After cleaning: `"KyaikHto Hotel *** Deluxe Room (Kyaikhto)"` — name + rating only, no URLs
- Over-aggressive regex (e.g., matching on word boundaries) strips star ratings. Use targeted URL removal + comma split instead.

## Known Pitfalls

1. **PUT/PATCH blocked** — Always use POST for updates
2. **Auth required for ALL endpoints** — Even "public" GETs need `Authorization: Bearer <token>`. Without auth you get `{"Hello": "World"}`.
3. **Itineraries require empty array fields** — `image`, `city_ids`, `accommodation_ids`, `meal_ids` must all be present as empty arrays or POST returns 500. This is the #1 cause of upload failures.
4. **500 errors may partially commit** — A POST that returns 500 can still persist some changes. Always GET after a failed POST to check actual state.
5. **Full object required** — You must GET then POST the entire tour object, not partial updates
6. **No batch operations** — Each resource update is individual
7. **No city lookup endpoint** — `GET /v1/travel/city` returns 404. Collect city IDs from tours.
8. **No itinerary delete endpoint** — Remove by filtering from array before POST
9. **`&` in Python heredocs** — When running multi-line Python via `python3 << 'EOF'`, `&` is interpreted as shell backgrounding. **Always write to `/tmp/file.py` then run `python3 /tmp/file.py`**
10. **Title convention:** prefix with "hermes - " for test tours
11. **Accommodation pivots: only IDs 1 and 2** — Do not populate all service pivots unless explicitly asked
10. **Itineraries require ALL fields** — If you omit `image`, `city_ids`, `accommodation_ids`, or `meal_ids`, the POST returns **500 (Server Error)**. Even if they're empty arrays, every field must be present. Discovered 2026-05-14 on tour 562.
    ```python
    # REQUIRED format for itinerary items:
    {
        'day_from': 1, 'day_to': 1,
        'title': 'Day 1: ...',
        'description': '<p>...</p>',
        'order': 1,
        'image': [],          # MUST be present (even if empty)
        'city_ids': [],       # MUST be present
        'accommodation_ids': [],  # MUST be present
        'meal_ids': [],       # MUST be present
    }
    ```
11. **Accommodation pivots stripped if empty** — When POSTing the tour, accommodation pivots with empty descriptions get dropped from the response. Only IDs with non-empty `pivot.description` persist visibly. IDs 3-10 may exist in the DB but won't appear in GET responses unless they have content.
12. **Only fill IDs 1 and 2** — Per user requirement, only accommodation pivot IDs 1 (Accommodation/Hotels) and 2 (Flights) should be populated with content. Do NOT populate Guide, Meals, Insurance, etc. unless explicitly asked.

## Workflows

### Edit Tour Itineraries
1. `POST /v1/auth/login` → extract `access_token`
2. `GET /v1/travel/tour/{id}` → fetch full tour object
3. Modify `itineraries` array (title, description)
4. For new days: append items without `id` field
5. `POST /v1/travel/tour/{id}` → send full modified object
6. Verify: GET again or check admin UI

### Upload Hotels from DOCX
1. Parse hotel tables from DOCX (see above)
2. Update accommodation pivot ID 1 — hotel name + star rating only, no URLs
3. POST full tour object
4. Verify pivots persisted
5. Flights (ID 2) uploaded separately when available

### Create New Tour
1. Login to get token
2. Construct tour object with all required fields
3. `POST /v1/travel/tour` → returns new tour with ID
4. Optional: Update itineraries via POST to `/v1/travel/tour/{new_id}`

## Admin UI

- URL: `https://admin.realisticasia.com`
- Credentials: same as API (`/tmp/cred.json`)
- Login at `/auth/login`
- Tour detail: `/travel/tour/{id}`

| Task | Preferred Method | Reason |
|------|-----------------|--------|
| Read tour data | **API** | Structured, fast |
| Update itineraries | **API** | Direct field control |
| Create/delete accommodations | **API** | Programmatic |
| Visual verification | **UI** | See rendered output |
| Complex form edits | **UI** | Multi-step workflows |

## Notes

- All timestamps: ISO 8601 (UTC)
- IDs: auto-incrementing integers
- Descriptions: HTML format
- API docs: `https://api.realisticasia.com/docs/api`
- Test tours: prefix with "hermes - ", keep `status=0` (draft)

## Reference Files

- `references/auth-and-quirks.md` — Auth response format, endpoint quirks
- `references/accommodation-template.md` — Template JSON structure, pivot IDs, session history
- `references/multi-platform-upload-tracking.md` — RA + VTF tracking sheet workflow, onboarding checklist
