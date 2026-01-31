"""Persistent memory using SQLite with vector search (sqlite-vec)."""

import asyncio
import json
import struct
from datetime import datetime
from pathlib import Path
from typing import Optional

import aiosqlite
import numpy as np
from openai import AsyncOpenAI

from config import DATA_DIR, OPENAI_API_KEY

# Database path
DB_PATH = DATA_DIR / "memory.db"

# Embedding model
EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIM = 1536

# OpenAI client for embeddings
_client: Optional[AsyncOpenAI] = None


def get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(api_key=OPENAI_API_KEY)
    return _client


def serialize_vector(vector: list[float]) -> bytes:
    """Serialize vector to bytes for sqlite-vec."""
    return struct.pack(f"{len(vector)}f", *vector)


def deserialize_vector(data: bytes) -> list[float]:
    """Deserialize bytes to vector."""
    n = len(data) // 4
    return list(struct.unpack(f"{n}f", data))


async def get_embedding(text: str) -> list[float]:
    """Get embedding vector for text using OpenAI."""
    client = get_client()
    response = await client.embeddings.create(model=EMBEDDING_MODEL, input=text)
    return response.data[0].embedding


async def init_db():
    """Initialize the database with tables."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    async with aiosqlite.connect(DB_PATH) as db:
        # Enable sqlite-vec extension if available
        try:
            await db.execute("SELECT load_extension('vec0')")
        except Exception:
            pass  # Extension may not be available

        # Create memories table
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                content TEXT NOT NULL,
                category TEXT,
                embedding BLOB,
                created_at TEXT NOT NULL,
                metadata TEXT
            )
        """
        )

        # Create index for faster searches
        await db.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_memories_category
            ON memories(category)
        """
        )

        await db.commit()


async def add_memory(
    content: str,
    category: Optional[str] = None,
    metadata: Optional[dict] = None,
    with_embedding: bool = True,
) -> dict:
    """Add a new memory entry with optional embedding."""
    await init_db()

    embedding_bytes = None
    if with_embedding:
        try:
            embedding = await get_embedding(content)
            embedding_bytes = serialize_vector(embedding)
        except Exception:
            pass  # Continue without embedding

    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """
            INSERT INTO memories (content, category, embedding, created_at, metadata)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                content,
                category,
                embedding_bytes,
                datetime.now().isoformat(),
                json.dumps(metadata) if metadata else None,
            ),
        )
        await db.commit()

        entry_id = cursor.lastrowid

    return {
        "id": entry_id,
        "content": content,
        "category": category,
        "created_at": datetime.now().isoformat(),
    }


async def search_memory(query: str, limit: int = 10) -> list[dict]:
    """Search memories by text content."""
    await init_db()

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """
            SELECT id, content, category, created_at, metadata
            FROM memories
            WHERE content LIKE ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (f"%{query}%", limit),
        )
        rows = await cursor.fetchall()

    return [
        {
            "id": row["id"],
            "content": row["content"],
            "category": row["category"],
            "created_at": row["created_at"],
            "metadata": json.loads(row["metadata"]) if row["metadata"] else None,
        }
        for row in rows
    ]


async def search_memory_semantic(query: str, limit: int = 5) -> list[dict]:
    """Search memories using semantic similarity (vector search)."""
    await init_db()

    try:
        query_embedding = await get_embedding(query)
    except Exception:
        # Fallback to text search if embedding fails
        return await search_memory(query, limit)

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row

        # Get all memories with embeddings
        cursor = await db.execute(
            """
            SELECT id, content, category, created_at, metadata, embedding
            FROM memories
            WHERE embedding IS NOT NULL
            """
        )
        rows = await cursor.fetchall()

    if not rows:
        return []

    # Calculate cosine similarity
    results = []
    query_vec = np.array(query_embedding)
    query_norm = np.linalg.norm(query_vec)

    for row in rows:
        if row["embedding"]:
            mem_vec = np.array(deserialize_vector(row["embedding"]))
            mem_norm = np.linalg.norm(mem_vec)

            if query_norm > 0 and mem_norm > 0:
                similarity = np.dot(query_vec, mem_vec) / (query_norm * mem_norm)
            else:
                similarity = 0

            results.append(
                {
                    "id": row["id"],
                    "content": row["content"],
                    "category": row["category"],
                    "created_at": row["created_at"],
                    "metadata": (
                        json.loads(row["metadata"]) if row["metadata"] else None
                    ),
                    "similarity": float(similarity),
                }
            )

    # Sort by similarity and return top results
    results.sort(key=lambda x: x["similarity"], reverse=True)
    return results[:limit]


async def load_all_memories(limit: int = 100) -> list[dict]:
    """Load all memories."""
    await init_db()

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """
            SELECT id, content, category, created_at, metadata
            FROM memories
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (limit,),
        )
        rows = await cursor.fetchall()

    return [
        {
            "id": row["id"],
            "content": row["content"],
            "category": row["category"],
            "created_at": row["created_at"],
            "metadata": json.loads(row["metadata"]) if row["metadata"] else None,
        }
        for row in rows
    ]


async def delete_memory(memory_id: int) -> bool:
    """Delete a memory by ID."""
    await init_db()

    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
        await db.commit()
        return cursor.rowcount > 0


async def get_memory_context(limit: int = 50) -> str:
    """Get memory as context string for system prompt."""
    memories = await load_all_memories(limit)

    if not memories:
        return ""

    lines = ["## Agent Memory"]
    for entry in memories:
        cat = f"[{entry['category']}] " if entry.get("category") else ""
        lines.append(f"- {cat}{entry['content']}")

    return "\n".join(lines)
