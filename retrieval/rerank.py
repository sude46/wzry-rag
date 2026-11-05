"""Rerank: coarse top-20 -> rerank -> top-k.

Backends: RERANK_BACKEND=llm (general LLM scoring) / bge (cross-encoder, default).
API credentials come from config.py (which reads .env), never os.environ directly.
"""
from __future__ import annotations

import logging
import sys
import time

import requests

sys.path.insert(0, ".")

from config import RetrievalConfigError, get_settings  # noqa: E402
from retrieval.hybrid import retrieve_hybrid  # noqa: E402
from retrieval.rag_pipeline import GEN_MODEL, client  # noqa: E402

settings = get_settings()
BACKEND = settings.rerank_backend
logger = logging.getLogger(__name__)

RERANK_PROMPT = """判断下面的资料是否能直接帮助回答问题。
只回答一个数字: 2=直接相关(包含答案), 1=部分相关(同主题但不直接回答), 0=无关。
不要输出任何其他内容。

问题: {query}
资料: {text}
评分:"""


def _require_key() -> str:
    key = settings.embed_api_key
    if not key:
        raise RetrievalConfigError(
            "rerank 需要 EMBED_API_KEY，但配置里没有。请检查 .env 或环境变量。"
        )
    return key


def _rerank_url() -> str:
    return f"{settings.embed_base_url.rstrip('/')}/rerank"


def llm_score(query: str, text: str) -> int:
    r = client.chat.completions.create(
        model=GEN_MODEL,
        messages=[
            {
                "role": "user",
                "content": RERANK_PROMPT.format(query=query, text=text[:300]),
            }
        ],
        temperature=0,
        max_tokens=4,
    )
    s = (r.choices[0].message.content or "").strip()
    return int(s) if s and s[0] in "012" else 0


def bge_rerank(query: str, pool: list[dict], k: int) -> list[dict]:
    """Cross-encoder rerank. Raises on configuration/HTTP/schema errors."""
    if not pool:
        return []
    resp = requests.post(
        _rerank_url(),
        headers={"Authorization": f"Bearer {_require_key()}"},
        json={
            "model": settings.rerank_model,
            "query": query,
            "documents": [c["text"] for c in pool],
            "top_n": min(k, len(pool)),
        },
        timeout=settings.rerank_timeout,
    )
    resp.raise_for_status()
    data = resp.json()
    results = data.get("results")
    if not isinstance(results, list):
        raise RuntimeError(f"rerank response missing results: {data}")

    ranked: list[dict] = []
    for item in results:
        idx = item.get("index")
        if not isinstance(idx, int) or not 0 <= idx < len(pool):
            raise RuntimeError(f"rerank returned invalid index: {item}")
        ranked.append(
            pool[idx] | {"rerank_score": round(float(item["relevance_score"]), 3)}
        )
    return ranked


def retrieve_rerank(query: str, collection: str = "semantic", k: int = 5) -> list[dict]:
    t0 = time.time()
    pool = retrieve_hybrid(query, collection=collection, k=max(20, k))
    t_coarse = time.time() - t0

    t0 = time.time()
    if BACKEND == "bge":
        top = bge_rerank(query, pool, k)
    else:
        for c in pool:
            c["rerank_score"] = llm_score(query, c["text"])
        pool.sort(key=lambda c: c["rerank_score"], reverse=True)
        top = pool[:k]
    t_rerank = time.time() - t0

    logger.info(
        "rerank backend=%s coarse=%.2fs rerank=%.2fs",
        BACKEND,
        t_coarse,
        t_rerank,
    )
    return top


if __name__ == "__main__":
    q = sys.argv[1] if len(sys.argv) > 1 else "名刀被动是什么"
    for i, c in enumerate(retrieve_rerank(q)):
        m = c["metadata"]
        print(
            f"[{i + 1}] 相关性={c.get('rerank_score')} | "
            f"{m.get('subject', '')}({m.get('type', '')}) | {c['text'][:60]}"
        )
