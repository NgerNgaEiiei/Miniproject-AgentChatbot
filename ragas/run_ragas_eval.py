"""
RAGAS Evaluation Script
==========================================================
- ใช้ InMemoryRateLimiter จำกัดที่ระดับ LLM call (กัน burst)
- Checkpoint ทุกคำถาม (JSON) → resume ได้ถ้า script crash
- Retry on 429 with exponential backoff (max_retries=10)
- ประเมิน Generation Quality ด้วย Ragas: Faithfulness, AnswerRelevancy, AnswerCorrectness

Output:
  ragas/ragas_checkpoints/q###.json   ← per-question raw data (Ragas)
  ragas/ragas_result.json             ← combined Ragas results + summary stats + metadata
  ragas/ragas_report.md               ← Markdown report (paste เข้า thesis ได้เลย)

ขั้นตอนก่อนรัน:
1. pip install ragas datasets langchain-google-genai langchain-huggingface python-dotenv langchain-core
2. ตรวจสอบว่ามีไฟล์ .env ที่ root project และมี GOOGLE_API_KEY อยู่
3. python ragas/run_ragas_eval.py

ถ้าหยุดกลางทาง → รันใหม่จะ resume จาก checkpoint อัตโนมัติ

Dataset format (ragas_dataset.json):
    - question:      str
    - answer:        str   ← คำตอบจากระบบ
    - contexts:      list  ← chunks ที่ระบบดึงมาใช้สร้างคำตอบ
    - ground_truth:  str   ← คำตอบอ้างอิงที่ถูกต้อง

หมายเหตุ: Retrieval Evaluation (Recall@k, Precision@k, MRR) ประเมินแยกใน ragas/evaluate.py
"""

import json
import math
import os
import logging
import statistics
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
from datasets import Dataset
from ragas import evaluate
from ragas.run_config import RunConfig
from ragas.metrics import (
    Faithfulness,
    AnswerRelevancy,
    AnswerCorrectness,
)
from ragas.llms import LangchainLLMWrapper
from ragas.embeddings import LangchainEmbeddingsWrapper
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_core.rate_limiters import InMemoryRateLimiter

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
log = logging.getLogger(__name__)


# ==============================================================================
# CONFIG
# ==============================================================================
load_dotenv()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
if not GOOGLE_API_KEY:
    raise ValueError("ไม่พบ GOOGLE_API_KEY ใน .env — กรุณาเพิ่ม GOOGLE_API_KEY = '...' ในไฟล์ .env")

MODEL_NAME     = "gemini-2.5-flash"   # Paid Tier: 1000 RPM, 10000 RPD
SCRIPT_DIR     = Path(__file__).parent
DATASET_PATH   = SCRIPT_DIR / "ragas_dataset.json"
CHECKPOINT_DIR = SCRIPT_DIR / "ragas_checkpoints"
CHECKPOINT_DIR.mkdir(exist_ok=True)
RESULT_JSON    = SCRIPT_DIR / "ragas_result.json"
REPORT_MD      = SCRIPT_DIR / "ragas_report.md"

METRIC_NAMES = ["faithfulness", "answer_relevancy", "answer_correctness"]


# ==============================================================================
# RATE LIMITER
# ==============================================================================
rate_limiter = InMemoryRateLimiter(
    requests_per_second=1.0,     # 60 RPM (well under 1000 RPM paid tier)
    check_every_n_seconds=0.1,
    max_bucket_size=10,
)


# ==============================================================================
# LLM + Embeddings
# ==============================================================================
llm_judge = ChatGoogleGenerativeAI(
    model=MODEL_NAME,
    google_api_key=GOOGLE_API_KEY,
    temperature=0,
    rate_limiter=rate_limiter,
    max_retries=10,
    timeout=120,
)
llm = LangchainLLMWrapper(llm_judge)

hf_embeddings = HuggingFaceEmbeddings(
    model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
)
embeddings = LangchainEmbeddingsWrapper(hf_embeddings)


# ==============================================================================
# METRICS — สร้างทีละตัวตอนรัน (เพื่อ selective retry)
# ==============================================================================
def make_metric(name: str):
    """สร้าง metric instance จากชื่อ"""
    if name == "faithfulness":
        return Faithfulness(llm=llm)
    elif name == "answer_relevancy":
        return AnswerRelevancy(llm=llm, embeddings=embeddings)
    elif name == "answer_correctness":
        return AnswerCorrectness(llm=llm, embeddings=embeddings)
    raise ValueError(f"Unknown metric: {name}")


# ==============================================================================
# RUN CONFIG
# ==============================================================================
run_config = RunConfig(
    max_workers=1,
    timeout=300,
    max_retries=10,
    max_wait=60,
)


# ==============================================================================
# LOAD DATASET
# ==============================================================================
with open(DATASET_PATH, "r", encoding="utf-8") as f:
    data = json.load(f)

log.info(f"โหลด {len(data)} คำถามจาก {DATASET_PATH.name}")


# ==============================================================================
# CHECKPOINT HELPERS — ใช้ JSON
# ==============================================================================
def get_checkpoint_path(idx):
    return CHECKPOINT_DIR / f"q{idx:03d}.json"


def save_checkpoint(idx, item, scores):
    """บันทึกผลรายคำถามเป็น JSON อ่านง่าย"""
    record = {
        "question_idx":    idx,
        "question":        item["question"],
        "answer":          item["answer"],
        "ground_truth":    item["ground_truth"],
        "contexts":        item["contexts"],
        "scores":          scores,
        "evaluated_at":    datetime.now().isoformat(timespec="seconds"),
    }
    with open(get_checkpoint_path(idx), "w", encoding="utf-8") as f:
        json.dump(record, f, ensure_ascii=False, indent=2)


def load_checkpoint(idx):
    p = get_checkpoint_path(idx)
    if not p.exists():
        return None
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


def extract_scores_from_result(result) -> dict:
    """
    ดึง scores จาก Ragas result object เป็น dict
    แปลง NaN → None เพื่อให้บันทึกใน JSON ได้ และคำนวณ stats ภายหลังไม่พัง
    """
    df = result.to_pandas()
    scores = {}
    for metric in METRIC_NAMES:
        if metric in df.columns:
            val = df[metric].iloc[0]
            if val is None:
                scores[metric] = None
            else:
                fval = float(val)
                # NaN เกิดเมื่อ Ragas คำนวณ metric นั้นไม่สำเร็จ (เช่น timeout / 503)
                scores[metric] = None if math.isnan(fval) else fval
    return scores


def get_metrics_to_run(idx: int):
    """
    ตรวจ checkpoint ว่ามี metric ไหนต้องรัน:
      - ถ้าไม่มี checkpoint → รันทุก metric
      - ถ้ามี checkpoint แต่บาง metric เป็น None/NaN → รันเฉพาะที่ failed
      - ถ้าครบทุก metric → คืน list ว่าง (ข้ามได้)
    คืน (metrics_to_run, existing_scores)
    """
    p = get_checkpoint_path(idx)
    if not p.exists():
        return list(METRIC_NAMES), {}

    with open(p, "r", encoding="utf-8") as f:
        record = json.load(f)

    existing = record.get("scores", {})
    to_run = []
    for metric in METRIC_NAMES:
        v = existing.get(metric)
        if v is None or (isinstance(v, float) and math.isnan(v)):
            to_run.append(metric)
    return to_run, existing


# ==============================================================================
# RUN — ทีละคำถาม + checkpoint
# ==============================================================================
log.info(f"🚀 เริ่มประเมินด้วย {MODEL_NAME}\n")

for i, item in enumerate(data):
    metrics_to_run, existing_scores = get_metrics_to_run(i)

    if not metrics_to_run:
        log.info(f"[{i+1}/{len(data)}] ⏭ ข้าม (checkpoint สมบูรณ์)")
        continue

    if existing_scores:
        log.info(
            f"[{i+1}/{len(data)}] 🔄 retry เฉพาะ metrics ที่ failed: {metrics_to_run}"
        )
    else:
        log.info(f"[{i+1}/{len(data)}] 📝 {item['question'][:60]}...")

    single_dataset = Dataset.from_dict({
        "question":     [item["question"]],
        "answer":       [item["answer"]],
        "contexts":     [item["contexts"]],
        "ground_truth": [item["ground_truth"]],
    })

    try:
        # สร้าง metric instances เฉพาะที่ต้องรัน → ประหยัด API calls
        metric_instances = [make_metric(m) for m in metrics_to_run]

        result = evaluate(
            single_dataset,
            metrics=metric_instances,
            run_config=run_config,
        )
        new_scores = extract_scores_from_result(result)

        # Merge: เก็บ existing + อัปเดตด้วย new_scores (ตัวที่เพิ่งรัน)
        merged_scores = {**existing_scores, **new_scores}

        save_checkpoint(i, item, merged_scores)
        log.info(f"    ✅ สำเร็จ — {new_scores}")
    except Exception as e:
        log.error(f"    ❌ Error: {e}")
        log.error(f"    → จะลองใหม่ครั้งหน้า (รัน script อีกครั้งเพื่อ resume)")


# ==============================================================================
# COMBINE RESULTS — รวม checkpoint + คำนวณ summary stats
# ==============================================================================
log.info("\n📊 รวมผลทั้งหมด...")

records = []
for p in sorted(CHECKPOINT_DIR.glob("q*.json")):
    with open(p, "r", encoding="utf-8") as f:
        records.append(json.load(f))

if not records:
    log.warning("⚠️ ไม่มีผลใน checkpoint")
    exit(0)


def compute_stats(values: list) -> dict:
    """
    คำนวณ mean, std, min, max ของ list (ไม่นับ None และ NaN)
    n = จำนวนคำถามที่ metric นี้คำนวณได้สำเร็จ
    """
    valid = [
        float(v) for v in values
        if v is not None and not (isinstance(v, float) and math.isnan(v))
    ]
    if not valid:
        return {"mean": None, "std": None, "min": None, "max": None, "n": 0}
    return {
        "mean": round(statistics.mean(valid), 4),
        "std":  round(statistics.stdev(valid), 4) if len(valid) > 1 else 0.0,
        "min":  round(min(valid), 4),
        "max":  round(max(valid), 4),
        "n":    len(valid),
    }


summary_stats = {
    metric: compute_stats([r["scores"].get(metric) for r in records])
    for metric in METRIC_NAMES
}

result_data = {
    "metadata": {
        "model":          MODEL_NAME,
        "dataset":        DATASET_PATH.name,
        "num_questions":  len(records),
        "metrics":        METRIC_NAMES,
        "evaluated_at":   datetime.now().isoformat(timespec="seconds"),
    },
    "summary": summary_stats,
    "details": records,
}

with open(RESULT_JSON, "w", encoding="utf-8") as f:
    json.dump(result_data, f, ensure_ascii=False, indent=2)


# ==============================================================================
# GENERATE MARKDOWN REPORT
# ==============================================================================
def generate_markdown_report(data: dict) -> str:
    md = []
    meta = data["metadata"]
    summary = data["summary"]
    details = data["details"]

    md.append(f"# RAGAS Evaluation Report\n")
    md.append(f"- **Model (Judge LLM)**: `{meta['model']}`")
    md.append(f"- **Dataset**: `{meta['dataset']}`")
    md.append(f"- **จำนวนคำถาม**: {meta['num_questions']}")
    md.append(f"- **เวลาที่ประเมิน**: {meta['evaluated_at']}")
    md.append("")
    md.append("## สรุปคะแนนเฉลี่ย (Generation Quality)\n")
    md.append("| Metric | Mean | Std | Min | Max | N |")
    md.append("|---|---|---|---|---|---|")
    for metric, stats in summary.items():
        md.append(
            f"| {metric} | {stats['mean']} | {stats['std']} | "
            f"{stats['min']} | {stats['max']} | {stats['n']} |"
        )
    md.append("")

    md.append("## ผลรายคำถาม\n")
    for r in details:
        md.append(f"### Q{r['question_idx'] + 1}: {r['question']}\n")
        md.append("**คะแนน:**")
        md.append("")
        md.append("| Metric | Score |")
        md.append("|---|---|")
        for metric in METRIC_NAMES:
            score = r["scores"].get(metric)
            if score is None or (isinstance(score, float) and math.isnan(score)):
                score_str = "❌ Failed (timeout/error)"
            else:
                score_str = f"{score:.4f}"
            md.append(f"| {metric} | {score_str} |")
        md.append("")
        md.append(f"**คำตอบของระบบ**: {r['answer'][:200]}{'...' if len(r['answer']) > 200 else ''}\n")
        md.append(f"**Ground Truth**: {r['ground_truth']}\n")
        md.append("---\n")
    return "\n".join(md)


report_md = generate_markdown_report(result_data)
REPORT_MD.write_text(report_md, encoding="utf-8")


# ==============================================================================
# CONSOLE SUMMARY
# ==============================================================================
print("\n" + "=" * 70)
print(f"✅ ประเมินสำเร็จ {len(records)}/{len(data)} คำถาม")
print("=" * 70)

print("\n📊 Generation Quality (Ragas):")
for metric, stats in summary_stats.items():
    if stats["mean"] is not None:
        print(f"  {metric:25s} = {stats['mean']:.4f}  (std={stats['std']:.4f}, n={stats['n']})")
    else:
        print(f"  {metric:25s} = N/A")

print(f"\n💾 ผลรวม Ragas (JSON):     {RESULT_JSON}")
print(f"💾 รายงาน (Markdown):      {REPORT_MD}")
print(f"💾 Checkpoint แต่ละ Q:     {CHECKPOINT_DIR}/")
