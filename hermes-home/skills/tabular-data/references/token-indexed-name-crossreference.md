# Token-Indexed Name Cross-Reference

Cross-referencing buyer names against tens of thousands of contacts across multiple sheets/databases. Solves the O(n×m) nested-loop timeout problem.

## Problem

Matching 781 buyer names against 30,667 contacts (Exhibitions + 30 Host Agency sheets) via nested loops times out at 600s. Row-by-row `iterrows()` over 25M+ comparisons is not viable.

## Solution: Token Index

Build a reverse index from name tokens → normalized names → contact rows. Only compare candidates that share at least one token.

```python
from collections import defaultdict

def normalize_name(name):
    """Strip accents, lowercase, remove parenthetical suffixes"""
    if not isinstance(name, str) or not name.strip():
        return ''
    name = re.sub(r'\([^)]*\)', '', name).strip()  # Remove (KUZUMI) etc.
    name = unicodedata.normalize('NFKD', name.lower()).encode('ASCII', 'ignore').decode('ASCII')
    name = re.sub(r'[^\w\s]', '', name).strip()
    return re.sub(r'\s+', ' ', name)

# Build index: token -> set of normalized names
token_index = defaultdict(set)
for norm_name in all_normalized_names:
    for token in norm_name.split():
        if len(token) > 2:  # Skip short noise tokens
            token_index[token].add(norm_name)

# For each buyer, find candidates via shared tokens
buyer_norm = normalize_name(buyer_name)
buyer_tokens = set(buyer_norm.split())
candidates = set()
for token in buyer_tokens:
    if token in token_index:
        candidates.update(token_index[token])

# Now compute overlap scores only for candidates
for cand in candidates:
    common = buyer_tokens & set(cand.split())
    total = buyer_tokens | set(cand.split())
    overlap = len(common) / len(total)
    if overlap >= 0.5 and len(common) >= 1:
        # This is a real match candidate — check company, email, etc.
```

## Name Similarity Scoring

| Score | Condition | Label |
|-------|-----------|-------|
| 100 | Normalized names identical | Exact Name |
| 85+ | One name fully contains the other | Close Name (substring) |
| 70-95 | Token overlap ≥ 70%, ≥ 2 shared tokens | Close Name (multi-token) |
| 80+ | Token overlap ≥ 50%, ≥ 1 shared token | Fuzzy Name |

## Company Matching

```python
def company_similarity(c1, c2):
    n1, n2 = str(c1).strip().lower(), str(c2).strip().lower()
    if n1 == n2:
        return 100, True  # (score, is_exact)
    if len(n1) >= 3 and len(n2) >= 3 and (n1 in n2 or n2 in n1):
        return int(min(len(n1), len(n2)) / max(len(n1), len(n2)) * 100), False
    return 0, False
```

## Multi-Sheet Excel Aggregation

When loading contacts from 30+ sheets with varying structures:

```python
host_xl = pd.ExcelFile('Host Agencies list.xlsx')
skip_sheets = {'Follow Up List', 'Newsletter', 'List of Host'}  # Summary-only sheets
frames = []
for sheet in host_xl.sheet_names:
    if sheet in skip_sheets:
        continue
    df = pd.read_excel(host_xl, sheet_name=sheet, header=3)
    df.columns = [str(c).strip() for c in df.columns]
    
    # Flexible column detection
    name_col = next((c for c in df.columns if 'contact' in str(c).lower() and 'name' in str(c).lower()), None)
    name_col = name_col or next((c for c in df.columns if 'full name' in str(c).lower()), None)
    company_col = next((c for c in df.columns if 'company' in str(c).lower()), None)
    
    mapped = pd.DataFrame({
        'Contact Name': df[name_col] if name_col else '',
        'Company name': df[company_col] if company_col else '',
        'Email 1': df.get('Email 1', ''),
        '_source': sheet
    })
    frames.append(mapped)

contacts = pd.concat(frames, ignore_index=True).reset_index(drop=True)
```

## Output Columns

- `Buyer Name` / `Buyer Company` — from ILTM buyer list
- `Matched Contact` — contact name from DB (or `(SAME)` if exact match)
- `Matched Company` — company from DB
- `Name Score` / `Company Score` — 0-100
- `Match Type` — Exact Name + Exact Company | Exact Name + Related Company | Close Name + Exact Company | Name only
- `Source` — which sheet/database the match came from
- `Email 1` / `Email 2` / `LinkedIn` — contact details

## Match Type Classification

- **Exact Name + Exact Company** (n=100, c=100): Confirmed same person, same company
- **Exact Name + Related Company** (n=100, c≥60): Same person, company name variant
- **Close Name + Exact Company** (n≥80, c=100): Fuzzy name at exact company
- **Name only** (n≥80, c<60): Person found but under a different company — highest interest for outreach (same person, new role)

## Performance

30K contacts × 781 buyers: ~5 seconds with token index vs timeout (>600s) with nested loops.
