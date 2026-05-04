"""
Voice Test Mode - Simulates voice input for testing without PyAudio

Useful for testing the voice pipeline without microphone/speaker setup.
"""

import time
from agent import handle_query

def test_voice_pipeline():
    """
    Simulate voice commands and test the complete pipeline.
    """
    print("=" * 70)
    print("Jarvis Voice System - TEST MODE (No PyAudio Required)")
    print("=" * 70)
    print("\nThis simulates voice input for testing.")
    print("Commands will be sent to handle_query() as if spoken.\n")
    
    test_commands = [
        "What is artificial intelligence?",
        "Summarize quantum computing",
        "Give me important points about machine learning",
        "explain blockchain technology"
    ]
    
    for i, command in enumerate(test_commands, 1):
        print(f"\n{'='*70}")
        print(f"[TEST {i}] 🎤 Simulated Voice Input:")
        print(f'   "{command}"')
        print("=" * 70)
        
        print("\n⏳ Processing through handle_query()...")
        response = handle_query(command)
        
        print(f"\n📝 Response:\n{response}")
        
        if i < len(test_commands):
            print("\n(Waiting 2 seconds before next test...)")
            time.sleep(2)
    
    print(f"\n{'='*70}")
    print("✅ Test complete! All commands processed successfully.")
    print("=" * 70)
    print("\nOnce PyAudio is installed, run: python main_voice.py")
    print("PyAudio installation: https://www.lfd.uci.edu/~gohlke/pythonlibs/#pyaudio")


if __name__ == "__main__":
    test_voice_pipeline()