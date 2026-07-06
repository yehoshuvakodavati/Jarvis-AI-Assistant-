"""
JARVIS AI Operating System — Futuristic Dashboard v2.1
======================================================

Production-grade Streamlit dashboard featuring:
- Real-time agent network visualization with SMIL animations
- Syntax-highlighted code blocks in chat
- Animated typing indicator
- Voice waveform visualization
- Glassmorphism monitor panels with tech corner brackets
- Cached sidebar data for performance
- Model configuration panel
- Recent notes viewer

Run: streamlit run app.py
"""

from __future__ import annotations

import logging
import sys
import tempfile
from datetime import datetime
from pathlib import Path

root = Path(__file__).parent
sys.path.insert(0, str(root))

import streamlit as st

# =============================================================================
# LOGGING
# =============================================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)-20s | %(levelname)-8s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("requests").setLevel(logging.WARNING)


# =============================================================================
# PAGE CONFIG — Must be first Streamlit call
# =============================================================================

st.set_page_config(
    page_title="JARVIS AI Operating System",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)


# =============================================================================
# CSS INJECTION
# =============================================================================

try:
    css_path = root / "styles" / "style.css"
    with css_path.open("r", encoding="utf-8") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
except Exception as e:
    logger.warning(f"CSS load failed: {e}")


# =============================================================================
# SYSTEM INITIALIZATION (runs once per session)
# =============================================================================

if "jarvis_initialized" not in st.session_state:
    try:
        from orchestrator import initialize_system

        initialize_system()
        st.session_state.jarvis_initialized = True
        st.session_state.session_id = f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        st.session_state.messages = []
        st.session_state.cards = {}
        st.session_state.pending_query = None
        st.session_state.ai_state = "idle"
        st.session_state.voice_state = "idle"
        logger.info("🚀 Session initialized")
    except Exception as e:
        logger.error(f"Initialization failed: {e}")
        st.error(f"❌ Failed to initialize JARVIS: {e}")
        st.stop()


# =============================================================================
# IMPORTS
# =============================================================================

from core.state import SystemState
from core.message_bus import MessageBus
from core.llm_client import LLMClient
from memory.memory_manager import MemoryManager
from orchestrator import get_commander

from ui.components import (
    render_agent_network,
    render_agent_monitor,
    render_chat_message,
    render_data_stream,
    render_execution_logs,
    render_memory_panel,
    render_model_panel,
    render_notes_viewer,
    render_search_cards,
    render_sidebar_agent_list,
    render_system_status_bar,
    render_typing_indicator,
    render_voice_waveform,
)

system_state = SystemState()
bus = MessageBus()
memory = MemoryManager()


# =============================================================================
# CACHED DATA FETCHERS (reduce DB/network load on rerenders)
# =============================================================================

@st.cache_data(ttl=30)
def get_llm_health() -> bool:
    """Cache LLM health check to avoid network call on every rerun."""
    try:
        return LLMClient().check_health()
    except Exception:
        return False


@st.cache_data(ttl=3)
def get_sidebar_data() -> tuple:
    """Cache sidebar data with 3-second TTL for real-time feel without overload."""
    logs, stats, notes, events = [], {}, [], []
    try:
        logs = memory.store.get_recent_executions(limit=8)
    except Exception as e:
        logger.debug(f"Logs fetch: {e}")
    try:
        stats = memory.get_stats()
    except Exception as e:
        logger.debug(f"Stats fetch: {e}")
    try:
        notes = memory.get_notes(limit=5)
    except Exception as e:
        logger.debug(f"Notes fetch: {e}")
    try:
        events = bus.get_history(limit=6)
    except Exception as e:
        logger.debug(f"Events fetch: {e}")
    return logs, stats, notes, events


# =============================================================================
# STATUS BAR
# =============================================================================

llm_ok = get_llm_health()
health = system_state.get_health_snapshot()
health.llm_available = llm_ok
st.markdown(render_system_status_bar(health), unsafe_allow_html=True)


# =============================================================================
# AGENT NETWORK (Centerpiece)
# =============================================================================

agent_states = system_state.get_all_agent_states()
active_agent = system_state.active_agent
ai_state = st.session_state.get("ai_state", "idle")

st.markdown(
    render_agent_network(active_agent, agent_states, ai_state),
    unsafe_allow_html=True,
)


# =============================================================================
# PENDING QUERY PROCESSING
# =============================================================================

if st.session_state.pending_query:
    query = st.session_state.pending_query
    st.session_state.pending_query = None
    st.session_state.ai_state = "thinking"

    try:
        commander = get_commander()
        session_id = st.session_state.get("session_id", "default")

        response = commander.process_user_input(query, session_id=session_id)

        # response.agent_name is already the routed agent (set by BaseAgent)
        st.session_state.messages.append(("bot", response.response, response.agent_name))

        if response.data and response.data.get("cards"):
            msg_idx = len(st.session_state.messages) - 1
            st.session_state.cards[msg_idx] = response.data["cards"]

        system_state.record_conversation()

    except Exception as e:
        logger.exception(f"Query processing failed: {e}")
        st.session_state.messages.append(("bot", f"❌ I encountered an error: {str(e)}", None))
        system_state.set_last_error(str(e))

    st.session_state.ai_state = "idle"
    st.rerun()


# =============================================================================
# CHAT INTERFACE
# =============================================================================

st.markdown('<div class="chat-box">', unsafe_allow_html=True)

for i, msg_data in enumerate(st.session_state.messages):
    role = msg_data[0]
    content = msg_data[1]
    agent_name = msg_data[2] if len(msg_data) > 2 else None

    st.markdown(render_chat_message(role, content, agent_name), unsafe_allow_html=True)

    if i in st.session_state.cards:
        st.markdown(render_search_cards(st.session_state.cards[i]), unsafe_allow_html=True)

# Typing indicator while processing
if st.session_state.ai_state == "thinking":
    st.markdown(render_typing_indicator(active_agent), unsafe_allow_html=True)

st.markdown('</div>', unsafe_allow_html=True)


# =============================================================================
# VOICE INPUT + TEXT INPUT
# =============================================================================

voice_col, input_col = st.columns([0.10, 0.90])

with voice_col:
    # Waveform visualization
    voice_active = st.session_state.get("voice_state", "idle") != "idle"
    st.markdown(render_voice_waveform(active=voice_active), unsafe_allow_html=True)

    try:
        from streamlit_mic_recorder import mic_recorder

        audio = mic_recorder(
            start_prompt="🎙️",
            stop_prompt="⏹",
            just_once=True,
            key="jarvis_mic",  # static key prevents widget state loss
        )

        if audio and audio.get("bytes"):
            st.session_state.voice_state = "processing"
            try:
                from voice.interface import VoiceInterface

                voice = VoiceInterface()
                if voice.stt_available:
                    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                        f.write(audio["bytes"])
                        transcribed = voice.transcribe(f.name)

                    if transcribed and len(transcribed) > 1:
                        st.session_state.messages.append(("user", transcribed))
                        st.session_state.pending_query = transcribed
                        st.session_state.ai_state = "thinking"
                        st.session_state.voice_state = "idle"
                        st.rerun()
                    else:
                        st.toast("🎙️ Could not understand audio. Please try again.", icon="⚠️")
                        st.session_state.voice_state = "idle"
                else:
                    st.toast("🎙️ Voice recognition not available.", icon="⚠️")
                    st.session_state.voice_state = "idle"
            except Exception as e:
                logger.warning(f"Voice processing failed: {e}")
                st.toast("🎙️ Voice processing error.", icon="⚠️")
                st.session_state.voice_state = "idle"
    except ImportError:
        st.markdown(
            '<div style="color:#4a6078;font-size:10px;text-align:center;margin-top:4px;">Voice N/A</div>',
            unsafe_allow_html=True,
        )

with input_col:
    user_input = st.chat_input("Command JARVIS...")
    if user_input:
        st.session_state.messages.append(("user", user_input))
        st.session_state.pending_query = user_input
        st.session_state.ai_state = "thinking"
        st.rerun()


# =============================================================================
# SIDEBAR — MONITORING DASHBOARD
# =============================================================================

logs, stats, notes, events = get_sidebar_data()

with st.sidebar:
    # Active Task
    st.markdown(
        render_agent_monitor(active_agent, system_state.active_task_description),
        unsafe_allow_html=True,
    )

    # Agent Network List
    st.markdown(render_sidebar_agent_list(agent_states), unsafe_allow_html=True)

    # Model Configuration
    st.markdown(render_model_panel(), unsafe_allow_html=True)

    # Execution Logs
    st.markdown(render_execution_logs(logs), unsafe_allow_html=True)

    # Data Stream
    st.markdown(render_data_stream(events), unsafe_allow_html=True)

    # Memory Core
    st.markdown(render_memory_panel(stats), unsafe_allow_html=True)

    # Recent Notes
    st.markdown(render_notes_viewer(notes), unsafe_allow_html=True)

    st.markdown("---")

    # Session Controls
    if st.button("🗑️ Clear Session", use_container_width=True, key="clear_btn"):
        st.session_state.messages = []
        st.session_state.cards = {}
        st.session_state.ai_state = "idle"
        st.session_state.pending_query = None
        st.session_state.voice_state = "idle"
        bus.clear_history()
        st.rerun()

    st.caption(
        "💡 **Tip:** Type naturally — JARVIS routes to the best agent automatically.\n\n"
        "**Agents:** Commander · Planner · Researcher · Memory · Coder · Executor · Browser · File · Learner"
    )
