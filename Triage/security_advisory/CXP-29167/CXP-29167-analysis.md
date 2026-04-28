> **Agent:** Security Advisory | **Repo:** [`CXEPI/risk-app`](https://github.com/CXEPI/risk-app)

# CXP-29167 — Executive Summary: Security Advisory Agent Failures

**Date:** 2026-04-20  
**Jira:** [CXP-29167](https://cisco-cxe.atlassian.net/browse/CXP-29167)  
**Agent:** Security Assessment AI Agent (`DEV--Security_Assessment_AI_Agent` / `ciq-agents-dev-usw2`)  
**Model:** `mistral-medium-2508`  
**Scope:** Two user prompts analyzed across multiple LangSmith traces, all with `checkId: ['989']`, URL `/assessments/security-advisories/989`

---

## Traces Analyzed

| Trace ID | User Prompt | Folder |
|---|---|---|
| `019daa0e-2d55-7bf2-a924-e54a0c167711` | "which rule is this?" | `which rule is this/` |
| `019daa08-b091-7af3-8d6f-e83b4066aae8` | "Explain me more about this vulnerability" | `Explain me more about this vulnerability/` |

---

## Issues Found

### Issue 1 — LLM Hallucinated Column Name

**Severity:** High — agent returned no answer  
**Trace:** `019daa0e-2d55-7bf2-a924-e54a0c167711` (run2)  
**Detail:** [`which rule is this/CXP-triage-results.md`](https://github.com/psmeunin-cxepi/my-cognitive-harness/blob/main/CXP-29167/which%20rule%20is%20this/CXP-triage-results.md)

The LLM translated the UI key `checkId` from the runtime context (camelCase) into `psirts.check_id` (snake_case), a column that does not exist in any schema table. The schema had been returned by `mcp_get_table_schema` in the same context window — the hallucination occurred despite the schema being visible.

**Owner:** LLM  
**System prompt violation:** *"Never use a column name in a query unless it appeared in the `mcp_get_table_schema` response for the current conversation."*

---

### Issue 2 — Missing `target_table_alias` Causes Wrong Base Table

**Severity:** High — agent returned no answer  
**Trace:** `019daa0e-2d55-7bf2-a924-e54a0c167711` (run4)  
**Detail:** [`which rule is this/CXP-triage-results.md`](https://github.com/psmeunin-cxepi/my-cognitive-harness/blob/main/CXP-29167/which%20rule%20is%20this/CXP-triage-results.md)

After the hallucination failure, the LLM retried with the correct filter (`bulletins.psirt_id = 989`) but omitted the `target_table_alias` parameter. The `mcp_build_sql_by_domain` wrapper silently defaulted to `target_table_alias = "assets"`, then forwarded `table_name = cvi_assets_view` to `build_sql_query` along with `bulletins.*` columns and no JOINs.

**Owners:**
- **LLM** — should have set `target_table_alias = "bulletins"` when all columns and filters belong to `bulletins`
- **`build_sql_query` MCP** — silently accepted a structurally contradictory request (`FROM assets` + `bulletins.*` columns + no JOINs) and generated invalid SQL instead of returning a validation error

---

### Issue 3 — Wrong Column Chosen via Semantic Match (`sav_id` instead of `psirt_id`)

**Severity:** Medium — agent self-corrected, recoverable  
**Trace:** `019daa08-b091-7af3-8d6f-e83b4066aae8` (call 1)  
**Detail:** [`Explain me more about this vulnerability/CXP-triage-results.md`](https://github.com/psmeunin-cxepi/my-cognitive-harness/blob/main/CXP-29167/Explain%20me%20more%20about%20this%20vulnerability/CXP-triage-results.md)

The LLM filtered on `psirts.sav_id = '989'` (string) instead of `bulletins.psirt_id = 989` (integer). The schema description for `sav_id` reads "vulnerability internal identifier" — semantically close to what the LLM was trying to filter on. The type mismatch error from `build_sql_query` provided enough signal for the LLM to self-correct on the next call.

**Owner:** LLM (self-corrected) + schema description ambiguity  
**Status:** Recoverable — one extra retry cycle consumed.

---

### Issue 4 — RAG Called Before SQL (Tool Ordering Violation)

**Severity:** Medium — answer not incorrect, sequencing wrong  
**Trace:** `019daa08-b091-7af3-8d6f-e83b4066aae8`  
**Detail:** [`Explain me more about this vulnerability/CXP-triage-rag-results.md`](https://github.com/psmeunin-cxepi/my-cognitive-harness/blob/main/CXP-29167/Explain%20me%20more%20about%20this%20vulnerability/CXP-triage-rag-results.md)

The LLM called `mcp_rag_data` as its **first tool**, before `mcp_get_table_schema` or any SQL call. Rule 1 in the system prompt mandates SQL-first when `checkId` is present. The LLM applied Rule 3 instead (conceptual/explanatory questions → RAG) because the "Explain me more" phrasing matched Rule 3's framing without ambiguity resolution in Rule 1.

**Owner:** LLM + system prompt  
**Root cause:** Rule 1 example phrases (`"this device"`, `"this check"`, `"this result"`) do not include `"explain"` or `"tell me more"`, leaving the overlap with Rule 3 unresolved.

---

### Issue 5 — RAG Search Returns Wrong Advisories (Structural, Not Just LLM)

**Severity:** High — RAG is unreliable for identifier-based queries  
**Traces:** `019daa08-b091-7af3-8d6f-e83b4066aae8`, confirmed by `019daa0e-2d55-7bf2-a924-e54a0c167711`  
**Detail:** [`Explain me more about this vulnerability/CXP-triage-rag-search-results.md`](https://github.com/psmeunin-cxepi/my-cognitive-harness/blob/main/CXP-29167/Explain%20me%20more%20about%20this%20vulnerability/CXP-triage-rag-search-results.md)

In both traces the LLM constructed the RAG query by embedding the numeric `checkId` value in the query string (`"Cisco security advisory check ID 989"`, `"Cisco PSIRT rule ID 989"`). Both calls returned 3 unrelated advisories — the correct advisory (`cisco-sa-20180620-nx-os-cli-execution`) was absent from all results.

**Root cause — structural:**
- `chat_with_rag` (`rag_mcp/server.py`) provides **pure semantic (vector) search only** — no `where` filter support
- The Weaviate `body` field is the only vectorized property; integer identifiers have no semantic vector representation and cannot match by cosine similarity
- `advisory_id` (the slug, e.g. `"cisco-sa-20180620-nx-os-cli-execution"`) is a top-level filterable property in Weaviate but there is **no code path** that maps `checkId → advisory_id` before making the RAG call
- `psirt_id` is not a top-level Weaviate property — cannot be used for exact-match filtering

**Owner:** `chat_with_rag` MCP design (no filter support) + agent impl (no `checkId → advisory_id` resolution before RAG)

---

## Summary Table

| # | Issue | Owner(s) | Recoverable | Prompt | | SQL layer | RAG layer |
|---|---|---|---|---|---|---|---|
| 1 | Hallucinated `psirts.check_id` | LLM | No | ❌ FM-4 violation | | | |
| 2 | Missing `target_table_alias` → wrong base table | LLM + `build_sql_query` MCP | No | ❌ FM-5 violation | | ❌ silent SQL | |
| 3 | `sav_id` chosen via semantic match | LLM | Yes (1 retry) | | | ❌ schema ambiguity | |
| 4 | RAG called before SQL | LLM + system prompt | Yes (ordering only) | ❌ Rule 1 vs Rule 3 | | | |
| 5 | RAG returns wrong advisories | `chat_with_rag` MCP + agent impl | No | | | | ❌ structural |

---

## Recommended Fixes

### Fix 1 — System prompt: extend Rule 1 trigger phrases (Issues 4, 1)
Add `"explain"`, `"tell me more about this"`, `"describe this"` to Rule 1 examples to prevent fall-through to Rule 3 when a deictic reference (`"this"`) is present with an active `checkId`.

### Fix 2 — System prompt: clarify `checkId` → `psirt_id` mapping (Issues 1, 3)
Add an explicit note that `checkId` from the runtime context maps to the `psirt_id` integer column in both `psirts` and `bulletins` tables. Prohibit inferring any other column name from `checkId`.

### Fix 3 — `build_sql_query` MCP: add input validation (Issue 2)
Return a validation error when column prefixes in `columns`/`filters` don't match the base table and no JOINs are provided, instead of silently generating invalid SQL.

### Fix 4 — `chat_with_rag` + agent impl: add `advisory_id` filter support (Issue 5)
Extend `chat_with_rag` (`rag_mcp/server.py`) to accept an optional `advisory_id` parameter and apply a Weaviate `where` filter on the `advisory_id` top-level property (already `index_filterable=True`). The agent must resolve `advisory_id` via SQL before calling RAG when `checkId` is present. This is the only fix that guarantees correct advisory retrieval regardless of query phrasing.

---

## Analysis Files

| File | Covers |
|---|---|
| [`which rule is this/CXP-triage-results.md`](https://github.com/psmeunin-cxepi/my-cognitive-harness/blob/main/CXP-29167/which%20rule%20is%20this/CXP-triage-results.md) | Issues 1 & 2 — hallucination, missing `target_table_alias`, `build_sql_query` silent failure |
| [`Explain me more about this vulnerability/CXP-triage-results.md`](https://github.com/psmeunin-cxepi/my-cognitive-harness/blob/main/CXP-29167/Explain%20me%20more%20about%20this%20vulnerability/CXP-triage-results.md) | Issue 3 — `sav_id` TYPE_MISMATCH and self-correction |
| [`Explain me more about this vulnerability/CXP-triage-rag-results.md`](https://github.com/psmeunin-cxepi/my-cognitive-harness/blob/main/CXP-29167/Explain%20me%20more%20about%20this%20vulnerability/CXP-triage-rag-results.md) | Issue 4 — RAG called before SQL, Rule 1 vs Rule 3 conflict |
| [`Explain me more about this vulnerability/CXP-triage-rag-search-results.md`](https://github.com/psmeunin-cxepi/my-cognitive-harness/blob/main/CXP-29167/Explain%20me%20more%20about%20this%20vulnerability/CXP-triage-rag-search-results.md) | Issue 5 — RAG search query failure, Weaviate schema analysis, fix options |
