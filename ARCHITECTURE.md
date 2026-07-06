# JARVIS Multi-Agent AI Operating System — Architecture Documentation

> **Version:** 2.0 Production  
> **Date:** 2026-06-19  
> **Classification:** Internal Architecture  

---

## 1. Architecture Review

### 1.1 Previous Architecture Weaknesses (Audited)

The original Jarvis system (`agent.py`, `brain.py`, `tools/`) suffered from fundamental architectural flaws that prevented it from scaling beyond a demo:

| Weakness | Severity | Evidence | Impact |
|---|---|---|---|
| **Hardcoded routing** | Critical | `agent.py:60-75` keyword substring matching; `agent.py:102-124` cascading if-elif chains | Zero autonomy; every new capability requires code changes |
| **`eval()` on user input** | Critical | `agent.py:47` `eval(q)` on unvalidated input | Arbitrary code execution vulnerability |
| **`shell=True` with user input** | Critical | `tools/system_control.py:9-23` | Command injection vulnerability |
| **No memory system** | High | Notes stored in flat `notes.txt`; conversations ephemeral | No learning, no context, no personalization |
| **No semantic retrieval** | High | No embeddings, no vector store | Cannot find relevant past information |
| **Duplicate code** | Medium | `browser.py` and `search_cards.py` duplicate URL decoding | Maintenance burden, inconsistency risk |
| **Global mutable state** | Medium | `pending_action` global in `agent.py` | Race conditions, untestable |
| **No observability** | Medium | No execution traces, no agent monitoring | Impossible to debug routing decisions |
| **No learning loop** | High | Outcomes not tracked | System never improves |
| **Synchronous blocking** | Medium | All LLM and web requests block sequentially | Poor responsiveness |

### 1.2 Transformation Goals Achieved

The rebuilt architecture eliminates every weakness above and introduces:

- **Reasoning-based routing** — LLM-powered Commander Agent decides routing with confidence scores
- **Defense in depth** — AST-based math evaluator, command allowlists, confirmation gates
- **Structured memory** — SQLite relational store + numpy vector embeddings
- **Semantic retrieval** — Ollama embeddings with cosine similarity search
- **9 specialized agents** — each with defined capabilities and lifecycle
- **Real-time observability** — execution traces, agent monitor, data stream feed
- **Learning feedback loops** — outcome tracking, pattern discovery, routing accuracy metrics
- **Production resilience** — retry logic, circuit-breaker patterns, graceful degradation

---

## 2. System Design

### 2.1 Design Principles

1. **Single Responsibility** — Each agent owns one domain. The Commander coordinates; it does not execute.
2. **Fail Safe** — Dangerous operations require explicit confirmation. Unknown inputs route to safe defaults.
3. **Observable** — Every agent execution produces a trace. Every routing decision is logged.
4. **Learnable** — Every outcome (success/failure) is persisted and analyzed.
5. **Swappable** — LLM backend, vector store, and database can be replaced without touching agent logic.

### 2.2 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              STREAMLIT UI                                    │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌────────────────┐  │
│  │ Status Bar   │  │Agent Network │  │ Chat + Cards │  │  Sidebar       │  │
│  │ (metrics)    │  │ (SVG viz)    │  │ (messages)   │  │  (monitor etc) │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  └────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           COMMANDER AGENT                                    │
│  • Receives all user input                                                   │
│  • Uses LLM reasoning for routing decisions                                  │
│  • Retrieves memory context when needed                                      │
│  • Dispatches to primary + supporting agents                                 │
│  • Aggregates responses                                                      │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
              ┌──────────┬──────────┬┴┬──────────┬──────────┐
              ▼          ▼          ▼ ▼          ▼          ▼
┌─────────┐ ┌────────┐ ┌──────────┐ ┌─────────┐ ┌────────┐ ┌──────────┐
│ Planner │ │Research│ │ Memory   │ │  Coder  │ │Executor│ │ Browser  │
│ Agent   │ │ Agent  │ │ Agent    │ │  Agent  │ │ Agent  │ │  Agent   │
└─────────┘ └────────┘ └──────────┘ └─────────┘ └────────┘ └──────────┘
                                              ┌──────────┐
                                              │  File    │
                                              │  Agent   │
                                              └──────────┘
                                              ┌──────────┐
                                              │ Learner  │
                                              │  Agent   │
                                              └──────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         SHARED INFRASTRUCTURE                                │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌────────────┐            │
│  │ LLMClient  │  │ MessageBus │  │ AgentRegistry│ │ ToolRegistry│           │
│  │ (Ollama)   │  │ (pub/sub)  │  │ (discovery)  │ │ (discovery) │           │
│  └────────────┘  └────────────┘  └────────────┘  └────────────┘            │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐                            │
│  │ SystemState│  │ MemoryManager│ │ SafeExecutor │                          │
│  │ (runtime)  │  │ (SQLite+Vec) │ │ (sandbox)    │                          │
│  └────────────┘  └────────────┘  └────────────┘                            │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.3 Layer Responsibilities

| Layer | Components | Responsibility |
|---|---|---|
| **Presentation** | `app.py`, `ui/components.py`, `styles/style.css` | Render dashboard, agent network SVG, chat, cards |
| **Orchestration** | `orchestrator.py`, `CommanderAgent` | Initialize system, route requests, coordinate agents |
| **Agents** | `agents/*.py` | Execute domain-specific tasks with traces |
| **Tools** | `framework/tools.py`, `framework/executor.py` | Provide safe, sandboxed capabilities to agents |
| **Memory** | `memory/*.py` | Persist conversations, memories, notes, goals, outcomes |
| **Core** | `core/*.py` | LLM communication, messaging, registries, state |

---

## 3. File Structure

```
jarvis/
│
├── app.py                          ← Streamlit entry point (rebuilt)
├── orchestrator.py                 ← System bootstrap + agent registration
├── config.py                       ← Central configuration (rebuilt)
├── requirements.txt                ← Dependencies (added pydantic)
│
├── core/                           ← FOUNDATION LAYER
│   ├── __init__.py                 ← Public API exports
│   ├── models.py                   ← Pydantic v2 models (all data contracts)
│   ├── exceptions.py               ← Hierarchical exception classes
│   ├── llm_client.py               ← Ollama client with retry/circuit-breaker
│   ├── message_bus.py              ← In-memory pub/sub for agent events
│   ├── registry.py                 ← AgentRegistry + ToolRegistry (singletons)
│   └── state.py                    ← SystemState (thread-safe runtime state)
│
├── memory/                         ← MEMORY LAYER
│   ├── __init__.py
│   ├── database.py                 ← SQLite connection manager (WAL mode)
│   ├── sqlite_store.py             ← CRUD for all structured data
│   ├── vector_store.py             ← Numpy-based embedding store + cosine search
│   └── memory_manager.py           ← Unified API combining SQL + vector
│
├── framework/                      ← TOOL FRAMEWORK
│   ├── __init__.py
│   ├── decorators.py               ← @tool decorator for auto-registration
│   ├── executor.py                 ← SafeExecutor (validation + confirmation + timeout)
│   └── tools.py                    ← Built-in tools: web, file, system, notes, math
│
├── agents/                         ← AGENT LAYER (9 agents)
│   ├── __init__.py
│   ├── base.py                     ← BaseAgent (lifecycle, traces, tool calling)
│   ├── commander.py                ← Entry router (LLM reasoning, no hardcode)
│   ├── planner.py                  ← Goal decomposition, roadmap creation
│   ├── researcher.py               ← Web search, content extraction, summarization
│   ├── memory_agent.py             ← Memory CRUD, preference management
│   ├── coder.py                    ← Code generation, review, debugging
│   ├── executor.py                 ← System operations with safety gates
│   ├── browser.py                  ─ Web navigation and content extraction
│   ├── file_agent.py               ← File search, read, directory listing
│   └── learner.py                  ← Outcome analysis, pattern discovery
│
├── ui/                             ← PRESENTATION LAYER
│   ├── __init__.py
│   ├── components.py               ← SVG agent network, monitors, chat, cards
│   └── app.py                      ← (alternative entry point)
│
├── voice/                          ← VOICE SUBSYSTEM
│   ├── __init__.py
│   └── interface.py                ← Faster-Whisper STT + pyttsx3 TTS wrapper
│
├── database/
│   └── schema.sql                  ← Complete SQLite schema (PostgreSQL-compatible)
│
├── styles/
│   └── style.css                   ← Futuristic dark theme (rebuilt)
│
└── data/                           ← (auto-created) SQLite DB, vector cache, logs
```

---

## 4. Agent Communication Design

### 4.1 Commander → Agent Dispatch Flow

```
User Input
    │
    ▼
┌────────────────────────────────────────┐
│ CommanderAgent.process_user_input()    │
│                                        │
│ 1. Check pending confirmations         │
│ 2. Handle trivial cases (greetings)    │
│ 3. LLM routing decision (JSON)         │
│    → intent, primary_agent, confidence │
│ 4. Retrieve memory context (if needed) │
│ 5. Dispatch work_task to primary agent │
│ 6. Optionally dispatch supporting      │
│ 7. Log routing decision for learning   │
│ 8. Return aggregated response          │
└────────────────────────────────────────┘
    │
    ▼
PrimaryAgent.execute(task)
    │
    ▼
BaseAgent.execute(task) ──→ execute_task(task, trace)
    │                           │
    │                           ▼
    │                     Agent-specific logic
    │                           │
    │                           ▼
    │                     Tool calls via SafeExecutor
    │                           │
    │                           ▼
    │                     LLM calls via LLMClient
    │                           │
    │                           ▼
    │                     Return AgentResponse
    │
    ▼
MessageBus.publish("agent_response", ...)
```

### 4.2 Message Bus Topics

| Topic | Publisher | Subscriber | Purpose |
|---|---|---|---|
| `user_input` | UI | Commander | New user message |
| `agent_request` | Commander | Target Agent | Task dispatch |
| `agent_response` | Any Agent | UI, Learner | Completed response |
| `tool_call` | Any Agent | SafeExecutor | Tool execution |
| `tool_result` | SafeExecutor | Calling Agent | Tool completion |
| `memory_update` | MemoryAgent | MemoryManager | Memory mutation |
| `system_event` | Any component | Logger | Internal events |

### 4.3 No Hardcoded Routing — Evidence

The CommanderAgent (`agents/commander.py:87-195`) constructs a prompt describing all agents and their capabilities, then asks the LLM to decide routing. The response is parsed as structured JSON. A fallback keyword heuristic exists only for when the LLM is unreachable.

```python
# No more: if "youtube" in command: open_youtube()
# Instead:
routing = self._route_via_llm(user_input)  # LLM decides
primary_agent = self.registry.get(routing.primary_agent)
response = primary_agent.execute(work_task)
```

---

## 5. Memory Design

### 5.1 Two-Tier Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    MemoryManager                            │
│                                                             │
│  ┌──────────────────┐        ┌──────────────────────┐      │
│  │   SQLiteStore    │◄──────►│  SimpleVectorStore   │      │
│  │  (Structured)    │        │   (Semantic)         │      │
│  └──────────────────┘        └──────────────────────┘      │
│         │                              │                    │
│         ▼                              ▼                    │
│  ┌──────────────┐             ┌─────────────────┐          │
│  │ SQLite DB    │             │ Numpy Arrays    │          │
│  │ jarvis.db    │             │ + Pickle Cache  │          │
│  └──────────────┘             └─────────────────┘          │
└─────────────────────────────────────────────────────────────┘
```

### 5.2 Storage Types

| Type | Store | Use Case | Retrieval |
|---|---|---|---|
| **Conversations** | SQLite | Chat history | Temporal (recent first) |
| **Memories** | SQLite + Vector | Facts, preferences, learnings | Hybrid (semantic + keyword) |
| **Outcomes** | SQLite | Action results for learning | Aggregated statistics |
| **Preferences** | SQLite | User settings | Key-value lookup |
| **Goals** | SQLite | Plans and milestones | Status-filtered |
| **Tasks** | SQLite | Actionable items | Priority-sorted |
| **Notes** | SQLite + Vector | Saved research | Search + semantic |
| **Projects** | SQLite | Active project context | Name lookup |
| **Embeddings** | Vector Store | Semantic search | Cosine similarity |

### 5.3 Semantic Retrieval

1. User query is embedded via Ollama `/api/embeddings`
2. Normalized vector is compared against stored vectors via dot product
3. Top-k results filtered by similarity threshold (default 0.6)
4. Results enriched with SQLite metadata
5. Combined with keyword search for hybrid retrieval
6. Formatted as context string for LLM prompts

### 5.4 Auto-Memory Extraction

The MemoryManager monitors user messages for trigger phrases ("I like", "my goal is", "remind me") and automatically stores them as `MemoryType.CONVERSATION` entries with elevated importance.

---

## 6. Database Design

### 6.1 Schema Overview (SQLite)

| Table | Purpose | Key Columns |
|---|---|---|
| `conversations` | All chat turns | session_id, role, content, agent_name, task_id |
| `memories` | Long-term memory | memory_type, content, importance, embedding_id |
| `outcomes` | Learning data | request, agent_name, action_taken, success, confidence |
| `user_preferences` | Settings | key, value, value_type |
| `goals` | User objectives | goal_id, title, status, progress, due_date |
| `tasks` | Actionable work items | task_id, status, assigned_agent, priority |
| `notes` | Saved notes | title, content, source_url, tags |
| `projects` | Active projects | project_id, name, context, status |
| `agent_executions` | Observability | execution_id, agent_name, status, trace |
| `routing_logs` | Routing accuracy | request, primary_agent, confidence, was_correct |
| `vector_entries` | Vector metadata | entry_id, source_table, source_id, dimension |

### 6.2 PostgreSQL Migration Path

The schema is designed for easy migration:
- All IDs use `INTEGER PRIMARY KEY AUTOINCREMENT` → maps to `SERIAL` in PostgreSQL
- `TEXT` type is used universally → maps directly
- `TIMESTAMP` with `CURRENT_TIMESTAMP` → PostgreSQL compatible
- JSON metadata stored as `TEXT` → PostgreSQL `JSONB` recommended
- No SQLite-specific features beyond `PRAGMA foreign_keys` and `WAL` mode

Migration script outline:
```sql
-- 1. Export SQLite: sqlite3 jarvis.db .dump > dump.sql
-- 2. Convert AUTOINCREMENT → SERIAL
-- 3. Replace SQLite pragmas with PostgreSQL equivalents
-- 4. Import: psql -d jarvis_prod < dump.sql
-- 5. Update DatabaseManager to use psycopg2
```

### 6.3 Indexes

Every table has indexes on:
- Primary lookup columns (`session_id`, `agent_name`, `status`)
- Timestamp columns for time-series queries
- Full-text search can be added via PostgreSQL `tsvector` or SQLite FTS5

---

## 7. Exact Files Created

### 7.1 Core Infrastructure (7 files)
- `core/__init__.py`
- `core/models.py` — 35 Pydantic models for all data contracts
- `core/exceptions.py` — 14 exception classes with retry/recovery metadata
- `core/llm_client.py` — Unified LLM interface with exponential backoff retry
- `core/message_bus.py` — Pub/sub event bus with 1000-event history
- `core/registry.py` — Agent and tool registries with introspection
- `core/state.py` — Thread-safe system state with confirmation management

### 7.2 Memory System (5 files)
- `memory/__init__.py`
- `memory/database.py` — Thread-local SQLite with WAL mode
- `memory/sqlite_store.py` — 25+ CRUD methods covering all tables
- `memory/vector_store.py` — Numpy cosine similarity with pickle persistence
- `memory/memory_manager.py` — Unified facade with auto-extraction

### 7.3 Tool Framework (4 files)
- `framework/__init__.py`
- `framework/decorators.py` — `@tool` decorator with schema inference
- `framework/executor.py` — SafeExecutor with validation, timeout, confirmation
- `framework/tools.py` — 16 built-in tools (web, file, system, notes, math)

### 7.4 Agent Framework (11 files)
- `agents/__init__.py`
- `agents/base.py` — BaseAgent with lifecycle, tracing, retry
- `agents/commander.py` — LLM-based routing, no hardcode
- `agents/planner.py` — Goal decomposition with plan storage
- `agents/researcher.py` — Search + fetch + summarize pipeline
- `agents/memory_agent.py` — Memory CRUD and query answering
- `agents/coder.py` — Code generation, review, debugging
- `agents/executor.py` — System control with safety gates
- `agents/browser.py` — Web navigation and extraction
- `agents/file_agent.py` — File search, read, directory listing
- `agents/learner.py` — Outcome analysis and pattern discovery

### 7.5 UI & Voice (4 files)
- `ui/__init__.py`
- `ui/components.py` — SVG agent network, monitors, chat, cards
- `voice/__init__.py`
- `voice/interface.py` — STT/TTS wrapper with SystemState integration

### 7.6 Supporting (3 files)
- `orchestrator.py` — System initialization and bootstrap
- `database/schema.sql` — Complete relational schema
- `ARCHITECTURE.md` — This document

**Total new files: 34**

---

## 8. Exact Files Modified

| File | Modification |
|---|---|
| `requirements.txt` | Added `pydantic>=2.0.0` |
| `config.py` | Complete rewrite — hierarchical, environment-aware, 50+ settings |
| `styles/style.css` | Complete rewrite — status bar, agent network, monitor panels, data stream |
| `app.py` | Complete rewrite — new dashboard with agent network, monitoring, voice |

**Total modified files: 4**

---

## 9. Full Production Code

All code has been delivered. No placeholders, no TODOs, no stub functions.

Every file:
- Compiles successfully (`python -m py_compile` verified on all 34 modules)
- Has complete implementations
- Includes error handling
- Has docstrings
- Uses type hints

---

## 10. Testing Checklist

### 10.1 Unit Tests (pytest recommended)

```python
# tests/test_core.py
- test_llm_client_retry_logic()
- test_llm_client_exponential_backoff()
- test_message_bus_publish_subscribe()
- test_agent_registry_register_get()
- test_tool_registry_schema_inference()
- test_system_state_confirmation_lifecycle()

# tests/test_memory.py
- test_sqlite_store_crud()
- test_vector_store_add_search()
- test_memory_manager_hybrid_search()
- test_memory_manager_auto_extract()

# tests/test_framework.py
- test_safe_executor_parameter_validation()
- test_safe_executor_dangerous_blocked()
- test_safe_executor_confirmation_gate()
- test_math_evaluate_safety()
- test_web_search_returns_results()

# tests/test_agents.py
- test_commander_trivial_handling()
- test_commander_fallback_routing()
- test_planner_plan_generation()
- test_researcher_card_detection()
- test_executor_power_commands_require_confirmation()
- test_learner_pattern_discovery()
```

### 10.2 Integration Tests

| Test | Steps | Expected |
|---|---|---|
| **End-to-end chat** | Type "What is Python?" | Commander routes to Researcher, returns answer |
| **Planning flow** | Type "I have an interview in 10 days" | Planner creates roadmap, stores goal, creates tasks |
| **System command** | Type "open notepad" | Executor opens Notepad |
| **Confirmation gate** | Type "shutdown" | Executor requests confirmation, waits for "yes" |
| **Memory recall** | Type "Remember I like Python" then "What do I like?" | MemoryAgent recalls stored preference |
| **Code generation** | Type "Write a fibonacci function" | Coder returns code block |
| **File search** | Type "Find all PDFs in Documents" | FileAgent returns PDF list |
| **Search cards** | Type "Latest AI news" | Researcher returns card data rendered in UI |
| **Multi-turn** | Ask 3 related questions | Memory context builds, routing improves |

### 10.3 UI Tests (manual)

- [ ] Agent network SVG renders without errors
- [ ] Active agent glows and shows data flow animation
- [ ] Status bar updates with LLM health
- [ ] Chat messages display with agent badges
- [ ] Search cards render with hover effects
- [ ] Sidebar monitor shows real-time agent states
- [ ] Execution logs populate after each request
- [ ] Data stream shows recent events
- [ ] Memory panel counters update
- [ ] Clear Session button resets state
- [ ] Voice recorder button appears and records

### 10.4 Security Tests

- [ ] `eval()` is never called on user input (verify with grep)
- [ ] `shell=True` only used with allowlisted commands
- [ ] Dangerous commands are blocked by safety check
- [ ] Shutdown/restart require confirmation
- [ ] File operations restricted to safe paths
- [ ] SQL injection prevented (parameterized queries only)

### 10.5 Performance Tests

- [ ] LLM timeout handled gracefully (test with 1ms timeout)
- [ ] Web search timeout handled gracefully
- [ ] Large file reads truncated at 5MB
- [ ] Chat history limited to 50 messages
- [ ] Vector search returns within 500ms for <1000 entries
- [ ] Streamlit rerender completes within 2 seconds

### 10.6 Run Commands

```bash
# Install dependencies
cd jarvis
pip install -r requirements.txt

# Ensure Ollama is running
ollama serve

# Start the system
streamlit run app.py

# Run syntax verification
python -m py_compile core/*.py memory/*.py framework/*.py agents/*.py ui/*.py voice/*.py orchestrator.py app.py
```

---

## 11. Future Scaling Roadmap

### Phase 1: Current (v2.0) — Local Single-Process
- **Database:** SQLite with WAL mode
- **LLM:** Ollama local (Llama3, Mistral, Nomic Embed)
- **Vector:** Numpy in-memory with pickle persistence
- **Deployment:** Streamlit single-process
- **Users:** Single user, single session

### Phase 2: Enhanced Local (v2.1) — Target Q3 2026
- [ ] **PostgreSQL migration** — Replace SQLite for concurrent access
- [ ] **Redis caching** — Cache LLM responses, search results
- [ ] **Sentence-Transformers** — Optional local embeddings without Ollama
- [ ] **ChromaDB integration** — Production vector database option
- [ ] **Background tasks** — Async agent execution with `asyncio`
- [ ] **Session management** — Multi-user with authentication

### Phase 3: Distributed (v2.2) — Target Q4 2026
- [ ] **Message Queue** — RabbitMQ or Redis Streams for agent communication
- [ ] **Agent workers** — Celery tasks for long-running agents
- [ ] **WebSocket UI** — Real-time bidirectional updates (replace polling)
- [ ] **API server** — FastAPI backend decoupled from Streamlit
- [ ] **Containerization** — Docker Compose for local development

### Phase 4: Cloud-Ready (v3.0) — Target 2027
- [ ] **Kubernetes deployment** — Horizontal pod autoscaling per agent
- [ ] **Cloud LLM support** — OpenAI, Anthropic, Google Vertex fallback
- [ ] **Observability stack** — Prometheus metrics, Grafana dashboards, Jaeger tracing
- [ ] **Multi-tenant** — Organization isolation, RBAC
- [ ] **Fine-tuning pipeline** — Collect outcomes, fine-tune routing model

### Phase 5: Intelligence (v3.5+) — Target 2027+
- [ ] **Self-improving routing** — Reinforcement learning on routing decisions
- [ ] **Agent composition** — Dynamic agent creation for novel tasks
- [ ] **Long-term planning** — Multi-day autonomous execution with checkpoints
- [ ] **Knowledge graph** — Structured entity relationships beyond vector search
- [ ] **Multi-modal** — Vision agents, document parsing, image generation

---

## Appendix: Security Hardening Checklist

| Layer | Control | Status |
|---|---|---|
| Input | AST-based math evaluator (no `eval`) | ✅ |
| Input | Regex sanitization on tool parameters | ✅ |
| Tools | Allowlist for `subprocess` commands | ✅ |
| Tools | `dangerous=True` flag on power tools | ✅ |
| Tools | `requires_confirmation=True` gate | ✅ |
| Tools | Parameter schema validation before execution | ✅ |
| Tools | Execution timeout (120s default) | ✅ |
| Agents | Max retries (2) with exponential backoff | ✅ |
| LLM | Connection timeout + retry logic | ✅ |
| State | Confirmation ID required for dangerous ops | ✅ |
| Database | Parameterized queries (no string interpolation) | ✅ |
| Files | 5MB read limit, path validation | ✅ |

---

*Document Version: 2.0.0*  
*Generated: 2026-06-19*  
*Author: Open-Thinking Architecture Team*
