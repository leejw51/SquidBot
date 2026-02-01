"""
Channel Abstraction - Unified interface for messaging platforms.

Provides a common interface for sending messages to different channels
(Telegram, WhatsApp, Discord, etc.).
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from session import ChannelType, DeliveryContext

logger = logging.getLogger(__name__)


@dataclass
class MessagePayload:
    """Unified message payload for all channels."""

    text: str
    media_paths: list[str] | None = None  # Paths to images/files
    reply_to_id: str | None = None
    metadata: dict[str, Any] | None = None


class ChannelAdapter(ABC):
    """Abstract base class for channel adapters."""

    channel_type: ChannelType

    @abstractmethod
    async def send_message(
        self,
        context: DeliveryContext,
        payload: MessagePayload,
    ) -> bool:
        """Send a message to the channel. Returns True on success."""
        pass

    @abstractmethod
    async def send_typing(self, context: DeliveryContext) -> None:
        """Send typing indicator to the channel."""
        pass

    def supports_media(self) -> bool:
        """Whether this channel supports media attachments."""
        return self.channel_type.supports_media

    def max_message_length(self) -> int:
        """Maximum message length for this channel."""
        return self.channel_type.max_message_length

    def split_message(self, text: str) -> list[str]:
        """Split a long message into chunks that fit the channel limit."""
        max_len = self.max_message_length()
        if max_len == 0 or len(text) <= max_len:
            return [text]

        chunks = []
        while text:
            if len(text) <= max_len:
                chunks.append(text)
                break
            # Try to split at newline
            split_idx = text.rfind("\n", 0, max_len)
            if split_idx == -1 or split_idx < max_len // 2:
                # No good newline, split at max length
                split_idx = max_len
            chunks.append(text[:split_idx])
            text = text[split_idx:].lstrip("\n")
        return chunks


class TelegramAdapter(ChannelAdapter):
    """Telegram channel adapter."""

    channel_type = ChannelType.TELEGRAM

    def __init__(self, bot: Any):
        self.bot = bot

    async def send_message(
        self,
        context: DeliveryContext,
        payload: MessagePayload,
    ) -> bool:
        try:
            chat_id = int(context.recipient_id)

            # Send text in chunks if needed
            for chunk in self.split_message(payload.text):
                await self.bot.send_message(chat_id=chat_id, text=chunk)

            # Send media if any
            if payload.media_paths:
                import os

                for path in payload.media_paths:
                    if os.path.exists(path):
                        with open(path, "rb") as f:
                            await self.bot.send_photo(chat_id=chat_id, photo=f)

            return True
        except Exception as e:
            logger.error(f"Failed to send Telegram message: {e}")
            return False

    async def send_typing(self, context: DeliveryContext) -> None:
        try:
            chat_id = int(context.recipient_id)
            await self.bot.send_chat_action(chat_id=chat_id, action="typing")
        except Exception as e:
            logger.warning(f"Failed to send typing indicator: {e}")


class TCPAdapter(ChannelAdapter):
    """TCP client channel adapter."""

    channel_type = ChannelType.TCP

    def __init__(
        self,
        get_writer: Callable[[str], asyncio.StreamWriter | None],
    ):
        self._get_writer = get_writer

    async def send_message(
        self,
        context: DeliveryContext,
        payload: MessagePayload,
    ) -> bool:
        import json

        writer = self._get_writer(context.recipient_id)
        if not writer:
            return False

        try:
            notification = {"status": "notification", "response": payload.text}
            data = json.dumps(notification) + "\n"
            writer.write(data.encode())
            await writer.drain()
            return True
        except Exception as e:
            logger.error(f"Failed to send TCP message: {e}")
            return False

    async def send_typing(self, context: DeliveryContext) -> None:
        # TCP clients don't support typing indicators
        pass


class WhatsAppAdapter(ChannelAdapter):
    """WhatsApp channel adapter (placeholder for future implementation)."""

    channel_type = ChannelType.WHATSAPP

    def __init__(self, client: Any = None):
        self.client = client

    async def send_message(
        self,
        context: DeliveryContext,
        payload: MessagePayload,
    ) -> bool:
        # TODO: Implement WhatsApp sending via WhatsApp Business API
        logger.warning("WhatsApp adapter not yet implemented")
        return False

    async def send_typing(self, context: DeliveryContext) -> None:
        # TODO: Implement WhatsApp typing indicator
        pass


class DiscordAdapter(ChannelAdapter):
    """Discord channel adapter (placeholder for future implementation)."""

    channel_type = ChannelType.DISCORD

    def __init__(self, client: Any = None):
        self.client = client

    async def send_message(
        self,
        context: DeliveryContext,
        payload: MessagePayload,
    ) -> bool:
        # TODO: Implement Discord sending via Discord.py
        logger.warning("Discord adapter not yet implemented")
        return False

    async def send_typing(self, context: DeliveryContext) -> None:
        # TODO: Implement Discord typing indicator
        pass


class SlackAdapter(ChannelAdapter):
    """Slack channel adapter (placeholder for future implementation)."""

    channel_type = ChannelType.SLACK

    def __init__(self, client: Any = None):
        self.client = client

    async def send_message(
        self,
        context: DeliveryContext,
        payload: MessagePayload,
    ) -> bool:
        # TODO: Implement Slack sending via Slack SDK
        logger.warning("Slack adapter not yet implemented")
        return False

    async def send_typing(self, context: DeliveryContext) -> None:
        # TODO: Implement Slack typing indicator
        pass


class ChannelRouter:
    """Routes messages to the appropriate channel adapter."""

    def __init__(self):
        self._adapters: dict[ChannelType, ChannelAdapter] = {}

    def register(self, adapter: ChannelAdapter) -> None:
        """Register a channel adapter."""
        self._adapters[adapter.channel_type] = adapter
        logger.info(f"Registered channel adapter: {adapter.channel_type}")

    def get_adapter(self, channel: ChannelType) -> ChannelAdapter | None:
        """Get the adapter for a channel type."""
        return self._adapters.get(channel)

    async def send(
        self,
        context: DeliveryContext,
        payload: MessagePayload,
    ) -> bool:
        """Send a message via the appropriate channel."""
        adapter = self.get_adapter(context.channel)
        if not adapter:
            logger.error(f"No adapter registered for channel: {context.channel}")
            return False
        return await adapter.send_message(context, payload)

    async def broadcast(
        self,
        contexts: list[DeliveryContext],
        payload: MessagePayload,
    ) -> dict[str, bool]:
        """Broadcast a message to multiple contexts."""
        results = {}
        for ctx in contexts:
            key = f"{ctx.channel}:{ctx.recipient_id}"
            results[key] = await self.send(ctx, payload)
        return results


# Global channel router instance
_channel_router: ChannelRouter | None = None


def get_channel_router() -> ChannelRouter:
    """Get the global channel router instance."""
    global _channel_router
    if _channel_router is None:
        _channel_router = ChannelRouter()
    return _channel_router
