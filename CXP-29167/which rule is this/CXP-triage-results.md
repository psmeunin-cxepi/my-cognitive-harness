# CXP Triage Results — Security Advisory Agent: "which rule is this?"

**Date:** 2026-04-20  
**Agent:** Security Assessment AI Agent (`DEV--Security_Assessment_AI_Agent` / `ciq-agents-dev-usw2`)  
**Model:** `mistral-medium-2508`  
**LangSmith trace:** `019daa0e-2d55-7bf2-a924-e54a0c167711`  
**User prompt:** "which rule is this?"  
**Runtime context:** `checkId: ['989']`, URL `/assessments/security-advisories/989`

---

## Summary

The agent failed to answer the question across two distinct LangSmith runs with different failure modes. **Run2** is a pure LLM hallucination — the model invented a column name not present in the schema. **Run4** is a shared failure — the LLM passed correct column choices but omitted a required tool argument, and the downstream `build_sql_query` MCP tool silently generated structurally broken SQL rather than rejecting the invalid input.

---

## Trace Files Analysed

| Run | File | Role |
|---|---|---|
| run2 | `run2_llm-019daa0e-43b2-7de2-8792-18aea62409e7.json` | LLM call that hallucinated `psirts.check_id` |
| run2 | `run2_tool_1-019daa0e-5615-7b20-8230-e136a98e61dd.json` | `get_table_schema` — schema the LLM had in context |
| run2 | `run2_tool_2-019daa0e-5644-7841-9fca-86249183ceac.json` | `build_sql_query` — accepted the hallucinated filter |
| run2 | `run2_tool_2-019daa0e-566a-7482-93a2-585e1e21dca1.json` | `run_sql_query` — executed the broken SQL |
| run4 | `run4_llm-019daa0e-612c-7551-8c7d-dc242a3e1e3f.json` | LLM retry call — correct filter, missing `target_table_alias` |
| run4 | `run4_tool_1-019daa0e-7ade-7872-a29e-85ae5c72cbdc.json` | `get_table_schema` — schema returned to LLM |
| run4 | `run4_tool_2-019daa0e-7b0c-7913-bbc9-1643d176f0ea.json` | `build_sql_query` — generated wrong FROM with no JOINs |
| run4 | `run4_tool_3-019daa0e-7b2f-78f0-87e6-386a590a9068.json` | `run_sql_query` — executed the broken SQL |

---

## Schema (Ground Truth)

**Domain:** `security_advisory`  
Three logical tables, all columns confirmed from `get_table_schema` responses in both runs:

| Alias | Physical table | Key columns |
|---|---|---|
| `assets` | `postgresql.public.cvi_assets_view_1__3__5` | `serial_number`, `platform_account_id`, advisory count fields |
| `psirts` | `postgresql.public.cvi_psirts_view_1__3__7` | `psirt_id` (integer), `serial_number`, `vulnerability_status`, `sav_id` |
| `bulletins` | `postgresql.public.pas_psirt_bulletins_view_1__3__1` | `psirt_id` (integer), `advisory_id`, `headline_name`, `severity_level_name`, `cvss_score` |

**Relationships:** `assets.serial_number → psirts.serial_number` (1:∗), `psirts.psirt_id → bulletins.psirt_id` (∗:1)

**`check_id` does not exist in any table.** The only PSIRT advisory identifier is `psirt_id` (integer) on both `psirts` and `bulletins`.

---

## Run2 — LLM Hallucination (`psirts.check_id`)

**Single failure owner: LLM**

### What happened

1. LLM called `mcp_get_table_schema` → received the full 3-table schema (run2_tool_1). The `psirts` table column list was explicitly returned: `product_family, sav_id, software_version, source, updated_at, vulnerability_reason, vulnerability_status, caveat, serial_number, product_id, psirt_id, platform_account_id, partition_key`.
2. Despite having the schema in context, the LLM called `mcp_build_sql_by_domain` with a hallucinated filter column:
   ```json
   "filters": [{ "column": "psirts.check_id", "operator": "=", "value": "989" }]
   ```
3. `build_sql_query` (downstream MCP, run2_tool_2) accepted the filter without validation and generated structurally correct SQL — right JOINs, right SELECT columns — but with the fake column in WHERE:
   ```sql
   SELECT bulletins.advisory_id, bulletins.headline_name, bulletins.severity_level_name,
          bulletins.summary_text, bulletins.cvss_score, bulletins.publish_date
   FROM postgresql.public.cvi_assets_view_1__3__5 AS assets
   INNER JOIN postgresql.public.cvi_psirts_view_1__3__7 AS psirts
     ON assets.serial_number = psirts.serial_number
   INNER JOIN postgresql.public.pas_psirt_bulletins_view_1__3__1 AS bulletins
     ON psirts.psirt_id = bulletins.psirt_id
   WHERE (psirts.check_id = '989')
   ```
4. Trino returned: `"Query failed: one or more column names are invalid."`

### Root cause

The LLM saw `checkId: ['989']` in the runtime context filter dict and translated the camelCase UI key `checkId` into the snake_case column name `check_id`, then prefixed it with `psirts.`. This directly violates the system prompt instruction:

> *"Never use a column name in a query unless it appeared in the mcp_get_table_schema response for the current conversation."*

The schema was in context. `check_id` was not in it. The column was fabricated.

### Note on JOIN structure

The LLM correctly provided `join_specs` (`assets→psirts→bulletins`) on this attempt, so `build_sql_query` generated valid JOINs. The SQL structure was correct — only the filter column name was wrong. This is a clean single-layer failure owned entirely by the LLM.

---

## Run4 — Two Distinct Failure Owners

**Failure owner 1: LLM** (missing `target_table_alias`)  
**Failure owner 2: `build_sql_query` MCP server** (accepted invalid inputs, generated broken SQL)

### What happened

After run2 failed with "column names invalid", the agent retried. This time the LLM chose the correct filter column — `bulletins.psirt_id = 989` — but made a different error:

1. LLM called `mcp_get_table_schema` → full schema returned (run4_tool_1).
2. LLM called `mcp_build_sql_by_domain` with correct bulletin columns and correct filter, but **omitted `target_table_alias`**:
   ```json
   {
     "domain": "security_advisory",
     "columns": ["bulletins.advisory_id", "bulletins.headline_name", "bulletins.severity_level_name",
                 "bulletins.summary_text", "bulletins.cvss_score", "bulletins.publish_date"],
     "filters": [{ "column": "bulletins.psirt_id", "operator": "=", "value": 989 }]
   }
   ```
   No `target_table_alias`. No `join_specs`.

3. The `mcp_build_sql_by_domain` Python wrapper ([security_assessment_agent_impl.py](../risk-app/security-advisory-ai-api/src/openapi_server/impl/security_assessment_agent_impl.py)) silently defaulted:
   ```python
   alias = (target_table_alias or "assets").lower()  # → "assets"
   table_name = tables["assets"]["table"]             # → cvi_assets_view_1__3__5
   ```
   It forwarded `table_name = "postgresql.public.cvi_assets_view_1__3__5"` to `build_sql_query` along with the `bulletins.*` columns and filter — with no joins attached.

4. `build_sql_query` (downstream MCP, run4_tool_2) received `table_name = cvi_assets_view_1__3__5`, `bulletins.*` columns, `bulletins.psirt_id` filter, and **no joins**. Rather than rejecting this structurally invalid combination, it silently generated:
   ```sql
   SELECT bulletins.advisory_id, bulletins.headline_name, bulletins.severity_level_name,
          bulletins.summary_text, bulletins.cvss_score, bulletins.publish_date
   FROM postgresql.public.cvi_assets_view_1__3__5
   WHERE (bulletins.psirt_id = 989)
   ```
5. Trino returned: `"Query failed: one or more column names are invalid."`

### Root cause — LLM (Failure owner 1)

The LLM requested columns exclusively from the `bulletins` table but passed no `target_table_alias` and no `join_specs`. The tool signature makes `target_table_alias` optional, defaulting to `"assets"`. The LLM should have set `target_table_alias = "bulletins"` when all columns and filters belong to that table. Without it, the wrapper had no way to infer the intended base table.

### Root cause — `build_sql_query` MCP server (Failure owner 2)

The `build_sql_query` tool (outside the `risk-app` repo) received a structurally contradictory request: `FROM cvi_assets_view` with `bulletins.*` columns and no JOINs — a set of column references that cannot be resolved against the specified base table. The tool should have:
- Returned a validation error indicating the column prefixes don't match the base table, OR
- Auto-detected the column prefixes and inferred that `bulletins` should be the base table (or that JOINs were missing)

Instead it silently passed the invalid SQL to Trino, consuming a retry cycle with no actionable error feedback to the LLM.

---

## Failure Attribution Summary

| Run | Failure | Owner | SQL error |
|---|---|---|---|
| run2 | Hallucinated `psirts.check_id` — column not in schema | LLM | "column names invalid" |
| run4 | Omitted `target_table_alias="bulletins"` → wrapper defaulted to `assets` base table | LLM | "column names invalid" |
| run4 | Accepted `FROM cvi_assets_view` + `bulletins.*` columns + no JOINs without error | `build_sql_query` MCP | "column names invalid" |

---

## Correct Query

For "which rule is this?" with `checkId: ['989']`, the correct call to `mcp_build_sql_by_domain` should be:

```json
{
  "domain": "security_advisory",
  "target_table_alias": "bulletins",
  "columns": [
    "bulletins.advisory_id",
    "bulletins.headline_name",
    "bulletins.severity_level_name",
    "bulletins.summary_text",
    "bulletins.cvss_score",
    "bulletins.publish_date",
    "bulletins.psirt_url_text"
  ],
  "filters": [
    { "column": "bulletins.psirt_id", "operator": "=", "value": 989 }
  ]
}
```

Resulting SQL:
```sql
SELECT bulletins.advisory_id, bulletins.headline_name, bulletins.severity_level_name,
       bulletins.summary_text, bulletins.cvss_score, bulletins.publish_date, bulletins.psirt_url_text
FROM postgresql.public.pas_psirt_bulletins_view_1__3__1 AS bulletins
WHERE bulletins.psirt_id = 989
```

No JOIN to `assets` or `psirts` is needed for a pure bulletin lookup — `bulletins` is public reference data not scoped per tenant.

---

## Recommendations

### Fix 1 — System prompt (quick win, highest leverage)

Add an explicit mapping note to the `<instructions>` block. The system prompt currently says to use `checkId` as a filter but does not tell the LLM which column it maps to:

**Add after the `<instructions>` block:**
```
<context_filter_mapping>
The runtime context key `checkId` maps to the integer column `psirts.psirt_id` AND `bulletins.psirt_id` in SQL.
There is NO column named `check_id` in any table — never use it.
When the user asks about "this rule", "this advisory", or "this check" and `checkId` is set in the runtime context,
filter on `bulletins.psirt_id = <value>` with `target_table_alias = "bulletins"`.
</context_filter_mapping>
```

### Fix 2 — `mcp_build_sql_by_domain` wrapper (defensive validation)

In [security_assessment_agent_impl.py](../risk-app/security-advisory-ai-api/src/openapi_server/impl/security_assessment_agent_impl.py), after resolving `table_name` from the schema, validate that all column prefixes in `columns` and `filters` belong to the resolved base table or to a table referenced in `join_specs`:

```python
# After resolving table_name, before calling build_sql_query:
# Extract all table prefixes from columns + filters
# If any prefix does not match the base alias and is not in join_specs,
# log a warning and/or return an early error to the LLM with a correction hint.
```

This would catch the run4 case (bulletins columns requested but assets base table selected with no joins) before hitting Trino.

### Fix 3 — `build_sql_query` downstream MCP (defensive, separate team)

The `build_sql_query` tool should validate that filter columns exist in the table/join set it has been given, and return a structured validation error rather than generating and passing invalid SQL to Trino. This would have caught the run2 `check_id` failure.

---

## Issue Context

| Field | Value |
|---|---|
| LangSmith project | `DEV--Security_Assessment_AI_Agent` |
| LangSmith workspace | `Cisco IQ - AI Assistant` (`nprd`) |
| Thread | `2bf0ce92-55dc-4cf3-b663-15901f8a4754` |
| UI URL at time of failure | `/assessments/security-advisories/989` |
| Runtime `checkId` | `['989']` |
| Local repo path | `/Users/psmeunin/Git/risk-app/security-advisory-ai-api` |
