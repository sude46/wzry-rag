"""BM25 keyword retrieval.

The index is built once at import time from the semantic chunks file.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import jieba
from rank_bm25 import BM25Okapi

if __name__ == "__main__":
    sys.path.insert(0, ".")

BASE_DIR = Path(__file__).resolve().parent.parent
CHUNKS_FILE = os.environ.get(
    "CHUNKS_FILE", str(BASE_DIR / "data" / "chunks" / "chunks_semantic.jsonl")
)
CHUNKS = [json.loads(line) for line in open(CHUNKS_FILE, encoding="utf-8")]
TOKENIZED = [list(jieba.lcut(c["text"])) for c in CHUNKS]
BM25 = BM25Okapi(TOKENIZED)


def bm25_search(query: str, k: int = 10) -> list[dict]:
    scores = BM25.get_scores(list(jieba.lcut(query)))
    top = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:k]
    return [
        {
            "text": CHUNKS[i]["text"],
            "metadata": {
                "doc_id": CHUNKS[i].get("doc_id", ""),
                "subject": CHUNKS[i].get("subject", ""),
                "type": CHUNKS[i].get("type", ""),
                "version": CHUNKS[i].get("version", ""),
                "source_url": CHUNKS[i].get("source_url", ""),
            },
            "score": float(scores[i]),
            "rank": rank,
        }
        for rank, i in enumerate(top)
        if scores[i] > 0
    ]


if __name__ == "__main__":
    q = sys.argv[1] if len(sys.argv) > 1 else "名刀被动"
    for r in bm25_search(q, k=5):
        print(
            f"[{r['rank'] + 1}] 分数={r['score']:.2f} | "
            f"{r['metadata']['subject']} | {r['text'][:60]}"
        )
