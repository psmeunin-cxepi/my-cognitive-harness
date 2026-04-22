# Configuration Best Practices — Agent Card Audit

**Source:** `CXEPI/configbp-ai` @ `a2a_server/config/agent_card.py` (commit `c31e5fb`)
**Original card:** [agent_card.original.py](agent_card.original.py)
**Fixed card:** [agent_card.fixed.py](agent_card.fixed.py)

The Configuration Best Practices agent is the agent whose card directly caused the CXP-28833 routing bug. The primary fix (removing presentation-qualifier tags `overview` and `summary`) is documented in the root cause section of [CXP-28833-analysis.md](CXP-28833-analysis.md). The findings below are additional routing-quality issues discovered during the full audit.

---

## Finding CBP-1 — `AgentCard.description` Enumerates Skills

The current `AgentCard.description` for `Assessments – Configuration` restates each of the four skills inline ("Capabilities span four skills: (1) … (2) … (3) … (4) …"). This is not required by the A2A protocol — `AgentSkill` already carries its own `description`, `tags`, and `examples`, and the router consumes them separately.

Per the agent-card-auditor heuristics, an `AgentCard.description` should answer two questions in one or two sentences:

- What does this agent do well?
- Where should requests stop being routed here?

Long inventories of every skill push the description into the anti-pattern the auditor flags ("long inventories of everything the agent might do"), and they dilute the discriminating signal a router uses to pick *between* agents.

### Suggested rewrite

```
Analyzes a customer's network configuration against Cisco best practice rules
and reports failures, severity, impacted assets, and remediation. Route here
for questions about configuration compliance posture, rule deviations, and
corrective actions — not for assessment rating/health scores or non-configuration
assessments (Security Advisory, Hardening, Field Notices).
```

This is applied in [agent_card.fixed.py](agent_card.fixed.py) alongside the tag fix.

> **Change classification:** mutating, not breaking.

---

## Finding CBP-2 — Skill ID and Name Reuse "Summary"

The same "summary" / "overview" framing that polluted the tag list is also present in the skill's `id` (`assessments-configuration-summary`) and human-display `name` (`Assessments Configuration Summary`). "Summary" is a presentation qualifier, not a domain identifier — the same critique that drove the tag fix.

**Why it matters less than the tags:**

- The router system prompt format renders skills as `**<id>** [tags]: description`. The `name` field does not appear to be in the router context, so it has no direct routing impact.
- The `id` itself is in the router context, but it sits next to the (now-clean) tag list and description, which carry the discriminating signal.

**Why it still matters:**

- The `id` is what the LLM emits as `agent_skill` and what every downstream consumer (handlers, eval datasets, semantic-router vector index) keys on. Leaving "summary" in the ID keeps the misleading framing in the system's vocabulary.

**Why it is out of scope for the cards-only fix:**

- Renaming the `id` is a coordinated, breaking change across the agent's request handler, the semantic router's agent registry / vector index, eval datasets, and any logged analytics. It cannot land in an agent-card-only PR.

**Cleaner version (applied in [agent_card.fixed.py](agent_card.fixed.py) for reference, but requires coordinated rollout before merging upstream):**

| Field | Original | Cleaner |
|---|---|---|
| `id` | `assessments-configuration-summary` | `configuration-assessment-posture` |
| `name` | `Assessments Configuration Summary` | `Configuration Assessment Posture` |

> **Action:** Treat the rename as a follow-up. Land the tag + description fix first (no breaking change). Schedule the ID rename as a separate, coordinated change.

---

## Finding CBP-3 — Skill IDs Are Not Self-Anchored to the Agent Domain

The remaining three skill IDs in this card (`asset-scope-analysis`, `rule-analysis`, `signature-asset-insights`) carry no reference to "Configuration" or "Configuration Assessment". They rely entirely on the parent `AgentCard.name` for domain context.

**Why this matters:**

- The router emits `agent_skill` as a flat string with no agent qualifier (e.g. `"asset-scope-analysis"`). Logs, eval datasets, and downstream consumers see the bare ID.
- Skill IDs effectively live in a **global namespace** across the agent fleet. Future agents (Security Advisory, Hardening, Field Notices) could reasonably introduce their own asset-scoped or rule-centric skills — collisions are likely, and the LLM's mental model of overlapping IDs is exactly the kind of confusion that produced the original CXP-28833 bug.
- The `asset-scope-analysis` tag list already includes `criticality`, `lifecycle`, `coverage`, `contract` — core domain terms for the **Assets (General)** and **Asset Criticality** agents. A router scanning tags could plausibly land here for a question that belongs elsewhere.

**Cleaner naming (applied in [agent_card.fixed.py](agent_card.fixed.py)):**

| Original `id` | Cleaner `id` | Cleaner `name` |
|---|---|---|
| `asset-scope-analysis` | `configuration-failures-by-asset` | `Configuration Failures by Asset` |
| `rule-analysis` | `configuration-rule-impact` | `Configuration Rule Impact` |
| `signature-asset-insights` | `signature-configuration-insights` | `Signature Configuration Insights` |

**Naming convention note (`signature-configuration-insights`):** This skill does not start with the `configuration-` prefix used by the other three. The leading token is `signature` (the customer tier), with `configuration` as the second token. This is a deliberate trade-off — `signature` is the more discriminating token (only this skill is Signature-gated) and putting it first makes the gating immediately visible in logs, eval datasets, and the router prompt. The auditor heuristic ("starts with a domain prefix that uniquely identifies the agent's domain") is satisfied by `signature-configuration-` as a compound prefix. The strict-rule alternative would be `configuration-signature-insights`. Keeping the current form for now; revisit if the team adopts a strict "first token = agent domain" convention.

**Same caveat as Finding CBP-2:** these `id` renames are **breaking changes** with cross-system blast radius (handlers, eval datasets, semantic-router vector index, analytics). They are reflected in the fixed card as a reference target, not as something that can land in an agent-card-only PR. Recommended rollout: ship the tag + description fix first; schedule all `id` renames as a single coordinated change.

---

## Finding CBP-4 — Skill Descriptions Are Not Self-Anchored to the Configuration Domain

The skill descriptions rely on the parent `AgentCard.name` ("Assessments – Configuration") for context. Most sentences in each description, read in isolation, do not contain the word "configuration" or any other Configuration-domain anchor.

**Why this matters:**

- An LLM router sees the parent context in the system prompt and resolves bare nouns (`failures`, `rules`, `assessment`) against it correctly. So this is not the proximate cause of CXP-28833.
- An **embedding-based / vector-search router** typically embeds the skill description (sometimes plus tags) as a single chunk **without** the parent agent name. Bare phrasing like "how many failures were detected" embeds similarly to the equivalent sentence in any sibling assessment agent (Security Advisory, Hardening, Field Notices) — the discriminating signal is missing from the vector.
- Even shared-domain vocabulary like "best practice rules" fails the substitute test, because Security Hardening also describes itself as "best practices". The qualifier must live on the noun phrase, not in the parent context.

### Substitute Test Verdicts (`configuration-assessment-posture` description, original)

Apply the substitute test: read each sentence in isolation. A sentence is under-anchored if it contains no domain-specific noun at all, or only vocabulary shared with sibling agents (e.g. "best practice rules" used by both Configuration and Hardening). A sentence that names the agent's own domain as the operative word is anchored — the fact that the grammatical slot could accept another noun does not make it under-anchored.

| Sentence fragment | Verdict |
|---|---|
| "how the customer's network configuration is doing" | OK — "configuration" is present and operative |
| "how many assets were assessed" | under-anchored |
| "how many best practice rules were evaluated" | under-anchored (shared with Hardening) |
| "how many failures were detected" | under-anchored |
| "how they break down by severity" | under-anchored |
| "execution summaries, pass/fail rates and percentages" | under-anchored |
| "technology and category breakdowns" | under-anchored |
| "top impacted assets ranked by failure count" | under-anchored |
| "the rules with the most failures" | under-anchored |
| "common configuration deviations across the network" | OK |
| "severity trends, overall assessment posture" | under-anchored ("assessment posture" is generic across all assessments) |
| "breakdowns by severity, category, and software type" | under-anchored |

The same pattern applies to the other three skill descriptions (`configuration-failures-by-asset`, `configuration-rule-impact`, `signature-configuration-insights`) — most sentences use bare nouns inherited from the parent context.

### Fix

The fix is in-place qualification, not rewriting:

- `failures` → `configuration failures`
- `rules` → `configuration rules`
- `best practice rules` → `configuration best practice rules`
- `assessment` → `configuration assessment`
- `severity` (when standalone) → `configuration severity`
- `corrective actions` → `configuration corrective actions`

Length increases by ~10–15% but every sentence now passes the substitute test.

Applied to all four skill descriptions in [agent_card.fixed.py](agent_card.fixed.py).

> **Change classification (per the auditor's Change Impact heuristic):** mutating, not breaking. The descriptions can ship in the agent-card-only PR alongside the tag and `AgentCard.description` fixes, without coordination with downstream consumers.

---

## Summary of Changes (Configuration Best Practices)

| Finding | Field | Change Type | Can ship independently? |
|---|---|---|---|
| Primary (root cause) | `skills[0].tags` | Mutating | Yes |
| CBP-1 | `AgentCard.description` | Mutating | Yes |
| CBP-2 | `skills[0].id`, `skills[0].name` | Breaking | No — coordinated rollout |
| CBP-3 | `skills[1-3].id`, `skills[1-3].name` | Breaking | No — coordinated rollout |
| CBP-4 | `skills[*].description` | Mutating | Yes |

**Recommended rollout:** Ship primary fix + CBP-1 + CBP-4 in a single agent-card PR (all mutating). Schedule CBP-2 + CBP-3 (ID renames) as a follow-up coordinated change.
