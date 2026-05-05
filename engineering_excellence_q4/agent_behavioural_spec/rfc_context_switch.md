# RFC: Context Switch Behavior Specification for Cisco IQ Agents

| Field | Value |
|---|---|
| **RFC ID** | RFC-001 |
| **Title** | Context Switch Behavior Specification |
| **Status** | Draft |
| **Author** | Philip Smeuninx |
| **Created** | 2026-04-23 |
| **Applies to** | All Cisco IQ domain agents receiving UI context |

## Abstract

This RFC defines the required behavior for Cisco IQ AI agents when the UI context changes — specifically, how agents MUST resolve ambiguous references, scope queries, and handle transitions between pages or entities.

The key words "MUST", "MUST NOT", "SHOULD", "SHOULD NOT", and "MAY" in this document are to be interpreted as described in [RFC 2119](https://www.rfc-editor.org/rfc/rfc2119).

## Motivation

When a user navigates between pages in Cisco IQ (e.g., from advisory A to advisory B), the UI sends updated context to the agent. The agent must correctly scope its responses to the current page — not to entities referenced in conversation history from a prior page.

Failure to handle this correctly causes the agent to answer about the wrong entity (see CXP-29702: agent answered about advisory #2943 when user had navigated to advisory #3065 and asked "explain this vulnerability").

## Terminology

| Term | Definition |
|---|---|
| **UI context** | The set of identifiers and application state sent by the frontend reflecting the user's current page (e.g., `checkId`, `ruleId`, `assetId`, `serialNumber`). Currently delivered via `context.filters`; migrating to `context.application`. |
| **Context entity** | The primary domain object identified by the UI context (e.g., a specific advisory, rule, or asset). |
| **Deictic reference** | A pronoun or demonstrative that refers to an entity without naming it: "this vulnerability", "this rule", "this device", "it", "this one". |
| **Named reference** | An explicit mention of an entity by name, ID, or CVE: "Blast-RADIUS", "CVE-2024-3596", "cisco-sa-iosxe-privesc". |
| **Portfolio-wide question** | A question that implies the user's full inventory or multiple entities, not a single one. |
| **Conversation history** | Prior messages in the current conversation thread. |

---

## 1. Normative Rules

### R1 — Context Reception

R1.1: The agent MUST accept UI context from the upstream A2A payload or API request.

R1.2: The agent MUST extract supported context keys and discard unsupported keys silently (no error to user).

R1.3: The agent SHOULD resolve opaque identifiers (e.g., `checkId`, `ruleId`, `assetId`) to human-readable names before the LLM processes the request. Raw identifiers SHOULD NOT be the only representation the LLM sees.

### R2 — Deictic Resolution

R2.1: When UI context identifies a specific entity and the user uses a deictic reference ("this vulnerability", "this rule", "this device", "it", "this one"), the agent MUST resolve the reference to the entity identified by the **current UI context**.

R2.2: The agent MUST NOT resolve deictic references from conversation history when a current UI context entity is present.

### R3 — Named Entity Override

R3.1: When the user explicitly names a different entity (by name, CVE, advisory ID, serial number, or other identifier), the agent MUST scope to the **user-named entity**, regardless of what the UI context identifies.

R3.2: A named reference signals direct user intent and MUST take precedence over both UI context and conversation history.

### R4 — Portfolio-Wide Questions

R4.1: When the user asks a question that implies multiple entities or their full portfolio, the agent MUST drop the UI context scope and query across the full scope.

R4.2: The following phrases (non-exhaustive) indicate portfolio-wide intent: "all my", "show all", "list all", "how many", "total", "across my network", "top N", "most critical", "most impactful", "which advisories", "do I have any", "are there any", "overview", "summary".

R4.3: The agent MUST NOT restrict portfolio-wide results to the currently viewed entity.

### R5 — Context Precedence Over History

R5.1: The current UI context MUST take precedence over conversation history when there is a conflict.

R5.2: If the conversation history references entity A but the current UI context identifies entity B, the agent MUST scope to entity B for deictic references — without asking the user.

R5.3: The agent SHOULD NOT require the user to explicitly confirm the context switch. The UI navigation is the user's implicit confirmation.

### R6 — Aligned Questions

R6.1: When the user's question is compatible with the UI context (no contradictions, not portfolio-wide), the agent SHOULD scope to the context entity and answer directly.

### R7 — Contradicting Values

R7.1: When the user's question mentions values that contradict the UI context (e.g., context says "Assessment Rating: High" but user asks about "Critical"), the agent SHOULD ask for clarification referencing both naturally — without exposing internal terms like "filter", "context", or "application state".

### R8 — Additional Dimensions

R8.1: When the user adds a new dimension not present in the UI context, the agent SHOULD combine the UI context with the user's additional constraint.

### R9 — No Context Available

R9.1: When no UI context is present and the user uses a deictic reference, the agent SHOULD resolve from conversation history.

R9.2: When no UI context is present and no conversation history provides a referent, the agent MUST ask the user to specify the entity.

### R10 — Internal Identifier Confidentiality

R10.1: The agent MUST NOT expose internal identifiers (`checkId`, `psirt_id`, `ruleId`, `source_id`, `asset_key`, `context_filter`) in user-facing responses.

R10.2: The agent MUST refer to entities by their human-readable name (e.g., advisory headline, rule name, hostname, serial number).

R10.3: The agent MUST NOT mention "UI context", "page context", "bracket context", "filters", "application state", or "runtime context" in responses. The agent should speak as if it naturally knows what the user is looking at.

---

## 2. Decision Table

The table below defines expected agent behavior for every combination of context state and user intent.

| # | UI Context | User Intent | Expected Behavior | Governing Rule |
|---|---|---|---|---|
| D1 | Entity A present | Deictic reference ("this vulnerability") | Scope to entity A | R2.1 |
| D2 | Entity A present | Names entity B explicitly | Scope to entity B, ignore context | R3.1 |
| D3 | Entity A present | Portfolio-wide ("how many critical advisories?") | Drop context, query full portfolio | R4.1 |
| D4 | Entity A present | Question aligns with A (no contradiction) | Scope to entity A, answer directly | R6.1 |
| D5 | Entity A present | Mentions contradicting values | Ask clarification naturally | R7.1 |
| D6 | Entity A present | Adds new dimension | Combine context + new constraint | R8.1 |
| D7 | Changed A → B | Deictic reference ("this one") | Scope to entity B (current) | R2.1, R5.1 |
| D8 | Changed A → B | "What about the previous one?" | Scope to entity A (from history) | R3.1 (named via "previous") |
| D9 | No context | Deictic reference, history has entity A | Scope to entity A (from history) | R9.1 |
| D10 | No context | Deictic reference, no history | Ask user to specify | R9.2 |
| D11 | Entity A present | Asks to compare entity A and entity B | Include both entities | R3.1 (both named) |
| D12 | Entity A present | "What can you help me with?" | Respond with capabilities, scoped to A if relevant | R6.1 |

---

## 3. Test Scenarios

Concrete scenarios derived from the decision table, written in BDD format. These can be translated directly into eval test cases.

### S1 — Deictic resolves to current context (D1)

```
Scenario: Deictic reference with active context
  Given the UI context identifies advisory "IOS XE Privilege Escalation" (checkId=3065)
  When the user asks "explain this vulnerability"
  Then the agent MUST answer about "IOS XE Privilege Escalation"
```

### S2 — Named entity overrides context (D2)

```
Scenario: User names a different entity
  Given the UI context identifies advisory "IOS XE Privilege Escalation" (checkId=3065)
  When the user asks "tell me about Blast-RADIUS"
  Then the agent MUST answer about "Blast-RADIUS"
  And the agent MUST NOT restrict the query to checkId=3065
```

### S3 — Portfolio-wide drops context (D3)

```
Scenario: Portfolio-wide question with active context
  Given the UI context identifies advisory "IOS XE Privilege Escalation" (checkId=3065)
  When the user asks "how many critical advisories affect my network?"
  Then the agent MUST query across the full portfolio
  And the response MUST NOT be limited to advisory 3065
```

### S4 — Context switch resolves to new page (D7)

```
Scenario: User navigates to a different entity and uses deictic
  Given the user was previously discussing advisory "Blast-RADIUS" (checkId=2943)
  And the UI context now identifies advisory "IOS XE Privilege Escalation" (checkId=3065)
  When the user asks "what does this vulnerability mean?"
  Then the agent MUST answer about "IOS XE Privilege Escalation"
  And the agent MUST NOT answer about "Blast-RADIUS"
```

### S5 — No context, resolve from history (D9)

```
Scenario: No UI context, deictic resolves from history
  Given no UI context is present
  And the conversation history last discussed advisory "Blast-RADIUS"
  When the user asks "how many of my devices are affected by this?"
  Then the agent MUST answer about "Blast-RADIUS"
```

### S6 — No context, no history, ask user (D10)

```
Scenario: No context and no history — agent asks for clarification
  Given no UI context is present
  And no prior conversation history exists
  When the user asks "explain this vulnerability"
  Then the agent MUST ask the user to specify which vulnerability
```

### S7 — Internal identifiers never exposed (R10)

```
Scenario: Agent does not expose internal identifiers
  Given the UI context identifies advisory "IOS XE Privilege Escalation" (checkId=3065)
  When the user asks "what is this advisory about?"
  Then the response MUST refer to the advisory by its headline name
  And the response MUST NOT contain "checkId", "psirt_id", "3065", or "context_filter"
```

### S8 — Contradicting values (D5)

```
Scenario: User mentions values that contradict context
  Given the UI context has Assessment Rating: High, Medium
  When the user asks "show me my Critical rated assets"
  Then the agent SHOULD ask whether the user wants Critical assets
    or the High/Medium assets they are currently viewing
  And the clarification MUST NOT use the words "filter" or "context"
```

---

## 4. Implementation Guidance

This section is non-normative. It describes patterns observed in current agent implementations that satisfy the rules above.

### 4.1 Context Injection Strategies

| Strategy | Used by | Mechanism |
|---|---|---|
| SystemMessage (markdown block) | CBP | Rendered context injected as first `SystemMessage` before user messages |
| HumanMessage prefix (bracket block) | HRI | `[The user is currently viewing...]` prepended to user prompt |
| SYSTEM_PROMPT suffix | Security Advisory/Hardening | Raw context summary appended to the static system prompt |

All three strategies can satisfy the normative rules. The critical factor is not *where* the context is injected but that the LLM prompt includes **explicit priority instructions** (R2, R5) telling the model how to handle conflicts.

### 4.2 ID Resolution

Agents SHOULD resolve opaque IDs before the LLM sees them (R1.3). Observed approaches:

- **MCP tool call** (CBP): Calls `resolve_filter_context` with `resolve_type` + `identifier`, caches results
- **SQL lookup** (Security Advisory PR #1308): Queries `bulletins` table for `headline_name` where `psirt_id = <checkId>`
- **Display labels** (HRI): Maps camelCase context keys to display labels, skips ID resolution

### 4.3 Prompt Rule Encoding

The context priority rules from Section 1 can be encoded in the system prompt as:

- **Enumerated rules** (HRI, Security Advisory PR #1308): Numbered list in the prompt, ordered by specificity
- **Disambiguation gate** (CBP): Formal condition-based rule appended when conversation history exists
- **Implicit precedence** (LDOS): No explicit rules — relies on the LLM's default behavior (not recommended)

Enumerated rules have shown the best results across model families (GPT, Mistral) because they reduce the LLM's interpretation burden.

---

## 5. Conformance

An agent conforms to this specification if:

1. All MUST rules (R1.1, R1.2, R2.1, R2.2, R3.1, R3.2, R4.1, R4.3, R5.1, R5.2, R9.2, R10.1, R10.2, R10.3) are satisfied
2. All decision table entries marked as MUST produce the expected behavior
3. All test scenarios (S1–S8) pass when executed against the agent

SHOULD rules are recommended but not required for conformance. Non-conforming behavior for SHOULD rules SHOULD be documented with rationale.

---

## References

- [CXP-29702](https://cisco-cxe.atlassian.net/browse/CXP-29702) — Context switch failure in Security Advisory agent
- [context_switch_spec.md](context_switch_spec.md) — Cross-agent landscape analysis (current implementations)
- [RFC 2119](https://www.rfc-editor.org/rfc/rfc2119) — Key words for use in RFCs to indicate requirement levels
- [CXP-28726](https://cisco-cxe.atlassian.net/browse/CXP-28726) — Enhance Security Advisory Agent with UI Context Awareness
- PR #1308 (CXEPI/risk-app) — Fix A + Fix B implementation for CXP-29702
