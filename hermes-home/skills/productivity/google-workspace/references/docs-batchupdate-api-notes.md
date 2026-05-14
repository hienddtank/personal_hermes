# Google Docs batchUpdate API — Notes & Quirks

## Credential: Service Account (May 2026)

User has service account at `D:\mkt\python\hermes\workspace\google\test-hermes-automation-45a191056406.json`
Container path: `/host/d/mkt/python/hermes/workspace/google/test-hermes-automation-45a191056406.json`
Email: `hermes-auto@test-hermes-automation.iam.gserviceaccount.com`
Project: `test-hermes-automation`

**IMPORTANT:** Service accounts CANNOT see user comments via the Docs API (even with writer permissions). Always ask user to paste comment text instead.

## Authentication Pattern

```python
from google.oauth2 import service_account
from googleapiclient.discovery import build

creds = service_account.Credentials.from_service_account_file(
    "/workspace/google/test-hermes-automation-45a191056406.json",
    scopes=["https://www.googleapis.com/auth/documents"],
)
docs = build("docs", "v1", credentials=creds)
```

## Environment Quirks

- Python at `/opt/venv/bin/python`, pip at `/usr/local/bin/pip`
- Install: `/usr/local/bin/pip install --target /opt/venv/lib/python3.11/site-packages google-api-python-client google-auth`
- Response key: `doc["body"]["content"]` NOT `doc["document"]["body"]["content"]`

## Index Model

- **Index 0** = implicit section break. Cannot be styled, deleted, or modified.
- All user-inserted text starts at **index 1**.
- `insertText` at `{index: 1}` inserts text BEFORE any existing content at position 1.
- When computing ranges for subsequent style updates, add offset of 1 to your string positions.

## Field Names That Trip Agents Up

| What you might guess | Actual field name |
|---------------------|-------------------|
| `namedStyle` | `namedStyleType` |
| `PARAGRAPH_STYLE_TYPE_NAMED_STYLE` (as fields value) | `"namedStyleType"` |

## DeleteContentRange Rules

- Range `[start, end)` is half-open: includes start, excludes end.
- **Cannot include the final newline of a segment** — use `endIndex - 1` when clearing content.
- If doc has only index 0 (empty after clear), don't attempt delete.

## Heading Style Names

- `"HEADING_1"` through `"HEADING_9"`
- `"TITLE"`, `"NORMAL_TEXT"`

## BatchUpdate Sequential Processing

Requests execute in order. Each request shifts indices for subsequent ones. Strategy:
1. Delete existing content (range-based)
2. Insert new text (at index 1)
3. Apply styles using ranges computed from the inserted text's positions

**Key**: compute all heading ranges BEFORE building requests, not after each insert.

## Example: Clear + Write Full Document

See the structured write pattern in SKILL.md under "Service Account — Docs: Structured Write Pattern".

## Error Messages → Fixes

| Error | Fix |
|-------|-----|
| `Unknown name "namedStyle"` | Use `"namedStyleType"` instead |
| `Cannot include the newline character at the end of the segment` | Use `endIndex - 1` in delete range |
| `Cannot operate on the first section break` | Don't target index 0; start ranges at 1 |
| `403 Insufficient Permission` | Share doc with service account email, or use a broader scope |

## Text Replacement Anti-Pattern: Index Shifting

When you do `deleteContentRange` + `insertText` pairs in batchUpdate, each pair shifts ALL subsequent absolute positions by `(old_length - new_length)`. This caused cascading corruption in a B2B protocol doc on 2026-05-12:

**What happened:** Replaced "potencial" with "potential" at position X, then replaced at position Y — but Y was computed before the first replacement executed, so it hit the wrong spot, creating "Interestpotentialtencial".

**SAFE pattern — find-by-content, not by pre-computed indices:**

```python
from google.oauth2 import service_account
from googleapiclient.discovery import build

def find_by_content(doc, search_text):
    """Find text content in doc, return absolute position or None."""
    for el in doc["body"]["content"]:
        if "paragraph" not in el: continue
        cur = el.get("startIndex", 0)
        for elem in el["paragraph"].get("elements", []):
            tr = elem.get("textRun", {})
            if not tr:
                cur += 1; continue
            content = tr.get("content", "")
            pos = content.find(search_text)
            if pos >= 0:
                return cur + pos, len(search_text)
            cur += len(content)
    return None

# Build replacements
fixes = [
    ("old_text_1", "new_text_1"),
    ("old_text_2", "new_text_2"),
]

# Read doc ONCE, find ALL positions
doc = docs.documents().get(documentId=DOC_ID).execute()
requests = []
for old, new in fixes:
    result = find_by_content(doc, old)
    if result:
        pos, length = result
        requests.append({"deleteContentRange": {"range": {"startIndex": pos, "endIndex": pos + length}}})
        requests.append({"insertText": {"location": {"index": pos}, "text": new}})

# Execute ALL at once
docs.documents().batchUpdate(documentId=DOC_ID, body={"requests": requests}).execute()
```

**Key rules:**
1. Read the doc ONCE, find all positions from that single read
2. If content is already corrupted, search for the EXACT corrupted string (e.g., "Interestpotentialtencial"), not the original
3. After each batch, verify by re-reading and scanning for bad patterns
4. Bullet inserts: check char AFTER insert position is space/newline, not a letter
