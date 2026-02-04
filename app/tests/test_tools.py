"""Tests for individual tools."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from squidbot.tools.cron import CronCreateTool, CronDeleteTool, CronListTool
from squidbot.tools.memory_tool import (MemoryAddTool, MemoryListTool,
                                        MemorySearchTool)
from squidbot.tools.web_search import WebSearchTool


class TestMemoryTools:
    """Test memory tools."""

    @pytest.mark.asyncio
    async def test_memory_add_tool(self):
        """Test MemoryAddTool."""
        tool = MemoryAddTool()

        assert tool.name == "memory_add"
        assert "memory" in tool.description.lower()

        result = await tool.execute(content="Test content", category="test")
        assert "Stored" in result
        assert "Test content" in result

    @pytest.mark.asyncio
    async def test_memory_search_tool(self):
        """Test MemorySearchTool."""
        # First add something
        add_tool = MemoryAddTool()
        await add_tool.execute(content="Python is great")

        # Then search
        tool = MemorySearchTool()
        result = await tool.execute(query="Python")
        assert "Python" in result

    @pytest.mark.asyncio
    async def test_memory_search_no_results(self):
        """Test MemorySearchTool with no results."""
        tool = MemorySearchTool()
        result = await tool.execute(query="nonexistent")
        assert "No memory entries found" in result

    @pytest.mark.asyncio
    async def test_memory_list_tool_empty(self):
        """Test MemoryListTool when empty."""
        tool = MemoryListTool()
        result = await tool.execute()
        assert "No memories" in result

    @pytest.mark.asyncio
    async def test_memory_list_tool(self):
        """Test MemoryListTool."""
        # Add some memories
        add_tool = MemoryAddTool()
        await add_tool.execute(content="Memory 1")
        await add_tool.execute(content="Memory 2")

        tool = MemoryListTool()
        result = await tool.execute()
        assert "Memory 1" in result
        assert "Memory 2" in result


class TestWebSearchTool:
    """Test web search tool."""

    def test_tool_properties(self):
        """Test WebSearchTool properties."""
        tool = WebSearchTool()
        assert tool.name == "web_search"
        assert "search" in tool.description.lower()
        assert "query" in tool.parameters["properties"]

    @pytest.mark.asyncio
    async def test_web_search_mock(self):
        """Test WebSearchTool with mocked DuckDuckGo."""
        tool = WebSearchTool()

        mock_results = [
            {
                "title": "Result 1",
                "href": "https://example.com/1",
                "body": "Description 1",
            },
            {
                "title": "Result 2",
                "href": "https://example.com/2",
                "body": "Description 2",
            },
        ]

        with patch("squidbot.tools.web_search.DDGS") as mock_ddgs:
            mock_instance = MagicMock()
            mock_instance.__enter__ = MagicMock(return_value=mock_instance)
            mock_instance.__exit__ = MagicMock(return_value=False)
            mock_instance.text = MagicMock(return_value=mock_results)
            mock_ddgs.return_value = mock_instance

            result = await tool.execute(query="python tutorials")

            assert "Result 1" in result
            assert "Result 2" in result
            assert "https://example.com" in result

    @pytest.mark.asyncio
    async def test_web_search_no_results(self):
        """Test WebSearchTool with no results."""
        tool = WebSearchTool()

        with patch("squidbot.tools.web_search.DDGS") as mock_ddgs:
            mock_instance = MagicMock()
            mock_instance.__enter__ = MagicMock(return_value=mock_instance)
            mock_instance.__exit__ = MagicMock(return_value=False)
            mock_instance.text = MagicMock(return_value=[])
            mock_ddgs.return_value = mock_instance

            result = await tool.execute(query="xyznonexistent123")

            assert "No results" in result

    @pytest.mark.asyncio
    async def test_web_search_error(self):
        """Test WebSearchTool error handling."""
        tool = WebSearchTool()

        with patch("squidbot.tools.web_search.DDGS") as mock_ddgs:
            mock_ddgs.side_effect = Exception("Network error")

            result = await tool.execute(query="test")

            assert "error" in result.lower()


class TestCronTools:
    """Test cron/scheduling tools."""

    @pytest.mark.asyncio
    async def test_cron_create_one_time(self):
        """Test creating a one-time reminder."""
        tool = CronCreateTool()

        result = await tool.execute(message="Check emails", delay_minutes=10)

        assert "Reminder set" in result
        assert "10 minutes" in result

    @pytest.mark.asyncio
    async def test_cron_create_recurring(self):
        """Test creating a recurring task."""
        tool = CronCreateTool()

        result = await tool.execute(
            message="Daily standup", cron_expression="0 9 * * *", recurring=True
        )

        assert "Recurring task" in result
        assert "0 9 * * *" in result

    @pytest.mark.asyncio
    async def test_cron_create_missing_schedule(self):
        """Test creating a cron job without schedule."""
        tool = CronCreateTool()

        result = await tool.execute(message="No schedule")

        assert "Error" in result

    @pytest.mark.asyncio
    async def test_cron_list_empty(self):
        """Test listing when no jobs exist."""
        tool = CronListTool()

        result = await tool.execute()

        assert "No scheduled tasks" in result

    @pytest.mark.asyncio
    async def test_cron_list(self):
        """Test listing scheduled tasks."""
        # Create some jobs
        create_tool = CronCreateTool()
        await create_tool.execute(message="Job 1", delay_minutes=5)
        await create_tool.execute(message="Job 2", cron_expression="0 8 * * *")

        list_tool = CronListTool()
        result = await list_tool.execute()

        assert "Job 1" in result
        assert "Job 2" in result

    @pytest.mark.asyncio
    async def test_cron_delete(self):
        """Test deleting a scheduled task."""
        # Create a job
        create_tool = CronCreateTool()
        await create_tool.execute(message="To delete", delay_minutes=5)

        # Delete it
        delete_tool = CronDeleteTool()
        result = await delete_tool.execute(job_id=1)

        assert "Deleted" in result

        # Verify it's gone
        list_tool = CronListTool()
        list_result = await list_tool.execute()
        assert "To delete" not in list_result

    @pytest.mark.asyncio
    async def test_cron_delete_nonexistent(self):
        """Test deleting a nonexistent job."""
        tool = CronDeleteTool()

        result = await tool.execute(job_id=999)

        assert "No job found" in result
