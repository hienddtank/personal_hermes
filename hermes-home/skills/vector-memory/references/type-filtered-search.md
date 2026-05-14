# Type-Filtered Search Pattern

When content types are split into separate FAISS tables, the query layer needs to support filtering by source type to control scoring weight and noise.

## Architecture
Six tables: `short_user`, `short_assistant`, `short_tool`, `long_user`, `long_assistant`, `long_tool`.

Each table stores embeddings for one content type × time horizon combination.

## Query Flow
1. **Load phase**: Load FAISS + metadata for requested tables only.
   ```python
   def load_tables(table_type=None, time_filter=None):
       all_tables = ["short_user", "short_assistant", "short_tool",
                     "long_user", "long_assistant", "long_tool"]
       for name in all_tables:
           if table_type and f"_{table_type}" not in name: continue
           if time_filter and f"{time_filter}_" not in name: continue
           # load meta_*.json and *.index
   ```

2. **Search phase**: Search all loaded tables, join results by weighted score.
   ```python
   TYPE_WEIGHTS = {"user": 1.0, "assistant": 0.9, "tool": 0.7}
   
   for name in meta_store:
       idx = indices[name]
       if idx.ntotal == 0: continue
       dists, ids_ = idx.search(query_emb, k)
       for d, i in zip(dists[0], ids_[0]):
           if i < 0: continue
           type_name = TABLE_TYPE_MAP[name]  # e.g. "user"
           weighted_score = float(d) * TYPE_WEIGHTS.get(type_name, 0.5)
   ```

3. **Display**: Group by type with visual tags `[USER]`, `[ASSISTANT]`, `[TOOL]`.

## Pitfalls from Iteration
- `global model` must be declared at the TOP of the function, before any variable reference — putting it inside `if model is None:` causes SyntaxError.
- Use `.replace()` instead of `re.sub()` for JSON escape sequence cleanup — regex escaping (`\\\\\"`) trips up Python's re parser.
- Table loading and search functions must accept `(meta_store, indices)` as separate params, not wrapped in a nested dict.