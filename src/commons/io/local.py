"""Local filesystem implementation of FileReader and FileWriter."""

import json
import os
from typing import Any


class LocalFileReader:
    """Read from local filesystem."""

    def read_text(self, path: str) -> str | None:
        try:
            with open(path, "r", encoding="utf-8") as f:
                return f.read()
        except FileNotFoundError:
            return None
        except Exception:
            raise

    def read_json(self, path: str) -> Any:
        if not os.path.exists(path):
            raise FileNotFoundError(f"JSON file not found: {path}")
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)


class LocalFileWriter:
    """Write to local filesystem."""

    def write_json(self, data: Any, path: str) -> None:
        if isinstance(data, str):
            data = json.loads(data)
        self.ensure_dir(path)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def ensure_dir(self, path: str) -> None:
        dirpath = os.path.dirname(path)
        if dirpath:
            os.makedirs(dirpath, exist_ok=True)
