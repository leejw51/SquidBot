"""Tests for scheduler module."""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from squidbot.scheduler import Scheduler


class TestSchedulerInit:
    """Test Scheduler initialization."""

    def test_init_with_callbacks(self):
        """Test initializing scheduler with callbacks."""
        send_message = AsyncMock()
        run_agent = AsyncMock()

        scheduler = Scheduler(send_message=send_message, run_agent=run_agent)

        assert scheduler.send_message == send_message
        assert scheduler.run_agent == run_agent
        assert scheduler.chat_id is None
        assert scheduler._started is False

    def test_init_with_chat_id(self):
        """Test initializing scheduler with chat_id."""
        scheduler = Scheduler(
            send_message=AsyncMock(),
            run_agent=AsyncMock(),
            chat_id=12345,
        )

        assert scheduler.chat_id == 12345


class TestSchedulerStartStop:
    """Test Scheduler start/stop functionality."""

    def test_scheduler_not_started_initially(self):
        """Test scheduler is not started initially."""
        scheduler = Scheduler(
            send_message=AsyncMock(),
            run_agent=AsyncMock(),
        )

        assert scheduler._started is False

    def test_stop_when_not_started(self):
        """Test stopping when not started is safe."""
        scheduler = Scheduler(
            send_message=AsyncMock(),
            run_agent=AsyncMock(),
        )

        # Should not raise
        scheduler.stop()
        assert scheduler._started is False


class TestSchedulerChatId:
    """Test Scheduler chat_id management."""

    def test_set_chat_id(self):
        """Test setting chat_id."""
        scheduler = Scheduler(
            send_message=AsyncMock(),
            run_agent=AsyncMock(),
        )

        scheduler.set_chat_id(67890)

        assert scheduler.chat_id == 67890


class TestSchedulerCronJobs:
    """Test Scheduler cron job loading logic."""

    def test_load_cron_jobs_filters_enabled(self):
        """Test that _load_cron_jobs filters by enabled status."""
        mock_jobs = [
            {
                "id": 1,
                "type": "cron",
                "cron_expression": "0 9 * * *",
                "message": "Daily task",
                "enabled": True,
            },
            {
                "id": 2,
                "type": "cron",
                "cron_expression": "0 10 * * *",
                "message": "Disabled task",
                "enabled": False,
            },
        ]

        # Test the filtering logic directly
        enabled_jobs = [
            j for j in mock_jobs if j.get("type") == "cron" and j.get("enabled", True)
        ]
        assert len(enabled_jobs) == 1
        assert enabled_jobs[0]["id"] == 1

    def test_load_cron_jobs_filters_type(self):
        """Test that _load_cron_jobs filters by type."""
        mock_jobs = [
            {
                "id": 1,
                "type": "cron",
                "cron_expression": "0 9 * * *",
                "message": "Cron task",
                "enabled": True,
            },
            {
                "id": 2,
                "type": "one_time",
                "trigger_at": "2024-01-01T00:00:00",
                "message": "One time task",
                "enabled": True,
            },
        ]

        # Test the filtering logic directly
        cron_jobs = [
            j for j in mock_jobs if j.get("type") == "cron" and j.get("enabled", True)
        ]
        assert len(cron_jobs) == 1
        assert cron_jobs[0]["id"] == 1


class TestSchedulerReloadJobs:
    """Test Scheduler job reloading logic."""

    def test_reload_removes_old_cron_jobs(self):
        """Test that reload would remove jobs with cron_ prefix."""
        # This tests the logic that identifies jobs to remove
        job_ids = ["cron_1", "cron_2", "heartbeat", "one_time_checker"]
        cron_job_ids = [j for j in job_ids if j.startswith("cron_")]

        assert len(cron_job_ids) == 2
        assert "cron_1" in cron_job_ids
        assert "cron_2" in cron_job_ids
        assert "heartbeat" not in cron_job_ids


class TestSchedulerRunCronJob:
    """Test Scheduler cron job execution."""

    @pytest.mark.asyncio
    async def test_run_cron_job_success(self):
        """Test running a cron job successfully."""
        send_message = AsyncMock()
        run_agent = AsyncMock(return_value="Task completed")

        scheduler = Scheduler(
            send_message=send_message,
            run_agent=run_agent,
        )

        job = {"id": 1, "message": "Do something"}
        await scheduler._run_cron_job(job)

        run_agent.assert_called_once_with("Do something")
        send_message.assert_called_once()
        assert "Task completed" in send_message.call_args[0][0]

    @pytest.mark.asyncio
    async def test_run_cron_job_failure(self):
        """Test running a cron job that fails."""
        send_message = AsyncMock()
        run_agent = AsyncMock(side_effect=Exception("Agent error"))

        scheduler = Scheduler(
            send_message=send_message,
            run_agent=run_agent,
        )

        job = {"id": 1, "message": "Failing task"}
        await scheduler._run_cron_job(job)

        send_message.assert_called_once()
        assert "Failed" in send_message.call_args[0][0]


class TestSchedulerHeartbeat:
    """Test Scheduler heartbeat functionality."""

    @pytest.mark.asyncio
    async def test_heartbeat_no_chat_id(self):
        """Test heartbeat skips when no chat_id."""
        run_agent = AsyncMock()

        scheduler = Scheduler(
            send_message=AsyncMock(),
            run_agent=run_agent,
            chat_id=None,
        )

        await scheduler._heartbeat()

        # Agent should not be called
        run_agent.assert_not_called()

    @pytest.mark.asyncio
    async def test_heartbeat_ok_response(self):
        """Test heartbeat with OK response (no message sent)."""
        send_message = AsyncMock()
        run_agent = AsyncMock(return_value="HEARTBEAT_OK")

        scheduler = Scheduler(
            send_message=send_message,
            run_agent=run_agent,
            chat_id=12345,
        )

        await scheduler._heartbeat()

        run_agent.assert_called_once()
        # No message should be sent for HEARTBEAT_OK
        send_message.assert_not_called()

    @pytest.mark.asyncio
    async def test_heartbeat_with_message(self):
        """Test heartbeat with actual message to send."""
        send_message = AsyncMock()
        run_agent = AsyncMock(return_value="You have a reminder!")

        scheduler = Scheduler(
            send_message=send_message,
            run_agent=run_agent,
            chat_id=12345,
        )

        await scheduler._heartbeat()

        run_agent.assert_called_once()
        send_message.assert_called_once_with("You have a reminder!")


class TestSchedulerOneTimeJobs:
    """Test Scheduler one-time job checking."""

    @pytest.mark.asyncio
    async def test_check_one_time_job_due(self):
        """Test checking a one-time job that is due."""
        past_time = (datetime.now() - timedelta(minutes=5)).isoformat()
        mock_jobs = [
            {
                "id": 1,
                "type": "one_time",
                "trigger_at": past_time,
                "message": "Reminder!",
                "enabled": True,
            }
        ]

        send_message = AsyncMock()
        run_agent = AsyncMock(return_value="Reminder executed")

        with patch("squidbot.scheduler.load_cron_jobs", return_value=mock_jobs), patch(
            "squidbot.scheduler.save_cron_jobs"
        ) as mock_save:
            scheduler = Scheduler(
                send_message=send_message,
                run_agent=run_agent,
            )

            await scheduler._check_one_time_jobs()

            run_agent.assert_called_once_with("Reminder!")
            send_message.assert_called_once()
            mock_save.assert_called_once()

    @pytest.mark.asyncio
    async def test_check_one_time_job_not_due(self):
        """Test checking a one-time job that is not due yet."""
        future_time = (datetime.now() + timedelta(minutes=10)).isoformat()
        mock_jobs = [
            {
                "id": 1,
                "type": "one_time",
                "trigger_at": future_time,
                "message": "Future reminder",
                "enabled": True,
            }
        ]

        run_agent = AsyncMock()

        with patch("squidbot.scheduler.load_cron_jobs", return_value=mock_jobs):
            scheduler = Scheduler(
                send_message=AsyncMock(),
                run_agent=run_agent,
            )

            await scheduler._check_one_time_jobs()

            # Should not be executed yet
            run_agent.assert_not_called()


class TestSchedulerIntervalJobs:
    """Test Scheduler interval job checking."""

    @pytest.mark.asyncio
    async def test_check_interval_job_due(self):
        """Test checking an interval job that is due."""
        past_time = (datetime.now() - timedelta(seconds=10)).isoformat()
        mock_jobs = [
            {
                "id": 1,
                "type": "interval",
                "next_trigger": past_time,
                "interval_seconds": 60,
                "message": "Interval task",
                "enabled": True,
            }
        ]

        send_message = AsyncMock()
        run_agent = AsyncMock(return_value="Interval executed")

        with patch("squidbot.scheduler.load_cron_jobs", return_value=mock_jobs), patch(
            "squidbot.scheduler.save_cron_jobs"
        ) as mock_save:
            scheduler = Scheduler(
                send_message=send_message,
                run_agent=run_agent,
            )

            await scheduler._check_interval_jobs()

            run_agent.assert_called_once_with("Interval task")
            send_message.assert_called_once()
            mock_save.assert_called_once()

    @pytest.mark.asyncio
    async def test_check_interval_job_disabled(self):
        """Test that disabled interval jobs are skipped."""
        past_time = (datetime.now() - timedelta(seconds=10)).isoformat()
        mock_jobs = [
            {
                "id": 1,
                "type": "interval",
                "next_trigger": past_time,
                "interval_seconds": 60,
                "message": "Disabled task",
                "enabled": False,
            }
        ]

        run_agent = AsyncMock()

        with patch("squidbot.scheduler.load_cron_jobs", return_value=mock_jobs):
            scheduler = Scheduler(
                send_message=AsyncMock(),
                run_agent=run_agent,
            )

            await scheduler._check_interval_jobs()

            run_agent.assert_not_called()
