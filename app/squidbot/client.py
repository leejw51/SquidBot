#!/usr/bin/env python3
"""
SquidBot Client

Terminal-based chat client that connects to the local SquidBot server.
Features: async operations, input history, loading animation, notifications.
"""

import asyncio
import json
import readline
import signal
import sys
import time
from pathlib import Path

from .config import DATA_DIR, SQUID_PORT

# Server configuration
SERVER_HOST = "127.0.0.1"
SERVER_PORT = SQUID_PORT

# History file
HISTORY_FILE = DATA_DIR / "client_history"


class Spinner:
    """Animated spinner for loading indication with elapsed time."""

    FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]

    def __init__(self, message: str = "Thinking"):
        self.message = message
        self.running = False
        self.task: asyncio.Task | None = None
        self.start_time: float = 0
        self.elapsed: float = 0

    async def _animate(self):
        """Run the animation loop."""
        idx = 0
        while self.running:
            frame = self.FRAMES[idx % len(self.FRAMES)]
            self.elapsed = time.time() - self.start_time
            print(
                f"\r{frame} {self.message}... ({self.elapsed:.1f}s)", end="", flush=True
            )
            idx += 1
            await asyncio.sleep(0.1)

    async def start(self):
        """Start the spinner."""
        self.start_time = time.time()
        self.running = True
        self.task = asyncio.create_task(self._animate())

    async def stop(self) -> float:
        """Stop the spinner and clear the line. Returns elapsed time."""
        self.running = False
        self.elapsed = time.time() - self.start_time
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
        # Clear the spinner line
        print("\r" + " " * 50 + "\r", end="", flush=True)
        return self.elapsed


class InputHistory:
    """Manage input history with readline."""

    def __init__(self, history_file: Path):
        self.history_file = history_file

    async def load(self):
        """Load history from file."""
        try:
            if self.history_file.exists():
                readline.read_history_file(str(self.history_file))
        except Exception:
            pass

    async def save(self):
        """Save history to file."""
        try:
            self.history_file.parent.mkdir(parents=True, exist_ok=True)
            readline.set_history_length(1000)
            readline.write_history_file(str(self.history_file))
        except Exception:
            pass

    async def setup(self):
        """Setup readline for history navigation."""
        readline.parse_and_bind(r'"\e[A": previous-history')
        readline.parse_and_bind(r'"\e[B": next-history')
        readline.parse_and_bind(r'"\e[C": forward-char')
        readline.parse_and_bind(r'"\e[D": backward-char')
        readline.parse_and_bind(r'"\e[1~": beginning-of-line')
        readline.parse_and_bind(r'"\e[4~": end-of-line')
        readline.parse_and_bind(r'"\e[3~": delete-char')
        await self.load()


class SquidBotClient:
    """Async chat client for SquidBot."""

    def __init__(self):
        self.reader: asyncio.StreamReader | None = None
        self.writer: asyncio.StreamWriter | None = None
        self.running = True
        self.history = InputHistory(HISTORY_FILE)
        self.spinner = Spinner("Thinking")
        self.pending_notifications: list[str] = []
        self.response_queue: asyncio.Queue = asyncio.Queue()
        self.reader_task: asyncio.Task | None = None

    async def connect(self) -> bool:
        """Connect to the server."""
        try:
            self.reader, self.writer = await asyncio.open_connection(
                SERVER_HOST, SERVER_PORT
            )
            return True
        except ConnectionRefusedError:
            print(f"Error: Cannot connect to server at {SERVER_HOST}:{SERVER_PORT}")
            print("Make sure the server is running: make start")
            print(f"(Port configured via SQUID_PORT in .env)")
            return False
        except Exception as e:
            print(f"Error connecting: {e}")
            return False

    async def send_request(self, message: str, command: str = "chat") -> None:
        """Send a request to the server."""
        if not self.writer:
            return

        request = {"command": command, "message": message}
        data = json.dumps(request) + "\n"
        self.writer.write(data.encode())
        await self.writer.drain()

    async def read_responses(self):
        """Single reader task that dispatches responses to the right handler."""
        while self.running and self.reader:
            try:
                data = await self.reader.readline()
                if not data:
                    # Connection closed
                    await self.response_queue.put(None)
                    break

                response = json.loads(data.decode().strip())

                if response.get("status") == "notification":
                    # Handle notification immediately
                    msg = response.get("response", "")
                    print(f"\n\n📢 [Scheduled Task]\n{msg}\n")
                    print("You: ", end="", flush=True)
                else:
                    # Queue response for chat handler
                    await self.response_queue.put(response)

            except asyncio.CancelledError:
                break
            except json.JSONDecodeError:
                continue
            except Exception:
                await self.response_queue.put(None)
                break

    async def get_response(self, timeout: float = 120.0) -> dict | None:
        """Get a response from the queue with timeout."""
        try:
            return await asyncio.wait_for(self.response_queue.get(), timeout=timeout)
        except asyncio.TimeoutError:
            return None

    async def chat(self, user_input: str) -> tuple[str | None, float]:
        """Send chat message with loading animation."""
        await self.spinner.start()

        try:
            await self.send_request(user_input, "chat")

            # Wait for response from queue
            response = await self.get_response(timeout=120.0)
            if response is None:
                return None, self.spinner.elapsed

            return response.get("response", ""), self.spinner.elapsed
        finally:
            await self.spinner.stop()

    async def close(self):
        """Close the connection."""
        if self.reader_task:
            self.reader_task.cancel()
            try:
                await self.reader_task
            except asyncio.CancelledError:
                pass

        if self.writer:
            self.writer.close()
            await self.writer.wait_closed()

    async def get_input(self, prompt: str) -> str:
        """Get user input asynchronously."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, lambda: input(prompt))

    async def run(self):
        """Run the interactive chat loop."""
        print("=" * 60)
        print("  SquidBot Client")
        print("=" * 60)
        print()

        if not await self.connect():
            return

        # Start the single reader task
        self.reader_task = asyncio.create_task(self.read_responses())

        # Verify connection
        await self.send_request("", "ping")
        response = await self.get_response(timeout=5.0)
        if not response or response.get("response") != "pong":
            print("Error: Server not responding correctly")
            return

        # Setup history
        await self.history.setup()

        print(f"Connected to SquidBot at {SERVER_HOST}:{SERVER_PORT}")
        print()
        print("Commands:")
        print("  /clear  - Clear conversation history")
        print("  /quit   - Exit the client")
        print()
        print("Tips:")
        print("  - Use ↑/↓ arrows to navigate input history")
        print("  - Scheduled tasks will appear automatically")
        print()
        print("-" * 60)

        while self.running:
            try:
                # Get user input
                user_input = await self.get_input("\nYou: ")

                if not user_input.strip():
                    continue

                # Handle commands
                cmd = user_input.strip().lower()
                if cmd in ["/quit", "/exit", "/q"]:
                    print("Goodbye!")
                    break

                if cmd == "/clear":
                    await self.send_request("", "clear")
                    response = await self.get_response(timeout=5.0)
                    if response:
                        print(f"\n{response.get('response', '')}")
                    continue

                # Send chat message with animation
                response, elapsed = await self.chat(user_input)

                if response is None:
                    print("Error: Lost connection to server")
                    break

                print(f"SquidBot: {response}")
                print(f"         ({elapsed:.1f}s)")

            except EOFError:
                print("\nGoodbye!")
                break
            except KeyboardInterrupt:
                print("\nGoodbye!")
                break

        # Cleanup
        self.running = False
        await self.history.save()
        await self.close()


async def async_main():
    """Async main entry point."""
    client = SquidBotClient()

    def signal_handler():
        client.running = False

    loop = asyncio.get_event_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, signal_handler)
        except NotImplementedError:
            pass

    await client.run()


def main():
    """Main entry point."""
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
