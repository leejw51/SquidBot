"""
Command Lanes - Execution context categorization.

Lanes categorize the context in which commands are executed,
enabling different behaviors for different execution paths.
"""

from enum import Enum


class CommandLane(str, Enum):
    """Command execution lane types."""

    MAIN = "main"  # Primary user interaction
    CRON = "cron"  # Scheduled/cron jobs
    SUBAGENT = "subagent"  # Sub-agent execution
    NESTED = "nested"  # Nested command execution
    WEBHOOK = "webhook"  # Webhook-triggered execution
    PROACTIVE = "proactive"  # Proactive/autonomous messages

    def __str__(self) -> str:
        return self.value

    @property
    def is_user_initiated(self) -> bool:
        """Whether this lane represents user-initiated actions."""
        return self in (CommandLane.MAIN, CommandLane.NESTED)

    @property
    def is_automated(self) -> bool:
        """Whether this lane represents automated actions."""
        return self in (CommandLane.CRON, CommandLane.WEBHOOK, CommandLane.PROACTIVE)


# Convenience exports
LANE_MAIN = CommandLane.MAIN
LANE_CRON = CommandLane.CRON
LANE_SUBAGENT = CommandLane.SUBAGENT
LANE_NESTED = CommandLane.NESTED
LANE_WEBHOOK = CommandLane.WEBHOOK
LANE_PROACTIVE = CommandLane.PROACTIVE
