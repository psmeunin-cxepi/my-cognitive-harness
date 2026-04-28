> **Agent:** Security Advisory
> **Repo:** [`CXEPI/risk-app`](https://github.com/CXEPI/risk-app)
> **Jira:** _to be created_

# Triage: `checkId` Context Switch — Agent Answers About Wrong Vulnerability

**Trace ID:** `019db4bd-f9fd-7530-ba97-5d9ea0a775a7`  
**Workspace:** nprd (`cx-iq-nprd`)  
**Agent:** Security Assessment Agent  
**Model:** mistral-medium-2508  
**Date:** 2026-04-22  
**User question:** "I don't understand what this vulnerability talks about, can you give me more details?"

---

## Summary

The agent answered about the **wrong vulnerability**. The user navigated to `psirt_id = 3065` ("Cisco IOS XE Software Privilege Escalation Vulnerabilities") but the agent explained `psirt_id = 2943` ("RADIUS Protocol Spoofing Vulnerability (Blast-RADIUS)") because it resolved "this vulnerability" from conversation history instead of the current page context.

---

## Evidence

### What the UI context sent

The runtime context injected into the system prompt:

```
checkId: ["3065"]
URL: /assessments/security-advisories/3065
```

`checkId` maps to `psirt_id` in the database. The user was viewing advisory `psirt_id = 3065`.

### What the earlier trace (same conversation) returned

The prior query ("List me the top 5 security advisories with most impact") returned:

| `psirt_id` | `headline_name` | `impacted_assets_count` |
|---|---|---|
| **2943** | RADIUS Protocol Spoofing Vulnerability (Blast-RADIUS): July 2024 | 167 |
| 3178 | Cisco IOS, IOS XE, Secure Firewall ... IKEv2 DoS Vulnerabilities | 118 |
| 2586 | Cisco IOS and IOS XE Software SSH DoS Vulnerability | 117 |
| **3065** | **Cisco IOS XE Software Privilege Escalation Vulnerabilities** | 116 |
| 1894 | Cisco IOx Application Framework Arbitrary File Creation Vulnerability | 107 |

The user then clicked into the **4th-ranked** advisory (psirt_id 3065), but the agent defaulted to the **1st** (psirt_id 2943) because Blast-RADIUS dominated conversation history.

### What the agent did

1. **LLM run 1** — chose `mcp_rag_data` tool with query: `"RADIUS Protocol Spoofing Vulnerability (Blast-RADIUS): July 2024"`. This text was extracted from conversation history, not from `checkId`.
2. **RAG retrieval** — returned the Blast-RADIUS document from Weaviate (score 0.995). The chunk metadata shows `"id": {"ids": ["2943"]}` — psirt_id 2943, not 3065.
3. **LLM run 2** — generated a detailed explanation of CVE-2024-3596 (Blast-RADIUS), including "167 devices in your inventory are flagged as potentially vulnerable."

The user received a correct explanation of the **wrong** advisory.

---

## Root Cause — Three layers of failure

### 1. No system prompt instruction to prioritize page context over conversation history

The context filter is appended to the system prompt as:

```
The user is currently viewing a page with the following active context filters.
Apply these as default query filters unless the user explicitly asks otherwise:
- filters: {'checkId': ['3065'], 'sortBy': ['vulnerabilityStatus'], 'sortOrder': ['desc']}
```

But there is no instruction telling the LLM:
- That `checkId` = `psirt_id` in the database
- That when the user says "this vulnerability", it refers to the advisory identified by `checkId`, not the last-mentioned advisory in conversation history
- That a new `checkId` value signals a **context switch** — the user navigated to a different page

### 2. No programmatic resolution of `checkId` before the LLM sees it

The `_format_context_filter()` function in `security_assessment_agent_impl.py` (lines 413–444) formats `checkId: ["3065"]` as raw text into the system prompt. The LLM receives a numeric ID with no label. It has no way to know that `3065` = "Cisco IOS XE Software Privilege Escalation Vulnerabilities" without first doing a SQL lookup — which it did not attempt.

A programmatic resolution step (before the LLM loop) could:
- Query `SELECT headline_name FROM bulletins WHERE psirt_id = 3065`
- Inject the resolved name into the system prompt: *"The user is viewing: Cisco IOS XE Software Privilege Escalation Vulnerabilities (psirt_id 3065)"*

### 3. RAG tool has no metadata filter path

The `chat_with_rag` MCP tool on `main` (SHA `1f20928`) accepts only `query: str` and `collection_name: Optional[str]`. There is no `filters` or `where` parameter. Even if the LLM attempted to use `checkId`, it could not pass `psirt_id = 3065` as a structured Weaviate filter.

The RAG collection stores `advisory_id` (string), `cve_id`, and `headline_name` as object properties. The numeric `psirt_id` is nested inside `body.id.ids[]`, not as a top-level searchable property. A Weaviate `where` filter on `psirt_id` would require adding it as an indexed property to the collection schema.

---

## Fix Recommendations

### Fix A: Programmatic `checkId` → advisory name resolution (recommended)

In `security_assessment_agent_impl.py`, before the agent loop:

1. Extract `checkId` from `context_filter.filters`
2. Query `SELECT headline_name, advisory_id FROM bulletins WHERE psirt_id = <checkId>` via Trino
3. Inject the resolved advisory identity into the system prompt:

```
The user is currently viewing advisory: "Cisco IOS XE Software Privilege Escalation Vulnerabilities"
(psirt_id: 3065, advisory_id: cisco-sa-iosxe-priv-esc-xxxxx).
When the user says "this vulnerability" or "this advisory", they mean this one.
```

This removes the ambiguity before the LLM even runs.

### Fix B: System prompt context priority instruction

Add to the system prompt:

```
<context_priority>
When the user references "this vulnerability", "this advisory", or similar deictic
expressions, resolve them using the active `checkId` context filter — NOT from
conversation history. The `checkId` value maps to `psirt_id` in the bulletins/psirts
tables. If you need the advisory name, query it first before answering.

A new `checkId` value signals the user navigated to a different page. Treat the question
as a new topic scoped to that advisory, even if conversation history discusses a
different one.
</context_priority>
```

### Fix C: Add metadata filter support to RAG tool

Extend `chat_with_rag` to accept a `filters` parameter that maps to a Weaviate `where` clause. Add `psirt_id` as an indexed integer property to the `RiskAppSecurityAssessmentAdvisoryCollection` schema so RAG retrieval can be constrained to a specific advisory.

### Recommended approach

**Fix A + Fix B together.** Fix A resolves the advisory name before the LLM runs (deterministic). Fix B gives the LLM explicit instructions for cases where programmatic resolution didn't run. Fix C is a longer-term improvement for RAG precision but requires Weaviate schema changes.

---

## Trace Timing

| Phase | Duration |
|---|---|
| Semantic Router (agent selection) | 1.6s |
| NeMo Guardrails (input check) | 3.7s |
| Agent LLM run 1 (tool selection) | 1.2s |
| RAG retrieval | 0.9s |
| Agent LLM run 2 (answer generation) | 13.3s |
| **Total** | **19.5s** |

Tokens: ~21,285 total (routing 8,211 + agent run 1 4,739 + agent run 2 8,335)

---

## Other Observations

### Guardrails 401 error (non-blocking)

The guardrails layer runs two parallel LLM calls. The `ChatMistralAI` (LangChain) path failed with HTTP 401 against `cxaihub-nprd.cisco.com/mistral-medium/v1/chat/completions` — `error="invalid_token"` in the `www-authenticate` header. The NeMo path succeeded, so the guardrail check passed. The token is present but expired/revoked — a configuration issue to fix separately.
