import os

DB_PATH = os.path.join(
    os.path.dirname(__file__), "..", "starter_pack", "client_intel.db"
)
AS_OF = "2026-11-01"
MODEL = "claude-opus-4-6"
OUTPUT_DIR = "output"
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_FOUNDRY_API_KEY", "placeholder-key")
ANTHROPIC_BASE_URL = os.environ.get("ANTHROPIC_FOUNDRY_BASE_URL", None)
TRIGGERS = ["renewal", "meeting_prep", "upsell", "at_risk"]
TRIGGER_DEFINITIONS = {
    "renewal": "Contract is approaching renewal. Focus on contract terms, notice deadlines, usage justification, pricing leverage, risks to retention, and what to propose.",
    "meeting_prep": "Rep has an upcoming meeting with this client. Provide a full briefing: relationship context, recent activity, talking points, open issues, and opportunities to raise.",
    "upsell": "Identify growth opportunities. Focus on whitespace products, usage trends showing demand, peer comparisons, pipeline, and what to pitch with supporting evidence.",
    "at_risk": "Client may be at risk of churn or downgrade. Focus on negative signals: declining usage, support issues, low CSAT, contract gaps, missing engagement, and competitive threats.",
}
