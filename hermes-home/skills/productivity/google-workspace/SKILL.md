---
name: google-workspace
description: "Gmail, Calendar, Drive, Docs, Sheets via gws CLI or Python."
version: 1.1.0
author: Nous Research
license: MIT
platforms: [linux, macos, windows]
required_credential_files:
  - path: google_token.json
    description: Google OAuth2 token (created by setup script)
  - path: google_client_secret.json
    description: Google OAuth2 client credentials (downloaded from Google Cloud Console)
metadata:
  hermes:
    tags: [Google, Gmail, Calendar, Drive, Sheets, Docs, Contacts, Email, OAuth]
    homepage: https://github.com/NousResearch/hermes-agent
    related_skills: [himalaya]
---

# Google Workspace

Gmail, Calendar, Drive, Contacts, Sheets, and Docs — through Hermes-managed OAuth and a thin CLI wrapper. When `gws` is installed, the skill uses it as the execution backend for broader Google Workspace coverage; otherwise it falls back to the bundled Python client implementation.

## References

- `references/gmail-search-syntax.md` — Gmail search operators (is:unread, from:, newer_than:, etc.)
- `references/docs-batchupdate-api-notes.md` — Google Docs batchUpdate API quirks, field names, and the structured document write pattern

## Scripts

- `scripts/setup.py` — OAuth2 setup (run once to authorize)
- `scripts/google_api.py` — compatibility wrapper CLI. It prefers `gws` for operations when available, while preserving Hermes' existing JSON output contract.

## Authentication Modes

This skill supports TWO auth modes. Pick the one that matches your credentials:

| Mode | When to use | Credential file | Setup needed? |
|------|-------------|-----------------|---------------|
| **OAuth2 (desktop)** | You need access as YOUR Google account (personal Gmail, Calendar, etc.) | `client_secret_*.json` from Google Cloud Console | Yes — interactive OAuth flow |
| **Service Account** | Automated agent access; you share specific Docs/Sheets/Drive files with the service email | `*-iam.gserviceaccount.com` JSON key | No — works immediately |

**If you have a service account JSON key**, skip the OAuth2 setup entirely. Use the Python Google API directly (see "Service Account Usage" below). The `gws` CLI and `google_api.py` script require OAuth2, but for Docs/Sheets/Drive automation, the Python API with service accounts is simpler and more reliable.

## Service Account Usage

No setup needed — just install deps and use:

```python
from google.oauth2 import service_account
from googleapiclient.discovery import build

creds = service_account.Credentials.from_service_account_file(
    "/path/to/service-account-key.json",
    scopes=["https://www.googleapis.com/auth/documents"],  # or spreadsheets, drive, etc.
)

docs = build("docs", "v1", credentials=creds)
sheets = build("sheets", "v4", credentials=creds)
drive = build("drive", "v3", credentials=creds)
```

Common scopes:
- `https://www.googleapis.com/auth/documents` — Docs read/write
- `https://www.googleapis.com/auth/spreadsheets` — Sheets read/write
- `https://www.googleapis.com/auth/drive` — Drive full access
- `https://www.googleapis.com/auth/drive.readonly` — Drive read-only

**Important:** The service account email (e.g. `hermes-auto@project.iam.gserviceaccount.com`) must be granted access to each specific Doc/Sheet/Drive file by the owner. Share via the Google UI or `drive share FILE_ID --email SERVICE_ACCOUNT_EMAIL`.

**Pip install note on this environment:** Python lives at `/opt/venv/bin/python` but pip is at `/usr/local/bin/pip`. If packages don't appear, use:
```bash
/usr/local/bin/pip install --target /opt/venv/lib/python3.11/site-packages google-api-python-client google-auth
```

### Service Account — Docs API Pitfalls (batchUpdate)

### Service Account — Docs API Pitfalls (batchUpdate)

These are hard-won from actual API calls — they will save you iterations:

0. **Docs API does not expose comments for service accounts** — The Docs v1 API has no `comments()` resource for service account credentials (returns 400 / AttributeError). However, the Drive v3 API DOES support comments via `drive.comments().list()`. Use this workaround:

   ```python
   from google.oauth2 import service_account
   from googleapiclient.discovery import build

   creds = service_account.Credentials.from_service_account_file(
       "/path/to/key.json",
       scopes=["https://www.googleapis.com/auth/documents", "https://www.googleapis.com/auth/drive"],
   )
   drive = build("drive", "v3", credentials=creds)

   result = drive.comments().list(
       fileId=DOC_ID,
       fields="comments(id,author,content,createdTime,modifiedTime,replies)"
   ).execute()
   for c in result.get("comments", []):
       print(c["content"])
       for r in c.get("replies", []):
           print(f"  reply: {r['content']}")
   ```

   The `fields` parameter is required — omitting it returns a 400 error. Use the field list above as the minimum that works. If the user mentions "comments" on a doc, try this Drive API approach before asking them to paste anything.

1. **Response structure**: The `get()` response is the document object directly — use `doc["body"]["content"]` NOT `doc["document"]["body"]["content"]`.

2. **Heading style field name**: Use `"namedStyleType"` (not `"namedStyle"`) in `updateParagraphStyle`:
   ```python
   {"updateParagraphStyle": {
       "range": {"startIndex": S, "endIndex": E},
       "paragraphStyle": {"namedStyleType": "HEADING_1"},
       "fields": "namedStyleType",
   }}
   ```

3. **Delete range cannot include final newline**: When clearing a doc, use `end_idx - 1`:
   ```python
   last = doc["body"]["content"][-1]["endIndex"]
   {"deleteContentRange": {"range": {"startIndex": 1, "endIndex": last - 1}}}
   ```

4. **Index 0 is the implicit section break** — you cannot style or delete it. All user content starts at index 1. When inserting text then applying heading styles, offset your computed ranges by +1:
   ```python
   # Text "B2B Email Reply Protocol" inserted at index 1
   # Its heading range is (1, 1+len("B2B Email Reply Protocol"))
   # NOT (0, len("..."))
   ```

5. **BatchUpdate processes requests sequentially** — if you insert text then compute ranges for styling, use the document positions AFTER insertion. The simplest pattern: compute all heading ranges from your source string first, then build a single batchUpdate with delete → insert → N style updates.

6. **Text replacement by position causes cascading corruption** — When doing multiple find/replace operations via batchUpdate (delete + insert at specific indices), each pair shifts ALL subsequent indices by the length difference. This causes later replacements to hit wrong positions, creating mangled text like "Interestpotentialtencial". The SAFE pattern:
   - Read the doc fresh ONCE
   - Search for corrupted text BY CONTENT (not pre-computed positions)
   - Record absolute positions from that single read
   - Sort fixes by position DESCENDING (reverse order)
   - Execute ALL in ONE batchUpdate call
   
   ```python
   def find_in_doc(doc, search_text):
       """Find text by content, return absolute position."""
       for el in doc["body"]["content"]:
           if "paragraph" not in el: continue
           cur = el.get("startIndex", 0)
           for elem in el["paragraph"].get("elements", []):
               tr = elem.get("textRun", {})
               if not tr: cur += 1; continue
               pos = tr.get("content", "").find(search_text)
               if pos >= 0: return cur + pos
               cur += len(tr.get("content", ""))
       return None
   ```

7. **Bullet inserts (`\u2022`) hit text run boundaries** — When inserting bullet characters at paragraph start indices, the insert can land mid-text-run if the paragraph contains formatting changes. Always verify by checking that the character AFTER your insert position is a space or newline, not a letter. If bullets end up inside words (e.g., "St•ep•s"), delete the stray bullets by finding them as content rather than by index.

8. **Empty paragraphs**: Sending `"\n"` as an insertText creates an empty paragraph. This is fine for spacing but be aware that each newline creates a separate paragraph element.

### Service Account — Docs: Structured Write Pattern

To write a full document from scratch (e.g., transferring content from a DOCX):

```python
# 1. Read current doc for end index
doc = docs.documents().get(documentId=DOC_ID).execute()
last = doc["body"]["content"][-1]["endIndex"]

# 2. Build your content as (text, style_or_None) tuples
parts = [
    ("My Title", "H1"),
    ("Intro paragraph.", None),
    ("\u2022 Bullet point", None),
]

# 3. Compute heading ranges with offset=1
STYLE_MAP = {"H1": "HEADING_1", "H2": "HEADING_2", "H3": "HEADING_3"}
full_text = ""
heading_ranges = []
offset = 1
for text, style in parts:
    line = (text or "") + "\n"
    if style:
        heading_ranges.append((offset, offset + len(text), STYLE_MAP[style]))
    full_text += line
    offset += len(line)

# 4. Single batchUpdate: delete old → insert new → apply styles
requests = [
    {"deleteContentRange": {"range": {"startIndex": 1, "endIndex": last - 1}}},
    {"insertText": {"location": {"index": 1}, "text": full_text}},
]
for s, e, style in heading_ranges:
    requests.append({"updateParagraphStyle": {
        "range": {"startIndex": s, "endIndex": e},
        "paragraphStyle": {"namedStyleType": style},
        "fields": "namedStyleType",
    }})

docs.documents().batchUpdate(documentId=DOC_ID, body={"requests": requests}).execute()
```

See `references/docs-batchupdate-api-notes.md` for the full reference.

### Service Account — Sheets examples

```python
# Read values
values = sheets.spreadsheets().values().get(spreadsheetId=SHEET_ID, range="Sheet1!A1:D10").execute()

# Update values
sheets.spreadsheets().values().update(
    spreadsheetId=SHEET_ID, valueInputOption="USER_ENTERED",
    body={"values": [["Name", "Score"], ["Alice", "95"]]},
    range="Sheet1!A1:B2",
).execute()
```

## First-Time Setup (OAuth2 Desktop Mode)

The setup is fully non-interactive — you drive it step by step so it works
on CLI, Telegram, Discord, or any platform.

Define a shorthand first:

```bash
GSETUP="python ${HERMES_HOME:-$HOME/.hermes}/skills/productivity/google-workspace/scripts/setup.py"
```

### Step 0: Check if already set up

```bash
$GSETUP --check
```

If it prints `AUTHENTICATED`, skip to Usage — setup is already done.

### Step 1: Triage — ask the user what they need

Before starting OAuth setup, ask the user TWO questions:

**Question 1: "What Google services do you need? Just email, or also
Calendar/Drive/Sheets/Docs?"**

- **Email only** → They don't need this skill at all. Use the `himalaya` skill
  instead — it works with a Gmail App Password (Settings → Security → App
  Passwords) and takes 2 minutes to set up. No Google Cloud project needed.
  Load the himalaya skill and follow its setup instructions.

- **Email + Calendar** → Continue with this skill, but use
  `--services email,calendar` during auth so the consent screen only asks for
  the scopes they actually need.

- **Calendar/Drive/Sheets/Docs only** → Continue with this skill and use a
  narrower `--services` set like `calendar,drive,sheets,docs`.

- **Full Workspace access** → Continue with this skill and use the default
  `all` service set.

**Question 2: "Does your Google account use Advanced Protection (hardware
security keys required to sign in)? If you're not sure, you probably don't
— it's something you would have explicitly enrolled in."**

- **No / Not sure** → Normal setup. Continue below.
- **Yes** → Their Workspace admin must add the OAuth client ID to the org's
  allowed apps list before Step 4 will work. Let them know upfront.

### Step 2: Create OAuth credentials (one-time, ~5 minutes)

Tell the user:

> You need a Google Cloud OAuth client. This is a one-time setup:
>
> 1. Create or select a project:
>    https://console.cloud.google.com/projectselector2/home/dashboard
> 2. Enable the required APIs from the API Library:
>    https://console.cloud.google.com/apis/library
>    Enable: Gmail API, Google Calendar API, Google Drive API,
>    Google Sheets API, Google Docs API, People API
> 3. Create the OAuth client here:
>    https://console.cloud.google.com/apis/credentials
>    Credentials → Create Credentials → OAuth 2.0 Client ID
> 4. Application type: "Desktop app" → Create
> 5. If the app is still in Testing, add the user's Google account as a test user here:
>    https://console.cloud.google.com/auth/audience
>    Audience → Test users → Add users
> 6. Download the JSON file and tell me the file path
>
> Important Hermes CLI note: if the file path starts with `/`, do NOT send only the bare path as its own message in the CLI, because it can be mistaken for a slash command. Send it in a sentence instead, like:
> `The JSON file path is: /home/user/Downloads/client_secret_....json`

Once they provide the path:

```bash
$GSETUP --client-secret /path/to/client_secret.json
```

If they paste the raw client ID / client secret values instead of a file path,
write a valid Desktop OAuth JSON file for them yourself, save it somewhere
explicit (for example `~/Downloads/hermes-google-client-secret.json`), then run
`--client-secret` against that file.

### Step 3: Get authorization URL

Use the service set chosen in Step 1. Examples:

```bash
$GSETUP --auth-url --services email,calendar --format json
$GSETUP --auth-url --services calendar,drive,sheets,docs --format json
$GSETUP --auth-url --services all --format json
```

This returns JSON with an `auth_url` field and also saves the exact URL to
`~/.hermes/google_oauth_last_url.txt`.

Agent rules for this step:
- Extract the `auth_url` field and send that exact URL to the user as a single line.
- Tell the user that the browser will likely fail on `http://localhost:1` after approval, and that this is expected.
- Tell them to copy the ENTIRE redirected URL from the browser address bar.
- If the user gets `Error 403: access_denied`, send them directly to `https://console.cloud.google.com/auth/audience` to add themselves as a test user.

### Step 4: Exchange the code

The user will paste back either a URL like `http://localhost:1/?code=4/0A...&scope=...`
or just the code string. Either works. The `--auth-url` step stores a temporary
pending OAuth session locally so `--auth-code` can complete the PKCE exchange
later, even on headless systems:

```bash
$GSETUP --auth-code "THE_URL_OR_CODE_THE_USER_PASTED" --format json
```

If `--auth-code` fails because the code expired, was already used, or came from
an older browser tab, it now returns a fresh `fresh_auth_url`. In that case,
immediately send the new URL to the user and have them retry with the newest
browser redirect only.

### Step 5: Verify

```bash
$GSETUP --check
```

Should print `AUTHENTICATED`. Setup is complete — token refreshes automatically from now on.

### Notes

- Token is stored at `~/.hermes/google_token.json` and auto-refreshes.
- Pending OAuth session state/verifier are stored temporarily at `~/.hermes/google_oauth_pending.json` until exchange completes.
- If `gws` is installed, `google_api.py` points it at the same `~/.hermes/google_token.json` credentials file. Users do not need to run a separate `gws auth login` flow.
- To revoke: `$GSETUP --revoke`

## Usage

All commands go through the API script. Set `GAPI` as a shorthand:

```bash
GAPI="python ${HERMES_HOME:-$HOME/.hermes}/skills/productivity/google-workspace/scripts/google_api.py"
```

### Gmail

```bash
# Search (returns JSON array with id, from, subject, date, snippet)
$GAPI gmail search "is:unread" --max 10
$GAPI gmail search "from:boss@company.com newer_than:1d"
$GAPI gmail search "has:attachment filename:pdf newer_than:7d"

# Read full message (returns JSON with body text)
$GAPI gmail get MESSAGE_ID

# Send
$GAPI gmail send --to user@example.com --subject "Hello" --body "Message text"
$GAPI gmail send --to user@example.com --subject "Report" --body "<h1>Q4</h1><p>Details...</p>" --html
$GAPI gmail send --to user@example.com --subject "Hello" --from '"Research Agent" <user@example.com>' --body "Message text"

# Reply (automatically threads and sets In-Reply-To)
$GAPI gmail reply MESSAGE_ID --body "Thanks, that works for me."
$GAPI gmail reply MESSAGE_ID --from '"Support Bot" <user@example.com>' --body "Thanks"

# Labels
$GAPI gmail labels
$GAPI gmail modify MESSAGE_ID --add-labels LABEL_ID
$GAPI gmail modify MESSAGE_ID --remove-labels UNREAD
```

### Calendar

```bash
# List events (defaults to next 7 days)
$GAPI calendar list
$GAPI calendar list --start 2026-03-01T00:00:00Z --end 2026-03-07T23:59:59Z

# Create event (ISO 8601 with timezone required)
$GAPI calendar create --summary "Team Standup" --start 2026-03-01T10:00:00-06:00 --end 2026-03-01T10:30:00-06:00
$GAPI calendar create --summary "Lunch" --start 2026-03-01T12:00:00Z --end 2026-03-01T13:00:00Z --location "Cafe"
$GAPI calendar create --summary "Review" --start 2026-03-01T14:00:00Z --end 2026-03-01T15:00:00Z --attendees "alice@co.com,bob@co.com"

# Delete event
$GAPI calendar delete EVENT_ID
```

### Drive

```bash
# Search existing files
$GAPI drive search "quarterly report" --max 10
$GAPI drive search "mimeType='application/pdf'" --raw-query --max 5

# Get metadata for a single file
$GAPI drive get FILE_ID

# Upload a local file (auto-detects MIME type)
$GAPI drive upload /path/to/report.pdf
$GAPI drive upload /path/to/image.png --name "Logo.png" --parent FOLDER_ID

# Download (binary files download as-is; Google-native files export to a
# sensible default — Docs→pdf, Sheets→csv, Slides→pdf, Drawings→png)
$GAPI drive download FILE_ID
$GAPI drive download DOC_ID --output ~/doc.pdf
$GAPI drive download DOC_ID --export-mime text/plain --output ~/doc.txt

# Create a folder
$GAPI drive create-folder "Reports"
$GAPI drive create-folder "Q4" --parent FOLDER_ID

# Share
$GAPI drive share FILE_ID --email alice@example.com --role reader
$GAPI drive share FILE_ID --email alice@example.com --role writer --notify
$GAPI drive share FILE_ID --type anyone --role reader        # anyone with link
$GAPI drive share FILE_ID --type domain --domain example.com --role reader

# Delete — defaults to trash (reversible). Use --permanent to skip the trash.
$GAPI drive delete FILE_ID
$GAPI drive delete FILE_ID --permanent
```

### Contacts

```bash
$GAPI contacts list --max 20
```

### Sheets

```bash
# Create a new spreadsheet
$GAPI sheets create --title "Q4 Budget"
$GAPI sheets create --title "Inventory" --sheet-name "Stock"

# Read
$GAPI sheets get SHEET_ID "Sheet1!A1:D10"

# Write
$GAPI sheets update SHEET_ID "Sheet1!A1:B2" --values '[["Name","Score"],["Alice","95"]]'

# Append rows
$GAPI sheets append SHEET_ID "Sheet1!A:C" --values '[["new","row","data"]]'
```

### Docs

```bash
# Read
$GAPI docs get DOC_ID

# Create a new Doc (optionally seeded with body text)
$GAPI docs create --title "Meeting Notes"
$GAPI docs create --title "Draft" --body "First paragraph..."

# Append text to the end of an existing Doc
$GAPI docs append DOC_ID --text "Additional content to append"
```

## Output Format

All commands return JSON. Parse with `jq` or read directly. Key fields:

- **Gmail search**: `[{id, threadId, from, to, subject, date, snippet, labels}]`
- **Gmail get**: `{id, threadId, from, to, subject, date, labels, body}`
- **Gmail send/reply**: `{status: "sent", id, threadId}`
- **Calendar list**: `[{id, summary, start, end, location, description, htmlLink}]`
- **Calendar create**: `{status: "created", id, summary, htmlLink}`
- **Drive search**: `[{id, name, mimeType, modifiedTime, webViewLink}]`
- **Drive get**: `{id, name, mimeType, modifiedTime, size, webViewLink, parents, owners}`
- **Drive upload**: `{status: "uploaded", id, name, mimeType, webViewLink}`
- **Drive download**: `{status: "downloaded", id, name, path, mimeType}`
- **Drive create-folder**: `{status: "created", id, name, webViewLink}`
- **Drive share**: `{status: "shared", permissionId, fileId, role, type}`
- **Drive delete**: `{status: "trashed" | "deleted", fileId, permanent}`
- **Contacts list**: `[{name, emails: [...], phones: [...]}]`
- **Sheets get**: `[[cell, cell, ...], ...]`
- **Sheets create**: `{status: "created", spreadsheetId, title, spreadsheetUrl}`
- **Docs create**: `{status: "created", documentId, title, url}`
- **Docs append**: `{status: "appended", documentId, inserted_at, characters}`

## Rules

1. **Never send email, create/delete calendar events, delete Drive files, share files, or modify Docs/Sheets without confirming with the user first.** Show what will be done (recipients, file IDs, content, share role) and ask for approval. For `drive delete`, prefer the default trash (reversible) over `--permanent`.
2. **Check auth before first use** — run `setup.py --check`. If it fails, guide the user through setup.
3. **Use the Gmail search syntax reference** for complex queries — load it with `skill_view("google-workspace", file_path="references/gmail-search-syntax.md")`.
4. **Calendar times must include timezone** — always use ISO 8601 with offset (e.g., `2026-03-01T10:00:00-06:00`) or UTC (`Z`).
5. **Respect rate limits** — avoid rapid-fire sequential API calls. Batch reads when possible.

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `NOT_AUTHENTICATED` | Run setup Steps 2-5 above |
| `REFRESH_FAILED` | Token revoked or expired — redo Steps 3-5 |
| `HttpError 403: Insufficient Permission` | Missing API scope — `$GSETUP --revoke` then redo Steps 3-5 |
| `AUTHENTICATED (partial)` or "Token missing scopes" | New write capabilities (Drive write/delete, Docs create/edit) require re-authorization. `$GSETUP --revoke` then redo Steps 3-5 to grant the upgraded scopes. |
| `HttpError 403: Access Not Configured` | API not enabled — user needs to enable it in Google Cloud Console |
| `ModuleNotFoundError` | Run `$GSETUP --install-deps` |
| Advanced Protection blocks auth | Workspace admin must allowlist the OAuth client ID |

## Revoking Access

```bash
$GSETUP --revoke
```
