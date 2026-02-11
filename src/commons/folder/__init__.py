"""Folder discovery and name parsing. Extend by adding new parsers or processors."""

from commons.folder.parser import FolderNameParser, StandardFolderNameParser
from commons.folder.processor import FolderProcessor, LocalFolderProcessor

__all__ = [
    "FolderNameParser",
    "StandardFolderNameParser",
    "FolderProcessor",
    "LocalFolderProcessor",
]
