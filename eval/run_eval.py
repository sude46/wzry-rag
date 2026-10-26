"""
Day5+: 跑评估集, 计算检索指标 Hit@5/Recall@5/MRR(subject匹配代理)
用法: uv run python eval/run_eval.py [数据集路径, 默认eval/dataset_seed.jsonl]
环境变量 RETRIEVER: 空=纯向量 / hybrid=混合 / rerank=混合+重排
拒答题(type==拒答)不计入检索指标, 单独统计拒答正确率
"""
import json
import sys
import os
from collections import defaultdict
from pathlib import Path
sys.path.insert(0, ".")
from retrieval.rag_pipeline import retrieve, generate

RETRIEVER = os.environ.get("RETRIEVER", "hybrid")
if RETRIEVER == "hybrid":
    from retrieval.hybrid import retrieve_hybrid as retrieve
elif RETRIEVER == "rerank":
    from retrieval.rerank import retrieve_rerank as retrieve

SYNONYMS = json.load(open("eval/synonyms.json", encoding="utf-8"))
ALIAS = {}
for slang, official in SYNONYMS.items():
    group = {slang, official}
    for name in group:
        ALIAS.setdefault(name, set()).update(group)

K = 5
COLLECTION = os.environ.get("COLLECTION", "semantic")
if RETRIEVER == "bm25":
    from retrieval.bm25 import bm25_search
    def retrieve(q, k=K, **_):
        return [{"text": r["text"], "metadata": r["metadata"]} for r in bm25_search(q, k=k)]
else:
    _base_retrieve = retrieve
    def retrieve(q, k=K, **_):
        return _base_retrieve(q, collection=COLLECTION, k=k)

DATASET = sys.argv[1] if len(sys.argv) > 1 else "eval/dataset_seed.jsonl"
rows = [json.loads(l) for l in open(DATASET, encoding="utf-8")]
print(f"数据集: {DATASET} ({len(rows)}条)  分块: {COLLECTION}  检索器: {RETRIEVER}")

REFUSE_WORDS = [
    "未收录",
    "没有收录",
    "没有找到相关内容",
    "无法回答",
    "资料中没有",
    "无法确定",
]

from concurrent.futures import ThreadPoolExecutor
GEN = os.environ.get("GEN", "1") != "0"

def run_one(row):
    q = row["question"]
    ctxs = retrieve(q, k=K)
    ans = generate(q, ctxs) if GEN else ""
    rtype = row.get("category", row.get("type"))
    rec = {"id": row.get("id"), "question": q, "answer": ans,
           "ground_truth": row["ground_truth"], "category": rtype,
           "subject": row.get("subject"),
           "contexts": [c["text"] for c in ctxs]}
    if rtype == "\u62d2\u7b54":
        rec["refused"] = any(w in ans for w in REFUSE_WORDS)
        return "refuse", rec
    targets = ALIAS.get(row["subject"], {row["subject"]})
    hits = [(c["metadata"].get("subject") in targets if c["metadata"].get("subject")
                else any(t in c["text"] for t in targets)) for c in ctxs]
    rec["hit"] = any(hits)
    rec["recall5"] = sum(hits) / K
    rec["mrr"] = next((1.0 / (i + 1) for i, h in enumerate(hits) if h), 0.0)
    return "normal", rec

import time

def run_one_safe(row):
    """限流/抖动自动重试3次, 每次等20秒"""
    for attempt in range(3):
        try:
            return run_one(row)
        except Exception as e:
            print(f"[重试{attempt+1}/3] {row.get('question','')[:20]}: {type(e).__name__}")
            time.sleep(20)
    raise

results = []
refuse_results = []
with ThreadPoolExecutor(max_workers=int(os.environ.get("WORKERS","4"))) as pool:
    for i, (kind, rec) in enumerate(pool.map(run_one_safe, rows), 1):
        (refuse_results if kind == "refuse" else results).append(rec)
        print(f"[{i:2d}/{len(rows)}] {rec['question'][:30]}")

n = len(results)
print(f"\n===== {Path(DATASET).stem} | {RETRIEVER} | K={K} | 有答案题{n}条 =====")
print(f"Hit@5   = {sum(r['hit'] for r in results) / n:.3f}")
print(f"Recall@5= {sum(r['recall5'] for r in results) / n:.3f}")
print(f"MRR     = {sum(r['mrr'] for r in results) / n:.3f}")

print("\n分类别:")
agg = defaultdict(list)
for r in results:
    agg[r["category"]].append(r)
for cat, rs in sorted(agg.items()):
    h = sum(x["hit"] for x in rs) / len(rs)
    m = sum(x["mrr"] for x in rs) / len(rs)
    print(f"  {cat}: Hit={h:.2f} MRR={m:.2f} ({len(rs)}条)")

if refuse_results and GEN:
    ok = sum(r["refused"] for r in refuse_results)
    print(f"\n拒答正确率 = {ok}/{len(refuse_results)}")
    for r in refuse_results:
        if not r["refused"]:
            print(f"  该拒未拒: {r['question']} -> {r['answer'][:50]}")

out = f"eval/results_{Path(DATASET).stem}_{COLLECTION}_{RETRIEVER}.jsonl"
with open(out, "w", encoding="utf-8") as f:
    for r in results + refuse_results:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")
print(f"\n明细已存 {out}")
