"""Protocols for file I/O. Implement these to add SharePoint, S3, etc."""

from typing import Any, Protocol


class FileReader(Protocol):
    """Read text or JSON from a source (local path, URL, etc.)."""

    def read_text(self, path: str) -> str | None:
        ...

    def read_json(self, path: str) -> Any:
        ...


class FileWriter(Protocol):
    """Write text or JSON to a destination."""

    def write_json(self, data: Any, path: str) -> None:
        ...

    def ensure_dir(self, path: str) -> None:
        ...
