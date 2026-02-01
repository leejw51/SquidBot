"""Tests for agent module."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent import (build_system_prompt, execute_tool, get_base_system_prompt,
                   run_agent_with_history)


class TestSecurityRestrictions:
    """Test security restrictions in system prompt."""

    def test_base_prompt_includes_squidbot_home(self):
        """Test that base prompt includes SQUIDBOT_HOME path."""
        prompt = get_base_system_prompt()
        assert ".squidbot" in prompt or "SQUIDBOT" in prompt

    def test_base_prompt_includes_security_section(self):
        """Test that base prompt includes security restrictions."""
        prompt = get_base_system_prompt()
        assert "SECURITY RESTRICTIONS" in prompt

    def test_base_prompt_restricts_workspace(self):
        """Test that prompt restricts access to workspace only."""
        prompt = get_base_system_prompt()
        assert "WORKSPACE BOUNDARY" in prompt
        assert "ONLY access files" in prompt

    def test_base_prompt_protects_private_keys(self):
        """Test that prompt protects private keys."""
        prompt = get_base_system_prompt()
        assert "Private keys" in prompt
        assert "NEVER EXPOSE" in prompt

    def test_base_prompt_protects_mnemonics(self):
        """Test that prompt protects mnemonics/seed phrases."""
        prompt = get_base_system_prompt()
        assert "Mnemonics" in prompt or "mnemonic" in prompt
        assert "seed phrase" in prompt.lower()

    def test_base_prompt_protects_env_files(self):
        """Test that prompt protects .env files."""
        prompt = get_base_system_prompt()
        assert ".env" in prompt

    def test_base_prompt_protects_credentials(self):
        """Test that prompt protects various credentials."""
        prompt = get_base_system_prompt()
        assert "API keys" in prompt
        assert "Passwords" in prompt
        assert "credentials" in prompt.lower()

    def test_base_prompt_protects_shell_configs(self):
        """Test that prompt protects shell configuration files."""
        prompt = get_base_system_prompt()
        assert ".zshrc" in prompt
        assert ".bashrc" in prompt
        assert ".bash_profile" in prompt

    def test_base_prompt_protects_cloud_credentials(self):
        """Test that prompt protects cloud provider credentials."""
        prompt = get_base_system_prompt()
        assert ".aws" in prompt
        assert ".gcloud" in prompt

    def test_base_prompt_includes_refuse_instruction(self):
        """Test that prompt instructs to refuse exposing secrets."""
        prompt = get_base_system_prompt()
        assert "REFUSE" in prompt
        assert "security risk" in prompt.lower()


class TestBuildSystemPrompt:
    """Test system prompt building."""

    @pytest.mark.asyncio
    async def test_build_basic_prompt(self):
        """Test building basic system prompt."""
        with patch(
            "agent.get_character_prompt", new_callable=AsyncMock
        ) as mock_char, patch(
            "agent.get_skills_context", new_callable=AsyncMock
        ) as mock_skills, patch(
            "agent.get_memory_context", new_callable=AsyncMock
        ) as mock_memory:
            mock_char.return_value = ""
            mock_skills.return_value = ""
            mock_memory.return_value = ""

            prompt = await build_system_prompt()

            assert "autonomous AI agent" in prompt
            assert "tools" in prompt.lower()

    @pytest.mark.asyncio
    async def test_build_prompt_includes_security(self):
        """Test that built prompt includes security restrictions."""
        with patch(
            "agent.get_character_prompt", new_callable=AsyncMock
        ) as mock_char, patch(
            "agent.get_skills_context", new_callable=AsyncMock
        ) as mock_skills, patch(
            "agent.get_memory_context", new_callable=AsyncMock
        ) as mock_memory:
            mock_char.return_value = ""
            mock_skills.return_value = ""
            mock_memory.return_value = ""

            prompt = await build_system_prompt()

            assert "SECURITY RESTRICTIONS" in prompt
            assert "Private keys" in prompt
            assert "NEVER EXPOSE" in prompt

    @pytest.mark.asyncio
    async def test_build_prompt_with_character(self):
        """Test building prompt with character."""
        with patch(
            "agent.get_character_prompt", new_callable=AsyncMock
        ) as mock_char, patch(
            "agent.get_skills_context", new_callable=AsyncMock
        ) as mock_skills, patch(
            "agent.get_memory_context", new_callable=AsyncMock
        ) as mock_memory:
            mock_char.return_value = "## Character\nYou are Bob."
            mock_skills.return_value = ""
            mock_memory.return_value = ""

            prompt = await build_system_prompt()

            assert "You are Bob" in prompt

    @pytest.mark.asyncio
    async def test_build_prompt_with_skills(self):
        """Test building prompt with skills."""
        with patch(
            "agent.get_character_prompt", new_callable=AsyncMock
        ) as mock_char, patch(
            "agent.get_skills_context", new_callable=AsyncMock
        ) as mock_skills, patch(
            "agent.get_memory_context", new_callable=AsyncMock
        ) as mock_memory:
            mock_char.return_value = ""
            mock_skills.return_value = "## Skills\n- Search\n- Browse"
            mock_memory.return_value = ""

            prompt = await build_system_prompt()

            assert "Skills" in prompt
            assert "Search" in prompt

    @pytest.mark.asyncio
    async def test_build_prompt_with_memory(self):
        """Test building prompt with memory context."""
        with patch(
            "agent.get_character_prompt", new_callable=AsyncMock
        ) as mock_char, patch(
            "agent.get_skills_context", new_callable=AsyncMock
        ) as mock_skills, patch(
            "agent.get_memory_context", new_callable=AsyncMock
        ) as mock_memory:
            mock_char.return_value = ""
            mock_skills.return_value = ""
            mock_memory.return_value = "## Memory\nUser likes Python."

            prompt = await build_system_prompt()

            assert "Memory" in prompt
            assert "Python" in prompt


class TestExecuteTool:
    """Test tool execution."""

    @pytest.mark.asyncio
    async def test_execute_known_tool(self):
        """Test executing a known tool."""
        mock_tool = MagicMock()
        mock_tool.execute = AsyncMock(return_value="Tool result")

        with patch("agent.get_tool_by_name", return_value=mock_tool):
            result = await execute_tool("test_tool", {"arg": "value"})

            assert result == "Tool result"
            mock_tool.execute.assert_called_once_with(arg="value")

    @pytest.mark.asyncio
    async def test_execute_unknown_tool(self):
        """Test executing an unknown tool."""
        with patch("agent.get_tool_by_name", return_value=None):
            result = await execute_tool("unknown_tool", {})

            assert "Error" in result
            assert "Unknown tool" in result

    @pytest.mark.asyncio
    async def test_execute_tool_exception(self):
        """Test tool execution with exception."""
        mock_tool = MagicMock()
        mock_tool.execute = AsyncMock(side_effect=Exception("Tool failed"))

        with patch("agent.get_tool_by_name", return_value=mock_tool):
            result = await execute_tool("failing_tool", {})

            assert "Error" in result
            assert "Tool failed" in result


class TestRunAgentWithHistory:
    """Test running agent with history management."""

    @pytest.mark.asyncio
    async def test_run_agent_updates_history(self):
        """Test that history is updated after agent run."""
        with patch("agent.run_agent", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = "Agent response"

            response, history = await run_agent_with_history("Hello", [])

            assert response == "Agent response"
            assert len(history) == 2
            assert history[0]["role"] == "user"
            assert history[0]["content"] == "Hello"
            assert history[1]["role"] == "assistant"
            assert history[1]["content"] == "Agent response"

    @pytest.mark.asyncio
    async def test_run_agent_preserves_history(self):
        """Test that existing history is preserved."""
        existing_history = [
            {"role": "user", "content": "Previous message"},
            {"role": "assistant", "content": "Previous response"},
        ]

        with patch("agent.run_agent", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = "New response"

            response, history = await run_agent_with_history(
                "New message", existing_history
            )

            assert len(history) == 4
            assert history[0]["content"] == "Previous message"
            assert history[3]["content"] == "New response"

    @pytest.mark.asyncio
    async def test_run_agent_truncates_long_history(self):
        """Test that history is truncated when too long."""
        # Create history with 50 messages (25 exchanges)
        long_history = []
        for i in range(25):
            long_history.append({"role": "user", "content": f"Message {i}"})
            long_history.append({"role": "assistant", "content": f"Response {i}"})

        with patch("agent.run_agent", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = "New response"

            response, history = await run_agent_with_history(
                "New message", long_history
            )

            # History should be truncated to last 40 messages
            assert len(history) <= 42  # 40 + 2 new messages


class TestRunAgentMocked:
    """Test run_agent with mocked OpenAI client."""

    @pytest.mark.asyncio
    async def test_run_agent_simple_response(self):
        """Test agent with simple text response (no tool calls)."""
        mock_message = MagicMock()
        mock_message.tool_calls = None
        mock_message.content = "Hello! How can I help?"

        mock_choice = MagicMock()
        mock_choice.message = mock_message

        mock_response = MagicMock()
        mock_response.choices = [mock_choice]

        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        with patch("agent.client", mock_client), patch(
            "agent.build_system_prompt", new_callable=AsyncMock
        ) as mock_prompt, patch("agent.get_openai_tools", return_value=[]):
            mock_prompt.return_value = "System prompt"

            from agent import run_agent

            response = await run_agent("Hi")

            assert response == "Hello! How can I help?"

    @pytest.mark.asyncio
    async def test_run_agent_max_iterations(self):
        """Test agent hitting max iterations."""
        # Create a response that always wants to call tools
        mock_tool_call = MagicMock()
        mock_tool_call.id = "call_1"
        mock_tool_call.function.name = "test_tool"
        mock_tool_call.function.arguments = "{}"

        mock_message = MagicMock()
        mock_message.tool_calls = [mock_tool_call]
        mock_message.content = ""

        mock_choice = MagicMock()
        mock_choice.message = mock_message

        mock_response = MagicMock()
        mock_response.choices = [mock_choice]

        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        mock_tool = MagicMock()
        mock_tool.execute = AsyncMock(return_value="Tool result")

        with patch("agent.client", mock_client), patch(
            "agent.build_system_prompt", new_callable=AsyncMock
        ) as mock_prompt, patch("agent.get_openai_tools", return_value=[]), patch(
            "agent.get_tool_by_name", return_value=mock_tool
        ):
            mock_prompt.return_value = "System prompt"

            from agent import run_agent

            response = await run_agent("Do something", max_iterations=3)

            # Should hit max iterations
            assert "maximum number of steps" in response.lower()
            assert mock_client.chat.completions.create.call_count == 3
