# 📦 Mini CS Advisor Agent — Codebase (รวมไฟล์เดียว)

> ไฟล์นี้รวมโค้ด Python ทั้งหมดของโปรเจกต์ไว้ที่เดียว
> อัปโหลดไฟล์นี้เข้า Project Knowledge ของ Claude Projects
> เพื่อให้ Claude ตอบคำถามโดยอ้างอิงจากโค้ดจริงได้

---

## 📁 สารบัญ

1. [app.py](#app-py) — Entry point
2. [agent/decision.py](#agent-decision-py) — Tools (DB queries)
3. [llm/llm_helper.py](#llm-llm_helper-py) — LLM API wrapper
4. [rag/ingest.py](#rag-ingest-py) — PDF → Chunk → Embed → Qdrant
5. [rag/search.py](#rag-search-py) — Semantic search + rerank
6. [rag/rag_tool.py](#rag-rag_tool-py) — RAG wrapper
7. [build_curriculum_db.py](#build_curriculum_db-py) — สร้าง SQLite
8. [ragas/evaluate.py](#ragas-evaluate-py) — Custom metrics (Recall/Precision/MRR)
9. [ragas/run_ragas_eval.py](#ragas-run_ragas_eval-py) — Ragas framework
10. [ragas/test_judge.py](#ragas-test_judge-py) — Debug judge LLM

---

<a name="app-py"></a>
## 1. `app.py` — Entry Point

```python
from agent.decision import count_courses, get_course_detail, check_prerequisite, get_learning_path, get_study_plan
from llm.llm_helper import decide_action, generate_response
from rag.rag_tool import get_rag_context

TOOLS = {
    "count_courses": count_courses,
    "get_course_detail": get_course_detail,
    "check_prerequisite": check_prerequisite,
    "get_learning_path": get_learning_path,
    "get_study_plan": get_study_plan,
}

print("🎓 Mini CS Advisor Agent (Agent Version)")
print("พิมพ์ 'exit' เพื่อออก\n")

while True:
    user_input = input("คุณ: ")

    if user_input.lower() == "exit":
        break

    try:
        # 1️⃣ Agent decides action
        action_data = decide_action(user_input)

        if not action_data:
            print("Agent: ขออภัย ฉันไม่เข้าใจคำถามนี้")
            continue

        action_name = action_data["action"]
        action_input = action_data.get("input", {})

        print(f"🔧 Tool: {action_name}, Input: {action_input}")

        observation = None

        # 2️⃣ Execute tool if exists
        if action_name in TOOLS:
            observation = TOOLS[action_name](**action_input)

        # 3️⃣ RAG search
        # วิชาที่ tool ให้ข้อมูลครบแล้ว ไม่ต้องใช้ RAG เพิ่ม
        skip_rag = {"count_courses", "get_study_plan"}
        if action_name in skip_rag:
            rag_context = ""
        else:
            rag_context = get_rag_context(user_input)

        # 4️⃣ Combine context
        context = {
            "tool_result": observation,
            "rag_docs": rag_context
        }

        # 5️⃣ Generate final response
        final_answer = generate_response(context, user_input)

        print("Agent:", final_answer)

    except Exception as e:
        print("Agent Error:", e)
```

---

<a name="agent-decision-py"></a>
## 2. `agent/decision.py` — Tools (SQLite queries)

```python
import os
import sqlite3

# path ของ curriculum.db
base_dir = os.path.dirname(os.path.dirname(__file__))
DB_PATH  = os.path.join(base_dir, "curriculum.db")


def _get_conn():
    """เปิด connection พร้อม row_factory ทุกครั้งที่เรียก"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _normalize_id(course_id: str) -> str:
    """
    normalize course_id ให้มีช่องว่างระหว่าง prefix และตัวเลข
    เช่น "CS271" → "CS 271", "EL395" → "EL 395"
    ส่วน TH code เช่น "คพ.271" ไม่เปลี่ยน
    """
    import re
    m = re.match(r'^([A-Z]{2,4})(\d{3}[A-Z]?)$', course_id.strip().upper())
    if m:
        return f"{m.group(1)} {m.group(2)}"
    return course_id.strip()


# =============================================================================
# TOOLS
# =============================================================================

def count_courses():
    """นับจำนวนวิชาทั้งหมดในหลักสูตร"""
    with _get_conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) AS total FROM courses")
        return {"total_courses": cur.fetchone()["total"]}


def get_course_detail(course_id: str):
    """
    ดึงข้อมูลรายวิชา รองรับทั้ง EN code และ TH code
    เช่น "CS 271" หรือ "คพ.271"
    """
    course_id = _normalize_id(course_id)
    with _get_conn() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT code_en, code_th, name_en, name_th,
                   credits, lecture, lab, self_study
            FROM courses
            WHERE code_en = ? OR code_th = ?
        """, (course_id, course_id))
        row = cur.fetchone()

    if not row:
        return {"error": f"ไม่พบวิชา '{course_id}'"}

    # ดึง prerequisites ของวิชานี้ด้วย
    with _get_conn() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT p.requires, c.name_th
            FROM prerequisites p
            LEFT JOIN courses c ON p.requires = c.code_en
            WHERE p.course = ?
        """, (row["code_en"],))
        prereqs = [{"code": r["requires"], "name": r["name_th"]} for r in cur.fetchall()]

    return {
        "code_en":       row["code_en"],
        "code_th":       row["code_th"],
        "name_en":       row["name_en"],
        "name_th":       row["name_th"],
        "credits":       row["credits"],
        "hours":         {"lecture": row["lecture"], "lab": row["lab"], "self_study": row["self_study"]},
        "prerequisites": prereqs,
    }


def check_prerequisite(course_id: str, completed_courses: list = None):
    """
    ตรวจสอบว่าลงทะเบียนวิชานี้ได้ไหม
    completed_courses = list ของ EN code ที่ผ่านมาแล้ว เช่น ["CS 101", "CS 111"]

    คืนค่า:
      eligible       — ลงได้หรือไม่
      missing        — วิชาที่ยังขาด (required เท่านั้น)
      concurrent     — วิชาที่ต้องเรียนพร้อมกัน
      required_grade — วิชาที่ต้องผ่านด้วยเกรดที่กำหนด และยังไม่ผ่าน
    """
    if completed_courses is None:
        completed_courses = []

    course_id = _normalize_id(course_id)
    with _get_conn() as conn:
        cur = conn.cursor()

        # ตรวจว่าวิชามีอยู่ไหม
        cur.execute("SELECT code_en, name_th FROM courses WHERE code_en = ? OR code_th = ?",
                    (course_id, course_id))
        row = cur.fetchone()
        if not row:
            return {"error": f"ไม่พบวิชา '{course_id}'"}
        en_code = row["code_en"]

        # ดึง prerequisites พร้อม cond_type และ min_grade
        cur.execute("""
            SELECT p.requires, c.name_th, p.cond_type, p.min_grade
            FROM prerequisites p
            LEFT JOIN courses c ON p.requires = c.code_en
            WHERE p.course = ?
        """, (en_code,))
        prereqs = cur.fetchall()

    missing        = []
    concurrent     = []
    required_grade = []

    for p in prereqs:
        code      = p["requires"]
        name      = p["name_th"] or code
        cond_type = p["cond_type"]
        min_grade = p["min_grade"]

        if cond_type == "concurrent":
            concurrent.append({"code": code, "name": name})

        elif cond_type == "required_grade":
            if code not in completed_courses:
                required_grade.append({
                    "code":      code,
                    "name":      name,
                    "min_grade": min_grade,
                })

        else:  # required
            if code not in completed_courses:
                missing.append({"code": code, "name": name})

    eligible = len(missing) == 0 and len(required_grade) == 0

    return {
        "course":         en_code,
        "eligible":       eligible,
        "missing":        missing,
        "concurrent":     concurrent,
        "required_grade": required_grade,
    }


def get_learning_path(target_course_id: str):
    """
    หาลำดับวิชาที่ต้องเรียนก่อนถึงจะถึง target_course_id
    ไล่ย้อนกลับจาก prerequisites ชั้นเดียว (first prerequisite)
    """
    path    = []
    current = _normalize_id(target_course_id)

    with _get_conn() as conn:
        cur = conn.cursor()

        while current:
            cur.execute("SELECT code_en FROM courses WHERE code_en = ? OR code_th = ?",
                        (current, current))
            row = cur.fetchone()
            if not row:
                break
            en_code = row["code_en"]

            if en_code in path:  # ป้องกัน infinite loop
                break
            path.insert(0, en_code)

            cur.execute("SELECT requires FROM prerequisites WHERE course = ? LIMIT 1",
                        (en_code,))
            prereq = cur.fetchone()
            current = prereq["requires"] if prereq else None

    return {"learning_path": path}


def get_study_plan(major: str, year: int = None, track: str = None):
    """
    ดูแผนการศึกษา
    major : "CIS" หรือ "ACS"
    year  : 1-4 (ถ้าไม่ระบุ = ทุกปี)
    track : "project", "coop", "all" (ถ้าไม่ระบุ = ทุก track)
    """
    with _get_conn() as conn:
        cur = conn.cursor()

        query  = """
            SELECT sp.code_en,
                   COALESCE(c.name_th, sp.code_en) AS name_th,
                   c.credits,
                   sp.year, sp.semester, sp.track, sp.course_type
            FROM study_plan sp
            LEFT JOIN courses c ON sp.code_en = c.code_en
            WHERE sp.major = ?
        """
        params = [major]

        if year is not None:
            query  += " AND sp.year = ?"
            params.append(year)

        if track is not None:
            query  += " AND sp.track IN (?, 'all')"
            params.append(track)

        query += " ORDER BY sp.year, sp.semester, sp.code_en"

        cur.execute(query, params)
        rows = cur.fetchall()

    return {
        "major":   major,
        "year":    year,
        "track":   track,
        "courses": [dict(r) for r in rows],
        "total":   len(rows),
    }
```

---

<a name="llm-llm_helper-py"></a>
## 3. `llm/llm_helper.py` — LLM API Wrapper

```python
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

    if "choices" not in data:
        print("LLM ERROR:", data)
        return None

    return data["choices"][0]["message"]["content"]


def decide_action(user_input):
    system_prompt = """
คุณเป็น Academic Advisor Agent

คุณมี tools ดังนี้:
1. count_courses()
   - ใช้เมื่อถามว่ามีกี่วิชา เช่น "มีกี่วิชา" "จำนวนวิชาทั้งหมด"
   - ห้ามใช้เมื่อถามว่า "มีวิชาอะไรบ้าง" หรือ "ปีที่ X เรียนอะไร"

2. get_course_detail(course_id)
   - ใช้เมื่อถามรายละเอียดวิชาที่รู้รหัสแน่นอน เช่น "CS 271 คืออะไร" "คพ.251 มีกี่หน่วยกิต"

3. check_prerequisite(course_id, completed_courses)
   - ใช้เมื่อถามว่า "ลงวิชานี้ได้ไหม" "ผ่านเงื่อนไขไหม"

4. get_learning_path(target_course_id)
   - ใช้เมื่อถามว่า "ต้องเรียนอะไรบ้างก่อนถึงจะเรียน X ได้"

5. get_study_plan(major, year, track)
   - ใช้เมื่อถามว่า "ปีที่ X เรียนอะไรบ้าง" "แผนการเรียนของวิชาเอก X"

ถ้าคำถามไม่ตรงกับ tool ไหนเลย ให้ตอบว่า:
{"action": "none", "input": {}}

ให้ตอบเป็น JSON เท่านั้น:
{
  "action": "ชื่อฟังก์ชัน",
  "input": {}
}
"""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_input}
    ]

    result = call_llm(messages)
    if not result:
        return None

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
    tool_result = context.get("tool_result", {})
    rag_docs = context.get("rag_docs", "")

    if isinstance(rag_docs, list):
        rag_docs = "\n\n".join(rag_docs)

    messages = [
        {
            "role": "system",
            "content": """คุณคือผู้ช่วยแนะแนวหลักสูตรวิทยาการคอมพิวเตอร์ มหาวิทยาลัยธรรมศาสตร์
ตอบโดยใช้เฉพาะข้อมูลที่อยู่ใน "ข้อมูลจากระบบ" และ "ข้อมูลจากเอกสารหลักสูตร" เท่านั้น
ห้ามเพิ่มข้อมูลที่ไม่มีในเอกสาร

กฎสำคัญ:
- ถ้า "ข้อมูลจากระบบ" มีข้อมูล ให้ใช้ข้อมูลนั้นเป็นหลักในการตอบ ห้ามใช้ข้อมูลจากที่อื่นแทน
- ถ้า "ข้อมูลจากระบบ" ว่างเปล่า ให้ใช้ "ข้อมูลจากเอกสารหลักสูตร" แทน
- ถ้าคำถามไม่เกี่ยวกับวิชาเลย เช่น ทักทาย ให้ตอบทักทายกลับตามปกติ
อธิบายสั้น กระชับ เข้าใจง่าย ห้ามใส่ <think>"""
        },
        {
            "role": "user",
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

    result = call_llm(messages)
    if not result:
        return "เกิดข้อผิดพลาดในการสร้างคำตอบ"

    start = result.find("</think>")
    if start != -1:
        result = result[start + len("</think>"):].strip()

    return result
```

---

<a name="rag-ingest-py"></a>
## 4. `rag/ingest.py` — PDF Ingestion Pipeline

```python
import fitz
import re
from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams, Distance, PointStruct


def load_pdf(path):
    text = ""
    doc = fitz.open(path)
    for page in doc:
        extracted = page.get_text("text")
        if extracted:
            cleaned = re.sub(r'\n', ' ', extracted)
            cleaned = re.sub(r'\s+', ' ', cleaned)
            text += cleaned + "\n"
    return text


def split_by_course(text):
    # ตัดข้อความทุกตำแหน่งที่ขึ้นต้นด้วยตัวเลขตามด้วย .
    pattern = r'(?=\d+\.\s+[^\d])'
    parts = re.split(pattern, text)
    chunks = [p.strip() for p in parts if p.strip()]
    return chunks


def extract_metadata(chunk):
    th_code = re.findall(r'คพ\s*\.\s*\d+', chunk)
    en_code = re.findall(r'CS\d+', chunk)
    en_name = re.findall(r'CS\d+\s+([A-Za-z][A-Za-z\s\-]+)\)', chunk)
    th_name = re.findall(r'คพ\s*\.\s*\d+\s+([\u0E00-\u0E7F][^\(]+)', chunk)

    return {
        "th_code": th_code[0] if th_code else None,
        "en_code": en_code[0] if en_code else None,
        "en_name": en_name[0].strip() if en_name else None,
        "th_name": th_name[0].strip() if th_name else None,
    }


model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")

def create_embeddings(chunks):
    return model.encode(chunks)


client = QdrantClient("localhost", port=6333)

# ลบ collection เก่า ป้องกันข้อมูลซ้ำ
try:
    client.delete_collection("coursesdetail")
except:
    pass

client.create_collection(
    collection_name="coursesdetail",
    vectors_config=VectorParams(
        size=384,
        distance=Distance.COSINE
    )
)


def store_vectors(chunks, embeddings):
    points = []
    for i, (chunk, emb) in enumerate(zip(chunks, embeddings)):
        metadata = extract_metadata(chunk)
        points.append(
            PointStruct(
                id=i,
                vector=emb,
                payload={
                    "text": chunk,
                    "th_code": metadata["th_code"],
                    "en_code": metadata["en_code"],
                    "en_name": metadata["en_name"],
                    "th_name": metadata["th_name"],
                    "chunk_index": i,
                }
            )
        )

    client.upsert(
        collection_name="coursesdetail",
        points=points
    )


if __name__ == "__main__":
    text = load_pdf("data/coursesdetail.pdf")
    chunks = split_by_course(text)
    embeddings = create_embeddings(chunks)
    store_vectors(chunks, embeddings)
    print("✅ Ingest Complete")
```

> ⚠️ **สังเกต:** ingest.py ใช้ collection name `"coursesdetail"` แต่ search.py ใช้ `"course_chunks_collection"` — อาจทำให้ search ไม่เจอข้อมูล

---

<a name="rag-search-py"></a>
## 5. `rag/search.py` — Semantic Search + Rerank

```python
import re
from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient

COLLECTION_NAME = "course_chunks_collection"

model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
client = QdrantClient("localhost", port=6333)


def extract_code(query: str) -> str | None:
    """ดึงรหัสวิชา EN จากคำถาม เช่น 'CS271' → 'CS 271'"""
    match = re.search(r"CS\s*\d{3}", query, re.IGNORECASE)
    if match:
        raw = match.group(0).upper()
        return re.sub(r"CS(\d)", r"CS \1", raw)
    return None


def rerank_with_code_boost(query: str, docs: list) -> list:
    """
    ถ้าคำถามระบุรหัสวิชาตรงๆ เช่น "CS 271 คืออะไร"
    → boost score ของวิชานั้น +1.0 เพื่อให้ขึ้นมาอันดับแรก
    """
    code = extract_code(query)

    def score(doc):
        base = doc["score"]
        if code and doc.get("en_code") == code:
            base += 1.0
        return base

    return sorted(docs, key=score, reverse=True)


def search_doc_with_id(query: str, top_k: int = 3) -> list:
    """
    ค้นหาเอกสารที่เกี่ยวข้องกับคำถามจาก Qdrant
    ขั้นตอน:
      1. แปลงคำถามเป็น vector ด้วย embedding model
      2. ค้นหา top_k chunks ที่ใกล้เคียงที่สุด
      3. rerank โดย boost วิชาที่ตรงกับรหัสในคำถาม
    """
    query_vector = model.encode(query)

    results = client.query_points(
        collection_name=COLLECTION_NAME,
        query=query_vector,
        limit=top_k,
    ).points

    docs = []
    for r in results:
        docs.append({
            "id":      r.id,
            "text":    r.payload["text"],
            "th_code": r.payload.get("th_code"),
            "en_code": r.payload.get("en_code"),
            "th_name": r.payload.get("th_name"),
            "en_name": r.payload.get("en_name"),
            "score":   r.score,
        })

    docs = rerank_with_code_boost(query, docs)
    return docs[:top_k]
```

---

<a name="rag-rag_tool-py"></a>
## 6. `rag/rag_tool.py` — RAG Wrapper

```python
from rag.search import search_doc_with_id

def get_rag_context(query):
    """
    ค้นหาเอกสารที่เกี่ยวข้องจาก Qdrant แล้วคืนเป็น string context
    """
    docs = search_doc_with_id(query)

    parts = []
    for doc in docs:
        header = f"[{doc['en_code']} | {doc['th_name']}]"
        parts.append(f"{header}\n{doc['text']}")

    return "\n\n".join(parts)
```

---

<a name="build_curriculum_db-py"></a>
## 7. `build_curriculum_db.py` — สร้าง SQLite DB

```python
"""
build_curriculum_db.py
======================
สร้าง SQLite database จากไฟล์ course_info.json + PDF (สำหรับ prerequisites)
ได้ 3 ตาราง:
  - courses      : ข้อมูลทุกรายวิชา (103 วิชา รวม GE)
  - prerequisites: วิชาบังคับก่อน พร้อม cond_type และ min_grade
  - study_plan   : ว่างไว้รอ --only-plan มาเติม
"""

import json
import re
import sqlite3
import pdfplumber
from pathlib import Path

JSON_PATH = "test-ingest/result/course_info.json"
PDF_PATH  = "data/CSTU_BSc_2566_V4_Edit 29 มิย 2566.pdf"
DB_PATH   = "curriculum.db"

COURSE_DESC_START = 44
COURSE_DESC_END   = 117

# FONT ENCODING FIX (PDF ใช้ font แปลก)
FONT_MAP = {
    "\uf052": "", "\uf06f": "",
    "\uf701": "\u0e34", "\uf702": "\u0e35", "\uf703": "\u0e36",
    "\uf705": "\u0e48", "\uf706": "\u0e49", "\uf709": "\u0e4c",
    # ... (ตัดให้สั้น — ดูไฟล์ต้นฉบับ)
}

def fix_encoding(text: str) -> str:
    for k, v in FONT_MAP.items():
        text = text.replace(k, v)
    return text


# TH CODE → EN CODE MAPPING
TH_TO_EN = {
    "คพ.100": "CS 100", "คพ.101": "CS 101", "คพ.102": "CS 102",
    # ... (มี 80+ รายการ — ดูไฟล์ต้นฉบับ)
    "สษ.295": "EL 295", "สษ.395": "EL 395",
}


# 1. โหลด JSON → courses
with open(JSON_PATH, encoding="utf-8") as f:
    data: dict = json.load(f)

CREDIT_OVERRIDE = {
    "CS 303": 2, "CS 304": 2,
    "CS 403": 4, "CS 404": 4,
}

courses_rows = []
for en_code, info in data.items():
    credits = CREDIT_OVERRIDE.get(en_code, info["credits"])
    courses_rows.append({
        "code_en":    info["en_code"],
        "code_th":    info["th_code"],
        "name_en":    info["en_name"],
        "name_th":    info["th_name"],
        "credits":    credits,
        "lecture":    info["hours"]["lecture"],
        "lab":        info["hours"]["lab"],
        "self_study": info["hours"]["self_study"],
    })


# 2. Parse prerequisites จาก PDF
COURSE_HEADER = re.compile(r"^([ก-ฮ]{1,3}\.\s*\d{3})\s+")
PREREQ_START  = re.compile(r"^วิชาบังคับก่อน[:：]\s*(.+)")
PREREQ_CONT   = re.compile(r"^(เคยศึกษา|ศึกษาพร้อมกับ|สอบได้)")
CODE_PAT      = re.compile(r"[ก-ฮ]{1,4}\.\d{3}[ก-ฮ]?")
GRADE_PAT     = re.compile(r"ไม่ต่ำกว่า(?:ระดับ)?\s*([A-D])")

# ... (อ่าน PDF ทีละหน้า, parse prerequisites แต่ละวิชา)


def parse_prereq_raw(th_course: str, raw: str) -> list[dict]:
    """
    แปลง raw prerequisite string → list ของ edge พร้อม cond_type

    cond_type:
      required       — ต้องผ่านก่อน (เคยศึกษา)
      concurrent     — เรียนพร้อมกันได้ (ศึกษาพร้อมกับ)
      required_grade — ต้องผ่านด้วยเกรดที่กำหนด (สอบได้ ... ไม่ต่ำกว่า C)
    """
    # ... (logic สำหรับแยก cond_type และ min_grade)


# 3. สร้าง SQLite 3 ตาราง: courses, prerequisites, study_plan
# ... (CREATE TABLE + INSERT)

# 4. สร้าง Index สำหรับ query ที่ใช้บ่อย
# CREATE INDEX idx_courses_th    ON courses(code_th)
# CREATE INDEX idx_prereq_course ON prerequisites(course)
# CREATE INDEX idx_prereq_req    ON prerequisites(requires)
# CREATE INDEX idx_prereq_type   ON prerequisites(cond_type)
# CREATE INDEX idx_plan_major    ON study_plan(major, track, year, semester)
```

> ℹ️ **หมายเหตุ:** ไฟล์เต็มยาว 333 บรรทัด ถ้าต้องการดู logic แบบละเอียดให้เปิด `build_curriculum_db.py` ในโปรเจกต์

---

<a name="ragas-evaluate-py"></a>
## 8. `ragas/evaluate.py` — Custom Metrics

```python
from search import search_doc_with_id

# Test dataset
test_data = [
    {"query": "วิชา CS102 เรียนอะไร",              "relevant_ids": [1]},
    {"query": "อยากเรียนเรื่อง OOP ต้องลงวิชาอะไร?",  "relevant_ids": [2]},
    {"query": "วิชาไหนสอนเรื่อง sorting และ searching?", "relevant_ids": [3]},
    {"query": "วิชาไหนเกี่ยวกับ algorithm บ้าง?",       "relevant_ids": [3]},
]


def recall_at_k(retrieved_ids, relevant_ids, k):
    """เจอของถูกกี่ชิ้นจากทั้งหมดที่ควรเจอ"""
    hit_count = 0
    for r in retrieved_ids[:k]:
        if r in relevant_ids:
            hit_count += 1
    return hit_count / len(relevant_ids) if relevant_ids else 0


def precision_at_k(retrieved_ids, relevant_ids, k):
    """ของที่เอามา กี่ชิ้นที่ถูก"""
    hit_count = 0
    for r in retrieved_ids[:k]:
        if r in relevant_ids:
            hit_count += 1
    return hit_count / len(retrieved_ids[:k]) if retrieved_ids else 0


def mrr_at_k(retrieved_ids, relevant_ids):
    """คำตอบที่ถูกอยู่ลำดับที่เท่าไหร่ (1/rank)"""
    for i, r in enumerate(retrieved_ids):
        if r in relevant_ids:
            return 1 / (i + 1)
    return 0


def evaluate_recall(top_k=3):
    total = 0
    for item in test_data:
        results = search_doc_with_id(item["query"], top_k)
        retrieved_ids = [r["id"] for r in results]
        score = recall_at_k(retrieved_ids, item["relevant_ids"], top_k)
        total += score
    return total / len(test_data)


def evaluate_precision(top_k=3):
    total = 0
    for item in test_data:
        results = search_doc_with_id(item["query"], top_k)
        retrieved_ids = [r["id"] for r in results]
        score = precision_at_k(retrieved_ids, item["relevant_ids"], top_k)
        total += score
    return total / len(test_data)


def evaluate_mrr(top_k=3):
    total = 0
    for item in test_data:
        results = search_doc_with_id(item["query"], top_k)
        retrieved_ids = [r["id"] for r in results]
        score = mrr_at_k(retrieved_ids, item["relevant_ids"])
        total += score
    return total / len(test_data)


if __name__ == "__main__":
    recall    = evaluate_recall(top_k=3)
    precision = evaluate_precision(top_k=3)
    mrr       = evaluate_mrr(top_k=3)

    print("Recall@3 เจอของถูกไหม =", recall)
    print("Precision@3 ของที่เอามา มั่วไหม =", precision)
    print("MRR@3 คำตอบที่ถูก อยู่ลำดับที่เท่าไหร่ =", mrr)
```

---

<a name="ragas-run_ragas_eval-py"></a>
## 9. `ragas/run_ragas_eval.py` — Ragas Framework

```python
"""
RAGAS Evaluation — ใช้ Google Gemini 2.5 Flash เป็น judge LLM
Metrics: Faithfulness, AnswerRelevancy, ContextPrecision, ContextRecall
"""

import json
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
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_huggingface import HuggingFaceEmbeddings

# ⚠️ SECURITY: ควรย้าย API key ไป .env
llm_judge = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    google_api_key="<YOUR_API_KEY>"  # ⚠️ hardcoded ในโค้ดจริง
)
llm = LangchainLLMWrapper(llm_judge)

hf_embeddings = HuggingFaceEmbeddings(
    model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
)
embeddings = LangchainEmbeddingsWrapper(hf_embeddings)

metrics = [
    Faithfulness(llm=llm),
    AnswerRelevancy(llm=llm, embeddings=embeddings),
    ContextPrecision(llm=llm),
    ContextRecall(llm=llm),
]

# โหลด dataset
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

run_config = RunConfig(max_workers=1, timeout=600, max_retries=3)
result = evaluate(dataset, metrics=metrics, run_config=run_config)

print("\n📊 ผลลัพธ์ RAGAS (ค่าเฉลี่ย):")
print(result)

df = result.to_pandas()
print("\n📋 รายละเอียดต่อ sample:")
print(df[["user_input", "faithfulness", "answer_relevancy",
          "context_precision", "context_recall"]].to_string(index=False))
```

> ⚠️ **Security issue:** ต้นฉบับมี Google API key อยู่ในโค้ดตรงๆ ควรย้ายไป `.env`

---

<a name="ragas-test_judge-py"></a>
## 10. `ragas/test_judge.py` — Debug Judge LLM

```python
"""
ทดสอบ judge model โดยตรง เพื่อหาสาเหตุที่ได้ค่า 0
"""

from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage

OLLAMA_MODEL    = "qwen2.5:0.5b"
OLLAMA_BASE_URL = "http://localhost:11434"

llm = ChatOllama(model=OLLAMA_MODEL, base_url=OLLAMA_BASE_URL, temperature=0)

# TEST 1: faithfulness — แยก answer เป็น statements
r1 = llm.invoke([HumanMessage(content="""
Given the following answer, break it down into individual statements.
Answer: ถ้าอยากเรียนเรื่อง recursion ต้องลงวิชา คพ.102 ...
Return ONLY a JSON object like this: {"statements": ["statement 1", "statement 2"]}
""")])
print("TEST 1 Response:", r1.content)

# TEST 2: context_recall — แยก ground truth เป็น statements
# TEST 3: answer_relevancy — สร้างคำถามย้อนกลับจาก answer

# สรุป: ถ้า model ตอบเป็นภาษาไทยหรือไม่ใช่ JSON = นั่นคือสาเหตุที่ได้ 0
```

---

## 📌 สรุปภาพรวม

- **Core logic:** `app.py` → `decide_action()` เลือก tool → execute → RAG search → `generate_response()`
- **Data sources:** SQLite (`curriculum.db`) สำหรับข้อมูลโครงสร้าง + Qdrant สำหรับ semantic search บนเนื้อหา PDF
- **LLM:** ThaiLLM Playground (main) + Google Gemini (Ragas judge)
- **Evaluation:** Custom metrics (Recall/Precision/MRR) + Ragas framework

## ⚠️ จุดที่ควร Review

1. Collection name ไม่ตรงกัน (`coursesdetail` vs `course_chunks_collection`)
2. Google API key hardcoded ใน `run_ragas_eval.py`
3. ไม่มี unit test
4. Error handling ใน `ingest.py` ใช้ bare `except: pass`
