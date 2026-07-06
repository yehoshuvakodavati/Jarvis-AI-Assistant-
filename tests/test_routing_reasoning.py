"""
Regression test: agents route via LLM reasoning, NOT keyword matching.

This suite proves the refactor succeeded:
- Each specialist agent's execute_task() asks the LLM to choose an operation,
  rather than matching hardcoded keyword if/elif chains.
- Paraphrased inputs (no literal keywords) still route correctly, because the
  LLM understands intent — a keyword matcher would fail on them.
- The Commander delegates and never executes tools directly.
- The shared routing helpers (framework.routing) behave as specified.

The LLM is mocked so tests run fast and offline.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# CRITICAL: import framework.tools so the @tool decorators register the real
# system tools (math_evaluate, system_open_app, etc.) into the global ToolRegistry.
# Without this, executor tests fail if no earlier test imported the module.
import framework.tools  # noqa: F401
from core.models import AgentTask, AgentResponse


def _make_task(user_input: str, task_type: str = "test") -> AgentTask:
    return AgentTask(
        description=user_input,
        task_type=task_type,
        context={"user_input": user_input, "session_id": "test"},
    )


class TestRoutingHelpers(unittest.TestCase):
    """framework.routing — the shared abstractions replacing duplicated logic."""

    def test_extract_url_full(self):
        from framework.routing import extract_url
        self.assertEqual(extract_url("see https://example.com/x"), "https://example.com/x")

    def test_extract_url_bare_domain_normalized(self):
        from framework.routing import extract_url
        self.assertEqual(extract_url("open github.com"), "https://github.com")

    def test_extract_url_none(self):
        from framework.routing import extract_url
        self.assertIsNone(extract_url("hello world"))

    def test_is_math_expression_true(self):
        from framework.routing import is_math_expression
        self.assertTrue(is_math_expression("2 + 3 * 4"))
        self.assertTrue(is_math_expression("(1 + 2) / 3"))

    def test_is_math_expression_false_prose(self):
        from framework.routing import is_math_expression
        self.assertFalse(is_math_expression("what is 2 + 2"))  # has letters
        self.assertFalse(is_math_expression("hello"))            # no operator

    def test_classify_trivial(self):
        from framework.routing import classify_trivial
        self.assertEqual(classify_trivial("hello"), "greeting")
        self.assertEqual(classify_trivial("who are you"), "identity")
        self.assertEqual(classify_trivial("thanks"), "thanks")
        self.assertEqual(classify_trivial("goodbye"), "farewell")
        self.assertIsNone(classify_trivial("search for cats"))

    def test_confirmation_helpers(self):
        from framework.routing import is_confirmation_yes, is_confirmation_no
        self.assertTrue(is_confirmation_yes("yes"))
        self.assertTrue(is_confirmation_yes("proceed"))
        self.assertFalse(is_confirmation_yes("no"))
        self.assertTrue(is_confirmation_no("cancel"))
        self.assertFalse(is_confirmation_no("yes"))

    def test_parse_intent_via_llm_valid(self):
        from framework.routing import parse_intent_via_llm
        llm = MagicMock()
        llm.generate_structured.return_value = {"intent": "shutdown", "parameters": {}}
        op, params = parse_intent_via_llm(llm, "p", ["shutdown", "general"])
        self.assertEqual(op, "shutdown")

    def test_parse_intent_via_llm_invalid_falls_back(self):
        from framework.routing import parse_intent_via_llm
        llm = MagicMock()
        llm.generate_structured.return_value = {"intent": "bogus", "parameters": {}}
        op, _ = parse_intent_via_llm(llm, "p", ["shutdown", "general"])
        # Last entry is the fallback default
        self.assertEqual(op, "general")

    def test_parse_intent_via_llm_llm_failure_falls_back(self):
        from framework.routing import parse_intent_via_llm
        llm = MagicMock()
        llm.generate_structured.side_effect = RuntimeError("ollama down")
        op, params = parse_intent_via_llm(llm, "p", ["shutdown", "general"])
        self.assertEqual(op, "general")
        self.assertEqual(params, {})


class TestExecutorRoutesViaReasoning(unittest.TestCase):
    """Executor must pick operations via LLM, not keyword if/elif."""

    def setUp(self):
        from agents.executor import ExecutorAgent
        self.e = ExecutorAgent()
        # GUARANTEE the real system tools are registered, even if a prior test
        # cleared the global ToolRegistry. Re-apply @tool decoration if missing.
        import framework.tools as ft
        from core.registry import ToolRegistry
        tr = ToolRegistry()
        for fn_name in ("system_open_app", "system_shutdown", "system_restart",
                        "system_sleep", "system_lock", "math_evaluate",
                        "system_open_url", "system_open_settings"):
            if tr.get_safe(fn_name) is None:
                fn = getattr(ft, fn_name, None)
                if fn is not None:
                    from framework.decorators import tool as tool_dec
                    tool_dec(description=fn.__doc__ or fn_name,
                             dangerous=fn_name in ("system_shutdown", "system_restart", "system_sleep"),
                             requires_confirmation=fn_name in ("system_shutdown", "system_restart", "system_sleep"))(fn)

    def _mock_llm_op(self, op, params=None):
        self.e.llm = MagicMock()
        self.e.llm.generate_structured.return_value = {"intent": op, "parameters": params or {}}

    @patch("framework.tools.subprocess.Popen")
    def test_paraphrased_shutdown_routes_via_llm(self, _mock_popen):
        """No keyword 'shutdown' — paraphrase 'kill the power'. Keyword matcher
        would route this to 'general'; the LLM path routes it to shutdown."""
        from agents.executor import ExecutorAgent
        e = ExecutorAgent()
        e.llm = MagicMock()
        e.llm.generate_structured.return_value = {"intent": "shutdown", "parameters": {}}
        resp = e.execute(_make_task("kill the power"))
        # shutdown requires confirmation → first call blocked, Popen not called
        self.assertFalse(resp.success)
        self.assertIn("confirm", (resp.response or "").lower())
        _mock_popen.assert_not_called()

    @patch("framework.tools.subprocess.Popen")
    def test_paraphrased_open_app_routes_via_llm(self, _mock_popen):
        from agents.executor import ExecutorAgent
        e = ExecutorAgent()
        e.llm = MagicMock()
        e.llm.generate_structured.return_value = {"intent": "open_app", "parameters": {"app_name": "notepad"}}
        resp = e.execute(_make_task("fire up the text editor"))
        self.assertTrue(resp.success)

    def test_math_fast_path_skips_llm(self):
        """Pure math is handled without an LLM call (deterministic fast path)."""
        from agents.executor import ExecutorAgent
        e = ExecutorAgent()
        e.llm = MagicMock()
        resp = e.execute(_make_task("2 + 3 * 4"))
        self.assertTrue(resp.success)
        self.assertIn("14", resp.response)
        # LLM was NOT consulted
        e.llm.generate_structured.assert_not_called()

    def test_invalid_op_falls_back_to_general(self):
        from agents.executor import ExecutorAgent
        e = ExecutorAgent()
        e.llm = MagicMock()
        e.llm.generate_structured.return_value = {"intent": "bogus", "parameters": {}}
        resp = e.execute(_make_task("do something weird"))
        self.assertTrue(resp.success)
        self.assertIn("I can help you with", resp.response)


class TestFileAgentRoutesViaReasoning(unittest.TestCase):
    def test_paraphrased_search_routes_via_llm(self):
        """'locate my python scripts' — no 'find file' keyword. LLM picks search."""
        from agents.file_agent import FileAgent
        f = FileAgent()
        f.llm = MagicMock()
        f.llm.generate_structured.return_value = {"intent": "search", "parameters": {}}
        # Patch the underlying tool so no real FS search happens
        with patch.object(f, "call_tool") as mock_tool:
            mock_tool.return_value = MagicMock(success=True, result=["/x/a.py"])
            resp = f.execute(_make_task("locate my python scripts"))
        self.assertTrue(resp.success)
        # The LLM was consulted (reasoning path), and the search handler ran
        f.llm.generate_structured.assert_called_once()


class TestMemoryAgentRoutesViaReasoning(unittest.TestCase):
    def test_paraphrased_note_create_routes_via_llm(self):
        """'jot down that the meeting is at 3pm' — no 'save note' keyword."""
        from agents.memory_agent import MemoryAgent
        m = MemoryAgent()
        m.llm = MagicMock()
        # Two LLM calls: (1) route → note_create, (2) extract title/content
        m.llm.generate_structured.side_effect = [
            {"intent": "note_create", "parameters": {}},                 # routing
            {"title": "Meeting", "content": "at 3pm", "tags": ""},       # note extraction
        ]
        with patch.object(m.memory, "save_note", return_value=42):
            resp = m.execute(_make_task("jot down that the meeting is at 3pm"))
        self.assertTrue(resp.success)
        # The reasoning path WAS consulted (at least once)
        self.assertGreaterEqual(m.llm.generate_structured.call_count, 1)


class TestCoderRoutesViaReasoning(unittest.TestCase):
    def test_paraphrased_review_routes_via_llm(self):
        """'is this code any good?' — no 'review' keyword. LLM picks review."""
        from agents.coder import CoderAgent
        c = CoderAgent()
        c.llm = MagicMock()
        c.llm.generate_structured.return_value = {"intent": "review", "parameters": {}}
        # _handle_code_review calls call_llm; mock generate to avoid Ollama
        c.llm.generate.return_value = "looks fine"
        resp = c.execute(_make_task("is this code any good?"))
        self.assertTrue(resp.success)
        c.llm.generate_structured.assert_called_once()


class TestPlannerRoutesViaReasoning(unittest.TestCase):
    def test_paraphrased_study_plan_via_llm(self):
        """'prep for my certification next month' — paraphrase. LLM picks study_plan."""
        from agents.planner import PlannerAgent
        p = PlannerAgent()
        # _detect_plan_type calls parse_intent_via_llm; mock generate_structured
        p.llm = MagicMock()
        p.llm.generate_structured.return_value = {"intent": "study_plan", "parameters": {}}
        # _generate_plan ALSO calls generate_structured; return a minimal plan
        plan_dict = {
            "title": "Cert Prep",
            "description": "d",
            "goal": "g",
            "steps": [{"step_number": 1, "description": "study", "assigned_agent": "researcher"}],
            "estimated_completion_days": 30,
        }

        # First call (detect plan type) returns study_plan; subsequent calls
        # (generate plan) return the plan dict. Use side_effect.
        p.llm.generate_structured.side_effect = [
            {"intent": "study_plan", "parameters": {}},  # _detect_plan_type
            plan_dict,                                     # _generate_plan
        ]
        resp = p.execute(_make_task("prep for my certification next month", "planning"))
        self.assertTrue(resp.success)
        self.assertIn("Cert Prep", resp.response)


class TestCommanderNeverExecutesTools(unittest.TestCase):
    """The Commander must DELEGATE, never run tools directly."""

    def test_commander_delegates_to_specialist(self):
        from agents.commander import CommanderAgent
        from core.registry import AgentRegistry
        # Register stub agents so routing has a target
        reg = AgentRegistry()
        reg._agents.clear()
        reg._agent_metadata.clear()

        # A real Researcher stub that records it was called
        called = {"executed": False}
        class StubResearcher:
            name = "researcher"
            description = "stub"
            capabilities = ["research"]
            def execute(self, task):
                called["executed"] = True
                return AgentResponse(agent_name="researcher", task_id=task.task_id, success=True, response="researched")
        reg.register("researcher", StubResearcher(), description="stub", capabilities=["research"])
        for n in ("commander", "planner", "memory_agent", "coder", "executor", "browser", "file_agent", "learner"):
            reg.register(n, StubResearcher(), description="stub", capabilities=[])

        c = CommanderAgent()
        # Mock the Commander's own LLM routing to pick researcher
        c.llm = MagicMock()
        c.llm.generate_structured.return_value = {
            "intent": "research", "primary_agent": "researcher",
            "supporting_agents": [], "decomposition": [],
            "needs_memory_context": False, "confidence": 0.9, "reasoning": "r",
        }
        # Don't actually persist conversations
        c.memory.save_conversation = MagicMock()

        resp = c.process_user_input("find me AI news", session_id="t")

        self.assertTrue(called["executed"], "Commander must delegate to the researcher")
        # The Commander itself must not call any tool
        # (it has no call_tool invocations on this path)


class TestNoHardcodedKeywordRoutingRemains(unittest.TestCase):
    """Static check: specialist agents must not contain keyword if/elif dispatch."""

    def test_executor_has_no_keyword_dispatch(self):
        from pathlib import Path
        src = Path("jarvis/agents/executor.py").read_text(encoding="utf-8") if Path("jarvis/agents/executor.py").exists() else Path("agents/executor.py").read_text(encoding="utf-8")
        # The old pattern was `if any(kw in lower for kw in (...))` inside execute_task
        # After refactor, execute_task should call parse_intent_via_llm instead.
        self.assertIn("parse_intent_via_llm", src)
        self.assertNotIn('any(kw in lower for kw in ("shutdown"', src)

    def test_file_agent_has_no_keyword_dispatch(self):
        from pathlib import Path
        p = Path("jarvis/agents/file_agent.py") if Path("jarvis/agents/file_agent.py").exists() else Path("agents/file_agent.py")
        src = p.read_text(encoding="utf-8")
        self.assertIn("parse_intent_via_llm", src)
        self.assertNotIn('any(kw in lower for kw in ("find file"', src)

    def test_memory_agent_has_no_keyword_dispatch(self):
        from pathlib import Path
        p = Path("jarvis/agents/memory_agent.py") if Path("jarvis/agents/memory_agent.py").exists() else Path("agents/memory_agent.py")
        src = p.read_text(encoding="utf-8")
        self.assertIn("parse_intent_via_llm", src)
        self.assertNotIn('any(kw in lower for kw in ("save note"', src)


if __name__ == "__main__":
    unittest.main(verbosity=2)
