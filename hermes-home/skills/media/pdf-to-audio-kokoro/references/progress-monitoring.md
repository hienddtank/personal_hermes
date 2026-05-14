# PDF-to-Audio TTS Progress Monitoring

## Quick Status Check

### Step 1: Check Cron Jobs for Active Monitors
```bash
cronjob action=list
```

Look for any active "Monitor TTS Conversion" or similar job.

### Step 2: Use Codex Forwarder to check system state
Check forwarder health first:
```bash
curl -s http://host.docker.internal:8768/health | python3 -m json.tool
```

Then send a task to inspect running processes, chunk files, and logs:
```bash
curl -X POST http://host.docker.internal:8768/run \
  -H "Content-Type: application/json" \
  -d '{
    "repo": "hermes_workspace",
    "prompt": "Check the following and output as structured summary:\n1. Run: ps aux | grep -E \"edge.tts|pdf_to_audio\" to see if TTS conversion is running\n2. List files in /tmp/tts_chunks/ or any chunk directories, count *_chunk_*.mp3 files\n3. Check /host/d/mkt/python/hermes/workspace/PDF_MP3 for output MP3 and chunk files\n4. Check /tmp/tts_run.log if it exists - show last 20 lines and grep for \"Saved\" count\n5. List cron jobs: crontab -l (if available)\nOutput format:\n- Running: yes/no (with PID if running)\n- Chunks created: X of Y total
- Output MP3 size/exists: yes/no (size if exists)
- Log summary: last errors or progress notes
- ETA estimate based on chunk timing",
    "approval": "never",
    "sandbox": "workspace-write"
  }'
```

### Step 3: If Codex Forwarder unavailable, check directly
```bash
crontab -l 2>/dev/null | grep -i tts || echo "No cron jobs found"
ps aux | grep -E "edge.tts|python.*tts" || echo "No TTS process found"
find /tmp -name "*_chunk_*.mp3" 2>/dev/null | wc -l
```

### Expected Output Format
```
Chunks: X/Y (Z%) | ETA: HH:MM | Status: Running / Complete
Output MP3: [exists with SIZE or not yet]
```

No extra commentary unless there's an error.