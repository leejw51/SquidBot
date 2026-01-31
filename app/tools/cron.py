"""Cron/scheduling tools for proactive messaging."""

import json
from datetime import datetime, timedelta
from typing import Optional

from config import CRON_FILE
from tools.base import Tool


def load_cron_jobs() -> list[dict]:
    """Load cron jobs from file."""
    if not CRON_FILE.exists():
        return []
    try:
        with open(CRON_FILE, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return []


def save_cron_jobs(jobs: list[dict]) -> None:
    """Save cron jobs to file."""
    with open(CRON_FILE, "w") as f:
        json.dump(jobs, f, indent=2, default=str)


class CronCreateTool(Tool):
    """Create a scheduled reminder/task."""

    @property
    def name(self) -> str:
        return "cron_create"

    @property
    def description(self) -> str:
        return "Create a scheduled task. The agent will execute the task (using tools if needed) at the specified time and send the result to the user."

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "message": {
                    "type": "string",
                    "description": "Task/prompt for the agent to execute when triggered (e.g., 'Check TechCrunch for latest news and summarize')",
                },
                "delay_minutes": {
                    "type": "integer",
                    "description": "Minutes from now to trigger (for one-time reminders)",
                },
                "interval_seconds": {
                    "type": "integer",
                    "description": "Repeat every N seconds (for recurring interval tasks, e.g., 20 for every 20 seconds)",
                },
                "cron_expression": {
                    "type": "string",
                    "description": "Cron expression for recurring tasks (e.g., '0 9 * * *' for daily at 9am)",
                },
                "recurring": {
                    "type": "boolean",
                    "description": "Whether this is a recurring task",
                    "default": False,
                },
            },
            "required": ["message"],
        }

    async def execute(
        self,
        message: str,
        delay_minutes: Optional[int] = None,
        interval_seconds: Optional[int] = None,
        cron_expression: Optional[str] = None,
        recurring: bool = False,
    ) -> str:
        jobs = load_cron_jobs()

        job = {
            "id": len(jobs) + 1,
            "message": message,
            "created_at": datetime.now().isoformat(),
            "recurring": recurring,
            "enabled": True,
        }

        if delay_minutes:
            trigger_at = datetime.now() + timedelta(minutes=delay_minutes)
            job["trigger_at"] = trigger_at.isoformat()
            job["type"] = "one_time"
        elif interval_seconds:
            job["interval_seconds"] = interval_seconds
            job["type"] = "interval"
            job["recurring"] = True
            # Set next trigger time
            job["next_trigger"] = (
                datetime.now() + timedelta(seconds=interval_seconds)
            ).isoformat()
        elif cron_expression:
            job["cron_expression"] = cron_expression
            job["type"] = "cron"
        else:
            return "Error: Must specify delay_minutes, interval_seconds, or cron_expression"

        jobs.append(job)
        save_cron_jobs(jobs)

        if delay_minutes:
            return f"Reminder set for {delay_minutes} minutes from now (id={job['id']}): {message}"
        elif interval_seconds:
            return f"Interval task scheduled every {interval_seconds} seconds (id={job['id']}): {message}"
        else:
            return f"Recurring task scheduled with cron '{cron_expression}' (id={job['id']}): {message}"


class CronListTool(Tool):
    """List scheduled tasks."""

    @property
    def name(self) -> str:
        return "cron_list"

    @property
    def description(self) -> str:
        return "List all scheduled reminders and tasks."

    @property
    def parameters(self) -> dict:
        return {"type": "object", "properties": {}, "required": []}

    async def execute(self) -> str:
        jobs = load_cron_jobs()
        if not jobs:
            return "No scheduled tasks."

        lines = [f"Scheduled tasks ({len(jobs)}):"]
        for job in jobs:
            status = "enabled" if job.get("enabled", True) else "disabled"
            job_type = job.get("type", "unknown")

            if job_type == "one_time":
                lines.append(
                    f"- [{job['id']}] {status} | At {job['trigger_at']}: {job['message']}"
                )
            elif job_type == "interval":
                lines.append(
                    f"- [{job['id']}] {status} | Every {job['interval_seconds']}s: {job['message']}"
                )
            elif job_type == "cron":
                lines.append(
                    f"- [{job['id']}] {status} | Cron {job['cron_expression']}: {job['message']}"
                )
            else:
                lines.append(f"- [{job['id']}] {status} | {job['message']}")

        return "\n".join(lines)


class CronDeleteTool(Tool):
    """Delete a scheduled task."""

    @property
    def name(self) -> str:
        return "cron_delete"

    @property
    def description(self) -> str:
        return "Delete a scheduled task by ID. Use cron_list first to see job IDs. Use cron_clear to delete ALL jobs."

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "job_id": {"type": "integer", "description": "ID of the job to delete"}
            },
            "required": ["job_id"],
        }

    async def execute(self, job_id: int) -> str:
        # Ensure job_id is an integer (LLM might pass string)
        job_id = int(job_id)

        jobs = load_cron_jobs()
        original_len = len(jobs)
        jobs = [j for j in jobs if j["id"] != job_id]

        if len(jobs) == original_len:
            return f"No job found with id={job_id}"

        save_cron_jobs(jobs)
        return f"Deleted job id={job_id}"


class CronClearTool(Tool):
    """Clear all scheduled tasks."""

    @property
    def name(self) -> str:
        return "cron_clear"

    @property
    def description(self) -> str:
        return "Delete ALL scheduled tasks. Use this to clear all cron jobs at once."

    @property
    def parameters(self) -> dict:
        return {"type": "object", "properties": {}, "required": []}

    async def execute(self) -> str:
        jobs = load_cron_jobs()
        count = len(jobs)

        if count == 0:
            return "No scheduled tasks to clear."

        save_cron_jobs([])
        return f"Cleared all {count} scheduled task(s)."
