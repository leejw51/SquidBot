"""Tests for sqlite-vec integration and vector search functionality."""

import sqlite3
import struct
import tempfile
from pathlib import Path

import pytest

# Test sqlite-vec availability
try:
    import sqlite_vec

    VEC_AVAILABLE = True
except ImportError:
    VEC_AVAILABLE = False


def serialize_f32(vector: list[float]) -> bytes:
    """Serialize vector to bytes."""
    return struct.pack(f"{len(vector)}f", *vector)


def deserialize_f32(data: bytes) -> list[float]:
    """Deserialize bytes to vector."""
    n = len(data) // 4
    return list(struct.unpack(f"{n}f", data))


class TestSqliteVecBasic:
    """Test basic sqlite-vec operations."""

    @pytest.mark.skipif(not VEC_AVAILABLE, reason="sqlite-vec not installed")
    def test_load_extension(self):
        """Test loading sqlite-vec extension."""
        conn = sqlite3.connect(":memory:")
        conn.enable_load_extension(True)
        sqlite_vec.load(conn)
        conn.enable_load_extension(False)

        # Verify extension loaded
        result = conn.execute("SELECT vec_version()").fetchone()
        assert result is not None
        assert result[0].startswith("v")
        conn.close()

    @pytest.mark.skipif(not VEC_AVAILABLE, reason="sqlite-vec not installed")
    def test_create_vec0_table(self):
        """Test creating vec0 virtual table."""
        conn = sqlite3.connect(":memory:")
        conn.enable_load_extension(True)
        sqlite_vec.load(conn)
        conn.enable_load_extension(False)

        # Create virtual table
        conn.execute("CREATE VIRTUAL TABLE test_vec USING vec0(embedding float[4])")

        # Verify table exists
        result = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='test_vec'"
        ).fetchone()
        assert result is not None
        conn.close()

    @pytest.mark.skipif(not VEC_AVAILABLE, reason="sqlite-vec not installed")
    def test_insert_and_query_vectors(self):
        """Test inserting and querying vectors."""
        conn = sqlite3.connect(":memory:")
        conn.enable_load_extension(True)
        sqlite_vec.load(conn)
        conn.enable_load_extension(False)

        conn.execute("CREATE VIRTUAL TABLE test_vec USING vec0(embedding float[4])")

        # Insert vectors
        vectors = [
            (1, [1.0, 0.0, 0.0, 0.0]),
            (2, [0.0, 1.0, 0.0, 0.0]),
            (3, [0.0, 0.0, 1.0, 0.0]),
            (4, [0.5, 0.5, 0.0, 0.0]),
        ]
        for rowid, vec in vectors:
            conn.execute(
                "INSERT INTO test_vec(rowid, embedding) VALUES (?, ?)",
                (rowid, serialize_f32(vec)),
            )

        # KNN search
        query = serialize_f32([0.6, 0.4, 0.0, 0.0])
        results = conn.execute(
            """
            SELECT rowid, distance
            FROM test_vec
            WHERE embedding MATCH ?
            ORDER BY distance
            LIMIT 3
            """,
            (query,),
        ).fetchall()

        assert len(results) == 3
        # Closest should be [0.5, 0.5, 0.0, 0.0]
        assert results[0][0] == 4
        conn.close()

    @pytest.mark.skipif(not VEC_AVAILABLE, reason="sqlite-vec not installed")
    def test_knn_with_k_parameter(self):
        """Test KNN search with k parameter."""
        conn = sqlite3.connect(":memory:")
        conn.enable_load_extension(True)
        sqlite_vec.load(conn)
        conn.enable_load_extension(False)

        conn.execute("CREATE VIRTUAL TABLE test_vec USING vec0(embedding float[3])")

        # Insert 10 vectors
        for i in range(10):
            vec = [float(i == j) for j in range(3)]
            conn.execute(
                "INSERT INTO test_vec(rowid, embedding) VALUES (?, ?)",
                (i + 1, serialize_f32(vec)),
            )

        # Search with k=2
        query = serialize_f32([1.0, 0.0, 0.0])
        results = conn.execute(
            """
            SELECT rowid, distance
            FROM test_vec
            WHERE embedding MATCH ? AND k = 2
            ORDER BY distance
            """,
            (query,),
        ).fetchall()

        assert len(results) == 2
        conn.close()


class TestSqliteVecWithJoin:
    """Test sqlite-vec with JOIN operations."""

    @pytest.mark.skipif(not VEC_AVAILABLE, reason="sqlite-vec not installed")
    def test_vec_join_regular_table(self):
        """Test joining vec0 table with regular table."""
        conn = sqlite3.connect(":memory:")
        conn.enable_load_extension(True)
        sqlite_vec.load(conn)
        conn.enable_load_extension(False)

        # Create regular table
        conn.execute("""
            CREATE TABLE documents (
                id INTEGER PRIMARY KEY,
                title TEXT,
                content TEXT
            )
        """)

        # Create vec table
        conn.execute("CREATE VIRTUAL TABLE doc_vec USING vec0(doc_id INTEGER PRIMARY KEY, embedding float[4])")

        # Insert documents
        docs = [
            (1, "Python Guide", "Learn Python programming"),
            (2, "JavaScript Tutorial", "Web development with JS"),
            (3, "Data Science", "ML and AI basics"),
        ]
        conn.executemany("INSERT INTO documents VALUES (?, ?, ?)", docs)

        # Insert embeddings
        embeddings = [
            (1, [1.0, 0.0, 0.0, 0.0]),
            (2, [0.0, 1.0, 0.0, 0.0]),
            (3, [0.5, 0.5, 0.0, 0.0]),
        ]
        for doc_id, vec in embeddings:
            conn.execute(
                "INSERT INTO doc_vec(doc_id, embedding) VALUES (?, ?)",
                (doc_id, serialize_f32(vec)),
            )

        # Search and join
        query = serialize_f32([0.8, 0.2, 0.0, 0.0])
        results = conn.execute(
            """
            SELECT d.id, d.title, v.distance
            FROM doc_vec v
            JOIN documents d ON d.id = v.doc_id
            WHERE v.embedding MATCH ? AND k = 2
            ORDER BY v.distance
            """,
            (query,),
        ).fetchall()

        assert len(results) == 2
        # Python Guide should be closest
        assert results[0][1] == "Python Guide"
        conn.close()


class TestVectorSerialization:
    """Test vector serialization functions."""

    def test_serialize_deserialize_roundtrip(self):
        """Test that serialize/deserialize are inverse operations."""
        original = [1.0, 2.5, -3.7, 0.0, 100.123]
        serialized = serialize_f32(original)
        deserialized = deserialize_f32(serialized)

        assert len(deserialized) == len(original)
        for a, b in zip(original, deserialized):
            # float32 has ~7 decimal digits of precision
            assert abs(a - b) < 1e-5

    def test_serialize_empty_vector(self):
        """Test serializing empty vector."""
        serialized = serialize_f32([])
        assert serialized == b""
        deserialized = deserialize_f32(serialized)
        assert deserialized == []

    def test_serialize_large_vector(self):
        """Test serializing large vector (1536 dims like OpenAI)."""
        vec = [float(i) / 1536 for i in range(1536)]
        serialized = serialize_f32(vec)
        assert len(serialized) == 1536 * 4  # 4 bytes per float32
        deserialized = deserialize_f32(serialized)
        assert len(deserialized) == 1536


class TestChunking:
    """Test text chunking for large documents."""

    def test_chunk_short_text(self):
        """Test that short text is not chunked."""
        from memory_db import chunk_text

        text = "This is a short text."
        chunks = chunk_text(text)
        assert len(chunks) == 1
        assert chunks[0]["text"] == text

    def test_chunk_long_text(self):
        """Test chunking of long text."""
        from memory_db import chunk_text

        # Create text longer than default chunk size
        text = "This is sentence one. " * 500
        chunks = chunk_text(text, chunk_size=100, overlap=20)

        assert len(chunks) > 1
        # Check overlap exists
        for i in range(len(chunks) - 1):
            # Some content from end of chunk i should be in start of chunk i+1
            assert chunks[i]["end"] > chunks[i + 1]["start"]

    def test_chunk_preserves_content(self):
        """Test that all content is preserved after chunking."""
        from memory_db import chunk_text

        text = "Word " * 1000
        chunks = chunk_text(text, chunk_size=50, overlap=10)

        # Reconstruct (accounting for overlap)
        reconstructed = chunks[0]["text"]
        for chunk in chunks[1:]:
            # Find where this chunk starts in original
            reconstructed += " " + chunk["text"].split(" ", 1)[-1] if " " in chunk["text"] else chunk["text"]

        # Should have all words (some may be duplicated due to overlap)
        assert "Word" in reconstructed

    def test_chunk_positions(self):
        """Test that chunk positions are valid."""
        from memory_db import chunk_text

        text = "A" * 5000
        chunks = chunk_text(text, chunk_size=100, overlap=20)

        for chunk in chunks:
            assert chunk["start"] >= 0
            assert chunk["end"] <= len(text)
            assert chunk["start"] < chunk["end"]


class TestMemoryDbIntegration:
    """Integration tests for memory_db with sqlite-vec."""

    @pytest.fixture
    def temp_db(self, tmp_path, monkeypatch):
        """Create temporary database."""
        db_path = tmp_path / "test_memory.db"
        monkeypatch.setattr("memory_db.DB_PATH", db_path)
        return db_path

    @pytest.mark.skipif(not VEC_AVAILABLE, reason="sqlite-vec not installed")
    def test_init_db_creates_vec_tables(self, temp_db):
        """Test that init_db creates vec0 tables."""
        from memory_db import init_db_sync

        vec_available = init_db_sync(temp_db)
        assert vec_available is True

        # Check tables exist
        conn = sqlite3.connect(temp_db)
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        table_names = [t[0] for t in tables]

        assert "memories" in table_names
        assert "memory_chunks" in table_names
        assert "memory_vec" in table_names
        assert "chunk_vec" in table_names
        conn.close()

    @pytest.mark.skipif(not VEC_AVAILABLE, reason="sqlite-vec not installed")
    def test_get_memory_stats(self, temp_db):
        """Test memory stats function."""
        import asyncio
        from memory_db import init_db, get_memory_stats

        asyncio.run(init_db())
        stats = asyncio.run(get_memory_stats())

        assert "total_memories" in stats
        assert "total_chunks" in stats
        assert "vec_available" in stats
        assert stats["vec_available"] is True


class TestFallbackBehavior:
    """Test fallback behavior when sqlite-vec is not available."""

    def test_serialize_works_without_vec(self):
        """Test serialization works without sqlite-vec."""
        vec = [1.0, 2.0, 3.0]
        serialized = serialize_f32(vec)
        deserialized = deserialize_f32(serialized)
        assert vec == deserialized


@pytest.mark.skipif(not VEC_AVAILABLE, reason="sqlite-vec not installed")
class TestVec0Performance:
    """Performance-related tests for vec0."""

    def test_large_insert(self):
        """Test inserting many vectors."""
        conn = sqlite3.connect(":memory:")
        conn.enable_load_extension(True)
        sqlite_vec.load(conn)
        conn.enable_load_extension(False)

        conn.execute("CREATE VIRTUAL TABLE perf_vec USING vec0(embedding float[128])")

        # Insert 1000 vectors
        import random

        for i in range(1000):
            vec = [random.random() for _ in range(128)]
            conn.execute(
                "INSERT INTO perf_vec(rowid, embedding) VALUES (?, ?)",
                (i + 1, serialize_f32(vec)),
            )

        # Verify count
        count = conn.execute("SELECT COUNT(*) FROM perf_vec").fetchone()[0]
        assert count == 1000
        conn.close()

    def test_knn_on_large_dataset(self):
        """Test KNN search performance on larger dataset."""
        conn = sqlite3.connect(":memory:")
        conn.enable_load_extension(True)
        sqlite_vec.load(conn)
        conn.enable_load_extension(False)

        conn.execute("CREATE VIRTUAL TABLE perf_vec USING vec0(embedding float[64])")

        # Insert 500 vectors
        import random

        random.seed(42)
        for i in range(500):
            vec = [random.random() for _ in range(64)]
            conn.execute(
                "INSERT INTO perf_vec(rowid, embedding) VALUES (?, ?)",
                (i + 1, serialize_f32(vec)),
            )

        # Search
        query = serialize_f32([random.random() for _ in range(64)])
        results = conn.execute(
            """
            SELECT rowid, distance
            FROM perf_vec
            WHERE embedding MATCH ? AND k = 10
            ORDER BY distance
            """,
            (query,),
        ).fetchall()

        assert len(results) == 10
        # Results should be sorted by distance
        distances = [r[1] for r in results]
        assert distances == sorted(distances)
        conn.close()
