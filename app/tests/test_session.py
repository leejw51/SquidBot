"""Tests for session and lane modules."""

import json
import tempfile
from pathlib import Path

import pytest

from lanes import LANE_CRON, LANE_MAIN, CommandLane
from session import ChannelType, DeliveryContext, Session, SessionManager


class TestCommandLane:
    """Test CommandLane enum."""

    def test_lane_values(self):
        """Test lane string values."""
        assert str(CommandLane.MAIN) == "main"
        assert str(CommandLane.CRON) == "cron"
        assert str(CommandLane.SUBAGENT) == "subagent"

    def test_lane_is_user_initiated(self):
        """Test user-initiated lane detection."""
        assert CommandLane.MAIN.is_user_initiated is True
        assert CommandLane.NESTED.is_user_initiated is True
        assert CommandLane.CRON.is_user_initiated is False
        assert CommandLane.WEBHOOK.is_user_initiated is False

    def test_lane_is_automated(self):
        """Test automated lane detection."""
        assert CommandLane.CRON.is_automated is True
        assert CommandLane.WEBHOOK.is_automated is True
        assert CommandLane.PROACTIVE.is_automated is True
        assert CommandLane.MAIN.is_automated is False


class TestChannelType:
    """Test ChannelType enum."""

    def test_channel_values(self):
        """Test channel string values."""
        assert str(ChannelType.TELEGRAM) == "telegram"
        assert str(ChannelType.WHATSAPP) == "whatsapp"
        assert str(ChannelType.DISCORD) == "discord"
        assert str(ChannelType.TCP) == "tcp"

    def test_supports_media(self):
        """Test media support detection."""
        assert ChannelType.TELEGRAM.supports_media is True
        assert ChannelType.DISCORD.supports_media is True
        assert ChannelType.TCP.supports_media is False
        assert ChannelType.API.supports_media is False

    def test_max_message_length(self):
        """Test message length limits."""
        assert ChannelType.TELEGRAM.max_message_length == 4096
        assert ChannelType.DISCORD.max_message_length == 2000
        assert ChannelType.TCP.max_message_length == 0  # No limit


class TestDeliveryContext:
    """Test DeliveryContext dataclass."""

    def test_create_context(self):
        """Test creating a delivery context."""
        ctx = DeliveryContext(
            channel=ChannelType.TELEGRAM,
            recipient_id="12345",
            thread_id="thread-1",
        )
        assert ctx.channel == ChannelType.TELEGRAM
        assert ctx.recipient_id == "12345"
        assert ctx.thread_id == "thread-1"

    def test_to_dict(self):
        """Test serialization to dict."""
        ctx = DeliveryContext(
            channel=ChannelType.TELEGRAM,
            recipient_id="12345",
        )
        data = ctx.to_dict()
        assert data["channel"] == "telegram"
        assert data["recipient_id"] == "12345"

    def test_from_dict(self):
        """Test deserialization from dict."""
        data = {
            "channel": "telegram",
            "recipient_id": "12345",
            "thread_id": "thread-1",
        }
        ctx = DeliveryContext.from_dict(data)
        assert ctx.channel == ChannelType.TELEGRAM
        assert ctx.recipient_id == "12345"
        assert ctx.thread_id == "thread-1"


class TestSession:
    """Test Session dataclass."""

    def test_create_key(self):
        """Test session key generation."""
        key = Session.create_key(ChannelType.TELEGRAM, "12345")
        assert key == "telegram:12345"

    def test_create_session(self):
        """Test creating a session."""
        session = Session.create(
            channel=ChannelType.TELEGRAM,
            recipient_id="12345",
        )
        assert session.session_key == "telegram:12345"
        assert session.channel == ChannelType.TELEGRAM
        assert session.history == []

    def test_add_message(self):
        """Test adding messages to history."""
        session = Session.create(ChannelType.TCP, "client-1")
        session.add_message("user", "Hello")
        session.add_message("assistant", "Hi there!")

        assert len(session.history) == 2
        assert session.history[0]["role"] == "user"
        assert session.history[1]["content"] == "Hi there!"

    def test_clear_history(self):
        """Test clearing history."""
        session = Session.create(ChannelType.TCP, "client-1")
        session.add_message("user", "Hello")
        session.clear_history()
        assert session.history == []

    def test_to_dict(self):
        """Test serialization."""
        session = Session.create(ChannelType.TELEGRAM, "12345")
        session.add_message("user", "test")
        data = session.to_dict()

        assert data["session_key"] == "telegram:12345"
        assert data["channel"] == "telegram"
        assert len(data["history"]) == 1

    def test_from_dict(self):
        """Test deserialization."""
        data = {
            "session_key": "telegram:12345",
            "channel": "telegram",
            "recipient_id": "12345",
            "history": [{"role": "user", "content": "test"}],
            "metadata": {},
            "created_at": 1000.0,
            "updated_at": 1000.0,
            "last_lane": "main",
        }
        session = Session.from_dict(data)

        assert session.session_key == "telegram:12345"
        assert session.channel == ChannelType.TELEGRAM
        assert len(session.history) == 1


class TestSessionManager:
    """Test SessionManager class."""

    @pytest.fixture
    def temp_store(self):
        """Create a temporary store directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    def test_get_or_create(self, temp_store):
        """Test getting or creating sessions."""
        manager = SessionManager(temp_store)

        session = manager.get(ChannelType.TELEGRAM, "12345")
        assert session is not None
        assert session.session_key == "telegram:12345"

        # Should return same session
        session2 = manager.get(ChannelType.TELEGRAM, "12345")
        assert session2.session_key == session.session_key

    def test_get_nonexistent(self, temp_store):
        """Test getting nonexistent session without creating."""
        manager = SessionManager(temp_store)
        session = manager.get(ChannelType.TELEGRAM, "99999", create_if_missing=False)
        assert session is None

    def test_update_session(self, temp_store):
        """Test updating sessions."""
        manager = SessionManager(temp_store)

        session = manager.get(ChannelType.TCP, "client-1")
        session.add_message("user", "Hello")
        manager.update(session)

        # Create new manager to test persistence
        manager2 = SessionManager(temp_store)
        session2 = manager2.get(ChannelType.TCP, "client-1")
        assert len(session2.history) == 1
        assert session2.history[0]["content"] == "Hello"

    def test_delete_session(self, temp_store):
        """Test deleting sessions."""
        manager = SessionManager(temp_store)

        session = manager.get(ChannelType.TELEGRAM, "12345")
        assert session is not None

        result = manager.delete("telegram:12345")
        assert result is True

        session2 = manager.get(ChannelType.TELEGRAM, "12345", create_if_missing=False)
        assert session2 is None

    def test_list_sessions(self, temp_store):
        """Test listing sessions."""
        manager = SessionManager(temp_store)

        # Create some sessions
        manager.get(ChannelType.TELEGRAM, "1")
        manager.get(ChannelType.TELEGRAM, "2")
        manager.get(ChannelType.DISCORD, "3")

        all_sessions = manager.list_sessions()
        assert len(all_sessions) == 3

        telegram_sessions = manager.list_sessions(channel=ChannelType.TELEGRAM)
        assert len(telegram_sessions) == 2

    def test_get_active_delivery_contexts(self, temp_store):
        """Test getting delivery contexts for broadcasting."""
        manager = SessionManager(temp_store)

        # Create sessions with delivery contexts
        session1 = manager.get(ChannelType.TELEGRAM, "1")
        session1.delivery_context = DeliveryContext(
            channel=ChannelType.TELEGRAM,
            recipient_id="1",
        )
        manager.update(session1)

        session2 = manager.get(ChannelType.TCP, "client-1")
        manager.update(session2)

        contexts = manager.get_active_delivery_contexts()
        assert len(contexts) == 2
