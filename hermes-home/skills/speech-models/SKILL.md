---
name: speech-models
description: Audio AI models — speech recognition (Whisper), audio generation (AudioCraft), and audio processing workflows. Use for transcription, text-to-speech, music generation, and audio analysis.
---

# Speech & Audio AI Models

Audio AI models for speech recognition, audio generation, and processing.

## Quick Selection Guide

- **Speech-to-Text (transcription)**: Whisper — 99 languages, robust ASR
- **Audio Generation (music/sounds)**: AudioCraft — MusicGen, AudioGen, EnCodec
- **Text-to-Speech (voice)**: Kokoro TTS, Edge TTS (see media skills)

## Whisper — Speech Recognition

OpenAI's multilingual speech recognition model. 99 languages, 680K hours of training data.

### When to use
- Speech-to-text transcription (99 languages)
- Podcast/video transcription
- Meeting notes automation
- Translation to English
- Noisy audio transcription

### Quick start

```bash
pip install -U openai-whisper
# Requires ffmpeg: brew install ffmpeg | sudo apt install ffmpeg
```

```python
import whisper

model = whisper.load_model("turbo")  # Best speed/quality
result = model.transcribe("audio.mp3", language="en")
print(result["text"])
```

### Model sizes

| Model | Params | Speed | VRAM |
|-------|--------|-------|------|
| tiny | 39M | ~32x | ~1 GB |
| base | 74M | ~16x | ~1 GB |
| small | 244M | ~6x | ~2 GB |
| medium | 769M | ~2x | ~5 GB |
| large | 1550M | 1x | ~10 GB |
| turbo | 809M | ~8x | ~6 GB |

**Recommendation**: Use `turbo` for best speed/quality balance.

### Transcription options

```python
# Language specification (faster than auto-detect)
result = model.transcribe("audio.mp3", language="en")

# Translation to English
result = model.transcribe("spanish.mp3", task="translate")

# Initial prompt for technical terms
result = model.transcribe("audio.mp3", initial_prompt="Technical podcast about ML.")

# Word-level timestamps
result = model.transcribe("audio.mp3", word_timestamps=True)
```

### Command line

```bash
whisper audio.mp3 --model turbo --output_format srt
whisper audio.mp3 --language Spanish
whisper audio.mp3 --task translate
```

### Best practices
1. Use `turbo` model for English
2. Specify language — faster than auto-detect
3. Add initial prompt for technical terms
4. Use GPU — 10-20× faster
5. Split long audio into <30 min chunks
6. Use `faster-whisper` for 4× speedup

### Limitations
- May hallucinate or repeat text
- Accuracy degrades on >30 min audio
- No speaker diarization
- Quality varies by accent and noise

## AudioCraft — Audio Generation

Meta's audio generation library: MusicGen (music), AudioGen (sound effects), EnCodec (compression).

### When to use
- AI-generated music from text prompts
- Sound effect generation
- Audio compression/decompression
- Music continuation from audio prompts

### Quick start

```bash
pip install audiocraft
```

```python
from audiocraft.models import MusicGen
import torchaudio

model = MusicGen.get_pretrained("large")
model.set_generation_params(duration=10.0, caption="lo-fi hip hop")
waveforms, token_sequences, _ = model.generate_description(["lo-fi hip hop"])
torchaudio.save("music.mp3", waveforms[0].cpu(), model.sample_rate)
```

### Models

| Model | Size | Use |
|-------|------|-----|
| MusicGen small | 150M | Quick prototyping |
| MusicGen large | 320M | Best quality music |
| MusicGen melody | — | Melody continuation |
| AudioGen large | — | Sound effects |
| EnCodec | — | Audio compression |

### Generation options

```python
model.set_generation_params(
    duration=30.0,           # Length in seconds
    caption="jazz piano",    # Text prompt
    top_k=250,               # Sampling temperature
    temperature=1.0,         # Higher = more creative
)
```

### Best practices
1. Use "large" for best quality
2. Keep durations short (<30s per generation)
3. Combine generations for longer tracks
4. Use melody model for continuation
5. GPU required for reasonable speeds

## Audio Processing Utilities

### FFmpeg for audio

```bash
# Extract audio from video
ffmpeg -i video.mp4 -vn -acodec pcm_s16le audio.wav

# Convert formats
ffmpeg -i input.mp3 -ar 16000 -ac 1 output.wav

# Remove silence
ffmpeg -i input.mp3 -af silencedetect=n=-50dB:d=1 output.mp3
```

### Batch transcription

```python
import whisper
import os

model = whisper.load_model("turbo")
for file in os.listdir("audio"):
    if file.endswith((".mp3", ".wav")):
        result = model.transcribe(f"audio/{file}")
        with open(f"transcripts/{file}.txt", "w") as f:
            f.write(result["text"])
```

## Resources

- **Whisper**: https://github.com/openai/whisper
- **AudioCraft**: https://github.com/facebookresearch/audiocraft
- **faster-whisper**: https://github.com/SYSTRAN/faster-whisper
