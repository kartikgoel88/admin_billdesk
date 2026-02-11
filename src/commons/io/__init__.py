"""File I/O abstractions. Extend by implementing Reader/Writer protocols."""

from commons.io.base import FileReader, FileWriter
from commons.io.local import LocalFileReader, LocalFileWriter

__all__ = ["FileReader", "FileWriter", "LocalFileReader", "LocalFileWriter"]
