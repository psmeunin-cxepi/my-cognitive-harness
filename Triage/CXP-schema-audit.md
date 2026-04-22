# Schema Quality Audit: `security_advisory` Domain

**Source file:** `text2sql_mcp/schema_advisory.py` (CXEPI/risk-app, main branch)  
**Schema assembler:** `text2sql_mcp/server.py` → `_get_schema_for_domain("security_advisory")`  
**Trace ID:** `019db47d-5e25-7a40-8e88-887392a1db1b`  
**Date:** 2026-04-22

**Related:** [CXP-system-schema.md](CXP-system-schema.md) — system prompt gap analysis | [CXP-triage.md](CXP-triage.md) — alias & data accuracy triage

---

## Purpose

This audit evaluates the schema returned by `mcp_get_table_schema` for the `security_advisory` domain from the **LLM's perspective**. Every description, note, relationship, and example filter is context the agent uses to construct SQL. Low-quality descriptions lead to incorrect queries, missed filters, and wrong results.

---

## Schema Structure Overview

The response contains:
- **3 tables**: `assets` (39 columns), `psirts` (10 columns), `bulletins` (11 columns)
- **2 relationships**: `assets_psirts`, `psirts_bulletins`
- **7 notes**
- **2 example_filters**
- **Top-level duplication**: `columns` and `column_schema` at root level repeat the `assets` table (backward compatibility)

---

## Column Description Audit

### Severity: HIGH — descriptions that caused or can cause incorrect SQL

| # | Table | Column | Current Description | Problem | Proposed Description |
|---|-------|--------|-------------------|---------|---------------------|
| H1 | psirts | `vulnerability_status` | `"Vulnerability assessment status."` | **Too vague.** Doesn't explain what VUL and POTVUL mean in business terms. The LLM failed to split counts by this column in the traced run because it didn't understand the business semantics. Root cause of the data accuracy bug. | `"Vulnerability assessment status. VUL = confirmed vulnerable (maps to UI 'Affected Assets'). POTVUL = potentially vulnerable, manual verification required (maps to UI 'Potentially Affected Assets'). When counting impacted assets, MUST split or filter on this column."` |
| H2 | psirts | `vulnerability_reason` | `"Reason why record is flagged vulnerable/potentially vulnerable."` | Doesn't explain the **mapping** between reason values and status values. The LLM sees both columns but has no explicit link: `"Match on SW Type, SW Version"` → VUL, `"...Manual Verification Required"` → POTVUL. | `"Why the record was flagged. 'Match on SW Type, SW Version' corresponds to VUL (confirmed). 'Match on SW Type, SW Version; Manual Verification Required' corresponds to POTVUL (potentially vulnerable)."` |
| H3 | assets | `advisory_count` | `"Per-device number of advisories. Do NOT SUM across rows to count total distinct advisories (double-counts)."` | **Ambiguous scope.** "advisories" — which advisory statuses does this count? All? Only VUL? Only security? The LLM cannot decide whether to use this vs. `security_advisories_count` vs. `affected_security_advisories_count`. | `"Per-device count of ALL advisories (all types, all statuses) affecting this asset. Includes security, field notices, etc. Do NOT SUM across rows — double-counts advisories shared across devices. For total distinct advisory count, JOIN psirts and use COUNT_DISTINCT on psirt_id."` |
| H4 | assets | `all_advisory_count` | `"Per-device total advisory count including all statuses. Do NOT SUM across rows to count total distinct advisories (double-counts)."` | **Nearly identical to `advisory_count`.** The LLM cannot tell these apart. What's the difference? If they're the same, one should be removed or deprecated. | `Clarify the distinction from advisory_count, or mark as deprecated/alias.` |
| H5 | assets | `security_advisories_count` | `"Per-device security advisories count. Do NOT SUM across rows to count total distinct advisories (double-counts)."` | Same problem — how does this relate to `affected_security_advisories_count`? Is this VUL + POTVUL combined? | `"Per-device count of security advisories (VUL + POTVUL combined). For affected-only, use affected_security_advisories_count. Do NOT SUM across rows."` |
| H6 | assets | `critical_security_advisories_count` | `"Per-device count of critical severity advisories. Do NOT SUM across rows to count total distinct advisories (double-counts). JOIN to psirts and use COUNT_DISTINCT on psirt_id instead."` | **Contradictory instruction.** It says "don't SUM" but also says "JOIN to psirts and use COUNT_DISTINCT" — but that sentence is about getting *total* distinct critical advisories, not per-device. The LLM may think this column should never be used. | `"Per-device count of Critical severity advisories. Use for per-device filtering only (e.g., WHERE critical_security_advisories_count > 0). To count total distinct Critical advisories across all devices, do NOT SUM this column — instead JOIN psirts → bulletins and use COUNT_DISTINCT(psirts.psirt_id) WHERE bulletins.severity_level_name = 'Critical'."` |
| H7 | assets | `high_security_advisories_count` | Same as H6 | Same issue as H6. | Same fix as H6, adapted for High severity. |

### Severity: MEDIUM — descriptions that are sparse or ambiguous

| # | Table | Column | Current Description | Problem | Proposed Description |
|---|-------|--------|-------------------|---------|---------------------|
| M1 | assets | `cx_level` | `"CX level."` | **Tautological.** Restates the column name. LLM has no idea what CX levels exist or what they mean. | `"Customer experience level classification (e.g., 'Essentials', 'Advantage', 'Premier'). Indicates the customer's CX service tier."` *(verify actual values)* |
| M2 | assets | `cx_level_label` | `"CX level label."` | Same problem. How does it differ from `cx_level`? | `"Human-readable label for the CX level. Use this for display; use cx_level for filtering."` |
| M3 | assets | `asset_type` | `"Type of asset (e.g., Hardware)."` | Only one example. Are there other values? Software? Virtual? | `"Type of asset. Known values: 'Hardware', [list other values]. Use for filtering device vs. non-device assets."` |
| M4 | assets | `role` | `"Asset role."` | Completely opaque. What roles exist? Is this "Core Router", "Access Switch"? | Add enum_values or examples. `"Functional role of the asset in the network (e.g., ...)."` |
| M5 | assets | `equipment_type` | `"Equipment type."` | Same as M4 — tautological. | Add enum_values or examples. |
| M6 | assets | `product_type` | `"Product type classification."` | No examples, no enum. How does this differ from `product_family`? | Clarify relationship to `product_family` and add examples. |
| M7 | assets | `tags` | `"Tags associated with the asset."` | Type is `"array|string"` — ambiguous. Can the LLM use `= 'tag'` or must it use `LIKE` or `array_contains()`? | `"Tags associated with the asset (stored as VARCHAR). Use LIKE '%tagname%' for filtering."` *(verify actual Trino type and query pattern)* |
| M8 | psirts | `partition_key` | `"Internal partition/hash key for storage."` | **Should the LLM ever use this?** If it's internal infrastructure, it shouldn't be in the schema at all, or it should be explicitly marked as "Do not use in queries." | `"Internal storage partition key. Do NOT use in queries — this is infrastructure metadata."` Or remove from schema. |
| M9 | psirts | `platform_account_id` | `"Customer/platform account identifier."` | Not marked as a required filter despite note #7 mentioning tenant-safe lookups. | `"Customer/platform account identifier. Required for tenant-scoped queries — always include in WHERE clause when provided in context."` |
| M10 | assets | `product_version_id` | `"Product version identifier."` | How does this relate to `software_version`? Is this a hardware version? | Clarify distinction. |
| M11 | bulletins | `publish_date` | `"Date the advisory was first published (ISO 8601)."` | Type is `"string"`, not `"timestamp"`. The LLM needs to know: can it use `>`, `<` comparisons? Does it need `CAST()`? | `"Date the advisory was first published (ISO 8601 string, e.g. '2024-03-15'). Stored as VARCHAR — use string comparison or CAST to timestamp for date range filters."` |
| M12 | bulletins | `revised_date` | `"Date the advisory was last revised (ISO 8601)."` | Same issue as M11 — string type, not timestamp. | Same fix as M11. |
| M13 | bulletins | `alert_status_cd` | `"Alert status code (e.g. 'ACTIVE')."` | Only one example. What other statuses exist? Can the LLM assume all bulletins are ACTIVE? | Add enum_values. `"Alert status code. Known values: 'ACTIVE', [list others]. Typically filter WHERE alert_status_cd = 'ACTIVE' for current advisories."` |
| M14 | bulletins | `cvss_score` | `"CVSS base score."` | No range info. Is this 0-10? CVSS v2 or v3? | `"CVSS base score (0.0–10.0). Higher = more severe. Use for ranking advisories by severity score."` |

### Severity: LOW — minor but fixable

| # | Table | Column | Current Description | Problem |
|---|-------|--------|-------------------|---------|
| L1 | assets | `parent_id` | `"Parent asset identifier."` | What does "parent" mean? Chassis → blade? No info on hierarchy. |
| L2 | assets | `quantity` | `"Asset quantity."` | Quantity of what? Instances of this asset? Licenses? |
| L3 | assets | `created_by` / `updated_by` | `"Created by user."` / `"Updated by user."` | User-facing or system user? Should the LLM ever query these? |
| L4 | assets | `created_at` vs `created_date` | Two creation timestamps | What's the difference? Which should the LLM prefer? |
| L5 | assets | `last_update_date` vs `updated_at` | Two update timestamps | Same problem as L4. |
| L6 | psirts | `serial_number` | `"Asset serial number."` | Should say `"Asset serial number (join key to assets table)."` to mirror the assets description. |
| L7 | psirts | `psirt_id` | `"Cisco PSIRT advisory identifier."` | Missing the `"join key to bulletins"` hint that the bulletins version of psirt_id has. |

---

## Notes Audit

| # | Current Note | Assessment | Issue |
|---|-------------|------------|-------|
| N1 | `"Primary table is 'assets' (cvi_assets_view). JOIN psirts on serial_number for vulnerability data."` | **Good** — clear and actionable | None |
| N2 | `"JOIN bulletins on psirt_id when filtering or enriching with PSIRT bulletin-level data."` | **Good** | Could specify: "JOIN psirts to bulletins" (not assets to bulletins) |
| N3 | `"Use psirts.vulnerability_status (VUL/POTVUL) to filter vulnerable assets."` | **Weak** — reads as a hint, not a rule | Doesn't say WHEN this is mandatory. Should state: "When counting affected/impacted assets, you MUST filter or split on this column." See H1. |
| N4 | `"Use assets advisory count fields ... NEVER use SUM() ... JOIN to psirts and use COUNT_DISTINCT on psirts.psirt_id."` | **Good** — strong language, clear prohibition | Long but effective. The only note with MUST-level language. |
| N5 | `"The severity column on bulletins is 'severity_level_name' ... There is NO column called 'severity'"` | **Good** — prevents a common hallucination | This is a model of what defensive descriptions should look like. |
| N6 | `"To count advisories broken down by severity: use COUNT_DISTINCT on psirts.psirt_id with GROUP BY bulletins.severity_level_name..."` | **Good** — prescriptive SQL pattern | Could add a concrete example query fragment. |
| N7 | `"Prefer platform_account_id and/or serial_number filters for tenant-safe lookups."` | **Weak** — "Prefer" is not strong enough for tenant isolation | Should say "MUST include platform_account_id in WHERE clause when provided in user context" for data isolation compliance. |

### Missing Notes

| # | Missing Rule | Why It Matters |
|---|-------------|---------------|
| MN1 | **When counting impacted assets, always split by `vulnerability_status`.** | Root cause of the data accuracy bug in this trace. Note N3 hints at filtering but doesn't cover aggregation. |
| MN2 | **Column name aliasing guidance.** | The LLM chose `impacted_assets_count` as an alias. While valid SQL, the schema could suggest standard alias conventions (e.g., `affected_asset_count`, `potentially_affected_asset_count`) to improve consistency with the UI. |
| MN3 | **When to use `assets.*_count` columns vs. JOIN + COUNT_DISTINCT.** | Note N4 says don't SUM the count columns, but doesn't give explicit decision criteria: "For per-device thresholds → use count columns. For aggregate totals → JOIN + COUNT_DISTINCT." |
| MN4 | **Trino SQL dialect notes.** | The schema never mentions the SQL engine is Trino. This matters because Trino has specific function names (e.g., `APPROX_DISTINCT`, `TRY_CAST`, no `ILIKE` support in some connectors). |

---

## Relationships Audit

| # | Relationship | Assessment | Issue |
|---|-------------|------------|-------|
| R1 | `assets_psirts`: assets.serial_number → psirts.serial_number (1:*) | **Good** — clear, correct cardinality | Description could add: "One asset can appear in multiple PSIRT advisories" |
| R2 | `psirts_bulletins`: psirts.psirt_id → bulletins.psirt_id (*:1) | **Good** — correct | Description could add: "Multiple devices can be affected by the same bulletin" |

### Missing

| # | Missing Relationship | Impact |
|---|---------------------|--------|
| MR1 | **No transitive relationship `assets → bulletins`** | The LLM must infer it needs TWO JOINs (assets → psirts → bulletins). A note or explicit 3-way relationship would help. |

---

## Example Filters Audit

| # | Current Example | Assessment | Issue |
|---|----------------|------------|-------|
| E1 | `psirts.vulnerability_status = 'VUL'` | **Incomplete** — only shows VUL | Should include a POTVUL example too, and ideally a combined example using CASE WHEN for the count split. |
| E2 | `assets.affected_security_advisories_count > 0` | **Good** — shows per-device threshold pattern | None |

### Missing Examples

| # | Missing Example | Why |
|---|----------------|-----|
| ME1 | `bulletins.severity_level_name = 'Critical'` | Common query pattern — not shown. |
| ME2 | `bulletins.cve_id LIKE '%CVE-2024-12345%'` | The column description says to use LIKE, but no example_filter demonstrates it. |
| ME3 | Date range filter on `publish_date` | Common use case — "advisories published in last 90 days". Shows the string-to-date casting pattern. |
| ME4 | `psirts.vulnerability_status IN ('VUL', 'POTVUL')` with GROUP BY for count split | Directly prevents the data accuracy bug. |

---

## Structural Issues

### S1: Top-level schema duplication

The response includes `columns` and `column_schema` at the root level (duplicating the `assets` table) AND inside `tables.assets`. This means the LLM receives the assets column list **three times** (root `columns`, root `column_schema`, `tables.assets.columns` + `tables.assets.column_schema`). This wastes ~2,500 tokens per schema call and may confuse the LLM about which is the "primary" schema.

**Recommendation:** Remove root-level `columns` and `column_schema` or add a note: "Root-level columns/column_schema refer to the primary table (assets). Use the `tables` object for multi-table queries."

### S2: No column_schema for `psirts` and `bulletins` at root level

While duplication is bad, the asymmetry may confuse the LLM — assets get top-level promotion, psirts and bulletins don't. The LLM must know to look inside `tables.psirts.column_schema` and `tables.bulletins.column_schema`.

### S3: `partition_key` exposed but useless

`psirts.partition_key` is an internal storage key with no query value. It adds noise to the schema. Either remove it or explicitly mark it as non-queryable (see M8).

### S4: No schema-level metadata

The response has no `version`, `last_updated`, or `description` field. Adding a top-level description like `"Security advisory domain: PSIRT vulnerability records for customer assets, with bulletin details and severity classifications"` would help the LLM understand the domain context before reading columns.

---

## Priority Summary

### Must fix (caused actual bugs)

1. **H1** — `vulnerability_status` description → root cause of data accuracy bug
2. **N3** → strengthen to mandatory aggregation rule
3. **MN1** → add missing note for count-split requirement

### Should fix (high risk of future bugs)

4. **H3–H7** — advisory count column descriptions → disambiguate the count family
5. **N7** → strengthen tenant isolation from "prefer" to "MUST"
6. **H2** — `vulnerability_reason` → add status mapping
7. **ME4** → add example filter for the count-split pattern
8. **M11–M12** — `publish_date`/`revised_date` type mismatch guidance

### Nice to have (reduce noise, improve clarity)

9. **S1** — remove root-level duplication
10. **S3** — remove or mark `partition_key`
11. **M1–M6** — enrich tautological descriptions
12. **MN4** — add Trino dialect note
13. **S4** — add schema-level metadata
