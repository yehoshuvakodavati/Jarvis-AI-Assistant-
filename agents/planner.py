"""
Planner Agent for Jarvis Multi-Agent AI Operating System.

Receives GOALS (not commands) and produces a structured plan:
  - Roadmap   : ordered PlanSteps with assigned agents
  - Milestones: named checkpoints grouping steps, with target progress
  - Subtasks  : per-step tasks persisted to the DB and (optionally) dispatched
                to the assigned specialist agent
  - Priorities: LLM-derived 1-5 priority per step

Dispatch is OPT-IN: by default the Planner returns the plan for display
(passive mode). When ``task.context["dispatch"]`` is True, it executes the
subtasks in dependency order against the registered agents and returns a
combined report. This keeps the chat flow fast and tests hermetic while
enabling autonomous multi-agent execution on demand.

Example:
    Goal: "I want to prepare for a Java interview."
    -> Roadmap of research + practice + review steps
    -> Milestones: "Core Java", "Frameworks", "Mock Interviews"
    -> Each step dispatched to researcher / coder / executor as assigned
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from config import MODEL_PLANNER
from core.models import (
    AgentResponse,
    AgentTask,
    AgentTask as _AgentTask,  # noqa: F401  (kept for clarity)
    ExecutionTrace,
    GoalStatus,
    Milestone,
    Plan,
    PlanStep,
    TaskStatus,
)
from agents.base import BaseAgent
from framework.routing import parse_intent_via_llm

logger = logging.getLogger(__name__)


class PlannerAgent(BaseAgent):
    """
    Creates plans, roadmaps, milestones, and dispatches subtasks to agents.

    Capabilities:
    - Goal decomposition into a prioritized roadmap
    - Milestone creation with target progress
    - Subtask generation persisted to the DB
    - Optional autonomous dispatch of subtasks to assigned agents
    """

    name = "planner"
    description = "Creates structured plans, roadmaps, milestones, and dispatches subtasks to agents"
    capabilities = ["planning", "scheduling", "roadmap", "goal_setting", "study_plan"]
    default_model = MODEL_PLANNER

    # Agents the Planner is allowed to dispatch to (safety allow-list).
    DISPATCHABLE_AGENTS = (
        "researcher", "coder", "executor", "browser", "file_agent", "memory_agent",
    )

    def execute_task(self, task: AgentTask, trace: ExecutionTrace | None = None) -> AgentResponse:
        """
        Execute a planning task.

        Flow:
            1. Detect plan type (LLM)
            2. Generate roadmap with milestones + priorities (LLM)
            3. Store goal + subtasks in memory
            4. If dispatch requested, execute subtasks in dependency order
            5. Return the formatted plan (+ dispatch report if any)
        """
        user_input = task.context.get("user_input", task.description)
        memory_context = task.context.get("memory_context", "")
        dispatch = bool(task.context.get("dispatch", False))

        if trace:
            trace.add_event("decision", "PlannerAgent analyzing goal")

        # 1. Plan type
        plan_type = self._detect_plan_type(user_input)
        if trace:
            trace.add_event("decision", f"Detected plan type: {plan_type}")

        # 2. Generate plan (roadmap + milestones + priorities)
        plan = self._generate_plan(user_input, plan_type, memory_context, trace)

        # 3. Persist
        goal_id = self._store_plan(plan, user_input)
        self._create_subtasks(plan, goal_id)

        if trace:
            trace.add_event("decision", f"Plan stored: {len(plan.steps)} steps, {len(plan.milestones)} milestones")

        # 4. Optional dispatch
        dispatch_report = ""
        if dispatch:
            dispatch_report = self._dispatch_subtasks(plan, task, trace)

        # 5. Format response
        response_text = self._format_plan_response(plan, goal_id)
        if dispatch_report:
            response_text += "\n\n" + dispatch_report

        return AgentResponse(
            agent_name=self.name,
            task_id=task.task_id,
            success=True,
            response=response_text,
            data={
                "plan": plan.model_dump(),
                "goal_id": goal_id,
                "dispatched": dispatch,
            },
        )

    # -------------------------------------------------------------------------
    # PLAN TYPE DETECTION (unchanged signature — kept for existing tests)
    # -------------------------------------------------------------------------

    def _detect_plan_type(self, user_input: str) -> str:
        """Detect what kind of plan the user wants via LLM (falls back to general)."""
        valid_types = ["study_plan", "project_plan", "schedule", "travel_plan", "general_plan"]
        prompt = (
            "Classify the user's planning request into one plan type.\n\n"
            "Types:\n"
            '- "study_plan"    : interview, exam, test, certification, study prep\n'
            '- "project_plan"  : build, develop, create a project\n'
            '- "schedule"      : daily/weekly routine or schedule\n'
            '- "travel_plan"   : trip, travel, vacation\n'
            '- "general_plan"  : none of the above (fallback)\n\n'
            f'User request: "{user_input}"\n\n'
            'Respond ONLY with JSON: {"intent": "<type>", "parameters": {}}'
        )
        plan_type, _ = parse_intent_via_llm(
            self.llm, prompt, valid_types, model=self.default_model
        )
        return plan_type

    # -------------------------------------------------------------------------
    # PLAN GENERATION (roadmap + milestones + priorities)
    # -------------------------------------------------------------------------

    def _generate_plan(
        self,
        user_input: str,
        plan_type: str,
        memory_context: str,
        trace: ExecutionTrace | None = None,
    ) -> Plan:
        """Use LLM to generate a structured plan with milestones and priorities."""

        system_prompt = """You are an expert planner. Create detailed, actionable plans.
Your output must be valid JSON only — no markdown, no prose."""

        prompt = f"""Create a detailed {plan_type} for the following goal:

"{user_input}"

{memory_context}

Produce a roadmap with clear steps AND milestones. Requirements:
- Each step has: description, estimated_duration_minutes, dependencies (list of step numbers it needs done first), assigned_agent (one of: researcher, coder, executor, browser, file_agent), priority (1=critical..5=low, integer).
- Group steps into 2-4 milestones. Each milestone has: title, description, step_numbers (the steps it covers), target_progress (0.0-1.0 of total plan).

Respond with ONLY a JSON object:
{{
  "title": "Plan title",
  "description": "Brief overview",
  "goal": "The main objective",
  "steps": [
    {{
      "step_number": 1,
      "description": "What to do",
      "estimated_duration_minutes": 60,
      "dependencies": [],
      "assigned_agent": "researcher",
      "priority": 1
    }}
  ],
  "milestones": [
    {{
      "title": "Milestone title",
      "description": "What this milestone represents",
      "step_numbers": [1, 2],
      "target_progress": 0.5
    }}
  ],
  "estimated_completion_days": 10
}}

Make the plan realistic and actionable. Every step must have a priority."""

        try:
            parsed = self.call_llm_structured(
                prompt,
                system=system_prompt,
                model=self.default_model,
                temperature=0.4,
            )

            if not isinstance(parsed, dict):
                raise ValueError(f"Expected dict, got {type(parsed)}")

            steps = self._parse_steps(parsed.get("steps", []))
            milestones = self._parse_milestones(parsed.get("milestones", []), steps)

            estimated_days = parsed.get("estimated_completion_days", 7)
            # Clamp absurd estimates
            try:
                estimated_days = max(1, min(int(estimated_days), 365))
            except (TypeError, ValueError):
                estimated_days = 7
            completion = datetime.utcnow() + timedelta(days=estimated_days)

            return Plan(
                title=parsed.get("title", "Untitled Plan"),
                description=parsed.get("description", ""),
                goal=parsed.get("goal", user_input),
                steps=steps,
                milestones=milestones,
                estimated_completion=completion,
            )

        except Exception as e:
            logger.error(f"Plan generation failed: {e}")
            # Minimal fallback plan — still valid, no milestones
            return Plan(
                title="General Plan",
                description=f"Plan for: {user_input}",
                goal=user_input,
                steps=[PlanStep(step_number=1, description=user_input)],
            )

    def _parse_steps(self, steps_data: List[Any]) -> List[PlanStep]:
        """Parse raw step dicts into PlanStep models with safe defaults."""
        steps: List[PlanStep] = []
        for i, s in enumerate(steps_data):
            if not isinstance(s, dict):
                continue
            # Coerce priority safely (1-5, default 3)
            try:
                priority = int(s.get("priority", 3))
                priority = max(1, min(5, priority))
            except (TypeError, ValueError):
                priority = 3
            steps.append(PlanStep(
                step_number=s.get("step_number", i + 1),
                description=s.get("description", f"Step {i + 1}"),
                assigned_agent=s.get("assigned_agent"),
                estimated_duration_minutes=s.get("estimated_duration_minutes"),
                dependencies=s.get("dependencies", []) or [],
                priority=priority,
            ))
        return steps

    def _parse_milestones(self, milestones_data: List[Any], steps: List[PlanStep]) -> List[Milestone]:
        """Parse raw milestone dicts into Milestone models, linking to steps."""
        milestones: List[Milestone] = []
        if not isinstance(milestones_data, list):
            return milestones
        for m in milestones_data:
            if not isinstance(m, dict):
                continue
            try:
                target = float(m.get("target_progress", 0.0))
                target = max(0.0, min(1.0, target))
            except (TypeError, ValueError):
                target = 0.0
            step_numbers = m.get("step_numbers", []) or []
            if not isinstance(step_numbers, list):
                step_numbers = []
            milestone = Milestone(
                title=m.get("title", f"Milestone {len(milestones) + 1}"),
                description=m.get("description"),
                step_numbers=[int(sn) for sn in step_numbers if isinstance(sn, (int, float))],
                target_progress=target,
            )
            # Link steps to this milestone
            for step in steps:
                if step.step_number in milestone.step_numbers:
                    step.milestone_id = milestone.milestone_id
            milestones.append(milestone)
        return milestones

    # -------------------------------------------------------------------------
    # PERSISTENCE
    # -------------------------------------------------------------------------

    def _store_plan(self, plan: Plan, user_input: str) -> str:
        """Store the plan as a goal + memory entry. Returns the goal_id."""
        goal_id = f"goal_{uuid.uuid4().hex[:8]}"

        self.memory.create_goal(
            goal_id=goal_id,
            title=plan.title,
            description=plan.description,
            status=GoalStatus.ACTIVE,
            due_date=plan.estimated_completion,
            metadata={
                "original_request": user_input,
                "plan_id": plan.plan_id,
                "step_count": len(plan.steps),
                "milestone_count": len(plan.milestones),
            },
        )

        plan_summary = (
            f"Plan created: {plan.title}\n"
            f"Goal: {plan.goal}\n"
            f"Steps: {len(plan.steps)}\n"
            f"Milestones: {len(plan.milestones)}"
        )
        self.memory.store_memory(
            content=plan_summary,
            memory_type="goal",
            category="planning",
            importance=0.8,
            source="planner_agent",
            metadata={"goal_id": goal_id, "plan_id": plan.plan_id},
        )

        return goal_id

    def _create_subtasks(self, plan: Plan, goal_id: str) -> None:
        """Persist each plan step as a DB task with its LLM-derived priority."""
        for step in plan.steps:
            # Map step.priority (1=critical..5=low) to DB priority (1=high..5=low)
            db_priority = step.priority
            self.memory.create_task(
                task_id=f"{goal_id}_step_{step.step_number}",
                title=step.description[:100],
                description=step.description,
                assigned_agent=step.assigned_agent or "executor",
                priority=db_priority,
                metadata={
                    "plan_id": plan.plan_id,
                    "step_number": step.step_number,
                    "milestone_id": step.milestone_id,
                    "dependencies": step.dependencies,
                },
            )

    # -------------------------------------------------------------------------
    # SUBTASK DISPATCH (opt-in, dependency-aware)
    # -------------------------------------------------------------------------

    def _dispatch_subtasks(
        self, plan: Plan, parent_task: AgentTask, trace: ExecutionTrace | None = None
    ) -> str:
        """
        Execute plan steps in dependency order by dispatching each to its
        assigned agent. Returns a human-readable report.

        Safety:
        - Only DISPATCHABLE_AGENTS are invoked (never 'commander'/'learner').
        - Each dispatch is isolated: one failure doesn't abort the plan.
        - Dependencies are honored: a step runs only after its deps complete.
        - A step whose assigned agent is unknown/None is skipped (reported).
        """
        session_id = parent_task.context.get("session_id", "default")
        completed: set[int] = set()
        results: List[str] = []
        remaining = list(plan.steps)
        # Allow multiple passes for dependency resolution
        max_passes = len(plan.steps) + 1

        for _ in range(max_passes):
            if not remaining:
                break
            progressed = False
            for step in list(remaining):
                # Check dependencies satisfied
                if not all(dep in completed for dep in step.dependencies):
                    continue
                remaining.remove(step)
                progressed = True
                outcome = self._dispatch_one(step, parent_task, session_id, trace)
                results.append(f"Step {step.step_number}: {outcome}")
                # Mark completed regardless of success — deps only need it "done"
                completed.add(step.step_number)
                step.status = TaskStatus.COMPLETED
            if not progressed:
                # Circular/unsatisfiable deps — report and stop
                for step in remaining:
                    results.append(f"Step {step.step_number}: SKIPPED (unmet dependencies {step.dependencies})")
                    step.status = TaskStatus.CANCELLED
                break

        header = "**Subtask Dispatch Report**"
        return header + "\n" + "\n".join(results)

    def _dispatch_one(
        self,
        step: PlanStep,
        parent_task: AgentTask,
        session_id: str,
        trace: ExecutionTrace | None,
    ) -> str:
        """Dispatch a single step to its assigned agent. Returns a status line."""
        agent_name = step.assigned_agent
        if not agent_name or agent_name not in self.DISPATCHABLE_AGENTS:
            return f"skipped (no dispatchable agent; got '{agent_name}')"

        # Use the shared AgentRegistry singleton (BaseAgent doesn't hold a ref).
        from core.registry import AgentRegistry
        agent = AgentRegistry().get_safe(agent_name)
        if agent is None:
            return f"skipped (agent '{agent_name}' not registered)"

        subtask = AgentTask(
            description=step.description,
            task_type="subtask",
            context={
                "session_id": session_id,
                "user_input": step.description,
                "memory_context": "",
                "parent_plan_step": step.step_number,
            },
            parent_task_id=parent_task.task_id,
            assigned_agent=agent_name,
            priority=step.priority,
        )

        if trace:
            trace.add_event("tool_call", f"Dispatching step {step.step_number} → {agent_name}")

        try:
            resp = agent.execute(subtask)
            summary = (resp.response or "").strip().replace("\n", " ")[:120]
            step.result_summary = summary
            return f"done via {agent_name} — {summary}"
        except Exception as e:
            logger.error(f"Subtask dispatch failed (step {step.step_number} → {agent_name}): {e}")
            step.status = TaskStatus.FAILED
            return f"FAILED via {agent_name} — {e}"

    # -------------------------------------------------------------------------
    # RESPONSE FORMATTING
    # -------------------------------------------------------------------------

    def _format_plan_response(self, plan: Plan, goal_id: str) -> str:
        """Format a plan (with milestones + priorities) for human-readable output."""
        lines = [
            f"📋 **{plan.title}**",
            "",
            f"🎯 Goal: {plan.goal}",
            "",
        ]

        # Milestones section
        if plan.milestones:
            lines.append("**Milestones:**")
            for ms in plan.milestones:
                pct = int(ms.target_progress * 100)
                steps_str = ", ".join(str(n) for n in ms.step_numbers) or "—"
                lines.append(f"  • {ms.title} (steps {steps_str}, target {pct}% progress)")
            lines.append("")

        # Roadmap section
        lines.append("**Roadmap:**")
        for step in plan.steps:
            duration = f" ~{step.estimated_duration_minutes}m" if step.estimated_duration_minutes else ""
            agent = f" [{step.assigned_agent}]" if step.assigned_agent else ""
            prio = self._priority_label(step.priority)
            deps = f" (after {step.dependencies})" if step.dependencies else ""
            lines.append(f"  {step.step_number}. {step.description}{duration}{agent} {prio}{deps}")

        if plan.estimated_completion:
            lines.append("")
            lines.append(f"⏱️ Estimated completion: {plan.estimated_completion.strftime('%Y-%m-%d')}")

        lines.append("")
        lines.append(f"📌 Tracking ID: `{goal_id}`")
        lines.append("I'll monitor your progress and can adjust the plan anytime.")

        return "\n".join(lines)

    @staticmethod
    def _priority_label(priority: int) -> str:
        """Map a 1-5 priority to a colored label string."""
        labels = {
            1: "🔴 Critical",
            2: "🟠 High",
            3: "🟡 Normal",
            4: "🟢 Low",
            5: "⚪ Optional",
        }
        return labels.get(priority, "🟡 Normal")
