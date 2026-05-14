#!/usr/bin/env python3
"""
Vietnamese Meeting Audio Transcriber
Uses faster-whisper to transcribe MP3/audio files to Vietnamese text.
Supports batch processing, timestamps, and clean output formatting.

Usage:
    # Single file
    python vi-transcribe.py input.mp3

    # Batch (all audio files in a directory)
    python vi-transcribe.py ./meetings/ --batch

    # Save to file instead of printing
    python vi-transcribe.py input.mp3 -o transcript.txt

    # With speaker timestamps (segments)
    python vi-transcribe.py input.mp3 --timestamps

    # Custom model (small = faster, large-v3 = most accurate)
    python vi-transcribe.py input.mp3 --model small   # ~1GB RAM
                               --model medium  # ~5GB RAM, better accuracy
                               --model large-v3        # best quality
"""

import argparse
import os
import sys
from datetime import datetime
from pathlib import Path

try:
    from faster_whisper import WhisperModel
except ImportError:
    print("ERROR: faster-whisper not installed. Run: pip install faster-whisper")
    sys.exit(1)


# Model mapping: name -> (model_size, recommended_device)
SUPPORTED_MODELS = {
    "tiny": ("tiny", "auto"),
    "base": ("base", "auto"),
    "small": ("small", "cpu"),      # CPU is fine for small
    "medium": ("medium", "cpu"),    # ~5GB RAM needed
    "large-v3": ("large-v3", "auto"),  # needs GPU or lots of RAM
}

DEFAULT_MODEL = "medium"  # Good balance of speed and accuracy on CPU


def transcribe_file(filepath, model_size="medium", beam_size=5, language="vi"):
    """Transcribe a single audio file in Vietnamese."""
    filepath = Path(filepath)
    if not filepath.exists():
        print(f"  [ERROR] File not found: {filepath}")
        return None

    # Auto-detect device (CPU vs GPU)
    try:
        import ctranslate2
        gpu_available = True
    except ImportError:
        gpu_available = False

    device = "cuda" if gpu_available else "cpu"
    compute_type = "int8" if device == "cpu" else "float16"

    print(f"  Loading model '{model_size}' on {device}...")
    model = WhisperModel(
        model_size,
        device=device,
        compute_type=compute_type,
        cpu_threads=os.cpu_count() or 4,
        num_workers=1,
    )

    print(f"  Transcribing: {filepath.name}")
    segments, info = model.transcribe(
        str(filepath),
        beam_size=beam_size,
        language=language,
        vad_filter=True,           # Filter silence for cleaner output
        vad_parameters=dict(
            min_silence_duration_ms=500,  # Silence threshold in ms
        ),
    )

    return segments, info


def format_transcript(segments, show_timestamps=False):
    """Format transcript segments into clean Vietnamese text."""
    lines = []
    if show_timestamps:
        for seg in segments:
            start = datetime.fromtimestamp(seg.start).strftime("%H:%M:%S")
            end = datetime.fromtimestamp(seg.end).strftime("%H:%M:%S")
            lines.append(f"[{start} -> {end}] {seg.text.strip()}")
    else:
        for seg in segments:
            lines.append(seg.text.strip())

    return "\n".join(lines)


def get_audio_files(directory, extensions=None):
    """Get all audio files from a directory."""
    if extensions is None:
        extensions = {".mp3", ".wav", ".flac", ".ogg", ".m4a", ".aac"}
    dirpath = Path(directory)
    files = []
    for f in sorted(dirpath.iterdir()):
        if f.is_file() and f.suffix.lower() in extensions:
            files.append(f)
    return files


def main():
    parser = argparse.ArgumentParser(
        description="Vietnamese Meeting Audio Transcriber",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
Examples:
  python vi-transcribe.py meeting.mp3
  python vi-transcribe.py ./recordings/ --batch
  python vi-transcribe.py meeting.mp3 -o output.txt
  python vi-transcribe.py meeting.mp3 --timestamps
  python vi-transcribe.py meeting.mp3 --model large-v3
        """,
    )

    parser.add_argument("input", help="Audio file or directory to process")
    parser.add_argument(
        "-o", "--output", help="Output file (default: print to stdout)",
    )
    parser.add_argument(
        "--timestamps", action="store_true",
        help="Include timestamps [HH:MM:SS -> HH:MM:SS] in output",
    )
    parser.add_argument(
        "--model", default=DEFAULT_MODEL, choices=list(SUPPORTED_MODELS.keys()),
        help=f"Model size (default: {DEFAULT_MODEL})",
    )
    parser.add_argument(
        "--batch", action="store_true",
        help="Process all audio files in the input directory",
    )
    parser.add_argument(
        "--beam-size", type=int, default=5,
        help="Beam search size (higher = more accurate but slower, default: 5)",
    )

    args = parser.parse_args()

    input_path = Path(args.input)

    # Validate model
    if args.model not in SUPPORTED_MODELS:
        print(f"ERROR: Unknown model '{args.model}'. Choose from: {list(SUPPORTED_MODELS.keys())}")
        sys.exit(1)

    model_size, recommended_device = SUPPORTED_MODELS[args.model]

    # Determine files to process
    if args.batch and input_path.is_dir():
        files = get_audio_files(input_path)
        if not files:
            print(f"ERROR: No audio files found in {input_path}")
            sys.exit(1)
        print(f"Found {len(files)} audio file(s) in {input_path}\n")

        # Batch processing with combined output
        all_text = []
        results = []
        for i, f in enumerate(files, 1):
            print(f"\n{'='*60}")
            print(f"[{i}/{len(files)}] Processing: {f.name}")
            print(f"{'='*60}")

            result = transcribe_file(f, model_size, args.beam_size)
            if result is None:
                continue

            segments, info = result
            text = format_transcript(segments, args.timestamps)
            results.append((f.name, text))

            # Summary
            duration_sec = info.duration
            print(f"  ✓ Done ({duration_sec:.1f}s audio)")

        # Output batch results
        if args.output:
            with open(args.output, "w", encoding="utf-8") as out:
                for name, text in results:
                    out.write(f"\n{'─'*50}\n\n")
                    out.write(f"FILE: {name}\n")
                    out.write(f"{'─'*50}\n\n")
                    out.write(text)
            print(f"\nAll results saved to: {args.output}")
        else:
            for name, text in results:
                print(f"\n{'─'*50}")
                print(f"FILE: {name}")
                print(f"{'─'*50}\n")
                print(text)

    elif input_path.is_file():
        # Single file processing
        segments, info = transcribe_file(input_path, model_size, args.beam_size)

        if segments is None:
            sys.exit(1)

        text = format_transcript(segments, args.timestamps)

        if args.output:
            with open(args.output, "w", encoding="utf-8") as out:
                out.write(text)
            print(f"\nSaved to: {args.output}")
        else:
            print(text)

    else:
        print(f"ERROR: '{input_path}' not found.")
        sys.exit(1)


if __name__ == "__main__":
    main()
