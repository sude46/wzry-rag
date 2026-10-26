"""Day11: answerer——按router的指令选择执行路径"""
import os
import sys
sys.path.insert(0, ".")
from agent.router import route
from retrieval.hybrid import retrieve_hybrid
from retrieval.rag_pipeline import generate

# 类型差异体现在prompt提示和K值; 检索统一hybrid(Day10矩阵结论)
TYPE_HINT = {
    "机制": "这是技能机制类问题, 回答时带上技能名、冷却、消耗和核心效果。",
    "装备": "这是装备类问题, 回答时带上总价、关键属性和被动/主动效果。",
    "背景": "这是背景定位类问题, 回答定位/称号即可, 不要展开技能。",
    "比较": "这涉及多个对象, 分别说明再对比。",
}

def answer(query):
    r = route(query)
    print(f"[router] 类型={r['type']} 多跳={r['multi_hop']}")
    if r["multi_hop"]:
        from agent.react import react_answer
        return react_answer(query), []
    ctxs = retrieve_hybrid(query, k=5)
    q2 = query + "（" + TYPE_HINT.get(r["type"], "") + "）"
    return generate(q2, ctxs), ctxs

if __name__ == "__main__":
    import sys
    ans, ctxs = answer(sys.argv[1])
    print("\n回答:", ans)
    print("引用:", [c["metadata"]["subject"] for c in ctxs])
