# Context Switch Handling — Cross-Agent Analysis

> **Workstream:** EE-6 — Agent Behavioural Spec
>
> **Date:** 2026-04-23
>
> **Status:** Research
>
> **Owner(s):** Philip Smeuninx
>
> **Validated:** All data sourced from local clones on `main` branch (April 23 2026).

---

## 1. What This Is

UI context switching is the ability for an agent to correctly scope its responses when a user navigates between pages or entities in the Cisco IQ product UI. When a user moves from viewing advisory A to advisory B and asks "tell me about this vulnerability", the agent must resolve "this vulnerability" to advisory B (the current page), not advisory A (from conversation history).

Getting this wrong causes the most visible class of agent bugs — the user sees a confident answer about the wrong entity. This document analyses how each agent handles context switching: how UI filters are extracted, whether opaque IDs are resolved to human-readable names, what rules govern context priority, and how disambiguation is handled.

---

## 2. How It Works Today

All agents receive UI context through the same frontend payload. The Cisco IQ frontend sends `context.filters` inside the A2A `message.metadata["filters"]` dict (see [ask-ai-payload.md](../ask-ai-payload.md) for the full payload spec). Each agent then handles these filters differently.

**Common pipeline stages** (not all agents implement all stages):

| Stage | Description |
|-------|-------------|
| **Extract** | Read raw filters from A2A message metadata |
| **Normalize** | Map keys, allowlist, strip nulls |
| **Resolve** | Convert opaque IDs (e.g., `checkId: 3065`) to human-readable names (e.g., `"CVE-2024-20356 — Cisco IMC Web UI Command Injection"`) |
| **Build** | Render filters into a markdown/bracket block for LLM consumption |
| **Inject** | Insert the rendered context into the message list (SystemMessage, HumanMessage prefix, or SYSTEM_PROMPT suffix) |

**Feature matrix:**

| Agent | Extracts UI Filters | Resolves IDs → Names | Context Priority Rules | Disambiguation | Injection Method |
|---|---|---|---|---|---|
| **Config Best Practices** | Yes | Yes — MCP (rule, asset, insight) with caching | Partial — "prefer UI context when unambiguous" | Yes — 4-condition AND gate | `SystemMessage` (markdown block) |
| **Health Risk Insights** | Yes | No — uses filter labels only | Yes — 13 enumerated rules | Via rules 4 + 9 (contradicting / different asset → ask) | `HumanMessage` prefix (bracket block) |
| **Security Advisory** | Yes | No on main ¹ | No on main ¹ | No | `SYSTEM_PROMPT` suffix |
| **Security Hardening** | Yes | No on main ¹ | No on main ¹ | No | `SYSTEM_PROMPT` suffix |
| **LDOS** | Yes (structured payload) | No | No UI context rules (7 conv-history rules) | No | Filters → API (not injected into LLM prompt) |

¹ PR #1308 (CXP-29702, open) adds ID resolution + 7 enumerated context rules for both Security Advisory and Hardening — see agent sections below.

---

## 3. Implementation Analysis

### 3.1 Config Best Practices

> **Repo:** `CXEPI/configbp-ai` · **Model:** GPT-5.3-chat

**Reference implementation** — most mature context pipeline across all agents.

#### Architecture

5-step pipeline: Extract → Forward → Accept → Build → Inject.

1. **Extract** — `a2a_server/` reads `message.metadata["filters"]` via `_extract_ui_filters()`
2. **Forward** — `agent_client.py` passes `ui_filters` dict to agent server via POST body
3. **Accept** — `agent/api/server.py` receives `ChatRequest` with `ui_filters: Optional[dict]`
4. **Build** — `agent/services/ui_context_builder.py` (517 lines): allowlist ~50 filter keys, resolve opaque IDs via MCP, render to markdown
5. **Inject** — `_build_messages()` prepends the rendered context as the first `SystemMessage`

#### Key Behaviors

| Behavior | Implementation |
|----------|----------------|
| **ID Resolution** | Resolves `ruleId`, `assetId`, `insightId` via MCP tool `resolve_filter_context`. Rules cached indefinitely (~500 shared rules), assets cached 24h (tenant-scoped via JWT `initiator_account_id`, max 10k entries), insights cached indefinitely. All resolutions run in parallel via `asyncio.gather()`. |
| **Context Priority** | No enumerated rules. Relies on header instruction: *"Prefer UI context values when the user's intent is unambiguous"* and footer: *"Do not expose internal identifiers (rule IDs, asset keys, source IDs)"*. |
| **Disambiguation** | `_DISAMBIGUATION_RULE` — formal 4-condition AND gate, appended when a resolved entity exists AND conversation history is present: (1) User's current message does not explicitly name a rule/asset/insight; (2) UI Context names entity `E_ui` of some type; (3) Most recent same-type entity in history is `E_hist`, and `E_hist ≠ E_ui`; (4) Answering requires that entity. All 4 true → ask one clarification question naming both candidates by display name. No history → rule omitted (saves tokens). |

#### Key Files

| File | Purpose |
|------|----------|
| `agent/services/ui_context_builder.py` | `build_ui_context()`, `ALLOWED_FILTERS`, `_DISAMBIGUATION_RULE`, resolution helpers |
| `agent/api/server.py` | `ChatRequest`, `_build_messages()` |

#### Known Gaps

- No enumerated context priority rules (e.g., "portfolio-wide questions ignore context")
- Disambiguation rule uses abstract variable notation (`E_ui`, `E_hist`) — works for GPT-5.3 but may not generalize to weaker models

---

### 3.2 Health Risk Insights

> **Repo:** `CXEPI/cxp-health-risk-insights-ai` · **Model:** Mistral

**Strongest prompt-level rules** — 13 enumerated rules covering all context switching scenarios.

#### Architecture

3-step pipeline: Extract → Normalize → Inject (bracket prefix).

1. **Extract** — `a2a_server/handlers/skill_handlers.py`: `_extract_filters()` reads `context.filters` from `DataPart.data`
2. **Normalize** — `_normalize_upstream_filters()` maps 13 camelCase keys to snake_case via `UPSTREAM_TO_INTERNAL_FILTER_MAP`
3. **Inject** — `_build_bracket_context()` formats as `[The user is currently viewing assets with the following filters: Assessment Rating: High, Medium | Product Family: ...]` and prepends to the user's prompt (HumanMessage)

#### Key Behaviors

| Behavior | Implementation |
|----------|----------------|
| **ID Resolution** | None — filters are injected as labels (e.g., "Product Family: Cisco Catalyst 9300 Series Switches"), not resolved from opaque IDs. The `asset_id` key is explicitly skipped in bracket context building. |
| **Context Priority** | 13 enumerated rules in `SHARED_PROMPT_INSTRUCTIONS` under `# ASSET PAGE CONTEXT` (see table below). |
| **Disambiguation** | No formal rule — relies on rule 4 (contradicting → ask) and rule 9 (different asset → ask), which are less rigorous than CBP's AND gate. |

**Context priority rules (13):**

| # | Rule | Behavior |
|---|---|---|
| 1 | Default scope | Use all bracket filters as default scope for tools |
| 2 | Single-asset detail page | Serial Number + "this asset" → use that asset |
| 3 | Question aligns with context | No contradictions, not portfolio-wide → use context |
| 4 | Contradicting filter values | User mentions different values → ask which they mean |
| 5 | Specific asset by identifier | Direct hostname/serial/IP → ignore context filters |
| 6 | Additional filter dimension | New dimension from user → combine with context |
| 7 | Portfolio-wide / aggregate | "all my", "how many", "top 10" → **drop all context filters** |
| 8 | Compare / multi-asset | Include all mentioned assets |
| 9 | Different single asset | Context has serial A, user names asset B → ask which |
| 10 | Context vs. history | **Current bracket context takes precedence over conversation history** |
| 11 | Never expose internals | Don't mention "filters", "UI context", "bracket context" |
| 12 | Date filters not supported | Inform user |
| 13 | No bracket context + direct query | Answer directly without clarification |

#### Key Files

| File | Purpose |
|------|---------|
| `a2a_server/handlers/skill_handlers.py` | `_extract_filters()`, `_normalize_upstream_filters()`, `_build_bracket_context()`, `UPSTREAM_TO_INTERNAL_FILTER_MAP` |
| `agent/core/prompt.py` | `SHARED_PROMPT_INSTRUCTIONS` (13 rules), `SHARED_GUARDRAIL_INSTRUCTIONS`, `fetch_system_prompt()` |

#### Known Gaps

- No opaque ID resolution — LLM sees filter labels, not resolved entity names
- Bracket context is prepended to HumanMessage (not SystemMessage) — may have lower precedence for some models
- No formal disambiguation rule — relies on rule 4 (contradicting → ask) and rule 9 (different asset → ask) which are less rigorous than CBP's AND gate

---

### 3.3 Security Advisory

> **Repo:** `CXEPI/risk-app` · **Model:** Mistral medium-2508

**Basic filter extraction on main; full context handling in open PR #1308.**

#### Architecture (on main)

2-step pipeline: Extract → Inject (raw).

1. **Extract** — `_format_context_filter()` in `security_assessment_agent_impl.py` reads `context_filter` and `context` dicts, skips `context_id`, filters the nested `filters` dict to only `checkId` and `assetId`
2. **Inject** — Raw filter summary appended to `SYSTEM_PROMPT` with preamble *"The user is currently viewing a page with the following active context filters. Apply these as default query filters unless the user explicitly asks otherwise"*

#### Key Behaviors (on main)

| Behavior | Implementation |
|----------|----------------|
| **ID Resolution** | None — raw `checkId` (numeric psirt_id) passed to LLM. `<context_filter_mapping>` in system prompt explains that `checkId` maps to `psirts.psirt_id` / `bulletins.psirt_id`, but the LLM must interpret the raw integer. |
| **Context Priority** | Tool-selection rule 1 instructs LLM to use SQL data-query flow when runtime context includes `checkId`/`assetId` and user asks a context-referential question. No enumerated rules for portfolio-wide, context vs. history, or named-entity override. |
| **Disambiguation** | None. |

#### Pending: PR #1308 (CXP-29702)

Adds two fixes (not yet merged):

- **Fix A**: Resolves `checkId` → `headline_name` + `advisory_id` via Trino query against `bulletins` table. Injects `"The user is currently viewing advisory: "<name>" (psirt_id: X). When the user says "this vulnerability" or "this advisory", they mean this one."` ahead of raw context.
- **Fix B**: `<advisory_context_rules>` section with 7 enumerated rules: default scope, detail page deictics, aligned questions, user-names-different-advisory override, portfolio-wide trigger phrases, context vs. history precedence, never-expose-internals.

#### Key Files

| File | Purpose |
|------|---------|
| `security-advisory-ai-api/src/openapi_server/impl/security_assessment_agent_impl.py` | `_format_context_filter()`, `_resolve_sql_aliases()`, prompt assembly |
| `security-advisory-ai-api/src/openapi_server/prompts/security_assessment_v1_mistral.py` | `SYSTEM_PROMPT` with `<context_filter_mapping>`, `<instructions>` |

#### Known Gaps (on main)

- No ID resolution → LLM sees raw `checkId: 3065` instead of advisory name
- No context priority rules → "this vulnerability" resolved from conversation history instead of current page context
- This was the root cause of the CXP-29702 / context switch bug (trace `019db4bd-f9fd-7530-ba97-5d9ea0a775a7`)

---

### 3.4 Security Hardening

> **Repo:** `CXEPI/risk-app` · **Model:** Mistral medium-2508

**Same architecture as Security Advisory, same gaps, same pending PR.**

#### Architecture (on main)

Identical pattern to Security Advisory. `_format_context_filter()` extracts filters, raw summary appended to `SYSTEM_PROMPT`. `<context_filter_mapping>` maps `ruleId` → `finding.source_id`.

#### Pending: PR #1308 (CXP-29702)

- **Fix A**: Resolves `ruleId` → `rule_name` via Trino query against `finding` table
- **Fix B**: `<rule_context_rules>` section with 7 enumerated rules (analogous to Advisory's `<advisory_context_rules>`)

#### Key Files

| File | Purpose |
|------|---------|
| `security-hardening-ai-api/src/openapi_server/impl/security_assessment_agent_impl.py` | Same pattern as Advisory |
| `security-hardening-ai-api/src/openapi_server/prompts/security_assessment_v1_mistral.py` | `SYSTEM_PROMPT` with `<context_filter_mapping>` for `ruleId` |

#### Known Gaps (on main)

Same as Security Advisory — no ID resolution, no context priority rules. Susceptible to the same context switch failure pattern.

---

### 3.5 LDOS

> **Repo:** `CXEPI/cvi-ldos-ai`

**Fundamentally different architecture** — text-to-SQL pipeline, not MCP tool-calling agent.

#### Architecture

LDOS does not inject UI context into the LLM prompt. Instead:

1. **Extract** — A2A handler in `a2a/server.py` parses `QuestionPayload` from `DataPart`, including `QuestionContextFilters` (SAV IDs, other filters)
2. **SAV ID extraction** — `_extract_sav_id_into_filters_if_missing()` uses an LLM call to extract SAV IDs from the user's message + recent context when not present in filters
3. **Forward** — `QuestionPayload` (with filters) sent to LDOS API via HTTP POST
4. **API processing** — `ContextHandler.extract_filter_from_request()` processes legacy `context_filter` or new `context.filters`, generates Trino context ID, validates SAV IDs
5. **SQL pipeline** — Filters drive Trino SQL query generation; LLM receives query results for natural-language formatting

The LLM's system prompt (`ldos_readable_answer_system_prompt`) is purely for converting SQL results to natural language — it contains no context handling instructions.

#### Key Behaviors

| Behavior | Implementation |
|----------|----------------|
| **ID Resolution** | None. |
| **Context Priority** | No UI context rules. 7 conversation history rules (see below) handle multi-turn follow-ups but not page navigation. |
| **Disambiguation** | None. |

**Conversation history rules (7):**

LDOS has a sophisticated conversation history resolver (`CONVERSATION_HISTORY_CONTEXT_SYSTEM_PROMPT`):

| # | Rule | Behavior |
|---|---|---|
| 1 | Pronouns → most recent subject | "it", "they", "those devices" → resolve to highest t-value |
| 2 | Implicit follow-ups → inherit constraints | No new subject → carry forward accumulated filters |
| 3 | Self-contained → return unchanged | Full subject + scope + no pronouns → don't inject history |
| 4 | Track active constraints | Maintain running set; supersede when new scope introduced |
| 5 | Preserve intent, don't over-accumulate | Only carry constraints still logically relevant |
| 6 | Don't add absent information | Never invent filters not in history |
| 7 | Numeric selection | "2" → select 2nd suggested question from prior response |

These rules handle multi-turn follow-ups but do not address UI page context switching — if the user navigates to a different asset page, the conversation history still references the previous asset.

#### Key Files

| File | Purpose |
|------|---------|
| `a2a/server.py` | `ask_ldos_handler()`, `_parse_request_node()`, `_extract_sav_id_into_filters_if_missing()` |
| `common/context_handler_service.py` | `ContextHandler` class, `extract_filter_from_request()`, SAV ID validation |
| `common/langgraph_utils/prompts.py` | `CONVERSATION_HISTORY_CONTEXT_SYSTEM_PROMPT` (7 rules), `ldos_readable_answer_system_prompt` |

#### Known Gaps

- No UI context injection into LLM prompt — filters go to the API/SQL layer, not to the LLM
- LLM has no awareness of what page the user is viewing
- Conversation history resolver handles follow-ups well but cannot detect page navigation / context switches
- If user navigates from asset A to asset B and asks "what's the EoL date for this device?", the LLM may resolve "this device" from history (asset A) rather than the current page (asset B)

---

## 4. Cross-Agent Comparison

### 4.1 Feature Matrix

**Context pipeline maturity:**

```
CBP ████████████████████ Full (extract → resolve → build → inject + disambiguation)
HRI ██████████████████   Strong (extract → normalize → bracket inject + 13 rules)  
SA  ██████████           Basic on main / Full in PR #1308
SH  ██████████           Basic on main / Full in PR #1308
LDOS ████████            Filters to API only; no LLM context awareness
```

**Architecture comparison:**

| Aspect | ConfigBP | HRI | Risk-App (PR) | LDOS |
|--------|----------|-----|---------------|------|
| **Injection target** | SystemMessage | HumanMessage prefix | SYSTEM_PROMPT suffix | API filters (not LLM) |
| **ID resolution** | MCP tool, cached | None (labels) | Trino SQL query | N/A |
| **Disambiguation** | Formal AND gate | Enumerated ask-rules | None | N/A |
| **Context vs. history** | Implicit (UI preferred) | Rule 10 (explicit) | Rule 6 in PR (explicit) | No rule |
| **Portfolio-wide handling** | Not addressed | Rule 7 (explicit triggers) | Rule 5 in PR (explicit triggers) | N/A |

### 4.2 Observations

1. **CBP is the reference implementation** for context switching — it has the most complete pipeline (5 stages) and the most rigorous disambiguation (formal AND gate). However, it lacks enumerated context priority rules.
2. **HRI has the strongest prompt-level rules** — 13 enumerated rules cover every scenario (portfolio-wide, contradicting filters, context vs. history). But it lacks opaque ID resolution.
3. **Security Advisory / Hardening are the weakest on main** — raw IDs, no context priority rules, no disambiguation. PR #1308 closes the gap significantly with both programmatic resolution and 7 enumerated rules.
4. **LDOS is architecturally different** — filters feed the SQL pipeline, not the LLM. The LLM has no awareness of what page the user is viewing, making UI context switches invisible to it.
5. **No agent has all best practices** — the ideal implementation would combine CBP's ID resolution + HRI's enumerated rules + CBP's formal disambiguation.

---

## 5. Recommendations

### 5.1 Per-Agent

1. **Security Advisory / Hardening**: Merge PR #1308 — it addresses the root cause of CXP-29702 with both programmatic resolution (Fix A) and prompt rules (Fix B)
2. **LDOS**: Consider injecting a bracket context block (similar to HRI) into the conversation history resolution prompt when UI filters are present — this would let the LLM know what asset the user is currently viewing
3. **CBP**: Consider adding enumerated context priority rules (like HRI's 13 rules) to handle portfolio-wide questions and explicit context vs. history precedence — the disambiguation rule alone doesn't cover these cases

### 5.2 Programmatic Context Switch Detection

**Proposal:** Detect context switches programmatically *before* any LLM/agent invocation, rather than relying on the LLM to infer the switch from prompt rules.

**How it works:** Compare `context.filters` from the current request with the filters stored from the previous turn in conversation history. If entity-identifying keys changed (`checkId`, `ruleId`, `assetId`, `serialNumber`, etc.) → context switch detected. If first message or same filters → no switch. This is a pure dict diff — no LLM call needed.

```python
# Proposed shared utility (location TBD)
def detect_context_switch(
    current_filters: dict,
    previous_filters: dict | None,
) -> ContextSwitchResult:
    """Returns: no_switch | entity_changed | filters_narrowed | filters_cleared"""
```

**Where to put it:** TBD — to be discussed with the team. Every agent already extracts filters from the A2A payload. The missing piece is persisting the previous turn's filters — most agents already have conversation history, so this means attaching filter metadata to it.

**Primary benefit — lighter system prompts:** The context switch detection result drives conditional prompt injection. Only include context switch rules when a switch is actually detected. This reduces system prompt weight for the majority of turns (no switch).

**Prompt layering model:**

| Layer | When injected | Content |
|-------|--------------|---------|
| **Always present** (lightweight) | Every turn | "Use current UI context as default scope. Don't expose filter internals." |
| **Context switch** | Only when `entity_changed` detected | "Context has changed from [old entity] to [new entity]. The user is now viewing [new entity]. Disregard references to [old entity] in conversation history unless the user explicitly refers back to it." |
| **Disambiguation** (CBP-style) | When history exists | Formal AND gate for conversational entity switches where the user names a different entity without changing pages. |

**Additional benefits:**

1. **Conversation history pruning** — optionally drop or tag stale history turns that reference the old entity, preventing the LLM from carrying forward outdated context
2. **Metrics / observability** — log context switch events to LangSmith (how often do users switch mid-conversation? does switching correlate with lower quality answers?)

**Caveat:** Programmatic detection only catches UI-level switches (filter changes from page navigation). It does not catch *conversational* entity switches where the user names a different entity without changing pages ("what about the 9400 instead?"). CBP's disambiguation rule handles that case and must remain in the prompt as the "disambiguation" layer above.
