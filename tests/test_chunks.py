import json
from pathlib import Path


def test_semantic_chunks_have_doc_id_and_version():
    path = Path("data/chunks/chunks_semantic.jsonl")
    first = json.loads(path.read_text(encoding="utf-8").splitlines()[0])
    assert first["doc_id"]
    assert first["version"]


def test_all_semantic_chunks_are_traceable():
    path = Path("data/chunks/chunks_semantic.jsonl")
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    assert all(row.get("doc_id") for row in rows)
    assert all(row.get("source_url") for row in rows)
