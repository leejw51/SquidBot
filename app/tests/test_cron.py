"""Tests for cron job functionality."""

import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest

from scheduler import Scheduler
from tools.cron import (CronClearTool, CronCreateTool, CronDeleteTool,
                        CronListTool, load_cron_jobs, save_cron_jobs)


class TestCronTools:
    """Test cron tool operations."""

    # ========================================
    # Add cron jobs
    # ========================================

    async def test_add_one_time_job(self):
        """Test adding a one-time reminder."""
        tool = CronCreateTool()
        result = await tool.execute(message="Test reminder", delay_minutes=5)

        assert "Reminder set" in result
        assert "5 minutes" in result

        jobs = load_cron_jobs()
        assert len(jobs) == 1
        assert jobs[0]["message"] == "Test reminder"
        assert jobs[0]["type"] == "one_time"
        assert jobs[0]["enabled"] is True

    async def test_add_interval_job(self):
        """Test adding an interval job."""
        tool = CronCreateTool()
        result = await tool.execute(
            message="Repeat every 30 seconds", interval_seconds=30
        )

        assert "Interval task" in result
        assert "30 seconds" in result

        jobs = load_cron_jobs()
        assert len(jobs) == 1
        assert jobs[0]["message"] == "Repeat every 30 seconds"
        assert jobs[0]["type"] == "interval"
        assert jobs[0]["interval_seconds"] == 30
        assert jobs[0]["recurring"] is True

    async def test_add_cron_expression_job(self):
        """Test adding a cron expression job."""
        tool = CronCreateTool()
        result = await tool.execute(message="Daily task", cron_expression="0 9 * * *")

        assert "Recurring task" in result
        assert "0 9 * * *" in result

        jobs = load_cron_jobs()
        assert len(jobs) == 1
        assert jobs[0]["message"] == "Daily task"
        assert jobs[0]["type"] == "cron"
        assert jobs[0]["cron_expression"] == "0 9 * * *"

    async def test_add_job_without_schedule_fails(self):
        """Test that adding a job without schedule fails."""
        tool = CronCreateTool()
        result = await tool.execute(message="No schedule")

        assert "Error" in result
        jobs = load_cron_jobs()
        assert len(jobs) == 0

    async def test_add_multiple_jobs(self):
        """Test adding multiple jobs."""
        tool = CronCreateTool()

        await tool.execute(message="Job 1", delay_minutes=5)
        await tool.execute(message="Job 2", interval_seconds=60)
        await tool.execute(message="Job 3", cron_expression="0 8 * * *")

        jobs = load_cron_jobs()
        assert len(jobs) == 3
        assert jobs[0]["id"] == 1
        assert jobs[1]["id"] == 2
        assert jobs[2]["id"] == 3

    # ========================================
    # List cron jobs
    # ========================================

    async def test_list_empty_jobs(self):
        """Test listing when no jobs exist."""
        tool = CronListTool()
        result = await tool.execute()

        assert "No scheduled tasks" in result

    async def test_list_jobs(self):
        """Test listing all jobs."""
        create = CronCreateTool()
        await create.execute(message="One-time", delay_minutes=10)
        await create.execute(message="Interval", interval_seconds=30)
        await create.execute(message="Cron", cron_expression="0 9 * * *")

        list_tool = CronListTool()
        result = await list_tool.execute()

        assert "Scheduled tasks (3)" in result
        assert "One-time" in result
        assert "Interval" in result
        assert "Every 30s" in result
        assert "Cron" in result
        assert "0 9 * * *" in result

    # ========================================
    # Remove cron jobs
    # ========================================

    async def test_delete_job(self):
        """Test deleting a job."""
        create = CronCreateTool()
        await create.execute(message="To delete", delay_minutes=5)

        jobs = load_cron_jobs()
        assert len(jobs) == 1

        delete = CronDeleteTool()
        result = await delete.execute(job_id=1)

        assert "Deleted" in result

        jobs = load_cron_jobs()
        assert len(jobs) == 0

    async def test_delete_nonexistent_job(self):
        """Test deleting a job that doesn't exist."""
        delete = CronDeleteTool()
        result = await delete.execute(job_id=999)

        assert "No job found" in result

    async def test_delete_specific_job(self):
        """Test deleting a specific job from multiple."""
        create = CronCreateTool()
        await create.execute(message="Job 1", delay_minutes=5)
        await create.execute(message="Job 2", delay_minutes=10)
        await create.execute(message="Job 3", delay_minutes=15)

        delete = CronDeleteTool()
        await delete.execute(job_id=2)

        jobs = load_cron_jobs()
        assert len(jobs) == 2
        assert jobs[0]["message"] == "Job 1"
        assert jobs[1]["message"] == "Job 3"

    async def test_delete_with_string_id(self):
        """Test deleting a job with string ID (LLM might pass string)."""
        create = CronCreateTool()
        await create.execute(message="Test job", delay_minutes=5)

        delete = CronDeleteTool()
        result = await delete.execute(job_id="1")  # String instead of int

        assert "Deleted" in result
        jobs = load_cron_jobs()
        assert len(jobs) == 0

    # ========================================
    # Clear all cron jobs
    # ========================================

    async def test_clear_all_jobs(self):
        """Test clearing all jobs."""
        create = CronCreateTool()
        await create.execute(message="Job 1", delay_minutes=5)
        await create.execute(message="Job 2", interval_seconds=30)
        await create.execute(message="Job 3", cron_expression="0 9 * * *")

        clear = CronClearTool()
        result = await clear.execute()

        assert "Cleared all 3" in result
        jobs = load_cron_jobs()
        assert len(jobs) == 0

    async def test_clear_empty_jobs(self):
        """Test clearing when no jobs exist."""
        clear = CronClearTool()
        result = await clear.execute()

        assert "No scheduled tasks to clear" in result


class TestSchedulerCronExecution:
    """Test scheduler cron job execution."""

    @pytest.fixture
    def mock_send_message(self):
        """Mock send_message function."""
        return AsyncMock()

    @pytest.fixture
    def mock_run_agent(self):
        """Mock run_agent function that returns a response."""
        return AsyncMock(return_value="Agent executed the task successfully")

    @pytest.fixture
    def scheduler(self, mock_send_message, mock_run_agent):
        """Create a scheduler instance."""
        return Scheduler(
            send_message=mock_send_message, run_agent=mock_run_agent, chat_id=12345
        )

    # ========================================
    # Run cron jobs
    # ========================================

    async def test_run_cron_job(self, scheduler, mock_send_message, mock_run_agent):
        """Test that cron jobs execute the agent."""
        job = {"id": 1, "message": "Check the weather", "type": "cron"}

        await scheduler._run_cron_job(job)

        # Agent should be called with the job message
        mock_run_agent.assert_called_once_with("Check the weather")

        # Message should be sent with the response
        mock_send_message.assert_called_once()
        call_args = mock_send_message.call_args[0][0]
        assert "[Scheduled Task]" in call_args
        assert "Agent executed the task successfully" in call_args

    async def test_run_one_time_job(self, scheduler, mock_send_message, mock_run_agent):
        """Test that one-time jobs execute and get disabled."""
        # Create a job that's already due
        past_time = datetime.now() - timedelta(minutes=1)
        jobs = [
            {
                "id": 1,
                "message": "One-time reminder",
                "type": "one_time",
                "trigger_at": past_time.isoformat(),
                "enabled": True,
            }
        ]
        save_cron_jobs(jobs)

        await scheduler._check_one_time_jobs()

        # Agent should be called
        mock_run_agent.assert_called_once_with("One-time reminder")

        # Message should be sent
        mock_send_message.assert_called_once()
        call_args = mock_send_message.call_args[0][0]
        assert "[Reminder]" in call_args

        # Job should be disabled
        jobs = load_cron_jobs()
        assert jobs[0]["enabled"] is False

    async def test_run_interval_job(self, scheduler, mock_send_message, mock_run_agent):
        """Test that interval jobs execute and reschedule."""
        # Create an interval job that's due
        past_time = datetime.now() - timedelta(seconds=5)
        jobs = [
            {
                "id": 1,
                "message": "Interval task",
                "type": "interval",
                "interval_seconds": 30,
                "next_trigger": past_time.isoformat(),
                "enabled": True,
                "recurring": True,
            }
        ]
        save_cron_jobs(jobs)

        await scheduler._check_interval_jobs()

        # Agent should be called
        mock_run_agent.assert_called_once_with("Interval task")

        # Message should be sent
        mock_send_message.assert_called_once()
        call_args = mock_send_message.call_args[0][0]
        assert "[Interval Task]" in call_args

        # Job should still be enabled with new trigger time
        jobs = load_cron_jobs()
        assert jobs[0]["enabled"] is True
        new_trigger = datetime.fromisoformat(jobs[0]["next_trigger"])
        assert new_trigger > datetime.now()

    async def test_skip_future_job(self, scheduler, mock_send_message, mock_run_agent):
        """Test that future jobs are not executed."""
        future_time = datetime.now() + timedelta(hours=1)
        jobs = [
            {
                "id": 1,
                "message": "Future job",
                "type": "one_time",
                "trigger_at": future_time.isoformat(),
                "enabled": True,
            }
        ]
        save_cron_jobs(jobs)

        await scheduler._check_one_time_jobs()

        # Agent should NOT be called
        mock_run_agent.assert_not_called()

        # Job should still be enabled
        jobs = load_cron_jobs()
        assert jobs[0]["enabled"] is True

    async def test_skip_disabled_job(
        self, scheduler, mock_send_message, mock_run_agent
    ):
        """Test that disabled jobs are not executed."""
        past_time = datetime.now() - timedelta(minutes=1)
        jobs = [
            {
                "id": 1,
                "message": "Disabled job",
                "type": "one_time",
                "trigger_at": past_time.isoformat(),
                "enabled": False,
            }
        ]
        save_cron_jobs(jobs)

        await scheduler._check_one_time_jobs()

        # Agent should NOT be called
        mock_run_agent.assert_not_called()

    async def test_cron_job_error_handling(
        self, scheduler, mock_send_message, mock_run_agent
    ):
        """Test cron job error handling."""
        mock_run_agent.side_effect = Exception("API Error")

        job = {"id": 1, "message": "Failing job", "type": "cron"}

        await scheduler._run_cron_job(job)

        # Error message should be sent
        mock_send_message.assert_called_once()
        call_args = mock_send_message.call_args[0][0]
        assert "Failed" in call_args
        assert "API Error" in call_args


class TestCronJobWorkflow:
    """Test complete cron job workflows."""

    @pytest.fixture
    def mock_send_message(self):
        return AsyncMock()

    @pytest.fixture
    def mock_run_agent(self):
        return AsyncMock(return_value="Task completed")

    async def test_full_workflow_one_time(self, mock_send_message, mock_run_agent):
        """Test complete one-time job workflow: add -> run -> verify disabled."""
        # 1. Create job
        create = CronCreateTool()
        result = await create.execute(message="Test task", delay_minutes=1)
        assert "Reminder set" in result

        # 2. Manually set trigger time to past (simulate time passing)
        jobs = load_cron_jobs()
        jobs[0]["trigger_at"] = (datetime.now() - timedelta(seconds=10)).isoformat()
        save_cron_jobs(jobs)

        # 3. Run scheduler check
        scheduler = Scheduler(
            send_message=mock_send_message, run_agent=mock_run_agent, chat_id=123
        )
        await scheduler._check_one_time_jobs()

        # 4. Verify execution
        mock_run_agent.assert_called_once_with("Test task")
        mock_send_message.assert_called_once()

        # 5. Verify job is disabled
        jobs = load_cron_jobs()
        assert jobs[0]["enabled"] is False

    async def test_full_workflow_interval(self, mock_send_message, mock_run_agent):
        """Test complete interval job workflow: add -> run -> verify rescheduled."""
        # 1. Create interval job
        create = CronCreateTool()
        result = await create.execute(message="Repeat task", interval_seconds=60)
        assert "Interval task" in result

        # 2. Set next_trigger to past
        jobs = load_cron_jobs()
        jobs[0]["next_trigger"] = (datetime.now() - timedelta(seconds=5)).isoformat()
        save_cron_jobs(jobs)

        # 3. Run scheduler check
        scheduler = Scheduler(
            send_message=mock_send_message, run_agent=mock_run_agent, chat_id=123
        )
        await scheduler._check_interval_jobs()

        # 4. Verify execution
        mock_run_agent.assert_called_once_with("Repeat task")

        # 5. Verify job is rescheduled (next_trigger is in future)
        jobs = load_cron_jobs()
        assert jobs[0]["enabled"] is True
        next_trigger = datetime.fromisoformat(jobs[0]["next_trigger"])
        assert next_trigger > datetime.now()

    async def test_add_run_delete_workflow(self, mock_send_message, mock_run_agent):
        """Test add -> run -> delete workflow."""
        # 1. Add job
        create = CronCreateTool()
        await create.execute(message="Temp job", delay_minutes=1)

        # 2. Set to past and run
        jobs = load_cron_jobs()
        jobs[0]["trigger_at"] = (datetime.now() - timedelta(seconds=10)).isoformat()
        save_cron_jobs(jobs)

        scheduler = Scheduler(
            send_message=mock_send_message, run_agent=mock_run_agent, chat_id=123
        )
        await scheduler._check_one_time_jobs()

        # 3. Verify it ran
        mock_run_agent.assert_called_once()

        # 4. Delete job
        delete = CronDeleteTool()
        result = await delete.execute(job_id=1)
        assert "Deleted" in result

        # 5. Verify deleted
        jobs = load_cron_jobs()
        assert len(jobs) == 0
