-- ============================================================================
-- Jarvis Multi-Agent AI Operating System - Database Schema
-- SQLite with PostgreSQL migration compatibility
-- ============================================================================

-- Enable foreign keys
PRAGMA foreign_keys = ON;

-- ============================================================================
-- CONVERSATIONS: Stores all conversation turns across sessions
-- ============================================================================
CREATE TABLE IF NOT EXISTS conversations (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id      TEXT NOT NULL,
    role            TEXT NOT NULL CHECK(role IN ('user', 'assistant', 'system')),
    content         TEXT NOT NULL,
    agent_name      TEXT,
    task_id         TEXT,
    metadata        TEXT,           -- JSON blob
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_conversations_session ON conversations(session_id, created_at);
CREATE INDEX IF NOT EXISTS idx_conversations_agent ON conversations(agent_name);
CREATE INDEX IF NOT EXISTS idx_conversations_task ON conversations(task_id);

-- ============================================================================
-- MEMORIES: Long-term memory store (conversations, preferences, projects, etc.)
-- ============================================================================
CREATE TABLE IF NOT EXISTS memories (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    memory_type     TEXT NOT NULL CHECK(memory_type IN (
                        'conversation', 'preference', 'project',
                        'goal', 'note', 'action', 'learning', 'insight'
                    )),
    content         TEXT NOT NULL,
    category        TEXT,           -- e.g., 'coding', 'personal', 'work'
    importance      REAL DEFAULT 0.5 CHECK(importance >= 0.0 AND importance <= 1.0),
    source          TEXT,           -- Where this memory came from
    metadata        TEXT,           -- JSON blob
    embedding_id    TEXT,           -- Reference to vector store entry
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_memories_type ON memories(memory_type);
CREATE INDEX IF NOT EXISTS idx_memories_category ON memories(category);
CREATE INDEX IF NOT EXISTS idx_memories_importance ON memories(importance DESC);
CREATE INDEX IF NOT EXISTS idx_memories_created ON memories(created_at DESC);

-- ============================================================================
-- OUTCOMES: Tracks agent actions and results for learning
-- ============================================================================
CREATE TABLE IF NOT EXISTS outcomes (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    request         TEXT NOT NULL,
    agent_name      TEXT NOT NULL,
    action_taken    TEXT NOT NULL,
    result          TEXT,
    success         INTEGER NOT NULL CHECK(success IN (0, 1)),
    feedback        TEXT,           -- User feedback or auto-assessment
    confidence      REAL DEFAULT 0.5,
    metadata        TEXT,           -- JSON blob: tools_used, execution_time, etc.
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_outcomes_agent ON outcomes(agent_name);
CREATE INDEX IF NOT EXISTS idx_outcomes_success ON outcomes(success);
CREATE INDEX IF NOT EXISTS idx_outcomes_request ON outcomes(request);
CREATE INDEX IF NOT EXISTS idx_outcomes_created ON outcomes(created_at DESC);

-- ============================================================================
-- USER_PREFERENCES: Key-value store for user settings and preferences
-- ============================================================================
CREATE TABLE IF NOT EXISTS user_preferences (
    key             TEXT PRIMARY KEY,
    value           TEXT NOT NULL,
    value_type      TEXT DEFAULT 'string' CHECK(value_type IN ('string', 'number', 'boolean', 'json')),
    description     TEXT,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================================
-- GOALS: User goals and plans managed by the Planner Agent
-- ============================================================================
CREATE TABLE IF NOT EXISTS goals (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    goal_id         TEXT NOT NULL UNIQUE,
    title           TEXT NOT NULL,
    description     TEXT,
    status          TEXT DEFAULT 'active' CHECK(status IN ('active', 'completed', 'paused', 'cancelled')),
    priority        INTEGER DEFAULT 3 CHECK(priority BETWEEN 1 AND 5),
    due_date        TIMESTAMP,
    progress        REAL DEFAULT 0.0 CHECK(progress >= 0.0 AND progress <= 1.0),
    parent_goal_id  TEXT REFERENCES goals(goal_id),
    metadata        TEXT,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_goals_status ON goals(status);
CREATE INDEX IF NOT EXISTS idx_goals_due ON goals(due_date);

-- ============================================================================
-- TASKS: Individual tasks created by Planner Agent
-- ============================================================================
CREATE TABLE IF NOT EXISTS tasks (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id         TEXT NOT NULL UNIQUE,
    parent_task_id  TEXT REFERENCES tasks(task_id),
    title           TEXT NOT NULL,
    description     TEXT,
    assigned_agent  TEXT,
    status          TEXT DEFAULT 'pending' CHECK(status IN ('pending', 'in_progress', 'completed', 'failed', 'cancelled')),
    priority        INTEGER DEFAULT 3 CHECK(priority BETWEEN 1 AND 5),
    scheduled_at    TIMESTAMP,
    started_at      TIMESTAMP,
    completed_at    TIMESTAMP,
    result          TEXT,
    metadata        TEXT,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
CREATE INDEX IF NOT EXISTS idx_tasks_agent ON tasks(assigned_agent);
CREATE INDEX IF NOT EXISTS idx_tasks_parent ON tasks(parent_task_id);
CREATE INDEX IF NOT EXISTS idx_tasks_scheduled ON tasks(scheduled_at);

-- ============================================================================
-- NOTES: Structured note storage (replaces flat notes.txt)
-- ============================================================================
CREATE TABLE IF NOT EXISTS notes (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    title           TEXT NOT NULL,
    content         TEXT NOT NULL,
    source_url      TEXT,
    tags            TEXT,           -- comma-separated
    category        TEXT,
    metadata        TEXT,
    embedding_id    TEXT,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_notes_category ON notes(category);
CREATE INDEX IF NOT EXISTS idx_notes_tags ON notes(tags);
CREATE INDEX IF NOT EXISTS idx_notes_created ON notes(created_at DESC);

-- ============================================================================
-- PROJECTS: Active project context tracking
-- ============================================================================
CREATE TABLE IF NOT EXISTS projects (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id      TEXT NOT NULL UNIQUE,
    name            TEXT NOT NULL,
    description     TEXT,
    context         TEXT,           -- AI-generated project context summary
    status          TEXT DEFAULT 'active' CHECK(status IN ('active', 'archived', 'deleted')),
    metadata        TEXT,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_projects_status ON projects(status);

-- ============================================================================
-- AGENT_EXECUTIONS: Observability - tracks every agent run
-- ============================================================================
CREATE TABLE IF NOT EXISTS agent_executions (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    execution_id        TEXT NOT NULL UNIQUE,
    agent_name          TEXT NOT NULL,
    task_id             TEXT,
    task_description    TEXT,
    tools_used          TEXT,       -- JSON array of tool calls
    execution_trace     TEXT,       -- JSON array of trace events
    status              TEXT DEFAULT 'running' CHECK(status IN ('running', 'completed', 'failed', 'cancelled')),
    started_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    ended_at            TIMESTAMP,
    execution_time_ms   INTEGER
);

CREATE INDEX IF NOT EXISTS idx_exec_agent ON agent_executions(agent_name);
CREATE INDEX IF NOT EXISTS idx_exec_status ON agent_executions(status);
CREATE INDEX IF NOT EXISTS idx_exec_started ON agent_executions(started_at DESC);

-- ============================================================================
-- ROUTING_LOGS: Tracks Commander routing decisions for learning
-- ============================================================================
CREATE TABLE IF NOT EXISTS routing_logs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    request         TEXT NOT NULL,
    intent          TEXT,
    primary_agent   TEXT NOT NULL,
    confidence      REAL,
    was_correct     INTEGER,        -- NULL until feedback, then 0 or 1
    user_feedback   TEXT,
    metadata        TEXT,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_routing_agent ON routing_logs(primary_agent);
CREATE INDEX IF NOT EXISTS idx_routing_correct ON routing_logs(was_correct);

-- ============================================================================
-- VECTORS: Metadata for vector store entries (actual vectors stored separately)
-- ============================================================================
CREATE TABLE IF NOT EXISTS vector_entries (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    entry_id        TEXT NOT NULL UNIQUE,
    source_table    TEXT NOT NULL,
    source_id       INTEGER NOT NULL,
    content_hash    TEXT NOT NULL,
    dimension       INTEGER NOT NULL,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_vector_source ON vector_entries(source_table, source_id);

-- ============================================================================
-- INITIAL PREFERENCES
-- ============================================================================
INSERT OR IGNORE INTO user_preferences (key, value, value_type, description) VALUES
    ('theme', 'dark', 'string', 'UI theme preference'),
    ('voice_enabled', 'true', 'boolean', 'Whether voice output is enabled'),
    ('auto_save_notes', 'true', 'boolean', 'Automatically save search summaries as notes'),
    ('confirmation_level', 'medium', 'string', 'Safety confirmation level: low, medium, high');
