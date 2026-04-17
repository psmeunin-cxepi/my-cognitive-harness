# CXP-28841 — Mistral Tool-Call Narration Bug: Analysis & Recommendations

## Summary

`mistral-medium-2508` occasionally returns a tool call serialized as plain text in the `content` field with `tool_calls: []` instead of using the structured `tool_calls` array. The agent loop treats this as a final answer and returns the raw JSON string to the user.

**Failure signature:**
```
AIMessage(
  content = 'I\'ll use the following tools: [{"id": "XZQ5YZQ5YZ", "function": {"name": "mcp_build_sql_by_domain", "arguments": "..."}, "type": "function"}]',
  tool_calls = []
)
```

---

## Evidence

Confirmed across 4 independent traces/inputs:

| Artifact | Agent | Trigger |
|---|---|---|
| LangSmith trace `019d9b06` | Security Assessment | B (schema re-fetch) |
| `security-input-1.json` / `output-1.json` | Security Assessment | A (3 consecutive failures) |
| `security-input-2.json` | Security Hardening | A (2 typed errors) |
| `security-input-3.json` / `security-output-3.txt` | Security Assessment | B (schema re-fetch) |

---

## Root Cause: Two Independent Triggers

### Trigger A — Consecutive typed errors (≥2–3)

After receiving multiple consecutive typed validation errors from `mcp_build_sql_by_domain`, the model loses confidence in structured tool calling and falls back to narrating the next intended call as plain text.

**Mechanism:**
1. Model calls `mcp_build_sql_by_domain` with invalid args (e.g., raw SQL expressions in `columns`, dot-qualified column names in `aggregations`)
2. Tool returns a typed error (e.g., `"Invalid column 'COUNT(DISTINCT assets.id) AS total_assets'"`)
3. Model retries with adjusted args — still invalid — gets another typed error
4. After 2–3 consecutive failures, model degenerates: produces narrated tool call in `content`, `tool_calls: []`

**Observed in:** `security-input-2.json` (2 typed errors → degeneration), `input-1.json` (2 typed + 1 generic → degeneration)

### Trigger B — Generic error instructing schema re-fetch

A generic SQL engine error contains `"Call mcp_get_table_schema to verify available columns and retry."` The model obeys, re-fetching the schema (~13K tokens). The conversation now reads `[schema → failed_sql → schema]`, structurally identical to the post-schema state at Turn 2. The model cannot issue a new structured tool call without forming a malformed conversation (two consecutive AI messages), so it narrates instead.

**Mechanism:**
1. Model calls `mcp_build_sql_by_domain` with dot-qualified column name (e.g., `bulletins.psirt_id`)
2. Tool returns generic error: `"Query failed: one or more column names are invalid. Call mcp_get_table_schema…"`
3. Model re-fetches schema → conversation context now has `[schema → fail → schema]`
4. Model cannot insert a new structured tool call after two consecutive tool results without a matching AI tool_call in between
5. Model narrates instead

**Observed in:** trace `019d9b06`, `security-input-3.json`

### Tool call ID behavior (secondary observation)

- When the degeneration follows a prior `mcp_build_sql_by_domain` failure, the model sometimes **recycles** the failed call's ID (e.g., `wfv9wUzx6` in input-3, `XZQZYQZQZQ` in input-2)
- When the prior failures were all resolved successfully (i.e., last failed call was consumed), the model **generates a fresh filler ID** (e.g., `XZQ5YZQ5YZ` in output-1)
- ID recycling is incidental, not causal

---

## Upstream Root: `mcp_build_sql_by_domain` input validation gaps

The tool accepts arguments the SQL engine rejects but does not validate at the tool boundary:

| Invalid input | Why model sends it | Error type |
|---|---|---|
| Raw SQL in `columns` (e.g., `COUNT(DISTINCT id) AS total`) | Model treats `columns` as a SQL SELECT list | Typed error |
| Dot-qualified names in `aggregations[].column` (e.g., `assets.id`) | Model observes `table.column` pattern in schema examples | Typed error |
| `COUNT_DISTINCT` as aggregation function | Model infers this from SQL semantics; `_normalize_aggregation_function` in the agent normalizes variant spellings to `COUNT_DISTINCT` but this value is still rejected by the SQL engine | Generic error |
| `bulletins.psirt_id` in `columns` | Model uses the table-qualified name from `join_specs` | Generic error → re-fetch |

---

## Agent-Level Issues

### 1. Loop exit does not detect narrated tool calls

In `security_assessment_agent_impl.py`:

```python
while isinstance(response, AIMessage) and response.tool_calls and ...:
    ...

answer = response.content  # ← returned directly to user
```

When degeneration occurs (`tool_calls=[]`, `content` = narrated JSON), the loop exits and the raw `"I'll use the following tools: [...]"` string is returned to the user with no detection or recovery.

### 2. `_normalize_aggregation_function` worsens Trigger A

```python
def _normalize_aggregation_function(function_name: str) -> str:
    normalized = function_name.strip().upper()
    if normalized in {"COUNT DISTINCT", "COUNT-DISTINCT", "COUNTDISTINCT"}:
        return "COUNT_DISTINCT"   # still unsupported by SQL engine
    return normalized
```

This normalizes variant spellings into `COUNT_DISTINCT` before passing to the SQL tool — but `COUNT_DISTINCT` itself is not a valid aggregation function. The normalization produces clean-looking arguments that still trigger the generic SQL error.

---

## Recommendations (Priority Order)

### Fix 1 — Remove schema re-fetch instruction from the generic error message *(blocks Trigger B entirely)*

**Location:** SQL MCP tool server — the error message returned by the SQL engine.

**Change:**
```
Before: "Query failed: one or more column names are invalid. Call mcp_get_table_schema to verify available columns and retry."
After:  "Query failed: column names must be plain identifiers without table prefix (e.g., 'psirt_id' not 'bulletins.psirt_id'). Remove any table alias prefixes and retry."
```

This mechanically prevents the re-fetch, so the `[schema → fail → schema]` conversation pattern never forms. Eliminates Trigger B entirely.

### Fix 2 — Validate and strip dot-qualified column names in `mcp_build_sql_by_domain` *(reduces Trigger A)*

**Location:** Either the SQL MCP tool server or `mcp_build_sql_by_domain` in `security_assessment_agent_impl.py`.

Reject (or auto-strip) `table.column` format in `columns`, `aggregations[].column`, `group_by`, `order_by`, and `filters[].column` with a specific typed error:

```
"'assets.id' is not a valid column name — use plain 'id' (no table prefix). Table aliases belong in join_specs only."
```

One clear, actionable error → model self-corrects in one turn → fewer failures accumulating toward Trigger A.

### Fix 3 — Reject `COUNT_DISTINCT` and fix `_normalize_aggregation_function`

**Location:** `security_assessment_agent_impl.py` → `_normalize_aggregation_function`

Replace the current normalization (which preserves an invalid value) with a rejection:

```python
VALID_AGG_FUNCTIONS = {"COUNT", "SUM", "AVG", "MIN", "MAX"}

def _normalize_aggregation_function(function_name: str) -> str:
    normalized = function_name.strip().upper()
    if normalized in {"COUNT DISTINCT", "COUNT-DISTINCT", "COUNTDISTINCT", "COUNT_DISTINCT"}:
        raise ValueError(
            "Unsupported aggregation function 'COUNT_DISTINCT'. "
            "Use function='COUNT' with distinct=True, or filter duplicates before aggregating."
        )
    if normalized not in VALID_AGG_FUNCTIONS:
        raise ValueError(
            f"Unsupported aggregation function '{normalized}'. "
            f"Valid values: {', '.join(sorted(VALID_AGG_FUNCTIONS))}."
        )
    return normalized
```

This produces a typed error the model can correct, rather than a generic SQL engine error that triggers the re-fetch instruction.

### Fix 4 — Detect degenerated response in the agent loop *(prevents bad output reaching the user)*

**Location:** `security_assessment_agent_impl.py` — after the agent loop.

Add a guard that detects the narration pattern and fails cleanly:

```python
answer = response.content

# Detect degenerated tool-call narration
if answer and "I'll use the following tools:" in answer and not response.tool_calls:
    logger.error(
        "LLM produced narrated tool call instead of structured tool_calls. "
        "This indicates model degeneration after repeated tool failures."
    )
    answer = (
        "I was unable to retrieve the data needed to answer your question. "
        "Please try rephrasing or narrowing your request."
    )
```

This does not fix the root cause but prevents the JSON from leaking to the user while the upstream fixes are deployed.

### Fix 5 — Stop re-fetch via system prompt *(cheap backstop)*

Add to the agent system prompt:

```
- Do not call mcp_get_table_schema more than once per conversation.
- If mcp_build_sql_by_domain fails twice in a row, stop and ask the user to clarify what data they need.
```

Low effectiveness on its own (instructions are ignored during degeneration), but adds a soft guardrail for edge cases and reduces schema re-fetch probability before degeneration occurs.

---

## Fix Effectiveness Matrix

| Fix | Blocks Trigger A | Blocks Trigger B | Prevents user exposure | Complexity |
|---|---|---|---|---|
| 1 — Remove re-fetch instruction | No | **Yes (fully)** | No | Low |
| 2 — Validate dot-qualified names | Partially | No | No | Medium |
| 3 — Reject COUNT_DISTINCT | Partially | No | No | Low |
| 4 — Agent loop guard | No | No | **Yes (fully)** | Low |
| 5 — System prompt retry guard | Partially | Partially | No | Low |

**Minimum viable set: Fix 1 + Fix 4** — eliminates Trigger B and prevents user exposure regardless of trigger.  
**Full remediation: Fix 1 + 2 + 3 + 4** — eliminates both triggers and closes the user-exposure gap.
