# Staged Outreach Distribution

Split contacts across campaign stages with balanced tier representation — each stage gets proportional mix of small/medium/large agencies. No person appears in more than one stage.

## Pattern

Used when: distributing outreach targets across batches so each batch has similar agency-size composition (not all giants in stage 1, all smalls in the last).

### Step 1 — One contact per group

```python
from collections import defaultdict

agencies = defaultdict(list)  # host_agency_name -> [contact_rows]
# ... populate from CSV ...

def pick_contact(rows):
    """Prefer sales contacts, then new status, then random."""
    # Skip non-sales (col 32 = 'Non-Sales Position')
    sales = [r for r in rows if len(r) > 32 and r[32].strip().upper() != 'TRUE']
    pool = sales if sales else rows
    # Prefer BD Status = 'New' (col 10)
    new_pool = [r for r in pool if len(r) > 10 and r[10].strip().lower() == 'new']
    return random.choice(new_pool if new_pool else pool)

selected = []
for agency, rows in agencies.items():
    sz = len(rows)
    # Assign tier based on contact count
    tier = ('small' if sz <= 5 else 'medium' if sz <= 10 else
            'large' if sz <= 20 else 'xlarge' if sz <= 40 else 'giant')
    selected.append((agency, tier, pick_contact(rows)))
```

### Step 2 — Round-robin deal into stages (stratified)

Sort by tier, then deal round-robin. This ensures each stage gets proportional representation from every tier.

```python
TIER_ORDER = ['giant', 'xlarge', 'large', 'medium', 'small']
selected.sort(key=lambda x: TIER_ORDER.index(x[1]))

ITEMS_PER_STAGE = 40
n_stages = (len(selected) + ITEMS_PER_STAGE - 1) // ITEMS_PER_STAGE

stages = [[] for _ in range(n_stages)]
for idx, item in enumerate(selected):
    stages[idx % n_stages].append(item)
```

**Why round-robin after sorting by tier works:** Items are grouped [giant… giant, xlarge… xlarge, large… large, medium… medium, small… small]. Dealing mod N distributes each contiguous block across all stages, so stage 1 gets some giants, some xlarge, etc. — naturally balanced.

### Step 3 — Multi-sheet Excel output

```python
from openpyxl import Workbook
wb = Workbook()
wb.remove(wb.active)

for idx, stage in enumerate(stages):
    ws = wb.create_sheet(f"Stage {idx+1}")
    ws.append(header)
    for agency, tier, row in sorted(stage, key=lambda x: x[0]):
        padded = row[:len(header)] + [''] * max(0, len(header) - len(row))
        ws.append(padded)

wb.save('output.xlsx')
```

## Contact Selection Priority (B2B Campaign Data)

1. **Skip non-sales** — `Non-Sales Position` column = FALSE or empty
2. **Prefer "New" BD Status** — untouched targets before followed-up ones
3. **Random tiebreak** — when multiple qualify, pick randomly (avoids always choosing first alphabetically)

## Pitfalls

- **Don't group by Company Name for Virtuoso data** — Company Name (col 1) is often empty; Host Agency (col 3) is the correct grouping key. B2B campaign CSVs have: rows 0-2 = summary/percentages, row 3 = header.
- **Always pad rows** — some rows have fewer columns than the header. Use `row[:N] + [''] * max(0, N - len(row))`.
- **Don't forget `newline=''` in CSV writer** on Windows — prevents blank lines between rows.

---

## Frequency-Based Spacing (Alternative Pattern)

Used when: user wants each agency's contacts spread evenly across stages proportional to their size — large agencies get wide spacing, small agencies cluster naturally. Prevents spam triggers by ensuring no stage has multiple contacts from the same agency.

### Algorithm

For each agency with *k* members across *S* total stages:
- **Interval** = `round(S / k)` — how far apart each contact goes
- **Phase offset** — unique per agency within its size group, prevents same-size agencies from sharing identical slots
- **Slot i** = `(phase + (i+1) × interval) mod S + 1`

```python
from collections import defaultdict

# Phase: stagger agencies of the same size so they don't collide
size_groups = defaultdict(list)  # size -> [agency_names]
for name in sorted_names:
    size_groups[len(agencies[name])].append(name)

phase = {}
for sz, names in size_groups.items():
    interval = max(1, round(NUM_STAGES / sz))
    for idx, name in enumerate(names):
        # Spread phases evenly within the group
        phase[name] = idx * max(1, interval // len(names))

# Assign slots
final = {}  # name -> set of slot ids
for name in sorted_names:
    k = len(agencies[name])
    interval = max(1, round(NUM_STAGES / k))
    p = phase[name]
    targets = [((p + (i+1) * interval - 1) % NUM_STAGES) + 1 for i in range(k)]
    assigned = set()
    for t in targets:
        # Collision resolution: expand outward if slot taken by same agency
        placed = False
        for off in range(NUM_STAGES):
            candidates = [t - off, t + off] if off > 0 else [t]
            for c in candidates:
                cs = ((c - 1) % NUM_STAGES) + 1
                if name not in assigned:
                    assigned.add(cs)
                    placed = True
                    break
            if placed:
                break
    final[name] = assigned
```

### Choosing Number of Stages

| Goal | Formula | Result (687 contacts, 160 agencies) |
|------|---------|-------------------------------------|
| ~1 contact/stage (max spread) | S = N | 687 stages, avg 1.0/stage |
| ~2 contacts/stage | S = N / 2 | 344 stages, avg 2.0/stage |
| ~4 contacts/stage | S = N / 4 | 172 stages, avg 4.0/stage |

**Rule of thumb:** More stages = smoother distribution but more sheets. Fewer stages = bigger stage sizes but the spacing formula still ensures each agency is well-distributed. Start with `S = N` for the cleanest frequency behavior.

### Why Phase Offset Matters

Without phase offset, three agencies of size 25 all get interval=27 → identical slots [27, 54, 81...]. Phase offsets them by different amounts so their slots interleave rather than overlap:
- Agency A (phase 0): [27, 54, 81...]
- Agency B (phase 9): [36, 63, 90...]
- Agency C (phase 18): [6, 45, 72...]

### Collision Resolution Between Different Agencies

Multiple agencies CAN share a stage (that's expected and correct). The only constraint: **no agency appears twice in the same stage**. The collision check is `name not in assigned`, NOT `slot is empty`. When two agencies' intervals land on the same stage, both contacts go there — one from each agency.

### Pitfalls

- **Never use `round()` for interval when k > S** — results in interval=0. Always `max(1, round(S / k))`.
- **Phase offset must be unique per agency within its size group** — otherwise same-size agencies share identical slots → max stage sizes spike (e.g., 67 contacts in one stage).
- **Process largest agencies first** — sorted desc by size ensures they get clean slots before smaller agencies fill remaining space.
