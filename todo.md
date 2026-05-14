# TODO — Hermes AgentMemory Integration

Goal: integrate `agentmemory` into the existing Hermes setup without breaking the current working Hermes folder.

Current assumption:

```text
Stable Hermes folder:
D:\mkt\python\hermes

Custom AgentMemory worktree:
D:\mkt\python\hermes-personal-agentmemory
```

Progress on branch `test-memory-agent-local`:

- [x] Stable Hermes folder protected with initial Git commit and `safe-before-agentmemory` tag.
- [x] Local `master` fast-forwarded to custom repo `origin/master`.
- [x] Custom AgentMemory branch created at `D:\mkt\python\hermes-personal-agentmemory` from `origin/master`.
- [x] AgentMemory updates cherry-picked onto branch `personal-hermes-agentmemory`.
- [x] AgentMemory server started and Windows health check verified.
- [x] Docker container access to `host.docker.internal:3111` verified.
- [x] AgentMemory MCP config merged without overwriting existing settings.
- [x] AgentMemory Hermes memory-provider plugin copied to `hermes-home/plugins/agentmemory`.
- [x] Docker Compose isolated under project `hermes-agentmemory` with container `hermes-agentmemory`.
- [x] Experimental Hermes API published on host port `18642`; stable `8642` is not used by this test stack.
- [x] Hermes image updated to install the `mcp` extra required by MCP stdio clients.
- [x] Missing `codebase-memory` MCP disabled only in the experimental config to avoid unrelated MCP startup errors.
- [x] Hermes memory provider reports `agentmemory` installed and available.
- [x] `hermes mcp test agentmemory` connects and discovers AgentMemory memory tools.
- [x] Hermes saved and recalled an AgentMemory test fact through the experimental API.
- [ ] Final merge path not done.

---

## 0. Rules for Hermes

- Do not modify the stable Hermes folder directly unless explicitly told.
- Work only inside the experimental folder:
  ```text
  D:\mkt\python\hermes-agentmemory
  ```
- Do not commit secrets, tokens, API keys, `.env` files, session files, logs, or local cache files.
- Before every major change, run:
  ```powershell
  git status
  ```
- After every successful step, commit a small checkpoint.
- If a command fails, stop and report the exact error.

---

## 1. Protect the current Hermes folder

```powershell

git repo for personal hermes: https://github.com/hienddtank/personal_hermes.git


cd D:\mkt\python\hermes
git status
```

If this is already a Git repository, continue.

If not a Git repository:

```powershell
cd D:\mkt\python\hermes
git init
```

Create or update `.gitignore` before committing.

Suggested `.gitignore` additions:

```gitignore
.env
*.env
*.key
*.pem
*.log
secrets/
tokens/
node_modules/
__pycache__/
*.pyc

hermes-home/cache/
hermes-home/logs/
hermes-home/tmp/
hermes-home/sessions/
hermes-home/workspace/
...
```

If `hermes-home/config.yaml` contains secrets, do not commit it.

Instead:

```powershell
Copy-Item hermes-home\config.yaml hermes-home\config.example.yaml
```

Then remove secret values from `config.example.yaml`.

Add this to `.gitignore` if needed:

```gitignore
hermes-home/config.yaml
```

Create safety commit:

```powershell
git add -A
git commit -m "Save current Hermes setup before AgentMemory integration"
git tag safe-before-agentmemory
```

---

## 2. Create experimental worktree

```powershell
cd D:\mkt\python\hermes
git worktree add D:\mkt\python\hermes-agentmemory -b hanh/hermes-agentmemory
```

Confirm:

```powershell
cd D:\mkt\python\hermes-agentmemory
git status
git branch
```

Expected branch:

```text
hanh/hermes-agentmemory
```

---

## 3. Start AgentMemory server on Windows host

Open a separate PowerShell window:

```powershell
npx -y @agentmemory/agentmemory
```

Do not close this window while testing.

Health check from Windows:

```powershell
curl http://localhost:3111/agentmemory/health
```

Expected result:

```json
{"status":"healthy"}
```

Viewer:

```text
http://localhost:3113
```

Checkpoint:

```powershell
cd D:\mkt\python\hermes-agentmemory
git status
git add -A
git commit -m "Prepare worktree for AgentMemory integration"
```

---

## 4. Test Docker container access to AgentMemory

From PowerShell:

```powershell
docker exec -it hermes-agent sh
```

Inside the Hermes container:

```sh
curl http://host.docker.internal:3111/agentmemory/health
```

Expected result:

```json
{"status":"healthy"}
```

If this fails, do not edit Hermes config yet.

Check:

```sh
ping host.docker.internal
```

Then exit:

```sh
exit
```

---

## 5. Add AgentMemory MCP config to Hermes

Edit:

```text
D:\mkt\python\hermes-agentmemory\hermes-home\config.yaml
```

Add or merge this section:

```yaml
mcp_servers:
  agentmemory:
    command: npx
    args: ["-y", "@agentmemory/mcp"]
    env:
      AGENTMEMORY_URL: "http://host.docker.internal:3111"

memory:
  provider: agentmemory
```

Important:

- Do not overwrite existing `mcp_servers`.
- If `mcp_servers` already exists, add `agentmemory` under it.
- If `memory` already exists, merge carefully.
- Keep existing model/provider/terminal settings unchanged.

Checkpoint:

```powershell
cd D:\mkt\python\hermes-agentmemory
git diff
git add -A
git commit -m "Add AgentMemory MCP configuration"
```

---

## 6. Point Docker Compose to the experimental folder

Find the Hermes service in `docker-compose.yml`.

Current stable volume may look like:

```yaml
volumes:
  - D:\mkt\python\hermes\hermes-home:/hermes-home
  - D:\mkt\python\hermes\workspace:/workspace
```

For the test setup, change it to:

```yaml
volumes:
  - D:\mkt\python\hermes-agentmemory\hermes-home:/hermes-home
  - D:\mkt\python\hermes-agentmemory\workspace:/workspace
```

If `workspace` does not exist:

```powershell
mkdir D:\mkt\python\hermes-agentmemory\workspace
```

Checkpoint:

```powershell
cd D:\mkt\python\hermes-agentmemory
git diff
git add -A
git commit -m "Point Hermes compose volumes to AgentMemory worktree"
```

---

## 7. Restart Hermes

From the folder that contains the active `docker-compose.yml`:

```powershell
docker compose up -d
```

or:

```powershell
docker compose restart hermes
```

Check logs:

```powershell
docker logs hermes-agent --tail 100
```

Look for:

```text
MCP
agentmemory
memory
```

If Hermes fails to start, save the logs and stop.

---

## 8. Test memory tools in Hermes

Ask Hermes:

```text
Use AgentMemory to remember: this Hermes instance is testing AgentMemory through MCP using host.docker.internal:3111.
```

Then ask:

```text
Search memory for how this Hermes instance connects to AgentMemory.
```

Expected result:

- Hermes can save memory.
- Hermes can search/retrieve that memory.
- No container networking error.
- No MCP command error.
- No Node/npx missing error.

Checkpoint:

```powershell
cd D:\mkt\python\hermes-agentmemory
git status
git add -A
git commit -m "Verify AgentMemory MCP save and recall"
```

---

## 9. Optional: install deeper Hermes plugin

Only do this after MCP works.

Clone AgentMemory source if not already cloned:

```powershell
cd D:\mkt\python
git clone https://github.com/rohitg00/agentmemory.git
```

Create plugins folder:

```powershell
mkdir D:\mkt\python\hermes-agentmemory\hermes-home\plugins -Force
```

Copy Hermes integration:

```powershell
Copy-Item `
  -Recurse `
  -Force `
  D:\mkt\python\agentmemory\integrations\hermes `
  D:\mkt\python\hermes-agentmemory\hermes-home\plugins\agentmemory
```

Restart Hermes:

```powershell
docker compose restart hermes
```

Check logs:

```powershell
docker logs hermes-agent --tail 150
```

Test again:

```text
Remember this as a plugin test: AgentMemory Hermes plugin is now enabled.
```

Then:

```text
Recall the AgentMemory Hermes plugin test.
```

Checkpoint:

```powershell
cd D:\mkt\python\hermes-agentmemory
git status
git add -A
git commit -m "Add AgentMemory Hermes plugin"
```

---

## 10. Rollback plan

Return to stable Hermes folder:

```powershell
cd D:\mkt\python\hermes
```

If Docker Compose was modified in the stable folder, restore the old volume paths:

```yaml
volumes:
  - D:\mkt\python\hermes\hermes-home:/hermes-home
  - D:\mkt\python\hermes\workspace:/workspace
```

Restart:

```powershell
docker compose up -d
```

If needed, hard reset experimental branch only:

```powershell
cd D:\mkt\python\hermes-agentmemory
git reset --hard safe-before-agentmemory
```

Do not run reset on the stable folder unless explicitly intended.

---

## 11. Success criteria

AgentMemory integration is considered successful only if all are true:

- `curl http://localhost:3111/agentmemory/health` works from Windows.
- `curl http://host.docker.internal:3111/agentmemory/health` works from inside Hermes container.
- Hermes starts without MCP errors.
- Hermes can save a memory.
- Hermes can search and recall that memory.
- Existing Hermes tools still work.
- Existing model provider config still works.
- No secrets were committed.
- Stable Hermes folder still works independently.

---

## 12. Final merge path

After successful testing:

```powershell
cd D:\mkt\python\hermes
git checkout hanh/local-custom
git merge hanh/hermes-agentmemory
```

If `hanh/local-custom` does not exist yet:

```powershell
git checkout -b hanh/local-custom
git merge hanh/hermes-agentmemory
```

Do not merge into `master` or `main` until the integration is stable for several sessions.

---

## 13. Notes for future maintenance

Recommended branch structure:

```text
master/main
  clean baseline

hanh/local-custom
  long-term personal Hermes version

hanh/hermes-agentmemory
  temporary integration branch
```

Recommended commit style:

```text
Save current Hermes setup before AgentMemory
Add AgentMemory MCP configuration
Verify AgentMemory MCP save and recall
Add AgentMemory Hermes plugin
Fix Docker host networking for AgentMemory
Clean config example and ignore local secrets
```

Recommended testing prompts:

```text
Remember that this Hermes setup uses AgentMemory through MCP.
```

```text
Search memory for the AgentMemory MCP setup.
```

```text
Summarize what you remember about this Hermes installation.
```

```text
What memory provider are you using?
```
