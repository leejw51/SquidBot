"""Tests for character/personality configuration."""

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest


class TestLoadCharacterFile:
    """Test loading character file."""

    @pytest.mark.asyncio
    async def test_load_existing_file(self):
        """Test loading an existing CHARACTER.md file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            char_file = Path(tmpdir) / "CHARACTER.md"
            char_file.write_text("# My Character\nI am helpful.")

            with patch("character.CHARACTER_FILE", char_file):
                from character import load_character_file

                content = await load_character_file()

            assert "My Character" in content
            assert "I am helpful" in content

    @pytest.mark.asyncio
    async def test_load_nonexistent_file(self):
        """Test loading when file doesn't exist."""
        with patch("character.CHARACTER_FILE", Path("/nonexistent/file.md")):
            from character import load_character_file

            content = await load_character_file()

        assert content == ""


class TestGetCharacterPrompt:
    """Test building character prompt."""

    @pytest.mark.asyncio
    async def test_default_character(self):
        """Test with default character (no customization)."""
        with patch("character.CHARACTER_NAME", "Assistant"), patch(
            "character.CHARACTER_PERSONA", ""
        ), patch("character.CHARACTER_STYLE", "helpful, friendly, concise"), patch(
            "character.CHARACTER_FILE", Path("/nonexistent")
        ):
            from character import get_character_prompt

            prompt = await get_character_prompt()

        # Should have style but not name (since name is "Assistant")
        assert "Communication style:" in prompt
        assert "helpful, friendly, concise" in prompt

    @pytest.mark.asyncio
    async def test_custom_name(self):
        """Test with custom character name."""
        with patch("character.CHARACTER_NAME", "Squidward"), patch(
            "character.CHARACTER_PERSONA", ""
        ), patch("character.CHARACTER_STYLE", ""), patch(
            "character.CHARACTER_FILE", Path("/nonexistent")
        ):
            from character import get_character_prompt

            prompt = await get_character_prompt()

        assert "Your name is Squidward" in prompt

    @pytest.mark.asyncio
    async def test_custom_persona(self):
        """Test with custom persona."""
        with patch("character.CHARACTER_NAME", "Assistant"), patch(
            "character.CHARACTER_PERSONA", "You are a wise sage."
        ), patch("character.CHARACTER_STYLE", ""), patch(
            "character.CHARACTER_FILE", Path("/nonexistent")
        ):
            from character import get_character_prompt

            prompt = await get_character_prompt()

        assert "wise sage" in prompt

    @pytest.mark.asyncio
    async def test_all_empty(self):
        """Test with all character options empty."""
        with patch("character.CHARACTER_NAME", "Assistant"), patch(
            "character.CHARACTER_PERSONA", ""
        ), patch("character.CHARACTER_STYLE", ""), patch(
            "character.CHARACTER_FILE", Path("/nonexistent")
        ):
            from character import get_character_prompt

            prompt = await get_character_prompt()

        assert prompt == ""

    @pytest.mark.asyncio
    async def test_with_character_file(self):
        """Test loading character from file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            char_file = Path(tmpdir) / "CHARACTER.md"
            char_file.write_text("# Custom\nI am a custom character.")

            with patch("character.CHARACTER_NAME", "Assistant"), patch(
                "character.CHARACTER_PERSONA", ""
            ), patch("character.CHARACTER_STYLE", ""), patch(
                "character.CHARACTER_FILE", char_file
            ):
                from character import get_character_prompt

                prompt = await get_character_prompt()

            assert "Custom" in prompt
            assert "custom character" in prompt


class TestCreateExampleCharacter:
    """Test creating example character file."""

    @pytest.mark.asyncio
    async def test_create_example_when_not_exists(self):
        """Test creating example when file doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            char_file = Path(tmpdir) / "CHARACTER.md"

            with patch("character.CHARACTER_FILE", char_file):
                from character import create_example_character

                await create_example_character()

            assert char_file.exists()
            content = char_file.read_text()
            assert "Character Definition" in content
            assert "Personality" in content

    @pytest.mark.asyncio
    async def test_skip_if_exists(self):
        """Test that existing file is not overwritten."""
        with tempfile.TemporaryDirectory() as tmpdir:
            char_file = Path(tmpdir) / "CHARACTER.md"
            char_file.write_text("My custom character")

            with patch("character.CHARACTER_FILE", char_file):
                from character import create_example_character

                await create_example_character()

            # Should not be overwritten
            content = char_file.read_text()
            assert content == "My custom character"
