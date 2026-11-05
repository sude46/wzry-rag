# Evaluation

## Dataset v2

`eval/dataset_80_v2.jsonl` contains 80 questions:

| Category | Count |
|---|---:|
| Mechanics (技能机制) | 25 |
| Items (装备) | 20 |
| Slang (黑话) | 15 |
| Lore (背景/定位) | 12 |
| Refusal (知识库未收录) | 8 |

72 questions are answerable; 8 expect refusal. Each answerable question has **one or more question-specific gold doc ids**, not the whole hero's document set:

```json
{
  "id": "mech_000",
  "question": "橘右京的被动是什么",
  "type": "机制",
  "subject": "橘右京",
  "gold_doc_ids": ["hero_163_skill_0"],
  "hard_negative_doc_ids": ["hero_163_skill_1", "hero_163_skill_2", "hero_163_skill_3"],
  "expect_refusal": false,
  "skill_label": "被动"
}
```

Gold construction:

- Mechanics: the skill document matching the requested label (`被动/一技能/二技能/三技能/四技能/大招`).
- Items / slang: the item document.
- Lore: the hero's `*_basic` document.
- Refusal: empty gold; scored separately.

`hard_negative_doc_ids` are same-hero other skills (mechanics), other heroes (lore), or other items (items/slang). They power the `wrong_negative` metric: a same-hero but wrong-skill result is counted when no gold doc is retrieved.

`eval/rebuild_gold.py` rebuilds v2 from the frozen questions. `eval/build_dataset.py` now generates question-specific gold ids and hard negatives instead of attaching `by_subject[subject][:10]`.

## Metrics

- **Doc Hit@k**: at least one gold doc id appears in the top k retrieved docs.
- **Doc Recall@k**: `|retrieved top-k ∩ gold| / |gold|`; for the usual one-gold case this equals Hit@k.
- **MRR**: reciprocal rank of the first gold doc.
- **wrong_negative**: no gold doc retrieved, but a hard-negative doc was; this is the "retrieved the hero but the wrong skill" signal.
- **Refusal**: evaluated separately as refused / not refused; refusal rows are excluded from retrieval means.

The old `Recall@5` implementation divided by `K` and counted same-subject chunks. That was **hit density**, not recall. It is removed from the headline.

## Results

Doc-level metrics, semantic chunks, K=5. Latest run: 2026-11-05, `make eval` (hybrid) and `RETRIEVER=vector|rerank`.

| Retriever | Hit@1 | Hit@3 | Hit@5 | Recall@5 | MRR | wrong_negative |
|---|---:|---:|---:|---:|---:|---:|
| Vector | 0.764 | 0.819 | 0.833 | 0.833 | 0.795 | 0.000 |
| **Hybrid (BM25 + Vector + RRF)** | **0.792** | **0.958** | **0.986** | **0.986** | **0.867** | **0.000** |
| Hybrid + bge-reranker-v2-m3 | 0.861 | 0.917 | 0.917 | 0.917 | 0.887 | 0.000 |

### What changed from the old subject-level result

| Metric | Old subject-level | Doc-level v2 |
|---|---:|---:|
| Hit@5 | 0.986 | 0.986 |
| Hit@1 | — | 0.792 |
| MRR | 0.910 | 0.867 |
| "Recall@5" | 0.567 (invalid) | 0.986 |

Hit@5 did **not** drop much because the correct skill was already in the top 5 for most questions. The leakage shows up in **Hit@1 and MRR**: the first result is often the hero's basic/equipment chunk, not the requested skill. This is a more useful finding than a fake Hit@5 drop.

### Interpretation

- Hybrid retrieval is still the best overall: Hit@5 0.986 vs 0.833 vector.
- Rerank has a higher Hit@1 (0.861 vs 0.792) but a lower Hit@5 (0.917 vs 0.986); it is not adopted for the production Top5. This is a real trade-off, not a blanket "rerank is bad".
- Wrong-negative is 0.000 at K=5 for all three; the remaining errors are misses, not same-hero wrong-skill answers.
- Fixed/heading chunks now carry `doc_ids` (fixed via source spans, heading via group membership), so retrieval results can be mapped back to documents. Citation quality still favors semantic chunks because each chunk has a single primary `doc_id`.

### Why rerank was not adopted

Three independent runs did not beat hybrid on the production Top5 metric. The identified cause was query-expansion text polluting the rerank candidate pool: the coarse stage used an expanded query while the cross-encoder saw the original query. A clean future experiment should retrieve from the original query or deduplicate the pool before reranking. The component remains behind `RETRIEVER=rerank`; this is a documented negative result, not a claim that reranking is universally useless.

## Historical 3×3 ablation

The original chunking/retriever matrix was measured with the older subject-level Hit@5, before the v2 doc-level gold. It is kept as historical evidence for the chunking decision, not as a doc-level benchmark:

| Chunking \ Retriever | Vector | BM25 | Hybrid |
|---|---:|---:|---:|
| Fixed length | 0.889* | 0.931* | 1.000* |
| Heading / paragraph | 0.903 | 0.764 | 0.986 |
| Semantic / per-doc | 0.875 | 0.708 | 0.972 |

\* Fixed-length chunks were judged by "text contains the target name" because they had no item metadata; that criterion is looser and not directly comparable. The production choice is semantic + hybrid because it has the best doc-level Recall@5 and citation-grade metadata; the fixed-length 1.000 is a known measurement artifact.

## Slang caveat

The 15 slang questions are **in-vocabulary**: they are generated from the same `eval/synonyms.json` used by query expansion. The 1.00 slang Hit@5 means "the dictionary expansion works", not "the system generalizes to unseen slang". A held-out slang set is future work; do not claim generalization from this number.

## Reproduce

```bash
cp .env.example .env   # set EMBED_API_KEY
make chunks
make index
make eval              # GEN=0, dataset_80_v2, hybrid
```

Per-question results go to `eval/results/` (gitignored) with a sidecar `.meta.json` containing `git_sha`, `index_version`, `prompt_version`, model, K and dataset hash. Only aggregate numbers belong in README/docs; raw results stay local.

## Known validity issues

- 72 answerable questions is small; report confidence intervals when comparing models.
- RAGAS uses an LLM judge; keep it as a relative signal, not an absolute score.
- Slang is in-vocabulary, not held out.
- The 2016 snapshot is not current-game data.
- Fixed/heading chunk mapping is approximate for chunks spanning multiple docs; semantic chunks remain the citation-grade strategy.
