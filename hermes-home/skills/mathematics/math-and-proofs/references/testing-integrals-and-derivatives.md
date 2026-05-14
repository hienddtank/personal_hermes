# Integration & Derivative Test Results — 2026-04-30

## Session context: Extensive testing of calculus_check.py for integrals and derivatives (product/chain/quotient rules, integration by parts).

## Verified Correct Claims (all returned ✅)

### Integrals
| Claim | Engine behavior |
|---|---|
| `integral of x^2 is x^3/3` | d/dx(x³/3) = x² → verified |
| `integral of cos(x) is sin(x)` | d/dx(sin(x)) = cos(x) → verified |
| `integral of sin(x) is -cos(x)` | d/dx(-cos(x)) = sin(x) → verified |
| `integral of e^x is e^x` | d/dx(exp(x)) = exp(x) → verified |
| `integral of 1/x is ln(x)` | d/dx(log(x)) = 1/x → verified |
| `integral of x*e^x is (x-1)*e^x` | Product rule integration by parts verified |
| `integral of ln(x) is x*ln(x) - x` | Integration by parts verified |
| `integral of sin(x)^2 is x/2 - sin(2*x)/4` | Trig power reduction verified |
| `integral of x^3 is x^4/4 + 1` | Constant doesn't matter — verified (derivative of constant = 0) |

### Derivatives
| Claim | Engine behavior |
|---|---|
| `d/dx(x^2*e^x) = x^2*e^x + 2*x*e^x` | Product rule — both terms present → verified |
| `d/dx(sin(x^2)) = 2*x*cos(x^2)` | Chain rule — inner derivative ×2x → verified |
| `d/dx(x/(1+x^2)) = (1-x^2)/(1+x^2)^2` | Quotient rule → verified |
| `d/dx(ln(sin(x))) = cos(x)/sin(x)` | Nested chain rule → verified |
| `d/dx(x^x) = x^x*(ln(x)+1)` | Logarithmic differentiation → verified |

## Detected Flaws (all returned ❌ with useful diagnostics)

### Wrong Integrals
| Claimed Answer | Actual derivative | Difference | What went wrong |
|---|---|---|---|
| `integral of x^2 is x^3/2` | 3x²/2 | x²/2 | Wrong coefficient (power rule error) |
| `integral of sin(x) is cos(x)` | -sin(x) | -2·sin(x) | Missing negative sign |
| `integral of e^x is x*e^x - 1` | (x+1)eˣ | eˣ | Treated as product rule — wrong antiderivative |
| `integral of x*e^x is x*e^x - 1` | (x+1)eˣ | eˣ | Same product rule confusion |
| `integral of ln(x) is x*ln(x)` | log(x)+1 | 1 | Missing the "-x" term from integration by parts |

### Wrong Derivatives
| Claimed Answer | What went wrong | Correct answer shown in output |
|---|---|---|
| `d/dx(x^2*e^x) = 2*x*e^x` | Missing x²eˣ product term | x²eˣ + 2xeˣ |
| `d/dx(sin(x^2)) = cos(x^2)` | Missed chain rule ×2x | 2x·cos(x²) |
| `d/dx(x/(1+x^2)) = 1/(1+x^2)` | Treated as substitution, missed quotient | (1-x²)/(1+x²)² |
| `d/dx(e^(sin(x))) = e^(sin(x))` | Forgot derivative of sin(x) = cos(x) | e^sin(x)·cos(x) |
| `d/dx(sqrt(1+x^2)) = x/(2*sqrt(1+x^2))` | Off by factor of 2 | x/√(1+x²) |

## Key observations for future sessions

1. **Numerical spot-checks at 5 points** (x = -1, 0.5, 1, 2, 3/2) are reliable even for trigonometric and exponential functions
2. **Constants in integrals don't matter** — d/dx(claimed + C) always eliminates C, so the engine is lenient about constant terms
3. **Product rule mistakes** show the largest numerical differences (often factor-of-2 or full-term mismatches)
4. **Chain rule mistakes** typically show as missing multiplicative factors at all 5 test points
5. The `type: numerical_mismatch` field in error output can appear multiple times — one per test point evaluated
