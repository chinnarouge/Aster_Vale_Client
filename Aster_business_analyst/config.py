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
