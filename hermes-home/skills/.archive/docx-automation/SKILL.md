---
name: docx-automation
description: Programmatic .docx generation and editing with python-docx — create reports, protocols, templates, and structured documents.
---

# docx-automation — Programmatic .docx Generation & Editing with python-docx

## Trigger Conditions
- User asks to create, edit, or automate Word documents (.docx) via script.
- Building reports, protocols, templates, or any structured doc output programmatically.

## Prerequisites
```bash
pip install python-docx -q
```

## Steps

1. **Load document:** `doc = docx.Document('/path/to/file.docx')`
2. **Add content:** Use headings (`level=0` to `9`), paragraphs, tables.
3. **Bullets:** The style name `'List Bullet'` is NOT always available in a loaded document. Check first:

   ```python
   bullet_style = None
   for name in ['List Bullet', 'List Bullet 1', 'ListBullet']:
       if name in [s.name for s in doc.styles]:
           bullet_style = doc.styles[name]
           break
   ```

   If no bullet style exists, use manual bullets:
   ```python
   def add_bullet(text):
       p = doc.add_paragraph()
       p.text = ''
       run = p.add_run('\u2022 ' + text)  # Unicode bullet character
       return p
   ```

4. **Tables:** `doc.add_table(rows=N, cols=M)` then set `table.rows[i].cells[j].text`
5. **Save:** `doc.save('/path/to/output.docx')`

## Pitfalls

- **⚠️ NEVER use `p.paragraph_format.style` to change style.** This does NOT work. Use one of these instead:
  - `doc.add_paragraph(text, style='List Bullet')` — pass style as parameter when creating
  - `p.style = doc.styles['List Bullet']` — assign the style object directly
  Using `paragraph_format.style` silently fails and leaves the paragraph with its default (usually Normal) style.
- **Style inheritance trap:** After calling `doc.add_heading()`, subsequent `doc.add_paragraph()` calls may inherit unexpected styles (e.g., Title). Always use the `style=` parameter explicitly for non-heading paragraphs to avoid this.
- **Timeout on large documents:** python-docx can hang on big files. Add debug prints at each step to identify where it stalls. Use `timeout 30` when testing.
- **Style names vary:** `'List Bullet'` may not exist even in a fresh doc — check available styles first via `[s.name for s in doc.styles]`.
- **Clearing paragraphs:** Loop with `for run in p.runs: run.text = ''; p.clear()` to wipe old content before rewriting.
- **File paths:** On Windows-mounted hosts, the file is at `/host/d/...` or similar — not `/mnt/d/...` or `~`.

## Reference Files
- See `references/docx-style-troubleshooting.md` for known style name quirks and fixes.
