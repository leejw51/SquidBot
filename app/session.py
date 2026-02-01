"""
Session Management - Channel-agnostic session handling.

Supports multiple channels: Telegram, WhatsApp, Discord, TCP, etc.
Designed for easy extension to new messaging platforms.
"""

import json
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from config import DATA_DIR
from lanes import CommandLane

logger = logging.getLogger(__name__)


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
class Session:
    """Session representing a conversation context."""

    session_key: str  # Unique session identifier
    channel: ChannelType
    recipient_id: str  # Primary recipient (chat/user ID)
    history: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    last_lane: CommandLane = CommandLane.MAIN
    delivery_context: DeliveryContext | None = None

    @classmethod
    def create_key(cls, channel: ChannelType, recipient_id: str) -> str:
        """Generate a unique session key."""
        return f"{channel}:{recipient_id}"

    @classmethod
    def create(
        cls,
        channel: ChannelType,
        recipient_id: str,
        **kwargs: Any,
    ) -> "Session":
        """Create a new session."""
        session_key = cls.create_key(channel, recipient_id)
        return cls(
            session_key=session_key,
            channel=channel,
            recipient_id=recipient_id,
            **kwargs,
        )

    def touch(self) -> None:
        """Update the session timestamp."""
        self.updated_at = time.time()

    def add_message(self, role: str, content: str) -> None:
        """Add a message to history."""
        self.history.append({"role": role, "content": content})
        self.touch()

    def clear_history(self) -> None:
        """Clear conversation history."""
        self.history = []
        self.touch()

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_key": self.session_key,
            "channel": str(self.channel),
            "recipient_id": self.recipient_id,
            "history": self.history,
            "metadata": self.metadata,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "last_lane": str(self.last_lane),
            "delivery_context": (
                self.delivery_context.to_dict() if self.delivery_context else None
            ),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Session":
        delivery_ctx = data.get("delivery_context")
        return cls(
            session_key=data["session_key"],
            channel=ChannelType(data["channel"]),
            recipient_id=data["recipient_id"],
            history=data.get("history", []),
            metadata=data.get("metadata", {}),
            created_at=data.get("created_at", time.time()),
            updated_at=data.get("updated_at", time.time()),
            last_lane=CommandLane(data.get("last_lane", "main")),
            delivery_context=(
                DeliveryContext.from_dict(delivery_ctx) if delivery_ctx else None
            ),
        )


class SessionManager:
    """Manages sessions across all channels."""

    def __init__(self, store_path: Path | None = None):
        self.store_path = store_path or DATA_DIR / "sessions"
        self.store_path.mkdir(parents=True, exist_ok=True)
        self._sessions: dict[str, Session] = {}
        self._load_sessions()

    def _session_file(self, session_key: str) -> Path:
        """Get the file path for a session."""
        safe_key = session_key.replace(":", "_").replace("/", "_")
        return self.store_path / f"{safe_key}.json"

    def _load_sessions(self) -> None:
        """Load all sessions from disk."""
        for path in self.store_path.glob("*.json"):
            try:
                data = json.loads(path.read_text())
                session = Session.from_dict(data)
                self._sessions[session.session_key] = session
            except Exception as e:
                logger.warning(f"Failed to load session {path}: {e}")

    def _save_session(self, session: Session) -> None:
        """Save a session to disk."""
        try:
            path = self._session_file(session.session_key)
            path.write_text(json.dumps(session.to_dict(), indent=2))
        except Exception as e:
            logger.error(f"Failed to save session {session.session_key}: {e}")

    def get(
        self,
        channel: ChannelType,
        recipient_id: str,
        create_if_missing: bool = True,
    ) -> Session | None:
        """Get or create a session."""
        session_key = Session.create_key(channel, recipient_id)

        if session_key in self._sessions:
            return self._sessions[session_key]

        if create_if_missing:
            session = Session.create(channel, recipient_id)
            self._sessions[session_key] = session
            self._save_session(session)
            return session

        return None

    def get_by_key(self, session_key: str) -> Session | None:
        """Get a session by its key."""
        return self._sessions.get(session_key)

    def update(self, session: Session) -> None:
        """Update a session."""
        session.touch()
        self._sessions[session.session_key] = session
        self._save_session(session)

    def delete(self, session_key: str) -> bool:
        """Delete a session."""
        if session_key in self._sessions:
            del self._sessions[session_key]
            path = self._session_file(session_key)
            if path.exists():
                path.unlink()
            return True
        return False

    def list_sessions(
        self,
        channel: ChannelType | None = None,
    ) -> list[Session]:
        """List all sessions, optionally filtered by channel."""
        sessions = list(self._sessions.values())
        if channel:
            sessions = [s for s in sessions if s.channel == channel]
        return sorted(sessions, key=lambda s: s.updated_at, reverse=True)

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
                # Create basic context from session
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
