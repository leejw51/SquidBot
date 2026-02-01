#!/usr/bin/env python3
"""
SquidBot Daemon Manager

Process supervisor for running SquidBot server and managing clients.
"""

import os
import signal
import subprocess
import sys
import time
from pathlib import Path

# PID and log files
DATA_DIR = Path.home() / ".squidbot"
PID_FILE = DATA_DIR / "squidbot.pid"
LOG_FILE = DATA_DIR / "squidbot.log"

# Script directory
SCRIPT_DIR = Path(__file__).parent.absolute()


def get_pid() -> int | None:
    """Get the PID of the running server."""
    if not PID_FILE.exists():
        return None
    try:
        pid = int(PID_FILE.read_text().strip())
        # Check if process is actually running
        os.kill(pid, 0)
        return pid
    except (ValueError, ProcessLookupError, PermissionError):
        # PID file exists but process is not running
        PID_FILE.unlink(missing_ok=True)
        return None


def is_running() -> bool:
    """Check if the server is running."""
    return get_pid() is not None


def find_squidbot_processes() -> list[tuple[int, str]]:
    """Find all SquidBot-related Python processes (server and client only)."""
    processes = []
    try:
        # Use ps to find Python processes
        result = subprocess.run(["ps", "aux"], capture_output=True, text=True)

        for line in result.stdout.split("\n"):
            # Only look for server.py and client.py, not daemon.py
            if "python" in line.lower() and any(
                script in line for script in ["server.py", "client.py"]
            ):
                parts = line.split()
                if len(parts) >= 2:
                    try:
                        pid = int(parts[1])
                        # Don't include ourselves
                        if pid != os.getpid():
                            processes.append((pid, line))
                    except ValueError:
                        pass
    except Exception:
        pass

    return processes


def show_env_info():
    """Display environment configuration to console."""
    import os

    from dotenv import load_dotenv

    load_dotenv()

    squid_port = int(os.environ.get("SQUID_PORT", "7777"))
    openai_model = os.environ.get("OPENAI_MODEL", "gpt-4o")
    heartbeat = int(os.environ.get("HEARTBEAT_INTERVAL_MINUTES", "30"))
    telegram_token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    openai_key = os.environ.get("OPENAI_API_KEY", "")

    print("")
    print("=" * 60)
    print("  SquidBot Configuration")
    print("=" * 60)
    print(f"  Home Directory : {DATA_DIR}")
    print(f"  Server Port    : 127.0.0.1:{squid_port}")
    print(f"  Model          : {openai_model}")
    print(f"  Heartbeat      : {heartbeat} minutes")
    print("-" * 60)
    print(f"  OPENAI_API_KEY : {'[SET]' if openai_key else '[NOT SET]'}")
    print(f"  Telegram Bot   : {'[ENABLED]' if telegram_token else '[DISABLED]'}")
    print("=" * 60)
    print("")


def start():
    """Start the server."""
    if is_running():
        print(f"SquidBot server is already running (PID: {get_pid()})")
        return False

    # Ensure data directory exists
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    main_script = SCRIPT_DIR / "server.py"

    # Show environment info to console
    show_env_info()

    print(f"Starting SquidBot server...")
    print(f"Log file: {LOG_FILE}")

    # Open log file
    log_fd = open(LOG_FILE, "a")

    # Start the process
    process = subprocess.Popen(
        [sys.executable, str(main_script)],
        stdout=log_fd,
        stderr=log_fd,
        cwd=str(SCRIPT_DIR),
        start_new_session=True,  # Detach from terminal
    )

    # Write PID file
    PID_FILE.write_text(str(process.pid))

    # Wait a moment to check if it started successfully
    time.sleep(1)

    if process.poll() is None:
        print(f"SquidBot server started (PID: {process.pid})")
        return True
    else:
        print("SquidBot failed to start. Check logs:")
        print(f"  tail -f {LOG_FILE}")
        PID_FILE.unlink(missing_ok=True)
        return False


def stop():
    """Stop the server."""
    pid = get_pid()
    if pid is None:
        print("SquidBot server is not running")
        return False

    print(f"Stopping SquidBot server (PID: {pid})...")

    try:
        # Send SIGTERM for graceful shutdown
        os.kill(pid, signal.SIGTERM)

        # Wait for process to terminate
        for _ in range(10):  # Wait up to 10 seconds
            time.sleep(1)
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                print("SquidBot server stopped")
                PID_FILE.unlink(missing_ok=True)
                return True

        # Force kill if still running
        print("Process not responding, sending SIGKILL...")
        os.kill(pid, signal.SIGKILL)
        time.sleep(1)
        PID_FILE.unlink(missing_ok=True)
        print("SquidBot server forcefully terminated")
        return True

    except ProcessLookupError:
        print("Process already terminated")
        PID_FILE.unlink(missing_ok=True)
        return True
    except PermissionError:
        print(f"Permission denied to stop process {pid}")
        return False


def stopall():
    """Stop server and kill all clients."""
    print("Stopping all SquidBot processes...")

    killed = 0

    # First, stop the server gracefully
    if is_running():
        stop()
        killed += 1

    # Find and kill any remaining processes
    processes = find_squidbot_processes()

    for pid, cmdline in processes:
        try:
            print(f"  Killing PID {pid}...")
            os.kill(pid, signal.SIGTERM)
            killed += 1
        except (ProcessLookupError, PermissionError):
            pass

    # Wait a moment
    if processes:
        time.sleep(1)

        # Force kill any remaining
        for pid, cmdline in processes:
            try:
                os.kill(pid, 0)  # Check if still running
                print(f"  Force killing PID {pid}...")
                os.kill(pid, signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                pass

    # Clean up PID file
    PID_FILE.unlink(missing_ok=True)

    print(f"Stopped {killed} process(es)")
    return True


def restart():
    """Restart the server."""
    if is_running():
        stop()
        time.sleep(1)
    start()


def status():
    """Show server status."""
    pid = get_pid()
    if pid:
        print(f"SquidBot server is running (PID: {pid})")
        print(f"Log file: {LOG_FILE}")

        # Show any client processes
        processes = find_squidbot_processes()
        clients = [(p, c) for p, c in processes if "client.py" in c]
        if clients:
            print(f"Active clients: {len(clients)}")

        return True
    else:
        print("SquidBot server is not running")
        return False


def logs(follow: bool = False, lines: int = 50):
    """Show server logs."""
    if not LOG_FILE.exists():
        print("No log file found")
        return

    if follow:
        os.execvp("tail", ["tail", "-f", str(LOG_FILE)])
    else:
        os.execvp("tail", ["tail", "-n", str(lines), str(LOG_FILE)])


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: python daemon.py <command>")
        print("")
        print("Commands:")
        print("  start    Start the server")
        print("  stop     Stop the server")
        print("  stopall  Stop server and kill all clients")
        print("  restart  Restart the server")
        print("  status   Show server status")
        print("  logs     Show recent logs")
        print("  logs -f  Follow logs in real-time")
        sys.exit(1)

    command = sys.argv[1]

    if command == "start":
        success = start()
        sys.exit(0 if success else 1)
    elif command == "stop":
        success = stop()
        sys.exit(0 if success else 1)
    elif command == "stopall":
        success = stopall()
        sys.exit(0 if success else 1)
    elif command == "restart":
        restart()
    elif command == "status":
        running = status()
        sys.exit(0 if running else 1)
    elif command == "logs":
        follow = "-f" in sys.argv or "--follow" in sys.argv
        logs(follow=follow)
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)


if __name__ == "__main__":
    main()
