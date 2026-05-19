# IQ Assistant Reports

Reports generated from the CX IQ Semantic Router Neo4j knowledge graph using the [`cx-iq-kg-insights`](../.agents/skills/cx-iq-kg-insights/SKILL.md) skill.

## What's Here

- **Feedback reports** — negative-feedback triage summaries covering a specific time window (e.g. `feedback-report-2026-05-11-to-2026-05-14.md`)
- **Routing / trace data** — raw trace exports and routing analysis snapshots (e.g. `traces.json`, `report.md`)

## How Reports Are Generated

1. Traces are ingested into the Neo4j KG via the [`iq-trace-ingest`](../.agents/skills/iq-trace-ingest/SKILL.md) skill.
2. Feedback and triage data are loaded from `triage/annotation_feedback/` docs using `load_feedback.py`.
3. An agent queries the KG using `cx-iq-kg-insights` Cypher patterns — aggregations on feedback, failure categories, defects, routing decisions, etc.
4. Results are assembled into a report and saved here with a descriptive, date-scoped filename.
