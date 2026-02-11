"""Text extraction from documents. Extend by implementing TextExtractor."""

from commons.ocr.base import TextExtractor
from commons.ocr.tesseract_extractor import TesseractPdfExtractor

__all__ = ["TextExtractor", "TesseractPdfExtractor"]
