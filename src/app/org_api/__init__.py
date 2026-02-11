"""
Optional org API integration: fetch employee details, leave, manager.
When enabled, data is fetched per employee and used to enrich the flow (e.g. decision context).
Non-mandatory: if disabled or API fails, processing continues without org data.
"""

from app.org_api.client import OrgApiClient, get_org_client

__all__ = ["OrgApiClient", "get_org_client"]
