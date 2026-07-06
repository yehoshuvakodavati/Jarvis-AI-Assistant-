"""
SQLite Database Connection Manager for Jarvis.

Provides thread-safe connection management with automatic schema initialization.
Designed for easy migration to PostgreSQL later via connection string abstraction.
"""

from __future__ import annotations

import logging
import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Generator, List, Tuple, Any

from config import DATABASE_PATH

logger = logging.getLogger(__name__)

SCHEMA_PATH = Path(__file__).parent.parent / "database" / "schema.sql"


class DatabaseManager:
    """
    Thread-safe SQLite database manager.

    Uses thread-local storage so each thread gets its own connection,
    avoiding SQLite threading issues.
    """

    _instance: DatabaseManager | None = None
    _lock = threading.Lock()

    def __new__(cls, db_path: str | Path | None = None) -> DatabaseManager:
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, db_path: str | Path | None = None) -> None:
        if hasattr(self, "_initialized"):
            return
        self.db_path = str(db_path or DATABASE_PATH)
        self._local = threading.local()
        self._ensure_tables()
        self._initialized = True

    def _get_connection(self) -> sqlite3.Connection:
        """Get a thread-local database connection."""
        if not hasattr(self._local, "conn") or self._local.conn is None:
            conn = sqlite3.connect(self.db_path, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys = ON")
            conn.execute("PRAGMA journal_mode = WAL")
            self._local.conn = conn
        return self._local.conn

    @contextmanager
    def cursor(self) -> Generator[sqlite3.Cursor, None, None]:
        """Context manager yielding a cursor with auto-commit/rollback."""
        conn = self._get_connection()
        cur = conn.cursor()
        try:
            yield cur
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            cur.close()

    def execute(self, sql: str, parameters: Tuple[Any, ...] = ()) -> sqlite3.Cursor:
        """Execute a single statement and commit."""
        with self.cursor() as cur:
            cur.execute(sql, parameters)
            return cur

    def executemany(self, sql: str, parameters: List[Tuple[Any, ...]]) -> sqlite3.Cursor:
        """Execute many statements and commit."""
        with self.cursor() as cur:
            cur.executemany(sql, parameters)
            return cur

    def fetchone(self, sql: str, parameters: Tuple[Any, ...] = ()) -> sqlite3.Row | None:
        """Execute and return the first row."""
        with self.cursor() as cur:
            cur.execute(sql, parameters)
            return cur.fetchone()

    def fetchall(self, sql: str, parameters: Tuple[Any, ...] = ()) -> List[sqlite3.Row]:
        """Execute and return all rows."""
        with self.cursor() as cur:
            cur.execute(sql, parameters)
            return cur.fetchall()

    def _ensure_tables(self) -> None:
        """Initialize database schema if tables don't exist."""
        if not SCHEMA_PATH.exists():
            logger.warning(f"Schema file not found: {SCHEMA_PATH}")
            return

        with SCHEMA_PATH.open("r", encoding="utf-8") as f:
            schema_sql = f.read()

        conn = self._get_connection()
        # Split and execute each statement individually to handle pragmas correctly
        statements = [s.strip() for s in schema_sql.split(";") if s.strip()]
        for stmt in statements:
            if stmt.upper().startswith("PRAGMA"):
                continue
            try:
                conn.execute(stmt)
            except sqlite3.OperationalError as e:
                if "already exists" in str(e):
                    continue
                logger.warning(f"Schema init warning: {e}")
        conn.commit()
        logger.info(f"Database initialized: {self.db_path}")

    def close(self) -> None:
        """Close the thread-local connection."""
        if hasattr(self._local, "conn") and self._local.conn:
            self._local.conn.close()
            self._local.conn = None

    def get_table_names(self) -> List[str]:
        """List all tables in the database."""
        rows = self.fetchall(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        return [r["name"] for r in rows]

    def get_row_count(self, table: str) -> int:
        """Get the row count of a table."""
        row = self.fetchone(f"SELECT COUNT(*) as cnt FROM {table}")
        return row["cnt"] if row else 0


def init_database(db_path: str | Path | None = None) -> DatabaseManager:
    """Factory: create and initialize the database."""
    return DatabaseManager(db_path)
