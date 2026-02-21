import requests
import json
import re

API_URL = "http://thaillm.or.th/api/openthaigpt/v1/chat/completions"
API_KEY = "hjcTjTVIklax0K1OUo7L0l6XTjuT0KbK"


def call_llm(messages):
    headers = {
        "Content-Type": "application/json",
        "apikey": API_KEY
    }

    payload = {
        "model": "/model",
        "messages": messages,
        "temperature": 0
    }

    response = requests.post(API_URL, headers=headers, json=payload)

    data = response.json()

    # debug ถ้า error
    if "choices" not in data:
        print("LLM ERROR:", data)
        return None

    return data["choices"][0]["message"]["content"]


def decide_action(user_input):
    system_prompt = """
คุณเป็น Academic Advisor Agent

คุณมี tools ดังนี้:
1. count_courses()
2. get_course_detail(course_id)
3. check_prerequisite(course_id, completed_courses)

ให้ตอบเป็น JSON เท่านั้น เช่น:

{
  "action": "ชื่อฟังก์ชัน",
  "input": {}
}

ห้ามอธิบาย
ห้ามตอบอย่างอื่น
"""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_input}
    ]

    result = call_llm(messages)

    if not result:
        return None

    # ดึง JSON block
    start = result.find("{")
    end = result.rfind("}")

    if start == -1 or end == -1:
        return None

    json_text = result[start:end+1]

    try:
        return json.loads(json_text)
    except:
        return None


def generate_response(observation, user_input):
    messages = [
        {"role": "system", "content": "ตอบสั้น กระชับ อธิบายผลลัพธ์ให้ผู้เรียนเข้าใจ ห้ามใส่ <think>"},
        {"role": "user", "content": f"คำถาม: {user_input}\nผลลัพธ์: {observation}"}
    ]

    result = call_llm(messages)

    if not result:
        return "เกิดข้อผิดพลาดในการสร้างคำตอบ"

    # 🔥 ลบ <think> ถ้ามี
    start = result.find("</think>")
    if start != -1:
        result = result[start + len("</think>"):].strip()

    return result