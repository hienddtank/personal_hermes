---
name: academic-paper-downloader
description: Download open-access PDFs of academic papers by DOI or URL. Uses Semantic Scholar API as primary source for OA PDF links, falls back to arXiv and publisher direct URLs. STOP immediately when hitting bot protection (403/Access Denied) — do not retry with different user-agents.
version: 1.0.0
category: research
---

# Academic Paper Downloader

## Quick Rules
- **STOP on bot protection:** When a server returns `403 Forbidden`, `Access Denied`, or Cloudflare challenge (`Just a moment...`), stop immediately and tell the user. Do NOT try different User-Agents, cookies, or workarounds — server-side bot filters always win from headless servers.
- **Always report what worked vs blocked** before creating zip files.

## Download Priority (fastest to slowest)

### 1. Semantic Scholar API (best source for OA PDFs)
```bash
curl -s "https://api.semanticscholar.org/graph/v1/paper/DOI:{doi}?fields=title,openAccessPdf,url,isOpenAccess" | python3 -m json.tool
```
Look for `openAccessPdf.url` — this is the most reliable source of direct PDF links.

### 2. arXiv (preprints)
Many paywalled papers have free arXiv preprints:
```bash
curl "https://export.arxiv.org/api/query?search_query=all:{doi}&start=0&max_results=3"
# Then download PDF from the entry link
wget -q -T 60 --user-agent="Mozilla/5.0 (compatible; Googlebot/2.1)" \
  -O paper.pdf "https://arxiv.org/pdf/{arxiv_id}.pdf"
```

### 3. Publisher Direct Download (with Googlebot UA)
```bash
wget -q -T 30 --user-agent="Mozilla/5.0 (compatible; Googlebot/2.1)" \
  -O paper.pdf "https://publisher.com/doi/pdf/{doi}"
```

### 4. Open Access Aggregators
- **CORE API:** `https://api.core.ac.uk/v3/search/works?q=doi:{doi}` — check for downloadLinks with `.pdf` URLs
- **Unpaywall:** `https://api.unpaywall.org/v2/{pmcid}?email=test@example.com`

## Known Publisher Behavior (from experience)
| Publisher | Bot Protection | Notes |
|-----------|---------------|-------|
| arXiv | None | Always works, use Googlebot UA for speed |
| Semantic Scholar API | None | Best OA source, no auth needed |
| MDPI | Akamai CDN blocks server requests | Open access but requires browser session with cookies |
| ACS Publications | Cloudflare `Just a moment...` page | Even Googlebot UA gets 403 — ask user to download manually |
| ScienceDirect (Elsevier) | Akamai/Cloudflare hybrid | Blocks non-browser clients consistently |
| APS (Physical Review) | Cloudflare | arXiv preprints often available as fallback |
| Springer/Nature | Varies | Check Semantic Scholar first |

## Workflow for Multiple Papers
1. Collect all DOIs from user request
2. Batch-query Semantic Scholar API for each DOI to find OA PDF links
3. For any without OA PDF, check arXiv using the title as search query
4. Attempt downloads in parallel (wget/curl with Googlebot UA)
5. **Immediately report** which were blocked — do not continue trying alternatives
6. Create zip of successfully downloaded PDFs and send to user

## Creating Zip and Sending via Telegram
```bash
cd /root/downloads
zip papers.zip *.pdf  # only valid PDFs
curl -F "chat_id={chat_id}" \
  -F "document=@papers.zip" \
  "https://api.telegram.org/bot{token}/sendDocument"
```

## Verification
Before zipping, verify each file is a real PDF:
```bash
file *.pdf | grep "PDF document"   # valid
file *.pdf | grep HTML              # blocked/download failed
```
