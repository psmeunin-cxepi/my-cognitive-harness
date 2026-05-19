# CX IQ Agent Gap Insights from the Semantic Router Knowledge Graph

> Date: 2026-05-13
>
> Data source: CX IQ Semantic Router Neo4j knowledge graph populated from `iq-assistant-feedback-reports/traces.json`
>
> Objective: Understand where IQ agents currently fall short on answering user prompts.

## 1. Executive Summary

The clearest current gap is not a single weak agent. It is a routing and coverage gap around product-relevant questions that users reasonably expect IQ to answer.

Across the graph there are 563 trace occurrences. Of those, 383 are non-empty user prompts. Among non-empty prompts, 45 did not route to any agent, for an unrouted rate of 11.7%.

The gap is highly concentrated by surface:

| App            | Non-empty prompts | Routed | Unrouted | Unrouted rate |
| -------------- | ----------------: | -----: | -------: | ------------: |
| assessments    |                46 |     27 |       19 |         41.3% |
| admin          |                10 |      7 |        3 |         30.0% |
| platform-home  |                59 |     48 |       11 |         18.6% |
| asset-explorer |               259 |    247 |       12 |          4.6% |
| support        |                 9 |      9 |        0 |          0.0% |

The strongest finding: `assessments` is the highest-risk surface. It has the most unrouted prompts and the highest no-route rate among meaningful user prompts. Many of these are not random or abusive prompts; they are security advisory, PSIRT, field notice, bug, remediation, and asset exposure questions.

The second major finding: no-route failures mostly surface as generic processing errors. Of 46 total no-route traces, 45 returned an `An error occurred while processing your request. Trace ID: ...` style response. That means the product experience hides a routing gap behind what looks like a system failure.

The third major finding: true multi-intent prompts are a small but high-risk slice of usage. Using a corrected strict definition, 9 of 383 non-empty prompt traces are multi-intent. Of those 9 traces, 6 did not route, for a 66.7% no-route rate. That is far worse than the overall 11.7% no-route rate for non-empty prompts.

## 2. How I Interpreted "Gaps"

I treated a gap as one of four observable failure modes in the graph:

1. No route: the router did not attach the prompt to any agent.
2. Weak route: the prompt routed to a fallback/default or an agent whose answer says it cannot help.
3. Execution failure: the prompt routed, but the response reports temporary system issues, missing data, or internal data problems.
4. Capability mismatch: the user asks for a natural extension of the product experience, but no current agent appears to own it.

The graph can show routing, app context, selected agent/skill, prompt text, and response text. It cannot, by itself, prove factual correctness, user satisfaction, tool call failures, or whether a human would consider an answer complete.

## 3. Baseline Observations

Overall graph shape:

| Metric          | Count |
| --------------- | ----: |
| Question traces |   563 |
| UI contexts     |     5 |
| Agents          |     8 |
| Responses       |   563 |
| Routed traces   |   517 |
| Unrouted traces |    46 |

Non-empty prompt baseline:

| Metric                         | Count |
| ------------------------------ | ----: |
| Non-empty user prompts         |   383 |
| Routed non-empty prompts       |   338 |
| Unrouted non-empty prompts     |    45 |
| Non-empty prompt no-route rate | 11.7% |

There are also 180 empty-input or context-only traces. Most empty-input traces are routed, especially from `asset-explorer` to `Assets (General)`. This matters because using all 563 traces can make routing look healthier than it feels for typed user prompts. The user-prompt view is the better denominator for this analysis.

## 4. Main Gap Clusters

I classified the 45 non-empty no-route prompts using transparent keyword rules and then reviewed representative examples.

| Gap cluster                        | Unrouted traces | Apps                                       | What it means                                                                          |
| ---------------------------------- | --------------: | ------------------------------------------ | -------------------------------------------------------------------------------------- |
| Security, field notice, bug, PSIRT |              20 | `assessments`, `asset-explorer`            | Domain-relevant security and defect questions are not consistently covered by routing. |
| Platform help and services         |              16 | `platform-home`, `asset-explorer`, `admin` | Users ask how IQ works, where features live, what services mean, and how to use APIs.  |
| Context follow-up or synthesis     |               4 | `assessments`                              | Follow-up prompts and summary/recommendation requests lose context or ownership.       |
| Other                              |               3 | `platform-home`, `asset-explorer`          | Account/ownership or numeric inputs with insufficient route context.                   |
| Asset lifecycle or coverage        |               2 | `asset-explorer`, `admin`                  | LDOS, not-covered assets, and coverage summaries occasionally miss routing.            |

### 4.1 Security, Field Notice, Bug, and PSIRT Gap

This is the largest cluster: 20 of 45 non-empty no-route prompts.

Examples:

- "Provide top 10 critical bugs"
- "how many devices do i have that have a psirt"
- "Can you tell me more about what devices are affected by advisories?"
- "Give me all the security advisories impacting all assets in santa clara location"
- "Tell me if there is any field notices impacting any asset in Santa Clara location"
- "What are the Field Notices associate with SAnta Clara site?"
- "9407-dualsup has been rebooting a lot lately, is it hitting a bug or fn?"
- "what is PQC"
- "what latest PQC FIPS standard from NIST"

Insight: the router is missing a family of security-adjacent and defect-adjacent phrasing. Users do not consistently say "security advisory" in canonical terms. They say PSIRT, vulnerability, field notice, bug, FN, critical bugs, rebooting, or ask general standards questions such as PQC/FIPS.

The product gap is not simply "no agent for security." There is a Security Advisory agent and Security Hardening agent, and some security prompts do route. The gap is phrase coverage, intent boundaries, and blended app context.

### 4.2 Platform Help, Product Education, and Services Gap

This cluster has 16 unrouted traces.

Examples:

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

Insight: users expect Ask AI to answer product navigation, terminology, service entitlement, and platform education questions. The current agent set is mostly operational-data oriented. When users ask product-help questions, the system often has no route.

Some service questions route to `Assets (General)`, but the response says the agent cannot provide that information because it focuses on inventory, lifecycle, security advisories, and infrastructure data. That is a capability boundary, not a successful answer.

Representative routed service examples:

| Prompt                                                                             | Route                                           | Observed response pattern                                                                                         |
| ---------------------------------------------------------------------------------- | ----------------------------------------------- | ----------------------------------------------------------------------------------------------------------------- |
| "can i see partner services in cisco IQ?"                                          | `Assets (General)` / `ask_cvi_ldos_ai_external` | Unable to provide partner-service information; capability focused on inventory/lifecycle/security/infrastructure. |
| "why is better to buy standard services than basic services?"                      | `Assets (General)` / `ask_cvi_ldos_ai_external` | Unable to provide recommendations or comparative analyses.                                                        |
| "could you explain me the difference between cisco services and partner services?" | No route                                        | Generic processing error.                                                                                         |

### 4.3 Context Follow-up and Synthesis Gap

The graph shows follow-up or synthesis prompts from `assessments` that did not route:

- "do i have any of them in my network?"
- "provide me the summary, recommendations and steps to implement"
- "Provide me an impact analysis and recommendation to fix it"

Insight: users are not always asking standalone questions. They refer to prior entities with "them" and "it", or ask for a synthesis step after earlier results. If the semantic router only sees the current utterance without enough conversation state or resolved entities, these prompts become hard to route.

This is especially important for assessments workflows because the user journey naturally moves from discovery to "what does this mean for me?" to "how do I fix it?".

### 4.4 Report Generation and Management Summary Gap

Report generation is uneven.

LDOS PPT generation works:

| Prompt                                                                      | Route                                           | Observed output                                  |
| --------------------------------------------------------------------------- | ----------------------------------------------- | ------------------------------------------------ |
| "Generate a PPT summary report for all Last Date of Support (LDOS) assets." | `Assets (General)` / `ask_cvi_ldos_ai_external` | "Your LDOS PPT has been generated successfully." |

Security/PSIRT management-report generation does not route:

| Prompt                                                                                                                                          | Route    | Observed output           |
| ----------------------------------------------------------------------------------------------------------------------------------------------- | -------- | ------------------------- |
| "Can you create a report for my management, which provides an overview of these critical PSIRTs and also provides remediation recommendations?" | No route | Generic processing error. |

Insight: the system has some report-generation capability, but users will generalize it to other domains. If LDOS can produce a PPT, users will expect PSIRT, advisory, hardening, and remediation reports too.

### 4.5 User-Visible Failure Responses

The largest response-level failure pattern is the generic processing-error response:

```text
An error occurred while processing your request. Trace ID: ...
```

This appears 45 times in both the knowledge graph and the raw `iq-assistant-reports/traces.json` file. All 45 of those traces are currently modeled as unrouted because `agent_name` and `agent_skill` are null. So they are not routed agent execution failures in the graph model, but they are absolutely user-visible failures and should be counted as such.

Generic processing-error responses by routing status:

| Route status | Traces |
| ------------ | -----: |
| Unrouted | 45 |
| Routed | 0 |

This changes the framing: the main failure mode is not routed agent execution. The main failure mode is that no-route outcomes are rendered to users as generic processing errors.

Routed execution failures also appear, but they are a smaller subset. I classified these by scanning routed `Response.output` text for stronger failure phrases such as `temporary system issue`, `data type mismatch`, and `no data available`.

Strong routed failure indicators among non-empty prompts:

| Agent                               |                      Skill | Non-empty prompts | Strong failures | Strong failure rate |
| ----------------------------------- | -------------------------: | ----------------: | --------------: | ------------------: |
| `Assets (General)`                  | `ask_cvi_ldos_ai_internal` |                 2 |               2 |              100.0% |
| `Assessments - Security Advisories` |  `ask_security_assessment` |                15 |               2 |               13.3% |
| `Cases`                             |         `cx_ai_list_cases` |                89 |               2 |                2.2% |

Representative examples:

| Prompt                                                                                                                        | Route                                                           | Failure pattern                                         |
| ----------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------- | ------------------------------------------------------- |
| "Show me my open cases"                                                                                                       | `Cases` / `cx_ai_list_cases`                                    | Temporary system issue retrieving open cases.           |
| "can you show me assets that have a critical vulnarability and those vulnerabilities should be released less then a year ago" | `Assessments - Security Advisories` / `ask_security_assessment` | Data type mismatch for released-in-last-year filtering. |
| "what's here"                                                                                                                 | `Assets (General)` / `ask_cvi_ldos_ai_internal`                 | "No data available at the moment."                      |
| "inevntory"                                                                                                                   | `Assets (General)` / `ask_cvi_ldos_ai_internal`                 | "No data available at the moment."                      |

Insight: the user-visible failure count is much larger than the routed execution-failure count. The 45 generic processing-error outputs are no-route failures in the graph, but they still represent failed user experiences. The routed failures are fewer, but they are concrete fixes. The Security Advisory date/type mismatch looks like a query-generation or schema-handling defect. The Cases issue looks like tool/service availability. The internal LDOS path may need better context or empty-state handling.

## 5. Routing Consistency Findings

I checked for repeated prompts that sometimes route and sometimes do not. There were no non-empty prompts that appeared both routed and unrouted after trimming whitespace.

I also checked for identical prompts routed to different agents. One repeated prompt did route to different agents:

| Prompt                                                                                  | Outcomes                                                                                       |
| --------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------- |
| "list my critical assets that will pass the last date of support in the next 12 months" | `Assets (General)` / `ask_cvi_ldos_ai_external`; `Asset Criticality` / `ask_asset_criticality` |

Insight: routing inconsistency is not the primary observed issue in this dataset. The larger problem is route coverage: prompts either route cleanly or fail to route at all. That said, the LDOS/criticality example shows an ambiguous boundary between lifecycle and criticality semantics.

## 6. Multi-Intent Prompt Analysis

I added a separate pass for multi-intent prompts because they are not the same as ordinary long prompts. A prompt can be multi-intent in two ways:

1. Cross-domain multi-intent: it asks across two primary domains, such as security plus troubleshooting, or security plus asset lifecycle.
2. Same-domain multi-intent: it stays in one domain but asks for multiple substantive topics, such as exposure plus details, remediation, recommendations, or service comparison.

I used a corrected strict definition: a prompt is multi-intent only when it asks for multiple requested outputs or actions. A prompt is not multi-intent merely because it compares two entities, applies multiple filters, or asks one question over multiple objects.

For example, these are single-intent prompts and should not be counted as multi-intent:

- "could you explain me the difference between cisco services and partner services?"
- "Can you tell me more about what devices are affected by advisories?"
- "list my critical assets that will pass the last date of support in the next 12 months"

They mention more than one object or constraint, but each has one user objective.

Strict multi-intent count:

| Metric | Count |
| ------ | ----: |
| Non-empty prompt traces | 383 |
| Distinct normalized non-empty prompts | 156 |
| Multi-intent traces | 9 |
| Distinct multi-intent prompts | 7 |
| Multi-intent share of prompt traces | 2.3% |
| Multi-intent share of distinct prompts | 4.5% |

Breakdown by type and routing outcome:

| Route status | Traces | Distinct prompts |
| ------------ | -----: | ---------------: |
| Routed | 3 | 3 |
| Unrouted | 6 | 4 |
| Total | 9 | 7 |

The important signal is failure concentration. Multi-intent prompts account for only 2.3% of non-empty prompt traces, but 6 of the 9 multi-intent traces did not route. That is a 66.7% no-route rate, compared with 11.7% across all non-empty prompts.

Representative examples:

| Prompt | Traces | Outcome |
| ------ | -----: | ------- |
| "Can you create a report for my management, which provides an overview of these critical PSIRTs and also provides remediation recommendations?" | 2 | No route. |
| "provide me the summary, recommendations and steps to implement" | 2 | No route. |
| "I am seeing exposure for CVE-2023-20198 on device Device_48_0_1_70. Can you confirm that I have exposure to this vulnerability? How can I fix this?" | 1 | Routed to `Assessments - Security Advisories` / `ask_security_assessment`. |
| "Need help troubleshooting a C9300. It is hitting bug CSCwq31287 (CVE-2017-12240) and I'd like information on how to remediate it" | 1 | Routed to `Troubleshooting` / `Enola_Get_CVE`. |
| "Provide me an impact analysis and recommendation to fix it" | 1 | No route. |
| "Which not covered chassis have critical field notice or security vulnerability matches and what are those field notices and security vulnerabilities." | 1 | No route. |
| "list my assets that are past the last date of support milestone and assets that will pass last date of support in the next 12 months" | 1 | Routed to `Assets (General)` / `ask_cvi_ldos_ai_external`. |

Insight: true multi-intent is not high-volume yet, but it is disproportionately likely to expose router gaps. The hardest cases combine multiple requested outcomes such as report plus remediation recommendations, summary plus implementation steps, impact analysis plus fix recommendation, or identification plus details.

This also changes how the routing issue should be framed. The router does not only need better labels for existing single-intent prompts. It needs an explicit strategy for decomposition, chaining, or choosing a lead agent when the user asks for multiple outcomes in one turn.

## 7. App-Specific Interpretation

### assessments

`assessments` is the most important gap surface.

Non-empty prompt stats:

- 46 prompts
- 27 routed
- 19 unrouted
- 41.3% no-route rate

Observed routed destinations include Security Advisories, Assets General, Security Hardening, Configuration, Asset Criticality, and Troubleshooting. That breadth is expected for assessment workflows, but it also means the router must make nuanced cross-domain decisions.

Key `assessments` gaps:

- Security advisory and vulnerability questions that do not route.
- Field notice and bug/FN questions that do not route.
- Follow-up prompts that require conversational context.
- Remediation, summary, and implementation-step synthesis.

### platform-home

`platform-home` has a meaningful no-route rate: 18.6% across non-empty prompts.

The gap is mostly product education and platform help:

- Cisco IQ overview questions.
- Cisco IQ link and API questions.
- Service terminology questions.
- User administration questions.

This suggests a missing product-help/knowledge-base route rather than a weakness in one operational agent.

### asset-explorer

`asset-explorer` has the healthiest non-empty no-route rate at 4.6%, but it still exposes important gaps because it has the largest volume.

Key gaps:

- Field notice questions tied to location.
- Partner-service questions.
- Security report synthesis.
- Some data-connector/product navigation questions.

### admin

`admin` has low volume but a 30.0% no-route rate.

Examples:

- "What are the data sources?"
- "Where is the help menu?"
- "summarize the list of assets that are not covered"

This surface likely needs product-help routing and better cross-linking to asset coverage capabilities.

### support

`support` has no unrouted non-empty prompts in this dataset. Its volume is small, so this should not be over-interpreted.

## 8. Product and Engineering Recommendations

1. Add a product-help route or agent.

   The platform-help/services cluster is too large to leave to operational agents. Users ask about Cisco IQ concepts, navigation, data connectors, services, APIs, help menus, and user administration. A product-help route could answer from documentation or a curated KB.

2. Expand router coverage for security-adjacent language.

   Add evals and routing examples for PSIRT, advisories, vulnerabilities, field notices, FNs, bugs, critical bugs, rebooting devices, remediation, and standards/security terminology. Map these intentionally across Security Advisory, Troubleshooting/FN, Security Hardening, and product-help depending on the prompt.

3. Replace generic no-route errors with useful no-route responses.

   A routing miss should not look like a system failure. The response should explain that the current assistant could not find the right capability, offer examples of supported asks, and preserve the Trace ID for support without making it the main user-facing content. These responses should also be labeled structurally as no-route failures so they are easy to count without scanning response text.

4. Improve follow-up context resolution before routing.

   Prompts like "do i have any of them in my network?" and "recommendation to fix it" need resolved antecedents. The router should receive a context-enriched query or a structured conversation state summary.

5. Treat report generation as a cross-domain capability.

   LDOS PPT generation works. Users now expect the same for PSIRT, advisory, remediation, and management summaries. Either expand report generation beyond LDOS or make the limitation explicit with a useful alternative.

6. Fix concrete routed execution defects.

   Prioritize the Security Advisory date/type mismatch for "released less than a year ago" vulnerability queries, Cases temporary retrieval errors, and the internal LDOS "No data available" path.

7. Build a regression dataset from the 45 no-route prompts.

   Use the no-route prompts as a golden eval set. Add expected route, expected skill, expected fallback behavior, and whether the answer needs product-help, operational data, report generation, or conversational context.

8. Add explicit outcome labels to the KG.

   The current graph stores response text but not answer success, tool error class, router confidence, guardrail reason, user feedback, or tool-call trace details. Adding these would make future gap analysis much more reliable.

9. Add multi-intent decomposition to routing.

   Multi-intent prompts should be decomposed into sub-intents before final routing, or the router should select a lead agent plus secondary tasks. This is most urgent for asset plus security prompts, security plus remediation prompts, and product-service comparison prompts.

## 9. Reflection and Critique

The biggest insight is that "agent gaps" are not only agent gaps. They are product capability gaps, routing taxonomy gaps, and user-experience gaps.

The data strongly supports these conclusions:

- `assessments` has a serious no-route problem for non-empty prompts.
- Security/FN/bug phrasing is under-covered.
- Platform-help and services questions need an owner.
- No-route currently looks like a generic processing error.
- Multi-intent prompts are disproportionately likely to miss routing.
- Routed execution failures exist but are smaller than no-route coverage gaps.

The data does not fully support these conclusions without further evidence:

- Whether routed answers were factually correct.
- Whether users were satisfied.
- Whether capability-boundary answers are acceptable product behavior.
- Whether no-route failures came from router confidence, guardrails, missing agent cards, app-context filtering, or upstream service errors.
- Whether a prompt should be answered by an existing agent or a new product-help capability.

The response-keyword scan also has false positives. Some good answers contain words like "cannot" because they accurately explain technical limitations. I used stronger failure patterns for the routed failure table, but true answer-quality evaluation needs structured labels or human/LLM review.

## 10. Additional Insights Worth Deriving Next

The next round of analysis should add these dimensions:

1. Session-level journey analysis.

   The current graph has trace occurrences, but the most interesting context gaps are conversational. Add or query conversation/session IDs to see how users arrive at no-route follow-ups.

2. Router confidence and candidate route analysis.

   For no-route prompts, capture candidate agents, confidence scores, and rejected skills. This would show whether misses are close calls or true coverage holes.

3. Tool-error taxonomy.

   Add structured error classes for SQL/type errors, MCP/tool timeouts, auth failures, no data, no entitlement, and downstream service issues.

4. Intent clustering with embeddings.

   Keyword clusters are useful but crude. Embedding-based clustering over no-route and low-quality routed responses would reveal latent demand patterns.

5. Answer-quality evaluation.

   Build an eval pass over routed responses to classify: answered, partially answered, refused, no data, tool failure, hallucination risk, and wrong route.

6. Agent-card and skill-description audit.

   The no-route prompts should be compared against current agent cards. If the agent can handle a prompt but the router does not select it, improve descriptions, examples, and skill tags. If no agent should handle it, create a new route or product-help capability.

7. Multi-intent decomposition evals.

   Create an eval set where each prompt has expected sub-intents, lead agent, secondary agent or tool needs, and expected synthesis behavior. Include both cross-domain and same-domain multi-intent examples.

## 11. Key Cypher Queries Used

Overall graph summary:

```cypher
RETURN
  count { (:Question) } AS questions,
  count { (:UIContext) } AS ui_contexts,
  count { (:Agent) } AS agents,
  count { (:Response) } AS responses,
  count { (:Question)-[:ROUTED_TO]->(:Agent) } AS routed,
  count { MATCH (q:Question) WHERE NOT (q)-[:ROUTED_TO]->(:Agent) } AS unrouted
```

Non-empty prompt routing rate by app:

```cypher
MATCH (q:Question)-[:OCCURRED_IN]->(ui:UIContext)
WHERE trim(q.input) <> ""
RETURN ui.app AS app,
       count(q) AS prompts,
       sum(CASE WHEN (q)-[:ROUTED_TO]->(:Agent) THEN 1 ELSE 0 END) AS routed,
       sum(CASE WHEN NOT (q)-[:ROUTED_TO]->(:Agent) THEN 1 ELSE 0 END) AS unrouted,
       round(100.0 * sum(CASE WHEN NOT (q)-[:ROUTED_TO]->(:Agent) THEN 1 ELSE 0 END) / count(q), 1) AS unrouted_pct
ORDER BY unrouted_pct DESC, unrouted DESC
```

No-route prompt examples:

```cypher
MATCH (q:Question)-[:OCCURRED_IN]->(ui:UIContext)
WHERE trim(q.input) <> "" AND NOT (q)-[:ROUTED_TO]->(:Agent)
WITH ui.app AS app, trim(q.input) AS input, count(q) AS traces, collect(DISTINCT q.date) AS dates
RETURN app, input, traces, dates
ORDER BY traces DESC, app, input
```

Same prompt routed to different agents:

```cypher
MATCH (q:Question)-[route:ROUTED_TO]->(a:Agent)
WHERE trim(q.input) <> ""
WITH trim(q.input) AS input,
     collect(DISTINCT a.name) AS agents,
     collect(DISTINCT a.name + " / " + route.skill) AS outcomes,
     count(q) AS traces,
     collect(DISTINCT q.date) AS dates
WHERE size(agents) > 1
RETURN input, traces, dates, outcomes
ORDER BY traces DESC, input
```

Strong routed failure indicators:

```cypher
MATCH (q:Question)-[route:ROUTED_TO]->(a:Agent),
      (q)-[:HAS_RESPONSE]->(r:Response)
WHERE trim(q.input) <> ""
WITH a.name AS agent,
     route.skill AS skill,
     count(q) AS prompts,
     sum(CASE WHEN toLower(r.output) CONTAINS "temporary system issue"
               OR toLower(r.output) CONTAINS "data type mismatch"
               OR toLower(r.output) CONTAINS "no data available"
               OR toLower(r.output) CONTAINS "an error occurred"
              THEN 1 ELSE 0 END) AS strong_failures
RETURN agent,
       skill,
       prompts,
       strong_failures,
       round(100.0 * strong_failures / prompts, 1) AS strong_failure_pct
ORDER BY strong_failures DESC, prompts DESC
```

Strict multi-intent prompt count:

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
OPTIONAL MATCH (q)-[:ROUTED_TO]->(a:Agent)
RETURN count(q) AS multi_intent_traces,
       count(DISTINCT toLower(original)) AS distinct_multi_intent_prompts,
       sum(CASE WHEN a IS NULL THEN 0 ELSE 1 END) AS routed_traces,
       sum(CASE WHEN a IS NULL THEN 1 ELSE 0 END) AS unrouted_traces,
       round(100.0 * sum(CASE WHEN a IS NULL THEN 1 ELSE 0 END) / count(q), 1) AS multi_intent_unrouted_pct
```