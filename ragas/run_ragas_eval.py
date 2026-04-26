"""
RAGAS Evaluation Script — ใช้ Ollama (llama3.2:3b) เป็น judge LLM
- patch ทั้ง invoke() และ ainvoke() บังคับ JSON ทุก call

ขั้นตอนก่อนรัน:
1. ollama pull llama3.2:3b
2. pip install ragas datasets langchain-ollama
3. python files/run_ragas_eval.py
"""

import json
import logging
logging.basicConfig(level=logging.DEBUG)
from pathlib import Path
from datasets import Dataset
from ragas import evaluate
from ragas.run_config import RunConfig
from ragas.metrics import (
    Faithfulness,
    AnswerRelevancy,
    ContextPrecision,
    ContextRecall,
)
from ragas.llms import LangchainLLMWrapper
from ragas.embeddings import LangchainEmbeddingsWrapper
# from langchain_ollama import ChatOllama, OllamaEmbeddings
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage
from langchain_huggingface import HuggingFaceEmbeddings

# ---- ตั้งค่า Ollama ----
OLLAMA_MODEL    = "qwen2.5:0.5b"
OLLAMA_BASE_URL = "http://localhost:11434"

# ---- สร้าง LLM และ embeddings ----
llm_judge = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash", 
    google_api_key="#"
)
llm = LangchainLLMWrapper(llm_judge)
hf_embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
embeddings = LangchainEmbeddingsWrapper(hf_embeddings)

# ---- instantiate metrics ----
metrics = [
    Faithfulness(llm=llm),
    AnswerRelevancy(llm=llm, embeddings=embeddings),
    ContextPrecision(llm=llm),
    ContextRecall(llm=llm),
]

# ---- โหลด dataset ----
script_dir   = Path(__file__).parent
dataset_path = script_dir / "ragas_dataset.json"

with open(dataset_path, "r", encoding="utf-8") as f:
    data = json.load(f)

ragas_data = {
    "question":     [d["question"]     for d in data],
    "answer":       [d["answer"]       for d in data],
    "contexts":     [d["contexts"]     for d in data],
    "ground_truth": [d["ground_truth"] for d in data],
}

dataset = Dataset.from_dict(ragas_data)

# ---- RunConfig: sequential ----
run_config = RunConfig(
    max_workers=1,
    timeout=600,
    max_retries=3,
)

# ---- รัน evaluation ----
print("🦙 กำลังรัน RAGAS ด้วย Ollama llama3.2:3b (JSON-forced mode) ...\n")
result = evaluate(dataset, metrics=metrics, run_config=run_config)

print("\n📊 ผลลัพธ์ RAGAS (ค่าเฉลี่ย):")
print(result)

df = result.to_pandas()
print("\n📋 รายละเอียดต่อ sample:")
print(df[["user_input", "faithfulness", "answer_relevancy",
          "context_precision", "context_recall"]].to_string(index=False))
