# Differential Equation Verification Patterns

## Supported Formats (calculus_check.py)

### Syntax
```
solve y' = <rhs> is y = <solution>          # 1st-order, explicit RHS
solve y'' = <rhs> is y = <solution>         # n-th order (more primes)
solve y' + p(x)*y = q(x) is y = g(x)       # implicit LHS/RHS linear form
```

### Verified Patterns

**Separable:** `y' = f(x)*y` → check `dy/dx == f(x)*g(x)`
- `y' = 2*y` → `y = C*exp(2*x)` ✅
- `y' = 2*x*y` → `y = C*exp(x**2)` ✅
- `y' = -2*x*y` → `y = C*exp(-x**2)` ✅

**Linear first-order:** `y' + p(x)*y = q(x)` (q=0 if absent)
- `y' + y = 0` → `y = C*exp(-x)` ✅
- `y' - y = 0` → `y = C*exp(x)` ✅

**Second-order:**
- `y'' = y` → `y = C1*exp(x) + C2*exp(-x)` ✅
- `y'' = -y` → `y = C1*sin(x) + C2*cos(x)` ✅

## Verification Algorithm

1. Parse DE: split on `'` to get order, extract LHS/RHS around `=`
2. Compute d^n(g)/dx^n symbolically via SymPy `.diff()`
3. Substitute y → g(x) in ALL DE terms (LHS expression + RHS) using `.subs(Symbol('y'), g)`
4. Check: `d^n(g)/dx^n + lhs_substituted == rhs_substituted`

## Common Mistakes Detected

| Wrong Claim | Actual Issue |
|---|---|
| y' = 2y → Ce^x | Missing factor in exponent (should be 2*x) |
| y' + y = 0 → Ce^x | Sign error (should be -x) |
| y'' = -y → sin(2x) | Frequency error (should be x, not 2x) |

## Pitfalls & Debug Notes

- **NEVER** use string regex for variable substitution in DEs — SymPy parses `2*y` as `Mul(2, y)` which already has `*`. Regex on str() loses structure. Always use `.subs(Symbol('y'), g(x))`.
- Quote character: `\'` in raw Python strings = `\` + `'`, NOT just `'`. Use actual `'` or `[']` pattern instead.
- Detection regex: `solve\s+y\'+?\s` (not `\s*=`) to catch `y' + ...` forms.
- Multiple constants (C1, C2, c1, c2): SymPy treats each as independent free symbols — works naturally.
