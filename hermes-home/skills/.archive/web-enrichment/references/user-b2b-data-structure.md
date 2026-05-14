# User's B2B Contact Data Structure

## Location
`/host/d/mkt/python/B2B/` and `/host/d/mkt/python/B2B cleaning 2/` on Windows host (WSL: `/host/d/mkt/python/B2B/`)

## Primary Datasets (by size)
| File | Rows | Key Columns | Notes |
|---|---|---|---|
| `Host Agencies list.xlsx` | 94,454 | xlsx format | LARGEST — full host agency master |
| `favorites_exploded.csv` | 80,677 | destination + continent | Exploded/expended contacts |
| `output_with_intro_bullets (1).csv` | 45,580 | Company, Full name, First name, Last name | |
| `remapped_by_company.xlsx` | 32,507 | nested per-company files | xlsx |
| `remapped_by_company_bak.xlsx` | 27,097 | same as above (backup) | |
| `favorites_with_continents.csv` | 26,919 | Company, Full name, First name, Last name, Email, LinkedIn, Phone, Job Title, Location + continent tags | MAIN enriched contact list |
| `favorites_with_continents copy.csv` | 7,696 | Same as above (backup variant) | |
| `Host Agencies list - Virtuoso.csv` | 10,505 | Same schema | Virtuoso-only subset |
| `output_with_first_name.csv` | 10,188 | url, name, first/last name, email, website, phone | CruisePlanners source |
| `cruise_planner.csv` (×7 variants) | 10,188 each | url, name, website, email, phone, status | CruisePlanners scraped data |
| `Host Agencies list - Travel Leaders.csv` | 7,912 | Source, Company, Full name, First name, Last name, Email | Travel Leaders network |

## Signature Network Data
**File:** `/host/d/mkt/python/B2B/Signature Network - Signature Network.csv` (also at `/workspace/signature-network/`)
- **2,010 rows** of Signature Travel Network agents
- Columns: `Name`, `Company`, `Location`, `Phone`, `Link` (profile URL), `bio`, `Language`, `Destination`, `specialize`, `Product`
- No LinkedIn column — this is a separate source for enrichment

## Agency Database Files (in `B2B cleaning 2/`)
| File | Rows | Notes |
|---|---|---|
| `Agency Database - Huyen.csv` | 2,869 | Generic columns (`'', '', '', ...`) |
| `Agency Database - Annie.csv` | 2,392 | Total, Protencial, Reached Out, Answered, Sent request, Have booking |
| `Agency Database - Nhung.csv` | 773 | Same as Annie |
| `Agency Database.xlsx` | 2,825 | Master agency DB (xlsx) |
| `Lemlist.xlsx` | 9,383 | Lemlist campaign data |
| `Mailchimp.xlsx` | 3,728 | Mailchimp campaign data |

## Nested Company Files (hundreds of individual company lists)
Two subdirectories with per-company Excel/CSV files:
- `/B2B cleaning 2/prepared_by_company/` — ~100+ per-company files (xlsx, ~600-900 rows each)
- `/B2B cleaning 2/remapped_by_company/` — same files (remapped versions)
- `/B2B cleaning 2/remapped_by_company_bak/` — backups of above

Each file is named after the company (e.g., `Fora.xlsx`, `Coastline Travel Advisors.xlsx`) and contains ~600-900 individual contacts at that agency.

## Key Patterns
- Some files have BOM (`\ufeff`) on first column name
- Company names are travel agencies (luxury travel industry)
- Data is B2B travel agency contacts for outreach campaigns
- `favorites_with_continents.csv` is the main enriched contact list (~4.5k) — LinkedIn column exists but is empty, ready for discovery
- The Signature Network data (2k agents) uses a different schema — needs separate enrichment workflow
- Large files (>10k rows) should be handled via terminal `find` commands rather than `search_files` (which times out on huge directories)
