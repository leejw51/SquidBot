"""Core autonomous agent loop with tool chaining."""

import asyncio
import json
import logging
from typing import Any

from openai import AsyncOpenAI

from character import get_character_prompt
from config import OPENAI_API_KEY, OPENAI_MODEL
from memory_db import get_memory_context
from skills import get_skills_context
from tools import get_openai_tools, get_tool_by_name

logger = logging.getLogger(__name__)

# Initialize OpenAI client
client = AsyncOpenAI(api_key=OPENAI_API_KEY)

# Base system prompt
BASE_SYSTEM_PROMPT = """You are an autonomous AI agent with access to tools. You can:
- Remember information using memory tools (with semantic search)
- Search the web for current information (web_search)
- Browse specific websites using Playwright browser tools
- Take screenshots of websites (browser_screenshot)
- Schedule reminders and recurring tasks (cron_create)

CRITICAL: You MUST use tools to perform actions. NEVER pretend or claim to have done something without actually calling the tool. If asked to visit a website, you MUST call browser_navigate. If asked to take a screenshot, you MUST call browser_screenshot.

Available Browser Tools:
- browser_navigate: Open a URL in the browser (REQUIRED before any other browser action)
- browser_get_text: Get the text content of the current page
- browser_screenshot: Take a screenshot of the current page (returns image file)
- browser_snapshot: Get accessibility tree of the page
- browser_click: Click an element on the page
- browser_type: Type text into an input field

IMPORTANT - Tool Selection:
- To visit a website: MUST call browser_navigate first
- To take a screenshot: MUST call browser_navigate, then browser_screenshot
- To read page content: MUST call browser_navigate, then browser_get_text
- For general searches: use web_search

When given a task, use the appropriate tools. Do NOT say you did something unless you actually called the tool.
"""


async def build_system_prompt() -> str:
    """Build the complete system prompt with character, skills, and memory."""
    parts = [BASE_SYSTEM_PROMPT]

    # Add character/personality
    character_prompt = await get_character_prompt()
    if character_prompt:
        parts.append(character_prompt)

    # Add skills
    skills_context = await get_skills_context()
    if skills_context:
        parts.append(skills_context)

    # Add memory context
    memory_context = await get_memory_context()
    if memory_context:
        parts.append(memory_context)

    return "\n\n".join(parts)


async def execute_tool(name: str, arguments: dict) -> str:
    """Execute a tool by name with given arguments."""
    tool = get_tool_by_name(name)
    if not tool:
        return f"Error: Unknown tool '{name}'"

    try:
        result = await tool.execute(**arguments)
        return str(result)
    except Exception as e:
        logger.exception(f"Tool execution error: {name}")
        return f"Error executing {name}: {str(e)}"


async def run_agent(
    user_message: str, history: list[dict] | None = None, max_iterations: int = 10
) -> str:
    """
    Run the autonomous agent loop.

    The agent will:
    1. Send message to LLM
    2. If LLM returns tool calls, execute them
    3. Add results to history and loop back to step 1
    4. If LLM returns text, return it (loop ends)

    Args:
        user_message: The user's input message
        history: Optional conversation history
        max_iterations: Maximum tool-calling iterations (safety limit)

    Returns:
        The agent's final text response
    """
    if history is None:
        history = []

    # Build system prompt with character, skills, and memory
    system_prompt = await build_system_prompt()

    # Prepare messages
    messages = [
        {"role": "system", "content": system_prompt},
        *history,
        {"role": "user", "content": user_message},
    ]

    # Get tools
    tools = get_openai_tools()

    iteration = 0
    while iteration < max_iterations:
        iteration += 1
        logger.info(f"Agent iteration {iteration}")

        # Call OpenAI
        response = await client.chat.completions.create(
            model=OPENAI_MODEL, messages=messages, tools=tools, tool_choice="auto"
        )

        assistant_message = response.choices[0].message

        # Check if we have tool calls
        if assistant_message.tool_calls:
            # Add assistant message to history
            messages.append(
                {
                    "role": "assistant",
                    "content": assistant_message.content or "",
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments,
                            },
                        }
                        for tc in assistant_message.tool_calls
                    ],
                }
            )

            # Execute tools in parallel
            tool_tasks = []
            for tc in assistant_message.tool_calls:
                name = tc.function.name
                try:
                    args = json.loads(tc.function.arguments)
                except json.JSONDecodeError:
                    args = {}

                logger.info(f"Executing tool: {name} with args: {args}")
                tool_tasks.append((tc.id, name, execute_tool(name, args)))

            # Gather results
            results = await asyncio.gather(*[t[2] for t in tool_tasks])

            # Add tool results to messages
            for (tool_call_id, tool_name, _), result in zip(tool_tasks, results):
                logger.info(f"Tool {tool_name} result: {result[:200]}...")
                messages.append(
                    {"role": "tool", "tool_call_id": tool_call_id, "content": result}
                )

            # Continue loop - send results back to LLM
            continue

        else:
            # No tool calls - we have a final response
            final_response = assistant_message.content or ""
            logger.info(f"Agent complete after {iteration} iterations")
            return final_response

    # Max iterations reached
    logger.warning(f"Agent hit max iterations ({max_iterations})")
    return "I apologize, but I've reached the maximum number of steps for this task. Here's what I've done so far - please let me know if you'd like me to continue."


async def run_agent_with_history(
    user_message: str, session_history: list[dict]
) -> tuple[str, list[dict]]:
    """
    Run agent and return updated history.

    Args:
        user_message: User input
        session_history: Existing session history

    Returns:
        Tuple of (response, updated_history)
    """
    response = await run_agent(user_message, session_history)

    # Update history with this exchange
    session_history.append({"role": "user", "content": user_message})
    session_history.append({"role": "assistant", "content": response})

    # Keep history manageable (last 20 exchanges)
    if len(session_history) > 40:
        session_history = session_history[-40:]

    return response, session_history
