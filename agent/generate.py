"""CLI compatibility wrapper around the shared RAG pipeline.

Run: uv run python -m agent.generate
"""
from __future__ import annotations

import uuid

from pipeline import get_pipeline


def answer(query: str, history=None, summary: str = "", **_):
    """Legacy signature kept for small scripts. Prefer get_pipeline().answer()."""
    result = get_pipeline().answer(query, session_id=f"legacy-{uuid.uuid4().hex[:8]}")
    return result.answer, [c.to_dict() for c in result.citations]


def main() -> None:
    sid = f"cli-{uuid.uuid4().hex[:8]}"
    pipeline = get_pipeline()
    print("王者知识库问答（输入 quit 退出）")
    while True:
        question = input("\n你：").strip()
        if question.lower() in {"quit", "exit"}:
            break
        result = pipeline.answer(question, session_id=sid)
        print(f"\n助手：{result.answer}")
        if result.citations:
            print("\n引用来源：")
            for citation in result.citations:
                print(f"- {citation.subject} {citation.source_url}")
        if result.trace:
            print(f"\n[trace] {result.trace}")


if __name__ == "__main__":
    main()
