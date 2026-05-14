# Breadcrumb: Telegram polling auto-cleanup + docker restart fix
- **When:** 2026-05-04 ~09:00 UTC
- **What:** Added automatic pre-start cleanup to docker-compose.yml (curl-based setWebhook/deleteWebhook hook). Also fixed docker-restart.ps1 encoding issues ($var: → ${var}, ASCII replacements for emojis) and documented Codex forwarder sandbox limitations.
- **Action:** Modified docker-compose.yml gateway command, patched entrypoint.sh, rewrote docker-restart.ps1, updated docker-restart skill with sandbox limitations reference.
- **Status:** FAILED_TO_RESTART — Codex forwarder cannot access Docker (no admin privileges on Windows). User must run `docker compose down && docker compose up -d --force-recreate` in elevated PowerShell manually to activate the cleanup hook.
