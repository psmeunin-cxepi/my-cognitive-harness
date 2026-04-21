# CXP-28833 — Semantic Router Routing Inconsistency

## Scope and Limits — Page Context Is the Primary Routing Anchor

Cisco IQ agents are surfaced through a web UI. A user on a domain-specific page (e.g. Configuration Best Practices) clicks "Ask AI" and may type a prompt with no domain anchor in the text itself: *"Which rules failed for this asset?"*. Read in isolation, that prompt is plausible for Configuration, Security Hardening, and Security Advisory.

The router does not (and cannot) resolve this from the prompt alone. The architecture relies on three layers of disambiguation, in priority order:

| Layer | Owner | Mechanism | Reliability |
|---|---|---|---|
| 1. UI page context | Cisco IQ frontend / A2A request envelope | `PREFERRED_AGENTS: [...]` block injected into the user message; near-override weight in the router prompt | Required; any path that bypasses the UI (programmatic API, A2A delegation, future surfaces) loses this anchor |
| 2. Conversation context | Router's Follow-Up Detection | Anaphora and entity references resolved against the last 2 agent turns | Only works after the first turn |
| 3. Agent card content (this work) | Agent owner | Tags, descriptions, examples, IDs that discriminate the agent from siblings | Last line of defense for first-turn prompts with no page context |

This work fixes layer 3. **It is necessary but not sufficient.** Layer 3 alone cannot rescue every bare prompt — and trying to make every skill match every shorthand prompt re-creates the original CXP-28833 bug (over-broad tags pulling the LLM into a false confident match instead of triggering clarification). The correct behaviour for an under-specified prompt with no page context and no conversation history is to **clarify**, not to guess.

**Implications for related teams:**

- **Cisco IQ frontend** — page context injection should be a contract requirement for any AI request originating from a domain-specific page, not best-effort. Any UI change that surfaces the "Ask AI" entry point must include the page context wiring.
- **Semantic router** — first-turn anaphoric prompts (`this`, `that`, `these`) without page context are a distinct failure mode from the multi-agent ambiguity already covered by Uncertainty Handling. Worth confirming the router's clarification logic catches them.
- **Eval harness** — coverage gap: vague-prompt evals typically either always-inject or never-inject page context. Same prompt set should be run in both modes to catch routing regressions on either side.

---

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

---

## Secondary Finding — `AgentCard.description` Enumerates Skills

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

---

## Tertiary Finding — Skill ID and Name Reuse "Summary"

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

## Quaternary Finding — Skill IDs Are Not Self-Anchored to the Agent Domain

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

**Same caveat as the Tertiary Finding:** these `id` renames are **breaking changes** with cross-system blast radius (handlers, eval datasets, semantic-router vector index, analytics). They are reflected in the fixed card as a reference target, not as something that can land in an agent-card-only PR. Recommended rollout: ship the tag + description fix first; schedule all `id` renames as a single coordinated change.

---

## Quinary Finding — Skill Descriptions Are Not Self-Anchored to the Configuration Domain

The skill descriptions rely on the parent `AgentCard.name` ("Assessments – Configuration") for context. Most sentences in each description, read in isolation, do not contain the word "configuration" or any other Configuration-domain anchor.

**Why this matters:**

- An LLM router sees the parent context in the system prompt and resolves bare nouns (`failures`, `rules`, `assessment`) against it correctly. So this is not the proximate cause of CXP-28833.
- An **embedding-based / vector-search router** typically embeds the skill description (sometimes plus tags) as a single chunk **without** the parent agent name. Bare phrasing like "how many failures were detected" embeds similarly to the equivalent sentence in any sibling assessment agent (Security Advisory, Hardening, Field Notices) — the discriminating signal is missing from the vector.
- Even shared-domain vocabulary like "best practice rules" fails the substitute test, because Security Hardening also describes itself as "best practices". The qualifier must live on the noun phrase, not in the parent context.

### Substitute Test Verdicts (`configuration-assessment-posture` description, original)

Apply the substitute test: read each sentence in isolation and try replacing with a sibling agent's domain noun (`security`, `hardening`, `field notice`). If it still parses, it is under-anchored.

| Sentence fragment | Verdict |
|---|---|
| "how the customer's network configuration is doing" | OK (anchored on "configuration") |
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
