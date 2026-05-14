---
name: email-thread-analysis
description: Complete email analysis workflow — parse .mbox archives (streaming line-by-line, HTML stripping, checkpoint resumption), filter noise, build threads via In-Reply-To/References, detect no-reply patterns, and export to Excel + JSON. Handles large files (2.6GB+).
---

# Email Analysis Workflow

Complete pipeline from .mbox archive to analyzed email threads in Excel.

## Two-Phase Pipeline

1. **Phase 1:** Parse mbox → raw JSON with full body (HTML stripped)
2. **Phase 2:** Filter noise + group into threads → Excel + JSON

## Why Two Phases?

Large mbox files (1GB+) will time out or run out of memory with regex-based splitting. Streaming line-by-line is the only reliable approach.

## Checkpoint Support

Scripts save progress to `.parse_checkpoint.json` every 250 emails. Re-running resumes from where it left off. Clean up with:
```bash
rm .parse_checkpoint.json .phase1_emails.json
```

## Phase 1: Stream Parse MBOX

```python
import json
import re
import os
import html as html_module

MBOX_PATH = "/path/to/file.mbox"
OUTPUT_DIR = "/path/to/output_dir"
CHECKPOINT_FILE = os.path.join(OUTPUT_DIR, ".parse_checkpoint.json")


def strip_html(html_text):
    """Strip HTML tags and decode entities."""
    if not html_text:
        return ""
    text = re.sub(r'<style[^>]*>.*?</style>', '', html_text, flags=re.S | re.I)
    text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.S | re.I)
    text = re.sub(r'<br\s*/?>', '\n', text, flags=re.I)
    text = re.sub(r'</p>', '\n\n', text, flags=re.I)
    text = re.sub(r'<[^>]+>', '', text)
    text = html_module.unescape(text)
    lines = [line.strip() for line in text.splitlines()]
    return ' '.join(line for line in lines if line)[:5000]


def extract_email(address_str):
    """Extract email from 'Name <email>' format."""
    if not address_str:
        return ""
    match = re.search(r'<([^>]*)>', address_str)
    return match.group(1).strip() if match else address_str.strip()


def extract_addresses(header_value):
    """Extract all emails from To/Cc/Bcc header fields."""
    if not header_value:
        return ""
    emails = re.findall(r'<([^>]*)>', header_value)
    if emails:
        return ", ".join(e.strip() for e in emails)
    emails = re.findall(r'[\w\.-]+@[\w\.-]+\.\w+', header_value)
    return ", ".join(emails) if emails else header_value.strip()


def load_checkpoint():
    if os.path.exists(CHECKPOINT_FILE):
        with open(CHECKPOINT_FILE, "r") as f:
            return json.load(f)
    return {"phase": 0, "email_count": 0, "line_pos": 0}


def save_checkpoint(checkpoint):
    with open(CHECKPOINT_FILE, "w") as f:
        json.dump(checkpoint, f)
    print(f"[CHECKPOINT] Phase {checkpoint['phase']}: {checkpoint['email_count']} emails at line {checkpoint['line_pos']}")


def parse_mbox_streaming(mbox_path, output_dir, checkpoint=None):
    if checkpoint is None:
        checkpoint = load_checkpoint()

    if checkpoint["phase"] >= 1 and os.path.exists(checkpoint.get("emails_path", "")):
        # Verify we actually finished parsing - don't skip if file is incomplete
        saved_count = len(json.load(open(checkpoint["emails_path"])))
        if saved_count >= 6000:  # Adjust threshold based on expected email count
            print(f"Skipping Phase 1 ({saved_count} emails already saved)")
            return checkpoint.get("emails_path")
        else:
            print(f"Resuming Phase 1 from {saved_count} saved emails...")

    emails = []
    count = 0
    line_pos = 0
    save_interval = 250  # Smaller interval for better recovery on very large files (30M+ lines)

    with open(mbox_path, "r", encoding="utf-8", errors="replace") as f:
        if checkpoint["line_pos"] > 0:
            print(f"Resuming from line {checkpoint['line_pos']}...")
            for i in range(checkpoint["line_pos"]):
                next(f)
            emails_path = os.path.join(output_dir, ".phase1_emails.json")
            if os.path.exists(emails_path):
                emails = json.load(open(emails_path))
                count = len(emails)

        current_headers = {}
        in_headers = False
        body_lines = []

        for line_num, line in enumerate(f, start=checkpoint["line_pos"]):
            line_pos = line_num + 1

            if line.startswith("From "):
                if current_headers.get("Message-ID"):
                    raw_body = "\n".join(body_lines).strip()
                    current_headers["Body"] = strip_html(raw_body)
                    count += 1
                    emails.append(current_headers)

                if count % save_interval == 0:
                    emails_path = os.path.join(output_dir, ".phase1_emails.json")
                    with open(emails_path, "w") as ef:
                        json.dump(emails, ef)
                    checkpoint = {"phase": 1, "email_count": count, "line_pos": line_pos, "emails_path": emails_path}
                    save_checkpoint(checkpoint)

                current_headers = {}
                in_headers = True
                body_lines = []
                continue

            if in_headers:
                if line.strip() == "":
                    in_headers = False
                    continue
                match = re.match(r'^([A-Za-z][\w-]*):\s*(.*)', line)
                if match:
                    current_headers[match.group(1)] = match.group(2).strip()
                else:
                    if current_headers:
                        last_key = list(current_headers.keys())[-1]
                        current_headers[last_key] += " " + line.strip()
            else:
                body_lines.append(line.rstrip())

        if current_headers.get("Message-ID"):
            current_headers["Body"] = strip_html("\n".join(body_lines).strip())
            count += 1
            emails.append(current_headers)

    emails_path = os.path.join(output_dir, ".phase1_emails.json")
    with open(emails_path, "w") as ef:
        json.dump(emails, ef)

    checkpoint = {"phase": 1, "email_count": count, "line_pos": line_pos, "emails_path": emails_path}
    save_checkpoint(checkpoint)
    print(f"\nTotal parsed: {count}")
    return emails_path
```

## Phase 2: Filter Noise, Thread, Export

### Noise Filtering

```python
# Noise patterns - Google, ads, automated notifications
NOISE_SENDERS_RE = re.compile(
    r"(?i)(noreply|no-reply|notification|newsletter|marketing|ads|"
    r"google|gmail|youtube|android|chromecast|playstore|"
    r"amazon|linkedin|twitter|facebook|instagram|tiktok|"
    r"spotify|apple|icloud|microsoft|outlook|office|"
    r"github|stackoverflow|reddit|medium|"
    r"promo|deals|offers|discount|sale|coupon|"
    r"daily digest|weekly roundup|subscription|"
    r"security-alert|verification|receipt|invoice)"
)

NOISE_DOMAINS = [
    "google.com", "youtube.com", "android.com", "chromecast.com",
    "accounts.google.com", "notifications.github.com",
    "amazon.com", "linkedin.com", "twitter.com", "facebook.com",
    "instagram.com", "tiktok.com", "spotify.com", "apple.com",
    "icloud.com", "microsoft.com", "office365.com", "hotmail.com",
    "outlook.com", "live.com", "msn.com", "yahoo.com",
    "aol.com", "mail.com", "zoho.com", "yandex.com",
    "protonmail.com", "pm.me", "proton.me",
]

NOISE_SUBJECTS_RE = re.compile(
    r"(?i)(your daily|welcome to|unsubscribe|update your|"
    r"security alert|verify your account|password reset|"
    r"new sign-in|login attempt|someone accessed|"
    r"your activity|watch later|recommended for you|"
    r"people also bought|you might like|trending now|"
    r"don't miss out|limited time|exclusive offer|"
    r"confirm your email|verify email|action required|"
    r"forwarded|notification from google|google drive|"
    r"google photos|google maps|google calendar|"
    r"google play|youtube premium|youtube music)"
)


def is_noise(headers):
    """Check if email headers indicate noise."""
    from_addr = extract_email(headers.get("From", "")).lower()
    subject = headers.get("Subject", "").lower()

    for domain in NOISE_DOMAINS:
        if from_addr.endswith(domain):
            return True
    if NOISE_SENDERS_RE.search(from_addr):
        return True
    if NOISE_SUBJECTS_RE.search(subject):
        return True
    return False
```

### Build Real Threads

```python
from collections import defaultdict
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime


def parse_date(date_str):
    try:
        dt = parsedate_to_datetime(date_str)
        if dt.tzinfo:
            dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
        return dt
    except Exception:
        return None


def build_threads(emails):
    """Group by REAL email threads using In-Reply-To / References headers (not subject)."""
    msg_by_id = {}
    for msg in emails:
        mid = msg.get("Message-ID", "").strip("<>")
        if mid:
            msg_by_id[mid] = msg

    thread_roots = defaultdict(list)
    for msg in emails:
        mid = msg.get("Message-ID", "").strip("<>")
        in_reply_to = msg.get("In-Reply-To", "").strip("<>")
        references = msg.get("References", "").strip("<>").split()

        parent_id = None
        if in_reply_to:
            parent_id = in_reply_to.strip("<>")
        elif references:
            parent_id = references[-1].strip("<>")

        if parent_id and parent_id in msg_by_id:
            visited = set()
            current = parent_id
            while current and current in msg_by_id and current not in visited:
                visited.add(current)
                parent = msg_by_id[current].get("In-Reply-To", "").strip("<>")
                if parent:
                    current = parent.strip("<>")
                else:
                    break
            root = current if current else list(visited)[0]
            thread_roots[root].append(msg)
        else:
            thread_roots[mid or id(msg)].append(msg)

    return dict(thread_roots)
```

### Export to Excel

```python
import openpyxl


def build_thread_data(threads):
    """Build thread data with From/To/Cc/Bcc + combined body for LLM categorization."""
    thread_data = []
    for thread_id, msgs in sorted(threads.items(), key=lambda x: len(x[1]), reverse=True):
        if not msgs:
            continue

        dates = []
        participants = set()
        from_addrs, to_addrs, cc_addrs, bcc_addrs = [], [], [], []

        for m in msgs:
            date = parse_date(m.get("Date", ""))
            if date:
                dates.append(date)
            from_e = extract_email(m.get("From", ""))
            to_e = m.get("To", "")
            cc_e = m.get("Cc", "")
            bcc_e = m.get("Bcc", "")

            if from_e:
                participants.add(from_e)
                from_addrs.append(from_e)
            if to_e:
                participants.add(to_e)
                to_addrs.append(extract_addresses(to_e))
            if cc_e:
                participants.add(cc_e)
                cc_addrs.append(extract_addresses(cc_e))
            if bcc_e:
                bcc_addrs.append(extract_addresses(bcc_e))

        first_date = min(dates).isoformat() if dates else ""
        last_date = max(dates).isoformat() if dates else ""

        # Build combined thread body (all messages, chronological)
        all_bodies = []
        sorted_msgs = sorted(msgs, key=lambda x: parse_date(x.get("Date", "")) or datetime.min)
        for m in sorted_msgs:
            from_e = extract_email(m.get("From", ""))
            body = m.get("Body", "").strip()
            if body:
                all_bodies.append(f"[{from_e}]: {body}")

        thread_data.append({
            "thread_id": thread_id,
            "message_count": len(msgs),
            "first_contact_date": first_date,
            "last_contact_date": last_date,
            "from": ", ".join(set(from_addrs)),
            "to": ", ".join(set(to_addrs)),
            "cc": ", ".join(set(cc_addrs)) if cc_addrs else "",
            "bcc": ", ".join(set(bcc_addrs)) if bcc_addrs else "",
            "participants": sorted(participants),
            "subject_preview": msgs[0].get("Subject", ""),
            "thread_body": "\n\n".join(all_bodies) if all_bodies else "",
        })

    return thread_data


def export_excel(thread_data, output_dir):
    """Export threads to Excel with From/To/Cc/Bcc + Thread_Body columns."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Threads"

    headers = [
        "Thread_ID", "Subject", "From", "To", "Cc", "Bcc",
        "Message_Count", "First_Contact_Date", "Last_Contact_Date",
        "Participants", "Thread_Body"
    ]
    for col, h in enumerate(headers, 1):
        ws.cell(row=1, column=col, value=h)

    for row_idx, t in enumerate(thread_data, 2):
        ws.cell(row=row_idx, column=1, value=row_idx - 1)
        ws.cell(row=row_idx, column=2, value=t["subject_preview"][:200])
        ws.cell(row=row_idx, column=3, value=t["from"])
        ws.cell(row=row_idx, column=4, value=t["to"])
        ws.cell(row=row_idx, column=5, value=t["cc"])
        ws.cell(row=row_idx, column=6, value=t["bcc"])
        ws.cell(row=row_idx, column=7, value=t["message_count"])
        ws.cell(row=row_idx, column=8, value=t["first_contact_date"])
        ws.cell(row=row_idx, column=9, value=t["last_contact_date"])
        ws.cell(row=row_idx, column=10, value="; ".join(t["participants"]))
        ws.cell(row=row_idx, column=11, value=t["thread_body"])

    # Auto-width
    for col in ws.columns:
        max_len = 0
        for cell in col:
            try:
                max_len = max(max_len, min(len(str(cell.value)), 500))
            except Exception:
                pass
        ws.column_dimensions[col[0].column_letter].width = min(max_len + 2, 100)

    excel_path = os.path.join(output_dir, "customer_threads.xlsx")
    wb.save(excel_path)
    return excel_path
```

## No-Reply Detection

Sorts messages within each thread by date, counts consecutive messages from campaign sender.

**No-reply rule**: if 2+ consecutive emails come from campaign sender without an external reply in between, the thread is flagged as "no reply".

```python
# Adjust threshold: set to 1 for stricter (any single email without reply = no-reply)
ra_consecutive >= 2
```

## Quick Run

```bash
# Phase 1: Parse mbox (streaming, with checkpoints)
python parse_mbox.py

# Phase 2: Thread analysis (reads .phase1_emails.json)
python parse_mbox_threads_checkpoint.py
```

## Requirements

```bash
pip install openpyxl
```

## Pitfalls & Troubleshooting

### Checkpoint resume skips Phase 1 incorrectly
If the script timed out during Phase 1, `checkpoint["phase"]` is set to 1 even though parsing didn't finish. The script will then skip to Phase 2 with incomplete data. ALWAYS verify saved email count before skipping:
```python
if checkpoint["phase"] >= 1 and os.path.exists(checkpoint.get("emails_path", "")):
    saved_count = len(json.load(open(checkpoint["emails_path"])))
    if saved_count >= EXPECTED_THRESHOLD:  # Adjust based on your mbox size
        return checkpoint.get("emails_path")  # Actually finished
    else:
        print(f"Resuming from {saved_count} emails...")
        # Continue parsing
```

### Timeout cycle math
A 2.6GB mbox with 30M+ lines requires multiple timeout cycles. With 180s timeout:
- Run 1: ~4500 emails (hits timeout)
- Run 2: ~7000 emails (completes Phase 1 + starts Phase 2)
- Total: ~6 minutes across 2-3 cycles
Save checkpoints every 250 emails for granular recovery.

### Clean restart when needed
If checkpoint logic gets confused, wipe and start fresh:
```bash
rm .parse_checkpoint.json .phase1_emails.json
```

### Key Patterns
- **Mbox format:** Messages start with `From ` line. Detect boundaries with this pattern.
- **Streaming is mandatory:** Regex-based splitting fails on files >1GB. Line-by-line only.
- **HTML stripping:** Remove `<style>`, `<script>`, `<br/>`, `</p>` tags; decode HTML entities; collapse whitespace
- **Thread grouping:** Use In-Reply-To / References headers for REAL threading (not subject-based). Walk the reply chain to find the root message.
- **Checkpoint saves:** Every 250 emails save line position + email count so parsing resumes after timeout
- **Body extraction:** Collect ALL body lines between headers and next `From ` line, then strip HTML and cap at 5000 chars per message
- **Address fields:** Extract From/To/Cc/Bcc with proper handling of `Name <email>` format using regex `<([^>]*)>`

## Quick Run

```bash
python3 parse_mbox_threads_checkpoint.py
```

Script supports checkpoints (`.{step}_checkpoint.json`) - if it times out, re-run and it resumes from the last saved phase.

## How It Works (4 Phases)

### Phase 1: Load & Filter Emails
- Reads `.phase1_emails.json` from previous mbox parsing
- Filters out noise domains (Google notifications, social media alerts, etc.)
- Noise domain list in script - add/remove as needed

### Phase 2: Build Real Threads
- Groups emails by In-Reply-To / References headers (NOT subject-based)
- Walks parent chain to find thread root
- Each email belongs to exactly one thread

### Phase 3: Classify & Filter (No-Reply Detection)
- Sorts messages within each thread by date
- Counts consecutive messages from `@realisticasia.com` addresses
- **No-reply rule**: if 2+ consecutive emails come from RealisticAsia without an external reply in between, the thread is flagged as "no reply"
- Strict filter: a thread with ANY gap of 2+ RA emails = no-reply (even if there was a reply earlier)

### Phase 4: Export Excel
- `customer_threads_llm_ready.xlsx` - threads with genuine back-and-forth conversations
- `no_reply_threads.xlsx` - threads where RealisticAsia sent multiple emails but got no response (for manual review)
- Both files include columns: Thread_ID, Subject, From, To, Cc, Bcc, Message_Count, First_Contact_Date, Last_Contact_Date, Participants, Thread_Body

## Customization

**Adjust no-reply threshold**: Edit `ra_consecutive >= 2` in Phase 3 to change the consecutive email count. Set to 1 for stricter (any single RA email without reply = no-reply).

**Adjust noise domains**: Edit `NOISE_DOMAINS` list at top of script.

**Change output columns**: Edit `headers` list and the Excel write loop in Phase 4.

## Troubleshooting

- Timeout mid-process: delete `.{step}_checkpoint.json` to restart that phase, or re-run to resume
- Want to adjust filtering: modify Phase 3 logic, then re-run (it skips Phases 1-2 from checkpoint)
