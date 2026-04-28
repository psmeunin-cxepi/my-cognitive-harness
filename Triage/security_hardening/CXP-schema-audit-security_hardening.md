> **Agent:** Security Hardening
> **Repo:** [`CXEPI/risk-app`](https://github.com/CXEPI/risk-app)
> **Jira:** _to be created_

# Schema Quality Audit: `security_hardening` Domain

**Source file:** `text2sql_mcp/schema_hardening.py` (CXEPI/risk-app, main branch)  
**Schema assembler:** `text2sql_mcp/server.py` → `_get_schema_for_domain("security_hardening")`  
**Date:** 2026-04-22

---

## Purpose

This audit flags column descriptions, notes, relationships, and example filters that need review with the **dataset owners**. Each item is evaluated from the **LLM/agent perspective**: the description is the only context the agent has to understand a column's meaning and decide how to use it in SQL. Flagged items are ones where the current description is insufficient for the agent to make correct decisions.

No proposed descriptions are included — the correct answers must come from whoever owns the data.

---

## Schema Overview

- **2 tables**: `finding` (33 columns), `assessment` (14 columns)
- **1 relationship**: `finding_assessment`
- **5 notes** (in `server.py`)
- **2 example_filters** (in `server.py`)
- **Top-level duplication**: `columns` and `column_schema` at root level repeat the `finding` table (backward compatibility)

---

## `HARDENING_COLUMN_SCHEMA` — finding table (33 columns)

### Flagged

| # | Column | Current Description | Why it needs review |
|---|--------|-------------------|-------------------|
| 1 | `source` | `"Rule/source identifier."` | **Identical meaning to `source_id`.** The `source_id` description is `"Rule/source identifier (duplicate logical key)."` — it even admits it's a duplicate. The agent cannot determine when to use `source` vs `source_id`, or whether they always contain the same value. Clarify: are these always equal? Should one be removed? |
| 2 | `source_id` | `"Rule/source identifier (duplicate logical key)."` | See #1. The parenthetical "(duplicate logical key)" is an internal code comment, not useful context for the agent. If these are truly the same, mark one as deprecated; if they differ, explain how. |
| 3 | `finding_type` | `"Finding kind (finding/ok/not_applicable/etc.)."` | Lists some values but uses "etc." — the agent doesn't know the full set. Should have `enum_values` like `["finding", "ok", "not_applicable", ...]`. Also: what does each value mean? Is `"finding"` = violation found? Is `"ok"` = compliant? |
| 4 | `finding_status` | `"Result status (VIOLATED/NOT_VIOLATED/MISSING_INFO/etc.)."` | Same "etc." problem — the agent doesn't know all possible statuses. Also: what is the relationship between `finding_type` and `finding_status`? Can a `finding_type = "ok"` have `finding_status = "VIOLATED"`? The agent sees two status-like columns with overlapping semantics and no guidance on which to use for what. |
| 5 | `severity` | `"Severity classification (HIGH/MEDIUM/UNKNOWN/etc.)."` | "etc." again. What are all the values? Is there a `LOW`? A `CRITICAL`? The example_filter uses `IN ('HIGH', 'MEDIUM')` — does that cover all non-trivial severities? Without `enum_values` the agent may miss severity levels or construct incomplete filters. |
| 6 | `finding_description` | `"Description payload (may be plain text or serialized JSON list)."` | Type is `"string|json|null"`. The agent doesn't know: can it use this in a WHERE clause with LIKE? Does it need JSON parsing? If it's sometimes JSON, what's the structure? This is important because the agent might try to search or filter on finding descriptions. |
| 7 | `evidence_log` | `"Evidence payload with extracted telemetry artifacts."` | Type is `"json|string"`. Same problem as #6 — the agent doesn't know the structure, can't query it, and has no guidance on whether to use it. Should it ever be in a SELECT? Can it be filtered? |
| 8 | `reference_urls` | `"Reference URLs payload."` | Type is `"string|json|null"`. No guidance on format or queryability. |
| 9 | `ic_type` | `"Implementation-check type when available."` | "When available" suggests it's often null. No enum_values or examples. The agent has no idea what IC types exist. |
| 10 | `ic_description` | `"Implementation-check description."` | No examples. When is this populated vs null? What does it contain? |
| 11 | `asset_type` | `"Asset class (for example Hardware)."` | Only one example. What other asset classes exist in the hardening domain? Same gap as the advisory schema. |
| 12 | `technology` | `"Technology tag if available."` | "If available" = often null. No examples or enum_values. What technologies are tagged? (e.g., "routing", "switching", "wireless"?) |
| 13 | `functional_category` | `"Functional category metadata."` | **Tautological.** "Functional category" is just the column name restated. No examples, no enum_values. The agent cannot use this for filtering without knowing what categories exist. |
| 14 | `assessment_category` | `"Assessment category metadata."` | Same problem — tautological, no examples. Also: this appears in both the `finding` and `assessment` tables. Are they always the same for related records? |
| 15 | `architecture` | `"Architecture metadata."` | Tautological. No examples or enum_values. What architectures are tracked? |
| 16 | `platform_account_id` | `"Platform account identifier."` | No indication this is a tenant isolation key. Note #1 mentions `asset_key/source_id` for lookups but doesn't mention `platform_account_id`. Should the agent always filter on this? |
| 17 | `customer_id` | `"Customer identifier."` | How does this relate to `platform_account_id`? Are they 1:1? Should the agent filter on one or both? |
| 18 | `run_id` | `"Assessment run identifier."` | How does this relate to `execution_id` and `assessment_id`? Three ID columns that all seem related to an assessment execution — the agent can't determine the hierarchy. |
| 19 | `execution_id` | `"Execution identifier for pipeline run."` | See #18. What's the relationship: assessment → run → execution? Or are these different names for the same concept? |
| 20 | `asset_entitlement` | `"Entitlement metadata for the asset."` | Type is `"string|null"`. What does this contain? Is it a license tier? A service level? The agent can't filter on it meaningfully. |
| 21 | `finding_reason` | `"Optional reason details."` | "Optional" = often null. No examples. How does this differ from `finding_description`? |
| 22 | `recommendation` vs `remediation` | `"Recommended remediation guidance."` / `"Detailed remediation content."` | Two columns with very similar descriptions. What's the distinction? Is `recommendation` a short summary and `remediation` the full detail? Or are they from different sources? |
| 23 | `management_system_id` | `"Managing system identifier if set."` | "If set" = often null. No examples. What managing systems exist? |
| 24 | `cmd_collection_time` | `"Command collection timestamp if present."` | "If present" = often null. When is it present and when not? Is this the time telemetry was collected from the device? |
| 25 | `asset_key` | `"Device asset key."` | Note #1 says "Use asset_key/source_id for device and rule-specific lookups." But the description doesn't explain what this key is. Is it the same as `serial_number`? A composite key? The agent doesn't know whether to use `asset_key` or `serial_number` to identify a device. |

### OK — no review needed

| Column | Description | Why it's fine |
|--------|------------|---------------|
| `finding_id` | `"Unique finding identifier."` | Clear, type indicates UUID. |
| `assessment_id` | `"Assessment identifier."` | Clear, serves as join key (noted in relationship). |
| `pid` | `"Product identifier (PID)."` | Clear. |
| `serial_number` | `"Device serial number."` | Clear. |
| `product_family` | `"Cisco product family."` | Clear. |
| `hostname` | `"Device hostname."` | Clear. |
| `os_version` | `"Operating-system version."` | Clear. |
| `os_type` | `"Operating-system type (for example IOS-XE)."` | Clear with example. |
| `rule_name` | `"Hardening rule/check name."` | Clear. |
| `detected_at` | `"Finding detection timestamp."` | Clear. |

---

## `HARDENING_ASSESSMENT_COLUMN_SCHEMA` — assessment table (14 columns)

### Flagged

| # | Column | Current Description | Why it needs review |
|---|--------|-------------------|-------------------|
| 26 | `assessment_status` | `"Status of the assessment."` | No enum_values. What statuses exist? (e.g., "completed", "in_progress", "failed"?) The agent can't filter on assessment status without knowing the values. |
| 27 | `assessment_category` | `"Category of the assessment."` | No enum_values or examples. Same column name appears in the `finding` table (#14) — are they always consistent? |
| 28 | `assessment_tags` | `"Tags associated with the assessment."` | Type is `"string"`. Is this a comma-separated list? JSON array? Single value? The agent doesn't know the query pattern. |
| 29 | `is_active` | `"Indicates whether the assessment is active."` | Should the agent default to filtering `WHERE is_active = true`? Or are inactive assessments valid query targets? No usage guidance. |
| 30 | `owner_id` / `owner_name` | `"Identifier of the assessment owner."` / `"Name of the assessment owner."` | Is this a user? A team? A system? Should the agent ever filter on this? |
| 31 | `version` | `"Version number of the assessment."` | Should the agent use the latest version? Can multiple versions coexist for the same assessment? No guidance. |
| 32 | `created_by` / `modified_by` | `"User who created the assessment."` / `"User who last modified the assessment."` | Is this a human user or system account? Should the agent query on these? |

### OK — no review needed

| Column | Description | Why it's fine |
|--------|------------|---------------|
| `assessment_id` | `"Unique assessment identifier."` | Clear, marked as unique. |
| `platform_account_id` | `"Platform account identifier."` | Clear (though tenant isolation guidance is missing — see finding #16). |
| `assessment_name` | `"Name of the assessment."` | Clear. |
| `assessment_description` | `"Detailed description of the assessment."` | Clear. |
| `created_date` | `"Timestamp when the assessment was created."` | Clear. |
| `modified_at` | `"Timestamp when the assessment was last modified."` | Clear. |

---

## Notes Audit (from `server.py`)

| # | Note | Flag | Why |
|---|------|------|-----|
| N1 | `"Use asset_key/source_id for device and rule-specific lookups."` | **Flag** | Doesn't explain what `asset_key` or `source_id` contain, or when to use them vs `serial_number` or `finding_id`. The agent may use the wrong identifier column. |
| N2 | `"Use severity and finding_status for compliance summaries."` | **Flag** | Names the columns but doesn't define the values. The agent needs to know the enum values to construct correct filters. Also doesn't clarify the relationship between `finding_type` and `finding_status` (see #3 and #4). |
| N3 | `"Use detected_at for time-window filtering and latest results."` | OK | Clear and actionable. |
| N4 | `"Join finding to assessment on assessment_id when assessment-level filters or fields are needed."` | OK | Clear. |
| N5 | `"Use build_sql_query with a join spec to build cross-table queries safely."` | OK | Procedural guidance, clear. |

### Missing notes

| # | Gap | Why it matters |
|---|-----|---------------|
| MN1 | **No tenant isolation rule.** | No note says to filter on `platform_account_id` (or `customer_id`). The advisory schema at least has a weak "Prefer platform_account_id" note — hardening has nothing. |
| MN2 | **No guidance on `finding_type` vs `finding_status` usage.** | Two status-like columns with overlapping semantics. The agent needs to know which to use for compliance queries, violation counts, etc. |
| MN3 | **No guidance on null handling.** | Many columns are typed `"string|null"` or `"type|null"`. The agent doesn't know which columns are frequently null and whether to use `IS NOT NULL` filters. |
| MN4 | **No note about the relationship between `source` and `source_id`.** | Two columns that the description admits are logically duplicated. The agent will be confused. |
| MN5 | **No guidance on `evidence_log` and `finding_description` JSON payloads.** | These can contain JSON. The agent needs to know: ignore for SQL? Use JSON functions? |

---

## Relationship Audit

| # | Relationship | Flag | Why |
|---|-------------|------|-----|
| R1 | `finding_assessment`: assessment.assessment_id → finding.assessment_id (1:*) | OK | Clear, correct cardinality. |

---

## Example Filters Audit

| # | Example | Flag | Why |
|---|---------|------|-----|
| E1 | `severity IN ('HIGH', 'MEDIUM')` | **Flag** | Implies these are the important severities but the agent doesn't know the full enum. Are there `LOW`, `CRITICAL`, `INFO` values being excluded? |
| E2 | `finding_status = 'VIOLATED'` | **Flag** | Only shows one status. What about `NOT_VIOLATED`, `MISSING_INFO`, and others mentioned in the column description "etc."? The agent doesn't know what other statuses to filter on for compliance reports. |

---

## Summary — items for data owner review

**32 flagged items** across 2 tables, notes, and examples.

### By category

| Category | Count | Key items |
|----------|-------|-----------|
| **Missing enum_values** | 8 | #3 (`finding_type`), #4 (`finding_status`), #5 (`severity`), #9 (`ic_type`), #12 (`technology`), #26 (`assessment_status`), #27 (`assessment_category`), E1/E2 |
| **Tautological / opaque descriptions** | 3 | #13 (`functional_category`), #14 (`assessment_category`), #15 (`architecture`) |
| **Duplicate / overlapping columns** | 3 | #1/#2 (`source` vs `source_id`), #22 (`recommendation` vs `remediation`) |
| **Ambiguous type / query pattern** | 3 | #6 (`finding_description`), #7 (`evidence_log`), #28 (`assessment_tags`) |
| **Unclear relationships between columns** | 3 | #17 (`customer_id` vs `platform_account_id`), #18/#19 (`run_id` vs `execution_id` vs `assessment_id`) |
| **Missing tenant isolation guidance** | 1 | #16 (`platform_account_id`) + MN1 |
| **"If available" / frequently null** | 4 | #9 (`ic_type`), #12 (`technology`), #23 (`management_system_id`), #24 (`cmd_collection_time`) |
| **Missing usage guidance** | 4 | #25 (`asset_key` vs `serial_number`), #29 (`is_active`), #31 (`version`), #21 (`finding_reason` vs `finding_description`) |
| **Weak notes** | 2 | N1 (unclear identifiers), N2 (missing enum context) |
| **Missing notes** | 5 | MN1–MN5 |
