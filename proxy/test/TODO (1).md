# TODO.md â€” Deterministic Test + Failure Capture System for llama.cpp Tool/Thinking Proxy

## Goal

Build a deterministic Python test and failure-capture system for the proxy.

The proxy currently normalizes llama.cpp responses by:

```txt
raw llama.cpp stream
â†’ strip thinking blocks
â†’ buffer tool-call fragments until complete
â†’ forward clean OpenAI-compatible tool calls
â†’ receive tool result
â†’ merge/continue response
â†’ expose clean non-streaming or streaming output
```

This TODO is for implementing the **stiff Python code first**.

Do **not** build an AI self-patching agent yet.

The current target is:

```txt
observe â†’ extract â†’ classify â†’ reproduce â†’ validate â†’ remember
```

The system should automatically capture useful live failures into test samples for future regression work.

---

## Non-goals

Do not implement automatic code patching yet.

Do not let any script rewrite proxy source files.

Do not let raw logs become approved tests automatically.

Do not collect secrets, API keys, full user prompts, or private data unless explicitly allowed by config.

Do not use AI for classification in this first version.

Everything in this phase should be deterministic Python.

---

## Proposed folder layout

Create this structure:

```txt
proxy/test/
  TODO.md

  samples/
    quarantine/
    minimized/
    approved/
    rejected/

  manifests/
    error_index.json

  regression/
    test_replay_samples.py

  unit/
    test_thinking_stripper.py
    test_tool_call_buffer.py
    test_stream_normalizer.py
    test_failure_classifier.py
    test_contract_validator.py

  fuzz/
    test_chunk_boundaries.py

proxy/
  observability/
    __init__.py
    failure_capture.py
    sample_schema.py
    redactor.py
    failure_classifier.py
    sample_writer.py
    sample_minimizer.py
    sample_deduper.py
    manifest_builder.py
    replay_runner.py
    contract_validator.py
```

Adjust paths if the project already has a different structure, but keep this separation:

```txt
proxy/observability/ = runtime capture and deterministic utilities
proxy/test/ = test samples and test runners
```

---

## Phase 1 â€” Define the sample schema

Create:

```txt
proxy/observability/sample_schema.py
```

Implement a stable JSON schema for captured failures.

Each sample should look like this:

```json
{
  "schema_version": 1,
  "id": "error_000001",
  "timestamp": "2026-04-29T10:00:00Z",
  "request_id": "req_xxx",
  "source": "live_proxy",
  "mode": "streaming",
  "model": "unknown",

  "category": "UNKNOWN",
  "severity": "unknown",
  "status": "quarantine",

  "failure": {
    "type": "UNKNOWN",
    "message": "",
    "exception_type": null,
    "stacktrace": null
  },

  "request_summary": {
    "endpoint": "/v1/chat/completions",
    "stream": true,
    "has_tools": false,
    "message_count": 0,
    "body_sha256": ""
  },

  "raw": {
    "llama_chunks": [],
    "client_chunks": [],
    "exception_text": "",
    "state_trace": []
  },

  "observed": {
    "visible_text": "",
    "tool_call_count": 0,
    "has_done": false,
    "empty_response": false,
    "thinking_leaked": false,
    "invalid_json": false,
    "incomplete_tool_call": false
  },

  "expected_behavior": {
    "mode": "needs_review",
    "notes": ""
  },

  "redaction": {
    "redacted": true,
    "rules_applied": []
  },

  "fingerprint": ""
}
```

Acceptance criteria:

```txt
- Can create a new sample object in Python.
- Can serialize sample to JSON.
- Can load it back.
- Missing optional fields should not crash the loader.
- Unknown future fields should be preserved when possible.
```

---

## Phase 2 â€” Add redaction

Create:

```txt
proxy/observability/redactor.py
```

Implement deterministic redaction before anything is written to disk.

Redact at least:

```txt
API keys
Bearer tokens
Authorization headers
cookies
password fields
secret fields
access_token
refresh_token
private IPs if configured
long user message content if configured
```

Default behavior:

```txt
- Keep structural data.
- Replace sensitive values with "[REDACTED]".
- Hash request bodies instead of storing full bodies by default.
- Store raw llama.cpp chunks only if PROXY_CAPTURE_RAW_CHUNKS=1.
```

Suggested environment flags:

```txt
PROXY_CAPTURE_FAILURES=1
PROXY_CAPTURE_DIR=proxy/test/samples/quarantine
PROXY_CAPTURE_RAW_CHUNKS=1
PROXY_CAPTURE_CLIENT_CHUNKS=1
PROXY_CAPTURE_STACKTRACE=1
PROXY_CAPTURE_MAX_CHARS=200000
PROXY_CAPTURE_REDACT_PRIVATE_IPS=0
```

Acceptance criteria:

```txt
- Authorization: Bearer abc123 becomes Authorization: Bearer [REDACTED].
- api_key values are redacted.
- password values are redacted.
- Redactor works on dicts, strings, lists, and nested JSON.
- Redactor never raises inside the live request path.
```

---

## Phase 3 â€” Add live proxy failure capture trigger

Create:

```txt
proxy/observability/failure_capture.py
proxy/observability/sample_writer.py
```

Add a runtime hook to the live proxy.

The hook should capture failures when any of these are detected:

```txt
1. Exception occurred inside proxy request handling.
2. Upstream response body is empty.
3. Stream ends before [DONE].
4. Stream produces zero visible assistant text and no tool calls.
5. Client-bound output still contains <think> or </think>.
6. Tool call started but never completed.
7. Tool arguments cannot be parsed as JSON after completion.
8. OpenAI response contract validation fails.
9. SSE output contains invalid JSON event.
10. Normalizer enters ERROR state.
```

Important:

```txt
- Capture must be best-effort.
- Capture must never crash the proxy.
- Capture must never block request handling for long.
- If writing the sample fails, log that failure and continue.
```

Basic implementation pattern:

```python
try:
    capture_failure_sample(...)
except Exception:
    logger.exception("failure capture failed")
```

Suggested live-proxy integration points:

```txt
- Before sending upstream request: create request_id and capture request summary.
- During llama.cpp stream: optionally append raw chunks to capture context.
- During normalized client output: optionally append client chunks.
- On normalizer state transition: optionally append state trace.
- On exception or invariant violation: write sample to quarantine.
```

Acceptance criteria:

```txt
- Setting PROXY_CAPTURE_FAILURES=0 disables capture completely.
- Setting PROXY_CAPTURE_FAILURES=1 enables capture.
- A forced exception creates one JSON file under proxy/test/samples/quarantine.
- Empty response creates one JSON file.
- Thinking leak creates one JSON file.
- Capture file has id, timestamp, category, request_id, and raw/observed sections.
```

---

## Phase 4 â€” Implement deterministic failure classifier

Create:

```txt
proxy/observability/failure_classifier.py
```

Classify samples using hardcoded rules.

Initial categories:

```txt
THINKING_LEAK
THINKING_TAG_SPLIT
EMPTY_UPSTREAM_BODY
EMPTY_AFTER_THINKING_STRIP
STREAM_CLOSED_EARLY
MISSING_DONE
INVALID_SSE_JSON
INVALID_OPENAI_CONTRACT
TOOL_CALL_INCOMPLETE
TOOL_ARGUMENTS_INVALID_JSON
TOOL_CALL_DUPLICATED
TOOL_RESULT_ORPHANED
BACKEND_TIMEOUT
BACKEND_CONNECTION_REFUSED
BACKEND_ERROR_STATUS
PROXY_EXCEPTION
UNKNOWN
```

Rule examples:

```txt
client output contains <think> or </think>
â†’ THINKING_LEAK

raw has content, raw contains <think>, final visible text empty, no tool call
â†’ EMPTY_AFTER_THINKING_STRIP

tool_call_started == true and tool_call_completed == false
â†’ TOOL_CALL_INCOMPLETE

streaming == true and has_done == false
â†’ MISSING_DONE

exception contains "timeout"
â†’ BACKEND_TIMEOUT

exception contains "connection refused"
â†’ BACKEND_CONNECTION_REFUSED
```

Each classification should return:

```json
{
  "category": "TOOL_CALL_INCOMPLETE",
  "layer": "tool_buffer",
  "replayable": true,
  "recommended_action": "fail_closed_or_fix_tool_buffer",
  "patch_allowed_later": true,
  "confidence": 0.9
}
```

Acceptance criteria:

```txt
- Classifier is deterministic.
- Same sample always returns same category.
- Unknown samples become UNKNOWN, not random categories.
- Unit tests cover each initial category.
```

---

## Phase 5 â€” Build sample writer and manifest builder

Create:

```txt
proxy/observability/sample_writer.py
proxy/observability/manifest_builder.py
```

Sample writer behavior:

```txt
- Write sample to quarantine by default.
- Filename format: error_{unix_ms}_{short_hash}.json
- Write atomically: write temp file, then rename.
- Add fingerprint.
- Do not overwrite existing samples.
```

Manifest builder behavior:

```txt
- Scan samples/quarantine, minimized, approved, rejected.
- Create proxy/test/manifests/error_index.json.
- Include id, file path, category, status, fingerprint, timestamp.
- Sort by timestamp desc.
```

Manifest example:

```json
{
  "schema_version": 1,
  "generated_at": "2026-04-29T10:00:00Z",
  "cases": [
    {
      "id": "error_000001",
      "file": "proxy/test/samples/quarantine/error_000001.json",
      "category": "THINKING_LEAK",
      "status": "quarantine",
      "fingerprint": "abc123",
      "replayable": true
    }
  ]
}
```

Acceptance criteria:

```txt
- Captured samples appear in manifest.
- Invalid JSON samples are skipped with warning.
- Manifest generation is deterministic.
```

---

## Phase 6 â€” Add sample deduplication

Create:

```txt
proxy/observability/sample_deduper.py
```

Dedupe based on fingerprint.

Fingerprint should include:

```txt
category
failure layer
normalized exception text
state where failure occurred
shape of raw chunks
hash of minimized or raw chunk content
```

Do not include timestamp in fingerprint.

Behavior:

```txt
- If same fingerprint exists, do not write duplicate sample.
- Instead update a counter file or manifest metadata.
```

Acceptable simple first version:

```txt
- Before writing, scan existing sample fingerprints.
- If fingerprint exists, skip write and log duplicate.
```

Acceptance criteria:

```txt
- Same failure captured twice does not create two approved-style cases.
- Distinct failures still create distinct samples.
```

---

## Phase 7 â€” Implement replay runner

Create:

```txt
proxy/observability/replay_runner.py
proxy/test/regression/test_replay_samples.py
```

Replay runner should load captured samples and replay:

```txt
sample.raw.llama_chunks
â†’ StreamNormalizer
â†’ internal clean events
â†’ OpenAI adapter if available
â†’ validators
```

Do not require live llama.cpp.

Do not require network.

Replay should work fully offline.

Expected behavior modes:

```txt
needs_review
must_pass_contract
must_fail_closed
must_not_leak_thinking
must_complete_tool_call
```

Initial rule:

```txt
Only run samples with status = approved in CI.
Quarantine samples can be replayed manually.
```

Acceptance criteria:

```txt
- Approved samples are loaded and replayed by pytest.
- Quarantine samples are not automatically enforced.
- Replayer can run a single sample by file path.
```

Suggested commands:

```powershell
python -m proxy.observability.manifest_builder
python -m proxy.observability.replay_runner proxy/test/samples/quarantine/error_x.json
pytest proxy/test/regression/test_replay_samples.py
```

---

## Phase 8 â€” Implement contract validator

Create:

```txt
proxy/observability/contract_validator.py
proxy/test/unit/test_contract_validator.py
```

Validate outgoing OpenAI-compatible responses.

For non-streaming responses, check:

```txt
object exists
choices is list
choices[0].message exists
message.role is assistant/tool where appropriate
tool_calls shape is valid if present
finish_reason exists
usage is optional but valid if present
```

For streaming SSE, check:

```txt
each event starts with data:
each data event is valid JSON except [DONE]
delta shape is valid
tool_call deltas do not contain invalid partial top-level JSON
[DONE] is present at end
no thinking tags are present
```

Acceptance criteria:

```txt
- Valid OpenAI-style response passes.
- Response containing <think> fails.
- Missing choices fails.
- Malformed SSE fails.
- Missing [DONE] fails for streaming mode.
```

---

## Phase 9 â€” Implement sample minimizer

Create:

```txt
proxy/observability/sample_minimizer.py
```

Purpose:

```txt
Reduce large captured samples into small reproducible samples.
```

Simple algorithm:

```txt
1. Load sample.
2. Confirm failure reproduces.
3. Try removing one chunk.
4. Replay.
5. If failure still reproduces, keep removal.
6. Repeat until no more chunks can be removed.
7. Save to proxy/test/samples/minimized.
```

Acceptance criteria:

```txt
- Minimizer never changes original quarantine sample.
- Minimized sample preserves same category.
- Minimized sample still reproduces the failure.
- If failure cannot be reproduced, mark sample as rejected or needs_review.
```

---

## Phase 10 â€” Add fuzz tests for chunk boundaries

Create:

```txt
proxy/test/fuzz/test_chunk_boundaries.py
```

Build deterministic fuzz tests for:

```txt
thinking tag split across every possible boundary
closing thinking tag split across every possible boundary
tool JSON split across every possible boundary
escaped quotes inside tool arguments
braces inside tool argument strings
nested JSON inside tool arguments
UTF-8 text split across chunks if applicable
```

Invariant:

```txt
Same logical input + different chunk boundaries = same normalized output.
```

Acceptance criteria:

```txt
- Fixed random seed.
- No network.
- No live llama.cpp.
- Test failures produce readable case names.
```

---

## Phase 11 â€” Add unit tests for core proxy normalizer components

Create or update:

```txt
proxy/test/unit/test_thinking_stripper.py
proxy/test/unit/test_tool_call_buffer.py
proxy/test/unit/test_stream_normalizer.py
```

Must test:

```txt
<think>hidden</think>
<think> split across chunks
</think> split across chunks
normal text before and after thinking
unfinished thinking block
tool call in one chunk
tool call split across chunks
tool arguments with nested JSON
tool arguments with escaped quotes
tool arguments containing literal "<think>" text
tool call while thinking block is active
thinking after tool call
multiple tool calls
duplicate tool call IDs
tool result without matching tool call
```

Acceptance criteria:

```txt
- No thinking content reaches visible output.
- Tool calls are emitted only when complete.
- Tool arguments remain valid.
- Partial tool JSON is never forwarded to client.
- Literal "<think>" inside a JSON string is not stripped unless explicitly intended by parser context.
```

---

## Phase 12 â€” Add promotion workflow

Create a script:

```txt
scripts/promote_sample.py
```

Behavior:

```txt
- Move sample from quarantine or minimized to approved.
- Require category is not UNKNOWN unless --allow-unknown is passed.
- Require expected_behavior.mode is not needs_review unless --allow-needs-review is passed.
- Rebuild manifest after promotion.
```

Example:

```powershell
python scripts/promote_sample.py proxy/test/samples/minimized/error_x.json
```

Acceptance criteria:

```txt
- Approved samples become regression tests.
- Quarantine samples stay non-blocking.
- Promotion updates status field.
- Manifest is rebuilt.
```

---

## Phase 13 â€” Add rejected workflow

Create:

```txt
scripts/reject_sample.py
```

Use when sample is noisy, private, non-reproducible, duplicate, or not useful.

Behavior:

```txt
- Move sample to proxy/test/samples/rejected.
- Add rejection_reason.
- Rebuild manifest.
```

Common rejection reasons:

```txt
duplicate
contains_private_data
not_reproducible
expected_backend_failure
not_proxy_bug
bad_capture
```

---

## Phase 14 â€” Add CLI entry points

Add simple command-line entry points.

Suggested commands:

```powershell
python -m proxy.observability.manifest_builder
python -m proxy.observability.replay_runner --all-approved
python -m proxy.observability.replay_runner --sample proxy/test/samples/quarantine/error_x.json
python -m proxy.observability.sample_minimizer --sample proxy/test/samples/quarantine/error_x.json
python scripts/promote_sample.py proxy/test/samples/minimized/error_x.json
python scripts/reject_sample.py proxy/test/samples/quarantine/error_x.json --reason not_reproducible
```

Acceptance criteria:

```txt
- Every CLI has --help.
- Every CLI exits nonzero on real failure.
- Every CLI prints concise readable output.
```

---

## Phase 15 â€” Add live proxy capture configuration

Add configuration values to proxy settings.

Required:

```txt
capture_failures: bool
capture_dir: str
capture_raw_chunks: bool
capture_client_chunks: bool
capture_stacktrace: bool
capture_max_chars: int
capture_sample_rate: float
```

Environment mapping:

```txt
PROXY_CAPTURE_FAILURES
PROXY_CAPTURE_DIR
PROXY_CAPTURE_RAW_CHUNKS
PROXY_CAPTURE_CLIENT_CHUNKS
PROXY_CAPTURE_STACKTRACE
PROXY_CAPTURE_MAX_CHARS
PROXY_CAPTURE_SAMPLE_RATE
```

Default safe values:

```txt
PROXY_CAPTURE_FAILURES=0
PROXY_CAPTURE_DIR=proxy/test/samples/quarantine
PROXY_CAPTURE_RAW_CHUNKS=0
PROXY_CAPTURE_CLIENT_CHUNKS=1
PROXY_CAPTURE_STACKTRACE=1
PROXY_CAPTURE_MAX_CHARS=200000
PROXY_CAPTURE_SAMPLE_RATE=1.0
```

Acceptance criteria:

```txt
- Capture is off by default.
- Capture can be enabled without code changes.
- Capture directory is created if missing.
- Oversized samples are truncated safely and marked as truncated.
```

---

## Phase 16 â€” Add failure report output

When a sample is captured, log a compact message:

```txt
Captured proxy failure sample:
  id: error_x
  category: TOOL_CALL_INCOMPLETE
  path: proxy/test/samples/quarantine/error_x.json
  replayable: true
```

Do not print secrets.

Acceptance criteria:

```txt
- Logs contain sample id and path.
- Logs do not contain raw prompt content unless explicitly configured.
```

---

## Phase 17 â€” Add README for the test sample system

Create:

```txt
proxy/test/samples/README.md
```

Explain:

```txt
quarantine = automatically captured, not trusted yet
minimized = reduced reproductions
approved = regression fixtures used by pytest
rejected = kept for audit/debug, not used
```

Include basic workflow:

```txt
1. Enable capture.
2. Run proxy.
3. Trigger/use proxy normally.
4. Inspect quarantine samples.
5. Minimize useful samples.
6. Promote useful samples.
7. Run regression tests.
```

---

## Phase 18 â€” Hard rule: no raw auto-promotion

Implement this rule:

```txt
A live-captured sample must never go directly into proxy/test/samples/approved.
```

It must go through:

```txt
quarantine â†’ minimized or reviewed â†’ approved
```

Acceptance criteria:

```txt
- sample_writer only writes quarantine.
- promote_sample.py is the only normal path to approved.
```

---

## Phase 19 â€” Minimal first milestone

The first working milestone is complete when this works:

```powershell
$env:PROXY_CAPTURE_FAILURES="1"
$env:PROXY_CAPTURE_RAW_CHUNKS="1"

# Run proxy and force a bad response / exception.

python -m proxy.observability.manifest_builder

python -m proxy.observability.replay_runner --sample proxy/test/samples/quarantine/<sample>.json
```

And pytest passes:

```powershell
pytest proxy/test/unit/test_failure_classifier.py
pytest proxy/test/unit/test_contract_validator.py
pytest proxy/test/regression/test_replay_samples.py
```

---

## Phase 20 â€” Definition of done

This TODO is complete when:

```txt
- Live proxy can automatically save failure samples.
- Samples are redacted.
- Samples are classified.
- Manifest is generated.
- Approved samples can be replayed offline.
- Contract validator catches thinking leaks and malformed SSE.
- Chunk-boundary fuzz tests exist.
- No AI agent is required.
- No source code is automatically patched.
```

---

## Critical design principle

Do not build a log hoarder.

Build a reproducible failure system.

The value is not in saving many logs.

The value is in saving small, redacted, classified, replayable samples that can become regression tests.

