"""
Debug script — ทดสอบ AnswerRelevancy metric แยกต่างหาก
เพื่อดู error จริงๆ ที่ทำให้ได้ NaN
รัน: python ragas/test_answer_relevancy.py
"""

import os
import logging
logging.basicConfig(level=logging.WARNING)  # ลด noise จาก DEBUG

from dotenv import load_dotenv
from datasets import Dataset
from ragas import evaluate
from ragas.run_config import RunConfig
from ragas.metrics import AnswerRelevancy
from ragas.llms import LangchainLLMWrapper
from ragas.embeddings import LangchainEmbeddingsWrapper
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_huggingface import HuggingFaceEmbeddings

load_dotenv()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

print("1️⃣  โหลด LLM...")
llm_judge = ChatGoogleGenerativeAI(
    model="gemini-2.0-flash",
    google_api_key=GOOGLE_API_KEY,
)
llm = LangchainLLMWrapper(llm_judge)
print("   ✅ LLM OK")

print("2️⃣  โหลด HuggingFace embeddings...")
try:
    hf_embeddings = HuggingFaceEmbeddings(
        model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    )
    embeddings = LangchainEmbeddingsWrapper(hf_embeddings)
    # ทดสอบ embed จริง
    test_vec = hf_embeddings.embed_query("ทดสอบ")
    print(f"   ✅ Embeddings OK (dim={len(test_vec)})")
except Exception as e:
    print(f"   ❌ Embeddings ERROR: {e}")
    raise

print("3️⃣  ทดสอบ LLM call โดยตรง...")
try:
    from langchain_core.messages import HumanMessage
    resp = llm_judge.invoke([HumanMessage(content="ตอบสั้นๆ: 1+1 เท่ากับเท่าไหร่")])
    print(f"   ✅ LLM call OK: {resp.content[:50]}")
except Exception as e:
    print(f"   ❌ LLM call ERROR: {e}")
    raise

print("4️⃣  รัน AnswerRelevancy บน 1 คำถาม...")
dataset = Dataset.from_dict({
    "question":     ["อยากเรียนเรื่อง OOP ต้องลงวิชาอะไร?"],
    "answer":       ["วิชาที่สอน OOP คือ คพ.111 แนวคิดเชิงวัตถุ (CS111) โดยมีวิชาบังคับก่อนคือ คพ.102"],
    "contexts":     [["คพ.111 แนวคิดเชิงวัตถุ (CS111 Object-Oriented Concepts) วิชาบังคับก่อน: คพ.102"]],
    "ground_truth": ["วิชาที่สอน OOP คือ คพ.111 (CS111 Object-Oriented Concepts)"],
})

metric = AnswerRelevancy(llm=llm, embeddings=embeddings)
run_config = RunConfig(max_workers=1, timeout=120, max_retries=2)

try:
    result = evaluate(dataset, metrics=[metric], run_config=run_config)
    df = result.to_pandas()
    print(f"\n   ผลลัพธ์ answer_relevancy = {df['answer_relevancy'].iloc[0]}")
    if str(df['answer_relevancy'].iloc[0]) == "nan":
        print("   ⚠️  ยังได้ NaN — ดู WARNING/ERROR ด้านบน")
    else:
        print("   ✅ สำเร็จ!")
except Exception as e:
    print(f"   ❌ evaluate ERROR: {e}")
