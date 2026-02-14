"""
Extendible commons package.

Subpackages:
  config   - ConfigProvider, YamlConfigProvider; add env/vault by implementing ConfigProvider
  io       - FileReader, FileWriter; add SharePoint/S3 by implementing these
  ocr      - TextExtractor; add cloud OCR by implementing it
  folder   - FolderNameParser, FolderProcessor; add new naming schemes via new parsers

Public API: FileUtils, config, load_config, Constants; config_pkg, io_pkg, ocr_pkg, folder_pkg for extension.
"""

from commons.file_utils import FileUtils
from commons.config import config, load_config
from commons.constants import Constants

# Extendible modules (use these to plug in new implementations)
from commons import config as config_pkg
from commons import io as io_pkg
from commons import ocr as ocr_pkg
from commons import folder as folder_pkg

__all__ = [
    "FileUtils",
    "config",
    "load_config",
    "Constants",
    "config_pkg",
    "io_pkg",
    "ocr_pkg",
    "folder_pkg",
]
