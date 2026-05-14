"""
Embedding Axis Walkthrough — Animated GIF + Summary Plot
=========================================================
Usage: Adapt the word lists, category colors, and axis definition for your own analysis.
Outputs: outputs/axis-walk.gif (animation) + outputs/axis-summary.png (static map)

Requirements: numpy, fastembed, matplotlib (Agg backend), Pillow
No sklearn/scipy needed — all PCA via np.linalg.eigh().
"""
import numpy as np
from fastembed import TextEmbedding
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.animation import FuncAnimation, PillowWriter
import os

# ─── CONFIG: Define your axis ────────────────────────────────
# Replace these with YOUR categories and words
WORDS = {
    "neutral_positive": ["person", "individual", "human", "neighbor", "colleague"],
    "positive": ["champion", "leader", "contributor", "pioneer", "visionary"],
    "mild_friendly": ["buddy", "pal", "mate", "friend", "companion"],
    "derogatory_general": ["idiot", "fool", "moron", "jerk", "loser"],
    # ... add your target categories here
}

# Map each word to its category for coloring
def build_vocab_and_categorize(word_dict):
    """Flatten dict → list of (word, category) tuples."""
    vocab = []
    cat_map = {}
    for cat, terms in word_dict.items():
        for w in terms:
            vocab.append(w)
            cat_map[w] = cat
    return vocab, cat_map

# ─── Color scheme ─────────────────────────────────────────────
CATEGORY_COLORS = {
    "neutral_positive": "#4CAF50",
    "positive": "#2196F3",
    "mild_friendly": "#FFEB3B",
    "derogatory_general": "#FF9800",
    # Add colors for your categories
}

# ─── Setup ────────────────────────────────────────────────────
model = TextEmbedding(model_name="sentence-transformers/all-MiniLM-L6-v2")
vocab_words, cat_map = build_vocab_and_categorize(WORDS)

print(f"Embedding {len(vocab_words)} words...")
all_embeds = list(model.embed(vocab_words))
vocab_vecs = np.stack(all_embeds).astype(np.float64)
norms = np.linalg.norm(vocab_vecs, axis=1, keepdims=True)
vocab_norms = vocab_vecs / norms

# ─── Compute axis direction ──────────────────────────────────
neutral_words = [w for w in vocab_words if cat_map[w] == "neutral_positive"]
target_words = [w for w in vocab_words if cat_map[w].startswith("derogatory")]

n_embeds = np.array([vocab_norms[vocab_words.index(w)] for w in neutral_words])
t_embeds = np.array([vocab_norms[vocab_words.index(w)] for w in target_words])

neutral_centroid = n_embeds.mean(axis=0)
target_centroid = t_embeds.mean(axis=0)
raw_dir = target_centroid - neutral_centroid
dir_mag = np.linalg.norm(raw_dir)
axis = -(target_centroid - neutral_centroid) / dir_mag  # higher = neutral, lower = target

print(f"Axis magnitude: {dir_mag:.4f}")

# ─── PCA to 2D ───────────────────────────────────────────────
X_c = vocab_norms - vocab_norms.mean(axis=0)
cov_m = np.cov(X_c.T)
eigvals, eigvecs = np.linalg.eigh(cov_m)
idx = np.argsort(eigvals)[::-1][:2]
pca_2d = X_c @ eigvecs[:, idx]

# ─── Walk along axis ─────────────────────────────────────────
num_steps = 30
positions = np.linspace(-1.5, 3.0, num_steps)
step_data = []

for pos in positions:
    probe = neutral_centroid + pos * axis
    probe_norm = probe / np.linalg.norm(probe)
    sims = vocab_norms @ probe_norm
    top_idx = np.argsort(sims)[::-1][:6]
    step_data.append({
        "position": pos,
        "probe_2d": (probe - vocab_norms.mean(axis=0)) @ eigvecs[:, :2],
        "top_words": [(vocab_words[i], float(sims[i]), cat_map[vocab_words[i]]) for i in top_idx],
    })

# ─── Build Animation ─────────────────────────────────────────
fig, axes = plt.subplots(2, 1, figsize=(14, 16), dpi=100)
fig.patch.set_facecolor('#ffffff')

# Scatter plot (top)
ax_scatter = axes[0]
ax_scatter.set_facecolor('#ffffff')
for spine in ax_scatter.spines.values():
    spine.set_visible(False)

for cat in CATEGORY_COLORS:
    mask = [cat_map[w] == cat for w in vocab_words]
    ax_scatter.scatter(pca_2d[mask, 0], pca_2d[mask, 1],
                       c=CATEGORY_COLORS[cat], s=40, alpha=0.25, edgecolors='none')

# Highlight dots with colored fill + black outline for contrast on white bg
highlights = [ax_scatter.scatter([], [], s=300, facecolor='#ffffff', 
                                  edgecolor='#222', linewidths=3.5, zorder=10) for _ in range(6)]

legend_handles = [mpatches.Patch(color=CATEGORY_COLORS[c], label=c.replace('_', ' ').title()) for c in CATEGORY_COLORS]
ax_scatter.legend(handles=legend_handles, loc='upper left', fontsize=9, framealpha=0.7, edgecolor='#ccc', facecolor='#fff')

# Bar chart (bottom)
ax_bar = axes[1]
ax_bar.set_facecolor('#ffffff')
for spine in ax_bar.spines.values():
    spine.set_visible(False)
bar_rects = [ax_bar.bar(0, 0, width=0.8, color='#ddd', edgecolor='#888')[0] for _ in range(6)]

output_dir = os.path.join(os.path.dirname(__file__), "outputs")
os.makedirs(output_dir, exist_ok=True)

def update(frame):
    data = step_data[frame]
    ax_scatter.set_title(f"Step {frame+1}/{num_steps} | Position: {data['position']:+.2f}", 
                         fontsize=15, fontweight='bold', color='#222')
    
    for i, (word, sim, cat) in enumerate(data["top_words"]):
        widx = vocab_words.index(word)
        highlights[i].set_offsets([[pca_2d[widx, 0], pca_2d[widx, 1]]])
        highlights[i].set_facecolor(CATEGORY_COLORS.get(cat, '#fff'))
        highlights[i].set_edgecolor('#222')
    
    for i, rect in enumerate(bar_rects):
        sim = data["top_words"][i][1]
        cat = data["top_words"][i][2]
        rect.set_height(sim)
        rect.set_color(CATEGORY_COLORS.get(cat, '#333'))
        rect.set_edgecolor('#fff')
    
    return [ax_scatter] + highlights

ani = FuncAnimation(fig, update, frames=num_steps, interval=600, blit=False)
gif_path = os.path.join(output_dir, "axis-walk.gif")
writer = PillowWriter(fps=2.5)
ani.save(gif_path, writer=writer, dpi=100)
print(f"GIF saved: {gif_path}")

# Static summary plot
fig2, ax2 = plt.subplots(1, 1, figsize=(14, 10), dpi=100)
fig2.patch.set_facecolor('#0a0a0f')
ax2.set_facecolor('#0d0d15')
for cat in CATEGORY_COLORS:
    mask = [cat_map[w] == cat for w in vocab_words]
    ax2.scatter(pca_2d[mask, 0], pca_2d[mask, 1], c=CATEGORY_COLORS[cat], s=60, alpha=0.5)
ax2.set_title("Embedding Space: Category Map", fontsize=14, fontweight='bold', color='#eee')
fig2.savefig(os.path.join(output_dir, "axis-summary.png"), dpi=100, bbox_inches='tight')
print(f"Summary saved: outputs/axis-summary.png")
