from config import Settings


def test_llm_falls_back_to_embed_credentials():
    settings = Settings(
        _env_file=None,
        embed_api_key="embed-key",
        embed_base_url="https://embed.example/v1",
        llm_api_key="",
        llm_base_url="",
    )
    assert settings.resolved_llm_api_key == "embed-key"
    assert settings.resolved_llm_base_url == "https://embed.example/v1"


def test_require_llm_key_raises_without_key():
    settings = Settings(_env_file=None, embed_api_key="", llm_api_key="")
    try:
        settings.require_llm_key()
    except RuntimeError as exc:
        assert "API key" in str(exc)
    else:
        raise AssertionError("expected RuntimeError")
