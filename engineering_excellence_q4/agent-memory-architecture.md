# Agent Memory Architecture

> **Workstream:** EE-1 — Agent Graph & State Architecture
>
> **Date:** 2026-04-29
>
> **Status:** Proposal
>
> **Owner(s):** TBD
>
> **JIRA:** [CXP-29385](https://cisco-cxe.atlassian.net/browse/CXP-29385)

---

## 1. Objective

Define the memory architecture for Cisco IQ domain agents: what types of memory each agent needs, what data belongs in each type, and what lifecycle governs how memory is written, managed, and read. This is the foundational "what" — implementation choices (checkpointer, persistence backend, store) follow from these decisions and are scoped separately.

---

## 2. Background

Today all Cisco IQ agents are **stateless**: they receive a `recent_context` string from the Semantic Router and re-derive conversational state on every request. There is no persistence across turns, no memory management, and no shared contract for what agents should remember or forget. As agents mature toward multi-turn, context-aware behaviour, a deliberate memory architecture is needed — not just a persistence mechanism, but a definition of *what kinds of memory exist, what goes into each, and how each is maintained*.

### 2.1 Current State

| Agent | Memory Mechanism | Persistence | State Management |
|---|---|---|---|
| Config Best Practices | `recent_context` from SR | None | Stateless |
| Health Risk Insights | `recent_context` from SR | None | Stateless |
| Security Advisory | `recent_context` from SR | None | Stateless |
| Security Hardening | `recent_context` from SR | None | Stateless |
| LDOS | `recent_context` from SR | None | Stateless |

No agent uses a LangGraph checkpointer. No agent retains or distils knowledge across sessions. All domain knowledge is retrieved ad-hoc via RAG or MCP tools on every request.

### 2.2 Why Now

- Multi-turn conversations require the agent to remember what was discussed within a session
- Context switch handling (RFC-001) depends on the agent knowing what the previous topic was
- Deictic resolution ("What about the 9200s?") requires episodic context from earlier turns
- Quality improvements (personalisation, proactive recommendations) require retained knowledge
- The Semantic Router's `recent_context` string is a crude approximation that cannot scale

---

## 3. Theoretical Foundation

The architecture uses four temporal scopes drawn from the standard cognitive architecture taxonomy. This is not a novel framework — it is the consensus vocabulary used across cognitive science, AI cognitive architectures, and the LLM agent research community.

### 3.1 Lineage

| Source | Year | Contribution |
|---|---|---|
| Atkinson & Shiffrin — Multi-store memory model | 1968 | Established the short-term / long-term memory distinction |
| Tulving — Episodic vs Semantic memory | 1972 | The foundational distinction: episodic = personal experiences on a timeline; semantic = abstracted facts and knowledge |
| Baddeley & Hitch — Working Memory model | 1974 | Active, limited-capacity processing during a task |
| Soar cognitive architecture (Laird, Newell, Rosenbloom) | 1987 | First AI architecture to implement all four memory types: Working + Procedural + Semantic + Episodic |
| CoALA — Cognitive Architectures for Language Agents (Sumers, Yao, Narasimhan, Griffiths, Princeton) | 2023 | Maps the Soar memory taxonomy to LLM-based agents; proposes structured action space (grounding, reasoning, retrieval, learning) |
| A Survey on the Memory Mechanism of LLM-based Agents (Zhang et al.) | 2024 | Comprehensive survey of memory in LLM agents; same taxonomy |
| Memory for Autonomous LLM Agents (Du) | 2026 | Adds the write-manage-read lifecycle model and five mechanism families |

### 3.2 The Write → Manage → Read Loop

Memory is not just store-and-retrieve. The Du (2026) survey formalises the lifecycle as a three-phase loop:

1. **Write** — what goes into memory, when, and in what format
2. **Manage** — how memory is maintained over time: pruning, summarisation, consolidation, invalidation
3. **Read** — how memory is retrieved when needed: by recency, relevance, session ID, or explicit lookup

The "manage" phase is where most systems fail. Without it, memory stores grow unbounded, fill with stale or contradictory entries, and eventually degrade the agent's reasoning through context dilution.

---

## 4. Memory Taxonomy

Four temporal scopes, each serving a different function with different persistence, retrieval, and management characteristics.

### 4.1 Working Memory — "The RAM"

**What it is:** The information the agent is actively reasoning with during a single request.

**AI implementation:** The context window. It includes the system prompt, conversation history, tool results, RAG-retrieved content, and the current user query.

**Role in architecture:** The only part of memory the LLM can "see" and reason with directly. Fast, but strictly limited by token count. Everything else must be retrieved *into* working memory to be used.

**Example:** When a user asks *"Are there any critical advisories for my Catalyst switches?"*, working memory holds the user's query, the resolved device list from MCP, and the advisory results — all assembled into a single prompt.

**Lifecycle:**

| Phase | Detail |
|---|---|
| **Write** | Assembled per-request from system prompt, episodic history, tool results, RAG content, user query |
| **Manage** | Pruning when token budget is exceeded; priority-based eviction (what gets dropped first?) |
| **Read** | Direct — the LLM attends to the full context window |

**Key questions:**

- What is the token budget per agent?
- What is the assembly order and priority when the window is constrained?
- What gets pruned first — older conversation turns? Tool results? RAG content?
- Should there be a shared schema for working memory assembly across all agents?

**Current state:** Each agent assembles its own context ad-hoc; no shared schema or priority model.

---

### 4.2 Episodic Memory — "The Diary"

**What it is:** A record of specific events and past experiences — what happened, when, in what order.

**AI implementation:** In LangGraph, this is the `GraphState` persisted via checkpointers (`MemorySaver`, `PostgresSaver`, `SqliteSaver`). The typed state object accumulates conversation turns, tool call results, and reasoning traces as the graph executes; the checkpointer serialises and restores it by thread ID across invocations. Stored as structured records (not vectors), retrieved by session/thread ID, recency, or relevance.

**Role in architecture:** Provides continuity across turns and sessions. Allows the agent to recall what was discussed, what tools were called, and what results were returned — without the user repeating themselves.

**Example:** The agent recalls that earlier in this session the user asked about Catalyst 9300 advisories, so when the user says *"What about the 9200s?"*, the agent understands this is a continuation, not a new topic.

**Lifecycle:**

| Phase | Detail |
|---|---|
| **Write** | Every turn: user message, agent response, tool calls and results, reasoning traces |
| **Manage** | Summarisation of older turns; eviction of stale sessions; consolidation triggers (e.g., session end) |
| **Read** | By session ID (current session), by recency (last N turns), or by relevance (semantic similarity to current query) |

**Key questions:**

- How many turns are retained in the current session?
- Is the record raw or summarised?
- What triggers consolidation or eviction?
- What defines a session boundary — time-based, intent-based, explicit user action, or protocol-defined (A2A ContextID)?
- Should episodic memory be the input to semantic memory distillation?

**Current state:** `recent_context` string from the Semantic Router is the only approximation. No agent uses a LangGraph checkpointer; no `GraphState` is persisted across invocations.

---

### 4.3 Semantic Memory — "The Encyclopedia"

**What it is:** Distilled, abstracted knowledge the agent has **learned and retained** — facts, heuristics, and conclusions derived from experience, not tied to a specific episode.

**AI implementation:** A persistent store where the agent writes knowledge it has derived through reasoning over episodic memory or user interactions. This is distinct from RAG retrieval (which queries external domain knowledge) and MCP tool calls (which fetch live data). Semantic memory is knowledge the agent *owns* — it wrote it, it manages it, and it can update or invalidate it.

**Role in architecture:** While episodic memory is *"what happened"*, semantic memory is *"what we learned from what happened."* It allows the agent to accumulate understanding over time rather than starting from zero on every request. In the CoALA framework, semantic memory is populated through **reflection** — the agent reasons over raw episodic records and distils them into generalised knowledge.

> **Important distinction:** RAG and MCP tool calls are **not memory** — they are retrieval actions against external knowledge sources. The agent does not own, manage, or write to those stores. Semantic memory is knowledge the agent has internalised and distilled from its own experience.

**Example:** After several sessions where a customer repeatedly asks about Catalyst 9300 NTP compliance, the agent distils: *"This customer's primary concern is NTP configuration on their Catalyst 9300 fleet."* This is not a fact retrieved from a database — it's a conclusion the agent learned from interaction history.

**Lifecycle:**

| Phase | Detail |
|---|---|
| **Write** | Distilled from episodic memory through reflection — the agent reasons over past interactions and extracts generalisable knowledge |
| **Manage** | Validation (is the learned fact still true?), versioning, invalidation (customer context changed), conflict resolution |
| **Read** | By key lookup, semantic search, or triggered by context (e.g., customer ID matches a stored preference) |

**Key questions:**

- What triggers distillation from episodic → semantic?
- How are learned facts validated, versioned, and invalidated?
- Is semantic memory per-customer, per-agent, or shared across agents?
- What is the relationship to RAG (external knowledge) vs. semantic memory (learned knowledge)?
- What are the risks of learned facts becoming stale or self-reinforcing?

**Current state:** Does not exist. All domain knowledge is retrieved ad-hoc via RAG or MCP tools on every request. Agents do not learn, retain, or distil knowledge across sessions.

**Note:** Semantic memory is likely the most advanced memory scope and may be deferred beyond Q4, depending on the prioritisation decision in Section 6.

---

### 4.4 Procedural Memory — "The Instruction Manual"

**What it is:** Encoded behavioural patterns — how the agent should act in specific situations.

**AI implementation:** System prompt instructions, persona definitions, guardrails, behavioural RFCs, tool selection heuristics, chain-of-thought templates, few-shot examples.

**Role in architecture:** Defines the "agent" in AI agent. It includes the rules for how the agent should respond, when to use tools, what guardrails to enforce, and how to handle edge cases (context switches, ambiguous queries, portfolio-wide questions). In the CoALA framework, procedural memory is the agent's "source code".

**Example:** The instruction *"When the user switches domain topic, acknowledge the switch and confirm the new intent before proceeding"* is a procedural rule — encoded today in each agent's system prompt, documented in RFC-001.

**Lifecycle:**

| Phase | Detail |
|---|---|
| **Write** | Authored by engineers as system prompt instructions, RFCs, or code-level behavioural logic |
| **Manage** | Versioned via code commits; updated through RFC process; tested via behavioural evals |
| **Read** | Loaded into working memory as part of the system prompt on every request |

**Key questions:**

- How are behavioural rules versioned and deployed?
- How do we ensure consistency across agents?
- What is the relationship to EE-5 (Behavioural Spec)?
- Should procedural memory be dynamic (agent learns new behaviours) or static (engineer-authored only)?

**Current state:** Embedded in system prompts per-agent; no shared standard, no version control beyond code commits.

---

### 4.5 Summary

| Memory Type | Analog | What It Stores | How It's Retrieved | Persistence |
|---|---|---|---|---|
| **Working** | RAM | Current prompt, conversation, tool results | Direct (attention mechanism) | Per-request only |
| **Episodic** | Diary | Session history, past interactions | Session ID, recency, relevance | Across turns and sessions |
| **Semantic** | Encyclopedia | Learned facts, distilled heuristics, user preferences | Key lookup, semantic search | Long-term, agent-managed |
| **Procedural** | Instruction Manual | System prompts, guardrails, behavioural rules | Hardcoded in prompt / code | Permanent, engineer-managed |

### 4.6 Why the Distinction Matters

If all memory is treated the same, agents suffer from **context dilution**:

- If **semantic** facts (learned customer preferences) are never distilled and must be re-derived from raw **episodic** logs every time, the agent wastes tokens and reasoning cycles
- If **procedural** rules (guardrails, behavioural specs) are stored only in **episodic** memory, the agent may "forget" them when the relevant log isn't retrieved
- If **episodic** history is never pruned or summarised, the context window fills with stale turns, pushing out the information the agent actually needs

RAG and MCP tool calls are **not memory** — they are retrieval actions against external knowledge sources. Memory is what the agent owns and manages internally.

---

## 5. Scope Boundaries

### 5.1 In Scope

- Define the four memory scopes with clear boundaries and data ownership
- For each in-scope scope: specify the write → manage → read lifecycle
- Working memory assembly standard: token budget, priority model, pruning strategy
- Session boundary definition: what constitutes a session, what triggers a new one
- Cross-agent applicability: the model must apply to all 5 GA agents

### 5.2 Out of Scope (for this ticket)

- **Implementation selection** — which checkpointer, which database, which vector store. These are "how" decisions that follow from the memory model and will be scoped in follow-up tickets
- **Multi-agent shared memory** — cross-agent memory sharing protocols (may be a separate ticket under EE-1)
- **Memory evaluation** — metrics and evals for memory quality (relates to EE-4/EE-5)

---

## 6. Key Decisions Required

| # | Decision | Considerations |
|---|---|---|
| 1 | Which memory scopes are in scope for Q4? | All four may not be needed immediately — working + episodic may be the priority; semantic + procedural may be longer-term |
| 2 | Session boundary definition | Time-based, intent-based, explicit user action, or protocol-defined (A2A ContextID)? |
| 3 | Working memory assembly standard | Shared schema for what goes into the context window and in what priority order |
| 4 | Episodic memory granularity | Raw conversation log vs. summarised history vs. hybrid |
| 5 | Semantic memory ownership | Agent-local vs. shared cross-agent vs. centralised service |
| 6 | Relationship to `recent_context` | Evolve it, replace it, or layer on top of it? |

---

## 7. Acceptance Criteria

- [ ] Memory taxonomy defined — four scopes documented with clear boundaries and data ownership
- [ ] For each in-scope memory type: write, manage, and read lifecycle specified
- [ ] Working memory assembly standard defined — token budget, priority model, pruning strategy
- [ ] Session boundary definition agreed — what constitutes a session, what triggers a new one
- [ ] Cross-agent applicability confirmed — the model applies to all 5 GA agents, not just one
- [ ] Explicit statement of what is deferred (implementation choices, shared memory, evaluation)
- [ ] Architecture specification is sufficient for follow-up implementation tickets

---

## 8. References

- CoALA: Cognitive Architectures for Language Agents (Sumers, Yao, Narasimhan, Griffiths, 2023) — [arXiv:2309.02427](https://arxiv.org/abs/2309.02427)
- Memory for Autonomous LLM Agents: Mechanisms, Evaluation, and Emerging Frontiers (Du, 2026) — [arXiv:2603.07670](https://arxiv.org/abs/2603.07670)
- A Survey on the Memory Mechanism of Large Language Model based Agents (Zhang et al., 2024) — [arXiv:2404.13501](https://arxiv.org/abs/2404.13501)
- A Practical Guide to Memory for Autonomous LLM Agents (Lawson, 2026) — [Towards Data Science](https://towardsdatascience.com/a-practical-guide-to-memory-for-autonomous-llm-agents/)
- [Conversation History — Cross-Agent Analysis](conversation-history-cross-agent-analysis.md)
- [RFC-001: Context Switch Behavior Specification](../agent_behavioural_spec/rfc_context_switch.md)
- Parent EPIC: [CXP-29377](https://cisco-cxe.atlassian.net/browse/CXP-29377) — Q4 Engineering Excellence
- EE-5 — Agent Behavioural Spec (procedural memory overlap)
