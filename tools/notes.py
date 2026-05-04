import os
import logging
from datetime import datetime
from config import NOTES_FILE, ENCODING, LOG_LEVEL

logging.basicConfig(level=LOG_LEVEL)
logger = logging.getLogger(__name__)


def save_note(title, bullets, source_url=None):
    """
    Save a note with title, bullet points, and optional source URL.
    
    Args:
        title: Title/topic of the note
        bullets: List of bullet point strings
        source_url: Optional source URL
        
    Returns:
        bool: True if saved successfully, False otherwise
    """
    try:
        # Build note content
        note_content = []
        note_content.append("=" * 70)
        note_content.append(f"TOPIC: {title}")
        note_content.append(f"DATE: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        if source_url:
            note_content.append(f"SOURCE: {source_url}")
        
        note_content.append("=" * 70)
        
        # Add bullet points
        if bullets and isinstance(bullets, list):
            for bullet in bullets:
                if bullet.strip():
                    # Ensure bullet starts with "- "
                    if not bullet.strip().startswith("-"):
                        note_content.append(f"- {bullet.strip()}")
                    else:
                        note_content.append(bullet.strip())
        else:
            note_content.append("- No bullet points generated")
        
        note_content.append("")
        note_content.append("")
        
        # Write to file with UTF-8 encoding
        with open(NOTES_FILE, "a", encoding=ENCODING) as f:
            f.write("\n".join(note_content))
        
        logger.info(f"Note saved: {title}")
        return True
        
    except IOError as e:
        logger.error(f"IO error while saving note: {str(e)}")
        return False
    except Exception as e:
        logger.error(f"Error saving note: {str(e)}")
        return False


def append_note(text):
    """
    Append raw text to notes file (legacy compatibility).
    
    Args:
        text: Text to append
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        with open(NOTES_FILE, "a", encoding=ENCODING) as f:
            f.write(text.strip() + "\n")
        return True
    except Exception as e:
        logger.error(f"Error appending to notes: {str(e)}")
        return False


def read_notes():
    """
    Read all notes from the file.
    
    Returns:
        str: Content of notes file or empty string if file doesn't exist
    """
    try:
        if os.path.exists(NOTES_FILE):
            with open(NOTES_FILE, "r", encoding=ENCODING) as f:
                return f.read()
        return ""
    except Exception as e:
        logger.error(f"Error reading notes: {str(e)}")
        return ""


def clear_notes():
    """
    Clear all notes from the file (with confirmation).
    
    Returns:
        bool: True if cleared successfully
    """
    try:
        if os.path.exists(NOTES_FILE):
            with open(NOTES_FILE, "w", encoding=ENCODING) as f:
                f.write("")
            logger.info("Notes cleared")
            return True
        return False
    except Exception as e:
        logger.error(f"Error clearing notes: {str(e)}")
        return False