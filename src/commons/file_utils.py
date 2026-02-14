"""
Facade over extendible commons (io, ocr, folder).

All methods delegate to LocalFileReader/Writer, TesseractPdfExtractor, StandardFolderNameParser, LocalFolderProcessor.
To extend: use custom FileReader/FileWriter, TextExtractor, or FolderNameParser and pass them where supported.
"""

import json
import os

from commons.config import load_config
from commons.io.local import LocalFileReader, LocalFileWriter
from commons.ocr.tesseract_extractor import TesseractPdfExtractor
from commons.folder.parser import StandardFolderNameParser
from commons.folder.processor import LocalFolderProcessor
from entity.employee import Employee

# Default implementations (replace for SharePoint, different OCR, etc.)
_default_reader = LocalFileReader()
_default_writer = LocalFileWriter()
_default_extractor = TesseractPdfExtractor()
_default_parser = StandardFolderNameParser()
_default_processor = LocalFolderProcessor(text_extractor=_default_extractor)


class FileUtils:
    """Facade for file, OCR, and folder operations."""

    @staticmethod
    def get_ocr_text_from_file(pdf_name: str, pdf_path: str) -> dict:
        """Extract text from a single file. Uses default TesseractPdfExtractor."""
        return _default_extractor.extract(pdf_name, pdf_path)

    @staticmethod
    def process_folder(folder_path: str):
        """Process all bill files in folder. Uses default LocalFolderProcessor."""
        return _default_processor.process_folder(folder_path)

    @staticmethod
    def extract_info_from_foldername(folder_path: str) -> Employee:
        """Parse folder name into Employee. Uses StandardFolderNameParser."""
        return _default_parser.parse(folder_path)

    @staticmethod
    def write_json_to_file(output, file_path: str) -> None:
        """Write JSON to file. Uses default LocalFileWriter."""
        _default_writer.ensure_dir(file_path)
        data = json.loads(output) if isinstance(output, str) else output
        _default_writer.write_json(data, file_path)
        print(f"data written to {file_path}")

    @staticmethod
    def load_text_file(file_path: str) -> str | None:
        """Load text file. Uses default LocalFileReader."""
        try:
            content = _default_reader.read_text(file_path)
            if content is not None:
                print("file text loaded successfully:")
            return content
        except FileNotFoundError:
            print(f"Error: The file '{file_path}' was not found.")
            return None
        except Exception as e:
            print(f"An error occurred: {e}")
            return None

    @staticmethod
    def load_json_from_file(file_path: str):
        """Load JSON file. Uses default LocalFileReader."""
        return _default_reader.read_json(file_path)
