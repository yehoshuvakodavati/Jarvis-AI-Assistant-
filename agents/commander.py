"""
Commander Agent for Jarvis Multi-Agent AI Operating System.

The Commander is the central entry point. It:
1. Receives all user requests
2. Uses LLM reasoning to determine routing
3. Retrieves relevant memory context
4. Dispatches to appropriate specialized agents
5. Aggregates and returns results
6. Records routing decisions for learning

No hardcoded routing. All decisions are reasoning-based via LLM.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any, Dict, List, Optional

from config import MODEL_COMMANDER, TEMP_STRUCTURED
from core.models import (
    AgentResponse,
    AgentTask,
    ExecutionTrace,
    Message,
    RoutingDecision,
)
from core.registry import AgentRegistry
from core.state import SystemState
from agents.base import BaseAgent
from framework.routing import (
    classify_trivial,
    is_math_expression,
    is_confirmation_yes,
    is_confirmation_no,
)

logger = logging.getLogger(__name__)


class CommanderAgent(BaseAgent):
    """
    Central router and dispatcher for all user requests.

    The Commander does not perform work itself (except for simple
    conversational responses). Instead, it reasons about which agents
    should handle each request and coordinates their execution.
    """

    name = "commander"
    description = "Central entry point that routes user requests to specialized agents using LLM-based reasoning"
    capabilities = ["routing", "coordination", "conversation", "general"]
    default_model = MODEL_COMMANDER

    def __init__(self) -> None:
        super().__init__()
        self.registry = AgentRegistry()
        self.max_delegation_depth = 3

    # -------------------------------------------------------------------------
    # MAIN ENTRY POINT
    # -------------------------------------------------------------------------

    def process_user_input(self, user_input: str, session_id: str = "default") -> AgentResponse:
        """
        Main entry point for processing user input.

        Args:
            user_input: The raw user message.
            session_id: Session identifier for context tracking.

        Returns:
            AgentResponse with the final result.
        """
        # Save conversation
        self.memory.save_conversation(session_id, "user", user_input)

        # Create task for the commander
        task = AgentTask(
            description=user_input,
            task_type="routing",
            context={"session_id": session_id, "user_input": user_input},
        )

        return self.execute(task)

    # -------------------------------------------------------------------------
    # TASK EXECUTION
    # -------------------------------------------------------------------------

    def execute_task(self, task: AgentTask, trace: ExecutionTrace | None = None) -> AgentResponse:
        """
        Execute the routing logic for a user request.
        """
        user_input = task.context.get("user_input", task.description)
        session_id = task.context.get("session_id", "default")

        # Check for pending confirmations first
        if self._handle_pending_confirmation(user_input):
            return self._create_response(task, "Confirmation processed.", success=True)

        # Step 1: Quick heuristics for trivial cases
        trivial_response = self._handle_trivial(user_input)
        if trivial_response:
            self.memory.save_conversation(session_id, "assistant", trivial_response)
            return self._create_response(task, trivial_response, success=True)

        # Step 2: LLM-based routing decision
        routing = self._route_via_llm(user_input, trace)

        if trace:
            trace.add_event("decision", f"Routing: {routing.primary_agent} (confidence: {routing.confidence:.2f})")

        # Step 3: Retrieve memory context if needed
        memory_context = ""
        if routing.needs_memory_context:
            memory_context = self.memory.build_context_for_prompt(user_input, max_items=5)
            if trace:
                trace.add_event("decision", f"Retrieved {len(memory_context)} chars of memory context")

        # Step 4: Dispatch to primary agent
        primary_agent = self.registry.get_safe(routing.primary_agent)

        if primary_agent is None:
            error_msg = f"Agent '{routing.primary_agent}' is not available. Available: {self.registry.list_agents()}"
            if trace:
                trace.add_event("error", error_msg)
            return self._create_response(task, error_msg, success=False)

        # Step 5: Create and dispatch the actual work task
        work_task = AgentTask(
            description=user_input,
            task_type=routing.intent,
            context={
                "session_id": session_id,
                "user_input": user_input,
                "memory_context": memory_context,
                "routing_decision": routing.model_dump(),
                "supporting_agents": routing.supporting_agents,
            },
            parent_task_id=task.task_id,
            assigned_agent=routing.primary_agent,
        )

        # Execute with the primary agent
        agent_response = primary_agent.execute(work_task)

        # Step 6: Optionally dispatch supporting agents
        if routing.supporting_agents and agent_response.success:
            for support_name in routing.supporting_agents:
                support_agent = self.registry.get_safe(support_name)
                if support_agent:
                    support_task = AgentTask(
                        description=f"Support task for: {user_input}",
                        task_type="support",
                        context={
                            "session_id": session_id,
                            "original_request": user_input,
                            "primary_result": agent_response.response,
                            "memory_context": memory_context,
                        },
                        parent_task_id=task.task_id,
                        assigned_agent=support_name,
                    )
                    support_response = support_agent.execute(support_task)
                    # Merge support data into primary response
                    agent_response.data[f"{support_name}_result"] = support_response.model_dump()

        # Step 7: Log routing decision for learning
        self.memory.store.log_routing(
            request=user_input,
            primary_agent=routing.primary_agent,
            intent=routing.intent,
            confidence=routing.confidence,
            metadata={
                "supporting_agents": routing.supporting_agents,
                "decomposition": routing.decomposition,
                "reasoning": routing.reasoning,
            },
        )

        # Save assistant response to conversation
        self.memory.save_conversation(session_id, "assistant", agent_response.response, agent_name=routing.primary_agent)

        return agent_response

    # -------------------------------------------------------------------------
    # ROUTING LOGIC
    # -------------------------------------------------------------------------

    def _route_via_llm(self, user_input: str, trace: ExecutionTrace | None = None) -> RoutingDecision:
        """
        Use the LLM to make a routing decision.

        Constructs a prompt describing all available agents and their
capabilities, then asks the LLM to decide the best routing.
        """
        agent_descriptions = self.registry.describe_for_llm()
        tool_descriptions = self.executor.registry.describe_for_llm()

        prompt = f"""You are the Commander Agent of Jarvis, a Multi-Agent AI Operating System.
Your sole responsibility is to analyze user requests and decide which specialized agent should handle them.

{agent_descriptions}

{tool_descriptions}

User request: "{user_input}"

Analyze this request carefully:
1. What is the primary intent? (e.g., search, plan, code, system_control, file_operation, memory_query)
2. Which agent is BEST suited to handle this primarily?
3. Should any supporting agents assist? (e.g., memory_agent retrieving context first)
4. Does this need to be broken into multiple steps?
5. Would accessing the user's memory/past conversations help answer this better?

Respond ONLY with a valid JSON object (no markdown, no extra text):
{{
  "intent": "brief description of the detected intent",
  "primary_agent": "exact_agent_name",
  "supporting_agents": ["agent_name_if_any"],
  "decomposition": [{{"step": 1, "description": "what to do", "agent": "agent_name"}}],
  "needs_memory_context": true_or_false,
  "confidence": 0.0_to_1.0,
  "reasoning": "1-2 sentence explanation"
}}

Be decisive. Choose ONE primary agent. Confidence should reflect your certainty."""

        try:
            # Use the PUBLIC structured-generation API so parsing is handled
            # inside the LLM client. Accessing _safe_json_parse through the
            # instance couples us to a private method and breaks any mock or
            # alternate LLM implementation.
            parsed = self.llm.generate_structured(
                prompt,
                model=self.default_model,
                temperature=TEMP_STRUCTURED,
            )

            if not isinstance(parsed, dict):
                logger.warning(f"LLM routing returned non-dict: {parsed}")
                return self._fallback_routing(user_input)

            # Normalize and validate
            primary = parsed.get("primary_agent", "executor")
            available = self.registry.list_agents()

            # Map common misnames to correct agent names
            name_mapping = {
                "research": "researcher",
                "researcher_agent": "researcher",
                "plan": "planner",
                "planner_agent": "planner",
                "memory": "memory_agent",
                "memories": "memory_agent",
                "code": "coder",
                "coding": "coder",
                "coder_agent": "coder",
                "execute": "executor",
                "execution": "executor",
                "executor_agent": "executor",
                "browse": "browser",
                "browsing": "browser",
                "browser_agent": "browser",
                "file": "file_agent",
                "files": "file_agent",
                "file_agent": "file_agent",
                "learn": "learner",
                "learning": "learner",
                "learner_agent": "learner",
                "commander": "commander",
            }
            primary_mapped = name_mapping.get(primary.lower(), primary)

            if primary_mapped not in available:
                logger.warning(f"LLM suggested unknown agent '{primary}', falling back")
                return self._fallback_routing(user_input)

            # Parse supporting agents
            supporting = []
            for s in parsed.get("supporting_agents", []):
                mapped = name_mapping.get(str(s).lower(), str(s))
                if mapped in available and mapped != primary_mapped:
                    supporting.append(mapped)

            decomposition = parsed.get("decomposition", [])
            if not isinstance(decomposition, list):
                decomposition = []

            confidence = float(parsed.get("confidence", 0.5))

            return RoutingDecision(
                intent=parsed.get("intent", "general"),
                primary_agent=primary_mapped,
                supporting_agents=supporting[:2],  # Max 2 supporting agents
                decomposition=decomposition,
                needs_memory_context=bool(parsed.get("needs_memory_context", True)),
                confidence=confidence,
                reasoning=parsed.get("reasoning", ""),
            )

        except Exception as e:
            logger.error(f"LLM routing failed: {e}")
            return self._fallback_routing(user_input)

    def _fallback_routing(self, user_input: str) -> RoutingDecision:
        """
        Fallback routing when LLM fails or returns invalid output.
        Uses simple keyword heuristics as a safety net.

        Order matters: most-specific patterns are checked FIRST so they
        are not shadowed by broader keywords (e.g. "open this url" must
        hit browser, not executor; "find all pdf" must hit file_agent,
        not researcher).
        """
        lower = user_input.lower()

        # 1. Planning (most specific verbs)
        if any(kw in lower for kw in ("plan", "schedule", "roadmap", "study for", "timeline", "prepare for")):
            return RoutingDecision(intent="planning", primary_agent="planner", confidence=0.6, reasoning="Keyword match: planning")
        # 2. Browsing — "url"/"website"/"browse" must beat the generic "open"
        if any(kw in lower for kw in ("website", "browse", "go to", "url", ".com", ".org", ".net")):
            return RoutingDecision(intent="browsing", primary_agent="browser", confidence=0.6, reasoning="Keyword match: browsing")
        # 3. File operations — "pdf"/"document"/"folder" must beat "find"
        if any(kw in lower for kw in ("pdf", "file", "folder", "document", "directory", "list files", "find files")):
            return RoutingDecision(intent="file_operation", primary_agent="file_agent", confidence=0.6, reasoning="Keyword match: file operation")
        # 4. Memory — "remember"/"preference" must beat generic "save"
        if any(kw in lower for kw in ("remember", "recall", "preference", "what do i", "my preference", "my notes")):
            return RoutingDecision(intent="memory", primary_agent="memory_agent", confidence=0.6, reasoning="Keyword match: memory")
        # 5. Coding
        if any(kw in lower for kw in ("code", "python", "java", "javascript", "function", "algorithm", "debug")):
            return RoutingDecision(intent="coding", primary_agent="coder", confidence=0.6, reasoning="Keyword match: coding")
        # 6. Research / general knowledge
        if any(kw in lower for kw in ("search", "find", "look up", "what is", "who is", "latest", "news", "current")):
            return RoutingDecision(intent="research", primary_agent="researcher", confidence=0.6, reasoning="Keyword match: research")
        # 7. System execution — "open"/"launch" only after the more-specific intents above
        if any(kw in lower for kw in ("open", "launch", "start", "shutdown", "restart", "sleep", "lock")):
            return RoutingDecision(intent="execution", primary_agent="executor", confidence=0.6, reasoning="Keyword match: system execution")
        # 8. Note management (generic "save"/"note")
        if any(kw in lower for kw in ("note", "save", "memory")):
            return RoutingDecision(intent="memory", primary_agent="memory_agent", confidence=0.6, reasoning="Keyword match: memory")

        return RoutingDecision(intent="general", primary_agent="executor", confidence=0.5, reasoning="Default fallback")

    # -------------------------------------------------------------------------
    # TRIVIAL HANDLING
    # -------------------------------------------------------------------------

    def _handle_trivial(self, user_input: str) -> str | None:
        """
        Handle trivial inputs quickly without an LLM call, using the shared
        classifiers in framework.routing. Returns a response string for
        trivial cases, None otherwise.
        """
        kind = classify_trivial(user_input)
        if kind == "greeting":
            return "Greetings, Commander. Jarvis is online and ready to assist you."
        if kind == "wellbeing":
            return "All systems operational, Commander. Ready to execute your commands."
        if kind == "identity":
            return (
                "I am Jarvis, your Multi-Agent AI Operating System. "
                "I coordinate specialized agents to research, plan, code, manage files, "
                "control your system, and learn from our interactions to serve you better."
            )
        if kind == "thanks":
            return "You're welcome, Commander. Always at your service."
        if kind == "farewell":
            return "Standing by, Commander. Simply address me when you need assistance."

        # Pure math expression — evaluate directly (single source of truth)
        if is_math_expression(user_input):
            from framework.tools import math_evaluate
            result = math_evaluate(user_input)
            return f"Commander, the result is {result}"

        return None

    # -------------------------------------------------------------------------
    # CONFIRMATION HANDLING
    # -------------------------------------------------------------------------

    def _handle_pending_confirmation(self, user_input: str) -> bool:
        """
        Check if the user is responding to a pending confirmation.

        Returns True if a confirmation was processed.
        """
        if is_confirmation_yes(user_input):
            pending = self.state.get_all_pending_confirmations()
            if pending:
                # Confirm the most recent pending action
                pc = pending[-1]
                try:
                    self.state.confirm_action(pc.action_id)
                    return True
                except Exception as e:
                    logger.error(f"Confirmation execution failed: {e}")
                    return True  # Still considered handled

        if is_confirmation_no(user_input):
            pending = self.state.get_all_pending_confirmations()
            if pending:
                for pc in pending:
                    self.state.cancel_action(pc.action_id)
                return True

        return False

    # -------------------------------------------------------------------------
    # UTILITIES
    # -------------------------------------------------------------------------

    def _create_response(self, task: AgentTask, response_text: str, success: bool = True) -> AgentResponse:
        """Create a standardized AgentResponse."""
        return AgentResponse(
            agent_name=self.name,
            task_id=task.task_id,
            success=success,
            response=response_text,
        )
