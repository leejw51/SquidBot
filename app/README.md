# SquidBot

<p align="center">
  <img src="squidbot.png" alt="SquidBot" width="200">
</p>

An autonomous AI agent with Telegram integration, persistent memory, web search, browser automation, and scheduled tasks.

## Features

- **Telegram Bot Interface** - Chat with your AI assistant via Telegram
- **OpenAI LLM** - Powered by GPT-4o with tool calling
- **Autonomous Tool Chaining** - Agent can chain multiple tools to complete complex tasks
- **Persistent Memory** - Remembers information across sessions (SQLite + vector search)
- **Web Search** - Search the web for current information
- **Browser Automation** - Browse and interact with websites via Playwright
- **Scheduled Tasks** - Set reminders and recurring tasks with cron expressions
- **Coding Agent** - Write, run, and test Zig and Python code in isolated workspace
- **Plugin System** - Extend functionality with plugins and lifecycle hooks
- **Web3 Integration** - Blockchain wallet with balance checking and CRO transfers
- **Custom Skills** - Extend agent behavior with markdown skill files
- **Custom Character** - Define AI personality and communication style

## Installation

### From PyPI (Recommended)

```bash
pip install squidbot
```

### From Source

```bash
git clone https://github.com/leejw51/SquidBot.git
cd SquidBot/app
pip install -e .
```

## Quick Start

```bash
# Configure environment
cp .env.example .env
# Edit .env with your API keys

# Start the server
squidbot start

# Run the chat client (optional - for terminal chat)
squidbot-client
```

### Alternative: Using Make (from source)

```bash
cd app
make install
make start
make client
```

## Environment Variables

Create a `.env` file in the `app/` directory:

```bash
# Required
TELEGRAM_BOT_TOKEN=your_telegram_bot_token    # From @BotFather
OPENAI_API_KEY=your_openai_api_key            # From OpenAI

# Optional - Model
OPENAI_MODEL=gpt-4o                           # Default: gpt-4o

# Optional - Proactive messaging
HEARTBEAT_INTERVAL_MINUTES=30                 # Default: 30

# Optional - Local server port
SQUID_PORT=7777                               # Default: 7777

# Optional - Home directory for all data
SQUIDBOT_HOME=~/.squidbot                     # Default: ~/.squidbot

# Optional - AI Character/Personality
CHARACTER_NAME=Assistant                      # Bot's name
CHARACTER_PERSONA=You are a helpful assistant # Personality description
CHARACTER_STYLE=helpful, friendly, concise    # Communication style

# Optional - Web3 Plugin (Blockchain)
SQUIDBOT_MNEMONICS=                           # BIP39 mnemonic (random if empty)
SQUIDBOT_WALLET_INDEX=0                       # HD wallet derivation index
SQUIDBOT_CHAINID=338                          # Chain ID (338 = Cronos testnet)
SQUIDBOT_RPC=https://evm-dev-t3.cronos.org    # RPC endpoint URL
```

### Getting API Keys

1. **Telegram Bot Token**: Message [@BotFather](https://t.me/BotFather) on Telegram, use `/newbot` command
2. **OpenAI API Key**: Get from [OpenAI Platform](https://platform.openai.com/api-keys)

## Skills System

Skills are markdown files that teach the agent specific behaviors. They are loaded from `~/.squidbot/skills/`.

### Directory Structure

```
~/.squidbot/
├── skills/
│   ├── weather/
│   │   └── SKILL.md
│   ├── search/
│   │   └── SKILL.md
│   └── reminder/
│       └── SKILL.md
├── CHARACTER.md          # Optional character definition
└── memory.db             # SQLite memory database
```

### Skill File Format

Each skill is a directory containing a `SKILL.md` file with YAML frontmatter:

```markdown
---
name: search
description: Search the web for information
---
When user asks a question requiring current information:

1. Use `web_search` tool with a clear query
2. Review the results
3. Synthesize a helpful answer with sources

Always cite sources when providing factual information.
```

### Example Skills

**Reminder Skill** (`~/.squidbot/skills/reminder/SKILL.md`):
```markdown
---
name: reminder
description: Set reminders and scheduled tasks
---
When user wants to set a reminder:

1. Extract the message and time
2. Use `cron_create` tool with appropriate delay_minutes or cron_expression
3. Confirm the reminder was set

Examples:
- "Remind me in 10 minutes" → delay_minutes=10
- "Remind me daily at 9am" → cron_expression="0 9 * * *"
```

### Template Skills

Example skills are provided in `app/skills_template/`:
- `search/` - Web search behavior
- `reminder/` - Setting reminders
- `summarize/` - Summarizing content

Copy these to `~/.squidbot/skills/` to use them.

## Character Configuration

Define your AI's personality in `~/.squidbot/CHARACTER.md`:

```markdown
# Character Definition

You are a helpful AI assistant with the following traits:

## Personality
- Friendly and approachable
- Patient and thorough
- Honest about limitations

## Communication Style
- Clear and concise responses
- Use examples when helpful
- Ask clarifying questions when needed
```

## Available Tools

| Tool | Description |
|------|-------------|
| `memory_store` | Store information for later recall |
| `memory_search` | Search stored memories |
| `web_search` | Search the web |
| `browser_navigate` | Navigate to a URL |
| `browser_get_text` | Extract text from current page |
| `browser_screenshot` | Take a screenshot |
| `cron_create` | Create scheduled tasks |
| `cron_list` | List scheduled tasks |
| `cron_delete` | Delete a scheduled task |
| `code_write` | Write Zig or Python code to workspace |
| `code_read` | Read code from workspace |
| `code_run` | Execute Zig or Python files |
| `code_list` | List projects and files |
| `code_delete` | Delete files or projects |
| `zig_build` | Build Zig projects (with release option) |
| `zig_test` | Run Zig tests |
| `python_test` | Run Python tests with pytest |
| `wallet_info` | Get wallet address and chain info (Web3 Plugin) |
| `get_balance` | Get CRO balance of wallet or address (Web3 Plugin) |
| `send_cro` | Send CRO to an address (Web3 Plugin) |
| `get_tx_count` | Get transaction count/nonce (Web3 Plugin) |

## Coding Agent

The coding agent allows the AI to write, run, and test code in an isolated workspace. It supports **Zig** and **Python**.

### Workspace Structure

```
~/.squidbot/coding/
├── my_project/
│   ├── main.py
│   ├── utils.py
│   └── test_main.py
├── zig_project/
│   ├── main.zig
│   └── build.zig
└── algorithms/
    └── sort.zig
```

### Supported Languages

| Language | Extensions | Features |
|----------|------------|----------|
| **Python** | `.py` | Run scripts, pytest integration, multi-file imports |
| **Zig** | `.zig` | Compile & run, build with release optimization, built-in test runner |

### Example Usage

```
User: Write a Python function to calculate fibonacci numbers and test it

Agent: [Uses code_write to create fibonacci.py]
       [Uses code_write to create test_fibonacci.py]
       [Uses python_test to run the tests]
       All 3 tests passed!

User: Now write the same in Zig

Agent: [Uses code_write to create fibonacci.zig with tests]
       [Uses zig_test to run the tests]
       All tests passed!
```

### Requirements

- **Python**: Uses the same Python interpreter as SquidBot
- **Zig**: Optional - install from [ziglang.org](https://ziglang.org/download/) for Zig support

## Plugin System

SquidBot supports a modular plugin architecture for extending functionality. Plugins can provide tools and register lifecycle hooks.

### Plugin Structure

```
app/plugins/
├── __init__.py       # Plugin exports
├── base.py           # Plugin base class
├── hooks.py          # Hook system
├── loader.py         # Plugin loader/registry
└── web3_plugin.py    # Web3 blockchain plugin
```

### Creating a Plugin

```python
from plugins.base import Plugin, PluginApi, PluginManifest
from plugins.hooks import HookName, BeforeToolCallEvent, BeforeToolCallResult
from tools.base import Tool

class MyPlugin(Plugin):
    @property
    def manifest(self) -> PluginManifest:
        return PluginManifest(
            id="my-plugin",
            name="My Plugin",
            description="A custom plugin",
            version="1.0.0",
        )

    def get_tools(self) -> list[Tool]:
        return [MyCustomTool()]

    def register_hooks(self, api: PluginApi) -> None:
        api.on(HookName.BEFORE_TOOL_CALL, self.on_before_tool, priority=10)

    async def on_before_tool(self, event: BeforeToolCallEvent, ctx) -> BeforeToolCallResult | None:
        # Intercept and optionally block tool calls
        if event.tool_name == "dangerous_tool":
            return BeforeToolCallResult(block=True, block_reason="Blocked!")
        return None

def get_plugin() -> Plugin:
    return MyPlugin()
```

### Available Hooks

| Hook | Type | Description |
|------|------|-------------|
| `before_agent_start` | Modifying | Inject context into system prompt |
| `agent_end` | Void | React to agent completion |
| `message_received` | Void | Intercept incoming messages |
| `message_sending` | Modifying | Modify or cancel outgoing messages |
| `message_sent` | Void | React to message delivery |
| `before_tool_call` | Modifying | Block or modify tool parameters |
| `after_tool_call` | Void | Log or react to tool results |
| `session_start` | Void | Track session start |
| `session_end` | Void | Track session end |

**Hook Types:**
- **Void**: Fire-and-forget, runs in parallel
- **Modifying**: Sequential execution, can return modified results

### Hook Priority

Hooks with higher priority run first. Default priority is 0.

```python
api.on(HookName.BEFORE_TOOL_CALL, handler, priority=100)  # Runs first
api.on(HookName.BEFORE_TOOL_CALL, handler, priority=10)   # Runs second
api.on(HookName.BEFORE_TOOL_CALL, handler)                # Runs last (priority=0)
```

## Web3 Plugin

The Web3 plugin provides blockchain wallet functionality for the Cronos chain.

### Features

- **Wallet Management**: Create wallet from mnemonic or generate random
- **Balance Checking**: Query CRO balance for any address
- **Send Transactions**: Transfer CRO to other addresses
- **Transaction Count**: Get nonce for an address

### Configuration

Set these environment variables in `.env`:

```bash
SQUIDBOT_MNEMONICS=word1 word2 ... word12    # BIP39 mnemonic (12 or 24 words)
SQUIDBOT_WALLET_INDEX=0                       # HD derivation index
SQUIDBOT_CHAINID=338                          # 338=Cronos testnet, 25=Cronos mainnet
SQUIDBOT_RPC=https://evm-dev-t3.cronos.org    # RPC endpoint
```

If `SQUIDBOT_MNEMONICS` is not set, a random wallet is generated on each startup.

### Web3 Tools

| Tool | Description |
|------|-------------|
| `wallet_info` | Get wallet address, chain ID, and connection status |
| `get_balance` | Get CRO balance (own wallet or specified address) |
| `send_cro` | Send CRO to an address (requires amount and recipient) |
| `get_tx_count` | Get transaction count (nonce) for address |

### Security Hooks

The Web3 plugin includes security hooks:
- **Transaction Limit**: Blocks transactions over 100 CRO by default
- **Logging**: All Web3 tool calls are logged with results

### Example Usage

```
User: What's my wallet address?
Agent: [Uses wallet_info]
       Your wallet address is 0x1aac...05aA on Cronos testnet (chain 338)

User: Check my balance
Agent: [Uses get_balance]
       Your balance is 803.16 CRO

User: Send 10 CRO to 0x1961...37d6
Agent: [Uses send_cro]
       Sent 10 CRO to 0x1961...37d6
       Transaction hash: 0x9680c829...
```

## Makefile Commands

### Server Management

| Command | Description |
|---------|-------------|
| `make start` | Start the server as a background daemon |
| `make stop` | Stop the server |
| `make stopall` | Stop server and kill all clients |
| `make restart` | Restart the server |
| `make status` | Show server status |
| `make logs` | Show recent server logs |
| `make logs-follow` | Follow logs in real-time (tail -f) |
| `make server` | Run server in foreground (for debugging) |
| `make client` | Run the terminal chat client |

### Installation

| Command | Description |
|---------|-------------|
| `make install` | Install dependencies with pip |
| `make install-dev` | Install with dev dependencies (pytest, coverage) |
| `make poetry-install` | Install with Poetry |
| `make poetry-install-dev` | Install dev dependencies with Poetry |

### Testing

| Command | Description |
|---------|-------------|
| `make test` | Run unit tests only |
| `make testall` | Run all tests (unit + integration) |
| `make integrationtest` | Run integration tests only |
| `make test-verbose` | Run unit tests with extra output |
| `make test-cov` | Run unit tests with coverage report |
| `make test-memory` | Run memory tests only |
| `make test-tools` | Run tool tests only |
| `make test-chaining` | Run tool chaining tests |
| `make test-proactive` | Run proactive messaging tests |
| `make test-coding` | Run coding agent tests (Zig/Python) |
| `make test-session` | Run session management tests |
| `make test-sqlite-vec` | Run vector search tests |

### Packaging

| Command | Description |
|---------|-------------|
| `make package` | Build standalone binary using PyInstaller |
| `make package-debug` | Build binary with console output (for debugging) |
| `make package-clean` | Remove PyInstaller build artifacts |

### Cleanup

| Command | Description |
|---------|-------------|
| `make clean` | Remove all cache and build files |

### Poetry Commands

| Command | Description |
|---------|-------------|
| `make poetry-test` | Run tests via Poetry |
| `make poetry-start` | Start server via Poetry |
| `make poetry-stop` | Stop server via Poetry |
| `make poetry-client` | Run client via Poetry |

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         SquidBot Server                             │
├─────────────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐          │
│  │  Telegram   │  │   TCP/HTTP  │  │    Scheduler        │          │
│  │    Bot      │  │   Clients   │  │  (cron/heartbeat)   │          │
│  └──────┬──────┘  └──────┬──────┘  └──────────┬──────────┘          │
│         │                │                    │                     │
│         └────────────────┼────────────────────┘                     │
│                          ▼                                          │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                    Plugin System                             │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │   │
│  │  │   Hooks     │  │  Registry   │  │    Plugin Loader    │  │   │
│  │  │  (10 types) │  │  (tools)    │  │   (auto-discovery)  │  │   │
│  │  └─────────────┘  └─────────────┘  └─────────────────────┘  │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                          │                                          │
│                          ▼                                          │
│                    ┌───────────┐                                    │
│                    │   Agent   │ ◄── Skills + Character             │
│                    │  (GPT-4o) │                                    │
│                    └─────┬─────┘                                    │
│                          │                                          │
│    ┌──────────┬──────────┼──────────┬──────────┬──────────┐        │
│    ▼          ▼          ▼          ▼          ▼          ▼        │
│ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ │
│ │ Memory │ │  Web   │ │Browser │ │  Cron  │ │ Coding │ │  Web3  │ │
│ │(SQLite)│ │ Search │ │  Auto  │ │  Jobs  │ │  Agent │ │ Plugin │ │
│ └────────┘ └────────┘ └────────┘ └────────┘ └────────┘ └────────┘ │
└─────────────────────────────────────────────────────────────────────┘
```

## Data Storage

All user data is stored in `~/.squidbot/` (or `$SQUIDBOT_HOME` if set).

On first startup, SquidBot automatically creates:
- Default `CHARACTER.md` with a helpful assistant personality
- Default skills (`search/` and `reminder/`)
- All required directories

**Startup Info**: When the server starts, it displays configuration info:
```
============================================================
  SquidBot Configuration
============================================================
  Home Directory : /Users/you/.squidbot
  Server Port    : 7777
  Model          : gpt-4o
  Heartbeat      : 30 minutes
------------------------------------------------------------
  Character File : /Users/you/.squidbot/CHARACTER.md
  Skills Dir     : /Users/you/.squidbot/skills
  Coding Dir     : /Users/you/.squidbot/coding
  Sessions Dir   : /Users/you/.squidbot/sessions
============================================================
```

| File | Description |
|------|-------------|
| `memory.db` | SQLite database with vector embeddings (WAL mode) |
| `cron_jobs.json` | Scheduled tasks |
| `CHARACTER.md` | AI character definition |
| `skills/` | Custom skill definitions |
| `coding/` | Coding agent workspace (Zig & Python projects) |
| `sessions/` | Session transcripts (JSONL format) |

## License

MIT
