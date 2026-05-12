> **Agent:** Troubleshooting (`cx_ai_fn_q_a` skill)
>
> **Repo:** Troubleshooting agent hosted at `cx-ai-assistants.cisco.com` · Semantic Router in [`CXEPI/cvi-ai-a2a`](https://github.com/CXEPI/cvi-ai-a2a)
>
> **Jira:** [CXP-32784](https://cisco-cxe.atlassian.net/browse/CXP-32784)

# Troubleshooting Agent Ignores UI Context — Asks for Field Notice ID Already Present in Payload

## Summary

User was viewing Field Notice FN72464 (Cisco Nexus 9300 DIMM memory failures) on the assessments page and asked "Can you explain me more on the field notice shown?" The Semantic Router correctly selected the Troubleshooting agent with skill `cx_ai_fn_q_a` and forwarded the full UI context including `context.filters.fieldNoticeId: ["72464"]`. However, the Troubleshooting agent did not consume the context filter and instead asked the user a clarifying question: "Which Field Notice is being shown? Please share the Field Notice ID." The FN ID was already present in the A2A payload.

## Trace

- **Trace ID:** `019e1bea-09d6-7982-8667-b70c031f244f`
- **Workspace:** cx-iq-prod
- **Agent:** Semantic Router → Troubleshooting (`cx_ai_fn_q_a`)
- **Date:** 2026-05-12
- **User:** Philip Smeuninx (psmeunin@cisco.com)
- **Platform Account:** `8a8be9f2-ccb7-4e38-a199-dc9b16d9b80a`

## UI Context

User was on `/assessments/field-notices/72464` viewing:

- **FN72464** — Cisco Nexus 9300 Switches and APIC Servers Can Experience Memory Failures - Hardware Upgrade Available
- **Severity:** Critical
- **Last updated:** Oct 2, 2024
- **Bug:** CSCwb98743
- **Asset Results:** 5 affected devices (ute11-leaf4, LEAF-176-FFF-35, LEAF-201-HHH-34, LEAF-202-HHH-35, FDO2452001X) — all Cisco Nexus 9000 switches

The UI sent the following `context.filters` in the payload:

```json
{
  "context": {
    "app": "assessments",
    "context_id": "fd632d9b-f949-485a-b9a4-166f23a848ec",
    "filters": {
      "fieldNoticeId": ["72464"]
    },
    "language": "en-US",
    "source": "prompt-input-bar:send",
    "url": "/assessments/field-notices/72464(assistant:docked/threads/fd632d9b-f949-485a-b9a4-166f23a848ec)"
  },
  "question": "Can you explain me more on the field notice shown?"
}
```

## Conversation Context

This was the 2nd turn in the conversation:

1. **User:** (empty question — Ask AI button click from FN page)
   **Agent:** Assets (General) responded with default greeting listing capabilities including "Field notices — see how many of your devices are affected."

2. **User:** "Can you explain me more on the field notice shown?"
   **Agent:** Troubleshooting → ❌ Asked clarifying question instead of answering: "Which Field Notice is being shown? Please share the Field Notice ID (for example: FN74214) or paste the title/summary you see in the UI."

## Execution Flow

| Step | Node | Span ID | Result |
|------|------|---------|--------|
| 1 | `check_if_customer` | `019e1bea-09d7-7590-a798-a50fcd1d6c89` | ✅ Pass |
| 2 | `check_entitlement` | `019e1bea-09d8-71c3-aef0-a26610750f90` | ✅ Pass |
| 3 | `fetch_recent_context_db` | `019e1bea-09d9-7ac0-b3f4-8b762ff2af57` | ✅ Fetched prior turn (Assets General greeting) |
| 4 | `fetch_agent_candidates_db` | `019e1bea-09dc-77c0-aa44-2790c5bec55d` | ✅ 7 agents loaded |
| 5 | `create_conversation_db` | `019e1bea-09e0-77b3-b8a3-969526ad6000` | ✅ |
| 6 | `route_to_agent` | `019e1bea-09e4-76d1-b962-45a8531706d1` | ✅ |
| 7 | `agent_selection` (ChatMistralAI) | `019e1bea-09f8-7dc0-9305-ec293434d398` | ✅ `cx_ai_fn_q_a` selected — correct |
| 8 | `field_notice_nemo_guardrail_input` | `019e1bea-09fe-7e00-9566-05ff8db891f7` | ✅ Not blocked (FN detail request allowed) |
| 9 | `semantic_router_nemo_guardrail_input` | `019e1bea-09fe-7602-88fb-af90a23a9e84` | ✅ Not blocked |
| 10 | `route_after_agent_choice` | `019e1bea-13c4-7411-a4d5-977e8b2e93a2` | ✅ Proceeded to execution |
| 11 | `execute_agent` | `019e1bea-13c6-7f72-979c-2197fcf07fef` | ⚠️ Agent responded with clarifying question |
| 12 | `route_after_execution` | `019e1bea-25ee-7113-b20c-fac73db02720` | ✅ Completed |

**Key observation:** The Semantic Router did everything correctly — right agent, right skill, guardrails passed, context forwarded. The failure is entirely inside the downstream Troubleshooting agent.

## Context Forwarding — Verified

The `execute_agent` span (ID: `019e1bea-13c6-7f72-979c-2197fcf07fef`) confirms the payload was forwarded to the Troubleshooting agent:

```
inputs.payload.context.filters.fieldNoticeId = ["72464"]
```

The Semantic Router passed the full `context` object including `app`, `url`, `filters`, and `language` to the downstream agent. The Troubleshooting agent had all the information needed to resolve "the field notice shown" to FN72464.

## Root Cause

| Category | Classification |
|----------|---------------|
| **Primary** | **Context handling** — Troubleshooting agent does not consume `context.filters.fieldNoticeId` from the A2A payload |

The Troubleshooting agent's `cx_ai_fn_q_a` skill receives the full payload including `context.filters.fieldNoticeId: ["72464"]` but does not use it. When the user asks about "the field notice shown" (a deictic reference to on-screen content), the agent cannot resolve the reference because its system prompt or tool-calling logic does not extract the FN ID from the context filters.

This is a single-point failure:
- **Trigger:** User uses a deictic reference ("the field notice shown") instead of explicitly stating "FN72464"
- **Gap:** The `cx_ai_fn_q_a` skill does not read `context.filters` to resolve such references

## Evidence

1. **Context present in A2A input:** `execute_agent` inputs contain `payload.context.filters.fieldNoticeId: ["72464"]` — confirmed via LangSmith trace.

2. **Agent ignores it:** The response asks: "Which Field Notice is being shown? Please share the Field Notice ID (for example: FN74214) or paste the title/summary you see in the UI." — proving the agent did not extract the ID from the payload.

3. **Routing was correct:** Agent selection LLM (Mistral-medium-2508) returned `cx_ai_fn_q_a` with `is_valid: true`. Page Context Preference was `[Assets (General)]`, but the LLM correctly determined this is an FN detail question suited for Troubleshooting. Both guardrails passed.

## Recommendations

| Priority | Fix | Owner | Description |
|----------|-----|-------|-------------|
| **P1** | Inject `fieldNoticeId` from `context.filters` into the agent's prompt or tool input | Troubleshooting agent (`cx-ai-assistants`) | When `context.filters.fieldNoticeId` is present, the agent should resolve deictic references ("the field notice shown", "this field notice") to the provided ID and pass it directly to the FN lookup tool without asking the user. |
| **P2** | Augment the user question before A2A dispatch | Semantic Router (`CXEPI/cvi-ai-a2a`) | As a defense-in-depth measure, when `context.filters.fieldNoticeId` is set and the question contains a deictic reference, the router could rewrite the question to include the explicit ID (e.g., "Can you explain me more on field notice FN72464?") before dispatching to the downstream agent. This makes the context explicit regardless of whether the downstream agent reads filters. |
