# Contributing

```bash
cp .env.example .env
uv sync --extra dev
make chunks
make index
make test
make lint
```

Guidelines:

- Never commit `.env`, API keys, `chroma_db/`, `data/raw/`, `local-reports/` or per-question evaluation outputs.
- Keep the RAG orchestration in `pipeline.py`; API, CLI, MCP and evaluation should not reimplement retrieval/generation logic.
- Prompt changes should include a `PROMPT_VERSION` bump and an evaluation note.
- Add a unit test for pure logic (RRF, query expansion, citation parsing, cache key).
- Keep the 2016 snapshot label unless the data is actually refreshed.

Good first issues: document-level evaluation metrics, rerank-with-original-query experiment, MCP resource templates.
