import requests
import json
import time
from pathlib import Path
from bs4 import BeautifulSoup

BASE="https://pvp.qq.com/web201605"
HEADERS={"User-Agent":"Mozilla/5.0"}
RAW=Path("data/raw")
DETAILS=RAW/"details"
DETAILS.mkdir(parents=True,exist_ok=True)

def get_soup(url):
    """详情页是老站，GBK编码，不设会乱码"""
    r=requests.get(url,headers=HEADERS,timeout=15)
    r.encoding="gbk"
    return BeautifulSoup(r.text,"html.parser")

#下载装备/铭文字典（顺便存盘，后面直接当语料用）
items=requests.get(f"{BASE}/js/item.json",headers=HEADERS,timeout=15).json()
mings=requests.get(f"{BASE}/js/ming.json",headers=HEADERS,timeout=15).json()
json.dump(items,open(RAW/"item.json","w",encoding="utf-8"),ensure_ascii=False,indent=2)
item_map={str(i["item_id"]):i["item_name"] for i in items}
ming_map={m["ming_id"]:m["ming_name"] for m in mings}

heroes=json.load(open(RAW/"heroes.json",encoding="utf-8"))
for h in heroes:
    hero_id=h["ename"]
    out=DETAILS/f"{hero_id}.json"
    if out.exists():
        continue
    soup=get_soup(f"{BASE}/herodetail/{hero_id}.shtml")

    #技能：name/desc配对，跳过空对（页面末尾有个空占位）
    skills=[
            {"name":n.get_text(strip=True),"desc":d.get_text(strip=True)}
            for n,d in zip(soup.select(".skill-name"),soup.select(".skill-desc"))
            if n.get_text(strip=True) and d.get_text(strip=True)
            ]
    #出装：data-item属性里的ID串->映射成装备名
    equips=[
            [item_map.get(i,i) for i in (ul.get("data-item") or "").split("|") if i]
            for ul in soup.select(".equip-list")
            ]
    #铭文：data-ming同理
    sugg=soup.select_one(".sugg-u1")
    mingwen=[ming_map.get(i,i) for i in (sugg.get("data-ming") or "").split("|") if i] if sugg else[]
    data={
            "hero_id":hero_id,
            "cname":h["cname"],
            "title":h.get("title",""),
            "skills":skills,
            "equip_suggestions":equips,
            "mingwen":mingwen,
            "source_url":f"{BASE}/herodetail/{hero_id}.shtml",
            "crawled_at":time.strftime("%Y-%m-%d %H:%M:%S"),
            }
    json.dump(data,open(out,"w",encoding="utf-8"),ensure_ascii=False,indent=2)
    print(f"[{hero_id}]{h['cname']}--{len(skills)}个技能")
    time.sleep(0.5)
print(f"\n完成，共{len(list(DETAILS.glob('*.json')))}个英雄详情")

