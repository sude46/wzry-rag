"""Day 8: 重排 —— 粗排 Top20 -> 重排 -> Top5
两种后端: RERANK_BACKEND=llm(通用LLM逐条判分) / bge(专用重排模型, 默认)
用法: uv run python retrieval/rerank.py "名刀被动是什么"
"""
import os
import sys
import time
sys.path.insert(0, ".")

import requests

from retrieval.hybrid import retrieve_hybrid
from retrieval.rag_pipeline import client, GEN_MODEL

BACKEND = os.environ.get("RERANK_BACKEND", "bge")

RERANK_PROMPT = """判断下面的资料是否能直接帮助回答问题。
只回答一个数字: 2=直接相关(包含答案), 1=部分相关(同主题但不直接回答), 0=无关。
不要输出任何其他内容。

问题: {query}
资料: {text}
评分:"""

def llm_score(query, text):
    r = client.chat.completions.create(
        model=GEN_MODEL,
        messages=[{"role": "user", "content": RERANK_PROMPT.format(query=query, text=text[:300])}],
        temperature=0, max_tokens=4,
    )
    s = r.choices[0].message.content.strip()
    return int(s) if s and s[0] in "012" else 0

def bge_rerank(query, pool, k):
    """专用重排模型: 一次调用给全部候选打分, 返回 relevance_score"""
    r = requests.post(
        "https://api.siliconflow.cn/v1/rerank",
        headers={"Authorization": f"Bearer {os.environ['EMBED_API_KEY']}"},
        json={"model": "BAAI/bge-reranker-v2-m3", "query": query,
              "documents": [c["text"] for c in pool], "top_n": k},
        timeout=30,
    )
    results = r.json()["results"]   # [{"index": 原序号, "relevance_score": 分数}]
    return [pool[item["index"]] | {"rerank_score": round(item["relevance_score"], 3)}
            for item in results]

def retrieve_rerank(query, collection="semantic", k=5):
    t0 = time.time()
    pool = retrieve_hybrid(query, collection=collection, k=20)
    t_coarse = time.time() - t0

    t0 = time.time()
    if BACKEND == "bge":
        top = bge_rerank(query, pool, k)
    else:
        for c in pool:
            c["rerank_score"] = llm_score(query, c["text"])
        pool.sort(key=lambda c: c["rerank_score"], reverse=True)
        top = pool[:k]
    t_rerank = time.time() - t0

    print(f"[耗时] 粗排={t_coarse:.2f}s 重排={t_rerank:.2f}s (后端={BACKEND})")
    return top

if __name__ == "__main__":
    q = sys.argv[1] if len(sys.argv) > 1 else "名刀被动是什么"
    for i, c in enumerate(retrieve_rerank(q)):
        m = c["metadata"]
        print(f"[{i+1}] 相关性={c['rerank_score']} | {m.get('subject','')}({m.get('type','')}) | {c['text'][:60]}")
