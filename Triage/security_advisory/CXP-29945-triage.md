> **Agent:** Security Advisory | **Repo:** [`CXEPI/risk-app`](https://github.com/CXEPI/risk-app)

# CXP-29945 Triage — Missing Quote Columns in Context Filter SQL Generation

## Summary

String-valued context filter columns are missing from `CONTEXT_FILTER_QUOTE_COLUMNS`, causing their values to be injected into SQL **unquoted**. Trino interprets the bare values as column references, resulting in `COLUMN_NOT_FOUND` errors.

## Symptom

```
Exception: Query for summary key 'oldest_chassis' failed with an error: 400:
Trino query error: TrinoUserError(type=USER_ERROR, name=COLUMN_NOT_FOUND,
message="line 11:32: Column 'sim65186149' cannot be resolved",
query_id=20260424_101146_17146_cmd2s)
```

A second trace confirmed the same class of bug for `equipment_type`:

```sql
-- Generated SQL (broken):
equipment_type IN (CHASSIS)

-- Expected SQL:
equipment_type IN ('CHASSIS')
```

## Root Cause

### File: `common/db_schema/ldos_db_schema.py`

`CONTEXT_FILTER_QUOTE_COLUMNS` (line 593) controls which column filter values receive SQL single-quotes when `create_context_filter_where_clause()` builds the WHERE clause.

### File: `common/common_sav_id_utils.py` (lines 617–627)

```python
if column_name in quote_columns:
    # String column → quoted
    clauses.append(f"{column_name} IN (" + ", ".join(f"'{v}'" for v in use_values) + ")")
else:
    # Assumed numeric → unquoted
    clauses.append(f"{column_name} IN (" + ", ".join(f"{v}" for v in use_values) + ")")
```

Columns **not** in `CONTEXT_FILTER_QUOTE_COLUMNS` have their values inserted without quotes. When the value is a string (e.g., `CHASSIS`, `sim65186149`), Trino parses it as a column identifier → `COLUMN_NOT_FOUND`.

## Filter Category Model

Every column in `SQL_TO_GRAPHQL_FILTER_MAP` falls into one of three handling paths:

| Category | List | Handling |
|---|---|---|
| **Quoted string** | `CONTEXT_FILTER_QUOTE_COLUMNS` | Values wrapped in `'...'` |
| **Date range bucket** | `DATE_RANGE_COLUMNS` | Bucket keys (e.g. `0_6_MONTH`) mapped to pre-built SQL via `DATE_RANGE_SQL_MAP` |
| **Numeric** | Neither list | Values inserted unquoted (intended for integer counts) |

The bug: several string-typed columns are not in any list, so they fall through to the "numeric" (unquoted) path.

## Affected Columns

Columns in `SQL_TO_GRAPHQL_FILTER_MAP` with string values **missing** from `CONTEXT_FILTER_QUOTE_COLUMNS`:

| Column | Example value | Confirmed broken? |
|---|---|---|
| `serial_number` | `sim65186149` | **Yes** — trace 1 |
| `equipment_type` | `CHASSIS` | **Yes** — trace 2 |
| `contract_number` | `1315729` | Risk — schema shows integer examples but column is varchar |
| `cx_level_label` | `STANDARD` | Yes if filtered |
| `hostname` | `003711866769` | Yes if filtered |
| `importance` | `Critical` | Yes if filtered |
| `managed_by_id` | `198.18.135.10 (CX Cloud Agent)` | Yes if filtered |
| `partner_name` | `Accenture` | Yes if filtered |
| `role` | `ACCESS` | Yes if filtered |
| `sav_id` | `SAV-100001` | Yes if filtered |
| `software_type` | `IOS-XE` | Yes if filtered |
| `support_type` | `SNT` | Yes if filtered |

**Note:** `has_security_advisories` and `cxc_advisory_count` are intentionally numeric and correctly unquoted. `tags` has special array handling elsewhere.

## Columns Already Correct

These are already in `CONTEXT_FILTER_QUOTE_COLUMNS` (no action needed):

`connectivity`, `contract_type`, `coverage_status`, `data_source`, `hweox_current_milestone`, `hweox_end_of_hardware_new_service_attachment_date`, `hweox_end_of_hardware_routine_failure_analysis_date`, `hweox_end_of_hardware_service_contract_renewal_date`, `hweox_end_of_life_external_announcement_date`, `hweox_end_of_sale_date`, `hweox_next_milestone`, `last_signal_date`, `last_signal_type`, `location`, `product_family`, `product_id`, `product_type`, `ship_date`, `sweox_end_of_software_maintenance_releases_date`, `sweox_end_of_software_vulnerability_or_security_support_date`

## Timeline

- **2025-11-25** — `CONTEXT_FILTER_QUOTE_COLUMNS` introduced in commit `c79ce8d4` (CXP-15693). `serial_number` and `equipment_type` were in `SQL_TO_GRAPHQL_FILTER_MAP` from the same commit but never added to the quote list.
- **2025-11-25 → 2026-04-24** — List reshuffled/cleaned across multiple commits; missing columns were never added.
- **2026-04-24** — Bug surfaced when UI sent `serialNumber` and `equipmentType` context filters.

## Reproduction Path

1. User navigates to Asset Explorer with a filter applied (e.g., `equipmentType=CHASSIS` in URL, or serial number filter from device detail page).
2. User asks a preset question like "Summarize assets past Last Date of Support (LDOS)."
3. `question_similarity_matching` matches it to `QUESTION_LDOS_LAST_12_MONTHS` (index 1, semantic match).
4. `execute_sql` calls `create_context_filter_where_clause()` with the saved context filter.
5. `equipment_type` / `serial_number` not in `CONTEXT_FILTER_QUOTE_COLUMNS` → value inserted unquoted.
6. Trino receives `equipment_type IN (CHASSIS)` → `COLUMN_NOT_FOUND`.

## Fix

Add missing string columns to `CONTEXT_FILTER_QUOTE_COLUMNS` in `common/db_schema/ldos_db_schema.py`:

```python
CONTEXT_FILTER_QUOTE_COLUMNS = [
    "connectivity",
    "contract_number",
    "contract_type",
    "coverage_status",
    "cx_level_label",
    "data_source",
    "equipment_type",
    "hostname",
    "hweox_current_milestone",
    "hweox_end_of_hardware_new_service_attachment_date",
    "hweox_end_of_hardware_routine_failure_analysis_date",
    "hweox_end_of_hardware_service_contract_renewal_date",
    "hweox_end_of_life_external_announcement_date",
    "hweox_end_of_sale_date",
    "hweox_next_milestone",
    "importance",
    "last_signal_date",
    "last_signal_type",
    "location",
    "managed_by_id",
    "partner_name",
    "product_family",
    "product_id",
    "product_type",
    "role",
    "sav_id",
    "serial_number",
    "ship_date",
    "software_type",
    "support_type",
    "sweox_end_of_software_maintenance_releases_date",
    "sweox_end_of_software_vulnerability_or_security_support_date",
]
```

## Design Consideration

The current approach (maintaining a manual allowlist of quoted columns) is fragile — any new filter column added to `SQL_TO_GRAPHQL_FILTER_MAP` must also be added to `CONTEXT_FILTER_QUOTE_COLUMNS` or it will silently break. A safer alternative would be to maintain a **denylist** of numeric columns (which is much shorter: `cxc_advisory_count`) and default to quoting everything else. This would prevent future regressions.
