# Review: "What Is a Cognitive Harness?" — README Section

> Analysis based on internal critique, architectural framing discussion, and cross-referencing against Salesforce Agentforce, Lilian Weng's LLM agent architecture, HuggingFace smolagents, and IBM Think documentation.

---

## Summary Verdict

The *spirit* of the definition is aligned with the industry. The *what/why vs how/where* framing is accurate and sourced. But the table conflates infrastructure with content, the closing sentence contradicts the table's framing, a recognized core component is absent, and the "personal" context that makes this a *cognitive* harness is never articulated.

---

## Finding 1 — Internal Architectural Contradiction

**Problem:** The table and the closing sentence use two incompatible framings that are never reconciled.

- **Table (Framing A):** "Agent Skills" is listed as a *layer of the harness* → the harness contains the agent's capabilities → the model is *inside* the harness.
- **Closing sentence (Framing B):** *"the agent handles what/why; the harness handles how/where"* → agent and harness are parallel peers → the model is *outside* the harness.

**What the sources say:** Salesforce defines a harness as *"software infrastructure that wraps around an AI model"* — consistently Framing A. The agent is the model + harness combined; neither is useful without the other.

**Recommendation:** Commit to Framing A. Replace the closing sentence with something internally consistent:

> The **model** reasons. The **harness** acts. Together they form a capable, disciplined **agent** — swap the model and the harness persists; add a new tool and the model adapts.

---

## Finding 2 — "Agent Skills" Is Not a Harness Infrastructure Layer

**Problem:** The table lists Agent Skills alongside MCP Servers, Context Engineering, and Guardrails as a peer infrastructure layer. This is categorically incorrect.

Skills are *content* — curated instructions injected into the context window to give the model domain expertise. They are consumed *by* the harness's context management system, not a layer of the harness itself. Listing skills as infrastructure is like listing "invoices" as a layer of an accounting system alongside "database," "auth," and "audit log."

No industry source (Salesforce, IBM, Lilian Weng, HuggingFace) treats domain knowledge or instructions as a harness component.

**What it actually is:** Agent Skills belong under Context Engineering — they are the primary mechanism by which context is curated and injected on demand.

**Recommendation:** Remove "Agent Skills" from the harness layer table. The table should describe infrastructure. Skills are what you *put into* the harness, not a part of its structure. The dedicated "Agent Skills" section later in the README handles this correctly — that is the right place for it.

---

## Finding 3 — Lifecycle and State Management Is Missing

**Problem:** The table has four layers. The industry consistently identifies a fifth: lifecycle and state management.

Salesforce calls this out explicitly as a core harness component: saving agent state to survive restarts, handling "AI amnesia" across long-running tasks, and managing the agent's boot sequence with correct system prompts and permissions. Lilian Weng's foundational agent architecture also treats long-term memory and persistence as a separate, first-class component alongside planning, memory, and tool use.

For a personal harness that spans multiple sessions, tools, and runtimes, this is arguably the most important differentiator from a simple prompt wrapper.

**Recommendation:** Add a fifth row to the table:

| **Lifecycle & Memory** | Session state, long-term memory, and continuity across contexts |

---

## Finding 4 — "MCP Servers" Describes a Protocol, Not a Harness Function

**Problem:** The MCP Servers row describes *connectivity* (connections to external tools, services, and data sources) but a harness layer should describe *function* (what the harness does with those connections).

The Salesforce definition of tool orchestration is more precise: intercept the model's tool request → validate permissions → execute in a sandboxed environment → sanitize output → return refined result to the model. MCP is the transport protocol that enables step three. Listing the protocol as the layer obscures the orchestration logic that actually makes tools reliable.

**Recommendation:** Rename and reframe the row:

| **Tool Orchestration** | Intercept, validate, execute, and sanitize tool calls via MCP and other integrations |

---

## Finding 5 — The "Personal" Dimension Is Never Stated

**Problem:** The definition could describe any enterprise harness (LangGraph Cloud, Vertex AI Agent Engine, Agentforce). Nothing in the definition answers: *what makes a personal cognitive harness different?*

The repo header calls this *personal agentic infrastructure* but the definition section never articulates the distinction:
- It persists across your tools, sessions, and workspaces — not a project.
- It is swappable across runtimes (Copilot, Claude, Gemini) — not tied to one vendor.
- It encodes *your* workflows, conventions, and context — not a team's.

**Recommendation:** Add one sentence after the table that makes the personal scope explicit. Example:

> Unlike enterprise orchestration platforms, a personal cognitive harness is runtime-agnostic and operator-owned — it travels with you across tools, sessions, and projects.

---

## Finding 6 — "Guardrails" Row Is Generic

**Problem:** "Boundaries, human-in-the-loop checkpoints, and safety policies" applies equally to any enterprise AI governance document. What makes cognitive guardrails distinct?

Specific, differentiating examples from industry sources include: prompt injection defense, retry budgets, autonomy-level controls (draft vs. send vs. delete), hallucination thresholds per tool, and interruptibility — the ability to gracefully halt an agent mid-task.

**Recommendation:** Tighten the Guardrails row description:

| **Guardrails** | Autonomy limits, retry budgets, injection defenses, and human approval checkpoints for high-risk actions |

---

## Finding 7 — Minor Language Issues

| Location | Current | Issue | Suggested Fix |
|---|---|---|---|
| Opening sentence | "the harness provides everything else" | Vacuous — "else" does no work | "the harness provides memory, reach, and discipline" |
| Closing sentence | "The distinction matters:" | Throat-clear, adds no information | Delete it; open with the consequential claim |
| Closing sentence | "will drift" | Unspecified — drift from what? | "will drift from its goal, hallucinate tool calls, or lose context" |

---

## Revised Table (Suggested)

| Layer | Responsibility |
|---|---|
| **Tool Orchestration** | Intercept, validate, execute, and sanitize tool calls via MCP and other integrations |
| **Context Engineering** | Curated prompts, rules, skills, and memory that keep the model focused and informed |
| **Guardrails** | Autonomy limits, retry budgets, injection defenses, and human approval checkpoints |
| **Lifecycle & Memory** | Session state, long-term memory, and continuity across contexts and runtimes |

---

## References Consulted

- Salesforce — [Agent Harness: The Infrastructure for Reliable AI](https://www.salesforce.com/agentforce/ai-agents/agent-harness/)
- Lilian Weng — [LLM Powered Autonomous Agents](https://lilianweng.github.io/posts/2023-06-23-agent/)
- IBM Think — [What are AI agents?](https://www.ibm.com/think/topics/ai-agents)
- HuggingFace smolagents — [What are agents?](https://huggingface.co/docs/smolagents/conceptual_guides/intro_agents)
- OpenAI — [Practices for Governing Agentic AI Systems](https://openai.com/index/practices-for-governing-agentic-ai-systems/)
- agentskills.io — [Specification](https://agentskills.io/specification)
