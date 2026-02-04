"""Scheduler for proactive messaging - cron jobs and heartbeat."""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Awaitable, Callable

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from .config import HEARTBEAT_INTERVAL_MINUTES
from .tools.cron import load_cron_jobs, save_cron_jobs

logger = logging.getLogger(__name__)


class Scheduler:
    """Manages scheduled tasks and heartbeat."""

    def __init__(
        self,
        send_message: Callable[[str], Awaitable[None]],
        run_agent: Callable[[str], Awaitable[str]],
        chat_id: int | None = None,
    ):
        self.scheduler = AsyncIOScheduler()
        self.send_message = send_message
        self.run_agent = run_agent
        self.chat_id = chat_id  # Default chat to send proactive messages
        self._started = False

    def start(self):
        """Start the scheduler."""
        if self._started:
            return

        # Load and schedule cron jobs
        self._load_cron_jobs()

        # Add heartbeat job
        if HEARTBEAT_INTERVAL_MINUTES > 0:
            self.scheduler.add_job(
                self._heartbeat,
                IntervalTrigger(minutes=HEARTBEAT_INTERVAL_MINUTES),
                id="heartbeat",
                replace_existing=True,
            )
            logger.info(
                f"Heartbeat scheduled every {HEARTBEAT_INTERVAL_MINUTES} minutes"
            )

        # Check one-time jobs every minute
        self.scheduler.add_job(
            self._check_one_time_jobs,
            IntervalTrigger(minutes=1),
            id="one_time_checker",
            replace_existing=True,
        )

        # Check interval jobs every 5 seconds
        self.scheduler.add_job(
            self._check_interval_jobs,
            IntervalTrigger(seconds=5),
            id="interval_checker",
            replace_existing=True,
        )

        self.scheduler.start()
        self._started = True
        logger.info("Scheduler started")

    def stop(self):
        """Stop the scheduler."""
        if self._started:
            self.scheduler.shutdown()
            self._started = False

    def _load_cron_jobs(self):
        """Load cron jobs from storage and schedule them."""
        jobs = load_cron_jobs()
        for job in jobs:
            if job.get("type") == "cron" and job.get("enabled", True):
                try:
                    self.scheduler.add_job(
                        self._run_cron_job,
                        CronTrigger.from_crontab(job["cron_expression"]),
                        id=f"cron_{job['id']}",
                        args=[job],
                        replace_existing=True,
                    )
                    logger.info(
                        f"Scheduled cron job {job['id']}: {job['cron_expression']}"
                    )
                except Exception as e:
                    logger.error(f"Failed to schedule job {job['id']}: {e}")

    async def _run_cron_job(self, job: dict):
        """Execute a cron job by running the agent."""
        logger.info(f"Running cron job {job['id']}: {job['message']}")
        try:
            # Run agent to actually perform the task
            response = await self.run_agent(job["message"])
            await self.send_message(f"[Scheduled Task]\n{response}")
        except Exception as e:
            logger.error(f"Failed to run cron job: {e}")
            await self.send_message(
                f"[Scheduled Task Failed] {job['message']}\nError: {str(e)}"
            )

    async def _check_one_time_jobs(self):
        """Check and execute one-time jobs that are due."""
        jobs = load_cron_jobs()
        now = datetime.now()
        updated = False

        for job in jobs:
            if job.get("type") != "one_time" or not job.get("enabled", True):
                continue

            trigger_at = datetime.fromisoformat(job["trigger_at"])
            if trigger_at <= now:
                logger.info(f"Triggering one-time job {job['id']}: {job['message']}")
                try:
                    # Run agent to actually perform the task
                    response = await self.run_agent(job["message"])
                    await self.send_message(f"[Reminder]\n{response}")
                    job["enabled"] = False  # Disable after triggering
                    updated = True
                except Exception as e:
                    logger.error(f"Failed to run reminder job: {e}")
                    await self.send_message(
                        f"[Reminder Failed] {job['message']}\nError: {str(e)}"
                    )
                    job["enabled"] = False
                    updated = True

        if updated:
            save_cron_jobs(jobs)

    async def _check_interval_jobs(self):
        """Check and execute interval jobs that are due."""
        jobs = load_cron_jobs()
        now = datetime.now()
        updated = False

        for job in jobs:
            if job.get("type") != "interval" or not job.get("enabled", True):
                continue

            next_trigger = datetime.fromisoformat(
                job.get("next_trigger", now.isoformat())
            )
            if next_trigger <= now:
                logger.info(f"Triggering interval job {job['id']}: {job['message']}")
                try:
                    # Run agent to actually perform the task
                    response = await self.run_agent(job["message"])
                    await self.send_message(f"[Interval Task]\n{response}")

                    # Schedule next trigger
                    interval = job.get("interval_seconds", 60)
                    job["next_trigger"] = (
                        datetime.now() + timedelta(seconds=interval)
                    ).isoformat()
                    updated = True
                except Exception as e:
                    logger.error(f"Failed to run interval job: {e}")
                    await self.send_message(
                        f"[Interval Task Failed] {job['message']}\nError: {str(e)}"
                    )
                    # Still schedule next trigger
                    interval = job.get("interval_seconds", 60)
                    job["next_trigger"] = (
                        datetime.now() + timedelta(seconds=interval)
                    ).isoformat()
                    updated = True

        if updated:
            save_cron_jobs(jobs)

    async def _heartbeat(self):
        """Periodic heartbeat - ask agent if there's anything to report."""
        if not self.chat_id:
            return

        logger.info("Running heartbeat check")
        try:
            # Ask the agent if there's anything to proactively share
            response = await self.run_agent(
                "This is a periodic heartbeat check. "
                "If there's anything important to proactively share with the user "
                "(e.g., completed background tasks, reminders, or relevant updates), "
                "please say it. Otherwise, respond with just 'HEARTBEAT_OK' and nothing else."
            )

            if response.strip() != "HEARTBEAT_OK":
                await self.send_message(response)
        except Exception as e:
            logger.error(f"Heartbeat error: {e}")

    def reload_jobs(self):
        """Reload cron jobs from storage."""
        # Remove existing cron jobs
        for job in self.scheduler.get_jobs():
            if job.id.startswith("cron_"):
                job.remove()

        # Reload
        self._load_cron_jobs()

    def set_chat_id(self, chat_id: int):
        """Set the default chat ID for proactive messages."""
        self.chat_id = chat_id
