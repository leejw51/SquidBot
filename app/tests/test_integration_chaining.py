#!/usr/bin/env python3
"""Integration tests for tool chaining using actual OpenAI agent.

Run with pytest: python -m pytest tests/test_integration_chaining.py -v -s
Run standalone: python tests/test_integration_chaining.py
"""
import asyncio
import os
import sys

sys.path.insert(0, ".")

# Load real API key from .env
from dotenv import load_dotenv
load_dotenv(override=True)

# Get real API key before it gets overwritten
REAL_API_KEY = os.environ.get("OPENAI_API_KEY")

import pytest
from openai import AsyncOpenAI

pytestmark = pytest.mark.integration

from agent import run_agent
from tools.cron import load_cron_jobs, save_cron_jobs
from memory_db import init_db
import agent as agent_module

# Replace agent's client with one using real API key
agent_module.client = AsyncOpenAI(api_key=REAL_API_KEY)


class TestToolChainingIntegration:
    """Integration tests for tool chaining with real OpenAI API."""

    @pytest.fixture(autouse=True)
    async def setup(self):
        """Setup before each test."""
        save_cron_jobs([])
        await init_db()
        yield
        # Cleanup
        save_cron_jobs([])

    # ========================================
    # Sequential Chaining Tests
    # ========================================

    @pytest.mark.asyncio
    async def test_memory_store_then_retrieve(self):
        """Test: Store in memory → Retrieve from memory."""
        # Store
        response = await run_agent("Remember that my favorite programming language is Python")
        print(f"Store response: {response}")
        assert "python" in response.lower() or "remember" in response.lower()

        # Retrieve
        response = await run_agent("What is my favorite programming language?")
        print(f"Retrieve response: {response}")
        assert "python" in response.lower()

    @pytest.mark.asyncio
    async def test_cron_create_list_delete(self):
        """Test: Create cron → List cron → Delete cron."""
        # Create
        response = await run_agent("Set a reminder for 10 minutes from now to take a break")
        print(f"Create response: {response}")
        
        jobs = load_cron_jobs()
        assert len(jobs) >= 1, "Should have created a job"
        job_id = jobs[0]["id"]

        # List
        response = await run_agent("Show me all my scheduled tasks")
        print(f"List response: {response}")
        assert "break" in response.lower() or "reminder" in response.lower()

        # Delete
        response = await run_agent(f"Delete the scheduled task with ID {job_id}")
        print(f"Delete response: {response}")
        
        jobs = load_cron_jobs()
        assert len(jobs) == 0, "Job should be deleted"

    @pytest.mark.asyncio
    async def test_memory_then_cron_chain(self):
        """Test: Remember something → Create reminder about it."""
        # Remember
        response = await run_agent("Remember that I have a dentist appointment next Tuesday")
        print(f"Memory response: {response}")

        # Create reminder
        response = await run_agent("Set a reminder for 5 minutes from now about my appointment")
        print(f"Cron response: {response}")

        jobs = load_cron_jobs()
        assert len(jobs) >= 1, "Should have created a reminder"

    # ========================================
    # Complex Multi-Step Chaining
    # ========================================

    @pytest.mark.asyncio
    async def test_multiple_memory_then_search(self):
        """Test: Store multiple facts → Search for specific one."""
        # Store multiple
        await run_agent("Remember my name is John")
        await run_agent("Remember I live in Seoul")
        await run_agent("Remember my favorite food is pizza")

        # Search specific
        response = await run_agent("Where do I live?")
        print(f"Search response: {response}")
        assert "seoul" in response.lower()

        response = await run_agent("What is my name?")
        print(f"Name response: {response}")
        assert "john" in response.lower()

    @pytest.mark.asyncio
    async def test_create_multiple_crons_then_clear(self):
        """Test: Create multiple crons → Clear all."""
        # Create multiple
        await run_agent("Set a reminder for 5 minutes to drink water")
        await run_agent("Create a task that runs every 60 seconds to check status")
        await run_agent("Set a reminder for 10 minutes to stretch")

        jobs = load_cron_jobs()
        print(f"Jobs created: {len(jobs)}")
        assert len(jobs) >= 2, "Should have multiple jobs"

        # Clear all
        response = await run_agent("Clear all my scheduled tasks")
        print(f"Clear response: {response}")

        jobs = load_cron_jobs()
        assert len(jobs) == 0, "All jobs should be cleared"

    # ========================================
    # Error Recovery Tests
    # ========================================

    @pytest.mark.asyncio
    async def test_delete_nonexistent_cron(self):
        """Test: Delete non-existent cron job gracefully."""
        response = await run_agent("Delete scheduled task with ID 9999")
        print(f"Delete response: {response}")
        # Should handle gracefully without crashing
        assert "not found" in response.lower() or "no" in response.lower() or "doesn't exist" in response.lower()

    @pytest.mark.asyncio
    async def test_search_empty_memory(self):
        """Test: Search memory when nothing stored - agent handles gracefully."""
        # Ask about something not stored - agent should handle gracefully
        response = await run_agent("What is my favorite book that I told you about?")
        print(f"Empty search response: {response}")
        # Should respond appropriately (no crash)
        assert response is not None


async def run_all_integration_tests():
    """Run all integration tests manually."""
    print("=" * 60)
    print("TOOL CHAINING INTEGRATION TESTS (using OpenAI)")
    print("=" * 60)

    async def reset_state():
        """Reset state before each test."""
        save_cron_jobs([])
        await init_db()

    async def test_memory_store_then_retrieve():
        """Test: Store in memory → Retrieve from memory."""
        response = await run_agent("Remember that my favorite programming language is Python")
        print(f"Store response: {response}")
        assert "python" in response.lower() or "remember" in response.lower()
        response = await run_agent("What is my favorite programming language?")
        print(f"Retrieve response: {response}")
        assert "python" in response.lower()

    async def test_cron_create_list_delete():
        """Test: Create cron → List cron → Delete cron."""
        response = await run_agent("Set a reminder for 10 minutes from now to take a break")
        print(f"Create response: {response}")
        jobs = load_cron_jobs()
        assert len(jobs) >= 1, "Should have created a job"
        job_id = jobs[0]["id"]
        response = await run_agent("Show me all my scheduled tasks")
        print(f"List response: {response}")
        response = await run_agent(f"Delete the scheduled task with ID {job_id}")
        print(f"Delete response: {response}")
        jobs = load_cron_jobs()
        assert len(jobs) == 0, "Job should be deleted"

    async def test_memory_then_cron_chain():
        """Test: Remember something → Create reminder about it."""
        response = await run_agent("Remember that I have a dentist appointment next Tuesday")
        print(f"Memory response: {response}")
        response = await run_agent("Set a reminder for 5 minutes from now about my appointment")
        print(f"Cron response: {response}")
        jobs = load_cron_jobs()
        assert len(jobs) >= 1, "Should have created a reminder"

    async def test_create_multiple_crons_then_clear():
        """Test: Create multiple crons → Clear all."""
        await run_agent("Set a reminder for 5 minutes to drink water")
        await run_agent("Create a task that runs every 60 seconds to check status")
        await run_agent("Set a reminder for 10 minutes to stretch")
        jobs = load_cron_jobs()
        print(f"Jobs created: {len(jobs)}")
        assert len(jobs) >= 2, "Should have multiple jobs"
        response = await run_agent("Clear all my scheduled tasks")
        print(f"Clear response: {response}")
        jobs = load_cron_jobs()
        assert len(jobs) == 0, "All jobs should be cleared"

    async def test_delete_nonexistent_cron():
        """Test: Delete non-existent cron job gracefully."""
        response = await run_agent("Delete scheduled task with ID 9999")
        print(f"Delete response: {response}")
        assert response is not None

    test_methods = [
        ("Memory Store → Retrieve", test_memory_store_then_retrieve),
        ("Cron Create → List → Delete", test_cron_create_list_delete),
        ("Memory → Cron Chain", test_memory_then_cron_chain),
        ("Multiple Crons → Clear", test_create_multiple_crons_then_clear),
        ("Delete Nonexistent Cron", test_delete_nonexistent_cron),
    ]

    passed = 0
    failed = 0

    for name, test_func in test_methods:
        print(f"\n{'=' * 40}")
        print(f"TEST: {name}")
        print("=" * 40)

        # Reset state
        await reset_state()

        try:
            await test_func()
            print(f"✓ PASSED: {name}")
            passed += 1
        except AssertionError as e:
            print(f"✗ FAILED: {name}")
            print(f"  Error: {e}")
            failed += 1
        except Exception as e:
            print(f"✗ ERROR: {name}")
            print(f"  Exception: {type(e).__name__}: {e}")
            failed += 1

    print("\n" + "=" * 60)
    print(f"RESULTS: {passed} passed, {failed} failed")
    print("=" * 60)

    return failed == 0


if __name__ == "__main__":
    success = asyncio.run(run_all_integration_tests())
    sys.exit(0 if success else 1)
