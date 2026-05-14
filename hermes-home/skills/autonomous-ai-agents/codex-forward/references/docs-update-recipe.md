---
name: Codex Documentation Update Skill
description: Automates using Codex AI agent to inspect and update project documentation (structure.md and README.md) for the Fish_Doc_Extractor repository.
author: Hermes Agent
version: 1.0
---

# Codex Documentation Update Skill

## Overview
This skill automates the workflow of using the Codex AI agent to inspect and update project documentation (structure.md and README.md) for the Fish_Doc_Extractor repository.

## Server Configuration
- **Endpoint**: `http://host.docker.internal:8768/run`
- **Service**: Codex forwarder (status 200 OK)
- **Path Format**: Windows-style paths required (`D:\mkt\python\Fish_Doc_Extractor`)

## API Payload Schema
```json
{
  "cwd": "D:\\mkt\\python\\Fish_Doc_Extractor",
  "prompt": "<your documentation update instructions>",
  "model": "gpt-5.4",
  "approval": "never",
  "sandbox": "workspace-write"
}
```

## Critical Bug Fix
The Codex forwarder has a known bug where `--ask-for-approval` is incorrectly passed to the command line. The fix requires adding `--` before the flag:

**Broken**:
```bash
F:\miniconda\codex.cmd exec -C D:\mkt\python\Fish_Doc_Extractor --model gpt-5.4 --ask-for-approval never ...
```

**Fixed**:
```bash
F:\miniconda\codex.cmd exec -C D:\mkt\python\Fish_Doc_Extractor --model gpt-5.4 -- --ask-for-approval never ...
```

## Prompt Template for Documentation Updates
Use this prompt structure to update project documentation:

```markdown
Please inspect and update the following files in the repository:
1. structure.md - Project structure documentation
2. README.md - Project README file

Tasks:
- Review current content and update with latest information
- Ensure all commands, paths, and configurations are accurate
- Add missing sections if applicable
- Keep formatting consistent and professional

Return a summary of changes made after completion.
```

## Expected Output
After successful execution, the agent will:
1. Read existing documentation files
2. Update content based on current project state
3. Provide a detailed summary of changes
4. Include file sizes and key sections updated

## Files Updated
- `structure.md` - Comprehensive project structure (typically ~5.9 KB)
- `README.md` - Full project documentation with setup instructions, commands reference, and notes (typically ~9.1 KB)

## Troubleshooting
1. **Path errors**: Ensure Windows-style paths are used (`D:\...` not `/d/...`)
2. **Approval flag errors**: Verify the `-- --ask-for-approval` fix is applied
3. **Connection refused**: Confirm server is running on port 8768
4. **Timeout issues**: May need to adjust execution timeout settings

## Example curl Command
```bash
curl -X POST http://host.docker.internal:8768/run \
  -H "Content-Type: application/json" \
  -d '{
    "cwd": "D:\\\\mkt\\\\python\\\\Fish_Doc_Extractor",
    "prompt": "Please inspect and update structure.md and README.md...",
    "model": "gpt-5.4",
    "approval": "never",
    "sandbox": "workspace-write"
  }'
```

## Notes
- This skill requires the Codex agent to be properly configured
- The sandbox mode `workspace-write` is required for file modifications
- Model `gpt-5.4` should be specified explicitly