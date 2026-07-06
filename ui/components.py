"""
UI Components for Jarvis Multi-Agent AI Operating System v2.1.

Futuristic dashboard components:
- Agent network visualization (SVG with SMIL animations)
- System status bar with live metrics
- Agent monitor panels with tech corners
- Execution logs with color-coded status
- Data stream feed
- Memory core statistics
- Model configuration panel
- Notes viewer
- Chat messages with code blocks, markdown, avatars
- Typing indicator animation
- Voice waveform animation
- Search result cards (glassmorphism)
"""

from __future__ import annotations

import html
import re
from datetime import datetime
from typing import Any, Dict, List

from core.models import AgentMonitorState, SystemHealth
from config import (
    MODEL_COMMANDER, MODEL_CONVERSATIONAL, MODEL_CODER,
    MODEL_EMBEDDING, MODEL_PLANNER, MODEL_RESEARCHER,
    TEMP_CONVERSATIONAL,
)

# =============================================================================
# AGENT VISUAL CONFIG
# =============================================================================

AGENT_CONFIG: Dict[str, Dict[str, str]] = {
    "commander":    {"color": "#00f0ff", "icon": "🎯", "label": "Commander"},
    "planner":      {"color": "#b829dd", "icon": "📋", "label": "Planner"},
    "researcher":   {"color": "#0088ff", "icon": "🔍", "label": "Researcher"},
    "memory_agent": {"color": "#00ff88", "icon": "🧠", "label": "Memory"},
    "coder":        {"color": "#ffaa00", "icon": "💻", "label": "Coder"},
    "executor":     {"color": "#ff3366", "icon": "⚡", "label": "Executor"},
    "browser":      {"color": "#00cccc", "icon": "🌐", "label": "Browser"},
    "file_agent":   {"color": "#ffdd00", "icon": "📁", "label": "File"},
    "learner":      {"color": "#ff66cc", "icon": "📈", "label": "Learner"},
}

AGENT_POSITIONS: Dict[str, tuple[float, float]] = {
    "commander":    (260.0, 80.0),
    "planner":      (375.7, 122.1),
    "researcher":   (437.3, 228.8),
    "memory_agent": (415.9, 350.0),
    "coder":        (321.6, 429.1),
    "executor":     (198.4, 429.1),
    "browser":      (104.1, 350.0),
    "file_agent":   (82.7, 228.8),
    "learner":      (144.3, 122.1),
}

HUB_CENTER = (260.0, 260.0)


def _status_str(status_obj: Any | None) -> str:
    """Safely extract a status string from an enum or raw string."""
    if status_obj is None:
        return "idle"
    if hasattr(status_obj, "value"):
        return str(status_obj.value)
    return str(status_obj)


# =============================================================================
# CODE HIGHLIGHTING
# =============================================================================

def _highlight_code(code: str, language: str) -> str:
    """Basic regex-based syntax highlighting."""
    code = html.escape(code)
    lang = language.lower()

    # Common patterns
    if lang in ("python", "py"):
        kw = r"\b(def|class|return|if|else|elif|for|while|try|except|finally|import|from|as|with|yield|lambda|pass|break|continue|raise|assert|del|global|nonlocal|and|or|not|in|is|None|True|False|self|cls|async|await)\b"
        code = re.sub(kw, r'<span style="color:#569cd6;font-weight:600">\1</span>', code)
        code = re.sub(r"(f?'[^']*?'|f?\"[^\"]*?\")", r'<span style="color:#ce9178">\1</span>', code)
        code = re.sub(r"(#.*?)$", r'<span style="color:#6a9955">\1</span>', code, flags=re.MULTILINE)
        code = re.sub(r"\b(\d+\.?\d*)\b", r'<span style="color:#b5cea8">\1</span>', code)
        code = re.sub(r"\b([A-Z_]\w*)\b", r'<span style="color:#4ec9b0">\1</span>', code)
    elif lang in ("javascript", "js", "typescript", "ts", "java", "c", "cpp", "csharp", "cs"):
        kw = r"\b(function|const|let|var|return|if|else|for|while|try|catch|import|export|from|class|new|this|typeof|instanceof|undefined|null|true|false|async|await|public|private|protected|static|void|int|string|float|double|bool)\b"
        code = re.sub(kw, r'<span style="color:#569cd6;font-weight:600">\1</span>', code)
        code = re.sub(r"(['\"`].*?['\"`])", r'<span style="color:#ce9178">\1</span>', code)
        code = re.sub(r"(//.*?)$", r'<span style="color:#6a9955">\1</span>', code, flags=re.MULTILINE)
        code = re.sub(r"\b(\d+\.?\d*)\b", r'<span style="color:#b5cea8">\1</span>', code)
    elif lang in ("html", "xml"):
        code = re.sub(r"(&lt;/?)(\w+)", r'\1<span style="color:#569cd6">\2</span>', code)
        code = re.sub(r"(\s)(\w+)=", r'\1<span style="color:#9cdcfe">\2</span>=', code)
        code = re.sub(r"(=)(['\"].*?['\"])", r'=\1<span style="color:#ce9178">\2</span>', code)
    elif lang in ("css", "scss"):
        code = re.sub(r"([.#]\w+)", r'<span style="color:#d7ba7d">\1</span>', code)
        code = re.sub(r"(\w+):", r'<span style="color:#9cdcfe">\1</span>:', code)
        code = re.sub(r":\s*([^;]+);", r': <span style="color:#ce9178">\1</span>;', code)
    elif lang in ("sql", "mysql", "postgres"):
        kw = r"\b(SELECT|FROM|WHERE|INSERT|UPDATE|DELETE|JOIN|LEFT|RIGHT|INNER|OUTER|ON|GROUP|ORDER|BY|HAVING|LIMIT|OFFSET|CREATE|TABLE|DROP|ALTER|INDEX|VALUES|AND|OR|NOT|NULL|AS|DESC|ASC|DISTINCT|COUNT|SUM|AVG|MAX|MIN)\b"
        code = re.sub(kw, r'<span style="color:#569cd6;font-weight:600">\1</span>', code, flags=re.IGNORECASE)
        code = re.sub(r"('.*?')", r'<span style="color:#ce9178">\1</span>', code)
        code = re.sub(r"(--.*?)$", r'<span style="color:#6a9955">\1</span>', code, flags=re.MULTILINE)
    elif lang in ("bash", "sh", "shell", "zsh", "powershell", "ps1"):
        kw = r"\b(echo|if|then|else|fi|for|do|done|while|case|esac|function|return|exit|cd|ls|mkdir|rm|cp|mv|cat|grep|awk|sed|chmod|sudo|export|source)\b"
        code = re.sub(kw, r'<span style="color:#569cd6;font-weight:600">\1</span>', code)
        code = re.sub(r"(#.*?)$", r'<span style="color:#6a9955">\1</span>', code, flags=re.MULTILINE)
        code = re.sub(r"('.*?')", r'<span style="color:#ce9178">\1</span>', code)

    return code


# =============================================================================
# CONTENT FORMATTING (Markdown + Code Blocks)
# =============================================================================

def format_bot_content(content: str) -> str:
    """
    Format bot response with code block detection and markdown support.

    Pipeline:
        1. Extract fenced code blocks → placeholders
        2. HTML-escape remaining text
        3. Convert markdown (bold, italic, inline code, URLs)
        4. Convert newlines → <br>
        5. Restore code blocks with syntax highlighting
    """
    if not content:
        return ""

    code_blocks: List[tuple[str, str]] = []

    def extract_code(match: re.Match) -> str:
        lang = match.group(1) or "code"
        code = match.group(2)
        idx = len(code_blocks)
        code_blocks.append((lang, code))
        return f"__CODE_BLOCK_{idx}__"

    # Step 1: Extract code blocks
    text = re.sub(r"```(\w+)?\n(.*?)```", extract_code, content, flags=re.DOTALL)

    # Step 2: Escape HTML
    text = html.escape(text)

    # Step 3: Convert markdown
    # Bold
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    # Italic
    text = re.sub(r"\*(.+?)\*", r"<em>\1</em>", text)
    # Inline code
    text = re.sub(r"`(.+?)`", r'<span class="inline-code">\1</span>', text)
    # URLs
    url_pat = r"(https?://[^\s<>\"{}|\\^`\[\]]+)"
    text = re.sub(
        url_pat,
        r'<a href="\1" target="_blank" style="color:#00f0ff;text-decoration:none;border-bottom:1px dotted rgba(0,240,255,0.5);">\1</a>',
        text,
    )

    # Step 4: Newlines
    text = text.replace("\n", "<br>")

    # Step 5: Restore code blocks
    for idx, (lang, code) in enumerate(code_blocks):
        placeholder = f"__CODE_BLOCK_{idx}__"
        highlighted = _highlight_code(code, lang)
        block_html = (
            f'<div class="code-block">'
            f'<div class="code-block-header">'
            f'<span class="code-lang">{html.escape(lang.upper())}</span>'
            f'</div>'
            f'<pre><code>{highlighted}</code></pre>'
            f'</div>'
        )
        text = text.replace(placeholder, block_html, 1)

    return text


# =============================================================================
# AGENT NETWORK (SVG)
# =============================================================================

def render_agent_network(
    active_agent: str | None,
    agent_states: List[AgentMonitorState],
    ai_state: str = "idle",
) -> str:
    """Generate the agent network visualization as an SVG string."""
    state_map = {s.agent_name: s for s in agent_states}
    hub_color = AGENT_CONFIG.get(active_agent, {}).get("color", "#00f0ff") if active_agent else "#00f0ff"

    svg_parts: List[str] = []
    svg_parts.append('<div class="network-wrapper">')
    svg_parts.append('<svg viewBox="0 0 520 520" width="100%" height="auto" style="max-width:520px;" xmlns="http://www.w3.org/2000/svg">')

    # Definitions
    svg_parts.append("<defs>")
    svg_parts.append('  <radialGradient id="bgGrad" cx="50%" cy="50%" r="50%">')
    svg_parts.append('    <stop offset="0%" stop-color="rgba(0,40,80,0.5)"/>')
    svg_parts.append('    <stop offset="100%" stop-color="rgba(2,4,8,0)"/>')
    svg_parts.append('  </radialGradient>')
    svg_parts.append('  <filter id="hubGlow" x="-50%" y="-50%" width="200%" height="200%">')
    svg_parts.append('    <feGaussianBlur stdDeviation="14" result="blur"/>')
    svg_parts.append('    <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>')
    svg_parts.append('  </filter>')
    svg_parts.append('  <filter id="activeGlow" x="-50%" y="-50%" width="200%" height="200%">')
    svg_parts.append('    <feGaussianBlur stdDeviation="10" result="blur"/>')
    svg_parts.append('    <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>')
    svg_parts.append('  </filter>')
    svg_parts.append('  <pattern id="grid" width="40" height="40" patternUnits="userSpaceOnUse">')
    svg_parts.append('    <path d="M 40 0 L 0 0 0 40" fill="none" stroke="rgba(0,240,255,0.035)" stroke-width="1"/>')
    svg_parts.append('  </pattern>')
    svg_parts.append("</defs>")

    # Background layers
    svg_parts.append('<rect width="520" height="520" fill="url(#bgGrad)"/>')
    svg_parts.append('<rect width="520" height="520" fill="url(#grid)"/>')
    svg_parts.append('<radialGradient id="vignette" cx="50%" cy="50%" r="70%"><stop offset="60%" stop-color="transparent"/><stop offset="100%" stop-color="rgba(2,4,8,0.85)"/></radialGradient>')
    svg_parts.append('<rect width="520" height="520" fill="url(#vignette)"/>')

    # Connection lines
    for name, (ax, ay) in AGENT_POSITIONS.items():
        hx, hy = HUB_CENTER
        color = AGENT_CONFIG[name]["color"]
        is_active = name == active_agent
        opacity = 0.5 if is_active else 0.10
        sw = 2.5 if is_active else 1

        svg_parts.append(f'  <line x1="{hx}" y1="{hy}" x2="{ax}" y2="{ay}" stroke="{color}" stroke-width="{sw}" opacity="{opacity}" stroke-linecap="round"/>')

        if is_active:
            svg_parts.append(f'  <line x1="{hx}" y1="{hy}" x2="{ax}" y2="{ay}" stroke="{color}" stroke-width="2" stroke-dasharray="5,10" opacity="0.7" stroke-linecap="round">')
            svg_parts.append(f'    <animate attributeName="stroke-dashoffset" from="0" to="-15" dur="0.5s" repeatCount="indefinite"/>')
            svg_parts.append('  </line>')
            svg_parts.append(f'  <circle r="4" fill="{color}" filter="url(#activeGlow)">')
            svg_parts.append(f'    <animateMotion dur="1.0s" repeatCount="indefinite" path="M{hx},{hy} L{ax},{ay}"/>')
            svg_parts.append('  </circle>')

    # Central hub
    hx, hy = HUB_CENTER
    for i, r in enumerate([65, 85, 105]):
        op = 0.18 - i * 0.04
        svg_parts.append(f'  <circle cx="{hx}" cy="{hy}" r="{r}" fill="none" stroke="{hub_color}" stroke-width="1" opacity="{op}">')
        svg_parts.append(f'    <animate attributeName="r" values="{r};{r+12};{r}" dur="{2.5+i}s" repeatCount="indefinite"/>')
        svg_parts.append(f'    <animate attributeName="opacity" values="{op};{op*0.2};{op}" dur="{2.5+i}s" repeatCount="indefinite"/>')
        svg_parts.append('  </circle>')

    svg_parts.append(f'  <circle cx="{hx}" cy="{hy}" r="40" fill="rgba(2,4,8,0.95)" stroke="{hub_color}" stroke-width="2.5" filter="url(#hubGlow)"/>')
    svg_parts.append(f'  <circle cx="{hx}" cy="{hy}" r="30" fill="{hub_color}" opacity="0.12">')
    if ai_state == "listening":
        svg_parts.append('    <animate attributeName="r" values="30;38;30" dur="0.8s" repeatCount="indefinite"/>')
        svg_parts.append('    <animate attributeName="opacity" values="0.12;0.3;0.12" dur="0.8s" repeatCount="indefinite"/>')
    elif ai_state == "thinking":
        svg_parts.append('    <animate attributeName="r" values="30;36;30" dur="0.4s" repeatCount="indefinite"/>')
    svg_parts.append('  </circle>')
    svg_parts.append(f'  <text x="{hx}" y="{hy+3}" text-anchor="middle" fill="{hub_color}" font-size="12" font-weight="800" letter-spacing="3" font-family="Segoe UI,sans-serif">JARVIS</text>')

    state_colors = {"idle": "#3a5060", "listening": "#00f0ff", "thinking": "#b829dd", "speaking": "#00ff88"}
    sc = state_colors.get(ai_state, "#3a5060")
    svg_parts.append(f'  <circle cx="{hx}" cy="{hy+24}" r="3.5" fill="{sc}">')
    if ai_state != "idle":
        svg_parts.append('    <animate attributeName="opacity" values="1;0.2;1" dur="0.8s" repeatCount="indefinite"/>')
    svg_parts.append('  </circle>')

    # Agent nodes
    for name, (ax, ay) in AGENT_POSITIONS.items():
        cfg = AGENT_CONFIG[name]
        color = cfg["color"]
        icon = cfg["icon"]
        label = cfg["label"]
        state = state_map.get(name)
        status = _status_str(state.status) if state else "idle"
        is_active = name == active_agent
        opacity = 1.0 if is_active else 0.50
        node_r = 27 if is_active else 22

        svg_parts.append(f'  <g class="agent-group" transform="translate({ax}, {ay})">')

        if is_active:
            svg_parts.append(f'    <circle r="{node_r+10}" fill="none" stroke="{color}" stroke-width="2" opacity="0.35" filter="url(#activeGlow)">')
            svg_parts.append(f'      <animate attributeName="r" values="{node_r+10};{node_r+16};{node_r+10}" dur="1.2s" repeatCount="indefinite"/>')
            svg_parts.append(f'      <animate attributeName="opacity" values="0.35;0.08;0.35" dur="1.2s" repeatCount="indefinite"/>')
            svg_parts.append('    </circle>')

        svg_parts.append(f'    <circle class="agent-bg" r="{node_r}" fill="rgba(2,4,8,0.95)" stroke="{color}" stroke-width="{2.5 if is_active else 1}" opacity="{opacity}"/>')

        if status == "running":
            svg_parts.append(f'    <circle r="{node_r+3}" fill="none" stroke="#00ff88" stroke-width="2" opacity="0.55" stroke-dasharray="6,4">')
            svg_parts.append(f'      <animateTransform attributeName="transform" type="rotate" from="0" to="360" dur="2.5s" repeatCount="indefinite"/>')
            svg_parts.append('    </circle>')
        elif status == "error":
            svg_parts.append(f'    <circle r="{node_r+3}" fill="none" stroke="#ff3366" stroke-width="2" opacity="0.55"/>')

        svg_parts.append(f'    <text y="4" text-anchor="middle" font-size="15">{icon}</text>')
        svg_parts.append(f'    <text y="{node_r+15}" text-anchor="middle" fill="{color}" font-size="8" font-weight="700" letter-spacing="0.5" opacity="{0.9 if is_active else 0.55}">{label}</text>')

        if is_active:
            svg_parts.append(f'    <rect x="-20" y="-{node_r+18}" width="40" height="14" rx="7" fill="{color}" opacity="0.9"/>')
            svg_parts.append(f'    <text y="-{node_r+8}" text-anchor="middle" fill="#020408" font-size="7.5" font-weight="800" letter-spacing="1">ACTIVE</text>')

        svg_parts.append('  </g>')

    svg_parts.append('</svg>')
    svg_parts.append('</div>')
    return "\n".join(svg_parts)


# =============================================================================
# SYSTEM STATUS BAR
# =============================================================================

def render_system_status_bar(health: SystemHealth, llm_available: bool = False) -> str:
    """Render the top status bar."""
    now = datetime.now().strftime("%a, %b %d | %H:%M")
    llm_status = "ONLINE" if llm_available else "OFFLINE"
    llm_cls = "" if llm_available else "offline"
    sys_status = "OPTIMAL" if health.last_error is None else "DEGRADED"
    sys_cls = "" if health.last_error is None else "degraded"

    return (
        '<div class="status-bar">'
        '  <div class="status-left">'
        '    <span class="status-brand">JARVIS</span>'
        '    <div class="status-separator"></div>'
        '    <span class="status-subtitle">AI Orchestration Hub</span>'
        '  </div>'
        '  <div class="status-center">'
        f'    <div class="status-metric"><span class="status-metric-label">System</span><span class="status-metric-value {sys_cls}">{sys_status}</span></div>'
        f'    <div class="status-metric"><span class="status-metric-label">LLM</span><span class="status-metric-value {llm_cls}">{llm_status}</span></div>'
        f'    <div class="status-metric"><span class="status-metric-label">Agents</span><span class="status-metric-value">{health.active_agents}</span></div>'
        f'    <div class="status-metric"><span class="status-metric-label">Memory</span><span class="status-metric-value">{health.memory_entries}</span></div>'
        f'    <div class="status-metric"><span class="status-metric-label">Uptime</span><span class="status-metric-value">{health.uptime_seconds // 60}m</span></div>'
        '  </div>'
        '  <div class="status-right">'
        f'    <span class="status-datetime">{now}</span>'
        '  </div>'
        '</div>'
    )


# =============================================================================
# AGENT MONITOR (SIDEBAR)
# =============================================================================

def render_agent_monitor(active_agent: str | None, active_task: str | None) -> str:
    """Render the active agent monitor panel."""
    parts = ['<div class="monitor-panel tech-corner">', '  <div class="panel-header">', '    <span class="panel-title">▣ Active Task</span>', '  </div>']
    if active_agent:
        cfg = AGENT_CONFIG.get(active_agent, {"color": "#00f0ff", "icon": "🤖", "label": active_agent})
        task = html.escape(active_task[:55]) if active_task else "Processing request..."
        parts.append('  <div class="active-agent-highlight">')
        parts.append(f'    <div class="active-agent-pulse" style="background:{cfg["color"]};box-shadow:0 0 15px {cfg["color"]}90;"></div>')
        parts.append('    <div class="active-agent-details">')
        parts.append(f'      <h4>{cfg["icon"]} {cfg["label"]} Agent</h4>')
        parts.append(f'      <p>{task}</p>')
        parts.append('    </div>')
        parts.append('  </div>')
    else:
        parts.append('  <div style="text-align:center;padding:12px;color:#4a6078;font-size:12px;">')
        parts.append('    <div style="font-size:24px;margin-bottom:6px;">⦿</div>')
        parts.append('    All agents standing by')
        parts.append('  </div>')
    parts.append('</div>')
    return "\n".join(parts)


def render_sidebar_agent_list(agent_states: List[AgentMonitorState]) -> str:
    """Render the agent state list for the sidebar."""
    state_map = {s.agent_name: s for s in agent_states}
    active_count = len([s for s in agent_states if _status_str(s.status) == "running"])
    parts = ['<div class="monitor-panel tech-corner">', '  <div class="panel-header">', '    <span class="panel-title">◈ Agent Network</span>', f'    <span class="panel-badge">{active_count} Active</span>', '  </div>']
    for name, cfg in AGENT_CONFIG.items():
        state = state_map.get(name)
        status = _status_str(state.status) if state else "idle"
        task = html.escape(state.current_task[:40]) if state and state.current_task else "Idle"
        parts.append('  <div class="agent-state-row">')
        parts.append(f'    <div class="agent-icon">{cfg["icon"]}</div>')
        parts.append('    <div class="agent-info">')
        parts.append(f'      <span class="agent-name">{cfg["label"]}</span>')
        parts.append(f'      <span class="agent-task">{task}</span>')
        parts.append('    </div>')
        parts.append(f'    <div class="state-dot {status}"></div>')
        parts.append('  </div>')
    parts.append('</div>')
    return "\n".join(parts)


# =============================================================================
# MODEL PANEL
# =============================================================================

def render_model_panel() -> str:
    """Render LLM configuration panel."""
    models = [
        ("Commander", MODEL_COMMANDER),
        ("Conversational", MODEL_CONVERSATIONAL),
        ("Researcher", MODEL_RESEARCHER),
        ("Coder", MODEL_CODER),
        ("Planner", MODEL_PLANNER),
        ("Embeddings", MODEL_EMBEDDING),
    ]
    parts = ['<div class="monitor-panel tech-corner">', '  <div class="panel-header">', '    <span class="panel-title">◇ Model Core</span>', '  </div>']
    for label, value in models:
        parts.append('  <div class="model-row">')
        parts.append(f'    <span class="model-label">{label}</span>')
        parts.append(f'    <span class="model-value">{html.escape(value)}</span>')
        parts.append('  </div>')
    parts.append('  <div class="model-row">')
    parts.append('    <span class="model-label">Temperature</span>')
    parts.append(f'    <span class="model-value">{TEMP_CONVERSATIONAL}</span>')
    parts.append('  </div>')
    parts.append('</div>')
    return "\n".join(parts)


# =============================================================================
# NOTES VIEWER
# =============================================================================

def render_notes_viewer(notes: List[Dict[str, Any]]) -> str:
    """Render recent notes panel."""
    parts = ['<div class="monitor-panel tech-corner">', '  <div class="panel-header">', '    <span class="panel-title">◉ Recent Notes</span>', f'    <span class="panel-badge">{len(notes)}</span>', '  </div>']
    if not notes:
        parts.append('  <p style="color:#4a6078;font-size:11px;text-align:center;padding:10px;">No notes yet</p>')
    else:
        for note in notes[:5]:
            title = html.escape(note.get("title", "Untitled")[:30])
            preview = html.escape(note.get("content", "")[:40].replace("\n", " "))
            parts.append('  <div class="note-item">')
            parts.append(f'    <div class="note-title">📝 {title}</div>')
            parts.append(f'    <div class="note-preview">{preview}...</div>')
            parts.append('  </div>')
    parts.append('</div>')
    return "\n".join(parts)


# =============================================================================
# EXECUTION LOGS
# =============================================================================

def render_execution_logs(logs: List[Dict[str, Any]], limit: int = 8) -> str:
    """Render recent execution logs."""
    parts = ['<div class="monitor-panel tech-corner">', '  <div class="panel-header">', '    <span class="panel-title">◊ Execution Logs</span>', '  </div>']
    if not logs:
        parts.append('  <p style="color:#4a6078;font-size:11px;text-align:center;padding:10px;">No executions yet</p>')
    else:
        for log in logs[:limit]:
            status = log.get("status", "unknown")
            sc = "success" if status == "completed" else "failed" if status == "failed" else "running"
            ts = log.get("started_at", "")
            if ts:
                try:
                    ts = ts.split(" ")[-1][:5]
                except Exception:
                    ts = "--:--"
            agent = log.get("agent_name", "?")
            desc = html.escape(log.get("task_description", "")[:45] or "No description")
            parts.append('  <div class="log-entry">')
            parts.append(f'    <span class="log-timestamp">{ts}</span>')
            parts.append(f'    <span class="log-agent">{agent[:8]}</span>')
            parts.append(f'    <span class="log-message">{desc}</span>')
            parts.append(f'    <span class="log-status {sc}"></span>')
            parts.append('  </div>')
    parts.append('</div>')
    return "\n".join(parts)


# =============================================================================
# DATA STREAM
# =============================================================================

def render_data_stream(events: List[Dict[str, Any]], limit: int = 6) -> str:
    """Render real-time data stream."""
    parts = ['<div class="monitor-panel tech-corner">', '  <div class="panel-header">', '    <span class="panel-title">◐ Data Stream</span>', '    <span class="panel-badge" style="color:#00ff88;">● LIVE</span>', '  </div>', '  <div class="data-stream">']
    if not events:
        parts.append('    <p style="color:#4a6078;font-size:10px;text-align:center;padding:8px;">Waiting for events...</p>')
    else:
        for evt in events[:limit]:
            ts = evt.get("timestamp", "")
            if ts:
                try:
                    ts = ts.split(" ")[-1][:5]
                except Exception:
                    ts = "--:--"
            source = evt.get("source", "sys")
            msg = html.escape(str(evt.get("message", evt.get("data", "")))[:40])
            parts.append('    <div class="stream-item">')
            parts.append(f'      <span class="stream-time">{ts}</span>')
            parts.append(f'      <span class="stream-event">{source[:6]}</span>')
            parts.append('      <span class="stream-arrow">→</span>')
            parts.append(f'      <span class="stream-event">{msg}</span>')
            parts.append('    </div>')
    parts.append('  </div>')
    parts.append('</div>')
    return "\n".join(parts)


# =============================================================================
# MEMORY PANEL
# =============================================================================

def render_memory_panel(stats: Dict[str, Any]) -> str:
    """Render memory statistics panel."""
    parts = ['<div class="monitor-panel tech-corner">', '  <div class="panel-header">', '    <span class="panel-title">◈ Memory Core</span>', '  </div>', '  <div class="memory-grid">']
    metrics = [("Conv", stats.get("conversations", 0)), ("Mem", stats.get("memories", 0)), ("Vec", stats.get("vectors", 0)), ("Goals", stats.get("goals", 0))]
    for label, value in metrics:
        parts.append('    <div class="memory-stat">')
        parts.append(f'      <div class="memory-stat-value">{value}</div>')
        parts.append(f'      <div class="memory-stat-label">{label}</div>')
        parts.append('    </div>')
    parts.append('  </div>')
    parts.append('</div>')
    return "\n".join(parts)


# =============================================================================
# TYPING INDICATOR
# =============================================================================

def render_typing_indicator(agent_name: str | None = None) -> str:
    """Render animated typing dots."""
    label = "JARVIS"
    if agent_name and agent_name in AGENT_CONFIG:
        label = AGENT_CONFIG[agent_name]["label"]
    return (
        f'<div class="chat-message" style="margin-bottom:12px;">'
        f'  <div class="chat-avatar bot">🤖</div>'
        f'  <div class="chat-content">'
        f'    <div class="chat-meta"><span class="chat-sender">{label}</span><span class="chat-time">typing...</span></div>'
        f'    <div class="typing-indicator">'
        f'      <span></span><span></span><span></span>'
        f'    </div>'
        f'  </div>'
        f'</div>'
    )


# =============================================================================
# VOICE WAVEFORM
# =============================================================================

def render_voice_waveform(active: bool = True) -> str:
    """Render CSS-based audio waveform."""
    bars = "".join(f'<div class="bar" style="animation-play-state: {"running" if active else "paused"};opacity:{"1" if active else "0.3"};"></div>' for _ in range(8))
    return f'<div class="voice-waveform">{bars}</div>'


# =============================================================================
# CHAT MESSAGES
# =============================================================================

def render_chat_message(
    role: str,
    content: str,
    agent_name: str | None = None,
) -> str:
    """Render an enhanced chat message bubble with avatar, badges, code blocks."""
    if role == "user":
        # User messages are echoed verbatim — no markdown/code processing,
        # so their literal text is never re-interpreted as formatting.
        safe = html.escape(content).replace("\n", "<br>")
        return (
            f'<div class="chat-message">'
            f'  <div class="chat-avatar">🧑</div>'
            f'  <div class="chat-content">'
            f'    <div class="chat-meta"><span class="chat-sender">You</span></div>'
            f'    <div class="chat-body user">{safe}</div>'
            f'  </div>'
            f'</div>'
        )
    else:
        safe = format_bot_content(content)
        badge = ""
        avatar_emoji = "🤖"
        sender = "JARVIS"
        if agent_name and agent_name in AGENT_CONFIG:
            cfg = AGENT_CONFIG[agent_name]
            color = cfg["color"]
            avatar_emoji = cfg["icon"]
            sender = cfg["label"]
            badge = f'<div class="agent-badge" style="color:{color};border:1px solid {color}30;background:{color}10;">{sender} Agent</div>'
        return (
            f'<div class="chat-message">'
            f'  <div class="chat-avatar bot">{avatar_emoji}</div>'
            f'  <div class="chat-content">'
            f'    <div class="chat-meta"><span class="chat-sender">{sender}</span></div>'
            f'    {badge}<div class="chat-body bot">{safe}</div>'
            f'  </div>'
            f'</div>'
        )


# =============================================================================
# SEARCH CARDS
# =============================================================================

def render_search_cards(cards: List[Dict[str, Any]]) -> str:
    """Render search result cards."""
    if not cards:
        return '<div class="no-results">No results found.</div>'
    parts = ['<div class="search-cards-container">']
    for card in cards:
        title = html.escape(card.get("title", "Untitled"))
        summary = html.escape(card.get("summary", "")[:260])
        url = html.escape(card.get("url", "#"))
        source = html.escape(card.get("source", "unknown"))
        ts = html.escape(card.get("timestamp", "")) if card.get("timestamp") else ""
        favicon = card.get("favicon", "")
        ts_html = f'<span class="card-timestamp">{ts}</span>' if ts else ""
        fav_html = f'<img src="{favicon}" class="card-favicon" alt="" loading="lazy" onerror="this.style.display=\'none\'">' if favicon else ""
        parts.append(f'''
        <div class="search-card">
            <div class="card-header">
                {fav_html}
                <div class="card-meta">
                    <span class="card-source">{source}</span>
                    {ts_html}
                </div>
            </div>
            <h4 class="card-title">{title}</h4>
            <p class="card-summary">{summary}{"..." if len(card.get("summary","")) > 260 else ""}</p>
            <a href="{url}" target="_blank" class="card-link-button">
                <span>Open</span>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"></path><polyline points="15 3 21 3 21 9"></polyline><line x1="10" y1="14" x2="21" y2="3"></line></svg>
            </a>
        </div>
        ''')
    parts.append('</div>')
    return "\n".join(parts)
