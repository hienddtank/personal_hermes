# DOCX → Platform Upload Workflow

Step-by-step procedure for uploading a tour from DOCX source to RealisticAsia (or VTF).

## Step 1: Auth
```python
import requests, json
cred = json.load(open('/tmp/cred.json'))
r = requests.post('https://api.realisticasia.com/v1/auth/login', json=cred)
token = r.json()['access_token']
headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}
```

## Step 2: Fetch Existing Tour
```python
BASE = 'https://api.realisticasia.com/v1/travel'
tour = requests.get(f'{BASE}/tour/{id}', headers=headers).json()
if 'data' in tour:
    tour = tour['data']
# Verify: print(tour['name'], tour['slug'])
```

## Step 3: Parse DOCX — Extract Day Sections
```python
from docx import Document
doc = Document('path/to/tour.docx')

current_day = None
day_sections = []
for p in doc.paragraphs:
    txt = p.text.strip()
    if not txt or len(txt) < 5:
        continue
    # Stop at non-itinerary sections
    if any(skip in txt.upper() for skip in ['QUOTATION', 'ACCOMODATION', 'BOOKING POLICY', 'PASSPORT']):
        break
    # Match day headers like "DAY 01: ARRIVE YANGON (-)"
    day_match = re.match(r'DAY\s+\d+:\s+.+', txt.strip(), re.IGNORECASE)
    if day_match and len(txt.strip()) < 120:
        current_day = txt.strip()
        day_sections.append({'title': current_day, 'paras': []})
    elif current_day:
        day_sections[-1]['paras'].append(txt.replace('\n', '<br>'))
```

## Step 4: Parse DOCX — Extract Hotels (Accommodation Tables)
```python
hotels_3 = hotels_4 = hotels_5 = []
for table in doc.tables:
    if len(table.rows) < 2:
        continue
    header = table.rows[0].cells[-1].text.strip()
    if '03* Star' in header:
        for row in table.rows[1:]:
            raw = row.cells[1].text.strip().replace('\n', ' ')
            # Remove URLs, split by comma, keep first part
            clean = re.sub(r'\s*https?://\S+', '', raw).split(',')[0].strip()
            hotels_3.append(f"{clean} (***)")
    elif '04* Star' in header:
        for row in table.rows[1:]:
            raw = row.cells[1].text.strip().replace('\n', ' ')
            clean = re.sub(r'\s*https?://\S+', '', raw).split(',')[0].strip()
            hotels_4.append(f"{clean} (****)")
    elif '05* Star' in header:
        for row in table.rows[1:]:
            raw = row.cells[1].text.strip().replace('\n', ' ')
            clean = re.sub(r'\s*https?://\S+', '', raw).split(',')[0].strip()
            hotels_5.append(f"{clean} (*****)")
```

## Step 5: Create New Hotels (if not existing)
```python
existing = requests.get(f'{BASE}/accommodation', headers=headers).json().get('data', [])
existing_names = {h['name'].lower() for h in existing}
id_map = {}

def ensure_hotel(name):
    if name.lower() in existing_names:
        for h in existing:
            if h['name'].lower() == name.lower():
                return h['id']
    r = requests.post(f'{BASE}/accommodation', headers=headers, json={'name': name})
    new = r.json().get('data', {})
    existing_names.add(name.lower())
    return new.get('id')

new_ids = []
for hotel_name in hotels_3 + hotels_4 + hotels_5:
    hid = ensure_hotel(re.sub(r'\s*\(\*+\)', '', hotel_name).strip())
    new_ids.append(hid)
```

## Step 6: Build Itineraries Array (ONE PER DAY)
```python
itineraries = []
for idx, section in enumerate(day_sections):
    desc_html = ''.join(f'<p>{para}</p>' for para in section['paras'])
    itineraries.append({
        'day_from': idx + 1,
        'day_to': idx + 1,
        'title': section['title'],
        'description': desc_html,
        'order': idx + 1,
        # REQUIRED empty arrays — omitting causes 500 error
        'image': [],
        'city_ids': [],
        'accommodation_ids': [],
        'meal_ids': [],
    })
```

## Step 7: Build Accommodation Pivots (ONLY IDs 1 AND 2)
```python
# Only populate ID 1 (Accommodation) and ID 2 (Flights if available)
acc_desc = '<p><strong>3* Star Hotel</strong><br>' + '<br>'.join(hotels_3) + '</p>'
acc_desc += '<p><strong>4* Star Hotel</strong><br>' + '<br>'.join(hotels_4) + '</p>'
acc_desc += '<p><strong>5* Star Hotel</strong><br>' + '<br>'.join(hotels_5) + '</p>'

accommodations = []
for acc in tour.get('accommodations', []):
    if acc['id'] == 1:
        accommodations.append({
            'id': 1,
            'name': acc['name'],
            'pivot': {'description': acc_desc, 'included': 1},
        })
    elif acc['id'] == 2:
        # Only fill if explicitly requested (flights info)
        accommodations.append({
            'id': 2,
            'name': acc['name'],
            'pivot': {'description': '', 'included': 1},
        })

# Skip IDs 3-10 unless user explicitly asks
```

## Step 8: Set Tour Fields
```python
tour['name'] = f'hermes - {original_name}'
tour['slug'] = f'hermes-{slugified_name}'
tour['introduction'] = brief_overview_html  # NOT the full itinerary!
tour['itineraries'] = itineraries  # One per day
tour['accommodations'] = accommodations  # Only IDs 1 and 2
```

## Step 9: POST Full Tour Object
```python
r = requests.post(f'{BASE}/tour/{id}', headers=headers, json=tour)
if r.status_code == 200:
    print("✅ Tour updated successfully")
else:
    print(f"❌ Error: {r.status_code} — {r.text[:200]}")
```

## Step 10: Verify via GET
```python
tour = requests.get(f'{BASE}/tour/{id}', headers=headers).json()
if 'data' in tour:
    tour = tour['data']
print(f"Name: {tour['name']}")
print(f"Itineraries: {len(tour.get('itineraries', []))}")
for itin in tour.get('itineraries', []):
    print(f"  Day {itin['day_from']}: {itin['title']}")
print("Accommodation pivots:")
for acc in tour.get('accommodations', []):
    pivot = acc.get('pivot', {})
    print(f"  ID {acc['id']} ({acc['name']}): included={pivot.get('included')}, desc_len={len(pivot.get('description', ''))}")
```

## Checklist

- [ ] Auth token obtained
- [ ] Tour fetched by ID (GET)
- [ ] DOCX parsed — days extracted as separate itinerary items
- [ ] Hotels extracted from DOCX tables
- [ ] New hotels created on platform if needed
- [ ] Itineraries array built (one per day, with empty arrays)
- [ ] Accommodation pivots: only IDs 1 and 2 populated
- [ ] Name/slug have `hermes -` prefix
- [ ] Tour posted (POST with full object)
- [ ] Verification via GET — itineraries count + pivot content confirmed
- [ ] Tracking sheet updated
