import pytest

import pipeline as pipeline_module
import retrieval.rerank as rerank_module
from config import RetrievalConfigError, Settings


def test_rerank_key_comes_from_settings(monkeypatch):
    monkeypatch.setattr(rerank_module, "settings", Settings(embed_api_key=""))
    with pytest.raises(RetrievalConfigError):
        rerank_module._require_key()


def test_rerank_url_uses_configured_base(monkeypatch):
    monkeypatch.setattr(
        rerank_module,
        "settings",
        Settings(embed_base_url="https://example.com/v1"),
    )
    assert rerank_module._rerank_url() == "https://example.com/v1/rerank"


def test_rerank_config_error_is_not_swallowed(monkeypatch):
    def boom(*args, **kwargs):
        raise RetrievalConfigError("missing rerank key")

    monkeypatch.setattr(rerank_module, "retrieve_rerank", boom)
    pipeline = pipeline_module.RagPipeline(settings=Settings(retriever="rerank"))
    with pytest.raises(RetrievalConfigError):
        pipeline.search("名刀多少钱")


def test_transient_rerank_failure_falls_back_with_trace(monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("rerank service down")

    def fake_vector(*args, **kwargs):
        return [
            {
                "text": "vector fallback",
                "metadata": {"doc_id": "v1", "subject": "测试"},
                "distance": 0.2,
            }
        ]

    monkeypatch.setattr(rerank_module, "retrieve_rerank", boom)
    monkeypatch.setattr(pipeline_module, "_vector_retrieve", fake_vector)
    pipeline = pipeline_module.RagPipeline(settings=Settings(retriever="rerank"))
    trace = {}
    chunks = pipeline.search("名刀多少钱", trace=trace)

    assert chunks[0].doc_id == "v1"
    assert trace["retrieval_mode"] == "vector_fallback"
    assert "retrieval_fallback" in trace
