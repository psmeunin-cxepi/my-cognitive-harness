# Trace 5 — "cuantos casos tengo abiertos?"

- **Trace ID:** `019e1cda-dfa2-7541-a96a-6f4aac8ca88c`
- **When:** 2026-05-12 15:42 UTC
- **Status:** `success`

## User question

> cuantos casos tengo abiertos?

(Spanish — "how many open cases do I have?")

## UI context (from `inputs.payload.context`)

| Field | Value |
|---|---|
| `app` | `platform-home` (docked assistant) |
| `url` | `/platform-home/overview(assistant:docked/threads)` |
| `filters` | `{}` (none) |
| `language` | **`en-US`** |
| `source` | `prompt-input-bar:send` |

## User feedback

| Field | Value |
|---|---|
| key | `user_feedback` |
| score | `0.0` (thumbs-down) |
| comment | *"Testing for language - prompts should be in english and not in Spanish"* |

## Routing

- `routing_method`: **semantic**
- `agent_name`: **Cases**
- `agent_skill`: `cx_ai_list_cases`
- `is_valid_input`: `true`

## Agent response (excerpt)

> …un **resumen** de algún caso  •  Solicitar una **actualización**, **escalar** un caso o **contactar al ingeniero**.
>
> Dime cómo te gustaría continuar.

The Cases agent answered entirely in Spanish.

## Triage

| Layer | Observation |
|---|---|
| SR routing | Correct — Cases / `cx_ai_list_cases` is the right skill for the question. |
| Cases agent | Mirrored the user's input language (Spanish) despite the UI declaring `language: en-US`. |
| Failure mode | No infra failure; disagreement is over response-language policy. |

## AI Analysis

**No enforced response-language policy.** The Cases agent's prompt likely defers to the LLM's natural behaviour (mirror the user). UI context provides `language: en-US`, but it is not consumed as a constraint on response language.

## AI Recommendations

1. Pick a response-language policy at the platform level. Either:
   - Always reply in `payload.context.language` (UI locale wins over input language), or
   - Always mirror input language (and update guardrails accordingly).
   The current behaviour is non-deterministic.
2. Add an evaluation set covering non-English inputs to catch regressions on both directions (mirroring and blocking) once the policy is enforced.

## Human Review

- **Reviewer:** Philip Smeuninx
- **Reviewed:** 2026-05-14
- **Verdict:** Accepted with edits (dropped the AI's "investigate the Cases agent" recommendation as out of scope for this feedback)
- **JIRA:** Recommendations 1 & 2 (response-language policy + non-English eval set) → [CXP-33285](https://cisco-cxe.atlassian.net/browse/CXP-33285) — created as a single ticket since the eval set is the regression guard for the policy
- **Reviewer Note:** Posted (AI Analysis + AI Recommendations only)
- **Notes:** The original AI rec #2 ("Investigate the Cases agent") was removed from this triage — agent-code investigation belongs inside the JIRA, not here.

<!-- jira: CXP-33285 -->
<!-- ai-note-id: 24738b22-ce84-4d88-8d20-9bf538e83208 -->
<!-- human-review-note-id: 458ee8e3-0fa9-4724-83de-1c8ad53e1d76 -->

