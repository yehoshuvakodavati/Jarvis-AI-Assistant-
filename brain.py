import requests
import json
import logging
from config import (
    OLLAMA_URL, OLLAMA_MODEL, OLLAMA_TIMEOUT,
    TEMP_JSON_MODE, TEMP_CONVERSATIONAL,
    SEARCH_KEYWORDS, LOG_LEVEL, MAX_BULLETS
)

# Setup logging
logging.basicConfig(level="DEBUG")
logger = logging.getLogger(__name__)
OLLAMA_URL = "http://localhost:11434/api/generate"
def call_model(model, prompt):
    try:
        response = requests.post(
            OLLAMA_URL,
            json={
                "model": model,
                "prompt": prompt,
                "stream": False,
            }
        )
        return response.json().get("response", "").strip()
        # response.raise_for_status()
        # data = response.json()
        # return data.get("response", "").strip()
    # except requests.exceptions.ConnectionError:
    #     logger.error("Cannot connect to Ollama. Make sure it's running on localhost:11434")
    #     return None
    # except requests.exceptions.Timeout:
    #     logger.error("Ollama request timed out")
    #     return None
    except Exception as e:
        return f"Error: {e}"
        # logger.error(f"Error communicating with Ollama: {str(e)}")
        # return None

def ask_jarvis(prompt, is_json=False):
    """
    Send a prompt to Ollama Mistral and get response.
    
    Args:
        prompt: The prompt text to send
        is_json: If True, expects JSON response
        
    Returns:
        str: The response from the LLM
    """
    prompt_lower = prompt.lower()

    # 🧠 CODE / TECH → better model
    if any(word in prompt_lower for word in [
        "code", "java", "python", "algorithm", "program"
    ]):
        return call_model("llama3", prompt)

    # ⚡ QUICK ANSWERS → fast model
    elif any(word in prompt_lower for word in [
        "who is", "what is", "when", "where"
    ]):
        return call_model("mistral", prompt)

    # 🧠 DEFAULT → smart model
    else:
        return call_model("llama3", prompt)
    
    # try:
    #     temperature = TEMP_JSON_MODE if is_json else TEMP_CONVERSATIONAL
        
    #     response = requests.post(
    #         OLLAMA_URL,
    #         json={
    #             "model": OLLAMA_MODEL,
    #             "prompt": prompt,
    #             "stream": False,
    #             "temperature": temperature
    #         },
    #         timeout=OLLAMA_TIMEOUT
    #     )
    #     response.raise_for_status()
    #     data = response.json()
    #     return data.get("response", "").strip()
    # except requests.exceptions.ConnectionError:
    #     logger.error("Cannot connect to Ollama. Make sure it's running on localhost:11434")
    #     return None
    # except requests.exceptions.Timeout:
    #     logger.error("Ollama request timed out")
    #     return None
    # except Exception as e:
    #     logger.error(f"Error communicating with Ollama: {str(e)}")
    #     return None


def decide_search_needed(user_query):
    """
    Decide if a web search is needed for this query.
    
    Args:
        user_query: The user's input
        
    Returns:
        bool: True if search is needed, False otherwise
    """
    
    query_lower = user_query.lower()
    
    # Rule-based override: Force search for summarization requests
    summarization_phrases = ["important points", "summary", "notes", "explain"]
    if any(phrase in query_lower for phrase in summarization_phrases):
        return True
    
    # Check for explicit search keywords
    if any(keyword in query_lower for keyword in SEARCH_KEYWORDS):
        return True
    
    # If query is a question (contains ?), likely needs search
    if "?" in user_query:
        return True
        
    return False


def generate_decision_prompt(user_query):
    """
    Generate a prompt to ask LLM if search is needed.
    
    Args:
        user_query: The user's input
        
    Returns:
        str: The prompt to send to LLM
    """
    return f"""You are Jarvis, an intelligent AI agent.

User query: "{user_query}"

Determine if this query requires a web search to provide a good answer.

Consider:
- Does the query ask for current information, facts, or explanations?
- Can you answer this from general knowledge?
- Would a web search improve the answer?

Respond with ONLY "yes" or "no" (lowercase, no punctuation)."""


def summarize_content(content):
    """
    Summarize web content into bullet points.
    
    Args:
        content: The cleaned text content to summarize
        
    Returns:
        list: List of bullet point strings
    """
    prompt = f"""You are an expert summarization assistant.

The input is cleaned page text. Ignore any ads, navigation, unrelated sidebars, metadata, or repeated content.
Extract only the most important learning points and key facts from this content.

Output requirements:
- Only bullet points
- Each point must start with "- "
- No numbering, no JSON, no headings, no explanations, no instructions
- No extra formatting or notes
- No repetition
- Keep each bullet concise and directly useful
- Prefer 5-7 bullets; if fewer are appropriate, use as many as needed

Content:
{content[:3000]}

Respond with only bullet points."""

    response = ask_jarvis(prompt)
    if not response:
        return []

    lines = [line.strip() for line in response.splitlines() if line.strip()]
    bullets = []
    for line in lines:
        if line.startswith("- ") or line.startswith("* ") or line.startswith("• ") or line.startswith("– ") or line.startswith("— "):
            normalized = line
            if not normalized.startswith("- "):
                normalized = "- " + normalized.lstrip("-*•–— ")
            bullets.append(normalized)
        elif line.startswith("-"):
            bullets.append("- " + line.lstrip("- "))

    if not bullets:
        # Fallback: convert plain lines or sentences into bullets
        candidate_lines = [line for line in lines if line]
        for line in candidate_lines:
            if len(bullets) >= MAX_BULLETS:
                break
            sanitized = line
            if not sanitized.startswith("- "):
                sanitized = "- " + sanitized
            bullets.append(sanitized)

    # Ensure bullets are clean and within limit
    cleaned_bullets = []
    for bullet in bullets:
        normalized = bullet.strip()
        if normalized.startswith("- "):
            cleaned_bullets.append(normalized)
        elif normalized.startswith("-"):
            cleaned_bullets.append("- " + normalized.lstrip("- "))

    return cleaned_bullets[:MAX_BULLETS]

def answer_query(user_query):
    """
    Generate a normal (non-search) answer to user query.
    
    Args:
        user_query: The user's input
        
    Returns:
        str: The response from the LLM
    """
    prompt = f"""You are Jarvis, a helpful AI assistant.

Answer this question clearly and concisely:
{user_query}

Keep response under 3 sentences."""

    response = ask_jarvis(prompt)
    return response if response else "I couldn't generate a response. Please try again."