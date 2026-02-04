# SquidBot

<p align="center">
  <img src="squidbot.png" alt="SquidBot" width="200">
</p>

An autonomous AI agent with Telegram integration, persistent memory, web search, browser automation, and scheduled tasks.

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

## Environment Setup

Create a `.env` file in the `app/` directory:

```bash
TELEGRAM_BOT_TOKEN=your_telegram_bot_token    # From @BotFather
OPENAI_API_KEY=your_openai_api_key            # From OpenAI
```

### Getting API Keys

1. **Telegram Bot Token**: Message [@BotFather](https://t.me/BotFather) on Telegram, use `/newbot` command
2. **OpenAI API Key**: Get from [OpenAI Platform](https://platform.openai.com/api-keys)

## Quick Start

```bash
# Start the server
squidbot start

# Run the chat client
squidbot-client

# Check status
squidbot status

# Stop the server
squidbot stop
```

## Documentation

See [app/README.md](app/README.md) for full documentation including:
- Skills system
- Character configuration
- Available tools
- Plugin system
- Web3 integration
- Makefile commands

## License

MIT
