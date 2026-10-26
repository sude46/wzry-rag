"""HTTP service: thin adapter over the shared RAG pipeline."""
from __future__ import annotations

import uuid

from api.schemas.ask import AskRequest
from api.sse import event
from pipeline import get_pipeline


class RagService:
    def stream_answer(self, req: AskRequest):
        request_id = uuid.uuid4().hex
        pipeline = get_pipeline()
        for name, data in pipeline.stream_answer(
            question=req.question,
            session_id=req.session_id,
            version=req.version,
            request_id=request_id,
        ):
            yield event(name, data)


_service = RagService()


def get_rag_service() -> RagService:
    return _service
