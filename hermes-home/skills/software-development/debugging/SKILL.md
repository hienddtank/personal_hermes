---
name: debugging
description: "Complete debugging toolkit: systematic methodology + Python (pdb/debugpy) + Node.js (node inspect/CDP) + Hermes TUI."
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [debugging, troubleshooting, root-cause, pdb, debugpy, node-inspect, cdp, tui]
    related_skills: [test-driven-development, systematic-debugging]
---

# Debugging

Class-level umbrella for all debugging workflows. Four layers of knowledge:

| Layer | Reference | Covers |
|---|---|---|
| **Methodology** | Below (in this file) | 4-phase root cause debugging, red flags, rule of three |
| **Python** | `references/python-debugging.md` | pdb, debugpy, remote-pdb, pytest debugging, async/multiprocessing |
| **Node.js** | `references/node-debugging.md` | node inspect, CDP, TypeScript sourcemaps, Vitest, heap/CPU profiles |
| **Hermes TUI** | `references/hermes-tui-debugging.md` | Slash commands, tui_gateway, Ink UI, autocomplete, config sync |

## When to Use

- Any bug, test failure, unexpected behavior, or performance issue
- When `print()`/`console.log` isn't enough
- When you need to inspect state, trace data flow, or step through execution

**Don't use for:** things logging/printing solves in under a minute.

---

## Systematic Debugging Methodology (4 Phases)

**Core principle: ALWAYS find root cause before attempting fixes.**

### Phase 1: Root Cause Investigation

1. **Read error messages completely** — stack traces, line numbers, error codes
2. **Reproduce consistently** — exact steps, deterministic trigger
3. **Check recent changes** — git diff, commits, dependency updates
4. **Gather evidence at component boundaries** — log inputs/outputs at each layer
5. **Trace data flow upstream** — find where the bad value originates, not where it crashes

**Checklist before proceeding:**
- [ ] Error messages read and understood
- [ ] Issue reproduced consistently
- [ ] Recent changes identified
- [ ] Evidence gathered (logs, state, data flow)
- [ ] Root cause hypothesis formed

### Phase 2: Pattern Analysis

1. Find working examples of similar code
2. Compare against references — list every difference
3. Understand dependencies (config, env, assumptions)

### Phase 3: Hypothesis and Testing

1. Form single hypothesis: "I think X because Y"
2. Test minimally — one variable at a time
3. If it works → Phase 4. If not → new hypothesis.

### Phase 4: Implementation

1. Create failing regression test first
2. Implement single fix addressing root cause
3. Verify fix + run full suite

**Rule of Three:** If 3+ fixes failed, stop and question the architecture. Don't attempt fix #4 without architectural discussion.

### Red Flags — STOP and Return to Phase 1

- "Quick fix for now, investigate later"
- "Just try changing X and see if it works"
- "Add multiple changes, run tests"
- Proposing solutions before tracing data flow
- "One more fix attempt" (after 2+ failures)
- Each fix reveals new shared state in a different place

---

## Quick Tool Selection

| Language/Context | First Choice | When It's Not Enough |
|---|---|---|
| Python (local) | `breakpoint()` + pdb | `python -m pdb` (no source edit) |
| Python (remote/headless) | `remote-pdb` | `debugpy` (DAP, IDE integration) |
| Python (pytest) | `--pdb` flag | `--showlocals --tb=long` |
| Node.js (local) | `node inspect` | `node --inspect-brk` + CDP scripting |
| Node.js (TypeScript) | `node --enable-source-maps --inspect-brk` | CDP with sourcemap support |
| Node.js (already running) | `kill -SIGUSR1 <pid>` + `node inspect -p` | CDP `chrome-remote-interface` |
| Hermes TUI | Depends on layer: Python (pdb) or Node (inspect) | See `references/hermes-tui-debugging.md` |

---

## Common Pitfalls (across all tools)

1. **pdb under pytest-xdist silently does nothing.** Use `-p no:xdist` or `-n 0`
2. **`PYTHONBREAKPOINT=0` disables all breakpoints.** Check env if breakpoint doesn't hit
3. **`breakpoint()` / `set_trace()` must be removed before committing.** `rg -n 'breakpoint\(\)|set_trace\(' --type py`
4. **`--inspect` vs `--inspect-brk`.** Use `-brk` when you need to set breakpoints before any code runs
5. **TypeScript sourcemaps.** `node inspect` CLI doesn't follow sourcemaps — break in `dist/*.js` or use CDP
6. **Port collisions.** Multiple inspectors default to 9229. Use `--inspect=0` for random port
7. **Forking/multiprocessing.** Debuggers don't follow forks. Each child needs its own breakpoint
8. **Background kills.** Ctrl+C from debugger while target is paused → target stays paused. `cont` or `kill` explicitly

## See Also

- `references/python-debugging.md` — Full Python debugging guide (pdb, debugpy, remote-pdb, 374 lines of recipes)
- `references/node-debugging.md` — Full Node.js debugging guide (node inspect, CDP, 318 lines of recipes)
- `references/hermes-tui-debugging.md` — Hermes TUI-specific debugging (slash commands, Ink, gateway)
