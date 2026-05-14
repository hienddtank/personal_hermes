# Cron Provider & Execution Issues

## Provider-Specific Failures (2026-05-08)

**Problem:** Cron jobs with `provider: openrouter` fail silently (`last_status: "error"`) because the cron execution context lacks OpenRouter API credentials. Jobs using `provider: custom` (local Hermes model) work reliably.

**Symptom pattern:**
- Batches 1–5 (Mon–Fri): `provider: openrouter`, `model: anthropic/claude-sonnet-4` → **all failing**
- Batch 6 (Sat): `provider: custom` → **passing**
- Sunday Review: `provider: custom` → **passing**

**Fix:** Switch to `provider: custom` + local model (`qwen3.6-27b`). If you need OpenRouter, the cron environment must have the appropriate credentials configured in docker-compose.yml or as environment variables.

## qwen3.6-27b Tool-Call Loop Diagnosis (2026-05-08)

**Scenario:** Skill audit cron job told model to "review each skill" using `skill_view()`. Model started calling it sequentially on ~100 skills.

**Confirmed session state at failure:**
- 22 total messages, 3 assistant turns, 18 tool responses
- Session duration: ~93 seconds with no final text output
- Last assistant message: "Good progress. Let me continue auditing the remaining non-archived skills in parallel batches."
- No delivery produced → `last_status: "error"`

**Diagnosis script:** Check any failed cron session file:
```python
import json
with open('session_cron_<jobid>_<date>.json') as f:
    data = json.load(f)
msgs = data['messages']
tool_msgs = [m for m in msgs if m.get('role') == 'tool']
assistant_msgs = [m for m in msgs if m.get('role') == 'assistant']
text_assistant = [m for m in assistant_msgs if isinstance(m.get('content',''), str) and m['content']]
print(f"Tool calls: {len(tool_msgs)}, Assistant with text: {len(text_assistant)}")
# Loop confirmed if tool_calls >> text_assistant and no final content
```

**Resolution:** Offload data collection to a Python script (stdlib-only), keep cron prompt as "run script, report results". See `references/python-cron-scripts.md`.

## cronjob(action='update') Does NOT Clear model/provider

When updating a cron job with `cronjob(action='update', prompt="...")`, the existing `model` and `provider` fields are preserved. You must explicitly pass new values:
```python
cronjob(action='update', job_id=..., 
        prompt="new prompt",
        model={"model": "qwen3.6-27b", "provider": "custom"})
```
