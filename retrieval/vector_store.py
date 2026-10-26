"""Vector retrieval CLI.

Usage:
    uv run python retrieval/vector_store.py "名刀被动是什么" -c semantic -k 5
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import chromadb
from openai import OpenAI

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import get_settings  # noqa: E402

parser = argparse.ArgumentParser()
parser.add_argument("query")
parser.add_argument("-c", "--collection", default="semantic")
parser.add_argument("-k", "--topk", type=int, default=5)
parser.add_argument("--type", default=None, help="按 type 过滤")
parser.add_argument("--subject", default=None, help="按 subject 过滤")
args = parser.parse_args()

settings = get_settings()
client = OpenAI(
    base_url=settings.embed_base_url,
    api_key=settings.resolved_llm_api_key or "sk-placeholder",
)
db = chromadb.PersistentClient(path=settings.chroma_path)
col = db.get_collection(f"chunks_{args.collection}")

qvec = client.embeddings.create(
    model=settings.embed_model,
    input=[args.query],
).data[0].embedding

conditions = []
if args.type:
    conditions.append({"type": {"$eq": args.type}})
if args.subject:
    conditions.append({"subject": {"$eq": args.subject}})
where = conditions[0] if len(conditions) == 1 else ({"$and": conditions} if conditions else None)

r = col.query(query_embeddings=[qvec], n_results=args.topk, where=where)
for i in range(len(r["ids"][0])):
    m = r["metadatas"][0][i]
    print(f"[{i + 1}] 距离={r['distances'][0][i]:.4f} | {m['subject']}({m['type']}) | {m['source_url']}")
    print(f"    {r['documents'][0][i][:100]}\n")
