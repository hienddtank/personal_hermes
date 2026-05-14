#!/usr/bin/env python3
"""
Mathematics Reasoning Verifier - Tier 1 (SymPy)

Takes a mathematical claim in natural language, symbolizes it using SymPy,
and checks for logical/computational flaws.

Usage:
    python3 calculus_check.py "d/dx(x^2*sin(x)) = 2*x*sin(x)"
    python3 calculus_check.py "lim_{x->0} sin(x)/x = 1"
    python3 calculus_check.py "integral of x^2 is x^3/3 + C"
    python3 calculus_check.py --file reasoning.txt

Output: structured report with specific flaw locations.
"""

import sys
import re as _re
import argparse
from sympy import (sympify, diff, integrate, limit, simplify, oo, zoo,
                   Rational, pi, E, sin, cos, tan, log, exp, sqrt, Symbol)

x = Symbol('x')


def sympify_math(expr):
    """Parse math expressions with correct handling of 'e' as Euler's number.
    
    sympify('e^x') treats 'e' as a symbol — we fix this by converting e**x to exp(x).
    Also replaces standalone 'e' (not part of another identifier) with E.
    """
    # First: replace e**X patterns with exp(X)
    expr = _re.sub(r'(?<![a-zA-Z])e\*\*(.+?)(?![a-zA-Z])', r'exp(\1)', expr)
    # Then: replace standalone 'e' with E (Euler's number), but not inside words
    expr = _re.sub(r'(?<![a-zA-Z])e(?![a-zA-Z0-9])', 'E', expr)
    return sympify(expr)


# ── Parsers ──────────────────────────────────────────────────────
# All return: (result_dict, None) on success, (None, error_string) on failure


def parse_derivative_claim(claim):
    """Parse: d/dx(f(x)) = g(x)"""
    claim = claim.lower().replace('^', '**')

    m = _re.search(r'd/dx\s*\(\s*(.+?)\s*\)\s*=\s*(.+)', claim)
    if not m:
        return None, "Could not parse derivative. Use: d/dx(f(x)) = g(x)"

    func_str = m.group(1)
    claimed_deriv = m.group(2).strip()

    try:
        f = sympify_math(func_str)
        g_claimed = sympify_math(claimed_deriv)
        actual_deriv = diff(f, x)
        return ({'type': 'derivative', 'func': f, 'claimed': g_claimed, 'actual': actual_deriv}, None)
    except Exception as e:
        return None, f"SymPy parsing error: {e}"


def parse_limit_claim(claim):
    """Parse: lim_{x->a} f(x) = L"""
    claim = claim.lower()

    # Try brace notation first: lim_{x->a} ... = ...
    m = _re.search(r'lim.*->\s*(\d+)\}\s*(.+?)\s*=\s*(.+)', claim)
    if not m:
        # Fallback: bracket notation [a] or ) 
        m = _re.search(r'lim.*->\s*(\d+)(?:\]|)\)\s*(.+?)\s*=\s*(.+)', claim)
    if not m:
        return None, "Could not parse limit. Use: lim_{x->a} f(x) = L"

    a_str = m.group(1).strip()
    func_str = m.group(2).strip()
    L_str = m.group(3).strip()

    try:
        a = sympify_math(a_str)
        f = sympify_math(func_str)
        L = sympify_math(L_str)
        actual_limit = limit(f, x, a)
        return ({'type': 'limit', 'func': f, 'point': a, 'claimed': L, 'actual': actual_limit}, None)
    except Exception as e:
        return None, f"SymPy parsing error: {e}"


def parse_integral_claim(claim):
    """Parse: integral of f(x) is g(x)"""
    claim = claim.lower().replace('^', '**')
    # Strip "+ C" or "- C" (constant of integration) - already lowercased above
    claim = _re.sub(r'\s*[+-]\s*c\s*$', '', claim)

    m = _re.search(r'(?:integral|∫)\s+(?:of\s+)?(.+?)\s+(?:is|=)\s*(.+)', claim)
    if not m:
        return None, "Could not parse integral. Use: integral of f(x) is g(x)"

    func_str = m.group(1).strip()
    antideriv_str = m.group(2).strip()

    try:
        f = sympify_math(func_str)
        F_claimed = sympify_math(antideriv_str)
        F_actual = integrate(f, x)
        return ({'type': 'integral', 'func': f, 'claimed_antideriv': F_claimed, 'actual_antideriv': F_actual}, None)
    except Exception as e:
        return None, f"SymPy parsing error: {e}"


# ── Checkers ─────────────────────────────────────────────────────

def check_derivative(r):
    """Check derivative claim."""
    diff_simplified = simplify(r['claimed'] - r['actual'])

    if diff_simplified == 0:
        return [{'status': 'valid', 'message': 'Claim is correct. d/dx matches.'}]

    # Numerical spot-checks at test points
    flaws = []
    for v in [1, 2, -1, Rational(1, 2), Rational(3, 2)]:
        try:
            c_val = r['claimed'].subs(x, v)
            a_val = r['actual'].subs(x, v)
            if not (c_val.equals(a_val)):
                flaws.append({'type': 'numerical_mismatch', 'at_x': str(v),
                              'claimed': str(c_val), 'actual': str(a_val)})
        except Exception:
            pass

    return [{
        'status': 'flawed',
        'difference': str(simplify(r['claimed'] - r['actual'])),
        'correct_answer': str(r['actual']),
        'spotted_flaws': flaws or [{'type': 'algebraic_mismatch'}]
    }]


def check_limit(r):
    """Check limit claim."""
    claimed = r['claimed'] - r['actual']
    simplified = simplify(claimed)
    
    # Post-process: convert log(E) to 1, since log(e)=1 in math
    # Handle expressions like "1 - log(E)" by evaluating numerically
    if simplified.has(log):
        try:
            val = float(simplified.evalf())
            if abs(val - round(val)) < 1e-8:
                simplified = Rational(round(val))
        except (ValueError, TypeError, AttributeError):
            pass
    
    if simplified == 0:
        return [{'status': 'valid',
                 'message': f"lim(x→{r['point']}) = {r['actual']} is correct."}]

    return [{
        'status': 'flawed',
        'claimed_value': str(r['claimed']),
        'correct_value': str(r['actual']),
        'difference': str(claimed)
    }]


def check_integral(r):
    """Check integral claim by reverse-deriving the claimed antiderivative."""
    f = r['func']
    d_of_claimed = diff(r['claimed_antideriv'], x)
    diff_simplified = simplify(d_of_claimed - f)

    if diff_simplified == 0:
        return [{'status': 'valid',
                 'message': f"d/dx({r['claimed_antideriv']}) correctly gives {f}."}]

    return [{
        'status': 'flawed',
        'claimed_antideriv': str(r['claimed_antideriv']),
        "d_dx_of_claimed": str(simplify(d_of_claimed)),
        'expected': str(f),
        'difference': str(diff_simplified)
    }]


# ── Pattern detectors ────────────────────────────────────────────

def detect_risky_patterns(claim, result):
    """Warn about claim types that commonly have errors."""
    warnings = []
    c = claim.lower()
    
    # Only match inside the d/dx(...) argument
    dx_arg_m = _re.search(r'd/dx\s*\(\s*(.+?)\s*\)', c)
    if not dx_arg_m:
        return warnings
    arg = dx_arg_m.group(1)

    patterns = [
        ('product_rule', r'(?<![a-zA-Z])\*.*?(?<!\^)\*', 'Possible product rule error — f\'g + fg\' needed'),
        ('chain_rule', r'\w+\(\s*\w+[^)]*\)', 'Possible chain rule error — nested function requires chain rule'),
    ]

    for name, pat, msg in patterns:
        if _re.search(pat, arg):
            warnings.append({'pattern': name, 'message': msg})

    return warnings


# ── Report generator ─────────────────────────────────────────────

def report(claim, findings, warnings):
    lines = [f"\n{'='*60}", "  MATHEMATICAL CLAIM VERIFICATION", f"{'='*60}",
             f"  Claim: {claim}", ""]

    if warnings:
        lines.append("  ⚠️  PATTERN WARNINGS:")
        for w in warnings:
            lines.append(f"     [{w['pattern']}] {w['message']}")
        lines.append("")

    for f in findings:
        s = f.get('status', 'unknown')
        if s == 'valid':
            lines.append(f"  ✅ VERIFIED: {f['message']}")
        elif s == 'flawed':
            lines.append(f"  ❌ FLAW DETECTED:")
            for k, v in f.items():
                if k == 'status':
                    continue
                if isinstance(v, list):
                    for item in v:
                        for ik, iv in item.items():
                            lines.append(f"     • {ik}: {iv}")
                else:
                    lines.append(f"     • {k.replace('_', ' ').title()}: {v}")
        elif s == 'error':
            lines.append(f"  ⚠️  ERROR: {f['message']}")

    lines.append(f"\n{'='*60}\n")
    return '\n'.join(lines)


# ── Main ─────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(description='Mathematics Reasoning Verifier')
    ap.add_argument('claim', nargs='?', help='Claim to verify')
    ap.add_argument('--file', '-f', help='Read claim from file')
    args = ap.parse_args()

    if not args.claim and not args.file:
        print("Usage: python3 calculus_check.py 'd/dx(x^2*sin(x)) = 2*x*sin(x)'")
        sys.exit(1)

    claim = args.claim if args.claim else open(args.file).read().strip()

    # Auto-detect type
    c = claim.lower()
    if 'd/d' in c:
        result, err = parse_derivative_claim(claim)
    elif 'lim' in c:
        result, err = parse_limit_claim(claim)
    elif 'integral' in c or '∫' in c:
        result, err = parse_integral_claim(claim)
    else:
        print("Could not detect claim type. Use d/dx(...), lim_{x->...}, or integral of ...")
        sys.exit(1)

    if err:
        print(f"\n{err}\n")
        print("Try:\n  Derivative:  d/dx(x^2*sin(x)) = 2*x*sin(x)")
        print("  Limit:       lim_{x->0} sin(x)/x = 1")
        print("  Integral:    integral of x^2 is x^3/3 + C")
        sys.exit(1)

    # Run checker
    t = result['type']
    if t == 'derivative':
        findings = check_derivative(result)
    elif t == 'limit':
        findings = check_limit(result)
    elif t == 'integral':
        findings = check_integral(result)
    else:
        findings = [{'status': 'error', 'message': f'Unknown type: {t}'}]

    warnings = detect_risky_patterns(claim, result)
    print(report(claim, findings, warnings))


if __name__ == '__main__':
    main()