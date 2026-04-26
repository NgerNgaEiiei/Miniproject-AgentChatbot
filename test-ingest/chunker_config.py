import re

# =============================================================================
# CONFIG
# =============================================================================

PDF_PATH       = "data/CSTU_BSc_2566_V4_Edit 29 มิย 2566.pdf"
START_PAGE     = 44         # หน้าเริ่มต้น OCR (คำอธิบายรายวิชา)
END_PAGE       = 84         # หน้าสุดท้าย OCR
OCR_DPI        = 300
OUT_CHUNKS     = "course_chunks.json"   # output สำหรับ RAG
OUT_INFO       = "course_info.json"     # output สำหรับ Tool
OUT_DB         = "curriculum.db"        # output SQLite (study_plan)

# path ของ tesseract.exe บน Windows
TESSERACT_EXE  = r"D:\Program Files\tesseract.exe"

# หน้าแผนการศึกษา (0-indexed) — ใช้ pdfplumber อ่านตรง ไม่ผ่าน OCR
STUDY_PLAN_PAGES = list(range(31, 43))  # หน้า 32–43 ของ PDF

# credits จริงของวิชา lab-only (JSON เก็บ credits=0)
CREDIT_OVERRIDE = {
    "CS 303": 2, "CS 304": 2,
    "CS 403": 4, "CS 404": 4,
}

# Font encoding พิเศษของ PDF ไทยนี้ (U+F7xx → Unicode Thai จริง)
# PDF นี้ใช้ font ที่ encode ตัวอักษรไทยบางตัวเป็น Unicode พิเศษ
# ทำให้ pdfplumber อ่านออกมาผิด ต้องแปลงกลับก่อน parse
FONT_MAP = {
    "\uf052": "",       "\uf06f": "",
    "\uf701": "\u0e34", # ิ
    "\uf702": "\u0e35", # ี
    "\uf703": "\u0e36", # ึ
    "\uf705": "\u0e48", # ่
    "\uf706": "\u0e49", # ้
    "\uf709": "\u0e4c", # ์
    "\uf70a": "\u0e48", # ่ (อีก font)
    "\uf70b": "\u0e49", # ้ (อีก font)
    "\uf70e": "\u0e4c", # ์ (อีก font)
    "\uf710": "\u0e31", # ั
    "\uf712": "\u0e47", # ็
    "\uf713": "\u0e4a", # ๊
}

# =============================================================================
# REGEX
# =============================================================================

# หัวข้อวิชาภาษาไทย เช่น "คพ.100   การพัฒนาเว็บ...   3 (3-0-6)"
RE_TH_HEADER = re.compile(
    r'^([ก-ฮ]{1,3}\.\s*\d{3}[ก-ฮ]?)'   # รหัสวิชา TH  เช่น คพ.100
    r'\s{2,}'                             # ช่องว่าง (tab-like จาก OCR)
    r'(.+?)'                              # ชื่อวิชาภาษาไทย
    r'\s+\d+\s+\(\d+-\d+-\d+\)',         # หน่วยกิต เช่น 3 (3-0-6)
    re.MULTILINE
)

# บรรทัด EN code เช่น "CS 100   Basic Web Development"
RE_EN_HEADER = re.compile(
    r'^([A-Z]{2,4}\s+\d{3}[A-Z]?)'      # รหัสวิชา EN  เช่น CS 100
    r'\s{2,}'                             # ช่องว่าง
    r'(.+)$',                             # ชื่อวิชาภาษาอังกฤษ
    re.MULTILINE
)

# หน่วยกิตและชั่วโมง เช่น (3-0-6)
RE_CREDITS = re.compile(r'\((\d+)-(\d+)-(\d+)\)')

# รหัสวิชา CS ที่อยู่ใน prerequisite line เช่น "CS 111", "CS216"
RE_PREREQ_CODES = re.compile(r'\bCS\s*\d{3}[A-Z]?\b')

# บรรทัดที่เป็น prerequisite (ใช้ตัดออกจาก content)
RE_PREREQ_TH      = re.compile(r'^วิชาบังคับก่อน[:：]')
RE_PREREQ_TH_CONT = re.compile(r'^(เคยศึกษา|ศึกษาพร้อมกับ|สอบได้)')
RE_PREREQ_EN      = re.compile(r'^Prerequisite\s*[:|：]', re.IGNORECASE)

# OCR garbage เช่น "a7", "a8" ที่ tesseract อ่านเลขหน้าผิด
RE_GARBAGE = re.compile(r'^[a-z]\d+$')