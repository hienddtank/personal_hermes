---
name: pre-implementation-docs
description: Create AGENT.md + HERMES.md before any Codex/implementation work. Captures architecture and user intent with nearest-wins scoping.
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [planning, documentation, workflow]
---

# Pre-Implementation Documentation

## When to Use

**Always use before:**
- Delegating coding tasks to Codex or any agent
- Starting implementation on a new project or feature area
- Creating subdirectory scope with its own design

**Don't skip when:**
- The task involves multiple files or components
- Future you (or another agent) needs context to continue

## File Types & Scoping

### Two Files Per Scope

| File | Content |
|------|---------|
| `AGENT.md` | System architecture — components, data flow, tech choices, trade-offs, phases |
| `HERMES.md` | User intent + goals + project direction + my operational role on it |

### Nearest-Wins Scoping

Multiple AGENT.md / HERMES.md can exist at different directory levels. The one **closest to the file being edited** takes precedence.

Example:
```
project-root/
├── AGENT.md          ← system-wide architecture (applies to root-level work)
├── HERMES.md         ← overall project goals & intent
├── backend/
│   ├── AGENT.md      ← overrides root for backend (API contracts, DB schema)
│   ├── HERMES.md     ← backend-specific goals & scope
│   └── server.py     ← reads backend/AG* and backend/HERM*
├── frontend/
│   ├── AGENT.md      ← overrides root for frontend (UI, state mgmt)
│   └── app.tsx       ← reads frontend/AG* and frontend/HERM*
```

**Rule:** When editing `backend/server.py`, I look at `backend/AGENT.md` and `backend/HERMES.md`. They don't exist → fall back to parent (root). Root doesn't exist → create.

## Tech Stack Convention — Option A (Single Source of Truth)

**Root AGENT.md owns the tech stack table.** Subdirectory AGENT.mds:
- Reference root's stack; **do not redefine it**
- May add scope-specific tools (e.g., "Alembic" for migrations, "Playwright" for e2e tests)
- Any deviation must include `## Tech Stack Override` section with explicit justification

This prevents tech drift across directory levels.

## Creation Process

### Step 1: Check Existing Docs

```python
# Look for existing AGENT/HERMES at current and parent levels
search_files("AGENT.md", target="files", path="<scope>/")
search_files("HERMES.md", target="files", path="<scope>/")
```

### Step 2: Read Parent-Level Docs (if any)

If `../AGENT.md` or `../HERMES.md` exists, read them for context — the current scope should be consistent with parent.

### Step 3: Create/Update AGENT.md

Structure:
1. **System Overview** — 2-3 sentence description of what this scope covers
2. **Architecture** — components, component diagram (ASCII), data flow
3. **Tech Stack** — only at root level; subdirs reference parent
4. **API/Interface Contracts** — endpoints, CLI interfaces, schemas
5. **Design Decisions & Trade-offs** — for each: context, decision, alternatives, trade-offs
6. **File & Directory Layout**
7. **Open Questions / Risks**
8. **Implementation Phases** — Foundation → Features → Polish

### Step 4: Create/Update HERMES.md

Structure:
1. **Project Intent** — user's goal in their own words or paraphrased, success criteria
2. **Scope & Boundaries** — what's IN and what's OUT of scope for this level
3. **Phase Priorities** — what matters first, what can wait
4. **My Operational Role** — how I should work on this (tools, constraints specific to this scope)
5. **Communication Rules** — any special instructions for this project

### Step 5: Review & Confirm with User

Before delegating to Codex or starting code:
- Show both files (or summary) to the user
- Confirm architecture choices align with their intent
- Confirm phases and priorities match expectations

### Step 6: Only Then → Implement

Proceed to coding delegation only after AGENT.md and HERMES.md are solid.

## Key Principles

1. **HerMES captures intent, not just ops** — it's where "why we're doing this" lives for that scope
2. **Root owns tech stack** — children reference, never redefine
3. **Nearest wins** — closest .md file to the target file governs
4. **No placeholder templates** — only create when there's a real project
5. **Show before delegating** — confirm with user before Codex touches code
