#!/usr/bin/env python3
"""Skill audit script — reads SKILL.md files and reports issues. Stdlib only.

Usage:
  python3 skill_audit.py                                # audit ALL skills
  python3 skill_audit.py --categories creative,devops     # audit these categories only
  python3 skill_audit.py --skills api/web-scraping        # audit specific names only
"""
import argparse
import json
import os
import re

SKILLS_DIR = "/hermes-home/skills"
ISSUE_KEYWORDS = ["tbd", "todo", "placeholder", "insert here", "fill in", "add description"]


def get_all_skills():
    """Return list of (category, name) tuples for all skills with SKILL.md.

    Supports two structures:
      1. {cat}/{name}/SKILL.md   (e.g., api/realisticasia-api/SKILL.md)
      2. {cat}/SKILL.md          (single-skill category, e.g., docker-restart/SKILL.md)
    """
    skills = []
    if not os.path.exists(SKILLS_DIR):
        return skills
    for category in sorted(os.listdir(SKILLS_DIR)):
        if category.startswith('.'):
            continue
        cat_path = os.path.join(SKILLS_DIR, category)
        if not os.path.isdir(cat_path):
            continue

        # Structure 1: {cat}/{name}/SKILL.md
        has_subdirs = any(
            os.path.isdir(os.path.join(cat_path, d)) and "SKILL.md" in (
                f for f in os.listdir(os.path.join(cat_path, d)) if f == "SKILL.md"
            )
            for d in sorted(os.listdir(cat_path))
        )

        # Structure 2: {cat}/SKILL.md directly
        direct_skill = os.path.exists(os.path.join(cat_path, "SKILL.md"))

        if has_subdirs:
            for name in sorted(os.listdir(cat_path)):
                skillemd = os.path.join(cat_path, name, "SKILL.md")
                if os.path.exists(skillemd):
                    skills.append((category, name))
        elif direct_skill:
            # Single skill — use category name as both category and name
            skills.append((category, category))
    return skills


def filter_skills(skills, categories=None, names=None):
    """Filter skill list by category or specific name."""
    result = skills[:]
    if categories:
        cats = set(c.strip() for c in categories.split(','))
        result = [(c, n) for c, n in result if c in cats]
    if names:
        target = set(n.strip() for n in names.split(','))
        result = [(c, n) for c, n in result if f"{c}/{n}" in target or n in target]
    return result


def parse_frontmatter(text):
    """Parse YAML frontmatter from SKILL.md content."""
    match = re.match(r'---\n(.*?)\n---', text, re.DOTALL)
    if not match:
        return None, text.strip()
    raw = match.group(1)
    fm = {}
    for line in raw.split('\n'):
        if ':' in line:
            key, _, val = line.partition(':')
            fm[key.strip()] = val.strip().strip('"').strip("'")
    body = text[match.end():].strip()
    return fm, body


def audit_skill(category, name):
    """Audit a single skill. Returns dict with findings."""
    skillemd = os.path.join(SKILLS_DIR, category, name, "SKILL.md")
    result = {
        "name": f"{category}/{name}" if category else name,
        "status": "ok",
        "issues": [],
        "frontmatter": {},
    }

    if not os.path.exists(skillemd):
        result["status"] = "ok"
        return result

    try:
        with open(skillemd, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        result["status"] = "error"
        result["issues"].append(f"Read error: {e}")
        return result

    fm, body = parse_frontmatter(content)
    result["frontmatter"] = fm or {}

    if not fm:
        result["status"] = "warning"
        result["issues"].append("No YAML frontmatter")

    desc = (fm.get("description", "") or "").strip() if fm else ""
    if not desc:
        result["status"] = "warning"
        result["issues"].append("Empty or missing description in frontmatter")

    lower_content = content.lower()
    for kw in ISSUE_KEYWORDS:
        if kw in lower_content:
            result["status"] = "warning"
            result["issues"].append(f"Contains placeholder text: '{kw}'")
            break

    if len(content) < 50:
        result["status"] = "warning"
        result["issues"].append("Very short SKILL.md (< 50 chars)")

    if desc and len(desc) < 20:
        result["status"] = "warning"
        result["issues"].append(f"Brief description ({len(desc)} chars)")

    return result


def main():
    parser = argparse.ArgumentParser(description="Skill audit")
    parser.add_argument("--categories", default=None, help="Comma-separated category filter")
    parser.add_argument("--skills", default=None, help="Comma-separated skill name filter (e.g. api/web-scraping)")
    args = parser.parse_args()

    all_skills = get_all_skills()
    skills = filter_skills(all_skills, categories=args.categories, names=args.skills)

    results = [audit_skill(cat, name) for cat, name in skills]

    ok = sum(1 for r in results if r["status"] == "ok")
    warnings = sum(1 for r in results if r["status"] == "warning")
    errors = sum(1 for r in results if r["status"] == "error")

    cats_seen = sorted(set(r["name"].split("/")[0] for r in results))
    print(f"\n=== Skill Audit Report ===")
    print(f"Total skills: {len(results)} | Categories: {len(cats_seen)}")
    print(f"OK: {ok} | Warnings: {warnings} | Errors: {errors}")
    print(f"\nCategories: {', '.join(cats_seen) if cats_seen else '(none matched filter)'}")

    if warnings or errors:
        print(f"\n--- Issues Found ---")
        for r in results:
            if r["status"] != "ok":
                issue_str = "; ".join(r["issues"])
                print(f"  [{r['status'].upper()}] {r['name']}: {issue_str}")
    else:
        print("\nAll skills look good!")


if __name__ == "__main__":
    main()
