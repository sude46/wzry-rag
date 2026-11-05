"""Build a question-level skeleton with doc-level gold ids.

The old version attached every document of a subject to every question. This
version maps each question to the document that actually answers it and adds
same-hero / same-category hard negatives.

Usage: uv run python eval/build_dataset.py
"""
from __future__ import annotations

import json
import random
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from eval.gold import (  # noqa: E402
    BY_ID,
    find_basic_doc,
    find_item_doc,
    find_skill_doc,
    hard_negatives,
)

BASE_DIR = Path(__file__).resolve().parent.parent
DOCS_PATH = BASE_DIR / "data" / "processed" / "docs.jsonl"
SYNONYMS_PATH = BASE_DIR / "eval" / "synonyms.json"
OUT = BASE_DIR / "eval" / "dataset_80.skeleton.jsonl"

random.seed(42)
docs = [json.loads(line) for line in DOCS_PATH.read_text(encoding="utf-8").splitlines()]
synonyms = json.loads(SYNONYMS_PATH.read_text(encoding="utf-8"))
print("字段名:", list(docs[0].keys()))
print("类型分布:", Counter(d["type"] for d in docs))

skills = [d for d in docs if d["type"] == "技能"]
items = [d for d in docs if d["type"] == "装备"]
heroes_docs = [d for d in docs if d["type"] == "英雄"]
all_heroes = {d["subject"] for d in heroes_docs}
skill_heroes = {d["subject"] for d in skills}
no_skill_heroes = sorted(all_heroes - skill_heroes)
print(f"有技能英雄: {len(skill_heroes)}, 无技能英雄(拒答素材): {len(no_skill_heroes)}")

SKILL_HEAD = re.compile(r"^(.*?)的(被动|一技能|二技能|三技能|四技能|大招)「(.*?)」")


def make_entry(
    idx: int,
    prefix: str,
    question: str,
    qtype: str,
    subject: str,
    ground_truth: str,
    gold_doc_ids: list[str],
    hard_negative_doc_ids: list[str],
    *,
    expect_refusal: bool = False,
    **extra,
) -> dict:
    return {
        "id": f"{prefix}_{idx:03d}",
        "question": question,
        "type": qtype,
        "subject": subject,
        "ground_truth": ground_truth,
        "gold_doc_ids": gold_doc_ids,
        "hard_negative_doc_ids": hard_negative_doc_ids,
        "expect_refusal": expect_refusal,
        "version": "2016-snapshot",
        **extra,
    }


entries: list[dict] = []

# ---- mechanics: 25 ----
random.shuffle(skills)
mech_templates = {
    "被动": ["{h}的被动是什么", "{h}的被动有什么用"],
    "大招": ["{h}的大招是什么", "{h}的大招效果是什么"],
    "default": ["{h}的{label}是什么", "{h}的{label}有什么用"],
}
n_mech = 0
for d in skills:
    if n_mech >= 25:
        break
    m = SKILL_HEAD.match(d["text"])
    if not m:
        continue
    hero, label, _ = m.groups()
    if "冷却值" in d["text"] and label != "被动" and random.random() < 0.3:
        q = f"{hero}的{label}冷却多久"
    else:
        q = random.choice(mech_templates.get(label, mech_templates["default"])).format(
            h=hero, label=label
        )
    gold = [find_skill_doc(hero, label)]
    entries.append(
        make_entry(
            n_mech,
            "mech",
            q,
            "机制",
            hero,
            BY_ID[gold[0]]["text"],
            gold,
            hard_negatives(gold[0], hero, "机制"),
        )
    )
    n_mech += 1

# ---- refusal: 5 ----
for i, hero in enumerate(no_skill_heroes[:5]):
    entries.append(
        make_entry(
            i,
            "refuse",
            f"{hero}的大招是什么",
            "拒答",
            hero,
            "知识库未收录该英雄的技能数据，正确行为是拒答并说明未收录。",
            [],
            [],
            expect_refusal=True,
        )
    )

# ---- items: 20 ----
item_subjects = sorted({d["subject"] for d in items})
random.shuffle(item_subjects)
item_templates = ["{n}多少钱", "{n}的属性是什么", "{n}适合什么英雄出", "{n}的被动是什么"]
for i, name in enumerate(item_subjects[:20]):
    q = random.choice(item_templates).format(n=name)
    gold = [find_item_doc(name)]
    entries.append(
        make_entry(
            i,
            "item",
            q,
            "装备",
            name,
            BY_ID[gold[0]]["text"],
            gold,
            hard_negatives(gold[0], name, "装备"),
        )
    )

# ---- lore: 15 ----
hero_subjects = sorted(all_heroes)
random.shuffle(hero_subjects)
lore_templates = ["{h}的背景故事是什么", "{h}是什么定位的英雄", "讲讲{h}这个角色"]
for i, hero in enumerate(hero_subjects[:15]):
    q = random.choice(lore_templates).format(h=hero)
    gold = [find_basic_doc(hero)]
    entries.append(
        make_entry(
            i,
            "lore",
            q,
            "背景",
            hero,
            BY_ID[gold[0]]["text"],
            gold,
            hard_negatives(gold[0], hero, "背景"),
        )
    )

# ---- slang: 15 (in-vocabulary only; see docs/evaluation.md) ----
slang_templates = ["{s}是什么", "{s}多少钱", "{s}有什么用"]
cnt = 0
for slang, official in synonyms.items():
    if cnt >= 15:
        break
    if official not in {d["subject"] for d in items}:
        continue
    q = random.choice(slang_templates).format(s=slang)
    gold = [find_item_doc(official)]
    entries.append(
        make_entry(
            cnt,
            "slang",
            q,
            "黑话",
            official,
            BY_ID[gold[0]]["text"],
            gold,
            hard_negatives(gold[0], official, "黑话"),
            in_vocab_slang=True,
        )
    )
    cnt += 1

OUT.write_text(
    "\n".join(json.dumps(e, ensure_ascii=False) for e in entries) + "\n",
    encoding="utf-8",
)
print(f"\n共生成 {len(entries)} 条 -> {OUT}")
print("类型分布:", Counter(e["type"] for e in entries))
print("gold 长度分布:", Counter(len(e["gold_doc_ids"]) for e in entries))
