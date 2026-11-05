"""Helpers for question-specific gold documents.

The old dataset attached every document of a hero to every question. These
helpers map a question to the document that actually answers it.
"""
from __future__ import annotations

import json
import random
import re
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DOCS_PATH = BASE_DIR / "data" / "processed" / "docs.jsonl"
SKILL_RE = re.compile(r"(被动|一技能|二技能|三技能|四技能|大招)")

DOCS = [json.loads(line) for line in DOCS_PATH.read_text(encoding="utf-8").splitlines()]
BY_ID = {d["doc_id"]: d for d in DOCS}
BY_SUBJECT: dict[str, list[dict]] = {}
for d in DOCS:
    BY_SUBJECT.setdefault(d["subject"], []).append(d)


def _one(cands: list[dict], description: str) -> dict:
    if len(cands) != 1:
        raise ValueError(f"expected exactly one {description}, got {len(cands)}")
    return cands[0]


def find_skill_doc(subject: str, label: str | None = None, question: str = "") -> str:
    label = label or (SKILL_RE.search(question).group(1) if SKILL_RE.search(question) else "")
    if not label:
        raise ValueError(f"cannot infer skill label from question: {question}")
    prefix = f"{subject}的{label}「"
    cands = [
        d
        for d in BY_SUBJECT.get(subject, [])
        if d.get("type") == "技能" and d.get("text", "").startswith(prefix)
    ]
    return _one(cands, f"skill doc for {subject}/{label}")["doc_id"]


def find_basic_doc(subject: str) -> str:
    cands = [
        d
        for d in BY_SUBJECT.get(subject, [])
        if d.get("type") == "英雄" and d.get("doc_id", "").endswith("_basic")
    ]
    return _one(cands, f"basic doc for {subject}")["doc_id"]


def find_item_doc(name: str) -> str:
    cands = [d for d in BY_SUBJECT.get(name, []) if d.get("type") == "装备"]
    return _one(cands, f"item doc for {name}")["doc_id"]


def hard_negatives(gold_doc_id: str, subject: str, category: str, limit: int = 3) -> list[str]:
    if category == "拒答":
        return []
    if category == "机制":
        return [
            d["doc_id"]
            for d in BY_SUBJECT.get(subject, [])
            if d.get("type") == "技能" and d["doc_id"] != gold_doc_id
        ][:limit]
    if category == "背景":
        basics = [
            d["doc_id"]
            for d in DOCS
            if d.get("type") == "英雄" and d.get("doc_id", "").endswith("_basic")
            and d["doc_id"] != gold_doc_id
        ]
    else:
        basics = [
            d["doc_id"]
            for d in DOCS
            if d.get("type") == "装备" and d["doc_id"] != gold_doc_id
        ]
    rng = random.Random(42)
    return rng.sample(basics, min(limit, len(basics)))


def build_entry(row: dict) -> dict:
    category = row["type"]
    subject = row["subject"]
    if category == "机制":
        gold = [find_skill_doc(subject, question=row["question"])]
        label = SKILL_RE.search(row["question"]).group(1)
    elif category == "背景":
        gold = [find_basic_doc(subject)]
        label = ""
    elif category in {"装备", "黑话"}:
        gold = [find_item_doc(subject)]
        label = ""
    elif category == "拒答":
        gold = []
        label = ""
    else:
        raise ValueError(f"unknown category: {category}")

    hard = hard_negatives(gold[0], subject, category) if gold else []
    ground_truth = BY_ID[gold[0]]["text"] if gold else row["ground_truth"]
    out = {
        "id": row["id"],
        "question": row["question"],
        "type": category,
        "subject": subject,
        "ground_truth": ground_truth,
        "gold_doc_ids": gold,
        "hard_negative_doc_ids": hard,
        "expect_refusal": category == "拒答",
        "version": "2016-snapshot",
    }
    if category == "机制":
        out["skill_label"] = label
    if category == "黑话":
        out["in_vocab_slang"] = True
    return out
