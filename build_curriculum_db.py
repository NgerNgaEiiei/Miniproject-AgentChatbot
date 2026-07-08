"""
build_curriculum_db.py
======================
สร้าง SQLite database จากไฟล์ course_info.json + PDF (สำหรับ prerequisites)
ได้ 3 ตาราง:
  - courses      : ข้อมูลทุกรายวิชา (103 วิชา รวม GE)
  - prerequisites: วิชาบังคับก่อน พร้อม cond_type และ min_grade
  - study_plan   : ว่างไว้รอ --only-plan มาเติม

วิธีใช้:
  python build_curriculum_db.py
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

# ──────────────────────────────────────────────
# FONT ENCODING FIX
# ──────────────────────────────────────────────
FONT_MAP = {
    "\uf052": "", "\uf06f": "",
    "\uf701": "\u0e34", "\uf702": "\u0e35", "\uf703": "\u0e36",
    "\uf705": "\u0e48", "\uf706": "\u0e49", "\uf709": "\u0e4c",
    "\uf70a": "\u0e48", "\uf70b": "\u0e49", "\uf70e": "\u0e4c",
    "\uf710": "\u0e31", "\uf712": "\u0e47", "\uf713": "\u0e4a",
}

def fix_encoding(text: str) -> str:
    for k, v in FONT_MAP.items():
        text = text.replace(k, v)
    return text


# ──────────────────────────────────────────────
# TH CODE → EN CODE MAPPING
# ──────────────────────────────────────────────
TH_TO_EN = {
    "คพ.100": "CS 100", "คพ.101": "CS 101", "คพ.102": "CS 102", "คพ.103": "CS 103",
    "คพ.104": "CS 104", "คพ.111": "CS 111", "คพ.140": "CS 140", "คพ.180": "CS 180",
    "คพ.213": "CS 213", "คพ.216": "CS 216", "คพ.217": "CS 217", "คพ.221": "CS 221",
    "คพ.222": "CS 222", "คพ.223": "CS 223", "คพ.224": "CS 224", "คพ.232": "CS 232",
    "คพ.233": "CS 233", "คพ.234": "CS 234", "คพ.240": "CS 240", "คพ.241": "CS 241",
    "คพ.242": "CS 242", "คพ.246": "CS 246", "คพ.251": "CS 251", "คพ.255": "CS 255",
    "คพ.261": "CS 261", "คพ.262": "CS 262", "คพ.263": "CS 263", "คพ.264": "CS 264",
    "คพ.265": "CS 265", "คพ.271": "CS 271", "คพ.285": "CS 285", "คพ.287": "CS 287",
    "คพ.299": "CS 299", "คพ.301": "CS 301", "คพ.303": "CS 303", "คพ.304": "CS 304",
    "คพ.305": "CS 305", "คพ.310": "CS 310", "คพ.314": "CS 314", "คพ.320": "CS 320",
    "คพ.325": "CS 325", "คพ.331": "CS 331", "คพ.332": "CS 332", "คพ.335": "CS 335",
    "คพ.336": "CS 336", "คพ.337": "CS 337", "คพ.340": "CS 340", "คพ.341": "CS 341",
    "คพ.342": "CS 342", "คพ.343": "CS 343", "คพ.345": "CS 345", "คพ.346": "CS 346",
    "คพ.347": "CS 347", "คพ.351": "CS 351", "คพ.353": "CS 353", "คพ.354": "CS 354",
    "คพ.355": "CS 355", "คพ.356": "CS 356", "คพ.360": "CS 360", "คพ.361": "CS 361",
    "คพ.362": "CS 362", "คพ.363": "CS 363", "คพ.364": "CS 364", "คพ.365": "CS 365",
    "คพ.366": "CS 366", "คพ.367": "CS 367", "คพ.368": "CS 368", "คพ.370": "CS 370",
    "คพ.371": "CS 371", "คพ.372": "CS 372", "คพ.373": "CS 373", "คพ.374": "CS 374",
    "คพ.381": "CS 381", "คพ.382": "CS 382", "คพ.384": "CS 384", "คพ.385": "CS 385",
    "คพ.390": "CS 390", "คพ.403": "CS 403", "คพ.404": "CS 404", "คพ.420": "CS 420",
    "คพ.430": "CS 430", "คพ.440": "CS 440", "คพ.450": "CS 450", "คพ.480": "CS 480",
    "คพ.490": "CS 490", "สษ.295": "EL 295", "สษ.395": "EL 395",
}

# ──────────────────────────────────────────────
# 1. โหลด JSON → courses
# ──────────────────────────────────────────────
print("โหลด JSON...")
with open(JSON_PATH, encoding="utf-8") as f:
    data: dict = json.load(f)
print(f"  พบ {len(data)} วิชา")

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

print(f"  courses: {len(courses_rows)} แถว")


# ──────────────────────────────────────────────
# 2. Parse prerequisites จาก PDF โดยตรง
#    เพื่อให้ได้ cond_type และ min_grade ที่ถูกต้อง
# ──────────────────────────────────────────────
print("\nParsing prerequisites จาก PDF...")

COURSE_HEADER = re.compile(r"^([ก-ฮ]{1,3}\.\s*\d{3})\s+")  # รองรับ "คพ. 450" (มีช่องว่างหลัง .)
PREREQ_START  = re.compile(r"^วิชาบังคับก่อน[:：]\s*(.+)")
PREREQ_CONT   = re.compile(r"^(เคยศึกษา|ศึกษาพร้อมกับ|สอบได้)")
CODE_PAT      = re.compile(r"[ก-ฮ]{1,4}\.\d{3}[ก-ฮ]?")
GRADE_PAT     = re.compile(r"ไม่ต่ำกว่า(?:ระดับ)?\s*([A-D])")

course_prereqs = {}
current_course = None
in_prereq      = False
current_raw    = ""

with pdfplumber.open(PDF_PATH) as pdf:
    for i in range(COURSE_DESC_START, COURSE_DESC_END + 1):
        text = fix_encoding(pdf.pages[i].extract_text() or "")
        for line in text.split("\n"):
            line = line.strip()
            if not line:
                continue
            m = COURSE_HEADER.match(line)
            if m:
                if current_course and current_raw:
                    course_prereqs[current_course] = current_raw.strip()
                current_course = m.group(1)
                in_prereq      = False
                current_raw    = ""
                continue
            m2 = PREREQ_START.match(line)
            if m2:
                in_prereq   = True
                current_raw = m2.group(1).strip()
                continue
            if in_prereq and PREREQ_CONT.match(line):
                current_raw += " " + line
                continue
            if in_prereq:
                in_prereq = False

    if current_course and current_raw:
        course_prereqs[current_course] = current_raw.strip()


def parse_prereq_raw(th_course: str, raw: str) -> list[dict]:
    """
    แปลง raw prerequisite string → list ของ edge พร้อม cond_type และ or_group

    cond_type:
      required       — ต้องผ่านก่อน (เคยศึกษา)
      concurrent     — เรียนพร้อมกันได้ (ศึกษาพร้อมกับ)
      required_grade — ต้องผ่านด้วยเกรดที่กำหนด (สอบได้ ... ไม่ต่ำกว่า C)

    or_group:
      None — AND condition (ต้องผ่านทุกวิชาในกลุ่ม)
      1    — OR condition (ต้องผ่านอย่างน้อย 1 วิชา)
             ตรวจจากคำว่า "หรือ" ระหว่าง code ใน raw string
    """
    # normalize เผื่อ PDF พิมพ์ "คพ. 450" มีช่องว่างหลัง "."
    th_course = re.sub(r"([ก-ฮ]{1,3}\.)" + r"\s+(\d)", r"\1\2", th_course)
    en_course = TH_TO_EN.get(th_course, th_course)
    codes     = CODE_PAT.findall(raw)
    if not codes:
        return []

    grade_m   = GRADE_PAT.search(raw)
    min_grade = grade_m.group(1) if grade_m else None
    is_grade  = "สอบได้" in raw

    # ตรวจว่า raw มีคำว่า "หรือ" ระหว่าง code ไหม → OR condition
    has_or = bool(re.search(r"หรือ", raw))

    edges = []
    seen  = set()

    for code in codes:
        en_req = TH_TO_EN.get(code)
        if not en_req or en_req in seen:
            continue  # skip วิชานอกหลักสูตร หรือ duplicate
        seen.add(en_req)

        # หา segment ก่อนและหลัง code เพื่อตรวจว่าเป็น concurrent
        idx = raw.find(code)

        # segment ระหว่าง code ก่อนหน้า (หรือต้น string) ถึง code นี้
        prev_end = 0
        for prev_m in CODE_PAT.finditer(raw):
            if prev_m.start() >= idx: break
            prev_end = prev_m.end()
        segment_before = raw[prev_end:idx]

        # segment หลัง code นี้ถึง code ถัดไป (หรือท้าย string)
        next_start = len(raw)
        for next_m in CODE_PAT.finditer(raw):
            if next_m.start() > idx:
                next_start = next_m.start()
                break
        segment_after = raw[idx + len(code): next_start]

        if is_grade:
            cond_type = "required_grade"
        elif ("ศึกษาพร้อมกับ" in segment_before or "ศึกษาพร้อม" in segment_before or
              "ศึกษาพร้อมกับ" in segment_after  or "ศึกษาพร้อม" in segment_after):
            cond_type = "concurrent"
        else:
            cond_type = "required"

        # or_group: ถ้ามี "หรือ" ใน raw และ cond_type เป็น required → or_group = 1
        # (concurrent และ required_grade ไม่ใช้ or_group)
        or_group = 1 if (has_or and cond_type == "required") else None

        edges.append({
            "course":    en_course,
            "requires":  en_req,
            "cond_type": cond_type,
            "min_grade": min_grade,
            "or_group":  or_group,
        })

    return edges


prereq_rows = []
for th_code, raw in course_prereqs.items():
    prereq_rows.extend(parse_prereq_raw(th_code, raw))

print(f"  prerequisites: {len(prereq_rows)} edges")


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
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            course    TEXT NOT NULL REFERENCES courses(code_en),
            requires  TEXT NOT NULL,
            cond_type TEXT NOT NULL DEFAULT 'required',
            min_grade TEXT,
            or_group  INTEGER DEFAULT NULL
        )
    """)
    cur.executemany("""
        INSERT INTO prerequisites (course, requires, cond_type, min_grade, or_group)
        VALUES (:course, :requires, :cond_type, :min_grade, :or_group)
    """, prereq_rows)
    print(f"  บันทึก {len(prereq_rows)} edges → prerequisites")

    # ── ตาราง study_plan ───────────────────────
    cur.execute("""
        CREATE TABLE study_plan (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            code_en     TEXT REFERENCES courses(code_en),
            major       TEXT NOT NULL,
            track       TEXT NOT NULL DEFAULT 'all',
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
    cur.execute("CREATE INDEX idx_prereq_type   ON prerequisites(cond_type)")
    cur.execute("CREATE INDEX idx_plan_major    ON study_plan(major, track, year, semester)")

    conn.commit()

print(f"\nสร้าง {DB_PATH} เสร็จแล้ว")


# ──────────────────────────────────────────────
# 4. เติม study_plan จาก PDF
# ──────────────────────────────────────────────
import sys as _sys
_sys.path.insert(0, "test-ingest")
from chunker_studyplan import build_study_plan

print("\nกำลัง parse study_plan จาก PDF (หน้า 32-43)...")
import logging
logging.basicConfig(level=logging.INFO, format="  %(message)s")
_n = build_study_plan(pdf_path=PDF_PATH, db_path=DB_PATH)
print(f"  บันทึก {_n} แถว → study_plan")


# ──────────────────────────────────────────────
# 5. ทดสอบ query
# ──────────────────────────────────────────────
print("\n" + "="*50)
print("ทดสอบ query")
print("="*50)

with sqlite3.connect(DB_PATH) as conn:
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    print("\nQ1: CS 271 มีกี่หน่วยกิต?")
    cur.execute("SELECT code_th, name_th, credits FROM courses WHERE code_en = ?", ("CS 271",))
    r = cur.fetchone()
    print(f"  {r['code_th']} | {r['name_th']} | {r['credits']} หน่วยกิต")

    print("\nQ2: prerequisites ของ CS 372?")
    cur.execute("""
        SELECT p.requires, c.name_th, p.cond_type, p.min_grade
        FROM prerequisites p LEFT JOIN courses c ON p.requires = c.code_en
        WHERE p.course = 'CS 372'
    """)
    for r in cur.fetchall():
        grade = f" (ไม่ต่ำกว่า {r['min_grade']})" if r["min_grade"] else ""
        print(f"  {r['requires']} | {r['name_th']} | {r['cond_type']}{grade}")

    print("\nQ3: วิชาที่มี concurrent prerequisites?")
    cur.execute("""
        SELECT DISTINCT p.course, p.requires, p.cond_type
        FROM prerequisites p WHERE p.cond_type = 'concurrent' ORDER BY p.course
    """)
    for r in cur.fetchall():
        print(f"  {r['course']} → {r['requires']} [{r['cond_type']}]")

    print("\nQ4: วิชาที่ต้องการ min_grade?")
    cur.execute("""
        SELECT p.course, p.requires, p.min_grade
        FROM prerequisites p WHERE p.min_grade IS NOT NULL ORDER BY p.course
    """)
    for r in cur.fetchall():
        print(f"  {r['course']} ต้องผ่าน {r['requires']} ไม่ต่ำกว่า {r['min_grade']}")