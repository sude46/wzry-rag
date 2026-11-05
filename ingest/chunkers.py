"""Build three chunking strategies from data/processed/docs.jsonl.

Usage: uv run python ingest/chunkers.py
"""
from __future__ import annotations

import json
from pathlib import Path

DOCS = Path("data/processed/docs.jsonl")
OUT = Path("data/chunks")
OUT.mkdir(parents=True, exist_ok=True)
DEFAULT_VERSION = "2016-snapshot"

docs = [json.loads(line) for line in open(DOCS, encoding="utf-8")]


def make_chunk(
    cid: str,
    strategy: str,
    text: str,
    doc_id: str = "",
    subject: str = "",
    type_: str = "",
    version: str = "",
    source_url: str = "",
    doc_ids: list[str] | None = None,
) -> dict:
    return {
        "chunk_id": cid,
        "doc_id": doc_id,
        "doc_ids": doc_ids or ([doc_id] if doc_id else []),
        "strategy": strategy,
        "text": text,
        "subject": subject,
        "type": type_,
        "version": version or DEFAULT_VERSION,
        "source_url": source_url,
    }


# ---------- strategy 1: fixed length ----------
CHARS_PER_TOKEN = 1.5
CHUNK = int(512 * CHARS_PER_TOKEN)
OVERLAP = int(50 * CHARS_PER_TOKEN)

parts: list[str] = []
spans: list[tuple[int, int, str]] = []
pos = 0
for d in docs:
    if parts:
        parts.append("\n")
        pos += 1
    start = pos
    parts.append(d["text"])
    pos += len(d["text"])
    spans.append((start, pos, d["doc_id"]))
river = "".join(parts)

fixed = []
i, n = 0, 0
while i < len(river):
    chunk = river[i : i + CHUNK]
    end = i + len(chunk)
    doc_ids: list[str] = []
    for start, stop, doc_id in spans:
        if start < end and stop > i and doc_id not in doc_ids:
            doc_ids.append(doc_id)
    fixed.append(
        make_chunk(
            f"fixed_{n:04d}",
            "fixed",
            chunk,
            doc_ids=doc_ids,
            version=DEFAULT_VERSION,
        )
    )
    i += CHUNK - OVERLAP
    n += 1

# ---------- strategy 2: heading / paragraph ----------
groups: dict[tuple[str, str], list[dict]] = {}
for d in docs:
    groups.setdefault((d["subject"], d["type"]), []).append(d)

heading = []
for (subject, type_), ds in groups.items():
    text = "\n".join(x["text"] for x in ds)
    heading.append(
        make_chunk(
            f"heading_{len(heading):04d}",
            "heading",
            text,
            doc_id=ds[0].get("doc_id", ""),
            doc_ids=[x["doc_id"] for x in ds],
            subject=subject,
            type_=type_,
            version=ds[0].get("version") or DEFAULT_VERSION,
            source_url=ds[0].get("source_url", ""),
        )
    )

# ---------- strategy 3: semantic / per-document ----------
semantic = [
    make_chunk(
        f"semantic_{i:04d}",
        "semantic",
        d["text"],
        doc_id=d.get("doc_id", ""),
        doc_ids=[d["doc_id"]],
        subject=d["subject"],
        type_=d["type"],
        version=d.get("version") or DEFAULT_VERSION,
        source_url=d.get("source_url", ""),
    )
    for i, d in enumerate(docs)
]


def dump(name: str, chunks: list[dict]) -> None:
    with open(OUT / name, "w", encoding="utf-8") as f:
        for c in chunks:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")
    lens = [len(c["text"]) for c in chunks]
    print(
        f"{name:24s} chunk数={len(chunks):5d}  "
        f"平均长度={sum(lens) / len(lens):6.0f}  "
        f"最大={max(lens):5d}  最小={min(lens):4d}"
    )


if __name__ == "__main__":
    dump("chunks_fixed.jsonl", fixed)
    dump("chunks_heading.jsonl", heading)
    dump("chunks_semantic.jsonl", semantic)
