---
name: workspace-territory
description: Pattern for establishing drive/workspace territory maps using 'HERMES READ THIS' files at each drive root with permission levels (READ/WRITE/GUARD) and folder vibes.
---

# Workspace Territory Map

When the user wants to establish or understand drive/workspace layout, use territory-based documentation instead of static directory trees.

## The Pattern

Place a `HERMES READ THIS` file at each major drive root (D:, E:, F:, etc.). Each file contains:

1. **Drive name + nickname/vibe** — one-line personality description
2. **Folder inventory** — key folders with their purpose and "vibe"
3. **Permission rules** — what you're allowed to READ vs WRITE in each zone
4. **Guardrails** — things never to touch, always consult first, etc.

## Why This Works Over a Static Map

- **Co-located** — lives where it belongs, not buried in another directory
- **Portable** — travels with the drive if moved
- **Per-drive ownership** — each drive explains its own character rather than having one file describe everything from far away
- **Captures semantics** — folder "vibes," intent, and rules that a filesystem tree can't express
- **Zero staleness** — user edits the right file when they add/move stuff

## Permission Levels

| Level | Meaning |
|-------|---------|
| READ | Consult, search, reference. Always OK. |
| WRITE | Create, modify, generate files. Only under explicit conditions. |
| GUARD | Never write here unless explicitly asked. Reference assets only. |

## Template

```markdown
=== DRIVE X: — "<nickname>" ===
Vibe: <one-line personality description>

Main folders:
  folder/   → <purpose + vibe, e.g. "your sandbox. all dev work goes here">
  other/    → <what it's for>

RULES:
- Primary rule (e.g. "start all new work here")
- Cross-drive rule if applicable
- Guardrails

PERMISSIONS:
- workspace/      : READ+WRITE
- hermes/         : READ, WRITE only skills/
- tools/          : READ ONLY
```

## When to Use

- User says they want a "map" or "mental map" of their drives
- New session and workspace layout is unclear
- User mentions confusion about where stuff lives
- Before making large file operations across multiple drives