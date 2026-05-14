---
name: kanban
description: >
  Complete Kanban system for multi-agent workflows — orchestrator decomposition playbook,
  worker lifecycle, specialist roster, workspace handling, and common patterns.
  Covers the full lifecycle: plan → decompose → dispatch → execute → review → complete.
version: 2.0.0
metadata:
  hermes:
    tags: [kanban, multi-agent, orchestration, routing, workflow, decomposition]
    related_skills: [kanban-orchestrator, kanban-worker]
---

# Kanban — Multi-Agent Workflow System

> The **core 6-step worker lifecycle** (orient → work → heartbeat → block/complete) is auto-injected into every kanban process via the `KANBAN_GUIDANCE` system-prompt block. This skill is the complete playbook covering both orchestrator and worker roles.

## When to use Kanban (vs. `delegate_task` or direct answer)

Create Kanban tasks when **any** of these are true:

1. **Multiple specialists are needed.** Research + analysis + writing = three profiles.
2. **The work should survive a crash or restart.** Long-running, recurring, or important.
3. **The user might want to interject.** Human-in-the-loop at any step.
4. **Multiple subtasks can run in parallel.** Fan-out for speed.
5. **Review / iteration is expected.** A reviewer profile loops on drafter output.
6. **The audit trail matters.** Board rows persist in SQLite forever.

If *none* of those apply — it's a small one-shot reasoning task — use `delegate_task` or answer directly.

---

## ORCHESTRATOR — Decomposition Playbook

### The anti-temptation rules

- **Do not execute the work yourself.** Your restricted toolset usually doesn't even include terminal/file/code/web for implementation. If you find yourself "just fixing this quickly" — stop and create a task.
- **For any concrete task, create a Kanban task and assign it.** Every single time.
- **If no specialist fits, ask the user which profile to create.** Do not default to doing it yourself.
- **Decompose, route, and summarize — that's the whole job.**

### Standard specialist roster (convention)

| Profile | Does | Typical workspace |
|---|---|---|
| `researcher` | Reads sources, gathers facts, writes findings | `scratch` |
| `analyst` | Synthesizes, ranks, de-dupes. Consumes multiple researcher outputs | `scratch` |
| `writer` | Drafts prose in the user's voice | `scratch` or `dir:` into vault |
| `reviewer` | Reads output, leaves findings, gates approval | `scratch` |
| `backend-eng` | Writes server-side code | `worktree` |
| `frontend-eng` | Writes client-side code | `worktree` |
| `ops` | Runs scripts, manages services, deployments | `dir:` into ops repo |
| `pm` | Writes specs, acceptance criteria | `scratch` |

### Decomposition playbook

#### Step 1 — Understand the goal
Ask clarifying questions if the goal is ambiguous. Cheap to ask; expensive to spawn the wrong fleet.

#### Step 2 — Sketch the task graph
Before creating anything, draft the graph out loud. Example for "Analyze whether we should migrate to Postgres":

```
T1  researcher        research: Postgres cost vs current
T2  researcher        research: Postgres performance vs current
T3  analyst           synthesize migration recommendation       parents: T1, T2
T4  writer            draft decision memo                       parents: T3
```

Show this to the user. Let them correct it before you create anything.

#### Step 3 — Create tasks and link
```python
t1 = kanban_create(
    title="research: Postgres cost vs current",
    assignee="researcher",
    body="Compare estimated infrastructure costs, migration costs, and ongoing ops costs over a 3-year window.",
    tenant=os.environ.get("HERMES_TENANT"),
)["task_id"]

t2 = kanban_create(
    title="research: Postgres performance vs current",
    assignee="researcher",
    body="Compare query latency, throughput, and scaling characteristics at our expected data volume (~500GB, 10k QPS peak).",
)["task_id"]

t3 = kanban_create(
    title="synthesize migration recommendation",
    assignee="analyst",
    body="Read the findings from T1 (cost) and T2 (performance). Produce a 1-page recommendation.",
    parents=[t1, t2],
)["task_id"]

t4 = kanban_create(
    title="draft decision memo",
    assignee="writer",
    body="Turn the analyst's recommendation into a 2-page memo for the CTO.",
    parents=[t3],
)["task_id"]
```

`parents=[...]` gates promotion — children stay in `todo` until every parent reaches `done`, then auto-promote to `ready`.

#### Step 4 — Complete your own task
If you were spawned as a task yourself, mark it done with a summary:

```python
kanban_complete(
    summary="decomposed into T1-T4: 2 researchers parallel, 1 analyst, 1 writer",
    metadata={
        "task_graph": {
            "T1": {"assignee": "researcher", "parents": []},
            "T2": {"assignee": "researcher", "parents": []},
            "T3": {"assignee": "analyst", "parents": ["T1", "T2"]},
            "T4": {"assignee": "writer", "parents": ["T3"]},
        },
    },
)
```

#### Step 5 — Report back to the user
Tell them what you created in plain prose with task IDs and dependencies.

### Common patterns

- **Fan-out + fan-in**: N `researcher` tasks with no parents, one `analyst` task with all as parents.
- **Pipeline with gates**: `pm → backend-eng → reviewer`. Each stage's `parents=[previous_task]`.
- **Same-profile queue**: 50 tasks, all assigned to `translator`, no dependencies. Dispatcher serializes.
- **Human-in-the-loop**: Any task can `kanban_block()` to wait for input. Dispatcher respawns after `/unblock`.

### Orchestrator pitfalls

- **Reassignment vs. new task.** If a reviewer blocks with "needs changes," create a NEW task linked from the reviewer's task — don't re-run the same task.
- **Argument order for links.** `kanban_link(parent_id=..., child_id=...)` — parent first.
- **Don't pre-create the whole graph if shape depends on intermediate findings.** Let downstream orchestrators plan dynamically.
- **Tenant inheritance.** Pass `tenant=os.environ.get("HERMES_TENANT")` on every `kanban_create` call.

---

## WORKER — Lifecycle and Execution

> The 6-step lifecycle is auto-injected. This section covers deeper detail, good handoff shapes, retry diagnostics, and edge cases.

### Workspace handling

| Kind | What it is | How to work |
|---|---|---|
| `scratch` | Fresh tmp dir, yours alone | Read/write freely; GC'd when task archived. |
| `dir:<path>` | Shared persistent directory | Other runs will read what you write. Path is absolute. |
| `worktree` | Git worktree at resolved path | If `.git` doesn't exist, run `git worktree add <path> <branch>` first. Commit work here. |

### Tenant isolation

If `$HERMES_TENANT` is set, prefix memory entries with the tenant:
- Good: `business-a: Acme is our biggest customer`
- Bad (leaks): `Acme is our biggest customer`

### Good summary + metadata shapes

**Coding task:**
```python
kanban_complete(
    summary="shipped rate limiter — token bucket, keys on user_id with IP fallback, 14 tests pass",
    metadata={
        "changed_files": ["rate_limiter.py", "tests/test_rate_limiter.py"],
        "tests_run": 14,
        "tests_passed": 14,
        "decisions": ["user_id primary, IP fallback for unauthenticated requests"],
    },
)
```

**Research task:**
```python
kanban_complete(
    summary="3 competing libraries reviewed; vLLM wins on throughput",
    metadata={
        "sources_read": 12,
        "recommendation": "vLLM",
        "benchmarks": {"vllm": 1.0, "sglang": 0.87, "trtllm": 0.72},
    },
)
```

**Review task:**
```python
kanban_complete(
    summary="reviewed PR #123; 2 blocking issues found",
    metadata={
        "pr_number": 123,
        "findings": [
            {"severity": "critical", "file": "api/search.py", "line": 42, "issue": "raw SQL concat"},
        ],
        "approved": False,
    },
)
```

### Block reasons that get answered fast

Bad: `"stuck"` — the human has no context.
Good: one sentence naming the specific decision. Leave longer context as a comment.

```python
kanban_comment(
    task_id=os.environ["HERMES_KANBAN_TASK"],
    body="Full context: I have user IPs from Cloudflare headers but some users are behind NATs.",
)
kanban_block(reason="Rate limit key: IP (simple, NAT-unsafe) or user_id (requires auth)?")
```

### Heartbeats worth sending

Good: `"epoch 12/50, loss 0.31"`, `"scanned 1.2M/2.4M rows"`
Bad: `"still working"`, empty notes, sub-second intervals. Skip entirely for tasks under ~2 minutes.

### Retry scenarios

| Outcome | Meaning | What to do |
|---|---|---|
| `timed_out` | Hit `max_runtime_seconds` | Chunk the work or shorten it |
| `crashed` | OOM or segfault | Reduce memory footprint |
| `spawn_failed` | Profile config issue (missing credential, bad PATH) | `kanban_block` and ask human |
| `reclaimed` | Operator archived task | Check status carefully; may not need to run |
| `blocked` | Previous attempt blocked | Unblock comment should be in thread |

### Worker pitfalls

- **Task state can change between dispatch and startup.** Always `kanban_show` first. If `blocked` or `archived`, stop.
- **Workspace may have stale artifacts.** Especially `dir:` and `worktree` — read comment thread.
- **Don't rely on CLI in containers.** `hermes kanban <verb>` fails in containerized backends. Use `kanban_*` tools.
- **Don't call `delegate_task` as substitute for `kanban_create`.** `delegate_task` = short subtasks within YOUR run; `kanban_create` = cross-agent handoffs.

### Do NOT

- Modify files outside `$HERMES_KANBAN_WORKSPACE` unless the task says to.
- Create follow-up tasks assigned to yourself — assign to the right specialist.
- Complete a task you didn't actually finish. Block it instead.

### CLI fallback (for human operators and scripts)

| Tool | CLI equivalent |
|---|---|
| `kanban_show` | `hermes kanban show <id> --json` |
| `kanban_complete` | `hermes kanban complete <id> --summary "..." --metadata '{...}'` |
| `kanban_block` | `hermes kanban block <id> "reason"` |
| `kanban_create` | `hermes kanban create "title" --assignee <profile> [--parent <id>]` |

Use tools from inside an agent; CLI exists for the human at the terminal.