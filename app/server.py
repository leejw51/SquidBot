#!/usr/bin/env python3
"""
SquidBot Server

Runs the Telegram bot (optional) and exposes a local TCP port for client connections.
Supports multiple channels via the session/lane abstraction.
"""
import asyncio
import json
import logging
import signal

from agent import run_agent_with_history
from channels import (ChannelRouter, MessagePayload, TCPAdapter,
                      TelegramAdapter, get_channel_router)
from config import OPENAI_API_KEY, SQUID_PORT, TELEGRAM_BOT_TOKEN
from lanes import LANE_CRON, LANE_MAIN, CommandLane
from scheduler import Scheduler
from session import (ChannelType, DeliveryContext, Session,
                     get_session_manager, record_inbound_session)

# Server configuration
SERVER_HOST = "127.0.0.1"
SERVER_PORT = SQUID_PORT

# Setup logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Connected TCP clients (for broadcasting scheduled messages)
connected_clients: dict[str, asyncio.StreamWriter] = {}

# Scheduler instance
scheduler: Scheduler | None = None

# Telegram app instance (for sending proactive messages)
telegram_app = None

# Server running flag
running = True

# Session manager
session_manager = get_session_manager()

# Channel router for multi-channel broadcasting
channel_router = get_channel_router()


# ============================================================
# Message broadcasting
# ============================================================


async def broadcast_to_clients(message: str):
    """Send a message to all connected TCP clients via channel router."""
    if not connected_clients:
        logger.info(f"[Broadcast] No clients connected: {message[:50]}...")
        return

    payload = MessagePayload(text=message)
    for client_id in list(connected_clients.keys()):
        context = DeliveryContext(
            channel=ChannelType.TCP,
            recipient_id=client_id,
        )
        success = await channel_router.send(context, payload)
        if success:
            logger.info(f"[Broadcast] Sent to {client_id}")
        else:
            # Remove disconnected clients
            connected_clients.pop(client_id, None)


async def send_to_telegram(message: str):
    """Send a message to Telegram if connected."""
    global telegram_app, scheduler

    if not telegram_app or not scheduler or not scheduler.chat_id:
        return

    context = DeliveryContext(
        channel=ChannelType.TELEGRAM,
        recipient_id=str(scheduler.chat_id),
    )
    payload = MessagePayload(text=message)

    success = await channel_router.send(context, payload)
    if success:
        logger.info(f"[Telegram] Sent message to chat {scheduler.chat_id}")


async def send_scheduled_message(message: str):
    """Send scheduled message to all active channels."""
    logger.info(f"[Scheduled] {message[:100]}...")

    # Broadcast to all active sessions
    contexts = session_manager.get_active_delivery_contexts()
    payload = MessagePayload(text=message)

    if contexts:
        results = await channel_router.broadcast(contexts, payload)
        success_count = sum(1 for v in results.values() if v)
        logger.info(f"[Scheduled] Broadcast to {success_count}/{len(results)} channels")
    else:
        # Fallback to legacy broadcast
        await broadcast_to_clients(message)
        await send_to_telegram(message)


# ============================================================
# Local TCP server for client connections
# ============================================================


async def handle_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    """Handle a local client connection."""
    addr = writer.get_extra_info("peername")
    client_id = f"{addr[0]}:{addr[1]}"
    logger.info(f"Client connected: {client_id}")

    # Register client for broadcasts
    connected_clients[client_id] = writer

    # Get or create session for this TCP client
    session = record_inbound_session(
        channel=ChannelType.TCP,
        recipient_id=client_id,
        lane=LANE_MAIN,
        delivery_context=DeliveryContext(
            channel=ChannelType.TCP,
            recipient_id=client_id,
        ),
    )

    try:
        while True:
            # Read message (newline-delimited JSON)
            data = await reader.readline()
            if not data:
                break

            try:
                request = json.loads(data.decode().strip())
                command = request.get("command", "chat")
                message = request.get("message", "")

                if command == "chat":
                    # Run agent with session history
                    response, updated_history = await run_agent_with_history(
                        message, session.history
                    )
                    session.history = updated_history
                    session_manager.update(session)

                    # Reload scheduler jobs in case new ones were created
                    if scheduler:
                        scheduler.reload_jobs()

                    reply = {"status": "ok", "response": response}

                elif command == "clear":
                    session.clear_history()
                    session_manager.update(session)
                    reply = {"status": "ok", "response": "Conversation cleared."}

                elif command == "ping":
                    reply = {"status": "ok", "response": "pong"}

                else:
                    reply = {
                        "status": "error",
                        "response": f"Unknown command: {command}",
                    }

            except json.JSONDecodeError:
                reply = {"status": "error", "response": "Invalid JSON"}
            except Exception as e:
                logger.exception("Error processing client request")
                reply = {"status": "error", "response": str(e)}

            # Send response
            response_data = json.dumps(reply) + "\n"
            writer.write(response_data.encode())
            await writer.drain()

    except asyncio.CancelledError:
        pass
    except Exception as e:
        logger.error(f"Client error: {e}")
    finally:
        logger.info(f"Client disconnected: {client_id}")
        connected_clients.pop(client_id, None)
        writer.close()
        await writer.wait_closed()


async def run_tcp_server():
    """Run the local TCP server."""
    server = await asyncio.start_server(handle_client, SERVER_HOST, SERVER_PORT)
    logger.info(f"TCP server listening on {SERVER_HOST}:{SERVER_PORT}")

    async with server:
        await server.serve_forever()


# ============================================================
# Telegram bot (optional)
# ============================================================


async def send_response_with_images(update, response: str):
    """Send response to Telegram, extracting and sending any screenshots as photos."""
    import os
    import re

    max_length = 4096

    # Find all screenshots in response - multiple patterns
    screenshots = []

    # Pattern 1: [SCREENSHOT:path]
    pattern1 = r"\[SCREENSHOT:([^\]]+)\]"
    screenshots.extend(re.findall(pattern1, response))

    # Pattern 2: backtick-wrapped paths like `/.../squidbot_screenshot_*.png`
    pattern2 = r"`([^`]*squidbot_screenshot_[^`]+\.png)`"
    screenshots.extend(re.findall(pattern2, response))

    # Pattern 3: plain paths /tmp/squidbot_screenshot_*.png or /var/folders/.../squidbot_screenshot_*.png
    pattern3 = r"(/(?:tmp|var/folders)[^\s`]*squidbot_screenshot_[^\s`]+\.png)"
    screenshots.extend(re.findall(pattern3, response))

    # Deduplicate
    screenshots = list(set(screenshots))

    # Remove screenshot paths from text response
    text_response = response
    text_response = re.sub(pattern1 + r"[^\n]*\n?", "", text_response)
    text_response = re.sub(
        r"Saved at:\s*\n?\s*" + pattern2 + r"\s*\n?", "", text_response
    )
    text_response = re.sub(pattern2, "", text_response)
    text_response = text_response.strip()

    # Send text response if any
    if text_response:
        if len(text_response) <= max_length:
            await update.message.reply_text(text_response)
        else:
            for i in range(0, len(text_response), max_length):
                chunk = text_response[i : i + max_length]
                await update.message.reply_text(chunk)

    # Send screenshots as photos
    for screenshot_path in screenshots:
        if os.path.exists(screenshot_path):
            try:
                with open(screenshot_path, "rb") as photo:
                    await update.message.reply_photo(photo=photo, caption="Screenshot")
                # Clean up temp file
                os.remove(screenshot_path)
                logger.info(f"Sent screenshot: {screenshot_path}")
            except Exception as e:
                logger.error(f"Failed to send screenshot: {e}")


async def run_telegram_bot():
    """Run the Telegram bot."""
    global telegram_app

    from telegram import Update
    from telegram.ext import (Application, CommandHandler, ContextTypes,
                              MessageHandler, filters)

    async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(
            "Hello! I'm SquidBot, your autonomous AI assistant.\n\n"
            "I can:\n"
            "- Remember things you tell me\n"
            "- Search the web for information\n"
            "- Browse websites\n"
            "- Set reminders and scheduled tasks\n\n"
            "Just send me a message!"
        )

    async def clear_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
        chat_id = update.effective_chat.id
        session = session_manager.get(ChannelType.TELEGRAM, str(chat_id))
        if session:
            session.clear_history()
            session_manager.update(session)
        await update.message.reply_text("Conversation history cleared.")

    async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
        chat_id = update.effective_chat.id
        user_message = update.message.text

        global scheduler
        if scheduler:
            scheduler.set_chat_id(chat_id)

        # Get or create session for this Telegram chat
        session = record_inbound_session(
            channel=ChannelType.TELEGRAM,
            recipient_id=str(chat_id),
            lane=LANE_MAIN,
            delivery_context=DeliveryContext(
                channel=ChannelType.TELEGRAM,
                recipient_id=str(chat_id),
                thread_id=(
                    str(update.message.message_thread_id)
                    if update.message.message_thread_id
                    else None
                ),
            ),
        )

        await context.bot.send_chat_action(chat_id=chat_id, action="typing")

        try:
            response, updated_history = await run_agent_with_history(
                user_message, session.history
            )
            session.history = updated_history
            session_manager.update(session)

            # Check for screenshots in response
            await send_response_with_images(update, response)

            if scheduler:
                scheduler.reload_jobs()

        except Exception as e:
            logger.exception("Error handling message")
            await update.message.reply_text(f"Sorry, an error occurred: {str(e)}")

    # Create application
    telegram_app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    telegram_app.add_handler(CommandHandler("start", start_command))
    telegram_app.add_handler(CommandHandler("clear", clear_command))
    telegram_app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)
    )

    # Initialize and run
    await telegram_app.initialize()
    await telegram_app.start()

    # Register Telegram channel adapter
    channel_router.register(TelegramAdapter(telegram_app.bot))
    await telegram_app.updater.start_polling(allowed_updates=Update.ALL_TYPES)

    # Wait until stopped
    while running:
        await asyncio.sleep(1)

    # Cleanup
    await telegram_app.updater.stop()
    await telegram_app.stop()
    await telegram_app.shutdown()


# ============================================================
# Main
# ============================================================


async def async_main():
    """Async main entry point."""
    global running, scheduler

    # Validate OpenAI key (required)
    if not OPENAI_API_KEY:
        logger.error("OPENAI_API_KEY not set")
        return

    # Register TCP channel adapter
    def get_tcp_writer(client_id: str):
        return connected_clients.get(client_id)

    channel_router.register(TCPAdapter(get_tcp_writer))

    # Setup scheduler with proper send_message callback
    async def run_agent_for_scheduler(prompt: str) -> str:
        response, _ = await run_agent_with_history(prompt, [])
        return response

    scheduler = Scheduler(
        send_message=send_scheduled_message, run_agent=run_agent_for_scheduler
    )
    scheduler.start()

    # Start tasks
    tasks = []

    # Always run TCP server
    tasks.append(asyncio.create_task(run_tcp_server()))
    logger.info("SquidBot server started")
    logger.info(f"  - Local client: {SERVER_HOST}:{SERVER_PORT}")

    # Optionally run Telegram bot
    if TELEGRAM_BOT_TOKEN:
        tasks.append(asyncio.create_task(run_telegram_bot()))
        logger.info(f"  - Telegram bot: active")
    else:
        logger.info(f"  - Telegram bot: disabled (no token)")

    # Handle shutdown
    def signal_handler():
        global running
        running = False
        logger.info("Shutting down...")

    loop = asyncio.get_event_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, signal_handler)

    # Wait for tasks
    try:
        await asyncio.gather(*tasks)
    except asyncio.CancelledError:
        pass
    finally:
        scheduler.stop()
        logger.info("SquidBot server stopped")


def main():
    """Main entry point."""
    logger.info("Starting SquidBot server...")
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
