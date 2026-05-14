# Tour Accommodation Template

**File:** `/host/d/mkt/python/hermes/workspace/tours/tour_accommodation.json`

Standard JSON template with all 10 accommodation category pivots pre-configured. Used as the baseline for every tour — only IDs 1 and 2 need content filled in.

## Structure

```json
{
  "accommodations": [
    {"id": 1, "name": "Accommodation",   "pivot": {"description": "", "included": 1}},
    {"id": 2, "name": "Flights",         "pivot": {"description": "", "included": 1}},
    {"id": 3, "name": "Guide",           "pivot": {"description": "<p>Experienced English-speaking guide...</p>", "included": 1}},
    {"id": 4, "name": "Meals",           "pivot": {"description": "<div>As per tour program: B/L/D...</div>", "included": 1}},
    {"id": 5, "name": "Insurance",       "pivot": {"description": "<div>Insurance are not included</div>", "included": 0}},
    {"id": 6, "name": "Transport",       "pivot": {"description": "<div>- Door-to-door pick-up...</div>", "included": 1}},
    {"id": 7, "name": "Optional",        "pivot": {"description": "<div>Insurance are not included</div>", "included": 2}},
    {"id": 8, "name": "Other included",  "pivot": {"description": "<div>- Accommodation with breakfast...</div>", "included": 1}},
    {"id": 9, "name": "Other not included", "pivot": {"description": "<div>• Flights, tips, E-visa...</div>", "included": 0}},
    {"id": 10, "name": "COVID-19...",    "pivot": {"description": null, "included": 2}}
  ]
}
```

## Usage

1. GET tour → extract existing accommodations
2. Load `tour_accommodation.json`
3. Fill ID 1 pivot.description with hotels from DOCX (name + rating only)
4. Fill ID 2 pivot.description with flight info (when available)
5. Replace tour's `accommodations` array entirely with template
6. POST full tour object

## Convention

- **No URLs** in any pivot description — plain text names and ratings only
- Star ratings: `***` (3-star), `****` (4-star), `*****` (5-star)
- Format: `"Hotel Name *** Room Type (City)"`
- IDs 3–10 are pre-configured and do not need modification unless explicitly changed

## Session History

### 2026-05-14 — Tour 561 fix
- Applied template to tour 561 "Journey to the Enchanting Golden Rock"
- Extracted hotels from DOCX, cleaned URLs and trailing notes
- Hotels: Grand United Ahlone (***), KyaikHto (*** Deluxe/Super Deluxe), Park Royal Yangon (****), Pan Pacific Yangon (***)
- Issue: Pan Pacific star rating lost during cleaning (raw DOCX has stars in separate cell/format)
- IDs 3–10 replaced with template defaults
