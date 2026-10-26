import json
import re
from pathlib import Path

RAW=Path("data/raw")
OUT=Path("data/processed")
OUT.mkdir(parents=True,exist_ok=True)
heroes=json.load(open(RAW/"heroes.json",encoding="utf-8"))
hero_base={str(h["ename"]):h for h in heroes}

PAT = re.compile(r"^(.*?)冷却值[:：]([^:：]*?)消耗[:：](.*)$")
TAG=re.compile(r"<[^>]+>")

docs=[]

def add(doc_id,subject,type_,text,source_url,**extra):
    docs.append({
        "doc_id":doc_id,"subject":subject,"type":type_,
        "text":text,"source_url":source_url,**extra,
        })
def strip_html(s):
    return TAG.sub("",s or "").strip()
#-------英雄/技能/推荐出装/推荐铭文--------------
n_missing=0
for f in sorted(RAW.glob("details/*.json"),key=lambda p: int(p.stem)):
    d=json.load(open(f,encoding="utf-8"))
    hid=str(d["hero_id"])
    base=hero_base.get(hid,{})
    cname=d["cname"]
    url=d["source_url"]

    if not d["skills"]:
        n_missing+=1
        add(f"hero_{hid}_basic",cname,"英雄",
            f"{cname}({d['title']}),知识库暂未收录该英雄的技能与出装详情",
            url,detail_available=False)
        continue
    role={1:"战士",2:"法师",3:"坦克",4:"刺客",5:"射手",6:"辅助"}.get(base.get("hero_type"),"未知")
    add(f"hero_{hid}_basic",cname,"英雄",f"{cname}({d['title']}),定位:{role}",
        url,detail_available=True)

    def skill_labels(n):
        if n <= 2:
            return ["被动", "大招"][:n]
        middle = ["一技能", "二技能", "三技能", "四技能"][:n - 2]
        return ["被动"] + middle + ["大招"]

    labels = skill_labels(len(d["skills"]))
    for i, s in enumerate(d["skills"]):
        label = labels[i]
        m = PAT.match(s["name"])
        if m:
            sname, cd, cost = m.group(1), m.group(2), m.group(3)
            text = f"{cname}的{label}「{sname}」，冷却值：{cd}，消耗：{cost}。{s['desc']}"
        else:
            sname = s["name"]
            text = f"{cname}的{label}「{sname}」。{s['desc']}"
        add(f"hero_{hid}_skill_{i}", cname, "技能", text, url)

    for j, equip in enumerate(d["equip_suggestions"]):
        add(f"hero_{hid}_equip_{j}", cname, "英雄",
            f"{cname}的官方推荐出装（第{j+1}套）：{'、'.join(equip)}。", url)
    if d["mingwen"]:
        add(f"hero_{hid}_mingwen", cname, "英雄",
            f"{cname}的官方推荐铭文：{'、'.join(d['mingwen'])}。", url)


# ---------- 装备 ----------
ITEM_TYPE = {1: "攻击", 2: "法术", 3: "防御", 4: "移动", 5: "打野", 6: "辅助"}
items = json.load(open(RAW / "item.json", encoding="utf-8"))
for it in items:
    attrs = [strip_html(it.get("des1")), strip_html(it.get("des2"))]
    attrs = [a for a in attrs if a]
    text = (f"{it['item_name']}，{ITEM_TYPE.get(it['item_type'], '其他')}类装备，"
            f"总价{it.get('total_price', '?')}金币。" + "；".join(attrs))
    add(f"equip_{it['item_id']}", it["item_name"], "装备",
        text, "https://pvp.qq.com/web201605/item.shtml")

# ---------- 铭文 ----------
COLOR = {"red": "红色", "blue": "蓝色", "green": "绿色"}
mings = json.load(open(RAW / "mings.json", encoding="utf-8"))
for m in mings:
    des = strip_html(m["ming_des"])
    add(f"ming_{m['ming_id']}", m["ming_name"], "铭文",
        f"{m['ming_name']}，{COLOR.get(m['ming_type'], m['ming_type'])}铭文，"
        f"{m['ming_grade']}级。效果：{des}",
        "https://pvp.qq.com/web201605/ming.shtml")

with open(OUT / "docs.jsonl", "w", encoding="utf-8") as fp:
    for doc in docs:
        fp.write(json.dumps(doc, ensure_ascii=False) + "\n")

print(f"共 {len(docs)} 条知识，{n_missing} 个英雄详情缺失")
