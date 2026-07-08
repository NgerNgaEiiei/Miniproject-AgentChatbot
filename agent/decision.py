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

def count_courses(major: str = None, course_type: str = None, no_prereq: bool = False):
    """
    นับจำนวนวิชา รองรับ filter หลายแบบ

    params:
      major       — "CIS" หรือ "ACS" (ใช้ร่วมกับ course_type)
      course_type — ประเภทวิชา เช่น "major_required", "core", "general_ed"
      no_prereq   — True = นับเฉพาะวิชาที่ไม่มี prerequisite
    """
    with _get_conn() as conn:
        cur = conn.cursor()

        # นับวิชาที่ไม่มี prerequisite
        if no_prereq:
            cur.execute("""
                SELECT COUNT(*) AS total FROM courses
                WHERE code_en NOT IN (SELECT DISTINCT course FROM prerequisites)
            """)
            return {"total_courses": cur.fetchone()["total"], "filter": "no_prerequisite"}

        # นับตาม major + course_type (จาก study_plan)
        if major or course_type:
            query  = "SELECT COUNT(DISTINCT code_en) AS total FROM study_plan WHERE 1=1"
            params = []
            if major:
                query += " AND major = ?"
                params.append(major)
            if course_type:
                query += " AND course_type = ?"
                params.append(course_type)
            cur.execute(query, params)
            result = {"total_courses": cur.fetchone()["total"]}
            if major:
                result["major"] = major
            if course_type:
                result["course_type"] = course_type
            return result

        # นับทั้งหมด (default)
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
        "code_en":      row["code_en"],
        "code_th":      row["code_th"],
        "name_en":      row["name_en"],
        "name_th":      row["name_th"],
        "credits":      row["credits"],
        "hours":        {"lecture": row["lecture"], "lab": row["lab"], "self_study": row["self_study"]},
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

    # normalize ทุก code ใน completed_courses ด้วย (รองรับ "CS111" → "CS 111")
    completed_courses = [_normalize_id(c) for c in completed_courses]
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

        # ดึง prerequisites พร้อม cond_type, min_grade และ or_group
        cur.execute("""
            SELECT p.requires, c.name_th, p.cond_type, p.min_grade,
                   COALESCE(p.or_group, -p.id) AS or_group
            FROM prerequisites p
            LEFT JOIN courses c ON p.requires = c.code_en
            WHERE p.course = ?
        """, (en_code,))
        prereqs = cur.fetchall()

    missing        = []  # ยังไม่ผ่าน (required)
    concurrent     = []  # ต้องเรียนพร้อมกัน
    required_grade = []  # ต้องผ่านด้วยเกรดที่กำหนด แต่ยังไม่ผ่าน

    # จัดกลุ่ม OR: prereqs ที่มี or_group เดียวกัน = ต้องผ่านอย่างน้อย 1 ใน group
    # or_group ที่ไม่ได้ตั้ง → ใช้ -id เป็น unique group (AND กันทุกตัว)
    or_groups = {}  # or_group_key → list of prereq dicts

    for p in prereqs:
        code      = p["requires"]
        name      = p["name_th"] or code
        cond_type = p["cond_type"]
        min_grade = p["min_grade"]
        og        = p["or_group"]

        if cond_type == "concurrent":
            concurrent.append({"code": code, "name": name})
            continue

        if cond_type == "required_grade":
            if code not in completed_courses:
                required_grade.append({"code": code, "name": name, "min_grade": min_grade})
            continue

        # required — จัดกลุ่ม OR
        if og not in or_groups:
            or_groups[og] = []
        or_groups[og].append({"code": code, "name": name})

    # ตรวจแต่ละ OR group: ถ้าไม่มีวิชาใดใน group ที่ผ่าน → missing ทั้ง group
    for og, group in or_groups.items():
        passed_any = any(item["code"] in completed_courses for item in group)
        if not passed_any:
            if len(group) == 1:
                # AND condition ปกติ — แสดงเป็น missing เดี่ยว
                missing.append(group[0])
            else:
                # OR condition — แสดงให้รู้ว่าต้องผ่านอย่างน้อย 1 ใน group
                missing.append({
                    "or_group": [item["code"] for item in group],
                    "or_names": [item["name"] for item in group],
                    "note": f"ต้องผ่านอย่างน้อย 1 วิชาใน: {', '.join(item['code'] for item in group)}",
                })

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
            # normalize เป็น en_code ก่อน
            cur.execute("SELECT code_en FROM courses WHERE code_en = ? OR code_th = ?",
                        (current, current))
            row = cur.fetchone()
            if not row:
                break
            en_code = row["code_en"]

            if en_code in path:  # ป้องกัน infinite loop
                break
            path.insert(0, en_code)

            # เอา prerequisite แรกมาต่อ
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
            # 'all' แสดงวิชาที่ทุก track ต้องเรียน (ปี 1-2)
            # ถ้าระบุ track เฉพาะ ให้แสดง track นั้น + all ด้วย
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