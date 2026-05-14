---
name: docx-python
description: Working with Word documents (.docx) in Python — reading, writing, template filling with python-docx and docxtpl.
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [docx, word, document-generation, python, xml]
---

# Working with Word Documents (.docx) in Python

## Key Insight: .docx is a ZIP Archive
A `.docx` file is actually a ZIP archive containing XML files. The main content lives in `word/document.xml`. This means you can read/write it three ways depending on your needs.

### Method 1: python-docx (for reading/manipulating text)
```python
from docx import Document as DocxDocument
doc = DocxDocument('file.docx')
for para in doc.paragraphs:
    print(para.text)

# Writing — create a new document
doc.add_paragraph("Hello " + "{{name}}")  # Use string concat, not f-strings!
doc.save('output.docx')
```
**Best for:** Reading content, modifying individual runs/paragraphs, creating new documents. Does NOT support template variable filling.

### Method 2: zipfile + raw XML (for pattern matching/search)
```python
import zipfile
with zipfile.ZipFile('file.docx') as zf:
    xml = zf.read('word/document.xml').decode('utf-8')

# Search for patterns in the XML directly
if '{{client_name}}' in xml:
    print("Found placeholder")
```
**Best for:** Finding patterns, bulk replacements, injecting markers. Use this when you need to scan or modify template structure.

### Method 3: docxtpl (for template filling)
```python
from docxtpl import DocxTemplate
doc = DocxTemplate('template.docx')
context = {"name": "John", "items": [...]}
doc.render(context)  # Fills {{variables}} and {% for %} loops
doc.save('output.docx')
```
**Best for:** Replacing `{{placeholders}}` with data values. Supports Jinja2 templating (loops, conditionals, filters).

## Common Pitfalls

### Never Use `p.paragraph_format.style`
`p.paragraph_format.style` silently fails and leaves the paragraph with its default (usually Normal) style. **Always use one of these instead:**
- `doc.add_paragraph(text, style='List Bullet')` — pass style as parameter when creating
- `p.style = doc.styles['List Bullet']` — assign the style object directly

### Style Inheritance After `add_heading()`
After calling `doc.add_heading()`, subsequent `doc.add_paragraph()` calls may inherit unexpected styles (e.g., Title). Always use the `style=` parameter explicitly for non-heading paragraphs.

### HTML Entity Encoding in docx XML
When reading `document.xml`, comment markers like `<!-- -->` may appear as:
```
&lt;!--AI:name--&gt;  instead of <!--AI:name-->
```
**Fix:** Always normalize before regex matching:
```python
normalized = raw_xml.replace('&lt;', '<').replace('&gt;', '>')
pattern = r'<!--\s*AI:\s*(\w+)\s*-->'
matches = re.findall(pattern, normalized, re.DOTALL)
```

### Double-Brace Confusion with Python f-strings
When creating test templates programmatically, `{{ }}` in Python becomes `{ }` if used inside an f-string:
```python
# WRONG — f-string eats the braces
f"Dear {{client_name}}"  # → "Dear {client_name}"

# RIGHT — use string concatenation or .format()
"Dear " + "{{client_name}}"
doc.add_paragraph("Date: " + "{{report_date}}")
```

### AI Section Markers Must Be in Separate Paragraphs
For reliable detection, `<!--AI:name-->` and `<!--END_AI:name-->` should each be their own paragraph element. Mixing them with other text makes regex matching fragile:
```python
# GOOD — separate paragraphs for markers
ai_start = doc.add_paragraph()  # empty or just the marker
ai_start.text = '<!--AI:section_name-->'

content_para = doc.add_paragraph('Some context text here')

ai_end = doc.add_paragraph()  # empty or just the marker
ai_end.text = '<!--END_AI:section_name-->'
```

## Recommended Approach for Document Generation Tools

When building a tool that fills templates with AI-generated content:
1. **Read template XML** via zipfile to find patterns/markers (fast, reliable)
2. **Use docxtpl** to render `{{variables}}` and `{%for%}` loops (battle-tested Jinja2 engine)
3. **Post-process** with python-docx for any content that needs injection after rendering

## Pitfalls When Modifying Existing Documents

### Bullet Style Lookup Fails Silently
`doc.styles['List Bullet']` throws `KeyError` if the document was created without that style (common with hand-written or imported .docx files).

**Fix:** Check available styles first, fallback to manual bullet:
```python
# Try style lookup
try:
    bullet_style = doc.styles['List Bullet']
except KeyError:
    bullet_style = None

# Use it safely
for item in items:
    if bullet_style:
        p = doc.add_paragraph(item)
        p.style = bullet_style
    else:
        p = doc.add_paragraph()  # manual bullet char
        p.add_run('\u2022 ' + item)
```

### Table Has Fewer Rows Than Needed
When updating a reference table with more items than existing rows, `table.rows[i]` throws `IndexError`.

**Fix:** Dynamically add rows via deepcopy before filling:
```python
from copy import deepcopy

while len(table.rows) < needed_count:
    new_row = deepcopy(table._tbl[-1])  # clone last row structure
    table._tbl.append(new_row)

# Now safely fill all rows
for i, (val, desc) in enumerate(data):
    table.rows[i].cells[0].text = val
    table.rows[i].cells[1].text = desc
```

### Clearing Paragraph Content Requires Cleaning Runs First
Calling `p.clear()` on a paragraph with multiple runs can leave orphaned XML. Always clear runs first:
```python
for run in p.runs:
    run.text = ''  # clear text but keep the run object
p.clear()         # now safe to remove element
```

### Timeout / Hang on Save
Large documents or complex formatting can make `doc.save()` take a long time or hang silently.

**Debug approach:** Add print statements at each step before saving. If it stops mid-way, you know which operation caused the issue. Use `timeout` in terminal calls when testing scripts:
```python
print("1: imported")
doc = docx.Document(path)
print("2: loaded")
# ... add content with print markers ...
print("DONE - saved successfully")
doc.save(output_path)
```

### Inserting Paragraphs at Specific Positions Creates Messy Ordering
Using `addprevious()` to reorder paragraphs after creation results in scrambled order and duplicates. This approach is fragile — XML reordering is unpredictable.

**Fix: Rebuild from scratch instead of surgical insert.** Read all existing content, create a fresh document, and write everything in the correct order:
```python
import docx

doc = docx.Document(original_path)
new_doc = docx.Document()

def copy_para(p):
    # Skip duplicate headings that will be added manually once
    if p.style and 'Heading' in p.style.name:
        if p.text == 'Partner': return None       # add it once
        if p.text == 'First Reply from Agency...': return None  # add it once
    new_p = new_doc.add_paragraph(style=p.style.name)
    for run in p.runs:
        nr = new_p.add_run(run.text)
        nr.bold = run.bold
        nr.italic = run.italic
        if run.font.size: nr.font.size = run.font.size
    return new_p

# Step 1: Copy sections that stay unchanged
for i in range(8): copy_para(doc.paragraphs[i])

# Step 2: Insert new content at the desired position
new_doc.add_paragraph('New Section', style='Heading 4')
new_doc.add_paragraph('Bullet item', style='List Bullet')

# Step 3: Copy remaining sections, filtering duplicates
for i in range(old_start_of_next_section, len(doc.paragraphs)):
    p = doc.paragraphs[i]
    if p.style and 'Heading' in (p.style.name if p.style else ''):
        # Handle headings that will be added manually
        if p.text == 'NextSection': continue  # add it below
    elif p.style and 'Heading' in p.style.name and p.text == 'Partner':
        continue  # skip duplicate
    copy_para(p)

new_doc.save(final_path)
```

**Key patterns for filtering during rebuild:**
- Filter duplicates by **heading text content**, not just position (source docs may have accidental duplicate headings from previous edits).
- Use `copy_para()` helper that preserves run-level formatting (bold, italic, font size) — don't just copy `.text`, because style-only changes (e.g. a paragraph changed from Normal to Heading 4) won't survive if you only read text+style_name.
- When inserting new content mid-document, write it between two loop ranges rather than trying to splice into an existing document object.

### Bullet Paragraphs Don't Show • in Terminal Print Output
python-docx stores bullet formatting at the XML level (in paragraph properties), NOT as a literal `•` character in the text. When you `print(para.text)` to debug, bullets will appear as plain text with no marker — but the document renders correctly in Word/Google Docs.

**This is only a debugging illusion.** Do not add manual `•` characters unless the style is truly missing (see "Bullet Style Lookup Fails Silently" above).

## Writing to Protected Paths
When the target path may have permission issues (e.g., `/host/d/...` on Windows-mounted drives), write to `/tmp/first` then copy:
```python
doc.save('/tmp/output.docx')  # always succeeds
import shutil
shutil.copy('/tmp/output.docx', '/host/d/path/to/final.docx')  # handles permission layer
```

## Testing Strategy
Always verify:
- Double braces `{{ }}` survived creation (not consumed by Python f-strings)
- AI markers appear in raw XML as expected (check with zipfile + regex search)
- All placeholders are filled in output (search for remaining `{{...}}`)
- Table dimensions match expected count (add rows dynamically if needed)
- Bullet styles exist or use fallback character (`\u2022`)

## Session Blueprints & References

### B2B Email Reply Protocol Structure
`references/b2b-email-reply-protocol.md` — template structure for building BD tracking protocols in .docx. Includes field design decisions (date format, dropdown states, CRM status mapping) and Python implementation patterns. Use as a starting point when creating business process documents for the user.