"""
Safe Tool Executor for Jarvis Multi-Agent AI Operating System.

Handles tool execution with:
- Parameter validation against schemas
- Safety checks for dangerous operations
- User confirmation gating
- Timeout enforcement
- Execution tracing
- Error handling and result wrapping
"""

from __future__ import annotations

import functools
import logging
import signal
import subprocess
import threading
import time
from typing import Any, Callable

import json

from core.exceptions import (
    SafetyError,
    ConfirmationRequiredError,
    ToolError,
    ToolExecutionError,
    ToolNotFoundError,
    ToolTimeoutError,
    ToolValidationError,
)
from core.models import ToolCall, ToolResult, ExecutionTrace
from core.registry import ToolRegistry
from core.state import SystemState
from config import DANGEROUS_COMMANDS, REQUIRES_CONFIRMATION, AGENT_EXECUTION_TIMEOUT

logger = logging.getLogger(__name__)


class SafeExecutor:
    """
    Executes tools safely with validation, confirmation, and timeout.

    Usage:
        executor = SafeExecutor()
        result = executor.execute(ToolCall(tool_name="web_search", parameters={"query": "AI news"}))
    """

    def __init__(self, registry: ToolRegistry | None = None, state: SystemState | None = None) -> None:
        self.registry = registry or ToolRegistry()
        self.state = state or SystemState()

    def execute(
        self,
        tool_call: ToolCall,
        *,
        trace: ExecutionTrace | None = None,
        skip_confirmation: bool = False,
    ) -> ToolResult:
        """
        Execute a tool call with full safety pipeline.

        Pipeline:
            1. Look up tool in registry
            2. Validate parameters against schema
            3. Check if dangerous / requires confirmation
            4. Gate on pending confirmation if needed
            5. Execute with timeout
            6. Record result and trace
        """
        start_time = time.time()

        # 1. Lookup
        tool_func = self.registry.get_safe(tool_call.tool_name)
        if tool_func is None:
            return ToolResult(
                call_id=tool_call.call_id,
                tool_name=tool_call.tool_name,
                success=False,
                error_message=f"Tool '{tool_call.tool_name}' not found",
            )

        schema = self.registry.get_schema(tool_call.tool_name)

        # 2. Validate parameters
        try:
            validated_params = self._validate_parameters(schema, tool_call.parameters)
        except ToolValidationError as e:
            if trace:
                trace.add_event("error", f"Parameter validation failed: {e}")
            return ToolResult(
                call_id=tool_call.call_id,
                tool_name=tool_call.tool_name,
                success=False,
                error_message=str(e),
            )

        # 3. Safety checks
        if schema.dangerous and not skip_confirmation:
            danger_reason = self._check_danger(validated_params)
            if danger_reason:
                if trace:
                    trace.add_event("error", f"Blocked dangerous operation: {danger_reason}")
                return ToolResult(
                    call_id=tool_call.call_id,
                    tool_name=tool_call.tool_name,
                    success=False,
                    error_message=f"Blocked for safety: {danger_reason}",
                )

        # 4. Confirmation gate
        if schema.requires_confirmation and not skip_confirmation:
            action_desc = f"{tool_call.tool_name}({validated_params})"
            confirmation_id = f"confirm:{tool_call.call_id}"
            self.state.request_confirmation(
                action_id=confirmation_id,
                description=action_desc,
                agent_name=trace.agent_name if trace else "unknown",
                callback=functools.partial(self._execute_raw, tool_func, validated_params),
            )
            if trace:
                trace.add_event("decision", f"Confirmation required: {action_desc}")
            return ToolResult(
                call_id=tool_call.call_id,
                tool_name=tool_call.tool_name,
                success=False,
                error_message=f"Confirmation required: {action_desc}. Say 'yes' to confirm.",
            )

        # 5. Execute with trace
        if trace:
            trace.add_event("tool_call", f"Executing {tool_call.tool_name}", parameters=validated_params)

        try:
            result = self._execute_with_timeout(tool_func, validated_params)
            elapsed_ms = int((time.time() - start_time) * 1000)

            if trace:
                trace.add_event("tool_result", f"{tool_call.tool_name} succeeded", result=str(result)[:200])

            return ToolResult(
                call_id=tool_call.call_id,
                tool_name=tool_call.tool_name,
                success=True,
                result=result,
                execution_time_ms=elapsed_ms,
            )

        except Exception as e:
            elapsed_ms = int((time.time() - start_time) * 1000)
            error_msg = str(e)
            logger.error(f"Tool execution failed [{tool_call.tool_name}]: {error_msg}")

            if trace:
                trace.add_event("error", f"{tool_call.tool_name} failed: {error_msg}")

            return ToolResult(
                call_id=tool_call.call_id,
                tool_name=tool_call.tool_name,
                success=False,
                error_message=error_msg,
                execution_time_ms=elapsed_ms,
            )

    def execute_many(
        self,
        tool_calls: list[ToolCall],
        *,
        trace: ExecutionTrace | None = None,
    ) -> list[ToolResult]:
        """Execute multiple tool calls sequentially."""
        results: list[ToolResult] = []
        for tc in tool_calls:
            results.append(self.execute(tc, trace=trace))
        return results

    # -------------------------------------------------------------------------
    # INTERNAL
    # -------------------------------------------------------------------------

    def _validate_parameters(self, schema: Any, params: dict[str, Any]) -> dict[str, Any]:
        """Validate and coalesce parameters against the tool schema."""
        validated: dict[str, Any] = {}
        param_map = {p.name: p for p in schema.parameters}

        for spec in schema.parameters:
            name = spec.name
            if name in params:
                validated[name] = params[name]
            elif spec.default is not None:
                validated[name] = spec.default
            elif spec.required:
                raise ToolValidationError(schema.name, f"Missing required parameter: '{name}'")

        # Reject unknown parameters
        for key in params:
            if key not in param_map:
                raise ToolValidationError(schema.name, f"Unknown parameter: '{key}'")

        return validated

    def _check_danger(self, params: dict[str, Any]) -> str | None:
        """Check if parameters contain dangerous patterns. Returns reason or None."""
        param_str = json.dumps(params).lower()
        for pattern in DANGEROUS_COMMANDS:
            if pattern.lower() in param_str:
                return f"Dangerous pattern detected: '{pattern}'"
        return None

    def _execute_raw(self, func: Callable[..., Any], params: dict[str, Any]) -> Any:
        """Direct execution without safety wrapper (used by confirmation callbacks)."""
        return func(**params)

    def _execute_with_timeout(self, func: Callable[..., Any], params: dict[str, Any]) -> Any:
        """Execute a function with a timeout."""
        result_container: list[Any] = []
        exception_container: list[Exception] = []

        def target() -> None:
            try:
                result_container.append(func(**params))
            except Exception as e:
                exception_container.append(e)

        thread = threading.Thread(target=target)
        thread.start()
        thread.join(timeout=AGENT_EXECUTION_TIMEOUT)

        if thread.is_alive():
            # Cannot truly kill threads in Python, but we can detach
            raise ToolTimeoutError(func.__name__, AGENT_EXECUTION_TIMEOUT)

        if exception_container:
            raise exception_container[0]

        return result_container[0] if result_container else None
