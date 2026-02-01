"""
Tests for Web3 Plugin

Tests wallet functionality, balance checking, and transaction operations.
"""

import os
from unittest.mock import MagicMock, patch

import pytest

# Set test environment before imports
os.environ.setdefault("SQUIDBOT_CHAINID", "338")
os.environ.setdefault("SQUIDBOT_RPC", "https://evm-dev-t3.cronos.org")
os.environ.setdefault("SQUIDBOT_WALLET_INDEX", "0")


class TestPluginSystem:
    """Test the plugin system itself."""

    def test_plugin_registry_import(self):
        """Test plugin registry can be imported."""
        from plugins import PluginRegistry, get_registry

        registry = get_registry()
        assert isinstance(registry, PluginRegistry)

    def test_load_builtin_plugins(self):
        """Test loading built-in plugins."""
        from plugins import get_registry, load_builtin_plugins

        load_builtin_plugins()
        registry = get_registry()
        plugins = registry.list_plugins()

        assert len(plugins) >= 1
        plugin_ids = [p["id"] for p in plugins]
        assert "web3" in plugin_ids

    def test_web3_plugin_manifest(self):
        """Test web3 plugin manifest."""
        from plugins import get_registry, load_builtin_plugins

        load_builtin_plugins()
        registry = get_registry()
        plugin = registry.get_plugin("web3")

        assert plugin is not None
        manifest = plugin.manifest
        assert manifest.id == "web3"
        assert manifest.name == "Web3 Plugin"
        assert manifest.version == "1.0.0"

    def test_web3_plugin_tools(self):
        """Test web3 plugin provides correct tools."""
        from plugins import get_registry, load_builtin_plugins

        load_builtin_plugins()
        registry = get_registry()
        plugin = registry.get_plugin("web3")

        tools = plugin.get_tools()
        tool_names = [t.name for t in tools]

        assert "wallet_info" in tool_names
        assert "get_balance" in tool_names
        assert "send_cro" in tool_names
        assert "get_tx_count" in tool_names


class TestWalletGeneration:
    """Test wallet generation and mnemonic handling."""

    def test_random_wallet_generation(self):
        """Test random wallet generation when no mnemonic set."""
        # Clear mnemonic to test random generation
        with patch.dict(os.environ, {"SQUIDBOT_MNEMONICS": ""}):
            # Reimport to pick up new env
            import importlib

            import plugins.web3_plugin as web3_module

            importlib.reload(web3_module)

            account, mnemonic = web3_module.get_wallet()

            assert account is not None
            assert account.address.startswith("0x")
            assert len(account.address) == 42
            assert mnemonic is not None
            assert len(mnemonic.split()) == 12  # 12 word mnemonic

    def test_wallet_from_mnemonic(self):
        """Test wallet derivation from mnemonic."""
        test_mnemonic = "abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon about"

        with patch.dict(os.environ, {"SQUIDBOT_MNEMONICS": test_mnemonic}):
            import importlib

            import plugins.web3_plugin as web3_module

            importlib.reload(web3_module)

            account, mnemonic = web3_module.get_wallet()

            assert account is not None
            assert account.address.startswith("0x")
            assert mnemonic == test_mnemonic
            # Known address for this mnemonic at index 0
            assert account.address == "0x9858EfFD232B4033E47d90003D41EC34EcaEda94"

    def test_wallet_index(self):
        """Test different wallet indices produce different addresses."""
        test_mnemonic = "abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon about"

        with patch.dict(
            os.environ,
            {"SQUIDBOT_MNEMONICS": test_mnemonic, "SQUIDBOT_WALLET_INDEX": "0"},
        ):
            import importlib

            import plugins.web3_plugin as web3_module

            importlib.reload(web3_module)
            account0, _ = web3_module.get_wallet()

        with patch.dict(
            os.environ,
            {"SQUIDBOT_MNEMONICS": test_mnemonic, "SQUIDBOT_WALLET_INDEX": "1"},
        ):
            importlib.reload(web3_module)
            account1, _ = web3_module.get_wallet()

        assert account0.address != account1.address


class TestWalletInfoTool:
    """Test WalletInfoTool."""

    @pytest.mark.asyncio
    async def test_wallet_info_success(self):
        """Test wallet_info returns correct data."""
        from plugins.web3_plugin import WalletInfoTool

        tool = WalletInfoTool()

        # Mock web3 connection
        with patch("plugins.web3_plugin.get_web3") as mock_web3:
            mock_w3 = MagicMock()
            mock_w3.is_connected.return_value = True
            mock_web3.return_value = mock_w3

            result = await tool.execute()

            assert result["success"] is True
            assert "address" in result
            assert result["address"].startswith("0x")
            assert result["chain_id"] == 338
            assert "rpc_url" in result

    def test_wallet_info_tool_schema(self):
        """Test wallet_info tool has correct schema."""
        from plugins.web3_plugin import WalletInfoTool

        tool = WalletInfoTool()

        assert tool.name == "wallet_info"
        assert "wallet" in tool.description.lower()
        assert tool.parameters["type"] == "object"


class TestGetBalanceTool:
    """Test GetBalanceTool."""

    @pytest.mark.asyncio
    async def test_get_balance_own_wallet(self):
        """Test getting balance of own wallet."""
        from plugins.web3_plugin import GetBalanceTool

        tool = GetBalanceTool()

        with patch("plugins.web3_plugin.get_web3") as mock_web3:
            mock_w3 = MagicMock()
            mock_w3.is_address.return_value = True
            mock_w3.to_checksum_address.return_value = (
                "0x9858EfFD232B4033E47d90003D41EC34EcaEda94"
            )
            mock_w3.eth.get_balance.return_value = 1000000000000000000  # 1 ETH in wei
            mock_w3.from_wei.return_value = 1.0
            mock_web3.return_value = mock_w3

            result = await tool.execute()

            assert result["success"] is True
            assert "balance_cro" in result
            assert "balance_wei" in result

    @pytest.mark.asyncio
    async def test_get_balance_specific_address(self):
        """Test getting balance of specific address."""
        from plugins.web3_plugin import GetBalanceTool

        tool = GetBalanceTool()
        test_address = "0x742d35Cc6634C0532925a3b844Bc9e7595f5c123"

        with patch("plugins.web3_plugin.get_web3") as mock_web3:
            mock_w3 = MagicMock()
            mock_w3.is_address.return_value = True
            mock_w3.to_checksum_address.return_value = test_address
            mock_w3.eth.get_balance.return_value = 5000000000000000000
            mock_w3.from_wei.return_value = 5.0
            mock_web3.return_value = mock_w3

            result = await tool.execute(address=test_address)

            assert result["success"] is True
            assert result["address"] == test_address

    @pytest.mark.asyncio
    async def test_get_balance_invalid_address(self):
        """Test getting balance with invalid address."""
        from plugins.web3_plugin import GetBalanceTool

        tool = GetBalanceTool()

        with patch("plugins.web3_plugin.get_web3") as mock_web3:
            mock_w3 = MagicMock()
            mock_w3.is_address.return_value = False
            mock_web3.return_value = mock_w3

            result = await tool.execute(address="invalid_address")

            assert result["success"] is False
            assert "error" in result

    def test_get_balance_tool_schema(self):
        """Test get_balance tool has correct schema."""
        from plugins.web3_plugin import GetBalanceTool

        tool = GetBalanceTool()

        assert tool.name == "get_balance"
        assert "address" in tool.parameters["properties"]


class TestSendCROTool:
    """Test SendCROTool."""

    @pytest.mark.asyncio
    async def test_send_cro_success(self):
        """Test sending CRO successfully."""
        from plugins.web3_plugin import SendCROTool

        tool = SendCROTool()
        to_address = "0x742d35Cc6634C0532925a3b844Bc9e7595f5c123"

        with patch("plugins.web3_plugin.get_web3") as mock_web3, patch(
            "plugins.web3_plugin.get_wallet"
        ) as mock_wallet:

            # Mock wallet
            mock_account = MagicMock()
            mock_account.address = "0x9858EfFD232B4033E47d90003D41EC34EcaEda94"
            mock_account.key = b"fake_key"
            mock_wallet.return_value = (mock_account, "mnemonic")

            # Mock web3
            mock_w3 = MagicMock()
            mock_w3.is_address.return_value = True
            mock_w3.to_checksum_address.return_value = to_address
            mock_w3.to_wei.return_value = 1000000000000000000
            mock_w3.eth.get_transaction_count.return_value = 5
            mock_w3.eth.gas_price = 5000000000
            mock_w3.eth.account.sign_transaction.return_value = MagicMock(
                raw_transaction=b"signed_tx"
            )
            mock_w3.eth.send_raw_transaction.return_value = bytes.fromhex(
                "abcd1234" * 8
            )
            mock_web3.return_value = mock_w3

            result = await tool.execute(to_address=to_address, amount="1.0")

            assert result["success"] is True
            assert "tx_hash" in result
            assert result["to"] == to_address
            assert result["amount_cro"] == "1.0"

    @pytest.mark.asyncio
    async def test_send_cro_invalid_address(self):
        """Test sending CRO to invalid address."""
        from plugins.web3_plugin import SendCROTool

        tool = SendCROTool()

        with patch("plugins.web3_plugin.get_web3") as mock_web3:
            mock_w3 = MagicMock()
            mock_w3.is_address.return_value = False
            mock_web3.return_value = mock_w3

            result = await tool.execute(to_address="invalid", amount="1.0")

            assert result["success"] is False
            assert "error" in result

    def test_send_cro_tool_schema(self):
        """Test send_cro tool has correct schema."""
        from plugins.web3_plugin import SendCROTool

        tool = SendCROTool()

        assert tool.name == "send_cro"
        assert "to_address" in tool.parameters["properties"]
        assert "amount" in tool.parameters["properties"]
        assert "to_address" in tool.parameters["required"]
        assert "amount" in tool.parameters["required"]


class TestGetTxCountTool:
    """Test GetTxCountTool."""

    @pytest.mark.asyncio
    async def test_get_tx_count_own_wallet(self):
        """Test getting tx count of own wallet."""
        from plugins.web3_plugin import GetTxCountTool

        tool = GetTxCountTool()

        with patch("plugins.web3_plugin.get_web3") as mock_web3:
            mock_w3 = MagicMock()
            mock_w3.is_address.return_value = True
            mock_w3.to_checksum_address.return_value = (
                "0x9858EfFD232B4033E47d90003D41EC34EcaEda94"
            )
            mock_w3.eth.get_transaction_count.return_value = 42
            mock_web3.return_value = mock_w3

            result = await tool.execute()

            assert result["success"] is True
            assert result["transaction_count"] == 42
            assert result["nonce"] == 42

    @pytest.mark.asyncio
    async def test_get_tx_count_specific_address(self):
        """Test getting tx count of specific address."""
        from plugins.web3_plugin import GetTxCountTool

        tool = GetTxCountTool()
        test_address = "0x742d35Cc6634C0532925a3b844Bc9e7595f5c123"

        with patch("plugins.web3_plugin.get_web3") as mock_web3:
            mock_w3 = MagicMock()
            mock_w3.is_address.return_value = True
            mock_w3.to_checksum_address.return_value = test_address
            mock_w3.eth.get_transaction_count.return_value = 100
            mock_web3.return_value = mock_w3

            result = await tool.execute(address=test_address)

            assert result["success"] is True
            assert result["address"] == test_address
            assert result["transaction_count"] == 100

    def test_get_tx_count_tool_schema(self):
        """Test get_tx_count tool has correct schema."""
        from plugins.web3_plugin import GetTxCountTool

        tool = GetTxCountTool()

        assert tool.name == "get_tx_count"
        assert "address" in tool.parameters["properties"]


class TestToolsIntegration:
    """Test tools integration with plugin system."""

    def test_plugin_tools_in_all_tools(self):
        """Test plugin tools are included in get_all_tools()."""
        from tools import get_all_tools

        tools = get_all_tools()
        tool_names = [t.name for t in tools]

        assert "wallet_info" in tool_names
        assert "get_balance" in tool_names
        assert "send_cro" in tool_names
        assert "get_tx_count" in tool_names

    def test_get_tool_by_name(self):
        """Test getting plugin tools by name."""
        from tools import get_tool_by_name

        wallet_tool = get_tool_by_name("wallet_info")
        assert wallet_tool is not None
        assert wallet_tool.name == "wallet_info"

        balance_tool = get_tool_by_name("get_balance")
        assert balance_tool is not None

    def test_openai_tools_format(self):
        """Test plugin tools are in OpenAI format."""
        from tools import get_openai_tools

        openai_tools = get_openai_tools()

        # Find wallet_info tool
        wallet_tool = None
        for tool in openai_tools:
            if tool["function"]["name"] == "wallet_info":
                wallet_tool = tool
                break

        assert wallet_tool is not None
        assert wallet_tool["type"] == "function"
        assert "description" in wallet_tool["function"]
        assert "parameters" in wallet_tool["function"]


class TestLiveNetwork:
    """Live network tests (run manually, skipped by default)."""

    @pytest.mark.skip(reason="Live network test - run manually")
    @pytest.mark.asyncio
    async def test_live_get_balance(self):
        """Test getting balance from live network."""
        from plugins.web3_plugin import GetBalanceTool

        tool = GetBalanceTool()
        # Use a known address with balance on Cronos testnet
        result = await tool.execute(
            address="0x0000000000000000000000000000000000000000"
        )

        print(f"Live balance result: {result}")
        assert result["success"] is True

    @pytest.mark.skip(reason="Live network test - run manually")
    @pytest.mark.asyncio
    async def test_live_wallet_info(self):
        """Test wallet info from live network."""
        from plugins.web3_plugin import WalletInfoTool

        tool = WalletInfoTool()
        result = await tool.execute()

        print(f"Live wallet info: {result}")
        assert result["success"] is True
        assert result["connected"] is True
