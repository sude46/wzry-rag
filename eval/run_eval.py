"""Doc-level retrieval evaluation.

Default: eval/dataset_80_v2.jsonl, hybrid retrieval, retrieval only (GEN=0).
Usage:
    uv run python eval/run_eval.py [dataset]
    GEN=1 uv run python eval/run_eval.py eval/dataset_80_v2.jsonl
    RETRIEVER=vector|hybrid|bm25|rerank ...
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import time
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from eval.metrics import mean_metric, ranking_metrics  # noqa: E402
from retrieval.rag_pipeline import generate, retrieve  # noqa: E402

RETRIEVER = os.environ.get("RETRIEVER", "hybrid")
if RETRIEVER == "hybrid":
    from retrieval.hybrid import retrieve_hybrid as retrieve  # noqa: F811
elif RETRIEVER == "rerank":
    from retrieval.rerank import retrieve_rerank as retrieve  # noqa: F811
elif RETRIEVER == "bm25":
    from retrieval.bm25 import bm25_search

    def retrieve(q, k=5, **_):
        return [
            {"text": r["text"], "metadata": r["metadata"]}
            for r in bm25_search(q, k=k)
        ]

K = int(os.environ.get("K", "5"))
COLLECTION = os.environ.get("COLLECTION", "semantic")
DATASET = sys.argv[1] if len(sys.argv) > 1 else "eval/dataset_80_v2.jsonl"
GEN = os.environ.get("GEN", "0") != "0"

# Map returned chunk text back to all source docs. This is needed for fixed
# chunks and for older indexes that only stored one doc_id.
TEXT_TO_DOCS: dict[str, list[str]] = {}
chunks_path = Path("data/chunks") / f"chunks_{COLLECTION}.jsonl"
if chunks_path.exists():
    for line in chunks_path.read_text(encoding="utf-8").splitlines():
        c = json.loads(line)
        ids = c.get("doc_ids") or ([c["doc_id"]] if c.get("doc_id") else [])
        TEXT_TO_DOCS[c["text"]] = ids


def _retrieve(q: str) -> list[dict]:
    if RETRIEVER in {"hybrid", "rerank", "vector"}:
        return retrieve(q, collection=COLLECTION, k=K)
    return retrieve(q, k=K)


def _doc_ids(item: dict) -> list[str]:
    meta = item.get("metadata") or {}
    raw = meta.get("doc_ids") or ""
    if isinstance(raw, list):
        ids = [str(x) for x in raw if x]
    else:
        ids = [x for x in str(raw).split(",") if x]
    if not ids and meta.get("doc_id"):
        ids = [str(meta["doc_id"])]
    mapped = TEXT_TO_DOCS.get(item.get("text", ""), [])
    # Heading chunks can cover several docs; prefer the full chunk mapping.
    if mapped and len(mapped) > len(ids):
        ids = mapped
    return ids


REFUSE_WORDS = [
    "未收录",
    "没有收录",
    "没有找到相关内容",
    "无法回答",
    "资料中没有",
    "无法确定",
]


def run_one(row: dict) -> tuple[str, dict]:
    q = row["question"]
    ctxs = _retrieve(q)
    ans = generate(q, ctxs) if GEN else ""
    retrieved_ids: list[str] = []
    for item in ctxs:
        for doc_id in _doc_ids(item):
            if doc_id and doc_id not in retrieved_ids:
                retrieved_ids.append(doc_id)

    rec = {
        "id": row.get("id"),
        "question": q,
        "type": row.get("type", row.get("category")),
        "subject": row.get("subject"),
        "answer": ans,
        "ground_truth": row.get("ground_truth", ""),
        "retrieved_doc_ids": retrieved_ids,
        "retrieved_subjects": [c.get("metadata", {}).get("subject", "") for c in ctxs],
        "contexts": [c["text"] for c in ctxs],
    }

    expect_refusal = bool(row.get("expect_refusal", row.get("type") == "拒答"))
    if expect_refusal:
        rec["refused"] = any(word in ans for word in REFUSE_WORDS)
        return "refuse", rec

    gold = row.get("gold_doc_ids")
    if gold is None:
        # Backward compatibility for the old broad dataset.
        gold = row.get("relevant_doc_ids", [])
        print(f"[legacy] {row.get('id')} uses broad relevant_doc_ids")
    hard = row.get("hard_negative_doc_ids", [])
    rec.update(ranking_metrics(retrieved_ids, gold, hard, K))
    return "normal", rec


def run_one_safe(row: dict) -> tuple[str, dict]:
    for attempt in range(3):
        try:
            return run_one(row)
        except Exception as exc:
            # Config errors should not be retried for a minute.
            if type(exc).__name__ in {"RetrievalConfigError", "RuntimeError"}:
                raise
            print(f"[retry {attempt + 1}/3] {row.get('question', '')[:24]}: {type(exc).__name__}")
            time.sleep(5)
    raise


def main() -> None:
    rows = [json.loads(line) for line in Path(DATASET).read_text(encoding="utf-8").splitlines()]
    print(f"dataset={DATASET} rows={len(rows)} retriever={RETRIEVER} collection={COLLECTION} K={K} gen={GEN}")

    results: list[dict] = []
    refusals: list[dict] = []
    for i, row in enumerate(rows, 1):
        kind, rec = run_one_safe(row)
        (refusals if kind == "refuse" else results).append(rec)
        print(f"[{i:2d}/{len(rows)}] {rec['question'][:34]}")

    n = len(results)
    print(f"\n===== {Path(DATASET).stem} | {RETRIEVER} | K={K} | answerable={n} =====")
    for name in ("hit@1", "hit@3", "hit@5", "recall@5", "mrr", "wrong_negative"):
        print(f"{name:16s}= {mean_metric(results, name):.3f}")

    print("\nby category:")
    grouped: dict[str, list[dict]] = defaultdict(list)
    for rec in results:
        grouped[rec["type"]].append(rec)
    for category, recs in sorted(grouped.items()):
        print(
            f"  {category}: n={len(recs)} "
            f"Hit@1={mean_metric(recs, 'hit@1'):.2f} "
            f"Hit@5={mean_metric(recs, 'hit@5'):.2f} "
            f"MRR={mean_metric(recs, 'mrr'):.2f} "
            f"wrong={mean_metric(recs, 'wrong_negative'):.2f}"
        )

    if refusals and GEN:
        ok = sum(r["refused"] for r in refusals)
        print(f"\nrefusal correct = {ok}/{len(refusals)}")

    try:
        git_sha = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], text=True, stderr=subprocess.DEVNULL
        ).strip()
    except Exception:
        git_sha = "unknown"
    meta = {
        "dataset": str(DATASET),
        "dataset_sha256": hashlib.sha256(Path(DATASET).read_bytes()).hexdigest(),
        "git_sha": git_sha,
        "retriever": RETRIEVER,
        "collection": COLLECTION,
        "k": K,
        "gen": GEN,
        "index_version": os.environ.get("INDEX_VERSION", "v1"),
        "prompt_version": os.environ.get("PROMPT_VERSION", "v2"),
        "model": os.environ.get("GEN_MODEL", "Qwen/Qwen2.5-7B-Instruct"),
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }

    out_dir = Path("eval/results")
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    out = out_dir / f"{Path(DATASET).stem}_{RETRIEVER}_{COLLECTION}_{stamp}.jsonl"
    with out.open("w", encoding="utf-8") as f:
        for rec in results + refusals:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    out.with_suffix(".meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"\nwrote {out}")
    print(f"wrote {out.with_suffix('.meta.json')}")


if __name__ == "__main__":
    main()
