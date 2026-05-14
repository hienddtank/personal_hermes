# Tour 562 - Gems of Myanmar Upload via DOCX

## Source Document
`D:\mkt\python\hermes\workspace\tours\06 Days_Gems of Myanmar Tour.docx`

## Result (Verified 2026-05-14)
- **Name:** `hermes - Gems of Myanmar Tour - 6 Days` (test prefix per convention)
- **Slug:** `hermes-gems-of-myanmar-tour-6-days`
- Duration: 6 days, 5 nights
- Route: YANGON – HEHO – KALAW – INLE LAKE – YANGON
- Admin: https://admin.realisticasia.com/travel/tour/562

## Itinerary from Paragraphs (not tables)

This DOCX had NO itinerary in tables — all daily content was in paragraphs. Day headers identified by `DAY \d+:` pattern, content collected until next day header or non-itinerary section (QUOTATION, ACCOMODATION, etc.).

```python
current_day = None
day_sections = []
for p in doc.paragraphs:
    txt = p.text.strip()
    if not txt or len(txt) < 5:
        continue
    if any(skip in txt.upper() for skip in ['QUOTATION', 'ACCOMODATION', 'BOOKING POLICY', 'PASSPORT']):
        break  # stop at non-itinerary
    day_match = re.match(r'(DAY\s+\d+|ARRIVAL|DEPARTURE)', txt, re.IGNORECASE)
    if day_match and len(txt) < 120:
        current_day = txt.strip()
        day_sections.append((current_day, []))
    elif current_day:
        day_sections[-1][1].append(txt.replace('\n', '<br>'))

# Build HTML
html = '<p><strong>Tour Title</strong></p>'
for title, paras in day_sections:
    html += f'<h3>{title}</h3>'
    for para in paras:
        html += f'<p>{para}</p>'
```

## Pricing Tables

DOCX contains 4 pricing tables (2 seasons x 2 cost types), each 6 rows x 9 columns:
- Table 1: Low Season - Supplier Net Cost
- Table 2: Low Season - RA Retail Cost
- Table 3: High Season - Supplier Net Cost
- Table 4: High Season - RA Retail Cost

Each table structure:
- Row 0: Header (merged cells)
- Row 1: Column labels: Tour Cost, 01 Pax, 02 Pax, 03-05 Pax, 06-09 Pax, 10-14 Pax, 15-19 Pax, 20+ Pax, Single Supplement
- Row 2: 03* Star Hotel prices
- Row 3: 04* Star Hotel prices
- Row 4: 05* Star Hotel prices
- Row 5: Surcharge for Language Speaking Guide

```python
def parse_price_table(table):
    rows = []
    for row in table.rows[1:]:  # skip header
        cells = [c.text.strip().replace(',', '').replace('\n', '') for c in row.cells]
        label = cells[0]
        prices = cells[1:]
        if prices and prices[0].isdigit():
            rows.append((label, [int(p) if p.isdigit() else 0 for p in prices]))
    return rows
```

## Accommodations Created

- ID 17: Nyaung Shwe City Hotel ***Superior Room (Inle Lake, 3*)
- ID 18: Amata Garden Inle Lake Resort **** Super Deluxe Room With Lake View (Inle Lake, 4*)
- ID 19: Aureum Palace Inle Hotel & Resort***** Deluxe Room With Lake View (Inle Lake, 5*)
- Reused from tour 561: IDs 12-14 (Yangon hotels)
