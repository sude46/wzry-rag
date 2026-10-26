from mcp_server.tools import SearchHit


def test_search_hit_schema_has_provenance_fields():
    hit = SearchHit(
        doc_id="hero_105_skill_0",
        subject="廉颇",
        type="技能",
        text="廉颇的被动…",
        source_url="https://example.com",
        score=0.9,
    ).model_dump()
    assert hit["subject"] == "廉颇"
    assert hit["source_url"] == "https://example.com"
    assert set(hit) >= {"doc_id", "subject", "type", "text", "source_url", "score"}
