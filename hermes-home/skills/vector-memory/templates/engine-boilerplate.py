"""
Lightweight embedding engine for agent memory.
Two FAISS tables:
  - Table 1 (long-term): Past conversations, saved memories, skills
  - Table 2 (short-term): Current project state, active tasks, recent context
Uses FastEmbed + AllMiniLM-L6-v2 (384-dim, optimized for ~250-char chunks).
"""

import os
import json
import time
import hashlib
from typing import Optional

import numpy as np
import faiss
from fastembed import TextEmbedding


# ── Config ──────────────────────────────────────────────────────────────────
WORKSPACE = "/host/d/mkt/python/hermes/workspace"
EMBED_DIR = os.path.join(WORKSPACE, "embedding_engine")
LONG_TERM_DB = os.path.join(EMBED_DIR, "long_term.index")
SHORT_TERM_DB = os.path.join(EMBED_DIR, "short_term.index")
META_FILE_LONG = os.path.join(EMBED_DIR, "meta_long.json")
META_FILE_SHORT = os.path.join(EMBED_DIR, "meta_short.json")
DIMENSION = 384


class EmbeddingEngine:
    """Two-table embedding engine for agent memory."""

    def __init__(self):
        self.embed_model = TextEmbedding(model_name="sentence-transformers/all-MiniLM-L6-v2")
        
        os.makedirs(EMBED_DIR, exist_ok=True)
        
        # Load or create FAISS indices
        if os.path.exists(LONG_TERM_DB):
            self.long_index = faiss.read_index(LONG_TERM_DB)
            self.long_meta = self._load_meta(META_FILE_LONG)
        else:
            self.long_index = faiss.IndexFlatIP(DIMENSION)
            self.long_meta = {"entries": [], "version": 1, "created_at": time.time()}
        
        if os.path.exists(SHORT_TERM_DB):
            self.short_index = faiss.read_index(SHORT_TERM_DB)
            self.short_meta = self._load_meta(META_FILE_SHORT)
        else:
            self.short_index = faiss.IndexFlatIP(DIMENSION)
            self.short_meta = {"entries": [], "version": 1, "created_at": time.time()}

    # ── Helpers ───────────────────────────────────────────────────────────
    def _load_meta(self, path):
        with open(path, "r") as f:
            return json.load(f)

    def _save_meta(self, meta, path):
        with open(path, "w") as f:
            json.dump(meta, f, indent=2)

    def _hash_id(self, content: str) -> str:
        return hashlib.md5(content.encode()).hexdigest()[:12]

    def _embed_batch(self, texts: list[str]) -> np.ndarray:
        embeddings = [np.array(e, dtype='float32') for e in self.embed_model.embed(texts)]
        arr = np.stack(embeddings)
        norms = np.linalg.norm(arr, axis=1, keepdims=True)
        norms[norms == 0] = 1
        arr = arr / norms
        return arr

    def _search(self, index, query_vec: np.ndarray, k: int = 5) -> tuple[np.ndarray, np.ndarray]:
        query_vec = query_vec.reshape(1, -1)
        return index.search(query_vec, min(k, index.ntotal))

    def _save_index(self, index, db_path: str, meta, meta_path: str):
        faiss.write_index(index, db_path)
        self._save_meta(meta, meta_path)

    # ── Add entries ───────────────────────────────────────────────────────
    def add_long_term(self, content: str, metadata: dict = None) -> str:
        entry_id = self._hash_id(content)
        if any(e.get("id") == entry_id for e in self.long_meta["entries"]):
            return entry_id
        
        embedding = self._embed_batch([content])[0]
        self.long_index.add(embedding.reshape(1, -1))
        
        entry = {
            "id": entry_id,
            "content": content[:500],
            "full_hash": hashlib.md5(content.encode()).hexdigest(),
            "metadata": metadata or {},
            "added_at": time.time(),
        }
        self.long_meta["entries"].append(entry)
        self._save_index(self.long_index, LONG_TERM_DB, self.long_meta, META_FILE_LONG)
        return entry_id

    def add_short_term(self, content: str, metadata: dict = None) -> str:
        entry_id = self._hash_id(content)
        if any(e.get("id") == entry_id for e in self.short_meta["entries"]):
            return entry_id
        
        embedding = self._embed_batch([content])[0]
        self.short_index.add(embedding.reshape(1, -1))
        
        entry = {
            "id": entry_id,
            "content": content[:500],
            "full_hash": hashlib.md5(content.encode()).hexdigest(),
            "metadata": metadata or {},
            "added_at": time.time(),
        }
        self.short_meta["entries"].append(entry)
        self._save_index(self.short_index, SHORT_TERM_DB, self.short_meta, META_FILE_SHORT)
        return entry_id

    # ── Query ─────────────────────────────────────────────────────────────
    def search(self, query: str, table: str = "both", k: int = 5) -> list[dict]:
        results = []
        query_emb = self._embed_batch([query])[0]
        
        if table in ("long", "both"):
            dists, idxs = self._search(self.long_index, query_emb, k)
            for d, i in zip(dists[0], idxs[0]):
                if i < 0: continue
                entry = self.long_meta["entries"][i]
                results.append({"table": "long", "score": float(d), **entry})
        
        if table in ("short", "both"):
            dists, idxs = self._search(self.short_index, query_emb, k)
            for d, i in zip(dists[0], idxs[0]):
                if i < 0: continue
                entry = self.short_meta["entries"][i]
                results.append({"table": "short", "score": float(d), **entry})
        
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:k]

    # ── Stats ─────────────────────────────────────────────────────────────
    def stats(self) -> dict:
        return {
            "long_term_entries": len(self.long_meta["entries"]),
            "short_term_entries": len(self.short_meta["entries"]),
            "total_entries": len(self.long_meta["entries"]) + len(self.short_meta["entries"]),
            "dimension": DIMENSION,
            "model": "sentence-transformers/all-MiniLM-L6-v2",
        }

    def clear_table(self, table: str):
        if table == "long":
            self.long_index = faiss.IndexFlatIP(DIMENSION)
            self.long_meta = {"entries": [], "version": 2, "created_at": time.time()}
            self._save_index(self.long_index, LONG_TERM_DB, self.long_meta, META_FILE_LONG)
        elif table == "short":
            self.short_index = faiss.IndexFlatIP(DIMENSION)
            self.short_meta = {"entries": [], "version": 2, "created_at": time.time()}
            self._save_index(self.short_index, SHORT_TERM_DB, self.short_meta, META_FILE_SHORT)


# ── CLI interface ───────────────────────────────────────────────────────────
def main():
    import sys
    
    engine = EmbeddingEngine()
    
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python engine.py search <query> [--table long|short|both] [--k 5]")
        print("  python engine.py add-long <content>")
        print("  python engine.py add-short <content>")
        print("  python engine.py stats")
        print("  python engine.py clear <long|short>")
        return
    
    cmd = sys.argv[1]
    
    if cmd == "search":
        query = " ".join(sys.argv[2:])
        table, k = "both", 5
        for i, arg in enumerate(sys.argv):
            if arg == "--table" and i + 1 < len(sys.argv):
                table = sys.argv[i + 1]
            if arg == "--k" and i + 1 < len(sys.argv):
                k = int(sys.argv[i + 1])
        results = engine.search(query, table=table, k=k)
        print(f"\nQuery: {query}\n")
        for r in results:
            print(f"--- [{r['table'].upper()}] score={r['score']:.4f} ---")
            print(r["content"])
            if r.get("metadata"):
                print(f"  metadata: {r['metadata']}")
            print()
        if not results:
            print("(no results)")
    
    elif cmd == "add-long":
        eid = engine.add_long_term(" ".join(sys.argv[2:]))
        print(f"Added to long-term: {eid}")
    
    elif cmd == "add-short":
        eid = engine.add_short_term(" ".join(sys.argv[2:]))
        print(f"Added to short-term: {eid}")
    
    elif cmd == "stats":
        for k, v in engine.stats().items():
            print(f"{k}: {v}")
    
    elif cmd == "clear":
        if len(sys.argv) < 3:
            print("Usage: python engine.py clear <long|short>")
            return
        engine.clear_table(sys.argv[2])
        print(f"Cleared {sys.argv[2]} table")


if __name__ == "__main__":
    main()
