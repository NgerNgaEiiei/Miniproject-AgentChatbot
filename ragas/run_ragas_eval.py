"""
RAGAS Evaluation Script — ใช้ Gemini 2.5 Flash เป็น judge LLM
- อ่าน GOOGLE_API_KEY จาก .env (อย่า hardcode key ใน code!)

ขั้นตอนก่อนรัน:
1. pip install ragas datasets langchain-google-genai langchain-huggingface python-dotenv
2. ตรวจสอบว่ามีไฟล์ .env ที่ root project และมี GOOGLE_API_KEY อยู่
3. python ragas/run_ragas_eval.py
"""

import json
import os
import time
import logging
logging.basicConfig(level=logging.DEBUG)
from pathlib import Path
from dotenv import load_dotenv
import pandas as pd
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
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_huggingface import HuggingFaceEmbeddings

# ---- โหลด environment variables จาก .env ----
load_dotenv()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
if not GOOGLE_API_KEY:
    raise ValueError("ไม่พบ GOOGLE_API_KEY ใน .env — กรุณาเพิ่ม GOOGLE_API_KEY = '...' ในไฟล์ .env")

# ---- สร้าง LLM และ embeddings ----
llm_judge = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    google_api_key=GOOGLE_API_KEY,
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

# ---- RunConfig: sequential ----
run_config = RunConfig(
    max_workers=1,
    timeout=600,
    max_retries=5,
)

# ---- รัน evaluation ทีละคำถาม เพื่อหลีกเลี่ยง Rate Limit 429 ----
SLEEP_BETWEEN = 15  # วินาที (Gemini Free Tier = ~5 RPM)

print("🔍 กำลังรัน RAGAS ด้วย Gemini 2.5 Flash เป็น judge LLM ...\n")
print(f"📌 ทั้งหมด {len(data)} คำถาม | หน่วงเวลา {SLEEP_BETWEEN} วิ ระหว่างแต่ละคำถาม\n")

all_dfs = []

for i, item in enumerate(data):
    print(f"[{i+1}/{len(data)}] ประเมิน: {item['question'][:50]}...")

    single_dataset = Dataset.from_dict({
        "question":     [item["question"]],
        "answer":       [item["answer"]],
        "contexts":     [item["contexts"]],
        "ground_truth": [item["ground_truth"]],
    })

    try:
        result = evaluate(single_dataset, metrics=metrics, run_config=run_config)
        all_dfs.append(result.to_pandas())
        print(f"  ✅ สำเร็จ")
    except Exception as e:
        print(f"  ❌ Error: {e}")

    if i < len(data) - 1:
        print(f"  ⏳ รอ {SLEEP_BETWEEN} วิ...")
        time.sleep(SLEEP_BETWEEN)

# ---- สรุปผล ----
if all_dfs:
    df = pd.concat(all_dfs, ignore_index=True)

    cols = ["user_input", "faithfulness", "answer_relevancy", "context_precision", "context_recall"]
    print("\n📋 ผลลัพธ์รายคำถาม:")
    print(df[cols].to_string(index=False))

    print("\n📊 ค่าเฉลี่ยทั้งหมด:")
    numeric_cols = ["faithfulness", "answer_relevancy", "context_precision", "context_recall"]
    print(df[numeric_cols].mean().round(4).to_string())
else:
    print("\n⚠️ ไม่มีผลลัพธ์ อาจเกิดข้อผิดพลาดทุกคำถาม")