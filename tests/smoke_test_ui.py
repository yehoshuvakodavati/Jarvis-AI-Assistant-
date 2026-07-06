"""
Runtime smoke test for the Jarvis UI startup path.

Exercises the exact code paths app.py hits on boot, WITHOUT requiring
Streamlit or Ollama to be running. Catches runtime errors that
py_compile cannot (attribute access, import-time side effects, etc.).

Run:  python tests/smoke_test_ui.py
"""

from __future__ import annotations

import os
import sys
import traceback
from pathlib import Path

# Ensure project root on path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# Keep the DB in a temp location so we don't touch the real jarvis.db
os.environ.setdefault("OLLAMA_BASE_URL", "http://127.0.0.1:1")  # unreachable → fast fail

PASS = 0
FAIL = 0


def check(name: str, fn) -> None:
    global PASS, FAIL
    try:
        fn()
        print(f"  [PASS] {name}")
        PASS += 1
    except Exception as e:
        print(f"  [FAIL] {name}: {type(e).__name__}: {e}")
        traceback.print_exc()
        FAIL += 1


# ---------------------------------------------------------------------------
# 1. Import layer — catches import-time errors across all UI deps
# ---------------------------------------------------------------------------

def test_imports():
    import ui.components  # noqa
    import core.state  # noqa
    import core.models  # noqa
    import core.registry  # noqa
    import core.message_bus  # noqa
    from core.models import AgentStatus, AgentMonitorState  # noqa


# ---------------------------------------------------------------------------
# 2. _status_str handles enum, string, None  (the crash regression)
# ---------------------------------------------------------------------------

def test_status_str():
    from ui.components import _status_str
    from core.models import AgentStatus
    assert _status_str(AgentStatus.RUNNING) == "running"
    assert _status_str("running") == "running"      # raw string must NOT crash
    assert _status_str(None) == "idle"
    assert _status_str(AgentStatus.IDLE) == "idle"


# ---------------------------------------------------------------------------
# 3. SystemState coerces a stray string status to enum  (root-cause guard)
# ---------------------------------------------------------------------------

def test_state_coerces_string_status():
    from core.state import SystemState
    from core.models import AgentStatus
    st = SystemState()
    # Simulate the OLD buggy call (raw string) — must not raise, must coerce
    st.update_agent_state("commander", status="running", current_task="t")
    s = st.get_agent_state("commander")
    assert s is not None
    # Must be usable both as enum and via .value
    assert s.status == AgentStatus.RUNNING
    assert s.status.value == "running"


# ---------------------------------------------------------------------------
# 4. render_agent_network runs with mixed/realistic states  (the crash site)
# ---------------------------------------------------------------------------

def test_render_network_with_states():
    from ui.components import render_agent_network
    from core.models import AgentMonitorState, AgentStatus
    states = [
        AgentMonitorState(agent_name="commander", status=AgentStatus.RUNNING, current_task="routing"),
        AgentMonitorState(agent_name="researcher", status=AgentStatus.IDLE),
    ]
    html = render_agent_network("commander", states, ai_state="thinking")
    assert isinstance(html, str)
    assert "<svg" in html
    assert "ACTIVE" in html  # active agent badge


def test_render_network_empty():
    from ui.components import render_agent_network
    html = render_agent_network(None, [], ai_state="idle")
    assert isinstance(html, str) and "<svg" in html


# ---------------------------------------------------------------------------
# 5. render_chat_message: user text is verbatim-escaped, not markdown-processed
# ---------------------------------------------------------------------------

def test_user_message_verbatim():
    from ui.components import render_chat_message
    # A user typing markdown must be escaped, not formatted
    out = render_chat_message("user", "**bold** and `code` and <script>")
    assert "<strong>" not in out          # no markdown bold applied
    assert "<span class=\"inline-code\"" not in out
    assert "&lt;script&gt;" in out        # HTML-escaped


def test_bot_message_codeblock():
    from ui.components import render_chat_message
    out = render_chat_message("bot", "Here:\n```python\ndef f():\n    return 1\n```")
    assert "code-block" in out
    assert "def" in out


# ---------------------------------------------------------------------------
# 6. All sidebar render functions produce strings without raising
# ---------------------------------------------------------------------------

def test_all_sidebar_renderers():
    from ui.components import (
        render_system_status_bar, render_agent_monitor,
        render_sidebar_agent_list, render_model_panel,
        render_execution_logs, render_data_stream,
        render_memory_panel, render_notes_viewer,
        render_search_cards, render_typing_indicator,
        render_voice_waveform,
    )
    from core.models import SystemHealth, AgentMonitorState, AgentStatus
    h = SystemHealth()
    assert isinstance(render_system_status_bar(h, llm_available=False), str)
    assert isinstance(render_agent_monitor("commander", "doing x"), str)
    assert isinstance(render_agent_monitor(None, None), str)
    states = [AgentMonitorState(agent_name="commander", status=AgentStatus.IDLE)]
    assert isinstance(render_sidebar_agent_list(states), str)
    assert isinstance(render_model_panel(), str)
    assert isinstance(render_execution_logs([]), str)
    assert isinstance(render_execution_logs([{"status": "completed", "agent_name": "x", "started_at": "2020-01-01 10:00:00", "task_description": "y"}]), str)
    assert isinstance(render_data_stream([]), str)
    assert isinstance(render_data_stream([{"timestamp": "2020-01-01 10:00:00", "source": "sys", "message": "hi"}]), str)
    assert isinstance(render_memory_panel({"conversations": 1, "memories": 2, "vectors": 3, "goals": 4}), str)
    assert isinstance(render_notes_viewer([]), str)
    assert isinstance(render_notes_viewer([{"title": "t", "content": "c"}]), str)
    assert isinstance(render_search_cards([{"title": "T", "summary": "S", "url": "http://x", "source": "x"}]), str)
    assert isinstance(render_typing_indicator("commander"), str)
    assert isinstance(render_voice_waveform(True), str)


# ---------------------------------------------------------------------------
# 7. format_bot_content edge cases
# ---------------------------------------------------------------------------

def test_format_bot_empty_and_url():
    from ui.components import format_bot_content
    assert format_bot_content("") == ""
    out = format_bot_content("see http://example.com here")
    assert "href=\"http://example.com\"" in out


# ---------------------------------------------------------------------------
# RUN
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("=" * 64)
    print("JARVIS UI RUNTIME SMOKE TEST")
    print("=" * 64)
    check("imports", test_imports)
    check("_status_str (enum/str/None)", test_status_str)
    check("SystemState coerces string status", test_state_coerces_string_status)
    check("render_agent_network with states", test_render_network_with_states)
    check("render_agent_network empty", test_render_network_empty)
    check("user message verbatim-escaped", test_user_message_verbatim)
    check("bot message code block", test_bot_message_codeblock)
    check("all sidebar renderers", test_all_sidebar_renderers)
    check("format_bot_content edges", test_format_bot_empty_and_url)
    print("-" * 64)
    print(f"RESULT: {PASS} passed, {FAIL} failed")
    sys.exit(1 if FAIL else 0)
