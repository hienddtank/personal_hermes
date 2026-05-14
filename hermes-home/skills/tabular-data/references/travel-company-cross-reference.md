# Travel Industry Company Cross-Reference

## When to Use
Matching two travel-industry datasets (e.g., exhibition buyers vs. host agency list) where both are full of generic company names containing "Travel", "Luxury", "Adventures", etc.

## The Problem
Both datasets contain thousands of companies with identical keywords. Substring matching alone produces 90%+ false positives.

## Safe Matching Pipeline

### Step 1: Full Normalization (Stopwords + Tokenize)
```python
import re

STOPWORDS = {
    'travel', 'luxury', 'group', 'agency', 'adventures', 'tours',
    'tourism', 'vacations', 'studio', 'co', 'inc', 'llc', 'ltd',
    'corp', 'the', 'of', '&', 'international', 'global'
}

def normalize_company(name):
    if pd.isna(name) or str(name).strip() == '':
        return ''
    n = str(name).strip().lower()
    # Remove stopwords in longest-first order (prevents partial removal)
    for sw in sorted(STOPWORDS, key=len, reverse=True):
        n = re.sub(r'\b' + re.escape(sw) + r'\b', '', n)
    # Collapse whitespace
    return re.sub(r'[\s_.,\-/&]+', ' ', n).strip()

# Build normalized lookups
agency_keys = {normalize_company(c): name for c, name in agency_companies.items()}
buyer_keys  = {normalize_company(c): name for c, name in buyer_companies.items()}
exact_matches = set(agency_keys) & set(buyer_keys)
```

### Step 2: Safe Substring (Multi-Token Overlap)
Only consider substring matches where:
- Both names have ≥ 3 tokens after normalization  
- They share at least one non-stopword token
- The shorter string is a meaningful portion of the longer one

```python
def safe_substring_match(name_a, name_b):
    a_set = set(str(name_a).strip().lower().split()) - STOPWORDS
    b_set = set(str(name_b).strip().lower().split()) - STOPWORDS
    shared = a_set & b_set
    if not shared: return False
    a_str, b_str = ' '.join(sorted(a_set)), ' '.join(sorted(b_set))
    return len(a_str) <= len(b_str) and a_str in b_str
```

### Step 3: Multi-Strategy Matching Order
1. **Exact normalized** — highest confidence, no false positives
2. **Substring/token-overlap** — medium confidence, flag for review
3. **Never** raw substring on un-normalized names (e.g., "HE Travel" vs "Travel Bus")

### Step 4: Output Structure
```
EXACT MATCHES (score 5):
  Buyer: X @ Company A → Contact: Y (email) | BD Status: Z

PARTIAL/AMBIGUOUS (score 2-3, FLAGGED for review):
  Buyer: X @ "The Travel Bus Co" ≈ Agency: "HE Travel" → [REVIEW]

UNMATCHED (score 0):
  Total unique buyers not matched: NNN
```

### Step 5: Save Separately
- `MATCHED_buyers_to_agencies.csv` — high-confidence matches only
- `PARTIAL_MATCHES_review.csv` — ambiguous cases for manual review
- NEVER overwrite originals

## Common False Positive Patterns
| Pattern | Example | Why It Fails |
|---------|---------|-------------|
| Single keyword containment | "HE Travel" ↔ "The Travel Bus Co" | Both share "travel" |
| Brand vs parent company | "Luxury Travel Co" ↔ "Luxury Travel Group" | One is brand, other is umbrella |
| Abbreviation | "MTA - Mobile Travel Agents" ↔ "Mobile Travel" | Shortened form |

## When No Matches Are Found
Zero matches between travel datasets is **common and normal** — especially when:
- The buyer list comes from a trade show/exhibition (new prospects)
- The agency list is your existing CRM (different source/timeframe)
- Both lists use different naming conventions (e.g., "Travel Oytser India" vs "Oytser Travel")

In this case, treat all unmatched buyers as **new prospects** and proceed with outreach.
