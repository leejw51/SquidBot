"""Persistent memory using SQLite with native vector search (sqlite-vec).

Supports large documents with chunking and fast KNN search via vec0 virtual table.
"""

import json
import logging
import sqlite3
import struct
from datetime import datetime
from pathlib import Path
from typing import Optional

import aiosqlite
from openai import AsyncOpenAI

from config import DATA_DIR, OPENAI_API_KEY

logger = logging.getLogger(__name__)

# Database path
DB_PATH = DATA_DIR / "memory.db"

# Embedding model
EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIM = 1536

# Chunking settings for large documents
CHUNK_SIZE = 500  # tokens (approx chars / 4)
CHUNK_OVERLAP = 100

# OpenAI client for embeddings
_client: Optional[AsyncOpenAI] = None

# sqlite-vec availability flag
_vec_available: Optional[bool] = None


def get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(api_key=OPENAI_API_KEY)
    return _client


def serialize_f32(vector: list[float]) -> bytes:
    """Serialize vector to bytes for sqlite-vec (float32 format)."""
    return struct.pack(f"{len(vector)}f", *vector)


def deserialize_f32(data: bytes) -> list[float]:
    """Deserialize bytes to vector."""
    n = len(data) // 4
    return list(struct.unpack(f"{n}f", data))


def _check_vec_available(conn: sqlite3.Connection) -> bool:
    """Check if sqlite-vec extension is available."""
    global _vec_available
    if _vec_available is not None:
        return _vec_available

    try:
        import sqlite_vec

        conn.enable_load_extension(True)
        sqlite_vec.load(conn)
        conn.enable_load_extension(False)
        _vec_available = True
        logger.info("sqlite-vec extension loaded successfully")
    except Exception as e:
        _vec_available = False
        logger.warning(f"sqlite-vec not available, using fallback: {e}")

    return _vec_available


def _load_vec_extension(conn: sqlite3.Connection) -> bool:
    """Load sqlite-vec extension into connection."""
    try:
        import sqlite_vec

        conn.enable_load_extension(True)
        sqlite_vec.load(conn)
        conn.enable_load_extension(False)
        return True
    except Exception:
        return False


async def get_embedding(text: str) -> list[float]:
    """Get embedding vector for text using OpenAI."""
    client = get_client()
    response = await client.embeddings.create(model=EMBEDDING_MODEL, input=text)
    return response.data[0].embedding


def chunk_text(
    text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP
) -> list[dict]:
    """Split text into overlapping chunks for large documents.

    Returns list of dicts with 'text', 'start', 'end' positions.
    """
    # Approximate tokens as chars / 4
    char_chunk_size = chunk_size * 4
    char_overlap = overlap * 4

    if len(text) <= char_chunk_size:
        return [{"text": text, "start": 0, "end": len(text)}]

    chunks = []
    start = 0

    while start < len(text):
        end = min(start + char_chunk_size, len(text))

        # Try to break at sentence/paragraph boundary
        if end < len(text):
            # Look for good break points
            for sep in ["\n\n", "\n", ". ", "! ", "? ", ", "]:
                break_pos = text.rfind(sep, start + char_chunk_size // 2, end)
                if break_pos != -1:
                    end = break_pos + len(sep)
                    break

        chunks.append(
            {
                "text": text[start:end].strip(),
                "start": start,
                "end": end,
            }
        )

        # Move start with overlap
        start = end - char_overlap if end < len(text) else end

    return [c for c in chunks if c["text"]]  # Filter empty chunks


def init_db_sync(db_path: Path = DB_PATH) -> bool:
    """Initialize database synchronously. Returns True if vec0 is available."""
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(db_path)

    # Enable WAL mode for better concurrency and performance
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")  # Good balance of safety and speed
    conn.execute("PRAGMA cache_size=-64000")  # 64MB cache
    conn.execute("PRAGMA busy_timeout=5000")  # 5 second timeout

    vec_available = _load_vec_extension(conn)

    # Create memories table
    conn.execute(
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

    # Create chunks table for large documents
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS memory_chunks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            memory_id INTEGER NOT NULL,
            chunk_index INTEGER NOT NULL,
            content TEXT NOT NULL,
            start_pos INTEGER NOT NULL,
            end_pos INTEGER NOT NULL,
            embedding BLOB,
            FOREIGN KEY (memory_id) REFERENCES memories(id) ON DELETE CASCADE
        )
    """
    )

    # Create indices
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_memories_category ON memories(category)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_chunks_memory_id ON memory_chunks(memory_id)"
    )

    # Create vec0 virtual table for fast KNN search if available
    if vec_available:
        try:
            conn.execute(
                f"""
                CREATE VIRTUAL TABLE IF NOT EXISTS memory_vec USING vec0(
                    memory_id INTEGER PRIMARY KEY,
                    embedding float[{EMBEDDING_DIM}]
                )
            """
            )
            conn.execute(
                f"""
                CREATE VIRTUAL TABLE IF NOT EXISTS chunk_vec USING vec0(
                    chunk_id INTEGER PRIMARY KEY,
                    embedding float[{EMBEDDING_DIM}]
                )
            """
            )
            logger.info("Created vec0 virtual tables for fast KNN search")
        except Exception as e:
            logger.warning(f"Failed to create vec0 tables: {e}")
            vec_available = False

    conn.commit()
    conn.close()

    return vec_available


async def init_db():
    """Initialize the database with tables."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    async with aiosqlite.connect(DB_PATH) as db:
        # Enable WAL mode for better concurrency and performance
        await db.execute("PRAGMA journal_mode=WAL")
        await db.execute("PRAGMA synchronous=NORMAL")
        await db.execute("PRAGMA cache_size=-64000")
        await db.execute("PRAGMA busy_timeout=5000")
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

        # Create chunks table for large documents
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS memory_chunks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                memory_id INTEGER NOT NULL,
                chunk_index INTEGER NOT NULL,
                content TEXT NOT NULL,
                start_pos INTEGER NOT NULL,
                end_pos INTEGER NOT NULL,
                embedding BLOB,
                FOREIGN KEY (memory_id) REFERENCES memories(id) ON DELETE CASCADE
            )
        """
        )

        # Create indices
        await db.execute(
            "CREATE INDEX IF NOT EXISTS idx_memories_category ON memories(category)"
        )
        await db.execute(
            "CREATE INDEX IF NOT EXISTS idx_chunks_memory_id ON memory_chunks(memory_id)"
        )

        await db.commit()

    # Initialize vec0 tables synchronously (sqlite-vec needs sync connection)
    init_db_sync(DB_PATH)


async def add_memory(
    content: str,
    category: Optional[str] = None,
    metadata: Optional[dict] = None,
    with_embedding: bool = True,
) -> dict:
    """Add a new memory entry with optional embedding."""
    await init_db()

    embedding_bytes = None
    embedding = None
    if with_embedding:
        try:
            embedding = await get_embedding(content)
            embedding_bytes = serialize_f32(embedding)
        except Exception as e:
            logger.warning(f"Failed to get embedding: {e}")

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

    # Add to vec0 index if available
    if embedding_bytes:
        try:
            conn = sqlite3.connect(DB_PATH)
            if _load_vec_extension(conn):
                conn.execute(
                    "INSERT OR REPLACE INTO memory_vec(memory_id, embedding) VALUES (?, ?)",
                    (entry_id, embedding_bytes),
                )
                conn.commit()
            conn.close()
        except Exception as e:
            logger.debug(f"Failed to add to vec0 index: {e}")

    return {
        "id": entry_id,
        "content": content,
        "category": category,
        "created_at": datetime.now().isoformat(),
    }


async def add_document(
    content: str,
    category: Optional[str] = None,
    metadata: Optional[dict] = None,
) -> dict:
    """Add a large document with automatic chunking and embedding."""
    await init_db()

    # Store full document
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """
            INSERT INTO memories (content, category, embedding, created_at, metadata)
            VALUES (?, ?, NULL, ?, ?)
            """,
            (
                content,
                category,
                datetime.now().isoformat(),
                json.dumps({**(metadata or {}), "chunked": True}),
            ),
        )
        await db.commit()
        memory_id = cursor.lastrowid

    # Chunk and embed
    chunks = chunk_text(content)
    chunk_ids = []

    for idx, chunk in enumerate(chunks):
        try:
            embedding = await get_embedding(chunk["text"])
            embedding_bytes = serialize_f32(embedding)

            async with aiosqlite.connect(DB_PATH) as db:
                cursor = await db.execute(
                    """
                    INSERT INTO memory_chunks
                    (memory_id, chunk_index, content, start_pos, end_pos, embedding)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        memory_id,
                        idx,
                        chunk["text"],
                        chunk["start"],
                        chunk["end"],
                        embedding_bytes,
                    ),
                )
                await db.commit()
                chunk_id = cursor.lastrowid
                chunk_ids.append(chunk_id)

            # Add to vec0 index
            try:
                conn = sqlite3.connect(DB_PATH)
                if _load_vec_extension(conn):
                    conn.execute(
                        "INSERT OR REPLACE INTO chunk_vec(chunk_id, embedding) VALUES (?, ?)",
                        (chunk_id, embedding_bytes),
                    )
                    conn.commit()
                conn.close()
            except Exception:
                pass

        except Exception as e:
            logger.warning(f"Failed to embed chunk {idx}: {e}")

    return {
        "id": memory_id,
        "content": content[:100] + "..." if len(content) > 100 else content,
        "category": category,
        "chunks": len(chunks),
        "created_at": datetime.now().isoformat(),
    }


async def search_memory(query: str, limit: int = 10) -> list[dict]:
    """Search memories by text content (LIKE query)."""
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
    """Search memories using semantic similarity via sqlite-vec KNN."""
    await init_db()

    try:
        query_embedding = await get_embedding(query)
        query_bytes = serialize_f32(query_embedding)
    except Exception:
        return await search_memory(query, limit)

    # Try native vec0 KNN search first
    try:
        conn = sqlite3.connect(DB_PATH)
        if _load_vec_extension(conn):
            # Search in memory_vec
            cursor = conn.execute(
                """
                SELECT m.id, m.content, m.category, m.created_at, m.metadata,
                       v.distance
                FROM memory_vec v
                JOIN memories m ON m.id = v.memory_id
                WHERE v.embedding MATCH ?
                  AND k = ?
                ORDER BY v.distance
                """,
                (query_bytes, limit * 2),
            )
            rows = cursor.fetchall()

            # Also search chunks
            cursor = conn.execute(
                """
                SELECT m.id, mc.content, m.category, m.created_at, m.metadata,
                       cv.distance, mc.chunk_index
                FROM chunk_vec cv
                JOIN memory_chunks mc ON mc.id = cv.chunk_id
                JOIN memories m ON m.id = mc.memory_id
                WHERE cv.embedding MATCH ?
                  AND k = ?
                ORDER BY cv.distance
                """,
                (query_bytes, limit * 2),
            )
            chunk_rows = cursor.fetchall()
            conn.close()

            # Combine results (convert distance to similarity)
            results = []
            seen_ids = set()

            for row in rows:
                if row[0] not in seen_ids:
                    seen_ids.add(row[0])
                    # L2 distance to cosine-like similarity
                    similarity = max(0, 1 - row[5] / 2)
                    results.append(
                        {
                            "id": row[0],
                            "content": row[1],
                            "category": row[2],
                            "created_at": row[3],
                            "metadata": json.loads(row[4]) if row[4] else None,
                            "similarity": similarity,
                        }
                    )

            for row in chunk_rows:
                if row[0] not in seen_ids:
                    seen_ids.add(row[0])
                    similarity = max(0, 1 - row[5] / 2)
                    results.append(
                        {
                            "id": row[0],
                            "content": row[1],
                            "category": row[2],
                            "created_at": row[3],
                            "metadata": json.loads(row[4]) if row[4] else None,
                            "similarity": similarity,
                            "chunk_index": row[6],
                        }
                    )

            results.sort(key=lambda x: x["similarity"], reverse=True)
            return results[:limit]

    except Exception as e:
        logger.debug(f"vec0 search failed, using fallback: {e}")

    # Fallback: Python-based cosine similarity
    return await _search_memory_fallback(query_embedding, limit)


async def _search_memory_fallback(
    query_embedding: list[float], limit: int
) -> list[dict]:
    """Fallback semantic search using Python cosine similarity."""
    import numpy as np

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
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

    query_vec = np.array(query_embedding)
    query_norm = np.linalg.norm(query_vec)

    results = []
    for row in rows:
        if row["embedding"]:
            mem_vec = np.array(deserialize_f32(row["embedding"]))
            mem_norm = np.linalg.norm(mem_vec)

            if query_norm > 0 and mem_norm > 0:
                similarity = float(np.dot(query_vec, mem_vec) / (query_norm * mem_norm))
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
                    "similarity": similarity,
                }
            )

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
    """Delete a memory and its chunks by ID."""
    await init_db()

    async with aiosqlite.connect(DB_PATH) as db:
        # Delete chunks first
        await db.execute("DELETE FROM memory_chunks WHERE memory_id = ?", (memory_id,))
        cursor = await db.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
        await db.commit()
        deleted = cursor.rowcount > 0

    # Remove from vec0 indices
    if deleted:
        try:
            conn = sqlite3.connect(DB_PATH)
            if _load_vec_extension(conn):
                conn.execute("DELETE FROM memory_vec WHERE memory_id = ?", (memory_id,))
                conn.execute(
                    "DELETE FROM chunk_vec WHERE chunk_id IN "
                    "(SELECT id FROM memory_chunks WHERE memory_id = ?)",
                    (memory_id,),
                )
                conn.commit()
            conn.close()
        except Exception:
            pass

    return deleted


async def get_memory_context(limit: int = 50) -> str:
    """Get memory as context string for system prompt."""
    memories = await load_all_memories(limit)

    if not memories:
        return ""

    lines = ["## Agent Memory"]
    for entry in memories:
        cat = f"[{entry['category']}] " if entry.get("category") else ""
        content = entry["content"]
        if len(content) > 200:
            content = content[:200] + "..."
        lines.append(f"- {cat}{content}")

    return "\n".join(lines)


async def get_memory_stats() -> dict:
    """Get memory database statistics."""
    await init_db()

    async with aiosqlite.connect(DB_PATH) as db:
        # Count memories
        cursor = await db.execute("SELECT COUNT(*) FROM memories")
        total_memories = (await cursor.fetchone())[0]

        # Count chunks
        cursor = await db.execute("SELECT COUNT(*) FROM memory_chunks")
        total_chunks = (await cursor.fetchone())[0]

        # Count with embeddings
        cursor = await db.execute(
            "SELECT COUNT(*) FROM memories WHERE embedding IS NOT NULL"
        )
        with_embeddings = (await cursor.fetchone())[0]

    # Check vec0 status
    vec_available = False
    vec_memory_count = 0
    vec_chunk_count = 0

    try:
        conn = sqlite3.connect(DB_PATH)
        if _load_vec_extension(conn):
            vec_available = True
            cursor = conn.execute("SELECT COUNT(*) FROM memory_vec")
            vec_memory_count = cursor.fetchone()[0]
            cursor = conn.execute("SELECT COUNT(*) FROM chunk_vec")
            vec_chunk_count = cursor.fetchone()[0]
        conn.close()
    except Exception:
        pass

    return {
        "total_memories": total_memories,
        "total_chunks": total_chunks,
        "with_embeddings": with_embeddings,
        "vec_available": vec_available,
        "vec_memory_count": vec_memory_count,
        "vec_chunk_count": vec_chunk_count,
    }
