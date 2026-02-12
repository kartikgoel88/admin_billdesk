"""
Document processing: base protocols, OCR, folder parsing, and facade.

Modules:
  base               - TextExtractor, FolderNameParser, FolderProcessor protocols
  tesseract_extractor - TesseractPdfExtractor (default OCR)
  parser             - StandardFolderNameParser
  processor          - LocalFolderProcessor
  facade             - FileUtils (backward-compatible API)
"""

from commons.documents.base import TextExtractor, FolderNameParser, FolderProcessor
from commons.documents.tesseract_extractor import TesseractPdfExtractor
from commons.documents.parser import StandardFolderNameParser
from commons.documents.processor import LocalFolderProcessor
from commons.documents.facade import FileUtils

__all__ = [
    "TextExtractor",
    "FolderNameParser",
    "FolderProcessor",
    "TesseractPdfExtractor",
    "StandardFolderNameParser",
    "LocalFolderProcessor",
    "FileUtils",
]
