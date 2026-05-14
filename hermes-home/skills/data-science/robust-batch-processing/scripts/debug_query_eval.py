"""debug_query_eval.py — Evaluate semantic search quality by showing raw results per query.

Usage:
  python3 debug_query_eval.py --queries "what did we work on|how do I fix errors"
  python3 debug_query_eval.py --table short_user --k 5

Shows full content snippets from each table type so user can judge relevance.
"""

import json, sys, argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from fastembed import TextEmbedding
import numpy as np
import faiss

DIM = 384
model = TextEmbedding(model_name='sentence-transformers/all-MiniLM-L6-v2')

def load_tables(table_filter=None):
    meta_store, indices = {}, {}
    for name in ['short_user', 'short_assistant', 'short_tool']:
        if table_filter and table_filter != name: continue
        with open(f'meta_{name}.json') as f:
            meta_store[name] = json.load(f)
        indices[name] = faiss.read_index(f'{name}.index')
    return meta_store, indices

def search(query, meta_store, indices, k=3):
    emb = np.array(list(model.embed([query]))[0], dtype='float32')
    if np.linalg.norm(emb) > 0:
        emb = emb / np.linalg.norm(emb)
    
    results = []
    for name, idx in indices.items():
        if idx.ntotal == 0: continue
        nk = min(k, idx.ntotal)
        dists, ids_ = idx.search(emb.reshape(1,-1), nk)
        for d, i in zip(dists[0], ids_[0]):
            if i < 0: continue
            e = meta_store[name]['entries'][i]
            results.append({
                'type': name.split('_')[-1],
                'score': float(d),
                'content': e['content'],
            })
    results.sort(key=lambda x: x['score'], reverse=True)
    return results

def clean(text, max_lines=3):
    text = text.replace('\\n', '\n').replace('\\\\', '\\')
    lines = [l.strip() for l in text.split('\n') if l.strip()]
    return '\n'.join(lines[:max_lines]) + ('...' if len(text) > 200 else '')

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--queries', type=str, help='Queries separated by |')
    parser.add_argument('--query-file', type=str, help='File with one query per line')
    parser.add_argument('--table', type=str, help='Filter to single table')
    parser.add_argument('--k', type=int, default=3)
    args = parser.parse_args()
    
    meta_store, indices = load_tables(args.table)
    
    if args.query_file:
        with open(args.query_file) as f:
            queries = [l.strip() for l in f if l.strip()]
    elif args.queries:
        queries = [q.strip() for q in args.queries.split('|')]
    else:
        print("Need --queries or --query-file")
        sys.exit(1)
    
    for q in queries:
        print(f"\n{'='*80}")
        print(f"Q: \"{q}\"")
        print(f"{'='*80}")
        
        results = search(q, meta_store, indices, k=args.k)
        if not results:
            print("  (no results)")
            continue
        
        # Show top result per type
        seen = set()
        for r in results[:15]:
            t = r['type'].replace('users','user').replace('assistants','assistant').replace('tools','tool')
            if t in seen: continue
            seen.add(t)
            print(f"\n[{t}] score={r['score']:.4f}")
            print(clean(r['content']))

if __name__ == "__main__":
    main()
