#!/usr/bin/env bash
set -euo pipefail
# Production-ish local entrypoint: hybrid retrieval is the selected default.
export RETRIEVER="${RETRIEVER:-hybrid}"
exec uv run uvicorn api.main:app --host 0.0.0.0 --port "${PORT:-8000}"
