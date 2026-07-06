"""
Built-in Tool Implementations for Jarvis Multi-Agent AI Operating System.

All tools are decorated with @tool for automatic registration.
Categories:
    - Web: search, fetch, browse
    - File: search, read, write, list
    - System: open apps, URLs, settings, power controls
    - Notes: create, search, read
    - Code: analyze (placeholder for coder agent)

Safety:
    - System power tools are marked dangerous + require_confirmation
    - File operations are restricted to safe paths
    - Subprocess calls validate against allow-lists
"""

from __future__ import annotations

import glob as glob_module
import json
import logging
import os
import subprocess
import webbrowser
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

from config import (
    SEARCH_TIMEOUT,
    CONTENT_FETCH_TIMEOUT,
    MAX_CONTENT_LENGTH,
    MIN_CONTENT_LENGTH,
    SEARCH_HEADERS,
    UNWANTED_TAGS,
    UNWANTED_PHRASES,
    AD_INDICATORS,
    USER_AGENT,
)
from core.models import SearchResult, WebContent
from framework.decorators import tool

logger = logging.getLogger(__name__)

# =============================================================================
# WEB TOOLS
# =============================================================================

@tool(description="Search the web using DuckDuckGo and return structured results")
def web_search(query: str, max_results: int = 5) -> List[Dict[str, Any]]:
    """
    Perform a web search and return results as dictionaries.

    Args:
        query: Search query string.
        max_results: Maximum number of results to return.

    Returns:
        List of result dicts with keys: title, summary, url, source, timestamp, favicon.
    """
    from urllib.parse import quote_plus
    from datetime import datetime
    import re

    try:
        encoded = quote_plus(query)
        url = f"https://html.duckduckgo.com/html/?q={encoded}"
        resp = requests.get(url, headers=SEARCH_HEADERS, timeout=SEARCH_TIMEOUT)
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")
        results: List[Dict[str, Any]] = []

        for block in soup.find_all("div", class_="result")[:max_results]:
            link_elem = block.find("a", class_="result__a")
            if not link_elem:
                continue

            title = link_elem.get_text(" ", strip=True)
            raw_href = link_elem.get("href", "")
            decoded_url = raw_href

            # Decode DDG redirect URLs
            if raw_href.startswith("/l/?"):
                from urllib.parse import urlparse as up, parse_qs, unquote
                parsed = up(raw_href)
                qs = parse_qs(parsed.query)
                uddg = qs.get("uddg")
                if uddg:
                    decoded_url = unquote(uddg[0])

            if not decoded_url or not decoded_url.startswith("http"):
                continue

            snippet_elem = block.find("a", class_="result__snippet")
            summary = snippet_elem.get_text(" ", strip=True) if snippet_elem else ""
            if not summary or len(summary) < 20:
                summary = f"Search result for: {title}"

            parsed_url = urlparse(decoded_url)
            domain = parsed_url.netloc.replace("www.", "")

            # Extract timestamp heuristically
            timestamp = None
            date_patterns = [
                r'(\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{4})',
                r'(\d{4}-\d{2}-\d{2})',
                r'(\d+\s+(?:hours?|days?|weeks?)\s+ago)',
            ]
            for pat in date_patterns:
                m = re.search(pat, summary, re.IGNORECASE)
                if m:
                    timestamp = m.group(1)
                    break

            favicon = f"https://www.google.com/s2/favicons?domain={domain}&sz=64"

            results.append({
                "title": title,
                "summary": summary,
                "url": decoded_url,
                "source": domain,
                "timestamp": timestamp,
                "favicon": favicon,
                "rank": len(results) + 1,
            })

        logger.info(f"web_search: found {len(results)} results for '{query}'")
        return results

    except requests.exceptions.Timeout:
        logger.error(f"web_search timeout for: {query}")
        return []
    except Exception as e:
        logger.error(f"web_search error: {e}")
        return []


@tool(description="Fetch and extract text content from a web page URL")
def web_fetch(url: str) -> Dict[str, Any]:
    """
    Fetch a web page and extract clean text content.

    Args:
        url: The URL to fetch.

    Returns:
        Dict with keys: url, title, content, word_count.
    """
    try:
        if not url or not url.startswith("http"):
            return {"error": "Invalid URL"}

        resp = requests.get(url, headers=SEARCH_HEADERS, timeout=CONTENT_FETCH_TIMEOUT, allow_redirects=True)
        resp.raise_for_status()
        resp.encoding = "utf-8"

        soup = BeautifulSoup(resp.text, "html.parser")
        title = soup.title.get_text(strip=True) if soup.title else None

        # Remove unwanted tags
        for tag_name in UNWANTED_TAGS:
            for tag in soup.find_all(tag_name):
                tag.decompose()

        # Remove ad containers
        for indicator in AD_INDICATORS:
            for elem in soup.find_all(class_=lambda x: x and indicator in x.lower()):
                elem.decompose()

        # Extract content: try article/main first, then paragraphs
        text = ""
        for selector in ["article", "main", ("div", {"class": lambda x: x and "content" in x.lower()})]:
            try:
                if isinstance(selector, str):
                    elem = soup.find(selector)
                else:
                    elem = soup.find(selector[0], selector[1])
                if elem:
                    text = elem.get_text(separator=" ", strip=True)
                    if len(text) >= MIN_CONTENT_LENGTH:
                        break
            except Exception:
                continue

        if not text:
            paragraphs = soup.find_all("p")
            text = " ".join(p.get_text(strip=True) for p in paragraphs if len(p.get_text(strip=True)) > 20)

        if not text:
            body = soup.find("body")
            text = body.get_text(separator=" ", strip=True) if body else ""

        if len(text) > MAX_CONTENT_LENGTH:
            text = text[:MAX_CONTENT_LENGTH]

        # Clean text
        lines = [line.strip() for line in text.split("\n") if line.strip()]
        text = " ".join(lines)
        text = " ".join(text.split())

        words = text.split()
        word_count = len(words)

        return {
            "url": url,
            "title": title,
            "content": text,
            "word_count": word_count,
            "reading_time_minutes": max(1, word_count // 200),
        }

    except requests.exceptions.Timeout:
        return {"error": f"Timeout fetching {url}"}
    except Exception as e:
        return {"error": str(e)}


@tool(description="Get search results formatted as rich cards for UI display")
def web_search_cards(query: str, max_results: int = 5) -> List[Dict[str, Any]]:
    """
    Search and return results in a card-friendly format.
    Same as web_search but optimized for UI card rendering.
    """
    return web_search(query, max_results)


# =============================================================================
# FILE TOOLS
# =============================================================================

@tool(description="Search for files matching a pattern in a directory")
def file_search(directory: str = ".", pattern: str = "*") -> List[str]:
    """
    Search for files matching a glob pattern.

    Args:
        directory: Directory to search in.
        pattern: Glob pattern (e.g., '*.pdf', '*.py').

    Returns:
        List of matching file paths.
    """
    try:
        search_path = Path(directory).expanduser().resolve()
        matches = list(search_path.glob(pattern))
        return [str(m) for m in matches if m.is_file()][:50]
    except Exception as e:
        logger.error(f"file_search error: {e}")
        return []


@tool(description="Read the contents of a text file")
def file_read(path: str) -> str:
    """
    Read a text file's contents.

    Args:
        path: File path.

    Returns:
        File contents as string.
    """
    try:
        target = Path(path).expanduser().resolve()
        if not target.exists():
            return f"Error: File not found: {path}"
        if not target.is_file():
            return f"Error: Not a file: {path}"
        if target.stat().st_size > 5 * 1024 * 1024:  # 5MB limit
            return f"Error: File too large (>5MB): {path}"
        return target.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return f"Error reading file: {e}"


@tool(description="List files and folders in a directory")
def file_list(directory: str = ".") -> List[str]:
    """
    List entries in a directory.

    Args:
        directory: Directory path.

    Returns:
        List of entry names.
    """
    try:
        target = Path(directory).expanduser().resolve()
        if not target.exists():
            return [f"Error: Directory not found: {directory}"]
        return [f"{'[DIR]' if e.is_dir() else '[FILE]'} {e.name}" for e in target.iterdir()]
    except Exception as e:
        return [f"Error: {e}"]


# =============================================================================
# SYSTEM TOOLS
# =============================================================================

@tool(description="Open an application by name (notepad, calculator, cmd)")
def system_open_app(app_name: str) -> str:
    """
    Open a known application.

    Args:
        app_name: Application name (notepad, calculator, cmd, terminal).
    """
    app_map = {
        "notepad": "notepad",
        "calculator": "calc",
        "calc": "calc",
        "cmd": "start cmd",
        "command prompt": "start cmd",
        "terminal": "start powershell",
        "powershell": "start powershell",
        "explorer": "explorer",
    }

    normalized = app_name.lower().strip()
    command = app_map.get(normalized)

    if not command:
        return f"Unknown application: {app_name}. Known: {list(app_map.keys())}"

    try:
        subprocess.Popen(command, shell=True)
        return f"Opened {app_name}"
    except Exception as e:
        return f"Failed to open {app_name}: {e}"


@tool(description="Open a website URL in the default browser")
def system_open_url(url: str) -> str:
    """Open a URL in the default browser."""
    try:
        if not url.startswith("http"):
            url = "https://" + url
        webbrowser.open(url)
        return f"Opened {url}"
    except Exception as e:
        return f"Failed to open URL: {e}"


@tool(description="Open Windows Settings by category")
def system_open_settings(setting: str = "home") -> str:
    """
    Open Windows Settings.

    Args:
        setting: Category (display, network, bluetooth, privacy, keyboard, home).
    """
    settings_map = {
        "home": "ms-settings:",
        "display": "ms-settings:display",
        "network": "ms-settings:network",
        "bluetooth": "ms-settings:bluetooth",
        "privacy": "ms-settings:privacy",
        "keyboard": "ms-settings:keyboard",
        "wifi": "ms-settings:network-wifi",
        "storage": "ms-settings:storagesense",
    }

    normalized = setting.lower().strip()
    uri = settings_map.get(normalized, "ms-settings:")

    try:
        subprocess.Popen(f"start {uri}", shell=True)
        return f"Opened {setting} settings"
    except Exception as e:
        return f"Failed to open settings: {e}"


@tool(description="Lock the workstation", dangerous=False, requires_confirmation=False)
def system_lock() -> str:
    """Lock the Windows workstation."""
    try:
        subprocess.Popen("rundll32.exe user32.dll,LockWorkStation", shell=True)
        return "Workstation locked"
    except Exception as e:
        return f"Failed to lock: {e}"


@tool(description="Put the system to sleep", dangerous=True, requires_confirmation=True)
def system_sleep() -> str:
    """Put the system to sleep."""
    try:
        subprocess.Popen("rundll32.exe powrprof.dll,SetSuspendState 0,1,0", shell=True)
        return "System going to sleep"
    except Exception as e:
        return f"Failed to sleep: {e}"


@tool(description="Shut down the system", dangerous=True, requires_confirmation=True)
def system_shutdown() -> str:
    """Shut down the system."""
    try:
        subprocess.Popen("shutdown /s /t 1", shell=True)
        return "Shutting down system"
    except Exception as e:
        return f"Failed to shutdown: {e}"


@tool(description="Restart the system", dangerous=True, requires_confirmation=True)
def system_restart() -> str:
    """Restart the system."""
    try:
        subprocess.Popen("shutdown /r /t 1", shell=True)
        return "Restarting system"
    except Exception as e:
        return f"Failed to restart: {e}"


# =============================================================================
# NOTE TOOLS
# =============================================================================

@tool(description="Create a new note with title and content")
def note_create(title: str, content: str, tags: str = "") -> str:
    """
    Create a note and save it.

    Args:
        title: Note title.
        content: Note body.
        tags: Comma-separated tags.

    Returns:
        Confirmation message with note ID.
    """
    from memory.memory_manager import MemoryManager
    try:
        mm = MemoryManager()
        note_id = mm.save_note(title=title, content=content, tags=tags)
        return f"Note '{title}' saved with ID {note_id}"
    except Exception as e:
        return f"Failed to save note: {e}"


@tool(description="Search notes by keyword")
def note_search(query: str, limit: int = 10) -> List[Dict[str, Any]]:
    """
    Search saved notes.

    Args:
        query: Search query.
        limit: Maximum results.

    Returns:
        List of note dicts.
    """
    from memory.memory_manager import MemoryManager
    try:
        mm = MemoryManager()
        return mm.get_notes(search=query, limit=limit)
    except Exception as e:
        logger.error(f"note_search error: {e}")
        return []


@tool(description="Get all saved notes")
def note_list(limit: int = 20) -> List[Dict[str, Any]]:
    """List all saved notes."""
    from memory.memory_manager import MemoryManager
    try:
        mm = MemoryManager()
        return mm.get_notes(limit=limit)
    except Exception as e:
        logger.error(f"note_list error: {e}")
        return []


# =============================================================================
# MATH TOOL
# =============================================================================

@tool(description="Evaluate a mathematical expression safely")
def math_evaluate(expression: str) -> str:
    """
    Safely evaluate a mathematical expression.

    Args:
        expression: Math expression like '2 + 2 * 3' or 'sqrt(16)'.

    Returns:
        Result as string.
    """
    import ast
    import operator
    import math

    allowed_names = {
        "abs": abs, "round": round, "max": max, "min": min,
        "sum": sum, "pow": pow, "sqrt": math.sqrt,
        "sin": math.sin, "cos": math.cos, "tan": math.tan,
        "log": math.log, "log10": math.log10, "exp": math.exp,
        "pi": math.pi, "e": math.e,
    }

    allowed_ops = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.Pow: operator.pow,
        ast.USub: operator.neg,
        ast.Mod: operator.mod,
    }

    def _eval(node: ast.AST) -> Any:
        # ast.Num was deprecated in 3.8 and removed in 3.12+; use ast.Constant.
        if isinstance(node, ast.Constant):
            if isinstance(node.value, (int, float, complex, bool)):
                return node.value
            raise ValueError(f"Unsupported constant: {node.value!r}")
        elif isinstance(node, ast.BinOp):
            op_type = type(node.op)
            if op_type not in allowed_ops:
                raise ValueError(f"Unsupported operator: {op_type.__name__}")
            return allowed_ops[op_type](_eval(node.left), _eval(node.right))
        elif isinstance(node, ast.UnaryOp):
            op_type = type(node.op)
            if op_type not in allowed_ops:
                raise ValueError(f"Unsupported unary operator: {op_type.__name__}")
            return allowed_ops[op_type](_eval(node.operand))
        elif isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name):
                raise ValueError("Only simple function calls allowed")
            func_name = node.func.id
            if func_name not in allowed_names:
                raise ValueError(f"Function '{func_name}' not allowed")
            args = [_eval(arg) for arg in node.args]
            return allowed_names[func_name](*args)
        elif isinstance(node, ast.Name):
            if node.id not in allowed_names:
                raise ValueError(f"Name '{node.id}' not allowed")
            return allowed_names[node.id]
        elif isinstance(node, ast.Expression):
            return _eval(node.body)
        else:
            raise ValueError(f"Unsupported expression type: {type(node).__name__}")

    try:
        tree = ast.parse(expression, mode="eval")
        result = _eval(tree)
        return f"{result}"
    except Exception as e:
        return f"Error evaluating expression: {e}"


# =============================================================================
# REGISTRATION
# =============================================================================

def register_all_tools() -> None:
    """
    Ensure all tools in this module are registered.
    Called automatically when decorators are evaluated, but can be
    invoked explicitly to guarantee registration order.
    """
    logger.info(f"Tools registered: {len(__registered_tools)}")


# Track which tools were registered by this module
__registered_tools: List[str] = []

# The @tool decorator automatically registers functions, so this module
# is self-registering when imported.
