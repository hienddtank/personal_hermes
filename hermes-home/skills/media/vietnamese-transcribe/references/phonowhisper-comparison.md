# PhoWhisper vs Standard Whisper — Vietnamese ASR Comparison

## Background

PhoWhisper (VinAI) is a Whisper model fine-tuned specifically on 844 hours of Vietnamese speech. It was expected to significantly outperform general Whisper for Vietnamese transcription.

## Installation

PhoWhisper uses the `transformers` pipeline, NOT `faster-whisper` (CTranslate2 format). Requires PyTorch:

```bash
pip install transformers accelerate soundfile torch --index-url https://download.pytorch.org/whl/cpu
```

Model sizes: `vinai/PhoWhisper-tiny`, `-base`, `-small`, `-medium` (~1-3GB each)

## Usage Pattern (different from faster-whisper)

PhoWhisper is NOT compatible with `faster-whisper`. Must use `transformers` pipeline directly:

```python
from transformers import AutoProcessor, WhisperForConditionalGeneration
import soundfile as sf

model = WhisperForConditionalGeneration.from_pretrained('vinai/PhoWhisper-medium')
processor = AutoProcessor.from_pretrained('vinai/PhoWhisper-medium')

audio, sr = sf.read(audio_path)  # Must be 16kHz mono WAV
input_features = processor(audio, sampling_rate=16000, return_tensors="pt").input_features

output_ids = model.generate(input_features, language="vietnamese", task="transcribe")
text = processor.batch_decode(output_ids, skip_special_tokens=True)[0]
```

## Performance on CPU (no GPU)

| Metric | Whisper-medium (faster-whisper) | PhoWhisper-medium (transformers) |
|--------|--------------------------------|----------------------------------|
| Load time | ~7s | ~8s |
| Transcription time (34s audio) | ~10-20s | ~23s per segment |
| RAM usage | ~5GB | ~8GB |

PhoWhisper is **~2× slower** on CPU because transformers pipeline lacks the CTranslate2 optimization. For long meetings, this adds up.

## Quality Comparison (Live Test Data)

Test file: `New Recording 9 - arguing.m4a` (33.7s, two people arguing/overlapping speech)

### PhoWhisper-medium strengths
- **"thỉnh thoảng"** → ✓ correct (vs Whisper's "thi thoại")
- Common Vietnamese words slightly better

### PhoWhisper-medium weaknesses
- **Proper nouns** (tên riêng, địa danh): Similar errors to general Whisper
- **Drops content**: Missed entire phrases that Whisper caught
- **"gặp nhau"** → transcribed as "cãi nhau" (wrong meaning)
- **"tiếng Pháp"** → dropped entirely from output
- **"tiếng Hàn"** → dropped entirely from output

### Whisper-medium strengths (on same file)
- Captured more of the content despite phonetic errors
- Better at preserving overlapping speech fragments

## Verdict

**PhoWhisper is NOT a clear improvement over general Whisper for this use case.** The speed penalty on CPU is significant, and quality gains are marginal — better on common words, worse on proper nouns and content preservation. For Vietnamese meetings:

1. **Default choice**: `faster-whisper` with `--model large-v3`
2. **If accuracy is critical and you have GPU**: PhoWhisper-large (not tested) may be worth the speed tradeoff
3. **For solo speaker meetings**: Either model works well at small/medium sizes

## HuggingFace Token Warning

PhoWhisper models trigger a 403 Forbidden error from HF when downloading without a token:
```
huggingface_hub.errors.HfHubHTTPError: Discussions are disabled for this repo.
Cannot access content at: https://huggingface.co/api/models/vinai/PhoWhisper-medium/discussions?p=0
```

This is harmless (model loads fine) but noisy in logs. Set `HF_TOKEN` to suppress the warning and speed up downloads.