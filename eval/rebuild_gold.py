"""Rebuild dataset_80 with question-specific gold doc ids.

Usage:
    uv run python eval/rebuild_gold.py

Input:  eval/dataset_80.jsonl (frozen questions, old broad relevant lists)
Output: eval/dataset_80_v2.jsonl
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from eval.gold import BY_ID, build_entry  # noqa: E402

BASE_DIR = Path(__file__).resolve().parent.parent
SRC = BASE_DIR / "eval" / "dataset_80.jsonl"
OUT = BASE_DIR / "eval" / "dataset_80_v2.jsonl"


def main() -> None:
    rows = [json.loads(line) for line in SRC.read_text(encoding="utf-8").splitlines()]
    out = [build_entry(row) for row in rows]

    for row in out:
        assert row["id"]
        assert all(doc_id in BY_ID for doc_id in row["gold_doc_ids"])
        assert all(doc_id in BY_ID for doc_id in row["hard_negative_doc_ids"])
        assert not (set(row["gold_doc_ids"]) & set(row["hard_negative_doc_ids"]))
        if row["expect_refusal"]:
            assert row["gold_doc_ids"] == []
        else:
            assert row["gold_doc_ids"], row["id"]
        if row["type"] == "机制":
            assert row["skill_label"] in BY_ID[row["gold_doc_ids"][0]]["text"]

    OUT.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in out) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {OUT} ({len(out)} rows)")
    print("gold lengths:", {n: sum(len(r["gold_doc_ids"]) == n for r in out) for n in {0, 1, 2, 3}})
    print("refusal:", sum(r["expect_refusal"] for r in out))


if __name__ == "__main__":
    main()
