"""
Pydantic data models for the Jarvis Multi-Agent AI Operating System.

All internal communication, storage, and API contracts use these models
to ensure type safety, validation, and serialization consistency.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator


# =============================================================================
# ENUMS
# =============================================================================

class AgentStatus(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    ERROR = "error"


class TaskStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class MemoryType(str, Enum):
    CONVERSATION = "conversation"
    PREFERENCE = "preference"
    PROJECT = "project"
    GOAL = "goal"
    NOTE = "note"
    ACTION = "action"
    LEARNING = "learning"
    INSIGHT = "insight"


class GoalStatus(str, Enum):
    ACTIVE = "active"
    COMPLETED = "completed"
    PAUSED = "paused"
    CANCELLED = "cancelled"


# =============================================================================
# CORE MESSAGE MODELS
# =============================================================================

class Message(BaseModel):
    """A single message in a conversation."""

    model_config = ConfigDict(json_encoders={datetime: lambda v: v.isoformat()})

    role: Literal["user", "assistant", "system"] = Field(..., description="Sender role")
    content: str = Field(..., min_length=1, description="Message content")
    agent_name: Optional[str] = Field(None, description="Agent that produced this message, if any")
    task_id: Optional[str] = Field(None, description="Associated task ID")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional context")


# =============================================================================
# TOOL MODELS
# =============================================================================

class ToolParameter(BaseModel):
    """Schema for a single tool parameter."""

    name: str
    type: str = Field(default="string", description="JSON Schema type")
    description: str
    required: bool = True
    default: Optional[Any] = None
    enum: Optional[List[Any]] = None


class ToolSchema(BaseModel):
    """JSON Schema-like definition for a tool."""

    name: str
    description: str
    parameters: List[ToolParameter] = Field(default_factory=list)
    returns: Dict[str, Any] = Field(default_factory=dict)
    dangerous: bool = False
    requires_confirmation: bool = False


class ToolCall(BaseModel):
    """Represents an invocation of a tool."""

    model_config = ConfigDict(json_encoders={datetime: lambda v: v.isoformat()})

    tool_name: str
    parameters: Dict[str, Any] = Field(default_factory=dict)
    call_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ToolResult(BaseModel):
    """Result of a tool execution."""

    model_config = ConfigDict(json_encoders={datetime: lambda v: v.isoformat()})

    call_id: str
    tool_name: str
    success: bool
    result: Any = None
    error_message: Optional[str] = None
    execution_time_ms: Optional[int] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# =============================================================================
# AGENT TASK / RESPONSE MODELS
# =============================================================================

class AgentTask(BaseModel):
    """A task assigned to an agent."""

    model_config = ConfigDict(json_encoders={datetime: lambda v: v.isoformat()})

    task_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:12])
    description: str = Field(..., min_length=1)
    task_type: str = Field(default="general", description="Category of task")
    priority: int = Field(default=3, ge=1, le=5)
    context: Dict[str, Any] = Field(default_factory=dict)
    parent_task_id: Optional[str] = None
    assigned_agent: Optional[str] = None
    status: TaskStatus = TaskStatus.PENDING
    created_at: datetime = Field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Optional[str] = None

    @field_validator("priority")
    @classmethod
    def validate_priority(cls, v: int) -> int:
        if not 1 <= v <= 5:
            raise ValueError("Priority must be between 1 and 5")
        return v


class AgentResponse(BaseModel):
    """Response from an agent after completing a task."""

    model_config = ConfigDict(json_encoders={datetime: lambda v: v.isoformat()})

    agent_name: str
    task_id: str
    success: bool
    response: str = Field(default="", description="Human-readable response")
    data: Dict[str, Any] = Field(default_factory=dict, description="Structured result data")
    tools_used: List[ToolCall] = Field(default_factory=list)
    tool_results: List[ToolResult] = Field(default_factory=list)
    execution_time_ms: int = Field(default=0, ge=0)
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# =============================================================================
# PLANNING MODELS
# =============================================================================

class PlanStep(BaseModel):
    """A single step in a plan."""

    step_number: int = Field(ge=1)
    description: str
    assigned_agent: Optional[str] = None
    estimated_duration_minutes: Optional[int] = None
    dependencies: List[int] = Field(default_factory=list)
    status: TaskStatus = TaskStatus.PENDING
    result_summary: Optional[str] = None
    # Priority: 1 (critical) .. 5 (low). Defaults to 3 (normal).
    priority: int = Field(default=3, ge=1, le=5)
    # Optional milestone this step belongs to (references Milestone.milestone_id).
    milestone_id: Optional[str] = None

    @field_validator("priority")
    @classmethod
    def validate_step_priority(cls, v: int) -> int:
        if not 1 <= v <= 5:
            raise ValueError("Step priority must be between 1 and 5")
        return v


class Milestone(BaseModel):
    """A named checkpoint grouping related plan steps, with a target date."""

    model_config = ConfigDict(json_encoders={datetime: lambda v: v.isoformat()})

    milestone_id: str = Field(default_factory=lambda: f"ms_{uuid.uuid4().hex[:8]}")
    title: str
    description: Optional[str] = None
    # Step numbers (not ids) this milestone encompasses.
    step_numbers: List[int] = Field(default_factory=list)
    # 0.0 .. 1.0 — fraction of overall plan progress this milestone represents.
    target_progress: float = Field(default=0.0, ge=0.0, le=1.0)
    due_date: Optional[datetime] = None
    status: TaskStatus = TaskStatus.PENDING


class Plan(BaseModel):
    """A structured plan created by the Planner Agent."""

    model_config = ConfigDict(json_encoders={datetime: lambda v: v.isoformat()})

    plan_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:12])
    title: str
    description: str
    goal: str
    steps: List[PlanStep] = Field(default_factory=list)
    milestones: List[Milestone] = Field(default_factory=list)
    estimated_completion: Optional[datetime] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    status: TaskStatus = TaskStatus.PENDING


# =============================================================================
# MEMORY MODELS
# =============================================================================

class MemoryEntry(BaseModel):
    """A single memory entry stored in the system."""

    model_config = ConfigDict(json_encoders={datetime: lambda v: v.isoformat()})

    id: Optional[int] = None
    memory_type: MemoryType
    content: str = Field(..., min_length=1)
    category: Optional[str] = None
    importance: float = Field(default=0.5, ge=0.0, le=1.0)
    source: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    embedding: Optional[List[float]] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None

    @field_validator("importance")
    @classmethod
    def validate_importance(cls, v: float) -> float:
        return max(0.0, min(1.0, v))


class MemoryRetrieval(BaseModel):
    """Result of a memory retrieval operation with similarity score."""

    memory: MemoryEntry
    similarity_score: float = Field(ge=0.0, le=1.0)
    retrieval_method: str = "semantic"  # semantic, keyword, temporal, hybrid


# =============================================================================
# LEARNING / OUTCOME MODELS
# =============================================================================

class Outcome(BaseModel):
    """Tracks the result of an agent action for learning."""

    model_config = ConfigDict(json_encoders={datetime: lambda v: v.isoformat()})

    id: Optional[int] = None
    request: str
    agent_name: str
    action_taken: str
    result: Optional[str] = None
    success: bool
    feedback: Optional[str] = None
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class PatternInsight(BaseModel):
    """An insight discovered by the Learning Agent."""

    pattern_description: str
    occurrence_count: int
    success_rate: float
    applicable_agents: List[str]
    suggested_adjustment: Optional[str] = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


# =============================================================================
# EXECUTION TRACE MODELS
# =============================================================================

class TraceEvent(BaseModel):
    """A single event in an execution trace."""

    model_config = ConfigDict(json_encoders={datetime: lambda v: v.isoformat()})

    event_type: Literal["start", "tool_call", "tool_result", "llm_call", "llm_response", "decision", "error", "end"]
    message: str
    data: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ExecutionTrace(BaseModel):
    """Complete trace of an agent execution for observability."""

    model_config = ConfigDict(json_encoders={datetime: lambda v: v.isoformat()})

    execution_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:12])
    agent_name: str
    task_id: Optional[str] = None
    task_description: Optional[str] = None
    events: List[TraceEvent] = Field(default_factory=list)
    status: Literal["running", "completed", "failed", "cancelled"] = "running"
    started_at: datetime = Field(default_factory=datetime.utcnow)
    ended_at: Optional[datetime] = None
    execution_time_ms: Optional[int] = None

    def add_event(self, event_type: str, message: str, **data: Any) -> None:
        """Append an event to the trace."""
        self.events.append(
            TraceEvent(event_type=event_type, message=message, data=data)
        )

    def finalize(self, status: Literal["completed", "failed", "cancelled"]) -> None:
        """Mark the trace as complete."""
        self.status = status
        self.ended_at = datetime.utcnow()
        if self.started_at:
            delta = self.ended_at - self.started_at
            self.execution_time_ms = int(delta.total_seconds() * 1000)


# =============================================================================
# ROUTING MODELS
# =============================================================================

class RoutingDecision(BaseModel):
    """Decision made by the Commander Agent for task routing."""

    intent: str = Field(description="Detected user intent")
    primary_agent: str = Field(description="Main agent to handle the task")
    supporting_agents: List[str] = Field(default_factory=list, description="Secondary agents")
    decomposition: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Subtask decomposition if multi-step",
    )
    needs_memory_context: bool = True
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    reasoning: str = Field(default="", description="Explanation of the routing decision")

    @field_validator("confidence")
    @classmethod
    def validate_confidence(cls, v: float) -> float:
        return max(0.0, min(1.0, v))


# =============================================================================
# SEARCH / WEB MODELS
# =============================================================================

class SearchResult(BaseModel):
    """A single web search result."""

    title: str
    summary: str
    url: str
    source: str
    timestamp: Optional[str] = None
    favicon: Optional[str] = None
    rank: int = 0


class WebContent(BaseModel):
    """Extracted web content."""

    url: str
    title: Optional[str] = None
    content: str
    extracted_at: datetime = Field(default_factory=datetime.utcnow)
    word_count: int = 0
    reading_time_minutes: int = 0


# =============================================================================
# UI / OBSERVABILITY MODELS
# =============================================================================

class AgentMonitorState(BaseModel):
    """Live state of an agent for the UI monitor."""

    agent_name: str
    status: AgentStatus
    current_task: Optional[str] = None
    current_task_id: Optional[str] = None
    tools_active: List[str] = Field(default_factory=list)
    progress_percent: int = 0
    last_activity: Optional[datetime] = None
    error_count: int = 0


class SystemHealth(BaseModel):
    """Overall system health snapshot."""

    uptime_seconds: int = 0
    active_agents: int = 0
    pending_tasks: int = 0
    total_conversations: int = 0
    memory_entries: int = 0
    last_error: Optional[str] = None
    llm_available: bool = False
    voice_available: bool = False
