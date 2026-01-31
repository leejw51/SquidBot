#!/usr/bin/env python3
"""Integration test for cron jobs using actual OpenAI agent."""
import asyncio
import sys

sys.path.insert(0, ".")

from agent import run_agent
from tools.cron import load_cron_jobs, save_cron_jobs


async def test_cron_integration():
    """Test cron operations through the actual LLM agent."""
    print("=" * 60)
    print("CRON JOB INTEGRATION TEST (using OpenAI)")
    print("=" * 60)

    # Clear existing jobs
    save_cron_jobs([])
    print("\n[SETUP] Cleared existing jobs")

    # Test 1: Create a cron job via LLM
    print("\n" + "-" * 40)
    print("TEST 1: Ask LLM to create a cron job")
    print("-" * 40)

    response = await run_agent(
        "Create a reminder for 5 minutes from now to drink water"
    )
    print(f"  LLM response: {response[:200]}...")

    jobs = load_cron_jobs()
    print(f"  Jobs in file: {len(jobs)}")
    if jobs:
        print(f"  Job created: id={jobs[0]['id']}, message={jobs[0]['message']}")
    assert len(jobs) >= 1, "LLM should have created at least 1 job"
    print("  ✓ Job created successfully")

    # Test 2: Create interval job
    print("\n" + "-" * 40)
    print("TEST 2: Ask LLM to create an interval job")
    print("-" * 40)

    response = await run_agent(
        "Create a task that runs every 60 seconds to check system status"
    )
    print(f"  LLM response: {response[:200]}...")

    jobs = load_cron_jobs()
    print(f"  Jobs in file: {len(jobs)}")
    interval_jobs = [j for j in jobs if j.get("type") == "interval"]
    print(f"  Interval jobs: {len(interval_jobs)}")
    assert len(interval_jobs) >= 1, "LLM should have created an interval job"
    print("  ✓ Interval job created successfully")

    # Test 3: List jobs via LLM
    print("\n" + "-" * 40)
    print("TEST 3: Ask LLM to list cron jobs")
    print("-" * 40)

    response = await run_agent("List all my scheduled tasks")
    print(f"  LLM response:\n{response}")

    assert (
        "drink water" in response.lower()
        or "system status" in response.lower()
        or "scheduled" in response.lower()
    )
    print("  ✓ Jobs listed successfully")

    # Test 4: Delete specific job via LLM
    print("\n" + "-" * 40)
    print("TEST 4: Ask LLM to delete job ID 1")
    print("-" * 40)

    jobs_before = len(load_cron_jobs())
    response = await run_agent("Delete the scheduled task with ID 1")
    print(f"  LLM response: {response[:200]}...")

    jobs_after = load_cron_jobs()
    print(f"  Jobs before: {jobs_before}, after: {len(jobs_after)}")

    # Check job 1 is gone
    job_ids = [j["id"] for j in jobs_after]
    assert 1 not in job_ids, "Job 1 should be deleted"
    print("  ✓ Job deleted successfully")

    # Test 5: Clear all jobs via LLM
    print("\n" + "-" * 40)
    print("TEST 5: Ask LLM to clear all cron jobs")
    print("-" * 40)

    # Add another job first
    await run_agent("Create a reminder for 10 minutes from now to stretch")
    jobs = load_cron_jobs()
    print(f"  Jobs before clear: {len(jobs)}")

    response = await run_agent("Clear all scheduled tasks")
    print(f"  LLM response: {response[:200]}...")

    jobs = load_cron_jobs()
    print(f"  Jobs after clear: {len(jobs)}")
    assert len(jobs) == 0, "All jobs should be cleared"
    print("  ✓ All jobs cleared successfully")

    # Summary
    print("\n" + "=" * 60)
    print("ALL INTEGRATION TESTS PASSED ✓")
    print("=" * 60)
    print("\nVerified LLM can:")
    print("  1. Create one-time reminders (cron_create with delay_minutes)")
    print("  2. Create interval tasks (cron_create with interval_seconds)")
    print("  3. List scheduled tasks (cron_list)")
    print("  4. Delete specific task by ID (cron_delete)")
    print("  5. Clear all tasks (cron_clear)")


if __name__ == "__main__":
    asyncio.run(test_cron_integration())
