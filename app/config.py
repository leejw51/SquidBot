"""Configuration loader from environment variables."""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# Required
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")

# Optional
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o")
HEARTBEAT_INTERVAL_MINUTES = int(os.environ.get("HEARTBEAT_INTERVAL_MINUTES", "30"))
SQUID_PORT = int(os.environ.get("SQUID_PORT", "7777"))

# Paths
DATA_DIR = Path.home() / ".squidbot"
MEMORY_FILE = DATA_DIR / "memory.json"
CRON_FILE = DATA_DIR / "cron_jobs.json"

# Ensure data directory exists
DATA_DIR.mkdir(parents=True, exist_ok=True)


def validate_config():
    """Validate required configuration."""
    errors = []
    if not TELEGRAM_BOT_TOKEN:
        errors.append("TELEGRAM_BOT_TOKEN not set")
    if not OPENAI_API_KEY:
        errors.append("OPENAI_API_KEY not set")
    if errors:
        raise ValueError("Missing required config:\n" + "\n".join(errors))
