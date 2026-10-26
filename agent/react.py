"""Day11: 显式ReAct——Thought/Action/Observation三段循环, 最多3轮, 60秒熔断"""
import os
import sys
sys.path.insert(0, ".")
import time
from openai import OpenAI
from retrieval.hybrid import retrieve_hybrid

client = OpenAI(api_key=os.environ.get("EMBED_API_KEY", "") or "sk-placeholder",
                base_url=os.environ.get("EMBED_BASE_URL", "https://api.siliconflow.cn/v1"))
MODEL = os.environ.get("GEN_MODEL", "Qwen/Qwen2.5-7B-Instruct")

REACT_PROMPT = """你在用多步推理回答王者荣耀的问题。每一步严格按以下格式输出两行:
Thought: <你接下来要查什么、为什么>
Action: 检索: <一个检索查询>

如果你已经有足够信息回答, 改为输出:
Thought: <总结>
Final: <最终答案>

问题: {q}
已进行的步骤:
{trace}"""

def react_answer(query, max_steps=3, timeout=60):
    t0 = time.monotonic()
    trace = "(无)"
    last_obs = ""
    for step in range(max_steps):
        if time.monotonic() - t0 > timeout:
            return f"[超时熔断]{query}: 已超过{timeout}秒, 基于已有信息无法完整回答"
        r = client.chat.completions.create(model=MODEL, temperature=0,
            messages=[{"role": "user", "content": REACT_PROMPT.format(q=query, trace=trace)}])
        out = r.choices[0].message.content.strip()
        print(f"[ReAct 第{step+1}轮] {out[:120]}")
        if "Final:" in out:
            return out.split("Final:", 1)[1].strip()
        if "检索:" in out:
            q2 = out.split("检索:", 1)[1].strip().split("\n")[0]
            ctxs = retrieve_hybrid(q2, k=3)
            last_obs = "\n".join(c["text"][:120] for c in ctxs)
            trace += f"\n{out}\nObservation: {last_obs}"
        else:
            return out   # 模型没按格式来, 直接把输出当答案兜底
    return f"[步数上限]已达{max_steps}轮。已检索到的信息:\n{last_obs}"

if __name__ == "__main__":
    import sys
    print(react_answer(sys.argv[1]))
