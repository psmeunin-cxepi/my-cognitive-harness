# Trace 1 — "Add a participant to a case's contact list"

- **Trace ID:** `019e1921-64a2-79c2-8111-6b8c2a1b2079`
- **When:** 2026-05-11 22:21 UTC
- **Status:** `success` (turn completed)

## User question

> Add a participant to a case's contact list

## UI context (from `inputs.payload.context`)

| Field | Value |
|---|---|
| `app` | `platform-home` |
| `url` | `/platform-home/overview(assistant:fullscreen/threads)` |
| `filters` | `{}` (none) |
| `language` | `en-US` |
| `source` | **`ai-assistant:suggestion`** |

The user was on the **platform home page** with **no case context** and clicked a **suggested prompt** surfaced by the AI assistant ("Add a participant to a case's contact list").

## User feedback

| Field | Value |
|---|---|
| key | `user_feedback` |
| score | `0.0` (thumbs-down) |
| comment | *(none)* |

## Routing

- `routing_method`: **static**
- `agent_name`: **Cases**
- `agent_skill`: `buff_mcp`

Static routing fired correctly — the suggested prompt is hard-mapped to the Cases agent.

## Agent response (verbatim)

The `execute_agent.outputs.answer` field is **literally**:

> ` that case.`
> `If not, please also share the **case number**.`
>
> `Once you provide the email (and case number if needed), I'll take care of the rest.`

The reply begins mid-sentence — leading space, no antecedent — so the first line (` that case.`) is unintelligible to the user. The asks for an email and a case number are correct in intent, but the message is malformed.

## Triage

| Layer | Observation |
|---|---|
| SR routing | Correct. |
| Cases agent | Asked for the missing parameters (email + case number) in a single turn — correct in intent. |
| Agent response wording | **Malformed.** The `answer` payload starts with ` that case.` — the leading sentence/clause is missing. The trace shows only the final concatenated string; whether the truncation happened during response construction inside the Cases agent or during streaming/assembly is not observable from this SR trace. |
| Failure mode | Combined: (a) UX — inactionable suggestion on home page; (b) response-quality — malformed opening that reads as nonsense. |

## AI Analysis

Two distinct issues compound here:

1. **UX issue with the suggested-prompts feature.** The home-page assistant surfaced "Add a participant to a case's contact list" as a one-click suggestion, but the home-page context provides no case number and no participant email. Clicking the shortcut therefore guarantees a parameter-elicitation turn.
2. **Malformed agent response.** Independently of the UX issue, the response the user saw begins with ` that case.` — a fragment with no preceding clause. This makes the elicitation read as nonsense even though the intent (ask for email + case number) is correct.

The thumbs-down is consistent with both factors.

## AI Recommendations

*Tracking:*
- Recommendation 1 → [CXP-33092](https://cisco-cxe.atlassian.net/browse/CXP-33092)
- Recommendation 3 → [CXP-33091](https://cisco-cxe.atlassian.net/browse/CXP-33091)

1. **Reconsider the suggested-prompt catalog on `platform-home`.** Action-oriented prompts that require parameters (a case number, a device, a CVE) shouldn't appear unless the platform can either (a) inject those parameters from context or (b) hand the user a richer form rather than a chat prompt.
2. **If keeping the suggestion**, gate it on prior context — only show "Add a participant to a case's contact list" when the user has recently viewed or created a case in the session.
3. **Open a JIRA to investigate the malformed response.** The `execute_agent.answer` literally begins with ` that case.` with no preceding clause. The SR trace shows only the final concatenated string, so the cause (Cases agent response construction vs. streaming/assembly) requires investigation outside this trace.

## Human Review

- **Reviewer:** Philip Smeuninx
- **Reviewed:** 2026-05-13
- **Verdict:** Accepted as-is
- **JIRA:** Created — [CXP-33092](https://cisco-cxe.atlassian.net/browse/CXP-33092) (recs 1 & 2, suggestion catalog), [CXP-33091](https://cisco-cxe.atlassian.net/browse/CXP-33091) (rec 3, malformed response)
- **Reviewer Note:** Posted (AI Analysis + AI Recommendations only)
- **Notes:** Recs 1 and 2 were merged into a single JIRA since they are the same UX concern.

<!-- jira: CXP-33092, CXP-33091 -->
<!-- ai-note-id: 3ba27990-c6b2-491b-9b1a-5debb63aeb84 -->

