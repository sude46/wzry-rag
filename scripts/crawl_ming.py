import requests, json
r = requests.get("https://pvp.qq.com/web201605/js/ming.json",
                 headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
mings = r.json()
json.dump(mings, open("data/raw/mings.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=2)
print(f"共 {len(mings)} 个铭文")
print(json.dumps(mings[0], ensure_ascii=False, indent=2))
