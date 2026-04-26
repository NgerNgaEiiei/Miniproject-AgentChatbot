"""
chunker_studyplan.py
====================
Parse แผนการศึกษา (study_plan) จาก PDF โดยตรง ด้วย pdfplumber
(หน้า 32-43 มี text layer อ่านได้เลย ไม่ต้อง OCR)

เรียกจาก pdf_ocr_chunker.py ใน STEP 7

ติดตั้งเพิ่ม:
    pip install pdfplumber
"""

import re
import sqlite3
import logging
from pathlib import Path

import pdfplumber

from chunker_config import PDF_PATH, OUT_DB, STUDY_PLAN_PAGES, FONT_MAP

log = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────
# 1. FONT ENCODING FIX
#    PDF นี้ใช้ font encoding พิเศษ U+F7xx แทน Unicode Thai จริง
#    ต้องแปลงกลับก่อน parse ไม่งั้นภาษาไทยจะผิดเพี้ยน
# ──────────────────────────────────────────────────────────────

def _fix_encoding(text: str) -> str:
    for wrong, correct in FONT_MAP.items():
        text = text.replace(wrong, correct)
    return text


# ──────────────────────────────────────────────────────────────
# 2. REGEX PATTERNS
# ──────────────────────────────────────────────────────────────

_MAJOR_LINE = re.compile(r"วิชาเอก\s+(.+)")
_YEAR_LINE  = re.compile(r"ปีการศึกษาท\s*ี่\s*(\d)")
_SEM_LINE   = re.compile(r"ภาคเรียนที่\s+(\d)")
_COURSE_ROW = re.compile(r"^([ก-ฮ]{1,3}\.\d{3})\s+")
_MULTI_CODE = re.compile(r"[ก-ฮ]{1,3}\.\d{3}")  # ตรวจบรรทัด minor table

_SKIP_PAT = re.compile(
    r"^(รวม|หมายเหตุ|สำหรับนักศึกษาที่จะ|หรือ|วิชาโท|วิชาเลือก|"
    r"\d+\.\d+\.\d+|แสดงแผน|4\.3)"
)

_MAJOR_MAP = {
    "วิทยาการคอมพิวเตอร์และสารสนเทศ": "CIS",
    "คอมพิวเตอร์ประยุกต์":             "ACS",
}


def _normalize_type(raw: str) -> str:
    """แปลง course_type ที่อาจถูกตัดหรือมี whitespace แปลกๆ"""
    r = re.sub(r"\s+", "", raw)
    if re.search(r"บังคับเอก|ับเอก|คับเอก|เอก$", r):        return "major_required"
    if re.search(r"บังคับร่วม|ับร่วม|คับร่วม|่วม\)?$", r):  return "common_required"
    if re.search(r"วิชาแกน|แกน$", r):                         return "core"
    if re.search(r"ศึกษาทั่วไป|ั่วไป$|ทั่วไป", r):          return "general_ed"
    if re.search(r"บังคับนอกสาขา|นอกสาขา", r):               return "outside_required"
    if re.search(r"วิชาเฉพาะ|เฉพาะ", r):                     return "specific"
    return raw


# ──────────────────────────────────────────────────────────────
# 3. CORE PARSER
# ──────────────────────────────────────────────────────────────

def parse_study_plan(pdf_path: str, th_to_en: dict) -> list[dict]:
    """
    อ่านหน้า STUDY_PLAN_PAGES จาก PDF แล้ว parse เป็น list ของ dict

    th_to_en : {th_code → en_code}  โหลดจาก DB เพื่อแปลง key
    """
    records       = []
    seen          = set()
    current_major = ""
    current_track = "project"
    current_year  = 0
    current_sem   = 0
    in_minor      = False

    with pdfplumber.open(pdf_path) as pdf:
        for page_idx in STUDY_PLAN_PAGES:
            if page_idx >= len(pdf.pages):
                continue
            raw  = pdf.pages[page_idx].extract_text() or ""
            text = _fix_encoding(raw)

            for line in text.split("\n"):
                line = line.strip()
                if not line:
                    continue

                # ── major ─────────────────────────────────────
                m = _MAJOR_LINE.match(line)
                if m:
                    for th, short in _MAJOR_MAP.items():
                        if th in m.group(1):
                            current_major = short
                            current_track = "project"
                            break
                    in_minor = False
                    continue

                # ── year (ตรวจ track จากวงเล็บในบรรทัดเดียวกัน) ──
                m = _YEAR_LINE.search(line)
                if m:
                    current_year = int(m.group(1))
                    if "สหกิจ" in line:
                        current_track = "coop"
                    elif "หัวข้อพิเศษ" in line:
                        current_track = "project"
                    in_minor = False
                    continue

                # ── semester ──────────────────────────────────
                m = _SEM_LINE.search(line)
                if m:
                    current_sem = int(m.group(1))
                    in_minor = False
                    continue

                # ── เข้า/ออก minor block (ตารางวิชาโท) ────────
                if "จะต้องลงทะเบียนวิชาต่อไปนี้" in line:
                    in_minor = True
                    continue
                if in_minor:
                    if "ภาคเรียนที่" in line or "ปีการศึกษาที่" in line:
                        in_minor = False  # ออก minor แล้ว process ต่อด้านล่าง
                    else:
                        continue

                # ── skip บรรทัดขยะ ────────────────────────────
                if _SKIP_PAT.match(line):
                    continue

                # ── course row ────────────────────────────────
                m = _COURSE_ROW.match(line)
                if not (m and current_major and current_year and current_sem):
                    continue

                # บรรทัด minor table มี code มากกว่า 1 ตัว → skip
                if len(_MULTI_CODE.findall(line)) > 1:
                    continue

                # course row จริงต้องลงท้ายด้วยตัวเลข (หน่วยกิต)
                # ถ้าไม่มี = บรรทัด wrap หรือหลุดจาก minor block → skip
                if not re.search(r"\d\s*$", line):
                    continue

                th_code = m.group(1)
                en_code = th_to_en.get(th_code, th_code)  # GE → ใช้ th_code แทน

                # ดึง course_type จากท้ายบรรทัด (ตัดเลขหน่วยกิตออกก่อน)
                rest     = re.sub(r"\s+\d+\s*$", "", line[m.end():].strip())
                tokens   = rest.split()
                raw_type = " ".join(tokens[-3:]) if len(tokens) >= 3 else rest
                ctype    = _normalize_type(raw_type)

                # ถ้า normalize แล้วยังไม่ใช่ค่ามาตรฐาน และเป็นวิชา GE → general_ed
                valid_types = {"major_required", "common_required", "core",
                               "general_ed", "outside_required", "specific"}
                if ctype not in valid_types:
                    ge_prefixes = ("มธ.", "สษ.", "ส.", "ค.")
                    if any(th_code.startswith(p) for p in ge_prefixes):
                        ctype = "general_ed"

                # ปี 1-2 ยังไม่แยก track → ใช้ 'all' แทน
                track = "all" if current_year <= 2 else current_track

                key = (en_code, current_major, track, current_year, current_sem)
                if key not in seen:
                    seen.add(key)
                    records.append({
                        "code_en":     en_code,
                        "major":       current_major,
                        "track":       track,
                        "year":        current_year,
                        "semester":    current_sem,
                        "course_type": ctype,
                    })

    return records


# ──────────────────────────────────────────────────────────────
# 4. DB WRITER
# ──────────────────────────────────────────────────────────────

def _ensure_tables(cur: sqlite3.Cursor) -> None:
    """สร้างตาราง courses และ study_plan ถ้ายังไม่มี"""
    cur.execute("""
        CREATE TABLE IF NOT EXISTS courses (
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
    cur.execute("""
        CREATE TABLE IF NOT EXISTS study_plan (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            code_en     TEXT REFERENCES courses(code_en),
            major       TEXT NOT NULL,
            track       TEXT NOT NULL DEFAULT 'project',
            year        INTEGER NOT NULL,
            semester    INTEGER NOT NULL,
            course_type TEXT
        )
    """)
    # รองรับกรณีที่ตาราง study_plan สร้างไว้ก่อนแล้วยังไม่มีคอลัมน์ track
    try:
        cur.execute("ALTER TABLE study_plan ADD COLUMN track TEXT NOT NULL DEFAULT 'project'")
    except Exception:
        pass  # มีอยู่แล้ว ข้ามได้
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_plan_major_year
        ON study_plan(major, track, year, semester)
    """)


def _load_th_to_en(cur: sqlite3.Cursor) -> dict:
    """โหลด mapping th_code → en_code จากตาราง courses"""
    cur.execute("SELECT code_th, code_en FROM courses")
    return {th: en for th, en in cur.fetchall()}


def build_study_plan(
    pdf_path: str = PDF_PATH,
    db_path:  str = OUT_DB,
) -> int:
    """
    Entry point หลัก: parse PDF แล้วเขียน study_plan ลง SQLite
    คืนจำนวนแถวที่บันทึก
    """
    if not Path(pdf_path).exists():
        raise FileNotFoundError(f"ไม่พบ PDF: {pdf_path}")

    log.info(f"parse study_plan จาก {pdf_path} (หน้า {STUDY_PLAN_PAGES})")

    with sqlite3.connect(db_path) as conn:
        cur = conn.cursor()
        _ensure_tables(cur)

        th_to_en = _load_th_to_en(cur)
        if not th_to_en:
            log.warning(
                "ตาราง courses ว่างเปล่า — ควรรัน build_curriculum_db.py ก่อน\n"
                "study_plan จะใช้ th_code เป็น code_en แทน"
            )

        records = parse_study_plan(pdf_path, th_to_en)

        # ล้างข้อมูลเก่าแล้วใส่ใหม่
        cur.execute("DELETE FROM study_plan")
        cur.executemany("""
            INSERT INTO study_plan
                (code_en, major, track, year, semester, course_type)
            VALUES
                (:code_en, :major, :track, :year, :semester, :course_type)
        """, records)

        conn.commit()

    n = len(records)
    log.info(f"✅ study_plan → {n} แถว (db: {db_path})")
    return n