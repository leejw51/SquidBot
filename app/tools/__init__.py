"""Tool registry - all available tools for the agent."""

from tools.base import Tool
from tools.browser import (BrowserClickTool, BrowserGetTextTool,
                           BrowserNavigateTool, BrowserScreenshotTool,
                           BrowserSnapshotTool, BrowserTypeTool)
from tools.cron import (CronClearTool, CronCreateTool, CronDeleteTool,
                        CronListTool)
from tools.memory_tool import (MemoryAddTool, MemoryDeleteTool, MemoryListTool,
                               MemorySearchTool)
from tools.web_search import WebSearchTool

# All available tools
ALL_TOOLS: list[Tool] = [
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
]


def get_tool_by_name(name: str) -> Tool | None:
    """Get a tool by its name."""
    for tool in ALL_TOOLS:
        if tool.name == name:
            return tool
    return None


def get_openai_tools() -> list[dict]:
    """Get all tools in OpenAI format."""
    return [tool.to_openai_tool() for tool in ALL_TOOLS]
