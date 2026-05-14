#!/usr/bin/env python3
"""
PDF-to-Audio converter using Kokoro TTS engine with sentence-based chunking.
Better text cleaning than edge-tts pipeline, ~5x faster conversion.
GPU mode by default, auto-fallback to CPU.
"""

import sys
import os
import re
import time
import torch
from pathlib import Path
import PyPDF2
import soundfile as sf
from kokoro import KPipeline


def detect_device():
    """Detect best available device. GPU preferred, fallback to CPU."""
    if torch.cuda.is_available():
        device = "cuda"
        print(f"     GPU detected: {torch.cuda.get_device_name(0)} ({torch.cuda.get_device_properties(0).total_mem / 1024**3:.1f} GB)")
    else:
        device = "cpu"
        print("     No GPU available, using CPU")
    return device


def clean_text(text: str) -> str:
    """Clean extracted PDF text by fixing formatting artifacts."""
    
    # Step 1: Remove copyright lines and Studocu/Download headers first (before collapsing whitespace)
    text = re.sub(r'[Cc]opyright.*?by.*?(?:Press|University)', '', text, flags=re.IGNORECASE)
    text = re.sub(r'(?i)(studocu|lomoarcpds|scan to open).*?(?=\n\n|\Z)', '', text, flags=re.DOTALL)
    text = re.sub(r'(?:[Dd]ownloaded|[Ii]ndividual|ba0mynguy3n).*$', '', text, flags=re.MULTILINE)
    
    # Step 2: Remove page numbers on their own line
    text = re.sub(r'^\s*\d+\s*$', '', text, flags=re.MULTILINE)
    
    # Step 3: Replace hyphenated line breaks (word-split across lines with hyphen)
    text = re.sub(r'(\w)-\s*\n\s*(\w)', r'\1-\2', text)
    
    # Step 4: Collapse ALL whitespace and newlines to single spaces, preserving sentence structure
    # First replace double-newline (paragraph breaks) with a placeholder
    text = re.sub(r'\n{2,}', '\x00PARABREAK\x00', text)
    # Now collapse remaining whitespace/newlines
    text = re.sub(r'[ \t]+', ' ', text)
    # Restore paragraph breaks as double-newline
    text = re.sub(r'\x00PARABREAK\x00', '\n\n', text)
    
    # Step 5: Fix known merge patterns (PDF whitespace artifacts)
    fixes = [
        ('intoseeing', 'into seeing'),
        ('butalso', 'but also'),
        ('pos si ble', 'possible'),
        ('Prince ton', 'Princeton'),
        ('permissions@press . princeton .edu', 'at sign press dot princeton dot edu'),
    ]
    for bad, good in fixes:
        text = re.sub(bad, good, text, flags=re.IGNORECASE)
    
    # Step 6: Remove email addresses  
    text = re.sub(r'\S+@\S+\.\S+', '', text)
    
    # Step 7: Final cleanup - trim each line and remove lines that are just noise
    lines = [line.strip() for line in text.split('\n')]
    cleaned_lines = []
    for line in lines:
        if not line:
            continue
        if len(line) < 30 and re.match(r'^[\s\w\s.,;:!?-]+$', line):
            # Skip very short lines that look like page headers/footers
            if any(kw in line.lower() for kw in ['princeton', 'university press', 'new jersey']):
                continue
        cleaned_lines.append(line)
    
    text = '\n'.join(cleaned_lines)
    text = re.sub(r' +', ' ', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    
    return text.strip()


def extract_text_from_pdf(pdf_path: str) -> str:
    """Extract and clean text from PDF."""
    with open(pdf_path, 'rb') as f:
        reader = PyPDF2.PdfReader(f)
        all_texts = []
        
        for page_num in range(len(reader.pages)):
            text = reader.pages[page_num].extract_text()
            
            # Skip pages that are clearly just titles/blank
            if len(text.strip()) < 50:
                continue
            
            cleaned = clean_text(text)
            all_texts.append(cleaned)
        
        return '\n\n'.join(all_texts)


def split_into_sentences(text: str, max_chars: int = 300) -> list:
    """Split text into sentence-based chunks with configurable max size."""
    # Split on sentence boundaries while preserving the delimiter
    sentences = re.split(r'(?<=[.!?])\s+(?=[A-Z"\'(])', text)
    
    chunks = []
    current_chunk = ""
    
    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue
        
        # If adding this sentence would exceed limit, start new chunk
        if len(current_chunk) + len(sentence) > max_chars and current_chunk:
            chunks.append(current_chunk)
            current_chunk = sentence
        else:
            current_chunk += " " + sentence if current_chunk else sentence
    
    if current_chunk:
        chunks.append(current_chunk)
    
    return chunks


def convert_text_to_audio(text: str, output_path: str, pipe, voice: str = "af_heart", speed: float = 1.0):
    """Convert a text chunk to audio using Kokero.
    
    Args:
        text: Text to convert
        output_path: Path to save WAV file
        pipe: Shared KPipeline instance (reused across chunks for consistent voice)
        voice: Voice to use
        speed: Speech speed multiplier
    """
    # CRITICAL: Remove ALL whitespace artifacts before passing to Kokoro.
    # Kokoro treats \n as a pause marker, causing audible "stops" at PDF line breaks.
    # Replace all whitespace with single spaces for smooth continuous speech.
    text = re.sub(r'\s+', ' ', text).strip()
    for i, (gs, ps, audio) in enumerate(pipe(text, voice=voice, speed=speed)):
        sf.write(output_path, audio, 24000)


def convert_pdf_to_mp3(pdf_path: str, output_dir: str = None, 
                       voice: str = "af_heart", max_chunk_chars: int = 300):
    """Main conversion function."""
    
    # Setup output directory
    if output_dir is None:
        output_dir = "/root/PDF_MP3"
    os.makedirs(output_dir, exist_ok=True)
    
    pdf_name = Path(pdf_path).stem.replace(' ', '_')
    chunk_dir = Path(output_dir) / f"{pdf_name}_chunks"
    os.makedirs(chunk_dir, exist_ok=True)
    
    # Extract text
    print(f"[1/4] Extracting and cleaning text from {Path(pdf_path).name}...")
    raw_text = extract_text_from_pdf(pdf_path)
    total_chars = len(raw_text)
    word_count = len(raw_text.split())
    print(f"     Text length: {total_chars} chars, ~{word_count} words")
    
    # Split into sentence chunks
    print("[2/4] Splitting into sentences...")
    chunks = split_into_sentences(raw_text, max_chars=max_chunk_chars)
    avg_size = sum(len(c) for c in chunks) // max(1, len(chunks))
    print(f"     Created {len(chunks)} sentence-chunks (avg {avg_size} chars/chunk)")
    
    # Convert each chunk to audio
    print("[3/4] Converting to audio with Kokoro...")
    # CRITICAL: Create pipeline ONCE and reuse across all chunks.
    # Creating a new pipeline per chunk resets voice state, causing janky transitions.
    # Auto-detect GPU, fallback to CPU
    device = detect_device()
    print(f"     Loading Kokoro model on {device} (first run downloads ~82MB)...")
    pipe = KPipeline(lang_code="a", device=device)
    
    chunk_files = []
    start_time = time.time()
    
    for i, chunk_text in enumerate(chunks):
        chunk_file = str(chunk_dir / f"chunk_{i:04d}.wav")
        
        # Convert and save as WAV first - pass shared pipeline
        convert_text_to_audio(chunk_text.strip(), chunk_file, pipe=pipe, voice=voice)
        chunk_files.append(chunk_file)
        
        elapsed = time.time() - start_time
        avg_time_per_chunk = elapsed / (i + 1) if i > 0 else 0
        remaining = len(chunks) - i - 1
        eta_minutes = (avg_time_per_chunk * remaining) / 60
        
        print(f"     [{i+1:4d}/{len(chunks):4d}] {os.path.basename(chunk_file)} "
              f"| {avg_time_per_chunk:.1f}s/chunk | ETA: {eta_minutes:.1f} min")
        
        # Flush to disk periodically
        if (i + 1) % 50 == 0:
            import gc; gc.collect()
    
    print(f"[4/4] Merging all {len(chunk_files)} audio files...")

    # Add silence padding between chunks to smooth transitions
    # Kokoro chunks end abruptly - adding 100ms silence prevents pops/cracks
    import subprocess

    padded_dir = chunk_dir / "padded"
    os.makedirs(padded_dir, exist_ok=True)
    padded_files = []

    for i, wf in enumerate(chunk_files):
        padded_wf = str(padded_dir / f"chunk_{i:04d}_padded.wav")
        # Add 100ms of silence at the end of each chunk (except the last one)
        if i < len(chunk_files) - 1:
            result = subprocess.run([
                'ffmpeg', '-y', '-i', wf,
                '-f', 'lavfi', '-i', 'anullsrc=channel_layout=mono:sample_rate=24000:duration=0.1',
                '-filter_complex', '[0:a][1:a]concat=n=2:v=0:a=1[out]',
                '-map', '[out]',
                '-ar', '24000', '-acodec', 'pcm_s16le',
                padded_wf
            ], capture_output=True, text=True)
        else:
            # Last chunk - no trailing silence needed
            result = subprocess.run([
                'ffmpeg', '-y', '-i', wf,
                '-ar', '24000', '-acodec', 'pcm_s16le',
                padded_wf
            ], capture_output=True, text=True)
        padded_files.append(padded_wf)

    # Merge padded WAV files using ffmpeg
    concat_list = chunk_dir / "concat_list.txt"
    with open(concat_list, 'w') as f:
        for wf in padded_files:
            abs_path = os.path.abspath(wf)
            f.write(f"file '{abs_path}'\n")

    # Concatenate WAV files (fast copy mode - no re-encoding)
    merged_wav = Path(output_dir) / f"{pdf_name}_merged.wav"
    result = subprocess.run([
        'ffmpeg', '-y', '-f', 'concat', '-safe', '0',
        '-i', str(concat_list),
        '-c', 'copy',
        str(merged_wav)
    ], capture_output=True, text=True)
    
    if result.returncode != 0:
        # Fallback: try with explicit codec if copy mode fails
        print("     Concat copy failed, trying direct encode...")
        subprocess.run([
            'ffmpeg', '-y', '-f', 'concat', '-safe', '0',
            '-i', str(concat_list),
            '-ar', '24000',
            '-acodec', 'pcm_s16le',
            str(merged_wav)
        ], capture_output=True, text=True)
    
    print(f"     Merged WAV: {os.path.getsize(merged_wav)/1024/1024:.1f} MB")
    
    # Convert to MP3 at 192kbps for reasonable file size
    output_mp3 = Path(output_dir) / f"{pdf_name}.mp3"
    subprocess.run([
        'ffmpeg', '-y', '-i', str(merged_wav),
        '-b:a', '192k',
        '-movflags', '+faststart',
        str(output_mp3)
    ], capture_output=True, text=True)
    
    final_size = os.path.getsize(output_mp3) / 1024 / 1024
    print(f"     Final MP3: {output_mp3.name} ({final_size:.1f} MB)")
    
    # Cleanup temporary files to save space
    print("     Cleaning up temporary files...")
    for wf in chunk_files:
        if os.path.exists(wf):
            os.remove(wf)
    if merged_wav.exists():
        merged_wav.unlink()
    concat_list.unlink()
    
    total_time = time.time() - start_time
    print(f"\n✅ Conversion complete!")
    print(f"   Total conversion: {total_time/60:.1f} minutes")
    print(f"   Avg per chunk: {total_time/(len(chunks)*60):.2f} min")
    print(f"   Output: {output_mp3}")
    return str(output_mp3)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python kokoro_pdf_converter.py <input.pdf> [output_dir]")
        print("\nOptions:")
        print('  --voice VOICE     Kokero voice (default: af_heart, also try am_adam, af_sarah)')
        print('  --max-chunk N      Max chars per chunk (default: 300, smaller = more natural pauses)')
        print("\nExamples:")
        print('  python kokoro_pdf_converter.py book.pdf')
        print('  python kokero_pdf_converter.py book.pdf /tmp/output --voice am_adam')
        sys.exit(1)
    
    pdf_path = sys.argv[1]
    output_dir = None
    
    # Parse optional arguments
    voice = "af_heart"
    max_chunk = 300
    
    i = 2
    while i < len(sys.argv):
        if sys.argv[i] == '--voice' and i+1 < len(sys.argv):
            voice = sys.argv[i+1]
            i += 2
        elif sys.argv[i] == '--max-chunk' and i+1 < len(sys.argv):
            max_chunk = int(sys.argv[i+1])
            i += 2
        elif not output_dir:
            output_dir = sys.argv[i]
            i += 1
        else:
            i += 1
    
    convert_pdf_to_mp3(
        pdf_path, 
        output_dir=output_dir,
        voice=voice,
        max_chunk_chars=max_chunk
    )
