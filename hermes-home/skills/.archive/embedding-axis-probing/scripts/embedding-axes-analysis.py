"""
Embedding Space Probing — Systematic analysis of all dimensions.
For each dimension, find the words that activate it most/least.
Cluster dimensions by semantic theme. Visualize the strongest axes.
"""
import numpy as np
from fastembed import TextEmbedding
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import os
from collections import defaultdict, Counter

model = TextEmbedding(model_name="sentence-transformers/all-MiniLM-L6-v2")

# Comprehensive vocabulary — diverse semantic categories
vocab = [
    # Emotions/feelings
    "happy", "sad", "angry", "fearful", "surprised", "disgusted",
    "anxious", "excited", "bored", "confused", "proud", "ashamed",
    "hopeful", "despairing", "jealous", "grateful",

    # Physical size/shape
    "big", "small", "tall", "short", "wide", "narrow",
    "heavy", "light", "thick", "thin", "round", "sharp",

    # Temporal concepts
    "ancient", "modern", "past", "future", "eternal", "fleeting",
    "old", "young", "new", "timeless", "brief", "lasting",

    # Social/political
    "democracy", "tyranny", "freedom", "oppression", "equality",
    "hierarchy", "republic", "monarchy", "liberal", "conservative",
    "socialism", "capitalism", "revolution", "tradition",

    # Moral/ethical
    "virtuous", "sinful", "just", "unfair", "kind", "cruel",
    "honest", "deceptive", "generous", "selfish", "brave", "cowardly",
    "loyal", "treacherous", "merciful", "vengeful",

    # Physical properties
    "hot", "cold", "wet", "dry", "hard", "soft", "rough", "smooth",
    "bright", "dark", "loud", "quiet", "fast", "slow",

    # Nature vs artificial
    "organic", "synthetic", "natural", "manufactured", "wild",
    "domesticated", "rustic", "urban", "rural", "industrial",
    "pristine", "corrupted", "pure", "polluted",

    # Cognitive/mental
    "wise", "foolish", "intelligent", "ignorant", "creative",
    "mechanical", "logical", "emotional", "rational", "impulsive",
    "focused", "scattered", "calm", "chaotic",

    # Social status/class
    "elite", "commoner", "royal", "peasant", "aristocratic",
    "plebeian", "noble", "vulgar", "refined", "coarse",
    "sophisticated", "naive", "cultured", "primitive",

    # Action verbs (abstract)
    "create", "destroy", "build", "collapse", "grow", "shrink",
    "advance", "retreat", "expand", "contract", "ascend", "descend",
    "connect", "separate", "unite", "divide",

    # Abstract/philosophical
    "infinite", "finite", "absolute", "relative", "objective",
    "subjective", "eternal", "contingent", "necessary", "possible",
    "true", "false", "real", "imaginary", "certain", "doubtful",

    # Colors/sensory (metaphorical)
    "vivid", "muted", "harsh", "gentle", "sharp", "blunt",
    "clear", "obscure", "transparent", "opaque", "pure", "tainted",

    # Health/body
    "healthy", "sick", "strong", "weak", "vital", "decaying",
    "virile", "sterile", "fertile", "withered", "robust", "frail",
]

print(f"Embedding {len(vocab)} words...")
all_embeds = np.array(list(model.embed(vocab))).astype(np.float64)
norms = np.linalg.norm(all_embeds, axis=1, keepdims=True)
normed = all_embeds / norms

D = all_embeds.shape[1]  # 384
print(f"Shape: {all_embeds.shape} — probing {D} dimensions\n")

# ─── Probing all dimensions ──────────────────────────────────
print("Probing all {} dimensions...".format(D))
dim_analysis = []
for d in range(D):
    dim_vals = all_embeds[:, d]
    top5_idx = np.argsort(dim_vals)[-5:][::-1]
    bot5_idx = np.argsort(dim_vals)[:5]

    dim_analysis.append({
        'dim': d,
        'top5': [(vocab[i], float(dim_vals[i])) for i in top5_idx],
        'bot5': [(vocab[i], float(dim_vals[i])) for i in bot5_idx],
        'range': float(np.max(dim_vals) - np.min(dim_vals)),
    })

# ─── Cluster dimensions by shared semantic themes ────────────
word_to_dims = defaultdict(list)
for d in range(D):
    for w, _ in dim_analysis[d]['top5']:
        word_to_dims[w].append(d)

dim_similarities = np.zeros((D, D))
for i in range(D):
    top_words_i = set(w for w, _ in dim_analysis[i]['top5'])
    for j in range(i+1, D):
        top_words_j = set(w for w, _ in dim_analysis[j]['top5'])
        intersection = len(top_words_i & top_words_j)
        union = len(top_words_i | top_words_j)
        if union > 0:
            sim = intersection / union
            dim_similarities[i, j] = sim
            dim_similarities[j, i] = sim

# Group dimensions by similarity threshold
threshold = 0.25
groups = []
assigned = np.zeros(D, dtype=bool)

for i in range(D):
    if assigned[i]:
        continue
    group = [i]
    assigned[i] = True
    for j in range(i+1, D):
        if not assigned[j] and dim_similarities[i, j] >= threshold:
            avg_sim_to_group = np.mean([dim_similarities[k, j] for k in group])
            if avg_sim_to_group >= threshold * 0.5:
                group.append(j)
                assigned[j] = True
    groups.append(group)

significant_groups = [g for g in groups if len(g) >= 2]
singleton_dims = [i for i in range(D) if not assigned[i]]

print(f"\nFound {len(significant_groups)} semantic clusters ({len(groups)} total, {D - sum(len(g) for g in significant_groups)} singleton dimensions)\n")

# ─── Print cluster themes ────────────────────────────────────
for gi, group in enumerate(significant_groups):
    all_top = []
    all_bot = []
    for d in group:
        all_top.extend(dim_analysis[d]['top5'])
        all_bot.extend(dim_analysis[d]['bot5'])

    top_counts = Counter(w for w, _ in all_top)
    bot_counts = Counter(w for w, _ in all_bot)

    top_words = [w for w, c in top_counts.most_common(8)]
    bot_words = [w for w, c in bot_counts.most_common(8)]

    avg_range = np.mean([dim_analysis[d]['range'] for d in group])

    print(f"\nCluster {gi+1}: dimensions {group} (avg range: {avg_range:.3f})")
    print(f"  Top words:  {' '.join(top_words)}")
    print(f"  Bot words:  {' '.join(bot_words)}")

# ─── Find the MOST active dimensions ─────────────────────────
sorted_dims = sorted(dim_analysis, key=lambda x: x['range'], reverse=True)
print("\n\nTOP 15 MOST ACTIVE DIMENSIONS:")
for da in sorted_dims[:15]:
    d = da['dim']
    top_str = " → ".join([f"{w}" for w, _ in da['top5']])
    bot_str = " → ".join([f"{w}" for w, _ in da['bot5']])
    print(f"  Dim {d:3d} (range={da['range']:.3f}): [{top_str}]")
    print(f"                    [-{bot_str}]")

# ─── Visualize top axes via PCA ──────────────────────────────
fig, ax = plt.subplots(1, 1, figsize=(18, 12), dpi=100)
fig.patch.set_facecolor('#ffffff')
ax.set_facecolor('#ffffff')
for spine in ax.spines.values():
    spine.set_visible(False)

X_centered = normed - normed.mean(axis=0)
cov_matrix = np.cov(X_centered.T)
eigenvalues, eigenvectors = np.linalg.eigh(cov_matrix)
idx = np.argsort(eigenvalues)[::-1][:2]
pc1_vec = eigenvectors[:, idx[0]]
pc2_vec = eigenvectors[:, idx[1]]
vocab_2d = X_centered @ np.column_stack([pc1_vec, pc2_vec])

ax.scatter(vocab_2d[:, 0], vocab_2d[:, 1], c='#999', s=30, alpha=0.6)

highlight_words = set()
for da in sorted_dims[:5]:
    for w, _ in da['top5']:
        highlight_words.add(w)
    for w, _ in da['bot5']:
        highlight_words.add(w)

for i, word in enumerate(vocab):
    if word in highlight_words:
        ax.annotate(word, xy=vocab_2d[i], fontsize=9, color='#1a1a1a', fontweight='bold',
                    xytext=(3, 3), textcoords='offset points')

for gi, group in enumerate(significant_groups[:8]):
    centroids = []
    for d in group:
        for w, _ in dim_analysis[d]['top5']:
            idx_w = vocab.index(w)
            centroids.append(vocab_2d[idx_w])
    if centroids:
        avg_pt = np.mean(centroids, axis=0)
        all_top = []
        for d in group:
            all_top.extend(dim_analysis[d]['top5'])
        word_counts = Counter(w for w, _ in all_top)
        reps = [w for w, _ in word_counts.most_common(2)]

        ax.scatter(*avg_pt, s=150, facecolors='none', edgecolors='#e53935', linewidths=2, zorder=5)
        ax.annotate(f"{' + '.join(reps)}", xy=avg_pt, fontsize=8, color='#c62828',
                   fontweight='bold', ha='center', va='bottom',
                   bbox=dict(boxstyle='round,pad=0.3', facecolor='#ffebee', edgecolor='#ef9a9a'))

ax.set_title("Embedding Space (384D → 2D PCA)\nRed dots = clusters, bold words = most active dimensions",
             fontsize=16, fontweight='bold', color='#222', pad=20)
ax.set_xlabel(f"PC1 ({eigenvalues[idx[0]]:.1f}%)", fontsize=11, color='#555')
ax.set_ylabel(f"PC2 ({eigenvalues[idx[1]]:.1f}%)", fontsize=11, color='#555')

os.makedirs("/workspace/outputs", exist_ok=True)
out = "/workspace/outputs/embedding-axes-overview.png"
fig.savefig(out, dpi=100, bbox_inches='tight', facecolor='#ffffff')
print(f"✅ Saved: {out}")