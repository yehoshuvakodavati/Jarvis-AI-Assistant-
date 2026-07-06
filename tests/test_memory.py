"""
Test suite: Memory subsystem — SQLite store, vector store, memory manager.

Uses a TEMP database (temp file) so the real jarvis.db is never touched.
LLM embeddings are mocked so no Ollama is required.

Validates:
- Conversation save/retrieve + persistence across re-instantiation
- Memory store/retrieve by type and keyword
- User preference get/set
- Goal/task creation and status updates
- Note save + retrieval
- Outcome recording (for learning)
- Vector store add/search with mocked embeddings + cosine similarity sanity check

Run: python tests/test_memory.py
"""

from __future__ import annotations

import math
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def _fresh_db():
    """Build a DatabaseManager pointing at a brand-new temp DB file."""
    from memory.database import DatabaseManager
    # DatabaseManager is a singleton keyed on first init; force a fresh one
    # by creating a new instance against a temp path and resetting its _initialized.
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    # Bypass singleton by constructing then overriding path
    db = DatabaseManager.__new__(DatabaseManager)
    db.db_path = tmp.name
    db._local = __import__("threading").local()
    db._initialized = True
    db._ensure_tables()
    return db, tmp.name


class TestSQLiteStoreConversations(unittest.TestCase):
    def setUp(self):
        from memory.sqlite_store import SQLiteStore
        self.db, self.db_path = _fresh_db()
        self.store = SQLiteStore(self.db)

    def tearDown(self):
        try: os.unlink(self.db_path)
        except OSError: pass

    def test_save_and_retrieve_conversation(self):
        self.store.save_conversation("s1", "user", "hello")
        self.store.save_conversation("s1", "assistant", "hi there", agent_name="commander")
        hist = self.store.get_conversation_history("s1")
        self.assertEqual(len(hist), 2)
        self.assertEqual(hist[0]["role"], "user")
        self.assertEqual(hist[1]["role"], "assistant")
        self.assertEqual(hist[1]["agent_name"], "commander")

    def test_conversation_count(self):
        self.store.save_conversation("s1", "user", "a")
        self.store.save_conversation("s1", "user", "b")
        self.store.save_conversation("s2", "user", "c")
        self.assertEqual(self.store.count_conversations("s1"), 2)
        self.assertEqual(self.store.count_conversations(), 3)

    def test_persistence_across_reopen(self):
        """Data must survive closing and reopening the DB (real persistence)."""
        self.store.save_conversation("s1", "user", "persist me")
        # Reopen the same file
        from memory.database import DatabaseManager
        from memory.sqlite_store import SQLiteStore
        db2 = DatabaseManager.__new__(DatabaseManager)
        db2.db_path = self.db_path
        db2._local = __import__("threading").local()
        db2._initialized = True
        db2._ensure_tables()
        store2 = SQLiteStore(db2)
        hist = store2.get_conversation_history("s1")
        self.assertEqual(len(hist), 1)
        self.assertEqual(hist[0]["content"], "persist me")


class TestSQLiteStoreMemories(unittest.TestCase):
    def setUp(self):
        from memory.sqlite_store import SQLiteStore
        from core.models import MemoryEntry, MemoryType
        self.MemoryEntry, self.MemoryType = MemoryEntry, MemoryType
        self.db, self.db_path = _fresh_db()
        self.store = SQLiteStore(self.db)

    def tearDown(self):
        try: os.unlink(self.db_path)
        except OSError: pass

    def test_save_and_get_memory(self):
        mid = self.store.save_memory(self.MemoryEntry(
            memory_type=self.MemoryType.PREFERENCE,
            content="user likes python",
            importance=0.8,
        ))
        self.assertGreater(mid, 0)
        mems = self.store.get_memories(memory_type=self.MemoryType.PREFERENCE)
        self.assertEqual(len(mems), 1)
        self.assertEqual(mems[0].content, "user likes python")

    def test_keyword_search(self):
        self.store.save_memory(self.MemoryEntry(memory_type=self.MemoryType.NOTE, content="Python is great"))
        self.store.save_memory(self.MemoryEntry(memory_type=self.MemoryType.NOTE, content="Java is also fine"))
        hits = self.store.search_memories_by_keyword("python")
        self.assertEqual(len(hits), 1)
        self.assertIn("Python", hits[0].content)

    def test_update_importance(self):
        mid = self.store.save_memory(self.MemoryEntry(memory_type=self.MemoryType.NOTE, content="x", importance=0.5))
        self.assertTrue(self.store.update_memory_importance(mid, 0.9))
        mems = self.store.get_memories()
        self.assertAlmostEqual(mems[0].importance, 0.9)

    def test_delete_memory(self):
        mid = self.store.save_memory(self.MemoryEntry(memory_type=self.MemoryType.NOTE, content="x"))
        self.assertTrue(self.store.delete_memory(mid))
        self.assertEqual(len(self.store.get_memories()), 0)


class TestPreferences(unittest.TestCase):
    def setUp(self):
        from memory.sqlite_store import SQLiteStore
        self.db, self.db_path = _fresh_db()
        self.store = SQLiteStore(self.db)

    def tearDown(self):
        try: os.unlink(self.db_path)
        except OSError: pass

    def test_set_get_string_preference(self):
        self.store.set_preference("theme", "dark", "string")
        self.assertEqual(self.store.get_preference("theme"), "dark")

    def test_get_missing_returns_default(self):
        self.assertIsNone(self.store.get_preference("nonexistent"))
        self.assertEqual(self.store.get_preference("nonexistent", "fallback"), "fallback")

    def test_boolean_preference(self):
        self.store.set_preference("voice_enabled", True, "boolean")
        self.assertTrue(self.store.get_preference("voice_enabled"))

    def test_update_existing_preference(self):
        self.store.set_preference("x", "a")
        self.store.set_preference("x", "b")
        self.assertEqual(self.store.get_preference("x"), "b")


class TestGoalsAndTasks(unittest.TestCase):
    def setUp(self):
        from memory.sqlite_store import SQLiteStore
        self.db, self.db_path = _fresh_db()
        self.store = SQLiteStore(self.db)

    def tearDown(self):
        try: os.unlink(self.db_path)
        except OSError: pass

    def test_create_and_list_goal(self):
        from core.models import GoalStatus
        self.assertTrue(self.store.create_goal("g1", "Learn Spring", "desc", status=GoalStatus.ACTIVE, priority=2))
        goals = self.store.get_goals(status=GoalStatus.ACTIVE)
        self.assertEqual(len(goals), 1)
        self.assertEqual(goals[0]["title"], "Learn Spring")

    def test_update_goal_progress(self):
        from core.models import GoalStatus
        self.store.create_goal("g2", "G", "d", status=GoalStatus.ACTIVE)
        self.assertTrue(self.store.update_goal_progress("g2", 0.5))
        goals = self.store.get_goals()
        self.assertAlmostEqual(goals[0]["progress"], 0.5)

    def test_task_status_lifecycle(self):
        from core.models import TaskStatus
        self.store.create_task("t1", "Do thing", "desc")
        self.assertTrue(self.store.update_task_status("t1", TaskStatus.IN_PROGRESS))
        self.assertTrue(self.store.update_task_status("t1", TaskStatus.COMPLETED, result="done"))
        tasks = self.store.get_tasks(status=TaskStatus.COMPLETED)
        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0]["result"], "done")


class TestOutcomes(unittest.TestCase):
    def setUp(self):
        from memory.sqlite_store import SQLiteStore
        from core.models import Outcome
        self.Outcome = Outcome
        self.db, self.db_path = _fresh_db()
        self.store = SQLiteStore(self.db)

    def tearDown(self):
        try: os.unlink(self.db_path)
        except OSError: pass

    def test_record_and_stats(self):
        self.store.save_outcome(self.Outcome(request="q1", agent_name="researcher", action_taken="search", success=True, confidence=0.8))
        self.store.save_outcome(self.Outcome(request="q2", agent_name="researcher", action_taken="search", success=False, confidence=0.4))
        stats = self.store.get_outcome_stats("researcher")
        self.assertEqual(stats["total"], 2)
        self.assertEqual(stats["successes"], 1)
        self.assertEqual(stats["failures"], 1)

    def test_filter_outcomes_by_success(self):
        self.store.save_outcome(self.Outcome(request="q", agent_name="a", action_taken="x", success=True))
        self.store.save_outcome(self.Outcome(request="q", agent_name="a", action_taken="x", success=False))
        fails = self.store.get_outcomes(success=False)
        self.assertEqual(len(fails), 1)
        self.assertFalse(fails[0].success)


class TestVectorStore(unittest.TestCase):
    """Vector store with mocked embeddings — verify cosine similarity ranking."""

    def setUp(self):
        from memory.vector_store import SimpleVectorStore
        self.db, self.db_path = _fresh_db()
        # Mock the LLM client's embed() to return controlled vectors
        self.vs = SimpleVectorStore.__new__(SimpleVectorStore)
        self.vs.db = self.db
        self.vs.llm = MagicMock()
        self.vs.dimension = 4
        import numpy as np
        self.vs._vectors = np.zeros((0, 4), dtype="float32")
        self.vs._entries = {}
        self.vs._id_to_index = {}
        self.vs._loaded = True
        self.vs._cache_dir = Path(tempfile.mkdtemp())
        self.vs._vector_cache = self.vs._cache_dir / "v.pkl"
        self.vs._meta_cache = self.vs._cache_dir / "m.pkl"

    def tearDown(self):
        try: os.unlink(self.db_path)
        except OSError: pass

    def test_add_and_count(self):
        self.vs.llm.embed.return_value = [1, 0, 0, 0]
        eid = self.vs.add("hello", "memories", 1)
        self.assertTrue(eid.startswith("memories:1:"))
        self.assertEqual(self.vs.count(), 1)

    def test_search_returns_most_similar(self):
        # doc A: aligned with query, doc B: orthogonal
        self.vs.llm.embed.side_effect = [
            [1, 0, 0, 0],   # add A
            [0, 1, 0, 0],   # add B
            [0.95, 0.05, 0, 0],  # query (close to A)
        ]
        self.vs.add("doc A", "memories", 1)
        self.vs.add("doc B", "memories", 2)
        results = self.vs.search("query", top_k=2, threshold=0.1)
        self.assertGreaterEqual(len(results), 1)
        # Top result should be doc A (source_id 1)
        top_meta, top_score = results[0]
        self.assertEqual(top_meta["source_id"], 1)
        self.assertGreater(top_score, 0.9)

    def test_search_empty_store(self):
        self.vs.llm.embed.return_value = [1, 0, 0, 0]
        results = self.vs.search("q")
        self.assertEqual(results, [])

    def test_dimension_mismatch_raises(self):
        self.vs.llm.embed.return_value = [1, 0, 0]  # 3 not 4
        with self.assertRaises(ValueError):
            self.vs.add("x", "memories", 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
