"""Scaffold for updating a RealisticAsia tour via API.

Usage: python3 <this_file>.py --tour-id 561
Modifies tour fields and itineraries, then POSTs back.
"""
import urllib.request, json, sys, os

# --- Config ---
CRED_FILE = '/tmp/cred.json'
BASE = 'https://api.realisticasia.com/v1'

# --- Auth ---
creds = json.loads(open(CRED_FILE).read())
req = urllib.request.Request(
    f"{BASE}/auth/login",
    data=json.dumps(creds).encode(),
    headers={"Content-Type": "application/json"},
    method="POST"
)
token = json.loads(urllib.request.urlopen(req).read())['access_token']
H = {
    "Authorization": f"Bearer {token}",
    "Accept": "application/json",
    "Content-Type": "application/json",
}

# --- GET current tour ---
tour_id = None
for arg in sys.argv[1:]:
    if arg == '--tour-id':
        tour_id = int(sys.argv[sys.argv.index(arg)+1])
if not tour_id:
    print("Usage: python3 update-tour.py --tour-id <id>")
    sys.exit(1)

r = urllib.request.Request(f"{BASE}/travel/tour/{tour_id}")
for k, v in H.items():
    r.add_header(k, v)
tour = json.loads(urllib.request.urlopen(r).read())['data']
print(f"Fetched tour {tour['id']}: {tour['name']}")

# --- TODO: Modify the tour ---
# Example:
tour['name'] = 'Updated Tour Name'
tour['slug'] = 'updated-tour-name'
tour['introduction'] = '<p>Updated intro HTML</p>'

# Itineraries
myanmar_days = [
    {"day_from": 1, "title": "Day 1 Title", "description": "<p>Day 1 content</p>"},
    {"day_from": 2, "title": "Day 2 Title", "description": "<p>Day 2 content</p>"},
]
for i, day in enumerate(myanmar_days):
    if i < len(tour['itineraries']):
        it = tour['itineraries'][i]
        it['title'] = day['title']
        it['description'] = day['description']
        it['day_from'] = day['day_from']
        it['day_to'] = day['day_from']
        it['order'] = day['day_from']

# --- POST update ---
data = json.dumps(tour).encode()
req2 = urllib.request.Request(
    f"{BASE}/travel/tour/{tour_id}",
    data=data,
    headers=H,
    method="POST"
)
try:
    resp = urllib.request.urlopen(req2)
    result = json.loads(resp.read())['data']
    print(f"Updated tour {result['id']}: {result['name']}")
    for it in result.get('itineraries', []):
        print(f"  Day {it['day_from']}: {it['title']}")
except urllib.error.HTTPError as e:
    err = e.read().decode()
    print(f"HTTP {e.code}: {err[:500]}")
    sys.exit(1)
