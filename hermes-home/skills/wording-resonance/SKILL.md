---
name: wording-resonance
description: >
  Compare different wordings of the same message by projecting them onto discovered 
  semantic axes. Outputs a "semantic profile" showing how each variant lands across 
  dimensions like moral character, political freedom, natural/artificial, class status, etc.
  Used for predicting which wording will resonate differently with audiences.
---

# Wording Resonance Checker
Compare multiple text variants by projecting them onto discovered semantic axes and showing how they diverge.

## When to use
- User wants to compare alternative wordings (emails, headlines, marketing copy, political messages)
- Need to understand which "vibe" or tone each version carries
- Checking for potential controversies before publishing text
- A/B testing different phrasings of the same message

## Prerequisites
- Pre-discovered semantic axes from `embedding-axis-probing` skill (or manually defined)
- `fastembed` with `all-MiniLM-L6-v2` installed

## Step 1: Define the semantic axes
Each axis is defined by:
```python
{
    'name': 'Moral Character',
    'high_words': ['honest', 'kind', 'unfair', 'selfish', 'pure'],  # words at high end
    'low_words':  ['withered', 'refined', 'finite', 'decaying'],     # words at low end
}
```

See `embedding-axis-probing` skill for how to discover axes systematically.

## Step 2: Compute axis directions
For each axis, compute direction vector from word centroids:
```python
all_words = high_words + low_words
word_embeds = np.array(list(model.embed(all_words)))
high_centroid = mean(embeddings of high_words)
low_centroid = mean(embeddings of low_words)
axis_direction = (high_centroid - low_centroid) / norm(high_centroid - low_centroid)
```

## Step 3: Project each text variant
```python
text_embed = np.array(list(model.embed([text])))[0]
text_embed = text_embed / norm(text_embed)
scores = {}
for ax in axes:
    scores[ax['name']] = dot(text_embed, ax['direction'])
```

## Step 4: Output format
For each variant, show:
1. The text (truncated if long)
2. Bar chart of scores on each axis (positive = toward high_words, negative = toward low_words)
3. Highlight the 4 most extreme axes
4. Side-by-side comparison showing shifts between variants

## Key semantic axes to use by default
| Axis | HIGH end words | LOW end words | Interpretation |
|------|---------------|---------------|----------------|
| Moral Character | honest, kind, selfish, pure | withered, refined, decaying | virtue ↔ moral decay |
| Political Freedom | absolute, freedom, oppression, tyranny | contingent, cultured, elite | political structure ↔ constraint |
| Natural vs Artificial | organic, synthetic, manufactured | cold, bored, jealous | natural ↔ artificial/constructed |
| Power & Agency | primitive, create, oppression | hot, elite, generous | raw power ↔ social order |
| Growth vs Stagnation | grow, advance, expand, fertile | sad, withered, confused | growth ↔ decline |
| Social Class | elite, royal, aristocratic | peasant, commoner, plebeian | upper class ↔ working class |
| Cognitive Clarity | clear, rational, logical, objective | confused, obscure, chaotic | clarity ↔ confusion |
| Emotional Intensity | surprised, excited, angry, intense | calm, gentle, quiet, bored | high arousal ↔ low arousal |

## Pitfalls
- **fastembed returns generators**: Always use `np.array(list(model.embed(texts)))` — never `model.embed(texts)[0]`
- **Normalize text embeddings before projection**: L2-normalize to unit length first
- **Axes must be calibrated with real word sets**: Don't guess direction vectors; derive from actual word embeddings
- **Small differences (< 0.05) are noise**: Only report shifts that exceed ~0.05 on any axis

## Output files
- Text-based semantic profile tables (suitable for Telegram/terminal output)
- Optional PNG visualization of multi-axis bar charts