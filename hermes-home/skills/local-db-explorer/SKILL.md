---
name: local-db-explorer
description: "Explore any local SQLite database — schema inspection, data browsing, and ad-hoc queries. Covers codebase-memory-mcp knowledge graphs (nodes/edges) and general-purpose SQLite databases."
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [sqlite, database, exploration, codebase-memory, knowledge-graph]
---

# Local DB Explorer

Explore SQLite databases on disk — schema introspection, data browsing, cross-table analysis, and codebase knowledge graphs.

## When to Use

- Inspecting any `.db`, `.sqlite`, or `.sqlite3` file on disk
- Exploring codebase-memory-mcp databases (knowledge graphs of indexed codebases)
- Understanding database schema, relationships, and data distributions
- Finding specific records, patterns, or anomalies in local databases

## Quick Reference

```python
# Python sqlite3 (always available, no install needed)
import sqlite3
conn = sqlite3.connect('/path/to/database.db')
cursor = conn.cursor()

# List all tables
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
tables = [r[0] for r in cursor.fetchall()]

# Row counts per table
for t in tables:
    cursor.execute(f"SELECT COUNT(*) FROM [{t}]")
    print(f"{t}: {cursor.fetchone()[0]} rows")

# Schema for a table
cursor.execute(f"PRAGMA table_info([{table_name}])")
for col in cursor.fetchall():
    # (cid, name, type, notnull, dflt_value, pk)
    print(f"  {col[1]} ({col[2]}) {'PK' if col[5] else ''}")

# Sample rows
cursor.execute(f"SELECT * FROM [{table_name}] LIMIT 5")
for row in cursor.fetchall():
    print(row)

conn.close()
```

## Codebase-Memory-MCP Databases

### Location

Codebase-memory-mcp stores indexed databases at:
```
~/.cache/codebase-memory-mcp/<project-name>.db
```

The project name is derived from the directory path (slashes replaced with dashes, leading dash removed). E.g., `/opt/hermes-agent` → `opt-hermes-agent.db`.

Override with `CBM_CACHE_DIR` env var.

### Schema (codebase-memory-mcp v0.6.1+)

**nodes** table — Every symbol/entity in the codebase:
| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER PK | Unique node ID |
| project | TEXT | Project identifier |
| label | TEXT | Node type: Function, Method, Class, File, Module, Route, Interface, Type, Variable, Section, Folder, Project, Enum |
| name | TEXT | Symbol name |
| qualified_name | TEXT | Fully qualified name (e.g., `project.module.Class.method`) |
| file_path | TEXT | Source file path (empty for abstract nodes) |
| start_line | INTEGER | First line in source file |
| end_line | INTEGER | Last line in source file |
| properties | TEXT | JSON string with extra metadata |

**edges** table — Relationships between nodes:
| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER PK | Unique edge ID |
| project | TEXT | Project identifier |
| source_id | INTEGER | Source node ID |
| target_id | INTEGER | Target node ID |
| type | TEXT | Edge type (see below) |
| properties | TEXT | JSON metadata |

**Edge types:** DEFINES, CALLS, USAGE, TESTS, DEFINES_METHOD, WRITES, CONTAINS_FILE, IMPORTS, SIMILAR_TO, CONTAINS_FOLDER, HTTP_CALLS, CONFIGURES, SEMANTICALLY_RELATED, HANDLES, RAISES, DECORATES, ASYNC_CALLS, THROWS, TESTS_FILE

**Other tables:**
- `file_hashes` — File integrity hashes for incremental updates
- `node_vectors` / `token_vectors` — Embedding vectors for semantic search
- `nodes_fts*` — FTS5 full-text search tables
- `projects` — Project metadata

### Common Queries

#### Find all functions calling a specific method

```python
cursor.execute("""
    SELECT n.name, n.qualified_name, n.file_path, n.start_line
    FROM edges e
    JOIN nodes n ON e.source_id = n.id
    JOIN nodes target ON e.target_id = target.id
    WHERE e.type = 'CALLS'
      AND target.name = 'run_conversation'
    ORDER BY n.file_path
""")
```

#### Find what a function calls (outgoing calls)

```python
cursor.execute("""
    SELECT n.name, n.qualified_name, e.type
    FROM edges e
    JOIN nodes n ON e.target_id = n.id
    WHERE e.source_id = ?
      AND e.type IN ('CALLS', 'USAGE', 'IMPORTS')
""", (node_id,))
```

#### Top N most-connected functions (call graph centrality)

```python
cursor.execute("""
    SELECT n.name, n.qualified_name, n.file_path,
           (SELECT COUNT(*) FROM edges WHERE source_id = n.id OR target_id = n.id) AS degree
    FROM nodes n
    WHERE n.label IN ('Function', 'Method')
    ORDER BY degree DESC
    LIMIT 10
""")
```

#### Find dead code (functions/methods with no callers)

```python
cursor.execute("""
    SELECT n.name, n.qualified_name, n.file_path
    FROM nodes n
    WHERE n.label IN ('Function', 'Method')
      AND n.id NOT IN (
        SELECT e.source_id FROM edges e
        WHERE e.type IN ('CALLS', 'USAGE')
      )
      AND n.qualified_name NOT LIKE '%main%'
      AND n.qualified_name NOT LIKE '%test%'
    LIMIT 20
""")
```

#### Explore a file's contents (all symbols defined in a file)

```python
cursor.execute("""
    SELECT n.label, n.name, n.start_line, n.end_line
    FROM nodes n
    WHERE n.file_path = ?
    ORDER BY n.start_line
""", ("run_agent.py",))
```

#### Trace a call chain (BFS from a function)

```python
def trace_calls(cursor, start_name, max_depth=3):
    cursor.execute("SELECT id FROM nodes WHERE name = ? AND label IN ('Function','Method')", (start_name,))
    start_id = cursor.fetchone()
    if not start_id:
        return []
    
    result = []
    current_level = [start_id[0]]
    
    for depth in range(max_depth):
        next_level = []
        for nid in current_level:
            cursor.execute("""
                SELECT DISTINCT n.id, n.name, e.type
                FROM edges e
                JOIN nodes n ON e.target_id = n.id
                WHERE e.source_id = ? AND e.type = 'CALLS'
            """, (nid,))
            for child_id, child_name, etype in cursor.fetchall():
                result.append((depth + 1, child_name, etype))
                next_level.append(child_id)
        current_level = next_level[:50]  # limit breadth
    return result
```

#### Module dependency graph

```python
cursor.execute("""
    SELECT src.file_path AS from_file, tgt.file_path AS to_file,
           COUNT(*) AS calls
    FROM edges e
    JOIN nodes src ON e.source_id = src.id
    JOIN nodes tgt ON e.target_id = tgt.id
    WHERE e.type = 'CALLS'
      AND src.file_path != '' AND tgt.file_path != ''
    GROUP BY src.file_path, tgt.file_path
    HAVING calls > 3
    ORDER BY calls DESC
    LIMIT 20
""")
```

### Indexing a Codebase

```bash
# Via CLI
codebase-memory-mcp cli index_repository '{"repo_path":"/path/to/project"}'

# Via MCP tool (when Hermes has the MCP server connected)
# Use mcp_codebase_memory_index_repository with repo_path parameter

# Check status
codebase-memory-mcp cli index_status '{"project":"project-name"}'

# List indexed projects
codebase-memory-mcp cli list_projects '{}'
```

### Using MCP Tools

When the `codebase-memory` MCP server is connected, these tools are available:

| Tool | Description |
|------|-------------|
| `mcp_codebase_memory_index_repository` | Index a codebase |
| `mcp_codebase_memory_search_graph` | Semantic/BM25 search across the knowledge graph |
| `mcp_codebase_memory_query_graph` | Cypher-like graph queries |
| `mcp_codebase_memory_trace_path` | Trace call paths |
| `mcp_codebase_memory_get_code_snippet` | Get source code for a symbol |
| `mcp_codebase_memory_get_architecture` | Architecture overview |
| `mcp_codebase_memory_get_graph_schema` | Schema introspection |
| `mcp_codebase_memory_search_code` | Regex/code search |
| `mcp_codebase_memory_list_projects` | List indexed projects |
| `mcp_codebase_memory_detect_changes` | Detect uncommitted changes |
| `mcp_codebase_memory_manage_adr` | Architecture Decision Records |
| `mcp_codebase_memory_ingest_traces` | Ingest execution traces |

## General SQLite Exploration Patterns

### Find foreign key relationships

```python
cursor.execute("""
    SELECT m.name AS table_name, p.from, p.to, p.on_update, p.on_delete
    FROM pragma_foreign_key_list(?) AS p
    JOIN sqlite_master m ON m.name = p."table"
""", (table_name,))
```

Or iterate all tables:
```python
for t in tables:
    cursor.execute(f"PRAGMA foreign_key_list([{t}])")
    fks = cursor.fetchall()
    if fks:
        for fk in fks:
            print(f"  {t}.{fk[3]} → {fk[2]}.{fk[4]}")
```

### Quick data profiling

```python
for t in tables:
    cursor.execute(f"PRAGMA table_info([{t}])")
    cols = cursor.fetchall()
    print(f"\n=== {t} ({len(cols)} columns) ===")
    for col in cols:
        col_name = col[1]
        col_type = col[2]
        # Non-null count
        cursor.execute(f"SELECT COUNT(*) FROM [{t}] WHERE [{col_name}] IS NOT NULL")
        nn = cursor.fetchone()[0]
        # Distinct values (sample for large tables)
        cursor.execute(f"SELECT COUNT(DISTINCT [{col_name}]) FROM (SELECT [{col_name}] FROM [{t}] LIMIT 10000)")
        dv = cursor.fetchone()[0]
        print(f"  {col_name:30s} {col_type:10s} nn={nn} distinct={dv}")
```

### Search for text across all tables

```python
def search_all_tables(cursor, search_term, tables):
    results = []
    for t in tables:
        cursor.execute(f"PRAGMA table_info([{t}])")
        text_cols = [c[1] for c in cursor.fetchall() if c[2] in ('TEXT', 'VARCHAR', 'CLOB', '')]
        for col in text_cols:
            cursor.execute(f"SELECT * FROM [{t}] WHERE [{col}] LIKE ? LIMIT 5", (f"%{search_term}%",))
            rows = cursor.fetchall()
            if rows:
                results.append((t, col, len(rows), rows[0]))
    return results
```

### Export table to CSV

```python
import csv
cursor.execute(f"SELECT * FROM [{table_name}]")
with open(f'{table_name}.csv', 'w', newline='') as f:
    writer = csv.writer(f)
    writer.writerow([desc[0] for desc in cursor.description])
    writer.writerows(cursor.fetchall())
```

## Finding SQLite Databases on Disk

```bash
# Find .db files
find /path/to/search -name "*.db" -o -name "*.sqlite" -o -name "*.sqlite3" 2>/dev/null

# Find by content (SQLite files start with "SQLite format 3")
find /path/to/search -type f -exec grep -l "SQLite format 3" {} \; 2>/dev/null

# Common locations
ls ~/.cache/*/
ls /var/lib/*/
ls ~/Downloads/*.db 2>/dev/null
```

## Pitfalls

- **Large tables**: Always `LIMIT` your queries. Tables like `edges` in codebase-memory-mcp can have 100K+ rows.
- **FTS tables**: Don't query `nodes_fts`, `nodes_fts_data`, etc. directly — they're internal FTS5 implementation details. Use the main `nodes` table or the MCP search tools.
- **Properties column**: Stored as JSON strings. Parse with `json.loads()` in Python.
- **Connection mode**: Use `sqlite3.connect()` (read-only by default). For explicit read-only: `sqlite3.connect('file:path?mode=ro', uri=True)`.
- **Concurrent access**: SQLite locks on writes. Multiple readers are fine. Use `check_same_thread=False` only if sharing connections across threads (rarely needed).
