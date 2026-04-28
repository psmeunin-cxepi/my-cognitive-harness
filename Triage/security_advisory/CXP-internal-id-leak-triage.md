> **Agent:** Security Advisory
> **Repo:** [`CXEPI/risk-app`](https://github.com/CXEPI/risk-app)
> **Jira:** _to be created_

# Triage: Agent Exposes Internal `psirt_id` as "Advisory ID" to User

**Trace:** `019dce32-9830-76d3-84a9-3b0a358ef60b`  
**Workspace:** `cx-iq-nprd`  
**Agent:** Security Assessment AI Agent  
**Model:** `mistral-medium-2508`

---

## Problem Statement

User asks: **"How many assets are impacted?"** while viewing advisory page with `checkId = 2789`.

Agent responds: **"37 assets are impacted by the advisory with ID **2789** (either vulnerable or potentially vulnerable)."**

The count (37) is correct. The problem is the agent references **"advisory with ID 2789"** — this is the internal `psirt_id` (an integer database key for the advisory check run on the customer's network). It has no meaning to the user. The real user-facing advisory identifier is `advisory_id` (e.g. `cisco-sa-xxxxx`), stored in the `bulletins` table.

---

## Trace Walkthrough

### Run 1 — LLM → `mcp_get_table_schema` (span 23 → 22)
LLM correctly calls schema lookup for `security_advisory` domain. Schema returned successfully with all three tables (assets, psirts, bulletins).

### Runs 2–4 — LLM → `mcp_build_sql_by_domain` (spans 19→18, 15→14, 11→10)
LLM attempts to build the query three times with identical arguments:
```json
{
  "columns": ["COUNT(DISTINCT assets.serial_number) AS impacted_assets_count"],
  "filters": [
    {"column": "psirts.psirt_id", "operator": "=", "value": 2789},
    {"column": "psirts.vulnerability_status", "operator": "IN", "value": ["VUL", "POTVUL"]}
  ],
  "join_specs": [{"join_type": "INNER", "table": "psirts", "on_left": "assets.serial_number", "on_right": "psirts.serial_number"}],
  "target_table_alias": "assets"
}
```
All three fail with: **"Column prefix(es) ['count(distinct assets'] do not match the base table alias 'assets'"** — the `build_sql_query` validator incorrectly parses `COUNT(DISTINCT assets.serial_number)` and chokes on the prefix extraction for aggregate expressions.

**Side finding (known issue):** `mcp_build_sql_by_domain`'s column prefix validation does not handle aggregate function expressions (e.g. `COUNT(DISTINCT alias.column)`). The prefix extractor splits on `.` and gets `count(distinct assets` as the prefix, which fails validation. The LLM's query construction was actually correct — the tooling rejected it. **This is the same bug documented in [CXP-sql-query-triage.md](CXP-sql-query-triage.md)** (trace `019db47d-5e25`, 2026-04-22), where the root cause was identified as the naive string split in `security_assessment_agent_impl.py` lines 682–716.

### Run 5 — LLM → `mcp_execute_sql` (span 7 → 5 → 6)
After 3 failures with `mcp_build_sql_by_domain`, the LLM falls back to `mcp_execute_sql` with raw SQL:
```sql
SELECT COUNT(DISTINCT assets.serial_number) AS impacted_assets_count 
FROM postgresql.public.cvi_assets_view_1__3__5 assets 
INNER JOIN postgresql.public.cvi_psirts_view_1__3__7 psirts 
  ON assets.serial_number = psirts.serial_number 
WHERE psirts.psirt_id = 2789 
  AND psirts.vulnerability_status IN ('VUL', 'POTVUL');
```
Result: `{"impacted_assets_count": 37}` — correct count.

### Run 6 — Final LLM response (span 1)
The LLM receives the tool result `{"impacted_assets_count": 37}` and generates:

> "37 assets are impacted by the advisory with ID **2789** (either vulnerable or potentially vulnerable)."

The LLM has only the count (37) and the filter value (`psirt_id = 2789`) from its own query. It has no advisory name or `advisory_id` string, so it uses the only identifier it knows — the internal `psirt_id`.

---

## Root Cause Analysis

**Primary cause: The agent never resolves `checkId` → advisory name before responding.**

The `checkId` context filter value (`2789`) maps to `psirts.psirt_id` — an internal integer database key. The user-facing identifier is `bulletins.advisory_id` (a string like `cisco-sa-xxxxx`) and/or `bulletins.headline_name` (the advisory title). The LLM received `checkId: ['2789']` in the context filter block but never queried the `bulletins` table to resolve the actual advisory name before answering.

**Contributing factors:**

| # | Factor | Detail |
|---|--------|--------|
| 1 | **No programmatic `checkId` → advisory name resolution** | The `_format_context_filter()` function in `security_assessment_agent_impl.py` passes the raw numeric `checkId` into the system prompt. It does not perform a lookup (e.g. `SELECT advisory_id, headline_name FROM bulletins WHERE psirt_id = 2789`) to inject the human-readable advisory name. |
| 2 | **System prompt does not instruct the LLM to look up the advisory name** | The `<context_filter_mapping>` block tells the LLM that `checkId` maps to `psirt_id`, but it does not instruct: "When referencing the advisory in your response, first look up `bulletins.advisory_id` and `bulletins.headline_name` for the `psirt_id` and use those in your answer — never surface `psirt_id` to the user." |
| 3 | **No output validation for internal IDs** | The `<confidentiality>` section prohibits SQL/table/column names in responses, but does not prohibit exposing raw internal database IDs like `psirt_id`. |
| 4 | **`mcp_build_sql_by_domain` aggregate expression bug (known — see [CXP-sql-query-triage.md](CXP-sql-query-triage.md))** | The 3 failed `mcp_build_sql_by_domain` calls forced a fallback to raw SQL (`mcp_execute_sql`). While this didn't directly cause the ID leak, it consumed 3 of 5 retries and changed the query path, reducing the LLM's opportunity to construct a richer query that might have included a JOIN to bulletins for the advisory name. |

---

## Relationship to Known Failure Modes

- **Partially FM-6** (context switch / `checkId` resolution): FM-6 is about the agent answering about the *wrong* advisory. Here, the agent answers about the *right* advisory but names it with an internal ID instead of a user-facing identifier. The underlying cause is the same — no programmatic `checkId` → advisory name resolution.
- **Known issue** — `mcp_build_sql_by_domain` column prefix validation fails for aggregate function expressions like `COUNT(DISTINCT alias.column)`. Previously documented in [CXP-sql-query-triage.md](CXP-sql-query-triage.md).

---

## Recommended Fixes

### Fix 1 — Programmatic `checkId` resolution (recommended, highest impact)
In `security_assessment_agent_impl.py`, before the agent loop, when `checkId` is present in context filters:
1. Execute: `SELECT advisory_id, headline_name FROM bulletins WHERE psirt_id = <checkId>`
2. Inject the resolved name into the system prompt, e.g.:
   ```
   The user is viewing advisory "cisco-sa-xxxxx" (headline: "Multiple Vulnerabilities in...").
   When referring to this advisory in your response, use the advisory ID "cisco-sa-xxxxx" or the headline — never the internal psirt_id.
   ```

### Fix 2 — System prompt instruction (quick, partial)
Add to `<context_filter_mapping>` or `<output_format>`:
```
When referencing an advisory in your response, ALWAYS look up the `bulletins.advisory_id` and 
`bulletins.headline_name` for the given `psirt_id` first. Never expose `psirt_id` values to the 
user — they are internal database keys with no user meaning. Use the advisory_id 
(e.g. "cisco-sa-xxxxx") or headline_name instead.
```

### Fix 3 — Fix `mcp_build_sql_by_domain` aggregate expression validation (already triaged)
The column prefix validator in `security_assessment_agent_impl.py` (lines 682–716) should handle aggregate expressions. See [CXP-sql-query-triage.md](CXP-sql-query-triage.md) for the full analysis and recommended fix options (Option A: skip aggregates in prefix check; Option B: parse aggregates from `columns` into `aggregations` specs in the wrapper).

---

## Severity Assessment

**User impact:** Medium — the answer count is correct, but "advisory with ID 2789" is confusing and meaningless to the user. It leaks an internal database identifier.

**Data accuracy:** Correct — the 37-asset count is verified from the SQL result.

**Confidentiality:** Minor concern — while `psirt_id` is not a security-sensitive value, surfacing internal database keys is a UX/trust issue and borderline violates the spirit of the `<confidentiality>` section.
