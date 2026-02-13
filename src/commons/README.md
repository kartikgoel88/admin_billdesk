# Commons (extendible)

Existing callers keep using `FileUtils`, `commons.config` (config, load_config), and `Constants` unchanged.

## Extending

### Config
- **Protocol:** `ConfigProvider` in `commons.config.loader` (implement `load() -> dict`).
- **Default:** `YamlConfigProvider` (reads `config/config.yaml`).
- **Example:** Add `EnvConfigProvider` or a vault-backed provider and use `get_config(provider)`.

### File I/O
- **Protocols:** `FileReader` (`read_text`, `read_json`), `FileWriter` (`write_json`, `ensure_dir`) in `commons.io.base`.
- **Default:** `LocalFileReader` / `LocalFileWriter` in `commons.io.local`.
- **Example:** Implement `SharePointFileReader` and pass it to code that accepts a `FileReader`.

### OCR / text extraction
- **Protocol:** `TextExtractor` in `commons.ocr.base` (implement `extract(file_name, file_path) -> dict`).
- **Default:** `TesseractPdfExtractor` in `commons.ocr.tesseract_extractor`.
- **Example:** Add a cloud OCR extractor and pass it to `LocalFolderProcessor(text_extractor=...)`.

### Folder naming and processing
- **Parser protocol:** `FolderNameParser` in `commons.folder.parser` (implement `parse(folder_path) -> Employee`).
- **Default:** `StandardFolderNameParser` (expects `{emp_id}_{emp_name}_{month}_{client}`).
- **Example:** Add `SharePointFolderNameParser` for a different naming scheme.
- **Processor:** `LocalFolderProcessor` in `commons.folder.processor` accepts a custom `TextExtractor` (and can be extended to accept a custom parser for discovery).
