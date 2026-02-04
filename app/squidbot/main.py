#!/usr/bin/env python3
"""
SquidBot - Autonomous AI Agent

A Telegram bot with:
- Telegram bot interface
- OpenAI LLM with tool calling
- Autonomous tool chaining loop
- Persistent memory
- Web search
- Browser automation (Playwright)
- Proactive messaging (cron/heartbeat)
"""

import asyncio
import logging

from telegram import Update
from telegram.ext import (Application, CommandHandler, ContextTypes,
                          MessageHandler, filters)

from .agent import run_agent_with_history
from .config import TELEGRAM_BOT_TOKEN, validate_config
from .scheduler import Scheduler

# Setup logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Session storage (in-memory for simplicity)
sessions: dict[int, list[dict]] = {}

# Scheduler instance (initialized later)
scheduler: Scheduler | None = None


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command."""
    await update.message.reply_text(
        "Hello! I'm your autonomous AI assistant.\n\n"
        "I can:\n"
        "- Remember things you tell me\n"
        "- Search the web for information\n"
        "- Browse websites\n"
        "- Set reminders and scheduled tasks\n\n"
        "Just send me a message!"
    )


async def clear_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /clear command - clear session history."""
    chat_id = update.effective_chat.id
    sessions[chat_id] = []
    await update.message.reply_text("Conversation history cleared.")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle incoming messages."""
    chat_id = update.effective_chat.id
    user_message = update.message.text

    # Update scheduler's chat_id for proactive messages
    global scheduler
    if scheduler:
        scheduler.set_chat_id(chat_id)

    # Get or create session history
    if chat_id not in sessions:
        sessions[chat_id] = []

    # Send typing indicator
    await context.bot.send_chat_action(chat_id=chat_id, action="typing")

    try:
        # Run the agent
        response, updated_history = await run_agent_with_history(
            user_message, sessions[chat_id]
        )
        sessions[chat_id] = updated_history

        # Send response (split if too long)
        max_length = 4096
        if len(response) <= max_length:
            await update.message.reply_text(response)
        else:
            # Split into chunks
            for i in range(0, len(response), max_length):
                chunk = response[i : i + max_length]
                await update.message.reply_text(chunk)

        # Reload scheduler jobs in case new ones were created
        if scheduler:
            scheduler.reload_jobs()

    except Exception as e:
        logger.exception("Error handling message")
        await update.message.reply_text(f"Sorry, an error occurred: {str(e)}")


async def send_proactive_message(app: Application, chat_id: int, message: str):
    """Send a proactive message to a chat."""
    try:
        await app.bot.send_message(chat_id=chat_id, text=message)
    except Exception as e:
        logger.error(f"Failed to send proactive message: {e}")


def main():
    """Main entry point."""
    # Validate configuration
    validate_config()

    # Create application
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # Add handlers
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("clear", clear_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Setup scheduler
    global scheduler

    async def send_message(message: str):
        """Wrapper to send messages from scheduler."""
        # Get the most recent chat_id
        if scheduler and scheduler.chat_id:
            await send_proactive_message(app, scheduler.chat_id, message)

    async def run_agent_for_scheduler(prompt: str) -> str:
        """Run agent from scheduler context."""
        response, _ = await run_agent_with_history(prompt, [])
        return response

    scheduler = Scheduler(send_message=send_message, run_agent=run_agent_for_scheduler)

    # Start scheduler when bot starts
    async def post_init(application: Application):
        scheduler.start()
        logger.info("Bot and scheduler started")

    async def post_shutdown(application: Application):
        scheduler.stop()
        logger.info("Scheduler stopped")

    app.post_init = post_init
    app.post_shutdown = post_shutdown

    # Run the bot
    logger.info("Starting SquidBot...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
