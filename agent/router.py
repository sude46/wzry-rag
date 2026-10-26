"""Day11: router——判断问题类型与是否需要多跳检索, 输出JSON指令"""
import json
import os
import sys
sys.path.insert(0, ".")
from openai import OpenAI

client = OpenAI(api_key=os.environ.get("EMBED_API_KEY", "") or "sk-placeholder",
                base_url=os.environ.get("EMBED_BASE_URL", "https://api.siliconflow.cn/v1"))
MODEL = os.environ.get("GEN_MODEL", "Qwen/Qwen2.5-7B-Instruct")

ROUTER_PROMPT = """你是王者荣耀问答系统的路由器。判断问题类型和是否需要多步检索。

类型(四选一):
- 机制: 英雄技能/被动/冷却/效果
- 装备: 装备价格/属性/被动/出装
- 背景: 英雄定位/称号/角色介绍
- 比较: 涉及两个以上对象对比, 或需要多次检索才能答全(如"连招""怎么克制")

multi_hop: 需要分步检索多个对象=true, 单一对象直接可查=false

只输出JSON, 不要任何其他文字: {{"type": "...", "multi_hop": true/false}}

问题: {q}"""

def route(query):
    r = client.chat.completions.create(model=MODEL, temperature=0,
        messages=[{"role": "user", "content": ROUTER_PROMPT.format(q=query)}])
    txt = r.choices[0].message.content.strip()
    try:
        return json.loads(txt[txt.index("{"):txt.rindex("}") + 1])
    except Exception:
        return {"type": "机制", "multi_hop": False}   # 解析失败的安全默认: 当单跳机制题处理

if __name__ == "__main__":
    import sys
    print(route(sys.argv[1]))
