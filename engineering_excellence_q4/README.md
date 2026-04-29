# AI Agent Engineering Excellence — Q4 FY (May–July 2026)

| Field | Value |
|---|---|
| **Owners** | TBD |
| **Horizon** | Q4 FY — May 1 to July 31, 2026 |
| **Type** | Engineering-driven (not PM/JIRA feature requests) |
| **Status** | Planning |

---

## What

A set of engineering-driven initiatives to standardize agent architecture, reduce per-agent divergence, and build shared infrastructure across the Cisco IQ domain agent portfolio.

The agents in scope are: **Config Best Practices (CBP)**, **Health Risk Insights (HRI)**, **Security Advisory**, **Security Hardening**, and **LDOS**. Each was built independently, resulting in parallel implementations of the same concerns: RAG retrieval, MCP tooling, context handling, state management, and observability.

### Workstreams

| Workstream | Summary |
|---|---|
| **EE-1 — Agent Graph & State Architecture** | Define standard LangGraph patterns (node structure, state schema, checkpointer, memory model, error handling) for all agents |
| **EE-2 — Common RAG Integration** | Converge on a single RAG integration pattern (shared client, ingestion pipeline, and standardized retrieval options per document category) used by all agents |
| **EE-3 — Common Data & MCP Platform** | Shared MCP tools (data access, Trino queries, ID resolution), centralized data schema registry, and standardized text-to-SQL patterns |
| **EE-4 — Deployment & Observability Platform** | Adopt LangSmith as the unified platform for agent deployment, tracing, and evaluation; standardize CI/CD pipelines, environment config, and release processes |
| **EE-5 — Agent Behavioural Spec** | Define and maintain normative behavioral specifications (RFCs) for all agents; establish compliance tooling and eval coverage |

---

## Why

### The Problem

Each Cisco IQ domain agent was built to solve a specific product problem — context was team-local, timelines were independent, and cross-agent standardization was not prioritized. The result is:

- **Duplicated implementations** of retrieval, MCP tooling, context parsing, and prompt patterns — multiplying maintenance cost for every change
- **Behavioral drift** — agents handle the same situations (context switching, deictic resolution, portfolio-wide queries) in different and sometimes incorrect ways, as documented in [RFC-001](../agent_behavioural_spec/rfc_context_switch.md)
- **No shared behavioral contract** — there is no normative specification of what agents are required to do, making it impossible to audit compliance, write cross-agent evals, or onboard agents to a shared standard
- **Steep onboarding cost** — a developer moving between agents must re-learn each codebase's bespoke patterns

### The Opportunity

Q4 is a window to invest in the platform before the next major feature cycle. Standardizing now means:

- New features affect one shared implementation, not six
- Behavioral fixes (e.g., context switch, RAG quality) propagate to all agents at once
- Evals can be defined once and run across all agents
- New agents can be bootstrapped from a vetted reference implementation

---

## How

### Approach

1. **Landscape first** — before proposing standards, document what each agent currently does (see [context_switch_spec.md](../agent_behavioural_spec/context_switch_spec.md) as the model for this approach)
2. **Reference implementation** — identify the strongest current implementation per concern, generalize it, and adopt it as the standard
3. **Per-workstream spec** — each workstream produces a lightweight spec (what the standard is, migration guidance, open questions) before any code changes
4. **Incremental migration** — agents migrate one workstream at a time; no "big bang" rewrites

### Governance

- Engineering-owned: prioritized by the engineering team, not gated on PM approval
- Each workstream has a designated lead and a target completion date within Q4
- Progress tracked in this directory; one subdirectory per workstream

### Out of Scope for Q4

- New product features
- ....

---

## Workstream Index

| Workstream | Directory | Lead | Status |
|---|---|---|---|
| EE-1 Agent Graph & State Architecture | `ee1_agent_architecture/` | TBD | Not started |
| EE-2 Common RAG Integration | `ee2_rag_integration/` | TBD | Not started |
| EE-3 Common Data & MCP Platform | `ee3_data_mcp/` | TBD | Not started |
| EE-4 Deployment & Observability Platform | `ee4_deploy_observability/` | TBD | Not started |
| EE-5 Agent Behavioural Spec | `ee5_agent_behaviour/` | TBD | Not started |

---

## References

- [RFC-001: Context Switch Behavior Specification](../agent_behavioural_spec/rfc_context_switch.md)
- [Cross-Agent Context Handling Landscape](../agent_behavioural_spec/context_switch_spec.md)
- [Step Updates — Cross-Agent Analysis](step-updates-cross-agent-analysis.md)
- [Conversation History — Cross-Agent Analysis](conversation-history-cross-agent-analysis.md)
