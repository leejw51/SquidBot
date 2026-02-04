"""Tests for skills system."""

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from squidbot.skills import (Skill, format_skills_for_prompt, load_all_skills,
                             load_skill, parse_frontmatter)


class TestParseFrontmatter:
    """Test YAML frontmatter parsing."""

    def test_parse_with_frontmatter(self):
        """Test parsing content with valid frontmatter."""
        content = """---
name: test-skill
description: A test skill
---
This is the body content."""

        metadata, body = parse_frontmatter(content)

        assert metadata["name"] == "test-skill"
        assert metadata["description"] == "A test skill"
        assert body == "This is the body content."

    def test_parse_without_frontmatter(self):
        """Test parsing content without frontmatter."""
        content = "Just regular content\nwith multiple lines."

        metadata, body = parse_frontmatter(content)

        assert metadata == {}
        assert body == content

    def test_parse_empty_frontmatter(self):
        """Test parsing content with empty frontmatter."""
        content = """---
---
Body only."""

        metadata, body = parse_frontmatter(content)

        assert metadata == {}
        assert body == "Body only."

    def test_parse_multiline_body(self):
        """Test parsing with multiline body content."""
        content = """---
name: multi
---
Line 1
Line 2
Line 3"""

        metadata, body = parse_frontmatter(content)

        assert metadata["name"] == "multi"
        assert "Line 1" in body
        assert "Line 2" in body
        assert "Line 3" in body

    def test_parse_frontmatter_with_colons_in_value(self):
        """Test parsing frontmatter where value contains colons."""
        content = """---
name: test
url: https://example.com
---
Body"""

        metadata, body = parse_frontmatter(content)

        assert metadata["name"] == "test"
        assert metadata["url"] == "https://example.com"


class TestLoadSkill:
    """Test loading individual skills."""

    @pytest.mark.asyncio
    async def test_load_skill_uppercase(self):
        """Test loading skill from SKILL.md."""
        with tempfile.TemporaryDirectory() as tmpdir:
            skill_dir = Path(tmpdir) / "test-skill"
            skill_dir.mkdir()

            skill_file = skill_dir / "SKILL.md"
            skill_file.write_text(
                """---
name: test
description: Test skill
---
Skill instructions here."""
            )

            skill = await load_skill(skill_dir)

            assert skill is not None
            assert skill.name == "test"
            assert skill.description == "Test skill"
            assert "Skill instructions" in skill.content

    @pytest.mark.asyncio
    async def test_load_skill_lowercase(self):
        """Test loading skill from skill.md (lowercase)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            skill_dir = Path(tmpdir) / "test-skill"
            skill_dir.mkdir()

            skill_file = skill_dir / "skill.md"
            skill_file.write_text(
                """---
name: lowercase
---
Content."""
            )

            skill = await load_skill(skill_dir)

            assert skill is not None
            assert skill.name == "lowercase"

    @pytest.mark.asyncio
    async def test_load_skill_no_file(self):
        """Test loading skill when no skill file exists."""
        with tempfile.TemporaryDirectory() as tmpdir:
            skill_dir = Path(tmpdir) / "empty-skill"
            skill_dir.mkdir()

            skill = await load_skill(skill_dir)

            assert skill is None

    @pytest.mark.asyncio
    async def test_load_skill_default_name(self):
        """Test that skill uses directory name as default name."""
        with tempfile.TemporaryDirectory() as tmpdir:
            skill_dir = Path(tmpdir) / "my-skill"
            skill_dir.mkdir()

            skill_file = skill_dir / "SKILL.md"
            skill_file.write_text("No frontmatter content.")

            skill = await load_skill(skill_dir)

            assert skill is not None
            assert skill.name == "my-skill"


class TestLoadAllSkills:
    """Test loading all skills from directory."""

    @pytest.mark.asyncio
    async def test_load_all_skills(self):
        """Test loading multiple skills."""
        with tempfile.TemporaryDirectory() as tmpdir:
            skills_dir = Path(tmpdir)

            # Create skill 1
            skill1_dir = skills_dir / "skill1"
            skill1_dir.mkdir()
            (skill1_dir / "SKILL.md").write_text("---\nname: skill1\n---\nContent 1")

            # Create skill 2
            skill2_dir = skills_dir / "skill2"
            skill2_dir.mkdir()
            (skill2_dir / "SKILL.md").write_text("---\nname: skill2\n---\nContent 2")

            skills = await load_all_skills(skills_dir)

            assert len(skills) == 2
            names = [s.name for s in skills]
            assert "skill1" in names
            assert "skill2" in names

    @pytest.mark.asyncio
    async def test_load_all_skills_empty_dir(self):
        """Test loading from empty directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            skills = await load_all_skills(Path(tmpdir))
            assert skills == []

    @pytest.mark.asyncio
    async def test_load_all_skills_nonexistent_dir(self):
        """Test loading from nonexistent directory."""
        skills = await load_all_skills(Path("/nonexistent/path"))
        assert skills == []

    @pytest.mark.asyncio
    async def test_load_all_skills_skips_files(self):
        """Test that files (not directories) are skipped."""
        with tempfile.TemporaryDirectory() as tmpdir:
            skills_dir = Path(tmpdir)

            # Create a valid skill
            skill_dir = skills_dir / "valid-skill"
            skill_dir.mkdir()
            (skill_dir / "SKILL.md").write_text("---\nname: valid\n---\nContent")

            # Create a file (not directory)
            (skills_dir / "not-a-skill.txt").write_text("Just a file")

            skills = await load_all_skills(skills_dir)

            assert len(skills) == 1
            assert skills[0].name == "valid"


class TestFormatSkillsForPrompt:
    """Test formatting skills for LLM prompt."""

    def test_format_empty_skills(self):
        """Test formatting with no skills."""
        result = format_skills_for_prompt([])
        assert result == ""

    def test_format_single_skill(self):
        """Test formatting a single skill."""
        skill = Skill(
            name="test-skill",
            description="A test skill",
            content="Do this thing.",
            file_path=Path("/fake/path"),
            metadata={},
        )

        result = format_skills_for_prompt([skill])

        assert "## Available Skills" in result
        assert "### test-skill" in result
        assert "*A test skill*" in result
        assert "Do this thing." in result

    def test_format_multiple_skills(self):
        """Test formatting multiple skills."""
        skills = [
            Skill(
                name="skill1",
                description="First skill",
                content="Content 1",
                file_path=Path("/fake/1"),
                metadata={},
            ),
            Skill(
                name="skill2",
                description="Second skill",
                content="Content 2",
                file_path=Path("/fake/2"),
                metadata={},
            ),
        ]

        result = format_skills_for_prompt(skills)

        assert "### skill1" in result
        assert "### skill2" in result
        assert "First skill" in result
        assert "Second skill" in result

    def test_format_skill_without_description(self):
        """Test formatting skill without description."""
        skill = Skill(
            name="no-desc",
            description="",
            content="Just content.",
            file_path=Path("/fake/path"),
            metadata={},
        )

        result = format_skills_for_prompt([skill])

        assert "### no-desc" in result
        assert "Just content." in result
        # Should not have empty italics
        assert "*\n" not in result
