---
name: baoyu
description: "Baoyu visual content generation — knowledge comics (知识漫画) and infographics (信息图). Covers art styles, tones, layouts, workflows, and image generation with the image_generate tool."
version: 1.0.0
author: 宝玉 (JimLiu), adapted by Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [baoyu, comic, infographic, knowledge-comic, creative, image-generation, 知识漫画, 信息图]
    homepage: https://github.com/JimLiu/baoyu-skills
---

# Baoyu Visual Content Generation

Adapted from [baoyu-skills](https://github.com/JimLiu/baoyu-skills) for Hermes Agent's tool ecosystem.

Creates visual content from text: **knowledge comics** (educational, biography, tutorial) and **infographics** (visual summaries, information graphics).

## When to Use

Trigger when the user asks to create:
- **Knowledge comics**: "知识漫画", "教育漫画", "Logicomix-style", biography comic, tutorial comic
- **Infographics**: "信息图", "可视化", "高密度信息大图", infographic, visual summary, information graphic

The user provides content (text, file path, URL, or topic) and optionally specifies style, layout, aspect ratio, or language.

## Quick Reference

| Feature | Comics | Infographics |
|---------|--------|--------------|
| Output dir | `comic/{slug}/` | `infographic/{slug}/` |
| Art styles | 6 (ligne-claire, manga, realistic, ink-brush, chalk, minimalist) | N/A (uses visual styles) |
| Tones | 7 (neutral, warm, dramatic, romantic, energetic, vintage, action) | N/A |
| Layouts | 7 (standard, cinematic, dense, splash, mixed, webtoon, four-panel) | 21 (bento-grid, linear-progression, etc.) |
| Styles | N/A | 21 (craft-handmade, claymation, kawaii, etc.) |
| Presets | 5 (ohmsha, wuxia, shoujo, concept-story, four-panel) | N/A |
| Aspect | 3:4 portrait default | landscape default |
| Pages | Multi-page with character sheets | Single image |

## Shared Principles

- **Strip secrets** — always scan source content for API keys, tokens, or credentials before including in any output
- **Language handling** — detect from user input, source content, or explicit option; use consistently
- **image_generate tool** — prompt-only, accepts `prompt` + `aspect_ratio` (landscape/portrait/square), returns URL that must be downloaded
- **Absolute paths for curl -o** — never rely on shell CWD persistence across batches
- **Prompt files** — always write the full prompt to a file BEFORE calling image_generate for reproducibility

## Mode Selection

When the user's request is ambiguous, default based on content:
- Sequential narrative with characters → **Comic**
- Data visualization, comparison, overview → **Infographic**
- When in doubt, ask via `clarify`

## Comic Workflow (see [references/comic-workflow.md](references/comic-workflow.md))

1. Analyze content → `analysis.md`
2. Confirm style/tone/audience (Step 2, REQUIRED)
3. Generate storyboard + characters → `storyboard.md`, `characters/characters.md`
4. Review outline (conditional)
5. Generate prompts → `prompts/*.md`
6. Review prompts (conditional)
7. Generate images (character sheet + pages) → `*.png`
8. Completion report

## Infographic Workflow (see [references/infographic-workflow.md](references/infographic-workflow.md))

1. Analyze content → `analysis.md`
2. Generate structured content → `structured-content.md`
3. Recommend layout×style combinations (3-5)
4. Confirm options with user
5. Generate prompt → `prompts/infographic.md`
6. Generate image → `infographic.png`
7. Output summary

## Art Styles (Comics)

Defined in `references/art-styles/`: `ligne-claire` (default), `manga`, `realistic`, `ink-brush`, `chalk`, `minimalist`

## Tones (Comics)

Defined in `references/tones/`: `neutral` (default), `warm`, `dramatic`, `romantic`, `energetic`, `vintage`, `action`

## Presets (Comics)

| Preset | Equivalent | Hook |
|--------|-----------|------|
| `ohmsha` | manga + neutral | Visual metaphors, no talking heads, gadget reveals |
| `wuxia` | ink-brush + action | Qi effects, combat visuals, atmospheric |
| `shoujo` | manga + romantic | Decorative elements, eye details, romantic beats |
| `concept-story` | manga + warm | Visual symbol system, growth arc, dialogue+action balance |
| `four-panel` | minimalist + neutral + four-panel layout | 起承转合 structure, B&W + spot color, stick-figure characters |

## Layouts

- **Comic layouts** (7): `references/layouts/comic/` — standard, cinematic, dense, splash, mixed, webtoon, four-panel
- **Infographic layouts** (21): `references/layouts/infographic/` — bento-grid, linear-progression, binary-comparison, etc.

## Visual Styles (Infographics)

21 options: `craft-handmade` (default), `claymation`, `kawaii`, `storybook-watercolor`, `chalkboard`, `cyberpunk-neon`, `bold-graphic`, `aged-academia`, `corporate-memphis`, `technical-schematic`, `origami`, `pixel-art`, `ui-wireframe`, `subway-map`, `ikea-manual`, `knolling`, `lego-brick`, `pop-laboratory`, `morandi-journal`, `retro-pop-grid`, `hand-drawn-edu`

## Reference Images (Comics)

Hermes' `image_generate` is **prompt-only**. Reference images are used to extract traits in text that get embedded in every page prompt. See [references/comic-workflow.md](references/comic-workflow.md) for details.

## Pitfalls

- **Always download** the URL from `image_generate` to a local PNG using absolute paths
- **Use absolute paths for curl -o** — CWD can drift between batches
- **Step 2 confirmation required** for comics — do not skip
- **One message per section** for infographics — avoid overloading
- **Character consistency** — driven by text descriptions in `characters/characters.md`, not by PNG reference sheets
- **Strip secrets** from all source content before any output
