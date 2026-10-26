# Evaluation

## Dataset

`eval/dataset_80.jsonl` contains 80 manually reviewed questions:

| Category | Count |
|---|---:|
| Mechanics (技能机制) | 25 |
| Items (装备) | 20 |
| Slang (黑话) | 15 |
| Lore (背景/定位) | 12 |
| Refusal (知识库未收录) | 8 |

72 questions have answers; 8 are refusal cases. Slang questions use `eval/synonyms.json` to map player terms (e.g. 帽子 → 博学者之怒) to official names.

## Metrics

Retrieval is evaluated with Hit@5, Recall@5 and MRR. For a question with subject `S`, a retrieved chunk counts as a hit when its metadata subject matches `S` (or a known alias). Refusal questions are excluded from retrieval metrics and scored separately as refused / not refused.

Generation is evaluated with RAGAS (Faithfulness, Answer Relevancy, LLM Context Precision/Recall). The judge is an LLM; this introduces self-preference bias, so the numbers should be read as relative signals, not absolute quality.

## Main result

Semantic chunks, K=5, Qwen2.5-7B-Instruct:

| Retriever | Hit@5 | Recall@5 | MRR |
|---|---:|---:|---:|
| Vector | 0.861 | 0.475 | 0.847 |
| Hybrid (BM25 + Vector + RRF) | **0.986** | **0.567** | **0.910** |
| Hybrid + bge-reranker-v2-m3 | 0.917 | 0.486 | 0.894 |

The hybrid row is the latest retrieval-only run after case-insensitive slang expansion. Generation is excluded (`GEN=0`) so the number measures retrieval, not the LLM.

## Ablation

A 3×3 matrix compared fixed-length, heading and semantic chunks against vector, BM25 and hybrid retrieval. The selected production combination is **semantic chunks + hybrid retrieval** because it has the best Recall@5 and complete citation metadata. Fixed-length chunks can score higher on a loose "text contains subject" criterion but cannot provide reliable citations.

## Why reranking was rejected

Reranking was tested three times. It did not beat hybrid retrieval, and the black-slang Hit dropped from 1.00 to 0.87. The diagnosis: query expansion concatenated slang and official names into one string, which polluted the cross-encoder input. A future experiment should rerank with the original query and deduplicated candidates.

## Known validity issues

- Hit@5 uses subject-level matching; a chunk about the same hero but the wrong skill can still count as a hit.
- `relevant_doc_ids` in the dataset is a subject-level candidate list, not a strict per-question gold set.
- The RAGAS judge is the same 7B model family as the generator.
- The set is small (72 answerable questions); report confidence intervals when comparing models.
- Per-question outputs and bad-case notes are kept local and are not published.

## Reproduce

```bash
cp .env.example .env   # set EMBED_API_KEY
make chunks
make index
RETRIEVER=hybrid uv run python eval/run_eval.py
```

The script writes per-question JSONL results under `eval/` (gitignored). Aggregate numbers above can be regenerated from those files.
