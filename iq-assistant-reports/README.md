# IQ Assistant Reports

Reports generated from the CX IQ Semantic Router Neo4j knowledge graph using the [`cx-iq-kg-insights`](../.agents/skills/cx-iq-kg-insights/SKILL.md) skill.

## How Reports Are Generated

1. Traces are ingested into the Neo4j KG via the [`iq-trace-ingest`](../.agents/skills/iq-trace-ingest/SKILL.md) skill. Feedback and triage data originate from the [`cx-iq-annotation-feedback`](../.agents/skills/cx-iq-annotation-feedback/SKILL.md) skill, which produces per-trace triage docs that are then loaded into the KG.
2. The user asks an agent to produce a report, describing what they are looking for — e.g. a feedback summary for a date range, a failure-category breakdown, defect trends, etc.
3. The agent queries the KG using `cx-iq-kg-insights` Cypher patterns, interprets the results, and assembles them into a report saved here.

## Example Reports

- **Feedback reports** — negative-feedback triage summaries for a specific time window (e.g. failure categories, defects filed, triage verdicts)
- **Trace reports** — routing analysis snapshots covering agent distribution, no-route patterns, and input trends
