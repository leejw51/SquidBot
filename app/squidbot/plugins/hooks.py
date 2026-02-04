"""
Plugin Hooks System

Provides lifecycle hooks for plugins to intercept and modify behavior.
Inspired by OpenClaw's hook architecture.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Awaitable, Callable

logger = logging.getLogger(__name__)


class HookName(str, Enum):
    """Available hook types."""

    # Agent lifecycle hooks
    BEFORE_AGENT_START = "before_agent_start"
    AGENT_END = "agent_end"

    # Message hooks
    MESSAGE_RECEIVED = "message_received"
    MESSAGE_SENDING = "message_sending"
    MESSAGE_SENT = "message_sent"

    # Tool hooks
    BEFORE_TOOL_CALL = "before_tool_call"
    AFTER_TOOL_CALL = "after_tool_call"

    # Session hooks
    SESSION_START = "session_start"
    SESSION_END = "session_end"


# ============================================================
# Hook Event/Context/Result Types
# ============================================================


@dataclass
class BeforeAgentStartEvent:
    """Event for before_agent_start hook."""

    prompt: str
    messages: list[dict] = field(default_factory=list)
    session_id: str | None = None


@dataclass
class BeforeAgentStartResult:
    """Result from before_agent_start hook."""

    system_prompt: str | None = None  # Override system prompt
    prepend_context: str | None = None  # Prepend to context


@dataclass
class AgentEndEvent:
    """Event for agent_end hook."""

    messages: list[dict]
    success: bool
    response: str = ""
    error: str | None = None
    duration_ms: float | None = None


@dataclass
class MessageReceivedEvent:
    """Event for message_received hook."""

    sender: str
    content: str
    channel: str
    metadata: dict = field(default_factory=dict)


@dataclass
class MessageSendingEvent:
    """Event for message_sending hook."""

    recipient: str
    content: str
    channel: str
    metadata: dict = field(default_factory=dict)


@dataclass
class MessageSendingResult:
    """Result from message_sending hook."""

    content: str | None = None  # Modified content
    cancel: bool = False  # Prevent sending


@dataclass
class MessageSentEvent:
    """Event for message_sent hook."""

    recipient: str
    content: str
    channel: str
    success: bool
    error: str | None = None


@dataclass
class BeforeToolCallEvent:
    """Event for before_tool_call hook."""

    tool_name: str
    params: dict = field(default_factory=dict)


@dataclass
class BeforeToolCallResult:
    """Result from before_tool_call hook."""

    params: dict | None = None  # Modified params
    block: bool = False  # Prevent tool call
    block_reason: str | None = None


@dataclass
class AfterToolCallEvent:
    """Event for after_tool_call hook."""

    tool_name: str
    params: dict
    result: Any = None
    error: str | None = None
    duration_ms: float | None = None


@dataclass
class SessionStartEvent:
    """Event for session_start hook."""

    session_id: str
    channel: str
    user_id: str | None = None


@dataclass
class SessionEndEvent:
    """Event for session_end hook."""

    session_id: str
    message_count: int
    duration_ms: float | None = None


@dataclass
class HookContext:
    """Context passed to all hooks."""

    plugin_id: str
    session_id: str | None = None
    channel: str | None = None
    metadata: dict = field(default_factory=dict)


# ============================================================
# Hook Registration
# ============================================================


@dataclass
class HookRegistration:
    """A registered hook handler."""

    plugin_id: str
    hook_name: HookName
    handler: Callable[..., Awaitable[Any] | Any]
    priority: int = 0  # Higher = runs first


class HookRegistry:
    """Registry for all hook handlers."""

    def __init__(self):
        self._hooks: list[HookRegistration] = []

    def register(
        self,
        plugin_id: str,
        hook_name: HookName,
        handler: Callable,
        priority: int = 0,
    ) -> None:
        """Register a hook handler."""
        self._hooks.append(
            HookRegistration(
                plugin_id=plugin_id,
                hook_name=hook_name,
                handler=handler,
                priority=priority,
            )
        )
        logger.debug(
            f"Registered hook {hook_name.value} from plugin {plugin_id} (priority={priority})"
        )

    def unregister(self, plugin_id: str) -> int:
        """Unregister all hooks for a plugin. Returns count removed."""
        before = len(self._hooks)
        self._hooks = [h for h in self._hooks if h.plugin_id != plugin_id]
        return before - len(self._hooks)

    def get_hooks(self, hook_name: HookName) -> list[HookRegistration]:
        """Get all hooks for a given hook name, sorted by priority (highest first)."""
        return sorted(
            [h for h in self._hooks if h.hook_name == hook_name],
            key=lambda h: h.priority,
            reverse=True,
        )

    def has_hooks(self, hook_name: HookName) -> bool:
        """Check if any hooks are registered for a hook name."""
        return any(h.hook_name == hook_name for h in self._hooks)

    def get_hook_count(self, hook_name: HookName) -> int:
        """Get count of hooks for a hook name."""
        return sum(1 for h in self._hooks if h.hook_name == hook_name)

    def list_all(self) -> list[dict]:
        """List all registered hooks."""
        return [
            {
                "plugin_id": h.plugin_id,
                "hook_name": h.hook_name.value,
                "priority": h.priority,
            }
            for h in self._hooks
        ]


# ============================================================
# Hook Runner
# ============================================================


class HookRunner:
    """Executes hooks with proper ordering and error handling."""

    def __init__(self, registry: HookRegistry, catch_errors: bool = True):
        self._registry = registry
        self._catch_errors = catch_errors

    async def _run_handler(
        self, hook: HookRegistration, event: Any, ctx: HookContext
    ) -> Any:
        """Run a single hook handler."""
        try:
            result = hook.handler(event, ctx)
            if asyncio.iscoroutine(result):
                result = await result
            return result
        except Exception as e:
            if self._catch_errors:
                logger.error(
                    f"Hook {hook.hook_name.value} from {hook.plugin_id} failed: {e}"
                )
                return None
            raise

    async def _run_void_hook(
        self, hook_name: HookName, event: Any, ctx: HookContext
    ) -> None:
        """Run a void hook (fire-and-forget, parallel execution)."""
        hooks = self._registry.get_hooks(hook_name)
        if not hooks:
            return

        tasks = [self._run_handler(hook, event, ctx) for hook in hooks]
        await asyncio.gather(*tasks, return_exceptions=self._catch_errors)

    async def _run_modifying_hook(
        self,
        hook_name: HookName,
        event: Any,
        ctx: HookContext,
        merge_fn: Callable[[Any, Any], Any] | None = None,
    ) -> Any:
        """Run a modifying hook (sequential, ordered by priority)."""
        hooks = self._registry.get_hooks(hook_name)
        if not hooks:
            return None

        result = None
        for hook in hooks:
            handler_result = await self._run_handler(hook, event, ctx)
            if handler_result is not None:
                if result is not None and merge_fn:
                    result = merge_fn(result, handler_result)
                else:
                    result = handler_result

        return result

    # ============================================================
    # Agent Hooks
    # ============================================================

    async def run_before_agent_start(
        self, event: BeforeAgentStartEvent, ctx: HookContext
    ) -> BeforeAgentStartResult | None:
        """Run before_agent_start hooks."""

        def merge(acc: BeforeAgentStartResult, next_: BeforeAgentStartResult):
            return BeforeAgentStartResult(
                system_prompt=next_.system_prompt or acc.system_prompt,
                prepend_context=(
                    f"{acc.prepend_context}\n\n{next_.prepend_context}"
                    if acc.prepend_context and next_.prepend_context
                    else (next_.prepend_context or acc.prepend_context)
                ),
            )

        return await self._run_modifying_hook(
            HookName.BEFORE_AGENT_START, event, ctx, merge
        )

    async def run_agent_end(self, event: AgentEndEvent, ctx: HookContext) -> None:
        """Run agent_end hooks."""
        await self._run_void_hook(HookName.AGENT_END, event, ctx)

    # ============================================================
    # Message Hooks
    # ============================================================

    async def run_message_received(
        self, event: MessageReceivedEvent, ctx: HookContext
    ) -> None:
        """Run message_received hooks."""
        await self._run_void_hook(HookName.MESSAGE_RECEIVED, event, ctx)

    async def run_message_sending(
        self, event: MessageSendingEvent, ctx: HookContext
    ) -> MessageSendingResult | None:
        """Run message_sending hooks."""

        def merge(acc: MessageSendingResult, next_: MessageSendingResult):
            return MessageSendingResult(
                content=next_.content or acc.content,
                cancel=next_.cancel or acc.cancel,
            )

        return await self._run_modifying_hook(
            HookName.MESSAGE_SENDING, event, ctx, merge
        )

    async def run_message_sent(self, event: MessageSentEvent, ctx: HookContext) -> None:
        """Run message_sent hooks."""
        await self._run_void_hook(HookName.MESSAGE_SENT, event, ctx)

    # ============================================================
    # Tool Hooks
    # ============================================================

    async def run_before_tool_call(
        self, event: BeforeToolCallEvent, ctx: HookContext
    ) -> BeforeToolCallResult | None:
        """Run before_tool_call hooks."""

        def merge(acc: BeforeToolCallResult, next_: BeforeToolCallResult):
            return BeforeToolCallResult(
                params=next_.params or acc.params,
                block=next_.block or acc.block,
                block_reason=next_.block_reason or acc.block_reason,
            )

        return await self._run_modifying_hook(
            HookName.BEFORE_TOOL_CALL, event, ctx, merge
        )

    async def run_after_tool_call(
        self, event: AfterToolCallEvent, ctx: HookContext
    ) -> None:
        """Run after_tool_call hooks."""
        await self._run_void_hook(HookName.AFTER_TOOL_CALL, event, ctx)

    # ============================================================
    # Session Hooks
    # ============================================================

    async def run_session_start(
        self, event: SessionStartEvent, ctx: HookContext
    ) -> None:
        """Run session_start hooks."""
        await self._run_void_hook(HookName.SESSION_START, event, ctx)

    async def run_session_end(self, event: SessionEndEvent, ctx: HookContext) -> None:
        """Run session_end hooks."""
        await self._run_void_hook(HookName.SESSION_END, event, ctx)


# ============================================================
# Global Instances
# ============================================================

_hook_registry = HookRegistry()
_hook_runner = HookRunner(_hook_registry)


def get_hook_registry() -> HookRegistry:
    """Get the global hook registry."""
    return _hook_registry


def get_hook_runner() -> HookRunner:
    """Get the global hook runner."""
    return _hook_runner
