#!/usr/bin/env python3
"""Verification script for cron job operations."""

import asyncio
import sys

sys.path.insert(0, ".")

from tools.cron import (CronClearTool, CronCreateTool, CronDeleteTool,
                        CronListTool, load_cron_jobs, save_cron_jobs)


async def test_cron_operations():
    """Test all cron operations step by step."""
    print("=" * 60)
    print("CRON JOB VERIFICATION TEST")
    print("=" * 60)

    # Clear any existing jobs first
    save_cron_jobs([])
    print("\n[SETUP] Cleared existing jobs")

    # 1. Create jobs
    print("\n" + "-" * 40)
    print("TEST 1: Create cron jobs")
    print("-" * 40)

    create = CronCreateTool()

    result1 = await create.execute(message="Job One - reminder", delay_minutes=5)
    print(f"  Created job 1: {result1}")

    result2 = await create.execute(message="Job Two - interval", interval_seconds=30)
    print(f"  Created job 2: {result2}")

    result3 = await create.execute(
        message="Job Three - cron", cron_expression="0 9 * * *"
    )
    print(f"  Created job 3: {result3}")

    jobs = load_cron_jobs()
    assert len(jobs) == 3, f"Expected 3 jobs, got {len(jobs)}"
    print(f"  ✓ Verified: {len(jobs)} jobs created")

    # 2. List jobs
    print("\n" + "-" * 40)
    print("TEST 2: List cron jobs")
    print("-" * 40)

    list_tool = CronListTool()
    result = await list_tool.execute()
    print(f"  List output:\n{result}")

    assert "Job One" in result
    assert "Job Two" in result
    assert "Job Three" in result
    print("  ✓ Verified: All jobs listed correctly")

    # 3. Delete job with integer ID
    print("\n" + "-" * 40)
    print("TEST 3: Delete job with integer ID")
    print("-" * 40)

    delete = CronDeleteTool()
    result = await delete.execute(job_id=2)
    print(f"  Delete result: {result}")

    jobs = load_cron_jobs()
    assert len(jobs) == 2, f"Expected 2 jobs, got {len(jobs)}"
    job_ids = [j["id"] for j in jobs]
    assert 2 not in job_ids, "Job 2 should be deleted"
    print(f"  ✓ Verified: Job 2 deleted, remaining IDs: {job_ids}")

    # 4. Delete job with STRING ID (LLM behavior)
    print("\n" + "-" * 40)
    print("TEST 4: Delete job with STRING ID (LLM passes string)")
    print("-" * 40)

    result = await delete.execute(job_id="1")  # String, not int!
    print(f"  Delete with string '1': {result}")

    jobs = load_cron_jobs()
    assert len(jobs) == 1, f"Expected 1 job, got {len(jobs)}"
    assert jobs[0]["id"] == 3, "Only job 3 should remain"
    print(f"  ✓ Verified: String ID works, remaining job ID: {jobs[0]['id']}")

    # 5. Delete nonexistent job
    print("\n" + "-" * 40)
    print("TEST 5: Delete nonexistent job")
    print("-" * 40)

    result = await delete.execute(job_id=999)
    print(f"  Delete job 999: {result}")

    assert "No job found" in result
    print("  ✓ Verified: Proper error message for missing job")

    # 6. Clear all jobs
    print("\n" + "-" * 40)
    print("TEST 6: Clear all jobs")
    print("-" * 40)

    # First add more jobs
    await create.execute(message="Extra job 1", delay_minutes=10)
    await create.execute(message="Extra job 2", delay_minutes=20)

    jobs = load_cron_jobs()
    print(f"  Jobs before clear: {len(jobs)}")

    clear = CronClearTool()
    result = await clear.execute()
    print(f"  Clear result: {result}")

    jobs = load_cron_jobs()
    assert len(jobs) == 0, f"Expected 0 jobs, got {len(jobs)}"
    print("  ✓ Verified: All jobs cleared")

    # 7. Clear empty list
    print("\n" + "-" * 40)
    print("TEST 7: Clear when already empty")
    print("-" * 40)

    result = await clear.execute()
    print(f"  Clear empty: {result}")

    assert "No scheduled tasks to clear" in result
    print("  ✓ Verified: Proper message for empty list")

    # Summary
    print("\n" + "=" * 60)
    print("ALL TESTS PASSED ✓")
    print("=" * 60)
    print("\nVerified operations:")
    print("  1. Create one-time, interval, and cron jobs")
    print("  2. List all jobs")
    print("  3. Delete job by integer ID")
    print("  4. Delete job by string ID (LLM compatibility)")
    print("  5. Handle delete of nonexistent job")
    print("  6. Clear all jobs")
    print("  7. Clear empty job list")


if __name__ == "__main__":
    asyncio.run(test_cron_operations())
