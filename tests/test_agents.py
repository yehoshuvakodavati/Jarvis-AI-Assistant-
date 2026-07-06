"""
Test suite: Agents — Commander routing, fallback, trivial handling, confirmation.

LLM is mocked so tests run without Ollama. Validates:
- Commander._fallback_routing keyword→agent mapping (safety net when LLM down)
- Commander._handle_trivial (greetings, math, identity)
- Commander._handle_pending_confirmation (yes/no)
- LLM-based routing with a mocked LLM returning JSON
- Planner plan generation with mocked LLM
- Executor power-command delegation (uses mocked subprocess)

Run: python tests/test_agents.py
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import framework.tools  # noqa: F401  (register tools)
from agents.commander import CommanderAgent
from agents.planner import PlannerAgent
from agents.executor import ExecutorAgent
from core.models import AgentTask, AgentStatus, RoutingDecision


class TestCommanderFallbackRouting(unittest.TestCase):
    """The keyword fallback is the safety net when the LLM is unreachable."""

    def setUp(self):
        self.c = CommanderAgent()
        # Don't actually hit the network in _route_via_llm tests below —
        # but fallback routing is pure logic, no LLM needed.

    def _fb(self, q):
        return self.c._fallback_routing(q)

    def test_planning_keywords(self):
        for q in ["plan my week", "create a roadmap", "study for exam", "schedule a meeting"]:
            d = self._fb(q)
            self.assertEqual(d.primary_agent, "planner", msg=q)

    def test_research_keywords(self):
        for q in ["search for cats", "what is quantum", "latest news", "current weather"]:
            d = self._fb(q)
            self.assertEqual(d.primary_agent, "researcher", msg=q)

    def test_coding_keywords(self):
        for q in ["write python code", "debug this function", "java algorithm"]:
            d = self._fb(q)
            self.assertEqual(d.primary_agent, "coder", msg=q)

    def test_execution_keywords(self):
        for q in ["open notepad", "shutdown the system", "restart computer"]:
            d = self._fb(q)
            self.assertEqual(d.primary_agent, "executor", msg=q)

    def test_file_keywords(self):
        for q in ["find all pdf files", "list my documents folder"]:
            d = self._fb(q)
            self.assertEqual(d.primary_agent, "file_agent", msg=q)

    def test_memory_keywords(self):
        for q in ["save a note", "remember this", "what do i prefer"]:
            d = self._fb(q)
            self.assertEqual(d.primary_agent, "memory_agent", msg=q)

    def test_browser_keywords(self):
        for q in ["browse to github", "go to website", "open this url"]:
            d = self._fb(q)
            self.assertEqual(d.primary_agent, "browser", msg=q)

    def test_default_fallback(self):
        d = self._fb("completely unrelated gibberish xyz123")
        self.assertEqual(d.primary_agent, "executor")

    def test_confidence_range(self):
        for q in ["plan x", "search y", "open z"]:
            d = self._fb(q)
            self.assertGreaterEqual(d.confidence, 0.0)
            self.assertLessEqual(d.confidence, 1.0)


class TestCommanderTrivial(unittest.TestCase):
    def setUp(self):
        self.c = CommanderAgent()

    def test_greeting(self):
        for g in ["hello", "hi", "hey", "good morning"]:
            r = self.c._handle_trivial(g)
            self.assertIsNotNone(r)
            self.assertIn("Commander", r)

    def test_identity(self):
        r = self.c._handle_trivial("who are you")
        self.assertIsNotNone(r)
        self.assertIn("Jarvis", r)

    def test_thanks(self):
        r = self.c._handle_trivial("thank you")
        self.assertIsNotNone(r)

    def test_math(self):
        r = self.c._handle_trivial("2 + 3 * 4")
        self.assertIsNotNone(r)
        self.assertIn("14", r)

    def test_nontrivial_returns_none(self):
        self.assertIsNone(self.c._handle_trivial("search for cats"))


class TestCommanderConfirmation(unittest.TestCase):
    def setUp(self):
        self.c = CommanderAgent()
        self.c.state.clear_session()

    def test_yes_confirms_pending_action(self):
        fired = []
        self.c.state.request_confirmation("cid", "shutdown", "executor", lambda: fired.append("done"))
        handled = self.c._handle_pending_confirmation("yes")
        self.assertTrue(handled)
        self.assertEqual(fired, ["done"])

    def test_no_cancels_pending_action(self):
        cb = MagicMock()
        self.c.state.request_confirmation("cid2", "restart", "executor", cb)
        handled = self.c._handle_pending_confirmation("no")
        self.assertTrue(handled)
        cb.assert_not_called()

    def test_no_pending_returns_false(self):
        self.assertFalse(self.c._handle_pending_confirmation("yes"))


class TestCommanderLLMRouting(unittest.TestCase):
    """Mock the LLM so _route_via_llm parses a JSON routing decision."""

    def setUp(self):
        self.c = CommanderAgent()
        # The Commander checks registry.list_agents() to validate the LLM's
        # suggestion. Ensure stub agents are registered if missing, WITHOUT
        # clearing the global registry (which would nuke real agents for other tests).
        from core.registry import AgentRegistry
        reg = AgentRegistry()
        for name in ("commander", "planner", "researcher", "memory_agent", "coder", "executor", "browser", "file_agent", "learner"):
            if reg.get_safe(name) is None:
                stub = MagicMock()
                stub.description = name
                stub.capabilities = []
                reg.register(name, stub, description=name, capabilities=[])

    def _mock_llm(self, parsed_obj):
        """Mock generate_structured to return a pre-parsed object."""
        self.c.llm = MagicMock()
        self.c.llm.generate_structured.return_value = parsed_obj

    def test_routes_to_researcher(self):
        self._mock_llm({"intent": "research", "primary_agent": "researcher", "supporting_agents": [], "decomposition": [], "needs_memory_context": False, "confidence": 0.9, "reasoning": "r"})
        d = self.c._route_via_llm("search for AI news")
        self.assertEqual(d.primary_agent, "researcher")
        self.assertAlmostEqual(d.confidence, 0.9)

    def test_misnamed_agent_normalized(self):
        # LLM says "research" (common misname) → normalized to "researcher"
        self._mock_llm({"intent": "x", "primary_agent": "research", "supporting_agents": ["memory"], "decomposition": [], "needs_memory_context": True, "confidence": 0.7, "reasoning": "r"})
        d = self.c._route_via_llm("find info")
        self.assertEqual(d.primary_agent, "researcher")
        self.assertIn("memory_agent", d.supporting_agents)

    def test_invalid_json_falls_back(self):
        # Non-dict parsed result (e.g. a plain string) → fallback to keywords
        self._mock_llm("not json at all")
        d = self.c._route_via_llm("search for cats")
        # Falls back to keyword routing
        self.assertEqual(d.primary_agent, "researcher")

    def test_empty_dict_falls_back(self):
        # Empty dict → no primary_agent → defaults to "executor"
        self._mock_llm({})
        d = self.c._route_via_llm("search for cats")
        self.assertEqual(d.primary_agent, "executor")

    def test_unknown_agent_falls_back(self):
        self._mock_llm({"intent": "x", "primary_agent": "nonexistent_agent", "supporting_agents": [], "decomposition": [], "needs_memory_context": False, "confidence": 0.5, "reasoning": "r"})
        d = self.c._route_via_llm("search for cats")
        self.assertEqual(d.primary_agent, "researcher")


class TestPlanner(unittest.TestCase):
    def setUp(self):
        self.p = PlannerAgent()

    def test_detect_plan_types(self):
        self.assertEqual(self.p._detect_plan_type("interview in 10 days"), "study_plan")
        self.assertEqual(self.p._detect_plan_type("build a project"), "project_plan")
        self.assertEqual(self.p._detect_plan_type("daily routine"), "schedule")
        self.assertEqual(self.p._detect_plan_type("random thing"), "general_plan")

    def test_generate_plan_with_mocked_llm(self):
        self.p.llm = MagicMock()
        self.p.llm.generate_structured.return_value = {
            "title": "Spring Boot Plan",
            "description": "desc",
            "goal": "pass interview",
            "steps": [
                {"step_number": 1, "description": "study core", "assigned_agent": "researcher", "estimated_duration_minutes": 60},
                {"step_number": 2, "description": "practice", "assigned_agent": "coder", "estimated_duration_minutes": 90},
            ],
            "estimated_completion_days": 10,
        }
        plan = self.p._generate_plan("spring boot interview in 10 days", "study_plan", "")
        self.assertEqual(plan.title, "Spring Boot Plan")
        self.assertEqual(len(plan.steps), 2)
        self.assertEqual(plan.steps[0].assigned_agent, "researcher")

    def test_format_plan_response_contains_steps(self):
        from core.models import Plan, PlanStep
        plan = Plan(title="T", description="D", goal="G", steps=[PlanStep(step_number=1, description="do x")])
        out = self.p._format_plan_response(plan, "goal_123")
        self.assertIn("T", out)
        self.assertIn("do x", out)
        self.assertIn("goal_123", out)


class TestExecutorAgent(unittest.TestCase):
    """Executor delegates to system tools — confirmations enforced by tool schemas."""

    def setUp(self):
        self.e = ExecutorAgent()

    @patch("framework.tools.subprocess.Popen")
    def test_open_app(self, mock_popen):
        from core.models import AgentTask
        task = AgentTask(description="open notepad", task_type="execution", context={"user_input": "open notepad"})
        resp = self.e.execute(task)
        # Either it opened (success) or hit confirmation — notepad is not dangerous
        self.assertTrue(resp.success)
        mock_popen.assert_called()

    def test_shutdown_triggers_confirmation(self):
        from core.models import AgentTask
        task = AgentTask(description="shutdown the system", task_type="execution", context={"user_input": "shutdown"})
        # We mock subprocess so even if confirmation were bypassed it wouldn't actually run
        with patch("framework.tools.subprocess.Popen") as mock_popen:
            resp = self.e.execute(task)
        # shutdown requires confirmation → first attempt should NOT succeed with Popen
        # (it asks for confirmation instead)
        self.assertFalse(resp.success)
        self.assertIn("confirm", (resp.response or "").lower())
        mock_popen.assert_not_called()


if __name__ == "__main__":
    unittest.main(verbosity=2)
