"""
Test suite: Planner Agent — goals, roadmaps, milestones, priorities, dispatch.

Verifies the upgraded Planner:
- Receives GOALS and produces a structured plan
- Creates milestones grouping steps with target progress
- Creates LLM-derived per-step priorities (1-5)
- Persists subtasks to the DB with correct priority
- Dispatches subtasks to assigned agents in DEPENDENCY ORDER (opt-in)
- Honors dependencies (a step runs only after its deps complete)
- Isolates failures (one failed subtask doesn't abort the plan)
- Never dispatches to non-dispatchable agents (commander/learner)
- Backward compatible: existing _detect_plan_type/_generate_plan still work
- Dispatch is opt-in: passive by default (no agent calls)

LLM is mocked so tests run offline and fast.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import framework.tools  # noqa: F401  (register tools)
from core.models import (
    AgentResponse, AgentTask, GoalStatus, Milestone, Plan, PlanStep, TaskStatus,
)
from agents.planner import PlannerAgent


def _goal_task(text: str, dispatch: bool = False) -> AgentTask:
    return AgentTask(
        description=text,
        task_type="planning",
        context={"user_input": text, "session_id": "test", "dispatch": dispatch},
    )


# =============================================================================
# PLAN GENERATION: milestones + priorities
# =============================================================================

class TestPlanGeneration(unittest.TestCase):
    def setUp(self):
        self.p = PlannerAgent()
        # Avoid touching the real DB
        self.p.memory.create_goal = MagicMock(return_value=True)
        self.p.memory.create_task = MagicMock(return_value=True)
        self.p.memory.store_memory = MagicMock(return_value=1)

    def _mock_llm_plan(self, plan_dict):
        """Mock both _detect_plan_type and _generate_plan LLM calls."""
        self.p.llm = MagicMock()
        # _detect_plan_type uses generate_structured; _generate_plan uses call_llm_structured
        self.p.llm.generate_structured.return_value = {"intent": "study_plan", "parameters": {}}
        self.p.call_llm_structured = MagicMock(return_value=plan_dict)

    def test_generates_plan_with_milestones_and_priorities(self):
        plan_dict = {
            "title": "Java Interview Prep",
            "description": "10-day roadmap",
            "goal": "Pass Java interview",
            "steps": [
                {"step_number": 1, "description": "Core Java", "estimated_duration_minutes": 120,
                 "dependencies": [], "assigned_agent": "researcher", "priority": 1},
                {"step_number": 2, "description": "Spring Boot", "estimated_duration_minutes": 180,
                 "dependencies": [1], "assigned_agent": "researcher", "priority": 2},
                {"step_number": 3, "description": "Mock interview", "estimated_duration_minutes": 60,
                 "dependencies": [1, 2], "assigned_agent": "coder", "priority": 1},
            ],
            "milestones": [
                {"title": "Fundamentals", "description": "Core Java", "step_numbers": [1], "target_progress": 0.4},
                {"title": "Frameworks + Practice", "description": "Spring + mock", "step_numbers": [2, 3], "target_progress": 1.0},
            ],
            "estimated_completion_days": 10,
        }
        self._mock_llm_plan(plan_dict)

        resp = self.p.execute(_goal_task("I want to prepare for a Java interview."))

        self.assertTrue(resp.success)
        plan = Plan.model_validate(resp.data["plan"])
        self.assertEqual(len(plan.steps), 3)
        self.assertEqual(len(plan.milestones), 2)
        # Priorities preserved
        self.assertEqual(plan.steps[0].priority, 1)
        self.assertEqual(plan.steps[1].priority, 2)
        # Milestones link to steps
        self.assertEqual(plan.milestones[0].step_numbers, [1])
        self.assertEqual(plan.milestones[1].step_numbers, [2, 3])
        # Steps reference their milestone
        self.assertEqual(plan.steps[0].milestone_id, plan.milestones[0].milestone_id)
        self.assertEqual(plan.steps[1].milestone_id, plan.milestones[1].milestone_id)

    def test_response_contains_milestones_and_priority_labels(self):
        plan_dict = {
            "title": "T", "description": "D", "goal": "G",
            "steps": [{"step_number": 1, "description": "step1", "priority": 1, "assigned_agent": "researcher"}],
            "milestones": [{"title": "M1", "step_numbers": [1], "target_progress": 0.5}],
            "estimated_completion_days": 5,
        }
        self._mock_llm_plan(plan_dict)
        resp = self.p.execute(_goal_task("prep for exam"))
        self.assertIn("Milestones", resp.response)
        self.assertIn("M1", resp.response)
        self.assertIn("Critical", resp.response)  # priority 1 label

    def test_priority_clamped_to_valid_range(self):
        # LLM returns absurd priority 99 — must clamp to 5
        plan_dict = {
            "title": "T", "description": "D", "goal": "G",
            "steps": [{"step_number": 1, "description": "s", "priority": 99}],
            "milestones": [], "estimated_completion_days": 3,
        }
        self._mock_llm_plan(plan_dict)
        resp = self.p.execute(_goal_task("x"))
        plan = Plan.model_validate(resp.data["plan"])
        self.assertEqual(plan.steps[0].priority, 5)  # clamped

    def test_missing_priority_defaults_to_3(self):
        plan_dict = {
            "title": "T", "description": "D", "goal": "G",
            "steps": [{"step_number": 1, "description": "s"}],  # no priority
            "milestones": [], "estimated_completion_days": 3,
        }
        self._mock_llm_plan(plan_dict)
        resp = self.p.execute(_goal_task("x"))
        plan = Plan.model_validate(resp.data["plan"])
        self.assertEqual(plan.steps[0].priority, 3)

    def test_estimated_days_clamped(self):
        plan_dict = {
            "title": "T", "description": "D", "goal": "G",
            "steps": [{"step_number": 1, "description": "s", "priority": 3}],
            "milestones": [], "estimated_completion_days": 99999,
        }
        self._mock_llm_plan(plan_dict)
        resp = self.p.execute(_goal_task("x"))
        plan = Plan.model_validate(resp.data["plan"])
        # Clamped to 365
        self.assertLessEqual((plan.estimated_completion - plan.created_at).days, 366)

    def test_fallback_plan_on_llm_failure(self):
        self.p.llm = MagicMock()
        self.p.llm.generate_structured.return_value = {"intent": "study_plan", "parameters": {}}
        self.p.call_llm_structured = MagicMock(side_effect=RuntimeError("ollama down"))
        resp = self.p.execute(_goal_task("some goal"))
        self.assertTrue(resp.success)
        plan = Plan.model_validate(resp.data["plan"])
        self.assertEqual(plan.title, "General Plan")
        self.assertEqual(len(plan.steps), 1)


# =============================================================================
# PERSISTENCE: subtasks saved with correct priority
# =============================================================================

class TestSubtaskPersistence(unittest.TestCase):
    def setUp(self):
        self.p = PlannerAgent()
        self.p.memory.create_goal = MagicMock(return_value=True)
        self.p.memory.store_memory = MagicMock(return_value=1)
        self.create_task = MagicMock(return_value=True)
        self.p.memory.create_task = self.create_task

    def test_subtasks_persisted_with_llm_priority(self):
        plan_dict = {
            "title": "T", "description": "D", "goal": "G",
            "steps": [
                {"step_number": 1, "description": "a", "priority": 1, "assigned_agent": "researcher"},
                {"step_number": 2, "description": "b", "priority": 4, "assigned_agent": "coder"},
            ],
            "milestones": [], "estimated_completion_days": 3,
        }
        self.p.llm = MagicMock()
        self.p.llm.generate_structured.return_value = {"intent": "study_plan", "parameters": {}}
        self.p.call_llm_structured = MagicMock(return_value=plan_dict)

        self.p.execute(_goal_task("goal"))

        self.assertEqual(self.create_task.call_count, 2)
        # First task (priority 1)
        first_args = self.create_task.call_args_list[0]
        self.assertEqual(first_args.kwargs["priority"], 1)
        self.assertEqual(first_args.kwargs["assigned_agent"], "researcher")
        # Second task (priority 4)
        second_args = self.create_task.call_args_list[1]
        self.assertEqual(second_args.kwargs["priority"], 4)

    def test_step_without_agent_defaults_to_executor(self):
        plan_dict = {
            "title": "T", "description": "D", "goal": "G",
            "steps": [{"step_number": 1, "description": "a", "priority": 3}],  # no assigned_agent
            "milestones": [], "estimated_completion_days": 3,
        }
        self.p.llm = MagicMock()
        self.p.llm.generate_structured.return_value = {"intent": "study_plan", "parameters": {}}
        self.p.call_llm_structured = MagicMock(return_value=plan_dict)

        self.p.execute(_goal_task("goal"))
        first_args = self.create_task.call_args_list[0]
        self.assertEqual(first_args.kwargs["assigned_agent"], "executor")


# =============================================================================
# DISPATCH: opt-in, dependency-aware, isolated
# =============================================================================

class TestSubtaskDispatch(unittest.TestCase):
    def setUp(self):
        self.p = PlannerAgent()
        self.p.memory.create_goal = MagicMock(return_value=True)
        self.p.memory.create_task = MagicMock(return_value=True)
        self.p.memory.store_memory = MagicMock(return_value=1)

        # Stub agents in the registry that record calls
        self.calls = []
        self._install_stub_agents()

    def _install_stub_agents(self):
        """Force-register recording stubs for all dispatchable agents.
        We overwrite (not skip) so prior tests' real/exploding agents don't
        leak in and steal the dispatch calls. Each stub binds its name via a
        default arg to avoid Python's late-binding closure pitfall."""
        from core.registry import AgentRegistry
        reg = AgentRegistry()
        recorder = self

        for name in self.p.DISPATCHABLE_AGENTS:
            # make_exec captures `name` at definition time via the default arg `n`.
            # `execute` takes (self, task) because it's accessed as an instance method.
            def make_exec(n):
                def execute(self, task):
                    recorder.calls.append(n)
                    return AgentResponse(agent_name=n, task_id=task.task_id,
                                         success=True, response=f"did {task.description[:20]}")
                return execute

            # type() creates a DISTINCT class each iteration (a `class` statement
            # in a loop would reuse one class object, leaking the last execute).
            Stub = type(f"Stub_{name}", (), {"name": name, "execute": make_exec(name)})
            reg.register(name, Stub(), description="stub", capabilities=[])

    def _mock_plan(self, steps, milestones=None, days=3):
        plan_dict = {
            "title": "T", "description": "D", "goal": "G",
            "steps": steps,
            "milestones": milestones or [],
            "estimated_completion_days": days,
        }
        self.p.llm = MagicMock()
        self.p.llm.generate_structured.return_value = {"intent": "study_plan", "parameters": {}}
        self.p.call_llm_structured = MagicMock(return_value=plan_dict)

    def test_passive_by_default_no_dispatch(self):
        """Without dispatch=True, NO agent.execute is called."""
        self._mock_plan([
            {"step_number": 1, "description": "a", "priority": 1, "assigned_agent": "researcher"},
        ])
        self.p.execute(_goal_task("goal", dispatch=False))
        self.assertEqual(self.calls, [], "Planner must NOT dispatch when dispatch flag is off")

    def test_dispatch_executes_steps(self):
        self._mock_plan([
            {"step_number": 1, "description": "a", "priority": 1, "assigned_agent": "researcher"},
            {"step_number": 2, "description": "b", "priority": 2, "assigned_agent": "coder"},
        ])
        resp = self.p.execute(_goal_task("goal", dispatch=True))
        self.assertEqual(set(self.calls), {"researcher", "coder"})
        self.assertIn("Subtask Dispatch Report", resp.response)

    def test_dispatch_respects_dependency_order(self):
        """Step 2 depends on step 1 → step 1 must execute first."""
        self._mock_plan([
            {"step_number": 1, "description": "first", "priority": 1, "assigned_agent": "researcher", "dependencies": []},
            {"step_number": 2, "description": "second", "priority": 1, "assigned_agent": "coder", "dependencies": [1]},
        ])
        self.p.execute(_goal_task("goal", dispatch=True))
        # researcher (step 1) must appear before coder (step 2)
        self.assertEqual(self.calls, ["researcher", "coder"])

    def test_dispatch_skips_unsatisfiable_dependencies(self):
        """Step depends on a non-existent step → reported as skipped, no crash."""
        self._mock_plan([
            {"step_number": 1, "description": "a", "priority": 1, "assigned_agent": "researcher", "dependencies": [99]},
        ])
        resp = self.p.execute(_goal_task("goal", dispatch=True))
        self.assertIn("SKIPPED", resp.response)
        self.assertEqual(self.calls, [])  # never executed

    def test_dispatch_isolates_failures(self):
        """One agent throwing must not abort the rest of the plan."""
        self._mock_plan([
            {"step_number": 1, "description": "a", "priority": 1, "assigned_agent": "researcher"},
            {"step_number": 2, "description": "b", "priority": 1, "assigned_agent": "coder"},
        ])
        # Make coder throw
        from core.registry import AgentRegistry
        reg = AgentRegistry()
        class ExplodingAgent:
            def execute(self, task): raise RuntimeError("boom")
        reg.register("coder", ExplodingAgent(), description="boom", capabilities=[])
        resp = self.p.execute(_goal_task("goal", dispatch=True))
        self.assertIn("researcher", self.calls)  # researcher still ran
        self.assertIn("FAILED", resp.response)    # coder failure reported

    def test_dispatch_skips_non_dispatchable_agents(self):
        """assigned_agent='commander' or 'learner' must be skipped, not called."""
        self._mock_plan([
            {"step_number": 1, "description": "a", "priority": 1, "assigned_agent": "commander"},
        ])
        resp = self.p.execute(_goal_task("goal", dispatch=True))
        self.assertIn("skipped", resp.response.lower())
        # No stub for commander was installed, so calls stays empty
        self.assertEqual(self.calls, [])

    def test_dispatch_skips_unregistered_agent(self):
        self._mock_plan([
            {"step_number": 1, "description": "a", "priority": 1, "assigned_agent": "nonexistent"},
        ])
        resp = self.p.execute(_goal_task("goal", dispatch=True))
        self.assertIn("skipped", resp.response.lower())


# =============================================================================
# BACKWARD COMPATIBILITY
# =============================================================================

class TestBackwardCompat(unittest.TestCase):
    def test_detect_plan_type_still_callable(self):
        p = PlannerAgent()
        p.llm = MagicMock()
        p.llm.generate_structured.return_value = {"intent": "study_plan", "parameters": {}}
        self.assertEqual(p._detect_plan_type("interview in 10 days"), "study_plan")

    def test_format_plan_response_still_shows_steps(self):
        p = PlannerAgent()
        plan = Plan(title="T", description="D", goal="G",
                    steps=[PlanStep(step_number=1, description="do thing", priority=2)])
        out = p._format_plan_response(plan, "goal_123")
        self.assertIn("do thing", out)
        self.assertIn("goal_123", out)

    def test_generate_plan_returns_plan_on_dict(self):
        p = PlannerAgent()
        p.llm = MagicMock()
        p.llm.generate_structured.return_value = {"intent": "general_plan", "parameters": {}}
        p.call_llm_structured = MagicMock(return_value={
            "title": "X", "description": "Y", "goal": "Z",
            "steps": [{"step_number": 1, "description": "s", "priority": 3}],
            "milestones": [], "estimated_completion_days": 5,
        })
        plan = p._generate_plan("goal", "general_plan", "")
        self.assertEqual(plan.title, "X")
        self.assertEqual(len(plan.steps), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
