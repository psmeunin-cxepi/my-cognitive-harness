# Context Switch Handling Across Cisco IQ Agents

How each Cisco IQ domain agent handles UI context switching — the ability to correctly scope LLM responses when a user navigates between pages or entities in the product UI.

> **Validated**: All data sourced from local clones on `main` branch (April 23 2026), except Health Check (unverified).

---

## Cross-Agent Research Summary

| Agent | Repo | Model | Extracts UI Filters | Resolves IDs → Names | Context Priority Rules | Disambiguation | Injection Method |
|---|---|---|---|---|---|---|---|
| **Config Best Practices** | `CXEPI/configbp-ai` | GPT-5.3-chat | Yes | Yes — MCP (rule, asset, insight) with caching | Partial — "prefer UI context when unambiguous" | Yes — 4-condition AND gate | `SystemMessage` (markdown block) |
| **Health Risk Insights** | `CXEPI/cxp-health-risk-insights-ai` | Mistral | Yes | No — uses filter labels only | Yes — 13 enumerated rules | Via rules 4 + 9 (contradicting / different asset → ask) | `HumanMessage` prefix (bracket block) |
| **Security Advisory** | `CXEPI/risk-app` | Mistral medium-2508 | Yes | No on main ¹ | No on main ¹ | No | `SYSTEM_PROMPT` suffix |
| **Security Hardening** | `CXEPI/risk-app` | Mistral medium-2508 | Yes | No on main ¹ | No on main ¹ | No | `SYSTEM_PROMPT` suffix |
| **LDOS** | `CXEPI/cvi-ldos-ai` | TBD | Yes (structured payload) | No | No UI context rules (7 conv-history rules) | No | Filters → API (not injected into LLM prompt) |
| **Health Check** | `CXEPI/healthcheck-ai-poc` | TBD | Not verified | Not verified | Not verified | Not verified | Not verified |

¹ PR #1308 (CXP-29702, open) adds ID resolution + 7 enumerated context rules for both Security Advisory and Hardening — see agent sections below.

---

## Config Best Practices (CBP)

**Reference implementation** — most mature context pipeline across all agents.

### Architecture

5-step pipeline: Extract → Forward → Accept → Build → Inject.

1. **Extract** — `a2a_server/` reads `message.metadata["filters"]` via `_extract_ui_filters()`
2. **Forward** — `agent_client.py` passes `ui_filters` dict to agent server via POST body
3. **Accept** — `agent/api/server.py` receives `ChatRequest` with `ui_filters: Optional[dict]`
4. **Build** — `agent/services/ui_context_builder.py` (517 lines): allowlist ~50 filter keys, resolve opaque IDs via MCP, render to markdown
5. **Inject** — `_build_messages()` prepends the rendered context as the first `SystemMessage`

### ID Resolution

Resolves `ruleId`, `assetId`, and `insightId` via MCP tool `resolve_filter_context`:
- Rules: cached indefinitely (shared across tenants, ~500 rules)
- Assets: cached 24h, tenant-scoped via JWT `initiator_account_id`, max 10k entries
- Insights: cached indefinitely
- All resolutions run in parallel via `asyncio.gather()`

### Context Priority

No enumerated rules in the system prompt. Instead relies on:
- Header instruction: *"Prefer UI context values when the user's intent is unambiguous"*
- Footer: *"Do not expose internal identifiers (rule IDs, asset keys, source IDs)"*

### Disambiguation

`_DISAMBIGUATION_RULE` — a formal 4-condition AND gate appended when a resolved entity exists AND conversation history is present:

1. User's current message does not explicitly name a rule, asset, or insight
2. UI Context names entity `E_ui` of some type (rule / asset / insight)
3. Most recent same-type entity in Conversation History is `E_hist`, and `E_hist ≠ E_ui`
4. Answering the question requires that entity

When all 4 are true → ask one clarification question naming both candidates by display name. When no history exists, the rule is omitted entirely (saves tokens).

### Key Files

- [agent/services/ui_context_builder.py](https://github.com/CXEPI/configbp-ai) — `build_ui_context()`, `ALLOWED_FILTERS`, `_DISAMBIGUATION_RULE`, resolution helpers
- [agent/api/server.py](https://github.com/CXEPI/configbp-ai) — `ChatRequest`, `_build_messages()`

### Known Gaps

- No enumerated context priority rules (e.g., "portfolio-wide questions ignore context")
- Disambiguation rule uses abstract variable notation (`E_ui`, `E_hist`) — works for GPT-5.3 but may not generalize to weaker models

---

## Health Risk Insights (HRI)

**Strongest prompt-level rules** — 13 enumerated rules covering all context switching scenarios.

### Architecture

3-step pipeline: Extract → Normalize → Inject (bracket prefix).

1. **Extract** — `a2a_server/handlers/skill_handlers.py`: `_extract_filters()` reads `context.filters` from `DataPart.data`
2. **Normalize** — `_normalize_upstream_filters()` maps 13 camelCase keys to snake_case via `UPSTREAM_TO_INTERNAL_FILTER_MAP`
3. **Inject** — `_build_bracket_context()` formats as `[The user is currently viewing assets with the following filters: Assessment Rating: High, Medium | Product Family: ...]` and prepends to the user's prompt (HumanMessage)

### ID Resolution

None — filters are injected as labels (e.g., "Product Family: Cisco Catalyst 9300 Series Switches"), not resolved from opaque IDs. The `asset_id` key is explicitly skipped in bracket context building.

### Context Priority Rules

13 enumerated rules in `SHARED_PROMPT_INSTRUCTIONS` under `# ASSET PAGE CONTEXT`:

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

### Key Files

- [a2a_server/handlers/skill_handlers.py](https://github.com/CXEPI/cxp-health-risk-insights-ai) — `_extract_filters()`, `_normalize_upstream_filters()`, `_build_bracket_context()`, `UPSTREAM_TO_INTERNAL_FILTER_MAP`
- [agent/core/prompt.py](https://github.com/CXEPI/cxp-health-risk-insights-ai) — `SHARED_PROMPT_INSTRUCTIONS` (13 rules), `SHARED_GUARDRAIL_INSTRUCTIONS`, `fetch_system_prompt()`

### Known Gaps

- No opaque ID resolution — LLM sees filter labels, not resolved entity names
- Bracket context is prepended to HumanMessage (not SystemMessage) — may have lower precedence for some models
- No formal disambiguation rule — relies on rule 4 (contradicting → ask) and rule 9 (different asset → ask) which are less rigorous than CBP's AND gate

---

## Security Advisory

**Basic filter extraction on main; full context handling in open PR #1308.**

### Architecture (on main)

2-step pipeline: Extract → Inject (raw).

1. **Extract** — `_format_context_filter()` in `security_assessment_agent_impl.py` reads `context_filter` and `context` dicts, skips `context_id`, filters the nested `filters` dict to only `checkId` and `assetId`
2. **Inject** — Raw filter summary appended to `SYSTEM_PROMPT` with preamble *"The user is currently viewing a page with the following active context filters. Apply these as default query filters unless the user explicitly asks otherwise"*

### ID Resolution (on main)

None — raw `checkId` (numeric psirt_id) passed to LLM. The `<context_filter_mapping>` section in the system prompt explains that `checkId` maps to `psirts.psirt_id` / `bulletins.psirt_id`, but the LLM must interpret the raw integer.

### Context Priority Rules (on main)

Tool-selection rule 1 instructs the LLM to use SQL data-query flow first when runtime context includes `checkId`/`assetId` and the user asks a context-referential question. No enumerated rules for portfolio-wide questions, context vs. history, or named-entity override.

### Pending: PR #1308 (CXP-29702)

Adds two fixes (not yet merged):

- **Fix A**: Resolves `checkId` → `headline_name` + `advisory_id` via Trino query against `bulletins` table. Injects `"The user is currently viewing advisory: "<name>" (psirt_id: X). When the user says "this vulnerability" or "this advisory", they mean this one."` ahead of raw context.
- **Fix B**: `<advisory_context_rules>` section with 7 enumerated rules: default scope, detail page deictics, aligned questions, user-names-different-advisory override, portfolio-wide trigger phrases, context vs. history precedence, never-expose-internals.

### Key Files

- [security-advisory-ai-api/src/openapi_server/impl/security_assessment_agent_impl.py](https://github.com/CXEPI/risk-app) — `_format_context_filter()`, `_resolve_sql_aliases()`, prompt assembly
- [security-advisory-ai-api/src/openapi_server/prompts/security_assessment_v1_mistral.py](https://github.com/CXEPI/risk-app) — `SYSTEM_PROMPT` with `<context_filter_mapping>`, `<instructions>`

### Known Gaps (on main)

- No ID resolution → LLM sees raw `checkId: 3065` instead of advisory name
- No context priority rules → "this vulnerability" resolved from conversation history instead of current page context
- This was the root cause of the CXP-29702 / context switch bug (trace `019db4bd-f9fd-7530-ba97-5d9ea0a775a7`)

---

## Security Hardening

**Same architecture as Security Advisory, same gaps, same pending PR.**

### Architecture (on main)

Identical pattern to Security Advisory. `_format_context_filter()` extracts filters, raw summary appended to `SYSTEM_PROMPT`. `<context_filter_mapping>` maps `ruleId` → `finding.source_id`.

### Pending: PR #1308 (CXP-29702)

- **Fix A**: Resolves `ruleId` → `rule_name` via Trino query against `finding` table
- **Fix B**: `<rule_context_rules>` section with 7 enumerated rules (analogous to Advisory's `<advisory_context_rules>`)

### Key Files

- [security-hardening-ai-api/src/openapi_server/impl/security_assessment_agent_impl.py](https://github.com/CXEPI/risk-app) — same pattern as Advisory
- [security-hardening-ai-api/src/openapi_server/prompts/security_assessment_v1_mistral.py](https://github.com/CXEPI/risk-app) — `SYSTEM_PROMPT` with `<context_filter_mapping>` for `ruleId`

### Known Gaps (on main)

Same as Security Advisory — no ID resolution, no context priority rules. Susceptible to the same context switch failure pattern.

---

## LDOS

**Fundamentally different architecture** — text-to-SQL pipeline, not MCP tool-calling agent.

### Architecture

LDOS does not inject UI context into the LLM prompt. Instead:

1. **Extract** — A2A handler in `a2a/server.py` parses `QuestionPayload` from `DataPart`, including `QuestionContextFilters` (SAV IDs, other filters)
2. **SAV ID extraction** — `_extract_sav_id_into_filters_if_missing()` uses an LLM call to extract SAV IDs from the user's message + recent context when not present in filters
3. **Forward** — `QuestionPayload` (with filters) sent to LDOS API via HTTP POST
4. **API processing** — `ContextHandler.extract_filter_from_request()` processes legacy `context_filter` or new `context.filters`, generates Trino context ID, validates SAV IDs
5. **SQL pipeline** — Filters drive Trino SQL query generation; LLM receives query results for natural-language formatting

The LLM's system prompt (`ldos_readable_answer_system_prompt`) is purely for converting SQL results to natural language — it contains no context handling instructions.

### Conversation History Handling

LDOS has a sophisticated conversation history resolver (`CONVERSATION_HISTORY_CONTEXT_SYSTEM_PROMPT`) with 7 rules:

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

### Key Files

- [a2a/server.py](https://github.com/CXEPI/cvi-ldos-ai) — `ask_ldos_handler()`, `_parse_request_node()`, `_extract_sav_id_into_filters_if_missing()`
- [common/context_handler_service.py](https://github.com/CXEPI/cvi-ldos-ai) — `ContextHandler` class, `extract_filter_from_request()`, SAV ID validation
- [common/langgraph_utils/prompts.py](https://github.com/CXEPI/cvi-ldos-ai) — `CONVERSATION_HISTORY_CONTEXT_SYSTEM_PROMPT` (7 rules), `ldos_readable_answer_system_prompt`

### Known Gaps

- No UI context injection into LLM prompt — filters go to the API/SQL layer, not to the LLM
- LLM has no awareness of what page the user is viewing
- Conversation history resolver handles follow-ups well but cannot detect page navigation / context switches
- If user navigates from asset A to asset B and asks "what's the EoL date for this device?", the LLM may resolve "this device" from history (asset A) rather than the current page (asset B)

---

## Health Check

**Not Verified** — PoC status, no local clone available, GitHub MCP tools disabled during validation.

Based on the repo structure (`hc_agent.py`, `hcmcp/`, `hc_api.py`, `intents/`), this is a lightweight PoC that likely does not implement full UI context handling. Needs direct repo inspection to confirm.

---

## Comparative Observations

### Context Pipeline Maturity

```
CBP ████████████████████ Full (extract → resolve → build → inject + disambiguation)
HRI ██████████████████   Strong (extract → normalize → bracket inject + 13 rules)  
SA  ██████████           Basic on main / Full in PR #1308
SH  ██████████           Basic on main / Full in PR #1308
LDOS ████████            Filters to API only; no LLM context awareness
HC  ██                   Unverified (PoC)
```

### Key Architectural Differences

| Aspect | CBP | HRI | Security (PR) | LDOS |
|---|---|---|---|---|
| **Injection target** | SystemMessage | HumanMessage prefix | SYSTEM_PROMPT suffix | API filters (not LLM) |
| **ID resolution** | MCP tool, cached | None (labels) | Trino SQL query | N/A |
| **Disambiguation** | Formal AND gate | Enumerated ask-rules | None | N/A |
| **Context vs. history** | Implicit (UI preferred) | Rule 10 (explicit) | Rule 6 in PR (explicit) | No rule |
| **Portfolio-wide handling** | Not addressed | Rule 7 (explicit triggers) | Rule 5 in PR (explicit triggers) | N/A |

### Recommendations

1. **Security Advisory / Hardening**: Merge PR #1308 — it addresses the root cause of CXP-29702 with both programmatic resolution (Fix A) and prompt rules (Fix B)
2. **LDOS**: Consider injecting a bracket context block (similar to HRI) into the conversation history resolution prompt when UI filters are present — this would let the LLM know what asset the user is currently viewing
3. **CBP**: Consider adding enumerated context priority rules (like HRI's 13 rules) to handle portfolio-wide questions and explicit context vs. history precedence — the disambiguation rule alone doesn't cover these cases
4. **Health Check**: Verify context handling when the PoC matures toward production
