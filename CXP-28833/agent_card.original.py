import os
from a2a.types import AgentCard, AgentCapabilities, AgentSkill

# Get A2A server URL from environment (fallback to localhost for development)
A2A_SERVER_URL = os.getenv("A2A_SERVER_URL", "http://localhost:9000")

# Define agent card using the proper A2A types
AGENT_CARD = AgentCard(
    name="Assessments – Configuration",
    version="1.0.0",
    description=(
        "Analyzes how a customer's network configuration is performing against "
        "best practice rules, surfaces detected failures with severity and "
        "impact details, and provides remediation recommendations and corrective "
        "actions. Capabilities span four skills: (1) assessment-wide summaries "
        "with severity distributions, failure counts, and aggregate metrics; "
        "(2) asset-scoped analysis filterable by hostname, IP, product family, "
        "software type, location, and 20+ other dimensions to pinpoint which "
        "devices are most impacted; (3) rule-centric impact analysis showing "
        "which best practice rules have the most failures, which assets are "
        "affected, and how to remediate; and (4) pre-generated AI insights for "
        "Signature-covered assets with prioritized focus areas."
    ),
    url=A2A_SERVER_URL,
    default_input_modes=["text/plain"],
    default_output_modes=["text/plain"],
    capabilities=AgentCapabilities(
        streaming=True, push_notifications=False, state_transition_history=False
    ),
    skills=[
        AgentSkill(
            id="assessments-configuration-summary",
            name="Assessments Configuration Summary",
            description=(
                "Provides a comprehensive overview of how the customer's network "
                "configuration is doing: how many assets were assessed, how many "
                "best practice rules were evaluated, how many failures were detected, "
                "and how they break down by severity (critical, high, medium, low). "
                "Returns execution summaries, pass/fail rates and percentages, "
                "technology and category breakdowns, top impacted assets ranked by "
                "failure count, and the rules with the most failures. Handles broad "
                "questions about common configuration deviations across the network, "
                "severity trends, overall assessment posture, and breakdowns by "
                "severity, category, and software type."
            ),
            tags=[
                "assessment",
                "summary",
                "severity",
                "overview",
                "distribution",
                "metrics",
                "technology",
                "execution",
                "failures",
                "pass-fail",
                "category",
                "trends",
            ],
            examples=[
                "Can you provide a summary of my recent Configuration Assessment?",
                "How many configuration best practice rules were evaluated, and how many resulted in at least one asset that did not pass?",
                "What are the most common configuration deviations across my network?",
                "How many assets were evaluated, and what percentage did not pass?",
                "Which categories have the most deviations from configuration best practices?",
                "Show breakdown of configuration best practice rules deviations by severity, category, and software type",
            ],
        ),
        AgentSkill(
            id="asset-scope-analysis",
            name="Asset Scope Analysis",
            description=(
                "Shows which specific assets have configuration failures and what "
                "to do about them, including corrective actions and remediation "
                "recommendations. Can show deviations for a single asset or a "
                "specific product family. Scopes analysis to individual devices or "
                "filtered asset sets by hostname, IP address, product family, product type, "
                "asset type, location, software type and version, contract number, "
                "coverage status, support type, telemetry status, data source, "
                "partner name, entitlement level, role, lifecycle milestones, and "
                "date-range dimensions. Returns failures, failed rules, severity "
                "distributions, corrective actions, and remediation recommendations "
                "for the scoped assets. Enables comparisons across product families, "
                "criticality levels, and software versions, and can break down "
                "critical and high severity deviations by asset criticality."
            ),
            tags=[
                "asset",
                "device",
                "hostname",
                "ip-address",
                "product-family",
                "product-type",
                "location",
                "impact",
                "software-type",
                "software-version",
                "contract",
                "coverage",
                "lifecycle",
                "criticality",
                "scope",
                "filter",
            ],
            examples=[
                "Which Cisco product families have the most deviations from configuration best practices?",
                "Which assets have the maximum of critical and high severity configuration deviations? What corrective actions are recommended?",
                "Show breakdown of critical and high severity configuration deviations by asset criticality",
            ],
        ),
        AgentSkill(
            id="rule-analysis",
            name="Rule Analysis",
            description=(
                "Explains which configuration best practice rules are failing, "
                "how many assets are affected, and what remediation or corrective "
                "actions to take. Identifies which deviations pose the highest risk "
                "to the network. Supports single-rule deep dives by rule ID or name "
                "with per-rule summaries, cross-rule comparisons, and rule-level "
                "summaries with failure counts. Returns rule descriptions, severity "
                "levels, technology and OS breakdowns of failures showing which "
                "technology contributes the most, and lists of impacted assets. "
                "Supports filtering by severity (e.g. high-severity only or critical "
                "rules only), technology, rule category, and optional asset scope to "
                "narrow impact to specific devices or product families."
            ),
            tags=[
                "rule",
                "compliance",
                "failure",
                "configuration",
                "policy",
                "remediation",
                "corrective-action",
                "impact",
                "risk",
                "category",
                "technology",
            ],
            examples=[
                "Which configuration deviations pose the highest risk to my network, and what corrective actions are recommended?",
            ],
        ),
        AgentSkill(
            id="signature-asset-insights",
            name="Signature Asset Insights",
            description=(
                "Surfaces pre-generated AI insights that tell Signature customers "
                "where their most important configuration issues are and what to "
                "focus on first. Provides a summary of the latest Signature asset "
                "assessment with prioritized observations, top insights, related "
                "rule IDs, impacted asset lists, and actionable remediation "
                "recommendations. Supports retrieving all insights or a specific "
                "insight by ID."
            ),
            tags=[
                "insights",
                "signature",
                "ai-generated",
                "recommendations",
                "prioritization",
                "remediation",
                "focus-areas",
            ],
        ),
    ],
)
