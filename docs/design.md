# Design notes

## 1. One pipeline, four entrypoints

The project exposes the same logic through four surfaces: FastAPI/SSE, CLI, MCP and evaluation. They all call `pipeline.RagPipeline`. This was a deliberate cleanup: earlier versions had separate orchestration in `api/service.py`, `agent/generate.py`, `eval/run_eval.py` and `mcp_server/tools.py`, which made the evaluation prompt drift from production.

## 2. Data contract

`contracts.py` defines `RetrievedChunk`, `Citation` and `AnswerResult`. Retrieval backends return dictionaries, but they are normalised at the pipeline boundary. This removed a class of bugs where vector results had `distance`, BM25 results had `rank`, and hybrid results had `rrf`, but citation code expected a fourth shape.

## 3. Retrieval

- **Semantic chunks**: one knowledge item per chunk. Best Recall@5 and the metadata needed for citations.
- **BM25**: exact hero/item names and player slang. `jieba` tokenisation; no custom dictionary because the ablation showed a net regression.
- **RRF**: fuse by rank with `k=60`. No score normalisation needed.
- **Distance retained**: hybrid results keep the vector distance so the refusal gate still has a signal.
- **Rerank**: available behind `RETRIEVER=rerank`, off by default. The negative result is documented.

## 4. Query rewriting

Multi-turn questions like "那她的大招呢" are rewritten into standalone queries before retrieval. Two safeguards matter more than the prompt:

1. The rewrite prompt contains only rewrite examples; it never contains an answer example.
2. After rewriting, every entity from the original question must still appear (directly or via an alias group). Otherwise, fall back to the original question.

This addressed two observed failures: the rewriter answering the question, and the rewriter replacing the user's new topic with the previous one.

## 5. Context and citations

- Deduplicate by `doc_id`.
- Add a per-document header with subject/type.
- Enforce a character budget; truncate long documents.
- Parse `[n]` citations and drop out-of-range ids.
- Return used citations, not every retrieved chunk.
- Strip old citation ids from history before putting it back into the prompt (planned/partially implemented: history is passed as messages, so assistant answers should be treated as non-authoritative).

## 6. Session memory and cache

Redis stores the last `KEEP=3` turns verbatim and compresses older turns into a short summary. Cache keys include query, index version, prompt version, model and K. Cached payloads include the answer and citations. Refusals are not cached.

## 7. MCP

The MCP server exposes `search_knowledge`, `get_hero` and `get_item`. Each hit is a typed object with provenance. Local use is stdio; remote use is SSE. The server should not import the old `agent.generate` module, because that would pull in Redis/LLM side effects just to search.

## 8. Known trade-offs

- Single-process monolith; no queue or distributed index. Appropriate for a portfolio project and a small knowledge base.
- 7B generation model: cheap, but occasional over-refusal and weak false-premise handling.
- 2016 data snapshot: reproducible, but incomplete for current-game questions.
- Subject-level Hit@5: useful for iteration, not a strict document-level benchmark.
