"""Tool registry - all available tools for the agent."""

import logging

from .base import Tool
from .browser import (BrowserClickTool, BrowserGetTextTool,
                      BrowserNavigateTool, BrowserScreenshotTool,
                      BrowserSnapshotTool, BrowserTypeTool)
from .coding import get_coding_tools
from .cron import CronClearTool, CronCreateTool, CronDeleteTool, CronListTool
from .memory_tool import (MemoryAddTool, MemoryDeleteTool, MemoryListTool,
                          MemorySearchTool)
from .web_search import WebSearchTool

logger = logging.getLogger(__name__)

# Core tools (always available)
CORE_TOOLS: list[Tool] = [
    # Memory (SQLite + vector search)
    MemoryAddTool(),
    MemorySearchTool(),
    MemoryListTool(),
    MemoryDeleteTool(),
    # Web search
    WebSearchTool(),
    # Browser
    BrowserNavigateTool(),
    BrowserScreenshotTool(),
    BrowserSnapshotTool(),
    BrowserClickTool(),
    BrowserTypeTool(),
    BrowserGetTextTool(),
    # Scheduling
    CronCreateTool(),
    CronListTool(),
    CronDeleteTool(),
    CronClearTool(),
    # Coding (Zig + Python)
    *get_coding_tools(),
]

# Plugin tools (loaded dynamically)
_plugin_tools: list[Tool] = []
_plugins_loaded = False


def _load_plugins() -> None:
    """Load plugins and their tools."""
    global _plugin_tools, _plugins_loaded

    if _plugins_loaded:
        return

    try:
        from ..plugins import get_registry, load_builtin_plugins

        # Load all built-in plugins
        load_builtin_plugins()

        # Get tools from all plugins
        registry = get_registry()
        _plugin_tools = registry.get_all_tools()

        logger.info(f"Loaded {len(_plugin_tools)} tools from plugins")

    except Exception as e:
        logger.warning(f"Failed to load plugins: {e}")
        _plugin_tools = []

    _plugins_loaded = True


def get_all_tools() -> list[Tool]:
    """Get all tools including plugin tools."""
    _load_plugins()
    return CORE_TOOLS + _plugin_tools


# Legacy alias for backward compatibility
ALL_TOOLS = CORE_TOOLS  # Will be updated after first call to get_all_tools()


def get_tool_by_name(name: str) -> Tool | None:
    """Get a tool by its name."""
    for tool in get_all_tools():
        if tool.name == name:
            return tool
    return None


def get_openai_tools() -> list[dict]:
    """Get all tools in OpenAI format."""
    return [tool.to_openai_tool() for tool in get_all_tools()]


def reload_plugins() -> None:
    """Reload all plugins (useful for development)."""
    global _plugins_loaded
    _plugins_loaded = False
    _load_plugins()
