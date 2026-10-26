"""Shared data contracts for retrieval, citations and answers."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class RetrievedChunk:
    doc_id: str = ""
    text: str = ""
    subject: str = ""
    type: str = ""
    source_url: str = ""
    version: str = ""
    score: float = 0.0
    vector_distance: float | None = None
    rrf_score: float | None = None
    rerank_score: float | None = None

    @classmethod
    def from_raw(cls, raw: dict[str, Any]) -> "RetrievedChunk":
        meta = raw.get("metadata") or {}
        if not isinstance(meta, dict):
            meta = {}
        return cls(
            doc_id=str(meta.get("doc_id") or raw.get("doc_id") or ""),
            text=str(raw.get("text") or raw.get("document") or ""),
            subject=str(meta.get("subject") or ""),
            type=str(meta.get("type") or ""),
            source_url=str(meta.get("source_url") or ""),
            version=str(meta.get("version") or ""),
            score=float(raw.get("score") or raw.get("rrf") or 0.0),
            vector_distance=(
                float(raw["distance"]) if raw.get("distance") is not None else None
            ),
            rrf_score=float(raw["rrf"]) if raw.get("rrf") is not None else None,
            rerank_score=(
                float(raw["rerank_score"]) if raw.get("rerank_score") is not None else None
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Citation:
    doc_id: str
    subject: str
    source_url: str
    type: str = ""
    used: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class AnswerResult:
    answer: str
    citations: list[Citation] = field(default_factory=list)
    refused: bool = False
    cached: bool = False
    request_id: str = ""
    trace: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "answer": self.answer,
            "citations": [c.to_dict() for c in self.citations],
            "refused": self.refused,
            "cached": self.cached,
            "request_id": self.request_id,
            "trace": self.trace,
        }
