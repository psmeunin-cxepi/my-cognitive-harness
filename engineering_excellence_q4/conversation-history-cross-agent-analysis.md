# Conversation History — Cross-Agent Analysis

> **Workstream:** EE-1 — Agent Graph & State Architecture
>
> **Date:** 2026-04-28
>
> **Status:** Research
>
> **Owner(s):** Philip Smeuninx

---

## 1. What This Is

CX IQ agents need to handle **multi-turn conversations** so that a follow-up question like *"and for the production devices?"* can be answered with awareness of what came before.

None of the agents in scope use a **LangGraph checkpointer** today — there is no agent-side persistence of state across runs, even within the same thread. Instead, each request carries the prior conversation as a string in the A2A message metadata (`recent_context`), produced by the upstream Semantic Router. Each agent then decides on its own how to extract, transform, and inject that string into the LLM call.

This document analyses how each agent handles that upstream-supplied conversation history — the "memory substitute" — and compares the approaches.

> **Note on terminology.** "Conversation history" here refers exclusively to the per-request string supplied by the caller. It is **not** persisted state, and it is **not** the same as a LangGraph checkpoint. A separate workstream covers checkpointer adoption.

---

## 2. How It Works Today

All agents share the same upstream contract:

```
Upstream (Semantic Router)
  → builds conversation summary string in "[role] content\n…" format
  → places it in A2A Message metadata as "recent_context"
  → (optionally for LDOS) also places a typed structured form as "recent_context_structured"
  ↓
A2A handler in agent
  → reads context.metadata["recent_context"]
  → forwards to internal /chat (or equivalent) HTTP endpoint
  ↓
Agent API layer
  → extracts, optionally transforms
  → injects into the LangGraph input messages (or stores it and never uses it)
  ↓
LLM call
```

**Three dimensions diverge across agents:**

1. **Transport into the agent core** — how the A2A string is forwarded to the agent's internal HTTP API (typed Pydantic field vs. untyped dict access).
2. **Transformation** — verbatim string vs. parsed list of typed `BaseMessage` objects.
3. **Injection format** — `SystemMessage` (templated), `HumanMessage` (with prefix), prepended typed-message list, or *not injected at all*.

No agent applies any of:
- Truncation / windowing (last N turns)
- Token budgeting
- Summarization
- Deduplication
- Input guardrails on the history itself

No agent uses a LangGraph checkpointer.

---

## 3. Implementation Analysis

### 3.1 Config Best Practices (ConfigBP)

#### Extraction
A2A handler `_extract_metadata` in [a2a_server/handlers/skill_handlers.py](a2a_server/handlers/skill_handlers.py) reads `context.metadata.get("recent_context", "")` (plain string, default `""`) and forwards it as a JSON `recent_context` field to the internal `/chat` endpoint. The internal API model is:

```python
class ChatRequest(BaseModel):
    prompt: str
    recent_context: str = ""
    user_metadata: Optional[UserMetadata] = None
    skill_id: str = ""
    ui_filters: Optional[dict] = None
```

#### Transformation
Verbatim — no parsing. The string is wrapped in a markdown template (`_CONVERSATION_HISTORY_TEMPLATE` in [agent/api/server.py](agent/api/server.py)) that frames the history for the LLM and includes a UI-context disambiguation rule:

```python
_CONVERSATION_HISTORY_TEMPLATE = (
    "## Conversation History\n"
    "Below is a summary of the recent conversation with this user. "
    "Use it to maintain continuity. Do not repeat information the user has "
    "already seen unless they ask. When the Active UI Context (if present) "
    "and this history reference different entities of the same type and the "
    "user's current message doesn't name which one, follow the disambiguation "
    "rule in the UI Context block.\n\n"
    "{recent_context}"
)
```

#### Injection
`_build_messages()` emits a `SystemMessage(template + history)` placed **after** the UI-context `SystemMessage` and **before** the current `HumanMessage(prompt)`. The `assistant` node in [agent/nodes/assistant.py](agent/nodes/assistant.py) then prepends a skill-specific `SystemMessage`. Final stack into the LLM:

```
[ skill SystemMessage,
  ui-context SystemMessage,        # if UI context present
  history SystemMessage,           # if history present
  HumanMessage(prompt) ]
```

#### Empty handling
Falsy `recent_context` → no message added. Silent.

#### Notes
- History is treated as **continuity-only**; the UI context is canonical for entity disambiguation when both reference the same entity type.
- No checkpointer.

---

### 3.2 LDOS (Asset General + Asset Criticality)

Both agents share the same A2A handler and API layer; conversation-history handling is identical between them.

#### Extraction
`ask_ldos_handler` in [a2a/server.py](a2a/server.py) reads **two** fields from A2A metadata:

```python
recent_context = context.metadata.get("recent_context", "")
recent_context_structured = context.metadata.get("recent_context_structured", None)
```

The `recent_context_structured` form is a typed `RecentContext` Pydantic model imported from `cvi_ai_shared.types`. LDOS is the only agent that accepts this structured form.

The API layer extracts via `ContextHandler.extract_conversation_history()` in [common/context_handler_service.py](common/context_handler_service.py), which accepts either a plain string or a list-of-dicts (the list is reformatted to `[role] content\n…`).

#### Transformation
- String form: passed through.
- List form: reformatted to `[role] content\n…` joined by newlines.
- Structured form: validated with `RecentContext.model_validate()`; on failure, silently degraded to `None`.
- No truncation, no dedup, no filtering.

#### Injection
Both forms are stored in `config["configurable"]` via `agent_configuration.create_configuration`:

```python
"recent_context": recent_context,
"structured_recent_context": structured_recent_context,
```

**They are never read.** No graph node references `config["configurable"]["recent_context"]` or its structured counterpart. No prompt template includes history. The fields reach the LangGraph configuration and stop there.

#### Empty handling
Returns `""` / `None`. Silent.

#### Notes
- The extraction and storage code paths are fully implemented and tested, but the consumption side has not been wired in — appears to be preparation for an unimplemented feature.
- No checkpointer.

---

### 3.3 Risk-App (Security Advisory + Security Hardening)

Both agents are byte-for-byte identical in conversation-history handling.

#### Extraction
A2A handler (`ask_security_assessment_handler` / `ask_security_hardening_handler` in [security-advisory-ai-a2a/server.py](security-advisory-ai-a2a/server.py) and [security-hardening-ai-a2a/server.py](security-hardening-ai-a2a/server.py)) reads `context.metadata.get("recent_context", "")` and **mutates** the outgoing payload:

```python
recent_context = context.metadata.get("recent_context", "")
if recent_context and question_payload.context is not None:
    question_payload.context.conversation_history = recent_context
```

The API layer then reads it back via untyped dict access:

```python
conversation_history = ai_ask_question.context.get("conversation_history") or ""
```

This is the only agent where the field is accessed untyped (not declared on the Pydantic model). See `ask_security_assessment_agent` in [security-advisory-ai-api/src/openapi_server/impl/security_assessment_agent_impl.py](security-advisory-ai-api/src/openapi_server/impl/security_assessment_agent_impl.py).

#### Transformation
Verbatim, prepended with a hard-coded instruction prefix:

```python
messages.append(HumanMessage(content=(
    "Here is the recent conversation history for context. "
    "Use it to understand follow-up questions, but always "
    "answer based on current data from your tools:\n\n"
    + conversation_history
)))
```

#### Injection
Wrapped in a **`HumanMessage`** (not `SystemMessage`), inserted between the system prompt and the current user `HumanMessage(question)`:

```
[ SystemMessage(system_prompt + context_filter_summary),
  HumanMessage(prefix + history),    # if history present
  HumanMessage(current question) ]
```

#### Empty handling
Falsy → message not added. Silent.

#### Notes
- `_format_context_filter()` includes a skiplist that excludes `conversation_history` from the system-prompt context summary — this prevents double-injection.
- **Guardrail gap:** input guardrails screen only the current question (`ai_ask_question.question`), not the history string. If an attacker can influence `recent_context`, prompt-injection content there would bypass input screening.
- No checkpointer.

---

### 3.4 Health Risk Insights (HRI)

#### Extraction
`_extract_metadata` in [a2a_server/handlers/skill_handlers.py](a2a_server/handlers/skill_handlers.py) reads `context.metadata.get("recent_context", "")` and forwards it to the internal `/chat` endpoint:

```python
class ChatRequest(BaseModel):
    prompt: str
    recent_context: Optional[str] = None
    user_metadata: Optional[dict] = None
    skill_id: Optional[str] = None
```

#### Transformation
HRI is the only agent that **parses** the history. `parse_conversation_history()` in [agent/utils/converstion_parser.py](agent/utils/converstion_parser.py) (sic — typo in filename) regex-parses the `[role] content` Semantic Router format into LangChain typed messages:

```python
_TURN_RE = re.compile(
    r"\[(?P<role>[^\]]+)\]\s*(?P<content>.+?)(?=\n\[|\Z)",
    re.DOTALL,
)

def parse_conversation_history(history: Optional[str]) -> List[HumanMessage | AIMessage]:
    if history is None or not str(history).strip():
        return []
    messages = []
    for match in _TURN_RE.finditer(history):
        role = match.group("role").strip().lower()
        content = match.group("content").strip()
        if not content:
            continue
        if role == "user":
            messages.append(HumanMessage(content=content))
        else:
            messages.append(AIMessage(content=content))
    return messages
```

- `[user]` → `HumanMessage`
- everything else (agent names, `[SUMMARY]`) → `AIMessage`
- empty content blocks dropped
- no truncation or windowing

#### Injection
Parsed list is **prepended** to the current `HumanMessage(prompt)` and passed as `state["messages"]` to LangGraph. The `assistant` node in [agent/nodes/assistant.py](agent/nodes/assistant.py) then prepends a single `SystemMessage(skill prompt)`. Final stack:

```
[ SystemMessage(skill prompt),
  HumanMessage(prev user turn),
  AIMessage(prev agent turn),
  …,
  HumanMessage(current prompt) ]
```

A code comment in `assistant.py` explicitly documents the design: *"Prior turns are expected in `state["messages"]` (e.g. from parsed `recent_context`); no duplicate history in the system prompt."*

#### Empty handling
`None` / empty / whitespace-only / unparseable → `[]`. Silent single-turn behavior.

#### Notes
- Closest to the LangChain idiomatic pattern — the LLM sees real role-tagged turns instead of a flattened string.
- A streaming `/chat/stream` endpoint exists but is marked *"NOT USED TODAY WITH CVI SEMANTIC ROUTER"*.
- No checkpointer.

---

## 4. Cross-Agent Comparison

### 4.1 Feature Matrix

| Dimension | ConfigBP | LDOS (Asset Gen + Crit) | Risk-App (Sec Adv + Hard) | HRI |
|---|---|---|---|---|
| **A2A field read** | `metadata.recent_context` | `metadata.recent_context` + `metadata.recent_context_structured` | `metadata.recent_context` | `metadata.recent_context` |
| **API model field** | `ChatRequest.recent_context: str` | `AIAskQuestion.conversation_history` (typed) | `AIAskQuestion.context["conversation_history"]` (untyped dict) | `ChatRequest.recent_context: Optional[str]` |
| **Structured form accepted** | No | Yes (`RecentContext` from `cvi_ai_shared`) | No | No |
| **Parsed?** | No (verbatim string) | Light: list-of-dicts → string | No (verbatim string) | Yes (regex → typed messages) |
| **Injection format** | `SystemMessage` (templated) | *Not injected* (stored in config only) | `HumanMessage` (with prefix) | Prepended typed `Human`/`AI` messages |
| **Position vs. system prompt** | After skill + UI-context system messages | n/a | After system, before user msg | After system, before current user msg |
| **Used by LLM?** | ✅ Yes | ❌ No (dead-end) | ✅ Yes | ✅ Yes |
| **Truncation / windowing** | None | None | None | None |
| **Empty handling** | Silent skip | Silent (`""` / `None`) | Silent skip | Silent (returns `[]`) |
| **Input guardrails on history** | n/a (no input guardrails) | n/a | ❌ No — only current question screened | n/a |
| **LangGraph checkpointer** | No | No | No | No |
| **Disambiguation logic ties to history** | Yes (paired with UI context in template) | No | No (generic instruction prefix) | No (relies on LLM) |

### 4.2 Observations

1. **The wire format is uniform.** Every agent reads A2A `context.metadata["recent_context"]`. This is a Semantic Router convention (`[role] content\n…`) and is the de facto contract — but it is undocumented on the agent side.
2. **Four implementations of the same concern.** Each agent invented its own injection style (`SystemMessage` template, `HumanMessage` prefix, parsed typed messages, or *nothing*). No shared helper exists in `cvi_ai_shared`.
3. **Only HRI uses the LangChain idiom.** Parsing into `HumanMessage`/`AIMessage` lets the LLM see actual role-tagged turns, which is what the chat-completion API was designed for. The other agents flatten history into a single block of text.
4. **LDOS extracts but never injects.** The A2A handler, API extractor, and configuration plumbing are all in place — but no node consumes the field. This appears to be groundwork for an unimplemented feature.
5. **LDOS is the only agent that accepts a structured form.** `RecentContext` exists in `cvi_ai_shared.types` and LDOS validates it, but the structured form is also unused in the workflow.
6. **No agent applies windowing or token budgeting.** The full upstream string is passed through. Token-budget overrun is left to the LLM provider.
7. **Risk-app does not screen history through input guardrails.** Only the current question is screened. If `recent_context` can be influenced by an attacker upstream, this is a prompt-injection vector.
8. **Only ConfigBP wires history into disambiguation.** Its template explicitly tells the LLM how to resolve entity-type collisions between UI context and history. Other agents leave disambiguation to the LLM.
9. **No agent uses a LangGraph checkpointer.** History-as-memory is the only mechanism in production today; the agents are stateless across requests by design (state lives upstream in the Semantic Router).

---

## 5. Recommendations

1. **Standardize the parser.** Promote HRI's `parse_conversation_history()` to `cvi_ai_shared` (e.g. `cvi_ai_shared.history.parse`). All agents should consume the same parser so the `[role] content` contract has one canonical implementation.
2. **Standardize the injection format.** Adopt **prepended typed `HumanMessage` / `AIMessage` list** (the HRI pattern) as the canonical injection — this is the LLM-native format and avoids the flattening that obscures turn boundaries.
3. **Promote the structured form.** `RecentContext` from `cvi_ai_shared.types` is already accepted by LDOS. Make all agents accept (and prefer) the structured form, falling back to the string form for backward compatibility. Update Semantic Router to emit it consistently.
4. **Resolve LDOS's unused path.** Either wire `recent_context` into the LDOS workflows (preferred — LDOS is multi-turn-capable from the UI) or remove the unused extraction/storage code to avoid misleading future maintainers.
5. **Close the risk-app guardrail gap.** Apply input guardrails (or at least a length/character-class sanity check) to `conversation_history` as well as the current question. Document the trust boundary.
6. **Document the upstream contract.** The `[role] content\n…` format and the `recent_context` / `recent_context_structured` keys are an implicit contract between Semantic Router and the agents. Promote it to a written spec under `agent_behavioural_spec/`.
7. **Add a token-budget / windowing strategy at the shared layer.** Today the full string is passed through. A shared helper (`trim_history_to_token_budget`, `keep_last_n_turns`) in `cvi_ai_shared` would let agents apply consistent limits.
8. **Plan checkpointer adoption (EE-1 follow-up).** This document is scoped to the "history-as-memory" substitute, which sits in the **short-term memory** layer of EE-1. A separate proposal under the same workstream should cover real LangGraph checkpointer adoption (Postgres / Redis backends) for short-term memory, and a **long-term memory** layer (cross-thread, persisted user/account-level memory) for facts the agents should remember beyond a single conversation.
