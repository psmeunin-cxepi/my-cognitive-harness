import os
from a2a.types import AgentCard, AgentCapabilities, AgentSkill

# Get A2A server URL from environment (fallback to localhost for development)
A2A_BASE_URL = os.getenv("A2A_BASE_URL", "http://localhost:9000")

# Define agent card using the proper A2A types
AGENT_CARD = AgentCard(
    name="Assessment Rating",
    version="1.0.0",
    description="AI agent specializing in analysing rating for each Assessment app like Security Advisory, Security Hardening, Configuration, Field notices etc.",
    url=A2A_BASE_URL,
    default_input_modes=["text/plain"],
    default_output_modes=["text/plain"],
    capabilities=AgentCapabilities(streaming=True, push_notifications=False, state_transition_history=False),
    skills=[
        AgentSkill(
            id="assessment-rating-analysis-query",
            name="Assessment Rating Analysis",
            description="Comprehensive Assessment rating analysis and criticality breakdown for each asset or network",
            tags=[
                "health-rating",
                "assessment-rating-analysis",
                "rating-analysis",
                "criticality-breakdown",
                "assessment-rating-categorization",
            ],
            examples=[
                "Are any of my High-rated assets borderline Critical?",
                "I have many Critical-rated assets. Which one is the absolute highest priority for me?",
                "Is there any Critical assessment rating on my low-importance devices that I can safely ignore for now?",
                "How much of my Critical assessment rating can be attributed to security threats compared to configuration assessment threats?",
                "Why is my asset rated as Critical?",
                "My asset has many findings but is only rated High. Why isn't it rated Critical?",
            ],
        ),
        AgentSkill(
            id="assessment-rating-capabilities",
            name="Assessment Rating Capabilities",
            description="Provides a concise overview of the agent's capabilities related to Cisco Assessment Rating analysis, including asset risk categorization, risk score breakdowns, and remediation prioritization. Helps users understand what questions they can ask and what insights the agent can provide about their network security risks.",
            tags=["assessment-rating-capabilities", "assessment-rating-welcome-message"],
            examples=[
                "What can Assessment Rating Agent help me with?",
            ],
        ),
    ],
)
