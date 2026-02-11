# Org API (optional)

Fetches employee details, leave details, and manager from your organisation API. **Not mandatory**: if disabled or the API fails, the rest of the flow runs as usual.

## Config (`config.yaml`)

```yaml
org_api:
  enabled: true
  base_url: "https://your-org-api.example.com"
  api_key_env: ORG_API_KEY    # optional; set env for Bearer token
  employee_path: "/api/employees/{employee_id}"
  timeout: 10
```

- **enabled**: Set to `true` to call the API. Default `false`.
- **base_url**: Base URL of the org API (no trailing slash).
- **api_key_env**: Env var name for API key (e.g. `export ORG_API_KEY="..."`). Omit or leave unset for no auth.
- **employee_path**: Path template. `{employee_id}` is replaced with the employee id (e.g. IIIPL-1234).
- **timeout**: Request timeout in seconds.

## Expected API contract

- **Method**: GET `{base_url}{employee_path}` e.g. `GET https://your-org-api.example.com/api/employees/IIIPL-1234`
- **Response**: JSON. The client normalises common keys into:
  - `employee_id`, `name`, `email`, `department`
  - `manager`: `{ id, name, email }`
  - `leave_details`: e.g. `{ balance_days, taken_this_month }` or your structure

If your API uses different field names, extend `OrgApiClient._normalize_employee_response()` or subclass the client.

## How it’s used

1. For each employee (from folder discovery), the app optionally calls the org API with that employee’s id.
2. Results are stored in `employee_org_data` (key = `emp_id_emp_name`) and passed into the decision engine so the LLM can use manager/leave info when making approve/reject decisions.
3. The same data is written to `decisions/{model}/employee_org_data.json` for downstream use or reporting.

No org data is used for extraction or validation; it’s only for enrichment and decision context.
