# Centroid vs Per-Dimension Correlation — Empirical Comparison

From session 2026-04-30: tested both approaches on MiniLM (384-dim) with 59 words across 8 categories.

## Results Summary

| Metric | Approach A (Centroid) | Approach B (Per-Dim Corr) |
|--------|----------------------|---------------------------|
| Max signal strength | **0.4881** direction magnitude | **r = 0.5649** per-dimension |
| Target word separation | Clean gradient: -0.29 to +0.45 | Scattered: no single dim captures all slurs |
| Interpretability | High — axis maps to real categories | Low — top dims are individual dimensions, hard to explain |
| External validation | Works: `cunt` = -0.16 (slur), `traitor` = +0.21 (neutral) | Fails: external words don't project meaningfully |

## Key Findings

1. **Centroid approach wins for nuanced concepts**: The directional semantic axis is not organized along any single embedding dimension. Individual dimensions capture only fragmentary signal (max r=0.56), but the COMBINED direction from category centroids captures the concept holistically.

2. **Per-dimension correlation finds noise**: Top correlated dimensions have moderate r values but represent fragmented aspects of the concept, not a unified axis. They work better for polarized binary concepts (positive↔negative sentiment) where one dimension genuinely encodes polarity.

3. **Different subtypes create sub-axes**: PCA on category centroids revealed:
   - PC1: clinical_referral vs everything else (0.26 variance)
   - PC2: race_slurs separate from others (0.21 variance)  
   - PC3: disability_slurs vs general derogatory (0.15 variance)
   
   This means "offensiveness" is not ONE axis — it's a constellation of related but distinct directions.

4. **Direction magnitude threshold**: Magnitude = 0.4881 was just under the 0.5 threshold for "strong axis." This reflects that offensiveness spans multiple subtypes rather than forming a clean single dimension. For stronger axes (like sentiment), expect magnitudes >0.7.

## When Per-Dimension Correlation Works Better

- Binary polarity: positive/negative sentiment words
- Formality gradient: academic vs slang vocabulary  
- Register differences: technical jargon vs everyday language
- Any concept where the model explicitly learned a dominant dimension during pretraining

## When Centroid Approach Wins

- Nuanced social concepts (offensiveness, bias, stereotyping)
- Multi-category contrasts (3+ categories with internal structure)
- Finding direction between specific pairs of concept clusters
- When you have labeled category members and want to discover the axis rather than assume one exists

## Session-Specific Empirical Data

### 2026-04-30 — Neutral→Slurs Axis

**Configuration**: 84 words across 9 categories, MiniLM (384-dim)
- Neutral/positive: person, individual, human, colleague, etc. (13 words)
- Slur subtypes: race (9), disability (5), sexuality (5) — 19 total slur words

**Result**: Direction magnitude = **0.4311** (moderate signal)
- Slightly lower than earlier runs (~0.49) — adding more word categories dilutes the single-axis signal further
- Confirms: "offensiveness" is a constellation of related but distinct directions, not one clean axis

### Why Magnitude Varies Across Runs

1. **More categories = weaker axis**: Each additional category (derogatory_general, vulgar, mild_friendly) pulls centroids away from each other, changing the neutral→slur vector
2. **Category size matters**: 5 words in disability_slurs vs 13 neutral words creates centroid bias toward the larger cluster
3. **Word selection within categories**: Different examples of "race slur" produce different embedding positions; the centroid is sensitive to which specific terms you include

**Recommendation**: For consistent results, use a fixed reference vocabulary and report magnitude alongside category counts. Magnitude alone is not comparable across different vocabularies.