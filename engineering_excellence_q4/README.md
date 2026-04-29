# AI Agent Engineering Excellence — Q4 FY (May–July 2026)

| Field | Value |
|---|---|
| **Owners** | TBD |
| **Horizon** | Q4 FY — May 1 to July 31, 2026 |
| **Type** | Engineering-driven (not PM/JIRA feature requests) |
| **Status** | Planning |

---

## Why

### The Problem

Each Cisco IQ domain agent was built to solve a specific product problem — context was team-local, timelines were independent, and cross-agent standardization was not prioritized. The result is:

- **Duplicated implementations** of retrieval, MCP tooling, context parsing, and prompt patterns — multiplying maintenance cost for every change
- **Behavioral drift** — agents handle the same situations (context switching, deictic resolution, portfolio-wide queries) in different and sometimes incorrect ways, as documented in [RFC-001](../agent_behavioural_spec/rfc_context_switch.md)
- **No shared behavioral contract** — there is no normative specification of what agents are required to do, making it impossible to audit compliance, write cross-agent evals, or onboard agents to a shared standard
- **Steep onboarding cost** — a developer moving between agents must re-learn each codebase's bespoke patterns

### The Complication

Without intervention, the divergence compounds:

- Every new feature requires parallel implementation across all agents — slowing delivery and increasing defect surface
- Behavioral bugs discovered in one agent (e.g., context switch failures) must be diagnosed and fixed independently in each codebase, with no guarantee of consistent resolution
- Agent-to-agent quality gaps widen as teams make local optimizations that never propagate
- Onboarding new engineers or standing up new agents becomes progressively harder as bespoke patterns accumulate

---

## What

Q4 is a window to invest in the platform before the next major feature cycle. Five workstreams targeting the key areas where the Cisco IQ domain agents have diverged: graph architecture, RAG retrieval, data access, deployment, and behavioral standards. Each workstream will produce a landscape analysis, a target specification, and an (incremental) migration path.

The agents in scope are: **Config Best Practices (CBP)**, **Health Risk Insights (HRI)**, **Security Advisory**, **Security Hardening**, and **LDOS**.

### Workstreams

| Workstream | Summary |
|---|---|
| **EE-1 — Agent Graph & State Architecture** | Define standard LangGraph patterns (node structure, state schema, checkpointer, memory model, error handling) for all agents |
| **EE-2 — Common RAG Integration** | Converge on a single RAG integration pattern (shared client, ingestion pipeline, and standardized retrieval options per document category) used by all agents |
| **EE-3 — Common Data & MCP Platform** | Shared MCP tools (data access, Trino queries, ID resolution), centralized data schema registry, and standardized text-to-SQL patterns |
| **EE-4 — Deployment & Observability Platform** | Adopt LangSmith as the unified platform for agent deployment, tracing, and evaluation; standardize CI/CD pipelines, environment config, and release processes |
| **EE-5 — Agent Behavioural Spec** | Define and maintain normative behavioral specifications (RFCs) for all agents; establish compliance tooling and eval coverage |

---

## How

### Governance

- Engineering-owned: prioritized by the engineering team, not gated on PM approval
- The **Engineering Excellence leads** are accountable for the initiative and its targets. They hold ultimate authority and decision rights across all workstreams
- Each workstream has a designated lead who is responsible for delivery and a target completion date within Q4
- Workstream leads are the gatekeepers for new requirements — they decide whether a proposal is accepted and whether it is scoped for Q4 or deferred
- New requirements are collected by the workstream leads with input from their respective agent teams. Any team member can propose work, but acceptance and prioritisation are decided jointly by the workstream lead and the Engineering Excellence leads
- Progress tracked in this directory; one subdirectory per workstream
- **PM consultation required** when changes under any workstream have external impact on agent behaviour or user-facing responses (e.g., answer quality, data exposure, conversational flow). Such changes must be reviewed with Product Management before rollout

### Tracking

All work is tracked under EPIC [CXP-29377](https://cisco-cxe.atlassian.net/browse/CXP-29377). The board uses swimlanes per workstream, driven by JIRA labels.

| Label | Scope |
|---|---|
| `ai-agent-engineering-excellence` | All tickets in the initiative |
| `ee1-agent-arch` | EE-1 — Agent Graph & State Architecture |
| `ee2-rag` | EE-2 — Common RAG Integration |
| `ee3-data-mcp` | EE-3 — Common Data & MCP Platform |
| `ee4-depl-obs` | EE-4 — Deployment & Observability Platform |
| `ee5-agent-spec` | EE-5 — Agent Behavioural Spec |

Every ticket must carry the general label **and** its workstream label.

### Approach

1. **Collect requirements** — assess what has already been documented and researched (landscape analyses, cross-agent comparisons, RFCs), and gather new requirements from workstream leads and agent teams
2. **Triage and scope** — for each item, decide whether it is accepted for Q4 or deferred to a later cycle
3. **Landscape first** — for accepted items where agents already have implementations, document what each agent currently does before proposing standards (see [context_switch_spec.md](../agent_behavioural_spec/context_switch_spec.md) as the model). For net-new capabilities, skip directly to specification
4. **Specify and build** — where existing implementations exist, identify the strongest one, generalize it, and adopt it as the standard. For net-new capabilities, design from scratch. Each workstream documents the target standard, migration guidance, and open questions before any code changes
5. **Behavioural spec** — any work across any workstream that impacts agent behaviour must be documented as a formal RFC under EE-5

### Out of Scope for Q4

- New product features
- ....

---

## References

- [RFC-001: Context Switch Behavior Specification](../agent_behavioural_spec/rfc_context_switch.md)
- [Cross-Agent Context Handling Landscape](../agent_behavioural_spec/context_switch_spec.md)
- [Step Updates — Cross-Agent Analysis](step-updates-cross-agent-analysis.md)
- [Conversation History — Cross-Agent Analysis](conversation-history-cross-agent-analysis.md)
