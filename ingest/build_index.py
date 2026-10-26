"""Upsert chunks into Chroma.

Usage:
    uv run python ingest/build_index.py
    uv run python ingest/build_index.py --collections semantic
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import chromadb
from openai import OpenAI

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import get_settings  # noqa: E402

settings = get_settings()
CHUNKS_DIR = Path("data/chunks")
BATCH = 64


def embed(client: OpenAI, texts: list[str]) -> list[list[float]]:
    r = client.embeddings.create(model=settings.embed_model, input=texts)
    return [d.embedding for d in r.data]


def build(collections: list[str], index_version: str) -> None:
    client = OpenAI(
        base_url=settings.embed_base_url,
        api_key=settings.resolved_llm_api_key,
        timeout=60,
        max_retries=2,
    )
    db = chromadb.PersistentClient(path=settings.chroma_path)

    for name in collections:
        path = CHUNKS_DIR / f"chunks_{name}.jsonl"
        chunks = [json.loads(line) for line in open(path, encoding="utf-8")]
        col = db.get_or_create_collection(
            f"chunks_{name}", metadata={"hnsw:space": "cosine"}
        )

        for i in range(0, len(chunks), BATCH):
            batch = chunks[i : i + BATCH]
            col.upsert(
                ids=[c["chunk_id"] for c in batch],
                embeddings=embed(client, [c["text"] for c in batch]),
                documents=[c["text"] for c in batch],
                metadatas=[
                    {
                        "doc_id": c.get("doc_id", ""),
                        "subject": c.get("subject", ""),
                        "type": c.get("type", ""),
                        "version": c.get("version", ""),
                        "source_url": c.get("source_url", ""),
                        "index_version": index_version,
                    }
                    for c in batch
                ],
            )
            print(f"chunks_{name}: {min(i + BATCH, len(chunks))}/{len(chunks)}")
        print(f"chunks_{name} done, total={col.count()}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--collections",
        default="fixed,heading,semantic",
        help="comma-separated: fixed,heading,semantic",
    )
    parser.add_argument("--index-version", default=settings.index_version)
    args = parser.parse_args()
    build([x.strip() for x in args.collections.split(",") if x.strip()], args.index_version)


if __name__ == "__main__":
    main()
