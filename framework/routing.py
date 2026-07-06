"""
Shared routing helpers for Jarvis agents.

Centralizes detection logic that was previously duplicated across agents:
- URL extraction (was in both executor.py and browser.py)
- Math expression detection (was in commander.py and old agent.py)
- Trivial-input classification (greetings, identity, farewells)

These are PURE FUNCTIONS — no LLM, no I/O. They are the small, well-defined
"fast path" that runs BEFORE the LLM-based intent parser in each agent.
The LLM parser remains the primary decision-maker; these helpers only
short-circuit unambiguous cases to save a round-trip.
"""

from __future__ import annotations

import re
from typing import Optional

# =============================================================================
# URL DETECTION (single source of truth)
# =============================================================================

# Matches http(s)://... or a bare domain like example.com/path
_URL_PATTERN = re.compile(
    r'(https?://[^\s<>"\']+|'                       # http:// or https://
    r'(?:[\w-]+\.)+(?:com|org|net|io|dev|co|edu|gov|ai|app)(?:/[^\s<>"\']*)?)',
    re.IGNORECASE,
)


def extract_url(text: str) -> Optional[str]:
    """
    Extract the first URL from text. Returns None if no URL found.

    Normalizes bare domains to https://.
    """
    if not text:
        return None
    m = _URL_PATTERN.search(text)
    if not m:
        return None
    url = m.group(1)
    if not url.startswith("http"):
        url = "https://" + url
    return url


def mentions_url(text: str) -> bool:
    """True if text contains any URL or bare domain."""
    return _URL_PATTERN.search(text or "") is not None


# =============================================================================
# MATH EXPRESSION DETECTION (single source of truth)
# =============================================================================

# A "pure" math expression: only digits, operators, parens, dots, commas, spaces
_PURE_MATH_PATTERN = re.compile(r'^\s*[\d\s+\-*/().,%^]+\s*$')
_HAS_OPERATOR = re.compile(r'[+\-*/^]')


def is_math_expression(text: str) -> bool:
    """
    True if text looks like a standalone arithmetic expression.

    Conservative: requires the WHOLE string to be math (no prose),
    and at least one operator. "2 + 2" → True; "what is 2 + 2" → False.
    """
    if not text or not _HAS_OPERATOR.search(text):
        return False
    return bool(_PURE_MATH_PATTERN.match(text.strip()))


# =============================================================================
# TRIVIAL INPUT CLASSIFICATION (single source of truth)
# =============================================================================

_GREETINGS = ("hello", "hi", "hey", "greetings", "good morning", "good afternoon", "good evening")
_IDENTITY = ("who are you", "what are you", "introduce yourself")
_THANKS = ("thanks", "thank you", "appreciate it", "thx")
_FAREWELLS = ("bye", "goodbye", "exit", "quit")
_WELLBEING = ("how are you", "how are you doing", "how's it going", "what's up")

_CONFIRM_YES = ("yes", "confirm", "do it", "proceed", "go ahead", "affirmative", "yep", "yeah")
_CONFIRM_NO = ("no", "cancel", "abort", "stop", "negative", "nope")


def classify_trivial(text: str) -> Optional[str]:
    """
    Classify trivially-answerable inputs without an LLM call.

    Returns one of: 'greeting', 'identity', 'thanks', 'farewell',
    'wellbeing', or None if the input is not trivial.
    """
    if not text:
        return None
    lower = text.lower().strip()

    if any(lower.startswith(g) for g in _GREETINGS):
        return "greeting"
    if lower in _IDENTITY:
        return "identity"
    if lower in _THANKS:
        return "thanks"
    if lower in _FAREWELLS:
        return "farewell"
    if lower in _WELLBEING:
        return "wellbeing"
    return None


def is_confirmation_yes(text: str) -> bool:
    """True if text is an affirmative confirmation."""
    return text.lower().strip() in _CONFIRM_YES


def is_confirmation_no(text: str) -> bool:
    """True if text is a negative/cancel confirmation."""
    return text.lower().strip() in _CONFIRM_NO


# =============================================================================
# INTENT PARSING VIA LLM (the reasoning-based replacement for keyword if/elif)
# =============================================================================

def parse_intent_via_llm(
    llm,
    prompt: str,
    valid_intents: list[str],
    *,
    model: str | None = None,
    temperature: float = 0.2,
) -> tuple[str, dict]:
    """
    Ask the LLM to classify an input into one of `valid_intents` and extract
    parameters, returning (intent, params).

    This is the shared reasoning primitive that replaces per-agent keyword
    if/elif chains. Each agent supplies its own prompt and valid intents.

    Falls back to (valid_intents[-1], {}) — the "general/default" intent —
    if the LLM fails or returns something unparseable. This means agents
    NEVER hard-fail on routing; they degrade to their default behavior.

    Args:
        llm: An LLMClient (or mock) with generate_structured().
        prompt: The full prompt to send.
        valid_intents: Allowed intent names. The LAST one is the fallback default.
        model: Optional model override.
        temperature: Low by default for deterministic classification.

    Returns:
        (intent, params) where intent is in valid_intents and params is a dict.
    """
    fallback = valid_intents[-1]
    try:
        parsed = llm.generate_structured(prompt, model=model, temperature=temperature)
    except Exception as e:
        # Import locally to avoid circulars in some test paths
        import logging
        logging.getLogger(__name__).warning(f"Intent parse LLM call failed: {e}")
        return fallback, {}

    if not isinstance(parsed, dict):
        return fallback, {}

    intent = str(parsed.get("intent", "")).strip().lower()
    if intent not in valid_intents:
        intent = fallback

    params = parsed.get("parameters", {})
    if not isinstance(params, dict):
        params = {}
    return intent, params
