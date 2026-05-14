"""
PDF Ingestion Template — copy and modify for your use case.
Extends EmbeddingEngine with document table support.

Usage:
  python ingest_pdfs.py --dirs /path/to/pdfs1 /path/to/pdfs2
  python ingest_pdfs.py --clear-doc-table --dirs /custom/path
  
Requires: pip install PyMuPDF (fitz)
"""

import sys
import os
from pathlib import Path

# Add engine to path
sys.path.insert(0, str(Path(__file__).parent))
from engine import EmbeddingEngine

import fitz  # PyMuPDF


# ── Config — customize these for your use case ────────────────────────

CHUNK_SIZE = 400        # Characters per chunk (larger than chat's 250)
OVERLAP = 80            # Overlap between chunks for continuity
SAMPLE_PAGES_FOR_CLASSIFY = 3  # Pages to scan for auto-tagging


# ── PDF Text Extraction ───────────────────────────────────────────────

def extract_pdf_pages(pdf_path: str) -> list[dict]:
    """Extract text from a PDF, returning list of page dicts.
    
    Each dict has: page_number (1-indexed), section_title, content.
    """
    doc = fitz.open(pdf_path)
    pages = []
    
    for page_num in range(len(doc)):
        page = doc[page_num]
        text = page.get_text("text").strip()
        section = detect_section_title(text)
        
        if not text:
            continue  # Skip blank pages
        
        pages.append({
            "page_number": page_num + 1,
            "section_title": section,
            "content": text,
        })
    
    doc.close()
    return pages


def detect_section_title(text: str) -> str:
    """Heuristic: first meaningful line that looks like a heading."""
    for line in text.split("\n")[:5]:
        stripped = line.strip()
        if not stripped:
            continue
        if len(stripped) < 100 and (stripped[0].isdigit() or stripped[0].isupper()):
            return stripped
    return ""


# ── Chunking ───────────────────────────────────────────────────────────

def chunk_page(page_text: str, page_number: int, chunk_size: int = CHUNK_SIZE,
               overlap: int = OVERLAP) -> list[dict]:
    """Split page text into chunks at paragraph boundaries."""
    paragraphs = [p.strip() for p in page_text.split("\n\n") if p.strip()]
    
    chunks = []
    current = ""
    idx = 0
    
    for para in paragraphs:
        if len(current) + len(para) > chunk_size and current:
            chunks.append({"text": current, "page_number": page_number, "chunk_index": idx})
            idx += 1
            start = max(0, len(current) - overlap)
            current = current[start:] + "\n\n" + para
        else:
            current = (current + "\n\n" + para) if current else para
    
    if current.strip():
        chunks.append({"text": current, "page_number": page_number, "chunk_index": idx})
    
    return chunks


# ── Classification ─────────────────────────────────────────────────────

def classify_document(pdf_path: str) -> dict:
    """Auto-tag document by scanning first few pages for domain keywords."""
    doc = fitz.open(pdf_path)
    sample = "".join(doc[i].get_text("text") for i in range(min(SAMPLE_PAGES_FOR_CLASSIFY, len(doc))))
    doc.close()
    
    tags = {"type": "general"}
    
    math_keywords = ["theorem", "proof", "integral", "derivative", "calculus",
                     "algebra", "matrix", "lemma", "equation", "∫", "∂", "Σ"]
    if any(kw in sample.lower() for kw in math_keywords):
        tags["type"] = "math"
    
    code_keywords = ["def ", "function", "class ", "import ", "return "]
    if any(kw in sample for kw in code_keywords):
        tags.setdefault("subcategories", []).append("programming")
    
    return tags


# ── Ingestion ──────────────────────────────────────────────────────────

def ingest_pdfs(pdf_dirs: list[str], engine: EmbeddingEngine) -> int:
    """Ingest all PDFs from given directories into the document table.
    
    Returns total number of chunks ingested.
    """
    total_chunks = 0
    
    for pdf_dir in pdf_dirs:
        if not os.path.isdir(pdf_dir):
            print(f"  ⚠ Directory not found: {pdf_dir}")
            continue
        
        for fname in sorted(os.listdir(pdf_dir)):
            if not fname.lower().endswith(".pdf"):
                continue
            
            pdf_path = os.path.join(pdf_dir, fname)
            print(f"\n  Processing: {fname}")
            
            tags = classify_document(pdf_path)
            print(f"    Type: {tags['type']}")
            
            pages = extract_pdf_pages(pdf_path)
            print(f"    Pages: {len(pages)}")
            
            for page in pages:
                chunks = chunk_page(page["content"], page["page_number"])
                
                for chunk in chunks:
                    metadata = {
                        "source_path": pdf_path,
                        "doc_name": fname,
                        "page_number": chunk["page_number"],
                        "chunk_index": chunk["chunk_index"],
                        "section_title": page.get("section_title"),
                        "content_type": tags["type"],
                        "tags": tags,
                    }
                    engine.add_document(chunk["text"], metadata)
                    total_chunks += 1
            
            print(f"    Chunks: {len(chunks)}")
    
    return total_chunks


# ── CLI ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Ingest PDFs into embedding engine")
    parser.add_argument("--dirs", nargs="+", required=True, help="PDF directories")
    parser.add_argument("--clear-doc-table", action="store_true",
                        help="Clear document table before ingesting")
    args = parser.parse_args()
    
    engine = EmbeddingEngine()
    if args.clear_doc_table:
        print("Clearing document table...")
        engine.clear_doc()
    
    chunks = ingest_pdfs(args.dirs, engine)
    print(f"\n✅ Ingested {chunks} chunks from all files")
    print(f"Stats: {engine.stats()}")
