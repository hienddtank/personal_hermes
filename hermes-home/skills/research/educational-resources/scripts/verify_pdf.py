#!/usr/bin/env python3
"""Verify downloaded PDFs are legitimate textbooks, not redirect wrappers or placeholders.

Usage: verify_pdf.py <file.pdf> [<file2.pdf> ...]

Checks:
  - File starts with %PDF header (not HTML)
  - MediaBox page count vs file size sanity
  - First page content for redirect indicators (/S /GoTo)
"""
import sys
import re
import os

def verify_pdf(path):
    errors = []
    warnings = []
    
    try:
        with open(path, 'rb') as f:
            data = f.read(20000)  # Read first 20KB for structural checks
    except Exception as e:
        return [f"CANNOT READ: {e}"]
    
    # Check 1: PDF header
    if not data.startswith(b'%PDF-'):
        html_match = re.search(rb'<html|<!DOCTYPE', data, re.IGNORECASE)
        if html_match:
            errors.append("HTML CONTENT detected — likely a blocked/redirect page")
        else:
            errors.append(f"Invalid PDF header (first 10 bytes: {data[:10]!r})")
    
    # Check 2: MediaBox page count
    all_data = open(path, 'rb').read()
    mediacount = len(re.findall(b'/MediaBox', all_data))
    
    fsize_mb = os.path.getsize(path) / (1024 * 1024)
    
    if mediacount == 0:
        # Could be fully compressed — use file size as proxy
        warnings.append(f"Fully compressed PDF (no raw MediaBox). Size: {fsize_mb:.1f}MB")
        # Full textbooks should be at least ~5MB
        if fsize_mb < 3:
            errors.append(f"Suspiciously small for a textbook ({fsize_mb:.1f}MB)")
    else:
        warnings.append(f"Estimated pages: {mediacount}")
        # Sanity: compressed textbooks are ~15-20KB per page, uncompressed ~3KB/page
        expected_min_kb = mediacount * 3  # rough minimum
        actual_kb = fsize_mb * 1024
        if actual_kb < expected_min_kb * 0.3:
            errors.append(f"Size ({fsize_mb:.1f}MB) too small for {mediacount} pages")
    
    # Check 3: Redirect indicators in first page object
    if b'/S /GoTo' in data or b'"\/S":"GoTo"' in data:
        warnings.append("First page contains GoTo redirect — may be a wrapper")
    
    # Check 4: Empty/zero-size check
    if os.path.getsize(path) < 1024:
        errors.append(f"File too small ({os.path.getsize(path)} bytes)")
    
    result = []
    for w in warnings:
        result.append(f"  ⚠ {w}")
    for e in errors:
        result.append(f"  ✗ {e}")
    
    if not errors and not warnings:
        result.append("  ✓ Looks valid")
    elif not errors:
        result.append("  ✓ Likely OK (with caveats above)")
    
    return result

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: verify_pdf.py <file.pdf> [<file2.pdf> ...]")
        sys.exit(1)
    
    all_ok = True
    for path in sys.argv[1:]:
        print(f"\n{os.path.basename(path)}")
        results = verify_pdf(path)
        for r in results:
            print(r)
        if any(r.startswith('  ✗') for r in results):
            all_ok = False
    
    sys.exit(0 if all_ok else 1)