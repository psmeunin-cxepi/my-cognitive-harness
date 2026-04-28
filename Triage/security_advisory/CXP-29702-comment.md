> **Agent:** Security Advisory | **Repo:** [`CXEPI/risk-app`](https://github.com/CXEPI/risk-app)

# CXP-29702 — Implementation Plan Comment

Copy everything below the line into the Jira comment box for [CXP-29702](https://cisco-cxe.atlassian.net/browse/CXP-29702).

---

## Implementation Plan: Context Switch Fix

_Source: Cross-agent context handling research (CBP, HRI, Security Advisory) + code review of `security_assessment_agent_impl.py`. Trace: `019db4bd-f9fd-7530-ba97-5d9ea0a775a7` (nprd)._

### Problem

The agent answers about the wrong advisory when the user navigates between advisories mid-conversation. User navigated to `psirt_id = 3065` ("Cisco IOS XE Software Privilege Escalation Vulnerabilities") but the agent explained `psirt_id = 2943` ("Blast-RADIUS") because it resolved "this vulnerability" from conversation history instead of the current page's `checkId` context.

Three layers of failure:
1. No system prompt instruction to prioritize page context over conversation history
2. No programmatic resolution of `checkId` before the LLM sees it — raw numeric ID with no label
3. RAG tool has no metadata filter path (out of scope for this fix)

### Phase 1: Fix A — Programmatic `checkId` Resolution

**File:** `security-advisory-ai-api/src/openapi_server/impl/security_assessment_agent_impl.py`

Add async helper `_resolve_check_id()` (~25 lines) inserted at line ~914, between `context_summary = _format_context_filter(...)` and `system_content += ...`:

1. Extract `checkId` from `ai_ask_question.context_filter.get("filters", {}).get("checkId", [])` — defensive access, first element, coerce to int
2. Build SQL: `SELECT headline_name, advisory_id FROM bulletins WHERE psirt_id = <id> LIMIT 1`
3. Resolve aliases via existing `_resolve_sql_aliases()` (uses cached FQN map from `text2sql_mcp`)
4. Execute via `trino_mcp_client.call_tool(trino_tool_name, {"sql": resolved_sql, "x_authz": x_authz})`
5. Parse result → extract `headline_name` and `advisory_id`
6. Inject before existing context block:

> The user is currently viewing advisory: "Cisco IOS XE Software Privilege Escalation Vulnerabilities" (psirt_id: 3065, advisory_id: cisco-sa-iosxe-priv-esc-xxxxx). When the user says "this vulnerability" or "this advisory", they mean this one.

**Error handling:** `try/except Exception` with `logger.warning` — resolution failure falls back to raw `checkId` (current behaviour, no regression).

**Cost:** ~100-300ms Trino query, only when `checkId` is present.

### Phase 2: Fix B — System Prompt Context Priority Rules (parallel with Phase 1)

**File:** `security-advisory-ai-api/src/openapi_server/prompts/security_assessment_v1_mistral.py`

Insert 7 enumerated rules in a new `<advisory_context_rules>` section after the existing `<context_filter_mapping>` block. Adapted from HRI's 13-rule pattern (most battle-tested for Mistral):

| # | Rule | Behavior |
|---|------|----------|
| 1 | Default scope | Use runtime context advisory as default scope for tool calls |
| 2 | Advisory detail page | "this vulnerability"/"this advisory" + no different advisory named → use context advisory |
| 3 | Question aligns | Compatible question + no contradictions → scope to context advisory |
| 4 | User names different advisory | User references specific advisory by name/CVE/ID → ignore context, answer about named advisory |
| 5 | Portfolio-wide/aggregate | Trigger phrases ("all my", "top 5", "how many", "overview") → drop advisory filter, query full portfolio |
| 6 | Context vs. history | **Runtime context advisory takes precedence over conversation history. No ambiguity question — use context directly.** |
| 7 | Never expose internals | Don't mention checkId, psirt_id, context filters. Use advisory headline name. |

**Full proposed prompt addition:**

```xml
<advisory_context_rules>
When the runtime context includes a resolved advisory name (from checkId), apply these rules in order before calling any tool.

1. Default scope: Use the advisory from runtime context as the default scope when calling tools — UNLESS a later rule overrides this.

2. Advisory detail page: If the runtime context identifies a specific advisory and the user asks about "this vulnerability", "this advisory", "this check", or uses similar pronouns without naming a different advisory, assume they mean the advisory from runtime context.

3. Question aligns with context: If the user's question is compatible with the runtime context advisory (no contradictions and not a portfolio-wide question), scope to that advisory and answer directly.

4. User names a different advisory: If the user asks about a SPECIFIC advisory by name, CVE ID, or advisory ID (e.g., "tell me about Blast-RADIUS", "what about CVE-2024-3596"), ignore the runtime context advisory entirely and answer about the one the user named. A specific advisory reference signals direct intent that overrides page context.

5. Portfolio-wide or aggregate questions — IGNORE advisory context entirely: When the user asks a question that implies multiple advisories or their full exposure, drop the advisory context filter and query across their full portfolio.
   Trigger phrases (non-exhaustive): "all my", "show all", "list all", "how many", "total", "across my network", "top 5", "top 10", "most impactful", "most critical", "which advisories", "do I have any", "are there any", "my Critical advisories", "overview", "summary".
   Examples when context is advisory "Cisco IOS XE Privilege Escalation":
   - "How many critical advisories affect my network?" → IGNORE context advisory, query across full portfolio.
   - "Show me my top 5 most impactful advisories" → IGNORE context advisory, query full portfolio.
   - "What does this vulnerability mean?" → USE context advisory.
   - "How many of my devices are affected by this?" → USE context advisory.

6. Context vs. history: The advisory identified in the current runtime context takes precedence over any advisory discussed in conversation history. When there is a conflict, use the runtime context advisory without asking.

7. Never expose internals: Do NOT mention "checkId", "psirt_id", "context filters", or "runtime context" in your response. Refer to advisories by their headline name.
</advisory_context_rules>
```

### Design Decisions

- **Fix A + Fix B together** — deterministic resolution (A) + LLM guidance (B) as defense-in-depth
- **HRI-style enumerated rules over CBP-style disambiguation gate** — CBP's 4-condition AND gate has a soft predicate (condition 4: "REQUIRES that entity") that Mistral can rationalize around. HRI's concrete trigger phrases are more reliable for Mistral.
- **No "ask user to confirm" on advisory context switch** — page navigation is an unambiguous intent signal. Asking adds a round-trip without value.
- **Descriptive labels** ("runtime context advisory") not algebraic notation (E_ui/E_hist) — safer for Mistral.

### Cross-Agent Reference

| Agent | Receives UI context? | Resolves IDs? | Prioritizes over history? | Explicit conflict rules? |
|-------|---------------------|---------------|--------------------------|------------------------|
| CBP (GPT-5.3) | Yes — SystemMessage | Yes — MCP resolution | Yes — ordering + disambiguation gate | Yes — 4-condition AND |
| HRI (Mistral) | Yes — bracket in prompt | Partial — label map | Yes — Rule 10 | Yes — 13 enumerated rules |
| Security Advisory (Mistral) | Partial — raw injection | No | No | No |

### Verification

1. **Reproduce bug** — list top 5 advisories → navigate to 4th (3065) → ask "what does this vulnerability talk about?" → confirm wrong answer
2. **Fix A unit test** — mock Trino for checkId=3065, verify resolved name in system prompt
3. **Fix A+B integration** — same replay, confirm answer about 3065 not 2943
4. **Edge cases** — missing checkId, Trino timeout, multiple values, non-numeric checkId
5. **Portfolio query** — with checkId=3065 active, ask "show me top 5 most impactful advisories" → confirm full portfolio query
6. **User-names-different** — with checkId=3065 active, ask "tell me about Blast-RADIUS" → confirm Blast-RADIUS answer
7. **LangSmith trace** — LLM run 1 tool call targets 3065 not 2943

### Files Changed

| File | Change |
|------|--------|
| `security_assessment_agent_impl.py` | New async helper `_resolve_check_id()` (~25 lines) + integration at line ~914-930 |
| `security_assessment_v1_mistral.py` | New `<advisory_context_rules>` section (7 rules) after `<context_filter_mapping>` |
