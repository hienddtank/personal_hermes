---
name: structured-output
description: Structured LLM output — guaranteed valid JSON, regex-constrained text, Pydantic models, and grammar-based generation. Covers Instructor (API + Pydantic), Outlines (local models, FSM), and Guidance (grammar/constrained templates). Use for data extraction, classification, form completion, and any workflow requiring typed, validated LLM responses.
category: mlops
---

# Structured LLM Output — Constrained Generation

## Decision Tree

```
Need structured LLM output?
├── Using OpenAI/Anthropic API + want Pydantic validation + auto-retry
│   └── Instructor (instructor) — wraps OpenAI/Anthropic SDK
├── Local models (Transformers, vLLM, llama.cpp) + JSON/regex constraints
│   └── Outlines — FSM-based, zero overhead, fastest
└── Grammar-level control, multi-step workflows, token healing
    └── Guidance — Microsoft Research, regex/grammar constrained
```

## Quick Comparison

| Feature | Instructor | Outlines | Guidance |
|---------|-----------|----------|----------|
| **Approach** | Pydantic + retry | FSM token filtering | Grammar + regex |
| **API models** | ✅ OpenAI, Anthropic | ⚠️ Limited | ✅ OpenAI, Anthropic |
| **Local models** | ❌ | ✅ Transformers, vLLM, llama.cpp | ✅ Transformers, llama.cpp |
| **Auto-retry** | ✅ On validation error | ❌ (generates valid once) | ❌ (constrained at gen) |
| **Pydantic** | ✅ Native | ✅ JSON schema from Pydantic | ❌ |
| **Regex** | ❌ | ✅ | ✅ |
| **Grammar** | ❌ | ⚠️ CFG → FSM | ✅ Full CFG |
| **Streaming** | ✅ Partial + iterable | ❌ | ❌ |
| **Token healing** | ❌ | ❌ | ✅ |
| **Best for** | Production API workflows | Local model deployment | Complex multi-step agents |

## Common Patterns (All Libraries Share)

### Data Extraction
```python
# All three can extract structured data from text:
# Input: "John Doe, 30, john@example.com"
# Output: {name: "John Doe", age: 30, email: "john@example.com"}
```

### Classification
```python
# Constrain to fixed categories
# Options: ["positive", "negative", "neutral"]
```

### JSON Generation
```python
# Guarantee valid JSON matching a schema
# No parsing errors, no truncation, always matches structure
```

### Form Completion
```python
# Fill structured forms with typed fields
# Email validation, date formats, numeric ranges
```

## Quick Start: Each Library

### Instructor — API + Pydantic (Easiest)
```python
import instructor
from pydantic import BaseModel
from anthropic import Anthropic

class User(BaseModel):
    name: str
    age: int
    email: str

client = instructor.from_anthropic(Anthropic())
user = client.messages.create(
    model="claude-sonnet-4-5-20250929",
    messages=[{"role": "user", "content": "Extract: John, 30, john@example.com"}],
    response_model=User
)
# Auto-retries on validation failure
```

### Outlines — Local Models (Fastest)
```python
import outlines
from pydantic import BaseModel

class User(BaseModel):
    name: str
    age: int
    email: str

model = outlines.models.transformers("microsoft/Phi-3-mini-4k-instruct")
generator = outlines.generate.json(model, User)
user = generator("Extract: John, 30, john@example.com")
# Guaranteed valid — FSM constrains at token level
```

### Guidance — Grammar/Regex (Most Flexible)
```python
from guidance import models, gen, select

lm = models.Anthropic("claude-sonnet-4-5-20250929")
# Regex-constrained
lm += "Email: " + gen("email", regex=r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
# Choice-constrained
lm += "Sentiment: " + select(["positive", "negative", "neutral"], name="sentiment")
# Multi-step with @guidance decorator
```

## When to Use Structured Output vs. Free Text

| Scenario | Structured Output | Free Text + Parse |
|----------|------------------|-------------------|
| Database ingestion | ✅ | ❌ |
| API integration | ✅ | ❌ |
| Quick exploration | ❌ | ✅ |
| Creative writing | ❌ | ✅ |
| Classification | ✅ | ⚠️ |
| Data extraction | ✅ | ⚠️ |

## Best Practices

1. **Define schemas first** — Design Pydantic models or JSON schemas before prompting
2. **Use Field descriptions** — Guide the LLM with clear field descriptions
3. **Add validators** — Use Pydantic validators for business logic constraints
4. **Set max_retries** — Instructor defaults to 3; adjust based on complexity
5. **Use Enums for fixed sets** — Constrained values prevent typos
6. **Batch processing** — Process multiple items in parallel for throughput
7. **Test with edge cases** — Empty fields, missing data, malformed input
8. **Monitor retry rates** — High retry rates indicate unclear schemas or prompts

## Resources
- Instructor: https://github.com/instructor-ai/instructor (⭐15k+)
- Outlines: https://github.com/dottxt-ai/outlines (⭐8k+)
- Guidance: https://github.com/guidance-ai/guidance (⭐18k+)
