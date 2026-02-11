"""
sync_sharepoint_to_resources.py

Reads a folder tree from SharePoint, normalizes folder names into
{emp_id}_{emp_name}_{month}_{client}, and downloads bills into:
  resources/commute/...
  resources/meal/...

Requirements:
  pip install Office365-REST-Python-Client

Env vars:
  SHAREPOINT_SITE_URL   e.g. https://<tenant>.sharepoint.com/sites/<SiteName>
  SHAREPOINT_USERNAME   e.g. user@tenant.onmicrosoft.com
  SHAREPOINT_PASSWORD   user's password (or app password)
  SHAREPOINT_ROOT       server-relative root, e.g. /sites/<SiteName>/Shared Documents/Bills

Run from project root:
  python scripts/sync_sharepoint_to_resources.py
"""

import os
import re
from typing import List, Tuple, Optional

from office365.sharepoint.client_context import ClientContext
from office365.runtime.auth.user_credential import UserCredential

# -------------------------------------------------------------------
# CONFIG
# -------------------------------------------------------------------

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
LOCAL_BASE_DIR = os.path.join(PROJECT_ROOT, "resources")
COMMUTE_DIR = os.path.join(LOCAL_BASE_DIR, "commute")
MEAL_DIR = os.path.join(LOCAL_BASE_DIR, "meal")

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

COMMUTE_KEYWORDS = ["cab", "taxi", "commute", "ride", "uber", "ola", "transport"]
MEAL_KEYWORDS = ["meal", "meals", "food", "lunch", "dinner"]

CLIENT_KEYWORDS = {
    "tesco": "tesco",
    "amex": "amex",
    "american express": "amex",
}

# Optional: map SharePoint folder display names to emp_id (IIIPL-xxxx)
EMPLOYEE_ID_MAP = {
    # "Naveen": "IIIPL-1000",
    # "Smitha": "IIIPL-1011",
}


# -------------------------------------------------------------------
# SharePoint helpers
# -------------------------------------------------------------------

def get_ctx() -> ClientContext:
    site_url = os.environ["SHAREPOINT_SITE_URL"]
    username = os.environ["SHAREPOINT_USERNAME"]
    password = os.environ["SHAREPOINT_PASSWORD"]
    ctx = ClientContext(site_url).with_credentials(UserCredential(username, password))
    return ctx


def walk_sharepoint_folders(ctx: ClientContext, root_folder_url: str) -> List[Tuple[str, list]]:
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
# Normalization helpers
# -------------------------------------------------------------------

def detect_category(path_lower: str) -> Optional[str]:
    if any(k in path_lower for k in COMMUTE_KEYWORDS):
        return "commute"
    if any(k in path_lower for k in MEAL_KEYWORDS):
        return "meal"
    return None


def detect_month(path_lower: str) -> Optional[str]:
    for key, std in MONTH_MAP.items():
        if re.search(rf"\b{re.escape(key)}\b", path_lower):
            return std
    return None


def detect_client(path_lower: str) -> str:
    for key, val in CLIENT_KEYWORDS.items():
        if key in path_lower:
            return val
    return "unknown"


def extract_employee_from_path(path: str) -> Tuple[str, str]:
    """Extract emp_id and emp_name from folder path (employee = segment under root)."""
    parts = [p for p in path.split("/") if p]
    if len(parts) < 2:
        return "", ""
    employee_folder = parts[-2]
    if re.match(r"(?i)^iiipl-\d+_", employee_folder):
        emp_id, emp_name = employee_folder.split("_", 1)
        return emp_id, emp_name.lower()
    emp_name = employee_folder.replace(" ", "_").lower()
    emp_id = EMPLOYEE_ID_MAP.get(employee_folder, "").strip()
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
        emp_id = emp_name.upper()
    return f"{emp_id}_{emp_name}_{month}_{client}"


def download_file(ctx: ClientContext, sp_file, dest_folder: str):
    os.makedirs(dest_folder, exist_ok=True)
    local_path = os.path.join(dest_folder, sp_file.name)
    print(f"  → {sp_file.name}")
    with open(local_path, "wb") as f:
        sp_file.download(f).execute_query()


def main():
    ctx = get_ctx()
    root_folder = os.environ["SHAREPOINT_ROOT"]

    print(f"Walking SharePoint: {root_folder}")
    folder_entries = walk_sharepoint_folders(ctx, root_folder)

    for folder_url, files in folder_entries:
        if not files:
            continue
        bill_files = [
            f for f in files
            if f.name.lower().endswith((".pdf", ".png", ".jpg", ".jpeg"))
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

        dest_emp_folder = os.path.join(COMMUTE_DIR if category == "commute" else MEAL_DIR, std_folder_name)
        print(f"\n{folder_url}")
        print(f"  → {std_folder_name}")

        for sp_file in bill_files:
            download_file(ctx, sp_file, dest_emp_folder)

    print("\nDone. Check resources/commute and resources/meal.")


if __name__ == "__main__":
    main()
