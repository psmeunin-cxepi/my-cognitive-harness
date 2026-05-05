# HRI Agent — UI Context: Current State & Opportunities

> Technical analysis for the HRI agent development team.  
> Reference: [`cxp-health-risk-insights-ai`](https://github.com/CXEPI/cxp-health-risk-insights-ai) · Jira: [CXP-28103](https://cisco-cxe.atlassian.net/browse/CXP-28103)

---

## Background

When a user interacts with the AI Assistant on Cisco IQ, the frontend assembles a payload via `buildMessageContext()` that includes `context.filters` — a map of the UI state (active filters, entity IDs of what the user is viewing). The **Config Best Practices (CBP)** agent (`configbp-ai`) already consumes this payload and injects it as a `SystemMessage` into the LLM, allowing it to pre-populate tool arguments without re-asking the user.

This document analyses whether the HRI agent currently does the same, and identifies which tool arguments can be mapped from `context.filters`.

---

## Part 1 — Current State: UI Context Flow

The CBP implementation defines a 5-step flow. The table below compares each step against the current HRI codebase.

| Step | What should happen | CBP (`configbp-ai`) | HRI (`cxp-health-risk-insights-ai`) | Status |
|---|---|---|---|---|
| **1. Extract filters from A2A metadata** | Read `message.metadata["filters"]`, strip nulls | `_extract_ui_filters()` in `a2a_server/handlers/skill_handlers.py` | Not present — only `prompt`, `x_authz`, `context_id` extracted | **Missing** |
| **2. Forward filters to agent** | Pass `ui_filters` as a parameter when calling the agent API | `call_agent_api(..., ui_filters=...)` | `call_agent_api(prompt, context_id, x_authz)` — no filters parameter | **Missing** |
| **3. Agent receives `ui_filters`** | `/chat` endpoint accepts a JSON body with `ui_filters: Optional[dict]` | `ChatRequest(ui_filters: Optional[dict])` Pydantic model on a `POST /chat` | `/chat` is a `GET` with only `prompt` as a query parameter — no request body | **Missing** |
| **4. Build UI context string** | `build_ui_context()` allowlists keys, resolves opaque IDs via MCP, renders as markdown | `agent/services/ui_context_builder.py` (399 lines) | `agent/services/` contains only `graph_builder.py` and `mcp_client.py` — no context builder | **Missing** |
| **5. Inject as `SystemMessage`** | Prepend the markdown string as the first `SystemMessage` before the user's `HumanMessage` | `_build_messages()` in `agent/api/server.py` | `agent/nodes/assistant.py` prepends a static system prompt from config — no UI context injection | **Missing** |

**Summary:** The HRI agent currently operates on **prompt-only**. None of the `context.filters` values from the frontend payload reach the LLM or influence tool argument population.

---

## Part 2 — Tool Arguments vs `context.filters` Mapping

### HRI exposes 2 MCP tools

#### Tool 1: `health_risk_analysis_tool` — fleet-level analysis

Returns the top-N riskiest assets across the customer's portfolio.

| Argument | Type | Default | Description |
|---|---|---|---|
| `risk_rating_levels` | `list[str]` | `["High", "Critical"]` | Filter results to one or more of: Critical, High, Medium, Low |
| `asset_count` | `int` | `10` | Number of assets to return (1–50) |
| `include_calculation_details` | `bool` | `True` | Include risk score calculation breakdown |
| `score_to_use` | `str` | `"cisco"` | Which scoring model to use: `"cisco"` or `"customer"` |
| `x_authz` | `str` | `""` | Auth token — auto-populated from request headers |

#### Tool 2: `individual_health_risk_query_tool` — single-asset detail

Fetches detailed risk data for one specific asset. Internally executes:

```sql
SELECT * FROM <table> WHERE impacted_scope_asset = '{asset_id}'
```

| Argument | Type | Default | Description |
|---|---|---|---|
| `asset_id` | `str` | `""` | The asset identifier — matched against `impacted_scope_asset` column in Trino |
| `include_calculation_details` | `bool` | `True` | Include risk score calculation breakdown |
| `x_authz` | `str` | `""` | Auth token — auto-populated from request headers |

---

### Mapping `context.filters` → tool arguments

| `context.filters` key | Set by | Corresponding tool argument | Confidence | Notes |
|---|---|---|---|---|
| `assetId` | HRI MFE detail page via `application.context` | `individual_health_risk_query_tool.asset_id` | **High** | Direct match. When a user views an individual asset's HRI page and asks "why is this high risk?", `assetId` is already known. Today the LLM must ask the user; with context injection it would call the tool immediately. |
| `severity` | HRI list view filter panel | `health_risk_analysis_tool.risk_rating_levels` | **Medium** | The UI severity filter values (Critical/High/Medium/Low) map directly to the `risk_rating_levels` argument. If the user has filtered the list to "Critical only" and then asks the AI, the same filter should be pre-applied. |

All other `context.filters` keys (`serialNumber`, `productFamily`, `savId`, `hostname`, etc.) have **no corresponding argument** in the current HRI tools. The Trino query only resolves assets by `asset_id`; serial number or hostname lookups would require either a new tool or an extended query.

---

### Highest-value scenario

> **User is on the individual asset HRI detail page** (e.g. `/assessments/health/asset/abc123`).  
> The MFE has registered `{ assetId: "abc123" }` in `application.context`, which flows into `context.filters`.  
> The user clicks "Ask AI" and types: *"Why does this asset have a High risk rating?"*

| | Today (no context injection) | After implementation |
|---|---|---|
| LLM behaviour | Must ask: *"Which asset are you referring to?"* | Reads `assetId` from `SystemMessage`, calls `individual_health_risk_query_tool(asset_id="abc123")` directly |
| User experience | Extra round-trip, friction | Zero friction — immediate answer |

---

## Part 3 — What Needs to Be Built

Based on the CBP reference implementation, four changes are required:

1. **`a2a_server/handlers/skill_handlers.py`**  
   Add `_extract_ui_filters(context)` to read `message.metadata["filters"]` and pass the result through to `call_agent_api()`.

2. **`a2a_server/client/agent_client.py`**  
   Add `ui_filters: dict = None` parameter to `call_agent_api()` and include it in the POST body sent to the agent server.

3. **`agent/api/server.py`**  
   - Switch `/chat` from `GET` (query param) to `POST` (JSON body) to support structured data  
   - Add `ui_filters: Optional[dict]` to the request model  
   - Call `build_ui_context()`, prepend the result as a `SystemMessage` before the user's `HumanMessage`

4. **`agent/services/ui_context_builder.py`** _(new file)_  
   Implement `build_ui_context()` scoped to HRI's relevant filters:
   - **Allowlist**: `assetId`, `severity` (and optionally `hostname`, `serialNumber` if Trino query is extended)
   - **Resolution**: `assetId` may need MCP-based resolution to `hostname` (similar to CBP's `resolve_filter_context` pattern) if the raw ID is opaque
   - **Output**: markdown `SystemMessage` following the same header/footer pattern as CBP

---

## References

| Resource | Link |
|---|---|
| CBP reference implementation (merged) | [`configbp-ai` commit CXP-24290](https://github.com/CXEPI/configbp-ai/commit/be70eabfeacbdc2b4aec3e229926b4bba5509389) |
| CBP `ui_context_builder.py` | `agent/services/ui_context_builder.py` in `configbp-ai` main |
| Frontend payload documentation | [`ask-ai-payload.md`](./ask-ai-payload.md) — Section 6 |
| HRI Jira epic | [CXP-28103 — HRI Enhanced Contextual Data](https://cisco-cxe.atlassian.net/browse/CXP-28103) |
| Parent capability | [CXP-15402 — AI Assistant: Phase 2 — Enhancements on Contextual Data](https://cisco-cxe.atlassian.net/browse/CXP-15402) |
