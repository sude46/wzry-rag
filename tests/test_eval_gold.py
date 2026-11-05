import json
from pathlib import Path

from eval.metrics import ranking_metrics


def _rows():
    path = Path("eval/dataset_80_v2.jsonl")
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_v2_dataset_has_one_gold_doc_per_answerable_question():
    rows = _rows()
    assert len(rows) == 80
    assert sum(r["expect_refusal"] for r in rows) == 8
    for row in rows:
        if row["expect_refusal"]:
            assert row["gold_doc_ids"] == []
        else:
            assert len(row["gold_doc_ids"]) >= 1
        assert not (set(row["gold_doc_ids"]) & set(row["hard_negative_doc_ids"]))


def test_mechanic_gold_points_to_requested_skill():
    docs = {
        json.loads(line)["doc_id"]: json.loads(line)
        for line in Path("data/processed/docs.jsonl").read_text(encoding="utf-8").splitlines()
    }
    for row in _rows():
        if row["type"] != "机制":
            continue
        gold = docs[row["gold_doc_ids"][0]]
        assert f"{row['subject']}的{row['skill_label']}「" in gold["text"]


def test_doc_level_metrics_penalize_wrong_skill():
    metrics = ranking_metrics(
        retrieved_doc_ids=["hero_1_skill_1", "hero_1_skill_2"],
        gold_doc_ids=["hero_1_skill_0"],
        hard_negative_doc_ids=["hero_1_skill_1", "hero_1_skill_2"],
    )
    assert metrics["hit@1"] is False
    assert metrics["hit@5"] is False
    assert metrics["recall@5"] == 0.0
    assert metrics["wrong_negative"] is True


def test_doc_level_mrr_and_recall():
    metrics = ranking_metrics(
        retrieved_doc_ids=["x", "hero_1_skill_2", "hero_1_skill_0"],
        gold_doc_ids=["hero_1_skill_0"],
        hard_negative_doc_ids=["hero_1_skill_2"],
    )
    assert metrics["hit@1"] is False
    assert metrics["hit@3"] is True
    assert metrics["mrr"] == 1 / 3
    assert metrics["recall@5"] == 1.0
    assert metrics["wrong_negative"] is False
