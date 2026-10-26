"""Hybrid retrieval = vector top-k + BM25 top-k, fused with RRF.

Also handles slang expansion while preserving the original vector distance so
the refusal gate still has a signal in hybrid mode.
"""
from __future__ import annotations

import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, ".")

from retrieval.bm25 import bm25_search  # noqa: E402
from retrieval.rag_pipeline import retrieve  # noqa: E402

BASE_DIR = Path(__file__).resolve().parent.parent
SYNONYMS = json.loads((BASE_DIR / "eval" / "synonyms.json").read_text(encoding="utf-8"))
RRF_K = 60  # standard RRF smoothing constant


def _casefold(text: str) -> str:
    return text.casefold()


def expand_query(query: str) -> str:
    """Append official names for slang hits.

    - ASCII is matched case-insensitively ("cd鞋" == "CD鞋").
    - Longest slang wins, so "名刀·司命" does not also trigger a second slang.
    - The official name is appended once even when it is already present:
      BM25 benefits from the repeated term, while rerank uses the original
      query rather than this expanded string.
    """
    q = query.strip()
    folded = _casefold(q)
    extra: list[str] = []
    for slang, official in sorted(SYNONYMS.items(), key=lambda item: len(item[0]), reverse=True):
        if _casefold(slang) in folded and official not in extra:
            extra.append(official)
    return q + "".join(extra)


def _safe_result(future, default):
    try:
        return future.result()
    except Exception:
        return default


def retrieve_hybrid(
    query: str,
    collection: str = "semantic",
    k: int = 5,
    version: str | None = None,
) -> list[dict]:
    q2 = expand_query(query)
    with ThreadPoolExecutor(max_workers=2) as pool:
        vec_future = pool.submit(retrieve, q2, collection, 10, None, version)
        bm_future = pool.submit(bm25_search, q2, 10)
        vec = _safe_result(vec_future, [])
        bm = _safe_result(bm_future, [])

    scores: dict[str, float] = {}
    pool_by_text: dict[str, dict] = {}
    for rank, c in enumerate(vec):
        key = c["text"]
        scores[key] = scores.get(key, 0.0) + 1.0 / (RRF_K + rank + 1)
        pool_by_text[key] = c
    for c in bm:
        key = c["text"]
        scores[key] = scores.get(key, 0.0) + 1.0 / (RRF_K + c["rank"] + 1)
        pool_by_text.setdefault(key, c)

    top = sorted(scores, key=scores.get, reverse=True)[:k]
    results = []
    for text in top:
        source = pool_by_text[text]
        item = {
            "text": text,
            "metadata": source.get("metadata", {}),
            "rrf": scores[text],
        }
        if source.get("distance") is not None:
            item["distance"] = source["distance"]
        results.append(item)
    return results


if __name__ == "__main__":
    q = sys.argv[1] if len(sys.argv) > 1 else "帽子是哪个装备"
    for i, c in enumerate(retrieve_hybrid(q)):
        m = c["metadata"]
        print(
            f"[{i + 1}] RRF={c['rrf']:.4f} | "
            f"{m.get('subject', '')}({m.get('type', '')}) | {c['text'][:60]}"
        )
