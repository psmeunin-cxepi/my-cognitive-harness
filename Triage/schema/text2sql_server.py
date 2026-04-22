"""
SQL Query Builder MCP Server

Generates safe, parameterized SQL SELECT queries from structured agent inputs.
All identifiers are validated against a strict regex, all literal values are
escaped, and operators/aggregation functions are restricted to known-safe enums.
No raw SQL fragments are accepted, making SQL-injection impossible by design.
"""

from __future__ import annotations

import json
import logging
import re
from enum import Enum
from typing import Any, Literal, cast

import common.logger.logging_config  # noqa: F401
from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field, field_validator, model_validator

from config import get_settings
from schema_advisory import (
    ADVISORY_ASSETS_COLUMN_SCHEMA,
    ADVISORY_COLUMN_SCHEMA,
    ADVISORY_PSIRT_BULLETINS_COLUMN_SCHEMA,
    ADVISORY_RELATIONSHIP_SCHEMA,
)
from schema_hardening import (
    HARDENING_ASSESSMENT_COLUMN_SCHEMA,
    HARDENING_COLUMN_SCHEMA,
    HARDENING_RELATIONSHIP_SCHEMA,
)

logger = logging.getLogger(__name__)
settings = get_settings()

# ---------------------------------------------------------------------------
# Identifier validation
# ---------------------------------------------------------------------------
# Permits:  simple_name  |  schema.table  |  catalog.schema.table  |  catalog.schema.table.column
# Forbids:  spaces, quotes, semicolons, SQL keywords injected via dots, etc.
_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*){0,3}$")


def _validate_identifier(name: str, label: str = "identifier") -> str:
    if not _IDENTIFIER_RE.match(name):
        raise ValueError(
            f"Invalid {label} '{name}'. Must be a plain SQL identifier "
            "(letters, digits, underscores; optionally schema-qualified with dots)."
        )
    return name


def _escape_string_literal(value: str) -> str:
    """Escape single-quotes in a SQL string literal (ANSI standard)."""
    return value.replace("'", "''")


SchemaDomain = Literal["security_advisory", "security_hardening"]


def _column_names(column_schema: list[dict[str, Any]]) -> list[str]:
    return [column["name"] for column in column_schema]


def _get_table_alias_map() -> dict[str, str]:
    """Return a mapping of short alias names to fully-qualified table names.

    This allows build_sql_query to resolve cases where the LLM passes an alias
    (e.g. 'psirts') instead of the full table name in a JoinSpec.
    """
    return {
        "assets": settings.security_advisory_assets_table
        or "<set SQL_MCP_SECURITY_ADVISORY_ASSETS_TABLE>",
        "psirts": settings.security_advisory_table
        or "<set SQL_MCP_SECURITY_ADVISORY_TABLE>",
        "bulletins": settings.security_advisory_psirt_bulletins_table
        or "<set SQL_MCP_SECURITY_ADVISORY_PSIRT_BULLETINS_TABLE>",
        "finding": settings.security_hardening_table,
        "assessment": settings.security_hardening_assessment_table
        or "<set SQL_MCP_SECURITY_HARDENING_ASSESSMENT_TABLE>",
    }


def _get_known_columns_by_table() -> dict[str, set[str]]:
    """Return a mapping of fully-qualified table name -> set of valid column names."""
    alias_map = _get_table_alias_map()
    schema_map: dict[str, list[dict[str, Any]]] = {
        alias_map["assets"]: ADVISORY_ASSETS_COLUMN_SCHEMA,
        alias_map["psirts"]: ADVISORY_COLUMN_SCHEMA,
        alias_map["bulletins"]: ADVISORY_PSIRT_BULLETINS_COLUMN_SCHEMA,
        alias_map["finding"]: HARDENING_COLUMN_SCHEMA,
        alias_map["assessment"]: HARDENING_ASSESSMENT_COLUMN_SCHEMA,
    }
    return {table: {col["name"] for col in cols} for table, cols in schema_map.items()}


def _validate_schema_domain(domain: str) -> SchemaDomain:
    normalized = domain.strip().lower()
    if normalized not in {"security_advisory", "security_hardening"}:
        raise ValueError("domain must be one of: security_advisory, security_hardening")
    return cast(SchemaDomain, normalized)


# Sentinel value that trino_mcp resolves to the real execution_id at query time.
_LATEST_EXECUTION_ID_PLACEHOLDER = "__LATEST_EXECUTION_ID__"


def _is_hardening_finding_table(table_name: str) -> bool:
    """Return True if *table_name* is the security-hardening finding table."""
    return table_name == settings.security_hardening_table


def _latest_execution_id_filter() -> str:
    """Return a WHERE clause with a placeholder for the latest execution_id.

    The placeholder is resolved by trino_mcp at execution time via a separate
    query so that the actual execution_id value is known before the main query
    runs.
    """
    return f"execution_id = '{_LATEST_EXECUTION_ID_PLACEHOLDER}'"


def _resolve_domain_table(domain: SchemaDomain) -> str:
    if domain == "security_advisory":
        return (
            settings.security_advisory_table or "<set SQL_MCP_SECURITY_ADVISORY_TABLE>"
        )
    return settings.security_hardening_table


def _get_schema_for_domain(domain: SchemaDomain) -> dict[str, Any]:
    if domain == "security_advisory":
        psirts_table = (
            settings.security_advisory_table or "<set SQL_MCP_SECURITY_ADVISORY_TABLE>"
        )
        assets_table = (
            settings.security_advisory_assets_table
            or "<set SQL_MCP_SECURITY_ADVISORY_ASSETS_TABLE>"
        )
        bulletins_table = (
            settings.security_advisory_psirt_bulletins_table
            or "<set SQL_MCP_SECURITY_ADVISORY_PSIRT_BULLETINS_TABLE>"
        )
        relationships = [
            {
                **rel,
                "from_table_ref": (
                    assets_table if rel["from_table"] == "assets" else psirts_table
                ),
                "to_table_ref": (
                    psirts_table if rel["to_table"] == "psirts" else bulletins_table
                ),
            }
            for rel in ADVISORY_RELATIONSHIP_SCHEMA
        ]
        return {
            "domain": domain,
            # primary table (assets) at top level for backward compatibility
            "table": assets_table,
            "columns": _column_names(ADVISORY_ASSETS_COLUMN_SCHEMA),
            "column_schema": ADVISORY_ASSETS_COLUMN_SCHEMA,
            # multi-table schema
            "tables": {
                "assets": {
                    "table": assets_table,
                    "columns": _column_names(ADVISORY_ASSETS_COLUMN_SCHEMA),
                    "column_schema": ADVISORY_ASSETS_COLUMN_SCHEMA,
                },
                "psirts": {
                    "table": psirts_table,
                    "columns": _column_names(ADVISORY_COLUMN_SCHEMA),
                    "column_schema": ADVISORY_COLUMN_SCHEMA,
                },
                "bulletins": {
                    "table": bulletins_table,
                    "columns": _column_names(ADVISORY_PSIRT_BULLETINS_COLUMN_SCHEMA),
                    "column_schema": ADVISORY_PSIRT_BULLETINS_COLUMN_SCHEMA,
                },
            },
            "relationships": relationships,
            "notes": [
                "Primary table is 'assets' (cvi_assets_view). JOIN psirts on serial_number for vulnerability data.",
                "JOIN bulletins on psirt_id when filtering or enriching with PSIRT bulletin-level data.",
                "Use psirts.vulnerability_status (VUL/POTVUL) to filter vulnerable assets.",
                "Use assets advisory count fields (advisory_count, affected_security_advisories_count, etc.) ONLY for per-device filtering (e.g. WHERE critical_security_advisories_count > 0). "
                "NEVER use SUM() on these count fields to get total distinct advisories — that double-counts advisories shared across devices. "
                "To count total distinct advisories, JOIN to the psirts table and use COUNT_DISTINCT on psirts.psirt_id.",
                "The severity column on bulletins is 'severity_level_name' (e.g. 'Critical', 'High', 'Medium'). "
                "There is NO column called 'severity' on bulletins — always use bulletins.severity_level_name.",
                "To count advisories broken down by severity: use COUNT_DISTINCT on psirts.psirt_id with "
                "GROUP BY bulletins.severity_level_name and filter WHERE bulletins.severity_level_name IN ('Critical', 'High'). "
                "Do NOT use two identical COUNT(DISTINCT psirt_id) columns without a GROUP BY or CASE WHEN — that returns the same number for both.",
                "Prefer platform_account_id and/or serial_number filters for tenant-safe lookups.",
            ],
            "example_filters": [
                {
                    "column": "psirts.vulnerability_status",
                    "operator": "=",
                    "value": "VUL",
                },
                {
                    "column": "assets.affected_security_advisories_count",
                    "operator": ">",
                    "value": 0,
                },
            ],
        }

    column_schema = HARDENING_COLUMN_SCHEMA
    finding_table = _resolve_domain_table(domain)
    assessment_table = (
        settings.security_hardening_assessment_table
        or "<set SQL_MCP_SECURITY_HARDENING_ASSESSMENT_TABLE>"
    )
    relationships = [
        {
            **rel,
            "from_table_ref": assessment_table,
            "to_table_ref": finding_table,
        }
        for rel in HARDENING_RELATIONSHIP_SCHEMA
    ]
    return {
        "domain": domain,
        # primary table (finding) kept at top level for backward compatibility
        "table": finding_table,
        "columns": _column_names(column_schema),
        "column_schema": column_schema,
        # multi-table schema
        "tables": {
            "finding": {
                "table": finding_table,
                "columns": _column_names(HARDENING_COLUMN_SCHEMA),
                "column_schema": HARDENING_COLUMN_SCHEMA,
            },
            "assessment": {
                "table": assessment_table,
                "columns": _column_names(HARDENING_ASSESSMENT_COLUMN_SCHEMA),
                "column_schema": HARDENING_ASSESSMENT_COLUMN_SCHEMA,
            },
        },
        "relationships": relationships,
        "notes": [
            "Use asset_key/source_id for device and rule-specific lookups.",
            "Use severity and finding_status for compliance summaries.",
            "Use detected_at for time-window filtering and latest results.",
            "Join finding to assessment on assessment_id when assessment-level filters or fields are needed.",
            "Use build_sql_query with a join spec to build cross-table queries safely.",
        ],
        "example_filters": [
            {"column": "severity", "operator": "IN", "value": ["HIGH", "MEDIUM"]},
            {"column": "finding_status", "operator": "=", "value": "VIOLATED"},
        ],
    }


def _build_security_query_prompt(domain: SchemaDomain, user_question: str) -> str:
    schema = _get_schema_for_domain(domain)

    if "tables" in schema:
        # Multi-table domain (security_hardening)
        table_blocks = []
        for alias, tbl in schema["tables"].items():
            col_lines = "\n".join(
                f"  - {c['name']} ({c['type']}): {c['description']}"
                for c in tbl["column_schema"]
            )
            table_blocks.append(f"Table '{alias}' ({tbl['table']}):\n{col_lines}")
        tables_section = "\n\n".join(table_blocks)

        rel_lines = "\n".join(
            f"  - {r['id']}: {r['from_table']}.{r['from_column']} -> "
            f"{r['to_table']}.{r['to_column']} ({r['cardinality']}) — {r['description']}"
            for r in schema.get("relationships", [])
        )
        relationships_section = f"Relationships:\n{rel_lines}" if rel_lines else ""

        return (
            "Generate SQL using only the provided schema and return parameterized "
            "inputs for build_sql_query (not raw SQL first).\n\n"
            f"Domain: {domain}\n\n"
            f"{tables_section}\n\n"
            f"{relationships_section}\n\n"
            "Rules:\n"
            "- Use only listed columns from the tables above.\n"
            "- When both assessment and finding data are needed, use a JOIN via the join parameter.\n"
            "- Prefer exact filters for status/severity fields.\n"
            "- Do NOT add a LIMIT unless the user explicitly asks for a sample, top N, or a limited number of results. "
            "When the user asks for 'all', 'any', or a complete list, omit LIMIT to return complete results.\n"
            "- If aggregation is needed, include matching group_by columns.\n"
            "- Default to the 'finding' table unless assessment-level fields are required.\n"
            "- In JOINs, always use the full schema-qualified table name shown in parentheses above (e.g. postgresql.public.cvi_psirts_view_...), NOT the short alias. "
            "Always provide table_alias for the FROM table when joining (e.g. table_alias='assets').\n\n"
            f"User question: {user_question}"
        )

    columns = "\n".join(
        f"- {column['name']} ({column['type']}): {column['description']}"
        for column in schema["column_schema"]
    )
    return (
        "Generate SQL using only the provided schema and return parameterized "
        "inputs for build_sql_query (not raw SQL first).\n\n"
        f"Domain: {domain}\n"
        f"Table: {schema['table']}\n"
        f"Columns:\n{columns}\n\n"
        "Rules:\n"
        "- Use only listed columns.\n"
        "- Prefer exact filters for status/severity fields.\n"
        "- Do NOT add a LIMIT unless the user explicitly asks for a sample, top N, or a limited number of results. "
        "When the user asks for 'all', 'any', or a complete list, omit LIMIT to return complete results.\n"
        "- If aggregation is needed, include matching group_by columns.\n"
        "- In JOINs, always use the full schema-qualified table name from the schema (e.g. postgresql.public.cvi_psirts_view_...), NOT the short alias. "
        "Always provide table_alias for the FROM table when joining (e.g. table_alias='assets').\n"
        "- AGGREGATION WARNING: The advisory count columns on the assets table (e.g. critical_security_advisories_count, "
        "high_security_advisories_count) are PER-DEVICE counts. Do NOT use SUM() on these columns to count total distinct "
        "advisories — that double-counts advisories affecting multiple devices. To count total distinct advisories, "
        "JOIN to the psirts table and use COUNT_DISTINCT on psirts.psirt_id with appropriate filters "
        "(e.g. vulnerability_status = 'VUL'). "
        "When filtering by severity on the bulletins table, use bulletins.severity_level_name (NOT 'severity'). "
        "To count advisories by severity, use GROUP BY bulletins.severity_level_name with COUNT_DISTINCT on psirts.psirt_id "
        "and filter WHERE bulletins.severity_level_name IN ('Critical', 'High'). "
        "Do NOT use two identical COUNT(DISTINCT psirt_id) columns without a GROUP BY or CASE WHEN — that returns the same number.\n\n"
        f"User question: {user_question}"
    )


# ---------------------------------------------------------------------------
# Pydantic models for structured input
# ---------------------------------------------------------------------------


class FilterOperator(str, Enum):
    EQ = "="
    NEQ = "!="
    LT = "<"
    GT = ">"
    LTE = "<="
    GTE = ">="
    IN = "IN"
    NOT_IN = "NOT IN"
    LIKE = "LIKE"
    ILIKE = "ILIKE"
    IS_NULL = "IS NULL"
    IS_NOT_NULL = "IS NOT NULL"


class FilterCondition(BaseModel):
    """A single WHERE predicate: <column> <operator> <value>."""

    column: str = Field(..., description="Column name (plain SQL identifier).")
    operator: FilterOperator = Field(..., description="Comparison operator.")
    value: str | int | float | list[str | int | float] | None = Field(
        None,
        description=(
            "Scalar value for most operators; list for IN / NOT IN; "
            "omit (null) for IS NULL / IS NOT NULL."
        ),
    )

    @field_validator("column")
    @classmethod
    def _check_column(cls, v: str) -> str:
        return _validate_identifier(v, "column")

    @model_validator(mode="after")
    def _check_value_matches_operator(self) -> "FilterCondition":
        op = self.operator
        value = self.value
        if op in (FilterOperator.IS_NULL, FilterOperator.IS_NOT_NULL):
            if value is not None:
                raise ValueError(f"Operator '{op.value}' must not have a value.")
        elif op in (FilterOperator.IN, FilterOperator.NOT_IN):
            if not isinstance(value, list) or len(value) == 0:
                raise ValueError(
                    f"Operator '{op.value}' requires a non-empty list value."
                )
        else:
            if value is None:
                raise ValueError(f"Operator '{op.value}' requires a scalar value.")
        return self


class AggregationSpec(BaseModel):
    """An aggregation expression: <function>(<column>) [AS <alias>]."""

    function: Literal["COUNT", "SUM", "AVG", "MIN", "MAX", "COUNT_DISTINCT"] = Field(
        ..., description="Aggregation function."
    )
    column: str = Field(
        ...,
        description="Column to aggregate. Use '*' only with COUNT.",
    )
    alias: str | None = Field(
        None, description="Optional output alias (plain identifier)."
    )

    @field_validator("column")
    @classmethod
    def _check_column(cls, v: str) -> str:
        if v == "*":
            return v
        return _validate_identifier(v, "aggregation column")

    @field_validator("alias")
    @classmethod
    def _check_alias(cls, v: str | None) -> str | None:
        if v is not None:
            return _validate_identifier(v, "alias")
        return v

    @model_validator(mode="after")
    def _check_star_only_with_count(self) -> "AggregationSpec":
        if self.column == "*" and self.function not in ("COUNT", "COUNT_DISTINCT"):
            raise ValueError("'*' column is only valid with COUNT.")
        return self


class OrderBySpec(BaseModel):
    """An ORDER BY term: <column> [ASC|DESC]."""

    column: str = Field(..., description="Column to sort by.")
    direction: Literal["ASC", "DESC"] = Field("ASC", description="Sort direction.")

    @field_validator("column")
    @classmethod
    def _check_column(cls, v: str) -> str:
        return _validate_identifier(v, "order-by column")


class JoinSpec(BaseModel):
    """A JOIN clause: <join_type> JOIN <table> [AS <alias>] ON <on_left> = <on_right>."""

    join_type: Literal["INNER", "LEFT", "RIGHT", "FULL"] = Field(
        "INNER", description="JOIN type (INNER, LEFT, RIGHT, or FULL)."
    )
    table: str = Field(
        ...,
        description="Table to join (may be schema-qualified, e.g. catalog.schema.table).",
    )
    alias: str | None = Field(
        None,
        description=(
            "Optional short alias for the joined table. "
            "Use this to qualify columns in SELECT, WHERE, ON, etc. "
            "(e.g. alias='psirts' lets you write psirts.serial_number)."
        ),
    )
    on_left: str = Field(
        ...,
        description=(
            "Left side column of the join condition. "
            "Qualify with table alias when columns are ambiguous "
            "(e.g. assets.serial_number)."
        ),
    )
    on_right: str = Field(
        ...,
        description=(
            "Right side column of the join condition. "
            "Qualify with table alias when columns are ambiguous "
            "(e.g. psirts.serial_number)."
        ),
    )

    @field_validator("table")
    @classmethod
    def _check_table(cls, v: str) -> str:
        return _validate_identifier(v, "join table")

    @field_validator("alias")
    @classmethod
    def _check_alias(cls, v: str | None) -> str | None:
        if v is not None:
            return _validate_identifier(v, "join alias")
        return v

    @field_validator("on_left", "on_right")
    @classmethod
    def _check_join_columns(cls, v: str) -> str:
        return _validate_identifier(v, "join column")


# ---------------------------------------------------------------------------
# SQL building helpers
# ---------------------------------------------------------------------------


def _render_literal(value: str | int | float) -> str:
    if isinstance(value, str):
        return f"'{_escape_string_literal(value)}'"
    return str(value)  # int / float are safe as-is


def _render_filter(f: FilterCondition) -> str:
    op = f.operator
    col = f.column

    if op == FilterOperator.IS_NULL:
        return f"{col} IS NULL"
    if op == FilterOperator.IS_NOT_NULL:
        return f"{col} IS NOT NULL"

    if op in (FilterOperator.IN, FilterOperator.NOT_IN):
        values_sql = ", ".join(_render_literal(v) for v in f.value)  # type: ignore[union-attr]
        return f"{col} {op.value} ({values_sql})"

    # Trino does not support ILIKE — emulate with LOWER() LIKE LOWER()
    if op == FilterOperator.ILIKE:
        return f"LOWER({col}) LIKE LOWER({_render_literal(f.value)})"  # type: ignore[arg-type]

    return f"{col} {op.value} {_render_literal(f.value)}"  # type: ignore[arg-type]


def _render_aggregation(agg: AggregationSpec) -> str:
    func = "COUNT" if agg.function == "COUNT_DISTINCT" else agg.function
    distinct = "DISTINCT " if agg.function == "COUNT_DISTINCT" else ""
    expr = f"{func}({distinct}{agg.column})"
    if agg.alias:
        expr += f" AS {agg.alias}"
    return expr


def _build_sql(
    table_name: str,
    columns: list[str] | None,
    filters: list[FilterCondition] | None,
    aggregations: list[AggregationSpec] | None,
    group_by: list[str] | None,
    order_by: list[OrderBySpec] | None,
    limit: int | None,
    joins: list[JoinSpec] | None = None,
    extra_where: list[str] | None = None,
    table_alias: str | None = None,
) -> str:
    # SELECT clause
    select_parts: list[str] = []
    if aggregations:
        select_parts.extend(_render_aggregation(a) for a in aggregations)
    if columns:
        select_parts.extend(columns)
    if not select_parts:
        select_parts = ["*"]

    from_clause = table_name
    if table_alias:
        from_clause += f" AS {table_alias}"
    sql = f"SELECT {', '.join(select_parts)}\nFROM {from_clause}"

    # JOIN clauses
    if joins:
        for j in joins:
            join_target = j.table
            if j.alias:
                join_target += f" AS {j.alias}"
            sql += f"\n{j.join_type} JOIN {join_target} ON {j.on_left} = {j.on_right}"

    # WHERE clause
    where_parts: list[str] = []
    if filters:
        where_parts.extend(f"({_render_filter(f)})" for f in filters)
    if extra_where:
        where_parts.extend(f"({clause})" for clause in extra_where)
    if where_parts:
        sql += f"\nWHERE {' AND '.join(where_parts)}"

    # GROUP BY clause
    if group_by:
        sql += f"\nGROUP BY {', '.join(group_by)}"

    # ORDER BY clause
    if order_by:
        order_parts = [f"{o.column} {o.direction}" for o in order_by]
        sql += f"\nORDER BY {', '.join(order_parts)}"

    # LIMIT clause
    if limit is not None:
        sql += f"\nLIMIT {limit}"
    if settings.deploy_env != "prod":
        logger.debug("[sql_builder] built_sql=%s", sql)
    return sql


# ---------------------------------------------------------------------------
# MCP server
# ---------------------------------------------------------------------------

mcp = FastMCP(
    "sql_query_builder_mcp_server",
    instructions="""
This MCP server generates safe SQL SELECT queries from structured parameters.

CRITICAL: ALWAYS use build_sql_query to generate SQL for execution by trino_mcp.
NEVER write raw SQL by hand. The build_sql_query tool applies mandatory security
filters automatically (e.g. execution_id scoping for security hardening queries).
If build_sql_query returns an error, fix the input parameters and call
build_sql_query again — do NOT bypass it by writing SQL manually.

Available tools:

1. get_table_schema(domain)
   Returns the domain-specific schema for a security domain,
   including table name, columns, and filter hints.

2. get_security_query_context(domain, user_question)
   Returns schema plus an LLM-ready planning prompt for the given user question.

3. build_sql_query(...)
   Generate a safe data query by providing a table name, optional column list,
   filter conditions, aggregations, GROUP BY, ORDER BY, and a LIMIT.
   All inputs are validated; no raw SQL is accepted, preventing injection.
   For security_hardening queries, an execution_id filter is injected
   automatically to scope results to the latest pipeline execution.

Available resources:

- schema://security/{domain}
  Read the schema JSON for a domain where domain is:
  security_advisory or security_hardening.

Available prompts:

- security_sql_planning_prompt(domain, user_question)
  Provides a planning prompt that agents can use for query generation workflow.

IMPORTANT: The SQL queries, table names, column names, and schema details
generated by this server are internal implementation details. They must NEVER
be displayed to the end user. Only the final query results should be presented.
""",
    host=settings.mcp_host,
    port=settings.mcp_port,
    sse_path=settings.mcp_sse_path,
)


@mcp.tool()
def get_table_schema(domain: SchemaDomain) -> dict[str, Any]:
    """
    Return table schema metadata for a supported security domain.

    Args:
        domain: One of "security_advisory" or "security_hardening".

    Returns:
        Dict with domain, table name, column list, and example filters.
    """
    logger.info("[get_table_schema] domain=%s", domain)
    result = _get_schema_for_domain(domain)
    if settings.deploy_env != "prod":
        table_keys = (
            list(result.get("tables", {}).keys()) if isinstance(result, dict) else []
        )
        logger.info(
            "[get_table_schema] domain=%s tables=%s column_count=%d",
            domain,
            table_keys,
            (
                sum(
                    len(t.get("columns", [])) for t in result.get("tables", {}).values()
                )
                if isinstance(result, dict)
                else 0
            ),
        )
    return result


@mcp.tool()
def get_security_query_context(
    domain: SchemaDomain,
    user_question: str | None = None,
) -> dict[str, Any]:
    """
    Return schema metadata and an optional LLM-planning prompt.

    Args:
        domain: One of "security_advisory" or "security_hardening".
        user_question: Optional natural language question to embed in the prompt.

    Returns:
        Dict with:
        - schema: domain schema metadata
        - prompt: query-planning prompt when user_question is provided
    """
    payload: dict[str, Any] = {"schema": _get_schema_for_domain(domain)}
    if user_question and user_question.strip():
        payload["prompt"] = _build_security_query_prompt(
            domain,
            user_question.strip(),
        )
    return payload


@mcp.prompt(
    name="security_sql_planning_prompt",
    description="Planning prompt for building SQL params from a security domain and question",
)
def security_sql_planning_prompt(domain: SchemaDomain, user_question: str) -> str:
    return _build_security_query_prompt(domain, user_question)


@mcp.tool()
def build_sql_query(
    table_name: str,
    columns: list[str] | None = None,
    filters: list[FilterCondition] | None = None,
    aggregations: list[AggregationSpec] | None = None,
    group_by: list[str] | None = None,
    order_by: list[OrderBySpec] | None = None,
    limit: int | None = None,
    joins: list[JoinSpec] | None = None,
    table_alias: str | None = None,
) -> dict:
    """
    Build a safe SQL SELECT query from structured parameters.

    All identifier names (table, columns, aliases) are validated against a strict
    regex that only allows plain SQL identifiers (letters, digits, underscores,
    optional dot-qualified schema/catalog prefix).  All string values in filters
    are escaped.  Operators and aggregation functions are restricted to known-safe
    enums — no raw SQL fragments are accepted anywhere.

    Args:
        table_name:
            Target table or view. May be schema-qualified (e.g. "catalog.schema.table").
            Must match ^[A-Za-z_][A-Za-z0-9_]*(\\.[A-Za-z_][A-Za-z0-9_]*){0,3}$.

        columns:
            Explicit column names to SELECT.  Omit (or pass null) to SELECT *.
            Ignored when aggregations cover all desired output columns.
            Example: ["id", "hostname", "region"]

        filters:
            List of WHERE predicates.  Each item has:
            - column   (str)  — column name
            - operator (str)  — one of: =, !=, <, >, <=, >=, IN, NOT IN,
                                LIKE, ILIKE, IS NULL, IS NOT NULL
            - value           — scalar (str/int/float) for most operators;
                                list for IN / NOT IN; omit for IS NULL / IS NOT NULL
            All predicates are ANDed together.
            Example: [{column:"status", operator:"=", value:"active"},
                      {column:"severity", operator:"IN", value:["high","critical"]}]

        aggregations:
            List of aggregation expressions to include in SELECT.  Each item has:
            - function (str) — COUNT, SUM, AVG, MIN, MAX, COUNT_DISTINCT
            - column   (str) — column to aggregate (use "*" only with COUNT)
            - alias    (str, optional) — output column alias
            Example: [{function:"COUNT", column:"*", alias:"total"},
                      {function:"AVG",   column:"cvss_score", alias:"avg_cvss"}]

        group_by:
            Columns for GROUP BY.  Required when aggregations are mixed with
            non-aggregated columns.
            Example: ["region", "severity"]

        order_by:
            List of ORDER BY terms.  Each item has:
            - column    (str) — column name
            - direction (str) — "ASC" or "DESC" (default "ASC")
            Example: [{column:"created_at", direction:"DESC"}]

        limit:
            Maximum number of rows to return.  Must be a positive integer and
            may not exceed the server's configured max_limit
            (configured max_limit by default).
            IMPORTANT: Do NOT set limit unless the user explicitly asks for a
            sample, top-N, or a specific number of results.  Questions like
            "are there any devices...", "which devices...", "show me all...",
            or "how many..." require complete results — omit limit (pass null)
            so all matching rows are returned.

        joins:
            Optional list of JOIN clauses.  Each item has:
            - join_type (str) — INNER, LEFT, RIGHT, or FULL (default INNER)
            - table     (str) — table to join (may be schema-qualified)
            - alias     (str, optional) — short alias for the joined table,
              used to qualify columns (e.g. alias="psirts" → psirts.serial_number)
            - on_left   (str) — left column of the join condition (qualify with alias)
            - on_right  (str) — right column of the join condition (qualify with alias)
            IMPORTANT: When columns exist in multiple tables, qualify them with
            table_alias or join alias to avoid ambiguous column errors.
            Example (advisory assets JOIN psirts):
              table_alias="assets",
              joins=[{join_type:"INNER",
                      table:"postgresql.public.cvi_psirts_view_1__3__5",
                      alias:"psirts",
                      on_left:"assets.serial_number",
                      on_right:"psirts.serial_number"}]

        table_alias:
            Optional short alias for the main FROM table. Use this to qualify
            columns when joins create ambiguity.
            Example: table_alias="assets"

    Returns:
        A dict with:
        - "sql"    — the generated SQL string (internal use only — never show to user)
        - "params" — always an empty dict (values are inlined safely)
        - "table"  — the validated table name (internal use only — never show to user)
    """

    if settings.deploy_env != "prod":
        logger.info(
            "[sql_builder] request | table=%s columns=%s filters=%s aggs=%s group_by=%s joins=%s limit=%s",
            table_name,
            columns,
            filters,
            aggregations,
            group_by,
            joins,
            limit,
        )

    try:
        # --- validate table name ---
        _validate_identifier(table_name, "table_name")

        # --- validate table_alias ---
        validated_table_alias: str | None = None
        if table_alias:
            validated_table_alias = _validate_identifier(table_alias, "table_alias")

        # --- optional allowlist check ---
        allowed = [t.strip() for t in settings.allowed_tables.split(",") if t.strip()]
        if allowed and table_name not in allowed:
            raise ValueError(
                f"Table '{table_name}' is not in the permitted table list. "
                f"Allowed: {allowed}"
            )

        # --- validate plain column names ---
        validated_columns: list[str] | None = None
        if columns:
            validated_columns = [_validate_identifier(c, "column") for c in columns]

        # --- validate group_by identifiers ---
        validated_group_by: list[str] | None = None
        if group_by:
            validated_group_by = [
                _validate_identifier(c, "group_by column") for c in group_by
            ]

        # --- validate aggregation + column mix requires GROUP BY ---
        if aggregations and validated_columns and not validated_group_by:
            raise ValueError(
                "When aggregations and plain columns are used together, "
                "group_by must include the non-aggregated columns. "
                f"Add group_by={validated_columns} and retry."
            )

        # --- validate limit ---
        validated_limit: int | None = None
        if limit is not None:
            if limit <= 0:
                raise ValueError("limit must be a positive integer.")
            if limit > settings.max_limit:
                raise ValueError(
                    f"limit {limit} exceeds the maximum allowed value of {settings.max_limit}."
                )
            validated_limit = limit
            if limit <= 20:
                logger.warning(
                    "[sql_builder] low LIMIT %d detected — ensure the user "
                    "explicitly requested a limited result set",
                    limit,
                )

        # --- auto-inject execution_id filter for hardening finding table ---
        extra_where: list[str] | None = None
        if _is_hardening_finding_table(table_name):
            extra_where = [_latest_execution_id_filter()]
            logger.info(
                "[sql_builder] auto-injecting latest execution_id filter for hardening table"
            )

        # --- resolve join table aliases to full qualified names ---
        alias_map = _get_table_alias_map()
        reverse_alias_map = {v: k for k, v in alias_map.items()}

        # Auto-set table_alias for the FROM table if not provided.
        # This must happen even without joins — the LLM often qualifies
        # columns with the alias (e.g. bulletins.psirt_id) on single-table
        # queries that have no AS clause, causing Trino COLUMN_NOT_FOUND.
        if not validated_table_alias and table_name in reverse_alias_map:
            validated_table_alias = reverse_alias_map[table_name]
            logger.info(
                "[sql_builder] auto-set table_alias=%s for %s",
                validated_table_alias,
                table_name,
            )

        if joins:
            for j in joins:
                if j.table in alias_map:
                    original_alias = j.table
                    resolved = alias_map[j.table]
                    logger.info(
                        "[sql_builder] resolved join alias %r -> %s",
                        j.table,
                        resolved,
                    )
                    j.table = resolved
                    # Auto-set alias so column references like psirts.col resolve
                    if not j.alias:
                        j.alias = original_alias
                elif not j.alias and j.table in reverse_alias_map:
                    # Full table name provided but no alias — auto-set it
                    j.alias = reverse_alias_map[j.table]
                    logger.info(
                        "[sql_builder] auto-set join alias %s for table %s",
                        j.alias,
                        j.table,
                    )

            # Auto-qualify unqualified on_left with the base table alias
            base_alias = validated_table_alias
            if base_alias:
                for j in joins:
                    if "." not in j.on_left:
                        qualified = f"{base_alias}.{j.on_left}"
                        logger.info(
                            "[sql_builder] auto-qualified on_left %r -> %s",
                            j.on_left,
                            qualified,
                        )
                        j.on_left = qualified

        # --- validate filter/column names exist in schema ---
        columns_by_table = _get_known_columns_by_table()
        # Build alias -> full table name mapping for this query
        active_tables: dict[str, str] = {}  # alias -> fully-qualified table name
        if validated_table_alias:
            active_tables[validated_table_alias.lower()] = table_name
        # Also map the unaliased table name
        reverse_alias = {v: k for k, v in _get_table_alias_map().items()}
        if table_name in reverse_alias:
            active_tables[reverse_alias[table_name].lower()] = table_name
        if joins:
            for j in joins:
                if j.alias:
                    active_tables[j.alias.lower()] = j.table
                if j.table in reverse_alias:
                    active_tables[reverse_alias[j.table].lower()] = j.table

        def _check_column_exists(col_ref: str) -> str | None:
            """Return an error message if col_ref is not a known column, else None."""
            if "." in col_ref:
                prefix, col_name = col_ref.split(".", 1)
                fq_table = active_tables.get(prefix.lower())
                if fq_table and fq_table in columns_by_table:
                    if col_name not in columns_by_table[fq_table]:
                        return (
                            f"Column '{col_name}' does not exist in table "
                            f"'{prefix}'. Available columns: "
                            f"{sorted(columns_by_table[fq_table])}"
                        )
            return None

        invalid_columns: list[str] = []
        for col_ref in validated_columns or []:
            err = _check_column_exists(col_ref)
            if err:
                invalid_columns.append(err)
        for f in filters or []:
            err = _check_column_exists(f.column)
            if err:
                invalid_columns.append(err)
        for col_ref in validated_group_by or []:
            err = _check_column_exists(col_ref)
            if err:
                invalid_columns.append(err)
        if invalid_columns:
            error_msg = "Column validation failed: " + "; ".join(invalid_columns)
            logger.warning("[sql_builder] %s", error_msg)
            raise ValueError(error_msg)

        sql = _build_sql(
            table_name=table_name,
            columns=validated_columns,
            filters=filters,
            aggregations=aggregations,
            group_by=validated_group_by,
            order_by=order_by,
            limit=validated_limit,
            joins=joins,
            extra_where=extra_where,
            table_alias=validated_table_alias,
        )

        if settings.deploy_env != "prod":
            logger.info(
                "[sql_builder] table=%s columns=%s filters=%d aggs=%d joins=%d sql_len=%d",
                table_name,
                validated_columns,
                len(filters or []),
                len(aggregations or []),
                len(joins or []),
                len(sql),
            )
            logger.info("[sql_builder] generated_sql=%s", sql)

        return {
            "sql": sql,
            "params": {},
            "table": table_name,
        }
    except Exception as exc:
        logger.error(
            "[sql_builder] failed | table=%s error=%s", table_name, exc, exc_info=True
        )
        raise


if __name__ == "__main__":
    mcp.run(transport="sse")

