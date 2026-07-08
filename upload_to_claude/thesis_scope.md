# Mini CS Advisor Agent — Thesis Scope

**วันที่ agree:** 2026-04-22
**เป้าหมาย:** ช่วย นศ ตอบคำถามหลักสูตร/ลงทะเบียน/รายวิชา เพื่อประกอบการตัดสินใจและวางแผน

---

## มีอยู่แล้ว (ไม่ต้องทำซ้ำ)

- 5 tools: count, detail, prereq, path, plan
- RAG (Qdrant + sentence-transformers)
- SQLite structured data (courses, prerequisites, study_plan)
- decide_action + generate_response
- Ragas evaluation framework

---

## Must-have (ต้องเพิ่ม)

- [ ] **Tool chaining** — เรียก tool หลายตัวในคำถามเดียว
- [ ] **Fallback handling** — tool ไม่เจอข้อมูล → ใช้ RAG แทน
- [ ] **Conversation memory** — เก็บ context 2-3 turn ล่าสุด

---

## Should-have (ถ้ามีเวลา)

- [ ] **Intent clarification** — ถามกลับเมื่อคำถามกำกวม
- [ ] **Baseline comparison** — LLM เปล่า vs RAG only vs ระบบเต็ม
- [ ] **User study** — ให้ นศ จริง 5-10 คนทดลองใช้

---

## Evaluation (สำคัญที่สุดสำหรับ thesis)

- [ ] สร้าง test set 50-100 คำถามจากคำถามจริงของ นศ
- [ ] วัด faithfulness, answer relevancy, context precision
- [ ] ทำ error analysis — ตอบผิดตรงไหน เพราะอะไร

---

## ไม่ทำ (Overkill — อย่าเผลอขยาย scope)

- ~~Multi-agent architecture~~
- ~~Self-reflection / critique loop~~
- ~~Long-term memory / user profile~~
- ~~Fine-tuning / RL~~
- ~~ระบบลงทะเบียนแทน นศ จริง~~

---

## หลักการ

เป้าหมายคือ **ช่วย นศ ตัดสินใจได้จริง** ไม่ใช่ **สร้าง agent ที่ซับซ้อนที่สุด**
เกณฑ์วัด = ความถูกต้องของคำตอบ + คุณภาพ evaluation ไม่ใช่ความซับซ้อนของ architecture
