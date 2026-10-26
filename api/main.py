from __future__ import annotations

from pathlib import Path

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from api.schemas.ask import AskRequest
from api.service import RagService, get_rag_service
from config import BASE_DIR
from memory.redis_store import ready as redis_ready

app = FastAPI(title="wzry-rag", version="0.2.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)
BASE_DIR = Path(BASE_DIR)
app.mount("/web", StaticFiles(directory=BASE_DIR / "web", html=True), name="web")


@app.get("/")
async def root():
    return RedirectResponse(url="/web/")


@app.post("/ask")
async def ask(req: AskRequest, service: RagService = Depends(get_rag_service)):
    return StreamingResponse(
        service.stream_answer(req),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/health")
async def health():
    return {"status": "ok", "version": app.version}


@app.get("/ready")
async def ready():
    checks = {"redis": redis_ready()}
    try:
        from retrieval.rag_pipeline import db

        checks["chroma"] = len(db.list_collections()) > 0
    except Exception:
        checks["chroma"] = False
    status = "ok" if all(checks.values()) else "degraded"
    return {"status": status, "checks": checks}
