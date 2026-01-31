---
name: reminder
description: Set reminders and scheduled tasks
---
When user wants to set a reminder:

1. Extract the message and time
2. Use `cron_create` tool with appropriate delay_minutes or cron_expression
3. Confirm the reminder was set

Examples:
- "Remind me in 10 minutes" → delay_minutes=10
- "Remind me daily at 9am" → cron_expression="0 9 * * *"
