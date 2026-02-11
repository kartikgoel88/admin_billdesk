import json
import os
from dataclasses import dataclass

import cv2
import fitz
import numpy as np
import pytesseract

from entity.employee import Employee


class FileUtils:

    @staticmethod
    def get_ocr_text_from_file(pdf_name,pdf_path):

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

        return {pdf_name:full_text}

    @staticmethod
    def process_folder(folder_path: str):
        if not os.path.isdir(folder_path):
            raise ValueError(f"Not a folder: {folder_path}")

        results = []
        for filename in os.listdir(folder_path):
            if filename.lower().endswith((".pdf", ".png", ".jpg")):
                pdf_path = os.path.join(folder_path, filename)
                pdf_name = os.path.splitext(filename)[0]
                print(pdf_name)
                print(f"📄 Processing: {pdf_path}")
                result = FileUtils.get_ocr_text_from_file(pdf_name,pdf_path)
                results.append(result)

        return results

    @staticmethod
    def extract_info_from_foldername(folder_path: str):
        if not os.path.isdir(folder_path):
            raise ValueError(f"Not a folder: {folder_path}")
        folder_path = os.path.abspath(folder_path)
        folder_name = os.path.basename(folder_path)
        emp = folder_name.split("_")
        emp_id = emp[0]
        emp_name = emp[1]
        emp_month = emp[2]
        client = emp[3]
        return Employee(emp_id, emp_name, emp_month, client)

    @staticmethod
    def write_json_to_file(output, file_path):
        data = json.loads(output)
        os.makedirs(os.path.dirname(file_path), exist_ok=True)

        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        print(f"data written to {file_path}")


    @staticmethod
    def load_text_file(file_path):
        try:
            with open(file_path, 'r') as file:
                file_txt = file.read()
            print("file text loaded successfully:")
            return file_txt
        except FileNotFoundError:
            print(f"Error: The file '{file_path}' was not found.")
            return None
        except Exception as e:
            print(f"An error occurred: {e}")
            return None

    @staticmethod
    def load_json_from_file(file_path):
        """
        Loads a JSON file and returns the parsed Python dictionary.
        Raises FileNotFoundError if the file doesn't exist.
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"JSON file not found: {file_path}")

        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
