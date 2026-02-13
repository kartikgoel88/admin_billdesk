"""Text extraction from documents. Extend by implementing TextExtractor."""

from commons.ocr.base import TextExtractor
from commons.ocr.tesseract_extractor import TesseractPdfExtractor, normalize_ocr_rupee_symbol

__all__ = ["TextExtractor", "TesseractPdfExtractor", "normalize_ocr_rupee_symbol"]
