# Improvement Notes — Mini CS Advisor Agent

> Hub รวบรวมจุดแข็ง จุดอ่อน และแนวทางพัฒนาเพิ่มเติมของโปรเจก
> ใช้เป็น backlog ไม่ต้องเร่งแก้ทั้งหมดในรอบเดียว

อัปเดตล่าสุด: 2026-04-30

---

## 1. RAG System

### 1.1 จุดแข็ง

**1) Multilingual embedding model**
ใช้ `paraphrase-multilingual-MiniLM-L12-v2` ที่ embed ภาษาไทยและอังกฤษใน vector space เดียวกัน ทำให้คำถามภาษาไทยสามารถค้นหา chunk ที่มีคำศัพท์ทั้งไทยและอังกฤษได้ เหมาะกับเอกสารหลักสูตรที่ปนสองภาษา

**2) Hybrid reranking (dense + symbolic)**
ฟังก์ชัน `rerank_with_code_boost` ใน `rag/search.py` แก้จุดอ่อนของ embedding ที่มักมองรหัสวิชาใกล้เคียงกัน (CS 271 vs CS 211) เป็นเรื่องเดียวกัน การ +1.0 ให้รหัสวิชาที่ตรงทำให้ผลลัพธ์แม่นขึ้นชัดเจน เป็น pattern best-practice ของ hybrid retrieval

**3) Rich metadata payload**
Qdrant payload เก็บ `th_code`, `en_code`, `th_name`, `en_name` ครบ ทำให้สามารถ rerank/filter ตาม metadata ได้ และ format header เพื่อให้ LLM อ่านง่าย (`[CS 271 | โครงสร้างข้อมูล]`)

**4) Conditional RAG**
ไม่ได้เรียก RAG ทุกคำถาม (`skip_rag` set ใน `app.py`) ลด latency + ลด noise สำหรับคำถามที่ structured DB ตอบได้ครบอยู่แล้ว เช่น `count_courses`, `get_study_plan`

---

### 1.2 จุดอ่อน + ข้อแนะนำ

**W1 — Dead code / Code duplication ใน ingestion**

มี 2 ingestion pipelines ที่ collection name ไม่ตรงกัน:

- `rag/ingest.py` → collection `"coursesdetail"`
- `test-ingest/ingest_course_chunks.py` → collection `"course_chunks_collection"`

`rag/search.py` ใช้ `"course_chunks_collection"` ดังนั้น `rag/ingest.py` คือ **dead code**

ผลกระทบ: reviewer/อาจารย์เปิดอ่านจะสับสน + maintainability แย่

แนวทาง: ลบ `rag/ingest.py` ทิ้ง หรือย้าย `ingest_course_chunks.py` มาอยู่ใน `rag/` ให้เป็น single source of truth

---

**W2 — extract_code รองรับแค่ prefix "CS"**

ใน `rag/search.py`:
```python
match = re.search(r"CS\s*\d{3}", query, re.IGNORECASE)
```

ปัญหา:
- ไม่รองรับ TH code (`คพ.271`)
- ไม่รองรับ prefix อื่น (MA, EL, TU)
- ถ้า user ถามเป็นไทย → ไม่ boost → retrieval อาจแย่

แนวทาง: ขยาย regex รองรับทั้ง EN code หลาย prefix และ TH code

---

**W3 — Top-k ตายตัวที่ 3**

ทุก query ดึง 3 chunks เท่ากัน:
- คำถามเฉพาะ (เช่น "CS 271 คืออะไร") — 1 chunk พอ → 2 chunks ที่เหลือเป็น noise
- คำถามกว้าง (เช่น "วิชาเกี่ยวกับ AI มีอะไรบ้าง") — 3 chunks อาจน้อยไป

แนวทาง:
- Score threshold (เก็บเฉพาะ score > 0.7)
- Adaptive top-k ตามประเภทคำถาม
- MMR (Maximal Marginal Relevance) — relevant + diverse

---

**W4 — ไม่ตรวจความยาว chunk / ไม่มี overlap**

ถ้า chunk ยาวเกิน 512 tokens (limit ของ MiniLM) embedding จะ truncate ทำให้ข้อมูลท้าย chunk หาย

แนวทาง:
- Validate ความยาวก่อน embed
- ถ้ายาวเกิน split ย่อยด้วย overlap 10-20%
- เช็คด้วย `model.tokenizer.encode(chunk)`

---

**W5 — ไม่มี evaluation ของ retrieval แยกจาก generation**

Ragas ตอนนี้ evaluate แบบ end-to-end ถ้าคำตอบแย่ จะแยกไม่ออกว่า retrieval ดึงผิด หรือ generation ใช้ context ไม่ดี

แนวทาง:
- เพิ่ม `context_precision` และ `context_recall` (Ragas มีให้แล้ว)
- เพิ่ม MRR (Mean Reciprocal Rank) เช็คว่า chunk ที่ relevant ที่สุดอยู่อันดับเท่าไหร่

---

### 1.3 แนวทางพัฒนาเพิ่มเติม (Thesis-level enhancements)

ส่วนนี้คือสิ่งที่ทำให้ thesis แข็งในเชิงวิจัย ไม่ใช่แค่ engineering ทุก idea คือการเพิ่ม empirical evidence ให้ design choice

**E1 — Embedding model comparison**

ลอง embedding model อื่นเทียบกับ MiniLM:
- multilingual-e5-small / e5-base
- BGE-M3 (multilingual, รองรับไทยดี)
- distiluse-base-multilingual-cased

Output: experiment table เทียบ retrieval metrics ใน thesis

Effort ขั้นต่ำ: เลือก 1 ตัวเทียบ, ใช้ test set 50 คำถาม → 1-2 วันเสร็จ (เปลี่ยนชื่อ model 1 บรรทัด + รัน eval)

---

**E2 — Chunking strategy comparison**

ลอง chunking หลายแบบเทียบกัน:
- Chunk by course (ปัจจุบัน)
- Chunk by paragraph
- Chunk by sentence with overlap
- Semantic chunking

Output: วัด precision/recall เทียบ → ใช้สนับสนุน design choice ใน thesis

---

**E3 — Cross-encoder reranking**

หลัง vector search → ใช้ cross-encoder rerank top-10 → เลือก top-3
- Candidate models: bge-reranker-base, MS-MARCO MiniLM
- Cross-encoder แม่นกว่า bi-encoder (vector search) แต่ช้ากว่า — ใช้รันแค่ rerank ตัวที่ candidate

Output: เทียบ precision ก่อน/หลัง cross-encoder

---

## 2. Tools (agent/decision.py)

(พื้นที่รอเติมภายหลัง)

ประเด็นที่อาจกลับมาเขียน:
- get_course_detail เปิด SQLite connection 2 ครั้งในฟังก์ชันเดียว — ควร merge
- get_learning_path ไล่ prerequisite แบบ first-only (LIMIT 1) อาจไม่ครอบคลุมกรณี OR group

---

## 3. Agent Logic / Orchestration (app.py + llm/llm_helper.py)

(พื้นที่รอเติมภายหลัง)

ประเด็นที่อาจกลับมาเขียน:
- `skip_rag` เป็น blocklist (เปราะ) ควรเปลี่ยนเป็น allowlist หรือ tool metadata
- LLM hallucinate ชื่อ tool → ระบบ silent skip (no log) ควรเพิ่ม warning
- Action `"none"` กับ tool ที่ไม่อยู่ใน TOOLS รวมเส้นทางเดียวกัน อาจแยกได้

---

## 4. Evaluation Pipeline (ragas/)

(พื้นที่รอเติมภายหลัง)
