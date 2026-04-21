import os
from a2a.types import AgentCard, AgentCapabilities, AgentSkill

# Get A2A server URL from environment (fallback to localhost for development)
A2A_SERVER_URL = os.getenv("A2A_SERVER_URL", "http://localhost:9000")

# Define agent card using the proper A2A types
AGENT_CARD = AgentCard(
    name="Assessments – Configuration",
    version="1.0.0",
    description=(
        "Analyzes a customer's network configuration against Cisco best "
        "practice rules and reports failures, severity, impacted assets, and "
        "remediation. Route here for questions about configuration compliance "
        "posture, rule deviations, and corrective actions — not for assessment "
        "rating/health scores or non-configuration assessments (Security "
        "Advisory, Hardening, Field Notices)."
    ),
    url=A2A_SERVER_URL,
    default_input_modes=["text/plain"],
    default_output_modes=["text/plain"],
    capabilities=AgentCapabilities(
        streaming=True, push_notifications=False, state_transition_history=False
    ),
    skills=[
        AgentSkill(
            id="configuration-assessment-posture",
            name="Configuration Assessment Posture",
            description=(
                "Provides a comprehensive overview of how the customer's network "
                "configuration is performing against best practice rules: how many "
                "assets were assessed against the configuration ruleset, how many "
                "configuration best practice rules were evaluated, how many "
                "configuration failures were detected, and how those configuration "
                "failures break down by severity (critical, high, medium, low). "
                "Returns configuration assessment execution summaries, configuration "
                "pass/fail rates and percentages, technology and configuration "
                "category breakdowns, top impacted assets ranked by configuration "
                "failure count, and the configuration rules with the most failures. "
                "Handles broad questions about common configuration deviations "
                "across the network, configuration severity trends, overall "
                "configuration assessment posture, and breakdowns of configuration "
                "failures by severity, category, and software type."
            ),
            tags=[
                "configuration-assessment",
                "best-practice-rules",
                "severity",
                "distribution",
                "metrics",
                "technology",
                "execution",
                "failures",
                "pass-fail",
                "category",
                "trends",
                "severity-distribution",
                "configuration-posture",
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
            id="configuration-failures-by-asset",
            name="Configuration Failures by Asset",
            description=(
                "Shows which specific assets have configuration failures and what "
                "to do about them, including configuration corrective actions and "
                "remediation recommendations. Can show configuration deviations for "
                "a single asset or a specific product family. Scopes the configuration "
                "analysis to individual devices or filtered asset sets by hostname, "
                "IP address, product family, product type, asset type, location, "
                "software type and version, contract number, coverage status, support "
                "type, telemetry status, data source, partner name, entitlement level, "
                "role, lifecycle milestones, and date-range dimensions. Returns "
                "configuration failures, failed configuration rules, configuration "
                "severity distributions, configuration corrective actions, and "
                "configuration remediation recommendations for the scoped assets. "
                "Enables comparisons of configuration failures across product "
                "families, criticality levels, and software versions, and can break "
                "down critical and high severity configuration deviations by asset "
                "criticality."
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
            id="configuration-rule-impact",
            name="Configuration Rule Impact",
            description=(
                "Explains which configuration best practice rules are failing, how "
                "many assets are affected by each configuration rule, and what "
                "configuration remediation or corrective actions to take. Identifies "
                "which configuration deviations pose the highest risk to the network. "
                "Supports single-rule deep dives by configuration rule ID or name "
                "with per-rule configuration summaries, cross-rule comparisons, and "
                "rule-level summaries with configuration failure counts. Returns "
                "configuration rule descriptions, configuration severity levels, "
                "technology and OS breakdowns of configuration failures showing which "
                "technology contributes the most, and lists of assets impacted by "
                "each configuration rule. Supports filtering by configuration severity "
                "(e.g. high-severity only or critical configuration rules only), "
                "technology, configuration rule category, and optional asset scope "
                "to narrow configuration impact to specific devices or product "
                "families."
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
            id="signature-configuration-insights",
            name="Signature Configuration Insights",
            description=(
                "Surfaces pre-generated AI insights that tell Signature customers "
                "where their most important configuration issues are and which "
                "configuration items to focus on first. Provides a summary of the "
                "latest Signature configuration assessment with prioritized "
                "configuration observations, top configuration insights, related "
                "configuration rule IDs, lists of assets impacted by each "
                "configuration insight, and actionable configuration remediation "
                "recommendations. Supports retrieving all configuration insights or "
                "a specific configuration insight by ID."
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
