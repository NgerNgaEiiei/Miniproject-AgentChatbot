"""
ทดสอบ judge model โดยตรง เพื่อหาสาเหตุที่ได้ค่า 0
รัน: python files/test_judge.py
"""

from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage

OLLAMA_MODEL    = "qwen2.5:0.5b"
OLLAMA_BASE_URL = "http://localhost:11434"

llm = ChatOllama(model=OLLAMA_MODEL, base_url=OLLAMA_BASE_URL, temperature=0)

# ---- Test 1: faithfulness ----
# RAGAS ส่ง prompt แบบนี้เพื่อแยก answer เป็น statements
print("=" * 60)
print("TEST 1: แยก answer เป็น statements (ใช้ใน faithfulness)")
print("=" * 60)
r1 = llm.invoke([HumanMessage(content="""
Given the following answer, break it down into individual statements.
Answer: ถ้าอยากเรียนเรื่อง recursion ต้องลงวิชา คพ.102 พื้นฐานการแก้ปัญหาและการโปรแกรมคอมพิวเตอร์ (CS102 Problem Solving Basics and Computer Programming) เนื่องจากวิชานี้มีเนื้อหาเกี่ยวกับฟังก์ชันเวียนเกิด (recursive functions)
Return ONLY a JSON object like this: {"statements": ["statement 1", "statement 2"]}
""")])
print("Response:", r1.content)

# ---- Test 2: context_recall ----
# RAGAS ส่ง prompt แบบนี้เพื่อแยก ground truth เป็น statements
print("\n" + "=" * 60)
print("TEST 2: แยก ground truth เป็น statements (ใช้ใน context_recall)")
print("=" * 60)
r2 = llm.invoke([HumanMessage(content="""
Given the following ground truth, break it down into individual statements.
Ground truth: วิชาที่สอนเรื่อง sorting และ searching คือ คพ.216 โครงสร้างข้อมูลและขั้นตอนวิธี (CS216 Data Structures and Algorithms)
Return ONLY a JSON object like this: {"statements": ["statement 1", "statement 2"]}
""")])
print("Response:", r2.content)

# ---- Test 3: answer_relevancy ----
# RAGAS ส่ง prompt แบบนี้เพื่อสร้างคำถามย้อนกลับ
print("\n" + "=" * 60)
print("TEST 3: สร้างคำถามย้อนกลับจาก answer (ใช้ใน answer_relevancy)")
print("=" * 60)
r3 = llm.invoke([HumanMessage(content="""
Generate a question that the following answer is responding to.
Answer: วิชาที่สอนเรื่อง sorting และ searching คือ คพ.216 โครงสร้างข้อมูลและขั้นตอนวิธี (CS216 Data Structures and Algorithms) ซึ่งมีเนื้อหาเกี่ยวกับการวิเคราะห์ความต้องการด้านเวลาและหน่วยความจำในการค้นหา (searching) และขั้นตอนวิธีเกี่ยวกับการค้นหาและการเรียงลำดับ (sorting) รวมถึงการวิเคราะห์ความซับซ้อนของขั้นตอนวิธีต่างๆ
Return ONLY a JSON object like this: {"question": "..."}
""")])
print("Response:", r3.content)

print("\n" + "=" * 60)
print("สรุป: ถ้า model ตอบเป็นภาษาไทยหรือไม่ใช่ JSON = นั่นคือสาเหตุที่ได้ 0")
print("=" * 60)
