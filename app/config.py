"""Configuration loader from environment variables."""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(override=True)  # Override existing env vars with .env values

# Required
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")

# Optional
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o")
HEARTBEAT_INTERVAL_MINUTES = int(os.environ.get("HEARTBEAT_INTERVAL_MINUTES", "30"))
SQUID_PORT = int(os.environ.get("SQUID_PORT", "7777"))

# Paths - Use SQUIDBOT_HOME env var or default to ~/.squidbot
DATA_DIR = Path(os.environ.get("SQUIDBOT_HOME", Path.home() / ".squidbot"))
MEMORY_FILE = DATA_DIR / "memory.json"
CRON_FILE = DATA_DIR / "cron_jobs.json"
CHARACTER_FILE = DATA_DIR / "CHARACTER.md"
SKILLS_DIR = DATA_DIR / "skills"
CODING_DIR = DATA_DIR / "coding"
SESSIONS_DIR = DATA_DIR / "sessions"

# Default CHARACTER.md content
DEFAULT_CHARACTER = """# Character Definition

You are a helpful AI assistant with the following traits:

## Personality
- Friendly and approachable
- Patient and thorough
- Honest about limitations

## Communication Style
- Clear and concise responses
- Use examples when helpful
- Ask clarifying questions when needed

## Guidelines
- Always be helpful and respectful
- Admit when you don't know something
- Provide accurate information
"""

# Default skill template
DEFAULT_SKILL_SEARCH = """---
name: search
description: Search the web for information
---
When user asks a question requiring current information:

1. Use `web_search` tool with a clear query
2. Review the results
3. Synthesize a helpful answer with sources

Always cite sources when providing factual information.
"""

DEFAULT_SKILL_REMINDER = """---
name: reminder
description: Set reminders and scheduled tasks
---
When user wants to set a reminder:

1. Extract the message and time
2. Use `cron_create` tool with appropriate delay_minutes or cron_expression
3. Confirm the reminder was set

Examples:
- "Remind me in 10 minutes" → delay_minutes=10
- "Remind me daily at 9am" → cron_expression="0 9 * * *"
"""


def ensure_data_dirs():
    """Ensure all data directories exist."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    SKILLS_DIR.mkdir(parents=True, exist_ok=True)
    CODING_DIR.mkdir(parents=True, exist_ok=True)
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)


def init_default_files():
    """Create default files if they don't exist."""
    ensure_data_dirs()

    # Create default CHARACTER.md
    if not CHARACTER_FILE.exists():
        CHARACTER_FILE.write_text(DEFAULT_CHARACTER, encoding="utf-8")
        print(f"  Created: {CHARACTER_FILE}")

    # Create default skills
    search_skill_dir = SKILLS_DIR / "search"
    if not search_skill_dir.exists():
        search_skill_dir.mkdir(parents=True, exist_ok=True)
        (search_skill_dir / "SKILL.md").write_text(
            DEFAULT_SKILL_SEARCH, encoding="utf-8"
        )
        print(f"  Created: {search_skill_dir / 'SKILL.md'}")

    reminder_skill_dir = SKILLS_DIR / "reminder"
    if not reminder_skill_dir.exists():
        reminder_skill_dir.mkdir(parents=True, exist_ok=True)
        (reminder_skill_dir / "SKILL.md").write_text(
            DEFAULT_SKILL_REMINDER, encoding="utf-8"
        )
        print(f"  Created: {reminder_skill_dir / 'SKILL.md'}")


def show_startup_info():
    """Display startup configuration info."""
    print("\n" + "=" * 60)
    print("  SquidBot Configuration")
    print("=" * 60)
    print(f"  Home Directory : {DATA_DIR}")
    print(f"  Server Port    : {SQUID_PORT}")
    print(f"  Model          : {OPENAI_MODEL}")
    print(f"  Heartbeat      : {HEARTBEAT_INTERVAL_MINUTES} minutes")
    print("-" * 60)
    print(f"  Character File : {CHARACTER_FILE}")
    print(f"  Skills Dir     : {SKILLS_DIR}")
    print(f"  Coding Dir     : {CODING_DIR}")
    print(f"  Sessions Dir   : {SESSIONS_DIR}")
    print("=" * 60)
    print("\n  To customize, set environment variables:")
    print("    SQUIDBOT_HOME=/path/to/home")
    print("    SQUID_PORT=7777")
    print("    OPENAI_MODEL=gpt-4o")
    print("=" * 60 + "\n")


def validate_config():
    """Validate required configuration."""
    errors = []
    if not TELEGRAM_BOT_TOKEN:
        errors.append("TELEGRAM_BOT_TOKEN not set")
    if not OPENAI_API_KEY:
        errors.append("OPENAI_API_KEY not set")
    if errors:
        raise ValueError("Missing required config:\n" + "\n".join(errors))


# Ensure data directory exists on import
ensure_data_dirs()
