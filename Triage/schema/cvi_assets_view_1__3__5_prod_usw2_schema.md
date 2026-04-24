# `cvi_assets_view_1__3__5` — Live Schema (PROD usw2)

- **Environment:** prod
- **Region:** usw2
- **Cluster context:** `cx-prd-usw2`
- **Database:** `consumption` on `cx-usw2-prod01-common-aurora-postgresql-2.cluster-c3asgig64fqg.us-west-2.rds.amazonaws.com:5432`
- **DB user:** `query_service`
- **Table:** `cvi_assets_view_1__3__5`
- **Total columns:** 162
- **Captured at:** 2026-04-24
- **Source query:**

  ```sql
  SELECT ordinal_position, column_name, data_type, is_nullable
  FROM information_schema.columns
  WHERE table_name = 'cvi_assets_view_1__3__5'
  ORDER BY ordinal_position;
  ```

## Columns

| # | Column | Data Type | Nullable |
|---:|---|---|:---:|
| 1 | `account_name` | text | YES |
| 2 | `advisory_count` | integer | YES |
| 3 | `affected_security_advisories_count` | integer | YES |
| 4 | `all_advisory_count` | integer | YES |
| 5 | `asset_managed_contract_latest_signal` | timestamp with time zone | YES |
| 6 | `asset_type` | text | YES |
| 7 | `business_entity` | text | YES |
| 8 | `cav_bu_id` | text | YES |
| 9 | `cav_id` | text | YES |
| 10 | `connectivity` | text | YES |
| 11 | `contract_end_date` | timestamp with time zone | YES |
| 12 | `contract_id` | integer | YES |
| 13 | `contract_number` | text | YES |
| 14 | `contract_owner` | text | YES |
| 15 | `contract_start_date` | timestamp with time zone | YES |
| 16 | `contract_status` | text | YES |
| 17 | `coverage_end_date` | timestamp with time zone | YES |
| 18 | `coverage_start_date` | timestamp with time zone | YES |
| 19 | `coverage_status` | text | YES |
| 20 | `created_at` | timestamp with time zone | YES |
| 21 | `created_by` | text | YES |
| 22 | `created_date` | timestamp with time zone | YES |
| 23 | `critical_security_advisories_count` | integer | YES |
| 24 | `critical_vulnerability_field_notice_count` | integer | YES |
| 25 | `current_hweox_milestone` | text | YES |
| 26 | `current_milestone` | text | YES |
| 27 | `current_milestone_date` | timestamp with time zone | YES |
| 28 | `current_sweox_milestone` | text | YES |
| 29 | `customer_name` | text | YES |
| 30 | `cx_level` | integer | YES |
| 31 | `cx_level_label` | text | YES |
| 32 | `data_source` | text | YES |
| 33 | `diagnostic_scan_latest_signal` | timestamp with time zone | YES |
| 34 | `end_of_bu_engineering_support_tac_date` | timestamp with time zone | YES |
| 35 | `end_of_last_date_of_support` | timestamp with time zone | YES |
| 36 | `end_of_last_hardware_ship_date` | timestamp with time zone | YES |
| 37 | `end_of_life_external_announcement_date` | timestamp with time zone | YES |
| 38 | `end_of_life_internal_announcement_date` | timestamp with time zone | YES |
| 39 | `end_of_new_service_attachment_date` | timestamp with time zone | YES |
| 40 | `end_of_product_sale_date` | timestamp with time zone | YES |
| 41 | `end_of_routine_failure_analysis_date` | timestamp with time zone | YES |
| 42 | `end_of_sale_date` | timestamp with time zone | YES |
| 43 | `end_of_service_contract_renewal_date` | timestamp with time zone | YES |
| 44 | `end_of_software_maintenance_date` | timestamp with time zone | YES |
| 45 | `end_of_vulnerability_or_security_support_date` | timestamp with time zone | YES |
| 46 | `equipment_type` | text | YES |
| 47 | `hardware_eox_id` | text | YES |
| 48 | `has_child_assets` | boolean | YES |
| 49 | `high_security_advisories_count` | integer | YES |
| 50 | `high_vulnerability_field_notice_count` | integer | YES |
| 51 | `hostname` | text | YES |
| 52 | `hw_id` | text | YES |
| 53 | `hweox_current_milestone` | text | YES |
| 54 | `hweox_current_milestone_date` | timestamp with time zone | YES |
| 55 | `hweox_end_of_bu_engineering_support_tac_date` | timestamp with time zone | YES |
| 56 | `hweox_end_of_hardware_new_service_attachment_date` | timestamp with time zone | YES |
| 57 | `hweox_end_of_hardware_routine_failure_analysis_date` | timestamp with time zone | YES |
| 58 | `hweox_end_of_hardware_service_contract_renewal_date` | timestamp with time zone | YES |
| 59 | `hweox_end_of_last_date_of_support` | timestamp with time zone | YES |
| 60 | `hweox_end_of_last_hardware_ship_date` | timestamp with time zone | YES |
| 61 | `hweox_end_of_life_external_announcement_date` | timestamp with time zone | YES |
| 62 | `hweox_end_of_life_internal_announcement_date` | timestamp with time zone | YES |
| 63 | `hweox_end_of_sale_date` | timestamp with time zone | YES |
| 64 | `hweox_end_of_signature_releases_date` | timestamp with time zone | YES |
| 65 | `hweox_end_of_software_availability_date` | timestamp with time zone | YES |
| 66 | `hweox_end_of_software_license_availability_date` | timestamp with time zone | YES |
| 67 | `hweox_end_of_software_maintenance_releases_date` | timestamp with time zone | YES |
| 68 | `hweox_end_of_software_vulnerability_or_security_support_date` | timestamp with time zone | YES |
| 69 | `hweox_last_date_of_support` | timestamp with time zone | YES |
| 70 | `hweox_next_milestone` | text | YES |
| 71 | `hweox_next_milestone_date` | timestamp with time zone | YES |
| 72 | `id` | text | YES |
| 73 | `importance` | text | YES |
| 74 | `install_site_city` | text | YES |
| 75 | `install_site_country` | text | YES |
| 76 | `install_site_state` | text | YES |
| 77 | `instance_id` | integer | YES |
| 78 | `ip_address` | text | YES |
| 79 | `is_cspi` | integer | YES |
| 80 | `last_date_of_support` | timestamp with time zone | YES |
| 81 | `last_scan` | timestamp with time zone | YES |
| 82 | `last_signal_date` | timestamp with time zone | YES |
| 83 | `last_signal_type` | text | YES |
| 84 | `last_update_date` | timestamp with time zone | YES |
| 85 | `lcs_latest_signal` | timestamp with time zone | YES |
| 86 | `location` | text | YES |
| 87 | `managed_by_id` | text | YES |
| 88 | `management_system_id` | text | YES |
| 89 | `management_system_type` | text | YES |
| 90 | `max_coverage_end_date` | timestamp with time zone | YES |
| 91 | `migration_info` | text | YES |
| 92 | `milestone_info` | text | YES |
| 93 | `mss_extended_support_approved_service_level` | text | YES |
| 94 | `mss_extended_support_assessment_result` | text | YES |
| 95 | `mss_extended_support_end_date` | timestamp with time zone | YES |
| 96 | `next_milestone` | text | YES |
| 97 | `next_milestone_date` | timestamp with time zone | YES |
| 98 | `parent_id` | text | YES |
| 99 | `parent_root_id` | text | YES |
| 100 | `partition_key` | text | YES |
| 101 | `partner_be_id` | text | YES |
| 102 | `partner_be_name` | text | YES |
| 103 | `partner_id` | text | YES |
| 104 | `partner_name` | text | YES |
| 105 | `platform_account_id` | text | YES |
| 106 | `post_date` | timestamp with time zone | YES |
| 107 | `potentially_affected_security_advisories_count` | integer | YES |
| 108 | `product_description` | text | YES |
| 109 | `product_family` | text | YES |
| 110 | `product_id` | text | YES |
| 111 | `product_name` | text | YES |
| 112 | `product_type` | text | YES |
| 113 | `product_version_id` | text | YES |
| 114 | `quantity` | integer | YES |
| 115 | `role` | text | YES |
| 116 | `sales_order_number` | text | YES |
| 117 | `security_advisories_count` | integer | YES |
| 118 | `serial_number` | text | YES |
| 119 | `service_coverage_latest_signal` | timestamp with time zone | YES |
| 120 | `service_level_agreement_description` | text | YES |
| 121 | `service_program` | text | YES |
| 122 | `service_request_latest_signal` | timestamp with time zone | YES |
| 123 | `service_type` | text | YES |
| 124 | `ship_date` | timestamp with time zone | YES |
| 125 | `site` | text | YES |
| 126 | `site_name` | text | YES |
| 127 | `sntc_latest_signal` | timestamp with time zone | YES |
| 128 | `software_eox_id` | integer | YES |
| 129 | `software_patch_version` | text | YES |
| 130 | `software_type` | text | YES |
| 131 | `software_version` | text | YES |
| 132 | `st_latest_signal` | timestamp with time zone | YES |
| 133 | `support_level` | text | YES |
| 134 | `support_type` | text | YES |
| 135 | `sweox_current_milestone` | text | YES |
| 136 | `sweox_current_milestone_date` | timestamp with time zone | YES |
| 137 | `sweox_end_of_bu_engineering_support_tac_date` | timestamp with time zone | YES |
| 138 | `sweox_end_of_engineering_date` | timestamp with time zone | YES |
| 139 | `sweox_end_of_hardware_new_service_attachment_date` | timestamp with time zone | YES |
| 140 | `sweox_end_of_hardware_routine_failure_analysis_date` | timestamp with time zone | YES |
| 141 | `sweox_end_of_hardware_service_contract_renewal_date` | timestamp with time zone | YES |
| 142 | `sweox_end_of_last_date_of_support` | timestamp with time zone | YES |
| 143 | `sweox_end_of_last_hardware_ship_date` | timestamp with time zone | YES |
| 144 | `sweox_end_of_life_external_announcement_date` | timestamp with time zone | YES |
| 145 | `sweox_end_of_life_internal_announcement_date` | timestamp with time zone | YES |
| 146 | `sweox_end_of_sale_date` | timestamp with time zone | YES |
| 147 | `sweox_end_of_signature_releases_date` | timestamp with time zone | YES |
| 148 | `sweox_end_of_software_availability_date` | timestamp with time zone | YES |
| 149 | `sweox_end_of_software_license_availability_date` | timestamp with time zone | YES |
| 150 | `sweox_end_of_software_maintenance_releases_date` | timestamp with time zone | YES |
| 151 | `sweox_end_of_software_vulnerability_or_security_support_date` | timestamp with time zone | YES |
| 152 | `sweox_last_date_of_support` | timestamp with time zone | YES |
| 153 | `sweox_next_milestone` | text | YES |
| 154 | `sweox_next_milestone_date` | timestamp with time zone | YES |
| 155 | `tags` | ARRAY | YES |
| 156 | `telemetry_status` | text | YES |
| 157 | `updated_at` | timestamp with time zone | YES |
| 158 | `updated_by` | text | YES |
| 159 | `vendor` | text | YES |
| 160 | `warranty_end_date` | timestamp with time zone | YES |
| 161 | `warranty_start_date` | timestamp with time zone | YES |
| 162 | `warranty_type` | text | YES |

## Notes

- All 162 columns are nullable (`is_nullable = YES`) as expected for a view.
- `tags` is reported as `ARRAY` by `information_schema` — the underlying element type is most commonly `text[]` for this view family. Confirm with `pg_typeof(tags)` against an actual row if exact element type matters.
- Numeric columns are all plain `integer` (precision 32, scale 0). No `numeric`/`bigint` columns are present in this view version.
- Schema captured directly from PROD via `./run_k8s_query.sh prod usw2`. The synced repo DBML (`.claude/db_schema.dbml`) is dev/nprd-aligned and may lag PROD.
