---
name: skill-audit
description: Systematically audit SKILL.md files across /hermes-home/skills/ for quality issues — placeholder text, missing frontmatter, empty descriptions. Runs as daily cron batches covering all 119+ skills.
created_at: 2026-05-08
---

# Skill Audit

Systematically audit all SKILL.md files in `/hermes-home/skills/` for quality issues.

## Purpose

Keep the skills library clean by detecting placeholder text, missing frontmatter, empty descriptions, and other quality problems across all skills.

## How to Run

The audit script lives at `/hermes-home/scripts/skill_audit.py`. It uses stdlib only.

```bash
# Audit ALL skills (119+ across 40 categories)
python3 /hermes-home/scripts/skill_audit.py

# Audit specific categories only
python3 /hermes-home/scripts/skill_audit.py --categories creative,devops,mlops

# Audit specific skill names
python3 /hermes-home/scripts/skill_audit.py --skills api/web-scraping,kanban/kanban
```

## Issue Categories Detected

- **No YAML frontmatter** — missing `---` header block
- **Empty description** in frontmatter  
- **Placeholder text**: "tbd", "todo", "placeholder", "insert here", "fill in", "add description" (case-insensitive)
- **Very short SKILL.md** (< 50 chars)
- **Brief description** (< 20 chars)

## ⚠️ Critical: Two SKILL.md Directory Structures

The skills directory has **two co-existing structures**. The script handles both automatically, but anyone modifying `get_all_skills()` must NOT assume a single layout:

1. **Multi-skill categories**: `{cat}/{name}/SKILL.md` — e.g., `creative/diagrams/SKILL.md`
2. **Single-skill categories**: `{cat}/SKILL.md` directly in the category folder — e.g., `docker-restart/SKILL.md`, `dogfood/SKILL.md`, `kanban/SKILL.md`

The script detects structure 1 by looking for subdirs, and falls back to structure 2 if no matching subdirs are found. **If you edit `get_all_skills()`, always check both patterns.**

## ⚠️ Pitfall: Zero-Skill False Negatives on `--categories` Filter

Before the fix (2026-05-08), when a filtered category had zero issues, the script reported "Total skills: 0" because `cats_seen` and counts were computed from results that only included non-ok items. **The fix:** `cats_seen` is now derived from ALL results regardless of status.

## Cron Batches (Token-Budget Friendly)

Skills are split into 6 daily batches so each cron invocation stays within context limits:

| Batch | Day | Categories | Count |
|-------|-----|-----------|-------|
| 1 | Mon | autonomous-ai-agents, api, data-science, creative, inference-sh, mcp, apple | 36 |
| 2 | Tue | devops, email, gaming, github, leisure, messaging, smart-home | 20 |
| 3 | Wed | media, mlops | 12 |
| 4 | Thu | productivity, research | 21 |
| 5 | Fri | software-development, social-media, mathematics, note-taking, red-teaming, kanban | 14 |
| 6 | Sat | docker-restart, dogfood, email-thread-analysis, embedding-session-recall, emotion-pathing, evolution-strategy-training, gpu-cloud-providers, kokoro-tts-batching, local-db-explorer, speech-models, tabular-data, travelleaders-crawler, vector-memory, vision-models, wording-resonance, yuanbao, academic-paper-downloader | 16 |

## Sunday Review (Weekly Cleanup)

The Sunday cron (`8b4a12ba2299`) audits ALL categories and instructs the LLM to:
1. Fix any skills with placeholder/TODO text  
2. Patch outdated SKILL.md files that no longer match their actual behavior
3. Flag truly dead/deprecated skills for removal
4. Consolidate any overlapping skills found during the week
