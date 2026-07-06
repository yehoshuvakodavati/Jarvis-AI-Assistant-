"""
Test suite: Core systems (LLM client, message bus, registries, state, models).

Runs without Ollama — LLM is mocked. Validates:
- MessageBus pub/sub semantics + history
- AgentRegistry/ToolRegistry register/get/lookup + describe_for_llm
- SystemState confirmation lifecycle + string-status coercion guard
- LLMClient retry/parse behavior (mocked transport)

Run: python tests/test_core.py
"""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


class TestMessageBus(unittest.TestCase):
    def setUp(self):
        from core.message_bus import MessageBus
        self.bus = MessageBus()
        # Clear singleton history
        self.bus.clear_history()

    def test_publish_subscribe(self):
        received = []
        self.bus.subscribe("test_topic", lambda t, d: received.append((t, d)))
        n = self.bus.publish("test_topic", {"hello": "world"}, source="tester")
        self.assertEqual(n, 1)
        self.assertEqual(received[0][0], "test_topic")
        self.assertEqual(received[0][1], {"hello": "world"})

    def test_multiple_subscribers(self):
        hits = []
        self.bus.subscribe("t", lambda t, d: hits.append(1))
        self.bus.subscribe("t", lambda t, d: hits.append(2))
        self.bus.publish("t", "x")
        self.assertEqual(hits, [1, 2])

    def test_unsubscribe(self):
        cb = MagicMock()
        self.bus.subscribe("t", cb)
        self.bus.unsubscribe("t", cb)
        self.bus.publish("t", "x")
        cb.assert_not_called()

    def test_history_filtered(self):
        self.bus.publish("a", 1)
        self.bus.publish("b", 2)
        self.bus.publish("a", 3)
        hist = self.bus.get_history(topic="a")
        self.assertEqual(len(hist), 2)
        self.assertTrue(all(e["topic"] == "a" for e in hist))

    def test_callback_isolated(self):
        """A failing callback must not prevent other subscribers."""
        good = MagicMock()
        def bad(t, d): raise RuntimeError("boom")
        self.bus.subscribe("t", bad)
        self.bus.subscribe("t", good)
        n = self.bus.publish("t", "x")
        self.assertEqual(n, 1)  # only the good one counted
        good.assert_called_once()

    def test_subscriber_count(self):
        # Use a unique topic so other tests' subscriptions don't pollute
        topic = "count_test_isolated"
        self.bus.subscribe(topic, lambda *a: None)
        self.assertEqual(self.bus.subscriber_count(topic), 1)
        self.assertEqual(self.bus.subscriber_count("none"), 0)


class TestRegistries(unittest.TestCase):
    def setUp(self):
        # Use FRESH LOCAL registry instances (not the global singletons).
        # Clearing the singletons would permanently deregister the real
        # system tools/agents for every other test in the suite.
        from core.registry import AgentRegistry, ToolRegistry
        self.ar = AgentRegistry.__new__(AgentRegistry)
        self.ar._agents = {}
        self.ar._agent_metadata = {}
        self.tr = ToolRegistry.__new__(ToolRegistry)
        self.tr._tools = {}
        self.tr._schemas = {}

    def test_register_and_get_agent(self):
        class FakeAgent:
            description = "fake"
            capabilities = ["x"]
        a = FakeAgent()
        self.ar.register("fake", a, description="d", capabilities=["x"])
        self.assertIs(self.ar.get("fake"), a)
        self.assertIn("fake", self.ar.list_agents())

    def test_get_unknown_agent_raises(self):
        from core.exceptions import AgentNotFoundError
        with self.assertRaises(AgentNotFoundError):
            self.ar.get("nope")

    def test_get_safe_returns_none(self):
        self.assertIsNone(self.ar.get_safe("nope"))

    def test_describe_for_llm(self):
        class A:
            description = "does x"
            capabilities = ["x", "y"]
        self.ar.register("a", A(), description="does x", capabilities=["x", "y"])
        desc = self.ar.describe_for_llm()
        self.assertIn("Available Agents", desc)
        self.assertIn("a", desc)

    def test_register_tool_with_schema_inference(self):
        def my_tool(query: str, count: int = 5) -> list:
            """A tool."""
            return []
        self.tr.register("my_tool", my_tool, description="A tool.")
        schema = self.tr.get_schema("my_tool")
        names = [p.name for p in schema.parameters]
        self.assertEqual(names, ["query", "count"])
        # query required, count optional
        q = next(p for p in schema.parameters if p.name == "query")
        c = next(p for p in schema.parameters if p.name == "count")
        self.assertTrue(q.required)
        self.assertFalse(c.required)

    def test_tool_not_found_raises(self):
        from core.exceptions import ToolNotFoundError
        with self.assertRaises(ToolNotFoundError):
            self.tr.get("nope")


class TestSystemState(unittest.TestCase):
    def setUp(self):
        from core.state import SystemState
        self.st = SystemState()
        # Clear ALL pending confirmations left over from other tests
        for pc in self.st.get_all_pending_confirmations():
            self.st.cancel_action(pc.action_id)
        self.st.clear_session()

    def test_active_agent_lifecycle(self):
        self.st.set_active_agent("commander", "tid", "do thing")
        self.assertEqual(self.st.active_agent, "commander")
        self.assertEqual(self.st.active_task_description, "do thing")
        self.st.clear_active_agent("commander")
        self.assertIsNone(self.st.active_agent)

    def test_confirmation_lifecycle(self):
        called = []
        def confirm_cb():
            called.append("yes")
            return "result_value"
        # Use a unique id in case another test left state
        self.st.request_confirmation("c1_iso", "shutdown", "executor", confirm_cb)
        self.assertTrue(self.st.has_pending_confirmations())
        result = self.st.confirm_action("c1_iso")
        self.assertEqual(result, "result_value")
        self.assertEqual(called, ["yes"])
        self.assertFalse(self.st.has_pending_confirmations())

    def test_cancel_action(self):
        cb = MagicMock()
        self.st.request_confirmation("c2", "restart", "executor", cb)
        ok = self.st.cancel_action("c2")
        self.assertTrue(ok)
        self.assertFalse(self.st.has_pending_confirmations())
        cb.assert_not_called()  # cancelled, never invoked

    def test_string_status_coercion(self):
        """Regression: raw string status must be coerced to enum, not crash."""
        from core.models import AgentStatus
        self.st.update_agent_state("x", status="running", current_task="t")
        s = self.st.get_agent_state("x")
        self.assertIsNotNone(s)
        self.assertEqual(s.status, AgentStatus.RUNNING)
        # Must also be usable via .value (the original crash)
        self.assertEqual(s.status.value, "running")

    def test_conversation_counter(self):
        n0 = self.st.conversation_count
        self.st.record_conversation()
        self.assertEqual(self.st.conversation_count, n0 + 1)


class TestLLMClient(unittest.TestCase):
    """LLMClient with mocked HTTP transport — no Ollama needed."""

    def _make_client(self, response_data):
        from core.llm_client import LLMClient
        c = LLMClient()
        # Bypass singleton init guards
        resp = MagicMock()
        resp.json.return_value = response_data
        resp.raise_for_status.return_value = None
        c.session = MagicMock()
        c.session.post.return_value = resp
        c.session.get.return_value = resp
        return c

    def test_generate_extracts_response(self):
        c = self._make_client({"response": "  hello  "})
        out = c.generate("hi")
        self.assertEqual(out, "hello")

    def test_embed_returns_list(self):
        c = self._make_client({"embedding": [0.1, 0.2, 0.3]})
        emb = c.embed("text")
        self.assertEqual(emb, [0.1, 0.2, 0.3])

    def test_safe_json_parse_plain(self):
        from core.llm_client import LLMClient
        self.assertEqual(LLMClient._safe_json_parse('{"a": 1}'), {"a": 1})

    def test_safe_json_parse_fenced(self):
        from core.llm_client import LLMClient
        raw = "```json\n{\"a\": 1}\n```"
        self.assertEqual(LLMClient._safe_json_parse(raw), {"a": 1})

    def test_safe_json_parse_invalid_returns_raw(self):
        from core.llm_client import LLMClient
        out = LLMClient._safe_json_parse("not json")
        self.assertIn("raw_response", out)


if __name__ == "__main__":
    unittest.main(verbosity=2)
