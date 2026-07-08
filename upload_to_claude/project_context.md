# 🎓 Mini CS Advisor Agent — Project Context

> ไฟล์นี้ใช้เป็น "บริบทหลัก" ให้ Claude เข้าใจโปรเจกต์ thesis อย่างรวดเร็ว
> อัปโหลดไฟล์นี้เข้า Project Knowledge ของ Claude Projects

---

## 🎯 เป้าหมาย Thesis

พัฒนา **Mini CS Advisor Agent** — ระบบแชทบอทที่ช่วยตอบคำถามเกี่ยวกับหลักสูตรวิทยาการคอมพิวเตอร์ (ของมหาวิทยาลัยธรรมศาสตร์) ทดลองแนวคิด

- **LLM Agent** — ใช้ LLM เป็นตัวตัดสินใจ (reasoning + decision)
- **Tool Execution** — เรียกใช้ Python function / Database queries สำหรับข้อมูลที่เชื่อถือได้
- **Retrieval Augmented Generation (RAG)** — ดึงข้อมูลจาก PDF หลักสูตรเพื่อเสริมคำตอบ

แนวคิด: **LLM = reasoning + decision, Tools/RAG = trusted knowledge source**

---

## 🧠 Architecture

```
User
 ↓
LLM (decide_action) → เลือก tool ที่เหมาะสม
 ↓
Tool execution (ดึงข้อมูลจาก SQLite)
 ↓
RAG search (Qdrant Vector DB) — ข้ามได้ถ้า tool ให้ข้อมูลครบแล้ว
 ↓
Context combination (tool_result + rag_docs)
 ↓
LLM (generate_response) → สร้างคำตอบภาษาธรรมชาติ
 ↓
User
```

---

## 🛠 Tech Stack

| Layer | Technology |
|---|---|
| Language | Python 3 |
| LLM API | ThaiLLM Playground (OpenThaiGPT) |
| LLM Orchestration | LangChain (สำหรับ Ragas evaluation) |
| Vector DB | Qdrant (localhost:6333) |
| Embeddings | sentence-transformers `paraphrase-multilingual-MiniLM-L12-v2` (384 dim) |
| Relational DB | SQLite (`curriculum.db`) |
| PDF parsing | PyMuPDF (`fitz`), pdfplumber |
| Evaluation | Ragas framework + Google Gemini as judge LLM |

---

## 📂 โครงสร้างไฟล์

```
Miniproject-AgentChatbot/
├── app.py                          # Entry point — loop รับ input, เรียก tool, สร้างคำตอบ
├── build_curriculum_db.py          # สคริปต์สร้าง curriculum.db จาก JSON + PDF
├── curriculum.db                   # SQLite (courses, prerequisites, study_plan)
├── requirements.txt
├── .env                            # API_KEY (ThaiLLM) — ห้ามอัปโหลด
│
├── agent/
│   └── decision.py                 # TOOLS: count_courses, get_course_detail,
│                                   #        check_prerequisite, get_learning_path,
│                                   #        get_study_plan
├── llm/
│   └── llm_helper.py               # call_llm(), decide_action(), generate_response()
├── rag/
│   ├── ingest.py                   # โหลด PDF → chunk → embed → ลง Qdrant
│   ├── search.py                   # semantic search + rerank with course code boost
│   └── rag_tool.py                 # wrapper สำหรับเรียกใน app.py
├── ragas/
│   ├── evaluate.py                 # Recall@k, Precision@k, MRR@k (custom metrics)
│   ├── run_ragas_eval.py           # Ragas framework (Faithfulness, AnswerRelevancy,
│   │                               #                  ContextPrecision, ContextRecall)
│   ├── ragas_dataset.json          # Q&A dataset พร้อม ground_truth
│   └── test_judge.py               # debug script ทดสอบ judge LLM
├── data/
│   ├── CSTU_BSc_2566_V4_Edit 29 มิย 2566.pdf   # เอกสารหลักสูตรฉบับเต็ม
│   ├── courses.json                             # sample เล็ก ๆ
│   ├── coursesdetail.pdf
│   └── curriculum.pdf
└── qdrant/                         # local Qdrant storage (ไม่ต้องอัปโหลด)
```

---

## 🔧 Tools ที่ Agent เลือกใช้ได้ (ตาม decision.py)

| Tool | ใช้เมื่อ | Input |
|---|---|---|
| `count_courses()` | ถามจำนวนวิชาทั้งหมด | — |
| `get_course_detail(course_id)` | ถามรายละเอียดวิชา | `"CS 271"` หรือ `"คพ.271"` |
| `check_prerequisite(course_id, completed_courses)` | ถามว่าลงได้ไหม | course_id + list วิชาที่ผ่านแล้ว |
| `get_learning_path(target_course_id)` | ถามลำดับเรียนก่อนถึงวิชา X | target course id |
| `get_study_plan(major, year, track)` | ถามแผนการเรียน | major: "CIS"/"ACS", year 1-4, track: "project"/"coop"/"all" |

Prerequisite มี 3 ประเภท (`cond_type`):
- `required` — ต้องผ่านก่อน
- `concurrent` — เรียนพร้อมกันได้ (ศึกษาพร้อมกับ)
- `required_grade` — ต้องผ่านด้วยเกรดขั้นต่ำ (สอบได้ ... ไม่ต่ำกว่า C)

---

## 🔍 RAG Pipeline (ingest.py → search.py → rag_tool.py)

1. **Load PDF** — `fitz.open()` + regex clean
2. **Chunking** — split by course pattern `(?=\d+\.\s+[^\d])`
3. **Metadata extraction** — ดึง `th_code`, `en_code`, `th_name`, `en_name` จาก chunk
4. **Embedding** — `paraphrase-multilingual-MiniLM-L12-v2` (384 dim, cosine)
5. **Store** — Qdrant collection
6. **Search** — top_k=3 + rerank โดย boost +1.0 ถ้ารหัสวิชาในคำถามตรง

---

## 📊 Evaluation

### Custom metrics (`ragas/evaluate.py`)
- Recall@k — เจอของถูกครบไหม
- Precision@k — ของที่เอามามั่วไหม
- MRR@k — คำตอบถูกอยู่อันดับที่เท่าไหร่

### Ragas framework (`ragas/run_ragas_eval.py`)
- Faithfulness — คำตอบยึดกับ context ไหม
- AnswerRelevancy — คำตอบตรงคำถามไหม
- ContextPrecision — context ที่ retrieve มาเกี่ยวไหม
- ContextRecall — ดึง context ครบไหม

Judge LLM: Google Gemini 2.5 Flash

---

## ⚠️ จุดที่อาจต้องทบทวน / ปรับปรุง

1. **Security** — ใน `ragas/run_ragas_eval.py` มี Google API key hardcoded ในโค้ด (บรรทัด `google_api_key="AIza..."`) ควรย้ายไปไว้ใน `.env`

2. **Collection name ไม่ตรงกัน**
   - `rag/ingest.py` ใช้ `collection_name="coursesdetail"`
   - `rag/search.py` ใช้ `COLLECTION_NAME = "course_chunks_collection"`
   - อาจทำให้ search ไม่เจอข้อมูล ถ้าไม่ได้ ingest ไปที่ collection เดียวกัน

3. **README example ล้าสมัย** — ตัวอย่างใน README.md ยังใช้ JSON แบบเก่า (CS101, CS201, CS301) ซึ่งไม่ตรงกับ `courses.json` ปัจจุบัน (CS102, CS111, CS216)

4. **Temperature = 0** — ใน `call_llm()` ตั้งเป็น 0 เพื่อ deterministic ซึ่งเหมาะกับ evaluation แต่อาจทำให้คำตอบแข็งเกินไป

5. **Error handling** — บาง exception ถูก pass ไว้เฉย ๆ (เช่น `client.delete_collection` ใน ingest.py) ควร log ด้วย

6. **ไม่มี test unit test** — ควรเพิ่ม pytest สำหรับ tools ใน `decision.py`

---

## 🎓 สิ่งที่ต้องการความช่วยเหลือจาก Claude

- Review โค้ดและสถาปัตยกรรม ชี้จุดอ่อน / best practices
- อธิบายการทำงานของ RAG pipeline เพื่อเอาไปเขียนในบท Methodology
- ช่วยแก้บั๊ก เช่น กรณี collection name ไม่ตรง
- เสนอ improvement เช่น re-ranker, hybrid search, query expansion
- ช่วยวิเคราะห์ผล Ragas และเขียน discussion
- ช่วยเขียนส่วนของ thesis (Implementation, Evaluation, Discussion)
- แนะนำ paper ที่ควรอ้างอิงในสาขานี้

**ภาษา:** ตอบเป็นภาษาไทยเป็นหลัก ศัพท์เทคนิคใช้ภาษาอังกฤษ
