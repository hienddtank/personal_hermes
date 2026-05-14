# Workspace Structure

Generated from `D:\mkt\python\hermes`.

Excluded by default: `.git`, `.mypy_cache`, `.pytest_cache`, `.ruff_cache`, `__pycache__`, `firecrawl-data`, `firecrawl-src`, `hermes-home/cache`, `hermes-home/logs`, `hermes-home/sessions`, `node_modules`, `open-webui-data`.

```text
D:\mkt\python\hermes\
|-- devops\
|   |-- codex-forwarder-maintenance\
|   |   `-- SKILL.md
|   `-- ngrok-forwarding\
|       |-- SKILL.md
|       `-- start-ngrok.ps1
|-- hermes-home\
|   |-- bin\
|   |   `-- tirith
|   |-- cron\
|   |   |-- output\
|   |   |   |-- 385eba784b0a\
|   |   |   `-- d7e8b712a22d\
|   |   |-- .tick.lock
|   |   `-- jobs.json
|   |-- document_cache\
|   |-- image_cache\
|   |-- memories\
|   |   |-- MEMORY.md
|   |   |-- MEMORY.md.lock
|   |   |-- USER.md
|   |   `-- USER.md.lock
|   |-- pairing\
|   |-- scripts\
|   |-- skills\
|   |   |-- api\
|   |   |   `-- realisticasia-api\
|   |   |-- apple\
|   |   |   |-- apple-notes\
|   |   |   |-- apple-reminders\
|   |   |   |-- findmy\
|   |   |   |-- imessage\
|   |   |   `-- DESCRIPTION.md
|   |   |-- autonomous-ai-agents\
|   |   |   |-- claude-code\
|   |   |   |-- codex\
|   |   |   |-- hermes-agent\
|   |   |   |-- opencode\
|   |   |   `-- DESCRIPTION.md
|   |   |-- creative\
|   |   |   |-- ascii-art\
|   |   |   |-- ascii-video\
|   |   |   |-- creative-ideation\
|   |   |   |-- excalidraw\
|   |   |   |-- manim-video\
|   |   |   |-- p5js\
|   |   |   |-- popular-web-designs\
|   |   |   |-- songwriting-and-ai-music\
|   |   |   `-- DESCRIPTION.md
|   |   |-- data-science\
|   |   |   |-- csv-filter-by-domain\
|   |   |   |-- excel-create-minimal\
|   |   |   |-- jupyter-live-kernel\
|   |   |   |-- read-xlsx\
|   |   |   `-- DESCRIPTION.md
|   |   |-- devops\
|   |   |   |-- chat-history-extraction\
|   |   |   |-- check-ngrok-status\
|   |   |   |-- codex-docs-update\
|   |   |   |-- fish-doc-extractor-tunnel-setup\
|   |   |   |-- hermes-tool-access-patterns\
|   |   |   |-- local-drive-access\
|   |   |   |-- local-file-access\
|   |   |   |-- ngrok-tunnel\
|   |   |   |-- tunnel-local-server\
|   |   |   `-- webhook-subscriptions\
|   |   |-- diagramming\
|   |   |   `-- DESCRIPTION.md
|   |   |-- dogfood\
|   |   |   |-- references\
|   |   |   |-- templates\
|   |   |   `-- SKILL.md
|   |   |-- domain\
|   |   |   `-- DESCRIPTION.md
|   |   |-- email\
|   |   |   |-- himalaya\
|   |   |   `-- DESCRIPTION.md
|   |   |-- feeds\
|   |   |   `-- DESCRIPTION.md
|   |   |-- find-ngrok\
|   |   |   |-- scripts\
|   |   |   `-- SKILL.md
|   |   |-- gaming\
|   |   |   |-- minecraft-modpack-server\
|   |   |   |-- pokemon-player\
|   |   |   `-- DESCRIPTION.md
|   |   |-- gifs\
|   |   |   `-- DESCRIPTION.md
|   |   |-- github\
|   |   |   |-- codebase-inspection\
|   |   |   |-- github-auth\
|   |   |   |-- github-code-review\
|   |   |   |-- github-issues\
|   |   |   |-- github-pr-workflow\
|   |   |   |-- github-repo-management\
|   |   |   `-- DESCRIPTION.md
|   |   |-- inference-sh\
|   |   |   |-- cli\
|   |   |   `-- DESCRIPTION.md
|   |   |-- leisure\
|   |   |   `-- find-nearby\
|   |   |-- mcp\
|   |   |   |-- mcporter\
|   |   |   |-- native-mcp\
|   |   |   `-- DESCRIPTION.md
|   |   |-- media\
|   |   |   |-- gif-search\
|   |   |   |-- heartmula\
|   |   |   |-- songsee\
|   |   |   |-- youtube-content\
|   |   |   `-- DESCRIPTION.md
|   |   |-- messaging\
|   |   |   |-- telegram\
|   |   |   `-- telegram-ai-bridge\
|   |   |-- mlops\
|   |   |   |-- cloud\
|   |   |   |-- evaluation\
|   |   |   |-- huggingface-hub\
|   |   |   |-- inference\
|   |   |   |-- models\
|   |   |   |-- research\
|   |   |   |-- training\
|   |   |   |-- vector-databases\
|   |   |   `-- DESCRIPTION.md
|   |   |-- music-creation\
|   |   |   `-- DESCRIPTION.md
|   |   |-- note-taking\
|   |   |   |-- obsidian\
|   |   |   `-- DESCRIPTION.md
|   |   |-- productivity\
|   |   |   |-- google-workspace\
|   |   |   |-- linear\
|   |   |   |-- nano-pdf\
|   |   |   |-- notion\
|   |   |   |-- ocr-and-documents\
|   |   |   |-- powerpoint\
|   |   |   `-- DESCRIPTION.md
|   |   |-- red-teaming\
|   |   |   `-- godmode\
|   |   |-- research\
|   |   |   |-- arxiv\
|   |   |   |-- blogwatcher\
|   |   |   |-- domain-intel\
|   |   |   |-- duckduckgo-search\
|   |   |   |-- llm-wiki\
|   |   |   |-- ml-paper-writing\
|   |   |   |-- parallel-cli\
|   |   |   |-- polymarket\
|   |   |   |-- research-paper-writing\
|   |   |   `-- DESCRIPTION.md
|   |   |-- smart-home\
|   |   |   |-- openhue\
|   |   |   `-- DESCRIPTION.md
|   |   |-- social-media\
|   |   |   |-- xitter\
|   |   |   `-- DESCRIPTION.md
|   |   |-- software-development\
|   |   |   |-- code-review\
|   |   |   |-- plan\
|   |   |   |-- requesting-code-review\
|   |   |   |-- subagent-driven-development\
|   |   |   |-- systematic-debugging\
|   |   |   |-- test-driven-development\
|   |   |   `-- writing-plans\
|   |   `-- .bundled_manifest
|   |-- .env
|   |-- .skills_prompt_snapshot.json
|   |-- auth.lock
|   |-- channel_directory.json
|   |-- config.yaml
|   |-- gateway.pid
|   |-- gateway_state.json
|   |-- models_dev_cache.json
|   |-- processes.json
|   |-- response_store.db
|   |-- response_store.db-shm
|   |-- response_store.db-wal
|   |-- SOUL.md
|   |-- state.db
|   |-- state.db-shm
|   `-- state.db-wal
|-- workspace\
|   |-- devops\
|   |   |-- local-file-access\
|   |   |   `-- SKILL.md
|   |   |-- tunnel-local-server\
|   |   |   `-- SKILL.md
|   |   `-- start-ngrok-tunnel.sh
|   |-- skills\
|   |   `-- realisticasia-api\
|   |       `-- SKILL.md
|   |-- check_emails.py
|   |-- DS NHÂN SỰ REALISTIC ASIA.xlsx
|   |-- image.png
|   |-- local_forwarder.py
|   `-- update_email.py
|-- docker-compose.yml
|-- docker-compose_2.yml
|-- Dockerfile
|-- local_forwarder.py
|-- structure.md
|-- telegram_token
`-- update_structure.py
```

Refresh with:

```powershell
python update_structure.py
```
