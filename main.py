#!/usr/bin/env python3
"""
Jarvis - AI Agent System
Main entry point for user interaction
"""

import logging
from agent import handle_query

# Setup logging
logging.basicConfig(
    level=logging.WARNING,  # Only show warnings and errors in main loop
    format='%(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """Main interaction loop"""
    print("=" * 70)
    print("🤖 JARVIS - AI Agent System")
    print("=" * 70)
    print("Commands:")
    print("  - Type your query for a response")
    print("  - Type 'search: <query>' to search and summarize")
    print("  - Type 'notes' to see saved notes")
    print("  - Type 'exit' to quit")
    print("=" * 70)
    print()
    
    while True:
        try:
            user_input = input("You: ").strip()
            
            if not user_input:
                continue
            
            if user_input.lower() == "exit":
                print("Jarvis: Goodbye! 👋")
                break
            
            if user_input.lower() == "notes":
                print("\nJarvis: Retrieving your notes...\n")
                from tools.notes import read_notes
                notes = read_notes()
                if notes:
                    print(notes)
                else:
                    print("(No notes saved yet)")
                print()
                continue
            
            # Process the query
            print("\nJarvis: Processing...\n")
            response = handle_query(user_input)
            print(f"Jarvis: {response}\n")
            
        except KeyboardInterrupt:
            print("\n\nJarvis: Interrupted. Goodbye! 👋")
            break
        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}")
            print(f"Jarvis: An unexpected error occurred. Please try again.\n")


if __name__ == "__main__":
    main()