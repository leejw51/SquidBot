"""Memory tools using SQLite with vector search."""

from ..memory_db import (add_memory, delete_memory, load_all_memories,
                         search_memory, search_memory_semantic)
from .base import Tool


class MemoryAddTool(Tool):
    """Add information to persistent memory."""

    @property
    def name(self) -> str:
        return "memory_add"

    @property
    def description(self) -> str:
        return "Store information in persistent memory with semantic search support. Use this to remember facts, preferences, or important details."

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "content": {
                    "type": "string",
                    "description": "The information to remember",
                },
                "category": {
                    "type": "string",
                    "description": "Optional category (e.g., 'preference', 'fact', 'task')",
                },
            },
            "required": ["content"],
        }

    async def execute(self, content: str, category: str = None) -> str:
        entry = await add_memory(content, category)
        return f"Stored in memory (id={entry['id']}): {content}"


class MemorySearchTool(Tool):
    """Search persistent memory using semantic similarity."""

    @property
    def name(self) -> str:
        return "memory_search"

    @property
    def description(self) -> str:
        return "Search persistent memory using semantic similarity. Finds related memories even if exact words don't match."

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "semantic": {
                    "type": "boolean",
                    "description": "Use semantic search (default true)",
                    "default": True,
                },
            },
            "required": ["query"],
        }

    async def execute(self, query: str, semantic: bool = True) -> str:
        if semantic:
            results = await search_memory_semantic(query)
        else:
            results = await search_memory(query)

        if not results:
            return f"No memory entries found for: {query}"

        lines = [f"Found {len(results)} memories:"]
        for r in results:
            cat = f"[{r['category']}] " if r.get("category") else ""
            sim = f" (similarity: {r['similarity']:.2f})" if "similarity" in r else ""
            lines.append(f"- {cat}{r['content']}{sim}")

        return "\n".join(lines)


class MemoryListTool(Tool):
    """List all memories."""

    @property
    def name(self) -> str:
        return "memory_list"

    @property
    def description(self) -> str:
        return "List all stored memories."

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of memories to return",
                    "default": 20,
                }
            },
            "required": [],
        }

    async def execute(self, limit: int = 20) -> str:
        entries = await load_all_memories(limit)

        if not entries:
            return "No memories stored yet."

        lines = [f"Total memories: {len(entries)}"]
        for e in entries:
            cat = f"[{e['category']}] " if e.get("category") else ""
            lines.append(f"- [{e['id']}] {cat}{e['content']}")

        return "\n".join(lines)


class MemoryDeleteTool(Tool):
    """Delete a memory by ID."""

    @property
    def name(self) -> str:
        return "memory_delete"

    @property
    def description(self) -> str:
        return "Delete a specific memory by its ID."

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "memory_id": {
                    "type": "integer",
                    "description": "ID of the memory to delete",
                }
            },
            "required": ["memory_id"],
        }

    async def execute(self, memory_id: int) -> str:
        success = await delete_memory(memory_id)
        if success:
            return f"Deleted memory id={memory_id}"
        return f"No memory found with id={memory_id}"
