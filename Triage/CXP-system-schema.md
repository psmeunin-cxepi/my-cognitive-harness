# System Prompt Gap: Schema Interpretation Guidance

**Trace ID:** `019db47d-5e25-7a40-8e88-887392a1db1b`  
**Workspace:** nprd (`cx-iq-nprd`)  
**Agent:** Security Assessment Agent  
**Model:** mistral-medium-2508  
**Date:** 2026-04-22  

**Related:** [CXP-triage.md](CXP-triage.md) — alias origin & data accuracy analysis | [CXP-sql-query-triage.md](CXP-sql-query-triage.md) — SQL validation failure analysis

---

## Summary

The system prompt provides **no guidance** on how the LLM should interpret the structured response returned by `mcp_get_table_schema`. The schema response contains rich metadata (`notes`, `column_schema`, `relationships`, `example_filters`) that the LLM must use to build correct SQL, but nothing in the prompt explains what these fields mean or how to prioritize them.

---

## What the system prompt says

The system prompt contains two relevant instructions:

1. **Rule: call `mcp_get_table_schema` FIRST** — The LLM is told to always call this tool before building SQL queries.
2. **"Learn column names and relationships"** — A vague instruction to extract column and relationship info from the response.

That's it. No further guidance on interpreting the response.

---

## What the tool docstring says

The `mcp_get_table_schema` wrapper in `security_assessment_agent_impl.py` has this docstring:

> `"Get internal query metadata for a security domain. Do not expose details to the user."`

This tells the LLM to keep the schema internal but says nothing about:
- What fields exist in the response
- How to use `notes[]` as mandatory constraints
- How to interpret `column_schema` (column names, types, enums, descriptions)
- How to use `relationships[]` for JOINs
- How to apply `example_filters[]`

---

## What the schema response actually contains

The `mcp_get_table_schema` response for the `security_advisory` domain returns a structured object with:

| Field | Content | Purpose |
|-------|---------|---------|
| `notes[]` | Array of natural-language rules (e.g., "Use `psirts.vulnerability_status` (VUL/POTVUL) to filter vulnerable assets") | **Mandatory constraints** that should govern SQL construction |
| `column_schema[]` | Per-column metadata: name, type, description, enum values | Column definitions for valid SQL targets |
| `relationships[]` | JOIN definitions with `from_table_ref`, `to_table_ref`, join keys | How to join tables correctly |
| `example_filters[]` | Sample WHERE clauses | Concrete SQL patterns to follow |

---

## Impact of the gap

### 1. `notes[]` are treated as optional hints

The LLM receives notes like:

> *"Use psirts.vulnerability_status (VUL/POTVUL) to filter vulnerable assets."*

Without guidance that notes are **mandatory rules**, the LLM treats them as suggestions. In the traced run, the LLM ignored note #3 entirely — it never filtered on `vulnerability_status`, resulting in a count that conflates affected (`VUL`) and potentially affected (`POTVUL`) assets.

### 2. Column descriptions are underused

The `psirts.vulnerability_status` column has `description: "Vulnerability assessment status."` and `enum: ["VUL", "POTVUL"]`. The LLM saw this but had no instruction to map these values to business concepts (affected vs. potentially affected). A richer description or a prompt-level mapping would have prevented the data accuracy issue.

### 3. `example_filters` are not emphasized

The schema includes `psirts.vulnerability_status = 'VUL'` as an example filter. Without prompt guidance to treat examples as recommended patterns, the LLM has no reason to prioritize them.

### 4. `relationships[]` were used correctly

The LLM did correctly use the `relationships[]` data to construct the JOIN. This is the one field that mapped intuitively to SQL construction without needing explicit guidance.

---

## Recommendation: Add `<schema_interpretation>` block to system prompt

Add a dedicated section to the system prompt that explains how to interpret the schema response:

```
<schema_interpretation>
When you call mcp_get_table_schema, the response contains structured metadata.
Use it as follows:

1. **notes[]** — These are MANDATORY rules. Always apply them when constructing SQL.
   They define required filters, aggregation constraints, and business logic.
   Never ignore a note; if a note conflicts with the user's request, inform the user.

2. **column_schema[]** — Column definitions. Use the `description` field to understand
   what each column represents. Use `enum` values to filter correctly.
   Match user concepts to column descriptions (e.g., "affected assets" → vulnerability_status = 'VUL').

3. **relationships[]** — JOIN definitions. Use `from_table_ref` and `to_table_ref` for
   fully qualified table names. Use the join keys to construct ON clauses.

4. **example_filters[]** — Recommended SQL patterns. Prefer these patterns when
   constructing WHERE clauses for common queries.
</schema_interpretation>
```

### Additional prompt-level mappings

For the security advisory domain specifically, the system prompt should include a concept-to-column mapping:

| User concept | SQL mapping |
|---|---|
| "affected assets" / "impacted assets" | `psirts.vulnerability_status = 'VUL'` |
| "potentially affected assets" | `psirts.vulnerability_status = 'POTVUL'` |
| "all impacted assets" (both) | No filter on `vulnerability_status`, but label clearly |

This eliminates ambiguity when the LLM translates natural-language queries into SQL filters.

---

## Fix Recommendations

### 1. System prompt — add `<schema_interpretation>` block

**File:** `security-advisory-ai-api/src/openapi_server/prompts/security_assessment_v1_mistral.py`

Add the `<schema_interpretation>` block (shown above) and the domain concept-to-column mappings table. This teaches the LLM how to read the schema response and map user intent to SQL.

### 2. Tool docstring — describe response structure

**File:** `security-advisory-ai-api/src/openapi_server/impl/security_assessment_agent_impl.py` (line ~588)

The current `mcp_get_table_schema` docstring is:

> `"Get internal query metadata for a security domain. Do not expose details to the user."`

Replace with something like:

> `"Get internal query metadata for a security domain. Returns notes (mandatory rules), column_schema (column definitions with types and enums), relationships (JOIN definitions), and example_filters (recommended WHERE patterns). Apply all notes as mandatory constraints when building SQL. Do not expose details to the user."`

### 3. Schema response — strengthen `notes[]` and enrich column descriptions

**File:** `text2sql_mcp/server.py` — `_get_schema_for_domain()`

The fix should go in **two places** within the schema response:

#### a. `psirts.vulnerability_status` column description

**Current:**
```
"Vulnerability assessment status."
```

**Proposed:**
```
"Vulnerability assessment status. VUL = confirmed vulnerable (affected assets). POTVUL = potentially vulnerable (manual verification required). When counting assets, always split or filter on this column to match the UI breakdown."
```

This is the first place the LLM encounters the column — a richer description maps enum values to business concepts directly at the point of discovery.

#### b. `notes[]` array — add or strengthen the aggregation rule

**Current note #3:**
```
"Use psirts.vulnerability_status (VUL/POTVUL) to filter vulnerable assets."
```

**Proposed (replace or add as new note):**
```
"When counting impacted/affected assets per advisory, you MUST filter or split on psirts.vulnerability_status. VUL = affected (confirmed vulnerable), POTVUL = potentially affected (manual verification required). A bare COUNT without this filter combines both statuses and does not match the UI breakdown."
```

Both changes are needed — the column description provides inline context when the LLM reads column metadata, and the note provides a mandatory rule that governs aggregation queries specifically.

### Summary of changes

| File | Location | Change |
|------|----------|--------|
| `prompts/security_assessment_v1_mistral.py` | System prompt | Add `<schema_interpretation>` block + concept mappings |
| `impl/security_assessment_agent_impl.py` | `mcp_get_table_schema` docstring (~line 588) | Describe response structure (notes, column_schema, relationships, example_filters) |
| `text2sql_mcp/server.py` | `psirts.vulnerability_status` column description | Enrich with VUL/POTVUL business meaning + aggregation guidance |
| `text2sql_mcp/server.py` | `notes[]` array (note #3) | Strengthen to MUST language + explicit aggregation rule |
