---
name: emotion-pathing
description: Model text sequences as trajectories through multi-axis semantic space instead of classifying individual texts. Optimizes for path shape, velocity, and direction — not static emotional labels. Used for blog content strategy, persuasive writing pipelines, and audience emotional journey design.
tags: [trajectory, emotion, semantic-path, blog-strategy, persuasive-writing, embedding]
---

# Emotion Pathing

Model sequences of text (blog posts, articles, speech segments) as **trajectories through multi-axis semantic space** rather than classifying individual texts into static emotion categories. The core insight: the *path* matters more than any point on it.

## When to Use

- **Blog/website content strategy**: Design emotional journey from first visit to loyal reader
- **Persuasive writing pipelines**: Optimize article sequences for specific emotional outcomes
- **Audience targeting**: Map where readers start (current position) and design path to destination
- **A/B testing sequences**: Compare trajectory shapes of different content strategies, not just single-article tone
- **Crisis communication**: Plan the emotional arc from shock → understanding → agency

## When NOT to Use

- Single-text analysis — use `embedding-axis-analysis` wording resonance instead
- When you only need a classification label (e.g., "is this offensive?") — classification is faster and more accurate for that purpose
- Without predefined semantic axes — emotion pathing *projects onto* existing axes; it doesn't discover them

## Core Concepts

### 1. Trajectory > Point Classification

Instead of: *"this article = anger"*
→ Track: *"this sequence moves reader from OUTRAGE (high emotion, low clarity) → CURIOSITY (clarity spike) → AGENTIVE HOPE (moral urgency + forward momentum)"*

The path shape encodes intent. A path that oscillates between high and low emotional intensity tells a different story than one with gradual ascent.

### 2. Path Metrics

- **Total semantic distance**: Sum of step-to-step distances across all axes. Higher = more dramatic journey.
- **Avg step size**: Mean movement per article/section. Indicates pacing density.
- **Step consistency (σ)**: Standard deviation of step sizes. Low σ = steady progression; high σ = volatile/emotional whiplash.
- **Final position**: Where the reader lands on each axis. This is your target state.
- **Velocity profile**: Rate of change per transition. Sharp moves followed by consolidation = effective pacing.

### 3. Axis Normalization for Path Comparison

When comparing paths across different topic clusters, normalize each axis independently to [-1, 1] range based on the path's own min/max. This makes trajectory shapes comparable regardless of absolute projection magnitudes.

```python
def normalize_path(path):
    """Normalize each axis to [-1, 1] range across the path."""
    arr = np.array([[p[an] for p in path] for an in axis_names])
    mins = arr.min(axis=1, keepdims=True)
    maxs = arr.max(axis=1, keepdims=True)
    ranges = maxs - mins
    ranges[ranges == 0] = 1  # avoid div by zero
    normalized = (arr - mins) / ranges * 2 - 1
    return normalized.tolist()
```

## Step-by-Step Workflow

### Step 1: Define Target Path Shape

Before writing, define where you want readers to END UP. Examples:
- **Outrage → Hope**: Start with moral anger (high intensity, high moral violation), transition through clarity (data/insight), end with agency + hope
- **Data → Heart**: Start cold/rational, pivot to human stories, land on synthesis of clarity + moral urgency
- **Relate → Inspire**: Personal vulnerability → shared frustration → collective power → calm conviction

### Step 2: Map Each Section to Axis Projections

For each section/article in the sequence, project onto your semantic axes. Use `embedding-axis-analysis` wording-resonance pattern for projection code.

```python
# For each section text:
text_embed = np.array(list(model.embed([text])))[0]
text_embed = text_embed / np.linalg.norm(text_embed)
scores = {ax['name']: float(np.dot(text_embed, ax['direction'])) for ax in axes}
```

### Step 3: Build the Trajectory

Collect all section projections into a path. Each path element is a point in multi-dimensional space (one dimension per axis).

### Step 4: Analyze Path Shape

Compute metrics and visualize:
- **2D trajectory plot**: Project onto 2 key axes (e.g., Clarity vs Intensity), draw arrows between consecutive steps
- **Radar chart**: Show full-axis profile at each step. Later steps more opaque to emphasize END STATE
- **Velocity chart**: Stacked bars showing per-axis contribution to step-to-step delta

### Step 5: Iterate on Path Shape

The engine's output should guide writing decisions:
- *"Step 3 drops emotional intensity too fast — readers disengage before call-to-action"*
- *"Swap 'statistics show' for 'here's what it costs families' to strengthen the clarity→emotion transition"*
- *"Your path oscillates between high and low moral character — pick a consistent moral framing"*

## Visualization Patterns

### Pattern 1: Trajectory Plot (2D Projection)
```python
# X = one axis, Y = another, draw arrows from step i → step i+1
x_vals = [p['Cognitive Clarity'] for p in path]
y_vals = [p['Emotional Intensity'] for p in path]
for i in range(len(x_vals) - 1):
    ax.annotate('', xy=(x_norm[i+1], y_norm[i+1]), xytext=(x_norm[i], y_norm[i]),
               arrowprops=dict(arrowstyle='->', color=colors[idx], lw=3, alpha=0.8))
```

### Pattern 2: Radar Chart (Multi-Axis Profile)
```python
# Per-axis values for each step, later steps more opaque
values = [path[i][an] for an in axis_names] + [path[i][axis_names[0]]]
color = colors_path[i % len(colors_path)]
alpha = 0.15 + (i / steps) * 0.45  # opacity increases with sequence position
ax.plot(angles, values, 'o-', color=color, linewidth=2, alpha=alpha)
```

### Pattern 3: Velocity Chart (Per-Step Delta)
```python
# Stacked bars showing which axes contribute most to each transition
deltas = [abs(path[i+1][an] - path[i][an]) for an in axis_names]
ax.bar(x_labels, deltas_per_axis, bar_width, label=axis_name)
ax.plot(x_labels, cumulative, 'o-', color='black', label='Total Δ')
```

## Strategy Templates

### Template A: Outrage → Hope (Activist Blog)
Path shape: **High Intensity/Low Clarity → Curiosity/Curiosity Spike → Clarity Building → Hope/Agency**
- Step 1: Problem statement (anger, injustice framing)
- Step 2: Data pivot ("but here's what most people miss")
- Step 3: Insight/revelation ("when we trace where the money goes...")
- Step 4: Human solution ("communities that restructured...")
- Step 5: Call to action ("redesign, not revolution")

### Template B: Data → Heart (Analytics Blog)
Path shape: **High Clarity/Low Emotion → Human Pivot → Emotional Impact → Synthesis**
- Step 1: Cold statistics ("Gini coefficients across 40 countries...")
- Step 2: Transition ("behind each data point is a person")
- Step 3: Story ("Maria works two jobs and can't afford childcare...")
- Step 4: Connection ("her story isn't an exception — it's the pattern")
- Step 5: Synthesis ("data tells us where; humanity tells us why")

### Template C: Relate → Inspire (Personal Essay Blog)
Path shape: **Vulnerability → Frustration/Clarity → Emotional Shift → Collective Power → Calm Conviction**
- Step 1: Personal story ("I used to think working harder was enough")
- Step 2: Realization ("then I realized the game was designed so most lose")
- Step 3: Emotional pivot ("that scared me but also freed me")
- Step 4: Collective framing ("when thousands see the same thing...")
- Step 5: Calm agency ("not rage — precision")

### Template D: Provoke → Reflect (Subversive Blog)
Path shape: **Shock/Provocation → Cold Truth → Philosophical Turn → Historical Framing → Urgency**
- Step 1: Provocation ("everything you know is a marketing campaign")
- Step 2: Hard data ("mobility declining for 40 years")
- Step 3: Reframe ("despair is also a choice")
- Step 4: History ("every major shift started with refusing to accept 'that's just how it is'")
- Step 5: Call → "Your anger is valid. Your hope is necessary. Your apathy is a luxury you can't afford."

## Integration with embedding-axis-analysis

Emotion pathing **requires** semantic axes as its foundation. Use `embedding-axis-analysis` to:
1. Discover your axes (centroid probing, PCA)
2. Build the wording-resonance checker for individual text projection
3. Validate axis quality before using for path analysis (magnitude >0.2 recommended)

The two skills are complementary: axis-analysis provides the coordinate system; emotion-pathing provides the trajectory modeling on top of it.

## Visualization Convention

**Always use white background with black text.** User preference:
- `fig.patch.set_facecolor('#ffffff')` — white figure background
- `ax.set_facecolor('#ffffff')` — white axes background
- All text in `'black'`, `'darkgray'` (60%), or similar — NO light gray on dark backgrounds
- Remove spines with `for spine in ax.spines.values(): spine.set_visible(False)`
- Convert GIFs to MP4 via ffmpeg if using animation (GIFs fail inline on Telegram)

## Pitfalls

- **Axes too weak**: If axis magnitude <0.1, the concept isn't organized as a single dimension — path projections will be noisy. Use axes discovered in `embedding-axis-analysis` with magnitude ≥0.2.
- **Missing intermediate states**: A path with only 2 points (start → end) reveals nothing about trajectory shape. Minimum 4-5 sections per path for meaningful velocity analysis.
- **Normalizing within path vs globally**: For comparing paths across topics, normalize each axis independently using that path's own min/max. For comparing different drafts of the same content, use a global normalization based on all variants.
- **Confusing intensity with valence**: High Emotional Intensity doesn't mean positive OR negative — it means strong arousal (could be anger or excitement). Always interpret alongside Moral Character and other axes.
- **Path directionality matters**: The arrow from Step 1→Step 2 is semantically different from Step 2→Step 1. A path that goes hope→outrage has a completely different psychological effect than outrage→hope, even if they share the same set of points.
- **Embedding normalization by L2 norm flattens sentence length effects**: Longer sentences may project differently due to token aggregation. Be consistent in text granularity across all steps of a path (all headlines, or all paragraph-length).

## Related Files

- `templates/emotion-pathing.py` — Full working script: define scenarios, project onto axes, generate 3 visualization types (trajectory plot, radar chart, velocity chart), compute path-level metrics. Drop in your topics and axes.
- `references/dataset-overview.md` — Summary of labeled text-to-reaction datasets (GoEmotions 58k comments/27 emotions, Moral Foundations Reddit Corpus) for training embedding→reaction models

## Related Skills

- `embedding-axis-analysis` — Derive the semantic axes used as coordinates for pathing
- `wording-resonance` — Project individual texts onto axes; use within emotion-pathing for section-by-section analysis
