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
