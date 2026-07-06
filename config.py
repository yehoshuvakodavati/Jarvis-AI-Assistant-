"""
Jarvis Multi-Agent AI Operating System - Configuration

Production-grade configuration with environment-aware defaults,
structured sections, and type-safe accessors.
"""

import os
from pathlib import Path
from typing import List, Dict, Any

# =============================================================================
# PATHS
# =============================================================================

BASE_DIR = Path(__file__).parent.resolve()
DATA_DIR = BASE_DIR / "data"
DATABASE_PATH = DATA_DIR / "jarvis.db"
VECTOR_INDEX_PATH = DATA_DIR / "vector_index"
LOGS_DIR = DATA_DIR / "logs"
NOTES_DIR = DATA_DIR / "notes"

# Ensure directories exist
for d in [DATA_DIR, LOGS_DIR, NOTES_DIR, VECTOR_INDEX_PATH]:
    d.mkdir(parents=True, exist_ok=True)

# =============================================================================
# OLLAMA / LLM SETTINGS
# =============================================================================

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_GENERATE_URL = f"{OLLAMA_BASE_URL}/api/generate"
OLLAMA_EMBED_URL = f"{OLLAMA_BASE_URL}/api/embeddings"
OLLAMA_TAGS_URL = f"{OLLAMA_BASE_URL}/api/tags"

OLLAMA_TIMEOUT = int(os.getenv("OLLAMA_TIMEOUT", "60"))
OLLAMA_MAX_RETRIES = int(os.getenv("OLLAMA_MAX_RETRIES", "3"))
OLLAMA_RETRY_DELAY = float(os.getenv("OLLAMA_RETRY_DELAY", "1.0"))

# Model assignments per capability
MODEL_COMMANDER = os.getenv("MODEL_COMMANDER", "llama3")
MODEL_PLANNER = os.getenv("MODEL_PLANNER", "llama3")
MODEL_RESEARCHER = os.getenv("MODEL_RESEARCHER", "llama3")
MODEL_CODER = os.getenv("MODEL_CODER", "llama3")
MODEL_CONVERSATIONAL = os.getenv("MODEL_CONVERSATIONAL", "mistral")
MODEL_EMBEDDING = os.getenv("MODEL_EMBEDDING", "nomic-embed-text")

# Temperature settings
TEMP_STRUCTURED = 0.2      # JSON, decisions, routing
TEMP_CONVERSATIONAL = 0.7  # General chat
TEMP_CREATIVE = 0.9        # Brainstorming, planning
TEMP_CODE = 0.3            # Code generation

# =============================================================================
# EMBEDDING SETTINGS
# =============================================================================

EMBEDDING_DIMENSION = int(os.getenv("EMBEDDING_DIMENSION", "768"))
EMBEDDING_BATCH_SIZE = int(os.getenv("EMBEDDING_BATCH_SIZE", "8"))
SIMILARITY_TOP_K = int(os.getenv("SIMILARITY_TOP_K", "5"))
SIMILARITY_THRESHOLD = float(os.getenv("SIMILARITY_THRESHOLD", "0.6"))

# =============================================================================
# WEB / SEARCH SETTINGS
# =============================================================================

SEARCH_TIMEOUT = int(os.getenv("SEARCH_TIMEOUT", "10"))
CONTENT_FETCH_TIMEOUT = int(os.getenv("CONTENT_FETCH_TIMEOUT", "15"))
MAX_CONTENT_LENGTH = int(os.getenv("MAX_CONTENT_LENGTH", "8000"))
MIN_CONTENT_LENGTH = int(os.getenv("MIN_CONTENT_LENGTH", "30"))
MAX_SEARCH_RESULTS = int(os.getenv("MAX_SEARCH_RESULTS", "8"))

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.0.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.0"
)

SEARCH_HEADERS: Dict[str, str] = {
    "User-Agent": USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Accept-Encoding": "gzip, deflate",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}

# Content extraction configuration
UNWANTED_TAGS = ["script", "style", "nav", "footer", "header", "form", "noscript", "aside", "iframe"]
AD_INDICATORS = ["ad", "advertisement", "banner", "sidebar", "widget", "popup", "ads", "sponsored"]
UNWANTED_PHRASES = [
    "click here", "read more", "subscribe", "advertisement",
    "sidebar", "cookie policy", "privacy policy", "terms of service",
    "all rights reserved", "copyright", "follow us", "share this",
    "comment", "newsletter", "sign up", "contact us", "related articles",
    "you may also like", "trending now", "sponsored content",
]

# =============================================================================
# MEMORY SETTINGS
# =============================================================================

MAX_CONVERSATION_HISTORY = int(os.getenv("MAX_CONVERSATION_HISTORY", "50"))
MEMORY_IMPORTANCE_THRESHOLD = float(os.getenv("MEMORY_IMPORTANCE_THRESHOLD", "0.3"))
AUTO_MEMORY_ENABLED = os.getenv("AUTO_MEMORY_ENABLED", "true").lower() == "true"

# =============================================================================
# LEARNING SETTINGS
# =============================================================================

LEARNING_ENABLED = os.getenv("LEARNING_ENABLED", "true").lower() == "true"
OUTCOME_ANALYSIS_INTERVAL_HOURS = int(os.getenv("OUTCOME_ANALYSIS_INTERVAL", "24"))
MIN_OUTCOMES_FOR_PATTERN = int(os.getenv("MIN_OUTCOMES_FOR_PATTERN", "3"))
CONFIDENCE_DECAY_RATE = float(os.getenv("CONFIDENCE_DECAY_RATE", "0.95"))

# =============================================================================
# AGENT SETTINGS
# =============================================================================

AGENT_EXECUTION_TIMEOUT = int(os.getenv("AGENT_EXECUTION_TIMEOUT", "120"))
MAX_AGENT_RETRIES = int(os.getenv("MAX_AGENT_RETRIES", "2"))
AGENT_MAX_TOOLS_PER_TASK = int(os.getenv("AGENT_MAX_TOOLS_PER_TASK", "10"))

# =============================================================================
# SAFETY SETTINGS
# =============================================================================

DANGEROUS_COMMANDS: List[str] = [
    "rm -rf", "del /f /s /q", "format", "rd /s /q", "rmdir /s /q",
    "shutdown /s /t 0", "shutdown /r /t 0", "poweroff", "halt",
    "mkfs", "dd if=", ":(){ :|:& };:", "> /dev/sda", "regsvr32",
]

REQUIRES_CONFIRMATION: List[str] = [
    "shutdown", "restart", "reboot", "sleep", "hibernate",
    "delete", "remove", "uninstall", "format",
]

# =============================================================================
# VOICE SETTINGS
# =============================================================================

VOICE_MODEL_SIZE = os.getenv("VOICE_MODEL_SIZE", "base")  # tiny, base, small, medium, large
VOICE_DEVICE = os.getenv("VOICE_DEVICE", "cpu")
VOICE_COMPUTE_TYPE = os.getenv("VOICE_COMPUTE_TYPE", "int8")
VOICE_SAMPLE_RATE = int(os.getenv("VOICE_SAMPLE_RATE", "16000"))
VOICE_RECORD_DURATION = int(os.getenv("VOICE_RECORD_DURATION", "5"))
VOICE_TTS_RATE = int(os.getenv("VOICE_TTS_RATE", "170"))
VOICE_WAKE_WORD_TIMEOUT = int(os.getenv("VOICE_WAKE_WORD_TIMEOUT", "5"))
VOICE_CLAP_THRESHOLD = int(os.getenv("VOICE_CLAP_THRESHOLD", "10000"))

# =============================================================================
# LOGGING
# =============================================================================

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FORMAT = "%(asctime)s | %(name)-20s | %(levelname)-8s | %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# =============================================================================
# UI SETTINGS
# =============================================================================

UI_PAGE_TITLE = "Jarvis AI Operating System"
UI_PAGE_ICON = "🤖"
UI_LAYOUT = "wide"
UI_THEME_COLOR = "#00d9ff"
UI_ACCENT_COLOR = "#b400ff"

# =============================================================================
# FILE ENCODING
# =============================================================================

DEFAULT_ENCODING = "utf-8"
NOTES_FILE_LEGACY = DATA_DIR / "notes_legacy.txt"
