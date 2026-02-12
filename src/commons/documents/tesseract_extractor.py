"""PDF/image text extraction with native text + Tesseract OCR fallback."""

import cv2
import fitz
import numpy as np
import pytesseract



def _tesseract_config() -> tuple[int, str]:
    try:
        from commons.config import config
        ocr = config.get("ocr") or {}
        t = ocr.get("tesseract") or {}
        return t.get("dpi", 300), t.get("lang", "eng")
    except Exception:
        return 300, "eng"


class TesseractPdfExtractor:
    """Extract text from PDF/images; uses native text first, then OCR. Params default from config.yaml ocr.tesseract."""

    def __init__(self, dpi: int | None = None, ocr_lang: str | None = None):
        cfg_dpi, cfg_lang = _tesseract_config()
        self.dpi = dpi if dpi is not None else cfg_dpi
        self.ocr_lang = ocr_lang if ocr_lang is not None else cfg_lang

    def extract(self, file_name: str, file_path: str) -> dict[str, str]:
        doc = fitz.open(file_path)
        full_text = ""

        for page in doc:
            native_text = page.get_text("text")
            if native_text.strip():
                full_text += native_text + "\n"
                continue

            pix = page.get_pixmap(dpi=self.dpi)
            img = np.frombuffer(pix.tobytes(), dtype=np.uint8)
            img = cv2.imdecode(img, cv2.IMREAD_COLOR)
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            gray = cv2.adaptiveThreshold(
                gray, 255,
                cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                cv2.THRESH_BINARY,
                31, 2,
            )
            text_ocr = pytesseract.image_to_string(gray, lang=self.ocr_lang)
            full_text += text_ocr + "\n"

        return {file_name: full_text}
