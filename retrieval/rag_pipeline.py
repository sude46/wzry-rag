"""Vector retrieval + generation helpers shared by CLI, eval and API.

The prompt lives in prompts/answer_v2.txt so evaluation and production use
exactly the same instructions.
"""
from __future__ import annotations

import os
from pathlib import Path

import chromadb
from openai import OpenAI

from config import get_settings

settings = get_settings()
BASE_DIR = Path(__file__).resolve().parent.parent

client = OpenAI(
    base_url=settings.embed_base_url,
    api_key=settings.resolved_llm_api_key or "sk-placeholder",
    timeout=60,
    max_retries=2,
)
db = chromadb.PersistentClient(path=settings.chroma_path)
EMBED_MODEL = settings.embed_model
GEN_MODEL = settings.gen_model
PROMPT = (BASE_DIR / "prompts" / "answer_v2.txt").read_text(encoding="utf-8")


def _build_where(where: dict | None = None, version: str | None = None) -> dict | None:
    if version:
        version_cond = {"version": {"$eq": version}}
        if where:
            return {"$and": [where, version_cond]}
        return version_cond
    return where


def retrieve(
    query: str,
    collection: str | None = None,
    k: int | None = None,
    where: dict | None = None,
    version: str | None = None,
) -> list[dict]:
    """Vector search. Returns a list of {text, metadata, distance} dicts."""
    collection = collection or settings.collection
    k = k or settings.top_k
    col = db.get_collection(f"chunks_{collection}")
    qvec = client.embeddings.create(model=EMBED_MODEL, input=[query]).data[0].embedding
    r = col.query(
        query_embeddings=[qvec],
        n_results=k,
        where=_build_where(where, version),
    )
    return [
        {"text": doc, "metadata": meta, "distance": dist}
        for doc, meta, dist in zip(
            r["documents"][0], r["metadatas"][0], r["distances"][0]
        )
    ]


def generate(query: str, contexts: list[dict]) -> str:
    """Non-streaming generation used by eval and CLI."""
    ctx = "\n".join(
        f'<doc id="{i + 1}" subject="{c.get("metadata", {}).get("subject", "")}" '
        f'type="{c.get("metadata", {}).get("type", "")}">\n{c["text"]}\n</doc>'
        for i, c in enumerate(contexts)
    )
    prompt = PROMPT.format(context=ctx)
    r = client.chat.completions.create(
        model=GEN_MODEL,
        messages=[
            {"role": "user", "content": f"{prompt}\n\n问题：{query}"},
        ],
        temperature=0,
        timeout=60,
    )
    return r.choices[0].message.content or ""


if __name__ == "__main__":
    import sys

    q = sys.argv[1] if len(sys.argv) > 1 else "妲己二技能晕多久"
    ctxs = retrieve(q)
    ans = generate(q, ctxs)
    print(f"Q:{q}\n\nA:{ans}\n\n----依据---")
    for i, c in enumerate(ctxs):
        m = c["metadata"]
        print(f"[{i + 1}] {m.get('subject', '')}({m.get('type', '')}) 距离={c['distance']:.3f}")
