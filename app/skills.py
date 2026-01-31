"""Skills system - load markdown prompts to teach agent behaviors."""

import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import aiofiles

from config import DATA_DIR

SKILLS_DIR = DATA_DIR / "skills"


@dataclass
class Skill:
    """A skill loaded from a markdown file."""

    name: str
    description: str
    content: str
    file_path: Path
    metadata: dict


def parse_frontmatter(content: str) -> tuple[dict, str]:
    """Parse YAML frontmatter from markdown content."""
    metadata = {}
    body = content

    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            frontmatter = parts[1].strip()
            body = parts[2].strip()

            for line in frontmatter.split("\n"):
                if ":" in line:
                    key, value = line.split(":", 1)
                    metadata[key.strip()] = value.strip()

    return metadata, body


async def load_skill(skill_dir: Path) -> Optional[Skill]:
    """Load a skill from a directory containing SKILL.md."""
    skill_file = skill_dir / "SKILL.md"
    if not skill_file.exists():
        skill_file = skill_dir / "skill.md"
        if not skill_file.exists():
            return None

    try:
        async with aiofiles.open(skill_file, "r", encoding="utf-8") as f:
            content = await f.read()

        metadata, body = parse_frontmatter(content)

        return Skill(
            name=metadata.get("name", skill_dir.name),
            description=metadata.get("description", ""),
            content=body,
            file_path=skill_file,
            metadata=metadata,
        )
    except Exception:
        return None


async def load_all_skills(skills_dir: Path = None) -> list[Skill]:
    """Load all skills from the skills directory."""
    if skills_dir is None:
        skills_dir = SKILLS_DIR

    if not skills_dir.exists():
        return []

    # Load skills concurrently
    tasks = []
    for item in skills_dir.iterdir():
        if item.is_dir():
            tasks.append(load_skill(item))

    results = await asyncio.gather(*tasks)
    return [s for s in results if s is not None]


def format_skills_for_prompt(skills: list[Skill]) -> str:
    """Format skills as a prompt section for the LLM."""
    if not skills:
        return ""

    lines = ["## Available Skills\n"]
    for skill in skills:
        lines.append(f"### {skill.name}")
        if skill.description:
            lines.append(f"*{skill.description}*\n")
        lines.append(skill.content)
        lines.append("")

    return "\n".join(lines)


async def get_skills_context() -> str:
    """Get all skills formatted for system prompt."""
    skills = await load_all_skills()
    return format_skills_for_prompt(skills)


async def ensure_skills_dir():
    """Ensure skills directory exists."""
    SKILLS_DIR.mkdir(parents=True, exist_ok=True)


async def create_example_skill():
    """Create an example skill if none exist."""
    await ensure_skills_dir()

    example_dir = SKILLS_DIR / "weather"
    if example_dir.exists():
        return

    example_dir.mkdir(parents=True, exist_ok=True)
    skill_content = """---
name: weather
description: Get weather information for a location
---
When the user asks about weather:

1. Use the `web_search` tool to search for current weather
2. Search query format: "weather in {city} today"
3. Extract the temperature, conditions, and forecast
4. Present the information in a friendly format

Example:
User: "What's the weather in Tokyo?"
→ Search: "weather in Tokyo today"
→ Response: "It's currently 18°C in Tokyo with partly cloudy skies..."
"""
    async with aiofiles.open(example_dir / "SKILL.md", "w") as f:
        await f.write(skill_content)
