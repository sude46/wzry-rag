"""Single RAG orchestration pipeline.

API, CLI, MCP and evaluation should all go through this module so prompt,
retrieval, refusal and citation behaviour stay in sync.
"""
from __future__ import annotations

import json
import re
import time
import uuid
from pathlib import Path
from typing import Iterator

from openai import OpenAI

from config import BASE_DIR, Settings, get_settings
from contracts import AnswerResult, Citation, RetrievedChunk
from memory import redis_store
from retrieval.rag_pipeline import generate as _generate_once
from retrieval.rag_pipeline import retrieve as _vector_retrieve

REFUSAL = "知识库中没有找到相关内容"
REFUSAL_MARKERS = ("没有找到相关内容", "未收录", "没有收录", "无法回答", "资料中没有", "无法确定")
CITATION_RE = re.compile(r"\[(\d+)\]")


class RagPipeline:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self.client = OpenAI(
            api_key=self.settings.resolved_llm_api_key or "sk-placeholder",
            base_url=self.settings.resolved_llm_base_url,
            timeout=60,
            max_retries=2,
        )
        self.answer_prompt = (BASE_DIR / "prompts" / "answer_v2.txt").read_text(
            encoding="utf-8"
        )
        self.rewrite_prompt = (BASE_DIR / "prompts" / "rewrite_v2.txt").read_text(
            encoding="utf-8"
        )
        self.synonyms = self._load_synonyms()
        self.alias_groups = self._load_alias_groups()

    # ------------------------------------------------------------------ setup
    @staticmethod
    def _load_synonyms() -> dict[str, str]:
        path = BASE_DIR / "eval" / "synonyms.json"
        if not path.exists():
            return {}
        return json.loads(path.read_text(encoding="utf-8"))

    def _load_alias_groups(self) -> dict[str, set[str]]:
        groups: dict[str, set[str]] = {}
        for slang, official in self.synonyms.items():
            group = {slang, official}
            for name in group:
                groups.setdefault(name.casefold(), set()).update(group)

        docs_path = BASE_DIR / "data" / "processed" / "docs.jsonl"
        if docs_path.exists():
            with docs_path.open(encoding="utf-8") as f:
                for line in f:
                    try:
                        subject = json.loads(line).get("subject", "")
                    except json.JSONDecodeError:
                        continue
                    if subject:
                        groups.setdefault(subject.casefold(), set()).add(subject)
        return groups

    def _entities_in(self, query: str) -> list[set[str]]:
        folded = query.casefold()
        found: list[set[str]] = []
        for alias, group in self.alias_groups.items():
            if len(alias) >= 2 and alias in folded:
                if group not in found:
                    found.append(group)
        return found

    # -------------------------------------------------------------- rewriting
    def _clean_history(self, history: list[dict]) -> list[dict]:
        """Old citation ids must not leak into the current context."""
        cleaned: list[dict] = []
        for message in history:
            content = message.get("content", "")
            if message.get("role") == "assistant":
                content = CITATION_RE.sub("", content)
            cleaned.append({"role": message.get("role", "user"), "content": content})
        return cleaned

    def rewrite_query(self, question: str, history: list[dict], summary: str = "") -> str:
        if not history:
            return question
        history = self._clean_history(history)
        lines: list[str] = []
        if summary:
            lines.append(f"历史摘要：{summary}")
        lines.extend(f"{m['role']}: {m['content']}" for m in history[-6:])
        hist = "\n".join(lines)
        try:
            resp = self.client.chat.completions.create(
                model=self.settings.gen_model,
                temperature=0,
                messages=[
                    {
                        "role": "user",
                        "content": self.rewrite_prompt.format(
                            history=hist, question=question
                        ),
                    }
                ],
            )
            rewritten = (resp.choices[0].message.content or "").strip()
        except Exception:
            return question
        return self._valid_rewrite(question, rewritten)

    def _valid_rewrite(self, question: str, rewritten: str) -> str:
        """Entity-preserving guard: bad rewrites fall back to the original."""
        text = rewritten.strip().strip('"“”')
        if not text:
            return question
        if "\n" in text:
            text = text.splitlines()[0].strip()
        if len(text) > max(80, len(question) * 2 + 30):
            return question
        if "。" in text or any(
            marker in text
            for marker in ("根据资料", "资料显示", "正确回答", "答案是", "[1]", "回答：")
        ):
            return question
        for group in self._entities_in(question):
            if not any(alias.casefold() in text.casefold() for alias in group):
                return question
        return text or question

    # -------------------------------------------------------------- retrieval
    def search(
        self,
        query: str,
        k: int | None = None,
        type: str | None = None,
        version: str | None = None,
    ) -> list[RetrievedChunk]:
        k = k or self.settings.top_k
        mode = self.settings.retriever
        try:
            if mode == "hybrid":
                from retrieval.hybrid import retrieve_hybrid

                raw = retrieve_hybrid(
                    query, collection=self.settings.collection, k=max(k, 5), version=version
                )
            elif mode == "rerank":
                from retrieval.rerank import retrieve_rerank

                raw = retrieve_rerank(
                    query, collection=self.settings.collection, k=max(k, 5)
                )
            else:
                raw = _vector_retrieve(
                    query,
                    collection=self.settings.collection,
                    k=max(k, 5),
                    version=version,
                )
        except Exception:
            raw = _vector_retrieve(
                query, collection=self.settings.collection, k=max(k, 5), version=version
            )

        chunks = [RetrievedChunk.from_raw(item) for item in raw]
        if type:
            chunks = [c for c in chunks if c.type == type]
        if version:
            chunks = [c for c in chunks if c.version == version]
        return chunks[:k]

    # --------------------------------------------------------------- context
    def build_context(
        self, chunks: list[RetrievedChunk], max_chars: int = 7000
    ) -> tuple[list[RetrievedChunk], str]:
        used: list[RetrievedChunk] = []
        blocks: list[str] = []
        seen: set[str] = set()
        total = 0
        for chunk in chunks:
            key = chunk.doc_id or chunk.text[:80]
            if key in seen:
                continue
            seen.add(key)
            text = chunk.text.strip()
            if len(text) > 1400:
                text = text[:1400] + "…"
            block = (
                f'<doc id="{len(used) + 1}" subject="{chunk.subject}" type="{chunk.type}">\n'
                f"{text}\n</doc>"
            )
            if total + len(block) > max_chars:
                break
            used.append(chunk)
            blocks.append(block)
            total += len(block)
        return used, "\n".join(blocks)

    def _gate(self, chunks: list[RetrievedChunk]) -> bool:
        """Refuse only when every vector-scored chunk is beyond the threshold."""
        distances = [c.vector_distance for c in chunks if c.vector_distance is not None]
        if not distances:
            return False
        return min(distances) > self.settings.distance_threshold

    def slang_hints(self, text: str) -> list[str]:
        folded = text.casefold()
        hints: list[str] = []
        for slang, official in self.synonyms.items():
            if slang.casefold() in folded and official.casefold() not in folded:
                hint = f"{slang}指{official}"
                if hint not in hints:
                    hints.append(hint)
        return hints

    def _messages(
        self, question: str, context: str, history: list[dict], summary: str
    ) -> list[dict]:
        prompt = self.answer_prompt.format(context=context)
        prefix = f"历史摘要：{summary}\n\n" if summary else ""
        messages = self._clean_history(history)
        hints = self.slang_hints(question)
        hint_txt = f"术语提示：{'；'.join(hints)}\n" if hints else ""
        messages.append(
            {"role": "user", "content": f"{prefix}{hint_txt}{prompt}\n\n问题：{question}"}
        )
        return messages

    # -------------------------------------------------------------- citations
    def sanitize_citations(
        self, answer: str, chunks: list[RetrievedChunk]
    ) -> tuple[str, list[Citation]]:
        valid_ids: set[int] = set()

        def repl(match: re.Match) -> str:
            idx = int(match.group(1))
            if 1 <= idx <= len(chunks):
                valid_ids.add(idx)
                return f"[{idx}]"
            return ""

        cleaned = CITATION_RE.sub(repl, answer)
        citations = [
            Citation(
                doc_id=chunks[i - 1].doc_id,
                subject=chunks[i - 1].subject,
                type=chunks[i - 1].type,
                source_url=chunks[i - 1].source_url,
                used=True,
            )
            for i in sorted(valid_ids)
        ]
        return cleaned, citations

    def _cached_result(self, payload: dict, request_id: str, trace: dict) -> AnswerResult:
        citations = [Citation(**c) for c in payload.get("citations", []) if isinstance(c, dict)]
        return AnswerResult(
            answer=payload.get("answer", ""),
            citations=citations,
            refused=bool(payload.get("refused", False)),
            cached=True,
            request_id=request_id,
            trace=trace,
        )

    @staticmethod
    def _is_refusal(answer: str) -> bool:
        return any(marker in answer for marker in REFUSAL_MARKERS)

    # ---------------------------------------------------------------- answer
    def answer(
        self,
        question: str,
        session_id: str,
        version: str | None = None,
        request_id: str | None = None,
    ) -> AnswerResult:
        request_id = request_id or uuid.uuid4().hex
        t0 = time.perf_counter()
        summary, history = redis_store.context_for_prompt(session_id)

        t1 = time.perf_counter()
        standalone = self.rewrite_query(question, history, summary)
        rewrite_ms = (time.perf_counter() - t1) * 1000

        key = redis_store.cache_key(standalone, version)
        cached = redis_store.cache_get(key)
        if cached:
            trace = {
                "standalone": standalone,
                "rewrite_ms": round(rewrite_ms, 1),
                "total_ms": round((time.perf_counter() - t0) * 1000, 1),
            }
            result = self._cached_result(cached, request_id, trace)
            redis_store.append_turn(session_id, question, result.answer)
            return result

        t2 = time.perf_counter()
        chunks = self.search(standalone, version=version)
        retrieve_ms = (time.perf_counter() - t2) * 1000

        if not chunks or self._gate(chunks):
            result = AnswerResult(
                answer=REFUSAL,
                refused=True,
                request_id=request_id,
                trace={
                    "standalone": standalone,
                    "rewrite_ms": round(rewrite_ms, 1),
                    "retrieve_ms": round(retrieve_ms, 1),
                    "total_ms": round((time.perf_counter() - t0) * 1000, 1),
                },
            )
            redis_store.append_turn(session_id, question, result.answer)
            return result

        used, context = self.build_context(chunks)
        messages = self._messages(question, context, history, summary)

        t3 = time.perf_counter()
        resp = self.client.chat.completions.create(
            model=self.settings.gen_model,
            messages=messages,
            temperature=0,
            timeout=60,
        )
        answer = resp.choices[0].message.content or ""
        generate_ms = (time.perf_counter() - t3) * 1000

        cleaned, citations = self.sanitize_citations(answer, used)
        refused = self._is_refusal(cleaned)
        if not refused:
            redis_store.cache_set(
                key,
                {
                    "answer": cleaned,
                    "citations": [c.to_dict() for c in citations],
                    "refused": False,
                },
            )
        redis_store.append_turn(session_id, question, cleaned)

        return AnswerResult(
            answer=cleaned,
            citations=citations,
            refused=refused,
            cached=False,
            request_id=request_id,
            trace={
                "standalone": standalone,
                "rewrite_ms": round(rewrite_ms, 1),
                "retrieve_ms": round(retrieve_ms, 1),
                "generate_ms": round(generate_ms, 1),
                "total_ms": round((time.perf_counter() - t0) * 1000, 1),
                "chunks": [c.doc_id for c in used],
                "prompt_version": self.settings.prompt_version,
                "index_version": self.settings.index_version,
            },
        )

    # ---------------------------------------------------------------- stream
    def stream_answer(
        self,
        question: str,
        session_id: str,
        version: str | None = None,
        request_id: str | None = None,
    ) -> Iterator[tuple[str, dict]]:
        request_id = request_id or uuid.uuid4().hex
        t0 = time.perf_counter()
        try:
            summary, history = redis_store.context_for_prompt(session_id)
            t1 = time.perf_counter()
            standalone = self.rewrite_query(question, history, summary)
            rewrite_ms = (time.perf_counter() - t1) * 1000
            key = redis_store.cache_key(standalone, version)
            cached = redis_store.cache_get(key)

            if cached:
                answer = cached.get("answer", "")
                for i in range(0, len(answer), 8):
                    yield "token", {"text": answer[i : i + 8]}
                for citation in cached.get("citations", []):
                    yield "citation", citation
                redis_store.append_turn(session_id, question, answer)
                yield "done", {
                    "answer_id": request_id,
                    "cached": True,
                    "refused": bool(cached.get("refused", False)),
                    "citations": cached.get("citations", []),
                    "trace": {
                        "standalone": standalone,
                        "rewrite_ms": round(rewrite_ms, 1),
                        "total_ms": round((time.perf_counter() - t0) * 1000, 1),
                    },
                }
                return

            t2 = time.perf_counter()
            chunks = self.search(standalone, version=version)
            retrieve_ms = (time.perf_counter() - t2) * 1000
            if not chunks or self._gate(chunks):
                yield "token", {"text": REFUSAL}
                redis_store.append_turn(session_id, question, REFUSAL)
                yield "done", {
                    "answer_id": request_id,
                    "cached": False,
                    "refused": True,
                    "citations": [],
                    "trace": {
                        "standalone": standalone,
                        "retrieve_ms": round(retrieve_ms, 1),
                        "total_ms": round((time.perf_counter() - t0) * 1000, 1),
                    },
                }
                return

            used, context = self.build_context(chunks)
            messages = self._messages(question, context, history, summary)

            t3 = time.perf_counter()
            stream = self.client.chat.completions.create(
                model=self.settings.gen_model,
                messages=messages,
                temperature=0,
                stream=True,
                timeout=60,
            )
            parts: list[str] = []
            for chunk in stream:
                delta = chunk.choices[0].delta.content or ""
                if delta:
                    parts.append(delta)
                    yield "token", {"text": delta}
            answer = "".join(parts)
            generate_ms = (time.perf_counter() - t3) * 1000

            cleaned, citations = self.sanitize_citations(answer, used)
            refused = self._is_refusal(cleaned)
            if not refused:
                redis_store.cache_set(
                    key,
                    {
                        "answer": cleaned,
                        "citations": [c.to_dict() for c in citations],
                        "refused": False,
                    },
                )
            for citation in citations:
                yield "citation", citation.to_dict()
            redis_store.append_turn(session_id, question, cleaned)
            yield "done", {
                "answer_id": request_id,
                "cached": False,
                "refused": refused,
                "citations": [c.to_dict() for c in citations],
                "trace": {
                    "standalone": standalone,
                    "rewrite_ms": round(rewrite_ms, 1),
                    "retrieve_ms": round(retrieve_ms, 1),
                    "generate_ms": round(generate_ms, 1),
                    "total_ms": round((time.perf_counter() - t0) * 1000, 1),
                    "chunks": [c.doc_id for c in used],
                    "prompt_version": self.settings.prompt_version,
                    "index_version": self.settings.index_version,
                },
            }
        except Exception as exc:  # keep the SSE stream alive with a typed error event
            yield "error", {"message": "服务暂时不可用，请稍后重试", "detail": str(exc)}


_pipeline: RagPipeline | None = None


def get_pipeline() -> RagPipeline:
    global _pipeline
    if _pipeline is None:
        _pipeline = RagPipeline()
    return _pipeline
