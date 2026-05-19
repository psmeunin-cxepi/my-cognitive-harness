# CX IQ Agent Gap Insights v2 from the Extended Semantic Router Knowledge Graph

> Date: 2026-05-13
>
> Data source: CX IQ Semantic Router Neo4j knowledge graph populated from `iq-assistant-feedback-reports/traces.json`
>
> Objective: Understand where IQ agents currently fall short on answering user prompts, using the extended graph schema with `routing_decision` and `SELECTED` relationships.

## 1. Executive Summary

The extended graph changes the diagnosis from a generic "no-route" story to a more precise routing-branch story.

The key new fact is that the graph now separates agent selection from execution:

- `SELECTED` means the router selected an agent/skill candidate.
- `ROUTED_TO` means the selected agent/skill actually executed.
- `Question.routing_decision` records the final branch: `execute`, `error`, `default`, or `guardrails_blocked` in this dataset.

Across 563 total traces, 516 executed. Among 383 non-empty user prompts, 337 executed and 46 did not execute, for a **12.0% non-execution rate**.

The major user-visible failure mode is now clear: **45 traces ended in `routing_decision = "error"` and returned the generic response `An error occurred while processing your request. Trace ID: ...`**. Of those, 44 were non-empty user prompts and 1 was an empty/context-only invocation.

The highest-risk app surface remains `assessments`:

| App | Non-empty prompts | Executed | Errors | Default | Guardrails blocked | Not executed rate |
| --- | ----------------: | -------: | -----: | ------: | -----------------: | ----------------: |
| assessments | 46 | 27 | 18 | 0 | 1 | 41.3% |
| admin | 10 | 7 | 3 | 0 | 0 | 30.0% |
| platform-home | 59 | 48 | 11 | 0 | 0 | 18.6% |
| asset-explorer | 259 | 246 | 12 | 1 | 0 | 5.0% |
| support | 9 | 9 | 0 | 0 | 0 | 0.0% |

The strongest gap clusters are still security/field-notice/bug language and platform-help/services questions. The difference in v2 is that these are not just missing `ROUTED_TO` edges; they are mostly explicit `error` routing decisions with no selected agent.

## 2. Validated Graph Schema

I validated the actual graph shape before deriving findings.

Observed node labels and properties:

| Label | Properties | Count |
| ----- | ---------- | ----: |
| `Question` | `trace_id`, `input`, `date`, `start_time`, `import_index`, `routing_decision` | 563 |
| `UIContext` | `app` | 5 |
| `Agent` | `name`, `skills` | 8 |
| `Response` | `trace_id`, `output` | 563 |

Observed relationship types and properties:

| Relationship | Properties | Count |
| ------------ | ---------- | ----: |
| `(:Question)-[:OCCURRED_IN]->(:UIContext)` | none | 563 |
| `(:Question)-[:HAS_RESPONSE]->(:Response)` | none | 563 |
| `(:Question)-[:SELECTED {skill}]->(:Agent)` | `skill` | 517 |
| `(:Question)-[:ROUTED_TO {skill}]->(:Agent)` | `skill` | 516 |
| `(:Agent)-[:PRODUCED {skill}]->(:Response)` | `skill` | 516 |

Observed routing decisions:

| Routing decision | Total traces | Non-empty prompts |
| ---------------- | -----------: | ----------------: |
| `execute` | 516 | 337 |
| `error` | 45 | 44 |
| `default` | 1 | 1 |
| `guardrails_blocked` | 1 | 1 |

Important semantic correction: `SELECTED` exists for the 516 executed traces and the 1 `default` trace. It does not exist for the `error` or `guardrails_blocked` traces in this dataset. That means the 45 generic processing errors failed before a selected agent/skill was recorded in the graph.

## 3. Baseline Execution View

Overall graph baseline:

| Metric | Count |
| ------ | ----: |
| Question traces | 563 |
| UI contexts | 5 |
| Agents | 8 |
| Responses | 563 |
| Selected traces | 517 |
| Executed traces | 516 |
| Not executed traces | 47 |

Non-empty user prompt baseline:

| Metric | Count |
| ------ | ----: |
| Non-empty user prompts | 383 |
| Executed prompts | 337 |
| Not executed prompts | 46 |
| Non-empty prompt non-execution rate | 12.0% |

There are also 180 empty-input or context-only traces. Of those, 179 executed and 1 ended in `error`. For gap analysis, non-empty prompts remain the better denominator because they represent user-entered asks.

Execution trend by date:

| Date | Prompts | Executed | Errors | Default | Guardrails blocked | Not executed rate |
| ---- | ------: | -------: | -----: | ------: | -----------------: | ----------------: |
| 2026-05-07 | 48 | 38 | 10 | 0 | 0 | 20.8% |
| 2026-05-08 | 66 | 52 | 14 | 0 | 0 | 21.2% |
| 2026-05-09 | 67 | 66 | 0 | 1 | 0 | 1.5% |
| 2026-05-10 | 69 | 66 | 3 | 0 | 0 | 4.3% |
| 2026-05-11 | 56 | 51 | 4 | 0 | 1 | 8.9% |
| 2026-05-12 | 77 | 64 | 13 | 0 | 0 | 16.9% |

The error branch is not evenly distributed over time. It spikes on 2026-05-07, 2026-05-08, and 2026-05-12.

## 4. Main Findings

### 4.1 Error Branch Is the Primary Failure Mode

The largest user-visible failure is not a routed agent execution failure. It is the router ending in `routing_decision = "error"` and returning a generic processing error.

Generic processing-error responses:

| Routing decision | Execution status | Traces |
| ---------------- | ---------------- | -----: |
| `error` | not executed | 45 |

The exact response pattern is:

```text
An error occurred while processing your request. Trace ID: ...
```

This matters because prior no-route analysis could only say there was no `ROUTED_TO` edge. The extended graph now shows a stronger diagnosis: these are explicit router `error` branch outcomes, not merely unknown missing routes.

### 4.2 Error Branch Has No Selected Agent

The 45 `error` traces have no `SELECTED` edge. That means the graph cannot attribute them to a selected agent card or skill. The failure likely occurs before or during agent selection / branch resolution rather than during downstream agent execution.

Selected agent/skill by routing branch:

| Routing decision | Selected traces | Interpretation |
| ---------------- | --------------: | -------------- |
| `execute` | 516 | Agent selected and executed. |
| `default` | 1 | Default selected, but no executed route. |
| `error` | 0 | No selected agent recorded. |
| `guardrails_blocked` | 0 | No selected agent recorded. |

This is one of the most important v2 insights: error branch failures need router-level instrumentation, not only agent-level debugging.

### 4.3 Gap Clusters in Non-Executed Prompts

I classified non-empty prompts where `routing_decision <> "execute"`.

| Gap cluster | Routing decision | Traces | Apps | Interpretation |
| ----------- | ---------------- | -----: | ---- | -------------- |
| Security, field notice, bug, PSIRT | `error` | 19 | `assessments`, `asset-explorer` | Security and defect-related phrasing often reaches router error rather than selecting an agent. |
| Platform help and services | `error` | 16 | `platform-home`, `asset-explorer`, `admin` | Product-help and service-terminology questions have no stable owner. |
| Context follow-up or synthesis | `error` | 4 | `assessments` | Follow-up/synthesis asks still fail branch resolution. |
| Other | `error` | 3 | `platform-home`, `asset-explorer` | Account/ownership or underspecified numeric prompts. |
| Asset lifecycle or coverage | `error` | 2 | `asset-explorer`, `admin` | LDOS/coverage summary gaps. |
| Security, field notice, bug, PSIRT | `guardrails_blocked` | 1 | `assessments` | One suspicious or malformed hardening phrase blocked by guardrails. |
| Other | `default` | 1 | `asset-explorer` | One default fallback for "why no data". |

The security/FN/bug cluster remains the largest technical domain gap. Examples include:

- "Provide top 10 critical bugs"
- "how many devices do i have that have a psirt"
- "Can you tell me more about what devices are affected by advisories?"
- "Give me all the security advisories impacting all assets in santa clara location"
- "Tell me if there is any field notices impacting any asset in Santa Clara location"
- "What are the Field Notices associate with SAnta Clara site?"
- "9407-dualsup has been rebooting a lot lately, is it hitting a bug or fn?"
- "what is PQC"
- "what latest PQC FIPS standard from NIST"

The platform-help/services cluster remains a product capability gap. Examples include:

- "what is cisco iq link"
- "how do i add a new user"
- "Where is the help menu?"
- "What are the data sources?"
- "How can I see the data connectors?"
- "where are the data connectors?"
- "Can you explain me what is it cisco IQ?"
- "How to use API from own applications to CiscoIQ"
- "could you explain me the difference between cisco services and partner services?"
- "describe me SNT service?"
- "describe me L1NBD service"

### 4.4 App-Specific Interpretation

`assessments` is still the most important surface to fix first. It has only 46 non-empty prompts, but 19 did not execute: 18 errors and 1 guardrail block. Its failures are concentrated in security advisory, vulnerability, field notice, bug/FN, remediation, and follow-up synthesis asks.

`platform-home` has 11 errors across 59 non-empty prompts. These are primarily product-help, Cisco IQ, API, service, and account ownership questions.

`asset-explorer` has the largest prompt volume and a lower non-execution rate, but still exposes high-value gaps: security/PSIRT report synthesis, field notice by site, partner-service explanation, and product navigation.

`admin` has low volume but a high failure rate. Its errors are product-help and asset coverage adjacent: data sources, help menu, and uncovered assets.

`support` executed all 9 non-empty prompts in this dataset, but the volume is too small to infer broad robustness.

### 4.5 Executed Routing Mix

Executed non-empty prompt routing is heavily concentrated in a few skills:

| App | Agent | Skill | Executed prompts |
| --- | ----- | ----- | ---------------: |
| asset-explorer | `Assets (General)` | `ask_cvi_ldos_ai_external` | 139 |
| asset-explorer | `Cases` | `cx_ai_list_cases` | 85 |
| platform-home | `Assets (General)` | `ask_cvi_ldos_ai_external` | 31 |
| assessments | `Assessments - Security Advisories` | `ask_security_assessment` | 11 |
| platform-home | `Troubleshooting` | `Enola_Get_CVE` | 10 |
| assessments | `Assets (General)` | `ask_cvi_ldos_ai_external` | 9 |

This mix shows that the router can execute cross-surface operational asks. The gap is not that agents are unavailable; it is that some user language patterns and product-help domains fall into `error` before selection.

### 4.6 Routed Agent Execution Failures Are Secondary

I separately scanned executed routed responses for strong failure phrases such as `temporary system issue`, `data type mismatch`, `no data available`, and `an error occurred`.

Strong executed response-failure indicators among non-empty prompts:

| Agent | Skill | Executed prompts | Strong failures | Strong failure rate |
| ----- | ----- | ---------------: | --------------: | ------------------: |
| `Assets (General)` | `ask_cvi_ldos_ai_internal` | 2 | 2 | 100.0% |
| `Assessments - Security Advisories` | `ask_security_assessment` | 15 | 2 | 13.3% |
| `Cases` | `cx_ai_list_cases` | 89 | 2 | 2.2% |

Representative examples:

- `Cases` / `cx_ai_list_cases`: "Show me my open cases" returned a temporary system issue.
- `Assessments - Security Advisories` / `ask_security_assessment`: "critical vulnerability released less than a year ago" returned a data type mismatch.
- `Assets (General)` / `ask_cvi_ldos_ai_internal`: "what's here" and "inevntory" returned "No data available at the moment."

These are concrete execution defects, but they are not the dominant failure mode. The dominant failure mode is the router `error` branch.

### 4.7 Strict Multi-Intent Prompts Are Rare but Fragile

Using the corrected strict definition, multi-intent means multiple requested outcomes/actions, not simply multiple entities, filters, or compared items.

Strict multi-intent count:

| Metric | Count |
| ------ | ----: |
| Non-empty prompt traces | 383 |
| Distinct normalized non-empty prompts | 156 |
| Multi-intent traces | 9 |
| Distinct multi-intent prompts | 7 |
| Executed multi-intent traces | 3 |
| Not executed multi-intent traces | 6 |
| Multi-intent not executed rate | 66.7% |

Examples that did not execute:

- "Can you create a report for my management, which provides an overview of these critical PSIRTs and also provides remediation recommendations?"
- "provide me the summary, recommendations and steps to implement"
- "Provide me an impact analysis and recommendation to fix it"
- "Which not covered chassis have critical field notice or security vulnerability matches and what are those field notices and security vulnerabilities."

Examples that executed:

- "I am seeing exposure for CVE-2023-20198 on device Device_48_0_1_70. Can you confirm that I have exposure to this vulnerability? How can I fix this?"
- "Need help troubleshooting a C9300. It is hitting bug CSCwq31287 (CVE-2017-12240) and I'd like information on how to remediate it"
- "list my assets that are past the last date of support milestone and assets that will pass last date of support in the next 12 months"

Multi-intent is low volume, but fragile. The router needs an explicit decomposition or lead-agent strategy for prompts asking for a report plus remediation, exposure plus fix, or identification plus details.

### 4.8 Routing Consistency

No identical non-empty prompt took multiple final `routing_decision` values after trimming whitespace. In other words, repeated prompts were not observed flipping between `execute` and `error`.

There is one repeated prompt that executed to different agents:

| Prompt | Outcomes |
| ------ | -------- |
| "list my critical assets that will pass the last date of support in the next 12 months" | `Assets (General)` / `ask_cvi_ldos_ai_external`; `Asset Criticality` / `ask_asset_criticality` |

This is not the dominant problem, but it does show a boundary ambiguity between lifecycle and criticality semantics.

## 5. Recommendations

1. Treat router `error` as a first-class product failure.

   The error branch is the main failure path. It should have structured reason codes, logs, candidate route state, and a user-facing response that does not look like a generic system crash.

2. Instrument pre-selection failure details.

   The `error` and `guardrails_blocked` traces have no `SELECTED` edge. Add candidate agents, scores, rejection reasons, guardrail categories, or exception details so future analysis can distinguish no candidate, low confidence, parsing error, policy block, and internal exception.

3. Replace generic processing-error responses.

   The `An error occurred while processing your request` response appears 45 times. Users need a helpful explanation, recovery suggestions, and examples of supported asks. Keep the Trace ID for support, but do not make it the whole answer.

4. Expand router coverage for security/FN/bug phrasing.

   Add routing examples and evals for PSIRT, vulnerability, advisory, field notice, FN, bug, critical bug, rebooting device, remediation, PQC, and FIPS language. These should be mapped intentionally across Security Advisory, Troubleshooting, Security Hardening, and product-help depending on the prompt.

5. Add a product-help or product-knowledge route.

   Platform-home, admin, and asset-explorer users ask product navigation and service meaning questions. These are legitimate Cisco IQ questions, but operational agents are not the right owners.

6. Improve follow-up and synthesis handling.

   Prompts like "do i have any of them in my network?" and "provide me the summary, recommendations and steps to implement" need conversation context and possibly multi-step synthesis before routing.

7. Add multi-intent decomposition.

   Multi-intent prompts are rare but have a high non-execution rate. The router should decompose these into sub-intents or select a lead agent with secondary tasks.

8. Fix routed execution defects separately.

   The Cases temporary system issue, Security Advisory date/type mismatch, and internal LDOS no-data path are real defects, but they should be tracked separately from router error branch failures.

9. Use the 46 non-executed non-empty prompts as a regression set.

   Label each with expected routing decision, expected selected agent/skill if applicable, expected user-facing fallback, and whether it requires product-help, operational data, context resolution, or multi-step decomposition.

## 6. Reflection and Critique

The extended graph materially improves the analysis. The old report could see missing `ROUTED_TO` edges, but not why. The new report can distinguish:

- `execute`: selected and executed.
- `error`: no execution and generic processing error.
- `default`: selected default, no execution.
- `guardrails_blocked`: no execution due to guardrail branch.

The strongest conclusion is that the main current gap is **router error handling before agent selection**, especially for security/FN/bug questions and platform-help/service questions.

What the graph still cannot prove:

- Whether executed answers were factually correct.
- Whether users were satisfied.
- Whether `error` was caused by no candidate, low confidence, parsing, guardrails, exception, or missing skill metadata.
- Whether a product-help question should be answered by a new agent, a documentation tool, or a router-level help response.
- Whether a routed response completed all sub-intents in a multi-intent prompt.

The next graph extension should add structured reason codes and candidate-route telemetry for non-execute branches. Without those fields, the `error` branch is now visible but still opaque.

## 7. Key Cypher Queries Used

Validate node schema:

```cypher
MATCH (n)
WITH labels(n) AS labels, keys(n) AS keys, count(*) AS count
RETURN labels, keys, count
ORDER BY labels, keys
```

Validate relationship schema:

```cypher
MATCH ()-[rel]->()
WITH type(rel) AS relationship, keys(rel) AS keys, count(*) AS count
RETURN relationship, keys, count
ORDER BY relationship, keys
```

Routing branch distribution:

```cypher
MATCH (q:Question)
RETURN coalesce(q.routing_decision, "UNKNOWN") AS routing_decision,
       count(q) AS traces,
       count(CASE WHEN trim(q.input) <> "" THEN 1 END) AS non_empty_prompts
ORDER BY traces DESC
```

Non-empty prompt execution by app:

```cypher
MATCH (q:Question)-[:OCCURRED_IN]->(ui:UIContext)
WHERE trim(q.input) <> ""
WITH ui.app AS app,
     count(q) AS prompts,
     sum(CASE WHEN q.routing_decision = "execute" THEN 1 ELSE 0 END) AS executed,
     sum(CASE WHEN q.routing_decision = "error" THEN 1 ELSE 0 END) AS errors,
     sum(CASE WHEN q.routing_decision = "default" THEN 1 ELSE 0 END) AS defaults,
     sum(CASE WHEN q.routing_decision = "guardrails_blocked" THEN 1 ELSE 0 END) AS guardrails_blocked
RETURN app,
       prompts,
       executed,
       errors,
       defaults,
       guardrails_blocked,
       round(100.0 * (errors + defaults + guardrails_blocked) / prompts, 1) AS not_executed_pct
ORDER BY not_executed_pct DESC, prompts DESC
```

Selected agent and skill by routing branch:

```cypher
MATCH (q:Question)-[selected:SELECTED]->(a:Agent)
RETURN coalesce(q.routing_decision, "UNKNOWN") AS routing_decision,
       a.name AS selected_agent,
       selected.skill AS selected_skill,
       count(q) AS traces,
       count(CASE WHEN trim(q.input) <> "" THEN 1 END) AS non_empty_prompts
ORDER BY routing_decision, traces DESC, selected_agent
```

Generic processing errors by branch:

```cypher
MATCH (q:Question)-[:HAS_RESPONSE]->(r:Response)
WHERE toLower(r.output) CONTAINS "an error occurred while processing your request"
OPTIONAL MATCH (q)-[:ROUTED_TO]->(a:Agent)
RETURN coalesce(q.routing_decision, "UNKNOWN") AS routing_decision,
       CASE WHEN a IS NULL THEN "not_executed" ELSE "executed" END AS execution_status,
       count(q) AS traces
ORDER BY traces DESC
```

Strict multi-intent count:

```cypher
MATCH (q:Question)
WHERE trim(q.input) <> ""
WITH q, trim(q.input) AS original, toLower(trim(q.input)) AS input
WHERE input CONTAINS "report for my management"
   OR input = "provide me the summary, recommendations and steps to implement"
   OR (input CONTAINS "confirm that i have exposure" AND input CONTAINS "how can i fix")
   OR (input CONTAINS "need help troubleshooting" AND input CONTAINS "remediate")
   OR (input CONTAINS "impact analysis" AND input CONTAINS "recommendation")
   OR input CONTAINS "past the last date of support milestone and assets that will pass"
   OR (input CONTAINS "which not covered chassis" AND input CONTAINS "what are those field notices")
RETURN count(q) AS multi_intent_traces,
       count(DISTINCT toLower(original)) AS distinct_multi_intent_prompts,
       sum(CASE WHEN q.routing_decision = "execute" THEN 1 ELSE 0 END) AS executed_traces,
       sum(CASE WHEN q.routing_decision <> "execute" THEN 1 ELSE 0 END) AS not_executed_traces,
       round(100.0 * sum(CASE WHEN q.routing_decision <> "execute" THEN 1 ELSE 0 END) / count(q), 1) AS multi_intent_not_executed_pct
```