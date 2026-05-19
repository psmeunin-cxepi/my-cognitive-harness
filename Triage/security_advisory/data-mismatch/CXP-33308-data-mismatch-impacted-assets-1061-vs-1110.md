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

## Root cause — the two surfaces query different view versions

The AI agent and the Asset Inventory UI read from **different versions of the same logical views**:

| Surface | Assets view | PSIRTs view |
|---|---|---|
| **Security Advisory AI agent** | `postgresql.public.cvi_assets_view_1__3__5` | `postgresql.public.cvi_psirts_view_1__3__7` |
| **Assets → Inventory UI** | `cvi_assets_view_1__3__9` | `cvi_psirts_view_1__3__11` |

The agent's view names are configured in [`text2sql_mcp/config.py`](https://github.com/CXEPI/risk-app/blob/main/text2sql_mcp/config.py#L60-L66) on `CXEPI/risk-app` (Pydantic settings, defaults below; overridable via env vars `SQL_MCP_SECURITY_ADVISORY_ASSETS_TABLE` / `SQL_MCP_SECURITY_ADVISORY_TABLE`):

```python
security_advisory_table: str = Field(
    "postgresql.public.cvi_psirts_view_1__3__7", ...
)
security_advisory_assets_table: str = Field(
    "postgresql.public.cvi_assets_view_1__3__5", ...
)
```

The deployed prod env is therefore pinned **4 minor versions behind** on `cvi_assets_view` (5 → 9) and **4 minor versions behind** on `cvi_psirts_view` (7 → 11). Even with identical SQL semantics on both sides, version drift of the underlying ETL output is sufficient to explain the 49-asset gap (different row counts, possibly different column definitions of `vulnerability_status`, possibly different join coverage).

### How the prod values are injected

The defaults in `config.py` are **local-dev only**. In prod the values come from env vars wired through Helm + External Secrets Operator — there is no `.env` file:

1. **External secret store** (org secret manager) at `.Values.externalSecrets.secretsPath` holds the canonical values.
2. [`text2sql_mcp/helm/templates/external-secret.yaml`](https://github.com/CXEPI/risk-app/blob/main/text2sql_mcp/helm/templates/external-secret.yaml) declares an `ExternalSecret` that syncs 5 keys (incl. `SQL_MCP_SECURITY_ADVISORY_TABLE`, `SQL_MCP_SECURITY_ADVISORY_ASSETS_TABLE`) into a K8s `Secret` named `<release>-api-secrets` (refresh interval ~1h).
3. [`text2sql_mcp/helm/templates/deployment.yaml#L112-L114`](https://github.com/CXEPI/risk-app/blob/main/text2sql_mcp/helm/templates/deployment.yaml#L112-L114) mounts the whole secret into the container env via `envFrom: secretRef: <release>-api-secrets`.
4. Pydantic Settings in `config.py` reads them at startup (defaults are overridden whenever the env var is present).

To **change the prod pin**, update the value in the upstream secret store; ExternalSecret will sync within the refresh interval and the new value is picked up on next pod restart. **No code change to `config.py` is required.** To verify the live value: `kubectl exec <pod> -- env | grep SQL_MCP_SECURITY_ADVISORY`.

## Action items

1. Align the agent's view versions to the Inventory UI's. Update `SQL_MCP_SECURITY_ADVISORY_ASSETS_TABLE` → `postgresql.public.cvi_assets_view_1__3__9` and `SQL_MCP_SECURITY_ADVISORY_TABLE` → `postgresql.public.cvi_psirts_view_1__3__11` in the **upstream secret store** that backs the prod `ExternalSecret` (not in `config.py`); restart the `text2sql_mcp` pod after the sync. Then rebase the hardcoded column schema (`text2sql_mcp/server.py` schema payloads) against the new views.
2. Re-run the same prompt against the same tenant after the pin is updated and confirm the count converges to the Inventory UI value.
3. If the counts still differ post-alignment, request the exact SQL the Inventory UI emits for the "Affected by security advisories" filter and diff predicates (likely `affected_security_advisories_count > 0` on the assets view vs. the agent's `INNER JOIN psirts WHERE vulnerability_status = 'VUL'`).

### AI agent SQL (for the diff)
```sql
SELECT COUNT(DISTINCT assets.serial_number) AS impacted_assets_count
FROM postgresql.public.cvi_assets_view_1__3__5 AS assets
INNER JOIN postgresql.public.cvi_psirts_view_1__3__7 AS psirts
  ON assets.serial_number = psirts.serial_number
WHERE psirts.vulnerability_status = 'VUL';
```

## Recommendations

- **P1 — Pin alignment as deploy invariant.** The `text2sql_mcp` view pins must be tracked against the same source of truth that the Inventory UI uses. Add a release-time check that fails CI/CD if the configured view versions drift behind the latest published `cvi_*_view`.
- **P2 — Same-question regression eval.** Add an eval case "How many assets are impacted by a security advisory?" anchored to the Inventory UI's count for a known tenant. Run on every release to catch silent drift.
- **P3 — Surface the view version in agent answers.** The agent should disclose which view + version it queried (in the trace and optionally in the user-facing answer footer) so this class of mismatch is debuggable in one step.

## Related (separate tickets)

The same trace exposed two unrelated agent issues, kept here as a pointer:
- `mcp_build_sql_by_domain` column-prefix validator false-positive on aggregate expressions (e.g. `COUNT(DISTINCT assets.serial_number)` parsed as table alias `count(distinct assets`). Forces fallback to raw `mcp_execute_sql`.
- The agent retried the identical failing `build_sql_by_domain` payload before falling back. The loop should short-circuit identical-args retries.
