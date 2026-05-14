# Document / PDF Ingestion Pattern

Extend the two-table (long/short conversation) vector memory with a **third table** for external documents. Designed for PDFs, reference materials, knowledge base entries — anything that isn't a chat session.

## Architecture

```
Documents table:
  - doc_table.index    (FAISS binary, 384-dim vectors)
  - meta_documents.json (Entry metadata with rich source info)

Each entry has:
  {
    "id": "...",
    "content": "chunk text up to 500 chars...",
    "metadata": {
      "source_path": "/path/to/file.pdf",     // Original file location
      "doc_name": "calculus_notes.pdf",         // Filename
      "page_number": 42,                        // Page in original doc
      "section_title": "The Fundamental Theorem of Calculus",
      "content_type": "math",                   // Auto-classified: math/general/programming
      "chunk_index": 3,                         // Position within page
      "tags": {"type": "math", "subcategories": ["calculus"]}
    }
  }
```

## Chunking Strategies

### Paragraph-aware (for PDFs) — RECOMMENDED
Break at `\n\n` (paragraph boundaries), not mid-sentence. Better semantic coherence.

```python
def chunk_pdf_page(page_text, page_number, metadata, chunk_size=400, overlap=80):
    paragraphs = [p.strip() for p in page_text.split("\n\n") if p.strip()]
    chunks = []
    current_chunk = ""
    chunk_idx = 0
    
    for para in paragraphs:
        if len(current_chunk) + len(para) > chunk_size and current_chunk:
            chunks.append({"text": current_chunk, "page_number": page_number, "chunk_index": chunk_idx})
            chunk_idx += 1
            # Keep overlap from end
            start = max(0, len(current_chunk) - overlap)
            current_chunk = current_chunk[start:] + "\n\n" + para
        else:
            current_chunk = (current_chunk + "\n\n" + para) if current_chunk else para
    
    if current_chunk.strip():
        chunks.append({"text": current_chunk, "page_number": page_number, "chunk_index": chunk_idx})
    return chunks
```

### Simple character-based (for chat sessions) — existing pattern
250 chars with 50 overlap. Fast, works for short messages. Use for `long_user/assistant/tool` tables.

## Section Title Detection

Heuristic: first meaningful line on a page that is short (<100 chars) and starts with a digit or capital letter. Not bulletproof — many PDFs have inconsistent formatting. For production, use OCR/layout analysis (PyMuPDF's `get_text("dict")` for structured blocks).

```python
def detect_section_title(text):
    lines = text.strip().split("\n")
    for line in lines[:5]:  # Check top 5 lines
        stripped = line.strip()
        if not stripped: continue
        if len(stripped) < 100 and (stripped[0].isdigit() or stripped[0].isupper()):
            return stripped
    return ""
```

## Auto-Classification

Tag documents by scanning first 3 pages for domain keywords. Cheap, no model needed.

```python
def classify_document(pdf_path):
    doc = fitz.open(pdf_path)
    sample = "".join(doc[i].get_text("text") for i in range(min(3, len(doc))))
    doc.close()
    
    tags = {"type": "general"}
    if any(w in sample.lower() for w in ["theorem","proof","integral","derivative","calculus","equation"]):
        tags["type"] = "math"
    if any(w in sample for w in ["def ","function","class ","import "]):
        tags.setdefault("subcategories", []).append("programming")
    
    return tags
```

## Reverse Lookup: Context Expansion

When a search returns a chunk from page X, fetch surrounding pages (X-2 to X+2) for richer context. Use `get_document_context(source_path, anchor_page, page_window)` on the engine.

## Chunk Size Guidance

| Content Type | Chunk Size | Overlap | Rationale |
|-------------|-----------|---------|-----------|
| Chat sessions | 250 chars | 50 | Short messages, fast ingestion |
| PDF pages | 400 chars | 80 | Paragraph breaks preserve semantic units |
| Code files | 600 chars | 100 | Functions/procedures need more context |
| Documentation | 350 chars | 70 | API docs are dense but self-contained |

## Known Pitfalls & Fixes

### `search_documents()` metadata flattening API inconsistency ⚠️
The `engine.search_documents()` method returns results with **flattened metadata fields** at the top level (`doc_name`, `page_number`, `section_title`, `content_type`, etc.) and sets `metadata: None`. It does NOT include a nested `metadata` dict like the two-table system does.

```python
# search_documents() returns:
{"score": 0.54, "doc_name": "calculus.pdf", "page_number": 2, "content": "..."}

# NOT this (like long/short tables):
{"score": 0.54, "metadata": {"doc_name": "calculus.pdf", ...}, "content": "..."}
```

**Bug symptom**: Using `r.get('metadata', {}).get('doc_name')` returns `None` — shows as "unknown" in output. Fix: read directly from top-level keys (`r['doc_name']`, `r['page_number']`).

### Blank pages crash chunking
PDFs with cover pages or page dividers produce empty text blocks. Always `.strip()` and skip if empty before chunking.

### Table-heavy PDFs don't chunk at \n\n
Table rows don't align with paragraph boundaries — chunking breaks table structure mid-row. For table-heavy docs, use PyMuPDF's `get_text("dict")` for structured block detection before chunking.

## Integration with Existing Engine

The document table integrates cleanly with the existing two-table system:
- Same FAISS index type (`IndexFlatIP`, 384-dim)
- Same embedding model (`sentence-transformers/all-MiniLM-L6-v2`)
- Same dedup mechanism (MD5 hash of content + unique identifier)
- Search joins all three tables, results sorted by score
- Metadata carries enough context to display "which doc, which page"

See `/workspace/embedding_engine/` for the live implementation.