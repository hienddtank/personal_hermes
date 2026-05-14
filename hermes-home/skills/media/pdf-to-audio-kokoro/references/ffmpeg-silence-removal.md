---
name: ffmpeg-silence-removal
description: Remove silence from audio files using FFmpeg. Critical gotcha - silenceremove filter uses RAW SAMPLE THRESHOLDS (0 to 32767 for 16-bit), NOT dB values. The -dB suffix is silently ignored causing total audio loss.
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux]
---

# FFmpeg Silence Removal Skill

## Critical Gotcha: Threshold Values Use RAW SAMPLES, Not dB!

FFmpeg's silenceremove filter ignores the -dB suffix silently. If you write start_threshold=-30dB, it is parsed as 0 (exact silence only), causing the entire audio to be removed.

**Always use raw sample values for threshold:**
- For 16-bit audio: range is 0 to 32767
- -48dB = approx 5
- -24dB = approx 92  
- -12dB = approx 369
- -6dB = approx 737

## Detecting Silence First (Always!)

Before removing, analyze what you are dealing with:

```bash
# Check average/max volume to understand audio characteristics
ffmpeg -i input.mp3 -af volumedetect -f null - 2>&1 | grep -E "mean_volume|max_volume"

# Find silence periods and their durations
ffmpeg -i input.mp3 -af silencedetect=noise=-1dB:d=0.5 -f null - 2>&1 | grep -E "silence_start|silence_end|silence_duration"
```

## Low-Volume Speech (Mean < -15dB)

When speech is very quiet (common with some TTS engines):
- Standard silenceremove thresholds will not work because all speech falls below any practical threshold
- Solution: Use silencedetect to find silent vs non-silent periods, then extract only the non-silent segments using FFmpeg -ss seeking + concatenation

## Approaches (in order of preference)

### Approach 1: Simple Start/End Trim (when just initial silence needs removal)
```bash
# Skip first N seconds - stream copy is INSTANT (no re-encoding)
ffmpeg -y -ss 400 -i input.mp3 -c:a copy output.mp3

# Or with re-encoding for precise cuts
ffmpeg -y -hide_banner -stats -ss 400 -i input.mp3 -c:a libmp3lame -b:a 64k output.mp3
```

### Approach 2: silenceremove (for removing internal gaps)
```bash
# CRITICAL: use RAW threshold values, NOT dB suffix!
ffmpeg -y -hide_banner \
  -i input.mp3 \
  -af "silenceremover=start_periods=1:start_duration=0.8:start_threshold=5:detection=rms" \
  -c:a libmp3lame -b:a 64k output.mp3

# Or for removing BOTH start and end silence:
ffmpeg -y -hide_banner \
  -i input.mp3 \
  -af "silenceremove=start_periods=1:start_threshold=5:detection=rms:stop_periods=-1:stop_threshold=0" \
  -c:a libmp3lame -b:a 64k output.mp3
```

### Approach 3: Segment Extraction (for many small gaps, low-volume audio)
When silenceremove cannot distinguish speech from silence due to low volume:

1. Use silencedetect=noise=-2dB:d=0.5 to find ALL silent periods
2. Build complement segments (gaps between silences = speech)  
3. Extract each segment with -ss seeking in parallel (use ProcessPoolExecutor or ThreadPoolExecutor)
4. Concatenate via FFmpeg concat demuxer protocol file

## PDF-to-Audio Chunk Merging Pattern

When merging TTS-generated MP3 chunks:
```bash
# 1. List all chunks sorted numerically
ls -1 /path/to/chunks_*.mp3 | sort > concat_list.txt

# 2. Create FFmpeg concat demuxer protocol file
sed "s|^|file '|; s|$|'|" concat_list.txt > concat_protocol.txt

# 3. Merge (uses same codec, just remux - very fast)
ffmpeg -y -f concat -safe 0 -i concat_protocol.txt -c:a copy output.mp3

# For re-encoding to uniform bitrate:
ffmpeg -y -f concat -safe 0 -i concat_protocol.txt -c:a libmp3lame -b:a 64k output.mp3
```

## Common Pitfalls

1. **silenceremove with -dB suffix** silently parses as 0, removes ALL audio
2. **-ss AFTER -i** is slow (decodes everything up to the point). Put -ss BEFORE -i for fast keyframe seeking
3. **Low-volume TTS audio** (~-20dB mean) makes silenceremove unable to distinguish speech from silence; use silencedetect + segment extraction instead
4. **MP3 concat with different codecs/bitrates** requires re-encoding to a common format first, or will get artifacts

## Verification After Trimming
```bash
# Check final duration and size
ffprobe -i output.mp3 -show_entries format=duration -v quiet -of csv=p=0
ls -lh output.mp3

# Verify no silence remains at start/end  
ffmpeg -i output.mp3 -af silencedetect=noise=-1dB:d=2 -f null - 2>&1 | grep silence_start
```