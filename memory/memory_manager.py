"""
Unified Memory Manager for Jarvis Multi-Agent AI Operating System.

Combines structured storage (SQLiteStore) and semantic retrieval (VectorStore)
into a single high-level API that all agents use.

Provides:
- Conversation persistence and retrieval
- Memory storage with automatic embedding
- Semantic and keyword search
- Context assembly for LLM prompts
- Preference management
- Goal and task tracking
- Note management
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from config import AUTO_MEMORY_ENABLED, MAX_CONVERSATION_HISTORY, MEMORY_IMPORTANCE_THRESHOLD
from core.models import (
    MemoryEntry,
    MemoryRetrieval,
    MemoryType,
    Outcome,
)
from core.llm_client import LLMClient
from memory.database import DatabaseManager
from memory.sqlite_store import SQLiteStore
from memory.vector_store import SimpleVectorStore

logger = logging.getLogger(__name__)


class MemoryManager:
    """
    Central memory coordinator.

    Usage:
        mm = MemoryManager()
        mm.save_conversation("user", "Hello!")
        mm.store_memory("user likes Python", type=MemoryType.PREFERENCE)
        results = mm.search("Python", top_k=5)
        context = mm.build_context_for_prompt("Tell me about Python")
    """

    _instance: MemoryManager | None = None
    _initialized: bool = False

    def __new__(cls, *args: Any, **kwargs: Any) -> MemoryManager:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(
        self,
        db: DatabaseManager | None = None,
        sqlite_store: SQLiteStore | None = None,
        vector_store: SimpleVectorStore | None = None,
        llm_client: LLMClient | None = None,
    ) -> None:
        if MemoryManager._initialized:
            return
        self.db = db or DatabaseManager()
        self.store = sqlite_store or SQLiteStore(self.db)
        self.vector = vector_store or SimpleVectorStore(self.db, llm_client)
        self.llm = llm_client or LLMClient()
        MemoryManager._initialized = True

    # =========================================================================
    # CONVERSATIONS
    # =========================================================================

    def save_conversation(
        self,
        session_id: str,
        role: str,
        content: str,
        *,
        agent_name: str | None = None,
        task_id: str | None = None,
    ) -> None:
        """Persist a conversation turn."""
        self.store.save_conversation(session_id, role, content, agent_name=agent_name, task_id=task_id)

        if AUTO_MEMORY_ENABLED and role == "user":
            # Auto-extract important facts from user messages
            self._auto_extract_memory(content)

    def get_conversation_history(
        self, session_id: str, limit: int = 20
    ) -> List[Dict[str, Any]]:
        """Get conversation history for a session."""
        return self.store.get_conversation_history(session_id, limit=limit)

    def get_formatted_history(self, session_id: str, limit: int = 10) -> str:
        """Get conversation history formatted for LLM prompt context."""
        history = self.get_conversation_history(session_id, limit=limit)
        lines = []
        for msg in history:
            role_label = "User" if msg["role"] == "user" else "Assistant"
            lines.append(f"{role_label}: {msg['content']}")
        return "\n".join(lines)

    # =========================================================================
    # MEMORY STORAGE & RETRIEVAL
    # =========================================================================

    def store_memory(
        self,
        content: str,
        *,
        memory_type: MemoryType = MemoryType.CONVERSATION,
        category: str | None = None,
        importance: float = 0.5,
        source: str | None = None,
        metadata: dict | None = None,
    ) -> int:
        """
        Store a memory with optional semantic indexing.

        Returns:
            Memory ID in the SQLite store.
        """
        # Coerce string memory_type to the enum (defensive: callers may pass either)
        if isinstance(memory_type, str):
            try:
                memory_type = MemoryType(memory_type)
            except ValueError:
                memory_type = MemoryType.CONVERSATION

        entry = MemoryEntry(
            memory_type=memory_type,
            content=content,
            category=category,
            importance=importance,
            source=source,
            metadata=metadata or {},
        )
        memory_id = self.store.save_memory(entry)

        # Index in vector store for semantic retrieval
        try:
            self.vector.add(
                text=content,
                source_table="memories",
                source_id=memory_id,
                metadata={"type": memory_type.value, "category": category},
            )
        except Exception as e:
            logger.warning(f"Vector indexing failed for memory {memory_id}: {e}")

        return memory_id

    def search(
        self,
        query: str,
        *,
        top_k: int = 5,
        use_semantic: bool = True,
        use_keyword: bool = True,
        memory_type: MemoryType | None = None,
    ) -> List[MemoryRetrieval]:
        """
        Hybrid search over memories: semantic + keyword.

        Args:
            query: Search query.
            top_k: Maximum results.
            use_semantic: Whether to use vector similarity.
            use_keyword: Whether to use keyword matching.
            memory_type: Filter by memory type.

        Returns:
            Ranked list of MemoryRetrieval objects.
        """
        results: List[MemoryRetrieval] = []
        seen_ids: set[int] = set()

        # Semantic search
        if use_semantic and self.vector.count() > 0:
            try:
                semantic_results = self.vector.search(query, top_k=top_k)
                for meta, score in semantic_results:
                    source_id = meta.get("source_id")
                    if source_id is not None and source_id not in seen_ids:
                        mem_entry = self._get_memory_by_id(source_id)
                        if mem_entry and (memory_type is None or mem_entry.memory_type == memory_type):
                            results.append(MemoryRetrieval(
                                memory=mem_entry,
                                similarity_score=score,
                                retrieval_method="semantic",
                            ))
                            seen_ids.add(source_id)
            except Exception as e:
                logger.warning(f"Semantic search failed: {e}")

        # Keyword search
        if use_keyword:
            keyword_memories = self.store.search_memories_by_keyword(query, limit=top_k)
            for mem in keyword_memories:
                if mem.id not in seen_ids:
                    if memory_type is None or mem.memory_type == memory_type:
                        results.append(MemoryRetrieval(
                            memory=mem,
                            similarity_score=0.5,  # Neutral score for keyword
                            retrieval_method="keyword",
                        ))
                        seen_ids.add(mem.id)

        # Sort by similarity score descending
        results.sort(key=lambda r: r.similarity_score, reverse=True)
        return results[:top_k]

    def build_context_for_prompt(self, query: str, max_items: int = 5) -> str:
        """
        Build a memory context string to prepend to LLM prompts.

        Retrieves relevant memories and formats them for inclusion.
        """
        memories = self.search(query, top_k=max_items)
        if not memories:
            return ""

        lines = ["Relevant context from memory:"]
        for mr in memories:
            m = mr.memory
            lines.append(f"- [{m.memory_type.value}] {m.content[:200]}")
        return "\n".join(lines)

    def get_recent_memories(self, memory_type: MemoryType | None = None, limit: int = 10) -> List[MemoryEntry]:
        """Get recently stored memories."""
        return self.store.get_memories(memory_type=memory_type, limit=limit)

    # =========================================================================
    # PREFERENCES
    # =========================================================================

    def set_preference(self, key: str, value: Any, value_type: str = "string", description: str = "") -> None:
        """Set a user preference."""
        self.store.set_preference(key, value, value_type, description)

    def get_preference(self, key: str, default: Any = None) -> Any:
        """Get a user preference."""
        return self.store.get_preference(key, default)

    def get_all_preferences(self) -> Dict[str, Any]:
        """Get all preferences as a dictionary."""
        return self.store.get_all_preferences()

    # =========================================================================
    # GOALS
    # =========================================================================

    def create_goal(self, goal_id: str, title: str, description: str = "", **kwargs: Any) -> bool:
        """Create a new goal."""
        return self.store.create_goal(goal_id, title, description, **kwargs)

    def get_active_goals(self) -> List[Dict[str, Any]]:
        """Get all active goals."""
        from core.models import GoalStatus
        return self.store.get_goals(status=GoalStatus.ACTIVE)

    def update_goal_progress(self, goal_id: str, progress: float) -> bool:
        """Update goal progress."""
        return self.store.update_goal_progress(goal_id, progress)

    # =========================================================================
    # TASKS
    # =========================================================================

    def create_task(self, task_id: str, title: str, description: str = "", **kwargs: Any) -> bool:
        """Create a new task."""
        return self.store.create_task(task_id, title, description, **kwargs)

    def get_pending_tasks(self, assigned_agent: str | None = None) -> List[Dict[str, Any]]:
        """Get pending tasks."""
        from core.models import TaskStatus
        return self.store.get_tasks(status=TaskStatus.PENDING, assigned_agent=assigned_agent)

    def update_task_status(self, task_id: str, status: Any, result: str | None = None) -> bool:
        """Update a task's status."""
        return self.store.update_task_status(task_id, status, result)

    # =========================================================================
    # NOTES
    # =========================================================================

    def save_note(
        self,
        title: str,
        content: str,
        *,
        source_url: str | None = None,
        tags: str | None = None,
        category: str | None = None,
    ) -> int:
        """Save a structured note and index it for search."""
        note_id = self.store.save_note(title, content, source_url=source_url, tags=tags, category=category)

        # Index in vector store
        try:
            full_text = f"{title}\n{content}"
            self.vector.add(
                text=full_text[:1000],
                source_table="notes",
                source_id=note_id,
                metadata={"title": title, "category": category, "tags": tags},
            )
        except Exception as e:
            logger.warning(f"Vector indexing failed for note {note_id}: {e}")

        return note_id

    def get_notes(self, **filters: Any) -> List[Dict[str, Any]]:
        """Get notes with filtering."""
        return self.store.get_notes(**filters)

    # =========================================================================
    # LEARNING / OUTCOMES
    # =========================================================================

    def record_outcome(self, outcome: Outcome) -> int:
        """Record an outcome for learning."""
        return self.store.save_outcome(outcome)

    def get_learning_insights(self, agent_name: str | None = None) -> Dict[str, Any]:
        """Get learning statistics and insights."""
        stats = self.store.get_outcome_stats(agent_name)

        # Get recent failures for pattern analysis
        recent_failures = self.store.get_outcomes(success=False, limit=20)
        failure_patterns: Dict[str, int] = {}
        for fo in recent_failures:
            key = f"{fo.agent_name}:{fo.action_taken}"
            failure_patterns[key] = failure_patterns.get(key, 0) + 1

        return {
            "stats": stats,
            "common_failures": dict(sorted(failure_patterns.items(), key=lambda x: x[1], reverse=True)[:5]),
        }

    # =========================================================================
    # PROJECTS
    # =========================================================================

    def create_project(self, project_id: str, name: str, description: str = "", **kwargs: Any) -> bool:
        """Create a new project."""
        return self.store.create_project(project_id, name, description, **kwargs)

    def get_active_projects(self) -> List[Dict[str, Any]]:
        """Get active projects."""
        return self.store.get_projects(status="active")

    # =========================================================================
    # HEALTH / STATS
    # =========================================================================

    def get_stats(self) -> Dict[str, Any]:
        """Get memory subsystem statistics."""
        return {
            "conversations": self.store.count_conversations(),
            "memories": self.store.count_memories(),
            "vectors": self.vector.count(),
            "preferences": len(self.store.get_all_preferences()),
            "goals": len(self.store.get_goals()),
        }

    # =========================================================================
    # INTERNAL
    # =========================================================================

    def _auto_extract_memory(self, user_message: str) -> None:
        """
        Automatically extract potentially important facts from user messages.

        Uses a lightweight heuristic + LLM for important-looking statements.
        """
        # Heuristic triggers
        triggers = [
            "i like", "i love", "i hate", "i prefer", "i want",
            "my name is", "i am a", "i work as", "i'm working on",
            "my project", "my goal", "remind me",
        ]
        lower_msg = user_message.lower()
        if not any(t in lower_msg for t in triggers):
            return

        # Store as preference/conversation memory
        self.store_memory(
            content=user_message,
            memory_type=MemoryType.CONVERSATION,
            importance=0.6,
            source="auto_extract",
        )
        logger.debug(f"Auto-extracted memory from user message")

    def _get_memory_by_id(self, memory_id: int) -> MemoryEntry | None:
        """Fetch a single memory by ID."""
        rows = self.store.get_memories(limit=1)
        # This is inefficient; better to query by ID directly
        # For now, we'll fetch all and filter (acceptable for small datasets)
        all_memories = self.store.get_memories(limit=10000)
        for mem in all_memories:
            if mem.id == memory_id:
                return mem
        return None
