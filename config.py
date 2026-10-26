"""Central runtime configuration.

All secrets come from environment variables / .env.  Never commit .env.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # LLM / embeddings
    embed_api_key: str = ""
    embed_base_url: str = "https://api.siliconflow.cn/v1"
    embed_model: str = "BAAI/bge-m3"
    llm_api_key: str = ""
    llm_base_url: str = ""
    gen_model: str = "Qwen/Qwen2.5-7B-Instruct"

    # Storage
    redis_url: str = "redis://127.0.0.1:6379/0"
    chroma_path: str = str(BASE_DIR / "chroma_db")

    # Retrieval
    retriever: str = "hybrid"
    collection: str = "semantic"
    top_k: int = 5
    distance_threshold: float = 0.6
    index_version: str = "v1"
    prompt_version: str = "v2"

    # API / MCP
    mcp_transport: str = "sse"
    mcp_host: str = "0.0.0.0"
    mcp_port: int = 8001
    max_question_chars: int = 500

    @property
    def resolved_llm_api_key(self) -> str:
        return self.llm_api_key or self.embed_api_key

    @property
    def resolved_llm_base_url(self) -> str:
        return self.llm_base_url or self.embed_base_url

    def require_llm_key(self) -> str:
        if not self.resolved_llm_api_key:
            raise RuntimeError(
                "No API key configured. Copy .env.example to .env and set "
                "EMBED_API_KEY (or LLM_API_KEY)."
            )
        return self.resolved_llm_api_key

    @property
    def prompts_dir(self) -> Path:
        return BASE_DIR / "prompts"

    @property
    def data_dir(self) -> Path:
        return BASE_DIR / "data"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
