"""
Structured SQLite Data Store for Jarvis.

Provides CRUD operations for all structured data:
- Conversations
- Memories
- Outcomes (learning)
- User preferences
- Goals
- Tasks
- Notes
- Projects
- Agent executions
- Routing logs
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from core.models import (
    GoalStatus,
    MemoryEntry,
    MemoryType,
    Outcome,
    TaskStatus,
)
from memory.database import DatabaseManager

logger = logging.getLogger(__name__)


def _to_json(data: Any) -> str | None:
    """Serialize data to JSON string, or None if empty."""
    if not data:
        return None
    return json.dumps(data, default=str)


def _from_json(text: str | None) -> Any:
    """Deserialize JSON string, returning empty dict on failure."""
    if not text:
        return {}
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {}


class SQLiteStore:
    """
    High-level CRUD interface over the SQLite database.

    All methods use parameterized queries to prevent SQL injection.
    """

    def __init__(self, db: DatabaseManager | None = None) -> None:
        self.db = db or DatabaseManager()

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
        metadata: dict | None = None,
    ) -> int:
        """Save a conversation turn. Returns the row ID."""
        cur = self.db.execute(
            """
            INSERT INTO conversations (session_id, role, content, agent_name, task_id, metadata)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (session_id, role, content, agent_name, task_id, _to_json(metadata)),
        )
        return cur.lastrowid or 0

    def get_conversation_history(
        self, session_id: str, limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Retrieve conversation history for a session."""
        rows = self.db.fetchall(
            """
            SELECT * FROM conversations
            WHERE session_id = ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (session_id, limit),
        )
        return [dict(r) for r in reversed(rows)]

    def get_recent_conversations(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get most recent conversations across all sessions."""
        rows = self.db.fetchall(
            "SELECT * FROM conversations ORDER BY created_at DESC LIMIT ?",
            (limit,),
        )
        return [dict(r) for r in rows]

    def count_conversations(self, session_id: str | None = None) -> int:
        """Count conversations, optionally filtered by session."""
        if session_id:
            row = self.db.fetchone(
                "SELECT COUNT(*) as cnt FROM conversations WHERE session_id = ?",
                (session_id,),
            )
        else:
            row = self.db.fetchone("SELECT COUNT(*) as cnt FROM conversations")
        return row["cnt"] if row else 0

    # =========================================================================
    # MEMORIES
    # =========================================================================

    def save_memory(self, entry: MemoryEntry) -> int:
        """Save a memory entry. Returns the row ID."""
        cur = self.db.execute(
            """
            INSERT INTO memories (memory_type, content, category, importance, source, metadata, embedding_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                entry.memory_type.value,
                entry.content,
                entry.category,
                entry.importance,
                entry.source,
                _to_json(entry.metadata),
                entry.metadata.get("embedding_id") if entry.metadata else None,
            ),
        )
        return cur.lastrowid or 0

    def get_memories(
        self,
        *,
        memory_type: MemoryType | None = None,
        category: str | None = None,
        limit: int = 50,
        min_importance: float = 0.0,
    ) -> List[MemoryEntry]:
        """Retrieve memories with optional filtering."""
        conditions = ["importance >= ?"]
        params: List[Any] = [min_importance]

        if memory_type:
            conditions.append("memory_type = ?")
            params.append(memory_type.value)
        if category:
            conditions.append("category = ?")
            params.append(category)

        where_clause = " AND ".join(conditions)
        rows = self.db.fetchall(
            f"""
            SELECT * FROM memories
            WHERE {where_clause}
            ORDER BY created_at DESC
            LIMIT ?
            """,
            tuple(params + [limit]),
        )
        return [self._row_to_memory(r) for r in rows]

    def search_memories_by_keyword(
        self, query: str, limit: int = 20
    ) -> List[MemoryEntry]:
        """Simple keyword search over memory content."""
        pattern = f"%{query}%"
        rows = self.db.fetchall(
            """
            SELECT * FROM memories
            WHERE content LIKE ? OR category LIKE ? OR source LIKE ?
            ORDER BY importance DESC, created_at DESC
            LIMIT ?
            """,
            (pattern, pattern, pattern, limit),
        )
        return [self._row_to_memory(r) for r in rows]

    def update_memory_importance(self, memory_id: int, importance: float) -> bool:
        """Update the importance score of a memory."""
        cur = self.db.execute(
            "UPDATE memories SET importance = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (max(0.0, min(1.0, importance)), memory_id),
        )
        return cur.rowcount > 0

    def delete_memory(self, memory_id: int) -> bool:
        """Delete a memory by ID."""
        cur = self.db.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
        return cur.rowcount > 0

    def count_memories(self, memory_type: MemoryType | None = None) -> int:
        """Count memories, optionally by type."""
        if memory_type:
            row = self.db.fetchone(
                "SELECT COUNT(*) as cnt FROM memories WHERE memory_type = ?",
                (memory_type.value,),
            )
        else:
            row = self.db.fetchone("SELECT COUNT(*) as cnt FROM memories")
        return row["cnt"] if row else 0

    def _row_to_memory(self, row: Any) -> MemoryEntry:
        """Convert a database row to a MemoryEntry."""
        return MemoryEntry(
            id=row["id"],
            memory_type=MemoryType(row["memory_type"]),
            content=row["content"],
            category=row["category"],
            importance=row["importance"],
            source=row["source"],
            metadata=_from_json(row["metadata"]),
            created_at=datetime.fromisoformat(row["created_at"]) if row["created_at"] else datetime.utcnow(),
        )

    # =========================================================================
    # OUTCOMES (Learning)
    # =========================================================================

    def save_outcome(self, outcome: Outcome) -> int:
        """Save an outcome for learning analysis. Returns row ID."""
        cur = self.db.execute(
            """
            INSERT INTO outcomes (request, agent_name, action_taken, result, success, feedback, confidence, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                outcome.request,
                outcome.agent_name,
                outcome.action_taken,
                outcome.result,
                1 if outcome.success else 0,
                outcome.feedback,
                outcome.confidence,
                _to_json(outcome.metadata),
            ),
        )
        return cur.lastrowid or 0

    def get_outcomes(
        self,
        *,
        agent_name: str | None = None,
        success: bool | None = None,
        limit: int = 100,
    ) -> List[Outcome]:
        """Retrieve outcomes with filtering."""
        conditions: List[str] = []
        params: List[Any] = []

        if agent_name:
            conditions.append("agent_name = ?")
            params.append(agent_name)
        if success is not None:
            conditions.append("success = ?")
            params.append(1 if success else 0)

        where_clause = " AND ".join(conditions) if conditions else "1=1"
        rows = self.db.fetchall(
            f"SELECT * FROM outcomes WHERE {where_clause} ORDER BY created_at DESC LIMIT ?",
            tuple(params + [limit]),
        )
        return [self._row_to_outcome(r) for r in rows]

    def get_outcome_stats(self, agent_name: str | None = None) -> Dict[str, Any]:
        """Get aggregated outcome statistics."""
        if agent_name:
            row = self.db.fetchone(
                """
                SELECT
                    COUNT(*) as total,
                    SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) as successes,
                    AVG(confidence) as avg_confidence
                FROM outcomes WHERE agent_name = ?
                """,
                (agent_name,),
            )
        else:
            row = self.db.fetchone(
                """
                SELECT
                    COUNT(*) as total,
                    SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) as successes,
                    AVG(confidence) as avg_confidence
                FROM outcomes
                """
            )
        if not row:
            return {"total": 0, "successes": 0, "failures": 0, "avg_confidence": 0.0}
        total = row["total"]
        return {
            "total": total,
            "successes": row["successes"],
            "failures": total - (row["successes"] or 0),
            "avg_confidence": row["avg_confidence"] or 0.0,
        }

    def _row_to_outcome(self, row: Any) -> Outcome:
        return Outcome(
            id=row["id"],
            request=row["request"],
            agent_name=row["agent_name"],
            action_taken=row["action_taken"],
            result=row["result"],
            success=bool(row["success"]),
            feedback=row["feedback"],
            confidence=row["confidence"],
            metadata=_from_json(row["metadata"]),
            created_at=datetime.fromisoformat(row["created_at"]) if row["created_at"] else datetime.utcnow(),
        )

    # =========================================================================
    # PREFERENCES
    # =========================================================================

    def set_preference(self, key: str, value: Any, value_type: str = "string", description: str = "") -> None:
        """Set or update a user preference."""
        str_value = json.dumps(value) if value_type == "json" else str(value)
        self.db.execute(
            """
            INSERT INTO user_preferences (key, value, value_type, description)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET
                value = excluded.value,
                value_type = excluded.value_type,
                description = COALESCE(excluded.description, user_preferences.description),
                updated_at = CURRENT_TIMESTAMP
            """,
            (key, str_value, value_type, description),
        )

    def get_preference(self, key: str, default: Any = None) -> Any:
        """Get a preference value, optionally returning a default."""
        row = self.db.fetchone(
            "SELECT value, value_type FROM user_preferences WHERE key = ?",
            (key,),
        )
        if not row:
            return default
        val, vtype = row["value"], row["value_type"]
        if vtype == "boolean":
            return val.lower() == "true"
        if vtype == "number":
            try:
                return float(val)
            except ValueError:
                return val
        if vtype == "json":
            return _from_json(val)
        return val

    def get_all_preferences(self) -> Dict[str, Any]:
        """Get all preferences as a dictionary."""
        rows = self.db.fetchall("SELECT key, value, value_type FROM user_preferences")
        result: Dict[str, Any] = {}
        for r in rows:
            result[r["key"]] = self.get_preference(r["key"])
        return result

    # =========================================================================
    # GOALS
    # =========================================================================

    def create_goal(
        self,
        goal_id: str,
        title: str,
        description: str = "",
        *,
        status: GoalStatus = GoalStatus.ACTIVE,
        priority: int = 3,
        due_date: datetime | None = None,
        parent_goal_id: str | None = None,
        metadata: dict | None = None,
    ) -> bool:
        """Create a new goal."""
        try:
            self.db.execute(
                """
                INSERT INTO goals (goal_id, title, description, status, priority, due_date, parent_goal_id, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    goal_id, title, description, status.value, priority,
                    due_date.isoformat() if due_date else None,
                    parent_goal_id, _to_json(metadata),
                ),
            )
            return True
        except Exception as e:
            logger.error(f"Failed to create goal: {e}")
            return False

    def get_goals(self, status: GoalStatus | None = None) -> List[Dict[str, Any]]:
        """Retrieve goals, optionally filtered by status."""
        if status:
            rows = self.db.fetchall(
                "SELECT * FROM goals WHERE status = ? ORDER BY priority ASC, created_at DESC",
                (status.value,),
            )
        else:
            rows = self.db.fetchall(
                "SELECT * FROM goals ORDER BY priority ASC, created_at DESC"
            )
        return [dict(r) for r in rows]

    def update_goal_progress(self, goal_id: str, progress: float) -> bool:
        """Update a goal's progress (0.0 to 1.0)."""
        progress = max(0.0, min(1.0, progress))
        cur = self.db.execute(
            "UPDATE goals SET progress = ?, updated_at = CURRENT_TIMESTAMP WHERE goal_id = ?",
            (progress, goal_id),
        )
        return cur.rowcount > 0

    def update_goal_status(self, goal_id: str, status: GoalStatus) -> bool:
        """Update a goal's status."""
        cur = self.db.execute(
            "UPDATE goals SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE goal_id = ?",
            (status.value, goal_id),
        )
        return cur.rowcount > 0

    # =========================================================================
    # TASKS
    # =========================================================================

    def create_task(
        self,
        task_id: str,
        title: str,
        description: str = "",
        *,
        assigned_agent: str | None = None,
        parent_task_id: str | None = None,
        priority: int = 3,
        scheduled_at: datetime | None = None,
        metadata: dict | None = None,
    ) -> bool:
        """Create a new task."""
        try:
            self.db.execute(
                """
                INSERT INTO tasks (task_id, parent_task_id, title, description, assigned_agent, priority, scheduled_at, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    task_id, parent_task_id, title, description, assigned_agent, priority,
                    scheduled_at.isoformat() if scheduled_at else None,
                    _to_json(metadata),
                ),
            )
            return True
        except Exception as e:
            logger.error(f"Failed to create task: {e}")
            return False

    def get_tasks(
        self,
        *,
        status: TaskStatus | None = None,
        assigned_agent: str | None = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Retrieve tasks with optional filtering."""
        conditions: List[str] = []
        params: List[Any] = []

        if status:
            conditions.append("status = ?")
            params.append(status.value)
        if assigned_agent:
            conditions.append("assigned_agent = ?")
            params.append(assigned_agent)

        where_clause = " AND ".join(conditions) if conditions else "1=1"
        rows = self.db.fetchall(
            f"SELECT * FROM tasks WHERE {where_clause} ORDER BY priority ASC, created_at DESC LIMIT ?",
            tuple(params + [limit]),
        )
        return [dict(r) for r in rows]

    def update_task_status(self, task_id: str, status: TaskStatus, result: str | None = None) -> bool:
        """Update a task's status and optionally set result."""
        fields = ["status = ?"]
        params: List[Any] = [status.value]

        if status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED):
            fields.append("completed_at = CURRENT_TIMESTAMP")
        if status == TaskStatus.IN_PROGRESS:
            fields.append("started_at = COALESCE(started_at, CURRENT_TIMESTAMP)")
        if result is not None:
            fields.append("result = ?")
            params.append(result)

        params.append(task_id)
        cur = self.db.execute(
            f"UPDATE tasks SET {', '.join(fields)} WHERE task_id = ?",
            tuple(params),
        )
        return cur.rowcount > 0

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
        metadata: dict | None = None,
    ) -> int:
        """Save a note. Returns row ID."""
        cur = self.db.execute(
            """
            INSERT INTO notes (title, content, source_url, tags, category, metadata)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (title, content, source_url, tags, category, _to_json(metadata)),
        )
        return cur.lastrowid or 0

    def get_notes(
        self, *, category: str | None = None, limit: int = 50, search: str | None = None
    ) -> List[Dict[str, Any]]:
        """Retrieve notes with optional filtering."""
        conditions: List[str] = []
        params: List[Any] = []

        if category:
            conditions.append("category = ?")
            params.append(category)
        if search:
            conditions.append("(title LIKE ? OR content LIKE ? OR tags LIKE ?)")
            pattern = f"%{search}%"
            params.extend([pattern, pattern, pattern])

        where_clause = " AND ".join(conditions) if conditions else "1=1"
        rows = self.db.fetchall(
            f"SELECT * FROM notes WHERE {where_clause} ORDER BY updated_at DESC LIMIT ?",
            tuple(params + [limit]),
        )
        return [dict(r) for r in rows]

    # =========================================================================
    # PROJECTS
    # =========================================================================

    def create_project(
        self,
        project_id: str,
        name: str,
        description: str = "",
        context: str = "",
        metadata: dict | None = None,
    ) -> bool:
        """Create a new project."""
        try:
            self.db.execute(
                "INSERT INTO projects (project_id, name, description, context, metadata) VALUES (?, ?, ?, ?, ?)",
                (project_id, name, description, context, _to_json(metadata)),
            )
            return True
        except Exception as e:
            logger.error(f"Failed to create project: {e}")
            return False

    def get_projects(self, status: str = "active") -> List[Dict[str, Any]]:
        """Retrieve projects by status."""
        rows = self.db.fetchall(
            "SELECT * FROM projects WHERE status = ? ORDER BY created_at DESC",
            (status,),
        )
        return [dict(r) for r in rows]

    # =========================================================================
    # AGENT EXECUTIONS (Observability)
    # =========================================================================

    def start_execution(self, execution_id: str, agent_name: str, task_id: str | None = None, task_description: str | None = None) -> bool:
        """Log the start of an agent execution."""
        try:
            self.db.execute(
                "INSERT INTO agent_executions (execution_id, agent_name, task_id, task_description) VALUES (?, ?, ?, ?)",
                (execution_id, agent_name, task_id, task_description),
            )
            return True
        except Exception as e:
            logger.error(f"Failed to log execution start: {e}")
            return False

    def end_execution(
        self,
        execution_id: str,
        status: str,
        execution_time_ms: int,
        tools_used: list | None = None,
        execution_trace: list | None = None,
    ) -> bool:
        """Log the end of an agent execution."""
        try:
            self.db.execute(
                """
                UPDATE agent_executions
                SET status = ?, ended_at = CURRENT_TIMESTAMP, execution_time_ms = ?,
                    tools_used = ?, execution_trace = ?
                WHERE execution_id = ?
                """,
                (
                    status, execution_time_ms,
                    _to_json(tools_used), _to_json(execution_trace),
                    execution_id,
                ),
            )
            return True
        except Exception as e:
            logger.error(f"Failed to log execution end: {e}")
            return False

    def get_recent_executions(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent agent execution logs."""
        rows = self.db.fetchall(
            "SELECT * FROM agent_executions ORDER BY started_at DESC LIMIT ?",
            (limit,),
        )
        return [dict(r) for r in rows]

    # =========================================================================
    # ROUTING LOGS
    # =========================================================================

    def log_routing(
        self,
        request: str,
        primary_agent: str,
        *,
        intent: str | None = None,
        confidence: float = 0.0,
        metadata: dict | None = None,
    ) -> int:
        """Log a routing decision. Returns row ID."""
        cur = self.db.execute(
            """
            INSERT INTO routing_logs (request, intent, primary_agent, confidence, metadata)
            VALUES (?, ?, ?, ?, ?)
            """,
            (request, intent, primary_agent, confidence, _to_json(metadata)),
        )
        return cur.lastrowid or 0

    def update_routing_feedback(self, log_id: int, was_correct: bool, feedback: str | None = None) -> bool:
        """Update routing log with user feedback."""
        cur = self.db.execute(
            "UPDATE routing_logs SET was_correct = ?, user_feedback = ? WHERE id = ?",
            (1 if was_correct else 0, feedback, log_id),
        )
        return cur.rowcount > 0

    def get_routing_accuracy(self, agent_name: str | None = None) -> float:
        """Calculate routing accuracy percentage."""
        if agent_name:
            row = self.db.fetchone(
                """
                SELECT AVG(CASE WHEN was_correct = 1 THEN 1.0 ELSE 0.0 END) as accuracy
                FROM routing_logs WHERE primary_agent = ? AND was_correct IS NOT NULL
                """,
                (agent_name,),
            )
        else:
            row = self.db.fetchone(
                """
                SELECT AVG(CASE WHEN was_correct = 1 THEN 1.0 ELSE 0.0 END) as accuracy
                FROM routing_logs WHERE was_correct IS NOT NULL
                """
            )
        return (row["accuracy"] or 0.0) * 100
