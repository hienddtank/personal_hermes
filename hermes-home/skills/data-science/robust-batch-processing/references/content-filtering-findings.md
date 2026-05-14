# Content Filtering for Semantic Search Ingestion

Session-specific findings from building Hermes Agent's conversation memory pipeline. These filters prevent noisy data from polluting search results.

## The Problem: Tool Output Contamination

When ingesting session logs (JSONL format with user/assistant/tool messages), **tool outputs dominate index noise**:
- Terminal error tracebacks
- Raw JSON dumps from API responses
- Web search result fragments
- System prompt leakage

In one test: tool outputs were 54% of all chunks (269/523), but returned as top results for 80%+ of vague queries.

## Filter Rules That Worked

### 1. Context Compaction Blocks
```python
if "[CONTEXT COMPACTION" in text:
    return False  # Skip auto-generated summaries
```
These are system-produced meta-summaries that add no searchable value.

### 2. System Prompt Fragments (Assistant)
```python
if role == "assistant" and "You are Hermes Agent" in text[:200]:
    return False  # System instructions leaking into response
```
Assistant sometimes echoes system prompt text — this is not actual conversation content.

### 3. JSON-Heavy Tool Outputs
```python
special_ratio = sum(1 for c in text if c in '{}[]()') / max(len(text), 1)
if special_ratio > 0.3:  # >30% brackets/parens
    return False
```
Raw API responses and terminal JSON output pollute embeddings. Natural language content is what matters for search.

### 4. Very Short Tool Outputs
```python
content_lines = [l for l in text.split('\n') if l.strip()]
if len(content_lines) < 2:
    return False
```
One-liner tool outputs like `{"error": null}` are just noise.

## Chunk Size Trade-offs (from testing)

| Chunk Size | Overlap | Chunks/Session | Avg Quality | Vague Query Score |
|------------|---------|----------------|-------------|-------------------|
| 250 chars  | 50      | ~50            | Fragmented  | 0.18–0.49         |
| 500 chars  | 100     | ~30            | Better context | 0.18–0.49       |

**Finding**: Larger chunks didn't improve vague query scores because the bottleneck is **noise**, not chunk size. The same tool output contamination exists regardless of chunk size.

## What Actually Improves Search Quality

1. **Filter first, embed second** — remove noisy content before it enters the index
2. **More real conversation data** — 178 sessions of actual dialogue > few sessions with clean chunks
3. **BM25 pre-filtering** — lexical match to narrow candidates before semantic scoring
4. **Role-based weighting** — user messages and assistant responses > tool outputs

## Session Log JSONL Structure (Hermes Agent)

```jsonl
{"role": "user", "content": "...", "timestamp": "..."}
{"role": "assistant", "content": "...", "reasoning_content": "...", "tool_calls": [...]}
{"role": "tool", "content": "...", "name": "terminal|web_search|..."}
{"role": "session_meta", "tools": [...]}  // Skip this entirely
```

Key: `session_meta` entries are the tools list for the session — always skip.
