> **Agent:** Security Advisory
> **Repo:** [`CXEPI/risk-app`](https://github.com/CXEPI/risk-app)
> **Jira:** _to be created_

# Triage: CVSS Score Hallucination for CVE-2025-20197

**LangSmith trace:** `019dceae-2cfa-7793-810e-ae0b811a9a28`  
**Workspace:** nprd  
**Date:** 2026-04-27  
**Question:** "What is its CVSS?" (referring to CVE-2025-20197, advisory 3065)

---

## Symptom

Agent returned:
- **CVSS score: 7.8 (High)**  
- **Vector: CVSS:3.1/AV:L/AC:L/PR:H/UI:N/S:U/C:H/I:H/A:H**

Actual values per [CVE.org](https://www.cve.org/CVERecord?id=CVE-2025-20197):
- **CVSS score: 6.7 (Medium)**  
- **Vector: CVSS:3.1/AV:L/AC:L/PR:H/UI:N/S:C/C:L/I:H/A:N**

Differences in vector components:

| Component | Agent (wrong) | Actual |
|-----------|--------------|--------|
| Scope (S) | U (Unchanged) | **C (Changed)** |
| Confidentiality (C) | H (High) | **L (Low)** |
| Availability (A) | H (High) | **N (None)** |
| Overall Score | 7.8 | **6.7** |

---

## Root Cause: LLM Hallucination — No Tool Evidence for CVSS

**Classification: New failure mode — FM-7: LLM fabricates CVSS score/vector not present in any tool output**

### Trace Walkthrough

The Security Assessment Agent chain (`019dceae-3a46-...`) executed **3 LLM calls** and **2 RAG tool calls**. No SQL tool (`mcp_build_sql_by_domain`) was invoked.

#### Run 1 — LLM (`019dceae-3a8c`)
- **Output:** Tool call → `mcp_rag_data(query="CVE-2025-20197 CVSS score and vector")`

#### Run 1 — RAG tool (`019dceae-3e79`)
- **Result:** Returned **wrong documents**:
  - `CVE-2025-20154` (cisco-sa-twamp-kV4FHugn, advisory 3102) — not related
  - `CVE-2023-20198,CVE-2023-20273` (cisco-sa-iosxe-webui-privesc-j22SaA4z, advisory 2789) — not related
- **No document for CVE-2025-20197 was returned.** RAG hybrid search failed to match.

#### Run 2 — LLM (`019dceae-42ae`)
- **Output:** Tool call → `mcp_rag_data(query="CVE-2025-20197 CVSS score and vector for advisory 3065")`

#### Run 2 — RAG tool (`019dceae-472d`)
- **Result:** Top hit was the **correct advisory** (cisco-sa-iosxe-privesc-su7scvdp, advisory 3065, score 0.92)
- But the RAG document's `summary_text` does **not** contain per-CVE CVSS scores or vectors. It only says: *"The Security Impact Rating (SIR) of this advisory has been raised to High"*
- The `cve_id` field lists all 5 CVEs comma-separated: `CVE-2025-20197,CVE-2025-20198,CVE-2025-20199,CVE-2025-20200,CVE-2025-20201`
- **No CVSS score or vector string appears anywhere in the RAG output.**

#### Run 3 — LLM (`019dceae-4a7d`) — Final response
- **Output:** The LLM generated `CVSS 7.8` and the full vector `CVSS:3.1/AV:L/AC:L/PR:H/UI:N/S:U/C:H/I:H/A:H`
- **This data was not present in any tool output.** The LLM fabricated a plausible-looking CVSS score and vector based on the vulnerability description (privilege escalation, local, privilege-15 required) and its parametric knowledge — but got the values wrong.

---

## Why the LLM Hallucinated

1. **RAG data gap:** The Weaviate collection stores advisory-level documents, not per-CVE CVSS data. The `summary_text` does not include CVSS scores or vectors for individual CVEs. This advisory covers 5 CVEs, each with potentially different CVSS scores.

2. **SQL path not attempted:** The `bulletins` table has a `cvss_score` column, but it stores a single score per advisory (per `psirt_id`), not per CVE. Even if the LLM had used SQL, the bulletins table would return the advisory-level score, not the per-CVE score for CVE-2025-20197.

3. **No tool can answer this question:** Neither RAG nor SQL has per-CVE CVSS data. The CVSS score and vector for a specific CVE within a multi-CVE advisory are only available from the Cisco PSIRT advisory page or the CVE.org record — neither of which the agent can query.

4. **System prompt does not guard against this:** There is no instruction telling the LLM: *"If the CVSS score/vector for a specific CVE is not present in tool output, say so — do not generate one from memory."*

---

## Impact

**Severity: High** — The agent presents fabricated CVSS data with full confidence, including a detailed vector breakdown. Users have no way to distinguish this from tool-backed data. This undermines trust in all numerical data the agent returns.

---

## Recommendations

### Fix 1 (Short-term): System prompt guard-rail
Add an explicit instruction to the system prompt:

```
<cvss_accuracy>
NEVER generate CVSS scores, CVSS vectors, or severity ratings from memory or inference.
Only report CVSS data that appears verbatim in a tool response (RAG or SQL result).
If the requested CVSS data is not present in any tool output, respond:
"The CVSS score for this specific CVE is not available in the advisory data. Please refer to the Cisco advisory page: [psirt_url_text]"
</cvss_accuracy>
```

### Fix 2 (Medium-term): Enrich RAG data with per-CVE CVSS
During Weaviate ingestion, extract per-CVE CVSS scores and vectors from the Cisco PSIRT API and store them as structured properties in the RAG collection. This allows the agent to answer per-CVE CVSS questions accurately.

### Fix 3 (Medium-term): Add `cvss_score` to SQL query path
When the user asks about CVSS, the LLM should prefer the SQL path (`mcp_build_sql_by_domain` targeting `bulletins` with a `cvss_score` column) over RAG. However, this only provides the advisory-level score, not per-CVE scores for multi-CVE advisories. The system prompt should clarify this distinction.

### Fix 4 (Long-term): Per-CVE data model
Add a CVE-level table or Weaviate property that stores individual CVSS scores and vectors for each CVE within an advisory. This is the only way to accurately answer per-CVE CVSS questions for multi-CVE advisories.

---

## Affected Schema

The `bulletins.cvss_score` column (see [schema_advisory.py](schema/schema_advisory.py)) stores a **single CVSS score per advisory**, not per CVE. For advisory 3065 which covers 5 CVEs, there is only one `cvss_score` value — it cannot distinguish between CVE-2025-20197 (actual: 6.7) and other CVEs in the same advisory.
