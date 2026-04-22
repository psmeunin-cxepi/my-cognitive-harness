# Triage: SQL Query Validation Failures in Security Advisory Agent

**Trace ID:** `019db47d-5e25-7a40-8e88-887392a1db1b`  
**Workspace:** nprd (`cx-iq-nprd`)  
**Agent:** Security Assessment Agent  
**Model:** mistral-medium-2508  
**Date:** 2026-04-22  
**User question:** "List me the top 5 security advisories with most impact"  
**Repo:** `CXEPI/risk-app` (main branch)

---

## Summary

The LLM attempted to use `mcp_build_sql_by_domain` three times to build a top-5 advisory query with `COUNT(DISTINCT psirts.serial_number) AS impacted_assets_count`. All three attempts were rejected by the wrapper's column prefix validator before reaching the downstream `build_sql_query` tool. The LLM then fell back to `mcp_execute_sql` (raw SQL), which succeeded.

The underlying `build_sql_query` tool **already supports aggregations** via a dedicated `aggregations` parameter (`AggregationSpec` model), but the LLM is unaware of this parameter and instead stuffs aggregate expressions into the `columns` array as raw SQL fragments.

---

## Execution Timeline

| Step | LLM Run | Action | Tool Called | Result |
|------|---------|--------|-------------|--------|
| 1 | `019db47d-6b55` | First attempt — `COUNT(psirts.serial_number) AS impacted_assets_count`, hallucinated column names (`bulletins.title`, `bulletins.severity`), no `target_table_alias`, extra join to `assets` | `mcp_build_sql_by_domain` | **Failed** — prefix `count(psirts` and `bulletins` didn't match default base table `assets` |
| 2 | `019db47d-791f` | Retry — added `target_table_alias = "bulletins"`, removed extra `assets` join, still used hallucinated column names | `mcp_build_sql_by_domain` | **Failed** — prefix `count(psirts` not recognized by column prefix validator |
| 3 | `019db47d-849f` | Re-fetched schema | `mcp_get_table_schema` | Got correct column names (`headline_name`, `severity_level_name`) |
| 4 | `019db47d-86fc` | Fixed column names from schema, added `DISTINCT`, kept same alias | `mcp_build_sql_by_domain` | **Failed** — same prefix validation error on `COUNT(DISTINCT psirts.serial_number) AS impacted_assets_count` |
| 5 | `019db47d-9567` | Fell back to raw SQL via `mcp_execute_sql` | `mcp_execute_sql` | **Succeeded** — Trino executed the raw SQL |

---

## Failed `mcp_build_sql_by_domain` Attempts — Detail

### Attempt 1 (LLM run `019db47d-6b55`)

**LLM tool call arguments:**

```json
{
  "domain": "security_advisory",
  "columns": [
    "bulletins.psirt_id",
    "bulletins.title",
    "bulletins.severity",
    "COUNT(psirts.serial_number) AS impacted_assets_count"
  ],
  "join_specs": [
    { "join_type": "INNER", "table": "psirts", "on_left": "bulletins.psirt_id", "on_right": "psirts.psirt_id" },
    { "join_type": "INNER", "table": "assets", "on_left": "psirts.serial_number", "on_right": "assets.serial_number" }
  ],
  "group_by": ["bulletins.psirt_id", "bulletins.title", "bulletins.severity"],
  "order_by": [{ "column": "impacted_assets_count", "direction": "desc" }],
  "limit": 5
}
```

**No `target_table_alias` provided.** The wrapper defaults to the base table `assets`.

**Validation error:**

> `Column prefix(es) ['bulletins', 'count(psirts'] do not match the base table alias 'assets' or any join. Known aliases: ['assets', 'psirts'].`

**Why it failed:**
1. Missing `target_table_alias` → wrapper resolved base table to `assets` (the schema's primary table).
2. All `columns` and `group_by` reference `bulletins.*`, but `bulletins` was not in `join_specs` and `assets` was the base table — so `bulletins` was not a known alias.
3. The aggregate expression `COUNT(psirts.serial_number) AS impacted_assets_count` was parsed as a column prefix `count(psirts`, which is not a valid alias.
4. Column names `bulletins.title` and `bulletins.severity` are **hallucinated** — the actual schema columns are `bulletins.headline_name` and `bulletins.severity_level_name`.

---

### Attempt 2 (LLM run `019db47d-791f`)

**LLM tool call arguments:**

```json
{
  "domain": "security_advisory",
  "target_table_alias": "bulletins",
  "columns": [
    "bulletins.psirt_id",
    "bulletins.title",
    "bulletins.severity",
    "COUNT(psirts.serial_number) AS impacted_assets_count"
  ],
  "join_specs": [
    { "join_type": "INNER", "table": "psirts", "on_left": "bulletins.psirt_id", "on_right": "psirts.psirt_id" }
  ],
  "group_by": ["bulletins.psirt_id", "bulletins.title", "bulletins.severity"],
  "order_by": [{ "column": "impacted_assets_count", "direction": "desc" }],
  "limit": 5
}
```

**Validation error:**

> `Column prefix(es) ['count(psirts'] do not match the base table alias 'bulletins' or any join. Known aliases: ['bulletins', 'psirts'].`

**Why it failed:**
1. The LLM corrected the missing `target_table_alias` (now `"bulletins"`) and removed the unnecessary `assets` join — the `bulletins` prefix error from attempt 1 was resolved.
2. However, `COUNT(psirts.serial_number) AS impacted_assets_count` was still parsed as prefix `count(psirts` — which is not `bulletins` or `psirts`, so validation rejected it.
3. Column names `bulletins.title` and `bulletins.severity` are still hallucinated (not yet corrected — the LLM did not re-fetch the schema between attempts 1 and 2).

---

### Attempt 3 (LLM run `019db47d-86fc`, after schema refresh)

Between attempts 2 and 3, the LLM called `mcp_get_table_schema` (LLM run `019db47d-849f`) and received the correct schema with column names `headline_name` and `severity_level_name`.

**LLM tool call arguments:**

```json
{
  "domain": "security_advisory",
  "target_table_alias": "bulletins",
  "columns": [
    "bulletins.psirt_id",
    "bulletins.headline_name",
    "bulletins.severity_level_name",
    "COUNT(DISTINCT psirts.serial_number) AS impacted_assets_count"
  ],
  "join_specs": [
    { "join_type": "INNER", "table": "psirts", "on_left": "bulletins.psirt_id", "on_right": "psirts.psirt_id" }
  ],
  "group_by": ["bulletins.psirt_id", "bulletins.headline_name", "bulletins.severity_level_name"],
  "order_by": [{ "column": "impacted_assets_count", "direction": "desc" }],
  "limit": 5
}
```

**Validation error:**

> `Column prefix(es) ['count(distinct psirts'] do not match the base table alias 'bulletins' or any join. Known aliases: ['bulletins', 'psirts'].`

**Why it failed:**
1. Column names are now **correct** (`headline_name`, `severity_level_name`) — the LLM self-corrected after the schema refresh.
2. The LLM also added `DISTINCT` to the count (better accuracy for the metric).
3. However, the root blocker remained: `COUNT(DISTINCT psirts.serial_number) AS impacted_assets_count` was parsed as prefix `count(distinct psirts` — still not a recognized alias.
4. **This is the structurally correct query** — it would produce valid SQL if the validator accepted aggregate expressions. The LLM had no remaining option but to fall back to `mcp_execute_sql`.

---

### Final SQL executed (via `mcp_execute_sql`)

```sql
SELECT bulletins.psirt_id, bulletins.headline_name, bulletins.severity_level_name,
       COUNT(DISTINCT psirts.serial_number) AS impacted_assets_count
FROM postgresql.public.pas_psirt_bulletins_view_1__3__1 bulletins
INNER JOIN postgresql.public.cvi_psirts_view_1__3__7 psirts
  ON bulletins.psirt_id = psirts.psirt_id
GROUP BY bulletins.psirt_id, bulletins.headline_name, bulletins.severity_level_name
ORDER BY impacted_assets_count DESC
LIMIT 5
```

---

## Root Cause: Two validation layers, failure is in the wrapper

### Layer 1: Column prefix check — `security_assessment_agent_impl.py` (lines 682–716) — **THIS IS WHERE IT FAILED**

This is a **pre-validation** in the `mcp_build_sql_by_domain` wrapper, **before** the request ever reaches `build_sql_query`. It does a naive string split:

```python
# security_assessment_agent_impl.py, lines 692-698
for col_list in (columns, group_by):
    for col in col_list or []:
        if "." in col:
            prefix = col.split(".")[0].lower()
            if prefix not in known_aliases:
                bad_prefixes.add(prefix)
```

When the LLM sends `COUNT(DISTINCT psirts.serial_number) AS impacted_assets_count` as a column entry, `.split(".")[0]` produces `count(distinct psirts` — which is not in `known_aliases` (`{'bulletins', 'psirts'}`).

**This is a naive string split that does not account for aggregate function syntax.** It treats the entire string before the first `.` as a table alias prefix.

### Layer 2: Identifier regex + Pydantic validators — `text2sql_mcp/server.py` — **NEVER REACHED**

The `build_sql_query` tool in `server.py` has proper structured input handling:

- **`columns`** parameter: validated via `_validate_identifier()` (regex `^[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*){0,3}$`) — only accepts plain `alias.column` references.
- **`aggregations`** parameter: a separate `AggregationSpec` Pydantic model that properly handles aggregate functions:

```python
# text2sql_mcp/server.py
class AggregationSpec(BaseModel):
    function: Literal["COUNT", "SUM", "AVG", "MIN", "MAX", "COUNT_DISTINCT"]
    column: str       # e.g. "psirts.serial_number"
    alias: str | None  # e.g. "impacted_assets_count"
```

**The `build_sql_query` tool already supports exactly what the LLM needs.** The correct call would have been:

```json
{
  "columns": ["bulletins.psirt_id", "bulletins.headline_name", "bulletins.severity_level_name"],
  "aggregations": [
    { "function": "COUNT_DISTINCT", "column": "psirts.serial_number", "alias": "impacted_assets_count" }
  ],
  "group_by": ["bulletins.psirt_id", "bulletins.headline_name", "bulletins.severity_level_name"]
}
```

But the LLM stuffed the aggregate expression into the `columns` array as a raw SQL fragment instead of using the `aggregations` parameter.

---

## Why the LLM doesn't use the `aggregations` parameter

1. **The `mcp_build_sql_by_domain` wrapper's docstring never mentions `aggregations`** — the tool signature exposes `columns`, `filters`, `group_by`, `order_by`, `join_specs`, `target_table_alias`, and `limit`, but there is no `aggregations` parameter in the wrapper's function signature.
2. **The wrapper does forward `aggregations` if provided** (line 721–724: `if aggregations: build_args["aggregations"] = _normalize_aggregations(aggregations)`), but the LLM has no way to discover this parameter since it's not in the tool definition visible to the LLM.
3. **The system prompt does not mention `aggregations`** as a parameter or provide examples of how to express aggregate queries through the structured API.

---

## Fix Recommendations

### Option A: Fix the wrapper's prefix validator (minimal change)

Modify the column prefix check in `security_assessment_agent_impl.py` to skip entries that look like aggregate expressions before doing the `.split(".")` check:

```python
_AGG_PATTERN = re.compile(r"^(COUNT|SUM|AVG|MIN|MAX)\s*\(", re.IGNORECASE)

for col in col_list or []:
    if _AGG_PATTERN.match(col):
        continue  # skip aggregate expressions — they aren't column references
    if "." in col:
        prefix = col.split(".")[0].lower()
        if prefix not in known_aliases:
            bad_prefixes.add(prefix)
```

**Pros:** Stops the false rejections.  
**Cons:** The aggregate expression still lands in `columns` and will be rejected by `build_sql_query`'s `_validate_identifier()` regex in Layer 2. This fix alone would just shift the failure to the next layer.

### Option B: Parse aggregates from `columns` into `aggregations` in the wrapper (preferred)

In the wrapper, detect entries in `columns` that match aggregate patterns (e.g., `COUNT(DISTINCT psirts.serial_number) AS impacted_assets_count`), extract them into proper `AggregationSpec` dicts, and move them to `aggregations` before forwarding to `build_sql_query`:

```python
import re
_AGG_RE = re.compile(
    r"^(COUNT_DISTINCT|COUNT|SUM|AVG|MIN|MAX)\s*\(\s*(DISTINCT\s+)?(.+?)\s*\)"
    r"(\s+AS\s+(\w+))?$",
    re.IGNORECASE,
)

extracted_aggs = []
clean_columns = []
for col in columns or []:
    m = _AGG_RE.match(col.strip())
    if m:
        func = m.group(1).upper()
        distinct = bool(m.group(2))
        agg_col = m.group(3).strip()
        alias = m.group(5)
        if func == "COUNT" and distinct:
            func = "COUNT_DISTINCT"
        extracted_aggs.append({"function": func, "column": agg_col, "alias": alias})
    else:
        clean_columns.append(col)
columns = clean_columns or None
aggregations = (aggregations or []) + extracted_aggs if extracted_aggs else aggregations
```

**Pros:** The LLM can keep using its natural pattern (aggregate in columns) and the wrapper transparently maps it to the structured API.  
**Cons:** More complex regex; needs testing for edge cases.

### Option C: Expose `aggregations` in the wrapper's tool definition

Add `aggregations` as a documented parameter in the `mcp_build_sql_by_domain` function signature and docstring. Update the system prompt to include an example of using it for COUNT/SUM queries.

**Pros:** Clean separation; the LLM learns the correct API.  
**Cons:** Requires system prompt changes and re-testing; existing behavior in production may break if the LLM start using it inconsistently.

### Recommended approach

**Combine Option B + Option C.** Option B provides immediate backward compatibility (the LLM's current pattern works), while Option C teaches the LLM the correct API going forward. Over time, Option B becomes a fallback as the LLM learns to use `aggregations` directly.

---

## Where each part of the final SQL comes from

| SQL element | Source |
|-------------|--------|
| `bulletins.psirt_id`, `bulletins.headline_name`, `bulletins.severity_level_name` | Schema response — `mcp_get_table_schema` returned these as valid columns for the `bulletins` table |
| `psirts.serial_number` | Schema response — valid column in `psirts` table |
| `INNER JOIN ... ON bulletins.psirt_id = psirts.psirt_id` | Schema `relationships[]` — relationship `psirts_bulletins` defines this join |
| `COUNT(DISTINCT ...) AS impacted_assets_count` | **LLM-invented** — the alias is a descriptive label chosen by the LLM; not sourced from any prompt, schema, or code |
| `ORDER BY impacted_assets_count DESC LIMIT 5` | **LLM-generated** — derived from "top 5 ... with most impact" |
| FQN table names (`postgresql.public.pas_psirt_bulletins_view_1__3__1`) | Schema response — `from_table_ref` / `to_table_ref` in `relationships[]` |
