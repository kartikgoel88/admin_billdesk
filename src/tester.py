import fitz  # PyMuPDF
import easyocr

# Initialize OCR engine
reader = easyocr.Reader(['en'], gpu=False)


def test_easyocr(pdf_path):
    print(f"\nTesting EasyOCR on: {pdf_path}\n")

    doc = fitz.open(pdf_path)

    for page_no, page in enumerate(doc, start=1):
        print(f"--- Page {page_no} ---")

        # Convert page to image
        pix = page.get_pixmap(dpi=220)
        img_bytes = pix.tobytes("png")

        # Save debug image
        img_file = f"debug_easy_page_{page_no}.png"
        pix.save(img_file)
        print(f"Saved: {img_file}")

        # OCR
        result = reader.readtext(img_bytes, detail=1, paragraph=True)

        # Extract text only
        text_lines = [item[1] for item in result]

        print("\nExtracted Text:")
        print("\n".join(text_lines))
        print("\n" + "="*50 + "\n")


if __name__ == "__main__":
    pdf_path = r"D:\pycharm\admin_billdesk\resources\CAB_RECEIPT_RD17506969273550314.pdf"
    test_easyocr(pdf_path)
