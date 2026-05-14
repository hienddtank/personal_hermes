# FastEmbed Supported Models Reference

## Quick Pick Guide

### For short text chunks (up to 512 tokens / ~250 chars)
| Model | Dim | Size | Speed | Notes |
|-------|-----|------|-------|-------|
| `sentence-transformers/all-MiniLM-L6-v2` | 384 | ~23MB | ⚡ Fastest (~15ms) | Contrastive-trained, best for short text, excellent at negative filtering |
| `BAAI/bge-small-en-v1.5` | 384 | ~67MB | Fast | Default in FastEmbed, supports query/doc prefixes |
| `snowflake/snowflake-arctic-embed-xs` | 384 | ~90MB | Fast | Snowflake's smallest, purpose-built for embeddings |

### For medium text (up to 512 tokens)
| Model | Dim | Size | Speed | Notes |
|-------|-----|------|-------|-------|
| `BAAI/bge-base-en-v1.5` | 768 | ~210MB | Medium | Good balance of quality/speed |
| `snowflake/snowflake-arctic-embed-s` | 384 | ~130MB | Medium | Arctic S variant |

### For long text / RAG (up to 2048+ tokens)
| Model | Dim | Size | Speed | Notes |
|-------|-----|------|-------|-------|
| `snowflake/snowflake-arctic-embed-m-long` | 768 | ~540MB | Slow | 2048 token truncation, extended context |
| `jinaai/jina-embeddings-v3` | 1024 | ~2.3GB | Slowest | Multi-task (~100 langs), query/doc prefixes, multimodal tasks |

### Key Finding (from Ben Terhechte benchmark)
For small chunks specifically:
- **AllMiniLM-L6-V2** achieves near-zero scores for irrelevant matches (~0.10) — excellent at saying "NOT related"
- Contrastive training makes it push similar things together, dissimilar apart
- For 500-word chunks: AllMiniLML12V2 scored highest on accuracy (0.4591)
- Larger models (Qwen3) win on large chunks (>3000 words) due to 32K context window

## Full Model List
Always call `TextEmbedding.list_supported_models()` in the container — models and URLs may change. FastEmbed caches downloaded models in its local cache directory after first download.
