#!/usr/bin/env python3
"""
Web3 Plugin Test Script

Run: python test_web3.py
"""

import asyncio
import os
import sys

from dotenv import load_dotenv

load_dotenv()


def print_header(title: str):
    print()
    print("=" * 60)
    print(f"  {title}")
    print("=" * 60)


def print_result(result: dict):
    for k, v in result.items():
        print(f"  {k}: {v}")


async def test_plugin_system():
    """Test plugin system loads correctly."""
    print_header("Plugin System")

    from plugins import get_registry, load_builtin_plugins

    load_builtin_plugins()
    registry = get_registry()

    plugins = registry.list_plugins()
    print(f"  Loaded plugins: {len(plugins)}")

    for p in plugins:
        print(f"  - {p['name']} v{p['version']}")
        print(f"    Tools: {', '.join(p['tools'])}")

    return len(plugins) > 0


async def test_wallet_info():
    """Test wallet info tool."""
    print_header("Wallet Info")

    from plugins.web3_plugin import WalletInfoTool

    tool = WalletInfoTool()
    result = await tool.execute()
    print_result(result)

    return result.get("success", False)


async def test_get_balance():
    """Test get balance tool."""
    print_header("Get Balance (Own Wallet)")

    from plugins.web3_plugin import GetBalanceTool

    tool = GetBalanceTool()
    result = await tool.execute()
    print_result(result)

    return result.get("success", False)


async def test_get_balance_address():
    """Test get balance for specific address."""
    print_header("Get Balance (Zero Address)")

    from plugins.web3_plugin import GetBalanceTool

    tool = GetBalanceTool()
    # Check zero address balance
    result = await tool.execute(address="0x0000000000000000000000000000000000000000")
    print_result(result)

    return result.get("success", False)


async def test_tx_count():
    """Test transaction count tool."""
    print_header("Transaction Count")

    from plugins.web3_plugin import GetTxCountTool

    tool = GetTxCountTool()
    result = await tool.execute()
    print_result(result)

    return result.get("success", False)


async def test_invalid_address():
    """Test error handling for invalid address."""
    print_header("Invalid Address (Error Handling)")

    from plugins.web3_plugin import GetBalanceTool

    tool = GetBalanceTool()
    result = await tool.execute(address="invalid_address_123")
    print_result(result)

    # Should fail gracefully
    return result.get("success") is False and "error" in result


async def test_tools_integration():
    """Test tools are integrated into main registry."""
    print_header("Tools Integration")

    from tools import get_all_tools, get_tool_by_name

    all_tools = get_all_tools()
    print(f"  Total tools: {len(all_tools)}")

    web3_tools = ["wallet_info", "get_balance", "send_cro", "get_tx_count"]
    found = []

    for name in web3_tools:
        tool = get_tool_by_name(name)
        if tool:
            found.append(name)
            print(f"  ✓ {name}")
        else:
            print(f"  ✗ {name} NOT FOUND")

    return len(found) == len(web3_tools)


async def test_send_cro_dry():
    """Test send_cro tool schema (no actual send)."""
    print_header("Send CRO Tool Schema")

    from plugins.web3_plugin import SendCROTool

    tool = SendCROTool()
    print(f"  Name: {tool.name}")
    print(f"  Description: {tool.description}")
    print(f"  Required params: {tool.parameters.get('required', [])}")

    # Verify schema
    props = tool.parameters.get("properties", {})
    has_to = "to_address" in props
    has_amount = "amount" in props

    print(f"  Has to_address: {has_to}")
    print(f"  Has amount: {has_amount}")

    return has_to and has_amount


async def main():
    """Run all tests."""
    print()
    print("╔══════════════════════════════════════════════════════════╗")
    print("║           Web3 Plugin Test Suite                         ║")
    print("╚══════════════════════════════════════════════════════════╝")

    tests = [
        ("Plugin System", test_plugin_system),
        ("Wallet Info", test_wallet_info),
        ("Get Balance", test_get_balance),
        ("Get Balance (Address)", test_get_balance_address),
        ("Transaction Count", test_tx_count),
        ("Invalid Address", test_invalid_address),
        ("Tools Integration", test_tools_integration),
        ("Send CRO Schema", test_send_cro_dry),
    ]

    results = []

    for name, test_func in tests:
        try:
            passed = await test_func()
            results.append((name, passed, None))
        except Exception as e:
            results.append((name, False, str(e)))

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
