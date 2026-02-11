"""Protocol for text extraction. Implement for different engines (Tesseract, cloud OCR, etc.)."""

from typing import Protocol


class TextExtractor(Protocol):
    """Extract text from a document (PDF/image) at the given path."""

    def extract(self, file_name: str, file_path: str) -> dict[str, str]:
        """
        Return a single-key dict: {file_name: extracted_text}.
        Implementations may use native PDF text, OCR, or both.
        """
        ...
