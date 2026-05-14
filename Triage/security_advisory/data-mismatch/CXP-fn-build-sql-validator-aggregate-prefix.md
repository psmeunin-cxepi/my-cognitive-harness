> **Agent:** Security Advisory
> **Repo:** [`CXEPI/risk-app`](https://github.com/CXEPI/risk-app)
> **Jira:** _to be created_

# `mcp_build_sql_by_domain` validator false-positive on aggregate column prefixes — forces raw-SQL fallback

## Summary

User asked *"How many assets are impacted by a security advisory, excluding the potentially affected assets."* The agent returned **"1,061 assets"**, which is consistent with the user's intent (distinct serials with `psirts.vulnerability_status = 'VUL'`). However, the answer was produced via a raw `mcp_execute_sql` fallback because the safer `mcp_build_sql_by_domain` tool rejected the query twice with a false-positive validation error: its column-prefix extractor split the literal `COUNT(DISTINCT assets.serial_number)` on `.` and treated `count(distinct assets` as the table alias. The LLM then bypassed the guarded path and built raw SQL itself.

## Trace
- **Trace ID:** `019e25c8-aeec-7952-ac70-5a7e7065b1d4`
- **Workspace:** cx-iq-prod (Semantic Router → routed to *Assessments – Security Advisories*)
- **Agent:** Security Advisory
- **Date:** 2026-05-14

## Execution Flow

1. **Router** classified to skill `ask_security_assessment` → invoked `Security Assessment Agent`.
2. **LLM #1** chose the SQL data flow per system prompt rule #4 → called `mcp_get_table_schema` (domain `security_advisory`).
3. Schema response confirmed `psirts.vulnerability_status` enum is `["VUL", "POTVUL"]` and the join key `assets.serial_number = psirts.serial_number`.
4. **LLM #2** called `mcp_build_sql_by_domain` with:
   ```json
   {
     "domain": "security_advisory",
     "columns": ["COUNT(DISTINCT assets.serial_number) AS impacted_assets_count"],
     "filters": [{"column": "psirts.vulnerability_status", "operator": "=", "value": "VUL"}],
     "join_specs": [{"join_type": "INNER", "table": "psirts",
                     "on_left": "assets.serial_number", "on_right": "psirts.serial_number"}],
     "target_table_alias": "assets"
   }
   ```
   → rejected with:
   > Query validation error: Column prefix(es) `['count(distinct assets']` do not match the base table alias `'assets'` or any join. Known aliases: `['assets', 'psirts']`. Add the missing table via join_specs or correct the column prefix.
5. **LLM #3** retried the **identical** payload → same error.
6. **LLM #4** fell back to `mcp_execute_sql` with hand-written SQL:
   ```sql
   SELECT COUNT(DISTINCT assets.serial_number) AS impacted_assets_count
   FROM postgresql.public.cvi_assets_view_1__3__5 AS assets
   INNER JOIN postgresql.public.cvi_psirts_view_1__3__7 AS psirts
     ON assets.serial_number = psirts.serial_number
   WHERE psirts.vulnerability_status = 'VUL';
   ```
   → returned `[{"impacted_assets_count": 1061}]`.
7. **LLM #5** rendered the final answer: *"There are **1,061 assets** impacted by security advisories…"*

## Root Cause

**Primary classification: Tool validation** (with secondary **Model behaviour** in the agent retry loop).

`mcp_build_sql_by_domain` validates that every `columns[]` entry is prefixed with a known table alias. Its extractor appears to split the entry on `.` without first stripping the surrounding aggregate function (`COUNT(`, `SUM(`, …) and `DISTINCT` keyword. For the input `COUNT(DISTINCT assets.serial_number) AS impacted_assets_count`:

- Extractor takes everything left of the first `.` → `count(distinct assets`
- Compares against known aliases `['assets', 'psirts']` → no match
- Raises validation error.

The actual column reference is well-formed (`assets.serial_number` is a valid prefix). This is a parser bug, not an LLM error.

Two compounding issues:

1. **Agent loop did not detect identical-args retry.** LLMs #2 and #3 sent the *same* payload and got the *same* error. The loop should short-circuit identical retries and either escalate to raw SQL with logging or surface a clean failure.
2. **Fallback to raw SQL bypasses the guardrail layer** (column allow-listing, tenant-filter injection if any, complexity caps). When `build_sql_by_domain` falsely rejects valid queries, the agent silently degrades to a less-protected execution path.

## Evidence

### `mcp_build_sql_by_domain` rejection (LLM #2 and #3 — identical)

Tool input:
```json
{"domain": "security_advisory",
 "columns": ["COUNT(DISTINCT assets.serial_number) AS impacted_assets_count"],
 "filters": [{"column": "psirts.vulnerability_status", "operator": "=", "value": "VUL"}],
 "join_specs": [{"join_type": "INNER", "table": "psirts",
                 "on_left": "assets.serial_number", "on_right": "psirts.serial_number"}],
 "target_table_alias": "assets"}
```

Tool output:
```
Query validation error: Column prefix(es) ['count(distinct assets'] do not match the base table alias 'assets' or any join. Known aliases: ['assets', 'psirts']. Add the missing table via join_specs or correct the column prefix.
```

### Raw SQL that produced the 1,061

```sql
SELECT COUNT(DISTINCT assets.serial_number) AS impacted_assets_count
FROM postgresql.public.cvi_assets_view_1__3__5 AS assets
INNER JOIN postgresql.public.cvi_psirts_view_1__3__7 AS psirts
  ON assets.serial_number = psirts.serial_number
WHERE psirts.vulnerability_status = 'VUL';
```
→ `{"impacted_assets_count": 1061}`

### Schema confirmation that the filter semantics match the user intent

From `mcp_get_table_schema` for the `psirts` view:
```json
{
  "name": "vulnerability_status",
  "type": "string",
  "description": "Vulnerability assessment status.",
  "enum_values": ["VUL", "POTVUL"]
}
```
And a top-level domain hint:
> *vulnerability_status (VUL/POTVUL) to filter vulnerable assets.*

So `WHERE vulnerability_status = 'VUL'` correctly excludes `POTVUL` ("potentially affected") — the headline number is semantically valid for the question.

## Decomposition of "1,061"

| Question element | SQL translation | Notes |
|---|---|---|
| "assets … impacted" | `COUNT(DISTINCT assets.serial_number)` after `INNER JOIN psirts` | Counts an asset once if it has ≥1 PSIRT match |
| "by a security advisory" | the `INNER JOIN` itself | All rows in `cvi_psirts_view_1__3__7` represent advisory matches |
| "excluding the potentially affected" | `WHERE psirts.vulnerability_status = 'VUL'` | Excludes the `POTVUL` enum |

So **1,061 = distinct serial numbers in scope with at least one `VUL` PSIRT match**.

## Open questions / things to verify

1. **Tenant scoping.** The runtime payload's `filters` block is entirely `None` and the emitted SQL contains no `platform_account_id` predicate. If tenant isolation is enforced server-side (Trino view rewrite or session var), this is fine. If not, **1,061 may be cross-tenant** and the agent is the wrong layer to depend on for that filter — it must be injected by the MCP/data layer.
2. **Aggregate-column cross-check.** `cvi_assets_view_1__3__5` exposes pre-aggregated counters. A join-free equivalent would be:
   ```sql
   SELECT COUNT(*) FROM cvi_assets_view_1__3__5 WHERE affected_security_advisories_count > 0;
   ```
   If the figure differs from 1,061 in the same tenant, the views are inconsistent and that itself is a data finding.

## Recommendations

### P1 — Fix the `build_sql_by_domain` column-prefix validator
- Strip aggregate-function wrappers (`COUNT(`, `SUM(`, `AVG(`, `MIN(`, `MAX(`, …) and the `DISTINCT` keyword before extracting the table alias.
- Equivalent: parse with a real SQL/expression parser instead of a regex split on `.`.
- Add a regression test using the exact failing payload from this trace, plus variants:
  - `COUNT(DISTINCT t.col)`
  - `SUM(t.col)`
  - `COUNT(*)` (no prefix — should be allowed)
  - `MAX(t1.col) - MIN(t2.col)` (multiple prefixes in one expression)
- **Likely location:** the text2sql MCP server in `CXEPI/risk-app` (mirrors the structure shown in this repo at [triage/schema/text2sql_server.py](triage/schema/text2sql_server.py)).

### P2 — Verify tenant scoping in the SQL execution path
- Confirm with the data-platform owners whether `cvi_assets_view_1__3__5` and `cvi_psirts_view_1__3__7` are tenant-rewritten at the Trino layer.
- If not, inject `platform_account_id` server-side in both `mcp_build_sql_by_domain` and `mcp_execute_sql` rather than relying on the LLM to add it.

### P3 — Short-circuit identical-args retries in the agent loop
- If a tool returns the same error for the same arguments, do not call it again with those arguments. Either (a) skip to the documented fallback (`mcp_execute_sql`) with a log line indicating the validator rejection, or (b) return a clean error.
- Saves at least one LLM round-trip per occurrence and reduces token spend.

### P4 — Prompt nudge: prefer pre-aggregated counts where available
- Once P2 is settled, add a system-prompt example for portfolio-level "how many impacted devices" questions that uses `affected_security_advisories_count > 0` on the assets view directly. Cheaper and avoids the join entirely.
