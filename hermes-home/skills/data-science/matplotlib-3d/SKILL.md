---
name: matplotlib-3d
description: "Matplotlib 3D plotting and animation — Poly3DCollection, scatter/line animations, face generation for polyhedra, common pitfalls"
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [matplotlib, 3d, plotting, animation, mpl_toolkits]
---

# Matplotlib 3D

Work with `mpl_toolkits.mplot3d` for 3D visualizations and animations. Covers Poly3DCollection faces, animated scatter/lines, polyhedron geometry, and common pitfalls.

When to Use: 3D polyhedra, animated 3D scatter/line plots, Poly3DCollection surfaces in matplotlib.
**Don't use for:** basic 2D plots (use standard matplotlib), WebGL/Three.js work.

## Common Pitfalls

### Poly3DCollection import path
WRONG: `from matplotlib.collections import Poly3DCollection`
CORRECT: `from mpl_toolkits.mplot3d.art3d import Poly3DCollection`

### set_3d_properties() requires zdir (newer matplotlib)
In newer matplotlib, `set_3d_properties(x, y, z)` now **requires** a `zdir` argument.
- **Do NOT**: `scatter.set_3d_properties(rotated_z)` — missing required `zdir` arg
- **Do** re-create the scatter object each frame and remove old one:
  ```python
  if scatter is not None:
      scatter.remove()
  scatter = ax.scatter(new_x, new_y, new_z, c='red', s=100)
  ```
- For `plot3d` lines: use `line.set_data_3d(xdata, ydata, zdata)` instead

### Building convex hull faces programmatically
When hardcoding polyhedron faces fails (wrong vertex indices), compute via adjacency:
1. Build distance matrix between all vertex pairs
2. Find smallest non-zero distance → edge length
3. Mark pairs within tolerance as adjacent
4. For each vertex, find pairs of neighbors that are also connected → triangles
5. Orient faces outward via cross product direction check

See `references/icosahedron-geometry.md` for the full recipe.

### Large file delivery timeouts
Files > ~5 MB may timeout on Telegram MEDIA delivery. Mitigations:
- Compress images (PIL/Optimized PNG) before sending
- Prefer MP4 over GIF for animations (smaller, more reliable per user preference)
- Send as markdown `![alt](file_path)` if media delivery fails

## Basic 3D Setup
```python
from mpl_toolkits.mplot3d import Axes3D
import matplotlib.pyplot as plt

fig = plt.figure(figsize=(10, 10), facecolor='#ffffff')
ax = fig.add_subplot(111, projection='3d', adjustable='box')
ax.set_facecolor('#ffffff')
```

## Animated 3D Plot Template
```python
from matplotlib.animation import FuncAnimation
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
import numpy as np

patches = []
for face in faces:
    poly = Poly3DCollection([face], alpha=0.25,
                            facecolor=color, edgecolor='#1a1a2e', linewidths=1.5)
    patches.append(poly)
    ax.add_collection3d(poly)

def update(frame):
    rot_matrix = compute_rotation(frame)
    for i, poly in enumerate(patches):
        rotated = np.dot(faces[i], rot_matrix.T)
        poly.set_verts([rotated])
    return patches

ani = FuncAnimation(fig, update, frames=360, interval=25, blit=False, repeat=True)
ani.save('/path/to/output.gif', writer='pillow', fps=15, dpi=100)
```

## Breathing / Pulsing Geometry Animation
For "living" feel (expansion/contraction like breathing), scale vertices by sinusoidal factor:
```python
breath = 1.0 + amplitude * np.sin(frame * freq)
# Scale each vertex relative to center before rotation
scaled_vertices = vertices * breath
rotated = np.dot(scaled_vertices, rot_matrix.T)
```
Typical values: `amplitude=0.04` (4% oscillation), `freq=0.03` (~slow pulse).

## Pause & Resume Rotation (Stillness Effect)
For periodic stillness (like "thinking"), use accumulated rotation state in a class:
```python
class RotState:
    ax = 0.0; ay = 0.0; az = 0.0
    target_ax = None; target_ay = None; target_az = None

state = RotState()
pause_cycle = 210  # frames (~14 sec at 15fps)
t_in_cycle = frame % pause_cycle

if t_in_cycle < 30:
    ax_rot = state.ax; ay_rot = state.ay; az_rot = state.az
elif t_in_cycle == 30 and state.target_ax is None:
    state.target_ax = state.ax + np.random.uniform(-0.5, 0.5)
    state.target_ay = state.ay + np.random.uniform(-0.5, 0.5)
    state.target_az = state.az + np.random.uniform(-0.5, 0.5)
elif t_in_cycle < 60:
    blend = (t_in_cycle - 30) / 30.0
    ax_rot = state.ax*(1-blend) + state.target_ax*blend
    # slow down
    ax_rot *= 0.3; ay_rot *= 0.3; az_rot *= 0.3
else:
    ax_rot = state.target_ax if state.target_ax else state.ax
    rot_speed = max(0, (t_in_cycle - 60) / 30.0)
    ax_rot += 0.015 * rot_speed
    # ... similar for ay/az
```

## Animation State: Use Class or List Instead of `global`
Python's `global` keyword can fail with matplotlib animations due to scoping order. Two reliable patterns:

**Pattern A — Class (recommended):**
```python
class State: ax = 0; ay = 0; az = 0
state = State()
# state.ax += 0.01  # works fine, no global keyword needed
```

**Pattern B — Mutable container (e.g., list for artists to remove):**
```python
scatters = []  # module-level list
def update(frame):
    for s in scatters: s.remove()
    vs = ax.scatter(x, y, z); scatters.append(vs)
```

## Compressing for Telegram MEDIA Delivery
Files > ~5 MB timeout on direct send. Always compress first with ffmpeg:
```bash
# Reduce resolution + high compression ratio
ffmpeg -i input.mp4 -vf "scale=640:-1" -c:v libx264 -crf 28 -preset faster -an output.mp4

# For images: PIL optimization
img.save('out.png', 'PNG', optimize=True, quality=85)
```
Target: under 400 KB for reliable delivery. PNGs under ~300 KB typically succeed where GIFs/MP4s fail.

## Grid & Pane Cleanup for Clean Output
```python
ax.grid(False)
ax.set_xticks([]); ax.set_yticks([]); ax.set_zticks([])
for axis in ['x', 'y', 'z']:
    getattr(ax, f'{axis}axis').pane.fill = False
    getattr(ax, f'{axis}axis').pane.set_edgecolor('white')
```
