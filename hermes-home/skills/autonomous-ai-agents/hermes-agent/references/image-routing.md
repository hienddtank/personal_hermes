# Hermes Image Routing Architecture

## Flow Overview

```
User sends photo (Telegram) → Telegram adapter downloads & caches to local path
    ↓
Gateway runner sees event.media_urls → calls _decide_image_input_mode()
    ↓
Routing decision: native vs text
    ↓
native  → build_native_content_parts() → base64 data URLs → sent as OpenAI-style image_url content blocks
text    → _enrich_message_with_vision() → vision_analyze pre-run → description prepended to user text
```

## Key Files

- `gateway/platforms/telegram.py` `_handle_media_message()` (line ~2696): Downloads photos from Telegram, caches via `cache_image_from_bytes()`, sets `event.media_urls` + `event.media_types`. Photos are **NOT** passed directly to agent — they're cached and routed through the image routing system.
- `gateway/run.py` `_decide_image_input_mode()` (line ~8791): Delegates to `agent/image_routing.py:decide_image_input_mode()`.
- `agent/image_routing.py`: Full decision logic.

## Decision Logic (`decide_image_input_mode`)

Priority order:
1. **Explicit mode config**: `agent.image_input_mode` in config.yaml — `"native"`, `"text"`, or `"auto"` (default)
2. **Auto mode**:
   - If `auxiliary.vision.provider` is explicitly set (not empty/auto) → text (user opted into dedicated vision backend)
   - If active model has `supports_vision=True` in `models.dev` metadata → native
   - Otherwise → text

## Config Key: `agent.image_input_mode`

```yaml
agent:
  image_input_mode: auto   # or "native" or "text"
```

- `"native"` — images sent as base64 content blocks to multimodal model. Best UX for vision-capable models.
- `"text"` — pre-analyzed via vision_analyze, descriptions prepended. Fallback for non-vision models.
- `"auto"` — checks model metadata. Works great with registered providers (OpenRouter, Anthropic, OpenAI, etc.)

## Troubleshooting: "Why does my multimodal model still use vision_analyze?"

Most common cause: custom/local provider (`custom`) is not registered in Hermes' model capabilities database, so `supports_vision` can't be resolved → auto falls back to `"text"`.

**Fix:** Set `agent.image_input_mode: native` in config.yaml if your model actually supports vision. Or use an OpenRouter-hosted multimodal model which is pre-registered.

## Config Hot Reload Behavior ⭐ CRITICAL

**`_decide_image_input_mode()` reads `config.yaml` fresh each turn.** Changes to `agent.image_input_mode` take effect immediately on the next message — no gateway restart required. There is NO hard-coded config cache at runtime for this setting.

This means:
1. Edit `config.yaml` → change `image_input_mode`
2. Next message is processed with the new setting immediately
3. Verify by sending an image and observing behavior (native response vs text summary)
4. Other config changes (model, provider, toolsets) may still require restart

## Image Size Limits (Reactive)

Hermes does NOT proactively resize images. It attaches full-size and shrinks on provider rejection:
- Anthropic: 5 MB per image (HTTP 400 if exceeded)
- OpenAI: ~49 MB+
- Gemini: ~100 MB

Resize happens transparently via `run_agent._try_shrink_image_parts_in_messages`.
