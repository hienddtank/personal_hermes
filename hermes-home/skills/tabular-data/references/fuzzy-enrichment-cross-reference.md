# Fuzzy Enrichment Cross-Reference with fuzzywuzzy

When cross-referencing records between datasets where company names and contact names have variations (typos, abbreviations, suffixes), use `fuzzywuzzy` with `python-Levenshtein` for significantly better matching than `difflib`.

## Install
```bash
pip install fuzzywuzzy python-Levenshtein
```

## Core Pattern: Multi-Strategy Matching

```python
from fuzzywuzzy import fuzz
import pandas as pd

def normalize(s):
    """Lowercase, strip whitespace, remove common business suffixes."""
    if pd.isna(s): return ''
    s = str(s).lower().strip()
    for suf in [' ltd', ' pte', ' pte ltd', ' inc', ' corp', ' group',
                ' travel', ' tours', ' llc', ' plc', ' ag', ' gmbh']:
        s = s.replace(suf, '')
    return s.strip()

def match_company(company, target_df, company_col, top_n=3):
    """Fuzzy match a company name against a dataframe column."""
    norm = normalize(company)
    if not norm: return []
    
    candidates = target_df[target_df[company_col].notna()][company_col].apply(normalize)
    candidates = candidates[candidates != '']
    
    scores = [(i, fuzz.ratio(norm, c)) for i, c in candidates.items()]
    scores.sort(key=lambda x: x[1], reverse=True)
    
    return [(target_df.iloc[idx].to_dict(), score) for idx, score in scores[:top_n] if score >= 70]
```

## Recommended Thresholds (travel industry data)

| Match Type | Threshold | Rationale |
|---|---|---|
| Company name (fuzz.ratio) | ≥ 70% | Allows for suffixes, abbreviations, regional variations |
| Contact name (fuzz.ratio) | ≥ 85% | Names need higher confidence to avoid false positives |
| Exact match | 100% | Keep as separate category for user transparency |

## Enrichment Workflow (3-source merge)

For the pattern "enrich buyers list using Exhibitions DB + Host Agencies DB":

1. **Primary match**: Company name → Exhibitions Full Database (company column)
2. **Secondary match**: Buyer name → Exhibitions Contact Name (name-only fallback, score ≥ 85)
3. **Cross-reference**: If exhibition record has "Host Agency" field, look up that agency in Host Agencies list for additional emails
4. **Direct host match**: If no exhibition match, try buyer company against Host Agencies directly

```python
# Report per-category, never silently combine
print(f"Company matches: {(df['match'] == 'Yes').sum()}")
print(f"Name-only matches: {(df['match'] == 'Name only').sum()}")
print(f"No match: {(df['match'] == 'No').sum()}")
```

## Performance

For ~800 buyers × ~3200 exhibition records: fuzzywuzzy completes in seconds. For larger datasets (>10K × 50K), consider building a FAISS index or using `rapidfuzz` instead.

## Session Example: ILTM Asia Pacific 2026 (2026-05-12)

- **Sources**: `all_buyers_clean.csv` (781 buyers), `Exhibitions.xlsx` Full Database (3204 contacts, 1065 emails), `Host Agencies list.xlsx` List of Host (138 agencies, 22 emails), Preferred Host Agency sheet (105 individual advisor contacts)
- **Result**: 370 company matches + 14 name-only from Exhibitions → 375 emails (48%); then 24 additional emails from Preferred Host domain matching → 399 total (51%)
- **Pattern discovered**: Exhibition sheets often have the matched buyer's company linked to a "Host Agency" field — cross-referencing that against the Host Agencies sheet can yield additional contact info even for non-exhibition buyers
- **Pattern discovered**: The Preferred Host Agency sheet was a **contact directory** (individuals with emails like `kody@preferrednaples.com`, `Allison@landmark-travel.com`), not a company list — no Company column populated. Extracted domains from emails, matched domain keywords against buyer company names → 24 additional matches (all from Landmark Travel / Anchors Away / Preferred Travel domains). Generic email providers (gmail, yahoo) are noise — filter them out.

## Post-Enrichment Quality Metrics

After enrichment, always report coverage broken down by match status:

```python
matched = df[df['match'].isin(['Yes', 'Name only'])]
unmatched = df[~df['match'].isin(['Yes', 'Name only'])]

for label, subset in [("MATCHED", matched), ("UNMATCHED", unmatched)]:
    has_email = subset['email'].notna().sum()
    has_linkedin = subset['linkedin'].notna().sum()
    print(f"\n{label} ({len(subset)}):")
    print(f"  Email: {has_email}/{len(subset)} ({has_email/len(subset)*100:.0f}%)")
    print(f"  LinkedIn: {has_linkedin}/{len(subset)} ({has_linkedin/len(subset)*100:.0f}%)")
```

**What the user typically asks:** "What % of matched have emails?" — Report per group (matched vs unmatched), not just total.

## Extracting Matched List for Export

When user wants the list of matched records with source attribution:

```python
matched_mask = df['exhib_match'].isin(['Yes', 'Name only']) | df['pref_host_match'].notna()
matched = df[matched_mask].copy()
# Add match_source column
def match_source(row):
    sources = []
    if row.get('exhib_match') in ['Yes', 'Name only']:
        sources.append('Exhibition')
    val = str(row.get('pref_host_match', '')).strip()
    if val and val.lower() not in ['nan', '']:
        sources.append('Preferred Host Agency')
    return '; '.join(sources)
matched['match_source'] = matched.apply(match_source, axis=1)
# Export clean list
matched[['buyer_name', 'buyer_company', 'match_source', 'email']].to_csv('matched.csv', index=False)
```

## NaN Handling in Boolean Masking

When filtering on columns that may contain NaN/empty string values:

```python
# ❌ FAILS — NaN is float, can't call .lower() or .strip() on float
pref_matched = df['col'].astype(str).str.strip().apply(lambda x: x.lower() != 'nan')

# ✅ Works — handle NaN at pandas level first
pref_matched = df['col'].notna() & (df['col'].astype(str).str.strip().str.lower() != 'nan')
```
