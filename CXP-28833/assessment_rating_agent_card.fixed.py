import os
from a2a.types import AgentCard, AgentCapabilities, AgentSkill

# Get A2A server URL from environment (fallback to localhost for development)
A2A_BASE_URL = os.getenv("A2A_BASE_URL", "http://localhost:9000")

# Define agent card using the proper A2A types
AGENT_CARD = AgentCard(
    name="Assessment Rating",
    version="1.0.0",
    description=(
        "Computes and explains composite assessment ratings (Critical, High, Medium, Low) "
        "that aggregate findings across all assessment types — Security Advisory, Security "
        "Hardening, Configuration, and Field Notices — into a single per-asset or per-network "
        "health score. Route here for questions about why an asset received a specific rating, "
        "what factors drive the rating, how ratings compare across assets, and which rated "
        "assets to prioritize — not for the underlying assessment findings themselves (route "
        "to the relevant assessment agent) or for Place-in-Network criticality rankings "
        "(route to Asset Criticality)."
    ),
    url=A2A_BASE_URL,
    default_input_modes=["text/plain"],
    default_output_modes=["text/plain"],
    capabilities=AgentCapabilities(streaming=True, push_notifications=False, state_transition_history=False),
    skills=[
        AgentSkill(
            id="assessment-rating-analysis",
            name="Assessment Rating Analysis",
            description=(
                "Analyzes composite assessment ratings that combine findings from Security Advisory, "
                "Security Hardening, Configuration, and Field Notice assessments into a single "
                "per-asset health score. Explains why an asset received a Critical, High, Medium, or "
                "Low rating, identifies which assessment categories contribute most to the rating, "
                "and ranks rated assets by priority for remediation."
            ),
            tags=[
                "assessment-rating",
                "health-score",
                "composite-rating",
                "rating-explanation",
                "rating-prioritization",
                "cross-assessment",
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
            description=(
                "Describes what the Assessment Rating agent can help with and what questions "
                "users can ask about composite assessment ratings, rating breakdowns, and "
                "rating-based prioritization."
            ),
            tags=["assessment-rating-capabilities", "assessment-rating-help"],
            examples=[
                "What can Assessment Rating Agent help me with?",
            ],
        ),
    ],
)
