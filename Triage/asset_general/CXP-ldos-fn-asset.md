> **Agent:** Asset General
> **Repo:** [`CXEPI/cvi-ldos-ai`](https://github.com/CXEPI/cvi-ldos-ai)
> **Jira:** _to be created_

# LDOS Agent: Field Notice Per-Asset Data Availability

**Repo:** `CXEPI/cvi-ldos-ai`  
**Data Model Source:** `CXEPI/cvi-success-track-config` → `models/cvi/entity/udm/`  
**Date:** 2026-04-24

**Trigger:** Can the LDOS AI Assistant answer "Which assets are impacted by FN74267?" or "Is this asset impacted by FN74267?"

---

## TL;DR

**No.** The LDOS agent cannot answer field-notice-specific queries today. It's blocked at two levels:

1. **Guardrail** — explicitly rejects any FN query beyond aggregate counts
2. **Schema** — the view the agent queries only has integer count columns, no FN IDs

The underlying per-asset, per-FN data **does exist** in the Iceberg datalake (`udm_field_notice` table with `field_notice_id` + `telemetry_dimension_key`), but it is not materialized into the PostgreSQL view the agent queries. The data gets collapsed into counts (`critical_vulnerability_field_notice_count`, `high_vulnerability_field_notice_count`) somewhere in the view/ETL pipeline.

---

## How the Pieces Fit Together

```
Source Systems (PAS, telemetry, etc.)
        │
        ▼
  Data Fabric ETL
        │
        ├──► Iceberg tables on S3 (datalake — system of record)
        │      • udm_asset
        │      • udm_field_notice          ← has field_notice_id per device
        │      • udm_field_notice_bulletins ← FN catalog/reference data
        │      • udm_psirt
        │      • udm_psirt_bulletins
        │      • udm_contract, udm_software, etc. (88 CVI tables total)
        │
        └──► PostgreSQL consumption clones (optional per-table)
                    │
                    ▼
              SQL VIEW: cvi_assets_view_1__3__5
              (JOINs + aggregates underlying PG tables)
              (FN data collapsed into integer counts here)
                    │
                    ▼
                  Trino (query federation layer, catalog=postgresql)
                    │
                    ▼
               APISIX Gateway (TLS + auth)
                    │
                    ▼
               LDOS AI Agent (aiotrino client)
```

**Key point:** Trino is a pass-through query federation layer, not a data store. It connects to PostgreSQL via `catalog="postgresql"`, `schema="public"`. PostgreSQL contains both Data Fabric consumption clone tables and manually-created views. The agent queries a specific **view** whose name comes from an environment variable, using a **column schema** that is hardcoded in Python source code.

---

## Agent-Side Constraints

### Guardrail restriction

In `common/guardrails/guardrail_prompts.py`:

> "ONLY count-based field notice questions are valid, and ONLY for critical and high severity levels. Questions asking for field notice details, descriptions, remediation steps, specific FN IDs, content of individual field notices, or severity levels other than critical/high are NOT valid and must be rejected."

### Table name vs. column schema — two separate things

The **table name** is **not hardcoded** — it comes from env vars in the K8s secret `api-secrets`. There are **two different tables** depending on caller type:

| Env var | Actual value (dev) | Used for |
|---|---|---|
| `CVI_LDOS_AI_DATA_CUSTOMER_TABLE_NAME` | `cvi_assets_view_1__3__5` | Customer-facing (external) queries |
| `CVI_LDOS_AI_DATA_INTERNAL_TABLE_NAME` | `cvi_assets_internal_view_1__0__17` | Cisco-internal queries |

The customer table is produced by `cvi_assets_udm_cxc_template.yaml`; the internal table by `cvi_assets_internal_udm_template.yaml` (both in `CXEPI/cvi-success-track-config`, `etl/cvi/` directory).

The **column schema** (what columns exist, their types, descriptions, usage rules) **is hardcoded** in `common/db_schema/ldos_db_schema.py` — constants `LDOS_TABLE_DESCRIPTION` and `LDOS_COLUMN_METADATA`. The LLM is told "this view has these columns" and generates SQL accordingly. There is zero dynamic schema introspection (`SHOW COLUMNS`, `DESCRIBE`, `INFORMATION_SCHEMA` are never called).

If the view name were changed to point to a view with different columns, the hardcoded column schema would be out of sync.

The only FN-related columns in the hardcoded schema are:

| Column | Type | What it holds |
|---|---|---|
| `critical_vulnerability_field_notice_count` | integer | Count of critical-severity FNs affecting the asset |
| `high_vulnerability_field_notice_count` | integer | Count of high-severity FNs affecting the asset |

No `field_notice_id`, no FN title, no FN details — just counts.

### Vetted SQL examples

In `common/questions/question_sql_pairs.py`, the FN-related SQL examples only use count-based filtering:

```sql
WHERE critical_vulnerability_field_notice_count > 0
WHERE high_vulnerability_field_notice_count > 0
```

---

## Datalake Architecture — Key Learnings

### What is a consumption clone?

A **consumption clone** is a read-optimized copy of an Iceberg datalake table, materialized into a different datastore (typically PostgreSQL) so downstream applications can query it efficiently. The clone is a **1:1 replica** of the Iceberg table — same columns, same rows. No transformation happens at the clone level.

### How `cvi_assets_view_1__3__5` is actually built

**Critical correction:** Despite the name, `cvi_assets_view_1__3__5` is **NOT a SQL VIEW** — it is a **PostgreSQL table** produced by an **ETL pipeline**. The ETL is defined entirely in Git:

- **Repo:** `CXEPI/cvi-success-track-config`
- **Instance config:** `etl/cvi/common/cvi_assets_udm_cxc_instance.yaml` — defines source tables + destination
- **Template (SQL logic):** `etl/cvi/common/cvi_assets_udm_template.yaml` (v2.0.19) — contains all transforms

The ETL pipeline reads **directly from Iceberg** (`SOURCE_CONNECTOR: iceberg:1.0.0`) — it does NOT use PG consumption clones as intermediates. It JOINs ~17 source tables, applies transforms, and writes the aggregated result to PostgreSQL (`SERVING_DESTINATION_CONNECTOR: pg-new:1.0.0`, save mode: `upsert`).

This means:
- **No PG clones are needed** — the ETL reads from Iceberg directly
- The "view" in the name is vestigial — it was likely a VIEW originally but was refactored into an ETL-produced table
- The FN count columns come from a specific transform step called `transform_advisory_counts`

### The `transform_advisory_counts` step — where FN IDs become counts

This is the exact SQL transform that aggregates individual FN records into per-device counts (from `cvi_assets_udm_template.yaml`, lines 482–550):

```sql
SELECT
  telemetry_dimension_key,
  SUM(CASE WHEN severity = 'critical' AND advisory_type = 1
    THEN count ELSE 0 END) AS critical_vulnerability_field_notice_count,
  SUM(CASE WHEN severity = 'high' AND advisory_type = 1
    THEN count ELSE 0 END) AS high_vulnerability_field_notice_count,
  -- ... (PSIRT counts use advisory_type = 2)
FROM (
  SELECT telemetry_dimension_key, severity, advisory_type,
         vulnerability_status, count(*) AS count
  FROM (
    -- PSIRT subquery (advisory_type = 2)
    SELECT p.telemetry_dimension_key, p.psirt_id AS advisory_id,
           2 as advisory_type, LOWER(pb.severity_level_name) as severity,
           LOWER(p.vulnerability_status) AS vulnerability_status
    FROM {source_udm_psirt.data} p
      JOIN {source_udm_psirt_bulletins.data} pb ON p.psirt_id = pb.psirt_id
    WHERE LOWER(pb.severity_level_name) in ('critical', 'high')
    UNION
    -- *** FIELD NOTICE subquery (advisory_type = 1) ***
    SELECT fn.telemetry_dimension_key, fn.field_notice_id AS advisory_id,
           1 as advisory_type, LOWER(fnb.impact_rating) as severity,
           LOWER(fn.vulnerability_status) AS vulnerability_status
    FROM {source_udm_field_notice.data} fn
      JOIN {source_udm_field_notice_bulletins.data} fnb
        ON fn.field_notice_id = fnb.field_notice_id
    WHERE LOWER(fnb.impact_rating) in ('critical', 'high')
  )
  GROUP BY telemetry_dimension_key, advisory_type, severity, vulnerability_status
)
GROUP BY telemetry_dimension_key
```

This is where `field_notice_id` is discarded — the UNION subquery selects it, but the outer GROUP BY collapses it to counts per `telemetry_dimension_key` (device).

### ETL source tables (from instance YAML)

| Parameter | Source Table | Connector |
|---|---|---|
| `SOURCE_UDM_FIELD_NOTICE_TABLE` | `udm_field_notice_1__0__6` | `iceberg:1.0.0` |
| `SOURCE_UDM_FIELD_NOTICE_BULLETINS_TABLE` | `udm_field_notice_bulletins_1__0__4` | `iceberg:1.0.0` |
| `SOURCE_UDM_ASSETS_TABLE` | `udm_asset_1__0__10` | `iceberg:1.0.0` |
| `SOURCE_UDM_ASSETS_TELEMETRY_TABLE` | `udm_asset_telemetry_1__0__9` | `iceberg:1.0.0` |
| `SOURCE_UDM_PSIRT_TABLE` | `udm_psirt_1__0__7` | `iceberg:1.0.0` |
| `SOURCE_UDM_PSIRT_BULLETINS_TABLE` | `udm_psirt_bulletins_1__0__4` | `iceberg:1.0.0` |
| ... (17 source tables total) | | |
| **SERVING_DESTINATION_TABLE** | **`cvi_assets_view_1__3__5`** | **`pg-new:1.0.0`** |

### Why is `cvi_assets_view_1__3__5` not in the Data Fabric catalog?

Because it's not a Data Fabric-managed table with Iceberg + optional clone. It's the **output** of a CX Platform ETL pipeline that writes directly to PostgreSQL. Data Fabric manages source Iceberg tables; this is a downstream serving table.

### Trino's role

Trino is a **query federation engine**, not a database. It exposes multiple catalogs:

- `postgresql` catalog → queries the PostgreSQL database, which contains both Data Fabric consumption clone tables **and** manually-created views like `cvi_assets_view_1__3__5`
- `iceberg` catalog → queries the Iceberg datalake tables on S3 directly

Trino doesn't know or care what a "consumption clone" is — that's a Data Fabric concept. The `postgresql` catalog exposes everything in PostgreSQL: clone tables, views, any other objects.

The LDOS agent is configured to use `catalog="postgresql"`, so it sees whatever exists in PostgreSQL. The raw Iceberg tables (including `udm_field_notice`) are theoretically queryable via the `iceberg` catalog, but the agent isn't configured for that.

---

## `udm_field_notice` — Per-Device FN Impact Records

**Source:** `CXEPI/cvi-success-track-config` → `models/cvi/entity/udm/udm_field_notice.json`  
**Datalake table:** `udm_field_notice_1__0__6` (latest version)  
**Consumption clone:** None (`"consumptionClones": {}`)  
**Description:** "Entity containing field_notices" — maps individual FNs to specific devices. Each row = one device affected by one FN.

| Column | Type | Description |
|---|---|---|
| `field_notice_id` | integer | **The specific FN identifier** (e.g., 74267) — required |
| `dimension_key` | signal_dimension_key | Unique key identifying the field notice entity |
| `dimension_key_type` | surrogate_key | Type of dimension key |
| `telemetry_dimension_key` | signal_dimension_key | **Links to the asset/device** via asset telemetry entity |
| `vulnerability_status` | string (max 16) | `VUL` (vulnerable) or `POTVUL` (potentially vulnerable) |
| `vulnerability_reason` | string (max 4000) | Description of why the device is vulnerable |
| `caveat` | string | Alert caveat for the FN |
| `source` | string | Source system where the FN association originated |
| `partition_key` | partition_key | Customer partition key |
| `delete_flag` | boolean | Soft-delete marker |
| `inserted_at` / `updated_at` | timestamp | Record lifecycle |
| `source_created_at` / `source_updated_at` | timestamp | Source system timestamps |

---

## `udm_field_notice_bulletins` — FN Reference / Catalog Data

**Source:** `CXEPI/cvi-success-track-config` → `models/cvi/entity/udm/udm_field_notice_bulletins.json`  
**Datalake table:** `udm_field_notice_bulletins_1__0__4` (latest version)  
**Consumption clone:** None  
**Description:** "Contains field notice information for Cisco devices that comes directly from PAS" — one row per FN with full advisory details.

| Column | Type | Description |
|---|---|---|
| `field_notice_id` | integer | **The FN identifier** (unique key) |
| `name` | string | FN title |
| `content` | string (JSON) | Full content: caveat, background, problem description, symptoms, workaround |
| `impact_rating` | string | Impact rating |
| `type` / `type_cd` | string | FN type / type code |
| `fn_alert_status` | string | Alert status |
| `defects` | string | Defects addressed |
| `url_text` | string | URL reference |
| `publish_date` / `revised_date` | timestamp | Publication lifecycle |
| `hw_affected_versions` | string | Affected HW versions |
| `eco_nums` | string | ECO numbers |
| `fn_distribution` | string | Distribution info |
| `plato_status` | string | Status in PLATO system |
| `pot_vul_cd` | string | Potential vulnerability code |
| `sn_avail_cd` | string | Serial number availability code |
| `publish_user_id` | string | Publisher |
| `inserted_at` / `updated_at` | timestamp | Record lifecycle |
| `source_create_date` / `source_update_date` | timestamp | Source timestamps |

---

## Jira Context

| Jira | Summary | Status |
|---|---|---|
| CXP-3358 | Feature 1 - Summarization and prioritization of LDOS assets | PM feature spec with user stories |
| CXP-28839 | FN64190 — user asks about specific FN, agent can't answer | To Do |
| CXP-29812 | Remove Field Notice Support Again | In Progress |
| CXP-29293 | Revert Field Notice Changes | Done |
| CXP-27999 | FN prioritization bug | Verified |
| CXP-28605 | Add FN guardrail | Cancelled |

The Jira history shows FN support has been added and reverted multiple times — it's been contentious.

---

## Data Fabric API Discovery

Using the Data Fabric API (`/data-fabric/v1alpha/tables`), we enumerated all 506 tables in the dev environment:

- **88 tables** belong to the `cvi-dev` data model
- **Zero** of the 88 CVI tables have PostgreSQL consumption clones (all Iceberg-only)
- Field-notice-related tables: `udm_field_notice` (6 versions, latest v1.0.6), `udm_field_notice_bulletins` (4 versions, latest v1.0.4)
- The `consumptionClones` field metadata determines whether a PG copy exists — an empty object means Iceberg-only
- The catalog data model schemas (JSON schema definitions) were accessible via GitHub (`CXEPI/cvi-success-track-config`) but **not** via the Data Fabric catalog API (returned 403)

---

## Live Prod Schema vs. Agent Schema — Drift Analysis

**Source:** Live `cvi_assets_view_1__3__5` schema from **PROD usw2** (captured 2026-04-24 via `information_schema.columns`). See [schema/cvi_assets_view_1__3__5_prod_usw2_schema.md](schema/cvi_assets_view_1__3__5_prod_usw2_schema.md) for the full 162-column listing.

| Metric | Value |
|---|---|
| PG table columns (prod) | **162** |
| Agent hardcoded columns (`LDOS_COLUMN_METADATA`) | **54** |
| In PG but **not** in agent schema | **111** — the LLM can't query these |
| In agent schema but **not** in PG | **3** — phantom columns that would cause SQL errors |

### FN-related columns in prod PG table

Only two — both integer counts, confirming the ETL analysis:

| Column | Type | Maps to |
|---|---|---|
| `critical_vulnerability_field_notice_count` | integer | `transform_advisory_counts` → `udm_field_notice` + `udm_field_notice_bulletins` |
| `high_vulnerability_field_notice_count` | integer | same |

No `field_notice_id`, no `vulnerability_status`, no `vulnerability_reason`. The live prod schema confirms what the ETL template told us: `udm_field_notice` data flows in, but only counts survive to the output table.

### Phantom columns (in agent schema, missing from PG)

These 3 columns are in `LDOS_COLUMN_METADATA` but do **not exist** in the prod table. If the LLM generates SQL using them, the query will fail:

| Column | In agent schema? | In prod PG? |
|---|---|---|
| `contract_type` | YES | **NO** |
| `product_list_price` | YES | **NO** |
| `sav_id` | YES | **NO** |

### Notable columns available in PG but hidden from agent (111 total)

Examples of potentially useful columns the agent doesn't know about:

- `customer_name`, `account_name` — customer identification
- `advisory_count`, `all_advisory_count` — total advisory aggregates
- `affected_security_advisories_count`, `potentially_affected_security_advisories_count` — finer PSIRT breakdowns
- `sweox_*` (15 columns) — software end-of-life milestones
- `hweox_*` (additional to what agent has) — more hardware EOL milestones
- `*_latest_signal` (7 columns) — last signal timestamps by type
- `migration_info`, `vendor`, `quantity` — asset metadata

---

## What Would It Take to Support "Which assets are impacted by FN74267?"

The data exists upstream. The technical path:

1. **ETL template change:** Modify `transform_advisory_counts` in `cvi_assets_udm_template.yaml` (and the CXC variant) to preserve `field_notice_id` alongside counts — or create a separate transform step that writes FN-per-device data to a second PG table
2. **Agent schema:** Add `field_notice_id` (and optionally FN title, vulnerability_status) to the hardcoded `LDOS_COLUMN_METADATA` in `ldos_db_schema.py`
3. **Guardrails:** Update `guardrail_prompts.py` to allow FN-specific queries
4. **SQL examples:** Add vetted SQL pairs in `question_sql_pairs.py` for FN-specific patterns (e.g., `WHERE field_notice_id = 74267`)

The constraint is not data availability — the ETL already reads `udm_field_notice` and `udm_field_notice_bulletins` from Iceberg. It's a **transform design choice** that discards `field_notice_id` during aggregation.

---

## What We Now Know (Resolved Questions)

| Previous question | Answer |
|---|---|
| Who manages `cvi_assets_view_1__3__5`? | The `CXEPI/cvi-success-track-config` repo — ETL template at `etl/cvi/common/cvi_assets_udm_template.yaml` (v2.0.19) |
| Is it a SQL VIEW? | **No.** It's a PostgreSQL **table** produced by an ETL pipeline |
| How do FN counts reach the table? | The ETL's `transform_advisory_counts` step reads `udm_field_notice` + `udm_field_notice_bulletins` **directly from Iceberg**, JOINs on `field_notice_id`, counts per device, and the main transform JOINs counts into the output |
| Why no PG clones for CVI tables? | PG clones aren't needed — the ETL reads from Iceberg directly. The final aggregated result is written to PG as the serving table |
| Where is `field_notice_id` discarded? | In the `GROUP BY telemetry_dimension_key` of `transform_advisory_counts` — the UNION subquery selects `field_notice_id`, but the outer aggregation collapses to counts |
| Does the live PG table have FN ID columns? | **No.** Confirmed from prod schema (162 columns) — only `critical_vulnerability_field_notice_count` and `high_vulnerability_field_notice_count` (integers) |
| Does the agent schema match the actual PG table? | **No.** Agent sees 54 of 162 columns; 3 phantom columns (`contract_type`, `product_list_price`, `sav_id`) don't exist in prod |

## What We Still Need

### 1. PM decision on FN-specific query support

**What:** Confirmation on whether "Which assets are impacted by FN74267?" should be a supported capability. The Jira history (CXP-29812 "Remove Field Notice Support Again", CXP-29293 "Revert Field Notice Changes") shows this has been added and reverted multiple times.  
**Why:** No point modifying the ETL if the PM/product decision is to keep FN queries out of scope.  
**From whom:** The **LDOS AI Product Manager** — whoever owns the CXP-3358 epic and the FN-related Jiras.  
**Ask:** "Is per-FN-ID asset impact querying in scope for LDOS AI? The data flows through the ETL already — the blocker is a transform design choice, not data availability."

### Summary table

| # | What | From whom | Status |
|---|---|---|---|
| ~~1~~ | ~~View DDL~~ | ~~Data team~~ | **RESOLVED** — found in `cvi-success-track-config` ETL template |
| ~~2~~ | ~~How FN counts reach the table~~ | ~~Data team~~ | **RESOLVED** — `transform_advisory_counts` reads directly from Iceberg |
| ~~3~~ | ~~Live PG schema~~ | ~~Colleague with Trino access~~ | **RESOLVED** — 162 columns captured from prod, confirms no FN ID columns |
| ~~4~~ | ~~Agent schema drift~~ | ~~(self)~~ | **RESOLVED** — 54 vs 162 columns; 3 phantom columns identified |
| 5 | PM decision on FN query scope | LDOS AI Product Manager | **OPEN** — decides if we proceed |
