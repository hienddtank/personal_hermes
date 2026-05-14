#!/usr/bin/env python3
"""Update a RealisticAsia tour via API — authenticated GET + modify + POST.

Usage:
    python3 scripts/update-tour.py --tour-id 561
    python3 scripts/update-tour.py --tour-id 561 --dry-run
"""
import urllib.request, json, sys

CRED_FILE = '/tmp/cred.json'
BASE = 'https://api.realisticasia.com/v1'

def auth():
    creds = json.loads(open(CRED_FILE).read())
    req = urllib.request.Request(
        f"{BASE}/auth/login",
        data=json.dumps(creds).encode(),
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    return json.loads(urllib.request.urlopen(req).read())['access_token']

def get_tour(token, tour_id):
    h = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    r = urllib.request.Request(f"{BASE}/travel/tour/{tour_id}")
    for k, v in h.items():
        r.add_header(k, v)
    return json.loads(urllib.request.urlopen(r).read())['data']

def post_tour(token, tour):
    h = {"Authorization": f"Bearer {token}", "Accept": "application/json", "Content-Type": "application/json"}
    req = urllib.request.Request(
        f"{BASE}/travel/tour/{tour['id']}",
        data=json.dumps(tour).encode(),
        headers=h,
        method="POST"
    )
    return json.loads(urllib.request.urlopen(req).read())['data']

if __name__ == '__main__':
    tour_id = None
    dry_run = False
    args = sys.argv[1:]
    for i, a in enumerate(args):
        if a == '--tour-id' and i + 1 < len(args):
            tour_id = int(args[i + 1])
        if a == '--dry-run':
            dry_run = True

    if not tour_id:
        print("Usage: update-tour.py --tour-id <id> [--dry-run]")
        sys.exit(1)

    token = auth()
    tour = get_tour(token, tour_id)

    # TODO: Modify tour fields here
    # tour['name'] = '...'
    # for it in tour['itineraries']: ...

    if dry_run:
        print(json.dumps(tour, indent=2))
    else:
        result = post_tour(token, tour)
        print(f"Updated: {result['id']} - {result['name']}")
        for it in result.get('itineraries', []):
            print(f"  Day {it['day_from']}: {it['title']}")
