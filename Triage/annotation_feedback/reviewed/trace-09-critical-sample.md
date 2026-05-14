# Trace 9 — "all devices with one or more critical security advisory"

- **Trace ID:** `019e2097-3d9d-7712-b961-89e802471ad0`
- **When:** 2026-05-13 09:07 UTC
- **Status:** `success`

## User question

> tell me the names of all devices that have one or more critical security advisory on them

## UI context (from `inputs.payload.context`)

| Field | Value |
|---|---|
| `app` | `platform-home` |
| `url` | `/platform-home/overview(assistant:fullscreen/threads)` |
| `filters` | `{}` (none) |
| `language` | `en-US` |
| `source` | `prompt-input-bar:send` |

## User feedback

| Field | Value |
|---|---|
| key | `user_feedback` |
| score | `0.0` (thumbs-down) |
| comment | *(none)* |

## Routing

- `routing_method`: **semantic**
- `agent_name`: **Assessments – Security Advisories**
- `agent_skill`: `ask_security_assessment`
- `is_valid_input`: `true`

## Agent response (excerpt)

> There are **1,383 devices** in your environment with one or more **Critical** security advisories. Below is a sample of the affected devices:
>
> | Hostname | Product Name | Serial Number |
> |---|---|---|
> | KLANSW-9248L-1 | Cisco Catalyst 9200L-48T-4X Switch | SIMDEMONC45 |
> | … | … | … |
>
> *(table of ~11 rows, no caption naming the truncation, no link to the full list)*

## Triage

| Layer | Observation |
|---|---|
| SR routing | Correct. |
| Security Advisories agent | Counted correctly (1,383 devices) and rendered a small representative table. |
| Failure mode | The user asked for **names of all** devices and received a sample of ~11. No caption like "showing 11 of 1,383", no "view all" / "export" affordance, no reason given for the truncation. |

## AI Analysis

**UX truncation without affordance.** The Security Advisories skill silently caps the device list at a fixed sample size when the result is large. The user can't tell whether they're being shown a representative slice or a deterministic truncation, and they have no path to the full list from inside the assistant.

There is also a deeper question: "tell me the names of all devices" is a list-export intent. The chat assistant is the wrong surface for a 1,383-row list; the right surface is Asset Explorer or an export.

## AI Recommendations

1. **Investigate the Security Advisories agent (`ask_security_assessment`)** to determine where the device list is being truncated and whether the agent is aware of the total result size when it renders the table. The fix — declaring `total / shown / next` and adding a "view all" affordance — requires changes in the agent code that cannot be specified without that review.
2. Once the truncation point is known, declare `total / shown / next` for sampled responses. A header like "*Showing 11 of 1,383 affected devices, ranked by [criticality]*" is the minimum.
3. Provide an explicit "view all" affordance that deep-links into Asset Explorer with the predicate pre-applied (e.g., `securityAdvisoryCount>=1&severity=Critical`).
4. Consider whether "give me all" intents should be detected at the SR or agent layer and answered with the count + an export prompt rather than a token-capped sample. Phrasings like "all", "every", "list everything", or numbers explicitly larger than 50 are signals for this branch.

## Human Review

- **Reviewer:** Philip Smeuninx
- **Reviewed:** 2026-05-14
- **Verdict:** Accepted with edits — agreed the response should be enhanced. The agent should explicitly indicate there are too many devices to show in the thread and suggest an alternative (e.g. download as Excel file).
- **JIRA:**
  - Recommendations 1, 2, 3 → [CXP-33287](https://cisco-cxe.atlassian.net/browse/CXP-33287) — Bug against the Security Advisories agent (truncation behaviour + caption + view-all/export affordance).
  - Recommendation 4 → [CXP-33288](https://cisco-cxe.atlassian.net/browse/CXP-33288) — Story to author a behavioural spec for list-export intents and large result sets (cross-agent contract under `engineering_excellence_q4/agent_behavioural_spec/`).
- **Reviewer Note:** Posted (AI Analysis + AI Recommendations only)
- **Notes:** Two tickets so the agent fix and the cross-agent spec can move independently; linked via "Relates".

<!-- jira: CXP-33287 -->
<!-- jira: CXP-33288 -->
<!-- ai-note-id: 9b4d9404-4c11-42d5-aca8-8623968b6a8f -->
<!-- human-review-note-id: 9b9736ad-aa91-42b3-bcb3-0b4b4fed46ba -->

