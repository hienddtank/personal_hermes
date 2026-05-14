---
name: subagent-web-research-patterns
description: Anti-patterns and optimized approaches for delegating web research to subagents — prevents wasted iterations on shotgun searching.
---

# Subagent Web Research Patterns

## Problem
Subagents delegated for web research tend to:
- Do 20-30 rapid-fire `web_search` calls with minimal returns (often ~50 bytes each)
- Rarely call `web_extract` to actually read content from pages
- Run out of iterations before producing useful output
- Never get past the "searching" phase into "analyzing"

## Solution: Two Approaches

### Approach A: Pre-Identify URLs (Preferred)
Before delegating research subagents, do 3-5 targeted searches yourself to find high-quality source URLs. Then pass those URLs directly to subagents via `web_extract` instructions in their prompt.

**Pattern:**
1. Main agent runs `web_search(query, limit=3)` for each research stream
2. Identify best 2-3 URLs per stream
3. Spawn subagents with prompt like: "Extract and analyze data from these specific URLs: [URLs]. Focus on: [key metrics needed]"

### Approach B: Constrained Subagent Prompts
If you must delegate blind, give extremely constrained prompts:
- **Hard limit searches:** "Perform exactly 3 web_search calls max"
- **Force extraction:** "After searching, extract content from the top 2 URLs using web_extract"
- **Require structured output:** Ask for a table with specific columns they must fill

**Example prompt prefix:**
```
You have limited iterations. Do this in order:
1. web_search (3 calls max) — find best sources
2. web_extract from top 2 URLs  
3. Compile findings into a structured table with specific columns
```

## When Subagent Research Works Well
- Deep dives on specific known articles/reports
- Extracting and summarizing a handful of URLs
- Comparing data across 2-3 pre-identified sources

## When NOT to Use Subagents for Research
- Exploratory discovery (you need to find good sources first)
- Topics with many shallow search results
- Time-sensitive tasks where iterations are limited
- **Non-English language content** (subagents waste iterations trying many keyword variations)

## Concrete Example: Vietnamese Market Research
When researching Vietnam's "đồ ăn vặt" market, subagents got stuck in infinite search loops trying Vietnamese keyword variations. Fix: main agent found 2-3 authority URLs via English searches (Metric Insights report, TikTok Shop Seller Center fee page), then delegated extraction to subagents with exact URLs — cut iterations from 30+ to ~5 per subagent.

**Key insight:** For non-English or geographically specific research, main agent should do source discovery itself, then delegate only extraction with exact URLs.

## Debugging Failed Subagent Research
If a subagent returns empty/short results:
1. Check tool_trace — if it shows 15+ web_search with no web_extract, the pattern failed
2. Retry with Approach A: extract URLs yourself first, then delegate extraction only
3. Lower max_iterations but increase focus in the prompt
