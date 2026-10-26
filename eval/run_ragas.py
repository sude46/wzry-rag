"""Day 5: 用 RAGAS 给 baseline 的 20 条问答打四指标分
输入: eval/baseline_results.jsonl (run_eval.py 的产物, 不用重新检索生成)
"""
import sys
import types

# 补丁: ragas 0.3.1 引用了 langchain-community 0.4 已移除的 vertexai 模块
# 我们不用 vertexai, 打个桩让 import 通过
_stub = types.ModuleType("langchain_community.chat_models.vertexai")
_stub.ChatVertexAI = type("ChatVertexAI", (), {})
sys.modules["langchain_community.chat_models.vertexai"] = _stub

import json
import os
from ragas import RunConfig
from datasets import Dataset
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from ragas import evaluate
from ragas.embeddings import LangchainEmbeddingsWrapper
from ragas.llms import LangchainLLMWrapper
from ragas.metrics import (AnswerRelevancy, Faithfulness,
                           LLMContextPrecisionWithReference, LLMContextRecall)

BASE = os.environ.get("EMBED_BASE_URL", "https://api.siliconflow.cn/v1")
KEY = os.environ["EMBED_API_KEY"]

judge = LangchainLLMWrapper(ChatOpenAI(
    base_url=BASE, api_key=KEY,
    model=os.environ.get("GEN_MODEL", "Qwen/Qwen2.5-7B-Instruct"),
    temperature=0, max_retries=5))
emb = LangchainEmbeddingsWrapper(OpenAIEmbeddings(
    base_url=BASE, api_key=KEY,
    model=os.environ.get("EMBED_MODEL", "BAAI/bge-m3")))

import sys
IN = sys.argv[1] if len(sys.argv) > 1 else "eval/baseline_results.jsonl"
OUT = IN.replace("eval/results_", "reports/ragas_").replace(".jsonl", ".csv")
rows = [json.loads(l) for l in open(IN, encoding="utf-8")]
rows = [r for r in rows if r.get("category") != "拒答"]  # 拒答题不进RAGAS
print(f"输入: {IN} ({len(rows)}条)")
ds = Dataset.from_list([{
    "user_input": r["question"],
    "response": r["answer"],
    "retrieved_contexts": r["contexts"],
    "reference": r["ground_truth"],
} for r in rows])

result = evaluate(
    ds,
    metrics=[Faithfulness(), AnswerRelevancy(),
             LLMContextPrecisionWithReference(), LLMContextRecall()],
    llm=judge, embeddings=emb,
    run_config=RunConfig(timeout=120,max_retries=3)
    )
print(result)
result.to_pandas().to_csv(OUT, index=False)
print(f"明细已存 {OUT}")
