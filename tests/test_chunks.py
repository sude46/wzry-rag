import json
from pathlib import Path


def test_semantic_chunks_have_doc_id_and_version():
    path = Path("data/chunks/chunks_semantic.jsonl")
    first = json.loads(path.read_text(encoding="utf-8").splitlines()[0])
    assert first["doc_id"]
    assert first["doc_ids"] == [first["doc_id"]]
    assert first["version"]


def test_fixed_and_heading_chunks_have_doc_mapping():
    for name in ("fixed", "heading"):
        path = Path(f"data/chunks/chunks_{name}.jsonl")
        first = json.loads(path.read_text(encoding="utf-8").splitlines()[0])
        assert first["doc_ids"]
        assert all(doc_id for doc_id in first["doc_ids"])


def test_all_semantic_chunks_are_traceable():
    path = Path("data/chunks/chunks_semantic.jsonl")
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    assert all(row.get("doc_id") for row in rows)
    assert all(row.get("source_url") for row in rows)
