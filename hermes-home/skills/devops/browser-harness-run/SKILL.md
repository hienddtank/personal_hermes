---
name: browser-harness-run
description: Execute browser commands against Docker Chromium via the browser-harness API at http://browser-harness:8769/run
---

# Browser Harness Run

Execute browser commands against Docker Chromium via `http://browser-harness:8769/run`.

## API

```
POST http://browser-harness:8769/run
{
  "code": "sync Python code using pre-imported helpers",
  "timeout": 120
}
```

Response: `{ok, returncode, stdout, stderr, elapsed_sec}`

## Key Rule

**Do NOT use async/await or raw Playwright.** The harness runs synchronous helper functions from its `helpers` module (pre-imported). Use sync helpers only.

## Helper Functions (pre-imported, no import needed)

| Function | Description |
|---|---|
| `goto_url(url)` | Navigate to URL |
| `wait_for_load(timeout=15)` | Wait for document.readyState == 'complete' |
| `page_info()` | Returns `{url, title, w, h, sx, sy, pw, ph}` |
| `capture_screenshot(path, full=False)` | Save screenshot to path |
| `click_at_xy(x, y, button='left', clicks=1)` | Click at coordinates |
| `type_text(text)` | Type text into focused element |
| `press_key(key, modifiers=0)` | Key press. Modifiers: Alt=1, Ctrl=2, Meta=4, Shift=8 |
| `scroll(x, y, dy=-300, dx=0)` | Scroll page |
| `js(expression, target_id=None)` | Execute JS in page context |
| `cdp(method, **params)` | Raw CDP: `cdp('Page.navigate', url='...')` |
| `new_tab(url='about:blank')` | Open new tab |
| `switch_tab(target_id)` | Switch to tab |
| `list_tabs(include_chrome=True)` | List all tabs |
| `current_tab()` | Get current tab info |
| `ensure_real_tab()` | Switch away from chrome:// internal pages |
| `dispatch_key(selector, key='Enter', event='keypress')` | Dispatch keyboard event on element |
| `http_get(url, headers=None, timeout=20)` | Pure HTTP request (no browser) |
| `wait(seconds=1.0)` | Sleep |
| `upload_file(selector, path)` | Set files on file input via CDP |
| `iframe_target(url_substr)` | Get iframe target ID |

## Docker Service URLs

- `http://open-webui:8080`
- `http://hermes:8642`
- `http://firecrawl-api:3002`
- Host services: `http://host.docker.internal:<port>`

## Examples

### Navigate and capture page info
```
goto_url('http://open-webui:8080'); wait_for_load(); print(page_info())
```

### Take screenshot
```
capture_screenshot('/tmp/page.png')
```

### Execute JS to extract content
```
js('document.querySelectorAll("h1")[0]?.textContent')
```

### Click at coordinates
```
click_at_xy(100, 200)
```

### Type text and press enter
```
type_text('hello world'); press_key('Enter')
```

### List tabs and switch
```
tabs = list_tabs(); print(tabs); switch_tab(tabs[0]['id'])
```

## Common Patterns

- **Navigation:** `goto_url(url); wait_for_load(); print(page_info())`
- **Screenshot:** `capture_screenshot('/tmp/shot.png')`
- **JS extraction:** `js('document.title')` or extract links with `js('JSON.stringify(Array.from(document.querySelectorAll("a")).map(a=>({t:a.textContent,h:a.href})))')`
- **Form fill:** `type_text('value'); press_key('Tab'); type_text('next')`
- **HTTP only (no browser):** `http_get('http://example.com/api/data')`

## Pitfalls

- NO `await` / NO `async def` / NO raw Playwright (`browser.new_page()`) — use sync helpers
- **Async mode produces NO stdout**: If you define `async def main():` and call `print()` inside it, output is swallowed — nothing appears in the harness response. Always use sync helpers (`goto_url`, `js`, `page_info`, etc.) for interactive exploration.
- Screenshot goes to harness container's filesystem (`/tmp/`), not local
- Each call reuses the same browser session (state persists between calls)
- Do NOT run concurrent browser tasks against the same profile
- Keep timeouts explicit for long tasks
- **Quoting hell**: Multi-line Python code with nested JS strings causes shell escaping failures. Use single-line code with `;` or write to a `.py` file first, then run via `execute_code` with `requests` library directly (with proper browser User-Agent)
- **SPA sites**: If `http_get()` returns a small HTML shell (20-40KB) with no content, the site is a JS SPA. Download the JS bundle (find it via `goto_url()` → `js()` to list `<script>` tags), then search the bundle for `fetch()`/`axios()` calls to find the real API. See `web-scraping` skill → `references/spa-api-discovery.md`
- **Rich text editors (TinyMCE/CKEditor)**: Editor content lives in iframes, not visible DOM. Access via `iframe.contentDocument.body.innerHTML`. Example: `Array.from(document.querySelectorAll('iframe')).map(f=>f.contentDocument?.body?.innerText)`. See `references/admin-panel-editing.md`
- **Form values via JS**: Setting `input.value = "x"` doesn't trigger Vue/React watchers. Must also dispatch events: `el.dispatchEvent(new Event("input",{bubbles:true}))`
- **Direct URL > list browsing**: Pages with pagination/lazy-load frequently timeout. Always use direct resource URLs (e.g., `/travel/tour/555`) instead of navigating through list pages.
- **Ant Design tab switching**: Use `.ant-tabs-tab` elements for tab navigation. Find by text content and click: `Array.from(document.querySelectorAll('.ant-tabs-tab')).find(t=>t.textContent.trim()=='TabName')?.click()`
- **Delete via UI when API fails**: If API DELETE endpoints don't exist or fail, use the admin panel UI. Ant Design delete buttons use `.ant-btn-danger`. Work bottom-up (delete highest index first) so indices don't shift. See `references/admin-panel-editing.md`
- **Save button fallback**: If `.ant-btn-primary` doesn't match (e.g., inside certain tabs), find by text: `Array.from(document.querySelectorAll('button')).find(b=>b.textContent.trim()==='Save')?.click()`
