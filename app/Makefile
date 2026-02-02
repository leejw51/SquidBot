.PHONY: all start stop stopall restart status logs client test testall integrationtest clean help \
        install install-dev poetry-install poetry-install-dev package package-version package-clean info

# Configuration (can be overridden via environment)
SQUIDBOT_HOME ?= $(HOME)/.squidbot
SQUID_PORT ?= 7777

# Default target - start the server (shows config automatically)
all: start

# ============================================================
# Server & Client
# ============================================================

# Show configuration info
info:
	@echo ""
	@echo "============================================================"
	@echo "  SquidBot Configuration"
	@echo "============================================================"
	@echo "  SQUIDBOT_HOME : $(SQUIDBOT_HOME)"
	@echo "  SQUID_PORT    : $(SQUID_PORT)"
	@echo "============================================================"
	@echo ""
	@echo "  To customize, set environment variables:"
	@echo "    export SQUIDBOT_HOME=/path/to/home"
	@echo "    export SQUID_PORT=8888"
	@echo "============================================================"
	@echo ""

# Start the server (daemon mode)
start:
	python daemon.py start

# Stop the server
stop:
	python daemon.py stop

# Stop server and kill all clients
stopall:
	python daemon.py stopall

# Restart the server
restart:
	python daemon.py restart

# Show server status
status:
	python daemon.py status

# Show server logs
logs:
	python daemon.py logs

# Follow server logs in real-time
logs-follow:
	python daemon.py logs -f

# Run the chat client (connects to server)
client:
	python client.py

# Run server in foreground (for debugging)
server:
	python server.py

# ============================================================
# Testing
# ============================================================

# Run unit tests only (excludes integration tests)
test:
	pytest tests/ -v --ignore=tests/test_integration_chaining.py

# Run all tests (unit + integration)
testall:
	pytest tests/ test_cron_integration.py test_cron_verify.py -v

# Run integration tests only
integrationtest:
	pytest tests/test_integration_chaining.py test_cron_integration.py test_cron_verify.py -v

# Run tests with extra verbosity
test-verbose:
	pytest tests/ -v -s --ignore=tests/test_integration_chaining.py

# Run tests with coverage
test-cov:
	pytest tests/ -v --cov=. --cov-report=term-missing --ignore=tests/test_integration_chaining.py

# Run specific test file
test-memory:
	pytest tests/test_memory.py -v

test-tools:
	pytest tests/test_tools.py -v

test-chaining:
	pytest tests/test_tool_chaining.py -v

test-proactive:
	pytest tests/test_proactive_messaging.py -v

test-coding:
	pytest tests/test_coding.py -v

test-session:
	pytest tests/test_session.py -v

test-sqlite-vec:
	pytest tests/test_sqlite_vec.py -v

# ============================================================
# Installation
# ============================================================

# Install with pip
install:
	pip install -r requirements.txt
	playwright install chromium

# Install dev dependencies with pip
install-dev:
	pip install -r requirements.txt
	pip install pytest pytest-asyncio pytest-cov
	playwright install chromium

# Install/reinstall Playwright browsers
install-browsers:
	playwright install chromium

# Check Playwright installation and web browsing
check-playwright:
	python playwright_check.py

# Check Playwright installation only (skip web test)
check-playwright-offline:
	python playwright_check.py --skip-web

# Install with Poetry
poetry-install:
	poetry install --only main
	poetry run playwright install chromium

# Install dev dependencies with Poetry
poetry-install-dev:
	poetry install
	poetry run playwright install chromium

# ============================================================
# Poetry commands
# ============================================================

# Run tests with Poetry
poetry-test:
	poetry run pytest tests/ -v

# Start server with Poetry
poetry-start:
	poetry run python daemon.py start

# Stop server with Poetry
poetry-stop:
	poetry run python daemon.py stop

# Run client with Poetry
poetry-client:
	poetry run python client.py

# ============================================================
# Packaging
# ============================================================

# Create release zip of the app folder
package:
	python release.py

# Create release zip with version tag
package-version:
	@if [ -z "$(VERSION)" ]; then \
		echo "Usage: make package-version VERSION=1.0.0"; \
		exit 1; \
	fi
	python release.py -v $(VERSION)

# Clean build artifacts
package-clean:
	rm -rf build/ dist/ *.spec

# ============================================================
# Cleanup
# ============================================================

# Clean up
clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	rm -rf .coverage htmlcov/
	rm -rf build/ dist/ *.spec

# ============================================================
# Help
# ============================================================

help:
	@echo "SquidBot - Autonomous AI Agent"
	@echo ""
	@echo "Usage:"
	@echo "  make              - Show config info and start the server"
	@echo "  make info         - Show configuration (SQUIDBOT_HOME, SQUID_PORT)"
	@echo "  make start        - Start the server as daemon"
	@echo "  make stop         - Stop the server"
	@echo "  make stopall      - Stop server and kill all clients"
	@echo "  make client       - Run the chat client"
	@echo ""
	@echo "Server Management:"
	@echo "  make restart      - Restart the server"
	@echo "  make status       - Show server status"
	@echo "  make logs         - Show recent logs"
	@echo "  make logs-follow  - Follow logs in real-time"
	@echo "  make server       - Run server in foreground (debug)"
	@echo ""
	@echo "Testing:"
	@echo "  make test            - Run unit tests only"
	@echo "  make testall         - Run all tests (unit + integration)"
	@echo "  make integrationtest - Run integration tests only"
	@echo "  make test-cov        - Run unit tests with coverage"
	@echo ""
	@echo "Installation:"
	@echo "  make install           - Install dependencies (pip)"
	@echo "  make install-dev       - Install with dev dependencies"
	@echo "  make install-browsers  - Install Playwright browsers"
	@echo "  make check-playwright  - Check Playwright is working"
	@echo ""
	@echo "Packaging:"
	@echo "  make package                  - Create release zip of app folder"
	@echo "  make package-version VERSION= - Create release zip with version"
	@echo "  make package-clean            - Remove build artifacts"
	@echo ""
	@echo "Cleanup:"
	@echo "  make clean        - Remove all cache and build files"
