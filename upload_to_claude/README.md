# 🎓 Mini CS Advisor Agent

Mini Agent-based Academic Advisor สำหรับหลักสูตร Computer Science
พัฒนาเพื่อทดลองแนวคิด LLM Agent + Tool Execution + Retrieval Augmented Generation (RAG)

ระบบสามารถตอบคำถามเกี่ยวกับหลักสูตร เช่น
- รายละเอียดรายวิชา
- จำนวนวิชา
- การตรวจสอบ prerequisite
- ข้อมูลจากเอกสารหลักสูตร
- โดยใช้ LLM เป็นตัวตัดสินใจ (decision maker) และ tools / database เป็นแหล่งข้อมูลจริง

---

## 📌 Overview

โปรเจกต์นี้เป็นการพัฒนา Agent ที่สามารถ:

- วิเคราะห์คำถามผู้ใช้ด้วย LLM
- ตัดสินใจเลือกใช้ Tool ที่เหมาะสม
- ดึงข้อมูลจากฐานข้อมูลรายวิชา (JSON)
- ค้นข้อมูลจากเอกสารหลักสูตรด้วย RAG (Vector Search)
- สร้างคำตอบอธิบายผลลัพธ์ให้เข้าใจง่าย

แนวคิดหลักของระบบคือ
```bash
LLM = reasoning + decision
Tools / RAG = trusted knowledge source
``` 

LLM ที่ใช้ ThaiLLM Playground 👉 https://playground.thaillm.or.th/

---

## 🧠 Architecture เดิม
```bash
User  
↓  
LLM → decide action  
↓  
Tool execution (Python functions เขียนเอง)  
↓  
LLM → generate response  
↓  
User
```
## 🧠 Architecture + RAG
```bash
User
 ↓
LLM → decide action
 ↓
Tool execution (Python functions)
 ↓
RAG search (Vector DB)
 ↓
Context combination
 ↓
LLM → generate response
 ↓
User
```  

---

## 🛠 Tools ที่รองรับ

1. `count_courses()`  
   → นับจำนวนรายวิชาในหลักสูตร

2. `get_course_detail(course_id)`  
   → ดึงรายละเอียดของรายวิชา

3. `check_prerequisite(course_id, completed_courses)`  
   → ตรวจสอบว่าสามารถลงทะเบียนเรียนได้หรือไม่

---

## 📚 RAG Knowledge Source
นอกจาก tools แล้ว ระบบยังสามารถค้นข้อมูลจาก
```bash
เอกสารหลักสูตร (PDF)
```
โดยใช้เทคนิค
```bash
Retrieval Augmented Generation (RAG)
```
Pipeline
```bash
PDF
 ↓
Text Chunking
 ↓
Embedding
 ↓
Vector Database (Qdrant)
 ↓
Semantic Search
 ↓
Context for LLM
```

Vector model ที่ใช้
```bash
sentence-transformers
all-MiniLM-L6-v2
```

Vector dimension 
```bash
384
```

Vector dimension คือ จำนวนตัวเลขที่ใช้แทนความหมายของข้อความใน embedding vector (ข้อความ → แปลงเป็น list ของตัวเลข)
จำนวนตัวเลขนั้นเรียกว่า dimension
ตัวอย่าง
สมมติเรามีคำว่า
```bash
"cat"
```
model อาจแปลงเป็น vector แบบนี้
```bash
[0.12, -0.33, 0.91]
```
มี 3 ตัวเลข ดังนั้น dimension = 3

## 🎓 Base Knowledge (JSON)
```JSON
{
  "courses": [
    {
      "course_id": "CS101",
      "course_name": "Intro to CS",
      "prerequisites": []
    },
    {
      "course_id": "CS201",
      "course_name": "Data Structures",
      "prerequisites": ["CS101"]
    },
    {
      "course_id": "CS301",
      "course_name": "Hello",
      "prerequisites": ["CS201"]
    }
  ]
}
```

### 📌 Explanation

- `course_id` — รหัสวิชา  
- `course_name` — ชื่อวิชา  
- `prerequisites` — รายการวิชาที่ต้องเรียนก่อน
---

## 🚀 How to Run

1. เปิด Terminal
2.  สร้าง virtual environment
```bash
python -m venv venv
.\venv\Scripts\Activate
```

3. ติดตั้ง dependencies
```bash
pip install requests
```

4. รันโปรแกรม
```bash
python app.py
```

**Response:**
```bash
🎓 Mini CS Advisor Agent (Agent Version)
พิมพ์ 'exit' เพื่อออก

คุณ: 
```

## 💡 Example Usage
```bash
คุณ: เรียนวิชา CS301 ได้ไหม
Agent: ไม่สามารถเรียนวิชา CS301 ได้ เนื่องจากขาดวิชา CS201 ซึ่งเป็นวิชาที่ต้องเรียนก่อน
```

```bash
คุณ: มีกี่วิชา
Agent: มี 3 วิชา
```

---
ในบางกรณี LLM จะเพิ่มคำอธิบายหรือคำแนะนำเพิ่มเติม เพื่อให้บทสนทนาดูเป็นธรรมชาติและมีความเป็นผู้ช่วยมากขึ้น
อย่างไรก็ตาม ข้อมูลหลักยังคงมาจาก tool ซึ่งเป็นแหล่งข้อมูลที่เชื่อถือได้ เช่น

### 🔍 Ask: เรียนวิชา CS101 ได้ไหม
```bash
คุณ: เรียนวิชา CS101 ได้ไหม
Agent: เรียนวิชา CS101 ได้เลยครับ คุณมีสิทธิ์เรียนวิชานี้ได้ และไม่มีวิชาใดที่ขาดหายไป คุณพร้อมที่จะเริ่มเรียนแล้ว

**คำแนะนำเพิ่มเติม:**

*   **เตรียมตัว:** ศึกษาพื้นฐานการเขียนโปรแกรมเบื้องต้น เช่น ภาษา Python หรือ Java เพื่อให้เข้าใจเนื้อหาในวิชาได้ดีขึ้น
*   **อุปกรณ์:** ตรวจสอบว่าคุณมีคอมพิวเตอร์และโปรแกรมที่จำเป็นสำหรับการเรียนวิชานี้หรือไม่
*   **ถามคำถาม:** ไม่ต้องกลัวที่จะถามคำถามครับ อาจารย์และเพื่อนร่วมชั้นยินดีช่วยเหลือ
*   **ฝึกฝน:** ฝึกเขียนโปรแกรมบ่อยๆ เพื่อให้เกิดความชำนาญ
*   **ตั้งเป้าหมาย:** กำหนดเป้าหมายในการเรียนวิชานี้ เพื่อให้คุณมีแรงจูงใจในการเรียน

ขอให้คุณประสบความสำเร็จในการเรียนวิชา CS101 นะครับ
```

### 🔍 Ask: วิชา CS101 ชื่อว่า
```bash
คุณ: วิชา CS101 ชื่อว่า
Agent: วิชา CS101 มีชื่อว่า **Intro to CS** หรือ **Introduction to Computer Science** ซึ่งเป็นวิชาที่           
สอนพื้นฐานของวิทยาการคอมพิวเตอร์สำหรับผู้เริ่มต้นเรียนรู้ ไม่ว่าจะเป็นการเขียนโปรแกรม การแก้ปัญหาด้วย                  
คอมพิวเตอร์ หรือแนวคิดพื้นฐานอื่นๆ ที่เกี่ยวข้องกับการพัฒนาซอฟต์แวร์และระบบคอมพิวเตอร์
```

### 🔍 Ask: ลงเรียนวิชา CS201 ได้ไหม
```bash
คุณ: ลงเรียนวิชา CS201 ได้ไหม
Agent: ไม่สามารถลงเรียนวิชา CS201 ได้ในขณะนี้ เนื่องจากคุณยังไม่ได้เรียนวิชา CS101 ซึ่งเป็นวิชาที่ต้อองเรียนก่อนหน้า

**คำแนะนำ:**

*   ลงเรียนวิชา CS101 ก่อน
*   เมื่อเรียนวิชา CS101 จบแล้ว คุณจะสามารถลงเรียนวิชา CS201 ได้

**เหตุผล:**

วิชา CS201 เป็นวิชาที่ต้องเรียนหลังจากวิชา CS101 เสร็จสิ้นแล้ว ดังนั้นจึงต้องเรียนวิชา CS101 ก่อน
```
🧠 ทำไม LLM ถึงเติมเองแบบนี้
เพราะ LLM ถูกฝึกมาให้:
- helpful
- explanatory
- supportive
- structured (หัวข้อ, bullet, เหตุผล)
โดยเฉพาะเมื่อมันเห็น pattern แบบนี้:
- ❌ ลงไม่ได้
- 📌 มีทางแก้ (เรียน CS101 ก่อน)

LLM จะตีความว่า:
“ผู้ใช้ควรรู้ วิธีแก้ปัญหา ไม่ใช่แค่ ผลลัพธ์”
เลยเกิด:
- คำแนะนำ
- เหตุผล
- การจัดรูปแบบสวย ๆ
นี่คือ default behavior ของ generative model
ไม่ใช่ bug และไม่ใช่ logic error




