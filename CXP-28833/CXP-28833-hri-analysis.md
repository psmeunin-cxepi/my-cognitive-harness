# Assessment Rating — Agent Card Audit

**Source:** `CXEPI/cxp-health-risk-insights-ai` @ `a2a_server/config/agent_card.py` (commit `0377244`)
**Original card:** [assessment_rating_agent_card.original.py](assessment_rating_agent_card.original.py)
**Fixed card:** [assessment_rating_agent_card.fixed.py](assessment_rating_agent_card.fixed.py)

The Assessment Rating agent is the second agent involved in CXP-28833. In Trace 2, the router correctly routes to `assessment-rating-analysis-query` thanks to page context (`PREFERRED_AGENTS: [Assessment Rating]`). The card itself was not the proximate cause of the bug, but auditing it reveals several routing-quality issues that would surface the moment page context is absent.

---

## Finding AR-1 — `AgentCard.description` Is Under-Specified and Has No Routing Boundary

**Original:**
> `"AI agent specializing in analysing rating for each Assessment app like Security Advisory, Security Hardening, Configuration, Field notices etc."`

**Issues:**

- Does not explain what "rating" means. A composite health score that aggregates findings across assessment types is a specific, differentiable concept — but the description hides it behind the bare word "rating".
- Claims to cover "each Assessment app" without saying what unique value it adds on top of those apps. A router comparing this against the Configuration, Security Advisory, and Security Hardening agents sees maximum overlap.
- "etc." gives the router no boundary signal.
- "AI agent specializing in" is filler — every card is an AI agent.
- No routing boundary (where to route, where *not* to route).

**Suggested rewrite (applied in [assessment_rating_agent_card.fixed.py](assessment_rating_agent_card.fixed.py)):**

```
Computes and explains composite assessment ratings (Critical, High, Medium, Low)
that aggregate findings across all assessment types — Security Advisory, Security
Hardening, Configuration, and Field Notices — into a single per-asset or per-network
health score. Route here for questions about why an asset received a specific rating,
what factors drive the rating, how ratings compare across assets, and which rated
assets to prioritize — not for the underlying assessment findings themselves (route
to the relevant assessment agent) or for Place-in-Network criticality rankings
(route to Asset Criticality).
```

> **Change classification:** mutating, not breaking.

---

## Finding AR-2 — Primary Skill ID Contains Presentation Qualifier `-query`

**Original ID:** `assessment-rating-analysis-query`

The suffix `-query` is a presentation qualifier — it describes the interaction mode (a query), not the domain. Same pattern as the `-summary` suffix caught in the Configuration card (Tertiary Finding).

**Suggested rename:** `assessment-rating-analysis`

> **Change classification:** breaking. Requires coordinated rollout (handlers, eval datasets, vector index, analytics).

---

## Finding AR-3 — Primary Skill Description Is Under-Anchored

**Original:**
> `"Comprehensive Assessment rating analysis and criticality breakdown for each asset or network"`

Apply the substitute test: replace "Assessment rating" with any sibling domain noun and the sentence still parses:

| Substitution | Parses? |
|---|---|
| "Comprehensive Security Advisory analysis and criticality breakdown for each asset or network" | Yes |
| "Comprehensive Configuration analysis and criticality breakdown for each asset or network" | Yes |

The discriminating concept — *a composite score that aggregates findings from multiple assessment types* — is completely absent.

**Suggested rewrite:**

```
Analyzes composite assessment ratings that combine findings from Security Advisory,
Security Hardening, Configuration, and Field Notice assessments into a single
per-asset health score. Explains why an asset received a Critical, High, Medium, or
Low rating, identifies which assessment categories contribute most to the rating,
and ranks rated assets by priority for remediation.
```

> **Change classification:** mutating, not breaking.

---

## Finding AR-4 — `criticality-breakdown` Tag Collides with Asset Criticality Agent

**Tag:** `criticality-breakdown`

The **Asset Criticality** agent has tags `criticality`, `risk-ranking`, `prioritization`, and `pin`. A user asking about "criticality breakdown" could mean either:

- Assessment Rating's composite score breakdown by severity category, or
- Asset Criticality's Place-in-Network importance ranking.

Sharing the `criticality` root between two agents with different concepts of "criticality" is a direct collision risk. The Configuration card audit already flagged tag overlap as a routing hazard.

**Suggested replacement:** Drop `criticality-breakdown`. The composite-score concept is better expressed by `composite-rating` and `rating-explanation` (applied in the fixed card).

> **Change classification:** mutating, not breaking.

---

## Finding AR-5 — Tag Set Has Low Routing Value

**Original tags:** `["health-rating", "assessment-rating-analysis", "rating-analysis", "criticality-breakdown", "assessment-rating-categorization"]`

| Tag | Issue |
|---|---|
| `health-rating` | Good — unique domain anchor |
| `assessment-rating-analysis` | Duplicates the skill ID. Low incremental routing value |
| `rating-analysis` | Drops the `assessment-` prefix, becoming generic |
| `criticality-breakdown` | Collides with Asset Criticality (see AR-4) |
| `assessment-rating-categorization` | Same root as `assessment-rating-analysis`, low incremental value |

Missing: task-verb tags (what does this agent *do*?) and the core concept of composite/cross-assessment scoring.

**Suggested replacement:**

```python
tags=[
    "assessment-rating",
    "health-score",
    "composite-rating",
    "rating-explanation",
    "rating-prioritization",
    "cross-assessment",
]
```

- `assessment-rating` — domain anchor, matches the agent name.
- `health-score` — the artifact this agent produces.
- `composite-rating` — signals aggregation across assessment types.
- `rating-explanation` — task verb: explains *why* a rating was assigned.
- `rating-prioritization` — task verb: ranks assets for action.
- `cross-assessment` — distinguishes from single-assessment agents.

> **Change classification:** mutating, not breaking.

---

## Finding AR-6 — Capabilities Skill Embeds Domain Claims That Belong in Primary Skill

**`assessment-rating-capabilities` description:**
> `"…including asset risk categorization, risk score breakdowns, and remediation prioritization."`

The phrases "asset risk categorization", "risk score breakdowns", and "remediation prioritization" are domain-task descriptions, not meta-information about the agent's help function. A router may select this skill for a domain question because it has richer domain language than the primary skill.

**Fix:** Move the domain claims into the primary skill description (done in the fixed card). Trim the capabilities skill to describe only what questions a user can ask, without restating domain scope.

Additionally, the capabilities skill says "network security risks" — but this agent spans all assessment types, not just security. This phrase anchors routing to the wrong sibling (Security Advisory / Security Hardening).

> **Change classification:** mutating, not breaking.

---

## Finding AR-7 — Capabilities Skill Tags Are Internal Labels

**Tags:** `["assessment-rating-capabilities", "assessment-rating-welcome-message"]`

No user searches for "welcome-message". These are internal identifiers, not user-intent keywords.

**Suggested replacement:** `["assessment-rating-capabilities", "assessment-rating-help"]`

This is a minor finding — the capabilities skill exists to handle meta-questions, and internal-sounding tags are less harmful for a meta-skill than for a domain skill.

> **Change classification:** mutating, not breaking.

---

## Summary of Changes (Assessment Rating)

| Finding | Field | Change Type | Can ship independently? |
|---|---|---|---|
| AR-1 | `AgentCard.description` | Mutating | Yes |
| AR-2 | `skills[0].id` | Breaking | No — coordinated rollout |
| AR-3 | `skills[0].description` | Mutating | Yes |
| AR-4 | `skills[0].tags` | Mutating | Yes |
| AR-5 | `skills[0].tags` | Mutating | Yes (same PR as AR-4) |
| AR-6 | `skills[1].description` | Mutating | Yes |
| AR-7 | `skills[1].tags` | Mutating | Yes |

**Recommended rollout:** Ship AR-1, AR-3–AR-7 in a single agent-card PR (all mutating). Schedule AR-2 (ID rename) as a follow-up coordinated change.
