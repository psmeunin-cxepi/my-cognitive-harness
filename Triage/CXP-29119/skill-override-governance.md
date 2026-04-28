> **Agent:** _cross-agent (Semantic Router)_
> **Repo:** _cvi_ai_shared_
> **Jira:** [CXP-29119](https://cisco-cxe.atlassian.net/browse/CXP-29119)

# Skill Override Layer — Governance Policy
## CXP-29119 | cvi_ai_shared PR #432
**Status:** Draft v0.1 — April 19, 2026
**Owner:** SR Team

---

## 1. Context

The Semantic Router (SR) is a central orchestrator that routes user questions to agents based on skill descriptions it doesn't own. Agent teams write those descriptions for their own purposes — their own apps, their own users. When agent cards change, routing can break silently. Fixing it today requires a code change through a pipeline and cross-team coordination that can take weeks.

The skill override layer (PR #432) gives the SR team a local control surface: the ability to override what the router "sees" for a skill description — without touching the upstream agent card, without asking permission, and without waiting. This document defines the governance rules under which that mechanism operates.

---

## 2. Guiding Principles

- **Governance is enforced, not advisory.** A strict policy and process governs the creation of overrides and the compliance of agent cards. The SR team acts as the enforcing authority — non-compliant agents are warned and, if unresolved, removed from routing. Participation in SR routing is a privilege, not a right.
- **Overrides are temporary workarounds, not permanent fixes.** The root cause is always one or more agent cards. An override buys time; fixing the card(s) is the expected outcome.
- **Quality is a hard gate, for both sides.** An agent does not enter SR routing until its card passes audit and evals. An override is not deployed until SR routing evals confirm it improves routing. Neither is a negotiation.
- **The SR team does not own routing alone.** Agent teams are responsible for their card quality. The SR team is responsible for routing accuracy and for documenting every override and its rationale.
- **External storage enables fast response.** Override data lives outside the deployment git repo so routing fixes can be applied in minutes without a redeploy, and can be queried via MCP for Agent Card Audits.

---

## 3. Minimum Requirements for Agent Cards

Before the SR accepts an agent card for routing, the agent team must satisfy the following requirements.

### 3.1 Requirements

#### Req 1 — Agent Card Audit
The agent card must have been audited using the Agent Card Audit Skill and all suggested changes implemented. The audit must include any active skill overrides as context (pulled automatically via MCP — see Section 8).

#### Req 2 — SR Routing Evals
SR routing evals must have been run and returned a positive result. Both teams share responsibility: the agent team runs evals against their card/agent; the SR team validates the results are sufficient for routing acceptance.

### 3.2 Attestation Signature

Agent teams prove compliance by adding a `cx_sr_attestation` field to their `.well-known/agent.json`:

```json
"cx_sr_attestation": {
  "audited_by": "<person or tool>",
  "audit_ref": "<link or reference to audit output>",
  "eval_run_id": "<LangSmith eval run ID>",
  "eval_result": "<pass/summary>",
  "date": "<ISO 8601 date>"
}
```

The attestation must prove the process was completed — by providing verifiable references and results — not merely declare it.

**SR fetch-time validation:** On every card fetch, the SR checks the `date` field. When the attestation is older than the agreed expiry window, the SR generates an alert and notifies the team. The card is not immediately rejected on first alert.

**Escalation if misuse is observed:** If self-attestation is found to be misused, the SR team will escalate to Option B: an SR-maintained approval registry that stores a hash of the approved card content and verifies it on every fetch. Any unapproved card change is automatically detected.

---

## 4. Onboarding — New Agents

New agents follow this sequence before being accepted into SR routing:

1. Agent team runs the Agent Card Audit Skill independently
2. Agent team runs SR routing evals independently; iterates until evals pass
   - Agent team may engage the SR team for diagnostic support — this is optional, not mandatory
   - There is no attempt limit — quality is a hard gate and an agent does not enter routing until evals pass
3. Agent team adds the `cx_sr_attestation` field to their card with references and results
4. Agent team submits their card for SR onboarding *(initiation process: TBD — Jira ticket / registration endpoint)*
5. SR team validates attestation references and eval results
6. Agent progresses through dev → stage → prod environments before going live

---

## 5. Existing Agents — Compliance Deadline

**No grandfathering.** All agents currently registered in the SR must:
- Audit their agent cards using the Agent Card Audit Skill
- Run and pass SR routing evals
- Add the `cx_sr_attestation` signature to their card

**Deadline: 30 days from the date this policy is published.**

The same two-strike escalation defined in Section 7 applies after the deadline.

---

## 6. Skill Override — Creation Process

### 6.1 When an override is created
The SR team creates an override when a routing failure is traced back to a skill description that is too vague, too broad, or missing a negative boundary — and the upstream card cannot be changed on the SR's timeline.

### 6.2 Override description quality
Override descriptions must follow a validated pattern proven to work for routing:

> **"Handles: [X]. Does NOT handle: [Y] — route those to [Z]."**

The FN override (CXP-29119) is the reference example:
> *"General Field Notice information (FN ID, summary, affected platforms). Does NOT check customer inventory or device-level impact — route those to Assets (General)."*

The Agent Card Audit Skill may optionally be applied for additional quality assurance. A character cap is not the primary control — a well-structured routing description polices itself. SR routing evals must confirm the override improves routing before deployment.

### 6.3 Pre-deployment consistency check
Before deploying any override, the deployment script must query all active overrides across all agents and check for conflicts — for example, a new override on agent A redirecting to agent B, while an existing override on agent B narrows its scope, creating a routing dead-end. If a conflict is detected, the script warns and requires explicit confirmation to proceed.

### 6.4 Multi-region deployment
The deployment script must apply the override to **all active regions in one execution**, or explicitly require a per-region confirmation flag before running. Partial region deployment is not permitted — routing behavior must be consistent across regions.

### 6.5 Override data storage
Override data is stored in MongoDB on the agent document (`skill_overrides` field). Git / config file storage is explicitly rejected — it would require a redeploy for every change, defeating the purpose of having an override mechanism. The MongoDB override data is exposed via MCP, giving agent teams and tooling (e.g. the Agent Card Audit Skill) programmatic read access to current overrides without requiring direct DB access.

### 6.6 Documentation requirement
For every override created, the SR team must document:
- What routing problem it fixes
- Which agent team(s) are involved
- The linked Jira ticket
- The expiry date and escalation status

---

## 7. Override Expiry and Escalation

Every override dict includes an expiry timestamp set by the SR team at creation time.

| Window | Default | Configurable? |
|---|---|---|
| Override expiry | 30 days | Yes — SR team may agree a different window with the agent team |

### Two-strike escalation

**First expiry — Warning**
The agent team is alerted. They have until the next expiry window to fix their card (audit + evals + new attestation) and remove the need for the override.

**Second expiry — Red card**
The agent is removed from SR routing and blocked on any subsequent card sync until the agent team proves they have fixed the routing problem (passing audit + evals → new attestation).

The SR team is responsible for monitoring expiry dates and triggering the escalation process.

---

## 8. Override Visibility

Active overrides must be accessible through two surfaces:

### MCP resource (programmatic)
Override data for any agent is queryable via MCP. This is consumed automatically by the Agent Card Audit Skill when auditing a card — an audit run without override context is considered incomplete.

### UI (human review)
A human-readable view showing all active overrides per agent, including: override text, who created it, creation date, expiry date, and linked documentation. Accessible to agent teams without requiring MongoDB access.

---

## 9. Observability — Routing Reason

Two mandatory observability requirements:

1. **Routing reason always captured:** Every SR routing trace must record why the SR chose the agent it did — the selected agent, the description it matched against, and the LLM's reasoning. This is a first-class requirement independent of overrides.

2. **Override flag:** When an override is active during routing, the LangSmith trace must additionally carry `skill_overrides_active: ["<skill_name>"]` in the trace metadata, so override impact can be isolated and analyzed at any point in time.

---

## 10. Kill Switch

Set `CVI_SKILL_OVERRIDES_ENABLED=false` to disable all overrides instantly — no code change, no deploy required. Both `_apply_skill_overrides()` and `_apply_description_override()` become no-ops.

---

## 11. Open Items

| Item | Status |
|---|---|
| Onboarding initiation process (Jira ticket / registration endpoint) | TBD |
| Attestation `date` expiry window (same as override 30-day window, or different?) | TBD |
