> **Agent:** Semantic Router (impacts Assets General)
>
> **Repo:** [`CXEPI/cvi_ai_shared`](https://github.com/CXEPI/cvi_ai_shared) (prompt + gating logic) · [`CXEPI/cvi_guardrails`](https://github.com/CXEPI/cvi_guardrails) (NeMo execution service)
>
> **Jira:** [CXP-32676](https://cisco-cxe.atlassian.net/browse/CXP-32676)

# Field Notice Guardrail False Positive Blocks Asset Inventory Query

## Summary

A follow-up asset inventory question — "can you share the list of SN related to the 13 Chassis Covered with Extended Support" — was correctly classified by the agent selection LLM as an Assets (General) follow-up (`ask_cvi_ldos_ai_external`, `is_valid: true`), but was falsely blocked by the `field_notice_nemo_guardrail_input` guardrail. The guardrail LLM (Mistral Medium 2508) incorrectly determined the question was "about Field Notices" and blocked it as not fitting the allowed Field Notice categories. The user received a generic error: "An error occurred while processing your request."

## Trace

- **Trace ID:** `019e1762-42e1-7732-acb0-2e3ae16a09b2`
- **Workspace:** cx-iq-prod
- **Agent:** Semantic Router → Assets (General) (never reached)
- **Date:** 2026-05-11
- **User:** Stefano Tadiello (stadiell@cisco.com)
- **Platform Account:** `8a8be9f2-ccb7-4e38-a199-dc9b16d9b80a`

## Conversation Context

This was the 3rd turn in a conversation, all routed to Assets (General):

1. **User:** "Summarize assets past Last Date of Support (LDOS)."
   **Agent:** Returned summary — 399 total chassis, 0 covered, **13 covered with extended support**, 386 not covered.

2. **User:** "share the list of product ID Chassis Covered with Extended Support"
   **Agent:** Returned 8 product IDs (1783-SR, ASR1002-F, CSP-2100-X1, N6K-C6001-64P, N9K-C92160YC-X, N9K-C9372TX, N9K-C9396PX, UCSC-C220-M4S).

3. **User:** "can you share the list of SN related to the 13 Chassis Covered with Extended Support"
   **Agent:** ❌ "An error occurred while processing your request."

## Execution Flow

| Step | Node | Timestamp | Result |
|------|------|-----------|--------|
| 1 | `check_if_customer` | 14:12:56.162 | ✅ Pass — `is_customer: true` |
| 2 | `check_entitlement` | 14:12:56.163 | ✅ Pass |
| 3 | `fetch_recent_context_db` | 14:12:56.163 | ✅ 2-turn chat history with Assets (General) loaded |
| 4 | `fetch_agent_candidates_db` | 14:12:56.167 | ✅ 8 candidate agents loaded; `weighted_agent_names: ["Assets (General)"]` |
| 5 | `create_conversation_db` | 14:12:56.171 | ✅ |
| 6 | `route_to_agent` | 14:12:56.180 | Three parallel sub-tasks launched ↓ |
| 6a | ↳ `agent_selection` (ChatMistralAI) | 14:12:56.194 → 14:12:57.736 | ✅ **Correct:** `is_valid: true`, `agent_skill: "ask_cvi_ldos_ai_external"` |
| 6b | ↳ `semantic_router_nemo_guardrail_input` | 14:12:56.210 → 14:12:58.850 | ✅ All checks pass — toxic: false, jailbreak: false, restrict_to_topic: false |
| 6c | ↳ `field_notice_nemo_guardrail_input` | 14:12:56.209 → 14:12:57.945 | ❌ **False positive:** `restrict to topic: is_blocked: true` |
| 7 | `route_after_agent_choice` | 14:12:58.852 | ❌ `agent_choice: null`, `validation_reason: "It appears you're exploring a currently unsupported task..."`, output: `"error"` |
| 8 | `error_response` | 14:12:58.853 | Returns generic error to user with inner trace ID `019e1762-4d65-7510-b127-e8873adad0b7` |

**Total latency:** 2.7 seconds (14:12:56.161 → 14:12:58.863)

## Root Cause

**Classification: Model behavior** (guardrail LLM false positive) + **Prompt gap** (insufficient negative examples in guardrail prompt)

### Trigger — Guardrail LLM misclassification

The `field_notice_nemo_guardrail_input` guardrail uses Mistral Medium 2508 with a topic-restriction prompt. The prompt explicitly instructs:

> *"Apply this policy ONLY to Field Notice requests. If the user message is not about Field Notices, allow it."*

Despite this instruction, the LLM classified the question "can you share the list of SN related to the 13 Chassis Covered with Extended Support" as a Field Notice request and blocked it with reason:

> *"The message is about Field Notices but does not fall into the allowed categories (count-based queries or detailed information requests about a specific Field Notice by ID)."*

The question contains zero Field Notice references. "SN" = serial number, "Chassis Covered with Extended Support" refers to coverage status — both are pure asset inventory concepts. The LLM failed to follow its own first instruction.

### Gap — FN guardrail prompt causes false positives on non-FN queries

The FN guardrail is a temporary topic-scoping gate that runs alongside agent selection. When the Assets route is active, it intentionally acts as a hard gate (line ~631) to restrict which FN-related queries can pass through — this is by design. The problem is that the guardrail's classifier cannot reliably distinguish FN queries from non-FN queries, causing it to block legitimate asset inventory questions.

The root cause is a prompt gap: `FIELD_NOTICE_RESTRICT_TO_TOPIC_CONTEXT` tells the LLM to "allow" non-FN messages but provides no definition of what a Field Notice is, no negative examples, and no disambiguation heuristics. The LLM is left to guess — and guesses wrong when it sees domain terms like "SN", "Chassis", or "Covered with Extended Support" that are adjacent to FN concepts but not FN-related.

### Architecture — Component Ownership

| Component | Repo | File | Role |
|-----------|------|------|------|
| `FIELD_NOTICE_RESTRICT_TO_TOPIC_CONTEXT` | `CXEPI/cvi_ai_shared` | `cvi_ai_shared/core/agents.py` (line 62) | Defines the FN guardrail prompt text |
| `choose_agent_and_screen_input()` | `CXEPI/cvi_ai_shared` | `cvi_ai_shared/core/agents.py` (line 460) | Runs 3 parallel tasks; FN guardrail is a hard gate at line ~631 |
| `_screen_with_guardrails("input_field_notice", ...)` | `CXEPI/cvi_ai_shared` | `cvi_ai_shared/core/agents.py` (line 1564) | Sends `restrict_to_topic_context` + `x-cvi-guardrail-trace-prefix: field_notice` to guardrails service |
| `_resolve_nemo_input_trace_name()` | `CXEPI/cvi_guardrails` | `cvi-guardrails/server.py` (line 577) | Assembles span name `field_notice_nemo_guardrail_input` from prefix header |
| NeMo `self_check_input` execution | `CXEPI/cvi_guardrails` | `cvi-guardrails/server.py` | Runs NeMo guardrails LLM call via Mistral; owns the prompt template that puts all instructions in the human message |

The `cvi-ai-a2a` repo (Semantic Router) calls `choose_agent_and_screen_input()` from the shared library but does not own the FN guardrail prompt, gating logic, or execution. The `cvi_guardrails` service is a policy executor — it runs whatever `restrict_to_topic_context` it receives via HTTP POST.

### Prompt Structure Deficiency

The NeMo guardrails framework (`cvi_guardrails`) uses a `self_check_input` rail that assembles a two-message prompt:

- **System message** (1 sentence): `"You are a guardrails policy evaluator. Return only the requested response format."`
- **Human message** (everything else): classification rules, Application Context, user message, JSON format instructions

This is architecturally inverted — classification instructions belong in the system prompt (highest-priority instruction channel). Stuffing them into the human message alongside the user input causes the model to conflate what it should evaluate with how it should evaluate. The `cvi_guardrails` service uses NeMo's default `self_check_input` prompt template, which can be overridden via `prompts.yml`.

The `FIELD_NOTICE_RESTRICT_TO_TOPIC_CONTEXT` itself lacks:
- A definition of what a Field Notice **is** (Cisco product notification about HW/SW defects)
- Negative examples showing what is **not** a Field Notice (serial number queries, coverage status, LDOS, asset inventory)
- Classification heuristics for ambiguous cases

## Evidence

### Agent selection output (correct)
```json
{
  "agent_skill": "ask_cvi_ldos_ai_external",
  "is_valid": true
}
```

### Semantic router guardrail output (correct — not blocked)
```json
{
  "result": false,
  "reason": "",
  "details": {
    "toxic language": { "is_blocked": false },
    "jailbreak attempt": { "is_blocked": false },
    "restrict to topic": { "is_blocked": false }
  }
}
```

### Field notice guardrail output (incorrect — false positive)
```json
{
  "result": true,
  "reason": "The message is about Field Notices but does not fall into the allowed categories (count-based queries or detailed information requests about a specific Field Notice by ID).",
  "details": {
    "restrict to topic": { "is_blocked": true }
  }
}
```

### Field notice guardrail prompt (relevant excerpt)
```
Apply this policy ONLY to Field Notice requests. If the user message is not about
Field Notices, allow it. For Field Notice requests, allow only these two categories:
(1) Count-based queries [...] (2) Detailed information requests [...]
Block every other Field Notice request outside these two categories.
```

The prompt's first sentence should have caused the LLM to allow the message. The LLM violated its own instruction by classifying a serial-number/coverage question as a Field Notice request.

### route_after_agent_choice input
```json
{
  "agent_choice": null,
  "validation_reason": "It appears you're exploring a currently unsupported task and I'm not able to address that specific question yet, ask me something else or browse prompts to see more options"
}
```

### Final output to user
```
An error occurred while processing your request. Trace ID: 019e1762-4d65-7510-b127-e8873adad0b7
```

## Recommendations

### Fix 1 — Improve `FIELD_NOTICE_RESTRICT_TO_TOPIC_CONTEXT` (cvi_ai_shared)

**Priority:** P1 — highest impact, lowest risk, scoped to FN screening only.

**Repo:** `CXEPI/cvi_ai_shared` · `cvi_ai_shared/core/agents.py` line 62

**Current prompt:**
```
Apply this policy ONLY to Field Notice requests. If the user message is not about
Field Notices, allow it. For Field Notice requests, allow only these two categories:
(1) Count-based queries: questions asking how many devices have field notices, ...
(2) Detailed information requests: asking for details about a specific Field Notice
by its ID (e.g. FN74267) or asking what a Field Notice is.
Block every other Field Notice request outside these two categories.
```

**Proposed prompt:**
```
You are a Field Notice topic guardrail. Your job is to classify whether a user
message is a Field Notice request and, if so, whether it is allowed.

A Field Notice (FN) is a Cisco product notification about significant hardware
or software defects (e.g., FN74267, FN-12345). Field Notice requests explicitly
mention "Field Notice", "FN", or a Field Notice ID.

Step 1 — Is this about Field Notices?
If the message does NOT mention Field Notices, FN IDs, or ask about product
defect notifications → ALLOW. The following are NOT Field Notice requests:
- Serial number (SN) queries, asset inventory, device lists
- Coverage status, extended support, contract status
- Last Date of Support (LDOS), End of Life (EoL), lifecycle
- Product IDs, chassis counts, hardware models
- Security advisories, bugs, vulnerabilities

Step 2 — If it IS a Field Notice request, allow only:
(1) Count-based queries: how many devices have field notices, top N devices by
    FN count, statistical aggregation of FN counts across assets.
    Block count queries about a specific FN ID (e.g., "How many assets are at
    risk for FN74267?").
(2) Detail requests: asking for details about a specific FN by ID, or asking
    what a Field Notice is. The Troubleshooting agent handles these.

Block every other Field Notice request outside these two categories.

When in doubt, ALLOW. False positives (blocking legitimate queries) are worse
than false negatives (letting a borderline FN query through).
```

**Changes:**
- Adds a definition of what a Field Notice is (Cisco product defect notification with FN ID)
- Adds explicit negative examples (SN queries, coverage, LDOS, product IDs, security advisories)
- Structures as a 2-step decision tree (is it FN? → is it allowed?)
- Adds default-allow heuristic for ambiguous cases

### Fix 2 — Move guardrail instructions to system prompt (cvi_guardrails)

**Priority:** P2 — correct architectural fix, wider blast radius (affects all guardrail checks).

**Repo:** `CXEPI/cvi_guardrails` · NeMo `self_check_input` prompt template

**Problem:** NeMo's default `self_check_input` rail puts a 1-sentence system prompt (`"You are a guardrails policy evaluator. Return only the requested response format."`) and stuffs all classification instructions into the human message alongside the user input. This causes the model to conflate policy instructions with content to evaluate.

**Proposed fix:** Override `prompts.yml` in the `cvi_guardrails` NeMo config to move the classification policy, negative examples, and output format instructions into the system message. The human message should contain only the user input being evaluated and the Application Context. This aligns with how instruction-tuned models weight system vs. user messages and would improve classification accuracy across all screening paths (FN, toxic, jailbreak, restrict_to_topic).
