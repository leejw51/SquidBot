#!/usr/bin/env python3
"""
Hook System Test Script

Run: python test_hooks.py
"""

import asyncio
import sys


def print_header(title: str):
    print()
    print("=" * 60)
    print(f"  {title}")
    print("=" * 60)


def print_result(label: str, value):
    print(f"  {label}: {value}")


async def test_hook_registry():
    """Test hook registry operations."""
    print_header("Hook Registry")

    from plugins.hooks import HookName, HookRegistry

    registry = HookRegistry()

    # Register hooks
    async def handler1(event, ctx):
        return {"from": "handler1"}

    async def handler2(event, ctx):
        return {"from": "handler2"}

    registry.register("plugin-a", HookName.BEFORE_TOOL_CALL, handler1, priority=10)
    registry.register("plugin-b", HookName.BEFORE_TOOL_CALL, handler2, priority=5)
    registry.register("plugin-a", HookName.AFTER_TOOL_CALL, handler1)

    print_result("Total hooks", len(registry.list_all()))
    print_result(
        "BEFORE_TOOL_CALL hooks", registry.get_hook_count(HookName.BEFORE_TOOL_CALL)
    )
    print_result(
        "AFTER_TOOL_CALL hooks", registry.get_hook_count(HookName.AFTER_TOOL_CALL)
    )

    # Check priority ordering
    hooks = registry.get_hooks(HookName.BEFORE_TOOL_CALL)
    print_result("Priority order", [f"{h.plugin_id}(p={h.priority})" for h in hooks])

    # Unregister
    removed = registry.unregister("plugin-a")
    print_result("Removed hooks for plugin-a", removed)
    print_result("Remaining hooks", len(registry.list_all()))

    return True


async def test_void_hooks():
    """Test void hooks (fire-and-forget)."""
    print_header("Void Hooks (Parallel Execution)")

    from plugins.hooks import (AgentEndEvent, HookContext, HookName,
                               HookRegistry, HookRunner)

    registry = HookRegistry()
    runner = HookRunner(registry)

    results = []

    async def handler_a(event, ctx):
        await asyncio.sleep(0.05)
        results.append("A")

    async def handler_b(event, ctx):
        results.append("B")

    registry.register("a", HookName.AGENT_END, handler_a)
    registry.register("b", HookName.AGENT_END, handler_b)

    event = AgentEndEvent(messages=[], success=True, response="Done")
    ctx = HookContext(plugin_id="test")

    await runner.run_agent_end(event, ctx)

    print_result("Execution order", results)
    print_result("Both executed", "A" in results and "B" in results)

    return "A" in results and "B" in results


async def test_modifying_hooks():
    """Test modifying hooks (sequential, returns result)."""
    print_header("Modifying Hooks (Sequential)")

    from plugins.hooks import (BeforeAgentStartEvent, BeforeAgentStartResult,
                               HookContext, HookName, HookRegistry, HookRunner)

    registry = HookRegistry()
    runner = HookRunner(registry)

    async def high_priority(event, ctx):
        return BeforeAgentStartResult(prepend_context="[HIGH PRIORITY]")

    async def low_priority(event, ctx):
        return BeforeAgentStartResult(prepend_context="[LOW PRIORITY]")

    registry.register("high", HookName.BEFORE_AGENT_START, high_priority, priority=100)
    registry.register("low", HookName.BEFORE_AGENT_START, low_priority, priority=1)

    event = BeforeAgentStartEvent(prompt="Hello")
    ctx = HookContext(plugin_id="test")

    result = await runner.run_before_agent_start(event, ctx)

    print_result("Result type", type(result).__name__)
    print_result("Prepend context", result.prepend_context if result else None)
    print_result(
        "Contains HIGH", "HIGH" in (result.prepend_context or "") if result else False
    )
    print_result(
        "Contains LOW", "LOW" in (result.prepend_context or "") if result else False
    )

    return (
        result is not None
        and "HIGH" in result.prepend_context
        and "LOW" in result.prepend_context
    )


async def test_tool_call_blocking():
    """Test before_tool_call hook can block execution."""
    print_header("Tool Call Blocking")

    from plugins.hooks import (BeforeToolCallEvent, BeforeToolCallResult,
                               HookContext, HookName, HookRegistry, HookRunner)

    registry = HookRegistry()
    runner = HookRunner(registry)

    async def security_check(event, ctx):
        dangerous_tools = ["rm_rf", "drop_database", "send_all_funds"]
        if event.tool_name in dangerous_tools:
            return BeforeToolCallResult(
                block=True,
                block_reason=f"Tool '{event.tool_name}' is blocked for security",
            )
        return None

    registry.register(
        "security", HookName.BEFORE_TOOL_CALL, security_check, priority=100
    )

    ctx = HookContext(plugin_id="test")

    # Test blocked tool
    event1 = BeforeToolCallEvent(tool_name="drop_database", params={})
    result1 = await runner.run_before_tool_call(event1, ctx)
    print_result("drop_database blocked", result1.block if result1 else False)
    print_result("Block reason", result1.block_reason if result1 else None)

    # Test allowed tool
    event2 = BeforeToolCallEvent(tool_name="web_search", params={"query": "test"})
    result2 = await runner.run_before_tool_call(event2, ctx)
    print_result("web_search blocked", result2.block if result2 else False)

    return (result1 and result1.block) and (result2 is None or not result2.block)


async def test_message_modification():
    """Test message_sending hook can modify content."""
    print_header("Message Modification")

    from plugins.hooks import (HookContext, HookName, HookRegistry, HookRunner,
                               MessageSendingEvent, MessageSendingResult)

    registry = HookRegistry()
    runner = HookRunner(registry)

    async def add_signature(event, ctx):
        return MessageSendingResult(content=f"{event.content}\n\n-- SquidBot")

    async def spam_filter(event, ctx):
        if "buy now" in event.content.lower():
            return MessageSendingResult(cancel=True)
        return None

    registry.register("signature", HookName.MESSAGE_SENDING, add_signature, priority=1)
    registry.register("spam", HookName.MESSAGE_SENDING, spam_filter, priority=100)

    ctx = HookContext(plugin_id="test")

    # Test normal message
    event1 = MessageSendingEvent(recipient="user", content="Hello!", channel="tcp")
    result1 = await runner.run_message_sending(event1, ctx)
    print_result("Normal message modified", result1.content if result1 else None)

    # Test spam message
    event2 = MessageSendingEvent(
        recipient="user", content="BUY NOW for cheap!", channel="tcp"
    )
    result2 = await runner.run_message_sending(event2, ctx)
    print_result("Spam cancelled", result2.cancel if result2 else False)

    return (result1 and "SquidBot" in result1.content) and (result2 and result2.cancel)


async def test_error_handling():
    """Test hook error handling."""
    print_header("Error Handling")

    from plugins.hooks import (AgentEndEvent, HookContext, HookName,
                               HookRegistry, HookRunner)

    registry = HookRegistry()
    runner = HookRunner(registry, catch_errors=True)

    async def failing_handler(event, ctx):
        raise ValueError("Intentional error")

    async def success_handler(event, ctx):
        pass

    registry.register("fail", HookName.AGENT_END, failing_handler)
    registry.register("success", HookName.AGENT_END, success_handler)

    event = AgentEndEvent(messages=[], success=True)
    ctx = HookContext(plugin_id="test")

    try:
        await runner.run_agent_end(event, ctx)
        print_result("Error caught", True)
        print_result("Execution continued", True)
        return True
    except Exception as e:
        print_result("Error caught", False)
        print_result("Exception", str(e))
        return False


async def test_web3_plugin_hooks():
    """Test Web3 plugin hooks."""
    print_header("Web3 Plugin Hooks")

    from plugins import (get_hook_registry, get_hook_runner, get_registry,
                         load_builtin_plugins)
    from plugins.hooks import (AfterToolCallEvent, BeforeToolCallEvent,
                               HookContext, HookName)

    # Load plugins
    load_builtin_plugins()

    registry = get_registry()
    hook_registry = get_hook_registry()
    runner = get_hook_runner()

    # Check plugin loaded
    plugins = registry.list_plugins()
    web3_plugin = next((p for p in plugins if p["id"] == "web3"), None)

    if not web3_plugin:
        print_result("Web3 plugin loaded", False)
        return False

    print_result("Web3 plugin loaded", True)
    print_result("Hooks registered", web3_plugin["hooks"])

    ctx = HookContext(plugin_id="test", session_id="test-session")

    # Test small transaction (allowed)
    event1 = BeforeToolCallEvent(
        tool_name="send_cro", params={"amount": "10", "to_address": "0x123"}
    )
    result1 = await runner.run_before_tool_call(event1, ctx)
    blocked1 = result1 and result1.block
    print_result("10 CRO transaction blocked", blocked1)

    # Test large transaction (blocked)
    event2 = BeforeToolCallEvent(
        tool_name="send_cro", params={"amount": "200", "to_address": "0x123"}
    )
    result2 = await runner.run_before_tool_call(event2, ctx)
    blocked2 = result2 and result2.block
    print_result("200 CRO transaction blocked", blocked2)
    if blocked2:
        print_result("Block reason", result2.block_reason)

    # Test after_tool_call
    event3 = AfterToolCallEvent(
        tool_name="get_balance",
        params={},
        result={"balance_cro": "100"},
        duration_ms=50.5,
    )
    await runner.run_after_tool_call(event3, ctx)
    print_result("after_tool_call executed", True)

    return not blocked1 and blocked2


async def test_plugin_integration():
    """Test full plugin system integration."""
    print_header("Plugin System Integration")

    from plugins import (BeforeToolCallEvent, HookContext, HookName,
                         get_hook_registry, get_hook_runner, get_registry)
    from tools import get_all_tools, get_tool_by_name

    registry = get_registry()
    hook_registry = get_hook_registry()

    # List all plugins
    plugins = registry.list_plugins()
    print_result("Total plugins", len(plugins))

    for p in plugins:
        print(f"    - {p['name']} v{p['version']}")
        print(f"      Tools: {', '.join(p['tools'])}")
        print(f"      Hooks: {', '.join(p['hooks']) if p['hooks'] else 'none'}")

    # List all hooks
    all_hooks = hook_registry.list_all()
    print_result("Total hooks registered", len(all_hooks))

    # Get tools including plugin tools
    all_tools = get_all_tools()
    print_result("Total tools available", len(all_tools))

    # Verify web3 tools are available
    web3_tool = get_tool_by_name("wallet_info")
    print_result("wallet_info tool found", web3_tool is not None)

    return len(plugins) > 0 and len(all_hooks) > 0


async def main():
    """Run all tests."""
    print()
    print("╔══════════════════════════════════════════════════════════╗")
    print("║           Hook System Test Suite                         ║")
    print("╚══════════════════════════════════════════════════════════╝")

    tests = [
        ("Hook Registry", test_hook_registry),
        ("Void Hooks", test_void_hooks),
        ("Modifying Hooks", test_modifying_hooks),
        ("Tool Call Blocking", test_tool_call_blocking),
        ("Message Modification", test_message_modification),
        ("Error Handling", test_error_handling),
        ("Web3 Plugin Hooks", test_web3_plugin_hooks),
        ("Plugin Integration", test_plugin_integration),
    ]

    results = []

    for name, test_func in tests:
        try:
            passed = await test_func()
            results.append((name, passed, None))
        except Exception as e:
            results.append((name, False, str(e)))
            import traceback

            traceback.print_exc()

    # Summary
    print_header("Test Summary")

    passed_count = 0
    failed_count = 0

    for name, passed, error in results:
        if passed:
            print(f"  ✓ {name}")
            passed_count += 1
        else:
            print(f"  ✗ {name}")
            if error:
                print(f"    Error: {error}")
            failed_count += 1

    print()
    print(f"  Passed: {passed_count}/{len(results)}")
    print(f"  Failed: {failed_count}/{len(results)}")
    print()

    if failed_count > 0:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
