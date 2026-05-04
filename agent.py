import logging
from numpy import power
from brain import (
    ask_jarvis, 
    decide_search_needed, 
    summarize_content, 
    answer_query
)
from tools.system_control import (
    open_application,
    open_website,
    open_settings,
    system_power
)
from tools.browser import get_first_link, fetch_page_content
from tools.notes import save_note
from tools.system_control import open_application, open_website, system_power, shutdown_system, restart_system
# Setup logging with more detail
logging.basicConfig(
    level=logging.DEBUG,
    format='%(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)
pending_action=None

def fast_knowledge(query):
    q = query.lower()

    # 🧮 Math (dynamic)
    try:
        if any(op in q for op in ["+", "-", "*", "/"]):
            result = eval(q)
            return f"Commander, the answer is {result}"
    except:
        pass

    return None
def fast_llm_answer(query):
    return ask_jarvis(
        f"Give a very short direct answer (1 sentence only): {query}"
    )
def classify_query(query):
    q = query.lower()

    if any(word in q for word in ["open", "shutdown", "restart"]):
        return "system"

    if any(word in q for word in ["search", "note", "summarize"]):
        return "search"

    if any(word in q.split()[0] for word in ["who", "what", "when", "where"]):
        return "question"

    return "general"

def handle_query(query):
    global pending_action

    q = query.lower()
    
    # ✅ HANDLE CONFIRMATION
    if pending_action:
        if q in ["yes", "confirm", "do it"]:
            action = pending_action
            pending_action = None
            return action()   # execute stored function
    
        elif q in ["no", "cancel"]:
            pending_action = None
            return "Commander, action cancelled"
    # ⚡ SYSTEM CONTROL FIRST

    app = open_application(query)
    if app:
        return app
    
    web = open_website(query)
    if web:
        return web
    settings = open_settings(query)
    if settings:
        return settings
    
    power = system_power(query)
    
    if power == "CONFIRM_SHUTDOWN":
        pending_action = shutdown_system()
        return "Commander, are you sure you want to shut down the system?"
    
    elif power == "CONFIRM_RESTART":
        pending_action = restart_system()
        return "Commander, are you sure you want to restart the system?"
    elif power:
        return power
    
    # ⚡ 1. Fast rule-based
    fast = fast_knowledge(query)
    if fast:
        return fast

    # 🧠 2. Intent detection
    intent = classify_query(query)

    # ⚡ 3. Routing
    if intent == "system":
        return system_power(query)

    elif intent == "search":
        return search_and_summarize(query)

    elif intent == "question":
        return fast_llm_answer(query)   # 🔥 FAST MODE

    else:
        return fast_llm_answer(query)


def search_and_summarize(query):
    """
    Execute the search, fetch, clean, summarize, and save pipeline.
    
    Args:
        query: The search query
        
    Returns:
        str: Summary or error message
    """
    
    # Step 1: Search for a link
    link = get_first_link(query)
    
    if not link:
        error_msg = "❌ No relevant links found. Try a different search term."
        return error_msg
    
    # Step 2: Fetch page content
    content = fetch_page_content(link)
    
    if not content:
        error_msg = "❌ Could not extract content from the page. It might be blocked or empty."
        return error_msg
    
    # Step 3: Summarize the content
    bullets = summarize_content(content)
    
    if not bullets:
        error_msg = "❌ Could not generate summary. The content might be invalid."
        return error_msg
    
    # Step 4: Save to notes
    success = save_note(
        title=query,
        bullets=bullets,
        source_url=link
    )
    
    if not success:
        error_msg = "⚠️ Summary generated but failed to save to notes.txt"
        return error_msg
    
    # Step 5: Return formatted summary
    summary_text = "📝 **Summary saved!** Here are the key points:\n\n"
    summary_text += "\n".join(bullets)
    summary_text += f"\n\n✅ Notes saved to notes.txt | Source: {link}"
    
    logger.info("Pipeline completed successfully")
    return summary_text