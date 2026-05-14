---
name: educational-resources
description: Find, verify, and organize free textbook/course materials (PDFs, lecture notes, exercise books). Handles discovery from OpenStax/MIT OCW/university sources and verification of PDF legitimacy.
version: 1.0.0
category: research
---

# Educational Resources Discovery

## Quick Rules
- **Verify before trusting:** Free textbook PDFs are often redirect wrappers or placeholder pages. Always check page count vs file size.
- **Use curl -L** not wget for academic sites (better redirect handling).
- **Descriptive filenames:** `<Source>_<Subject>Vol<N>.pdf` — never `download.pdf`.

## Discovery

### Search Patterns (use duckduckgo-search)
- `<topic> textbook exercises PDF free download`
- `<topic> "free" filetype:pdf`
- `<university> <course-name> open courseware pdf`

### Reliable Sources
| Source | What It Has | Notes |
|--------|------------|-------|
| OpenStax | Full peer-reviewed textbooks (Calc Vol 1/2/3) | Free, CC licensed. PDFs are ~10MB+ each |
| MIT OCW | Complete course materials + textbooks | Use specific file links, not the landing page |
| Portland State (Erdman) | Pure exercise/problem sets | Great supplementary practice |
| LibreTexts | Online textbooks | Sometimes has downloadable PDFs |
| archive.org | Older/out-of-print textbooks | May be slow to download |
| University department pages | Lecture notes, custom texts | Varies in quality |

## Verification (CRITICAL STEP)

Free textbook PDFs are often redirect wrappers. ALWAYS verify:

```bash
# Count MediaBox entries (one per page in uncompressed PDFs)
python3 -c "
import re
with open('file.pdf', 'rb') as f:
    data = f.read()
print(f'MediaBox count: {len(re.findall(b\"/MediaBox\", data))}')
"

# Sanity check: size vs page count
#   300+ pages → should be 5MB+ (compressed) or 15MB+ (uncompressed)
#   < 2MB with >100 "pages" = likely a redirect/placeholder
```

Red flags of fake/incomplete PDFs:
- File size < 3MB for a claimed full textbook
- First page contains `/S /GoTo` (redirect destination object)
- Page count doesn't match expected textbook length
- `strings file.pdf | head -10` shows HTML content instead of `%PDF`

## Download Pattern
```bash
cd <target-directory>
curl -L -o "DescriptiveName.pdf" "<url>" --compressed
# Use generous timeouts for large files:
# timeout 600 curl -L ...
```

## Verification Script
Run `scripts/verify_pdf.py <files...>` for automated checks (header, MediaBox count, size sanity, redirect detection).

```bash
python3 /hermes-home/skills/research/educational-resources/scripts/verify_pdf.py file1.pdf file2.pdf
```

## Known Quirks
- **OpenStax PDFs are fully compressed** (FlateDecode) — `/MediaBox` won't appear in raw bytes. Use file size (~10MB per volume) as the proxy.
- **MIT OCW landing pages** may link to course notes, not textbooks. Verify with page count.
- **Portland State / some university sites** serve PDFs that redirect internally — verify the real content length.