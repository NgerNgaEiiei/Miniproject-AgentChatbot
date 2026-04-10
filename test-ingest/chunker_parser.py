import logging
import re
from pythainlp.tokenize import sent_tokenize as th_sent_tokenize

from chunker_config import (
    RE_TH_HEADER, RE_EN_HEADER, RE_CREDITS, 
    RE_PREREQ_EN, RE_PREREQ_CODES, 
    RE_PREREQ_TH, RE_PREREQ_TH_CONT
)

log = logging.getLogger(__name__)

def split_by_course(text: str) -> list[dict]:
    """
    ใช้ RE_TH_HEADER เป็นตัวแบ่ง
    แต่ละ header = จุดเริ่มต้นของวิชาใหม่
    คืนค่า list ของ dict ที่มี th_code, th_name, block_text
    """
    headers = list(RE_TH_HEADER.finditer(text))
    if not headers:
        log.warning("ไม่พบหัวข้อวิชาเลย — ตรวจสอบไฟล์ .fixed.txt")
        return []

    log.info(f"พบ {len(headers)} วิชา")
    blocks = []
    for i, header in enumerate(headers):
        start = header.start()
        end   = headers[i + 1].start() if i + 1 < len(headers) else len(text)

        blocks.append({
            "th_code_raw": header.group(1),
            "th_name":     header.group(2),
            "block_text":  text[start:end].strip(),
        })
    return blocks


def parse_course_block(block: dict) -> tuple[dict, dict]:
    """
    รับ block ของวิชาหนึ่ง → คืน (chunk, info)

    chunk  = ข้อมูลสำหรับ RAG  : metadata + content (คำอธิบายวิชาล้วนๆ)
    info   = ข้อมูลสำหรับ Tool : credits, hours, prerequisites
    """
    lines = block["block_text"].splitlines()

    # --- normalize รหัสวิชา TH: ตัดช่องว่างกลาง "คพ. 102" → "คพ.102" ---
    th_code = re.sub(r'\s+', '', block["th_code_raw"])
    th_name = block["th_name"].strip()

    # --- ดึง EN code และชื่อ EN จากบรรทัดที่ 2 ของ block ---
    en_code, en_name = _extract_en_header(block["block_text"])

    # --- ดึง credits และชั่วโมงจากบรรทัดแรก (TH header) ---
    credits, hours = _extract_credits(lines[0] if lines else "")

    # --- ดึง prerequisite codes จาก EN prereq line ---
    prerequisites = _extract_prerequisites(lines)

    # --- สร้าง content สำหรับ RAG ---
    content = _build_content(lines)

    # --- สร้าง output ---
    chunk = {
        "metadata": {
            "th_code": th_code,
            "en_code": en_code,
            "th_name": th_name,
            "en_name": en_name,
        },
        "content":        content,
        "sentence_count": len(th_sent_tokenize(content, engine="crfcut")),
    }

    info = {
        "th_code":       th_code,
        "en_code":       en_code,
        "th_name":       th_name,
        "en_name":       en_name,
        "credits":       credits,
        "hours":         hours,
        "prerequisites": prerequisites,
    }

    return chunk, info


def _extract_en_header(block_text: str) -> tuple[str, str]:
    """ดึง EN code และ EN name จาก block"""
    m = RE_EN_HEADER.search(block_text)
    if not m:
        return "", ""
    en_code = re.sub(r'\s+', ' ', m.group(1)).strip()
    en_name = m.group(2).strip()
    return en_code, en_name


def _extract_credits(header_line: str) -> tuple[int, dict]:
    """ดึงหน่วยกิตและชั่วโมงจาก header เช่น '3 (3-0-6)' """
    m = RE_CREDITS.search(header_line)
    if not m:
        return 0, {"lecture": 0, "lab": 0, "self_study": 0}
    lec, lab, self_ = int(m.group(1)), int(m.group(2)), int(m.group(3))
    return lec, {"lecture": lec, "lab": lab, "self_study": self_}


def _extract_prerequisites(lines: list[str]) -> list[str]:
    """ดึงรหัสวิชา prerequisite จาก EN prereq line"""
    for line in lines:
        if RE_PREREQ_EN.match(line):
            codes = RE_PREREQ_CODES.findall(line)
            # normalize: "CS216" → "CS 216"
            return [re.sub(r'([A-Z]+)(\d)', r'\1 \2', c) for c in codes]
    return []


def _build_content(lines: list[str]) -> str:
    """สร้าง content สำหรับ RAG โดยตัดบรรทัดที่ไม่ใช่คำอธิบายออก"""
    content_lines = []
    in_th_prereq = False

    for i, line in enumerate(lines):
        if i == 0:
            continue
        if RE_EN_HEADER.match(line):
            continue
        if RE_PREREQ_EN.match(line):
            continue
        if RE_PREREQ_TH.match(line):
            in_th_prereq = True
            continue
        if in_th_prereq and RE_PREREQ_TH_CONT.match(line):
            continue
        in_th_prereq = False
        if line.strip():
            content_lines.append(line.strip())

    raw_content = " ".join(content_lines)
    sentences = th_sent_tokenize(raw_content, engine="crfcut")
    return " ".join(s.strip() for s in sentences if s.strip())
