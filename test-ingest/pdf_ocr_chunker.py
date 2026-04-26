"""
pdf_ocr_chunker.py
==================
แปลง PDF หลักสูตร → 3 ไฟล์สำหรับ Agent Chatbot

  course_chunks.json  → RAG  (เนื้อหาคำอธิบายวิชา)
  course_info.json    → Tool (credits, prerequisites)
  curriculum.db       → Tool (study_plan: ปี/เทอม/วิชาเอก)

ขั้นตอน:
  PDF (หน้า 44-84) → ภาพ → OCR → แก้ error → แยกวิชา → export JSON
  PDF (หน้า 32-43) → pdfplumber → parse study_plan → SQLite

ติดตั้ง:
  pip install pdf2image pytesseract pythainlp Pillow pdfplumber
  Windows: ติดตั้ง Tesseract จาก https://github.com/UB-Mannheim/tesseract/wiki
           (เลือกติ๊ก Thai language ด้วย)
"""

import os
import json
import platform
import logging
from pathlib import Path
import pytesseract

from chunker_config import PDF_PATH, OUT_CHUNKS, OUT_INFO, OUT_DB, TESSERACT_EXE
from chunker_ocr import pdf_to_images, images_to_text
from chunker_cleaner import fix_ocr_errors, clean_text
from chunker_parser import split_by_course, parse_course_block
from chunker_studyplan import build_study_plan

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
log = logging.getLogger(__name__)


# =============================================================================
# PIPELINE — เรียกทุก step ตามลำดับ
# =============================================================================

def run(
    pdf_path:     str  = PDF_PATH,
    raw_txt_path: str  = None,      # ถ้าระบุ → ข้าม OCR แล้วโหลดจากไฟล์นี้แทน
    out_chunks:   str  = OUT_CHUNKS,
    out_info:     str  = OUT_INFO,
    out_db:       str  = OUT_DB,    # path ของ SQLite สำหรับ study_plan
    skip_plan:    bool = False,     # --skip-plan : ข้าม STEP 7
    only_plan:    bool = False,     # --only-plan : รันแค่ STEP 7 ข้าม STEP 1-6
):
    """
    รัน pipeline ทั้งหมด

    ถ้ามี raw.txt อยู่แล้ว ใช้ --from-raw เพื่อข้าม OCR
    (OCR 41 หน้าใช้เวลาหลายนาที)
    """

    # --only-plan: ข้าม STEP 1-6 ทั้งหมด รันแค่ STEP 7
    if only_plan:
        log.info("--only-plan: รันเฉพาะ STEP 7 (study_plan)")
        n = build_study_plan(pdf_path=pdf_path, db_path=out_db)
        log.info(f"✅ {out_db} → study_plan {n} แถว")
        return

    # STEP 1–2: PDF → OCR (หรือโหลด raw text จากไฟล์)
    if raw_txt_path:
        log.info(f"โหลด raw text จาก: {raw_txt_path}")
        raw_text = Path(raw_txt_path).read_text(encoding="utf-8")
    else:
        if not Path(pdf_path).exists():
            raise FileNotFoundError(f"ไม่พบไฟล์: {pdf_path}")

        images   = pdf_to_images(pdf_path)
        raw_text = images_to_text(images)
        # บันทึก raw text ไว้สำหรับ debug และรันซ้ำโดยไม่ต้อง OCR ใหม่
        raw_path = Path(out_chunks).with_suffix(".raw.txt")
        raw_path.write_text(raw_text, encoding="utf-8")
        log.info(f"บันทึก raw text → {raw_path}")

    # STEP 3: แก้ OCR error
    fixed_text = fix_ocr_errors(raw_text)
    fixed_path = Path(out_chunks).with_suffix(".fixed.txt")
    fixed_path.write_text(fixed_text, encoding="utf-8")
    log.info(f"บันทึก fixed text → {fixed_path}")

    # STEP 4: Clean
    clean = clean_text(fixed_text)

    # STEP 5: แบ่งเป็น block ต่อวิชา
    blocks = split_by_course(clean)
    if not blocks:
        log.error("ไม่พบวิชาใดเลย — เปิด .fixed.txt ตรวจสอบ")
        return

    # STEP 6: แปลงแต่ละ block → chunk + info
    chunks, info_list = [], []
    for block in blocks:
        chunk, info = parse_course_block(block)
        chunks.append(chunk)
        info_list.append(info)

    # บันทึก course_chunks.json (RAG)
    Path(out_chunks).write_text(
        json.dumps(chunks, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    log.info(f"✅ {out_chunks} → {len(chunks)} วิชา")

    # บันทึก course_info.json (Tool) keyed by EN code
    info_map = {
        (inf["en_code"] or inf["th_code"]): inf
        for inf in info_list
    }
    Path(out_info).write_text(
        json.dumps(info_map, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    log.info(f"✅ {out_info} → {len(info_map)} วิชา")

    # STEP 7: parse study_plan จาก PDF (pdfplumber, ไม่ต้อง OCR)
    # หมายเหตุ: ต้องรัน build_curriculum_db.py ก่อน
    #           เพื่อให้ตาราง courses มีข้อมูลสำหรับแปลง th_code → en_code
    if skip_plan:
        log.info("ข้าม STEP 7 (--skip-plan)")
    else:
        try:
            n = build_study_plan(pdf_path=pdf_path, db_path=out_db)
            log.info(f"✅ {out_db} → study_plan {n} แถว")
        except Exception as e:
            log.warning(
                f"STEP 7 ล้มเหลว: {e}\n"
                f"  → รัน build_curriculum_db.py ก่อน แล้วลองใหม่"
            )

    _print_summary(chunks, info_list)


def _print_summary(chunks, info_list):
    print("\n" + "=" * 65)
    print(f"สรุป: {len(chunks)} วิชา")
    print("=" * 65)
    for chunk, info in list(zip(chunks, info_list))[:5]:
        m = chunk["metadata"]
        print(f"  {m['th_code']} / {m['en_code']}")
        print(f"  TH  : {m['th_name']}")
        print(f"  EN  : {m['en_name']}")
        print(f"  หน่วยกิต : {info['credits']} | prereq: {info['prerequisites']}")
        print(f"  content  : {len(chunk['content'])} chars, {chunk['sentence_count']} ประโยค")
        print()
    if len(chunks) > 5:
        print(f"  ... และอีก {len(chunks) - 5} วิชา")


# =============================================================================
# ENTRY POINT
# =============================================================================

if __name__ == "__main__":

    import argparse

    # ตั้งค่า Tesseract path สำหรับ Windows
    if platform.system() == "Windows":
        if not os.path.exists(TESSERACT_EXE):
            raise EnvironmentError(
                f"ไม่พบ Tesseract ที่ '{TESSERACT_EXE}'\n"
                f"ติดตั้งจาก https://github.com/UB-Mannheim/tesseract/wiki\n"
                f"หรือแก้ TESSERACT_EXE ในไฟล์ chunker_config.py"
            )
        pytesseract.pytesseract.tesseract_cmd = TESSERACT_EXE

    ap = argparse.ArgumentParser(description="แปลง PDF หลักสูตร → JSON + SQLite สำหรับ Agent Chatbot")
    ap.add_argument("--pdf",       default=PDF_PATH,   help="path ไฟล์ PDF")
    ap.add_argument("--from-raw",  default=None,        help="ข้าม OCR โดยโหลดจาก raw.txt ที่มีอยู่")
    ap.add_argument("--chunks",    default=OUT_CHUNKS,  help="output RAG json")
    ap.add_argument("--info",      default=OUT_INFO,    help="output Tool json")
    ap.add_argument("--db",        default=OUT_DB,      help="output SQLite db สำหรับ study_plan")
    ap.add_argument("--skip-plan", action="store_true", help="ข้าม STEP 7 (parse study_plan)")
    ap.add_argument("--only-plan", action="store_true", help="รันแค่ STEP 7 ข้าม STEP 1-6 ทั้งหมด")
    args = ap.parse_args()

    run(
        pdf_path     = args.pdf,
        raw_txt_path = args.from_raw,
        out_chunks   = args.chunks,
        out_info     = args.info,
        out_db       = args.db,
        skip_plan    = args.skip_plan,
        only_plan    = args.only_plan,
    )