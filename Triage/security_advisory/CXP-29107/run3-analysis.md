> **Agent:** Security Advisory | **Repo:** [`CXEPI/risk-app`](https://github.com/CXEPI/risk-app)

# Run 3 — Root Cause Analysis

> **Trace**: `019d9ff7-20f8-78a1-a49d-38d10218491c`  
> **Run 3 span**: `019d9ff7-4999-7561-8ccb-a343f9b17af3` (LLM)  
> **Tool 1 span**: `019d9ff7-620c-7361-9f09-f2c5be6ef842` (get_table_schema)  
> **Tool 2 span**: `019d9ff7-623e-7730-996e-43ce8ca08472` (build_sql_query)  
> **Model**: `mistral-medium-2508`  
> **Analysed**: 2026-04-18

---

## 1. What Run 3 Does

Run 3 is the LLM's **second attempt** to build a SQL query. It arrives with 7 input messages:

| # | Role | Content |
|---|---|---|
| 0 | System | Security Advisory assistant prompt |
| 1 | Human | Conversation history context |
| 2 | Human | "Can you list the high severity advisories?" |
| 3 | AI | *(tool_call: `get_table_schema`)* |
| 4 | Tool | Schema response (57,805 chars) — includes `relationships[]` with both short aliases and FQNs |
| 5 | AI | *(tool_call: `mcp_build_sql_by_domain` — run 2, first SQL attempt)* |
| 6 | Tool | `{"error": true, "message": "The data query could not be completed. Please check the query parameters and try again."}` |

The LLM enters run 3 having already received the full schema **and** a generic, non-actionable error from its first SQL attempt.

---

## 2. What the LLM Decides to Call

Run 3 output is a single tool call to `mcp_build_sql_by_domain`:

```json
{
  "domain": "security_advisory",
  "target_table_alias": "assets",
  "columns": [
    "bulletins.psirt_id",
    "bulletins.advisory_id",
    "bulletins.severity_level_name",
    "bulletins.headline_name",
    "bulletins.cvss_score",
    "bulletins.publish_date"
  ],
  "filters": [
    { "column": "assets.serial_number", "operator": "=", "value": "SIM651871" },
    { "column": "bulletins.severity_level_name", "operator": "=", "value": "High" }
  ],
  "join_specs": [
    {
      "join_type": "INNER",
      "table": "postgresql.public.cvi_psirts_view_1__3__7",
      "on_left": "assets.serial_number",
      "on_right": "postgresql.public.cvi_psirts_view_1__3__7.serial_number"
    },
    {
      "join_type": "INNER",
      "table": "postgresql.public.pas_psirt_bulletins_view_1__3__1",
      "on_left": "postgresql.public.cvi_psirts_view_1__3__7.psirt_id",
      "on_right": "postgresql.public.pas_psirt_bulletins_view_1__3__1.psirt_id"
    }
  ]
}
```

The logic, columns, filters, and join structure are **correct**. The defect is in the `on_right` and `on_left` values of the joins.

---

## 3. The Error

`build_sql_query` (via `mcp_build_sql_by_domain`) returns:

```
Error executing tool build_sql_query: 3 validation errors for build_sql_queryArguments
joins.0.on_right
  Value error, Invalid join column
  'postgresql.public.cvi_psirts_view_1__3__7.serial_number'.
  Must be a plain SQL identifier (letters, digits, underscores;
  optionally schema-qualified with dots).
joins.1.on_left
  Value error, Invalid join column
  'postgresql.public.cvi_psirts_view_1__3__7.psirt_id'.
  ...
joins.1.on_right
  Value error, Invalid join column
  'postgresql.public.pas_psirt_bulletins_view_1__3__1.psirt_id'.
  ...
```

---

## 4. Root Cause

This is a **two-layer root cause**.

### Layer 1 — LLM uses `from_table_ref` as a column qualifier (upstream trigger)

`get_table_schema("security_advisory")` returns a `relationships` array where each entry contains **both** a short alias (`from_table`/`to_table`) **and** a fully-qualified Trino catalog path (`from_table_ref`/`to_table_ref`):

```json
[
  {
    "id": "assets_psirts",
    "from_table": "assets",
    "from_column": "serial_number",
    "to_table": "psirts",
    "to_column": "serial_number",
    "from_table_ref": "postgresql.public.cvi_assets_view_1__3__5",
    "to_table_ref": "postgresql.public.cvi_psirts_view_1__3__7"
  },
  {
    "id": "psirts_bulletins",
    "from_table": "psirts",
    "from_column": "psirt_id",
    "to_table": "bulletins",
    "to_column": "psirt_id",
    "from_table_ref": "postgresql.public.cvi_psirts_view_1__3__7",
    "to_table_ref": "postgresql.public.pas_psirt_bulletins_view_1__3__1"
  }
]
```

The LLM needs a column reference for the ON clause, which requires both a table qualifier and a column name. The relationship entry provides both pieces:

| Field | Value | Used as |
|---|---|---|
| `to_table_ref` | `postgresql.public.cvi_psirts_view_1__3__7` | table qualifier |
| `to_column` | `serial_number` | column name |

The LLM concatenated them: `to_table_ref` + `.` + `to_column` → `postgresql.public.cvi_psirts_view_1__3__7.serial_number`.

Run 2 (first attempt, no prior error) did the same concatenation using `to_table` instead: `psirts` + `.` + `to_column` → `psirts.serial_number` — which passed validation.

After receiving the generic Trino error on run 2, the LLM switched from `to_table` to `to_table_ref` as the qualifier, producing the 4-component form that fails the regex.

### Layer 2 — `_validate_identifier` regex blocks 4-component identifiers (downstream blocker)

`JoinSpec.on_left` and `on_right` are validated via Pydantic `@field_validator` calling `_validate_identifier()` in `text2sql_mcp/server.py`:

```python
_IDENTIFIER_RE = re.compile(
    r"^[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*){0,2}$"
)

def _validate_identifier(name: str, label: str = "identifier") -> str:
    if not _IDENTIFIER_RE.match(name):
        raise ValueError(
            f"Invalid {label} '{name}'. Must be a plain SQL identifier "
            "(letters, digits, underscores; optionally schema-qualified with dots)."
        )
    return name
```

The `{0,2}` quantifier permits at most **2 additional dot-separated components** after the first token — a maximum of **3 components total** (e.g. `catalog.schema.table`). Appending `.column_name` to a 3-component FQN produces **4 components**, which does not match. `_validate_identifier()` raises `ValueError` for each failing field, which Pydantic surfaces as simultaneous validation errors.

### Causal chain

```
get_table_schema returns relationships[]
  ├── from_table: "psirts"          ← short alias (correct for ON column qualification)
  └── from_table_ref: "postgresql.public.cvi_psirts_view_1__3__7"  ← FQN (intended for JOIN table= only)
           │
           │  No schema note distinguishes which field to use in on_left/on_right
           │
           ▼
LLM (after generic error on run 2) picks from_table_ref as column qualifier
  └── on_right = "postgresql.public.cvi_psirts_view_1__3__7.serial_number"  ← 4 components
           │
           ▼
_validate_identifier() matches against {0,2} → fails at 4 components
  └── Pydantic ValidationError × 3 → tool call rejected entirely
```

---

## 5. Fix Options

> **Note**: which option to apply is a developer decision — the analysis below states what each option changes, not which is correct.

### Option A — Extend the identifier regex to accept 4-component paths

`catalog.schema.table.column` is a valid Trino SQL construct. Changing the regex would make the validator accept it:

```python
# text2sql_mcp/server.py — line 32
# Before:
_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*){0,2}$")

# After:
_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*){0,3}$")
#                                                                                   ^^^
```

If the 4-component form is intentionally disallowed (e.g. because ON clauses should only reference aliases, not catalog paths), Option A is the wrong fix.

### Option B — Remove or restrict `from_table_ref`/`to_table_ref` from the relationships array

The `relationships[]` entries currently expose both `from_table` (short alias) and `from_table_ref` (FQN). The LLM used `from_table_ref` as a column qualifier. Two sub-options:

Option B1 — **Remove them entirely**: the `tables{}` dict already maps each short alias to its FQN (`tables.psirts.table = "postgresql.public.cvi_psirts_view_1__3__7"`), so the FQN is still discoverable.

Option B2 — **Keep but annotate** with an explicit field that constrains their use:

```json
{
  "from_table": "assets",
  "from_table_fqn": "postgresql.public.cvi_assets_view_1__3__5",
  "from_table_fqn_note": "Use in join table= field only. Use short alias in on_left/on_right.",
  ...
}
```

If 4-component ON column references are intentionally disallowed, Option B is the correct fix.

### Options are mutually exclusive alternatives

| Option | Changes | Valid if... |
|---|---|---|
| A | Extend regex `{0,2}` → `{0,3}` in `server.py` | 4-component Trino column refs are acceptable in ON clauses |
| B1 | Remove `from_table_ref`/`to_table_ref` from `relationships[]` in `server.py` | ON clauses must only use short aliases; FQN in ON is undesirable |
| B2 | Rename + annotate `from_table_ref` fields | Same as B1 but FQN must remain visible in relationships for other reasons |

---

## 6. Key Files

| File | Relevant symbol |
|---|---|
| `text2sql_mcp/server.py` | `_IDENTIFIER_RE`, `_validate_identifier()`, `JoinSpec`, `_get_schema_for_domain()` |
| `trino_mcp/trino_client.py` | `_sanitized_error_message()` — generic error hides the real Trino failure that triggered run 3's over-specification |
