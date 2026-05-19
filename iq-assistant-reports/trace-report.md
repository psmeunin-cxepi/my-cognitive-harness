> **Agent:** Semantic Router (`ciq-agents-prod-usw2`)
>
> **Repo:** [`CXEPI/cvi-ai-a2a`](https://github.com/CXEPI/cvi-ai-a2a) (routing logic)
>
> **Period:** 2026-05-05 — 2026-05-12 (7 days, up to 100 traces/day)

# CX IQ Semantic Router — 7-Day Input/Output Analysis

## Summary

800 traces collected from `ciq-agents-prod-usw2` (PROD cluster, `cx-iq-prod` workspace) over 7 days. Of those, **517 were successfully routed** to an agent (65%) and **283 were context-only "Ask AI" invocations** that triggered a default welcome message (35%). Of the routed traces, **45 had real user input but received no `agent_choice`** — these represent unhandled or out-of-scope queries.

Full trace data: [`traces.json`](./traces.json) — one record per trace with `input`, `output`, `agent_name`, `agent_skill`.

---

## Routing Distribution

| Agent | Count | Skills |
|---|---|---|
| Assets (General) | 337 | `ask_cvi_ldos_ai_external`, `ask_cvi_ldos_ai_internal` |
| Cases | 99 | `cx_ai_list_cases`, `buff_mcp`, `caia_generate_summary`, `cx_ai_case_create` |
| Assessments - Security Advisories | 27 | `ask_security_assessment` |
| Assessments - Security Hardening | 19 | `ask_security_hardening` |
| Troubleshooting | 19 | `Enola_Get_CVE`, `cx_ai_fn_q_a` |
| Asset Criticality | 8 | `ask_asset_criticality` |
| Assessments – Configuration | 7 | `assessments-configuration-summary`, `asset-scope-analysis`, `rule-analysis` |
| default | 1 | `default` |
| **No route (Ask AI clicks)** | 238 | — |
| **No route (real input, unhandled)** | 45 | — |
| **Total** | **800** | |

---

## Input Patterns by Agent

### Assets (General) — 337 traces
The dominant agent. Most inputs are templated UI-injected queries (static routing), with a small tail of freeform questions.

Recurring templated inputs:
- "Summarize assets reaching Last Date of Support (LDOS) in the next 12 months."
- "Summarize assets past Last Date of Support (LDOS)."

Freeform inputs (semantic routing):
- "How many different software versions are present in my top 5 software types?"
- "How many devices have no telemetry"
- "Can you see the asset I have open"
- "Make switch health report LE-CPD-EP_9300_ACC_SUBEST"
- "Cuantas licencias de tipo DNA se tienen actualmente" *(non-English input)*

### Cases — 99 traces
Highly repetitive. The vast majority are a single templated query routed statically.

Recurring:
- "Show me my open cases" (>80% of Cases traces)

Freeform:
- "Give me a summary for 700720541"
- "Add a participant to a case's contact list"

### Assessments - Security Advisories — 27 traces
Mix of static (welcome-trigger) and semantic routing.

Freeform:
- "How do I resolve the vulnerabilities"
- "How do I check my CVE exposure"

### Assessments - Security Hardening — 19 traces
Mix of static and semantic.

Freeform:
- "Recommendations for addressing failed checks"
- "Hardening guidance"

### Troubleshooting — 19 traces
All semantic routing. Most specific and diverse inputs of any agent.

Examples:
- "Need help troubleshooting a C9300. It is hitting bug CSCwq31287 (CVE-2017-12240) and I'd like information on how to remediate it"
- "bb8-s4-leaf1 has been dropping traffic lately, why?"
- "Nexus 93180YC-FX on NX-OS 10.2"
- "This device has been rebooting a lot lately"
- "We have a ASR1001-X running 17.9.4a which is affected by a bug. What is the next minimum recommended version to remediate"
- "apic. managed"

### Asset Criticality — 8 traces
Low volume, all static routing.

### Assessments – Configuration — 7 traces
Low volume, mix of skills.

Examples:
- "Which Cisco product families have the most deviations from configuration best practices?"
- "What are the most common configuration deviations across my network?"

---

## No-Route Traces with Real Input (45)

These traces had a non-empty user input but no `agent_choice` in the output — the router returned `status=success` without selecting an agent. These represent either out-of-scope queries or routing gaps.

### Platform / Navigation Questions (router has no agent for these)
- "Where is the help menu?"
- "How to use API from own applications to CiscoIQ"
- "What are the data sources?"
- "Where are the data connectors?" / "How can I see the data connectors?"
- "What is Cisco IQ?"
- "I migrated from CX Cloud"
- "How do I add a new user"
- "What is it Cisco IQ?" / "Can you explain me what is Cisco IQ?"

### Cross-Agent / Multi-Domain Queries (no single agent owns these)
- "Can you give me a breakdown by product family of which devices are past their last date of support and are also vulnerable?"
- "Out of the 401 chassis which are not covered which ones are affected by critical security vulnerabilities"
- "Give me all the security advisories impacting all assets in Santa Clara location"
- "What are the Field Notices associated with Santa Clara site"
- "Can you create a report for my management, which provides an overview of these critical PSIRTs and also provides remediation recommendations?" (x2)
- "Are there any product-related trends you can point out regarding vulnerable items?"
- "Among my assets with security advisories, what type of products have the highest percentage of vulnerable items?"

### Troubleshooting-adjacent (should likely route to Troubleshooting)
- "9407-dualsup has been rebooting a lot lately, is it hitting a bug or fn?" (x2)
- "Provide top 10 critical bugs"
- "Show me the most vulnerable assets"
- "How many devices do I have that have a PSIRT" / "Do I have any of them in my network?"

### Out-of-Scope / General Knowledge
- "What latest PQC FIPS standard from NIST"
- "What is PQC"
- "Security hardening and brocolli project" *(likely a test/junk input)*
- "Describe me SNT service?"
- "Could you explain me the difference between Cisco services and partner services?" (x4)
- "Describe me L1NBD service"
- "12345678" *(junk input)*

### Context-dependent (require prior turn to interpret)
- "Provide me an impact analysis and recommendation to fix it"
- "Provide me the summary, recommendations and steps to implement" (x2)
- "Summarize the LDOS for the last 6 months and its criticality"
- "What GUIDs are added to this account?"
- "Whose assets are these?"
- "Can you tell me more about what devices are affected by advisories?"
- "Can you give me a breakdown of the product family with the most security vulnerabilities?"
- "Summarize the list of assets that are not covered"
- "Which not covered chassis have critical field notice or security vulnerability matches..."

---

## Observations

1. **Static routing dominates.** ~65% of routed traces use static routing (exact-match trigger phrases from the UI), not semantic routing. The semantic router is primarily exercised by freeform user input.

2. **Assets (General) is by far the most used agent** (65% of routed traffic), driven largely by UI-injected LDOS summary cards.

3. **Empty input = 417 traces (52%).** More than half of all traces have no user-typed question — they are "Ask AI" button clicks where the router uses only the UI context (`app`, `url`, `filters`) to route. These all result in welcome/capability messages.

4. **45 real inputs produced no route.** The clearest routing gaps are:
   - Cross-domain queries spanning Assets + Security (no agent owns the intersection)
   - Platform/navigation questions (out of agent scope entirely)
   - Multi-turn context-dependent follow-ups that lack a prior conversation context

5. **Non-English input observed.** At least one Spanish-language input ("Cuantas licencias de tipo DNA se tienen actualmente") was successfully routed to Assets (General).

6. **Troubleshooting inputs are the most specific and technical** but have the lowest volume (19 traces). These are the hardest to route correctly and the most likely to benefit from semantic routing improvements.
