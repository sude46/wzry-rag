import requests,json

url="https://pvp.qq.com/web201605/js/herolist.json"
r=requests.get(url,headers={"User-Agent":"Mozilla/5.0"})
heroes=r.json()
print(f"共{len(heroes)}个英雄")
print(json.dumps(heroes[0],ensure_ascii=False,indent=2))
with open("data/raw/heroes.json","w",encoding="utf-8") as f:
    json.dump(heroes,f,ensure_ascii=False,indent=2)



