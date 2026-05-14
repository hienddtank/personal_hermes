---
name: Hermes Tool Access Patterns
description: Guide for accessing session search and memory tools in Hermes Agent environment
version: 1.1
---

# Hermes Tool Access Patterns

## Session Search and Memory Tools Location

The session search and memory tools are **not** available as direct imports from `hermes_tools`. Instead, they are located in `/opt/hermes-agent/tools/` as separate modules.

### Available Locations

- **Session Search**: `/opt/hermes-agent/tools/session_search_tool.py`
- **Memory Tool**: `/opt/hermes-agent/tools/memory_tool.py`

## Recommended Approach: Use Hermes CLI (Cron-Friendly)

For cron jobs and automated data collection, the CLI approach is more reliable and doesn't require a running agent process.

### Export Sessions via CLI

```bash
hermes sessions export /path/to/output.jsonl
```

This exports all sessions to JSONL format with fields:
- `id`: Session ID
- `source`: Source type (cron, user, etc.)
- `model`: Model used
- `system_prompt`: System prompt configuration

### List Memory via CLI

```bash
hermes memory list
```

Output format: `key: value` pairs, one per line.

## Access Methods (Programmatic)

#### Session Search (`session_search_tool`)

```python
import sys
sys.path.insert(0, '/opt/hermes-agent/tools')
from session_search_tool import session_search

# Requires a query parameter (empty string for recent sessions)
result = session_search(query="")
# Returns a JSON-formatted string, not a dict
print(result)  # Parse as needed
```

**Important**: In cron environments, the session database may not be available:
```json
{"error": "Session database not available.", "success": false}
```

#### Memory Tool (`memory_tool`)

The memory tool is designed as an action-based interface:

```python
from memory_tool import memory_tool

# Add entry
result = memory_tool(action="add", target="memory", content="Some content")

# Replace entry
result = memory_tool(action="replace", target="memory", old_text="old", content="new")

# Remove entry
result = memory_tool(action="remove", target="memory", old_text="text to remove")
```

**Parameters**:
- `action`: "add" | "replace" | "remove"
- `target`: "memory" (agent notes) or "user" (user preferences)
- `content`: Content to add/replace with
- `old_text`: Required for replace/remove actions

### Memory Directory Structure

Memory files are stored in: `~/.hermes/memories/`

Key files:
- `MEMORY.md` - Agent's personal notes and observations
- `USER.md` - User preferences and communication style
- `*.lock` - Lock files (can be ignored)

Entries are delimited by `§` (section sign). Files can contain plain text or JSON.

## Alternative Access (Direct File Reading)

If the memory tool module is unavailable, read directly from disk:

```python
memory_dir = os.path.expanduser("~/.hermes/memories")
for f in os.listdir(memory_dir):
    filepath = os.path.join(memory_dir, f)
    if os.path.isfile(filepath) and not f.endswith('.lock'):
        with open(filepath, 'r') as mf:
            content = mf.read()
            # Parse JSON or split by § for plain text entries
```

## Cron Job Data Collection Pattern

For automated chat history collection in cron environments:

```python
#!/usr/bin/env python3
import subprocess
import json
from datetime import datetime

chat_history_dir = os.path.expanduser("~/.hermes/chat_history")
os.makedirs(chat_history_dir, exist_ok=True)

today = datetime.now().strftime('%Y%m%d')
export_path = f'/tmp/sessions_export_{today}.jsonl'

# Export sessions via CLI
result = subprocess.run(
    ['hermes', 'sessions', 'export', export_path],
    capture_output=True, text=True, timeout=30
)

if result.returncode == 0:
    with open(export_path, 'r') as f:
        for line in f:
            session = json.loads(line)
            # Process session data...
    os.remove(export_path)

# Get memory entries
result = subprocess.run(
    ['hermes', 'memory', 'list'],
    capture_output=True, text=True, timeout=30
)

# Write to chat history file
file_path = os.path.join(chat_history_dir, f"{today}.jsonl")
with open(file_path, 'w') as f:
    # Write session and memory records...
```

## Troubleshooting

### "ModuleNotFoundError" for hermes_tools
- The `hermes_tools` package doesn't expose these tools directly
- Use the direct path `/opt/hermes-agent/tools/` instead
- Or use the CLI approach (recommended for cron)

### Session Database Unavailable
- Check if the cron environment has proper initialization
- Memory operations will still work independently
- Consider using CLI-based export as fallback

## Cron Job Data Collection Pattern

For automated chat history collection in cron environments:

```python
#!/usr/bin/env python3
import subprocess
import json
from datetime import datetime

chat_history_dir = os.path.expanduser("~/.hermes/chat_history")
os.makedirs(chat_history_dir, exist_ok=True)

today = datetime.now().strftime('%Y%m%d')
export_path = f'/tmp/sessions_export_{today}.jsonl'

# Export sessions via CLI
result = subprocess.run(
    ['hermes', 'sessions', 'export', export_path],
    capture_output=True, text=True, timeout=30
)

if result.returncode == 0:
    with open(export_path, 'r') as f:
        for line in f:
            session = json.loads(line)
            # Process session data...
    os.remove(export_path)

# Get memory entries
result = subprocess.run(
    ['hermes', 'memory', 'list'],
    capture_output=True, text=True, timeout=30
)

# Write to chat history file
file_path = os.path.join(chat_history_dir, f"{today}.jsonl")
with open(file_path, 'w') as f:
    # Write session and memory records...
```
- Consider using CLI-based export as fallback

## Related Skills

- `memory`: For using the memory tool interface
- `session_search`: For searching past conversations (when available)", "old_string": "---\nname: Hermes Tool Access Patterns\ndescription: Guide for accessing session search and memory tools in Hermes Agent environment\nversion: 1.0\n---"