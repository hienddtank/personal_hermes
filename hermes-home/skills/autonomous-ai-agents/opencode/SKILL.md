---
name: opencode
description: Delegate coding tasks to OpenCode CLI agent for feature implementation, refactoring, PR review, and long-running autonomous sessions. Requires the opencode CLI installed and authenticated.
version: 1.2.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [Coding-Agent, OpenCode, Autonomous, Refactoring, Code-Review]
    related_skills: [claude-code, codex, hermes-agent]
---

# OpenCode CLI

Use [OpenCode](https://opencode.ai) as an autonomous coding worker orchestrated by Hermes terminal/process tools. OpenCode is a provider-agnostic, open-source AI coding agent with a TUI and CLI.

## When to Use

- User explicitly asks to use OpenCode
- You want an external coding agent to implement/refactor/review code
- You need long-running coding sessions with progress checks
- You want parallel task execution in isolated workdirs/worktrees

## Prerequisites

- OpenCode installed: `npm i -g opencode-ai@latest` or `brew install anomalyco/tap/opencode`
- Auth configured: `opencode auth login` or set provider env vars (OPENROUTER_API_KEY, etc.)
- Verify: `opencode auth list` should show at least one provider
- Git repository for code tasks (recommended)
- `pty=true` for interactive TUI sessions

## Custom Provider Configuration (Local/Remote LLM)

**Important:** Setting `OPENAI_API_KEY` and `OPENAI_BASE_URL` env vars alone does NOT work with OpenCode v1.14+. OpenCode still consults its built-in model registry and fails with "Model not found". You must create a full provider config file.

Config location: `~/.config/opencode/opencode.json`

Steps:
1. Discover models on the endpoint:
   ```
   curl -s http://<host>:<port>/v1/models | python3 -c "import sys,json; d=json.load(sys.stdin); [print(m['id']) for m in d.get('data',[])]"
   ```
2. Write the config with explicit model definitions (model IDs must match exactly):
   ```json
   {
     "$schema": "https://opencode.ai/config.json",
     "provider": {
       "openai": {
         "npm": "@ai-sdk/openai-compatible",
         "name": "Local LLM (llama.cpp)",
         "options": {
           "baseURL": "http://<host>:<port>/v1"
         },
         "models": {
           "<MODEL_ID>": {
             "name": "<Human-Readable Name>",
             "tools": true,
             "capabilities": {
               "parallel_tool_calls": false
             }
           }
         }
       }
     }
   }
   ```
3. Test: `opencode run 'Respond with exactly: TEST_OK' --model openai/<MODEL_ID>`

Pitfalls:
- Do NOT use env vars alone for custom endpoints — they are ignored by OpenCode's model resolver
- Model names in config must match the exact string from `/v1/models` response
- Set `parallel_tool_calls: false` for llama.cpp models (they may not support it)
- After creating/updating the config, no restart needed — OpenCode reads it on each invocation

## Permission / External Directory Access

OpenCode defaults `external_directory` to `"ask"`, which auto-rejects in non-TUI mode. This blocks writes to mounted paths like `/host/d/mkt/**`. You must whitelist them explicitly:

Add to the config file (after the provider section):
```json
{
  "permission": {
    "external_directory": {
      "/host/d/mkt/**": "allow"
    }
  }
}
```

Adjust the path pattern to match your mounted drives. Without this, OpenCode will create files in `/root` instead of your project workspace and silently fail on writes.

## Binary Resolution (Important)

Shell environments may resolve different OpenCode binaries. If behavior differs between your terminal and Hermes, check:

```
terminal(command="which -a opencode")
terminal(command="opencode --version")
```

If needed, pin an explicit binary path:

```
terminal(command="$HOME/.opencode/bin/opencode run '...'", workdir="~/project", pty=true)
```

## One-Shot Tasks

Use `opencode run` for bounded, non-interactive tasks:

```
terminal(command="opencode run 'Add retry logic to API calls and update tests'", workdir="~/project")
```

Attach context files with `-f`:

```
terminal(command="opencode run 'Review this config for security issues' -f config.yaml -f .env.example", workdir="~/project")
```

Show model thinking with `--thinking`:

```
terminal(command="opencode run 'Debug why tests fail in CI' --thinking", workdir="~/project")
```

Force a specific model:

```
terminal(command="opencode run 'Refactor auth module' --model openrouter/anthropic/claude-sonnet-4", workdir="~/project")
```

## Interactive Sessions (Background)

For iterative work requiring multiple exchanges, start the TUI in background:

```
terminal(command="opencode", workdir="~/project", background=true, pty=true)
# Returns session_id

# Send a prompt
process(action="submit", session_id="<id>", data="Implement OAuth refresh flow and add tests")

# Monitor progress
process(action="poll", session_id="<id>")
process(action="log", session_id="<id>")

# Send follow-up input
process(action="submit", session_id="<id>", data="Now add error handling for token expiry")

# Exit cleanly — Ctrl+C
process(action="write", session_id="<id>", data="\x03")
# Or just kill the process
process(action="kill", session_id="<id>")
```

**Important:** Do NOT use `/exit` — it is not a valid OpenCode command and will open an agent selector dialog instead. Use Ctrl+C (`\x03`) or `process(action="kill")` to exit.

### TUI Keybindings

| Key | Action |
|-----|--------|
| `Enter` | Submit message (press twice if needed) |
| `Tab` | Switch between agents (build/plan) |
| `Ctrl+P` | Open command palette |
| `Ctrl+X L` | Switch session |
| `Ctrl+X M` | Switch model |
| `Ctrl+X N` | New session |
| `Ctrl+X E` | Open editor |
| `Ctrl+C` | Exit OpenCode |

### Resuming Sessions

After exiting, OpenCode prints a session ID. Resume with:

```
terminal(command="opencode -c", workdir="~/project", background=true, pty=true)  # Continue last session
terminal(command="opencode -s ses_abc123", workdir="~/project", background=true, pty=true)  # Specific session
```

## Common Flags

| Flag | Use |
|------|-----|
| `run 'prompt'` | One-shot execution and exit |
| `--continue` / `-c` | Continue the last OpenCode session |
| `--session <id>` / `-s` | Continue a specific session |
| `--agent <name>` | Choose OpenCode agent (build or plan) |
| `--model provider/model` | Force specific model |
| `--format json` | Machine-readable output/events |
| `--file <path>` / `-f` | Attach file(s) to the message |
| `--thinking` | Show model thinking blocks |
| `--variant <level>` | Reasoning effort (high, max, minimal) |
| `--title <name>` | Name the session |
| `--attach <url>` | Connect to a running opencode server |

## Procedure

1. Verify tool readiness:
   - `terminal(command="opencode --version")`
   - `terminal(command="opencode auth list")`
2. For bounded tasks, use `opencode run '...'` (no pty needed).
3. For iterative tasks, start `opencode` with `background=true, pty=true`.
4. Monitor long tasks with `process(action="poll"|"log")`.
5. If OpenCode asks for input, respond via `process(action="submit", ...)`.
6. Exit with `process(action="write", data="\x03")` or `process(action="kill")`.
7. Summarize file changes, test results, and next steps back to user.

## PR Review Workflow

OpenCode has a built-in PR command:

```
terminal(command="opencode pr 42", workdir="~/project", pty=true)
```

Or review in a temporary clone for isolation:

```
terminal(command="REVIEW=$(mktemp -d) && git clone https://github.com/user/repo.git $REVIEW && cd $REVIEW && opencode run 'Review this PR vs main. Report bugs, security risks, test gaps, and style issues.' -f $(git diff origin/main --name-only | head -20 | tr '\n' ' ')", pty=true)
```

## Parallel Work Pattern

Use separate workdirs/worktrees to avoid collisions:

```
terminal(command="opencode run 'Fix issue #101 and commit'", workdir="/tmp/issue-101", background=true, pty=true)
terminal(command="opencode run 'Add parser regression tests and commit'", workdir="/tmp/issue-102", background=true, pty=true)
process(action="list")
```

## Session & Cost Management

List past sessions:

```
terminal(command="opencode session list")
```

Check token usage and costs:

```
terminal(command="opencode stats")
terminal(command="opencode stats --days 7 --models anthropic/claude-sonnet-4")
```

## Multi-Phase Project Modification Pattern

For large repo modifications (e.g., adding a new feature system), break into sequential phases:

1. **Write phase task files** — Create comprehensive markdown instructions at `/root/.hermes/workspace/opencode-phase<N>-task.md`
2. **Launch each phase separately** — `opencode run "PHASE N: ... Read the full task from /path/to/phase-N-task.md"` with `timeout=600`
3. **Verify between phases** — Check created files exist before launching the next phase: `find ... -name "*.tsx" | sort` or `ls` on expected paths
4. **Handle timeouts** — OpenCode often hits 600s timeout mid-phase. Files created before the cutoff persist. Verify what exists, then launch a final targeted task for only the missing pieces rather than rerunning everything

### Task File Format (Better Than -f Flag)

Large inline prompts can be truncated or lose detail. Instead:
```markdown
# Write task to file
write_file("/root/.hermes/workspace/task.md", """
You are modifying a Next.js project at /path/to/project.

## CONTEXT
[Background info]

## STEP 1: Create X
Create `/path/to/x.tsx`:
[code]

## STEP 2: Create Y
...

## DELIVERABLES
List every file created/modified.
""")

# Then run
terminal("opencode run 'Read the full task from /root/.hermes/workspace/task.md and execute it'", workdir="/path/to/project", timeout=600)
```

### GitHub Repo Modification Workflow

1. Search for repos: `web_search("github [topic] open source project")`
2. Find a suitable repo with `npm install` setup
3. Clone into workspace: `git clone <url> /host/d/mkt/python/hermes/workspace/<project-name>`
4. Run phases sequentially (schema → API routes → UI components)

### Timeout Recovery Checklist

When a phase process times out (exit_code=124):
- Run `find ...` to list all expected new files
- Check which parts completed vs what's missing
- Write a focused task file for ONLY the missing items
- Launch with a shorter prompt (fewer steps = more likely to finish)

## Pitfalls

- Interactive `opencode` (TUI) sessions require `pty=true`. The `opencode run` command does NOT need pty.
- `/exit` is NOT a valid command — it opens an agent selector. Use Ctrl+C to exit the TUI.
- PATH mismatch can select the wrong OpenCode binary/model config.
- If OpenCode appears stuck, inspect logs before killing:
  - `process(action="log", session_id="<id>")`
- Avoid sharing one working directory across parallel OpenCode sessions.
- Enter may need to be pressed twice to submit in the TUI (once to finalize text, once to send).
- **600s timeout is common for large tasks** — plan phases accordingly; expect partial completion and verify before continuing.

## Verification

Smoke test:

```
terminal(command="opencode run 'Respond with exactly: OPENCODE_SMOKE_OK'")
```

Success criteria:
- Output includes `OPENCODE_SMOKE_OK`
- Command exits without provider/model errors
- For code tasks: expected files changed and tests pass

## Rules

1. Prefer `opencode run` for one-shot automation — it's simpler and doesn't need pty.
2. Use interactive background mode only when iteration is needed.
3. Always scope OpenCode sessions to a single repo/workdir.
4. For long tasks, provide progress updates from `process` logs.
5. Report concrete outcomes (files changed, tests, remaining risks).
6. Exit interactive sessions with Ctrl+C or kill, never `/exit`.
