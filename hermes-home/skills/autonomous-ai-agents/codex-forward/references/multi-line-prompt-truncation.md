# Multi-Line Prompt Pitfall — Codex Forwarder

## Problem
When sending `POST /run-async` (or `POST /run`) via the Codex Forwarder with **multi-line file content embedded directly in the `prompt` string**, Codex (gpt-5.4) often truncates or drops the newlines. The model sees "create file with content:" but then only receives the first line because `\n` sequences in JSON strings get mangled during prompt processing.

Symptom: Codex replies with "Your instructions are incomplete" or creates files with only partial content (e.g., just `@echo off` instead of full script).

## Root Cause
The forwarder passes the `prompt` as a single command-line argument to `codex.exec`. Multi-line strings in JSON become `\n\n` sequences that get interpreted as prompt section breaks or are silently dropped before reaching the model's context window.

## Workarounds

### Workaround 1: Use shell commands (preferred)
Instead of embedding file content in the prompt, instruct Codex to use echo/printf/shell redirection:

```json
{
  "prompt": "Create D:/path/file.bat by running:\necho @echo off > D:/path/file.bat\necho HELLO >> D:/path/file.bat\necho exit /b 0 >> D:/path/file.bat\nThen verify the file content.",
  ...
}
```

### Workaround 2: Use Python one-liner
For more complex file content, have Codex run Python to write the file:

```json
{
  "prompt": "Run this Python command to create the file:\npython -c \"\nwith open(r'D:/path/file.py', 'w') as f:\\n    f.write('line1\\nline2\\nline3')\"\nThen verify the content.",
  ...
}
```

### Workaround 3: Use a separate /run-async for file content
First job: create an empty file. Second job (with repo context): write content using Codex's file-writing tools directly (not via prompt text).

### Workaround 4: POST /run instead of /run-async
`POST /run` (blocking) sometimes preserves multi-line content better because it keeps the connection alive — but this is not guaranteed. Test both if one fails.

## Decision Tree
1. Simple file creation (few lines) → Use shell echo commands in prompt
2. Complex file creation (many lines, code) → Write via Python one-liner or use Codex's built-in file write tools directly (ask it to create the file, not embed content in text)
3. If still failing → Split into multiple jobs: first creates structure, second populates content

## Verification Always After
After any job that creates/modifies files, always add a verification step to the prompt: "Then verify the file exists and show its full content." Without this, you won't know if the truncation happened until you try to use the file.
