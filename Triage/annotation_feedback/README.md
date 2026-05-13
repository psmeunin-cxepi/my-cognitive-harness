# Annotation Feedback Triage

This folder is the working area for triaging **negative user feedback** (thumbs-down) traces from the CX IQ LangSmith **`negative-user-feedback`** annotation queue.

The full process is owned by the [`cx-iq-annotation-feedback`](../../.agents/skills/cx-iq-annotation-feedback/SKILL.md) agent skill. This README is the human-facing entry point: what lives here, how to kick off a batch, and what to do once the AI has produced its assessment.

---

## What lives here

| Path | Purpose |
|---|---|
| `_raw/<trace-id>.json` | Untouched LangSmith payloads (root + children + feedback). Source of truth — never edit. |
| `trace-NN-<slug>.md` | Per-trace assessment doc **pending human review / posting**. |
| `reviewed/trace-NN-<slug>.md` | Per-trace assessment doc **already posted as a Reviewer Note** on LangSmith. |
| `README.md` | This file — process. The current batch index is rebuilt by the skill on each run. |

---

## High-level process

```
┌─────────────────────────────┐
│ LangSmith annotation queue  │
│ "negative-user-feedback"    │
└──────────────┬──────────────┘
               │  (skill: pull queue + raw traces)
               ▼
        _raw/<trace-id>.json
               │
               │  (skill: per-trace inspection → assessment)
               ▼
     trace-NN-<slug>.md   ◄── human review
               │
               │  per trace, human confirms each step:
               │
               │   1. JIRA?    → skill drafts + creates via Jira MCP
               │                   → JIRA key written into the doc
               │   2. Note?    → skill POSTs /feedback key=note
               │                   (note includes JIRA link if any)
               │   3. Move     → reviewed/trace-NN-<slug>.md
               ▼
   reviewed/trace-NN-<slug>.md  +  Jira ticket  +  LangSmith reviewer note
```

Five phases, each gated by an explicit human checkpoint:

1. **Pull** — fetch every run currently in the queue, plus its children and feedback rows, into `_raw/`.
2. **Assess** — for each trace, write a per-trace doc with **AI Analysis** and **AI Recommendations** grounded only in that trace's payload.
3. **Review** — human reads the docs and pushes back on anything unsupported.
4. **JIRA first** — for each trace flagged for further investigation, the human confirms; the skill drafts and (with consent) creates the ticket via the Jira MCP, then writes the JIRA key back into the per-trace doc. The human can also choose draft-only and create it manually.
5. **Post + archive** — the AI assessment is posted to LangSmith as a Reviewer Note (`feedback` row with `key='note'`) on the root run, including the JIRA link if one exists, then the doc is moved into [`reviewed/`](./reviewed/).

---

## How to use the skill

In a Copilot / Claude Code chat in this repo, ask for one of:

- **Refresh the batch** — *"Pull the latest negative-user-feedback queue and triage it."* The skill pulls all runs currently in the queue, writes per-trace docs, and produces a fresh batch index in this folder.
- **Re-triage a single trace** — *"Re-triage trace `<id>` from the annotation queue."* Refreshes only one `_raw/` file and rewrites only that per-trace doc.
- **Post the reviewed batch** — *"Post the AI assessment as Reviewer Notes for the traces I've reviewed."* The skill walks the pending docs, asks per trace (or accepts a blanket answer) which sections to post, calls `POST /feedback`, and moves each posted doc into `reviewed/`.
- **Draft JIRAs** — *"Draft the JIRAs for the traces flagged for further investigation."* Skill outputs ticket title + body; you paste.

The skill enforces the discipline rules (evidence-only claims, no speculative agent fixes, JIRA-only recommendation for generic error responses). See [`.agents/memory/feedback-triage-discipline.md`](../../.agents/memory/feedback-triage-discipline.md) for the codified rules and [`.agents/skills/cx-iq-annotation-feedback/SKILL.md`](../../.agents/skills/cx-iq-annotation-feedback/SKILL.md) for the full workflow.

---

## What the AI never does on its own

- Does not post a Reviewer Note without per-trace human confirmation.
- Does not create a JIRA without per-trace human confirmation.
- Does not delete or modify existing human-authored feedback / notes on LangSmith.
- Does not modify files under `_raw/` after the initial pull.
- Does not propose code changes to downstream agents based on a Semantic Router trace alone — those investigations belong in a JIRA opened against the agent owner.

---

## Per-trace doc structure

Each `trace-NN-<slug>.md` follows a fixed layout:

1. Header (trace id, project, timestamp, queue link)
2. UI context (app, url, language, filters)
3. Routing decision
4. User feedback (verbatim quote + score)
5. **AI Analysis** — what the trace shows, evidence-grounded
6. **AI Recommendations** — actionable items; for generic-error responses this is a single line: *"Open a JIRA for further investigation."*
7. **Human Review** — audit trail of the human's verdict, the JIRAs created (or skipped), and the reviewer-note posting decision; populated by the skill in step 8 just before the doc is moved to `reviewed/`.

Once posted, the doc is moved to `reviewed/` and a footer comment records the LangSmith feedback id of the posted note (`<!-- ai-note-id: <uuid> -->`) so it can be retracted later via `DELETE /feedback/<id>`.

---

## Reviewer Notes — how they appear in LangSmith

Reviewer Notes are stored as `feedback` rows with `key='note'` on the **root run**. Multiple notes coexist (the UI appends; it does not overwrite), so AI-posted notes never displace human-authored ones.

AI-posted notes are always prefixed with:

> `**AI Triage** — auto-posted from cx-iq-annotation-feedback skill`

so reviewers can distinguish them at a glance.
