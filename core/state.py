"""
Centralized System State Manager for Jarvis Multi-Agent AI Operating System.

Maintains global system state including:
- Current active agent and task
- Pending confirmations
- Session information
- Agent health/status snapshots

Thread-safe for concurrent access within the single-process model.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from core.models import AgentMonitorState, AgentStatus, SystemHealth

logger = logging.getLogger(__name__)


@dataclass
class PendingConfirmation:
    """Represents an action awaiting user confirmation."""
    action_id: str
    description: str
    agent_name: str
    callback: Any  # Callable to execute on confirmation
    created_at: float = field(default_factory=time.time)


class SystemState:
    """
    Singleton managing the global runtime state of Jarvis.

    Provides thread-safe accessors for:
        - active_agent: Currently executing agent name
        - active_task_id: Current task being processed
        - pending_confirmations: Safety-gated operations awaiting approval
        - agent_states: Health/status snapshots of all agents
        - session_metadata: Ephemeral session data
    """

    _instance: Optional[SystemState] = None
    _initialized: bool = False

    def __new__(cls) -> SystemState:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if SystemState._initialized:
            return
        self._lock = threading.RLock()
        self._active_agent: Optional[str] = None
        self._active_task_id: Optional[str] = None
        self._active_task_description: Optional[str] = None
        self._pending_confirmations: Dict[str, PendingConfirmation] = {}
        self._agent_states: Dict[str, AgentMonitorState] = {}
        self._session_start: float = time.time()
        self._session_metadata: Dict[str, Any] = {}
        self._last_error: Optional[str] = None
        self._conversation_count: int = 0
        SystemState._initialized = True

    # -------------------------------------------------------------------------
    # ACTIVE AGENT / TASK
    # -------------------------------------------------------------------------

    def set_active_agent(self, agent_name: str, task_id: str | None = None, task_description: str | None = None) -> None:
        """Mark an agent as currently active."""
        with self._lock:
            self._active_agent = agent_name
            self._active_task_id = task_id
            self._active_task_description = task_description
            self._update_agent_state(agent_name, status=AgentStatus.RUNNING, current_task=task_description)
        logger.debug(f"Active agent set: {agent_name} (task: {task_id})")

    def clear_active_agent(self, agent_name: str | None = None) -> None:
        """Clear the active agent (optionally verifying it matches)."""
        with self._lock:
            if agent_name is None or self._active_agent == agent_name:
                if self._active_agent:
                    self._update_agent_state(self._active_agent, status=AgentStatus.IDLE)
                self._active_agent = None
                self._active_task_id = None
                self._active_task_description = None

    @property
    def active_agent(self) -> Optional[str]:
        with self._lock:
            return self._active_agent

    @property
    def active_task_id(self) -> Optional[str]:
        with self._lock:
            return self._active_task_id

    @property
    def active_task_description(self) -> Optional[str]:
        with self._lock:
            return self._active_task_description

    # -------------------------------------------------------------------------
    # CONFIRMATIONS
    # -------------------------------------------------------------------------

    def request_confirmation(self, action_id: str, description: str, agent_name: str, callback: Any) -> None:
        """Register an action requiring user confirmation."""
        with self._lock:
            self._pending_confirmations[action_id] = PendingConfirmation(
                action_id=action_id,
                description=description,
                agent_name=agent_name,
                callback=callback,
            )
        logger.info(f"Confirmation requested [{action_id}]: {description}")

    def get_pending_confirmation(self, action_id: str) -> Optional[PendingConfirmation]:
        """Retrieve a pending confirmation by ID."""
        with self._lock:
            return self._pending_confirmations.get(action_id)

    def get_all_pending_confirmations(self) -> List[PendingConfirmation]:
        """List all pending confirmations."""
        with self._lock:
            return list(self._pending_confirmations.values())

    def confirm_action(self, action_id: str) -> Any:
        """Execute the callback for a confirmed action."""
        with self._lock:
            pc = self._pending_confirmations.pop(action_id, None)
        if pc is None:
            logger.warning(f"Confirmation for unknown action: {action_id}")
            return None
        logger.info(f"Action confirmed [{action_id}]: {pc.description}")
        try:
            return pc.callback()
        except Exception as e:
            logger.error(f"Confirmed action failed [{action_id}]: {e}")
            raise

    def cancel_action(self, action_id: str) -> bool:
        """Cancel a pending confirmation."""
        with self._lock:
            pc = self._pending_confirmations.pop(action_id, None)
        if pc:
            logger.info(f"Action cancelled [{action_id}]: {pc.description}")
            return True
        return False

    def has_pending_confirmations(self) -> bool:
        with self._lock:
            return len(self._pending_confirmations) > 0

    # -------------------------------------------------------------------------
    # AGENT STATES
    # -------------------------------------------------------------------------

    def _update_agent_state(self, agent_name: str, **kwargs: Any) -> None:
        """Internal: update or create an agent's monitor state."""
        if agent_name not in self._agent_states:
            self._agent_states[agent_name] = AgentMonitorState(agent_name=agent_name, status=AgentStatus.IDLE)
        state = self._agent_states[agent_name]
        for key, value in kwargs.items():
            if hasattr(state, key):
                # Coerce string status values into proper AgentStatus enum.
                # This defends against raw string assignment via setattr.
                if key == "status" and isinstance(value, str):
                    try:
                        value = AgentStatus(value)
                    except ValueError:
                        value = AgentStatus.IDLE
                setattr(state, key, value)
        state.last_activity = time.time()

    def update_agent_state(self, agent_name: str, **kwargs: Any) -> None:
        """Public: update an agent's state."""
        with self._lock:
            self._update_agent_state(agent_name, **kwargs)

    def get_agent_state(self, agent_name: str) -> Optional[AgentMonitorState]:
        """Get the current state of a specific agent."""
        with self._lock:
            return self._agent_states.get(agent_name)

    def get_all_agent_states(self) -> List[AgentMonitorState]:
        """Get states of all known agents."""
        with self._lock:
            return list(self._agent_states.values())

    def increment_agent_error(self, agent_name: str) -> None:
        """Increment the error count for an agent."""
        with self._lock:
            if agent_name not in self._agent_states:
                self._agent_states[agent_name] = AgentMonitorState(agent_name=agent_name, status=AgentStatus.ERROR)
            self._agent_states[agent_name].error_count += 1
            self._agent_states[agent_name].status = AgentStatus.ERROR

    # -------------------------------------------------------------------------
    # SESSION / HEALTH
    # -------------------------------------------------------------------------

    def record_conversation(self) -> None:
        """Increment the conversation counter."""
        with self._lock:
            self._conversation_count += 1

    @property
    def conversation_count(self) -> int:
        with self._lock:
            return self._conversation_count

    def set_last_error(self, error_message: str) -> None:
        with self._lock:
            self._last_error = error_message

    def get_health_snapshot(self) -> SystemHealth:
        """Generate a current system health snapshot."""
        with self._lock:
            return SystemHealth(
                uptime_seconds=int(time.time() - self._session_start),
                active_agents=sum(1 for s in self._agent_states.values() if s.status == AgentStatus.RUNNING),
                pending_tasks=len(self._pending_confirmations),
                total_conversations=self._conversation_count,
                memory_entries=0,  # Populated by MemoryManager
                last_error=self._last_error,
                llm_available=False,  # Populated by caller
                voice_available=False,  # Populated by caller
            )

    # -------------------------------------------------------------------------
    # SESSION METADATA
    # -------------------------------------------------------------------------

    def get_session_meta(self, key: str, default: Any = None) -> Any:
        with self._lock:
            return self._session_metadata.get(key, default)

    def set_session_meta(self, key: str, value: Any) -> None:
        with self._lock:
            self._session_metadata[key] = value

    def clear_session(self) -> None:
        """Reset session-specific state without affecting agents."""
        with self._lock:
            self._session_metadata.clear()
            self._pending_confirmations.clear()
            self._conversation_count = 0
            self._last_error = None
