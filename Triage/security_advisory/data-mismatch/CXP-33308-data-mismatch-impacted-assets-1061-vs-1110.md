> **Agent:** Security Advisory
> **Repo:** [`CXEPI/risk-app`](https://github.com/CXEPI/risk-app)
> **Jira:** [CXP-33308](https://cisco-cxe.atlassian.net/browse/CXP-33308)

# Data mismatch — AI Security Advisory returns 1,061 impacted assets vs. 1,110 in the Asset Inventory UI

## Summary

A user on the same tenant ("Prod Testing - US") sees two different numbers for what they perceive as the same question — *"how many of my assets are impacted by a security advisory"*:

- **Assets → Inventory** page, with the **"Affected by security advisories"** filter applied (chip shows "Filters (2)"): **1,110 results**.
- **Security Advisory → Ask AI** ("How many assets are impacted by a security advisory, excluding the potentially affected assets."): **1,061 assets**.

Both are customer-facing answers to "impacted assets". The 49-asset gap erodes trust regardless of which figure is technically correct. This ticket reconciles them.

> **Note on screenshots.** The "250 results" visible on the Security Advisories page is the **number of advisories**, not assets — separate concept, not the source of either number under investigation here.

## Trace
- **Trace ID:** `019e25c8-aeec-7952-ac70-5a7e7065b1d4`
- **Workspace:** cx-iq-prod (Semantic Router → routed to *Assessments – Security Advisories*)
- **Agent:** Security Advisory
- **Tenant:** Prod Testing - US (same user/tenant in both screenshots)
- **Date:** 2026-05-14

## The two surfaces side by side

### Surface A — Assets → Inventory (UI), "Affected by security advisories" filter
- Path: **Assets → Inventory**.
- Filters applied (chip shows "Filters (2)"):
  - **Affected by security advisories** = true
  - **Equipment type** = `chassis`
- Result count: **1,110 assets**.
- **Removing the `equipment_type = chassis` filter does not reconcile the gap** — the Inventory count still differs from the agent's 1,061 (and is ≥ 1,110). The chassis filter is therefore not the source of the discrepancy; the "Affected by security advisories" predicate itself is defined differently between the two surfaces.
- Each row is an asset; the **Security Advisories** column shows the per-asset advisory count (14, 34, 34, …).
- Screenshot: [asset-results-ui.png](triage/security_advisory/data-mismatch/asset-results-ui.png)

### Surface B — Security Advisory → Ask AI
- Question: *"How many assets are impacted by a security advisory, excluding the potentially affected assets."*
- Answer: *"There are 1,061 assets impacted by security advisories, excluding those marked as only potentially affected. Impacted Assets: 1,061 (`vulnerability_status = "VUL"`)"*.
- Screenshot: [security-results-ai.png](triage/security_advisory/data-mismatch/security-results-ai.png)
- SQL emitted (raw fallback via `mcp_execute_sql`):
   ```sql
   SELECT COUNT(DISTINCT assets.serial_number) AS impacted_assets_count
   FROM postgresql.public.cvi_assets_view_1__3__5 AS assets
   INNER JOIN postgresql.public.cvi_psirts_view_1__3__7 AS psirts
     ON assets.serial_number = psirts.serial_number
   WHERE psirts.vulnerability_status = 'VUL';
   ```
   → `1,061`.

The agent's SQL is internally consistent with the schema (`vulnerability_status` enum is `["VUL","POTVUL"]`, join on `serial_number`, `COUNT(DISTINCT)` for de-dup) — but it is computing **a different thing** than the Inventory filter, and possibly against a different view than the Inventory backend.

> **The chassis filter is not the cause.** The user confirmed that removing `equipment_type = chassis` from the Inventory filter does not bring the Inventory count down to 1,061 — the gap persists. The discrepancy lives in how each surface defines "affected by a security advisory" (predicate / source view), not in equipment-type scoping.

## Action items

1. **Confirm the table** the `Assets → Inventory` page reads from when the "Affected by security advisories" filter is applied.
2. **Confirm the SQL query** that page emits to produce the 1,110 count.
3. **Diff** that query against the AI agent's SQL (below) and report where they differ — table, predicate, joins, filters.

### AI agent SQL (for the diff)
```sql
SELECT COUNT(DISTINCT assets.serial_number) AS impacted_assets_count
FROM postgresql.public.cvi_assets_view_1__3__5 AS assets
INNER JOIN postgresql.public.cvi_psirts_view_1__3__7 AS psirts
  ON assets.serial_number = psirts.serial_number
WHERE psirts.vulnerability_status = 'VUL';
```

## Related (separate tickets)

The same trace exposed two unrelated agent issues, kept here as a pointer:
- `mcp_build_sql_by_domain` column-prefix validator false-positive on aggregate expressions (e.g. `COUNT(DISTINCT assets.serial_number)` parsed as table alias `count(distinct assets`). Forces fallback to raw `mcp_execute_sql`.
- The agent retried the identical failing `build_sql_by_domain` payload before falling back. The loop should short-circuit identical-args retries.
