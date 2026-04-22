"""Column and relationship schemas for the security_advisory domain."""

from __future__ import annotations

ADVISORY_COLUMN_SCHEMA = [
    {
        "name": "product_family",
        "type": "string",
        "description": "Cisco product family name.",
        "examples": ["Cisco UCS C-Series Rack Servers"],
    },
    {
        "name": "software_version",
        "type": "string",
        "description": "Detected software version on the asset.",
        "examples": ["3.0(1c)"],
    },
    {
        "name": "updated_at",
        "type": "timestamp",
        "description": "Last refresh timestamp for this match record.",
        "examples": ["2026-03-30T13:22:43", "2026-03-27T13:19:05"],
    },
    {
        "name": "vulnerability_reason",
        "type": "string",
        "description": "Reason why record is flagged vulnerable/potentially vulnerable.",
        "enum_values": [
            "Match on SW Type, SW Version",
            "Match on SW Type, SW Version; Manual Verification Required",
        ],
        "examples": [
            "Match on SW Type, SW Version",
            "Match on SW Type, SW Version; Manual Verification Required",
        ],
    },
    {
        "name": "vulnerability_status",
        "type": "string",
        "description": "Vulnerability assessment status.",
        "enum_values": ["VUL", "POTVUL"],
        "examples": ["VUL", "POTVUL"],
    },
    {
        "name": "serial_number",
        "type": "string",
        "description": "Asset serial number.",
        "examples": ["EM8775C4DC"],
    },
    {
        "name": "product_id",
        "type": "string",
        "description": "Cisco PID/model identifier.",
        "examples": ["UCSC-C220-M4L"],
    },
    {
        "name": "psirt_id",
        "type": "integer",
        "description": "Cisco PSIRT advisory identifier.",
        "examples": [1480, 1492, 2890, 3191],
    },
    {
        "name": "platform_account_id",
        "type": "string",
        "description": "Customer/platform account identifier.",
        "examples": ["0c1ba711-9b16-470d-8fed-56970cf9fd07"],
    },
    {
        "name": "partition_key",
        "type": "string",
        "description": "Internal partition/hash key for storage.",
        "examples": ["27a72f88553527edc12b78758ae8e51d"],
    },
]
# {
#     "name": "sav_id",
#     "type": "string|null",
#     "description": "Service advisory/vulnerability internal identifier.",
#     "examples": [None],
# },
# {
#     "name": "caveat",
#     "type": "string",
#     "description": "Special handling notes or manual verification instructions; can be empty string.",
#     "examples": [
#         "",
#         "Manual verification required to check if the Cisco IMC web-management interface is enabled.",
#     ],
# },
# {
#     "name": "source",
#     "type": "string",
#     "description": "Record source system.",
#     "enum_values": ["CXC"],
#     "examples": ["CXC"],
# },


ADVISORY_ASSETS_COLUMN_SCHEMA = [
    # Identifiers
    {"name": "id", "type": "string", "description": "Asset unique identifier."},
    {
        "name": "instance_id",
        "type": "integer",
        "description": "Asset instance identifier.",
    },
    {
        "name": "serial_number",
        "type": "string",
        "description": "Device serial number (join key to psirts).",
    },
    {
        "name": "platform_account_id",
        "type": "string",
        "description": "Customer/platform account identifier.",
    },
    {"name": "parent_id", "type": "string", "description": "Parent asset identifier."},
    # Asset attributes
    {
        "name": "asset_type",
        "type": "string",
        "description": "Type of asset (e.g., Hardware).",
    },
    {
        "name": "product_family",
        "type": "string",
        "description": "Cisco product family.",
    },
    {
        "name": "product_id",
        "type": "string",
        "description": "Cisco PID/model identifier.",
    },
    {"name": "product_name", "type": "string", "description": "Product name."},
    {
        "name": "product_description",
        "type": "string",
        "description": "Product description.",
    },
    {
        "name": "product_type",
        "type": "string",
        "description": "Product type classification.",
    },
    {
        "name": "product_version_id",
        "type": "string",
        "description": "Product version identifier.",
    },
    {"name": "hostname", "type": "string", "description": "Device hostname."},
    {"name": "ip_address", "type": "string", "description": "Device IP address."},
    {
        "name": "tags",
        "type": "array|string",
        "description": "Tags associated with the asset.",
    },
    {"name": "role", "type": "string", "description": "Asset role."},
    {"name": "quantity", "type": "integer", "description": "Asset quantity."},
    {"name": "equipment_type", "type": "string", "description": "Equipment type."},
    # Software
    {
        "name": "software_version",
        "type": "string",
        "description": "Software/OS version.",
    },
    {"name": "software_type", "type": "string", "description": "Software type."},
    {
        "name": "software_patch_version",
        "type": "string",
        "description": "Software patch version.",
    },
    {"name": "cx_level", "type": "string", "description": "CX level."},
    {"name": "cx_level_label", "type": "string", "description": "CX level label."},
    # Advisory counts
    {
        "name": "advisory_count",
        "type": "integer",
        "description": "Per-device number of advisories. Do NOT SUM across rows to count total distinct advisories (double-counts).",
    },
    {
        "name": "all_advisory_count",
        "type": "integer",
        "description": "Per-device total advisory count including all statuses. Do NOT SUM across rows to count total distinct advisories (double-counts).",
    },
    {
        "name": "security_advisories_count",
        "type": "integer",
        "description": "Per-device security advisories count. Do NOT SUM across rows to count total distinct advisories (double-counts).",
    },
    {
        "name": "affected_security_advisories_count",
        "type": "integer",
        "description": "Per-device count of advisories where asset is affected. Do NOT SUM across rows to count total distinct advisories (double-counts).",
    },
    {
        "name": "potentially_affected_security_advisories_count",
        "type": "integer",
        "description": "Per-device count of advisories where asset is potentially affected. Do NOT SUM across rows to count total distinct advisories (double-counts).",
    },
    {
        "name": "critical_security_advisories_count",
        "type": "integer",
        "description": "Per-device count of critical severity advisories. Do NOT SUM across rows to count total distinct advisories (double-counts). JOIN to psirts and use COUNT_DISTINCT on psirt_id instead.",
    },
    {
        "name": "high_security_advisories_count",
        "type": "integer",
        "description": "Per-device count of high severity advisories. Do NOT SUM across rows to count total distinct advisories (double-counts). JOIN to psirts and use COUNT_DISTINCT on psirt_id instead.",
    },
    # Signal/timestamp fields
    {
        "name": "created_at",
        "type": "timestamp",
        "description": "Asset record creation timestamp.",
    },
    {"name": "created_by", "type": "string", "description": "Created by user."},
    {"name": "created_date", "type": "timestamp", "description": "Asset created date."},
    {
        "name": "updated_at",
        "type": "timestamp",
        "description": "Asset record last updated timestamp.",
    },
    {"name": "updated_by", "type": "string", "description": "Updated by user."},
    {
        "name": "last_update_date",
        "type": "timestamp",
        "description": "Last update date.",
    },
    {"name": "last_scan", "type": "timestamp", "description": "Last scan timestamp."},
    {
        "name": "last_signal_date",
        "type": "timestamp",
        "description": "Last telemetry signal date.",
    },
    {
        "name": "last_signal_type",
        "type": "string",
        "description": "Type of last telemetry signal.",
    },
]
# Customer/org
# {"name": "cav_id", "type": "string", "description": "CAV asset identifier."},
# {
#     "name": "cav_bu_id",
#     "type": "string",
#     "description": "CAV business unit identifier.",
# },
# {"name": "hw_id", "type": "string", "description": "Hardware identifier."},
# {
#     "name": "hardware_eox_id",
#     "type": "string",
#     "description": "Hardware EOX record identifier.",
# },
# {
#     "name": "software_eox_id",
#     "type": "integer",
#     "description": "Software EOX record identifier.",
# },
# {
#     "name": "importance",
#     "type": "string",
#     "description": "Asset importance classification.",
# },
# {"name": "connectivity", "type": "string", "description": "Connectivity status."},
# {
#     "name": "telemetry_status",
#     "type": "string",
#     "description": "Telemetry collection status.",
# },
# {
#     "name": "is_cspi",
#     "type": "boolean|integer",
#     "description": "Whether asset is CSPI.",
# },
# {"name": "account_name", "type": "string", "description": "Customer account name."},
# {"name": "customer_name", "type": "string", "description": "Customer name."},
# {"name": "location", "type": "string", "description": "Asset location."},
# {"name": "site", "type": "string", "description": "Site identifier."},
# {"name": "site_name", "type": "string", "description": "Site name."},
# {
#     "name": "management_system_id",
#     "type": "string",
#     "description": "Managing system identifier.",
# },
# {
#     "name": "management_system_type",
#     "type": "string",
#     "description": "Type of managing system.",
# },
# {"name": "data_source", "type": "string", "description": "Data source identifier."},
# {
#     "name": "managed_by_id",
#     "type": "string",
#     "description": "Managed-by system identifier.",
# },
# # Contract/coverage
# {"name": "contract_id", "type": "integer", "description": "Contract identifier."},
# {"name": "contract_number", "type": "string", "description": "Contract number."},
# {"name": "contract_status", "type": "string", "description": "Contract status."},
# {"name": "contract_owner", "type": "string", "description": "Contract owner."},
# {
#     "name": "contract_start_date",
#     "type": "timestamp",
#     "description": "Contract start date.",
# },
# {
#     "name": "contract_end_date",
#     "type": "timestamp",
#     "description": "Contract end date.",
# },
# {"name": "coverage_status", "type": "string", "description": "Coverage status."},
# {
#     "name": "coverage_start_date",
#     "type": "timestamp",
#     "description": "Coverage start date.",
# },
# {
#     "name": "coverage_end_date",
#     "type": "timestamp",
#     "description": "Coverage end date.",
# },
# {
#     "name": "max_coverage_end_date",
#     "type": "timestamp",
#     "description": "Maximum coverage end date.",
# },
# {"name": "support_level", "type": "string", "description": "Support level."},
# {"name": "support_type", "type": "string", "description": "Support type."},
# {
#     "name": "service_level_agreement_description",
#     "type": "string",
#     "description": "SLA description.",
# },
# {"name": "service_program", "type": "string", "description": "Service program."},
# {"name": "service_type", "type": "string", "description": "Service type."},
# Milestone / EOL
# {
#     "name": "current_milestone",
#     "type": "string",
#     "description": "Current lifecycle milestone.",
# },
# {
#     "name": "current_milestone_date",
#     "type": "timestamp",
#     "description": "Current milestone date.",
# },
# {
#     "name": "next_milestone",
#     "type": "string",
#     "description": "Next lifecycle milestone.",
# },
# {
#     "name": "next_milestone_date",
#     "type": "timestamp",
#     "description": "Next milestone date.",
# },
# {
#     "name": "last_date_of_support",
#     "type": "timestamp",
#     "description": "Last date of support.",
# },
# {
#     "name": "end_of_product_sale_date",
#     "type": "timestamp",
#     "description": "End of product sale date.",
# },
# {
#     "name": "end_of_software_maintenance_date",
#     "type": "timestamp",
#     "description": "End of software maintenance date.",
# },
# {
#     "name": "end_of_vulnerability_or_security_support_date",
#     "type": "timestamp",
#     "description": "End of vulnerability/security support date.",
# },
# {
#     "name": "end_of_sale_date",
#     "type": "timestamp",
#     "description": "End of sale date.",
# },
# {
#     "name": "end_of_new_service_attachment_date",
#     "type": "timestamp",
#     "description": "End of new service attachment date.",
# },
# {
#     "name": "end_of_routine_failure_analysis_date",
#     "type": "timestamp",
#     "description": "End of routine failure analysis date.",
# },
# {
#     "name": "end_of_service_contract_renewal_date",
#     "type": "timestamp",
#     "description": "End of service contract renewal date.",
# },
# {
#     "name": "end_of_bu_engineering_support_tac_date",
#     "type": "timestamp",
#     "description": "End of BU engineering support (TAC) date.",
# },
# {
#     "name": "end_of_last_date_of_support",
#     "type": "timestamp",
#     "description": "End of last date of support.",
# },
# {
#     "name": "end_of_last_hardware_ship_date",
#     "type": "timestamp",
#     "description": "End of last hardware ship date.",
# },
# {
#     "name": "end_of_life_external_announcement_date",
#     "type": "timestamp",
#     "description": "EOL external announcement date.",
# },
# {
#     "name": "end_of_life_internal_announcement_date",
#     "type": "timestamp",
#     "description": "EOL internal announcement date.",
# },
# # HWEOX milestones
# {
#     "name": "current_hweox_milestone",
#     "type": "string",
#     "description": "Current HWEOX milestone.",
# },
# {
#     "name": "hweox_current_milestone",
#     "type": "string",
#     "description": "HW EOX current milestone (alternate field).",
# },
# {
#     "name": "hweox_current_milestone_date",
#     "type": "timestamp",
#     "description": "HW EOX current milestone date.",
# },
# {
#     "name": "hweox_next_milestone",
#     "type": "string",
#     "description": "HW EOX next milestone.",
# },
# {
#     "name": "hweox_next_milestone_date",
#     "type": "timestamp",
#     "description": "HW EOX next milestone date.",
# },
# {
#     "name": "hweox_last_date_of_support",
#     "type": "timestamp",
#     "description": "HW EOX last date of support.",
# },
# {
#     "name": "hweox_end_of_sale_date",
#     "type": "timestamp",
#     "description": "HW EOX end of sale date.",
# },
# {
#     "name": "hweox_end_of_last_hardware_ship_date",
#     "type": "timestamp",
#     "description": "HW EOX end of last hardware ship date.",
# },
# {
#     "name": "hweox_end_of_life_external_announcement_date",
#     "type": "timestamp",
#     "description": "HW EOX EOL external announcement date.",
# },
# {
#     "name": "hweox_end_of_hardware_new_service_attachment_date",
#     "type": "timestamp",
#     "description": "HW EOX end of hardware new service attachment date.",
# },
# {
#     "name": "hweox_end_of_hardware_routine_failure_analysis_date",
#     "type": "timestamp",
#     "description": "HW EOX end of hardware routine failure analysis date.",
# },
# {
#     "name": "hweox_end_of_hardware_service_contract_renewal_date",
#     "type": "timestamp",
#     "description": "HW EOX end of hardware service contract renewal date.",
# },
# {
#     "name": "hweox_end_of_software_maintenance_releases_date",
#     "type": "timestamp",
#     "description": "HW EOX end of software maintenance releases date.",
# },
# # SWEOX milestones
# {
#     "name": "current_sweox_milestone",
#     "type": "string",
#     "description": "Current SWEOX milestone.",
# },
# {
#     "name": "sweox_current_milestone",
#     "type": "string",
#     "description": "SW EOX current milestone.",
# },
# {
#     "name": "sweox_current_milestone_date",
#     "type": "timestamp",
#     "description": "SW EOX current milestone date.",
# },
# {
#     "name": "sweox_next_milestone",
#     "type": "string",
#     "description": "SW EOX next milestone.",
# },
# {
#     "name": "sweox_next_milestone_date",
#     "type": "timestamp",
#     "description": "SW EOX next milestone date.",
# },
# {
#     "name": "sweox_last_date_of_support",
#     "type": "timestamp",
#     "description": "SW EOX last date of support.",
# },
# {
#     "name": "sweox_end_of_sale_date",
#     "type": "timestamp",
#     "description": "SW EOX end of sale date.",
# },
# {
#     "name": "sweox_end_of_life_external_announcement_date",
#     "type": "timestamp",
#     "description": "SW EOX EOL external announcement date.",
# },
# {
#     "name": "sweox_end_of_life_internal_announcement_date",
#     "type": "timestamp",
#     "description": "SW EOX EOL internal announcement date.",
# },
# {
#     "name": "sweox_end_of_bu_engineering_support_tac_date",
#     "type": "timestamp",
#     "description": "SW EOX end of BU engineering support (TAC) date.",
# },
# {
#     "name": "sweox_end_of_hardware_new_service_attachment_date",
#     "type": "timestamp",
#     "description": "SW EOX end of hardware new service attachment date.",
# },
# {
#     "name": "sweox_end_of_hardware_routine_failure_analysis_date",
#     "type": "timestamp",
#     "description": "SW EOX end of hardware routine failure analysis date.",
# },
# {
#     "name": "sweox_end_of_hardware_service_contract_renewal_date",
#     "type": "timestamp",
#     "description": "SW EOX end of hardware service contract renewal date.",
# },
# {
#     "name": "sweox_end_of_signature_releases_date",
#     "type": "timestamp",
#     "description": "SW EOX end of signature releases date.",
# },
# {
#     "name": "sweox_end_of_software_availability_date",
#     "type": "timestamp",
#     "description": "SW EOX end of software availability date.",
# },
# {
#     "name": "sweox_end_of_software_license_availability_date",
#     "type": "timestamp",
#     "description": "SW EOX end of software license availability date.",
# },
# {
#     "name": "sweox_end_of_software_maintenance_releases_date",
#     "type": "timestamp",
#     "description": "SW EOX end of software maintenance releases date.",
# },
# {
#     "name": "sweox_end_of_software_vulnerability_or_security_support_date",
#     "type": "timestamp",
#     "description": "SW EOX end of vulnerability/security support date.",
# },
# {"name": "ship_date", "type": "timestamp", "description": "Hardware ship date."},
# {"name": "post_date", "type": "timestamp", "description": "Post date."},
# {
#     "name": "asset_managed_contract_latest_signal",
#     "type": "timestamp",
#     "description": "Latest asset managed contract signal.",
# },
# {
#     "name": "diagnostic_scan_latest_signal",
#     "type": "timestamp",
#     "description": "Latest diagnostic scan signal.",
# },
# {
#     "name": "lcs_latest_signal",
#     "type": "timestamp",
#     "description": "Latest LCS signal.",
# },
# {
#     "name": "service_coverage_latest_signal",
#     "type": "timestamp",
#     "description": "Latest service coverage signal.",
# },
# {
#     "name": "service_request_latest_signal",
#     "type": "timestamp",
#     "description": "Latest service request signal.",
# },
# {
#     "name": "sntc_latest_signal",
#     "type": "timestamp",
#     "description": "Latest SNTC signal.",
# },
# {
#     "name": "st_latest_signal",
#     "type": "timestamp",
#     "description": "Latest SmartTrack signal.",
# },
# Partner/sales
# {"name": "partner_id", "type": "string", "description": "Partner identifier."},
# {"name": "partner_name", "type": "string", "description": "Partner name."},
# {
#     "name": "partner_be_id",
#     "type": "string",
#     "description": "Partner business entity identifier.",
# },
# {
#     "name": "partner_be_name",
#     "type": "string",
#     "description": "Partner business entity name.",
# },
# {
#     "name": "sales_order_number",
#     "type": "string",
#     "description": "Sales order number.",
# },
# {"name": "warranty_type", "type": "string", "description": "Warranty type."},
# {
#     "name": "warranty_start_date",
#     "type": "timestamp",
#     "description": "Warranty start date.",
# },
# {
#     "name": "warranty_end_date",
#     "type": "timestamp",
#     "description": "Warranty end date.",
# },
# {
#     "name": "migration_info",
#     "type": "string",
#     "description": "Migration information.",
# },
# {
#     "name": "milestone_info",
#     "type": "string",
#     "description": "Milestone information.",
# },

ADVISORY_PSIRT_BULLETINS_COLUMN_SCHEMA = [
    {
        "name": "psirt_id",
        "type": "integer",
        "description": "Cisco PSIRT advisory identifier (join key to psirts table). Whenever user UI context references 'checkID', this is the field to use for filtering/joining.",
    },
    {
        "name": "advisory_id",
        "type": "string",
        "description": "Cisco advisory ID string (e.g. 'cisco-sa-20060118-sgbp').",
    },
    {
        "name": "severity_level_name",
        "type": "string",
        "description": "Severity level of the advisory (e.g. 'Critical', 'High', 'Medium'). Use this column — NOT 'severity' — when filtering bulletins by severity.",
    },
    {
        "name": "headline_name",
        "type": "string",
        "description": "Short headline / title of the PSIRT bulletin.",
    },
    {
        "name": "summary_text",
        "type": "string",
        "description": "Summary description of the advisory.",
    },
    {
        "name": "cve_id",
        "type": "string",
        "description": "CVE identifier(s) associated with this advisory. Values can be comma-separated (e.g. 'CVE-2011-0939,CVE-2011-2072'). Use LIKE '%CVE-xxxx-xxxxx%' instead of = when filtering by a specific CVE.",
    },
    {
        "name": "cvss_score",
        "type": "double",
        "description": "CVSS base score.",
    },
    {
        "name": "publish_date",
        "type": "string",
        "description": "Date the advisory was first published (ISO 8601).",
    },
    {
        "name": "revised_date",
        "type": "string",
        "description": "Date the advisory was last revised (ISO 8601).",
    },
    {
        "name": "alert_status_cd",
        "type": "string",
        "description": "Alert status code (e.g. 'ACTIVE').",
    },
    {
        "name": "psirt_url_text",
        "type": "string",
        "description": "URL to the full Cisco PSIRT advisory page.",
    },
]

ADVISORY_RELATIONSHIP_SCHEMA = [
    {
        "id": "assets_psirts",
        "from_table": "assets",
        "from_column": "serial_number",
        "to_table": "psirts",
        "to_column": "serial_number",
        "cardinality": "1:*",
        "description": "An asset may have many PSIRT vulnerability records",
    },
    {
        "id": "psirts_bulletins",
        "from_table": "psirts",
        "from_column": "psirt_id",
        "to_table": "bulletins",
        "to_column": "psirt_id",
        "cardinality": "*:1",
        "description": "Many PSIRT records link to one PSIRT bulletin definition",
    },
]

