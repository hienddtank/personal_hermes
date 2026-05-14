---
name: self-modify-loop
description: "Self-modify loop — AI agent proposes code modifications, implements them under strict constraints, runs experiments, evaluates results, and iteratively improves. Architecture spans SMO1–SMO5 evolution of Karpathy-style autoresearch systems adapted for STOCK_RL forex trading."
version: 1.1.0
author: Hermes Agent (Hien Dinh)
tags: [autonomous-ai, self-modifying-code, evolution-strategy, research-automation]
---

# Self-Modify Loop Architecture

## When to Use

- Building autonomous AI training/experimentation systems
- Implementing LLM-in-the-loop code improvement cycles
- Setting up evolution strategy pipelines with automated change management
- Running overnight/unsupervised ML experiments where an AI agent modifies and evaluates code
- You want to find a loop on disk — check `/host/f/AI/` for SMO1–SMO5 variants

## Core Loop Pattern

```
LOOP FOREVER:
  1. RESTORE stable version of allowed files
  2. CALL Codex in "proposal" mode (read-only sandbox)
  3. CHECK duplicate vs prior experiments (fuzzy matching)
  4. REJECT if too similar to past idea → go back to step 2
  5. CALL Codex in "implementation" mode (write sandbox)
  6. ENFORCE protected files unchanged (snapshot before, restore if modified)
  7. RUN training/experiment with time budget
  8. COMPARE result vs incumbent (is_better function)
  9. KEEP if better → save as new stable; RESTORE if not
  10. LOG result to results.tsv with status: keep/discard/crash
```

## Key Files Structure (SMO3 / STOCK_RL variant)

| File | Purpose |
|------|---------|
| `smo3_codex_loop.py` | Main orchestration (~950 lines) — the brain of the loop |
| `program.md` / `AGENT.md` | Instructions given to Codex for each experiment |
| `results.tsv` | Experiment history: run_id, score, memory_gb, status, description |
| `.self_modify_loop/stable/` | Persistent working copies of allowed files |
| `.self_modify_loop/checkpoints/` | Per-run training checkpoints |
| `.self_modify_loop/run_logs/` | Archived full logs per run |
| `.smo3_loop/` | Legacy variant — contains codex_exec.log, stable_model.py, stable_trainer.py |

**Path convention**: SMO3 lives at `F:/AI/self_modify_baseline/STOCK_RL/`. Inside Docker: `/host/f/AI/self_modify_baseline/STOCK_RL/`.

## SMO Evolution (SMO1–SMO5)

| Version | Domain | Key Feature | Status |
|---------|--------|-------------|--------|
| **SMO1** | Text generation (val_bpb) | Original Karpathy autoresearch | Historical |
| **SMO2** | Same, different codebase | Iteration 2 | Historical |
| **SMO3** | STOCK_RL forex trading | Codex CLI two-phase calls, protected files, experiment memory | **Active — main loop** |
| **SMO4** | Time-series diffusion forecasting | ViT-style model, separate codebase | Standalone |
| **SMO5** | Simplified restructure | `data_prep.py` + `train_test.py` (~12KB total) | Minimal prototype |

## Allowed vs Protected Files

**Allowed to modify:** Core training code, model architecture, optimizer settings.
- In STOCK_RL: `model.py`, `evolution/flattener.py`, `evolution/trainer.py`

**Protected (never touch):** Reward/fitness functions, environment mechanics, evaluation logic.
- In STOCK_RL: `evolution/fitness.py`, `evolution/env.py`, `env/` directory

Enforcement via snapshot before each experiment and automatic restore on violation.

## Duplicate Detection

Uses combined similarity scoring to avoid repeating past ideas:

```python
# 1. Normalize description (lowercase, strip numbers, tokenize)
def _normalize_description(text):
    text = re.sub(r'\d+(\.\d+)?', ' ', text.lower())
    text = re.sub(r'[^a-z0-9]+', ' ', text).strip()

# 2. Jaccard token similarity + SequenceMatcher ratio
# 3. If combined score > threshold (default 0.72), reject as duplicate
```

Also maintains "experiment memory" fed back to Codex: recent tail, best accepted ideas, repeated failed directions.

## Two-Phase Codex Calls

**Phase 1 — Proposal (read-only sandbox):**
- Codex proposes exactly ONE change idea
- Cannot run commands, cannot edit files
- Output starts with `PROPOSAL: <description>`
- Checked against prior history for duplicates before proceeding

**Phase 2 — Implementation (write sandbox):**
- Codex implements the approved proposal
- Can only edit allowed files
- Cannot train, cannot run git, cannot long-running commands
- Output starts with `EXPERIMENT: <change description>`
- Protected file enforcement runs after

This separation prevents Codex from both proposing AND running unvetted experiments.

## Experiment Memory (Context Given to Codex)

Each proposal gets this context block injected into the prompt:
```
Recent tail:
- run12: keep, gen=25, score=438.04, idea=adaptive mutation on stagnation
- run13: keep, gen=26, score=550.57, idea=rank-weighted parent selection

Best accepted ideas:
- run13: gen=26, score=550.57, idea=rank-weighted parent + immigrants

Repeated failed directions to avoid:
- x2: discard, pattern=top elitism, example=add explicit top-2 elitism
```

This forces Codex to build on wins and avoid past failures.

## Configuration (defaults in smo3_codex_loop.py)

| Parameter | Default | Purpose |
|-----------|---------|---------|
| `DEFAULT_BUDGET_SECONDS` | 1800 (30min) | Training time per experiment |
| `DEFAULT_MAX_VRAM_MB` | 1800 | VRAM cap (hard limit, MB) |
| `DEFAULT_CODEX_MODEL` | gpt-5.4-mini | LLM model for proposals/implementations |
| `DEFAULT_REASONING_EFFORT` | medium | Model reasoning budget |
| `DEFAULT_FUZZY_MATCH_THRESHOLD` | 0.72 | Duplicate detection sensitivity |
| `DEFAULT_STOP_ON_CRASH` | True | Stop loop after crash? |
| `DEFAULT_MAX_EXPERIMENTS` | 0 | 0 = infinite loop until interrupted |
| `DEFAULT_MAX_PROPOSAL_ATTEMPTS` | 0 | 0 = unlimited attempts per iteration |

**Stock RL specific env vars:**
- `STOCK_RL_DEVICE` — default `cuda:1` (RTX 5060 Ti)
- `STOCK_RL_POP_SIZE` — default 512
- `STOCK_RL_GENERATIONS` — default 50,000
- `STOCK_RL_STEPS` — default 5,000
- `STOCK_RL_VRAM_LIMIT_MB` — hard limit per training process

## Results TSV Format

```
run_id\tgenerations_completed\tbest_score\tmemory_gb\tstatus\tdescription
baseline-20260508-105936\t24\t433.880000\t0.1\tkeep\tbaseline
run-20260508-115918\t26\t595.600000\t0.1\tkeep\tlayer-aware two-parent crossover
```

Status values: `keep`, `discard`, `crash`

## Current Best Results (SMO3/STOCK_RL, 2026-05-08)

Top keepers after first full run day:

| Run | Score | Idea |
|-----|-------|------|
| **162729** | **690.56** | Momentum-conditioned projection + gated residual branch |
| 152322 | 633.41 | Hall-of-fame archive + crossover from archived parents |
| 115918 | 595.60 | Layer-aware two-parent crossover path |
| 113552 | 550.57 | Rank-weighted parent selection + immigrants |

Baseline started at score 433.88, improved to 690.56 in ~11 accepted iterations.

## Important Lessons

### 1. The stable directory is critical
`STABLE_DIR` (e.g., `.self_modify_loop/stable/`) persists working code across experiments. `restore_stable_files()` resets to the last kept state before each new proposal. This prevents one bad experiment from corrupting a good baseline.

### 2. Protected file enforcement catches sneaky edits
Codex sometimes tries to modify fitness.py or env.py under the guise of "fixing" something. The snapshot-before/restore-after mechanism catches this and logs it as a rejected experiment. Always keep protected files in your experiment memory so Codex learns not to try again.

### 3. Two-parent crossover was a major win
Rank-weighted parent selection + layer-aware two-parent crossover produced the biggest single jump (450 → 595, +32%). Worth noting as a successful direction if Codex gets stuck on smaller tweaks.

### 4. Adaptive mutation handles stagnation
When best fitness stalls for consecutive generations, increasing offspring noise re-invigorates exploration. When improvement resumes, the rate snaps back to default.

## Troubleshooting

### Codex keeps proposing duplicates
Lower `--fuzzy-match-threshold` (default 0.72). Check that experiment memory is being fed back correctly. Ensure descriptions are sufficiently detailed — vague descriptions match too broadly.

### Training always crashes after a change
Check if the change affected allowed files in a way that breaks the trainer output format. The loop parses specific lines: `Gen ... | best=...`, `Done. N generations in Ts`, `Best fitness:`, `Final VRAM:`. Breaking these will cause parse failures.

### Protected file modification keeps happening
Codex is trying to modify reward/fitness/env code. Check the experiment memory — if it's being repeated, add explicit negative feedback in the rejected proposals block for that specific change.

### Loop stalls (no improvement for many runs)
Try: (1) reducing fuzzy match threshold to allow more diverse proposals, (2) increasing budget seconds per experiment, (3) adding a "reset stable" run where you manually restore an earlier baseline state and let Codex start fresh.

## Extending Beyond Codex

This pattern works with any agent that supports read-only and write sandboxes:
- **Claude Code**: Use file scope constraints in prompts
- **OpenCode**: Use workspace-write sandbox mode
- **Custom agent**: Adapt the proposal → verify → implement → run → select cycle

Core abstraction: two modes — **proposal** (read-only, propose without editing) and **implementation** (write-sandbox, edit allowed files only).

## Related Skills

- `evolution-strategy-training` — ES training patterns (fitness evaluation, checkpointing)
- `subagent-web-research-patterns` — When to use subagents vs self-modify loops