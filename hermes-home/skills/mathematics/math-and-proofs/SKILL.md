---
name: math-and-proofs
description: Dual-engine system for calculus math verification — natural language reasoning → formal symbols → automated flaw detection. Supports SymPy symbolic checks (quick) and Coq formal proofs (rigorous).
tags: [mathematics, calculus, verification, formal-methods]
---

# Math Solver & Formal Prover

A dual-engine system that takes mathematical reasoning, symbolizes it, and runs automated checks to find flaws in logic or computation.

## Stack

- **SymPy 1.14+** — symbolic calculus verification (fast, daily use)
- **Coq 8.16+** — formal proof engine (rigorous, deep proofs)
- **mpmath** — arbitrary precision arithmetic for edge cases

## Quick Start: SymPy Check Engine

Run the check engine to verify mathematical claims in natural language:

```bash
python3 /root/.hermes/skills/math-and-proofs/scripts/calculus_check.py "CLAIM"
```

### Claim Syntax (three formats, auto-detected):

**Derivatives:** `d/dx(f(x)) = g(x)` — e.g. `d/dx(x^2*sin(x)) = 2*x*sin(x)`  
**Limits:** `lim_{x->a} f(x) = L` — e.g. `lim_{x->0} sin(x)/x = 1`  
**Integrals:** `integral of f(x) is g(x)` — e.g. `integral of x^2 is x^3/3 + C`

### Expression Syntax
- Use `^` for exponentiation: `x^2`, `e^x`
- Use `*` for multiplication: `2*x*sin(x)`
- Functions: `sin`, `cos`, `tan`, `log`, `exp`, `sqrt`
- **Important**: `e` is auto-recognized as Euler's number — no need to write `E`

## Differential Equation Verification (ODEs)

DE claims are verified by **substitution**: compute d^n(g)/dx^n, substitute y→g(x) into DE terms, check equality. See `references/de-verification-patterns.md` for full pattern catalog.

**Key pitfall**: Always use SymPy's `.subs(Symbol('y'), g(x))` for variable substitution — NEVER string regex on the expression text. String-based implicit multiplication fix (`[a-zA-Z][a-zA-Z]`) breaks because SymPy already parsed `2*y` as a proper `Mul` node, and converting back to string loses structure.

## Verification Pipeline (SymPy Tier 1)

The engine (`scripts/calculus_check.py`) performs:

1. **Parse** — regex pattern matching on claim type
2. **Symbolize** — SymPy with custom `sympify_math()` that correctly handles `e^x` → `exp(x)` conversion
3. **Compute** — symbolic answer (diff/integrate/limit)
4. **Compare** — algebraic simplification (`simplify(claimed - actual) == 0`)
5. **Spot-check** — numerical substitution at x = 1, 2, -1, 1/2, 3/2
6. **Detect patterns** — warns about risky operations (product rule, chain rule, quotient rule)

### Output format:

**Wrong:** ❌ FLAW DETECTED with difference, correct answer, numerical mismatches  
**Correct:** ✅ VERIFIED with confirmation message  
**Warnings:** ⚠️ PATTERN WARNINGS for risky constructs

## When to Escalate

- Use **Tier 1 (SymPy)** for: routine calculus problems, homework checks, quick verification
- Use **Tier 2 (Coq)** for: theorem-style proofs, claims with quantifiers, edge cases (see `references/coq_examples.v`)
- For agent reasoning traces (tool calls, decisions): Coq can formalize invariants only — not full execution traces

## Verified Capabilities

The following claim types have been tested end-to-end and confirmed working:

**Derivatives:**
- Power rule: `d/dx(x^n)` — basic and nested powers
- Product rule: `d/dx(f·g)` — e.g. `x^2*e^x` (correctly requires both terms)
- Chain rule: `d/dx(sin(x^2))` → `2x·cos(x^2)` (catches missing inner derivative)
- Nested chain: `d/dx(e^(sin(x)))`, `d/dx(ln(sin(x)))`
- Quotient rule: `d/dx(x/(1+x^2))` → `(1-x^2)/(1+x^2)^2`
- Logarithmic diff: `d/dx(x^x)` → `x^x·(ln(x)+1)` — works via SymPy's power rule

**Integrals:** (verified by differentiating claimed answer)
- Power rule: ∫x² = x³/3, ∫x³ = x⁴/4 + 1
- Trig: ∫cos(x) = sin(x), ∫sin(x) = -cos(x), ∫sin²(x) = x/2 - sin(2x)/4
- Exponential: ∫eˣ = eˣ
- Logarithmic: ∫ln(x) = x·ln(x) - x
- Integration by parts: ∫x·eˣ = (x-1)eˣ
- Rational: ∫1/x = ln(x)

**Limits:**
- Standard limits: `lim_{x->0} sin(x)/x = 1`
- Exponential limits: `lim_{x->0} (e^x - 1)/x = 1`

### Constant handling in integrals
The engine treats ∫f = g + C the same as ∫f = g for any constant C, because d/dx(claimed) eliminates the constant. Adding "+1", "+C", or "-5" won't cause a false negative — only a missing term will be caught.

## Pitfalls

### SymPy 'e' symbol confusion
`sympify('e')` returns a Symbol named `e`, NOT Euler's number. The engine fixes this via `sympify_math()` which:
- Converts `e**X` patterns to `exp(X)` before sympification  
- Replaces standalone `e` with `E` (Euler's constant)

### Regex brace escaping quirk
`\{` doesn't always match literal `{` in Python regex within certain contexts. Use character class `[{}]` instead when matching braces.

### Limit post-processing
Some limits return unsimplified expressions like `log(E)` instead of `1`. Always add numerical evalf check with tolerance before declaring a mismatch: if `float(expr.evalf())` rounds to integer, accept it.

## File Layout

```
mathematics/math-and-proofs/
├── SKILL.md                          ← this file (instructions)
├── scripts/calculus_check.py         ← SymPy check engine — run directly
└── references/
    ├── coq_examples.v                ← Coq 8.16 lemma reference patterns
    └── testing-integrals-and-derivatives.md  ← tested edge cases and observations
```

See also: `references/coq_examples.v` for formal proof building blocks; `references/testing-integrals-and-derivatives.md` for verified claim patterns and common error signatures.