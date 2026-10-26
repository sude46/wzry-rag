from contracts import RetrievedChunk
from pipeline import RagPipeline


def test_bad_rewrite_falls_back_to_original():
    pipeline = RagPipeline()
    original = "吸血刀的作用是什么"
    bad = "冷静之靴的作用是什么"
    assert pipeline._valid_rewrite(original, bad) == original


def test_answer_like_rewrite_is_rejected():
    pipeline = RagPipeline()
    original = "cd鞋是啥"
    answer_like = "根据资料，冷静之靴可以提供冷却缩减。那么cd鞋是啥"
    assert pipeline._valid_rewrite(original, answer_like) == original


def test_sanitize_citations_drops_out_of_range_ids():
    pipeline = RagPipeline()
    chunks = [
        RetrievedChunk(doc_id="d1", subject="妲己", source_url="u1"),
        RetrievedChunk(doc_id="d2", subject="妲己", source_url="u2"),
    ]
    answer, citations = pipeline.sanitize_citations("结论[1]，细节[9]。", chunks)
    assert "[9]" not in answer
    assert [c.doc_id for c in citations] == ["d1"]


def test_slang_hint_maps_player_term_to_official_name():
    pipeline = RagPipeline()
    assert pipeline.slang_hints("金身是什么") == ["金身指辉月"]


def test_gate_refuses_when_all_distances_are_large():
    pipeline = RagPipeline()
    chunks = [RetrievedChunk(vector_distance=0.9), RetrievedChunk(vector_distance=0.8)]
    assert pipeline._gate(chunks) is True
