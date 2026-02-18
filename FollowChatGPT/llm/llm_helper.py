def classify_intent(user_input: str) -> str:
    user_input = user_input.lower()

    if "ได้ไหม" in user_input or "ลง" in user_input:
        return "check_prerequisite"

    return "unknown"

def explain_result(message: str) -> str:
    # mock LLM: แค่เรียบเรียงข้อความ
    return f"📌 ผลการพิจารณา:\n{message}"
