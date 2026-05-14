# LinkedIn Crawling — Selectors, Patterns & Pitfalls

## Search URL Pattern

```
https://www.linkedin.com/search/results/all/?keywords=NAME+COMPANY&origin=GLOBAL_SEARCH_HEADER
```

Use `quote_plus()` for the keywords parameter. Include company name in query for better accuracy.

## Search Results DOM Structure

After navigation, look for these selectors:

| What | Selector | Notes |
|------|----------|-------|
| Profile links | `a[href*="/in/"]` | Most reliable — matches any person profile card |
| Result cards | `[data-entity-urn]` | Container around each result |
| Card titles | `.text-body-small, .t-black--normal, .t-black--light` | Snippet text below name |
| Connection count (on profile) | `.pv-top-card-social-contacts a span` | Shows "500+ connections" |

## Profile Page Selectors

| What | Selector |
|------|----------|
| Headline | `.pv-top-card-section--headline .text-body-medium.break-words` |
| Connection count | `.pv-top-card-social-contacts a span` |
| Industry | `.pv-top-card-skills-and-experts .t-black--light` |

## Anti-Detection Guidelines

### Rate Limiting
- **4-9 seconds** between searches (randomized)
- LinkedIn typically allows ~15-30 searches before triggering friction
- After a captcha: wait 15-30 minutes before retrying

### Session Management
- Use `launch_persistent_context()` with a directory like `.linkedin_session/`
- First login MUST be in headed mode (interactive browser window)
- Subsequent runs can use `headless=True`
- Clear session dir (`rm -rf .linkedin_session/`) to force re-login

### Common Failure Modes

1. **Captcha wall** — URL contains `/checkpointTrigger*`. Stop, wait, re-login.
2. **"See yourself" pop-up** — LinkedIn prompts you to verify your profile. Dismiss with the X button or by navigating away.
3. **Search throttling** — If search results load slowly or show generic "People you may know", you've been rate-limited. Add longer delays (10-15s).
4. **Account restriction** — Unusual activity flag. Requires manual login on a recognized device/browser to resolve.

## URL Cleaning

LinkedIn profile URLs often come with tracking params. Clean them:

```python
# Input: https://www.linkedin.com/in/john-doe?originalReferer=...
# Output: https://www.linkedin.com/in/john-doe

url = href.split('?')[0]
if not url.startswith('http'):
    url = 'https://www.linkedin.com' + url
url = url.rstrip('/')
```

## JavaScript Extraction Patterns

### From Search Results Page
Extract data without clicking into each profile (faster, less detection risk):

```javascript
// Extract first result card's text fields
const link = document.querySelector('a[href*="/in/"]');
const container = link?.closest('[data-entity-urn]');
const texts = Array.from(container?.querySelectorAll('.text-body-small, .t-black--normal') || [])
    .map(el => el.innerText.trim())
    .filter(t => t);
// texts[0] = title, texts[1] = company, texts[2] = location (varies)
```

### From Profile Page
Get headline and connections:

```javascript
const headlineEl = document.querySelector('.pv-top-card-section--headline .text-body-medium.break-words');
const connEl = document.querySelector('.pv-top-card-social-contacts a span');
return {
    headline: headlineEl?.innerText.trim(),
    connections: connEl?.innerText.trim().match(/\d+/)?.[0] || ''
};
```

## Performance Notes

- **Search page only** (~3s per record): Extract name, title, company from search snippet. Fastest, lowest detection risk.
- **Visit profile page** (~5s per record): Gets headline and connection count. Higher detection risk but richer data.
- **Recommendation**: Visit profile page for first 20 records to build confidence, then switch to search-only extraction for the batch to reduce exposure.
