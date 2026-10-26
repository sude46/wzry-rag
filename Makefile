.PHONY: install chunks index dev api mcp test lint eval clean

install:
	uv sync --extra dev

chunks:
	uv run python ingest/chunkers.py

index:
	uv run python ingest/build_index.py

dev:
	RETRIEVER=hybrid uv run uvicorn api.main:app --reload --host 0.0.0.0 --port 8000

api:
	RETRIEVER=hybrid uv run uvicorn api.main:app --host 0.0.0.0 --port 8000

mcp:
	MCP_TRANSPORT=stdio uv run python -m mcp_server.server

test:
	uv run pytest

lint:
	uv run ruff check .

eval:
	RETRIEVER=hybrid uv run python eval/run_eval.py

clean:
	rm -rf .pytest_cache .ruff_cache __pycache__ */__pycache__ */*/__pycache__
