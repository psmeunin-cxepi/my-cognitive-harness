> **Agent:** Semantic Router
>
> **Repo:** [`CXEPI/cvi-ai-a2a`](https://github.com/CXEPI/cvi-ai-a2a) (routing + error handling) · [`CXEPI/cvi_ai_shared`](https://github.com/CXEPI/cvi_ai_shared) (error builder)
>
> **Jira:** [CXP-32681](https://cisco-cxe.atlassian.net/browse/CXP-32681)

# Out-of-Scope Questions Return Generic Processing Error Instead of Helpful Response

## Summary

When the agent selection LLM correctly identifies a question as out-of-scope (`is_valid: false`, no agent skill matched), the Semantic Router returns a generic "An error occurred while processing your request" instead of a helpful message explaining what the system can help with. The routing logic in `route_after_agent_choice()` treats "no agent matched" the same as "something broke" — both land in `error_response_node`, which unconditionally returns a processing error with a trace ID.

The system already has a capability discovery pattern (`_capability_discovery_fallback`) that lists what the user *can* ask about, but there is no code path that invokes it when agent selection legitimately rejects a query.

Secondary finding: transient HTTP 401 errors from `cxaihub.cisco.com/mistral-medium` on first attempt for both LLM calls, succeeding on retry. Infrastructure issue, not application.

## Trace

- **Trace ID:** `019e1799-3f86-7a83-9ee7-9434b86cbbc5`
- **Workspace:** cx-iq-prod
- **Agent:** Semantic Router (no downstream agent reached)
- **Date:** 2026-05-11
- **User:** Baha Araji (baraji@cisco.com)
- **Platform Account:** `8a8be9f2-ccb7-4e38-a199-dc9b16d9b80a`

## Conversation Context

This was the 2nd turn in a conversation. The 1st turn was an Assets (General) greeting/capability discovery. The user then asked:

1. **User:** _(greeting / capability discovery)_
   **Agent:** Assets (General) responded with capabilities.

2. **User:** "how can i add new contracts to my account?"
   **Agent:** ❌ "An error occurred while processing your request."

The question is genuinely out of scope — contract management is not supported by any CX IQ agent. The system correctly identified this but failed to communicate it helpfully.

App context: `asset-explorer`, `equipmentType=CHASSIS` filter active.

## Execution Flow

| Step | Node | Timestamp | Result |
|------|------|-----------|--------|
| 1 | `check_if_customer` | 15:12:59.782 | ✅ Pass |
| 2 | `check_entitlement` | 15:12:59.783 | ✅ Pass |
| 3 | `fetch_recent_context_db` | 15:12:59.783 | ✅ Chat history loaded |
| 4 | `fetch_agent_candidates_db` | 15:12:59.784 | ✅ Agent candidates loaded |
| 5 | `create_conversation_db` | 15:12:59.785 | ✅ |
| 6 | `route_to_agent` | 15:12:59.786 | Parallel sub-tasks launched ↓ |
| 6a | ↳ `agent_selection` | 15:13:00.814 → 15:13:02.443 | ✅ **Correct:** `is_valid: false`, `agent_skill: null` — no agent can handle this topic |
| 6b | ↳ `field_notice_nemo_guardrail_input` | 15:13:00.981 → 15:13:03.359 | ✅ `is_blocked: false` (not relevant to this issue) |
| 7 | `route_after_agent_choice` | 15:13:03.360 | **`is_valid_input: false`, `agent_choice: null`** → routes to `"error"` |
| 8 | `error_response` | 15:13:03.361 | ❌ Returns generic error instead of capability hints |

**Total latency:** 3.6 seconds (15:12:59.782 → 15:13:03.381)

## Root Cause

**Classification: Missing code path** — the Semantic Router conflates "no agent matched" with "processing failure", returning a generic error for both.

### The Routing Gap

When `agent_selection` returns `is_valid: false` and `agent_skill: null`, it means no agent can handle the question. This is a **correct, expected outcome** — not an error. But the routing logic in `route_after_agent_choice()` ([`routing.py`](https://github.com/CXEPI/cvi-ai-a2a) line 6) treats it as one:

```python
def route_after_agent_choice(state):
    if not state.get("is_valid_input", True):
        if state.get("guardrails_blocked"):
            return "guardrails_blocked"    # AI Defense block → helpful message
        return "error"                     # everything else → generic error  ← THE GAP
    ...
```

The `"error"` branch conflates two fundamentally different situations:
1. **Legitimate rejection** — the LLM correctly determined no agent matches (`is_valid: false`, `agent_choice: null`)
2. **Processing failure** — something actually broke during routing (exception, timeout, malformed response)

Both land in `error_response_node`, which unconditionally calls `build_processing_error_response()` → `"An error occurred while processing your request. Trace ID: ..."`.

### Why the Error Message Is Wrong

`error_response_node` (nodes.py line 1174) has a single code path — it always calls `build_processing_error_response()` from `cvi_ai_shared/core/errors.py`:

```python
agent_response = build_processing_error_response(
    context_id=context_id,
    question=payload.question if payload else "",
    trace_id=trace_id,
)
```

Which returns:
```python
answer="An error occurred while processing your request. Trace ID: {trace_id}"
```

There is no check for whether the state represents a legitimate rejection (no agent matched) vs. an actual failure (exception thrown). The node was designed for processing failures (see its docstring: "Agent execution fails", "Output validation fails") but is also receiving legitimate out-of-scope rejections that need a completely different response.

### Architecture — Component Ownership

| Component | Repo | File | Role |
|-----------|------|------|------|
| `route_after_agent_choice()` | `CXEPI/cvi-ai-a2a` | `graph/routing.py` (line 6) | Routes `is_valid_input=False` to `"error"` — does not distinguish rejection from failure |
| `error_response_node()` | `CXEPI/cvi-ai-a2a` | `graph/nodes.py` (line 1174) | Always returns generic processing error; no awareness of out-of-scope case |
| `build_processing_error_response()` | `CXEPI/cvi_ai_shared` | `core/errors.py` (line 8) | Hardcoded "An error occurred..." message — the message the user sees |
| `_capability_discovery_fallback()` | `CXEPI/cvi-ai-a2a` | `graph/nodes.py` | Exists and works — generates helpful capability hints from `agent_candidates` |

### The Existing Pattern That Should Be Reused

The codebase already has a function that generates helpful "here's what I can do" text from the available agent candidates:

```python
hints = _capability_discovery_fallback(agent_candidates)
```

This is currently used in `guardrails_blocked_node` and `default_agent_node`, but **not** in the path that handles out-of-scope rejections. The fix is to ensure this path also returns capability hints instead of a generic error.

## Evidence

### Agent selection output (correct — out of scope)
```json
{
  "is_valid": false,
  "agent_skill": null
}
```

### Guardrails output (correct — not blocked)
```json
{
  "is_blocked": false
}
```

### State at route_after_agent_choice
```json
{
  "is_valid_input": false,
  "guardrails_blocked": false,
  "agent_choice": null,
  "validation_reason": ""
}
```

### Routing decision
```json
{
  "output": "error"
}
```

### Final output to user
```
An error occurred while processing your request. Trace ID: 019e1799-4d89-7971-9e03-6d1d0d80936d
```

### Transient 401 errors (secondary finding)
Both `agent_selection` and `field_notice_nemo_guardrail_input` LLM calls failed on first attempt with HTTP 401 from `cxaihub.cisco.com/mistral-medium/v1/chat/completions`, then succeeded on retry. This added ~1 second of latency. Retry logic is working correctly — this is an infrastructure/token-refresh issue, not an application bug.

## Recommendations

### Fix 1 — Add "out-of-scope rejection" path to routing (cvi-ai-a2a)

**Priority:** P1 — directly fixes the user-facing UX gap.

**Repo:** `CXEPI/cvi-ai-a2a` · `graph/routing.py` + `graph/nodes.py`

**Option A — Reuse `guardrails_blocked_node` for all rejections:**

In `route_after_agent_choice()`, when `is_valid_input=False` and `guardrails_blocked=False` and there is no `error` in state (i.e., no exception occurred), route to `"guardrails_blocked"` instead of `"error"`. The `guardrails_blocked_node` already generates a helpful rejection with capability hints.

This is the minimal change but overloads the "guardrails_blocked" semantic — traces would show guardrail-blocked for non-guardrail rejections, reducing observability.

**Option B (preferred) — Add a new `out_of_scope` node:**

1. Add a new routing outcome `"out_of_scope"` in `route_after_agent_choice()`:
   ```python
   if not state.get("is_valid_input", True):
       if state.get("guardrails_blocked"):
           return "guardrails_blocked"
       if not state.get("error"):
           return "out_of_scope"      # ← NEW: legitimate rejection
       return "error"                  # actual processing failure
   ```

2. Create `out_of_scope_node` in `nodes.py` — similar to `guardrails_blocked_node` but with different rejection text and trace metadata:
   ```python
   async def out_of_scope_node(state: RouterState) -> RouterState:
       rejection_text = (
           "I'm not able to help with that topic. "
           "Try asking me something else, or browse prompts to see what I can help with."
       )
       agent_candidates = state.get("agent_candidates")
       if agent_candidates:
           hints = _capability_discovery_fallback(agent_candidates)
           rejection_text = f"{rejection_text}\n\n{hints}"
       # ... build AgentResponse, save, publish (same pattern as guardrails_blocked_node)
   ```

3. Register the new node and edge in `graph.py`:
   ```python
   workflow.add_node("out_of_scope", out_of_scope_node)
   # In route_after_agent_choice mapping:
   {"default": "default_agent", "execute": "execute_agent",
    "guardrails_blocked": "guardrails_blocked", "out_of_scope": "out_of_scope",
    "error": "error_response"}
   ```

**Benefits of Option B:**
- Clean separation in traces: `guardrails_blocked` = AI Defense policy violation, `out_of_scope` = legitimate topic mismatch, `error` = processing failure
- Different response text appropriate to each case
- Easier to add topic-specific rejection messages later (e.g., "Contract management is available in Cisco.com > My Account")

### Fix 2 — Investigate transient 401s from cxaihub (infrastructure)

**Priority:** P3 — retry logic handles it, but adds ~1s latency and generates noise in traces.

The `cxaihub.cisco.com/mistral-medium/v1/chat/completions` endpoint returned HTTP 401 on first attempt for both parallel LLM calls in this trace. This suggests a token refresh race condition or intermittent auth issue. Worth raising with the cxaihub team if this pattern appears frequently in traces.
