"""
SquidBot Plugin System

Provides a modular plugin architecture for extending SquidBot functionality.
"""

from .base import Plugin, PluginApi, PluginManifest
from .hooks import AfterToolCallEvent  # Event types; Global instances
from .hooks import (AgentEndEvent, BeforeAgentStartEvent,
                    BeforeAgentStartResult, BeforeToolCallEvent,
                    BeforeToolCallResult, HookContext, HookName, HookRegistry,
                    HookRunner, MessageReceivedEvent, MessageSendingEvent,
                    MessageSendingResult, MessageSentEvent, SessionEndEvent,
                    SessionStartEvent, get_hook_registry, get_hook_runner)
from .loader import (PluginRegistry, get_registry, load_builtin_plugins,
                     load_external_plugins)

__all__ = [
    # Base
    "Plugin",
    "PluginApi",
    "PluginManifest",
    # Hooks
    "HookName",
    "HookContext",
    "HookRegistry",
    "HookRunner",
    "BeforeAgentStartEvent",
    "BeforeAgentStartResult",
    "AgentEndEvent",
    "MessageReceivedEvent",
    "MessageSendingEvent",
    "MessageSendingResult",
    "MessageSentEvent",
    "BeforeToolCallEvent",
    "BeforeToolCallResult",
    "AfterToolCallEvent",
    "SessionStartEvent",
    "SessionEndEvent",
    "get_hook_registry",
    "get_hook_runner",
    # Loader
    "PluginRegistry",
    "get_registry",
    "load_builtin_plugins",
    "load_external_plugins",
]
