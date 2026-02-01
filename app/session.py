"""
Session Management - Channel-agnostic session handling with JSONL transcripts.

Supports multiple channels: Telegram, WhatsApp, Discord, TCP, etc.
Uses JSONL format for session transcripts (one JSON object per line).
"""

import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Iterator

from config import DATA_DIR
from lanes import CommandLane

logger = logging.getLogger(__name__)

# Session format version
SESSION_VERSION = 1


class ChannelType(str, Enum):
    """Supported messaging channels."""

    TELEGRAM = "telegram"
    WHATSAPP = "whatsapp"
    DISCORD = "discord"
    SLACK = "slack"
    TCP = "tcp"  # Local TCP client
    WEB = "web"  # Web interface
    API = "api"  # Direct API access

    def __str__(self) -> str:
        return self.value

    @property
    def supports_media(self) -> bool:
        """Whether this channel supports media messages."""
        return self in (
            ChannelType.TELEGRAM,
            ChannelType.WHATSAPP,
            ChannelType.DISCORD,
            ChannelType.SLACK,
            ChannelType.WEB,
        )

    @property
    def supports_reactions(self) -> bool:
        """Whether this channel supports message reactions."""
        return self in (
            ChannelType.TELEGRAM,
            ChannelType.DISCORD,
            ChannelType.SLACK,
        )

    @property
    def max_message_length(self) -> int:
        """Maximum message length for this channel."""
        limits = {
            ChannelType.TELEGRAM: 4096,
            ChannelType.WHATSAPP: 4096,
            ChannelType.DISCORD: 2000,
            ChannelType.SLACK: 40000,
            ChannelType.TCP: 0,  # No limit
            ChannelType.WEB: 0,  # No limit
            ChannelType.API: 0,  # No limit
        }
        return limits.get(self, 4096)


@dataclass
class DeliveryContext:
    """Context for message delivery routing."""

    channel: ChannelType
    recipient_id: str  # Chat ID, user ID, etc.
    account_id: str | None = None  # Bot account if multiple
    thread_id: str | None = None  # Thread/topic ID if applicable
    guild_id: str | None = None  # Discord guild/server ID
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "channel": str(self.channel),
            "recipient_id": self.recipient_id,
            "account_id": self.account_id,
            "thread_id": self.thread_id,
            "guild_id": self.guild_id,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DeliveryContext":
        return cls(
            channel=ChannelType(data["channel"]),
            recipient_id=data["recipient_id"],
            account_id=data.get("account_id"),
            thread_id=data.get("thread_id"),
            guild_id=data.get("guild_id"),
            metadata=data.get("metadata", {}),
        )


@dataclass
class SessionEntry:
    """Session metadata stored in sessions.json index."""

    session_id: str
    session_key: str
    channel: ChannelType
    recipient_id: str
    transcript_file: str  # Path to .jsonl transcript
    created_at: float
    updated_at: float
    last_lane: CommandLane = CommandLane.MAIN
    delivery_context: DeliveryContext | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    message_count: int = 0
    display_name: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "session_key": self.session_key,
            "channel": str(self.channel),
            "recipient_id": self.recipient_id,
            "transcript_file": self.transcript_file,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "last_lane": str(self.last_lane),
            "delivery_context": (
                self.delivery_context.to_dict() if self.delivery_context else None
            ),
            "metadata": self.metadata,
            "message_count": self.message_count,
            "display_name": self.display_name,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SessionEntry":
        delivery_ctx = data.get("delivery_context")
        return cls(
            session_id=data["session_id"],
            session_key=data["session_key"],
            channel=ChannelType(data["channel"]),
            recipient_id=data["recipient_id"],
            transcript_file=data["transcript_file"],
            created_at=data.get("created_at", time.time()),
            updated_at=data.get("updated_at", time.time()),
            last_lane=CommandLane(data.get("last_lane", "main")),
            delivery_context=(
                DeliveryContext.from_dict(delivery_ctx) if delivery_ctx else None
            ),
            metadata=data.get("metadata", {}),
            message_count=data.get("message_count", 0),
            display_name=data.get("display_name"),
        )


@dataclass
class TranscriptMessage:
    """A single message in a session transcript."""

    type: str  # "message", "tool_call", "tool_result", "system", etc.
    role: str  # "user", "assistant", "system"
    content: str
    timestamp: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TranscriptMessage":
        return cls(
            type=data.get("type", "message"),
            role=data["role"],
            content=data["content"],
            timestamp=data.get("timestamp", datetime.now().isoformat()),
            metadata=data.get("metadata", {}),
        )


class SessionTranscript:
    """JSONL-based session transcript."""

    def __init__(self, file_path: Path, session_id: str | None = None):
        self.file_path = file_path
        self.session_id = session_id or str(uuid.uuid4())
        self._ensure_header()

    def _ensure_header(self) -> None:
        """Ensure transcript has a header line."""
        if not self.file_path.exists():
            self.file_path.parent.mkdir(parents=True, exist_ok=True)
            header = {
                "type": "session",
                "version": SESSION_VERSION,
                "id": self.session_id,
                "timestamp": datetime.now().isoformat(),
            }
            self._append_line(header)

    def _append_line(self, data: dict) -> None:
        """Append a JSON line to the transcript."""
        with open(self.file_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(data, ensure_ascii=False) + "\n")

    def append_message(
        self,
        role: str,
        content: str,
        msg_type: str = "message",
        metadata: dict | None = None,
    ) -> None:
        """Append a message to the transcript."""
        msg = TranscriptMessage(
            type=msg_type,
            role=role,
            content=content,
            timestamp=datetime.now().isoformat(),
            metadata=metadata or {},
        )
        self._append_line(msg.to_dict())

    def append_user_message(self, content: str, metadata: dict | None = None) -> None:
        """Append a user message."""
        self.append_message("user", content, "message", metadata)

    def append_assistant_message(
        self, content: str, metadata: dict | None = None
    ) -> None:
        """Append an assistant message."""
        self.append_message("assistant", content, "message", metadata)

    def append_tool_call(
        self, tool_name: str, tool_input: dict, metadata: dict | None = None
    ) -> None:
        """Append a tool call."""
        self._append_line(
            {
                "type": "tool_call",
                "tool": tool_name,
                "input": tool_input,
                "timestamp": datetime.now().isoformat(),
                "metadata": metadata or {},
            }
        )

    def append_tool_result(
        self, tool_name: str, result: str, metadata: dict | None = None
    ) -> None:
        """Append a tool result."""
        self._append_line(
            {
                "type": "tool_result",
                "tool": tool_name,
                "result": result,
                "timestamp": datetime.now().isoformat(),
                "metadata": metadata or {},
            }
        )

    def read_messages(self) -> Iterator[dict]:
        """Read all messages from transcript (excluding header)."""
        if not self.file_path.exists():
            return

        with open(self.file_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    if data.get("type") != "session":  # Skip header
                        yield data
                except json.JSONDecodeError:
                    logger.warning(f"Invalid JSON line in transcript: {line[:50]}...")

    def get_history(self, limit: int | None = None) -> list[dict]:
        """Get conversation history as list of message dicts."""
        messages = []
        for msg in self.read_messages():
            if msg.get("type") == "message":
                messages.append(
                    {
                        "role": msg["role"],
                        "content": msg["content"],
                    }
                )
        if limit:
            messages = messages[-limit:]
        return messages

    def get_full_history(self) -> list[dict]:
        """Get full transcript including tool calls."""
        return list(self.read_messages())

    def count_messages(self) -> int:
        """Count messages in transcript."""
        count = 0
        for msg in self.read_messages():
            if msg.get("type") == "message":
                count += 1
        return count

    def clear(self) -> None:
        """Clear transcript and write new header."""
        if self.file_path.exists():
            self.file_path.unlink()
        self._ensure_header()


@dataclass
class Session:
    """Session representing a conversation context."""

    entry: SessionEntry
    transcript: SessionTranscript

    @property
    def session_key(self) -> str:
        return self.entry.session_key

    @property
    def session_id(self) -> str:
        return self.entry.session_id

    @property
    def channel(self) -> ChannelType:
        return self.entry.channel

    @property
    def recipient_id(self) -> str:
        return self.entry.recipient_id

    @property
    def history(self) -> list[dict]:
        """Get conversation history."""
        return self.transcript.get_history()

    @history.setter
    def history(self, value: list[dict]) -> None:
        """Set history by clearing and rewriting transcript."""
        self.transcript.clear()
        for msg in value:
            self.transcript.append_message(
                role=msg["role"],
                content=msg["content"],
            )
        self.entry.message_count = len(value)

    @property
    def delivery_context(self) -> DeliveryContext | None:
        return self.entry.delivery_context

    @delivery_context.setter
    def delivery_context(self, value: DeliveryContext | None) -> None:
        self.entry.delivery_context = value

    @property
    def last_lane(self) -> CommandLane:
        return self.entry.last_lane

    @last_lane.setter
    def last_lane(self, value: CommandLane) -> None:
        self.entry.last_lane = value

    @classmethod
    def create_key(cls, channel: ChannelType, recipient_id: str) -> str:
        """Generate a unique session key."""
        return f"{channel}:{recipient_id}"

    def touch(self) -> None:
        """Update the session timestamp."""
        self.entry.updated_at = time.time()

    def add_message(self, role: str, content: str) -> None:
        """Add a message to transcript."""
        self.transcript.append_message(role, content)
        self.entry.message_count += 1
        self.touch()

    def clear_history(self) -> None:
        """Clear conversation history."""
        self.transcript.clear()
        self.entry.message_count = 0
        self.touch()

    def to_dict(self) -> dict[str, Any]:
        """For backwards compatibility."""
        return {
            **self.entry.to_dict(),
            "history": self.history,
        }


class SessionManager:
    """Manages sessions across all channels using JSONL transcripts."""

    def __init__(self, store_path: Path | None = None):
        self.store_path = store_path or DATA_DIR / "sessions"
        self.store_path.mkdir(parents=True, exist_ok=True)
        self._index_file = self.store_path / "sessions.json"
        self._sessions: dict[str, Session] = {}
        self._entries: dict[str, SessionEntry] = {}
        self._load_index()

    def _load_index(self) -> None:
        """Load session index from sessions.json."""
        if not self._index_file.exists():
            return

        try:
            data = json.loads(self._index_file.read_text())
            for key, entry_data in data.items():
                try:
                    entry = SessionEntry.from_dict(entry_data)
                    self._entries[key] = entry
                except Exception as e:
                    logger.warning(f"Failed to load session entry {key}: {e}")
        except Exception as e:
            logger.error(f"Failed to load session index: {e}")

    def _save_index(self) -> None:
        """Save session index to sessions.json."""
        try:
            data = {key: entry.to_dict() for key, entry in self._entries.items()}
            self._index_file.write_text(json.dumps(data, indent=2, ensure_ascii=False))
        except Exception as e:
            logger.error(f"Failed to save session index: {e}")

    def _transcript_path(self, session_id: str, thread_id: str | None = None) -> Path:
        """Get transcript file path."""
        if thread_id:
            safe_thread = str(thread_id).replace("/", "_").replace(":", "_")
            filename = f"{session_id}-thread-{safe_thread}.jsonl"
        else:
            filename = f"{session_id}.jsonl"
        return self.store_path / filename

    def _get_or_create_session(
        self,
        channel: ChannelType,
        recipient_id: str,
        create_if_missing: bool = True,
    ) -> Session | None:
        """Get or create a session."""
        session_key = Session.create_key(channel, recipient_id)

        # Check cache first
        if session_key in self._sessions:
            return self._sessions[session_key]

        # Check index
        if session_key in self._entries:
            entry = self._entries[session_key]
            transcript_path = Path(entry.transcript_file)
            if not transcript_path.is_absolute():
                transcript_path = self.store_path / transcript_path
            transcript = SessionTranscript(transcript_path, entry.session_id)
            session = Session(entry=entry, transcript=transcript)
            self._sessions[session_key] = session
            return session

        # Create new
        if create_if_missing:
            session_id = str(uuid.uuid4())
            transcript_path = self._transcript_path(session_id)
            transcript = SessionTranscript(transcript_path, session_id)

            entry = SessionEntry(
                session_id=session_id,
                session_key=session_key,
                channel=channel,
                recipient_id=recipient_id,
                transcript_file=str(transcript_path.relative_to(self.store_path)),
                created_at=time.time(),
                updated_at=time.time(),
            )

            session = Session(entry=entry, transcript=transcript)
            self._sessions[session_key] = session
            self._entries[session_key] = entry
            self._save_index()
            return session

        return None

    def get(
        self,
        channel: ChannelType,
        recipient_id: str,
        create_if_missing: bool = True,
    ) -> Session | None:
        """Get or create a session."""
        return self._get_or_create_session(channel, recipient_id, create_if_missing)

    def get_by_key(self, session_key: str) -> Session | None:
        """Get a session by its key."""
        if session_key in self._sessions:
            return self._sessions[session_key]

        if session_key in self._entries:
            entry = self._entries[session_key]
            return self.get(entry.channel, entry.recipient_id, create_if_missing=False)

        return None

    def update(self, session: Session) -> None:
        """Update a session."""
        session.touch()
        self._sessions[session.session_key] = session
        self._entries[session.session_key] = session.entry
        self._save_index()

    def delete(self, session_key: str) -> bool:
        """Delete a session."""
        if session_key not in self._entries:
            return False

        entry = self._entries[session_key]

        # Delete transcript file
        transcript_path = self.store_path / entry.transcript_file
        if transcript_path.exists():
            transcript_path.unlink()

        # Remove from caches
        self._sessions.pop(session_key, None)
        del self._entries[session_key]
        self._save_index()

        return True

    def list_sessions(
        self,
        channel: ChannelType | None = None,
    ) -> list[Session]:
        """List all sessions, optionally filtered by channel."""
        sessions = []
        for key, entry in self._entries.items():
            if channel and entry.channel != channel:
                continue
            session = self.get_by_key(key)
            if session:
                sessions.append(session)
        return sorted(sessions, key=lambda s: s.entry.updated_at, reverse=True)

    def get_active_delivery_contexts(
        self,
        channel: ChannelType | None = None,
    ) -> list[DeliveryContext]:
        """Get all active delivery contexts for broadcasting."""
        contexts = []
        for session in self.list_sessions(channel):
            if session.delivery_context:
                contexts.append(session.delivery_context)
            else:
                contexts.append(
                    DeliveryContext(
                        channel=session.channel,
                        recipient_id=session.recipient_id,
                    )
                )
        return contexts


# Global session manager instance
_session_manager: SessionManager | None = None


def get_session_manager() -> SessionManager:
    """Get the global session manager instance."""
    global _session_manager
    if _session_manager is None:
        _session_manager = SessionManager()
    return _session_manager


def record_inbound_session(
    channel: ChannelType,
    recipient_id: str,
    lane: CommandLane = CommandLane.MAIN,
    delivery_context: DeliveryContext | None = None,
) -> Session:
    """Record an inbound message session."""
    manager = get_session_manager()
    session = manager.get(channel, recipient_id, create_if_missing=True)

    if session:
        session.last_lane = lane
        if delivery_context:
            session.delivery_context = delivery_context
        manager.update(session)

    return session
