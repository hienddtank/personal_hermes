# Memory Management (Cleanup & Consolidation)

## When to Run Memory Cleanup
- Agent memory has grown beyond ~50 entries
- Memories feel stale or contradictory after major project shifts
- User says "our memories are getting messy" or "remember this differently"

## Systematic Approach

### Step 1: Audit Current State
```bash
# List all sessions from past week
session_search limit=20
```

Identify memories that:
- Have been superseded by newer facts
- Are temporary task state (should go in session_search, not persistent memory)
- Duplicate each other

### Step 2: Consolidate Related Memories
Group related entries (e.g., "User prefers Python over JavaScript" + "User uses pydantic") → single entry:
"Uses Python ecosystem with pydantic for data validation; prefers Python over JS."

### Step 3: Remove Stale Entries
```bash
# Remove by exact content match
memory(action='remove', target='user', old_text='Old preference text here')
```

### Key Rules
1. **Don't remove** — only consolidate or remove truly stale entries
2. **Keep procedural knowledge in skills, not memory** — workflows belong in SKILL.md files
3. **User preferences > environment facts** — user corrections and preferences take priority

## Common Pitfalls
- Saving task progress as memory (goes stale quickly)
- Imperative phrasing ("Always do X") instead of factual ("User prefers X")