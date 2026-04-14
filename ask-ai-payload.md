# The "Ask AI" Request Payload

> Research grounded in `cx-platform-ui` source code, Confluence, and Jira (CXP/CXPL).  
> Last updated: 2026-04-13

---

## 1. Overview

When a user clicks an "Ask AI" button or types in the banner chat bar on Cisco IQ,
the frontend (`cx-platform-ui`) sends a request to the **CVI Semantic Router (SR)**
with the following shape:

```json
{
  "question": "Why is device XYZ end-of-life?",
  "context": {
    "source":     "ask-ai",
    "url":        "/assessments/field-notices/FN-70782",
    "language":   "en",
    "app":        "assessments",
    "application": {
      "id":      "assessments",
      "context": { "fieldNoticeId": "FN-70782" }
    },
    "context_id": "thread-uuid-abc123",
    "filters": {
      "fieldNoticeId": ["FN-70782"],
      "savId": ["SAV-001"]
    },
    "appTags": ["iq-ldos"]
  }
}
```

This object is assembled by **`buildMessageContext()`** in  
`libs/shared/core/data-access/platform-shell-ai/src/lib/ai-interaction-store/ai-interaction.utils.ts`.

### Field Summary

| Field | Source | What it represents |
|---|---|---|
| `question` | User input | Natural-language question typed or pre-filled by an Ask AI button |
| `context.source` | `askAi()` wrapper (auto-injected) | Routing signal: `"ask-ai"` = button click (Tier 1); absent/other = banner bar (Tier 2) |
| `context.url` | `Router` (current URL) | Active browser URL; normalized to `app + first-path-segment` for Tier 2 route matching |
| `context.language` | `TranslationStore` | UI locale (e.g. `"en"`, `"ja-JP"`); agents reply in this language |
| `context.app` | `MfeStore.appKey()` | MFE application name (e.g. `"assessments"`, `"support"`); shorthand for `application.id` |
| `context.application` | `AiAssistantGlobalContextStore` | Full application object `{ id, context }` — `context` holds page-level entity IDs (e.g. `serialNumber`, `fieldNoticeId`) |
| `context.context_id` | LangGraph thread ID | Conversation session identifier; enables multi-turn memory |
| `context.filters` | Merged: URL query params + `application.context` + call-site filters | UI view state (selected rows, active filters) + entity IDs from the current page, all normalized to arrays |
| `context.appTags` | In-context Ask AI call site | Explicit agent routing tags (e.g. `"iq-ldos"`); used by SR for Tier 1 hard-filter |

---

## 2. Field Reference

### `question` — `string`

The raw, natural-language text the user typed or that was pre-filled by an "Ask AI" button.

---

### `context.source` — `string | undefined`

> **Routing signal, not entity data.**

| Value | Origin | Effect in SR |
|---|---|---|
| `"ask-ai"` | In-context "Ask AI" button click | **Tier 1 hard-filter** — agent pool restricted to agents matched by `appTags` or route |
| _(absent / other)_ | Banner chat bar (user typed) | **Tier 2 weighted preference** — matched agents scored higher, all remain eligible |

`source` is injected automatically by the `askAi()` wrapper and is **never set manually** by each call site.
Defined in CXP-26207 / CXP-26208.

---

### `context.url` — `string`

The current browser URL at the time of the request (e.g. `/assessments/field-notices/FN-70782?tab=details`).

Used by the SR for **Tier 2 URL-based routing**: the URL is normalized to `app + first-path-segment`
(e.g. `"assessments:/field-notices"`) and looked up in the route→agent mapping table.

---

### `context.language` — `string`

UI locale code (e.g. `"en"`, `"ja-JP"`). Sourced from `TranslationStore.currentLanguageCode()`.
Agents use this to respond in the user's language.

---

### `context.app` — `string`

The MFE application ID — equivalent to `globalContext.application.id`.  
Examples: `"assessments"`, `"support"`, `"inventory"`.

Used for Tier 2 route normalization in the SR alongside `url`.  
Note: `app` alone is too broad — all 6 assessment agents share `app: "assessments"`,
which is why `appTags` and URL routing are needed.

---

### `context.application` — `object`

The full `globalContext.application` object. TypeScript type (from `ai-assistant-global-context.models.ts`):

```typescript
type AiAssistantApiContext = {
  application: {
    id: string;                        // same value as `app`
    context: Record<string, unknown>;  // page-level entity scope (see below)
  };
  // ...
};
```

#### `application.id`

Same as `app`. The MFE key registered via `MfeStore.appKey()`.

#### `application.context`

A free-form key-value object populated by each MFE detail page via  
`withGlobalAiApplicationContext(computed(() => ({ ... })))`.  
It holds the **entity IDs of what the user is currently looking at**.

> **MFE ownership & no enforced schema.**  
> Any MFE team can decide what to push here. The type is `Record<string, unknown>` — there is no
> shared contract or validation at the TypeScript level. Key names are chosen freely by each team
> (e.g. Inventory chose `serialNumber`, Assessments teams chose `assetId`, `fieldNoticeId`,
> `checkId`, `ruleId`). The agent receiving the values in `filters` is responsible for knowing
> what to do with them.  
>
> The registration is **entirely in the MFE's own UI store code** — no backend involvement.
> The lifecycle is managed automatically by `withGlobalAiApplicationContext()`:
> - **`onInit`** — dispatches the context (namespaced by `appKey`) to the root-level `AiAssistantGlobalContextStore`
> - **Signal reactivity** — if the entity ID changes while the page is open, the context re-dispatches immediately
> - **`onDestroy`** — clears the MFE's context slice, so stale entity IDs are never leaked to the next page

**Concrete values registered by each MFE page:**

| Page / Feature | `application.context` |
|---|---|
| Asset Detail (Inventory) | `{ serialNumber: "<asset SN>" }` |
| Evaluated Asset Details (Assessments) | `{ assetId: "<asset ID>" }` |
| Field Notice Details | `{ fieldNoticeId: "<FN ID>" }` |
| Field Notice → Asset Assessment Result | `{ fieldNoticeId: "<FN ID>", assetId: "<asset ID>" }` |
| Security Advisory Details | `{ checkId: "<advisory ID>" }` |
| Security Advisory → Affected Asset Details | `{ checkId: "<psirt ID>", assetId: "<asset ID>" }` |
| Config Best Practices Details | `{ ruleId: "<rule ID>" }` |
| Security Hardening Details | `{ checkId: "<rule ID>" }` |
| List/overview pages (no selected entity) | `{}` (empty — no context registered) |

**How it works:**  
Each MFE detail store embeds `withGlobalAiApplicationContext(computed(() => ({ ... })))`.
The computed signal is reactive — if the user navigates to a new entity ID,
the context is automatically re-dispatched.

**Where `application.context` ends up:**  
In `buildMessageContext()`, `application.context` is spread into `filters`:

```typescript
filters: normalizeToArrayValues({
  ...globalContext.queryParams,
  ...globalContext.application.context,   // ← entity IDs land here
  ...(providedContext?.['filters'] ?? {}),
}),
```

So the agent receives these entity IDs inside `filters`, not as top-level fields.

---

### `context.context_id` — `string`

The LangGraph thread ID. Identifies the conversation session for multi-turn interactions.
Must be included on every request in a thread to preserve conversation state.

Also referred to as `contextId` in the A2A protocol (page 904036367).

---

### `context.filters` — `Record<string, unknown[]>`

Assembled by `normalizeToArrayValues()` from three sources merged in order:

1. `globalContext.queryParams` — active URL query parameters (e.g. `?savId=SAV-001` → `{ savId: ["SAV-001"] }`)
2. `globalContext.application.context` — entity IDs from the active MFE page (see above)
3. `providedContext.filters` — any filters explicitly passed by the call site (e.g. selected table rows)

Every value is normalized to an array, even scalars.

> `filters` carries **UI state** (what the user has selected / is viewing).  
> It is explicitly **not** routing intent — routing uses `appTags` and `source`. (CXP-25805)

---

### `context.appTags` — `string[]`

> **Q3 routing signal** (CXP-25805 / CXP-25804).

An explicit list of agent tags sent by in-context "Ask AI" buttons.
The SR uses these for **Tier 1 hard-filter** routing — restricting the agent pool to only
the tagged agents.  
Default value is `[]` when no tags are passed.

**Tag → Agent mapping:**

| `appTags` value | Agent |
|---|---|
| `"iq-cases"` | Troubleshooting (TAC/PSIRTs/FNs) |
| `"iq-ldos"` | LDOS Analysis |
| `"iq-config-assessment"` | Assessments – Configuration |
| `"iq-health-risk"` | Assessments – Health Risk Insights |
| `"iq-product-rec"` | Product Recommendation |
| `"iq-security"` | Security Assessment Analysis (both assessment + hardening skills) |

---

## 3. How `buildMessageContext()` Assembles the Payload

```typescript
// ai-interaction.utils.ts
export function buildMessageContext({
  providedContext,
  globalContext,
  threadId,
}: {
  providedContext: Record<string, unknown> | undefined;
  globalContext: AiAssistantApiContext;
  threadId: string;
}): Record<string, unknown> {
  return {
    ...providedContext,                          // source, caller-provided context, appTags
    url: globalContext.url,
    language: globalContext.language,
    app: globalContext.application.id,
    application: globalContext.application,      // { id, context: { entityId... } }
    context_id: threadId,
    filters: normalizeToArrayValues({
      ...globalContext.queryParams,
      ...globalContext.application.context,      // entity IDs merged into filters
      ...((providedContext?.['filters'] ?? {}) as Record<string, unknown>),
    }),
  };
}
```

`source` and the call-site `filters` arrive via `providedContext`
(the `additionalContext` passed to `askAi()` gets wrapped inside `{ source, filters }` before reaching this function).

`appTags` is hoisted to top-level from `providedContext` (not nested inside `filters`).

---

## 4. CVI Semantic Router Routing Logic

The SR uses three routing tiers, evaluated in order:

| Tier | Condition | Behavior |
|---|---|---|
| **1 — Hard filter** | `source == "ask-ai"` + matched `appTags` | Pool restricted to matched agents only |
| **2 — Weighted preference** | `source != "ask-ai"` + `url` + `app` | Matched agents scored higher in LLM prompt; all eligible |
| **3 — Fallback** | No match | All agents eligible (same as pre-Q3) |

**URL normalization for Tier 2:**  
`"/assessments/field-notices/FN-123?tab=details"` → `"assessments:/field-notices"`

**Tier 2 route → agent mappings:**

| Composite key | Preferred agents |
|---|---|
| `assessments:/field-notices` | LDOS Analysis |
| `assessments:/security` | Security Assessment Analysis |
| `assessments:/config` | Assessments – Configuration |
| `assessments:/health` | Assessments – Health Risk Insights |
| `assessments:/` | All 4 assessment agents (catch-all) |
| `support:/` | Troubleshooting |

Thread scoping: `appTags` apply to the **first message only**.
Subsequent turns use the intent classifier for same-agent vs new-topic routing.

---

## 5. Two Levels of User Context

From the "Contextual AI Assistant" Confluence page (830177293):

| Level | What it contains |
|---|---|
| **User-level** | CCOID, name, email, company name (from platform shell / IAM) |
| **Application & page/asset-level** | CIQ app name, active filters, entity IDs (SN, asset ID, FN ID, rule ID), and asset data including serial number, connectivity, support contract, field notice info, hostname, IP address, product ID |

The payload described in this document carries the **application & page/asset-level** context.
User-level context is resolved server-side from the session cookie (CCOID).

---

## 6. Application Context as Tool Argument Helper (proposal)

The application context (`context.filters`, `context.application`) acts as a **pre-populated argument source** for tool calls. 
When the LLM selects a tool, it should check whether any of its arguments
can already be resolved from the application context before asking the user.

| Principle | Detail |
|---|---|
| The LLM classifies the question first, then selects a tool | Application context is only relevant at argument population time |
| Conditional — not always applicable | Some tools have no overlap with the UI context; the instruction must not force it |
| Avoids redundant prompting | Entity IDs already known from the UI (e.g. `fieldNoticeId`, `serialNumber`) should not be re-asked |

System prompt section with context.application or context.filters parsed

```python
"## Application Context\n"
"The following context reflects what the user is currently viewing in the UI. "
"When selecting a tool, check whether any of its arguments can be resolved "
"from this context before asking the user.\n\n"
f"{app_context}"
```

---

### How `{app_context}` Is Built — Config Best Practices Implementation

> Reference implementation: [`configbp-ai`](https://github.com/CXEPI/configbp-ai) — commit [CXP-24290](https://github.com/CXEPI/configbp-ai/commit/be70eabfeacbdc2b4aec3e229926b4bba5509389), merged to `main`.  
> Key files: `a2a_server/handlers/skill_handlers.py`, `agent/api/server.py`, `agent/services/ui_context_builder.py`.

The end-to-end flow from payload arrival to `SystemMessage` injection:

**Step 1 — Frontend sends `filters` in A2A message metadata**  
The CX Cloud frontend (via the CVI Semantic Router A2A adapter) includes the `context.filters` map from the `buildMessageContext()` payload inside `message.metadata["filters"]`. Only non-null, non-empty entries are included.

**Step 2 — `_extract_ui_filters()` strips stray nulls**  
In `a2a_server/handlers/skill_handlers.py`, the `_extract_ui_filters()` function reads `context.message.metadata["filters"]` and does a defensive pass to remove any `None` or empty-string values, returning a clean `dict`.

**Step 3 — Filters forwarded to the agent server as `ui_filters`**  
The A2A skill handler passes `ui_filters` to the agent's internal `/chat` or `/chat/stream` endpoint via `ChatRequest.ui_filters`. This is a plain `Optional[dict]` field on the Pydantic model.

**Step 4 — `build_ui_context()` processes the raw filters**  
`agent/services/ui_context_builder.py` is the core logic. It performs four sub-steps:

1. **Allowlist filtering & key normalisation** — only keys in `ALLOWED_FILTERS` pass through (~50 named filter keys covering identifiers, finding-level filters, asset-scope filters, and date/threshold filters). Variant keys ending in `Equals` (e.g. `productFamilyEquals`) are mapped to their canonical form. Single-element lists are flattened to scalar strings.

2. **MCP resolution of opaque identifiers** — `ruleId` (an opaque source ID) is resolved to a human-readable `rule_name` via the MCP tool `resolve_filter_context(resolve_type="rule")`. `assetId` (a 32-char MD5 hash or serial number) is resolved to `{hostname, serial_number, asset_key}` via `resolve_filter_context(resolve_type="asset")`. If both are present, they are resolved in parallel with `asyncio.gather()`. Results are cached (rules: indefinitely; assets: 24 h, tenant-scoped to prevent cross-tenant leakage).

3. **Markdown lines assembled** — resolved names replace raw IDs; remaining allowed filters are rendered as `- **Label**: value` lines using a human-friendly label map.

4. **Final markdown string built** — the lines are joined, then a `header` and a `footer` are constructed separately and concatenated (`return header + footer`):
   - **header** — contains the `## Application Context(UI Context)` title, the instruction to populate tool arguments from context, and the bullet lines.
   - **footer** — a fixed warning appended after the bullet lines instructing the LLM never to expose internal identifiers (rule IDs, asset keys, etc.) to the user.

**Step 5 — `_build_messages()` injects the string as a `SystemMessage`**  
In `agent/api/server.py`, if `ui_context` is non-empty, it is prepended to the message list as the first `SystemMessage` before conversation history and the user's `HumanMessage`.

**Summary flow:**

```
Frontend payload
  └─ context.filters (from buildMessageContext)
       └─ A2A message.metadata["filters"]
            └─ _extract_ui_filters()   → clean dict
                 └─ ChatRequest.ui_filters
                      └─ build_ui_context()
                           ├─ allowlist + normalise keys
                           ├─ resolve ruleId / assetId via MCP (cached)
                           └─ build markdown string
                                └─ SystemMessage(content=app_context)
                                     └─ injected first in message list to LLM
```

---

## 7. Source Files

| File | Purpose |
|---|---|
| `libs/shared/core/data-access/platform-shell-ai/src/lib/ai-interaction-store/ai-interaction.utils.ts` | `buildMessageContext()` — assembles the payload |
| `libs/shared/core/data-access/platform-shell-ai/src/lib/global-context-store/ai-assistant-global-context.models.ts` | `AiAssistantApiContext` type definition |
| `libs/shared/core/data-access/platform-shell-ai/src/lib/global-context-store/ai-assistant-global-context.store.ts` | Global context store — tracks URL, language, application |
| `libs/shared/core/data-access/platform-shell-ai/src/lib/global-context-store/with-global-ai-application-context.feature.ts` | `withGlobalAiApplicationContext()` — MFE feature to register page entity context |
| `cvi_ai_shared/core/route_mappings.py` | SR backend routing logic |
| `cvi_ai_shared/types.py` | `QuestionContext` (backend schema) |

**Jira:**  
- CXP-15402 - AI Assistant: Phase 2- Enhancements on Contextual Data
- CXP-25805 — Frontend `appTags` pass-through + `buildMessageContext()` change  
- CXP-26207 / CXP-26208 — Source-based tiered routing (Q3)  
- CXP-25133 — App Tagging epic  

**Confluence:**  
- [Contextual AI Assistant](https://cisco-cxe.atlassian.net/wiki/spaces/CVICXPM/pages/830177293) — context levels, use-case matrix  
- [CVI Semantic Router: App Tagging Design](https://cisco-cxe.atlassian.net/wiki/spaces/CIA/pages/1463943206) — routing tiers, tag inventory, route mappings  
- [AI Assistant / LDOS Agent - Engineering Handoff](https://cisco-cxe.atlassian.net/wiki/spaces/CPC/pages/1511456811) — LDOS-specific API parameters  


