# CXP-28833 — Semantic Router Routing Inconsistency

## Traces

| | Trace 1 | Trace 2 |
|---|---|---|
| **LangSmith ID** | `019d9aff-6156-7e31-944d-5c9cfe847ae7` | `019d9afa-68ab-7c73-bbdb-eaa93c87f30e` |
| **Prompt** | "Give me an overview of my last assessment results" | same |
| **Result** | `assessments-configuration-summary` | `assessment-rating-analysis-query` |
| **Input tokens** | 6,839 | 7,002 (+163) |

### Why each decision was made

| | Trace 1 | Trace 2 |
|---|---|---|
| **Page context** | None | `PREFERRED_AGENTS: [Assessment Rating]` |
| **Routing driver** | Keyword match on skill tags — **wrong, should have clarified** | Page context preference — correctly routes to Assessment Rating |
| **Correct behaviour?** | No — ambiguity should have been triggered | Yes |

The 163-token difference is the `## Page Context Preference` block injected in Trace 2. With it, the system prompt instructs the LLM to route to Assessment Rating if the question can reasonably be handled there, which it can. **Trace 1 is the bug** — with no page context and two plausible agents, it should have triggered clarification but instead picked Configuration based on tag matching.

> **Note on `PREFERRED_AGENTS` weight:** The page context instruction carries near-override weight. The prompt sets a very high bar to ignore it — "ZERO relevance" to the preferred agent's domain. Any reasonable fit is sufficient to route there, bypassing ambiguity handling entirely. This means the same vague question will produce different routes depending solely on which page the user is on, which is by design but important to keep in mind when debugging routing decisions.

---

## Real Problem — Ambiguity Handling Failure in Trace 1

**Trace 1 is the problematic trace.** With no page context and no conversation history, `"Give me an overview of my last assessment results"` has at least **two plausible agents**:
- **Assessments – Configuration** — handles assessment-wide summaries and overviews
- **Assessment Rating** — covers rating analysis across all assessment types (Configuration, Security Advisory, Security Hardening, Field Notices)

Per the uncertainty handling rules, 2+ plausible agents should trigger `agent_skill: "clarify"`. Instead, Trace 1 routes directly to Configuration.

### Why: Over-weighted format tags on `assessments-configuration-summary`

The skill tag list for `assessments-configuration-summary` includes:

```
[assessment, summary, severity, overview, distribution, metrics, ...]
```

The words **"overview"** and **"summary"** are **presentation qualifiers**, not domain identifiers. They describe *how* the user wants the answer (high-level), not *which domain* they're asking about. Any assessment agent could answer an "overview" question.

By listing them as skill tags, `assessments-configuration-summary` effectively claims ownership of every vague assessment question that uses natural summary language — pulling the LLM away from the ambiguity check and straight into a (false) confident match.

### Possible fix

Remove `overview` and `summary` from the `assessments-configuration-summary` tag list. Replace them with domain-specific terms that uniquely identify Configuration assessment scope, for example:

```
[configuration-assessment, best-practice-rules, failures, pass-fail, severity-distribution, configuration-posture]
```

This ensures the tag list discriminates between agents rather than matching on generic language. Without a spuriously strong tag match, the LLM will correctly see two plausible agents and trigger clarification, which is the intended behaviour for this question without page context.
