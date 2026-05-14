---
name: pi-agent
description: Guide to Pi Agent — a terminal-based, model-agnostic AI coding agent with deep extensibility via in-process TypeScript hooks. MIT license by Maxime Labissonnier (@pouria). Supports 15+ providers, session forking, RPC mode, and comprehensive tool replacement.
license: MIT
---

# Pi Agent

Terminal-based AI coding agent by Maxime Labissonnier (@pouria), MIT licensed. Focuses on deep extensibility — replace everything (tools, UI, context window) via TypeScript hooks.

## Installation

```bash
npx pi@latest          # Interactive install
pi --version            # Verify
```

## CLI Reference

```
pi [command] [options]

Commands:
  run        Interactive session with model (default)
  print      Single-shot output (no interactive loop)
  rpc        JSON-RPC 2.0 server for external control

Global Flags:
  -m, --model MODEL    Set model/provider (e.g., anthropic/claude-sonnet-4)
  -p, --profile NAME   Use named profile
  -e, --ext FILE       Load extension file
  -E, --extensions DIR Load extensions from directory
  -t, --theme THEME    Set theme
```

## Built-in Tools (LLM callable)

Pi ships with a minimal core of ~6 tools:

| Tool | Description |
|------|-------------|
| `read` | Read file contents + auto-detect MIME type (images included) |
| `write` | Create or overwrite files |
| `edit` | Surgical search-and-replace with fuzzy matching + unified diff |
| `ls` | List directory contents (sizes, timestamps) |
| `grep` | Regex content search in files |
| `find` | Recursive file search using `fd` |

Plus **bash** — shell execution available to the LLM.

## Key Commands / Slash Commands

Pi has NO built-in slash command system by design. Instead:
- Commands come from extensions/packages
- Use @mentions and natural language to invoke functionality
- Custom behavior via extension hooks (not commands)

The philosophy is: "ask pi to build what you want" rather than shipping fixed commands.

## Agent System / Architecture

Pi uses a single-agent architecture with extensive lifecycle hooks:

- **No built-in agent types** — everything is customizable
- Session forking via JSONL tree format (branching conversations)
- Context window management via replaceable hook (`ContextWindowHook`)
- Can build multi-agent pipelines using hooks + branching

## Lifecycle Hooks (25+)

Pi's main differentiator — extensive TypeScript hook system:

| Hook Category | Hooks | Purpose |
|---|---|---|
| **Session** | `SessionStart`, `SessionEnd` | Session lifecycle events |
| **Context** | `ContextWindowHook` | Replace how context is built/compressed per-turn |
| **Input** | `InputHook` | Intercept/modify user input |
| **Output** | `OutputHook` | Intercept/modify LLM output |
| **Tool** | `ToolCallHook`, `ToolResultHook` | Intercept tool calls and results |
| **Bash** | `BashSpawnHook` | Modify commands, cwd, env before execution |
| **UI** | `UIToolbar`, `UIMenuItem`, `UIFooter` | Replace UI components |

## Permissions / Safety

Pi has NO built-in permission system. You build it yourself via extensions:
- `BashSpawnHook` — intercept and modify/block any bash command
- `ToolCallHook` — intercept and modify/block any tool call
- Full control at the hook level

## Extensions / Plugin System

**In-process TypeScript (via jiti)** — zero serialization overhead.

```bash
# Install from npm, git, or local path
pi -e ./my-ext.ts
pi -E ./extensions-dir/

# Stack multiple extensions
pi -e ext1.ts -e ext2.ts
```

Extensions can:
- Replace the entire UI
- Intercept and modify context window per-turn
- Add custom tools
- Replace tool execution logic
- Communicate via shared event bus
- Build branching conversation pipelines

## Other Features

| Feature | Pi Agent |
|---------|----------|
| Session format | JSONL tree (forking) |
| RPC mode | Yes (JSON-RPC 2.0) |
| Print mode | Yes (single-shot output) |
| HTML export | Yes |
| Themes | Built-in theme system |
| Model providers | 15+ |
| Language | TypeScript/JavaScript |
| License | MIT |

## Session Management

```bash
# List sessions
pi session list

# Fork/branch a session
# (done via API, not CLI command — use context hooks)

# Export session as HTML
pi session export <id> --format html
```

## Pitfalls

- No built-in slash commands — you extend via TypeScript extensions
- In-process extensions means any crash can bring down the agent
- No permission system — must implement security yourself if needed
- Less out-of-the-box functionality than OpenCode or Claude Code