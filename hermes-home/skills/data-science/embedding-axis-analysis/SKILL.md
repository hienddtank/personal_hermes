---
name: embedding-axis-analysis
description: Derive semantic axes from word/sentence embeddings — offensiveness, sentiment, formality, gender, and other directional dimensions in vector space. Uses centroid-comparison and PCA to find interpretable directions in 384-dim MiniLM or similar embedding spaces.
tags: [embedding, semantics, pca, direction-analysis, interpretability]
---

# Embedding Axis Analysis

Derive semantic axes from embedding vectors to understand what dimensions capture specific conceptual contrasts. Applied to FastEmbed MiniLM (384-dim), but generalizes to any fixed-dimension embedding model.

## Use Cases

- **Offensiveness/slur axis**: Find which directions separate offensive vs neutral language
- **Sentiment gradient**: Identify positive→negative polarity direction
- **Formality dimension**: Distinguish formal/clinical terms from casual/colloquial
- **Gender bias detection**: Similar to Bolukbasi et al. (2016) gender debiasing
- **Domain separation**: Separate technical vs layman terminology, or register differences

## When NOT to Use

- Small labeled sets (<5 per category) — axis will be noisy and underdetermined
- When categories have high intra-class variance (e.g., "friend" in romantic vs platonic contexts) — embeddings collapse contextual nuance
- If you need fine-grained per-word offsets rather than coarse centroid-level axes
- **Pejorative-within-category axes**: Don't compare "rich" vs "poor" when looking for insults ABOUT the rich. Pejective terms stay within their semantic cluster and shift toward power/distribution criticism (nepotism, nouveau riche, exploiter) — they don't cross to opposite economic status. If you want "slur version of X," define your comparison within the same semantic domain (wealth-positive vs wealth-negative connotations), not across domains.

## Step 1: Prepare Labeled Word Lists

Create at least 3 categories with 5+ words each:
- **Target category**: words expected to be extreme on the axis (e.g., slurs, clinical terms, slang)
- **Baseline category**: neutral/positive anchor words (general baseline)
- **Intermediate category** (optional): words in between (e.g., mild insults vs strong slurs)

Example for offensiveness axis:
```python
words = {
    "neutral_positive": ["person", "individual", "neighbor", "colleague", "citizen"],
    "mild_friendly":     ["buddy", "pal", "mate", "friend", "companion"],
    "derogatory_general":["idiot", "fool", "jerk", "loser", "weirdo"],
    "target_slurs":      ["slur_word_1", "slur_word_2", ...],  # 5+ minimum
    "clinical_referral": ["formal_equivalent_1", ...],          # anti-slur clinical terms
}
```

## Step 2: Embed and Normalize

Use FastEmbed to get normalized embeddings (cosine-ready):

```python
from fastembed import TextEmbedding
import numpy as np

model = TextEmbedding(model_name="sentence-transformers/all-MiniLM-L6-v2")
all_text = []
text_to_cat = {}
for cat, terms in words.items():
    for t in terms:
        all_text.append(t)
        text_to_cat[t] = cat

embeddings = np.stack(list(model.embed(all_text))).astype(np.float64)
norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
embeddings_norm = embeddings / norms  # L2-normalized for cosine similarity
```

## Step 3: Derive the Axis (Two Approaches)

### Approach A — Centroid Direction (RECOMMENDED)

More robust than per-dimension correlation. Computes category centroids and takes their difference:

```python
def compute_centroids(texts, cats, vecs):
    centroids = {}
    for cat in set(cats.values()):
        indices = [i for i, t in enumerate(texts) if cats[t] == cat]
        centroids[cat] = np.mean(vecs[indices], axis=0)
    return centroids

centroids = compute_centroids(all_text, text_to_cat, embeddings_norm)

# Direction from neutral → target
target_centroid = np.mean([centroids[c] for c in ["race_slurs", "disability_slurs", "sexuality_slurs"]], axis=0)
neutral_centroid = np.mean([centroids[c] for c in ["neutral_positive", "clinical_referral"]], axis=0)

raw_direction = target_centroid - neutral_centroid
slur_axis = raw_direction / np.linalg.norm(raw_direction)  # unit vector

# Normalize convention: higher projection = more positive/neutral, lower = more target-like
slur_axis = -(target_centroid - neutral_centroid) / np.linalg.norm(target_centroid - neutral_centroid)
```

**Interpretation**: Direction magnitude >0.5 indicates a strong semantic axis. Magnitude <0.1 means the concept is not organized as a single axis in this embedding space (likely distributed across multiple dimensions).

### Approach B — Per-Dimension Correlation

Find individual dimensions correlated with a numeric label vector:

```python
labels = np.zeros(len(all_text))  # -2 for slurs, -1 for derogatory, 0 neutral, +1 clinical, +2 positive
for i, text in enumerate(all_text):
    cat = text_to_cat[text]
    if cat in ["race_slurs", "disability_slurs", "sexuality_slurs"]: labels[i] = -2.0
    elif cat == "derogatory_general": labels[i] = -1.0
    elif cat == "clinical_referral": labels[i] = +1.0
    elif cat in ["neutral_positive", "positive"]: labels[i] = +2.0

# Manual Pearson correlation (no scipy needed)
def pearson_r(a, b):
    mean_a, mean_b = np.mean(a), np.mean(b)
    num = np.sum((a - mean_a) * (b - mean_b))
    den = np.sqrt(np.sum((a - mean_a)**2) * np.sum((b - mean_b)**2))
    return num / den if den != 0 else 0.0

correlations = []
for i in range(embeddings_norm.shape[1]):
    corr = pearson_r(embeddings_norm[:, i], labels)
    correlations.append((i, abs(corr), corr))

correlations.sort(key=lambda x: x[1], reverse=True)
# Top dimensions with highest |r| are the most predictive
```

**Warning**: Per-dimension correlation often fails for nuanced concepts (max |r| rarely exceeds 0.5). Combined Approach A is preferred.

## Step 4: Project and Interpret

Project all words onto the derived axis:

```python
projections = embeddings_norm @ slur_axis
sorted_words = sorted(zip(all_text, projections), key=lambda x: x[1])

for word, proj in sorted_words:
    bar_len = int(abs(proj) * 40)
    # Visualize with bars or just print values
    print(f"{word}: {proj:.4f} [{text_to_cat[word]}]")
```

**Expected patterns**:
- Target words cluster at one extreme, neutral words at the other
- Clinical/referral terms may land near neutral (they are conceptually distinct from slurs)
- Mild/colloquial terms form a gradient between neutral and derogatory
- If target words scatter across the axis → no clean single-axis exists for this concept

## Step 5: Validate with External Words

Test the axis on unseen words to check generalization:

```python
test_words = ["word1", "word2", ...]  # not in training set
test_vecs = np.stack(list(model.embed(test_words))).astype(np.float64)
test_vecs_norm = test_vecs / np.linalg.norm(test_vecs, axis=1, keepdims=True)
test_projs = test_vecs_norm @ slur_axis
```

If test words with known offensiveness align with the axis direction, the axis is validated. If they scatter randomly, the axis captures dataset-specific noise rather than a general semantic dimension.

## Step 6: Axis Walk Visualization (RECOMMENDED for interpretation)

Walk along the derived axis and at each step find the nearest neighbors — reveals whether the axis produces meaningful, interpretable transitions or jumps abruptly between unrelated concepts.

```python
num_steps = 30
positions = np.linspace(-1.5, 3.0, num_steps)  # tune range to your data

step_data = []
for pos in positions:
    probe = neutral_centroid + pos * slur_axis
    
    # Normalize probe and find top-K nearest words
    probe_norm = probe / np.linalg.norm(probe)
    sims = embeddings_norm @ probe_norm
    top_k = np.argsort(sims)[::-1][:6]
    
    step_data.append({
        "position": pos,
        "top_words": [(all_text[i], float(sims[i]), text_to_cat[all_text[i]]) for i in top_k]
    })

# Print summary
for data in step_data:
    print(f"pos={data['position']:+.2f}:  {', '.join([w[0][:15] for w in data['top_words']])}")
```

**What to look for:**
- Smooth transition from neutral→mild→derogatory→slurs = axis is meaningful
- Abrupt jumps (neutral → unrelated slur with no intermediates) = the axis captures dataset noise, not a real semantic dimension
- Words from different categories clustering together = embedding space doesn't organize this concept linearly

**Rendering**: Use the `axis-walkthrough.py` template for animated visualization showing the walk in real-time. Convert output to MP4 via ffmpeg (GIFs often fail on Telegram):
```bash
ffmpeg -i input.gif -vf "fps=25,scale=1280:-1:flags=lanczos" -c:v libx264 -pix_fmt yuv420p output.mp4
# If height is odd, pad/scale first: scale=1280:1464 (round to even)
```

## Step 7: PCA on Centroids (Optional Deep Dive)

Run PCA on category centroids to discover multiple orthogonal axes simultaneously — useful when a single axis walk reveals the concept is multi-dimensional.

```python
cat_names = sorted(set(text_to_cat.values()))
centroid_matrix = np.array([centroids[c] for c in cat_names])
cc = centroid_matrix - centroid_matrix.mean(axis=0)
cov_m = np.cov(cc.T)
eigenvalues, eigenvectors = np.linalg.eigh(cov_m)
idx = np.argsort(eigenvalues)[::-1]
centroid_pc = cc @ eigenvectors[:, idx]
```

Each PC axis represents a different semantic contrast. Interpret by which categories load heavily on each component.

## Step 7b: Moral Valence Axes (Pejorative Within Same Domain)

When you want "what's the insulting version of X?" — compare within the same semantic domain, not across domains. This revealed in session 2026-04-30 that pejorative terms about wealth DON'T map to poverty semantics; they stay in the wealth cluster and shift toward moral criticism (nepotism, nouveau riche, exploiter, fat cat).

```python
# Pattern: same domain, positive connotation vs negative connotation
neutral_domain = ["wealthy", "rich", "affluent", "millionaire", "business owner"]
pejorative_domain = ["plutocrat", "tycoon", "oligarch", "magnate", "trust fund",
                     "nepotism", "nouveau riche", "fat cat", "parasite", "vampire"]
baseline = ["person", "individual", "human", "neighbor", "citizen", "colleague"]

# Axis: baseline → pejorative within domain
pej_axis = np.mean(pej_centroids) - np.mean(baseline_centroids)
pej_axis /= np.linalg.norm(pej_axis)

# Walk reveals: baseline → neutral-wealth terms → moral criticism terms
# NOT: baseline → poverty terms (cross-domain)
```

**Key insight**: Embeddings organize words by *semantic domain* first, then *moral valence* second. An insult about rich people stays near wealth terms; it doesn't jump to poor terms. This is true across domains — insults about intelligence stay near intelligence concepts, not near unrelated domains.

## Visualization Convention

**Always use white background with black text and color-coded words.** User preference for matplotlib outputs:
- `fig.patch.set_facecolor('#ffffff')` — white figure background
- `ax.set_facecolor('#ffffff')` — white axes background  
- All text labels in `'black'`, `'darkgray'` (60%), or similar — NO light gray like `#eee` or `#aaa` on dark backgrounds
- Category colors stay the same (green for neutral, blue for positive, etc.) but points get a black outline (`edgecolor='#222', linewidths=1.5`) to stand out on white
- Remove spines with `for spine in ax.spines.values(): spine.set_visible(False)` for clean look
- Legend: white fill with thin gray border (`facecolor='#fff', edgecolor='#ccc'`)

## Pitfalls

- **Centroid averaging washes out intra-category variance**: A category with internally conflicting meanings (e.g., "gay" used as slang vs identity term) will produce a centroid that falls between its extremes. Check per-word projections, not just centroid position.
- **Short compound terms bias embeddings**: Multi-word clinical terms like `"intellectual_disability"` embed differently than single words due to tokenization effects. Use consistent granularity across categories.
- **Small sample size produces noisy axes**: <5 words per category → axis is unstable. Each added word can shift the direction significantly. Minimum 8+ per category for stable results.
- **Direction magnitude matters**: Magnitude >0.5 = strong semantic axis. 0.2–0.5 = moderate, interpretable but noisy. <0.1 = concept not organized as a single axis; likely distributed across many dimensions (PCA on centroids will reveal the actual structure).
- **No scipy/sklearn dependency**: This skill uses only numpy and FastEmbed — no sklearn or scipy required. PCA via `np.linalg.eigh()` covariance decomposition, correlation via manual computation.
- **Matplotlib emojis don't render in DejaVu Sans**: Unicode emojis (👑💰⚖️) show as boxes in matplotlib output. Use text symbols (`Q`, `$`, `=`) or plain text labels instead. If you need fancy glyphs, use a font with emoji support — but that requires system-level font installation which is unreliable in Docker containers.
- **Inline media fails on Telegram**: GIFs and MP4s do not display inline reliably in Telegram bot chats. Always serve via ngrok with download links, or send as separate file attachments using MEDIA:/path syntax.

## Automatic Axis Discovery (Systematic Probing)

Instead of pre-defining categories, probe ALL dimensions to discover axes automatically:

1. Embed a diverse vocabulary (50-200 words across many semantic categories)
2. For each dimension d, find top-5 and bottom-5 activating words
3. Cluster dimensions by Jaccard similarity of their top-5 word sets (threshold ≥ 0.25)
4. Each cluster = one interpretable axis; name it from the shared theme
5. Build direction vectors from cluster centroids

This discovered axes like: Moral Character [dims 12,314], Political Freedom [137,292], Natural↔Artificial [382,59], Growth↔Stagnation [97,30]. See `references/axis-catalog.md` for the full catalog.

## Wording Resonance Checker

Project ANY text onto discovered axes to get a "semantic profile" — useful for:
- Comparing alternative wordings (emails, headlines, marketing copy)
- Measuring how provocative/intense a piece of text is before publishing
- A/B testing phrasings by axis score differences

```python
# For each text variant:
text_embed = np.array(list(model.embed([text])))[0]
text_embed = text_embed / np.linalg.norm(text_embed)
scores = {ax['name']: float(np.dot(text_embed, ax['direction'])) for ax in axes}
# Output: bar chart per axis, highlight 4 most extreme, compare shifts between variants
```

See `references/testing-results.md` for example outputs.

## Systematic Dimension Probing (from embedding-axis-probing)

When you don't have pre-defined categories and want to **discover axes from scratch**:

1. **Build diverse vocab**: 50-200+ words spanning emotions, physical properties, politics, morality, nature/artificial, cognitive states
2. **Probe each dimension**: For dimension d, find top-5 and bottom-5 activating words
3. **Cluster by Jaccard**: Group dimensions with top-5 word overlap ≥ 0.25
4. **Name each cluster**: Extract most frequent top/bottom words, identify shared theme
5. **Build direction vectors**: Centroid difference method (see Step 3 above)
6. **Project new text**: L2-normalize → dot product with axis direction

**Additional Probing Pitfalls** (beyond main pitfalls above):
- **fastembed returns generators**: Use `np.array(list(model.embed(texts)))`, NOT `model.embed(texts)[0]`
- **Word list bias**: Discovered axes reflect your vocabulary choices — missing categories = missing axes
- **Dimensions not independent**: Adjacent dims often share semantics; clustering identifies true underlying axes vs redundant slices

## Related Files

- `references/centroid-vs-correlation.md` — When to use each approach with empirical guidance from live session data
- `references/axis-catalog.md` — Example axes discovered via automatic dimension clustering (Moral, Political Freedom, etc.)
- `references/testing-results.md` — Wording resonance test results across food/politics/economy scenarios
- `references/training-datasets.md` — Labeled datasets (GoEmotions, Moral Foundations) for training embedding→reaction models
- `templates/axis-walkthrough.py` — Animated GIF + summary plot template for visualizing axis walks. Drop in your categories and run.
- `scripts/embedding-axes-analysis.py` — Full systematic probing implementation (from embedding-axis-probing)