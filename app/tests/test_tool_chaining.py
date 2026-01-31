"""Tests for tool chaining (autonomous agent loop)."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent import execute_tool, run_agent
from tools import ALL_TOOLS, get_openai_tools, get_tool_by_name


class TestToolRegistry:
    """Test tool registry functions."""

    def test_get_all_tools(self):
        """Test that all tools are registered."""
        assert len(ALL_TOOLS) > 0
        tool_names = [t.name for t in ALL_TOOLS]
        assert "memory_add" in tool_names
        assert "web_search" in tool_names
        assert "browser_navigate" in tool_names
        assert "cron_create" in tool_names

    def test_get_tool_by_name(self):
        """Test getting a tool by name."""
        tool = get_tool_by_name("memory_add")
        assert tool is not None
        assert tool.name == "memory_add"

    def test_get_tool_by_name_not_found(self):
        """Test getting a non-existent tool."""
        tool = get_tool_by_name("nonexistent_tool")
        assert tool is None

    def test_get_openai_tools_format(self):
        """Test that tools are properly formatted for OpenAI."""
        tools = get_openai_tools()
        assert len(tools) > 0

        for tool in tools:
            assert tool["type"] == "function"
            assert "function" in tool
            assert "name" in tool["function"]
            assert "description" in tool["function"]
            assert "parameters" in tool["function"]


class TestExecuteTool:
    """Test individual tool execution."""

    @pytest.mark.asyncio
    async def test_execute_memory_add(self):
        """Test executing memory_add tool."""
        result = await execute_tool(
            "memory_add", {"content": "Test memory", "category": "test"}
        )
        assert "Stored in memory" in result
        assert "Test memory" in result

    @pytest.mark.asyncio
    async def test_execute_unknown_tool(self):
        """Test executing an unknown tool."""
        result = await execute_tool("unknown_tool", {})
        assert "Error" in result
        assert "Unknown tool" in result

    @pytest.mark.asyncio
    async def test_execute_tool_with_error(self):
        """Test tool execution error handling."""
        # Missing required argument
        result = await execute_tool("memory_add", {})
        assert "Error" in result


class TestAgentLoop:
    """Test the autonomous agent loop with tool chaining."""

    @pytest.mark.asyncio
    async def test_simple_response_no_tools(
        self, mock_openai_client, mock_openai_response
    ):
        """Test agent returning simple text without tools."""
        mock_openai_client.chat.completions.create = AsyncMock(
            return_value=mock_openai_response(content="Hello! How can I help?")
        )

        response = await run_agent("Hi there")
        assert response == "Hello! How can I help?"

    @pytest.mark.asyncio
    async def test_single_tool_call(
        self, mock_openai_client, mock_openai_response, mock_tool_call
    ):
        """Test agent making a single tool call."""
        # First response: tool call
        tool_call = mock_tool_call("memory_add", {"content": "Test fact"})
        first_response = mock_openai_response(content="", tool_calls=[tool_call])

        # Second response: final text
        second_response = mock_openai_response(content="I've remembered that for you!")

        mock_openai_client.chat.completions.create = AsyncMock(
            side_effect=[first_response, second_response]
        )

        response = await run_agent("Remember this: Test fact")

        assert response == "I've remembered that for you!"
        assert mock_openai_client.chat.completions.create.call_count == 2

    @pytest.mark.asyncio
    async def test_multiple_sequential_tool_calls(
        self, mock_openai_client, mock_openai_response, mock_tool_call
    ):
        """Test agent making multiple sequential tool calls (tool chaining)."""
        # First response: add to memory
        tool_call1 = mock_tool_call("memory_add", {"content": "User likes blue"})
        response1 = mock_openai_response(content="", tool_calls=[tool_call1])

        # Second response: search memory
        tool_call2 = mock_tool_call("memory_search", {"query": "blue"})
        response2 = mock_openai_response(content="", tool_calls=[tool_call2])

        # Third response: final text
        response3 = mock_openai_response(content="I found that you like blue!")

        mock_openai_client.chat.completions.create = AsyncMock(
            side_effect=[response1, response2, response3]
        )

        response = await run_agent("Remember I like blue, then search for it")

        assert "blue" in response.lower()
        assert mock_openai_client.chat.completions.create.call_count == 3

    @pytest.mark.asyncio
    async def test_parallel_tool_calls(
        self, mock_openai_client, mock_openai_response, mock_tool_call
    ):
        """Test agent making parallel tool calls in single response."""
        # Response with multiple tool calls (parallel)
        tool_call1 = mock_tool_call("memory_add", {"content": "Fact 1"})
        tool_call2 = mock_tool_call("memory_add", {"content": "Fact 2"})
        first_response = mock_openai_response(
            content="", tool_calls=[tool_call1, tool_call2]
        )

        # Final response
        second_response = mock_openai_response(content="Stored both facts!")

        mock_openai_client.chat.completions.create = AsyncMock(
            side_effect=[first_response, second_response]
        )

        response = await run_agent("Remember two facts")

        assert response == "Stored both facts!"
        # Only 2 LLM calls, but 2 tools executed in parallel
        assert mock_openai_client.chat.completions.create.call_count == 2

    @pytest.mark.asyncio
    async def test_max_iterations_limit(
        self, mock_openai_client, mock_openai_response, mock_tool_call
    ):
        """Test that agent respects max iterations limit."""
        # Always return a tool call (infinite loop scenario)
        tool_call = mock_tool_call("memory_list", {})
        infinite_response = mock_openai_response(content="", tool_calls=[tool_call])

        mock_openai_client.chat.completions.create = AsyncMock(
            return_value=infinite_response
        )

        response = await run_agent("Do something", max_iterations=3)

        # Should stop after max_iterations
        assert mock_openai_client.chat.completions.create.call_count == 3
        assert "maximum" in response.lower()


class TestToolChainScenarios:
    """Test realistic tool chaining scenarios."""

    @pytest.mark.asyncio
    async def test_memory_workflow(self):
        """Test a complete memory workflow using actual tools."""
        # Add memory
        result1 = await execute_tool(
            "memory_add", {"content": "User's name is Alice", "category": "personal"}
        )
        assert "Stored" in result1

        # Add another
        result2 = await execute_tool(
            "memory_add", {"content": "User works at TechCorp", "category": "work"}
        )
        assert "Stored" in result2

        # Search
        result3 = await execute_tool("memory_search", {"query": "Alice"})
        assert "Alice" in result3

        # List all
        result4 = await execute_tool("memory_list", {})
        assert "Alice" in result4
        assert "TechCorp" in result4

    @pytest.mark.asyncio
    async def test_cron_workflow(self):
        """Test a complete cron workflow using actual tools."""
        # Create a reminder
        result1 = await execute_tool(
            "cron_create", {"message": "Check emails", "delay_minutes": 5}
        )
        assert "Reminder set" in result1

        # Create a recurring task
        result2 = await execute_tool(
            "cron_create",
            {
                "message": "Daily standup",
                "cron_expression": "0 9 * * *",
                "recurring": True,
            },
        )
        assert "Recurring task" in result2

        # List jobs
        result3 = await execute_tool("cron_list", {})
        assert "Check emails" in result3
        assert "Daily standup" in result3

        # Delete one (job id=1)
        result4 = await execute_tool("cron_delete", {"job_id": 1})
        assert "Deleted" in result4

        # Verify deletion
        result5 = await execute_tool("cron_list", {})
        assert "Check emails" not in result5
        assert "Daily standup" in result5

    @pytest.mark.asyncio
    async def test_memory_then_cron_workflow(self):
        """Test memory add then cron create (remember X and remind me)."""
        from tools.cron import save_cron_jobs

        save_cron_jobs([])

        # Store in memory
        result1 = await execute_tool(
            "memory_add",
            {"content": "Meeting with Bob at 3pm tomorrow", "category": "calendar"},
        )
        assert "Stored" in result1

        # Create reminder about it
        result2 = await execute_tool(
            "cron_create",
            {"message": "Reminder: Meeting with Bob at 3pm", "delay_minutes": 60},
        )
        assert "Reminder set" in result2

        # Verify both exist
        result3 = await execute_tool("memory_search", {"query": "meeting bob"})
        assert "bob" in result3.lower() or "meeting" in result3.lower()

        result4 = await execute_tool("cron_list", {})
        assert "Bob" in result4

    @pytest.mark.asyncio
    async def test_cron_clear_workflow(self):
        """Test creating multiple cron jobs then clearing all."""
        from tools.cron import load_cron_jobs, save_cron_jobs

        save_cron_jobs([])

        # Create multiple jobs
        await execute_tool("cron_create", {"message": "Job A", "delay_minutes": 5})
        await execute_tool("cron_create", {"message": "Job B", "interval_seconds": 30})
        await execute_tool(
            "cron_create", {"message": "Job C", "cron_expression": "0 9 * * *"}
        )

        # Verify 3 jobs
        jobs = load_cron_jobs()
        assert len(jobs) == 3

        # Clear all
        result = await execute_tool("cron_clear", {})
        assert "Cleared all 3" in result

        # Verify empty
        jobs = load_cron_jobs()
        assert len(jobs) == 0

    @pytest.mark.asyncio
    async def test_web_search_mock(self):
        """Test web search tool with mocked DDGS."""
        with patch("tools.web_search.DDGS") as mock_ddgs:
            mock_instance = MagicMock()
            mock_instance.__enter__ = MagicMock(return_value=mock_instance)
            mock_instance.__exit__ = MagicMock(return_value=False)
            mock_instance.text.return_value = [
                {
                    "title": "Python Tutorial",
                    "href": "https://python.org",
                    "body": "Learn Python",
                }
            ]
            mock_ddgs.return_value = mock_instance

            result = await execute_tool("web_search", {"query": "Python tutorial"})
            assert "Python Tutorial" in result
            assert "python.org" in result

    @pytest.mark.asyncio
    async def test_search_then_memory_workflow(self):
        """Test web search then store result in memory."""
        with patch("tools.web_search.DDGS") as mock_ddgs:
            mock_instance = MagicMock()
            mock_instance.__enter__ = MagicMock(return_value=mock_instance)
            mock_instance.__exit__ = MagicMock(return_value=False)
            mock_instance.text.return_value = [
                {
                    "title": "Best Coffee Shop Seoul",
                    "href": "https://coffee.com",
                    "body": "Top rated coffee in Gangnam",
                }
            ]
            mock_ddgs.return_value = mock_instance

            # Search
            search_result = await execute_tool(
                "web_search", {"query": "best coffee seoul"}
            )
            assert "Coffee" in search_result

            # Store in memory
            store_result = await execute_tool(
                "memory_add",
                {
                    "content": f"Coffee search result: {search_result[:100]}",
                    "category": "search",
                },
            )
            assert "Stored" in store_result

            # Verify in memory
            memory_result = await execute_tool("memory_search", {"query": "coffee"})
            assert "coffee" in memory_result.lower()


class TestToolChainingErrors:
    """Test error handling in tool chaining."""

    @pytest.mark.asyncio
    async def test_delete_nonexistent_cron(self):
        """Test deleting a cron job that doesn't exist."""
        from tools.cron import save_cron_jobs

        save_cron_jobs([])

        result = await execute_tool("cron_delete", {"job_id": 999})
        assert "No job found" in result

    @pytest.mark.asyncio
    async def test_memory_search_no_results(self):
        """Test memory search with no matching results."""
        result = await execute_tool("memory_search", {"query": "xyznonexistent12345"})
        # Should return empty or "no results" message
        assert result is not None

    @pytest.mark.asyncio
    async def test_cron_create_no_schedule(self):
        """Test creating cron job without schedule fails."""
        result = await execute_tool("cron_create", {"message": "No schedule"})
        assert "Error" in result

    @pytest.mark.asyncio
    async def test_tool_missing_required_param(self):
        """Test tool with missing required parameter."""
        result = await execute_tool("cron_delete", {})
        assert "Error" in result
