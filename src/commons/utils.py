import os

import cv2
import fitz
import numpy as np
import pytesseract

class Utils:

    @staticmethod
    def get_ocr_text_from_file(pdf_path):

        doc = fitz.open(pdf_path)
        full_text = ""

        for page_num, page in enumerate(doc):
            # Step 1 → Try native text extraction
            native_text = page.get_text("text")
            if native_text.strip():
                full_text += native_text + "\n"
                continue

            # Step 2 → OCR fallback (image based)
            pix = page.get_pixmap(dpi=300)
            img = np.frombuffer(pix.tobytes(), dtype=np.uint8)
            img = cv2.imdecode(img, cv2.IMREAD_COLOR)

            # Preprocess for accurate OCR
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            gray = cv2.adaptiveThreshold(
                gray, 255,
                cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                cv2.THRESH_BINARY,
                31, 2
            )

            text_ocr = pytesseract.image_to_string(gray, lang="eng")
            full_text += text_ocr + "\n"

        return full_text

    @staticmethod
    def process_folder(folder_path: str):
        if not os.path.isdir(folder_path):
            raise ValueError(f"Not a folder: {folder_path}")

        results = []
        for filename in os.listdir(folder_path):
            if filename.lower().endswith(".pdf"):
                pdf_path = os.path.join(folder_path, filename)
                print(f"📄 Processing: {pdf_path}")
                result = Utils.get_ocr_text_from_file(pdf_path)
                results.append(result)

        return results
