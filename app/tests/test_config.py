"""Tests for configuration module."""

import os
from pathlib import Path

import pytest


class TestConfigValidation:
    """Test configuration validation."""

    def test_validate_config_raises_on_missing_token(self):
        """Test validation raises ValueError when TELEGRAM_BOT_TOKEN is empty."""
        # Import fresh config module
        import config

        # Save original values
        orig_token = config.TELEGRAM_BOT_TOKEN
        orig_key = config.OPENAI_API_KEY

        try:
            # Set empty values
            config.TELEGRAM_BOT_TOKEN = ""
            config.OPENAI_API_KEY = "test_key"

            with pytest.raises(ValueError) as exc_info:
                config.validate_config()

            assert "TELEGRAM_BOT_TOKEN" in str(exc_info.value)
        finally:
            # Restore
            config.TELEGRAM_BOT_TOKEN = orig_token
            config.OPENAI_API_KEY = orig_key

    def test_validate_config_raises_on_missing_api_key(self):
        """Test validation raises ValueError when OPENAI_API_KEY is empty."""
        import config

        orig_token = config.TELEGRAM_BOT_TOKEN
        orig_key = config.OPENAI_API_KEY

        try:
            config.TELEGRAM_BOT_TOKEN = "test_token"
            config.OPENAI_API_KEY = ""

            with pytest.raises(ValueError) as exc_info:
                config.validate_config()

            assert "OPENAI_API_KEY" in str(exc_info.value)
        finally:
            config.TELEGRAM_BOT_TOKEN = orig_token
            config.OPENAI_API_KEY = orig_key

    def test_validate_config_raises_on_both_missing(self):
        """Test validation lists both missing configs."""
        import config

        orig_token = config.TELEGRAM_BOT_TOKEN
        orig_key = config.OPENAI_API_KEY

        try:
            config.TELEGRAM_BOT_TOKEN = ""
            config.OPENAI_API_KEY = ""

            with pytest.raises(ValueError) as exc_info:
                config.validate_config()

            error_msg = str(exc_info.value)
            assert "TELEGRAM_BOT_TOKEN" in error_msg
            assert "OPENAI_API_KEY" in error_msg
        finally:
            config.TELEGRAM_BOT_TOKEN = orig_token
            config.OPENAI_API_KEY = orig_key

    def test_validate_config_passes_with_values(self):
        """Test validation passes when config values are set."""
        import config

        orig_token = config.TELEGRAM_BOT_TOKEN
        orig_key = config.OPENAI_API_KEY

        try:
            config.TELEGRAM_BOT_TOKEN = "test_token"
            config.OPENAI_API_KEY = "test_key"

            # Should not raise
            config.validate_config()
        finally:
            config.TELEGRAM_BOT_TOKEN = orig_token
            config.OPENAI_API_KEY = orig_key


class TestConfigDefaults:
    """Test configuration default values."""

    def test_openai_model_has_default(self):
        """Test OPENAI_MODEL has a default value."""
        import config

        # The default is set during import from env or hardcoded
        assert config.OPENAI_MODEL is not None
        assert len(config.OPENAI_MODEL) > 0

    def test_heartbeat_interval_is_integer(self):
        """Test HEARTBEAT_INTERVAL_MINUTES is an integer."""
        import config

        assert isinstance(config.HEARTBEAT_INTERVAL_MINUTES, int)
        assert config.HEARTBEAT_INTERVAL_MINUTES >= 0

    def test_squid_port_is_integer(self):
        """Test SQUID_PORT is an integer."""
        import config

        assert isinstance(config.SQUID_PORT, int)
        assert config.SQUID_PORT > 0


class TestConfigPaths:
    """Test configuration paths."""

    def test_data_dir_is_path(self):
        """Test DATA_DIR is a Path object."""
        import config

        assert isinstance(config.DATA_DIR, Path)

    def test_memory_file_is_path(self):
        """Test MEMORY_FILE is a Path object."""
        import config

        assert isinstance(config.MEMORY_FILE, Path)

    def test_cron_file_is_path(self):
        """Test CRON_FILE is a Path object."""
        import config

        assert isinstance(config.CRON_FILE, Path)

    def test_memory_file_has_correct_name(self):
        """Test MEMORY_FILE has correct filename."""
        import config

        assert config.MEMORY_FILE.name == "memory.json"

    def test_cron_file_in_data_dir(self):
        """Test CRON_FILE is inside DATA_DIR."""
        import config

        assert config.CRON_FILE.parent == config.DATA_DIR

    def test_data_dir_exists_or_can_be_created(self):
        """Test DATA_DIR can be created if it doesn't exist."""
        import config

        # The config module creates DATA_DIR on import
        # We just verify it's a valid path
        assert config.DATA_DIR.is_absolute() or str(config.DATA_DIR).startswith("~")

    def test_character_file_is_path(self):
        """Test CHARACTER_FILE is a Path object."""
        import config

        assert isinstance(config.CHARACTER_FILE, Path)
        assert config.CHARACTER_FILE.name == "CHARACTER.md"

    def test_skills_dir_is_path(self):
        """Test SKILLS_DIR is a Path object."""
        import config

        assert isinstance(config.SKILLS_DIR, Path)
        assert config.SKILLS_DIR.name == "skills"

    def test_coding_dir_is_path(self):
        """Test CODING_DIR is a Path object."""
        import config

        assert isinstance(config.CODING_DIR, Path)
        assert config.CODING_DIR.name == "coding"

    def test_sessions_dir_is_path(self):
        """Test SESSIONS_DIR is a Path object."""
        import config

        assert isinstance(config.SESSIONS_DIR, Path)
        assert config.SESSIONS_DIR.name == "sessions"


class TestSquidbotHome:
    """Test SQUIDBOT_HOME environment variable."""

    def test_default_home_is_dot_squidbot(self, monkeypatch):
        """Test default home is ~/.squidbot when SQUIDBOT_HOME not set."""
        monkeypatch.delenv("SQUIDBOT_HOME", raising=False)

        # Re-import to get fresh values
        import importlib

        import config

        importlib.reload(config)

        assert ".squidbot" in str(config.DATA_DIR)

    def test_custom_home_from_env(self, tmp_path, monkeypatch):
        """Test custom home from SQUIDBOT_HOME env var."""
        custom_home = tmp_path / "custom_squidbot"
        monkeypatch.setenv("SQUIDBOT_HOME", str(custom_home))

        import importlib

        import config

        importlib.reload(config)

        assert config.DATA_DIR == custom_home


class TestInitDefaultFiles:
    """Test init_default_files function."""

    def test_creates_character_file(self, tmp_path, monkeypatch):
        """Test that init_default_files creates CHARACTER.md."""
        monkeypatch.setenv("SQUIDBOT_HOME", str(tmp_path))

        import importlib

        import config

        importlib.reload(config)

        # Remove if exists
        if config.CHARACTER_FILE.exists():
            config.CHARACTER_FILE.unlink()

        config.init_default_files()

        assert config.CHARACTER_FILE.exists()
        content = config.CHARACTER_FILE.read_text()
        assert "Character Definition" in content

    def test_creates_default_skills(self, tmp_path, monkeypatch):
        """Test that init_default_files creates default skills."""
        monkeypatch.setenv("SQUIDBOT_HOME", str(tmp_path))

        import importlib

        import config

        importlib.reload(config)

        config.init_default_files()

        search_skill = config.SKILLS_DIR / "search" / "SKILL.md"
        reminder_skill = config.SKILLS_DIR / "reminder" / "SKILL.md"

        assert search_skill.exists()
        assert reminder_skill.exists()

        assert "web_search" in search_skill.read_text()
        assert "cron_create" in reminder_skill.read_text()

    def test_does_not_overwrite_existing(self, tmp_path, monkeypatch):
        """Test that init_default_files does not overwrite existing files."""
        monkeypatch.setenv("SQUIDBOT_HOME", str(tmp_path))

        import importlib

        import config

        importlib.reload(config)

        # Create custom character file
        config.ensure_data_dirs()
        custom_content = "# My Custom Character"
        config.CHARACTER_FILE.write_text(custom_content)

        config.init_default_files()

        # Should not be overwritten
        assert config.CHARACTER_FILE.read_text() == custom_content

    def test_creates_all_directories(self, tmp_path, monkeypatch):
        """Test that ensure_data_dirs creates all required directories."""
        monkeypatch.setenv("SQUIDBOT_HOME", str(tmp_path))

        import importlib

        import config

        importlib.reload(config)

        config.ensure_data_dirs()

        assert config.DATA_DIR.exists()
        assert config.SKILLS_DIR.exists()
        assert config.CODING_DIR.exists()
        assert config.SESSIONS_DIR.exists()


class TestShowStartupInfo:
    """Test show_startup_info function."""

    def test_show_startup_info_runs(self, capsys):
        """Test that show_startup_info runs without error."""
        import config

        config.show_startup_info()

        captured = capsys.readouterr()
        assert "SquidBot Configuration" in captured.out
        assert "Home Directory" in captured.out
        assert "Server Port" in captured.out

    def test_show_startup_info_shows_paths(self, capsys):
        """Test that show_startup_info shows all paths."""
        import config

        config.show_startup_info()

        captured = capsys.readouterr()
        assert "Character File" in captured.out
        assert "Skills Dir" in captured.out
        assert "Coding Dir" in captured.out
        assert "Sessions Dir" in captured.out

    def test_show_startup_info_shows_env_hint(self, capsys):
        """Test that show_startup_info shows env var hints."""
        import config

        config.show_startup_info()

        captured = capsys.readouterr()
        assert "SQUIDBOT_HOME" in captured.out
        assert "SQUID_PORT" in captured.out
