import requests
import json

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

    if response.status_code != 200:
        print("LLM HTTP ERROR:", response.text)
        return None
    
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
1. count_courses() — ใช้เมื่อถามว่ามีกี่วิชา เช่น "มีกี่วิชา" หรือ "จำนวนวิชาทั้งหมด" ห้ามใช้เมื่อถามว่า "มีวิชาอะไรบ้าง" หรือ "วิชาเกี่ยวกับอะไรบ้าง"
2. get_course_detail(course_id) — ใช้เมื่อถามรายละเอียดวิชาที่รู้รหัสแน่นอน เช่น CS102
3. check_prerequisite(course_id, completed_courses) — ใช้เมื่อถามว่า "เรียนได้เลยไหม" หรือ "ผ่านเงื่อนไขไหม"
4. get_learning_path(target_course_id) — ใช้เมื่อรู้รหัสวิชาแน่นอนเท่านั้น เช่น "เส้นทางการเรียนของ CS216" ห้ามใช้เมื่อถามเรื่องหัวข้อหรือเนื้อหา เช่น "OOP" หรือ "recursion"

ถ้าคำถามไม่ตรงกับ tool ไหนเลย ให้ตอบว่า:
{"action": "none", "input": {}}

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


def generate_response(context, user_input):

    tool_result = context.get("tool_result", {})    # ดึงข้อมูลจาก tool_result ใน context (app.py)
    rag_docs = context.get("rag_docs", "")          # ดึงข้อมูลจาก rag_docs ใน context (app.py) 

    if isinstance(rag_docs, list):                  # เช็คว่า rag_docs เป็น list ไหม
        rag_docs = "\n\n".join(rag_docs)            # รวม list เป็นข้อความเดียว ให้ LLM อ่านง่าย

    messages = [
        {
            "role": "system",   # กำหนดพฤติกรรมของ LLM
            "content": """คุณคือผู้ช่วยแนะแนวหลักสูตรวิทยาการคอมพิวเตอร์ มหาวิทยาลัยธรรมศาสตร์
ตอบคำถามนักศึกษาโดยใช้ข้อมูลที่ให้มาเท่านั้น
ห้ามเพิ่มข้อมูลที่ไม่มีในเอกสาร
ถ้าคำถามไม่เกี่ยวกับวิชาเลย เช่น ทักทาย ให้ตอบทักทายกลับตามปกติ ไม่ต้องแสดงข้อมูลวิชา
อธิบายสั้น กระชับ เข้าใจง่าย ห้ามใส่ <think>"""
        },
        {
            "role": "user",     # สร้างข้อความที่จะส่งให้ LLM
            "content": f"""
คำถาม:
{user_input}

ข้อมูลจากระบบ:
{tool_result}

ข้อมูลจากเอกสารหลักสูตร:
{rag_docs}

ให้ตอบโดยใช้ข้อมูลที่ให้มา
"""
        }
    ]

    result = call_llm(messages)     # เรียก LLM

    if not result:
        return "เกิดข้อผิดพลาดในการสร้างคำตอบ"

    start = result.find("</think>")
    if start != -1:
        result = result[start + len("</think>"):].strip()

    return result