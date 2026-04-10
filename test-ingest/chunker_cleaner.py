import re
from chunker_config import RE_GARBAGE

def fix_ocr_errors(text: str) -> str:
    """
    แก้ความผิดพลาดของ OCR ที่พบในเอกสารนี้:

    ปัญหา 1: Tesseract อ่าน "คพ." เป็น "AW." หรือ "aw."
             เพราะตัวอักษร ค+พ หน้าตาคล้าย AW ในฟอนต์ TH Sarabun
    ปัญหา 2: Tesseract อ่าน "CS" เป็น "65"
             เพราะ C≈6, S≈5 เมื่อ resolution ไม่พอ
    """
    fixed_lines = []
    for line in text.splitlines():
        line = line.strip()

        # แก้ "AW.xxx" หรือ "aw.xxx" ที่ต้นบรรทัด → "คพ.xxx"
        line = re.sub(r'^(AW|aw|Aw)\s*\.', 'คพ.', line)

        # แก้ "65 xxx" ที่ต้นบรรทัด → "CS xxx"  (EN code line)
        line = re.sub(r'^65\s+(\d{3})', r'CS \1', line)

        # แก้ "aw." ที่อยู่กลางบรรทัด → "คพ."  (เช่น ใน prerequisite)
        line = re.sub(r'\b(AW|aw|Aw)\.', 'คพ.', line)

        fixed_lines.append(line)

    return "\n".join(fixed_lines)


def clean_text(text: str) -> str:
    """
    ลบสิ่งที่ไม่ต้องการออก:
    - เลขหน้าโดดๆ เช่น "44", "45"
    - OCR garbage เช่น "a7", "a8"
    - บรรทัดว่างที่ติดกันเกิน 2 บรรทัด
    """
    cleaned = []
    for line in text.splitlines():
        s = line.strip()
        if not s:
            continue
        if re.fullmatch(r'\d{1,3}', s):    # เลขหน้า
            continue
        if RE_GARBAGE.match(s):             # OCR garbage
            continue
        cleaned.append(s)

    result = "\n".join(cleaned)
    result = re.sub(r'\n{3,}', '\n\n', result)  # ลด blank line ซ้ำ
    return result
