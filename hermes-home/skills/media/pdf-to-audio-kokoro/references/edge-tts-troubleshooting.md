---
name: troubleshoot-edge-tts-failures
description: Diagnose and fix edge-tts batch conversion issues — massive output files from chunk concatenation bugs, silence gaps, and O(n²) duplication patterns.
category: mlops
---

# Troubleshoot edge-tts Batch Conversion Failures

## Trigger Conditions
- A script processes a large document via edge-tts in batches/chunks and produces an output file
- The output file is unexpectedly massive (e.g., GB-scale for what should be minutes of audio)
- Volume analysis shows consistent audio levels across the entire file duration (not just at start/end)

## Diagnostic Steps

### 1. Check file metadata
```bash
ffprobe -v quiet -show_entries format=size,duration,bit_rate -of default=noprint_wrappers=1 output.mp3
```
Calculate expected size: `duration_hours * bitrate_kbps / 8 * 1024 ≈ estimated_bytes`

### 2. Sample audio at multiple timestamps
```bash
python3 << 'EOF'
import subprocess
def check_silence(filepath, start_sec, duration_sec=30):
    cmd = ['ffmpeg', '-y', '-i', filepath, '-ss', str(start_sec), '-t', str(duration_sec),
           '-af', 'volumedetect', '-f', 'null', '-']
    result = subprocess.run(cmd, capture_output=True, text=True)
    for line in result.stderr.split('\n'):
        if 'max_volume' in line: print(f"  {line.strip()}")
for s in [0, 600, 1200, 3600, 7200]:
    print(f"t={s}s:")
    check_silence('output.mp3', s)
EOF
```

### 3. Interpret results
- **Consistent volume at all timestamps** → audio data is actually present throughout; the file may genuinely be long OR there's a concatenation bug
- **Silence in middle, audio at edges** → normal chunk gaps (may need `silenceremove` filter)
- **Silence everywhere** → TTS failed entirely

### 4. Check source log for clues
```bash
grep -E "chunk|Saving|Saved|Failed|Retrying|edge-tts" /tmp/edge_convert.log | tail -20
```
Look for: chunk count, total chars extracted, retry counts, final saved message size

## Common Bug Patterns

### Concatenation with excessive padding
edge-tts scripts sometimes add a fixed silence gap between each chunk. With 247+ chunks, this becomes significant but not massive. If the file is GB-scale, look for:
- Loop appending to wrong variable (overwriting vs appending)
- Each iteration re-processing all previous chunks (O(n²) duplication)
- Wrong concatenation method creating duplicate streams

### Solution — extract known-good segment
If a smaller reference file exists (e.g., `spiderweb_cap.mp3`):
```bash
ffmpeg -y -i reference.mp3 -ar 48000 -b:a 192k output_clean.mp3
```

### Solution — silence removal (for moderate padding)
```bash
ffmpeg -y -i input.mp3 \
  -af "silenceremove=start_periods=1:start_duration=0.5:start_threshold=-40dB:detection=peak,areverse,\
       silenceremove=start_periods=1:start_duration=0.5:start_threshold=-40dB:detection=peak,areverse" \
  output_clean.mp3
```

## Prevention
- Always check `format.size` and `duration` after TTS batch jobs
- Log the expected duration based on text length (~2 minutes per KB of spoken text)
- If chunks > 100, verify concatenation logic doesn't have O(n²) behavior
- **ALWAYS use explicit voice parameter** in every edge-tts call — don't rely on defaults or previous tests
- **Never mix test scripts and production scripts in the same /tmp directory** — different voices get concatenated

## NEW: Voice Contamination Bug (Discovered 2026-04)

### Symptom
Output file has correct duration but sounds like a DIFFERENT LANGUAGE than expected. For example, an English PDF converted with `en-US-JennyNeural` plays back in Vietnamese via `vi-VN-HoaiMyNeural`.

### Root Cause
Multiple edge-tts scripts ran in the same session using `/tmp/edge_*.mp3` filenames. A test script (e.g., testing different voices) wrote to the same output directory as a production script, and both files got concatenated during the final merge step.

### How to Detect
1. Check all scripts that touched the output directory:
   ```bash
   grep -rl "JennyNeural\|HoaiMyNeural\|en-US\|vi-VN" /tmp/*.py 2>/dev/null
   find /tmp -name "*.mp3" -newer PDF_file 2>/dev/null | head -10
   ```
2. Check the conversion log for which voice was actually used:
   ```bash
   grep "Using voice\|voice:" edge_convert.log
   ```
3. Sample audio at different timestamps — if volume/profile changes mid-file, different voices were concatenated

### Fix
You CANNOT fix this with trimming or filtering. You must re-extract the PDF text and re-run edge-tts with a clean script that:
- Uses ONLY the correct voice (`en-US-JennyNeural` for English)
- Writes temp files to an isolated directory (not `/tmp/`)
- Validates each chunk before concatenation (check file size > 100 bytes, verify duration makes sense)
- Removes all non-ASCII text from PDF extractions before TTS (PDFs may contain encoding artifacts that edge-tts interprets differently depending on the voice model)

### Robust Edge-TTS Script Pattern
```python
#!/usr/bin/env python3
"""Clean PDF-to-audio pipeline with voice safety."""
import asyncio, os, re, glob
from edge_tts import Communicate

VOICE = "en-US-JennyNeural"  # ALWAYS explicit
OUTPUT_DIR = "/workspace/AUDIO"  # Never /tmp/
TEMP_DIR = "/tmp/tts_temp_$$"  # Isolated temp dir

os.makedirs(OUTPUT_DIR, exist_ok=True)

async def convert_chunk(text, chunk_num):
    """Convert one text chunk. Validate before returning."""
    clean = re.sub(r'[^\x00-\x7F]+', ' ', text)  # Remove non-ASCII
    filename = f"{TEMP_DIR}/chunk_{chunk_num:04d}.mp3"
    
    comm = Communicate(clean, VOICE)
    await comm.save(filename)
    
    size = os.path.getsize(filename)
    if size < 100:
        os.remove(filename)
        return None
    return filename

async def main():
    # Extract and clean text from PDF...
    chunks = [clean_text(text[i:i+2500]) for i in range(0, len(clean_text(text)), 2500)]
    
    mp3_files = []
    for chunk_num, chunk in enumerate(chunks):
        result = await convert_chunk(chunk, chunk_num)
        if result: mp3_files.append(result)
    
    # Concatenate with ffmpeg concat demuxer
    list_file = f"{TEMP_DIR}/concat.txt"
    with open(list_file, 'w') as f:
        for mp3 in mp3_files:
            f.write(f"file '{mp3}'\n")
    
    subprocess.run([
        'ffmpeg', '-y', '-f', 'concat', '-safe', '0',
        '-i', list_file, '-ar', '48000', '-b:a', '192k', '-ac', '1',
        f"{OUTPUT_DIR}/output.mp3"
    ])

asyncio.run(main())
```
