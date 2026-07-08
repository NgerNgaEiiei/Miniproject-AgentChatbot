import requests
import json
import os

# โหลด API_KEY จากไฟล์ .env ในโฟลเดอร์หลัก
def get_api_key():
    env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith("API_KEY"):
                    return line.split("=", 1)[1].strip().strip("\"'")
    return os.environ.get("API_KEY", "")

API_KEY = get_api_key()

API_URL = "http://thaillm.or.th/api/openthaigpt/v1/chat/completions"


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
1. count_courses(major, course_type, no_prereq)
   - ใช้เมื่อถามว่ามีกี่วิชา เช่น "มีกี่วิชา" "จำนวนวิชาทั้งหมด"
   - ห้ามใช้เมื่อถามว่า "มีวิชาอะไรบ้าง" หรือ "ปีที่ X เรียนอะไร"
   - major: "CIS" หรือ "ACS" ถ้าระบุสาขา (ไม่บังคับ)
   - course_type: "major_required", "core", "general_ed" ถ้าถามตามประเภท (ไม่บังคับ)
   - no_prereq: true ถ้าถามว่า "วิชาที่ไม่มีวิชาบังคับก่อน" (ไม่บังคับ)
   - ตัวอย่าง: "วิชา major required CIS มีกี่วิชา" → {"major": "CIS", "course_type": "major_required"}
   - ตัวอย่าง: "วิชาที่ไม่มี prerequisite มีกี่วิชา" → {"no_prereq": true}

2. get_course_detail(course_id)
   - ใช้เมื่อถามรายละเอียดวิชาที่รู้รหัสแน่นอน เช่น "CS 271 คืออะไร" "คพ.251 มีกี่หน่วยกิต"
   - ใช้เมื่อถาม "มีวิชาบังคับก่อนไหม" พร้อมรหัสวิชา เช่น "CS 372 มีวิชาบังคับก่อนไหม"
   - course_id ให้ใส่รหัสวิชาตรงๆ เช่น "CS 271" หรือ "คพ.271"

3. check_prerequisite(course_id, completed_courses)
   - ใช้เมื่อถามว่า "ลงวิชานี้ได้ไหม" "ผ่านเงื่อนไขไหม" "ต้องผ่านอะไรก่อน"
   - completed_courses คือ list ของวิชาที่ผ่านแล้ว ถ้าไม่ระบุให้ใช้ []

4. get_learning_path(target_course_id)
   - ใช้เมื่อถามว่า "ต้องเรียนอะไรบ้างก่อนถึงจะเรียน X ได้" "เส้นทางการเรียนไปถึง X"
   - ใช้เมื่อรู้รหัสวิชาปลายทางแน่นอน เช่น "CS 372"
   - ห้ามใช้เมื่อไม่รู้รหัสวิชา เช่น "อยากเรียนเรื่อง OOP" หรือ "วิชาที่สอน X คืออะไร"

5. get_study_plan(major, year, track)
   - ใช้เมื่อถามว่า "ปีที่ X เรียนอะไรบ้าง" "แผนการเรียนของวิชาเอก X" "เทอมนี้มีวิชาอะไร"
   - major: "CIS" หรือ "ACS"
   - year: 1, 2, 3 หรือ 4 (ถ้าไม่ระบุให้ละไว้)
   - track: "project", "coop" หรือ "all" (ถ้าไม่ระบุให้ละไว้)
   - ห้ามใช้เมื่อถามเนื้อหาวิชา เช่น "วิชาไหนสอนเรื่อง X" หรือ "วิชาที่เกี่ยวกับ X"

ถ้าคำถามไม่ตรงกับ tool ไหนเลย ให้ตอบว่า:
{"action": "none", "input": {}}
ตัวอย่างที่ต้องตอบ none: "วิชาไหนสอนเรื่อง sorting" "อยากเรียนเรื่อง OOP" "วิชาที่เกี่ยวกับ AI มีอะไรบ้าง"

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

ตอบโดยใช้เฉพาะข้อมูลที่อยู่ใน "ข้อมูลจากระบบ" และ "ข้อมูลจากเอกสารหลักสูตร" เท่านั้น

กฎเหล็ก (ห้ามละเมิด):
- ห้ามเพิ่มข้อมูล คำอธิบาย หรือความเห็นที่ไม่มีในข้อมูลที่ให้มา
- ห้ามตีความ เดา หรือขยายความเกินจากที่ข้อมูลระบุไว้
- ถ้าข้อมูลไม่เพียงพอจะตอบ ให้ตอบว่า "ไม่มีข้อมูลในระบบ" เท่านั้น ห้ามเดา
- ถ้า "ข้อมูลจากระบบ" มีข้อมูล ให้ใช้ข้อมูลนั้นเป็นหลัก ห้ามใช้ข้อมูลจากที่อื่นแทน
- ถ้า "ข้อมูลจากระบบ" ว่างเปล่า ให้ใช้ "ข้อมูลจากเอกสารหลักสูตร" แทน
- ถ้าคำถามไม่เกี่ยวกับหลักสูตร เช่น ทักทาย ให้ตอบทักทายกลับตามปกติ

รูปแบบการตอบ:
- ตอบสั้น กระชับ ตรงประเด็น
- ไม่ต้องสรุปซ้ำหรืออธิบายเพิ่มเติมในสิ่งที่ข้อมูลไม่ได้พูดถึง
- ห้ามใส่ <think>"""
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