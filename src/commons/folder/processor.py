"""Process folders (list bill files, run OCR). Extend by swapping parser or text extractor."""

import os
from typing import List

from commons.ocr.base import TextExtractor
from commons.folder.parser import FolderNameParser, StandardFolderNameParser
from commons.ocr.tesseract_extractor import TesseractPdfExtractor

# Fallback when config not available
DEFAULT_BILL_EXTENSIONS = (".pdf", ".png", ".jpg", ".jpeg")


def _bill_extensions_from_config() -> tuple[str, ...]:
    try:
        from commons.config_reader import config
        exts = config.get("folder") or {}
        lst = exts.get("bill_extensions")
        if lst is not None:
            return tuple(lst)
    except Exception:
        pass
    return DEFAULT_BILL_EXTENSIONS


class FolderProcessor:
    """Protocol: process a folder and return list of {filename: text} dicts."""

    def process_folder(self, folder_path: str) -> List[dict]:
        ...


class LocalFolderProcessor:
    """
    List local folder, run text extraction on each bill file.
    Inject a different TextExtractor or FolderNameParser to extend.
    extensions default from config.yaml folder.bill_extensions.
    """

    def __init__(
        self,
        text_extractor: TextExtractor | None = None,
        extensions: tuple[str, ...] | None = None,
        verbose: bool = True,
    ):
        self.text_extractor = text_extractor or TesseractPdfExtractor()
        self.extensions = extensions if extensions is not None else _bill_extensions_from_config()
        self.verbose = verbose

    def process_folder(self, folder_path: str) -> List[dict]:
        if not os.path.isdir(folder_path):
            raise ValueError(f"Not a folder: {folder_path}")

        results = []
        for filename in os.listdir(folder_path):
            if not filename.lower().endswith(self.extensions):
                continue
            file_path = os.path.join(folder_path, filename)
            file_name = os.path.splitext(filename)[0]
            if self.verbose:
                print(file_name)
                print(f"📄 Processing: {file_path}")
            result = self.text_extractor.extract(file_name, file_path)
            results.append(result)
        return results
