# Run 2 — Root Cause Analysis

> **Trace**: `019d9ff7-20f8-78a1-a49d-38d10218491c`  
> **Run 2 span**: `019d9ff7-3256-78c0-879f-2e748b73e1c8` (LLM)  
> **Tool 1 span**: `019d9ff7-468f-7df1-bb17-72fd2bf2fdf4` (get_table_schema)  
> **Tool 2 span**: `019d9ff7-471d-7950-bd2a-4858b6fe29f6` (build_sql_query)  
> **Tool 3 span**: `019d9ff7-4748-70e1-a5a5-7c581e730a7b` (run_sql_query)  
> **Model**: `mistral-medium-2508`  
> **Analysed**: 2026-04-18

---

## 1. What Run 2 Does

Run 2 is the LLM's **first SQL attempt**. It arrives with 5 input messages:

| # | Role | Content |
|---|---|---|
| 0 | System | Security Advisory assistant prompt |
| 1 | Human | Conversation history context |
| 2 | Human | "Can you list the high severity advisories?" |
| 3 | AI | *(tool_call: `get_table_schema` — run 1's output)* |
| 4 | Tool | Schema response (57,805 chars) — tables, relationships, notes |

No prior errors. Run 2 is operating on the schema alone.

---

## 2. Tool Call Chain

### LLM Output → `mcp_build_sql_by_domain`

Run 2 produces a single tool call to `mcp_build_sql_by_domain`:

```json
{
  "domain": "security_advisory",
  "target_table_alias": "assets",
  "columns": [
    "bulletins.psirt_id", "bulletins.advisory_id", "bulletins.severity_level_name",
    "bulletins.headline_name", "bulletins.cvss_score", "bulletins.publish_date"
  ],
  "filters": [
    { "column": "assets.serial_number", "operator": "=", "value": "SIM651871" },
    { "column": "bulletins.severity_level_name", "operator": "=", "value": "High" }
  ],
  "join_specs": [
    { "join_type": "INNER", "table": "psirts",   "on_left": "assets.serial_number", "on_right": "psirts.serial_number" },
    { "join_type": "INNER", "table": "bulletins", "on_left": "psirts.psirt_id",      "on_right": "bulletins.psirt_id" }
  ]
}
```

The LLM uses **short aliases** (`psirts`, `bulletins`) in both `table` and `on_left`/`on_right`. This is the correct pattern.

`mcp_build_sql_by_domain` is a wrapper — it does not call Trino directly. It internally triggers three sequential MCP tool calls:

### Tool 1 — `get_table_schema`

Called internally by `mcp_build_sql_by_domain` to resolve the primary table name for the given domain. Returns successfully with tables, relationships, and notes.

### Tool 2 — `build_sql_query`

Receives the join specs with short aliases and performs **alias resolution** via `_get_table_alias_map()`:

| Short alias | Resolves to |
|---|---|
| `psirts` | `postgresql.public.cvi_psirts_view_1__3__7` |
| `bulletins` | `postgresql.public.pas_psirt_bulletins_view_1__3__1` |

It also auto-sets `table_alias = "assets"` for the FROM table and auto-qualifies unqualified `on_left` columns. The generated SQL:

```sql
SELECT bulletins.psirt_id, bulletins.advisory_id, bulletins.severity_level_name,
       bulletins.headline_name, bulletins.cvss_score, bulletins.publish_date
FROM postgresql.public.cvi_assets_view_1__3__5 AS assets
INNER JOIN postgresql.public.cvi_psirts_view_1__3__7 AS psirts
        ON assets.serial_number = psirts.serial_number
INNER JOIN postgresql.public.pas_psirt_bulletins_view_1__3__1 AS bulletins
        ON psirts.psirt_id = bulletins.psirt_id
WHERE (assets.serial_number = 'SIM651871')
  AND (bulletins.severity_level_name = 'High')
```

`build_sql_query` returns **successfully** (`isError: false`). The SQL is syntactically and semantically correct.

### Tool 3 — `run_sql_query` (Trino)

Receives the SQL above and returns:

```json
{
  "error": true,
  "message": "The data query could not be completed. Please check the query parameters and try again.",
  "rows": [],
  "row_count": 0,
  "columns": [],
  "truncated": false
}
```

Notable: the MCP transport level succeeds (`isError: false` on the span) — the tool executed and returned a response. The `"error": true` is an **application-level error payload** from the Trino client, not a tool failure.

---

## 3. Code Validation

The following was validated against the actual agent code at
`security-advisory-ai-api/src/openapi_server/impl/security_assessment_agent_impl.py`.

### `mcp_build_sql_by_domain` — how the Trino result is returned to the LLM

After `build_sql_query` succeeds and generates SQL, the wrapper executes it (lines ~458–560):

```python
exec_result = await trino_mcp_client.call_tool(trino_tool_name, exec_args)
# ...
result_str = _stringify_mcp_result(exec_result)   # ← converts to string
try:
    parsed = json.loads(result_str)
    if isinstance(parsed, dict) and isinstance(parsed.get("rows"), list):
        # row truncation / count logic ...
except (json.JSONDecodeError, TypeError):
    pass
return result_str                                  # ← returned to LLM as-is
```

**There is no check on `parsed.get("error")` before returning.** The Trino error payload:

```json
{"error": true, "message": "The data query could not be completed...", "rows": [], "row_count": 0}
```

— passes through `_stringify_mcp_result`, falls through the `rows` list check (empty list → no truncation), and is returned verbatim to the LLM. The agent code never inspects `"error": true`.

### `_stringify_mcp_result` — what it does with Trino errors

```python
def _stringify_mcp_result(result: object) -> str:
    if isinstance(result, dict):
        if result.get("isError"):          # ← checks MCP transport-level isError
            return "MCP error result: " + json.dumps(result)
        content = result.get("content")    # ← uses content[] text if present
        if isinstance(content, list): ...
        structured = result.get("structuredContent")
        if structured is not None:
            return json.dumps(structured)  # ← falls through to structuredContent
    return json.dumps(result)
```

For the Trino error response, `isError` on the MCP span is `false` (the tool call itself succeeded at transport level). The function reaches `structuredContent`, which contains the `{"error": true, ...}` dict, and serialises it as JSON. That JSON — including the generic error message — is what the LLM sees.

### `join_specs` passthrough — confirmed

In `mcp_build_sql_by_domain`, `join_specs` from the LLM is passed directly as `build_args["joins"]` with no transformation:

```python
if join_specs:
    build_args["joins"] = join_specs
```

This confirms that the short alias values (`psirts`, `bulletins`) in the LLM's tool call reach `build_sql_query` unchanged, where `_get_table_alias_map()` resolves them to FQNs — consistent with trace observation.

---

## 4. Root Cause

### What is observable

- The SQL is correct — correct tables, correct join columns, correct filter values, correct alias structure.
- `build_sql_query` passed all validation and generated valid SQL.
- The error originates entirely within `run_sql_query` / `trino_client.py`.
- The trace contains only the generic message — **no Trino error code, no exception type, no SQL fragment** is surfaced.

### What `_sanitized_error_message()` does

`trino_mcp/trino_client.py` catches the Trino exception and maps it:

```python
def _sanitized_error_message(exc: Exception) -> str:
    exc_str = str(exc)
    if "COLUMN_NOT_FOUND"    in exc_str: return "Query failed: one or more column names are invalid. ..."
    if "TABLE_NOT_FOUND"     in exc_str: return "Query failed: a referenced table does not exist. ..."
    if "SYNTAX_ERROR"        in exc_str: return "Query failed: SQL syntax error. ..."
    if "TYPE_MISMATCH"       in exc_str: return "Query failed: data type mismatch. ..."
    # ← any other error code lands here
    return "The data query could not be completed. Please check the query parameters and try again."
```

The real exception is **logged server-side** but not returned to the agent. The generic fallback is returned instead.

### What the real Trino error is

Cannot be determined from the trace alone. The real exception is only in the `trino_mcp` container logs. Given that the SQL is correct, the candidates are:

| Candidate | Reasoning |
|---|---|
| `PERMISSION_DENIED` | Most likely — the service account may lack SELECT on one or more of the three views being joined (`cvi_assets_view`, `cvi_psirts_view`, `pas_psirt_bulletins_view`) simultaneously |
| `AUTHORIZATION_ERROR` | Same class — JWT `assessments-security_service_account` may not have cross-view join rights |
| Trino view resolution failure | A view definition dependency (e.g. underlying table missing or renamed) failing at plan time |

**To confirm**: search `trino_mcp` container logs for `otel_trace_id = a03d131a6bc0b31d7607aac17455f797` or thread `933db8c4-e37c-46ce-b0b2-4bb0e61cda2b` around `2026-04-18T09:41`.

---

## 5. Consequence for Run 3

The generic error returned to the LLM contains zero diagnostic information:

> *"The data query could not be completed. Please check the query parameters and try again."*

The LLM cannot determine whether the failure was a permission issue, a column error, or a structural problem. It concludes "something was wrong with the query construction" and on run 3 tries to be more explicit — switching from short aliases (`psirts.serial_number`) to fully-qualified references (`postgresql.public.cvi_psirts_view_1__3__7.serial_number`). This triggers the FM-1 validation failure documented in `run3-analysis.md`.

Run 2's generic error is the **upstream trigger** for run 3's Pydantic failure.

---

## 6. Fix Options

### Option A — Extend `_sanitized_error_message()` to recognize additional Trino error codes

Add `PERMISSION_DENIED`, `AUTHORIZATION_ERROR`, and any other codes observed in logs:

```python
# trino_mcp/trino_client.py
if "PERMISSION_DENIED" in exc_str or "AUTHORIZATION_ERROR" in exc_str:
    return "Query failed: access denied. The current user may not have permission to access this data."
```

This alone does not fix the underlying access problem, but gives the LLM a correct error category. The system prompt can then instruct the agent to stop retrying access errors and return a meaningful user message instead of exhausting its retry budget.

### Option B — Investigate and fix the actual Trino access issue

Check `trino_mcp` server logs to identify the real exception. If it is a `PERMISSION_DENIED` or RLS policy issue, update the Trino access policy to permit the service account to join these three views.

### Option C — Return `error_code` separately in the Trino MCP response

Modify the response payload to include the Trino error code alongside the sanitized message:

```json
{
  "error": true,
  "error_code": "PERMISSION_DENIED",
  "message": "Query failed: access denied. ...",
  "rows": []
}
```

This allows the agent wrapper to detect non-retriable error categories and skip the retry loop immediately rather than retrying 4 times.

### Recommended order

| Priority | Action |
|---|---|
| **1** | Check Trino logs — identify the real error code |
| **2** | Fix the root access issue if it is PERMISSION_DENIED / policy (Option B) |
| **3** | Add the error code to `_sanitized_error_message()` regardless (Option A) — prevents silent failures for future unrecognized codes |
| **4** | Consider Option C to make the agent retry-aware for access errors |

---

## 7. Relationship to Run 3

```
Run 2: correct SQL → Trino fails
  └── _sanitized_error_message() returns generic text
  └── LLM receives: "The data query could not be completed."
          │
          ▼  (no diagnostic info → LLM assumes query construction was wrong)
Run 3: LLM over-qualifies ON columns with FQN
  └── _validate_identifier() rejects 4-component identifier
  └── 3 Pydantic validation errors
  (see run3-analysis.md)
```

Fixing run 2's error (Options A/B/C) would prevent run 3's failure mode from ever being triggered.

---

## 8. Key Files

| File | Relevant symbol |
|---|---|
| `trino_mcp/trino_client.py` | `_sanitized_error_message()` — swallows the real Trino error |
| `text2sql_mcp/server.py` | `_get_table_alias_map()` — correctly resolves short aliases in run 2 |
| `security-advisory-ai-api/.../security_assessment_agent_impl.py` | `mcp_build_sql_by_domain` retry logic — exhausts retries due to generic error |
