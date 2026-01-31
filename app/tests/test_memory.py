"""Tests for persistent memory using SQLite."""

import pytest

from memory_db import (add_memory, delete_memory, get_memory_context, init_db,
                       load_all_memories, search_memory)


class TestMemory:
    """Test persistent memory functions."""

    async def test_load_empty_memory(self):
        """Test loading when no memory exists."""
        entries = await load_all_memories()
        assert entries == []

    async def test_add_memory(self):
        """Test adding a memory entry."""
        entry = await add_memory("User's favorite color is blue", "preference")

        assert entry["id"] == 1
        assert entry["content"] == "User's favorite color is blue"
        assert entry["category"] == "preference"
        assert "created_at" in entry

    async def test_add_multiple_memories(self):
        """Test adding multiple memory entries."""
        await add_memory("Fact 1")
        await add_memory("Fact 2")
        entry3 = await add_memory("Fact 3")

        assert entry3["id"] == 3
        entries = await load_all_memories()
        assert len(entries) == 3

    async def test_search_memory(self):
        """Test searching memory entries."""
        await add_memory("User likes Python programming")
        await add_memory("User's birthday is March 15")
        await add_memory("User prefers dark mode")

        results = await search_memory("python")
        assert len(results) == 1
        assert "Python" in results[0]["content"]

    async def test_search_memory_case_insensitive(self):
        """Test that search is case insensitive."""
        await add_memory("User likes PYTHON")

        # SQLite LIKE is case-insensitive for ASCII
        results = await search_memory("python")
        assert len(results) == 1

    async def test_search_memory_no_results(self):
        """Test search with no matching results."""
        await add_memory("User likes JavaScript")

        results = await search_memory("python")
        assert len(results) == 0

    async def test_get_memory_context_empty(self):
        """Test getting context when memory is empty."""
        context = await get_memory_context()
        assert context == ""

    async def test_get_memory_context(self):
        """Test getting memory context string."""
        await add_memory("Fact 1", "general")
        await add_memory("Fact 2")

        context = await get_memory_context()
        assert "## Agent Memory" in context
        assert "Fact 1" in context
        assert "Fact 2" in context
        assert "[general]" in context

    async def test_memory_persistence(self):
        """Test that memory persists across load cycles."""
        await add_memory("Persistent fact")

        # Load fresh
        entries = await load_all_memories()
        assert len(entries) == 1
        assert entries[0]["content"] == "Persistent fact"

    async def test_delete_memory(self):
        """Test deleting a memory entry."""
        entry = await add_memory("To be deleted")
        memory_id = entry["id"]

        # Verify it exists
        entries = await load_all_memories()
        assert len(entries) == 1

        # Delete it
        result = await delete_memory(memory_id)
        assert result is True

        # Verify it's gone
        entries = await load_all_memories()
        assert len(entries) == 0

    async def test_delete_nonexistent_memory(self):
        """Test deleting a memory that doesn't exist."""
        result = await delete_memory(9999)
        assert result is False

    async def test_memory_with_metadata(self):
        """Test adding memory with metadata."""
        entry = await add_memory(
            "Important meeting",
            "calendar",
            metadata={"date": "2024-01-15", "participants": ["Alice", "Bob"]},
        )

        assert entry["id"] == 1
        assert entry["content"] == "Important meeting"
        assert entry["category"] == "calendar"
