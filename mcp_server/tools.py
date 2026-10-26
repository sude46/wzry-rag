"""MCP tools exposed by wzry-rag.

Keep return values JSON-serialisable and always include provenance so external
agents can cite the source.
"""
from __future__ import annotations

from pydantic import BaseModel

from pipeline import get_pipeline


class SearchHit(BaseModel):
    doc_id: str = ""
    subject: str = ""
    type: str = ""
    text: str = ""
    source_url: str = ""
    score: float = 0.0


def search_knowledge(
    query: str,
    k: int = 5,
    type: str | None = None,
) -> list[dict]:
    """检索王者荣耀知识库，返回相关文档列表（供外部 Agent 调用）。"""
    chunks = get_pipeline().search(query, k=k, type=type)
    return [
        SearchHit(
            doc_id=c.doc_id,
            subject=c.subject,
            type=c.type,
            text=c.text,
            source_url=c.source_url,
            score=c.rerank_score or c.rrf_score or c.score or 0.0,
        ).model_dump()
        for c in chunks
    ]


def get_hero(name: str) -> list[dict]:
    """按英雄名查询英雄介绍、技能与推荐出装。"""
    return search_knowledge(name, k=8, type=None)


def get_item(name: str) -> list[dict]:
    """按装备名查询装备价格、属性和被动。"""
    return search_knowledge(name, k=5, type="装备")
