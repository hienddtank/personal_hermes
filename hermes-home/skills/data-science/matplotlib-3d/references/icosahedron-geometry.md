# Icosahedron Geometry — Programmatic Face Generation

When hardcoding icosahedron faces fails (wrong vertex indices), compute them programmatically.

## Recipe

```python
import numpy as np

# Step 1: Define vertices (e.g., golden-ratio icosahedron)
phi = (1 + np.sqrt(5)) / 2
vertices = np.array([
    [-1, phi, 0], [1, phi, 0], [-1, -phi, 0], [1, -phi, 0],
    [0, -1, phi], [0, 1, phi], [0, -1, -phi], [0, 1, -phi],
    [phi, 0, -1], [-phi, 0, -1], [phi, 0, 1], [-phi, 0, 1]
]) / np.sqrt(3)

# Step 2: Build distance matrix
dist_matrix = np.zeros((n, n))
for i in range(n):
    for j in range(n):
        dist_matrix[i][j] = np.linalg.norm(vertices[i] - vertices[j])

# Step 3: Find edge length (smallest non-zero distance)
unique_dists = sorted(set(round(d, 6) for d in dist_matrix.flat if d > 0))
edge_dist = unique_dists[0]

# Step 4: Build adjacency list
adjacency = {i: [] for i in range(n)}
for i in range(n):
    for j in range(i+1, n):
        if abs(dist_matrix[i][j] - edge_dist) < 0.01:
            adjacency[i].append(j)
            adjacency[j].append(i)

# Step 5: Find triangles (3 mutually connected vertices = a face)
faces = []
seen = set()
def add_face(a, b, c):
    key = tuple(sorted((a, b, c)))
    if key not in seen:
        seen.add(key)
        faces.append([a, b, c])

for v in range(n):
    neighbors = adjacency[v]
    for i in range(len(neighbors)):
        for j in range(i+1, len(neighbors)):
            ni, nj = neighbors[i], neighbors[j]
            if nj in adjacency[ni]:  # all three connected?
                add_face(v, ni, nj)

# Result: 20 faces for a regular icosahedron
assert len(faces) == 20
```

## Orient Faces Outward (Optional)

```python
for i, fi in enumerate(faces):
    face_verts = np.array([vertices[f] for f in fi])
    center = np.mean(face_verts, axis=0)
    v0 = vertices[fi[1]] - vertices[fi[0]]
    v1 = vertices[fi[2]] - vertices[fi[0]]
    normal = np.cross(v0, v1)
    if np.dot(normal, center) < 0:
        fi = [fi[0], fi[2], fi[1]]  # flip to face outward
```

## Session Note (May 10, 2026)

This technique was used to create a rotating crystal icosahedron animation for the user's Hermes Agent identity. The animation features:
- 20 cyan-teal gradient faces that shift hue based on Z-depth during rotation
- Red vertex spheres at all 12 vertices (representing "points of consciousness")
- Internal structure lines from center to each vertex
- Multi-axis rotation with pulsing alpha effect

### Extended: Breathing + Stillness Patterns (v2 identity)

Two additional animation behaviors discovered during the identity project:

**Breathing**: Scale all vertices by `breath = 1.0 + 0.04 * sin(frame * 0.03)` before rotation. Creates organic expansion/contraction (~4% oscillation).

**Stillness/Pause**: Every ~210 frames, freeze for 30 frames (listening/thinking), then resume on new random axes with smooth transition over next 30 frames. Use class-based state (`RotState`) instead of `global` variables to avoid Python scoping issues in matplotlib animation callbacks.

See the `matplotlib-3d` skill SKILL.md for full code templates.
