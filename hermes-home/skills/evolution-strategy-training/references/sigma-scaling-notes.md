# σ (Sigma) Scaling for Evolution Strategy

## Problem

When using distribution-guided evolution (CMA-ES style), σ controls the mutation strength per parameter. If σ is too large relative to the weight scale, sampled weights push the network into regimes where activations blow up → NaN through BatchNorm → entire population gets penalty.

## Derivation

For a model with orthogonal initialization (gain=g):
- Weights are drawn from N(0, g)
- After L layers, signal variance scales as g^L
- If σ >> g, one mutation step can dominate the base weight

**Example**: gain=0.01, L=4 layers
- Base weights: ~0.01 std dev
- With σ=0.5: sampled weights can be ±1.5 (150x base scale)
- With σ=0.02: sampled weights are ±0.06 (6x base scale) — reasonable

## Session Observations (STOCK_RL)

| σ_init | σ_max | NaN Rate | Mean Fitness |
|--------|-------|----------|-------------|
| 0.5 | 3.0 | 90%+ | -939 |
| 0.02 | 0.5 | <5% | -10 to -5 |

With σ_init=0.5, 29/32 models per gen got NaN penalty (-1000). Mean fitness was -939, indicating almost all models were broken.

With σ_init=0.02, mean fitness was -10 to -5, indicating models were surviving and making small losses (learning baseline behavior).

## Weight Clipping

Clipping bounds must also match weight scale:
- `np.clip(pop, -5, 5)` is meaningless for gain=0.01 weights
- Use `np.clip(pop, -1, 1)` or tighter
