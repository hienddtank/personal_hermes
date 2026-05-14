"""
Emotion Pathing — Trajectory Through Semantic Space
====================================================
Instead of classifying individual texts, we model the *trajectory* 
from one text to the next. The blog doesn't have a "tone" — it has 
a direction and velocity through emotional/semantic space.

Usage: Replace SCENARIOS dict with your topics/articles. Run to get
3 visualizations + console path analysis.

Requires: numpy, fastembed, matplotlib
"""
import numpy as np
from fastembed import TextEmbedding
import matplotlib.pyplot as plt

model = TextEmbedding(model_name="sentence-transformers/all-MiniLM-L6-v2")

# ═══════════════════════════════════════════════════════════
# STEP 1: Define your semantic axes (from embedding-axis-analysis)
# ═══════════════════════════════════════════════════════════
axis_names = [
    'Moral Character', 'Political Freedom', 
    'Power & Agency', 'Growth vs Stagnation',
    'Cognitive Clarity', 'Emotional Intensity'
]

# Define high/low word sets for each axis (from your prior axis discovery)
high_words_map = {
    'Moral Character': ['honest', 'kind', 'pure', 'virtuous'],
    'Political Freedom': ['freedom', 'absolute', 'tyranny', 'oppression'],
    'Power & Agency': ['create', 'primitive', 'control', 'destroy'],
    'Growth vs Stagnation': ['grow', 'advance', 'expand', 'fertile'],
    'Cognitive Clarity': ['clear', 'rational', 'logical', 'objective'],
    'Emotional Intensity': ['angry', 'excited', 'disgusted', 'intense'],
}

low_words_map = {
    'Moral Character': ['decaying', 'withered', 'refined', 'finite'],
    'Political Freedom': ['cultural', 'contingent', 'grateful', 'elite'],
    'Power & Agency': ['hot', 'foolish', 'gentle', 'rural'],
    'Growth vs Stagnation': ['sad', 'decay', 'collapse', 'confused'],
    'Cognitive Clarity': ['chaotic', 'obscure', 'vague', 'indistinct'],
    'Emotional Intensity': ['calm', 'serene', 'quiet', 'bored', 'gentle'],
}

# Calculate axis directions from embeddings
axis_words_flat = []
for words in high_words_map.values():
    axis_words_flat.extend(words)
for words in low_words_map.values():
    axis_words_flat.extend(words)

word2vec = {w: i for i, w in enumerate(axis_words_flat)}
embeddings_all = np.array(list(model.embed(axis_words_flat))).astype(np.float64)

axis_directions = {}
for name in axis_names:
    hi_mean = np.mean([embeddings_all[word2vec[w]] for w in high_words_map[name]], axis=0)
    lo_mean = np.mean([embeddings_all[word2vec[w]] for w in low_words_map[name]], axis=0)
    dir_vec = (hi_mean - lo_mean) / np.linalg.norm(hi_mean - lo_mean)
    axis_directions[name] = dir_vec

def project_text(text):
    """Project a text onto all axes, returns dict of scores."""
    emb = np.array(list(model.embed([text]))[0]).astype(np.float64)
    emb = emb / np.linalg.norm(emb)
    return {name: float(np.dot(emb, axis_directions[name])) for name in axis_names}

def normalize_path(path):
    """Normalize each axis to [-1, 1] range across the path."""
    arr = np.array([[p[an] for p in path] for an in axis_names])
    mins = arr.min(axis=1, keepdims=True)
    maxs = arr.max(axis=1, keepdims=True)
    ranges = maxs - mins
    ranges[ranges == 0] = 1
    normalized = (arr - mins) / ranges * 2 - 1
    return normalized.tolist()

# ═══════════════════════════════════════════════════════════
# STEP 2: Define your scenarios — replace with your content
# ═══════════════════════════════════════════════════════════
scenarios = {
    "YOUR BLOG STRATEGY NAME": [
        ("Section 1 text here", "keyword description"),
        ("Section 2 text here", "keyword description"),
        ("Section 3 text here", "keyword description"),
        ("Section 4 text here", "keyword description"),
        ("Section 5 text here", "keyword description"),
    ],
}

# ═══════════════════════════════════════════════════════════
# STEP 3: Compute paths
# ═══════════════════════════════════════════════════════════
all_paths = {}
for name, steps in scenarios.items():
    path = []
    for text, keywords in steps:
        proj = project_text(text)
        proj['keywords'] = keywords
        proj['text_preview'] = text[:80]
        path.append(proj)
    all_paths[name] = path

# ═══════════════════════════════════════════════════════════
# STEP 4: Visualization — Trajectory Plot (2D projection)
# ═══════════════════════════════════════════════════════════
fig, axes = plt.subplots(2, 2 if len(all_paths) <= 4 else 4, 
                        figsize=(16, max(7, len(all_paths) * 3.5)))

if len(all_paths) == 1:
    axes = [axes]
elif len(all_paths) <= 4:
    axes = axes.ravel() if len(all_paths) > 2 else [axes.flatten()[0]]
else:
    axes = axes.ravel()

colors_list = ['#e74c3c', '#3498db', '#2ecc71', '#f39c12', '#9b59b6', '#1abc9c']

for idx, (name, path) in enumerate(all_paths.items()):
    ax = axes[idx] if len(all_paths) > 1 else axes
    x_vals = [p['Cognitive Clarity'] for p in path]
    y_vals = [p['Emotional Intensity'] for p in path]
    
    # Normalize per-path for visibility
    range_x = max(max(x_vals) - min(x_vals), 0.01)
    range_y = max(max(y_vals) - min(y_vals), 0.01)
    x_norm = [(x - (min(x_vals)+max(x_vals))/2) / range_x for x in x_vals]
    y_norm = [(y - (min(y_vals)+max(y_vals))/2) / range_y for y in y_vals]
    
    color = colors_list[idx % len(colors_list)]
    for i in range(len(x_norm) - 1):
        ax.annotate('', xy=(x_norm[i+1], y_norm[i+1]), xytext=(x_norm[i], y_norm[i]),
                   arrowprops=dict(arrowstyle='->', color=color, lw=3, alpha=0.8))
    for i, (x, y) in enumerate(zip(x_norm, y_norm)):
        ax.plot(x, y, 'o', color=color, markersize=14, alpha=0.7)
        ax.annotate(str(i+1), (x, y), textcoords="offset points", 
                   xytext=(0, 12), ha='center', fontsize=10, fontweight='bold')
    
    ax.axhline(y=0, color='gray', lw=0.5, alpha=0.3)
    ax.axvline(x=0, color='gray', lw=0.5, alpha=0.3)
    ax.set_title(f'{name}', fontsize=13, fontweight='bold')
    ax.set_xlabel('Cognitive Clarity →', fontsize=10, color='#666')
    ax.set_ylabel('Emotional Intensity ↑', fontsize=10, color='#666')
    ax.set_facecolor('#ffffff')
    ax.tick_params(left=False, bottom=False)
    ax.set_xticks([])
    ax.set_yticks([])

plt.suptitle('Emotion Pathing: Blog Trajectories Through Semantic Space', 
            fontsize=16, fontweight='bold', y=0.98)
plt.figtext(0.5, 0.93, 
           'Each dot = one section/article. Arrows show direction of reader journey.', 
           ha='center', fontsize=9, style='italic', color='#666')
plt.tight_layout(rect=[0, 0, 1, 0.92])
plt.savefig('/workspace/outputs/emotion-pathing-trajectories.png', dpi=150, facecolor='#ffffff')

# ═══════════════════════════════════════════════════════════
# STEP 5: Visualization — Radar Chart (multi-axis per step)
# ═══════════════════════════════════════════════════════════
fig, axes = plt.subplots(2, 2 if len(all_paths) <= 4 else 4,
                        figsize=(16, max(7, len(all_paths) * 3.5)))

if len(all_paths) == 1:
    axes = [axes]
elif len(all_paths) <= 4:
    axes = axes.ravel() if len(all_paths) > 2 else [axes.flatten()[0]]
else:
    axes = axes.ravel()

for idx, (name, path) in enumerate(all_paths.items()):
    ax = axes[idx] if len(all_paths) > 1 else axes
    steps = len(path)
    angle_step = 2 * np.pi / len(axis_names)
    angles = [i * angle_step for i in range(len(axis_names))] + [0]
    
    colors_path = ['#e74c3c', '#e67e22', '#f1c40f', '#2ecc71', '#3498db']
    for i in range(steps):
        values = [path[i][an] for an in axis_names] + [path[i][axis_names[0]]]
        color = colors_path[i % len(colors_path)]
        alpha = 0.15 + (i / steps) * 0.45
        ax.plot(angles, values, 'o-', color=color, linewidth=2, markersize=6, alpha=alpha)
    
    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(axis_names, fontsize=8)
    ax.set_ylim(-1.2, 1.2)
    ax.fill(angles, [0]*len(angles), alpha=0.05, color='gray')
    for r in [-0.6, -0.3, 0, 0.3, 0.6]:
        ax.plot(angles, [r]*len(angles), '--', color='#ddd', lw=0.5)
    
    kw_str = ' → '.join([p['keywords'][:15] for p in path])
    ax.set_title(f'Steps: {kw_str}', fontsize=10)
    ax.legend(loc='upper right', fontsize=7)
    ax.set_facecolor('#ffffff')

plt.suptitle('Full Axis Profiles: How Each Section Shifts the Emotional Balance', 
            fontsize=14, fontweight='bold', y=0.98)
plt.figtext(0.5, 0.93, 
           'Later steps more opaque = emphasis on end state.', 
           ha='center', fontsize=9, style='italic', color='#666')
plt.tight_layout(rect=[0, 0, 1, 0.92])
plt.savefig('/workspace/outputs/emotion-pathing-radar.png', dpi=150, facecolor='#ffffff')

# ═══════════════════════════════════════════════════════════
# STEP 6: Visualization — Velocity (per-step delta)
# ═══════════════════════════════════════════════════════════
fig, axes = plt.subplots(1, min(len(all_paths), 2), figsize=(14, 5))
if len(all_paths) == 1:
    axes = [axes]

for idx, (name, path) in enumerate(list(all_paths.items())[:2]):
    ax_plot = axes[idx] if len(all_paths) > 1 else axes[0]
    
    deltas = []
    for i in range(len(path) - 1):
        delta_detail = {an: abs(path[i+1][an] - path[i][an]) for an in axis_names}
        deltas.append({
            'detail': delta_detail,
            'from_kw': path[i]['keywords'],
            'to_kw': path[i+1]['keywords']
        })
    
    x_labels = [f"{d['from_kw'].split()[0]}→{d['to_kw'].split()[0]}" for d in deltas]
    bottom = np.zeros(len(deltas))
    an_colors = ['#e74c3c', '#3498db', '#2ecc71', '#f39c12']
    
    for j, an in enumerate(axis_names[:4]):
        offsets = [d['detail'][an] for d in deltas]
        ax_plot.bar(x_labels, offsets, 0.8, label=an, bottom=bottom, color=an_colors[j], alpha=0.8)
        bottom += np.array(offsets)
    
    ax_plot.plot(x_labels, bottom, 'o-', color='black', linewidth=2, markersize=8, label='Total Δ')
    ax_plot.set_title(f'Emotion Change Velocity — {name}', fontsize=12)
    ax_plot.set_ylabel('Semantic Shift Magnitude')
    ax_plot.legend(fontsize=7)
    ax_plot.tick_params(axis='x', rotation=45)

plt.suptitle('Velocity: How Much Does Each Section Move the Needle?', 
            fontsize=14, fontweight='bold')
plt.figtext(0.5, 0.93, 
           'Thick bars = big emotional shift. Sharp moves + consolidation = effective pacing.', 
           ha='center', fontsize=9, style='italic', color='#666')
plt.tight_layout(rect=[0, 0, 1, 0.92])
plt.savefig('/workspace/outputs/emotion-pathing-velocity.png', dpi=150, facecolor='#ffffff')

# ═══════════════════════════════════════════════════════════
# STEP 7: Console — detailed path breakdown + metrics
# ═══════════════════════════════════════════════════════════
print("\n" + "="*80)
print("  EMOTION PATHING BREAKDOWN")
print("="*80)

for name, path in all_paths.items():
    print(f"\n{'─'*70}")
    print(f"  {name}")
    print(f"{'─'*70}")
    
    for i, step in enumerate(path):
        print(f"\n  Step {i+1}: \"{step['text_preview']}...\"")
        print(f"    Keywords: {step['keywords']}")
        for an in axis_names:
            val = step[an]
            bar_len = int(abs(val) * 8)
            if val > 0:
                bar = "▮" * bar_len + "░" * (8 - bar_len)
                print(f"    {an[:20]:20s} |{bar}| {val:+.3f}")
            elif val < 0:
                bar = "▯" * bar_len + "░" * (8 - bar_len)
                print(f"    {an[:20]:20s} |{bar}| {val:+.3f}")
            else:
                bar = "░" * 8
                print(f"    {an[:20]:20s} |{bar}| 0.000")

print("\n\n" + "="*80)
print("  PATH-LEVEL METRICS (comparing strategies)")
print("="*80)

for name, path in all_paths.items():
    total_distance = sum(np.linalg.norm(
        np.array([path[i][an] for an in axis_names]) - 
        np.array([path[i-1][an] for an in axis_names])
    ) for i in range(1, len(path)))
    
    final = path[-1]
    deltas_per_step = [sum(abs(path[i][an] - path[i-1][an]) for an in axis_names) 
                       for i in range(1, len(path))]
    
    print(f"\n  {name}")
    print(f"    Total semantic distance:          {total_distance:.2f}")
    print(f"    Avg step size:                    {np.mean(deltas_per_step):.3f}")
    print(f"    Step size consistency (σ):        {np.std(deltas_per_step):.3f}")
    print(f"    Final moral character score:      {final['Moral Character']:+.3f}")
    print(f"    Final emotional intensity:        {final['Emotional Intensity']:+.3f}")
    print(f"    Final clarity score:              {final['Cognitive Clarity']:+.3f}")
