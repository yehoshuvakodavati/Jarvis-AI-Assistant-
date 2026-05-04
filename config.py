"""
Configuration for Jarvis AI Agent System
"""

# ===== OLLAMA SETTINGS =====
OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "mistral"
OLLAMA_TIMEOUT = 60  # seconds

# ===== LLM TEMPERATURE SETTINGS =====
# Lower = more deterministic, Higher = more creative
TEMP_JSON_MODE = 0.3      # For structured responses
TEMP_CONVERSATIONAL = 0.7  # For normal chat

# ===== FILE SETTINGS =====
NOTES_FILE = "notes.txt"
ENCODING = "utf-8"

# ===== SEARCH SETTINGS =====
SEARCH_TIMEOUT = 10  # seconds per request
CONTENT_FETCH_TIMEOUT = 15  # seconds
MAX_CONTENT_LENGTH = 5000  # characters to fetch
MIN_CONTENT_LENGTH = 30  # minimum content to process (reduced for better extraction)

# ===== SUMMARIZATION SETTINGS =====
MAX_BULLETS = 10  # Maximum bullet points to generate
MIN_BULLETS = 3   # Minimum bullet points to attempt
SUMMARY_MAX_CHARS = 3000  # Content length for summarization

# ===== SEARCH KEYWORDS =====
# These trigger automatic web search
SEARCH_KEYWORDS = [
    "search", "look up", "find", "what is", "tell me about",
    "explain", "summary", "summarize", "recent", "latest",
    "news", "current", "how", "why", "information about",
    "research", "study", "fact", "definition", "meaning"
]

# ===== USER AGENT =====
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"

# ===== LOGGING LEVEL =====
# Options: DEBUG, INFO, WARNING, ERROR, CRITICAL
LOG_LEVEL = "INFO"

# ===== CONTENT CLEANING =====
# Phrases to remove from content
UNWANTED_PHRASES = [
    "click here", "read more", "subscribe", "advertisement",
    "sidebar", "cookie", "privacy policy", "terms of service",
    "all rights reserved", "copyright", "follow us", "share this",
    "comment", "newsletter", "sign up", "contact us"
]

# HTML Tags to remove
UNWANTED_TAGS = ["script", "style", "nav", "footer", "header", "form", "noscript"]

# Ad-related classes/IDs to remove
AD_INDICATORS = ["ad", "advertisement", "banner", "sidebar", "widget", "popup", "ads"]

# ===== CONTENT EXTRACTION SELECTORS =====
# Prioritized list of CSS selectors to find main content
CONTENT_SELECTORS = [
    "article",
    ("div", {"class": lambda x: x and "content" in x.lower()}),
    ("div", {"class": lambda x: x and "main" in x.lower()}),
    "main",
    ("div", {"id": lambda x: x and "content" in x.lower()})
]
