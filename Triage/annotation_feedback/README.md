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

## Current batch — pulled 2026-05-14

Source queue: **`negative-user-feedback`** · workspace **`cx-iq-prod`** · all rows project **`ciq-agents-prod-usw2`** unless noted.

| # | Trace ID | Project | UI app | User question | SR routed to (skill) | `is_valid_input` | Failure layer | File |
|---|---|---|---|---|---|---|---|---|
| 07 | `019e1d4f-109c-73a2-9ad7-e8107e65a0b7` | `ciq-agents-prod-euc1` | `assessments` | how can i fix Cisco 4000 Series ISR affected by CVE-2017-12229? | `Enola_Get_CVE` | true | UI / downstream rendering (duplicate message) | [trace-07-cve-duplicate.md](trace-07-cve-duplicate.md) |
| 10 | `019e2192-0127-7c40-8727-15f6db37eaab` | `ciq-agents-prod-usw2` | `asset-explorer` | Review asset inventory, ignore LDOS gear; report IOS release / hostnames / model / MGT IP | `ask_cvi_ldos_ai_external` | true | LDOS agent — column content (`Management Ip`, `Current Ios Code Release`) | [reviewed/trace-10-ldos-asset-inventory-missing-data.md](reviewed/trace-10-ldos-asset-inventory-missing-data.md) |
| 11 | `019e21a7-b407-7d73-b1aa-680ccfc7f1bf` | `ciq-agents-prod-usw2` | `asset-explorer` | Wireless APs unique SKUs, JSON-only with strict schema | `ask_cvi_ldos_ai_external` | true | LDOS agent — instruction-following (returned prose, not JSON) | [reviewed/trace-11-ldos-json-instruction-ignored.md](reviewed/trace-11-ldos-json-instruction-ignored.md) |
| 12 | `019e21de-f21b-7fc0-9720-4b027970988e` | `ciq-agents-prod-usw2` | `platform-home` | Review FN74383 — list of impacted APs and versions | `cx_ai_fn_q_a` | false (FN guardrail) | Generic error rendering of FN guardrail veto | [reviewed/trace-12-fn74383-guardrail-error.md](reviewed/trace-12-fn74383-guardrail-error.md) |
| 13 | `019e2209-528e-7913-8a93-b3f5b58f1d7f` | `ciq-agents-prod-usw2` | `platform-home` | Workaround for fn72424 | `cx_ai_fn_q_a` | false (FN guardrail) | Generic error rendering of FN guardrail veto | [reviewed/trace-13-fn72424-workaround-guardrail-error.md](reviewed/trace-13-fn72424-workaround-guardrail-error.md) |
| 14 | `019e2242-0343-7f50-8d91-e7947cc44697` | `ciq-agents-prod-usw2` | `asset-explorer` | Excel of assets going EOS in 2025–2026, include business unit | `ask_cvi_ldos_ai_external` | true | LDOS agent — `Business Entity` column blank, per-serial duplication | [reviewed/trace-14-ldos-eos-excel-business-unit-blank.md](reviewed/trace-14-ldos-eos-excel-business-unit-blank.md) |
| 15 | `019e23f0-bc56-7f61-9287-69278df47fc8` | `ciq-agents-prod-usw2` | `asset-explorer` | Field Notice 72464 の影響範囲をまとめて (Japanese) | `cx_ai_fn_q_a` | false (FN guardrail) | Generic error rendering of FN guardrail veto + Japanese-prompt / English-error locale mismatch | [reviewed/trace-15-fn72464-japanese-guardrail-error.md](reviewed/trace-15-fn72464-japanese-guardrail-error.md) |

Already reviewed (in [`reviewed/`](./reviewed/)): traces 01, 02, 03, 04, 05, 06, 07, 08, 09, 10, 11, 12, 13, 14, 15.

---

## Current batch — pulled 2026-05-20

Source queue: **`negative-user-feedback`** · workspace **`cx-iq-prod`** · project **`ciq-agents-prod-usw2`** unless noted.

| # | Trace ID | Project | UI app | User question (excerpt) | SR routed to (skill) | Failure layer | File |
|---|---|---|---|---|---|---|---|
| 16 | `019e25ca-3d4e-7da2-b410-7a29a90c1d94` | `ciq-agents-prod-euc1` | `admin` | Export per-device SA executive report | `ask_security_assessment` | SA agent export error | [trace-16-sa-export-error.md](trace-16-sa-export-error.md) |
| 17 | `019e25f8-62bc-7cf1-b0fb-f2c868e66a53` | `ciq-agents-prod-usw2` | `platform-home` | (cases list request) | `cx_ai_case_list` | Unknown — no comment | [trace-17-cases-list.md](trace-17-cases-list.md) |
| 18 | `019e2613-5064-7e50-8ba0-f5660a172543` | `ciq-agents-prod-usw2` | `assessments` | how many assets are impacted by FN74186 | `ask_cvi_ldos_ai_external` | FN guardrail block → error string | [trace-18-fn74186-guardrail-block.md](trace-18-fn74186-guardrail-block.md) |
| 19 | `019e2824-005e-7db0-b131-00fa40d0d1c1` | `ciq-agents-prod-usw2` | `asset-explorer` | mostre a config do device (Portuguese) | *(rejected)* | Agent selection `is_valid=False` → error string | [trace-19-portuguese-config-request.md](trace-19-portuguese-config-request.md) |
| 20 | `019e31dd-fc39-78d1-85a7-56c9f759844c` | `ciq-agents-prod-usw2` | `assessments` | list of security hardening rules checked | `ask_security_hardening` | SH agent — response flagged inaccurate | [trace-20-sh-rules-list.md](trace-20-sh-rules-list.md) |
| 21 | `019e3be9-7d77-7b23-86dc-abede075870f` | `ciq-agents-prod-usw2` | `admin` | Dame un resumen de LDOS (Spanish) | `ask_cvi_ldos_ai_external` | LDOS agent — English response to Spanish question | [trace-21-spanish-ldos-english-response.md](trace-21-spanish-ldos-english-response.md) |
| 22 | `019e3bf2-c94a-7d93-8c41-28133a62df2f` | `ciq-agents-prod-usw2` | `admin` | LDOS próximos 12 meses (Spanish) | `ask_cvi_ldos_ai_external` | LDOS agent — English response to Spanish question | [trace-22-spanish-ldos-english-response-2.md](trace-22-spanish-ldos-english-response-2.md) |
| 23 | `019e3bfa-cca0-79c0-876e-1cd8ef79a96f` | `ciq-agents-prod-usw2` | `admin` | hazme una presentación (Spanish PPT) | *(rejected)* | Agent selection `is_valid=False` + guardrail LLM errors | [trace-23-ppt-request-guardrail-error.md](trace-23-ppt-request-guardrail-error.md) |
| 24 | `019e3bea-6e05-7c53-9738-344aa5d48254` | `ciq-agents-prod-usw2` | `platform-home` | como puedo identificar si mis AP estan afectados (Spanish) | `cx_ai_fn_q_a` | Unknown — no comment | [trace-24-troubleshooting-ap-affected.md](trace-24-troubleshooting-ap-affected.md) |
| 25 | `019e3c02-6ef6-7fb3-9f30-765a7b42b3df` | `ciq-agents-prod-usw2` | `admin` | genera una presentación LDOS (Spanish PPT) | `ask_cvi_ldos_ai_external` | LDOS agent — English + no PPT export | [trace-25-ldos-ppt-english-no-export.md](trace-25-ldos-ppt-english-no-export.md) |
| 26 | `019e3bf4-f48c-7732-8f26-0a9d93618c43` | `ciq-agents-prod-usw2` | `platform-home` | RMA creation (Spanish) | `cx_ai_case_create` | Cases agent — inconsistent Spanish terminology | [trace-26-cases-rma-spanish-terminology.md](trace-26-cases-rma-spanish-terminology.md) |
| 27 | `019e3c12-b2b4-7ae2-b373-171efdc0baa9` | `ciq-agents-prod-usw2` | `admin` | Case creation info (Spanish) | `cx_ai_case_create` | Cases agent — duplicate response | [trace-27-cases-duplicate-response.md](trace-27-cases-duplicate-response.md) |
| 28 | `019e3c22-23d9-71b3-bb81-7abd2b2f427e` | `ciq-agents-prod-usw2` | `admin` | weather in Mexico City (Spanish) | *(rejected)* | Agent selection `is_valid=False` + guardrail LLM errors | [trace-28-weather-out-of-scope-error.md](trace-28-weather-out-of-scope-error.md) |
| 29 | `019e3c28-070f-7840-b0c2-8f810e45671a` | `ciq-agents-prod-usw2` | `admin` | severity escalation (Spanish) | `buff_mcp` | Cases agent — English→Spanish replacement visible + terminology | [trace-29-cases-severity-english-then-spanish.md](trace-29-cases-severity-english-then-spanish.md) |
| 30 | `019e3c3f-b4c9-7051-bd25-a4773ecd0261` | `ciq-agents-prod-usw2` | `admin` | PPT vulnerabilities summary (Spanish) | *(rejected)* | Agent selection `is_valid=False` + guardrail LLM errors | [trace-30-ppt-vulnerabilities-error.md](trace-30-ppt-vulnerabilities-error.md) |
| 31 | `019e3dea-3ec6-7d92-bda4-5e9b5b094e48` | `ciq-agents-prod-usw2` | `asset-explorer` | How many devices are vulnerable to security advisories? | `ask_security_assessment` | SA agent — retrieval failure | [trace-31-sa-device-count-retrieval-failure.md](trace-31-sa-device-count-retrieval-failure.md) |

### Cross-cutting patterns in this batch

1. **Spanish-language testing session (T021–T030)** — 10 of 16 traces appear to be from a single user testing CX IQ in Spanish on 2026-05-18, all from the `admin` app on the `data-connector` page. The `context.language` field is `en-US` for all (browser locale, not input language).

2. **LDOS agent does not respond in the user's input language** (T021, T022, T025) — the Assets (General) agent consistently responds in English when the user writes in Spanish. The data returned is correct, but prose and table headers remain English. Whether the agent uses `context.language` or should infer from the question text needs investigation.

3. **PPT/presentation generation is unsupported — inconsistent handling** (T023, T025, T030) — presentation export is not a supported capability. T023 and T030: `agent_selection` correctly returns `is_valid=False`. T025: `agent_selection` returns `is_valid=True` and routes to LDOS (question combines valid data request with unsupported export). All result in user confusion.

4. **Guardrail LLM `RetryError/SdkException`** (T023, T028, T030) — both `semantic_router_nemo_guardrail_input` and `field_notice_nemo_guardrail_input` errored with `RetryError/SdkException` in multiple traces during the same session window. Likely a transient infrastructure issue with the NeMo guardrails service.

5. **Cases agent handles Spanish better but has quality issues** (T026, T027, T29) — the Cases agent responds in Spanish (unlike LDOS), but: inconsistent terminology (T026), duplicate responses (T027), and visible English→Spanish replacement during streaming (T029).

6. **Generic error strings for out-of-scope rejections** (T019, T023, T028, T030) — when `agent_selection` returns `is_valid=False`, the user sees "An error occurred while processing your request" instead of an informative out-of-scope message. Same pattern as batch 1 traces 03, 04, 06, 08, 12, 13, 15.

7. **FN guardrail false positive** (T018) — FN guardrail blocked "how many assets are impacted by FN74186" on the FN detail page. Same class as batch 1 traces 12, 13, 15.

---

## Previous batch — pulled 2026-05-14

### Cross-cutting patterns in this pull

- **Generic error rendering of deliberate guardrail vetoes** (traces 12, 13, 15) — same class as already-reviewed traces 03, 04, 06, 08. The FN-specific guardrail correctly identifies "give me workaround / impact list / impact summary for FN X" as outside its allowed categories (count-based or general-by-ID definitions only), but the user only sees `"An error occurred while processing your request."`. Trace 13's reviewer comment explicitly says CIQ "should be able to answer the Field Notice question" — confirming the user expectation gap on top of the rendering bug. Trace 15 adds an English-error-on-Japanese-prompt locale mismatch.
- **LDOS agent content / instruction-following gaps** (traces 10, 11, 14) — routing and guardrails are clean and the agent returns a rendered table, but the trace shows column-content defects (10: wrong values in `Management Ip` / `Current Ios Code Release`), instruction non-compliance (11: JSON-only request answered in prose), and missing/blank columns the user explicitly asked for (14: `Business Entity` blank for every visible row). Each requires investigation in `cvi-ldos-ai`; no agent-code recommendations are made from the SR trace alone.

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
               │   1. JIRA?      → skill drafts + creates via Jira MCP
               │   2. AI note?   → skill POSTs /feedback key=note
               │                     (AI Analysis + Recommendations only)
               │   3. Human Review → skill fills the section + posts it
               │                     as a second /feedback key=note
               │   4. Move        → reviewed/trace-NN-<slug>.md
               │   5. Mark done   → POST /annotation-queues/status/{qr}
               ▼
   reviewed/trace-NN-<slug>.md  +  Jira ticket(s)  +  2 LangSmith notes
   (queue run flipped to "Completed" so it stops re-surfacing)
```

Five phases, each gated by an explicit human checkpoint:

1. **Pull** — fetch every run currently in the queue, plus its children and feedback rows, into `_raw/`.
2. **Assess** — for each trace, write a per-trace doc with **AI Analysis** and **AI Recommendations** grounded only in that trace's payload. These two sections stay pure model output.
3. **Review** — human reads the docs and pushes back on anything unsupported.
4. **JIRA first** — for each trace flagged for further investigation, the human confirms; the skill drafts and (with consent) creates the ticket via the Jira MCP. The JIRA key is recorded in the doc footer (`<!-- jira: CXP-XXXXX -->`) and in the `## Human Review` section — **never** added to `## AI Recommendations`.
5. **Post + archive + close** — the AI assessment is posted to LangSmith as a Reviewer Note, then the `## Human Review` block is posted as a second Reviewer Note (carrying the JIRA refs), the doc is moved into [`reviewed/`](./reviewed/), and the queue run is marked completed via `POST /annotation-queues/status/{queue_run_id}` so the next batch pull doesn't re-surface it.

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
5. **AI Analysis** — what the trace shows, evidence-grounded. Pure model output — no human edits, no JIRA refs.
6. **AI Recommendations** — actionable items; for generic-error responses this is a single line: *"Open a JIRA for further investigation."* Pure model output — **never** carries `Tracking:` lines or JIRA links.
7. **Human Review** — audit trail of the human's verdict, the JIRAs created (mapped to each AI recommendation), and the reviewer-note posting decision; populated by the skill in step 8 just before the doc is moved to `reviewed/`. **All JIRA references live here**, not in AI Recommendations.

Once posted, the doc is moved to `reviewed/` and footer comments record the LangSmith feedback ids of both posted notes plus the JIRA keys:

```html
<!-- jira: CXP-XXXXX, CXP-YYYYY -->
<!-- ai-note-id: <uuid> -->
<!-- human-review-note-id: <uuid> -->
```

Either note can be retracted later via `DELETE /feedback/<uuid>`.

---

## Reviewer Notes — how they appear in LangSmith

Reviewer Notes are stored as `feedback` rows with `key='note'` on the **root run**. Multiple notes coexist (the UI appends; it does not overwrite), so AI-posted notes never displace human-authored ones.

The skill posts **two** notes per reviewed trace:

1. **AI Triage note** — AI Analysis + AI Recommendations, posted before the human verdict.
2. **Human Review note** — the `## Human Review` block (verdict, JIRAs created, reviewer name/date), posted after the human signs off. This is what gives reviewers in the queue UI a one-glance answer to "what was decided?".

Both are prefixed with:

> `**AI Triage** — auto-posted from cx-iq-annotation-feedback skill`

so reviewers can distinguish them from human-authored notes at a glance.

The AI note must be posted with `feedback_source: {"type": "app"}` — without it, notes are stored on the run but stay invisible in the annotation queue UI.
