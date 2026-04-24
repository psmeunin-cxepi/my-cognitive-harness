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

### View name vs. column schema — two separate things

The **view name** (e.g., `cvi_assets_view_1__3__5`) is **not hardcoded** — it comes from the env var `CVI_LDOS_AI_DATA_INTERNAL_TABLE_NAME` (or `CVI_LDOS_AI_DATA_CUSTOMER_TABLE_NAME` for external users), set in the K8s secret `api-secrets`. It could point to a different view without a code change.

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

Transformations happen at two other layers:

| Layer | Where | Example |
|---|---|---|
| **Before** clone | ETL pipeline (transform step) | Source data → cleaned/enriched → written to both Iceberg + PG |
| **After** clone | SQL VIEW in PostgreSQL | Raw PG clone tables → JOINed/aggregated into `cvi_assets_view_1__3__5` |

**The clone itself is always a 1:1 copy.** The Data Fabric API table metadata has no transformation configuration in the clone definition — just target type, name suffix, and resulting table name:

```json
{
  "consumptionTableName": "sec_hrd_rule_evaluation_summary_pg_0__0__11",
  "tableNameSuffix": "pg",
  "type": "postgresql"
}
```

The ETL pipeline writes to both Iceberg and PG targets in parallel as part of the same job — the clone isn't created *from* the Iceberg table via replication, but rather both are outputs of the same ETL pipeline. So the Iceberg table is the system of record directionally, but mechanically they are written alongside each other.

### How does a SQL VIEW relate to clones?

A PostgreSQL VIEW is a stored query that runs against tables **within PostgreSQL**. It cannot reach outside the database into Iceberg. So:

- If an Iceberg table has a PG consumption clone → a VIEW can reference that clone
- If an Iceberg table has **no** PG consumption clone → a VIEW **cannot** reference it

`cvi_assets_view_1__3__5` is a VIEW (not a Data Fabric-managed table — it doesn't appear in the `/tables` API). It sits on top of PG clone tables and performs JOINs + aggregations, which is where FN records get collapsed into per-asset counts.

### Why is `cvi_assets_view_1__3__5` not in the Data Fabric catalog?

Data Fabric manages **tables** (Iceberg + optional PG clones). Views are a layer above — typically created by the application team or a DBA via `CREATE VIEW`. The Data Fabric API tracks tables and their clones; VIEWs aren't in its scope.

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

## What Would It Take to Support "Which assets are impacted by FN74267?"

The data exists upstream. The technical path:

1. **Data layer:** Either provision PG consumption clones for `udm_field_notice` + `udm_field_notice_bulletins`, or configure the agent to query Trino's `iceberg` catalog directly
2. **View layer:** Create a joinable view or modify `cvi_assets_view_1__3__5` to include FN ID columns instead of (or alongside) counts
3. **Agent schema:** Add `field_notice_id` (and optionally FN title, vulnerability_status) to the hardcoded `LDOS_COLUMN_METADATA` in `ldos_db_schema.py`
4. **Guardrails:** Update `guardrail_prompts.py` to allow FN-specific queries
5. **SQL examples:** Add vetted SQL pairs in `question_sql_pairs.py` for FN-specific patterns (e.g., `WHERE field_notice_id = 74267`)

The constraint is not data availability — it's a materialization and view design choice.

---

## Open Questions

1. **Who manages the `cvi_assets_view_1__3__5` view definition?** — Needed to understand how FN counts get aggregated and whether FN ID columns could be added
2. **Why do all 88 CVI tables have empty consumption clones?** — Were clones provisioned in an older version and later removed? Is there a separate mechanism?
3. **Could the agent query the Iceberg catalog directly?** — Would avoid needing PG clones, but would require changes to `trino_utils.py` (catalog config) and may have performance implications
