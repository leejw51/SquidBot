"""
Plugin Base Classes

Defines the plugin interface and base classes for SquidBot plugins.
Inspired by OpenClaw's plugin architecture.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Awaitable, Callable

from tools.base import Tool

if TYPE_CHECKING:
    from plugins.hooks import HookName, HookRegistry


@dataclass
class PluginManifest:
    """Plugin metadata and configuration."""

    id: str
    name: str
    description: str
    version: str = "1.0.0"
    author: str = ""
    config_schema: dict = field(default_factory=dict)


class PluginApi:
    """API provided to plugins for registration."""

    def __init__(self, plugin_id: str, hook_registry: "HookRegistry"):
        self._plugin_id = plugin_id
        self._hook_registry = hook_registry

    def on(
        self,
        hook_name: "HookName",
        handler: Callable[..., Awaitable[Any] | Any],
        priority: int = 0,
    ) -> None:
        """Register a hook handler.

        Args:
            hook_name: The hook to listen for
            handler: Async or sync function(event, context) -> result
            priority: Higher priority handlers run first (default: 0)
        """
        self._hook_registry.register(
            plugin_id=self._plugin_id,
            hook_name=hook_name,
            handler=handler,
            priority=priority,
        )


class Plugin(ABC):
    """Base class for all plugins."""

    @property
    @abstractmethod
    def manifest(self) -> PluginManifest:
        """Return plugin manifest with metadata."""
        pass

    @abstractmethod
    def get_tools(self) -> list[Tool]:
        """Return list of tools provided by this plugin."""
        pass

    def register_hooks(self, api: PluginApi) -> None:
        """Register hooks using the plugin API. Override to add hooks.

        Example:
            def register_hooks(self, api: PluginApi) -> None:
                api.on(HookName.BEFORE_TOOL_CALL, self.on_before_tool, priority=10)
                api.on(HookName.AFTER_TOOL_CALL, self.on_after_tool)
        """
        pass

    def activate(self) -> None:
        """Called when plugin is activated. Override for initialization."""
        pass

    def deactivate(self) -> None:
        """Called when plugin is deactivated. Override for cleanup."""
        pass

    def validate_config(self, config: dict) -> tuple[bool, str | None]:
        """Validate plugin configuration. Returns (is_valid, error_message)."""
        return True, None

    def get_config_defaults(self) -> dict[str, Any]:
        """Return default configuration values."""
        return {}
