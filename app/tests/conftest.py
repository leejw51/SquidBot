"""Pytest configuration and fixtures."""

import json
import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Set test environment variables before importing config
os.environ["TELEGRAM_BOT_TOKEN"] = "test_token"
os.environ["OPENAI_API_KEY"] = "test_api_key"
os.environ["OPENAI_MODEL"] = "gpt-4o"
os.environ["HEARTBEAT_INTERVAL_MINUTES"] = "0"


@pytest.fixture(autouse=True)
def temp_data_dir(tmp_path, monkeypatch):
    """Create a temporary data directory for tests - auto-used for all tests."""
    import config
    import memory_db
    from tools import cron

    # Create temp paths
    temp_db = tmp_path / "memory.db"
    temp_cron = tmp_path / "cron_jobs.json"

    # Patch config module
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "CRON_FILE", temp_cron)

    # Patch memory_db module
    monkeypatch.setattr(memory_db, "DB_PATH", temp_db)

    # Also patch the cron module
    monkeypatch.setattr(cron, "CRON_FILE", temp_cron)

    # Mock embedding function to avoid API calls
    async def fake_embedding(text):
        import hashlib
        import random

        hash_val = int(hashlib.md5(text.encode()).hexdigest(), 16)
        random.seed(hash_val)
        return [random.random() for _ in range(1536)]

    monkeypatch.setattr(memory_db, "get_embedding", fake_embedding)

    yield tmp_path


@pytest.fixture
def mock_openai_client():
    """Mock OpenAI client for testing."""
    with patch("agent.client") as mock_client:
        yield mock_client


@pytest.fixture
def mock_openai_response():
    """Factory for creating mock OpenAI responses."""

    def _create_response(content=None, tool_calls=None):
        response = MagicMock()
        message = MagicMock()
        message.content = content
        message.tool_calls = tool_calls
        response.choices = [MagicMock(message=message)]
        return response

    return _create_response


@pytest.fixture
def mock_tool_call():
    """Factory for creating mock tool calls."""

    def _create_tool_call(name, arguments):
        tc = MagicMock()
        tc.id = f"call_{name}"
        tc.function.name = name
        tc.function.arguments = json.dumps(arguments)
        return tc

    return _create_tool_call


@pytest.fixture
def mock_embedding():
    """Mock OpenAI embedding response for tests."""

    async def mock_get_embedding(text):
        # Return a fake embedding (1536 dimensions)
        import hashlib

        # Generate deterministic fake embedding based on text
        hash_val = int(hashlib.md5(text.encode()).hexdigest(), 16)
        import random

        random.seed(hash_val)
        return [random.random() for _ in range(1536)]

    return mock_get_embedding
