# CXP — RAG Collection Name Error + Trino Generic Error

## Trace

- **Trace ID:** `019dba2f-f2fc-7b52-aee7-255fa2dc5f52`
- **Workspace:** cx-iq-nprd
- **Project:** DEV--Security_Assessment_AI_Agent
- **Agent:** Security Assessment Agent (Assessments - Security Advisories)
- **Timestamp:** 2026-04-23T11:53:17Z
- **User:** psmeunin
- **Code ref:** `risk-app` @ `bacd04ef` (main)

## User Question

> "Can you give me an over of the official advisory?"

Context: `checkId: ["3046"]`, Security Advisories page. This is the 6th turn in a conversation about PSIRT advisory 3046 (Cisco IOS XR Software CLI Privilege Escalation Vulnerability). Previous turns successfully answered impact and remediation questions.

## Outcome

Agent failed to answer. Returned a fallback message:

> "I wasn't able to retrieve the official advisory details for PSIRT ID 3046. Could you try rephrasing your question or check the advisory directly on the Cisco PSIRT website."

3 of 4 tool calls returned errors. All 3 errors are infrastructure/validation issues, not LLM reasoning errors.

---

## Agent Execution Flow (4 LLM runs)

### Run 1 — LLM decides on parallel RAG + schema lookup

**LLM calls two tools in parallel:**

| # | Tool | Args | Result |
|---|------|------|--------|
| 1 | `mcp_rag_data` | `query: "Cisco IOS XR Software CLI Privilege Escalation Vulnerability with PSIRT ID 3046"`, `collection_name_override: "security_advisory"` | **ERROR** — Weaviate 422 |
| 2 | `mcp_get_table_schema` | `domain: "security_advisory"` | OK — full schema returned |

### Run 2 — LLM builds SQL query from schema

| # | Tool | Args | Result |
|---|------|------|--------|
| 3 | `mcp_build_sql_by_domain` | `target_table_alias: "bulletins"`, `columns: [bulletins.psirt_id, headline_name, summary_text, severity_level_name, cvss_score, publish_date, psirt_url_text]`, `filters: [{psirt_id = 3046}]` | **ERROR** — generic Trino error |

**SQL generated** (by `build_sql_query` — MCP tool within the wrapper):
```sql
SELECT bulletins.psirt_id, bulletins.headline_name, bulletins.summary_text,
       bulletins.severity_level_name, bulletins.cvss_score, bulletins.publish_date,
       bulletins.psirt_url_text
FROM postgresql.public.pas_psirt_bulletins_view_1__3__1 AS bulletins
WHERE (bulletins.psirt_id = 3046)
```

SQL is syntactically correct. Column names match schema. `target_table_alias` is present and correct. The error originates from Trino execution, not SQL generation.

### Run 3 — LLM retries with RAG (different query)

| # | Tool | Args | Result |
|---|------|------|--------|
| 4 | `mcp_rag_data` | `query: "Cisco PSIRT advisory 3046"`, `collection_name_override: "security_advisory"` | **ERROR** — Weaviate 422 (same) |

### Run 4 — LLM gives up

No tool calls. Returns fallback text to user.

---

## Error Analysis

### Error 1 & 3: RAG `chat_with_rag` — Weaviate collection name validation failure

**Span IDs:** `019dba30-0519-7f31-aa26-2ffcbe4a57b2` (run 1), `019dba30-1a22-71a0-9c03-64e526f3e3b4` (run 3)

**Error message:**
```
Error executing tool chat_with_rag: Status Code: 422,
Message: {"message":"String should match pattern '^[A-Z][A-Za-z0-9].*$'
string_pattern_mismatch at ('path', 'collectionName')"}
```

**What happened:**

1. The LLM called `mcp_rag_data` with `collection_name_override: "security_advisory"`.
2. The `mcp_rag_data` wrapper in `security_assessment_agent_impl.py` (line ~571) uses `collection_name_override or collection_name` as the effective collection. Since `collection_name_override` is set, it takes precedence.
3. The wrapper passed `collection_name: "security_advisory"` to `chat_with_rag` in `rag_mcp/server.py`.
4. `chat_with_rag` passed it to `vectordb.hybrid_search_queries(collection_name="security_advisory", ...)`.
5. Weaviate rejected the request because `"security_advisory"` does not match its collection naming pattern `^[A-Z][A-Za-z0-9].*$` — it starts with lowercase and contains an underscore.

**Root cause:** The LLM passed the **domain name** (`security_advisory`) as a Weaviate **collection name**. These are different things:
- Domain name: `security_advisory` (lowercase, used for schema/SQL routing)
- Weaviate collection name: `RiskAppSecurityAssessmentAdvisoryCollection` (PascalCase, the actual default defined at line 33 of `security_assessment_agent_impl.py`)

The `mcp_rag_data` wrapper does not validate or map `collection_name_override` — it passes the value through directly to Weaviate. When the LLM provides a domain name instead of a collection name, the request fails.

**Failure owner:** Mixed — LLM + missing guardrail.
- **LLM**: Should not have set `collection_name_override` at all — the default collection is already configured for the security advisory domain. The LLM tool description for `mcp_rag_data` says "Optional" but does not specify valid collection names.
- **Wrapper**: No validation on `collection_name_override`. The wrapper could reject or map values that don't match expected collection names.

**Fix options:**
- **Option A (recommended):** Remove `collection_name_override` from the `mcp_rag_data` tool definition exposed to the LLM. The wrapper already resolves the correct collection from `settings.mcp_collection_assessment or COLLECTION_NAME`. The LLM should never need to override it.
- **Option B:** Add validation in the wrapper — if `collection_name_override` is set but does not match any known collection name, ignore it and use the default.
- **Option C:** Map domain name to collection name in the wrapper (e.g., `{"security_advisory": "RiskAppSecurityAssessmentAdvisoryCollection"}`).

---

### Error 2: `run_sql_query` — Generic Trino error (FM-2)

**Span ID:** `019dba30-133b-7872-8ea9-2d236068b7da`

**Error message (application-level, `isError: false` at MCP transport level):**
```json
{
  "error": true,
  "message": "The data query could not be completed. Please check the query parameters and try again.",
  "rows": [],
  "row_count": 0,
  "columns": [],
  "truncated": false
}
```

**What happened:**

1. `build_sql_query` generated a valid SQL query (see above). The SQL references correct columns, correct table FQN, correct filter column and type (integer 3046 for integer column `psirt_id`).
2. `run_sql_query` executed the SQL against Trino and got an error.
3. `_sanitized_error_message()` in `trino_mcp/trino_client.py` (line 188) did not match any of the 4 known error codes (COLUMN_NOT_FOUND, TABLE_NOT_FOUND, SYNTAX_ERROR, TYPE_MISMATCH) and returned the generic fallback.

**What is NOT known from the trace:**
- The actual Trino error code and exception message. The generic fallback masks it. The real error is only in server-side Trino MCP logs.
- Since the SQL is syntactically correct and column names/types match, the likely candidates for the underlying error are: `PERMISSION_DENIED`, `CATALOG_NOT_FOUND`, `SCHEMA_NOT_FOUND`, or a Trino gateway/connectivity error. **This requires server-side log confirmation.**

**This is a known issue — FM-2.** The generic error is non-actionable for the LLM. It received `"The data query could not be completed..."` which gives it nothing to correct. The LLM then fell back to a second RAG attempt, which also failed (same collection name issue).

**Fix:** Extend `_sanitized_error_message()` to handle additional error codes, or return the error code as a separate field so the LLM (and operators) can see what type of error occurred without leaking schema names.

---

## Summary

| # | Tool | Error Type | Root Cause | Fix Priority |
|---|------|-----------|------------|-------------|
| 1 | `mcp_rag_data` → `chat_with_rag` | Weaviate 422 — collection name validation | LLM passed domain name (`security_advisory`) as collection name; wrapper has no validation | **High** — deterministic failure, every RAG call with `collection_name_override` will fail |
| 2 | `run_sql_query` | Generic Trino error (FM-2) | Underlying Trino error code not in the 4 handled codes; actual error unknown from trace | **Medium** — requires server-side log investigation; FM-2 is a known gap |
| 3 | `mcp_rag_data` → `chat_with_rag` | Weaviate 422 — same as #1 | Same root cause as #1 (LLM retried with same `collection_name_override`) | Same fix as #1 |

**Net impact:** All 3 data retrieval paths failed (2x RAG, 1x SQL). The agent had no data to answer with and returned a fallback message. The user received no answer to "Can you give me an overview of the official advisory?"

**New failure mode identified:** The RAG collection name validation error is not covered by the existing FM catalog (FM-1 through FM-6). This is a new failure pattern — **the LLM conflates domain names with Weaviate collection names** when `collection_name_override` is exposed as a tool parameter.
