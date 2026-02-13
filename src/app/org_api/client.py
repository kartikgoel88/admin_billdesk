"""
Org API client: fetch employee details, leave, manager from your org API.
Configure in config.yaml under org_api. When disabled or on failure, returns None so flow continues.
"""

import os
from typing import Any, Dict, Optional

import requests

from commons.config import config


def _org_api_config() -> Dict[str, Any]:
    return config.get("org_api") or {}


def is_org_api_enabled() -> bool:
    return bool(_org_api_config().get("enabled", False))


def get_org_client() -> Optional["OrgApiClient"]:
    """Return an OrgApiClient if org_api is enabled and configured, else None."""
    if not is_org_api_enabled():
        return None
    cfg = _org_api_config()
    base_url = (cfg.get("base_url") or "").rstrip("/")
    if not base_url:
        return None
    return OrgApiClient(
        base_url=base_url,
        api_key=os.getenv(cfg.get("api_key_env") or "ORG_API_KEY"),
        timeout=cfg.get("timeout", 10),
        employee_path_template=cfg.get("employee_path") or "/api/employees/{employee_id}",
    )


class OrgApiClient:
    """
    Fetches employee details (and optionally leave, manager) from an org API.
    Expects GET {base_url}/api/employees/{employee_id} (or your path) returning JSON.
    Normalizes response to a standard shape for use in the app.
    """

    def __init__(
        self,
        base_url: str,
        api_key: Optional[str] = None,
        timeout: int = 10,
        employee_path_template: str = "/api/employees/{employee_id}",
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self.employee_path_template = employee_path_template

    def _headers(self) -> Dict[str, str]:
        h = {"Accept": "application/json", "Content-Type": "application/json"}
        if self.api_key:
            h["Authorization"] = f"Bearer {self.api_key}"
        return h

    def get_employee_details(self, employee_id: str) -> Optional[Dict[str, Any]]:
        """
        Fetch employee details for the given employee_id.
        Returns a normalized dict with keys: employee_id, name, email, manager, leave_details.
        Returns None on any failure (network, non-2xx, missing config); caller can continue without.
        """
        if not employee_id:
            return None
        path = self.employee_path_template.format(employee_id=employee_id)
        url = f"{self.base_url}{path}"
        try:
            resp = requests.get(url, headers=self._headers(), timeout=self.timeout)
            resp.raise_for_status()
            data = resp.json()
            return self._normalize_employee_response(data, employee_id)
        except Exception:
            return None

    def _normalize_employee_response(self, data: Dict[str, Any], employee_id: str) -> Dict[str, Any]:
        """
        Map API response to a standard shape. Override or extend for your API.
        Expected from API (any of): id, employee_id, name, full_name, email, manager, manager_id, manager_name,
        leave_balance, leave_taken, leave_details, department.
        """
        if not isinstance(data, dict):
            return {"employee_id": employee_id}
        # Common key mappings (API-specific keys -> standard keys)
        name = data.get("name") or data.get("full_name") or data.get("employee_name") or ""
        email = data.get("email") or data.get("email_id") or ""
        manager = data.get("manager")
        if isinstance(manager, dict):
            manager_info = {
                "id": manager.get("id") or manager.get("employee_id"),
                "name": manager.get("name") or manager.get("full_name"),
                "email": manager.get("email"),
            }
        else:
            manager_info = {
                "id": data.get("manager_id"),
                "name": data.get("manager_name"),
                "email": data.get("manager_email"),
            }
        leave = data.get("leave_details") or data.get("leave")
        if leave is None:
            leave = {
                "balance_days": data.get("leave_balance"),
                "taken_this_month": data.get("leave_taken"),
            }
        return {
            "employee_id": data.get("id") or data.get("employee_id") or employee_id,
            "name": name,
            "email": email,
            "department": data.get("department") or data.get("dept"),
            "manager": manager_info,
            "leave_details": leave,
        }
