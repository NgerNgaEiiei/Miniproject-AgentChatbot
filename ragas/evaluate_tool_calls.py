"""
Tool Call Accuracy Evaluation
================================================================
ประเมินว่า LLM Agent เลือกเครื่องมือ (Tool) ได้ถูกต้องไหม
ใช้ heuristic metric — ไม่ใช้ LLM judge → ไม่กิน API quota

วัด 3 metrics:
  1. Tool Selection Accuracy — เลือกชื่อ tool ถูกไหม
  2. Argument Accuracy — ใส่ arguments ถูกไหม (เฉพาะกรณี tool ตรง)
  3. Exact Match — tool + argument ถูกทั้งคู่

Reference:
  - AgentBench (Liu et al., 2023)
  - ToolBench (Qin et al., 2023)

วิธีรัน:
  python ragas/evaluate_tool_calls.py
"""

import json
import sys
from pathlib import Path

# เพิ่ม project root ใน path เพื่อ import llm.llm_helper
sys.path.insert(0, str(Path(__file__).parent.parent))

from llm.llm_helper import decide_action


# ==============================================================================
# CONFIG
# ==============================================================================
SCRIPT_DIR    = Path(__file__).parent
DATASET_PATH  = SCRIPT_DIR / "tool_call_dataset.json"
RESULT_PATH   = SCRIPT_DIR / "tool_call_result.json"


# ==============================================================================
# HELPERS — normalize arguments เพื่อเปรียบเทียบ
# ==============================================================================
def normalize_course_id(code: str) -> str:
    """
    Normalize รหัสวิชาให้รูปแบบเดียวกัน
    "CS271" → "CS 271", "cs 271" → "CS 271", "CS  271" → "CS 271"
    """
    import re
    if not isinstance(code, str):
        return code
    code = code.strip().upper()
    m = re.match(r'^([A-Z]{2,4})\s*(\d{3}[A-Z]?)$', code)
    if m:
        return f"{m.group(1)} {m.group(2)}"
    return code


def normalize_input(input_dict: dict) -> dict:
    """Normalize ค่าใน input dict ให้เปรียบเทียบได้"""
    if not isinstance(input_dict, dict):
        return {}
    normalized = {}
    for k, v in input_dict.items():
        if k in ("course_id", "target_course_id"):
            normalized[k] = normalize_course_id(v)
        elif k == "completed_courses" and isinstance(v, list):
            normalized[k] = sorted([normalize_course_id(c) for c in v])
        else:
            normalized[k] = v
    return normalized


# ==============================================================================
# METRICS
# ==============================================================================
def evaluate_single(predicted: dict, expected: dict) -> dict:
    """
    เปรียบเทียบ predicted action กับ expected action

    คืนค่า dict ของ 3 metrics:
      tool_selection: 1.0 ถ้าเลือก tool ถูก, 0.0 ถ้าผิด
      argument:       1.0 ถ้า arguments ถูก (เฉพาะตอน tool ถูก), 0.0 อื่นๆ
      exact_match:    1.0 ถ้าทั้ง tool และ argument ถูก, 0.0 อื่นๆ
    """
    if predicted is None:
        return {
            "tool_selection": 0.0,
            "argument": 0.0,
            "exact_match": 0.0,
            "predicted_action": None,
            "predicted_input": None,
        }

    pred_action = predicted.get("action", "")
    pred_input  = normalize_input(predicted.get("input", {}))
    exp_action  = expected.get("action", "")
    exp_input   = normalize_input(expected.get("input", {}))

    # 1. Tool Selection Accuracy
    tool_match = pred_action == exp_action

    # 2. Argument Accuracy (เฉพาะกรณี tool ตรง)
    arg_match = False
    if tool_match:
        arg_match = pred_input == exp_input

    # 3. Exact Match
    exact_match = tool_match and arg_match

    return {
        "tool_selection":   1.0 if tool_match else 0.0,
        "argument":         1.0 if arg_match else 0.0,
        "exact_match":      1.0 if exact_match else 0.0,
        "predicted_action": pred_action,
        "predicted_input":  pred_input,
    }


# ==============================================================================
# MAIN
# ==============================================================================
def main():
    # โหลด dataset
    with open(DATASET_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    print(f"📂 โหลด {len(data)} test cases จาก {DATASET_PATH.name}\n")
    print("=" * 80)

    results = []

    for i, item in enumerate(data):
        question = item["question"]
        expected = item["expected_action"]

        print(f"\n[{i+1}/{len(data)}] {question}")

        # เรียก decide_action ให้ LLM ตัดสินใจ
        try:
            predicted = decide_action(question)
        except Exception as e:
            print(f"  ❌ Error: {e}")
            predicted = None

        # เปรียบเทียบ
        scores = evaluate_single(predicted, expected)

        print(f"  Expected:  {expected['action']:25s} {expected.get('input', {})}")
        print(f"  Predicted: {scores['predicted_action'] or 'None':25s} {scores['predicted_input'] or {}}")
        print(f"  Tool Selection: {'✅' if scores['tool_selection'] else '❌'}  "
              f"Argument: {'✅' if scores['argument'] else '❌'}  "
              f"Exact Match: {'✅' if scores['exact_match'] else '❌'}")

        results.append({
            "question":         question,
            "expected_action":  expected,
            "predicted_action": {
                "action": scores["predicted_action"],
                "input":  scores["predicted_input"],
            },
            "tool_selection":   scores["tool_selection"],
            "argument":         scores["argument"],
            "exact_match":      scores["exact_match"],
        })

    # ==============================================================================
    # SUMMARY
    # ==============================================================================
    n = len(results)
    avg_tool   = sum(r["tool_selection"] for r in results) / n
    avg_arg    = sum(r["argument"]       for r in results) / n
    avg_exact  = sum(r["exact_match"]    for r in results) / n

    print("\n" + "=" * 80)
    print("📊 สรุปผล")
    print("=" * 80)
    print(f"\nจำนวนคำถาม: {n}")
    print(f"Tool Selection Accuracy : {avg_tool:.2%}  ({int(avg_tool * n)}/{n})")
    print(f"Argument Accuracy       : {avg_arg:.2%}  ({int(avg_arg * n)}/{n})")
    print(f"Exact Match             : {avg_exact:.2%}  ({int(avg_exact * n)}/{n})")

    # บันทึกผล
    output = {
        "summary": {
            "total_questions": n,
            "tool_selection_accuracy": round(avg_tool, 4),
            "argument_accuracy":       round(avg_arg, 4),
            "exact_match":             round(avg_exact, 4),
        },
        "details": results,
    }
    with open(RESULT_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n💾 บันทึกผลที่: {RESULT_PATH}")


if __name__ == "__main__":
    main()
