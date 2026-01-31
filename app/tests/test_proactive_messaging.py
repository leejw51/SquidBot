"""Tests for proactive messaging (heartbeat and cron jobs)."""

import json
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from scheduler import Scheduler
from tools.cron import load_cron_jobs, save_cron_jobs


class TestCronJobs:
    """Test cron job management."""

    def test_load_empty_cron_jobs(self):
        """Test loading when no cron file exists."""
        jobs = load_cron_jobs()
        assert jobs == []

    def test_save_and_load_cron_jobs(self):
        """Test saving and loading cron jobs."""
        jobs = [
            {
                "id": 1,
                "message": "Test job",
                "type": "cron",
                "cron_expression": "0 9 * * *",
                "enabled": True,
            }
        ]
        save_cron_jobs(jobs)

        loaded = load_cron_jobs()
        assert len(loaded) == 1
        assert loaded[0]["message"] == "Test job"

    def test_one_time_job_structure(self):
        """Test one-time job data structure."""
        trigger_at = datetime.now() + timedelta(minutes=5)
        jobs = [
            {
                "id": 1,
                "message": "Reminder",
                "type": "one_time",
                "trigger_at": trigger_at.isoformat(),
                "enabled": True,
            }
        ]
        save_cron_jobs(jobs)

        loaded = load_cron_jobs()
        assert loaded[0]["type"] == "one_time"
        assert "trigger_at" in loaded[0]


class TestScheduler:
    """Test the scheduler for proactive messaging."""

    @pytest.fixture
    def mock_send_message(self):
        """Mock send_message function."""
        return AsyncMock()

    @pytest.fixture
    def mock_run_agent(self):
        """Mock run_agent function."""
        return AsyncMock(return_value="Agent response")

    @pytest.fixture
    def scheduler(self, mock_send_message, mock_run_agent):
        """Create a scheduler instance for testing."""
        return Scheduler(
            send_message=mock_send_message, run_agent=mock_run_agent, chat_id=12345
        )

    def test_scheduler_init(self, scheduler):
        """Test scheduler initialization."""
        assert scheduler.chat_id == 12345
        assert scheduler._started is False

    def test_set_chat_id(self, scheduler):
        """Test setting chat ID."""
        scheduler.set_chat_id(67890)
        assert scheduler.chat_id == 67890

    @pytest.mark.asyncio
    async def test_run_cron_job_executes_agent(
        self, scheduler, mock_send_message, mock_run_agent
    ):
        """Test that cron jobs execute the agent."""
        job = {"id": 1, "message": "Check TechCrunch and summarize", "type": "cron"}

        await scheduler._run_cron_job(job)

        # Verify agent was called with the job message
        mock_run_agent.assert_called_once_with("Check TechCrunch and summarize")

        # Verify response was sent
        mock_send_message.assert_called_once()
        call_args = mock_send_message.call_args[0][0]
        assert "[Scheduled Task]" in call_args
        assert "Agent response" in call_args

    @pytest.mark.asyncio
    async def test_run_cron_job_handles_error(
        self, scheduler, mock_send_message, mock_run_agent
    ):
        """Test cron job error handling."""
        mock_run_agent.side_effect = Exception("API error")

        job = {"id": 1, "message": "Test task", "type": "cron"}
        await scheduler._run_cron_job(job)

        # Should send error message
        mock_send_message.assert_called()
        call_args = mock_send_message.call_args[0][0]
        assert "Failed" in call_args

    @pytest.mark.asyncio
    async def test_check_one_time_jobs_triggers_due_jobs(
        self, scheduler, mock_send_message, mock_run_agent
    ):
        """Test that due one-time jobs are triggered."""
        # Create a job that's already due
        past_time = datetime.now() - timedelta(minutes=1)
        jobs = [
            {
                "id": 1,
                "message": "Overdue reminder",
                "type": "one_time",
                "trigger_at": past_time.isoformat(),
                "enabled": True,
            }
        ]
        save_cron_jobs(jobs)

        await scheduler._check_one_time_jobs()

        # Verify agent was called
        mock_run_agent.assert_called_once_with("Overdue reminder")

        # Verify message was sent
        mock_send_message.assert_called_once()

        # Verify job is now disabled
        loaded = load_cron_jobs()
        assert loaded[0]["enabled"] is False

    @pytest.mark.asyncio
    async def test_check_one_time_jobs_skips_future_jobs(
        self, scheduler, mock_send_message, mock_run_agent
    ):
        """Test that future jobs are not triggered."""
        future_time = datetime.now() + timedelta(hours=1)
        jobs = [
            {
                "id": 1,
                "message": "Future reminder",
                "type": "one_time",
                "trigger_at": future_time.isoformat(),
                "enabled": True,
            }
        ]
        save_cron_jobs(jobs)

        await scheduler._check_one_time_jobs()

        # Agent should not be called
        mock_run_agent.assert_not_called()

        # Job should still be enabled
        loaded = load_cron_jobs()
        assert loaded[0]["enabled"] is True

    @pytest.mark.asyncio
    async def test_check_one_time_jobs_skips_disabled_jobs(
        self, scheduler, mock_send_message, mock_run_agent
    ):
        """Test that disabled jobs are not triggered."""
        past_time = datetime.now() - timedelta(minutes=1)
        jobs = [
            {
                "id": 1,
                "message": "Disabled reminder",
                "type": "one_time",
                "trigger_at": past_time.isoformat(),
                "enabled": False,
            }
        ]
        save_cron_jobs(jobs)

        await scheduler._check_one_time_jobs()

        mock_run_agent.assert_not_called()


class TestHeartbeat:
    """Test heartbeat functionality."""

    @pytest.fixture
    def mock_send_message(self):
        return AsyncMock()

    @pytest.fixture
    def mock_run_agent(self):
        return AsyncMock(return_value="HEARTBEAT_OK")

    @pytest.fixture
    def scheduler(self, mock_send_message, mock_run_agent):
        return Scheduler(
            send_message=mock_send_message, run_agent=mock_run_agent, chat_id=12345
        )

    @pytest.mark.asyncio
    async def test_heartbeat_no_message_when_ok(
        self, scheduler, mock_send_message, mock_run_agent
    ):
        """Test heartbeat doesn't send message when agent returns HEARTBEAT_OK."""
        mock_run_agent.return_value = "HEARTBEAT_OK"

        await scheduler._heartbeat()

        mock_run_agent.assert_called_once()
        mock_send_message.assert_not_called()

    @pytest.mark.asyncio
    async def test_heartbeat_sends_message_when_content(
        self, scheduler, mock_send_message, mock_run_agent
    ):
        """Test heartbeat sends message when agent has something to say."""
        mock_run_agent.return_value = "Your scheduled task completed!"

        await scheduler._heartbeat()

        mock_run_agent.assert_called_once()
        mock_send_message.assert_called_once_with("Your scheduled task completed!")

    @pytest.mark.asyncio
    async def test_heartbeat_skips_without_chat_id(
        self, mock_send_message, mock_run_agent
    ):
        """Test heartbeat skips when no chat_id is set."""
        scheduler = Scheduler(
            send_message=mock_send_message, run_agent=mock_run_agent, chat_id=None
        )

        await scheduler._heartbeat()

        mock_run_agent.assert_not_called()

    @pytest.mark.asyncio
    async def test_heartbeat_handles_error(
        self, scheduler, mock_send_message, mock_run_agent
    ):
        """Test heartbeat error handling."""
        mock_run_agent.side_effect = Exception("API error")

        # Should not raise
        await scheduler._heartbeat()

        mock_send_message.assert_not_called()
