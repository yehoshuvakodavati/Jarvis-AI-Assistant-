"""
Base Agent for Jarvis Multi-Agent AI Operating System.

Provides the foundation that all specialized agents extend:
- Lifecycle management (init, execute, cleanup)
- Execution tracing and observability
- Safe tool invocation
- Memory access
- Message bus integration
- Outcome recording for learning
"""

from __future__ import annotations

import logging
import time
import traceback
from abc import abstractmethod
from typing import Any, Dict, List, Optional

from config import AGENT_EXECUTION_TIMEOUT, MAX_AGENT_RETRIES, MODEL_COMMANDER
from core.exceptions import AgentExecutionError, SafetyError, ConfirmationRequiredError
from core.llm_client import LLMClient
from core.message_bus import MessageBus
from core.models import (
    AgentResponse,
    AgentStatus,
    AgentTask,
    ExecutionTrace,
    Message,
    Outcome,
    ToolCall,
    ToolResult,
)
from core.registry import AgentRegistry
from core.state import SystemState
from framework.executor import SafeExecutor
from memory.memory_manager import MemoryManager

logger = logging.getLogger(__name__)


class BaseAgent:
    """
    Abstract base class for all Jarvis agents.

    Subclasses must override:
        - name: str (class attribute)
        - description: str (class attribute)
        - capabilities: List[str] (class attribute)
        - execute_task(task): AgentResponse

    Optional overrides:
        - can_handle(task): bool
        - initialize(): void
        - shutdown(): void
    """

    name: str = "base"
    description: str = "Base agent - override in subclass"
    capabilities: List[str] = []
    default_model: str = MODEL_COMMANDER

    def __init__(self) -> None:
        self.llm = LLMClient()
        self.memory = MemoryManager()
        self.bus = MessageBus()
        self.state = SystemState()
        self.executor = SafeExecutor()
        self._initialized = False

    def initialize(self) -> None:
        """Called once before the agent processes its first task."""
        self._initialized = True
        logger.info(f"Agent '{self.name}' initialized")

    def shutdown(self) -> None:
        """Called when the agent is being shut down."""
        self._initialized = False
        logger.info(f"Agent '{self.name}' shut down")

    # -------------------------------------------------------------------------
    # PUBLIC EXECUTION API
    # -------------------------------------------------------------------------

    def execute(self, task: AgentTask) -> AgentResponse:
        """
        Execute a task with full lifecycle management.

        This is the main entry point. It handles:
        1. Initialization
        2. Trace creation
        3. State updates
        4. Delegation to execute_task()
        5. Error handling and retries
        6. Cleanup and logging
        """
        if not self._initialized:
            self.initialize()

        execution_id = f"{self.name}_{task.task_id}"
        trace = ExecutionTrace(
            execution_id=execution_id,
            agent_name=self.name,
            task_id=task.task_id,
            task_description=task.description,
        )

        # Update system state
        self.state.set_active_agent(self.name, task.task_id, task.description)
        self.state.update_agent_state(self.name, status=AgentStatus.RUNNING, current_task=task.description)

        # Log execution start
        self.memory.store.start_execution(execution_id, self.name, task.task_id, task.description)

        trace.add_event("start", f"Starting execution of task: {task.description}")

        start_time = time.time()
        last_error: Exception | None = None

        for attempt in range(1, MAX_AGENT_RETRIES + 1):
            try:
                trace.add_event("decision", f"Execution attempt {attempt}/{MAX_AGENT_RETRIES}")
                response = self.execute_task(task, trace=trace)

                # Successful execution
                elapsed_ms = int((time.time() - start_time) * 1000)
                trace.finalize("completed")
                response.execution_time_ms = elapsed_ms

                # Log execution end
                self.memory.store.end_execution(
                    execution_id=execution_id,
                    status="completed",
                    execution_time_ms=elapsed_ms,
                    tools_used=[tc.model_dump() for tc in response.tools_used],
                    execution_trace=[e.model_dump() for e in trace.events],
                )

                # Record outcome for learning
                self._record_outcome(task, response, trace)

                # Update state
                self.state.clear_active_agent(self.name)
                self.state.update_agent_state(self.name, status=AgentStatus.IDLE)

                # Publish response
                self.bus.publish_agent_response(self.name, response, task_id=task.task_id)

                return response

            except ConfirmationRequiredError:
                # Don't retry confirmation-required errors
                elapsed_ms = int((time.time() - start_time) * 1000)
                trace.finalize("failed")
                self.state.clear_active_agent(self.name)

                response = AgentResponse(
                    agent_name=self.name,
                    task_id=task.task_id,
                    success=False,
                    response="This action requires your confirmation. Please respond with 'yes' to proceed.",
                    execution_time_ms=elapsed_ms,
                )
                return response

            except Exception as e:
                last_error = e
                elapsed_ms = int((time.time() - start_time) * 1000)
                error_msg = f"{type(e).__name__}: {str(e)}"
                trace.add_event("error", f"Attempt {attempt} failed: {error_msg}", traceback=traceback.format_exc())
                logger.error(f"Agent '{self.name}' task failed (attempt {attempt}): {error_msg}")

                if attempt < MAX_AGENT_RETRIES:
                    logger.info(f"Retrying task {task.task_id}...")
                    time.sleep(0.5 * attempt)  # Small backoff

        # All retries exhausted
        elapsed_ms = int((time.time() - start_time) * 1000)
        trace.finalize("failed")

        self.memory.store.end_execution(
            execution_id=execution_id,
            status="failed",
            execution_time_ms=elapsed_ms,
            execution_trace=[e.model_dump() for e in trace.events],
        )

        self.state.increment_agent_error(self.name)
        self.state.clear_active_agent(self.name)
        self.state.update_agent_state(self.name, status=AgentStatus.ERROR)
        self.state.set_last_error(str(last_error) if last_error else "Unknown error")

        # Record failure outcome
        failure_response = AgentResponse(
            agent_name=self.name,
            task_id=task.task_id,
            success=False,
            response=f"I encountered an error while processing your request: {last_error}",
            execution_time_ms=elapsed_ms,
        )
        self._record_outcome(task, failure_response, trace)

        return failure_response

    def can_handle(self, task: AgentTask) -> bool:
        """
        Check if this agent can handle the given task.

        Default implementation checks if task.task_type is in capabilities.
        Subclasses can override for more nuanced logic.
        """
        return task.task_type in self.capabilities or "general" in self.capabilities

    # -------------------------------------------------------------------------
    # ABSTRACT METHOD
    # -------------------------------------------------------------------------

    @abstractmethod
    def execute_task(self, task: AgentTask, trace: ExecutionTrace | None = None) -> AgentResponse:
        """
        Implement the agent's core logic.

        Args:
            task: The task to execute.
            trace: Execution trace for observability.

        Returns:
            AgentResponse with the result.
        """
        raise NotImplementedError

    # -------------------------------------------------------------------------
    # UTILITY METHODS FOR SUBCLASSES
    # -------------------------------------------------------------------------

    def call_tool(self, tool_name: str, **parameters: Any) -> ToolResult:
        """Convenience: invoke a tool via the safe executor."""
        tc = ToolCall(tool_name=tool_name, parameters=parameters)
        return self.executor.execute(tc)

    def call_llm(
        self,
        prompt: str,
        *,
        system: str | None = None,
        model: str | None = None,
        temperature: float | None = None,
        json_mode: bool = False,
    ) -> str:
        """Convenience: call the LLM."""
        return self.llm.generate(
            prompt,
            system=system,
            model=model or self.default_model,
            temperature=temperature,
            json_mode=json_mode,
        )

    def call_llm_structured(
        self,
        prompt: str,
        *,
        system: str | None = None,
        model: str | None = None,
        temperature: float | None = None,
    ) -> Any:
        """Convenience: call the LLM and parse structured output."""
        return self.llm.generate_structured(
            prompt,
            system=system,
            model=model or self.default_model,
            temperature=temperature,
        )

    def get_memory_context(self, query: str, max_items: int = 5) -> str:
        """Get relevant memory context for a query."""
        return self.memory.build_context_for_prompt(query, max_items=max_items)

    def record_outcome(self, task: AgentTask, response: AgentResponse, success: bool, feedback: str | None = None) -> None:
        """Manually record an outcome for learning."""
        outcome = Outcome(
            request=task.description,
            agent_name=self.name,
            action_taken=task.task_type,
            result=response.response,
            success=success,
            feedback=feedback,
            metadata={
                "task_id": task.task_id,
                "tools_used": [t.tool_name for t in response.tools_used],
                "execution_time_ms": response.execution_time_ms,
            },
        )
        self.memory.record_outcome(outcome)

    # -------------------------------------------------------------------------
    # PRIVATE
    # -------------------------------------------------------------------------

    def _record_outcome(self, task: AgentTask, response: AgentResponse, trace: ExecutionTrace) -> None:
        """Automatically record outcome after task completion."""
        outcome = Outcome(
            request=task.description,
            agent_name=self.name,
            action_taken=task.task_type,
            result=response.response[:500] if response.response else None,
            success=response.success,
            metadata={
                "task_id": task.task_id,
                "tools_used": [t.tool_name for t in response.tools_used],
                "execution_time_ms": response.execution_time_ms,
                "trace_event_count": len(trace.events),
            },
        )
        try:
            self.memory.record_outcome(outcome)
        except Exception as e:
            logger.warning(f"Failed to record outcome: {e}")
