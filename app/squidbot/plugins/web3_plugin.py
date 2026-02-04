"""
Web3 Plugin for SquidBot

Provides blockchain wallet functionality:
- Wallet from mnemonic or random generation
- Get balance
- Send CRO
- Get transaction count

Hooks:
- before_tool_call: Log and optionally block dangerous transactions
- after_tool_call: Log transaction results
"""

import logging
import os
from typing import Any

from dotenv import load_dotenv

from ..tools.base import Tool
from .base import Plugin, PluginApi, PluginManifest
from .hooks import (AfterToolCallEvent, BeforeToolCallEvent,
                    BeforeToolCallResult, HookContext, HookName)

logger = logging.getLogger(__name__)

# Load environment
load_dotenv()

# Configuration from environment
SQUIDBOT_MNEMONICS = os.environ.get("SQUIDBOT_MNEMONICS", "")
SQUIDBOT_WALLET_INDEX = int(os.environ.get("SQUIDBOT_WALLET_INDEX", "0"))
SQUIDBOT_CHAINID = int(os.environ.get("SQUIDBOT_CHAINID", "338"))
SQUIDBOT_RPC = os.environ.get("SQUIDBOT_RPC", "https://evm-dev-t3.cronos.org")


def get_web3():
    """Get Web3 instance connected to configured RPC."""
    try:
        from web3 import Web3

        w3 = Web3(Web3.HTTPProvider(SQUIDBOT_RPC))
        return w3
    except ImportError:
        logger.error("web3 package not installed. Run: pip install web3")
        raise


def get_wallet():
    """Get wallet from mnemonic or generate random."""
    try:
        from eth_account import Account

        Account.enable_unaudited_hdwallet_features()

        mnemonics = SQUIDBOT_MNEMONICS.strip()

        if not mnemonics:
            # Generate random mnemonic using os.urandom
            from mnemonic import Mnemonic

            mnemo = Mnemonic("english")
            entropy = os.urandom(16)  # 128 bits = 12 words
            mnemonics = mnemo.to_mnemonic(entropy)
            logger.info("Generated random wallet (mnemonic not configured)")
            logger.info(f"Random mnemonic: {mnemonics}")
            logger.warning("Set SQUIDBOT_MNEMONICS in .env to use a persistent wallet")

        # Derive account from mnemonic with wallet index
        account = Account.from_mnemonic(
            mnemonics, account_path=f"m/44'/60'/0'/0/{SQUIDBOT_WALLET_INDEX}"
        )
        return account, mnemonics

    except ImportError as e:
        logger.error(f"Required package not installed: {e}")
        logger.error("Run: pip install web3 mnemonic")
        raise


class WalletInfoTool(Tool):
    """Get wallet address and basic info."""

    @property
    def name(self) -> str:
        return "wallet_info"

    @property
    def description(self) -> str:
        return "Get the wallet address and chain information"

    @property
    def parameters(self) -> dict:
        return {"type": "object", "properties": {}, "required": []}

    async def execute(self, **kwargs) -> Any:
        try:
            account, _ = get_wallet()
            w3 = get_web3()

            return {
                "success": True,
                "address": account.address,
                "chain_id": SQUIDBOT_CHAINID,
                "rpc_url": SQUIDBOT_RPC,
                "wallet_index": SQUIDBOT_WALLET_INDEX,
                "connected": w3.is_connected(),
            }
        except Exception as e:
            return {"success": False, "error": str(e)}


class GetBalanceTool(Tool):
    """Get wallet balance in CRO."""

    @property
    def name(self) -> str:
        return "get_balance"

    @property
    def description(self) -> str:
        return "Get the CRO balance of the wallet or a specified address"

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "address": {
                    "type": "string",
                    "description": "Address to check balance (optional, defaults to wallet address)",
                }
            },
            "required": [],
        }

    async def execute(self, address: str = "", **kwargs) -> Any:
        try:
            w3 = get_web3()

            if not address:
                account, _ = get_wallet()
                address = account.address

            # Validate address
            if not w3.is_address(address):
                return {"success": False, "error": f"Invalid address: {address}"}

            checksum_address = w3.to_checksum_address(address)
            balance_wei = w3.eth.get_balance(checksum_address)
            balance_cro = w3.from_wei(balance_wei, "ether")

            return {
                "success": True,
                "address": checksum_address,
                "balance_wei": str(balance_wei),
                "balance_cro": str(balance_cro),
                "unit": "CRO",
            }
        except Exception as e:
            return {"success": False, "error": str(e)}


class SendCROTool(Tool):
    """Send CRO to an address."""

    @property
    def name(self) -> str:
        return "send_cro"

    @property
    def description(self) -> str:
        return "Send CRO to a specified address"

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "to_address": {
                    "type": "string",
                    "description": "Recipient address",
                },
                "amount": {
                    "type": "string",
                    "description": "Amount of CRO to send (e.g., '1.5')",
                },
            },
            "required": ["to_address", "amount"],
        }

    async def execute(self, to_address: str, amount: str, **kwargs) -> Any:
        try:
            w3 = get_web3()
            account, _ = get_wallet()

            # Validate recipient address
            if not w3.is_address(to_address):
                return {"success": False, "error": f"Invalid address: {to_address}"}

            to_checksum = w3.to_checksum_address(to_address)
            amount_wei = w3.to_wei(float(amount), "ether")

            # Get current nonce
            nonce = w3.eth.get_transaction_count(account.address)

            # Build transaction
            tx = {
                "nonce": nonce,
                "to": to_checksum,
                "value": amount_wei,
                "gas": 21000,  # Standard ETH transfer
                "gasPrice": w3.eth.gas_price,
                "chainId": SQUIDBOT_CHAINID,
            }

            # Sign and send
            signed_tx = w3.eth.account.sign_transaction(tx, account.key)
            tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)

            return {
                "success": True,
                "tx_hash": tx_hash.hex(),
                "from": account.address,
                "to": to_checksum,
                "amount_cro": amount,
                "amount_wei": str(amount_wei),
                "chain_id": SQUIDBOT_CHAINID,
            }
        except Exception as e:
            return {"success": False, "error": str(e)}


class GetTxCountTool(Tool):
    """Get transaction count (nonce) for an address."""

    @property
    def name(self) -> str:
        return "get_tx_count"

    @property
    def description(self) -> str:
        return "Get the transaction count (nonce) for the wallet or a specified address"

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "address": {
                    "type": "string",
                    "description": "Address to check (optional, defaults to wallet address)",
                }
            },
            "required": [],
        }

    async def execute(self, address: str = "", **kwargs) -> Any:
        try:
            w3 = get_web3()

            if not address:
                account, _ = get_wallet()
                address = account.address

            # Validate address
            if not w3.is_address(address):
                return {"success": False, "error": f"Invalid address: {address}"}

            checksum_address = w3.to_checksum_address(address)
            tx_count = w3.eth.get_transaction_count(checksum_address)

            return {
                "success": True,
                "address": checksum_address,
                "transaction_count": tx_count,
                "nonce": tx_count,  # Alias for clarity
            }
        except Exception as e:
            return {"success": False, "error": str(e)}


class Web3Plugin(Plugin):
    """Web3 blockchain plugin for SquidBot."""

    @property
    def manifest(self) -> PluginManifest:
        return PluginManifest(
            id="web3",
            name="Web3 Plugin",
            description="Blockchain wallet functionality for Cronos chain",
            version="1.0.0",
            author="SquidBot",
            config_schema={
                "type": "object",
                "properties": {
                    "SQUIDBOT_MNEMONICS": {
                        "type": "string",
                        "description": "BIP39 mnemonic phrase (12 or 24 words)",
                    },
                    "SQUIDBOT_WALLET_INDEX": {
                        "type": "integer",
                        "description": "HD wallet derivation index",
                        "default": 0,
                    },
                    "SQUIDBOT_CHAINID": {
                        "type": "integer",
                        "description": "Blockchain chain ID",
                        "default": 338,
                    },
                    "SQUIDBOT_RPC": {
                        "type": "string",
                        "description": "RPC endpoint URL",
                        "default": "https://evm-dev-t3.cronos.org",
                    },
                },
            },
        )

    def get_tools(self) -> list[Tool]:
        return [
            WalletInfoTool(),
            GetBalanceTool(),
            SendCROTool(),
            GetTxCountTool(),
        ]

    def register_hooks(self, api: PluginApi) -> None:
        """Register hooks for transaction monitoring."""

        # Hook: Before tool call - monitor and optionally block transactions
        async def on_before_tool_call(
            event: BeforeToolCallEvent, ctx: HookContext
        ) -> BeforeToolCallResult | None:
            # Only interested in web3 tools
            if event.tool_name not in (
                "send_cro",
                "get_balance",
                "wallet_info",
                "get_tx_count",
            ):
                return None

            logger.info(f"[Web3 Hook] Before {event.tool_name}: {event.params}")

            # Example: Block large transactions (over 100 CRO)
            if event.tool_name == "send_cro":
                amount = float(event.params.get("amount", 0))
                if amount > 100:
                    logger.warning(
                        f"[Web3 Hook] Blocking large transaction: {amount} CRO"
                    )
                    return BeforeToolCallResult(
                        block=True,
                        block_reason=f"Transaction amount {amount} CRO exceeds limit of 100 CRO",
                    )

            return None

        # Hook: After tool call - log results
        async def on_after_tool_call(
            event: AfterToolCallEvent, ctx: HookContext
        ) -> None:
            # Only interested in web3 tools
            if event.tool_name not in (
                "send_cro",
                "get_balance",
                "wallet_info",
                "get_tx_count",
            ):
                return

            if event.error:
                logger.error(f"[Web3 Hook] {event.tool_name} failed: {event.error}")
            else:
                logger.info(
                    f"[Web3 Hook] {event.tool_name} completed in {event.duration_ms:.2f}ms"
                )

                # Log transaction hash for send_cro
                if event.tool_name == "send_cro" and isinstance(event.result, dict):
                    tx_hash = event.result.get("tx_hash")
                    if tx_hash:
                        logger.info(f"[Web3 Hook] Transaction hash: {tx_hash}")

        # Register hooks with priority
        api.on(HookName.BEFORE_TOOL_CALL, on_before_tool_call, priority=10)
        api.on(HookName.AFTER_TOOL_CALL, on_after_tool_call, priority=10)

    def activate(self) -> None:
        logger.info(f"Web3 Plugin activated - Chain ID: {SQUIDBOT_CHAINID}")
        logger.info(f"RPC: {SQUIDBOT_RPC}")

        # Log wallet status (not the actual mnemonic for security)
        if SQUIDBOT_MNEMONICS:
            logger.info("Using configured mnemonic")
        else:
            logger.info("No mnemonic configured - will generate random wallet")

    def deactivate(self) -> None:
        logger.info("Web3 Plugin deactivated")


def get_plugin() -> Plugin:
    """Factory function to create plugin instance."""
    return Web3Plugin()
