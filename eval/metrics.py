"""Pure ranking metrics for doc-level evaluation."""
from __future__ import annotations

from collections.abc import Iterable


def ranking_metrics(
    retrieved_doc_ids: Iterable[str],
    gold_doc_ids: Iterable[str],
    hard_negative_doc_ids: Iterable[str] = (),
    k: int = 5,
) -> dict:
    top = list(retrieved_doc_ids)[:k]
    gold = set(gold_doc_ids)
    hard = set(hard_negative_doc_ids)
    positions = [i + 1 for i, doc_id in enumerate(top) if doc_id in gold]

    def hit_at(n: int) -> bool:
        return any(pos <= n for pos in positions)

    return {
        "hit@1": hit_at(1),
        "hit@3": hit_at(3),
        "hit@5": hit_at(5),
        "recall@5": (len(set(top) & gold) / len(gold)) if gold else 0.0,
        "mrr": (1.0 / positions[0]) if positions else 0.0,
        # A hard negative is a same-hero/same-category distractor. Count it as
        # "wrong skill/entity" only when no gold document was retrieved.
        "wrong_negative": bool(not positions and any(doc_id in hard for doc_id in top)),
    }


def mean_metric(records: list[dict], name: str) -> float:
    if not records:
        return 0.0
    return sum(float(r[name]) for r in records) / len(records)
