> **Agent:** Security Advisory | **Repo:** [`CXEPI/risk-app`](https://github.com/CXEPI/risk-app)

# CXP-29107 — Analysis: Security Advisory Agent Query Failures

> **Trace**: `019d9ff7-20f8-78a1-a49d-38d10218491c` (cx-iq-nprd · DEV--Security)  
> **Question**: "Can you list the high severity advisories?"  
> **Context filters**: `assetId: SIM651871`, `checkId: 989`  
> **Model**: `mistral-medium-2508`  
> **Final user-facing answer**: "I wasn't able to retrieve the list of high severity advisories for the device with serial number SIM651871. Could you try rephrasing your request?"  
> **Analysed**: 2026-04-18

---

## 1. Executive Summary

Two independent issues caused the Security Advisory agent to fail completely on this query.

| # | Severity | Issue | Layer |
|---|---|---|---|
| 1 | **High** | Trino returns an unrecognized exception type → agent receives a generic, non-actionable error message on every attempt | `trino_mcp/trino_client.py` |
| 2 | **Medium** | LLM uses 4-component fully-qualified column name in `JoinSpec.on_right`/`on_left` → Pydantic rejects it with 3 validation errors | `text2sql_mcp/server.py` |
| 3 | **Low** | `mcp_build_sql_by_domain` docstring does not clarify that join ON columns must use alias names, not full catalog paths | `security_assessment_agent_impl.py` |

Issue 1 is the **primary blocker** — even the correctly-structured SQL queries (calls 1 and 3) and the manually-written fallback SQL all returned the same error. The agent had no way to recover regardless of how well it structured the query.

---

## 2. Trace Walk-through

### 2.1 Chronology

| Step | Span | What happened |
|---|---|---|
| 1 | `mcp_get_table_schema` | Schema fetched for `security_advisory` domain |
| 2 | **`mcp_build_sql_by_domain` call 1** (019d9ff7-468d) | Valid join aliases → SQL generated correctly → Trino fails with generic error |
| 3 | **`mcp_build_sql_by_domain` call 2** (019d9ff7-620a) | LLM uses 4-component FQN in ON columns → **3 Pydantic validation errors** |
| 4 | **`mcp_build_sql_by_domain` call 3** (019d9ff7-7166) | LLM drops to unqualified column names → SQL is **ambiguous** (no table qualification on ON right-hand sides) → Trino fails with generic error |
| 5 | **`mcp_execute_sql`** (019d9ff7-85ec) | LLM writes SQL manually with `DISTINCT` and correct joins → Trino still fails with generic error |
| 6 | Final LLM response | Agent gives up, tells user to rephrase |

---

## 3. Issue 1 — Trino Generic Error (Primary)

### 3.1 What happens

Every SQL execution attempt — including **semantically correct queries** — returns:

```json
{
  "error": true,
  "message": "The data query could not be completed. Please check the query parameters and try again.",
  "rows": [],
  "row_count": 0
}
```

### 3.2 Root cause

`trino_mcp/trino_client.py:_sanitized_error_message()` maps known Trino exception codes to actionable messages, but falls through to a **generic fallback for any unrecognized code**:

```python
def _sanitized_error_message(exc: Exception) -> str:
    exc_str = str(exc)
    if "COLUMN_NOT_FOUND" in exc_str:
        return "Query failed: one or more column names are invalid. ..."
    if "TABLE_NOT_FOUND" in exc_str:
        return "Query failed: a referenced table does not exist. ..."
    if "SYNTAX_ERROR" in exc_str:
        return "Query failed: SQL syntax error. ..."
    if "TYPE_MISMATCH" in exc_str:
        return "Query failed: data type mismatch. ..."
    # ← all other errors land here, including PERMISSION_DENIED
    return (
        "The data query could not be completed. "
        "Please check the query parameters and try again."
    )
```

The actual Trino exception is logged server-side (`logger.error("[trino_exec] query failed: %s | sql=%s", exc, ...)`) but **never surfaced to the agent**.

### 3.3 Likely actual Trino error

The SQL generated on call 1 is syntactically and semantically correct:

```sql
SELECT bulletins.psirt_id, bulletins.advisory_id, bulletins.severity_level_name,
       bulletins.headline_name, bulletins.cvss_score, bulletins.publish_date
FROM postgresql.public.cvi_assets_view_1__3__5 AS assets
INNER JOIN postgresql.public.cvi_psirts_view_1__3__7 AS psirts
       ON assets.serial_number = psirts.serial_number
INNER JOIN postgresql.public.pas_psirt_bulletins_view_1__3__1 AS bulletins
       ON psirts.psirt_id = bulletins.psirt_id
WHERE (assets.serial_number = 'SIM651871') AND (bulletins.severity_level_name = 'High')
```

Since this query also fails, the error is **not a query correctness problem**. Most likely candidates:

| Candidate | Evidence |
|---|---|
| `PERMISSION_DENIED` / Row-Level Security | Joining across three views with the invoker's account token may exceed the RLS policy for this account |
| `AUTHORIZATION_ERROR` | The `x_authz` JWT belongs to `assessments-security_service_account` + `Ruby Networks-Dev` initiator — this account may not have access to the cross-view join |
| Transient infrastructure issue | Consistent across 4 independent calls in rapid succession — less likely to be transient |
| `severity_level_name` case sensitivity | Check actual data values: are they `"High"`, `"HIGH"`, or `"high"`? This would produce empty rows, not an error |

**To confirm**: search Trino MCP container logs for trace `019d9ff7` or timestamp `2026-04-18T09:41`.

### 3.4 Effect on agent

The generic message gives the LLM **zero information** for self-correction:
- It retried 4 times with structurally different queries, all failing identically
- It correctly applied the retry logic from the system prompt but could never determine why the query failed
- With 18,684 prompt tokens by the final iteration, it exhausted its context budget before recovering

### 3.5 Fix proposals

**Fix 1A — Extend the recognized Trino error code list** *(low risk)*  
Add `PERMISSION_DENIED`, `AUTHORIZATION_ERROR`, and `INSUFFICIENT_RESOURCES` to the mapping so they produce actionable messages:

```python
# trino_mcp/trino_client.py
if "PERMISSION_DENIED" in exc_str or "AUTHORIZATION_ERROR" in exc_str:
    return (
        "Query failed: access denied. The current user may not have "
        "permission to access this data. Contact your administrator."
    )
```

This alone won't enable self-correction (access errors can't be self-corrected by the LLM), but it surfaces the correct failure category so the system prompt can instruct the agent to stop retrying and give a meaningful user response.

**Fix 1B — Return the Trino error code separately** *(medium risk)*  
Modify the Trino MCP response payload to include an `error_code` field alongside the sanitized `message`:

```json
{
  "error": true,
  "error_code": "PERMISSION_DENIED",
  "message": "Query failed: access denied. ...",
  "rows": []
}
```

This allows the agent wrapper (`mcp_build_sql_by_domain`) to detect non-retriable errors and skip the retry loop immediately.

**Fix 1C — Investigate and fix the actual Trino access issue** *(required)*  
Check the Trino MCP server logs for the real exception. If the issue is RLS policy for the `assessments-security` service account joining `cvi_assets_view`, `cvi_psirts_view`, and `pas_psirt_bulletins_view` simultaneously, update the Trino policy to permit this join pattern.

---

## 4. Issue 2 — JoinSpec Identifier Regex Rejects 4-Component Column References

### 4.1 What happens

On the second `mcp_build_sql_by_domain` call, the LLM — after receiving an unhelpful error and re-reading the schema — uses the **fully-qualified Trino catalog name** as the table qualifier in `on_right`/`on_left`:

```python
# LLM call 2 join_specs (from trace):
join_specs = [
    {
        "join_type": "INNER",
        "table": "postgresql.public.cvi_psirts_view_1__3__7",
        "on_left": "assets.serial_number",
        "on_right": "postgresql.public.cvi_psirts_view_1__3__7.serial_number"  # 4 components
    },
    {
        "join_type": "INNER",
        "table": "postgresql.public.pas_psirt_bulletins_view_1__3__1",
        "on_left": "postgresql.public.cvi_psirts_view_1__3__7.psirt_id",        # 4 components
        "on_right": "postgresql.public.pas_psirt_bulletins_view_1__3__1.psirt_id"  # 4 components
    }
]
```

### 4.2 Root cause

This is a **two-layer root cause**:

**Layer 1 — Schema exposes FQNs alongside short aliases (upstream trigger)**

`get_table_schema("security_advisory")` returns a `relationships` array where each entry includes **both** a short alias (`from_table`/`to_table`) and a fully-qualified Trino catalog path (`from_table_ref`/`to_table_ref`):

```json
{
  "from_table": "psirts",
  "from_table_ref": "postgresql.public.cvi_psirts_view_1__3__7",
  "to_table": "bulletins",
  "to_table_ref": "postgresql.public.pas_psirt_bulletins_view_1__3__1"
}
```

The schema provides no instruction indicating that `from_table_ref`/`to_table_ref` must **not** be used as column qualifiers in ON clauses. When the LLM is unsure after a failed attempt it non-deterministically selects `from_table_ref` as the table qualifier, appends `.column_name`, and produces a 4-component identifier like `postgresql.public.cvi_psirts_view_1__3__7.serial_number`.

**Layer 2 — `_validate_identifier` regex rejects 4-component identifiers (downstream blocker)**

`JoinSpec.on_left`/`on_right` fields are validated via:

```python
_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*){0,2}$")
```

The `{0,2}` suffix allows at most **2 additional dot-separated components** after the first identifier — a maximum of 3 components total (e.g., `catalog.schema.table`). Appending `.column_name` to a 3-component FQN produces 4 components, which this regex does not match. `_validate_identifier()` raises `ValueError`, which Pydantic surfaces as a validation error on each failing field.

### 4.3 Exact Pydantic errors from trace

```
Error executing tool build_sql_query: 3 validation errors for build_sql_queryArguments
joins.0.on_right
  Value error, Invalid join column
  'postgresql.public.cvi_psirts_view_1__3__7.serial_number'.
  Must be a plain SQL identifier (letters, digits, underscores;
  optionally schema-qualified with dots).
joins.1.on_left
  Value error, Invalid join column
  'postgresql.public.cvi_psirts_view_1__3__7.psirt_id'.
  ...
joins.1.on_right
  Value error, Invalid join column
  'postgresql.public.pas_psirt_bulletins_view_1__3__1.psirt_id'.
  ...
```

### 4.4 Fix proposals

**Fix 2A — Extend identifier regex to 4 components** *(low risk)*  
`catalog.schema.table.column` is a valid Trino construct and the builder should accept it in ON clauses:

```python
# text2sql_mcp/server.py
_IDENTIFIER_RE = re.compile(
    r"^[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*){0,3}$"
    # was {0,2}, now {0,3} to accept catalog.schema.table.column
)
```

This is the most minimal fix. The SQL MCP server would pass the fully-qualified reference through to `build_sql`, which generates `ON ... = postgresql.public.cvi_psirts_view_1__3__7.serial_number` — valid Trino SQL.

**Fix 2B — Fix the docstring to prevent over-qualification** *(preferred as documentation fix)*  
Add explicit guidance to the `mcp_build_sql_by_domain` docstring that `on_left`/`on_right` must use the **short alias** (as defined in `join_specs[].table`), not the fully-qualified table name:

```python
# security_assessment_agent_impl.py — in the mcp_build_sql_by_domain docstring
# Add to the join_specs description:
"""
IMPORTANT: In on_left and on_right, always use the short alias from
`join_specs[].table` (e.g. 'psirts'), NOT the fully-qualified catalog name.
Valid:   on_right="psirts.serial_number"
Invalid: on_right="postgresql.public.cvi_psirts_view_1__3__7.serial_number"
"""
```

Both fixes are complementary. Fix 2A prevents the validation failure; Fix 2B prevents the LLM from generating bad input in the first place.

---

## 5. Issue 3 — Ambiguous JOIN ON Columns (Call 3)

### 5.1 What happens

After the validation failure on call 2, the LLM over-corrects by **dropping the table qualifier entirely** from `on_right`:

```python
# Call 3 join_specs:
{"on_left": "serial_number", "on_right": "serial_number"}   # both unqualified
{"on_left": "psirts.psirt_id", "on_right": "psirt_id"}      # right side unqualified
```

This passes Pydantic validation but generates ambiguous SQL:

```sql
INNER JOIN ... AS psirts ON assets.serial_number = serial_number
--                                                 ^ which table?
```

Trino would normally reject this with `AMBIGUOUS_NAME`. However, in this trace, it returns the generic error (Issue 1), so this ambiguity was masked.

### 5.2 Fix proposal

**Fix 3A — Validate that ON columns are table-qualified when a JOIN alias is defined**  
Add a cross-field validator to `JoinSpec` that warns if `on_right` is unqualified when a join alias is present (but allow — do not block — since Trino resolves some cases):

Alternatively, the same docstring fix from Fix 2B covers this: by showing the correct `alias.column` pattern explicitly, the LLM learns to qualify both sides.

---

## 6. Recommended Fix Priority

| Priority | Fix | File | Impact |
|---|---|---|---|
| **P0** | Investigate actual Trino error in server logs — likely PERMISSION_DENIED | Infrastructure / Trino policy | Unblocks all SQL queries |
| **P1** | Extend `_sanitized_error_message()` to recognize PERMISSION_DENIED and similar codes (Fix 1A) | `trino_mcp/trino_client.py` | Agent gets correct error category, can stop retrying |
| **P2** | Extend identifier regex to 4 components (Fix 2A) | `text2sql_mcp/server.py` | Eliminates the 3-validation-error failure mode |
| **P3** | Add docstring guidance on ON column qualification (Fix 2B) | `security_assessment_agent_impl.py` | Prevents LLM from generating over/under-qualified references |

---

## 7. Key Files

| File | Role |
|---|---|
| `security-advisory-ai-api/src/openapi_server/impl/security_assessment_agent_impl.py` | Agent tool wrapper — `mcp_build_sql_by_domain` |
| `text2sql_mcp/server.py` | SQL builder MCP — `build_sql_query`, Pydantic models, `_IDENTIFIER_RE` |
| `trino_mcp/trino_client.py` | Trino executor — `run_query`, `_sanitized_error_message` |
| `security-advisory-ai-api/src/openapi_server/prompts/security_assessment_v1_mistral.py` | System prompt with retry logic |
