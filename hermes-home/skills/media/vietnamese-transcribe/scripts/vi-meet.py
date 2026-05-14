#!/usr/bin/env python3
"""
Vietnamese meeting transcriber — pyannote diarization + faster-whisper.

Optimized strategy: transcribe FULL audio once with whisper (1 model call),
then assign each whisper segment to the closest diarization speaker boundary.
This is ~5-10x faster than calling whisper on every tiny segment.

Usage:
    python3 vi-meet.py <audio_file> [-o output.txt] [--model medium|large-v3] [--gap 0.4]
    python3 vi-meet.py <audio_file> --no-diarize   # raw transcript, faster (~57s for 34s audio)

Output format: speaker-labeled transcript with timestamps, overlapping speech preserved.

Performance (CPU-only, ~34s Vietnamese audio):
    Full pipeline (diarize + large-v3 int8 @ 4 threads): ~87s total
    Raw only (--no-diarize + large-v3 int8): ~57s total
"""
import sys, os, argparse, numpy as np, subprocess


def load_audio_np(path):
    r = subprocess.run(
        ["ffmpeg", "-i", path, "-f", "f32le", "-ac", "1", "-ar", "16000", "-"],
        capture_output=True, check=True,
    )
    return np.frombuffer(r.stdout, dtype=np.float32)


def format_ts(s, use_hms=False):
    if not use_hms:
        return f"{s:6.1f}s"
    h = int(s // 3600)
    m = int((s % 3600) // 60)
    sec = s % 60
    return f"{h:02d}:{m:02d}:{sec:05.2f}"


def main():
    parser = argparse.ArgumentParser(
        description="Vietnamese meeting transcriber (diarization + faster-whisper)",
    )
    parser.add_argument("audio", help="Audio file (m4a/mp3/wav)")
    parser.add_argument("-o", "--output", default=None, help="Output text file")
    parser.add_argument("--model", default="medium",
                       choices=["base", "small", "medium", "large-v3"],
                       help="Whisper model (default: medium)")
    parser.add_argument("--gap", type=float, default=0.4,
                       help="Max gap (s) to merge same-speaker segments (default: 0.4)")
    parser.add_argument("--timestamps", action="store_true",
                       help="Format timestamps as HH:MM:SS instead of seconds")
    parser.add_argument("--no-diarize", action="store_true",
                       help="Skip diarization — faster, no speaker labels (~57s for 34s audio)")

    args = parser.parse_args()
    if not os.path.exists(args.audio):
        print(f"[!] File not found: {args.audio}")
        sys.exit(1)

    audio = load_audio_np(args.audio)
    sr = 16000
    duration = len(audio) / sr

    print(f"[*] Audio: {duration:.1f}s")

    # ── Step 1: Speaker Diarization (VAD + labels) — optional ──
    if not args.no_diarize:
        from whisperx.diarize import DiarizationPipeline
        print("[*] Running pyannote diarization...")
        pipe = DiarizationPipeline(model_name=None, device="cpu")
        diarize_df = pipe(audio)
        diarize_done = True
    else:
        diarize_done = False

    speaker_ids = sorted(diarize_df['speaker'].unique()) if diarize_done else []
    label_map = {s: chr(65 + i) for i, s in enumerate(speaker_ids)}
    print(f"[+] Speakers: {', '.join(label_map[s] for s in speaker_ids)}")
    print(f"[+] {len(diarize_df)} speech turns detected" if diarize_done else "[*] Diarization skipped — raw transcript only")

    # ── Step 2: Transcribe FULL audio ONCE with whisper ──
    from faster_whisper import WhisperModel
    print(f"[*] Loading faster-whisper ({args.model}) on CPU...")
    fw = WhisperModel(args.model, device="cpu", compute_type="int8",
                      cpu_threads=4,  # sweet spot for whisper on this hardware
                      download_root="/root/.cache/whisper/")

    print("[*] Transcribing full audio (single pass)...")
    segments, info = fw.transcribe(
        audio, language="vi", beam_size=5, vad_filter=False,
    )
    all_whisper = list(segments)
    print(f"[*] Whisper produced {len(all_whisper)} text segments from {info.duration:.0f}s")

    # ── Step 3: Assign whisper segments to speakers (or skip if --no-diarize) ──
    if not diarize_done:
        # No diarization — treat all as single stream
        print("[*] Diarization skipped — outputting raw transcript")
        speaker_results = {'[RAW]': []}
        for ws in all_whisper:
            if ws.text.strip():
                speaker_results['[RAW]'].append({
                    'start': ws.start, 'end': ws.end,
                    'text': ws.text.strip(),
                })

        # ── Step 4/5/6: Print + save raw transcript ──
        print(f"\n{'='*80}")
        print("VIETNAMESE MEETING TRANSCRIPT (raw)")
        print(f"{'='*80}\n")

        cur = None
        for ws in all_whisper:
            if not ws.text.strip():
                continue
            ts_start = format_ts(ws.start, args.timestamps)
            ts_end = format_ts(ws.end, args.timestamps)
            d = ws.end - ws.start
            label = "[RAW]"  # no diarization
            if label != cur:
                print(f"\n--- {label} ---")
                cur = label
            print(f"  [{ts_start} - {ts_end}] ({d:.1f}s) {ws.text.strip()}")

        # Save raw transcript
        if args.output:
            os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(f"VIETNAMESE MEETING TRANSCRIPT (raw)\n")
                f.write(f"Source: {args.audio}\n")
                f.write(f"Duration: {duration:.1f}s\n")
                f.write(f"Model: {args.model} | No diarization\n\n")

                for ws in all_whisper:
                    if not ws.text.strip():
                        continue
                    ts_start = format_ts(ws.start, args.timestamps)
                    ts_end = format_ts(ws.end, args.timestamps)
                    d = ws.end - ws.start
                    f.write(f"[{ts_start} - {ts_end}] ({d:.1f}s) {ws.text.strip()}\n")
            print(f"\n[+] Saved to: {args.output}")
        sys.exit(0)

    # ── DARIIZED MODE ──

    # Assign each whisper segment to the best-matching diarization turn
    print("[*] Mapping whisper segments to speaker labels...")

    diarization_turns = []
    for _, row in diarize_df.iterrows():
        diarization_turns.append({
            'start': float(row['start']),
            'end': float(row['end']),
            'speaker': label_map.get(row['speaker'], '?'),
            'raw_start': float(row['start']),
            'raw_end': float(row['end']),
        })

    # Build per-speaker results from whisper assignments
    speaker_results = {}  # speaker_label -> [(whisper_start, whisper_end, text)]
    for ws in all_whisper:
        ws_start, ws_end = ws.start, ws.end
        if not ws.text.strip():
            continue

        best_overlap = 0.0
        best_turn = diarization_turns[0] if diarization_turns else None

        for turn in diarization_turns:
            t_start, t_end = turn['start'], turn['end']
            # Overlap duration
            overlap_start = max(ws_start, t_start)
            overlap_end = min(ws_end, t_end)
            overlap_dur = max(0.0, overlap_end - overlap_start)

            if best_turn is None:
                best_overlap = 0
                best_turn = turn
                continue

            # Score: how much of the whisper segment falls in this turn
            ws_duration = ws_end - ws_start
            if ws_duration <= 0:
                continue
            coverage = overlap_dur / ws_duration

            # If coverage is same, prefer turns that are closer in time (midpoint)
            if coverage > best_overlap or (coverage == best_overlap and best_turn is not None):
                if coverage > 0.3:  # only accept meaningful overlap
                    best_overlap = coverage
                    best_turn = turn

        speaker_label = best_turn['speaker'] if best_turn else '?'
        if speaker_label not in speaker_results:
            speaker_results[speaker_label] = []
        speaker_results[speaker_label].append({
            'start': ws_start, 'end': ws_end,
            'text': ws.text.strip(),
        })

    # ── Step 4: Reconstruct speaker-labeled transcript ──
    print("[*] Building final transcript...")

    # Merge consecutive whisper segments for same speaker into single lines
    merged = []
    for turn in diarization_turns:
        label = turn['speaker']
        raw_start = turn['raw_start']
        raw_end = turn['raw_end']

        # Find whisper segments that should be attributed to this speaker at this time
        ws_for_turn = []
        for entry in speaker_results.get(label, []):
            # Check if this whisper segment overlaps with the diarization turn
            overlap_s = max(entry['start'], raw_start)
            overlap_e = min(entry['end'], raw_end)
            if overlap_s < overlap_e:
                ws_for_turn.append(entry)

        if ws_for_turn:
            # Merge text from overlapping whisper segments
            texts = [e['text'] for e in ws_for_turn if e['text']]
            merged.append({
                'start': raw_start,
                'end': raw_end,
                'speaker': label,
                'text': " ".join(texts),
            })

    # Merge adjacent same-speaker with small gap
    final = []
    for seg in merged:
        if (final and final[-1]['speaker'] == seg['speaker']
                and (seg['start'] - final[-1]['end']) < args.gap):
            final[-1]['end'] = seg['end']
            final[-1]['text'] += " " + seg['text']
        else:
            final.append(seg)

    # ── Step 5: Print (diarized mode) ──
    print(f"\n{'='*80}")
    print("VIETNAMESE MEETING TRANSCRIPT")
    print(f"{'='*80}\n")

    cur = None
    for seg in final:
        if seg['speaker'] != cur:
            print(f"\n--- {seg['speaker']} ---")
            cur = seg['speaker']
        d = seg['end'] - seg['start']
        ts_start = format_ts(seg['start'], args.timestamps)
        ts_end = format_ts(seg['end'], args.timestamps)
        print(f"  [{ts_start} - {ts_end}] ({d:.1f}s) {seg['text']}")

    # ── Step 6: Save (diarized mode) ──
    if args.output:
        os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
        with open(args.output, "w", encoding="utf-8") as f:
            labels = ', '.join(label_map[s] for s in speaker_ids)
            ts_fmt = "HH:MM:SS" if args.timestamps else "seconds"
            f.write(f"VIETNAMESE MEETING TRANSCRIPT\n")
            f.write(f"Source: {args.audio}\n")
            f.write(f"Duration: {duration:.1f}s\n")
            f.write(f"Speakers: {labels} ({', '.join(speaker_ids)})\n")
            f.write(f"Model: {args.model} | Gaps merged: <{args.gap}s | Timestamps: {ts_fmt}\n\n")

            cur = None
            for seg in final:
                if seg['speaker'] != cur:
                    f.write(f"\n{'='*60}\n{seg['speaker']}\n{'='*60}\n\n")
                    cur = seg['speaker']
                d = seg['end'] - seg['start']
                ts_start = format_ts(seg['start'], args.timestamps)
                ts_end = format_ts(seg['end'], args.timestamps)
                f.write(f"[{ts_start} - {ts_end}] ({d:.1f}s) {seg['text']}\n")
        print(f"\n[+] Saved to: {args.output}")


if __name__ == "__main__":
    main()
