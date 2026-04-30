# Agent Skill Routing — Cross-Agent Analysis

> **Workstream:** EE-5 — Agent Behavioural Spec
>
> **Date:** 2026-04-30
>
> **Status:** Research
>
> **Owner(s):** Philip Smeuninx

---

## 1. What This Is

Every Cisco IQ domain agent is invoked by an upstream **Semantic Router** that selects, on behalf of the user, which **agent skill** the agent should execute. The selected skill id is delivered alongside the user prompt at the time of invocation (e.g. `ask_security_assessment`, `ask_cvi_ldos_ai_external`, `assessment-rating-capabilities`, `assessments-configuration-summary`, …).

Each agent must therefore answer four behavioural questions:

1. **Where** does the skill id arrive in the payload?
2. **Is it validated** against the skills the agent actually advertises (its AgentCard)?
3. **How is it used internally** — to pick a prompt? a tool set? a sub-graph? a downstream endpoint?
4. **What happens when the user's prompt is out of scope** for the selected skill — does the agent perform its own intent classification, refuse, or silently answer anyway?

This document analyses how each agent answers those questions today and compares the approaches.

---

## 2. How It Works Today

The end-to-end invocation path is the same for every agent:

```
User prompt
  → Semantic Router (selects an agent + skill_id from a global skill catalog)
  → Agent endpoint
       • A2A agents: skill_id arrives in A2A Message.metadata
       • FastAPI agents: skill_id arrives in the JSON request body (skill_id field)
  → Agent extracts skill_id (with a hardcoded default if absent)
  → Agent uses skill_id to derive: system prompt, optional sub-graph, downstream endpoint
  → LLM + tools execute
```

**Key shared facts:**

- The Semantic Router is **trusted**. No agent re-runs intent classification on the user prompt to verify the router's choice.
- The shared library `cvi_ai_shared` exposes `Skills` types (including `min_entitlement_tier`) used to register an agent in the router catalog, but provides **no helper for extracting, validating, or dispatching on skill id** — every agent does that itself.
- The A2A framework (`cvi-ai-a2a`) does not enforce that `Message.metadata["skill_id"]` matches one of the `AgentCard.skills` it served — validation, if any, is entirely the agent's responsibility.

**The skill id is renamed three times along the path:**

```
AgentChoice.agent_skill                     (router decision, in the SR routing graph)
    → cx_routed_skill                       (stamped onto SR internal state for LangSmith / observability)
    → MessageSendParams.metadata["skill_id"] (A2A wire — see below)
    → context.metadata["skill_id"]          (what every agent executor reads)
    → effective_intent                      (only inside ConfigBP's graph state)
```

The wire detail matters: `cvi_ai_shared.core.payloads.question_payload_to_a2a_request()` puts the router-selected skill into **`MessageSendParams.metadata`**, not `Message.metadata`. All other agent context (`app`, `source`, `url`, `filters`, `language`, `cco_id`, `conversation_id`, `task_id`, …) is placed in `Message.metadata`. The two layers are merged by the a2a-sdk before they reach the agent's `RequestContext.metadata`, so agent code can't tell them apart — but the split exists on the wire and is non-obvious.

> **Naming-churn observation.** `agent_skill` (router model) → `cx_routed_skill` (router state) → `skill_id` (A2A wire) → `effective_intent` (ConfigBP graph) is four names for the same value. The internal SR fields `agent_skill` and `cx_routed_skill` are also surfaced verbatim in the conversation history (`recent_context_structured.chat_history[*].agent_skill`) and in any payload dumps a developer inspects, which is a frequent source of confusion when reasoning about what the agent actually receives.

---

## 3. Implementation Analysis

### 3.1 Config Best Practices

> **Repo:** `CXEPI/configbp-ai`

#### Architecture

**Two inbound paths converging on one graph:**

1. **A2A path (production, used by the Semantic Router)** — `A2AStarletteApplication` serves the AgentCard on port 9000. `ConfigBPAgentExecutor.execute()` extracts `skill_id` from `context.metadata` and dispatches to a registered skill handler, which in turn POSTs to the internal FastAPI `/chat` endpoint with `skill_id` in the body.
2. **Direct FastAPI path** — `POST /chat` and `POST /chat/stream` accept `ChatRequest.skill_id` directly. Used for local testing and any non-A2A callers.

Both paths feed the same LangGraph: `flow_router → assistant ⇄ tools`.

#### Key Behaviors

**Skill plumbing:**

| Aspect | Implementation |
|--------|----------------|
| **Inbound field** | A2A: `context.metadata["skill_id"]`. FastAPI: `ChatRequest.skill_id` (optional) on `POST /chat`. |
| **Default** | `DEFAULT_SKILL_ID = "assessments-configuration-summary"` (applied in both the A2A executor and the FastAPI handler) |
| **State key** | Renamed to `effective_intent` and injected into the graph input dict (`{"messages": ..., "effective_intent": resolved}`) |
| **Validation sets** | Two independent surfaces: (a) A2A `_registry` populated by `@register_skill(...)` decorators in `a2a_server/handlers/skill_handlers.py` (4 skills registered: `assessments-configuration-summary`, `asset-scope-analysis`, `rule-analysis`, `signature-asset-insights`); (b) `_VALID_SKILLS` set in `agent/nodes/assistant.py` used only for the prompt-template lookup. |
| **Validation behaviour** | A2A: unknown `skill_id` → `get_skill_handler()` returns a silent no-op (same hang behaviour as LDOS / Risk-App). FastAPI direct call: no validation; flows through to the graph and silently falls back to `DEFAULT_SKILL_ID` for prompt lookup if `effective_intent ∉ _VALID_SKILLS`. |
| **Routing use** | All four registered A2A skill handlers funnel into `_generic_skill_handler(...)`, which forwards the same `skill_id` over HTTP to `/chat`. Inside the graph, `effective_intent` is **only** used in `_fetch_system_prompt(effective_intent)` to pull the matching MCP prompt template. It does **not** drive node routing — the `flow_router` node switches on `flow_type` (`"chat"` vs `"expertInsightsAsync"`), not on the skill. |
| **Tool selection** | Same tool set for all skills |
| **Intent classification** | None |
| **Out-of-scope handling** | None — the assistant LLM answers regardless of whether the user's prompt fits the selected skill |

**Graph structure:**
```
A2A executor → skill handler → HTTP POST /chat ─┐
                                                ├─→ START → flow_router → assistant ⇄ tools → END
Direct POST /chat ──────────────────────────────┘                ↑           ↑          |
                                                          (flow_type)        └──────────┘  (tool-calling loop)
```

#### Key Files

| File | Purpose |
|------|---------|
| `a2a_server/app.py` | `A2AStarletteApplication`, `build_app()`, `AGENT_CARD` |
| `a2a_server/config/agent_card.py` | `AgentCard` with 4 `AgentSkill`s |
| `a2a_server/core/executor.py` | `ConfigBPAgentExecutor.execute()` — extracts `skill_id` from metadata, dispatches via registry |
| `a2a_server/core/skill_registry.py` | `_registry`, `register_skill`, `get_skill_handler` |
| `a2a_server/handlers/skill_handlers.py` | 4 `@register_skill(...)` handlers; all call `_generic_skill_handler(... skill_id)` |
| `a2a_server/client/agent_client.py` | `AgentBackendClient.call_agent_api()` — POSTs to internal `/chat` with `skill_id` |
| `agent/api/server.py` | `ChatRequest.skill_id`, builds graph input as `effective_intent` |
| `agent/core/state.py` | `AgentState.effective_intent: Optional[str]` |
| `agent/core/config.py` | `DEFAULT_SKILL_ID` |
| `agent/nodes/assistant.py` | `_VALID_SKILLS`, `_fetch_system_prompt(effective_intent)` |
| `agent/nodes/flow_router.py` | Branches on `flow_type` (not skill) |

#### Known Gaps

- Public API field is `skill_id`, internal graph state uses `effective_intent` — diverges from every other agent
- Two independent validation sources of truth (`_registry` in A2A layer, `_VALID_SKILLS` in graph layer) that can drift apart from each other and from the AgentCard
- A2A unknown skill → silent no-op (request hangs); direct FastAPI unknown skill → silent fallback to default — same field, two different failure modes depending on the caller
- Skill influences only the prompt; no tool/guardrail/schema selection. The 4 registered A2A handlers all collapse into the same `_generic_skill_handler`, so the registry split is structural only

---

### 3.2 LDOS (Asset General / Asset Criticality)

> **Repo:** `CXEPI/cvi-ldos-ai`

#### Architecture

A2A `AgentExecutor` in front of a thin API request handler. Two AgentCards are served by the same process:

- **Assets (General)** — skills `ask_cvi_ldos_ai_internal`, `ask_cvi_ldos_ai_external`
- **Asset Criticality** — skill `ask_asset_criticality`

#### Key Behaviors

**Skill plumbing:**

| Aspect | Implementation |
|--------|----------------|
| **Inbound field** | `context.metadata["skill_id"]` on the A2A `RequestContext` |
| **Default** | `"ask_cvi_ldos_ai_external"` |
| **Validation set** | Hardcoded `_registry` dict populated by `@register_skill(...)` decorators (`a2a/server.py` ≈ L1053–1055 — all three skills registered) |
| **Validation behaviour** | `get_skill_handler(skill_id)` returns a **silent no-op** if the id is not in the registry. The A2A request never enqueues an event; the call effectively hangs from the user's perspective. |
| **Routing use** | All three registered skills point at the **same** handler (`ask_ldos_handler`). The handler reads `skill_id` but **does not branch on it**. The actual divergence (internal vs external dataset) is decided by `check_if_customer(x_authz)`, which selects the downstream endpoint (`ask`/`ask-internal`/`ask-external`) — **authorization, not skill, is what discriminates**. |
| **Tool selection** | N/A — delegates to the LDOS API |
| **Intent classification** | None at the skill level. (LDOS does perform LLM-based **SAV ID** extraction/validation for internal users — but that is entity extraction, not skill-fit classification.) |
| **Out-of-scope handling** | None — same handler runs whichever of the three skills the router picked |

#### Key Files

| File | Purpose |
|------|---------|
| `a2a/server.py` | `build_app()` / `build_criticality_app()` (AgentCards), `get_skill_handler()`, `CVILDOSExecutor.execute()`, `@register_skill(...)` decorators, `ask_ldos_handler()` |
| `a2a/skills.py` | `AgentSkill` definitions used to populate the AgentCards |

#### Known Gaps

- Three distinct skills funnel into one handler — the skill id is effectively decorative
- Internal vs external is decided by authz, so a router that picks `ask_cvi_ldos_ai_external` for an internal user would still be overridden — the skill id from the router is, in practice, ignored for the only thing it could meaningfully drive
- Unknown skill → silent no-op → request hang with no error to the user

---

### 3.3 Security Advisory / Security Hardening

> **Repo:** `CXEPI/risk-app`

Both agents are structurally identical; only the AgentCard skill id differs (`ask_security_assessment` vs `ask_security_hardening`) and the downstream Security Assessment / Hardening API.

#### Architecture

A2A `AgentExecutor` in front of a single monolithic async handler that calls the Security Assessment / Hardening API.

#### Key Behaviors

**Skill plumbing:**

| Aspect | Implementation |
|--------|----------------|
| **Inbound field** | `context.metadata["skill_id"]` on the A2A `RequestContext` |
| **Default** | `"ask_security_assessment"` (advisory) / `"ask_security_hardening"` (hardening) |
| **Validation set** | Same `_registry` + `@register_skill(...)` pattern; exactly one skill registered per agent |
| **Validation behaviour** | Unknown skill → silent no-op handler; no event enqueued |
| **Routing use** | One skill ↔ one handler ↔ one downstream API. The skill id is read but does not parameterise anything inside the handler. |
| **Tool selection** | N/A — delegates to the Security Assessment / Hardening API |
| **Intent classification** | None |
| **Out-of-scope handling** | None at the skill layer. (Each agent does run output guardrails on the LLM response, but those check the response content, not whether the user prompt matched the selected skill.) |

#### Key Files

| File | Purpose |
|------|---------|
| `security-advisory-ai-a2a/server.py` | `AgentCard` (single skill), `get_skill_handler`, `CVISecurityAssessmentExecutor.execute()`, `@register_skill("ask_security_assessment")` |
| `security-hardening-ai-a2a/server.py` | Identical structure for `ask_security_hardening` |

#### Known Gaps

- Single-skill agents using a registry pattern designed for multi-skill dispatch — over-engineered for current scope, but also means no validation cost is being paid even though it could be
- Silent no-op on unknown skill (same hang-without-error behaviour as LDOS)

---

### 3.4 Health Risk Insights (Assessment Rating)

> **Repo:** `CXEPI/cxp-health-risk-insights-ai`

#### Architecture

FastAPI `/chat` endpoint feeding a LangGraph (`assistant ⇄ execute_tools`). A2A skill handler also exists for inbound A2A traffic.

#### Key Behaviors

**Skill plumbing:**

| Aspect | Implementation |
|--------|----------------|
| **Inbound field** | `ChatRequest.skill_id` on `POST /chat` (and A2A metadata via the A2A handler) |
| **Default** | `DEFAULT_SKILL_ID = "assessment-rating-capabilities"` |
| **State key** | `AgentState.skill_id: Optional[str]` (consistent naming, unlike ConfigBP) |
| **Validation set** | `VALID_INTENTS = ["assessment-rating-analysis-query", "assessment-rating-capabilities"]` defined in `agent/core/config.py` — **declared but never referenced** anywhere in the runtime path |
| **Validation behaviour** | None enforced. An unknown skill id flows straight through to `fetch_system_prompt(skill_id)`; if MCP returns nothing, a generic fallback prompt is used and the LLM still responds. |
| **Routing use** | Same single graph for every skill. `skill_id` is used only to fetch the matching MCP prompt template. |
| **Tool selection** | Same tool set for all skills |
| **Intent classification** | None |
| **Out-of-scope handling** | None — the LLM answers whatever the user asked under whichever prompt was loaded |

#### Key Files

| File | Purpose |
|------|---------|
| `agent/api/server.py` | `ChatRequest.skill_id`, builds graph input |
| `agent/core/state.py` | `AgentState.skill_id` |
| `agent/core/config.py` | `DEFAULT_SKILL_ID`, `VALID_INTENTS` (unused) |
| `agent/nodes/assistant.py` | `fetch_system_prompt(skill_id)` |
| `a2a_server/handlers/skill_handlers.py` | A2A inbound handler that forwards skill id to the graph |

#### Known Gaps

- `VALID_INTENTS` is dead code — the intent it implies (validation) is not actually performed
- MCP prompt fetch failure on an unknown skill silently degrades to a generic prompt, with no user-visible signal that the router/agent disagreed

---

## 4. Cross-Agent Comparison

### 4.1 Feature Matrix

| Aspect | ConfigBP | LDOS | Risk-App (Adv/Hard) | HRI |
|--------|----------|------|---------------------|-----|
| **Inbound transport** | A2A metadata (prod) + FastAPI body (direct) | A2A metadata | A2A metadata | FastAPI body (+ A2A) |
| **Inbound field name** | `skill_id` | `skill_id` | `skill_id` | `skill_id` |
| **Internal field name** | `effective_intent` | (handler-local) | (handler-local) | `skill_id` |
| **Default if missing** | `assessments-configuration-summary` | `ask_cvi_ldos_ai_external` | `ask_security_assessment` / `ask_security_hardening` | `assessment-rating-capabilities` |
| **Validates against AgentCard?** | No | No | No | No |
| **Has a "valid skills" set in code?** | Yes — **two** (`_registry` in A2A + `_VALID_SKILLS` in graph) | Yes (`_registry`) | Yes (`_registry`) | Yes (`VALID_INTENTS`) |
| **Is that set actually enforced?** | A2A: yes (no-op). Graph: partial (falls back to default for prompt lookup). | Yes — unknown skill → no-op | Yes — unknown skill → no-op | **No — declared but unused** |
| **Behaviour on unknown skill** | A2A: **silent no-op; hangs**. Direct: silent fallback; LLM answers. | **Silent no-op; request hangs** | **Silent no-op; request hangs** | Generic prompt; LLM still answers |
| **Skill drives system prompt?** | Yes (via MCP template) | No | No (single skill per agent) | Yes (via MCP template) |
| **Skill drives tool selection?** | No | No | No | No |
| **Skill drives sub-graph routing?** | No (router branches on `flow_type`) | No (one handler for all skills) | No (one skill per agent) | No |
| **Skill drives downstream endpoint?** | No | **No** — endpoint chosen by `x_authz` (customer vs internal), not skill | No | No |
| **Performs intent classification?** | No | No (SAV-ID extraction is entity, not intent) | No | No |
| **Out-of-scope detection?** | No | No | No | No |
| **Out-of-scope refusal?** | No | No | No | No |
| **Uses shared lib for skill handling?** | No (no helper exists) | No | No | No |

### 4.2 Observations

1. **Every agent blindly trusts the Semantic Router.** None re-classifies the user prompt against the selected skill, and none refuse when the prompt is clearly off-topic for the chosen skill. The router is a single point of correctness for routing decisions.

2. **No agent validates the skill id against its own AgentCard.** Four different ad-hoc validation surfaces exist (`_VALID_SKILLS`, `_registry`×2, `VALID_INTENTS`) and none of them are tied back to the `AgentSkill` list the agent advertises. A skill renamed in the AgentCard would silently break with no compile-time or startup-time error.

3. **Unknown-skill behaviour splits along framework lines.** Every A2A inbound path (LDOS, Risk-App×2, and ConfigBP when called via the Semantic Router) silently no-ops — the request enqueues nothing and the user sees a hang. The non-A2A paths (HRI's `/chat`, ConfigBP's direct `/chat`) silently fall back to a default prompt and answer anyway. Both are bad in different ways: A2A hides errors as timeouts, direct FastAPI hides errors as plausible answers. ConfigBP exhibits **both** failure modes depending on which inbound transport is used.

4. **The skill id rarely drives anything meaningful.** Across all four codebases the skill id influences only the **system prompt** (ConfigBP, HRI) — and even then only via an MCP fetch that itself silently falls back. It never drives tool selection, sub-graph routing, schema selection, or guardrail policy. LDOS registers three skills that collapse into one handler, with the actual data-scope decision made by authorization. ConfigBP registers four A2A skill handlers that all collapse into one `_generic_skill_handler` — the registry split is structural only.

5. **HRI has the worst signal/noise ratio on validation.** `VALID_INTENTS` is declared in config but never referenced — a reader is led to believe validation exists when it does not.

6. **ConfigBP is the only agent that renames the parameter internally.** Public field is `skill_id`, internal state is `effective_intent`. This adds friction for cross-agent debugging and search.

7. **No entitlement enforcement at the agent layer.** `cvi_ai_shared.types.Skills.min_entitlement_tier` exists for router-side catalog metadata but is never consulted by an agent at invocation time.

8. **No shared helper.** Each agent re-implements skill extraction, default selection, and (such as it is) validation. A `cvi_ai_shared` helper analogous to `post_working_update_to_a2a_handler()` would naturally live here.

---

## 5. Recommendations

1. **Define a skill-handling contract in `cvi_ai_shared`.** Provide `extract_skill_id(context_or_body, *, allowed: set[str], default: str) -> str` and a paired `assert_skill_in_agent_card(skill_id, agent_card)` so that every agent extracts and validates the same way.

2. **Validate against the AgentCard at startup, not against ad-hoc lists.** Replace `_VALID_SKILLS`, `_registry`, and `VALID_INTENTS` with a single check that enumerates `AgentCard.skills`. A renamed skill should fail loud.

3. **Standardize unknown-skill behaviour.** Pick one of:
   - return a structured 4xx / A2A error with `skill_id_unknown` (preferred — visible to caller and observable in traces); or
   - fall back to a documented default and emit a `worklog` step update saying so.
   The current mix of silent hangs and silent fallbacks must end.

4. **Add an out-of-scope guardrail (RFC under EE-5).** Either a lightweight LLM intent check at agent entry or a structured refusal path when the LLM itself signals "this isn't what I'm for". The router cannot be the only line of defence.

5. **Standardize the parameter name to `skill_id` everywhere.** Rename ConfigBP's `effective_intent` to align with the other three agents.

6. **Make the skill id actually mean something, or remove it.** Either:
   - have the skill id drive prompt + tool subset + (where applicable) downstream endpoint, with the AgentCard documenting what each skill enables; or
   - collapse single-skill agents (Security Advisory, Security Hardening, Asset Criticality) to not require a skill id at all.

7. **Wire `min_entitlement_tier` into agent entry checks** (or document explicitly that entitlement enforcement is a router-only concern and remove the field from the agent-side type).

8. **Standardize on a single name for the skill id end-to-end.** Eliminate the `agent_skill` / `cx_routed_skill` / `skill_id` / `effective_intent` churn — use `skill_id` from the router decision through to agent state. Document the two-layer A2A metadata convention (`MessageSendParams.metadata` vs `Message.metadata`) so developers stop expecting `skill_id` to live alongside the other context fields in `Message.metadata`.
