"""Column and relationship schemas for the security_hardening domain."""

from __future__ import annotations

HARDENING_COLUMN_SCHEMA = [
    {
        "name": "finding_id",
        "type": "uuid|string",
        "description": "Unique finding identifier.",
    },
    {
        "name": "run_id",
        "type": "uuid|string",
        "description": "Assessment run identifier.",
    },
    {
        "name": "platform_account_id",
        "type": "uuid|string",
        "description": "Platform account identifier.",
    },
    {
        "name": "customer_id",
        "type": "uuid|string",
        "description": "Customer identifier.",
    },
    {
        "name": "assessment_id",
        "type": "uuid|string",
        "description": "Assessment identifier.",
    },
    {
        "name": "execution_id",
        "type": "uuid|string",
        "description": "Execution identifier for pipeline run.",
    },
    {"name": "source", "type": "uuid|string", "description": "Rule/source identifier."},
    {
        "name": "source_id",
        "type": "uuid|string",
        "description": "Rule/source identifier (duplicate logical key).",
    },
    {
        "name": "ic_type",
        "type": "string|null",
        "description": "Implementation-check type when available.",
    },
    {"name": "asset_key", "type": "string", "description": "Device asset key."},
    {"name": "pid", "type": "string", "description": "Product identifier (PID)."},
    {
        "name": "asset_entitlement",
        "type": "string|null",
        "description": "Entitlement metadata for the asset.",
    },
    {
        "name": "asset_type",
        "type": "string",
        "description": "Asset class (for example Hardware).",
    },
    {"name": "serial_number", "type": "string", "description": "Device serial number."},
    {
        "name": "product_family",
        "type": "string",
        "description": "Cisco product family.",
    },
    {"name": "hostname", "type": "string", "description": "Device hostname."},
    {
        "name": "os_version",
        "type": "string",
        "description": "Operating-system version.",
    },
    {
        "name": "os_type",
        "type": "string",
        "description": "Operating-system type (for example IOS-XE).",
    },
    {
        "name": "severity",
        "type": "string",
        "description": "Severity classification (HIGH/MEDIUM/UNKNOWN/etc.).",
    },
    {
        "name": "rule_name",
        "type": "string",
        "description": "Hardening rule/check name.",
    },
    {
        "name": "detected_at",
        "type": "timestamp",
        "description": "Finding detection timestamp.",
    },
    {
        "name": "technology",
        "type": "string|null",
        "description": "Technology tag if available.",
    },
    {
        "name": "finding_type",
        "type": "string",
        "description": "Finding kind (finding/ok/not_applicable/etc.).",
    },
    {
        "name": "finding_status",
        "type": "string",
        "description": "Result status (VIOLATED/NOT_VIOLATED/MISSING_INFO/etc.).",
    },
    {
        "name": "finding_description",
        "type": "string|json|null",
        "description": "Description payload (may be plain text or serialized JSON list).",
    },
    {
        "name": "reference_urls",
        "type": "string|json|null",
        "description": "Reference URLs payload.",
    },
    {
        "name": "finding_reason",
        "type": "string|null",
        "description": "Optional reason details.",
    },
    {
        "name": "evidence_log",
        "type": "json|string",
        "description": "Evidence payload with extracted telemetry artifacts.",
    },
    {
        "name": "management_system_id",
        "type": "string|null",
        "description": "Managing system identifier if set.",
    },
    {
        "name": "recommendation",
        "type": "string|null",
        "description": "Recommended remediation guidance.",
    },
    {
        "name": "remediation",
        "type": "string|null",
        "description": "Detailed remediation content.",
    },
    {
        "name": "functional_category",
        "type": "string|null",
        "description": "Functional category metadata.",
    },
    {
        "name": "assessment_category",
        "type": "string|null",
        "description": "Assessment category metadata.",
    },
    {
        "name": "architecture",
        "type": "string|null",
        "description": "Architecture metadata.",
    },
    {
        "name": "ic_description",
        "type": "string|null",
        "description": "Implementation-check description.",
    },
    {
        "name": "cmd_collection_time",
        "type": "timestamp|null",
        "description": "Command collection timestamp if present.",
    },
]

HARDENING_ASSESSMENT_COLUMN_SCHEMA = [
    {
        "name": "assessment_id",
        "type": "string",
        "description": "Unique assessment identifier.",
        "metadata": {"unique": True},
    },
    {
        "name": "platform_account_id",
        "type": "string",
        "description": "Platform account identifier.",
    },
    {
        "name": "assessment_name",
        "type": "string",
        "description": "Name of the assessment.",
    },
    {
        "name": "assessment_status",
        "type": "string",
        "description": "Status of the assessment.",
    },
    {
        "name": "assessment_description",
        "type": "string",
        "description": "Detailed description of the assessment.",
    },
    {
        "name": "assessment_category",
        "type": "string",
        "description": "Category of the assessment.",
    },
    {
        "name": "assessment_tags",
        "type": "string",
        "description": "Tags associated with the assessment.",
    },
    {
        "name": "is_active",
        "type": "boolean",
        "description": "Indicates whether the assessment is active.",
    },
    {
        "name": "created_date",
        "type": "timestamp",
        "description": "Timestamp when the assessment was created.",
    },
    {
        "name": "created_by",
        "type": "string",
        "description": "User who created the assessment.",
    },
    {
        "name": "modified_at",
        "type": "timestamp",
        "description": "Timestamp when the assessment was last modified.",
    },
    {
        "name": "modified_by",
        "type": "string",
        "description": "User who last modified the assessment.",
    },
    {
        "name": "version",
        "type": "integer",
        "description": "Version number of the assessment.",
    },
    {
        "name": "owner_id",
        "type": "string",
        "description": "Identifier of the assessment owner.",
    },
    {
        "name": "owner_name",
        "type": "string",
        "description": "Name of the assessment owner.",
    },
]

HARDENING_RELATIONSHIP_SCHEMA = [
    {
        "id": "finding_assessment",
        "from_table": "assessment",
        "from_column": "assessment_id",
        "to_table": "finding",
        "to_column": "assessment_id",
        "cardinality": "1:*",
        "description": "An assessment has many findings",
    }
]

