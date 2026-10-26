"""eval/build_dataset.py — Day9: 半自动生成 80 条评估集骨架"""
import json
import random
import re
from collections import Counter
from pathlib import Path

random.seed(42)

docs = [json.loads(l) for l in open("data/processed/docs.jsonl", encoding="utf-8")]
synonyms = json.load(open("eval/synonyms.json", encoding="utf-8"))

print("字段名:", list(docs[0].keys()))
print("类型分布:", Counter(d["type"] for d in docs))

# 自动探测 id 字段(可能叫 id / doc_id / chunk_id)
ID_KEY = next(k for k in ("id", "doc_id", "chunk_id", "uid") if k in docs[0])
print("id 字段:", ID_KEY)

skills = [d for d in docs if d["type"] == "技能"]
items = [d for d in docs if d["type"] == "装备"]
heroes_docs = [d for d in docs if d["type"] == "英雄"]

all_heroes = {d["subject"] for d in heroes_docs}
skill_heroes = {d["subject"] for d in skills}
no_skill_heroes = sorted(all_heroes - skill_heroes)
print(f"有技能英雄: {len(skill_heroes)}, 无技能英雄(拒答素材): {len(no_skill_heroes)}")

SKILL_HEAD = re.compile(r"^(.*?)的(被动|一技能|二技能|三技能|四技能|大招)「(.*?)」")

by_subject = {}
for d in docs:
    by_subject.setdefault(d["subject"], []).append(d)


def make_entry(idx, prefix, question, qtype, subject, ground_truth, version="S35"):
    rel = [d[ID_KEY] for d in by_subject.get(subject, [])][:10]
    return {"id": f"{prefix}_{idx:03d}", "question": question, "type": qtype,
            "ground_truth": ground_truth, "relevant_doc_ids": rel, "version": version}


entries = []

# ---- 机制类 25 条 ----
random.shuffle(skills)
mech_templates = {"被动": ["{h}的被动是什么", "{h}的被动有什么用"],
                  "大招": ["{h}的大招是什么", "{h}的大招效果是什么"],
                  "default": ["{h}的{label}是什么", "{h}的{label}有什么用"]}
n_mech = 0
for d in skills:
    if n_mech >= 25:
        break
    m = SKILL_HEAD.match(d["text"])
    if not m:
        continue
    hero, label, sname = m.groups()
    if "冷却值" in d["text"] and label != "被动" and random.random() < 0.3:
        q = f"{hero}的{label}冷却多久"
    else:
        q = random.choice(mech_templates.get(label, mech_templates["default"])).format(h=hero, label=label)
    entries.append(make_entry(n_mech, "mech", q, "机制", hero, d["text"]))
    n_mech += 1

# ---- 拒答类 5 条 ----
for i, hero in enumerate(no_skill_heroes[:5]):
    entries.append(make_entry(i, "refuse", f"{hero}的大招是什么", "拒答", hero,
                              "知识库未收录该英雄的技能数据，正确行为是拒答并说明未收录。"))

# ---- 装备类 20 条 ----
item_subjects = sorted({d["subject"] for d in items})
random.shuffle(item_subjects)
item_templates = ["{n}多少钱", "{n}的属性是什么", "{n}适合什么英雄出", "{n}的被动是什么"]
for i, name in enumerate(item_subjects[:20]):
    q = random.choice(item_templates).format(n=name)
    gt = " ".join(d["text"] for d in by_subject[name])[:300]
    entries.append(make_entry(i, "item", q, "装备", name, gt))

# ---- 背景/英雄类 15 条 ----
hero_subjects = sorted(all_heroes)
random.shuffle(hero_subjects)
lore_templates = ["{h}的背景故事是什么", "{h}是什么定位的英雄", "讲讲{h}这个角色"]
for i, hero in enumerate(hero_subjects[:15]):
    q = random.choice(lore_templates).format(h=hero)
    gt = " ".join(d["text"] for d in by_subject[hero])[:300]
    entries.append(make_entry(i, "lore", q, "背景", hero, gt))

# ---- 黑话类 15 条 ----
slang_templates = ["{s}是什么", "{s}多少钱", "{s}有什么用"]
cnt = 0
for slang, official in synonyms.items():
    if cnt >= 15:
        break
    if official not in by_subject:
        continue
    q = random.choice(slang_templates).format(s=slang)
    gt = " ".join(d["text"] for d in by_subject[official])[:300]
    entries.append(make_entry(cnt, "slang", q, "黑话", official, gt))
    cnt += 1

out = Path("eval/dataset_80.skeleton.jsonl")
with out.open("w", encoding="utf-8") as f:
    for e in entries:
        f.write(json.dumps(e, ensure_ascii=False) + "\n")

print(f"\n共生成 {len(entries)} 条 -> {out}")
print("类型分布:", Counter(e["type"] for e in entries))
