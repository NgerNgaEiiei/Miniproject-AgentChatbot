import logging
from pdf2image import convert_from_path
import pytesseract
from chunker_config import START_PAGE, END_PAGE, OCR_DPI

log = logging.getLogger(__name__)

def pdf_to_images(pdf_path: str) -> list:
    """แปลงหน้า START_PAGE–END_PAGE เป็น PIL Image ทีละหน้า"""
    log.info(f"แปลง PDF หน้า {START_PAGE}–{END_PAGE} → ภาพ (DPI={OCR_DPI})")
    images = convert_from_path(
        pdf_path,
        dpi=OCR_DPI,
        first_page=START_PAGE,
        last_page=END_PAGE,
        fmt="jpeg",
        thread_count=4,
    )
    log.info(f"ได้ {len(images)} หน้า")
    return images

def images_to_text(images: list) -> str:
    """รัน OCR ทุกหน้า แล้วรวมเป็น string เดียว"""
    pages = []
    for i, img in enumerate(images, 1):
        log.info(f"  OCR หน้า {i}/{len(images)}")
        text = pytesseract.image_to_string(img, lang="tha+eng", config="--oem 3 --psm 6")
        pages.append(text)
    return "\n".join(pages)
