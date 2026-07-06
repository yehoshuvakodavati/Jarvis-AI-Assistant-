"""
Executor Agent for Jarvis Multi-Agent AI Operating System.

Handles system-level operations via LLM-based intent parsing (NOT keyword
matching). The agent asks the LLM to classify the request into one of its
operations and extract the needed parameters, then delegates to the
appropriate tool through the SafeExecutor.

Operations (decided by reasoning, not hardcoded):
- shutdown / restart / sleep / lock  (power controls; sleep+ require confirmation)
- open_app
- open_url
- open_settings
- math
- general (fallback)

The Executor never runs subprocess directly — it calls registered tools.
"""

from __future__ import annotations

import logging
from typing import Any, Dict

from config import MODEL_CONVERSATIONAL
from core.models import AgentResponse, AgentTask, ExecutionTrace
from agents.base import BaseAgent
from framework.routing import extract_url, is_math_expression, parse_intent_via_llm

logger = logging.getLogger(__name__)

# Valid operations the LLM may choose. Order matters: last is the fallback.
_VALID_OPS = [
    "shutdown", "restart", "sleep", "lock",
    "open_app", "open_url", "open_settings",
    "math",
    "general",
]


class ExecutorAgent(BaseAgent):
    """
    Executes system operations via reasoning-based intent parsing.

    Capabilities:
    - Open applications and websites
    - Control system settings
    - Power management (with safety confirmations enforced by tool schemas)
    - General command execution
    """

    name = "executor"
    description = "Opens apps, controls system settings, and manages power states with safety checks"
    capabilities = ["execution", "system_control", "app_launch", "settings", "power"]
    default_model = MODEL_CONVERSATIONAL

    def execute_task(self, task: AgentTask, trace: ExecutionTrace | None = None) -> AgentResponse:
        """Execute a system-level task via LLM intent parsing + tool delegation."""
        user_input = task.context.get("user_input", task.description)

        if trace:
            trace.add_event("decision", "ExecutorAgent parsing intent via LLM")

        # ---- Fast path: unambiguous detections with NO LLM call ----
        # These are pure, deterministic, and save a round-trip for clear cases.
        # They are NOT "hardcoded routing" — they're well-defined input shapes,
        # and the LLM path below remains the general decision-maker.

        # Pure math expression → math tool
        if is_math_expression(user_input):
            if trace:
                trace.add_event("decision", "Fast path: pure math expression")
            return self._execute_tool(task, "math_evaluate", {"expression": user_input}, trace)

        # Bare URL → open it
        url = extract_url(user_input)
        if url and user_input.strip().lower().startswith(("open", "go to", "visit", "browse")):
            if trace:
                trace.add_event("decision", f"Fast path: URL detected ({url})")
            return self._execute_tool(task, "system_open_url", {"url": url}, trace)

        # ---- Reasoning path: LLM classifies the operation + extracts params ----
        prompt = self._build_intent_prompt(user_input)
        op, params = parse_intent_via_llm(
            self.llm, prompt, _VALID_OPS, model=self.default_model
        )

        if trace:
            trace.add_event("decision", f"LLM selected operation: {op} with {params}")

        # ---- Delegate to the appropriate tool ----
        return self._dispatch(task, op, params, trace)

    # -------------------------------------------------------------------------
    # INTENT PROMPT (reasoning, not keyword matching)
    # -------------------------------------------------------------------------

    def _build_intent_prompt(self, user_input: str) -> str:
        """Build the prompt asking the LLM to classify + extract params."""
        return f"""You are the Executor Agent of Jarvis. Classify the user's request into exactly one operation and extract its parameters.

Valid operations:
- "shutdown"   : power off the computer
- "restart"    : reboot the computer
- "sleep"      : put the computer to sleep
- "lock"       : lock the workstation
- "open_app"   : launch an application. params: {{"app_name": "notepad|calculator|cmd|terminal|powershell|explorer"}}
- "open_url"   : open a website. params: {{"url": "full URL"}}
- "open_settings": open Windows settings. params: {{"setting": "home|display|network|bluetooth|privacy|keyboard|wifi|storage"}}
- "math"       : evaluate a math expression. params: {{"expression": "the expression"}}
- "general"    : none of the above (fallback)

User request: "{user_input}"

Rules:
- If the request names a known app, set app_name to that app.
- If the request contains a URL or website name (youtube, google, github, stackoverflow, gmail), use open_url with the full URL.
- For math, set expression to the math portion only.
- Respond ONLY with JSON: {{"intent": "<one of the operations>", "parameters": {{...}}}}"""

    # -------------------------------------------------------------------------
    # DISPATCH
    # -------------------------------------------------------------------------

    def _dispatch(self, task: AgentTask, op: str, params: Dict[str, Any], trace: ExecutionTrace | None) -> AgentResponse:
        """Map an operation to its tool and execute via the safe executor."""
        tool_map = {
            "shutdown": ("system_shutdown", {}),
            "restart": ("system_restart", {}),
            "sleep": ("system_sleep", {}),
            "lock": ("system_lock", {}),
            "open_app": ("system_open_app", {"app_name": params.get("app_name", "explorer")}),
            "open_url": ("system_open_url", {"url": params.get("url", "https://www.google.com")}),
            "open_settings": ("system_open_settings", {"setting": params.get("setting", "home")}),
            "math": ("math_evaluate", {"expression": params.get("expression", task.context.get("user_input", ""))}),
        }

        if op in tool_map:
            tool_name, tool_params = tool_map[op]
            return self._execute_tool(task, tool_name, tool_params, trace)

        # Fallback
        return self._handle_general_execution(task, trace)

    # -------------------------------------------------------------------------
    # TOOL EXECUTION (unchanged from prior implementation)
    # -------------------------------------------------------------------------

    def _execute_tool(
        self,
        task: AgentTask,
        tool_name: str,
        parameters: Dict[str, Any],
        trace: ExecutionTrace | None = None,
    ) -> AgentResponse:
        """Execute a system tool through the SafeExecutor and format the response."""
        if trace:
            trace.add_event("tool_call", f"Executing {tool_name}")

        result = self.call_tool(tool_name, **parameters)

        if trace:
            trace.add_event("tool_result", f"{tool_name} result: {result.success}")

        if result.success:
            return AgentResponse(
                agent_name=self.name,
                task_id=task.task_id,
                success=True,
                response=str(result.result) if result.result else f"Executed {tool_name}",
            )

        # Confirmation-required is a controlled "failure" — surface the message
        if "confirmation required" in (result.error_message or "").lower():
            return AgentResponse(
                agent_name=self.name,
                task_id=task.task_id,
                success=False,
                response=result.error_message or "This action requires your confirmation.",
            )
        return AgentResponse(
            agent_name=self.name,
            task_id=task.task_id,
            success=False,
            response=f"Failed to execute: {result.error_message}",
        )

    def _handle_general_execution(self, task: AgentTask, trace: ExecutionTrace | None = None) -> AgentResponse:
        """Fallback when the LLM can't classify the request."""
        response = (
            "I can help you with:\n"
            "- Open apps: Notepad, Calculator, CMD, Terminal\n"
            "- Open websites: YouTube, Google, GitHub, etc.\n"
            "- System: Settings, Display, Network, Bluetooth\n"
            "- Power: Lock, Sleep, Shutdown, Restart (with confirmation)\n"
            "\nWhat would you like to do?"
        )
        return AgentResponse(
            agent_name=self.name,
            task_id=task.task_id,
            success=True,
            response=response,
        )
