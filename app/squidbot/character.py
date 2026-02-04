"""AI Character/Personality configuration."""

import os
from pathlib import Path

import aiofiles

from .config import DATA_DIR

# Character configuration from environment
CHARACTER_NAME = os.environ.get("CHARACTER_NAME", "Assistant")
CHARACTER_PERSONA = os.environ.get("CHARACTER_PERSONA", "")
CHARACTER_STYLE = os.environ.get("CHARACTER_STYLE", "helpful, friendly, concise")

# Optional character file
CHARACTER_FILE = DATA_DIR / "CHARACTER.md"


async def load_character_file() -> str:
    """Load character definition from file if exists."""
    if CHARACTER_FILE.exists():
        try:
            async with aiofiles.open(CHARACTER_FILE, "r", encoding="utf-8") as f:
                return await f.read()
        except Exception:
            pass
    return ""


async def get_character_prompt() -> str:
    """Build character prompt section."""
    parts = []

    # Name
    if CHARACTER_NAME and CHARACTER_NAME != "Assistant":
        parts.append(f"Your name is {CHARACTER_NAME}.")

    # Persona from env
    if CHARACTER_PERSONA:
        parts.append(CHARACTER_PERSONA)

    # Style
    if CHARACTER_STYLE:
        parts.append(f"Communication style: {CHARACTER_STYLE}")

    # Character file content
    file_content = await load_character_file()
    if file_content:
        parts.append(file_content)

    if not parts:
        return ""

    return "## Character\n" + "\n".join(parts)


async def create_example_character():
    """Create an example CHARACTER.md if it doesn't exist."""
    if CHARACTER_FILE.exists():
        return

    example = """# Character Definition

You are a helpful AI assistant with the following traits:

## Personality
- Friendly and approachable
- Patient and thorough
- Honest about limitations

## Communication Style
- Clear and concise responses
- Use examples when helpful
- Ask clarifying questions when needed

## Knowledge Areas
- General knowledge
- Programming and technology
- Problem solving
"""
    CHARACTER_FILE.parent.mkdir(parents=True, exist_ok=True)
    async with aiofiles.open(CHARACTER_FILE, "w") as f:
        await f.write(example)
