"""
build_curriculum_db.py
======================
สร้าง SQLite database จากไฟล์ course_info.json
ได้ 3 ตาราง:
  - courses      : ข้อมูลทุกรายวิชา (86 วิชา)
  - prerequisites: วิชาบังคับก่อน (81 edges, deduplicated)
  - study_plan   : ว่างไว้รอ --only-plan มาเติม

วิธีใช้:
  python build_curriculum_db.py
"""

import json
import sqlite3
from pathlib import Path

JSON_PATH = "test-ingest/result/course_info.json"
DB_PATH   = "curriculum.db"

# ──────────────────────────────────────────────
# 1. โหลด JSON
# ──────────────────────────────────────────────
print("โหลด JSON...")
with open(JSON_PATH, encoding="utf-8") as f:
    data: dict = json.load(f)
print(f"  พบ {len(data)} วิชา")


# ──────────────────────────────────────────────
# 2. แปลงเป็น list พร้อม clean ข้อมูล
# ──────────────────────────────────────────────
courses_rows = []
prereq_rows  = []

CREDIT_OVERRIDE = {
    "CS 303": 2, "CS 304": 2,
    "CS 403": 4, "CS 404": 4,
}

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

    # deduplicate prerequisites
    seen_prereqs = set()
    for req in info["prerequisites"]:
        if req not in seen_prereqs:
            seen_prereqs.add(req)
            prereq_rows.append({
                "course":   en_code,
                "requires": req,
            })

print(f"  courses: {len(courses_rows)} แถว")
print(f"  prerequisites: {len(prereq_rows)} edges (หลัง deduplicate)")


# ──────────────────────────────────────────────
# 3. สร้าง SQLite
# ──────────────────────────────────────────────
if Path(DB_PATH).exists():
    Path(DB_PATH).unlink()

print(f"\nสร้าง {DB_PATH}...")
with sqlite3.connect(DB_PATH) as conn:
    cur = conn.cursor()

    # ── ตาราง courses ──────────────────────────
    cur.execute("""
        CREATE TABLE courses (
            code_en     TEXT PRIMARY KEY,
            code_th     TEXT UNIQUE,
            name_en     TEXT NOT NULL,
            name_th     TEXT NOT NULL,
            credits     INTEGER NOT NULL,
            lecture     INTEGER,
            lab         INTEGER,
            self_study  INTEGER
        )
    """)
    cur.executemany("""
        INSERT INTO courses VALUES
        (:code_en, :code_th, :name_en, :name_th,
         :credits, :lecture, :lab, :self_study)
    """, courses_rows)
    print(f"  บันทึก {len(courses_rows)} วิชา → courses")

    # ── ตาราง prerequisites ────────────────────
    cur.execute("""
        CREATE TABLE prerequisites (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            course   TEXT NOT NULL REFERENCES courses(code_en),
            requires TEXT NOT NULL
        )
    """)
    cur.executemany("""
        INSERT INTO prerequisites (course, requires)
        VALUES (:course, :requires)
    """, prereq_rows)
    print(f"  บันทึก {len(prereq_rows)} edges → prerequisites")

    # ── ตาราง study_plan (ว่างไว้รอ --only-plan) ──
    cur.execute("""
        CREATE TABLE study_plan (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            code_en     TEXT REFERENCES courses(code_en),
            major       TEXT NOT NULL,
            track       TEXT NOT NULL DEFAULT 'project',
            year        INTEGER NOT NULL,
            semester    INTEGER NOT NULL,
            course_type TEXT
        )
    """)
    print("  สร้างตาราง study_plan (ว่าง — รัน --only-plan เพื่อเติม)")

    # ── Index ──────────────────────────────────
    cur.execute("CREATE INDEX idx_courses_th    ON courses(code_th)")
    cur.execute("CREATE INDEX idx_prereq_course ON prerequisites(course)")
    cur.execute("CREATE INDEX idx_prereq_req    ON prerequisites(requires)")
    cur.execute("CREATE INDEX idx_plan_major    ON study_plan(major, track, year, semester)")

    conn.commit()

print(f"\nสร้าง {DB_PATH} เสร็จแล้ว")


# ──────────────────────────────────────────────
# 4. ทดสอบ query
# ──────────────────────────────────────────────
print("\n" + "="*45)
print("ทดสอบ query")
print("="*45)

with sqlite3.connect(DB_PATH) as conn:
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    print("\nQ1: CS 271 มีกี่หน่วยกิต?")
    cur.execute("SELECT code_th, name_th, credits FROM courses WHERE code_en = ?",
                ("CS 271",))
    r = cur.fetchone()
    print(f"  {r['code_th']} | {r['name_th']} | {r['credits']} หน่วยกิต")

    print("\nQ2: คพ.251 ชื่ออะไร?")
    cur.execute("SELECT code_en, name_en, credits FROM courses WHERE code_th = ?",
                ("คพ.251",))
    r = cur.fetchone()
    print(f"  {r['code_en']} | {r['name_en']} | {r['credits']} credits")

    print("\nQ3: วิชาไหนบ้างที่ต้องผ่าน CS 271 ก่อน?")
    cur.execute("""
        SELECT p.course, c.name_th
        FROM prerequisites p
        JOIN courses c ON p.course = c.code_en
        WHERE p.requires = 'CS 271'
        ORDER BY p.course
    """)
    for r in cur.fetchall():
        print(f"  {r['course']} | {r['name_th']}")

    print("\nQ4: วิชาที่เรียนได้เลยโดยไม่ต้องผ่านวิชาอื่น?")
    cur.execute("""
        SELECT code_en, name_th, credits
        FROM courses
        WHERE code_en NOT IN (SELECT DISTINCT course FROM prerequisites)
        ORDER BY code_en
    """)
    rows = cur.fetchall()
    for r in rows:
        print(f"  {r['code_en']} | {r['name_th']} | {r['credits']}c")
    print(f"  รวม {len(rows)} วิชา")

    print("\nQ5: วิชาที่มีเงื่อนไข prerequisites มากที่สุด?")
    cur.execute("""
        SELECT p.course, c.name_th, COUNT(*) AS cnt
        FROM prerequisites p
        JOIN courses c ON p.course = c.code_en
        GROUP BY p.course
        ORDER BY cnt DESC
        LIMIT 5
    """)
    for r in cur.fetchall():
        print(f"  {r['course']} | {r['name_th']} | {r['cnt']} prerequisites")
