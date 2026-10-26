"""Redis session memory + answer cache.

Layering strategy: older turns are compressed into a short summary; the last
KEEP turns stay verbatim. All keys have a TTL. Cache keys are versioned so a
prompt/index/model change cannot silently serve stale answers.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import redis
from openai import OpenAI

from config import get_settings

settings = get_settings()
r = redis.from_url(
    settings.redis_url,
    decode_responses=True,
    socket_connect_timeout=2,
    socket_timeout=2,
)

TTL = 3600
KEEP = 3
COMPRESS_AT = 10
BASE_DIR = Path(__file__).resolve().parent.parent
SUMMARY_PROMPT = (BASE_DIR / "prompts" / "summary_v1.txt").read_text(encoding="utf-8")


def _client() -> OpenAI:
    return OpenAI(
        api_key=settings.resolved_llm_api_key or "sk-placeholder",
        base_url=settings.resolved_llm_base_url,
        timeout=60,
        max_retries=2,
    )


def ready() -> bool:
    try:
        return bool(r.ping())
    except redis.RedisError:
        return False


def get_history(sid: str) -> list[dict]:
    try:
        return [json.loads(x) for x in r.lrange(f"sess:{sid}:hist", 0, -1)]
    except redis.RedisError:
        return []


def append_turn(sid: str, q: str, a: str) -> None:
    key = f"sess:{sid}:hist"
    try:
        r.rpush(key, json.dumps({"role": "user", "content": q}, ensure_ascii=False))
        r.rpush(key, json.dumps({"role": "assistant", "content": a}, ensure_ascii=False))
        r.expire(key, TTL)
        if r.llen(key) > COMPRESS_AT * 2:
            compress(sid)
    except redis.RedisError:
        return


def compress(sid: str) -> None:
    """Compress turns older than the last KEEP turns into a summary."""
    key = f"sess:{sid}:hist"
    try:
        msgs = [json.loads(x) for x in r.lrange(key, 0, -1)]
        old, recent = msgs[: -KEEP * 2], msgs[-KEEP * 2 :]
        if not old:
            return
        prev = r.get(f"sess:{sid}:summary") or ""
        conversation = (prev + "\n" + "\n".join(f"{m['role']}: {m['content']}" for m in old)).strip()
        try:
            resp = _client().chat.completions.create(
                model=settings.gen_model,
                temperature=0,
                messages=[
                    {
                        "role": "user",
                        "content": SUMMARY_PROMPT.format(conversation=conversation),
                    }
                ],
            )
            summary = (resp.choices[0].message.content or "").strip()
        except Exception:
            return
        r.set(f"sess:{sid}:summary", summary, ex=TTL)
        r.delete(key)
        for m in recent:
            r.rpush(key, json.dumps(m, ensure_ascii=False))
        r.expire(key, TTL)
    except redis.RedisError:
        return


def context_for_prompt(sid: str) -> tuple[str, list[dict]]:
    try:
        summary = r.get(f"sess:{sid}:summary") or ""
        # Sliding TTL: reading a session keeps it alive.
        r.expire(f"sess:{sid}:hist", TTL)
        if summary:
            r.expire(f"sess:{sid}:summary", TTL)
    except redis.RedisError:
        summary = ""
    return summary, get_history(sid)


def cache_key(query: str, version: str | None = None) -> str:
    payload = {
        "query": query,
        "index_version": settings.index_version,
        "prompt_version": settings.prompt_version,
        "model": settings.gen_model,
        "k": settings.top_k,
        "version": version or "",
    }
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()
    return f"cache:ans:v2:{digest}"


def cache_get(key: str) -> dict | None:
    try:
        raw = r.get(key)
    except redis.RedisError:
        return None
    if not raw:
        return None
    try:
        value = json.loads(raw)
        return value if isinstance(value, dict) else None
    except json.JSONDecodeError:
        return None


def cache_set(key: str, payload: dict, ttl: int = TTL) -> None:
    try:
        r.set(key, json.dumps(payload, ensure_ascii=False), ex=ttl)
    except redis.RedisError:
        return


# ---- Backward-compatible helpers (used by older CLI scripts) ----
def ans_get(q: str) -> str | None:
    try:
        return r.get("cache:ans:" + hashlib.md5(q.encode()).hexdigest())
    except redis.RedisError:
        return None


def ans_set(q: str, a: str) -> None:
    try:
        r.set("cache:ans:" + hashlib.md5(q.encode()).hexdigest(), a, ex=TTL)
    except redis.RedisError:
        return
