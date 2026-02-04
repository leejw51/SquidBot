"""
Plugin Loader and Registry

Handles plugin discovery, loading, and lifecycle management.
"""

import importlib
import importlib.util
import logging
import pkgutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .base import Plugin

from ..tools.base import Tool

logger = logging.getLogger(__name__)


@dataclass
class PluginInfo:
    """Information about a loaded plugin."""

    plugin: "Plugin"
    enabled: bool = True
    load_error: str | None = None
    hook_count: int = 0


class PluginRegistry:
    """Central registry for all loaded plugins."""

    def __init__(self):
        self._plugins: dict[str, PluginInfo] = {}
        self._tool_cache: list[Tool] | None = None

    def register(self, plugin: "Plugin") -> bool:
        """Register a plugin. Returns True if successful."""
        from .base import PluginApi
        from .hooks import get_hook_registry

        try:
            manifest = plugin.manifest
            plugin_id = manifest.id

            if plugin_id in self._plugins:
                logger.warning(f"Plugin '{plugin_id}' already registered, skipping")
                return False

            # Create plugin API for hook registration
            hook_registry = get_hook_registry()
            api = PluginApi(plugin_id, hook_registry)

            # Register hooks first
            plugin.register_hooks(api)
            hook_count = (
                hook_registry.get_hook_count_for_plugin(plugin_id)
                if hasattr(hook_registry, "get_hook_count_for_plugin")
                else 0
            )

            # Then activate
            plugin.activate()

            self._plugins[plugin_id] = PluginInfo(
                plugin=plugin,
                enabled=True,
                hook_count=hook_count,
            )
            self._tool_cache = None  # Invalidate cache

            logger.info(f"Registered plugin: {manifest.name} v{manifest.version}")
            return True

        except Exception as e:
            logger.error(f"Failed to register plugin: {e}")
            return False

    def unregister(self, plugin_id: str) -> bool:
        """Unregister a plugin by ID."""
        from .hooks import get_hook_registry

        if plugin_id not in self._plugins:
            return False

        info = self._plugins[plugin_id]

        # Unregister hooks
        hook_registry = get_hook_registry()
        hook_registry.unregister(plugin_id)

        # Deactivate plugin
        try:
            info.plugin.deactivate()
        except Exception as e:
            logger.warning(f"Error deactivating plugin '{plugin_id}': {e}")

        del self._plugins[plugin_id]
        self._tool_cache = None
        return True

    def get_plugin(self, plugin_id: str) -> "Plugin | None":
        """Get a plugin by ID."""
        info = self._plugins.get(plugin_id)
        return info.plugin if info else None

    def get_all_plugins(self) -> list["Plugin"]:
        """Get all registered plugins."""
        return [info.plugin for info in self._plugins.values() if info.enabled]

    def get_all_tools(self) -> list[Tool]:
        """Get all tools from all enabled plugins."""
        if self._tool_cache is not None:
            return self._tool_cache

        tools = []
        for info in self._plugins.values():
            if info.enabled:
                try:
                    tools.extend(info.plugin.get_tools())
                except Exception as e:
                    logger.error(
                        f"Error getting tools from plugin '{info.plugin.manifest.id}': {e}"
                    )

        self._tool_cache = tools
        return tools

    def enable_plugin(self, plugin_id: str) -> bool:
        """Enable a plugin."""
        if plugin_id not in self._plugins:
            return False
        self._plugins[plugin_id].enabled = True
        self._tool_cache = None
        return True

    def disable_plugin(self, plugin_id: str) -> bool:
        """Disable a plugin."""
        if plugin_id not in self._plugins:
            return False
        self._plugins[plugin_id].enabled = False
        self._tool_cache = None
        return True

    def list_plugins(self) -> list[dict]:
        """List all plugins with their status."""
        from .hooks import get_hook_registry

        hook_registry = get_hook_registry()
        result = []

        for plugin_id, info in self._plugins.items():
            manifest = info.plugin.manifest

            # Count hooks for this plugin
            hooks = [h for h in hook_registry.list_all() if h["plugin_id"] == plugin_id]

            result.append(
                {
                    "id": plugin_id,
                    "name": manifest.name,
                    "version": manifest.version,
                    "description": manifest.description,
                    "enabled": info.enabled,
                    "tools": [t.name for t in info.plugin.get_tools()],
                    "hooks": [h["hook_name"] for h in hooks],
                }
            )
        return result


# Global registry instance
_registry = PluginRegistry()


def get_registry() -> PluginRegistry:
    """Get the global plugin registry."""
    return _registry


def load_builtin_plugins() -> None:
    """Load all built-in plugins from the plugins directory."""
    from .base import Plugin

    plugins_dir = Path(__file__).parent

    # Find all Python files in plugins directory (excluding base.py, loader.py, hooks.py, __init__.py)
    excluded = {"base", "loader", "hooks", "__init__"}

    for _, module_name, _ in pkgutil.iter_modules([str(plugins_dir)]):
        if module_name in excluded:
            continue

        try:
            module = importlib.import_module(
                f".{module_name}", package="squidbot.plugins"
            )

            # Look for get_plugin() function or Plugin subclass
            if hasattr(module, "get_plugin"):
                plugin = module.get_plugin()
                if isinstance(plugin, Plugin):
                    _registry.register(plugin)
            else:
                # Search for Plugin subclasses
                for attr_name in dir(module):
                    attr = getattr(module, attr_name)
                    if (
                        isinstance(attr, type)
                        and issubclass(attr, Plugin)
                        and attr is not Plugin
                    ):
                        try:
                            plugin = attr()
                            _registry.register(plugin)
                        except Exception as e:
                            logger.error(
                                f"Failed to instantiate plugin {attr_name}: {e}"
                            )

        except Exception as e:
            logger.error(f"Failed to load plugin module '{module_name}': {e}")


def load_external_plugins(plugins_dir: Path) -> None:
    """Load plugins from an external directory."""
    if not plugins_dir.exists():
        return

    for plugin_path in plugins_dir.glob("*.py"):
        if plugin_path.name.startswith("_"):
            continue

        try:
            spec = importlib.util.spec_from_file_location(plugin_path.stem, plugin_path)
            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)

                if hasattr(module, "get_plugin"):
                    plugin = module.get_plugin()
                    _registry.register(plugin)

        except Exception as e:
            logger.error(f"Failed to load external plugin '{plugin_path.name}': {e}")
