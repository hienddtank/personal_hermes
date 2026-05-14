# Query Performance Patterns & Known Issues

## Score Ranges by Query Type

| Query Category | Typical Score Range | Example Queries |
|---------------|-------------------|-----------------|
| **Concrete** (specific terms from session) | 0.60–0.90 | "calculus exercises pdf", "embedding engine faiss" |
| **Vague** (abstract/general) | 0.18–0.49 | "what is the goal", "the database problem", "why does it crash" |
| **Meta** (about the session itself) | 0.15–0.35 | "what was the plan again", "remember when we set up" |

## Why Vague Queries Underperform

Semantic embeddings match on *lexical similarity*, not *semantic intent*. A query like "the database problem" won't match "Building embedding engine for Hermes memory" because the words don't overlap, even though they refer to the same topic.

**This is a fundamental limitation of dense vector search on short text.** It works well when the query reuses specific vocabulary from the target content (concrete queries). It fails when the query uses different phrasing or abstract references.

## Tool Output Contamination (Critical)

Tool outputs dominate top results for vague queries because they contain:
- System prompt fragments ("You are Hermes Agent...")
- Code snippets and error traces
- Raw web search result text
- Query result duplication (a tool output containing previous query results)

**Example**: Query "how do I fix errors" → top hit is a Python `TypeError` traceback, not actual debugging advice.

### Mitigation Strategies

1. **Filter at ingestion time**: Skip tool chunks that start with system prompt patterns
   ```python
   if role == "tool":
       content = msg["content"]
       if "You are Hermes Agent" in content[:200]:
           return None  # skip
   ```

2. **Lower tool table weight**: During scoring, multiply tool scores by 0.3–0.5 to demote them relative to user/assistant content.

3. **Hybrid search (BM25 + vector)**: Pre-filter candidates with keyword matching before doing semantic ranking. Useful for vague queries that need lexical anchors.

4. **Summarize before embedding**: Run a lightweight summarizer on long tool outputs (terminal dumps, web results) and embed only the summary.

## Concrete vs Vague Query Examples

```
# ✅ WORKS — reuses session vocabulary
Q: "calculus exercises pdf" → 0.67
   Match: User message contains exact terms

# ✅ WORKS — technical term match
Q: "embedding engine faiss" → 0.55
   Match: Assistant reasoning mentions both words

# ⚠️ UNDERPERFORMS — abstract reference
Q: "the database problem" → 0.49 (tool output)
   Expected: Session about building embedding engine
   Got: Query result text from previous search

# ⚠️ UNDERPERFORMS — system prompt contamination
Q: "what files are important" → 0.46 (tool output)  
   Expected: Discussion of FAISS .index vs JSON files
   Got: System instructions about FAISS binary format

# ✅ WORKS — direct user question
Q: "can you help me learn" → 0.26 (user message)
   Match: User message about calculus self-study
```

## Recommended Query Design

For best results, construct queries using **concrete vocabulary** from the target content:

- ❌ "what should I work on next" → vague, scores ~0.35
- ✅ "calculus study plan next steps" → concrete terms, scores ~0.60+

When designing a retrieval interface for users, consider adding query rewrites or synonyms to improve vague query performance.
