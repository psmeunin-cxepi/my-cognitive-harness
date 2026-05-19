> **Source:** CX IQ Semantic Router KG — Feedback & Triage subgraph
>
> **Feedback window:** 2026-05-11 — 2026-05-14
>
> **Report date:** 2026-05-19

# CX IQ — Negative Feedback & Triage Report

## Summary

14 traces received negative feedback (score 0 / thumbs-down) over a 4-day window. All 14 have been triaged and posted — none are pending. Every piece of feedback was validated as a real issue (0 rejections), resulting in 10 distinct Jira defects.

| Metric | Count |
|---|---|
| Feedback traces | 14 |
| Triaged | 14 |
| Failure categories | 7 |
| Defects filed | 10 |
| Triage acceptance rate | 100% |

---

## Feedback Volume by Date

| Date | Traces |
|---|---|
| 2026-05-11 | 2 |
| 2026-05-12 | 4 |
| 2026-05-13 | 7 |
| 2026-05-14 | 1 |

11 of 14 traces landed on May 12–13, suggesting a concentrated testing / feedback session.

---

## Routing Decision Split

| Routing Decision | Traces |
|---|---|
| `execute` (reached an agent) | 7 |
| `error` (never reached an agent) | 7 |

Half of the negative feedback comes from traces that errored before reaching any agent.

---

## Feedback by Agent (executed traces)

| Agent | Feedback Count | Avg Score |
|---|---|---|
| Assets (General) | 4 | 0.0 |
| Cases | 2 | 0.0 |
| Assessments - Security Advisories | 1 | 0.0 |

The remaining 7 traces had no agent selected (errors / guardrail blocks).

---

## Failure Category Breakdown

| Category | Triages | Description |
|---|---|---|
| `generic-error-rendering` | 9 | Platform shows a generic error instead of a useful message |
| `guardrail-false-positive` | 4 | Valid questions incorrectly blocked by guardrails |
| `agent-content-defect` | 2 | Agent returned incomplete or incorrect content |
| `agent-instruction-noncompliance` | 1 | Agent ignored explicit output format instructions |
| `unsupported-capability` | 1 | Query requests a capability the agent doesn't support |
| `duplicate-response` | 1 | Agent returned a duplicate response |
| `language-mismatch` | 1 | Non-English input produced mismatched language handling |

Note: some traces are classified into multiple categories, hence 19 total classifications across 14 triages.

---

## Triage Verdicts

| Verdict | Count |
|---|---|
| accepted | 12 |
| accepted-with-edits | 2 |
| rejected | 0 |

---

## Feedback Trace Details

| # | Date | Input (truncated) | Routing | Agent | Comment |
|---|---|---|---|---|---|
| 1 | 05-11 | Add a participant to a case's contact list | execute | Cases | — |
| 2 | 05-11 | Summarize assets past LDOS | execute | Assets (General) | Test from 'Full Analysis' or 'AI Assistant' |
| 3 | 05-12 | BGP between 3 cat 9k routers … topology diagram | error | — | Generic error |
| 4 | 05-12 | Cisco Security Advisory ID | error | — | — |
| 5 | 05-12 | cuantos casos tengo abiertos? | execute | Cases | Prompts should be in English, not Spanish |
| 6 | 05-12 | elenca tutte le milestone e le date | error | — | — |
| 7 | 05-13 | what about field notices? | error | — | Guardrail should trigger default message on IQ capabilities |
| 8 | 05-13 | tell me the names of all devices … critical security advisory | execute | Security Advisories | — |
| 9 | 05-13 | Review asset inventory, ignore LDOS gear … code upgrades | execute | Assets (General) | Missing data that was requested |
| 10 | 05-13 | WAPs in install base … JSON formatted response | execute | Assets (General) | Failed to follow JSON output instruction |
| 11 | 05-13 | Review FN74383 … list of APs and versions impacted? | error | — | Query not processed; error generated |
| 12 | 05-13 | What is the workaround for fn72424 | error | — | CIQ should answer Field Notice questions |
| 13 | 05-13 | excel sheet of assets … end of support 2025/2026 … business unit | execute | Assets (General) | — |
| 14 | 05-14 | Field Notice 72464の影響範囲をまとめて | error | — | Response is bugged |

---

## Defects Filed

| Jira Key | Traces | Theme |
|---|---|---|
| [CXP-32676](https://cisco-cxe.atlassian.net/browse/CXP-32676) | 7 | Generic error rendering — umbrella defect for error-path traces |
| [CXP-33091](https://cisco-cxe.atlassian.net/browse/CXP-33091) | 1 | Cases: "Add participant" unsupported capability |
| [CXP-33092](https://cisco-cxe.atlassian.net/browse/CXP-33092) | 1 | Cases: duplicate response |
| [CXP-33285](https://cisco-cxe.atlassian.net/browse/CXP-33285) | 1 | Cases: Spanish language mismatch |
| [CXP-33287](https://cisco-cxe.atlassian.net/browse/CXP-33287) | 1 | Security Advisories: device count retrieval failure |
| [CXP-33291](https://cisco-cxe.atlassian.net/browse/CXP-33291) | 1 | Assets: missing requested data fields |
| [CXP-33292](https://cisco-cxe.atlassian.net/browse/CXP-33292) | 3 | Field Notice questions blocked / errored |
| [CXP-33295](https://cisco-cxe.atlassian.net/browse/CXP-33295) | 1 | Assets: JSON output instruction noncompliance |
| [CXP-33296](https://cisco-cxe.atlassian.net/browse/CXP-33296) | 1 | Assets: EOS excel export gap |
| [CXP-33297](https://cisco-cxe.atlassian.net/browse/CXP-33297) | 1 | Assets: business unit column blank |

### Defects by Agent

| Agent | Distinct Defects | Keys |
|---|---|---|
| Assets (General) | 4 | CXP-33291, CXP-33295, CXP-33296, CXP-33297 |
| Cases | 3 | CXP-33091, CXP-33092, CXP-33285 |
| Assessments - Security Advisories | 1 | CXP-33287 |
| No agent (error path) | 2 | CXP-32676, CXP-33292 |

---

## Key Takeaways

1. **Error rendering is the #1 issue.** CXP-32676 alone covers 7 of 14 traces — half the feedback corpus. Fixing the generic error page would eliminate the most common negative signal.

2. **Guardrail false-positives block valid queries.** Field Notice and non-English questions are being rejected when they shouldn't be (CXP-33292 covers 3 traces).

3. **Assets (General) has the most agent-side defects** — 4 distinct tickets for content gaps, instruction noncompliance, and missing data.

4. **100% triage acceptance rate** — all feedback was validated, indicating the annotation queue is surfacing real user pain.

5. **Temporal cluster on May 12–13** — 11 of 14 traces landed in a 2-day window, likely a focused feedback / QA session.
