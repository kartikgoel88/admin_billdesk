import os
import fitz
import easyocr
import json
from groq import Groq


#############################################
# 1. OCR Engine (EasyOCR – Windows Friendly)
#############################################

reader = easyocr.Reader(['en'], gpu=False)


def extract_text_from_pdf(pdf_path: str):
    doc = fitz.open(pdf_path)
    all_text = []

    for page in doc:
        pix = page.get_pixmap(dpi=220)
        img_bytes = pix.tobytes("png")

        # OCR
        result = reader.readtext(img_bytes, detail=1, paragraph=True)
        text_lines = [item[1] for item in result]
        all_text.append("\n".join(text_lines))

    return "\n\n".join(all_text).strip()


#############################################
# 2. LLM – Field Extraction (Groq)
#############################################

def extract_fields_with_groq(text: str):
    client = Groq()

    prompt = f"""
Extract ride receipt fields from the OCR text.

Return ONLY JSON with this structure:

{{
  "provider": null,
  "ride_id": null,
  "date": null,
  "time": null,
  "total_amount": null,
  "currency": null,
  "pickup_address": null,
  "dropoff_address": null,
  "vehicle_number": null
}}

OCR Text:
---------------------
{text}
---------------------
"""

    resp = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[
            {"role": "system", "content": "Return ONLY valid JSON."},
            {"role": "user", "content": prompt}
        ],
        temperature=0
    )

    output = resp.choices[0].message.content
    cleaned = output[output.find("{"):output.rfind("}") + 1]
    return json.loads(cleaned)


#############################################
# 3. Process a single PDF
#############################################

def process_single_pdf(pdf_path: str):
    text = extract_text_from_pdf(pdf_path)
    if not text or len(text) < 5:
        return {"file": pdf_path, "error": "Empty OCR output"}

    fields = extract_fields_with_groq(text)

    return {
        "file": pdf_path,
        "ocr_text": text,
        "extracted_fields": fields
    }


#############################################
# 4. Process an entire folder
#############################################

def process_folder(folder_path: str):
    if not os.path.isdir(folder_path):
        raise ValueError(f"Not a folder: {folder_path}")

    results = []
    for filename in os.listdir(folder_path):
        if filename.lower().endswith(".pdf"):
            pdf_path = os.path.join(folder_path, filename)
            print(f"📄 Processing: {pdf_path}")
            result = process_single_pdf(pdf_path)
            results.append(result)

    return results


#############################################
# 5. CLI Entry Point
#############################################

if __name__ == "__main__":

    folder_path = "D:/pycharm/admin_billdesk/resources"
    output = process_folder(folder_path)

    # Specify the file path where you want to save the JSON data
    file_path = "output.json"

    # Open the file in write mode ('w') and use json.dump()
    with open(file_path, 'w') as json_file:
        json.dump(output, json_file, indent=4)  # indent for pretty-printing
