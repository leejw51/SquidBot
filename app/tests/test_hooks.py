"""
Tests for Plugin Hooks System
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from plugins.hooks import (AfterToolCallEvent, AgentEndEvent,
                           BeforeAgentStartEvent, BeforeAgentStartResult,
                           BeforeToolCallEvent, BeforeToolCallResult,
                           HookContext, HookName, HookRegistry, HookRunner,
                           MessageReceivedEvent, MessageSendingEvent,
                           MessageSendingResult)


class TestHookRegistry:
    """Test HookRegistry class."""

    def test_register_hook(self):
        """Test registering a hook."""
        registry = HookRegistry()

        async def handler(event, ctx):
            pass

        registry.register(
            "test-plugin", HookName.BEFORE_AGENT_START, handler, priority=5
        )

        hooks = registry.get_hooks(HookName.BEFORE_AGENT_START)
        assert len(hooks) == 1
        assert hooks[0].plugin_id == "test-plugin"
        assert hooks[0].priority == 5

    def test_priority_ordering(self):
        """Test hooks are ordered by priority (highest first)."""
        registry = HookRegistry()

        async def handler(event, ctx):
            pass

        registry.register("plugin-a", HookName.BEFORE_TOOL_CALL, handler, priority=10)
        registry.register("plugin-b", HookName.BEFORE_TOOL_CALL, handler, priority=50)
        registry.register("plugin-c", HookName.BEFORE_TOOL_CALL, handler, priority=5)

        hooks = registry.get_hooks(HookName.BEFORE_TOOL_CALL)
        assert len(hooks) == 3
        assert hooks[0].plugin_id == "plugin-b"  # priority 50
        assert hooks[1].plugin_id == "plugin-a"  # priority 10
        assert hooks[2].plugin_id == "plugin-c"  # priority 5

    def test_unregister_plugin(self):
        """Test unregistering all hooks for a plugin."""
        registry = HookRegistry()

        async def handler(event, ctx):
            pass

        registry.register("plugin-a", HookName.BEFORE_TOOL_CALL, handler)
        registry.register("plugin-a", HookName.AFTER_TOOL_CALL, handler)
        registry.register("plugin-b", HookName.BEFORE_TOOL_CALL, handler)

        removed = registry.unregister("plugin-a")
        assert removed == 2

        all_hooks = registry.list_all()
        assert len(all_hooks) == 1
        assert all_hooks[0]["plugin_id"] == "plugin-b"

    def test_has_hooks(self):
        """Test checking if hooks exist."""
        registry = HookRegistry()

        assert not registry.has_hooks(HookName.BEFORE_AGENT_START)

        async def handler(event, ctx):
            pass

        registry.register("test", HookName.BEFORE_AGENT_START, handler)
        assert registry.has_hooks(HookName.BEFORE_AGENT_START)
        assert not registry.has_hooks(HookName.AGENT_END)


class TestHookRunner:
    """Test HookRunner class."""

    @pytest.mark.asyncio
    async def test_void_hook_parallel_execution(self):
        """Test void hooks run in parallel."""
        registry = HookRegistry()
        runner = HookRunner(registry)

        call_order = []

        async def handler_a(event, ctx):
            await asyncio.sleep(0.05)
            call_order.append("a")

        async def handler_b(event, ctx):
            call_order.append("b")

        registry.register("plugin-a", HookName.AGENT_END, handler_a)
        registry.register("plugin-b", HookName.AGENT_END, handler_b)

        event = AgentEndEvent(messages=[], success=True)
        ctx = HookContext(plugin_id="test")

        await runner.run_agent_end(event, ctx)

        # Both should complete, "b" should finish first
        assert "a" in call_order
        assert "b" in call_order

    @pytest.mark.asyncio
    async def test_modifying_hook_sequential(self):
        """Test modifying hooks run sequentially by priority."""
        registry = HookRegistry()
        runner = HookRunner(registry)

        async def handler_low(event, ctx):
            return BeforeAgentStartResult(prepend_context="LOW")

        async def handler_high(event, ctx):
            return BeforeAgentStartResult(prepend_context="HIGH")

        registry.register("low", HookName.BEFORE_AGENT_START, handler_low, priority=1)
        registry.register(
            "high", HookName.BEFORE_AGENT_START, handler_high, priority=10
        )

        event = BeforeAgentStartEvent(prompt="test")
        ctx = HookContext(plugin_id="test")

        result = await runner.run_before_agent_start(event, ctx)

        # HIGH runs first (priority 10), LOW runs second (priority 1)
        # Result should be merged: "HIGH\n\nLOW"
        assert result is not None
        assert "HIGH" in result.prepend_context
        assert "LOW" in result.prepend_context

    @pytest.mark.asyncio
    async def test_before_tool_call_block(self):
        """Test before_tool_call can block execution."""
        registry = HookRegistry()
        runner = HookRunner(registry)

        async def blocker(event, ctx):
            if event.tool_name == "dangerous_tool":
                return BeforeToolCallResult(block=True, block_reason="Blocked!")
            return None

        registry.register("blocker", HookName.BEFORE_TOOL_CALL, blocker)

        # Test blocked
        event = BeforeToolCallEvent(tool_name="dangerous_tool", params={})
        ctx = HookContext(plugin_id="test")
        result = await runner.run_before_tool_call(event, ctx)

        assert result is not None
        assert result.block is True
        assert result.block_reason == "Blocked!"

        # Test allowed
        event2 = BeforeToolCallEvent(tool_name="safe_tool", params={})
        result2 = await runner.run_before_tool_call(event2, ctx)
        assert result2 is None

    @pytest.mark.asyncio
    async def test_message_sending_modify(self):
        """Test message_sending can modify content."""
        registry = HookRegistry()
        runner = HookRunner(registry)

        async def modifier(event, ctx):
            return MessageSendingResult(content=f"[Modified] {event.content}")

        registry.register("modifier", HookName.MESSAGE_SENDING, modifier)

        event = MessageSendingEvent(recipient="user", content="Hello", channel="tcp")
        ctx = HookContext(plugin_id="test")

        result = await runner.run_message_sending(event, ctx)

        assert result is not None
        assert result.content == "[Modified] Hello"

    @pytest.mark.asyncio
    async def test_message_sending_cancel(self):
        """Test message_sending can cancel sending."""
        registry = HookRegistry()
        runner = HookRunner(registry)

        async def canceller(event, ctx):
            if "spam" in event.content.lower():
                return MessageSendingResult(cancel=True)
            return None

        registry.register("spam-filter", HookName.MESSAGE_SENDING, canceller)

        # Test cancelled
        event = MessageSendingEvent(
            recipient="user", content="Buy spam now!", channel="tcp"
        )
        ctx = HookContext(plugin_id="test")
        result = await runner.run_message_sending(event, ctx)

        assert result is not None
        assert result.cancel is True

        # Test allowed
        event2 = MessageSendingEvent(recipient="user", content="Hello!", channel="tcp")
        result2 = await runner.run_message_sending(event2, ctx)
        assert result2 is None

    @pytest.mark.asyncio
    async def test_error_handling_catch_mode(self):
        """Test errors are caught when catch_errors=True."""
        registry = HookRegistry()
        runner = HookRunner(registry, catch_errors=True)

        async def failing_handler(event, ctx):
            raise ValueError("Test error")

        async def success_handler(event, ctx):
            pass

        registry.register("fail", HookName.AGENT_END, failing_handler)
        registry.register("success", HookName.AGENT_END, success_handler)

        event = AgentEndEvent(messages=[], success=True)
        ctx = HookContext(plugin_id="test")

        # Should not raise, both handlers are called
        await runner.run_agent_end(event, ctx)

    @pytest.mark.asyncio
    async def test_sync_handler_support(self):
        """Test synchronous handlers are supported."""
        registry = HookRegistry()
        runner = HookRunner(registry)

        def sync_handler(event, ctx):
            return BeforeToolCallResult(params={"modified": True})

        registry.register("sync", HookName.BEFORE_TOOL_CALL, sync_handler)

        event = BeforeToolCallEvent(tool_name="test", params={})
        ctx = HookContext(plugin_id="test")

        result = await runner.run_before_tool_call(event, ctx)

        assert result is not None
        assert result.params == {"modified": True}


class TestWeb3PluginHooks:
    """Test Web3 plugin hooks integration."""

    @pytest.mark.asyncio
    async def test_web3_blocks_large_transactions(self):
        """Test Web3 plugin blocks transactions over 100 CRO."""
        from plugins import get_hook_runner, get_registry, load_builtin_plugins

        load_builtin_plugins()
        runner = get_hook_runner()

        # Test large transaction (should be blocked)
        event = BeforeToolCallEvent(
            tool_name="send_cro",
            params={"amount": "150", "to_address": "0x123"},
        )
        ctx = HookContext(plugin_id="test", session_id="test")

        result = await runner.run_before_tool_call(event, ctx)

        assert result is not None
        assert result.block is True
        assert "100 CRO" in result.block_reason

    @pytest.mark.asyncio
    async def test_web3_allows_small_transactions(self):
        """Test Web3 plugin allows transactions under 100 CRO."""
        from plugins import get_hook_runner

        runner = get_hook_runner()

        # Test small transaction (should be allowed)
        event = BeforeToolCallEvent(
            tool_name="send_cro",
            params={"amount": "50", "to_address": "0x123"},
        )
        ctx = HookContext(plugin_id="test", session_id="test")

        result = await runner.run_before_tool_call(event, ctx)

        # No blocking result
        assert result is None or result.block is False

    @pytest.mark.asyncio
    async def test_web3_ignores_other_tools(self):
        """Test Web3 hooks ignore non-web3 tools."""
        from plugins import get_hook_runner

        runner = get_hook_runner()

        event = BeforeToolCallEvent(
            tool_name="web_search",
            params={"query": "test"},
        )
        ctx = HookContext(plugin_id="test")

        result = await runner.run_before_tool_call(event, ctx)

        # Should not interfere with other tools
        assert result is None


class TestHookEventTypes:
    """Test hook event/result dataclasses."""

    def test_before_agent_start_event(self):
        """Test BeforeAgentStartEvent creation."""
        event = BeforeAgentStartEvent(
            prompt="Hello",
            messages=[{"role": "user", "content": "Hi"}],
            session_id="123",
        )
        assert event.prompt == "Hello"
        assert len(event.messages) == 1
        assert event.session_id == "123"

    def test_before_tool_call_result_defaults(self):
        """Test BeforeToolCallResult defaults."""
        result = BeforeToolCallResult()
        assert result.params is None
        assert result.block is False
        assert result.block_reason is None

    def test_hook_context(self):
        """Test HookContext creation."""
        ctx = HookContext(
            plugin_id="test",
            session_id="session-123",
            channel="telegram",
            metadata={"user_id": 42},
        )
        assert ctx.plugin_id == "test"
        assert ctx.session_id == "session-123"
        assert ctx.channel == "telegram"
        assert ctx.metadata["user_id"] == 42
