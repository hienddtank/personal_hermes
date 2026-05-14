# Tour 561 - Myanmar Upload via DOCX

## Source Document
`D:\mkt\python\hermes\workspace\tours\05 Days_Journey to the Enchanting Golden Rock.docx`

## Parsing Strategy
- First table row → tour introduction
- Paragraphs with `DAY\s*0*\d+:\s*(.*)` regex → day headers
- Subsequent paragraphs until next day header → day content
- Stop at "QUOTATION", "ACCOMMODATION" sections
- Meal indicators `(B)`, `(-)` stripped from titles

## Result
- Title: `hermes - Journey to the Enchanting Golden Rock`
- Slug: `hermes-journey-to-the-enchanting-golden-rock-5-days`
- 5 itineraries with HTML `<p>...</p>` descriptions
- All itinerary IDs preserved (6235–6239)

## AMPERSAND TRAP (Critical)
Python heredocs (`<< 'EOF' ... EOF`) interpret `&` as background process. When building DOCX content with HTML containing `&amp;` or similar entities, the heredoc silently breaks. 

**Fix:** Always write Python scripts to `/tmp/file.py` then run via `python3 /tmp/file.py`. Never use inline heredocs for scripts that process DOCX content or contain HTML entities.

## Itinerary ID Management
- Existing IDs: 6235–6239 (Days 1–5)
- Empty extra days (IDs 6242–6246) were removed by filtering array
- When adding new itineraries: omit `id` field → API auto-generates
