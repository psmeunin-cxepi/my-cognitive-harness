> **Agent:** Security Advisory | **Repo:** [`CXEPI/risk-app`](https://github.com/CXEPI/risk-app)

# Schema Quality Audit: `security_advisory` Domain

**Source file:** `text2sql_mcp/schema_advisory.py` (CXEPI/risk-app, main branch)  
**Schema assembler:** `text2sql_mcp/server.py` → `_get_schema_for_domain("security_advisory")`  
**Trace ID:** `019db47d-5e25-7a40-8e88-887392a1db1b`  
**Date:** 2026-04-22

**Related:** [CXP-system-schema.md](CXP-system-schema.md) — system prompt gap analysis | [CXP-triage.md](CXP-triage.md) — alias & data accuracy triage

---

## Purpose

This audit flags column descriptions, notes, relationships, and example filters that need review with the **dataset owners**. Each item is evaluated from the **LLM/agent perspective**: the description is the only context the agent has to understand a column's meaning and decide how to use it in SQL. Flagged items are ones where the current description is insufficient for the agent to make correct decisions.

No proposed descriptions are included — the correct answers must come from whoever owns the data.

---

## Schema Overview

- **3 tables**: `assets` (39 columns), `psirts` (10 columns), `bulletins` (11 columns)
- **2 relationships**: `assets_psirts`, `psirts_bulletins`
- **7 notes** (in `server.py`)
- **2 example_filters** (in `server.py`)

---

## `ADVISORY_COLUMN_SCHEMA` — psirts table (10 columns)

### Flagged

| # | Column | Current Description | Why it needs review |
|---|--------|-------------------|-------------------|
| 1 | `vulnerability_status` | `"Vulnerability assessment status."` | **Caused a data accuracy bug.** The enum values `VUL` and `POTVUL` are listed but their business meaning is not explained. The agent doesn't know what each status represents, when to filter on them, or that the UI maps these to separate "Affected Assets" and "Potentially Affected Assets" columns. The agent constructed a bare `COUNT` without filtering on this column. |
| 2 | `partition_key` | `"Internal partition/hash key for storage."` | The description says "internal" but doesn't tell the agent whether it should ever use this column in queries. If it's infrastructure-only, it shouldn't be in the schema, or it needs an explicit "do not use in queries" instruction. As-is, the agent may include it in SELECT or WHERE clauses. |
| 3 | `platform_account_id` | `"Customer/platform account identifier."` | Note #7 says "Prefer platform_account_id ... for tenant-safe lookups" but the column description itself has no indication this is a tenant isolation key. Need to clarify: is this required for data isolation? When should the agent include it? |
| 4 | `psirt_id` | `"Cisco PSIRT advisory identifier."` | Missing join-key context. The `bulletins` version of this column says "join key to psirts table" but this version doesn't say "join key to bulletins table." Asymmetric descriptions for the same join key. |
| 5 | `serial_number` | `"Asset serial number."` | Same asymmetry — the `assets` version says "join key to psirts" but this version doesn't say "join key to assets." |

### OK — no review needed

| Column | Description | Why it's fine |
|--------|------------|---------------|
| `vulnerability_reason` | `"Reason why record is flagged vulnerable/potentially vulnerable."` | Clear — has enum_values and examples. |
| `product_family` | `"Cisco product family name."` | Clear, has examples. |
| `software_version` | `"Detected software version on the asset."` | Clear, has examples. |
| `updated_at` | `"Last refresh timestamp for this match record."` | Clear, has examples. |
| `product_id` | `"Cisco PID/model identifier."` | Clear, has examples. |

---

## `ADVISORY_ASSETS_COLUMN_SCHEMA` — assets table (39 columns)

### Flagged

| # | Column | Current Description | Why it needs review |
|---|--------|-------------------|-------------------|
| 6 | `advisory_count` | `"Per-device number of advisories. Do NOT SUM across rows..."` | **Unclear scope.** "Advisories" — which types? Which statuses? The agent cannot distinguish this from `all_advisory_count` or `security_advisories_count`. |
| 7 | `all_advisory_count` | `"Per-device total advisory count including all statuses..."` | **Indistinguishable from `advisory_count`.** Both say "per-device" and "all." What's the actual difference? If there is none, one should be removed or marked as deprecated. |
| 8 | `security_advisories_count` | `"Per-device security advisories count..."` | **Unclear relationship to siblings.** Is this VUL + POTVUL combined? Is it the sum of `affected_security_advisories_count` + `potentially_affected_security_advisories_count`? The agent cannot determine the hierarchy of these count columns. |
| 9 | `affected_security_advisories_count` | `"Per-device count of advisories where asset is affected..."` | Does "affected" correspond to `vulnerability_status = 'VUL'`? The description doesn't say. The agent has to guess the mapping. |
| 10 | `potentially_affected_security_advisories_count` | `"Per-device count of advisories where asset is potentially affected..."` | Same question — does "potentially affected" correspond to `vulnerability_status = 'POTVUL'`? No explicit link. |
| 11 | `critical_security_advisories_count` | `"Per-device count of critical severity advisories. Do NOT SUM... JOIN to psirts and use COUNT_DISTINCT on psirt_id instead."` | **Contradictory.** The description prohibits SUM and then immediately says to JOIN + COUNT_DISTINCT — but that's an alternative approach for aggregate totals, not a replacement for this column. The agent may conclude this column should never be used. Need to clarify: when is this column appropriate (per-device filtering) vs. when to use the JOIN approach (aggregate totals)? |
| 12 | `high_security_advisories_count` | Same as #11 | Same contradiction. |
| 13 | `cx_level` | `"CX level."` | **Tautological.** Restates the column name. No enum_values, no examples. The agent has zero context for what CX levels exist or what they represent. |
| 14 | `cx_level_label` | `"CX level label."` | Same problem. Also unclear how it differs from `cx_level` — is one a code and the other a display name? |
| 15 | `asset_type` | `"Type of asset (e.g., Hardware)."` | Only one example value. What other types exist? Without enum_values the agent cannot construct correct filters for non-hardware assets. |
| 16 | `role` | `"Asset role."` | Tautological. No enum_values, no examples. The agent doesn't know what roles exist in the data. |
| 17 | `equipment_type` | `"Equipment type."` | Same — tautological, no enum_values, no examples. |
| 18 | `product_type` | `"Product type classification."` | No enum_values or examples. Also unclear how it relates to `product_family` — the agent sees both and can't determine which to use for different queries. |
| 19 | `product_version_id` | `"Product version identifier."` | Unclear relationship to `software_version`. Is this a hardware version? A product revision? |
| 20 | `tags` | `"Tags associated with the asset."` | Type is `"array|string"` — ambiguous. The agent doesn't know the actual Trino storage type or the correct query pattern (`=`, `LIKE`, `array_contains()`). |
| 21 | `quantity` | `"Asset quantity."` | Quantity of what? Instances? Units? Licenses? |
| 22 | `parent_id` | `"Parent asset identifier."` | What constitutes a parent/child relationship? Chassis → blade? Stack → member? The agent has no hierarchy context. |
| 23 | `created_at` vs `created_date` | `"Asset record creation timestamp."` / `"Asset created date."` | Two creation timestamp columns with nearly identical descriptions. Which should the agent use? Is one the record-creation time and the other the asset-onboarding time? |
| 24 | `updated_at` vs `last_update_date` | `"Asset record last updated timestamp."` / `"Last update date."` | Same problem — two update timestamps, no guidance on which to prefer. |
| 25 | `created_by` / `updated_by` | `"Created by user."` / `"Updated by user."` | Is this a human user or a system process? Should the agent ever query on these? |
| 26 | `platform_account_id` | `"Customer/platform account identifier."` | Same issue as psirts #3 — no indication this is a tenant isolation key. |

### OK — no review needed

| Column | Description | Why it's fine |
|--------|------------|---------------|
| `id` | `"Asset unique identifier."` | Clear. |
| `instance_id` | `"Asset instance identifier."` | Clear. |
| `serial_number` | `"Device serial number (join key to psirts)."` | Good — includes join-key context. |
| `product_family` | `"Cisco product family."` | Clear. |
| `product_id` | `"Cisco PID/model identifier."` | Clear. |
| `product_name` | `"Product name."` | Clear. |
| `product_description` | `"Product description."` | Clear. |
| `hostname` | `"Device hostname."` | Clear. |
| `ip_address` | `"Device IP address."` | Clear. |
| `software_version` | `"Software/OS version."` | Clear. |
| `software_type` | `"Software type."` | Acceptable. |
| `software_patch_version` | `"Software patch version."` | Clear. |
| `last_scan` | `"Last scan timestamp."` | Clear. |
| `last_signal_date` | `"Last telemetry signal date."` | Clear. |
| `last_signal_type` | `"Type of last telemetry signal."` | Clear. |

---

## `ADVISORY_PSIRT_BULLETINS_COLUMN_SCHEMA` — bulletins table (11 columns)

### Flagged

| # | Column | Current Description | Why it needs review |
|---|--------|-------------------|-------------------|
| 27 | `publish_date` | `"Date the advisory was first published (ISO 8601)."` | Type is `"string"`, not `"timestamp"`. The agent doesn't know whether it can use `>`, `<` comparisons directly or needs `CAST()` for date range queries. |
| 28 | `revised_date` | `"Date the advisory was last revised (ISO 8601)."` | Same issue — string type with no query pattern guidance. |
| 29 | `alert_status_cd` | `"Alert status code (e.g. 'ACTIVE')."` | Only one example value. What other statuses exist? Should the agent default to filtering `WHERE alert_status_cd = 'ACTIVE'`? Without enum_values the agent may return inactive/revoked advisories. |
| 30 | `cvss_score` | `"CVSS base score."` | No range or version info. Is this 0–10? CVSS v2 or v3? The agent cannot make informed severity-threshold decisions. |

### OK — no review needed

| Column | Description | Why it's fine |
|--------|------------|---------------|
| `psirt_id` | `"Cisco PSIRT advisory identifier (join key to psirts table)..."` | Good — includes join-key context and checkID mapping. |
| `advisory_id` | `"Cisco advisory ID string (e.g. 'cisco-sa-20060118-sgbp')."` | Clear with example. |
| `severity_level_name` | `"Severity level of the advisory... Use this column — NOT 'severity'..."` | Strong defensive description — model for how to prevent hallucination. |
| `headline_name` | `"Short headline / title of the PSIRT bulletin."` | Clear. |
| `summary_text` | `"Summary description of the advisory."` | Clear. |
| `cve_id` | `"CVE identifier(s)... Use LIKE '%CVE-xxxx-xxxxx%' instead of =..."` | Good — includes query pattern guidance for comma-separated values. |
| `psirt_url_text` | `"URL to the full Cisco PSIRT advisory page."` | Clear. |

---

## Notes Audit (from `server.py`)

| # | Note | Flag | Why |
|---|------|------|-----|
| N1 | `"Primary table is 'assets'... JOIN psirts on serial_number..."` | OK | Clear and actionable. |
| N2 | `"JOIN bulletins on psirt_id when filtering or enriching..."` | OK | Clear. Could specify "JOIN psirts to bulletins" to avoid ambiguity about which tables to join. |
| N3 | `"Use psirts.vulnerability_status (VUL/POTVUL) to filter vulnerable assets."` | **Flag** | Reads as a suggestion, not a rule. Doesn't say this is mandatory for aggregation queries. The agent ignored this note in the traced run and produced incorrect counts. Needs strengthening — see [CXP-triage.md](CXP-triage.md#fix-recommendations). |
| N4 | `"Use assets advisory count fields... NEVER use SUM()..."` | OK | Strong language, clear prohibition. Effective. |
| N5 | `"The severity column on bulletins is 'severity_level_name'... There is NO column called 'severity'..."` | OK | Excellent defensive note — prevents a common hallucination. |
| N6 | `"To count advisories broken down by severity..."` | OK | Prescriptive SQL pattern. |
| N7 | `"Prefer platform_account_id and/or serial_number filters for tenant-safe lookups."` | **Flag** | "Prefer" is too weak for tenant data isolation. If this is a data security requirement, it should use mandatory language. |

### Missing notes

| # | Gap | Why it matters |
|---|-----|---------------|
| MN1 | No rule for splitting counts by `vulnerability_status` during aggregation | Root cause of the data accuracy bug. Note N3 covers filtering but not the aggregation case. |
| MN2 | No guidance on when to use `assets.*_count` columns vs. JOIN + COUNT_DISTINCT | Note N4 says "don't SUM" but doesn't give the decision criteria: when is the count column appropriate vs. the JOIN approach. |

---

## Relationships Audit

| # | Relationship | Flag | Why |
|---|-------------|------|-----|
| R1 | `assets_psirts` (1:*) | OK | Clear, correct cardinality. |
| R2 | `psirts_bulletins` (*:1) | OK | Clear, correct cardinality. |

---

## Example Filters Audit

| # | Example | Flag | Why |
|---|---------|------|-----|
| E1 | `psirts.vulnerability_status = 'VUL'` | **Flag** | Only shows VUL. Missing POTVUL example and the aggregation split pattern (CASE WHEN / GROUP BY). |
| E2 | `assets.affected_security_advisories_count > 0` | OK | Good per-device threshold pattern. |

---

## Summary — items for data owner review

**30 flagged items** across 3 tables, notes, and examples.

### By category

| Category | Count | Key items |
|----------|-------|-----------|
| **Missing business meaning** | 3 | #1 (`vulnerability_status`), #9 (`affected_...count`), #10 (`potentially_affected_...count`) |
| **Indistinguishable columns** | 4 | #6/#7 (`advisory_count` vs `all_advisory_count`), #23 (`created_at` vs `created_date`), #24 (`updated_at` vs `last_update_date`) |
| **Missing enum_values** | 6 | #13 (`cx_level`), #15 (`asset_type`), #16 (`role`), #17 (`equipment_type`), #18 (`product_type`), #29 (`alert_status_cd`) |
| **Contradictory instructions** | 2 | #11 (`critical_...count`), #12 (`high_...count`) |
| **Ambiguous type/query pattern** | 3 | #20 (`tags`), #27 (`publish_date`), #28 (`revised_date`) |
| **Unclear scope** | 3 | #8 (`security_advisories_count`), #21 (`quantity`), #22 (`parent_id`) |
| **Missing tenant isolation guidance** | 2 | #3/#26 (`platform_account_id`) |
| **Weak notes** | 2 | N3 (vulnerability filtering), N7 (tenant isolation) |
| **Internal column exposed** | 1 | #2 (`partition_key`) |
| **Asymmetric join-key labels** | 2 | #4 (`psirt_id`), #5 (`serial_number`) |
| **Missing info** | 3 | #19 (`product_version_id` vs `software_version`), #25 (`created_by`/`updated_by`), #30 (`cvss_score`) |
