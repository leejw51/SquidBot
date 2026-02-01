"""Tests for session and lane modules with JSONL transcripts."""

import json
import tempfile
from pathlib import Path

import pytest

from lanes import LANE_CRON, LANE_MAIN, CommandLane
from session import (ChannelType, DeliveryContext, Session, SessionEntry,
                     SessionManager, SessionTranscript)


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


class TestSessionTranscript:
    """Test JSONL-based SessionTranscript."""

    @pytest.fixture
    def temp_transcript(self, tmp_path):
        """Create a temporary transcript file."""
        file_path = tmp_path / "test_session.jsonl"
        return SessionTranscript(file_path, session_id="test-123")

    def test_creates_header(self, temp_transcript):
        """Test that transcript creates header on init."""
        assert temp_transcript.file_path.exists()

        with open(temp_transcript.file_path) as f:
            header = json.loads(f.readline())

        assert header["type"] == "session"
        assert header["id"] == "test-123"
        assert "version" in header
        assert "timestamp" in header

    def test_append_message(self, temp_transcript):
        """Test appending messages."""
        temp_transcript.append_message("user", "Hello")
        temp_transcript.append_message("assistant", "Hi there!")

        messages = list(temp_transcript.read_messages())
        assert len(messages) == 2
        assert messages[0]["role"] == "user"
        assert messages[0]["content"] == "Hello"
        assert messages[1]["role"] == "assistant"

    def test_append_user_message(self, temp_transcript):
        """Test append_user_message helper."""
        temp_transcript.append_user_message("Test message")
        messages = list(temp_transcript.read_messages())
        assert messages[0]["role"] == "user"

    def test_append_assistant_message(self, temp_transcript):
        """Test append_assistant_message helper."""
        temp_transcript.append_assistant_message("Response")
        messages = list(temp_transcript.read_messages())
        assert messages[0]["role"] == "assistant"

    def test_append_tool_call(self, temp_transcript):
        """Test appending tool calls."""
        temp_transcript.append_tool_call("web_search", {"query": "test"})
        messages = list(temp_transcript.read_messages())
        assert messages[0]["type"] == "tool_call"
        assert messages[0]["tool"] == "web_search"
        assert messages[0]["input"]["query"] == "test"

    def test_append_tool_result(self, temp_transcript):
        """Test appending tool results."""
        temp_transcript.append_tool_result("web_search", "Found results")
        messages = list(temp_transcript.read_messages())
        assert messages[0]["type"] == "tool_result"
        assert messages[0]["result"] == "Found results"

    def test_get_history(self, temp_transcript):
        """Test getting conversation history."""
        temp_transcript.append_message("user", "Hello")
        temp_transcript.append_tool_call("test", {})
        temp_transcript.append_message("assistant", "Hi")

        history = temp_transcript.get_history()
        assert len(history) == 2  # Only messages, not tool calls
        assert history[0]["role"] == "user"
        assert history[1]["role"] == "assistant"

    def test_get_history_with_limit(self, temp_transcript):
        """Test history limit."""
        for i in range(10):
            temp_transcript.append_message("user", f"Message {i}")

        history = temp_transcript.get_history(limit=3)
        assert len(history) == 3
        assert history[0]["content"] == "Message 7"

    def test_get_full_history(self, temp_transcript):
        """Test getting full history including tool calls."""
        temp_transcript.append_message("user", "Hello")
        temp_transcript.append_tool_call("test", {})
        temp_transcript.append_message("assistant", "Hi")

        full = temp_transcript.get_full_history()
        assert len(full) == 3

    def test_count_messages(self, temp_transcript):
        """Test counting messages."""
        temp_transcript.append_message("user", "1")
        temp_transcript.append_message("assistant", "2")
        temp_transcript.append_tool_call("test", {})

        assert temp_transcript.count_messages() == 2  # Tool calls not counted

    def test_clear(self, temp_transcript):
        """Test clearing transcript."""
        temp_transcript.append_message("user", "Hello")
        temp_transcript.clear()

        # Should have new header but no messages
        messages = list(temp_transcript.read_messages())
        assert len(messages) == 0


class TestSession:
    """Test Session with JSONL transcript."""

    @pytest.fixture
    def temp_session(self, tmp_path):
        """Create a temporary session."""
        transcript_path = tmp_path / "session.jsonl"
        transcript = SessionTranscript(transcript_path, "session-123")
        entry = SessionEntry(
            session_id="session-123",
            session_key="telegram:12345",
            channel=ChannelType.TELEGRAM,
            recipient_id="12345",
            transcript_file=str(transcript_path),
            created_at=1000.0,
            updated_at=1000.0,
        )
        return Session(entry=entry, transcript=transcript)

    def test_session_properties(self, temp_session):
        """Test session property accessors."""
        assert temp_session.session_key == "telegram:12345"
        assert temp_session.session_id == "session-123"
        assert temp_session.channel == ChannelType.TELEGRAM
        assert temp_session.recipient_id == "12345"

    def test_create_key(self):
        """Test session key generation."""
        key = Session.create_key(ChannelType.TELEGRAM, "12345")
        assert key == "telegram:12345"

    def test_add_message(self, temp_session):
        """Test adding messages."""
        temp_session.add_message("user", "Hello")
        temp_session.add_message("assistant", "Hi!")

        history = temp_session.history
        assert len(history) == 2
        assert history[0]["role"] == "user"

    def test_clear_history(self, temp_session):
        """Test clearing history."""
        temp_session.add_message("user", "Hello")
        temp_session.clear_history()
        assert len(temp_session.history) == 0
        assert temp_session.entry.message_count == 0

    def test_history_setter(self, temp_session):
        """Test setting history directly."""
        temp_session.history = [
            {"role": "user", "content": "A"},
            {"role": "assistant", "content": "B"},
        ]
        assert len(temp_session.history) == 2
        assert temp_session.entry.message_count == 2

    def test_to_dict(self, temp_session):
        """Test serialization."""
        temp_session.add_message("user", "test")
        data = temp_session.to_dict()

        assert data["session_key"] == "telegram:12345"
        assert data["channel"] == "telegram"
        assert len(data["history"]) == 1


class TestSessionManager:
    """Test SessionManager with JSONL transcripts."""

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

    def test_creates_jsonl_transcript(self, temp_store):
        """Test that session creates JSONL transcript file."""
        manager = SessionManager(temp_store)
        session = manager.get(ChannelType.TCP, "client-1")

        # Transcript file should exist
        transcript_path = temp_store / session.entry.transcript_file
        assert transcript_path.exists()
        assert transcript_path.suffix == ".jsonl"

    def test_creates_index_file(self, temp_store):
        """Test that manager creates sessions.json index."""
        manager = SessionManager(temp_store)
        manager.get(ChannelType.TELEGRAM, "1")

        index_file = temp_store / "sessions.json"
        assert index_file.exists()

        data = json.loads(index_file.read_text())
        assert "telegram:1" in data

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
        transcript_file = temp_store / session.entry.transcript_file
        assert transcript_file.exists()

        result = manager.delete("telegram:12345")
        assert result is True
        assert not transcript_file.exists()

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


class TestJSONLFormat:
    """Test JSONL file format compliance."""

    @pytest.fixture
    def temp_transcript(self, tmp_path):
        """Create a temporary transcript file."""
        file_path = tmp_path / "test.jsonl"
        return SessionTranscript(file_path, session_id="jsonl-test")

    def test_each_line_is_valid_json(self, temp_transcript):
        """Test that each line in transcript is valid JSON."""
        temp_transcript.append_message("user", "Hello")
        temp_transcript.append_tool_call("test", {"a": 1})
        temp_transcript.append_message("assistant", "Hi")

        with open(temp_transcript.file_path) as f:
            for line in f:
                line = line.strip()
                if line:
                    # Should not raise
                    data = json.loads(line)
                    assert isinstance(data, dict)

    def test_newline_delimited(self, temp_transcript):
        """Test that entries are newline-delimited."""
        temp_transcript.append_message("user", "A")
        temp_transcript.append_message("assistant", "B")

        content = temp_transcript.file_path.read_text()
        lines = content.strip().split("\n")
        assert len(lines) == 3  # header + 2 messages

    def test_unicode_support(self, temp_transcript):
        """Test that JSONL supports unicode."""
        temp_transcript.append_message("user", "Hello 世界 🌍")
        messages = list(temp_transcript.read_messages())
        assert messages[0]["content"] == "Hello 世界 🌍"
