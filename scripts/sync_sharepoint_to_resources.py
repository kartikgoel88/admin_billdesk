"""
sync_sharepoint_to_resources.py

Two modes:

1) SharePoint mode (default): reads folder tree from SharePoint, normalizes folder names
   into {emp_id}_{emp_name}_{month}_{client} (emp_id defaults to 0000 when not found), and downloads bills into:
     resources/commute/...
     resources/meal/...
     resources/fuel/...
   Zips are detected and unzipped into the same folder (folder name includes category and month).

2) Local mode (--local): reads from local resources (e.g. resources/ashwini/cab/, resources/ashwini/cab june/, ...),
   builds the same folder naming, and copies files into paths.processed_dir
   (e.g. resources/processed_inputs/commute/..., meal/..., fuel/...).
   Supports category subfolders with optional month in name: 'cab', 'cab june', 'meals', 'meals june'
   (month in name → distinct output folder e.g. 0000_ashwini_jun_unknown so all months are processed).
   Supports employee folder as .zip (e.g. resources/kartik.zip): extracted to temp and walked.
   Zips are copied then unzipped into the destination. The app can use --resources-dir resources/processed_inputs.

Configuration is read from src/config/config.yaml (sharepoint, paths, folder).
Env vars override and supply credentials:
  SHAREPOINT_SITE_URL   overrides sharepoint.site_url
  SHAREPOINT_ROOT       overrides sharepoint.root_folder
  SHAREPOINT_USERNAME   e.g. user@tenant.onmicrosoft.com
  SHAREPOINT_PASSWORD   user's password (or app password)

Requirements:
  pip install -e ".[sharepoint]"   # or: pip install Office365-REST-Python-Client

Run from project root:
  python scripts/sync_sharepoint_to_resources.py           # SharePoint
  python scripts/sync_sharepoint_to_resources.py --local   # local resources -> processed
"""

import argparse
import json
import os
import re
import shutil
import tempfile
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Load .env so SHAREPOINT_*, etc. are available (no dependency on commons)
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
except ImportError:
    pass

# SharePoint mode only
try:
    from office365.runtime.auth.user_credential import UserCredential
    from office365.sharepoint.client_context import ClientContext
except ImportError:
    UserCredential = None
    ClientContext = None

# -------------------------------------------------------------------
# Config loading (no dependency on commons so script runs without PYTHONPATH)
# -------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = PROJECT_ROOT / "src" / "config" / "config.yaml"


def _load_config() -> Dict[str, Any]:
    import yaml
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _config() -> Dict[str, Any]:
    if not hasattr(_config, "_cache"):
        _config._cache = _load_config()
    return _config._cache


def _paths_from_config() -> Tuple[str, str, str, str]:
    paths = _config().get("paths") or {}
    base = paths.get("resources_dir", "resources")
    base_abs = os.path.join(PROJECT_ROOT, base)
    return (
        base_abs,
        os.path.join(base_abs, "commute"),
        os.path.join(base_abs, "meal"),
        os.path.join(base_abs, "fuel"),
    )


def _processed_dir_from_config() -> str:
    paths = _config().get("paths") or {}
    out = paths.get("processed_dir", "resources/processed_inputs")
    return os.path.join(PROJECT_ROOT, out) if not os.path.isabs(out) else out


def _bill_extensions_from_config() -> Tuple[str, ...]:
    folder_cfg = _config().get("folder") or {}
    exts = folder_cfg.get("bill_extensions") or [".pdf", ".png", ".jpg", ".jpeg"]
    return tuple(exts)


def _archive_extensions() -> Tuple[str, ...]:
    """Extensions treated as archives (downloaded and unzipped); destination path has category and month in name."""
    return (".zip",)


def _sharepoint_settings() -> Dict[str, Any]:
    sp = _config().get("sharepoint") or {}
    site_url = os.environ.get("SHAREPOINT_SITE_URL", sp.get("site_url") or "")
    root_folder = os.environ.get("SHAREPOINT_ROOT", sp.get("root_folder") or "")
    return {
        "site_url": site_url,
        "root_folder": root_folder,
        "default_client": sp.get("default_client", "unknown"),
        "default_month": sp.get("default_month", "unknown"),  # for local mode when month not in path
        "employee_mapping_file": sp.get("employee_mapping_file") or "",
        "categories": sp.get("categories") or {},
        "client_keywords": sp.get("client_keywords") or {},
    }


def _category_keywords() -> Dict[str, List[str]]:
    """Map category name -> list of keywords for detection."""
    cats = _sharepoint_settings()["categories"]
    return {
        name: (c.get("keywords") or [])
        for name, c in cats.items()
    }


def _employee_id_map() -> Dict[str, str]:
    path = _sharepoint_settings()["employee_mapping_file"]
    if not path:
        return {}
    full_path = PROJECT_ROOT / path
    if not full_path.exists():
        return {}
    with open(full_path, "r", encoding="utf-8") as f:
        return json.load(f)


# Month name -> standard 3-letter (lowercase)
MONTH_MAP = {
    "jan": "jan", "january": "jan",
    "feb": "feb", "february": "feb",
    "mar": "mar", "march": "mar",
    "apr": "apr", "april": "apr",
    "may": "may", "jun": "jun", "june": "jun",
    "jul": "jul", "july": "jul",
    "aug": "aug", "august": "aug",
    "sep": "sep", "sept": "sep", "september": "sep",
    "oct": "oct", "october": "oct",
    "nov": "nov", "november": "nov",
    "dec": "dec", "december": "dec",
}

# -------------------------------------------------------------------
# SharePoint helpers
# -------------------------------------------------------------------


def get_ctx() -> "ClientContext":
    if ClientContext is None:
        raise ImportError("Office365-REST-Python-Client is required for SharePoint mode. Install with: pip install Office365-REST-Python-Client")
    site_url = os.environ.get("SHAREPOINT_SITE_URL") or _sharepoint_settings()["site_url"]
    username = os.environ.get("SHAREPOINT_USERNAME", "")
    password = os.environ.get("SHAREPOINT_PASSWORD", "")
    if not site_url or not username or not password:
        raise ValueError(
            "Set SHAREPOINT_SITE_URL (or sharepoint.site_url in config), "
            "SHAREPOINT_USERNAME, and SHAREPOINT_PASSWORD."
        )
    ctx = ClientContext(site_url).with_credentials(UserCredential(username, password))
    return ctx


def walk_sharepoint_folders(ctx: "ClientContext", root_folder_url: str) -> List[Tuple[str, list]]:
    """Recursively walk SharePoint folders. Returns list of (folder_url, [file objects])."""
    results = []

    def _walk(folder_url: str):
        folder = ctx.web.get_folder_by_server_relative_url(folder_url)
        files = folder.files
        subfolders = folder.folders
        ctx.load(files)
        ctx.load(subfolders)
        ctx.execute_query()
        results.append((folder_url, list(files)))
        for sf in subfolders:
            _walk(sf.serverRelativeUrl)

    _walk(root_folder_url)
    return results


# -------------------------------------------------------------------
# Normalization helpers (use config for categories and client)
# -------------------------------------------------------------------


def detect_category(path_lower: str) -> Optional[str]:
    keywords = _category_keywords()
    for category, kws in keywords.items():
        if any(k in path_lower for k in kws):
            return category
    return None


def detect_month(path_lower: str) -> Optional[str]:
    for key, std in MONTH_MAP.items():
        if re.search(rf"\b{re.escape(key)}\b", path_lower):
            return std
    return None


def detect_client(path_lower: str) -> str:
    client_keywords = _sharepoint_settings()["client_keywords"]
    default_client = _sharepoint_settings()["default_client"]
    for key, val in client_keywords.items():
        if key in path_lower:
            return val
    return default_client


def extract_employee_from_path(path: str) -> Tuple[str, str]:
    """Extract emp_id and emp_name from folder path (employee = segment under root)."""
    employee_map = _employee_id_map()
    parts = [p for p in path.split("/") if p]
    if len(parts) < 2:
        return "", ""
    employee_folder = parts[-2]
    if re.match(r"(?i)^iiipl-\d+_", employee_folder):
        emp_id, emp_name = employee_folder.split("_", 1)
        return emp_id, emp_name.lower()
    emp_name = employee_folder.replace(" ", "_").lower()
    emp_id = employee_map.get(employee_folder, "").strip()
    return emp_id, emp_name


def build_standard_folder_name(sp_folder_url: str, category: str) -> Optional[str]:
    """Build {emp_id}_{emp_name}_{month}_{client}. Returns None if we can't infer enough."""
    path_lower = sp_folder_url.lower()
    emp_id, emp_name = extract_employee_from_path(sp_folder_url)
    month = detect_month(path_lower)
    client = detect_client(path_lower)
    if not emp_name or not month:
        return None
    if not emp_id:
        emp_id = "0000"
    return f"{emp_id}_{emp_name}_{month}_{client}"


def download_file(ctx: "ClientContext", sp_file, dest_folder: str) -> str:
    """Download file to dest_folder. Returns path to the downloaded file."""
    os.makedirs(dest_folder, exist_ok=True)
    local_path = os.path.join(dest_folder, sp_file.name)
    print(f"  → {sp_file.name}")
    with open(local_path, "wb") as f:
        sp_file.download(f).execute_query()
    return local_path


def _is_archive(filename: str) -> bool:
    return filename.lower().endswith(_archive_extensions())


def unzip_into(zip_path: str, dest_folder: str, remove_zip: bool = True) -> None:
    """Extract zip_path into dest_folder. Optionally remove the zip after extraction."""
    with zipfile.ZipFile(zip_path, "r") as zf:
        names = zf.namelist()
        zf.extractall(dest_folder)
    print(f"    unzipped {len(names)} file(s)")
    if remove_zip:
        os.remove(zip_path)


def _category_to_local_dir(category: str) -> str:
    _, commute_dir, meal_dir, fuel_dir = _paths_from_config()
    if category == "commute":
        return commute_dir
    if category == "meal":
        return meal_dir
    if category == "fuel":
        return fuel_dir
    return os.path.join(_paths_from_config()[0], category)


# -------------------------------------------------------------------
# Local mode: read from resources, write to processed_dir
# -------------------------------------------------------------------

def _local_folder_to_category(folder_name: str) -> Optional[str]:
    """Map a local subfolder name (e.g. cab, cabs, meals) to category."""
    lower = folder_name.lower().strip()
    keywords = _category_keywords()
    for category, kws in keywords.items():
        if any(k in lower for k in kws) or lower in kws:
            return category
    return None


def _build_standard_name_for_local(
    emp_name: str,
    category: str,
    month: Optional[str] = None,
) -> str:
    """Build {emp_id}_{emp_name}_{month}_{client} for local mode. month from folder name (e.g. 'cab june') or default."""
    sp = _sharepoint_settings()
    emp_map = _employee_id_map()
    emp_id = (
        emp_map.get(emp_name) or emp_map.get(emp_name.title()) or ""
    ).strip() or "0000"
    month = (month or sp.get("default_month") or "unknown").strip().lower()
    client = sp.get("default_client") or "unknown"
    name_part = emp_name.replace(" ", "_").lower()
    return f"{emp_id}_{name_part}_{month}_{client}"


def _local_file_to_category(filename: str) -> Optional[str]:
    """Infer category from filename (e.g. cab.zip -> commute, meals.zip -> meal)."""
    stem = Path(filename).stem.lower()
    return _local_folder_to_category(stem)


def _detect_month_from_folder_name(folder_name: str) -> Optional[str]:
    """Detect month from folder name (e.g. 'cab june' -> 'jun', 'meals june' -> 'jun'). Uses MONTH_MAP."""
    path_lower = folder_name.lower().strip()
    for key, std in MONTH_MAP.items():
        if re.search(rf"\b{re.escape(key)}\b", path_lower):
            return std
    return None


def _walk_one_employee_dir(
    emp_dir: Path,
    emp_name: str,
    bill_extensions: Tuple[str, ...],
) -> List[Tuple[str, str, str, List[str], Optional[str]]]:
    """
    Collect (emp_name, category, folder_path, file_paths, month_override) from one employee dir.
    Supports subfolders like 'cab', 'cab june', 'meals', 'meals june' (month in name -> distinct output folder).
    """
    results: List[Tuple[str, str, str, List[str], Optional[str]]] = []
    sp = _sharepoint_settings()
    default_month = sp.get("default_month") or "unknown"

    # 1) Subfolders named by category (cab, cab june, meals, meals june, etc.) with bill/archive files inside
    for sub in emp_dir.iterdir():
        if not sub.is_dir():
            continue
        category = _local_folder_to_category(sub.name)
        if not category:
            continue
        month_override = _detect_month_from_folder_name(sub.name) or default_month
        files = [
            str(p) for p in sub.iterdir()
            if p.is_file() and (
                any(p.name.lower().endswith(ext) for ext in bill_extensions)
                or p.name.lower().endswith(_archive_extensions())
            )
        ]
        if files:
            results.append((emp_name, category, str(sub), files, month_override))
    # 2) Category-named files directly in employee folder (e.g. kartik/cab.zip)
    for f in emp_dir.iterdir():
        if not f.is_file() or f.name.startswith("."):
            continue
        if not (
            any(f.name.lower().endswith(ext) for ext in bill_extensions)
            or f.name.lower().endswith(_archive_extensions())
        ):
            continue
        category = _local_file_to_category(f.name)
        if not category:
            continue
        # Stem can be "cab june" etc.; detect month from filename if present
        month_override = _detect_month_from_folder_name(Path(f.name).stem) or default_month
        results.append((emp_name, category, str(emp_dir), [str(f)], month_override))
    return results


def walk_local_folders(
    resources_root: str,
    bill_extensions: Tuple[str, ...],
) -> List[Tuple[str, str, str, List[str], Optional[str]]]:
    """
    Walk resources_root (e.g. resources/). Returns (emp_name, category, folder_path, [file paths], month_override).
    Supports:
      - resources/{emp_name}/{category_folder}/files   (e.g. ashwini/cab/*.pdf, ashwini/cab june/*.pdf, meals, meals june)
      - resources/{emp_name}/{category_file}           (e.g. kartik/cab.zip at employee level)
      - resources/{emp_name}.zip                       (employee folder as zip; extracted to temp and walked)
    Month in folder name (e.g. 'cab june', 'meals june') produces a distinct output folder per month.
    """
    results: List[Tuple[str, str, str, List[str], Optional[str]]] = []
    resources_path = Path(resources_root)
    if not resources_path.is_dir():
        return results
    for emp_entry in resources_path.iterdir():
        if emp_entry.name.startswith("."):
            continue
        if emp_entry.is_dir():
            emp_name = emp_entry.name
            results.extend(_walk_one_employee_dir(emp_entry, emp_name, bill_extensions))
        elif emp_entry.is_file() and emp_entry.name.lower().endswith(_archive_extensions()):
            # 3) Employee folder as zip (e.g. resources/kartik.zip)
            emp_name = emp_entry.stem
            with tempfile.TemporaryDirectory(prefix="sync_emp_") as tmp:
                with zipfile.ZipFile(emp_entry, "r") as zf:
                    zf.extractall(tmp)
                results.extend(
                    _walk_one_employee_dir(Path(tmp), emp_name, bill_extensions)
                )
    return results


def copy_local_to_processed(
    processed_base: str,
    category: str,
    std_folder_name: str,
    file_paths: List[str],
) -> None:
    dest_dir = os.path.join(processed_base, category, std_folder_name)
    os.makedirs(dest_dir, exist_ok=True)
    for src in file_paths:
        name = os.path.basename(src)
        dest = os.path.join(dest_dir, name)
        if src != dest:
            shutil.copy2(src, dest)
            print(f"  → {name}")
        if _is_archive(name):
            unzip_into(dest, dest_dir, remove_zip=True)


def main_local() -> None:
    config = _config()
    paths_cfg = config.get("paths") or {}
    resources_dir = paths_cfg.get("resources_dir", "resources")
    resources_abs = os.path.join(PROJECT_ROOT, resources_dir) if not os.path.isabs(resources_dir) else resources_dir
    processed_dir = _processed_dir_from_config()
    bill_extensions = _bill_extensions_from_config()

    print(f"Local mode: reading from {resources_abs}")
    print(f"Writing to processed dir: {processed_dir}")

    entries = walk_local_folders(resources_abs, bill_extensions)
    if not entries:
        print("No bill folders found under resources (expected: resources/<emp_name>/<cab|meals|...>/files).")
        return

    for emp_name, category, folder_path, file_paths, month_override in entries:
        std_name = _build_standard_name_for_local(emp_name, category, month=month_override)
        print(f"\n{folder_path}")
        print(f"  → {std_name}")
        copy_local_to_processed(processed_dir, category, std_name, file_paths)

    print(f"\nDone. Run the app with: --resources-dir {os.path.relpath(processed_dir, PROJECT_ROOT)}")


def main():
    config = _config()
    sp = _sharepoint_settings()
    root_folder = sp["root_folder"]
    if not root_folder:
        raise ValueError(
            "SharePoint root folder is required. Set one of:\n"
            "  • src/config/config.yaml → sharepoint.root_folder (e.g. /sites/YourSite/Shared Documents/Bills)\n"
            "  • Environment: SHAREPOINT_ROOT=<server-relative-path>"
        )

    ctx = get_ctx()
    bill_extensions = _bill_extensions_from_config()
    archive_exts = _archive_extensions()

    print(f"Walking SharePoint: {root_folder}")
    folder_entries = walk_sharepoint_folders(ctx, root_folder)

    for folder_url, files in folder_entries:
        if not files:
            continue
        bill_files = [
            f for f in files
            if f.name.lower().endswith(bill_extensions) or f.name.lower().endswith(archive_exts)
        ]
        if not bill_files:
            continue

        path_lower = folder_url.lower()
        category = detect_category(path_lower)
        if not category:
            print(f"Skipping (unknown category): {folder_url}")
            continue

        std_folder_name = build_standard_folder_name(folder_url, category)
        if not std_folder_name:
            print(f"Skipping (cannot build standard name): {folder_url}")
            continue

        dest_base = _category_to_local_dir(category)
        dest_emp_folder = os.path.join(dest_base, std_folder_name)
        print(f"\n{folder_url}")
        print(f"  → {std_folder_name}  (category and month in folder name)")

        for sp_file in bill_files:
            local_path = download_file(ctx, sp_file, dest_emp_folder)
            if _is_archive(sp_file.name):
                unzip_into(local_path, dest_emp_folder, remove_zip=True)

    resources_dir = (config.get("paths") or {}).get("resources_dir", "resources")
    print(f"\nDone. Check {resources_dir}/commute, {resources_dir}/meal, {resources_dir}/fuel.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Sync bills from SharePoint or from local resources into processed folder.",
    )
    parser.add_argument(
        "--local",
        action="store_true",
        help="Local mode: read from paths.resources_dir, write to paths.processed_dir (app can use --resources-dir <processed_dir>).",
    )
    args = parser.parse_args()
    if args.local:
        main_local()
    else:
        main()
