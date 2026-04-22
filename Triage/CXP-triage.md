# Triage: `impacted_assets_count` alias and Data Accuracy in Security Advisory Agent

**Trace ID:** `019db47d-5e25-7a40-8e88-887392a1db1b`  
**Workspace:** nprd (`cx-iq-nprd`)  
**Agent:** Security Assessment Agent  
**Model:** mistral-medium-2508  
**Date:** 2026-04-22  
**User question:** "List me the top 5 security advisories with most impact"

**Related:** [CXP-sql-query-triage.md](CXP-sql-query-triage.md) — full analysis of the SQL query validation failures.

---

## Summary

The generated SQL counts **all** psirt records (`COUNT(DISTINCT psirts.serial_number)`) with **no filter on `psirts.vulnerability_status`**, combining both `VUL` (confirmed vulnerable) and `POTVUL` (potentially vulnerable) assets into a single number. The UI shows these as two separate columns — "Affected Assets" and "Potentially Affected Assets" — so the returned count is inaccurate: it conflates the two statuses and does not match either UI column.

The schema provides the `vulnerability_status` enum and a filtering hint (note #3), but the column and note descriptions lack the semantic clarity to convey that a bare `COUNT` without splitting by status produces a meaningless number. The LLM defaulted to counting all records.

---

## Where each part of the SQL comes from

The final SQL executed was:

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

| SQL element | Source |
|-------------|--------|
| `bulletins.psirt_id`, `bulletins.headline_name`, `bulletins.severity_level_name` | Schema response — `mcp_get_table_schema` returned these as valid columns for the `bulletins` table |
| `psirts.serial_number` | Schema response — valid column in `psirts` table |
| `INNER JOIN ... ON bulletins.psirt_id = psirts.psirt_id` | Schema `relationships[]` — relationship `psirts_bulletins` defines this join |
| `COUNT(DISTINCT ...) AS impacted_assets_count` | **LLM-invented** — the alias is a descriptive label chosen by the LLM; not sourced from any prompt, schema, or code |
| `ORDER BY impacted_assets_count DESC LIMIT 5` | **LLM-generated** — derived from "top 5 ... with most impact" |
| FQN table names (`postgresql.public.pas_psirt_bulletins_view_1__3__1`) | Schema response — `from_table_ref` / `to_table_ref` in `relationships[]` |

---

## Assessment

- **Is `impacted_assets_count` a bug?** No — it's a valid, descriptive SQL alias chosen by the LLM. The underlying metric (`COUNT(DISTINCT psirts.serial_number)`) correctly counts distinct impacted devices per advisory, which is consistent with the schema notes.
- **Is the fallback to `mcp_execute_sql` a concern?** Yes — raw SQL bypasses the structured validator's identifier checks. The system prompt rule 6 permits this ("Use `mcp_execute_sql` only when `mcp_build_sql_by_domain` cannot express the required query"), so the LLM followed instructions correctly, but the guardrail gap remains. See [CXP-sql-query-triage.md](CXP-sql-query-triage.md) for the full validation failure analysis.

---

## Data Accuracy Issue: Affected vs. Potentially Affected Assets

### Problem

The SQL counts **all** psirt records via `COUNT(DISTINCT psirts.serial_number)` with **no filter on `psirts.vulnerability_status`**. This combines both `VUL` (affected) and `POTVUL` (potentially affected) assets into a single number. The UI shows these as two separate columns — "Affected Assets" and "Potentially Affected Assets" — so the returned count conflates the two.

### What context the LLM has

The schema **does** provide the information to distinguish the two statuses:

| Schema element | Content |
|---|---|
| `psirts.vulnerability_status` description | `"Vulnerability assessment status."` |
| `psirts.vulnerability_status` enum values | `["VUL", "POTVUL"]` |
| Schema note #3 | `"Use psirts.vulnerability_status (VUL/POTVUL) to filter vulnerable assets."` |
| `psirts.vulnerability_reason` enum values | `"Match on SW Type, SW Version"` (→ VUL), `"Match on SW Type, SW Version; Manual Verification Required"` (→ POTVUL) |
| Example filter | `psirts.vulnerability_status = 'VUL'` |

### Why the LLM didn't use it

1. **No explicit mapping to UI labels.** The schema never states that `VUL` = "Affected Assets" and `POTVUL` = "Potentially Affected Assets" as shown in the UI.
2. **Note #3 reads as a filtering hint, not an aggregation rule.** `"Use psirts.vulnerability_status (VUL/POTVUL) to filter vulnerable assets"` suggests using it for WHERE clauses, not as a mandatory split for COUNT aggregations.
3. **User intent was ambiguous.** "Most impact" doesn't specify whether to count only confirmed-vulnerable or also potentially-vulnerable devices. The LLM defaulted to counting all.
4. **No system prompt instruction** maps the UI concepts of "Affected" / "Potentially Affected" to the specific `vulnerability_status` values.

### Correct SQL

To match the UI's "Affected Assets" column:

```sql
COUNT(DISTINCT CASE WHEN psirts.vulnerability_status = 'VUL'
      THEN psirts.serial_number END) AS affected_assets_count
```

To match the UI's "Potentially Affected Assets" column:

```sql
COUNT(DISTINCT CASE WHEN psirts.vulnerability_status = 'POTVUL'
      THEN psirts.serial_number END) AS potentially_affected_assets_count
```

### Schema fix recommendation

Add a note to the `get_table_schema` response:

> *"When counting impacted/affected assets per advisory, always filter or split on `psirts.vulnerability_status`. `VUL` = affected (confirmed vulnerable), `POTVUL` = potentially affected (manual verification required). A bare `COUNT` without this filter combines both statuses and does not match the UI breakdown."*