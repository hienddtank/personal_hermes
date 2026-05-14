# Weekly Session Review Cron (Debugging & Maintenance)

## Purpose
Automated weekly scan of past sessions to update memory and surface open threads. Typically runs Sunday 6AM via cron job.

## Common Failure Mode: qwen3.6-27b Tool-Call Loop

### Symptoms
- Job status shows "error"
- Session file has 10+ messages, all assistant turns with `content_len: 0` and `tool_calls > 0`
- No final text response delivered to chat
- qwen3.6-27b keeps making tool calls forever without producing output

### Resolution: Heartbeat Fix Pattern
1. **Diagnose**: Check session file for empty-content tool-call loops
2. **Simplify**: Reduce prompt to 2-3 steps max, remove deep analysis phases
3. **Offload to script**: Move data collection into a standalone Python script (stdlib only)
4. **Use cron `script` field**: Point to the script so cron runs it as an isolated subprocess
5. **Verify**: Run manually with `cronjob(action='run')` and check for non-zero content length

### Template Cron Job
```json
{
  "name": "Weekly Session Review",
  "schedule": "0 6 * * 0",
  "script": "~/.hermes/scripts/weekly_review_check.sh",
  "prompt": "Read the weekly review results file. Summarize any open threads and suggest memory updates.",
  "deliver": "origin"
}
```

### Script Requirements
- Use only stdlib (json, os, datetime)
- Read from `~/.hermes/chat_history/*.jsonl`
- Write results to `~/.hermes/scripts/weekly_output.json`
- Return exit code 0 even if no new data found

## Related: Weekly Session Review Hub Skill
The hub-installed `weekly-session-review` skill provides a pre-built Sunday 6AM cron pattern. Check it if you want an opinionated weekly review workflow.