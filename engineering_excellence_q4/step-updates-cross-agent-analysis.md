# Step Updates — Cross-Agent Analysis

> **Workstream:** EE-1 — Agent Graph & State Architecture
>
> **Date:** 2026-04-28
>
> **Status:** Research
>
> **Owner(s):** Philip Smeuninx

---

## 1. What This Is

When a user asks a question, each CX IQ agent sends real-time progress messages ("step updates") to indicate where it is in the processing flow. These appear in the UI as collapsible steps under **"View task breakdown"**.

Example (Config Best Practices):
```
▶ View task breakdown
  Thinking about your question...
  Gathering information...
  Preparing your answer...
```

This document analyses how each agent implements this feature — what messages are sent, when they fire, and how the delivery pipeline works — and compares the approaches.

---

## 2. How It Works Today

All agents share the same end-to-end delivery mechanism:

```
Agent code
  → builds MCP TaskStatusNotification (status="working", statusMessage=<text>)
  → HTTP POST to A2A /tasks bridge endpoint
  → bridge looks up EventQueue by context_id in process-local registry
  → wraps notification in A2A TaskStatusUpdateEvent (state=working)
  → enqueues onto EventQueue
  → SSE stream delivers to frontend
```

**Shared library:** `cvi_ai_shared/core/stream_bridge.py` provides:
- `build_a2a_working_task_update()` — wraps MCP notification into A2A `TaskStatusUpdateEvent`
- `post_working_update_to_a2a_handler()` — builds + POSTs the notification envelope
- `parse_mcp_task_status_notification()` — validates incoming `/tasks` payloads

**Payload structure** (all agents):
```json
{
  "context_id": "<thread-id>",
  "task_id": "<thread-id>",
  "notification": {
    "method": "notifications/tasks/status",
    "params": {
      "taskId": "<thread-id>",
      "status": "working",
      "statusMessage": "Thinking about your question...",
      "createdAt": "2026-04-28T12:00:00Z",
      "lastUpdatedAt": "2026-04-28T12:00:00Z",
      "ttl": 30000,
      "pollInterval": 1000
    }
  },
  "mcp_server": "",
  "mcp_tool": ""
}
```

The A2A event delivered to the frontend contains a `DataPart` with `type: "worklog"` — the UI uses this to distinguish progress from conversation messages.

---

## 3. Implementation Analysis

### 3.1 Config Best Practices

> **Repo:** `CXEPI/configbp-ai`

#### Architecture

LangGraph nodes.

#### Key Behaviors

**Messages (3 fixed):**

| # | Message | Progress | Trigger |
|---|---------|----------|---------|
| 1 | `"Thinking about your question..."` | 0.2 | LLM starts processing (no prior tool results) |
| 2 | `"Gathering information..."` | 0.4 | LLM decides to call tools (`response.tool_calls` non-empty) |
| 3 | `"Preparing your answer..."` | 0.8 | LLM re-enters with tool results (second pass) |

| Behavior | Implementation |
|----------|----------------|
| **Emission function** | Custom `emit_progress()` in `agent/services/progress_notifier.py` — **fire-and-forget** via `asyncio.create_task(_do_post(payload))`, does not block the graph node. Silent no-op if `context_id_var` is unset. |
| **Deduplication** | `AgentState.progress_started` flag (prevents duplicate "Thinking" and "Gathering" on re-entry), `AgentState.progress_finalizing` flag (prevents duplicate "Preparing"), `once=True` parameter (ContextVar-based per-request dedup, available but not primary mechanism). |

**Graph structure:**
```
START → flow_router → assistant ⇄ tools → END
                          ↑          |
                          └──────────┘  (tool-calling loop)
```

#### Key Files

| File | Purpose |
|------|---------|
| `agent/services/progress_notifier.py` | `emit_progress()` — fire-and-forget POST to `/tasks` |
| `agent/nodes/assistant.py` | 3 `emit_progress` calls in the LLM node |
| `agent/core/state.py` | `AgentState` with `progress_started`, `progress_finalizing` |
| `agent/core/context_id.py` | `context_id_var` ContextVar |
| `a2a_server/core/streaming.py` | `/tasks` bridge — `tasks_handler()`, EventQueue registry |
| `a2a_server/core/executor.py` | `register_queue()`/`unregister_queue()` lifecycle |

#### Known Gaps

- Fire-and-forget emission risks a race where the EventQueue is unregistered before the notification arrives (mitigated by short timeout)

---

### 3.2 LDOS (Asset General / Asset Criticality)

> **Repo:** `CXEPI/cvi-ldos-ai`

#### Architecture

API request handler (no LangGraph for progress).

#### Key Behaviors

**Messages (4 fixed):**

| # | Message | Progress | Trigger |
|---|---------|----------|---------|
| 1 | `"Understanding your question…"` | 0.1 | After logging input |
| 2 | `"Validating your request…"` | 0.2 | After context extraction |
| 3 | `"Running your query…"` | 0.6 | Before welcome/processing |
| 4 | `"Done — here's what I found."` | 1.0 | Final completion (multiple sites) |

| Behavior | Implementation |
|----------|----------------|
| **Emission function** | `emit_working_update()` in `common/streaming/live_updates.py` — wraps `post_working_update_to_a2a_handler()` from `cvi_ai_shared`. **Awaited** — blocks until POST completes. Extracts `context_id` from `AIAskQuestion.context`. |
| **Deduplication** | None — linear flow means each message fires exactly once. |

#### Key Files

| File | Purpose |
|------|---------|
| `api/src/openapi_server/impl/ai_agent_impl.py` | 4 `emit_working_update` calls in `_ask_agent_core_inner()` |
| `common/streaming/live_updates.py` | `emit_working_update()` wrapper |
| `a2a/server.py` | `/tasks` bridge — `_tasks_node()`, EventQueue registry |

#### Known Gaps

- No tool-aware messages — all messages are generic regardless of what processing step is running

---

### 3.3 Security Advisory / Security Hardening

> **Repo:** `CXEPI/risk-app`

Both agents share **identical** code in `security_assessment_agent_impl.py`. The only differences are environmental (MCP schema endpoints, system prompts, guardrail policies).

#### Architecture

Monolithic async function (no LangGraph).

#### Key Behaviors

**Messages (4 fixed + dynamic per tool):**

| # | Message | Progress | Trigger |
|---|---------|----------|---------|
| 1 | `"Understanding your question..."` | 0.1 | Initial entry |
| 2 | `"Checking available data..."` | 0.3 | Before first LLM invocation |
| 3 | **Dynamic** (see below) | 0.3–0.85 | Per tool-call loop iteration |
| 4 | `"Preparing your answer..."` | 0.9 | Before guardrails/output |

**Dynamic tool messages** — `_build_working_message()`:

| Tool name | Message |
|-----------|---------|
| `mcp_rag_data` | `"Checking available data..."` |
| `mcp_get_table_schema` | `"Checking available data..."` |
| `mcp_build_sql_by_domain` | `"Planning the best way to retrieve your data..."` |
| `mcp_execute_sql` | `"Gathering latest results..."` |
| *(fallback)* | `"Validating your request..."` |

**Dynamic progress calculation:**
```python
progress = min(0.3 + (iteration / max_iterations) * 0.5, 0.85)
```

| Behavior | Implementation |
|----------|----------------|
| **Emission function** | Local `_emit_working_update()` wrapper — calls `post_working_update_to_a2a_handler()` from `cvi_ai_shared`. **Awaited** — blocks until POST completes. Extracts `context_id` from `ai_ask_question.context["context_id"]`. |
| **Deduplication** | None — fires on every loop iteration. The same message (e.g. "Checking available data...") can be sent multiple times. |

#### Key Files

| File | Purpose |
|------|---------|
| `security-advisory-ai-api/src/openapi_server/impl/security_assessment_agent_impl.py` | All progress calls + `_build_working_message()` |
| `security-hardening-ai-api/src/openapi_server/impl/security_assessment_agent_impl.py` | Identical copy |

#### Known Gaps

- Duplicate messages possible — same message sent on consecutive loop iterations with no dedup

---

### 3.4 Health Risk Insights (Assessment Rating)

> **Repo:** `CXEPI/cxp-health-risk-insights-ai`

#### Architecture

LangGraph nodes + A2A skill handler (dual-layer emission).

#### Key Behaviors

**Messages (4 across 2 layers):**

| # | Message | Progress | Source |
|---|---------|----------|--------|
| A2A | `"Understanding your request..."` or `"Assessing your asset..."` | — | A2A skill handler (direct EventQueue enqueue) |
| 1 | `"Thinking about your question..."` | 0.2 | LangGraph `assistant` node |
| 2 | `"Analyzing your data..."` | 0.4 | LangGraph `execute_tools` node |
| 3 | `"Done — here's what I found."` | 100 | `/chat` endpoint (non-streaming only) |

**A2A handler message selection:**
```python
working_event_message = "Understanding your request..."
if not prompt.strip():
    if serial_numbers:
        working_event_message = "Assessing your asset..."
```

| Behavior | Implementation |
|----------|----------------|
| **Emission functions** | Graph nodes: Custom `emit_progress()` in `agent/services/progress_notifier.py` — **awaited** (unlike ConfigBP). A2A handler: `_enqueue_working_event()` — direct `event_queue.enqueue_event()` (no HTTP POST; already in the A2A process). |
| **Deduplication** | `once=True` parameter only (no state flags). Prevents "Thinking" from firing again when `assistant` is re-entered after tools. |

**Graph structure:**
```
START → assistant → [tools_condition] → execute_tools → assistant → ... → END
```

#### Key Files

| File | Purpose |
|------|---------|
| `agent/services/progress_notifier.py` | `emit_progress()` — **awaited** POST to `/tasks` |
| `agent/nodes/assistant.py` | 1 `emit_progress` call ("Thinking") |
| `agent/services/graph_builder.py` | 1 `emit_progress` call ("Analyzing") in `execute_tools()` |
| `agent/api/server.py` | 1 `emit_progress` call ("Done") in `/chat` handler |
| `a2a_server/handlers/skill_handlers.py` | `_enqueue_working_event()` — direct enqueue ("Understanding"/"Assessing") |
| `a2a_server/core/streaming.py` | `/tasks` bridge, EventQueue registry |

#### Known Gaps

- "Done" message only fires on non-streaming `/chat` endpoint, not on `/chat/stream`
- Dual-layer emission creates more progress events than other agents — one from A2A layer before agent API is even called

---

## 4. Cross-Agent Comparison

### 4.1 Feature Matrix

**Message inventory:**

| Message | ConfigBP | LDOS | Risk-App | HRI |
|---------|:--------:|:----:|:--------:|:---:|
| "Understanding your question..." | | x | x | |
| "Understanding your request..." | | | | x |
| "Thinking about your question..." | x | | | x |
| "Validating your request..." | | x | x* | |
| "Checking available data..." | | | x | |
| "Planning the best way to retrieve your data..." | | | x | |
| "Gathering information..." | x | | | |
| "Gathering latest results..." | | | x | |
| "Analyzing your data..." | | | | x |
| "Running your query..." | | x | | |
| "Assessing your asset..." | | | | x** |
| "Preparing your answer..." | x | | x | |
| "Done — here's what I found." | | x | | x*** |

\* Risk-App: fallback message in `_build_working_message()` only
\** HRI: conditional — only when empty prompt + serial numbers
\*** HRI: non-streaming `/chat` endpoint only

**Architecture comparison:**

| Aspect | ConfigBP | LDOS | Risk-App (Adv/Hard) | HRI |
|--------|----------|------|---------------------|-----|
| **Emission architecture** | LangGraph nodes | API request handler | Monolithic async fn | LangGraph + A2A handler |
| **Total distinct messages** | 3 | 4 | 6 (incl. dynamic) | 4 (across 2 layers) |
| **Emit function** | Custom `emit_progress()` | `emit_working_update()` (shared) | `_emit_working_update()` (local wrapper) | Custom `emit_progress()` |
| **Fire-and-forget?** | **Yes** | No (awaited) | No (awaited) | No (awaited) |
| **Dedup mechanism** | State flags + `once` | None (linear) | None | `once=True` only |
| **Tool-aware messages?** | No (generic) | No | **Yes** (per tool type) | No |
| **Dynamic progress value?** | No (fixed 0.2/0.4/0.8) | No (fixed 0.1/0.2/0.6/1.0) | **Yes** (sliding 0.3–0.85) | No (fixed 0.2/0.4) |
| **Sends "Done" message?** | No | Yes | No | Yes (non-streaming) |
| **Uses `cvi_ai_shared` directly?** | No (custom notifier) | Yes | Yes | No (custom notifier) |

### 4.2 Observations

1. **No standardized message set.** Each agent defines its own strings independently. There is no shared enum, constant file, or contract governing what messages to send.

2. **ConfigBP is the only fire-and-forget agent.** All others await the POST, which guarantees the A2A server receives the update before the graph node continues. ConfigBP's fire-and-forget risks a race where the EventQueue is unregistered before the notification arrives (mitigated by the short timeout).

3. **Risk-App is the most granular.** It maps tool names to specific user-facing messages (`_build_working_message()`) and uses a sliding progress value that advances with each iteration. Other agents use fixed messages.

4. **HRI has dual-layer emission.** The A2A skill handler enqueues a working event directly onto the EventQueue (no HTTP POST needed since it's in the same process), while the graph nodes POST via the `/tasks` bridge. This means HRI sends more progress events than the others — one from the A2A layer before the agent API is even called.

5. **LDOS is the simplest.** Linear flow through the API request handler, no dedup needed, no tool awareness.

6. **Two different `emit_progress` implementations exist.** ConfigBP and HRI both define their own `agent/services/progress_notifier.py`, but they differ: ConfigBP uses fire-and-forget, HRI uses awaited POST. Neither uses the shared `post_working_update_to_a2a_handler()` from `cvi_ai_shared`.

7. **"Done" messages are inconsistent.** LDOS and HRI send a completion message; ConfigBP and Risk-App do not. HRI only sends it on the non-streaming `/chat` endpoint, not on `/chat/stream`.

---

## 5. Recommendations

1. **Standardize message strings.** Define a shared set of step-update messages (enum or constant file in `cvi_ai_shared`) so all agents present a consistent UX.
2. **Standardize emission pattern.** Decide between fire-and-forget (ConfigBP) and awaited (all others). Awaited is safer; fire-and-forget is faster but risks races.
3. **Consolidate `emit_progress` implementations.** ConfigBP and HRI both have custom `progress_notifier.py` — unify into `cvi_ai_shared` with configurable fire-and-forget vs. awaited behavior.
4. **Add deduplication to Risk-App.** Currently fires the same message on consecutive tool-call loop iterations — add message-level dedup to avoid redundant UI updates.
5. **Decide on "Done" messages.** Either all agents send one (consistent UX) or none do (simpler, let the final response itself signal completion).
