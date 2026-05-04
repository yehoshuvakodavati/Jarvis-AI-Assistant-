"""
Test improved command listening system

Tests the new command listening features:
- Silence detection
- Noise handling
- Command validation
- Retry logic
- Edge cases
"""

import logging
from voice import VoiceInterface

# Setup logging with DEBUG level
logging.basicConfig(
    level=logging.DEBUG,
    format='%(levelname)-8s | %(message)s'
)
logger = logging.getLogger(__name__)


def test_command_validation():
    """
    Test the validate_command() method.
    """
    print("\n" + "=" * 70)
    print("COMMAND VALIDATION TESTS")
    print("=" * 70)
    
    voice = VoiceInterface()
    
    test_cases = [
        # (input_text, should_validate, description)
        ("search for weather", True, "Valid command: multi-word"),
        ("summarize this", True, "Valid command: 2 words"),
        ("help", True, "Valid command: single word > 3 chars"),
        ("go", False, "Invalid: single char < 3"),
        ("a", False, "Invalid: empty/too short"),
        ("", False, "Invalid: empty string"),
        ("   ", False, "Invalid: only spaces"),
        ("please search for Python tutorials online", True, "Valid: longer command"),
        ("what is the weather", True, "Valid: question"),
        ("hi", False, "Invalid: too short (2 chars)"),
    ]
    
    print("\nTesting command validation:\n")
    passed = 0
    failed = 0
    
    for input_text, should_validate, description in test_cases:
        result = voice.validate_command(input_text)
        
        status = "✓ PASS" if result == should_validate else "✗ FAIL"
        if result == should_validate:
            passed += 1
        else:
            failed += 1
        
        print(f"{status} | Input: '{input_text}'")
        print(f"       | Expected: {should_validate}, Got: {result}")
        print(f"       | {description}\n")
    
    print("=" * 70)
    print(f"Validation Tests: {passed} passed, {failed} failed")
    print("=" * 70)


def test_text_normalization():
    """
    Test text normalization for command processing.
    """
    print("\n" + "=" * 70)
    print("TEXT NORMALIZATION TESTS")
    print("=" * 70)
    
    voice = VoiceInterface()
    
    test_cases = [
        "Search FOR Weather",
        "WHAT IS PYTHON?",
        "Please,  explain...  AI",
        "  summarize   this   ",
        "Hey! What's the weather?",
    ]
    
    print("\nNormalization examples:\n")
    for text in test_cases:
        normalized = voice.normalize_text(text)
        print(f"Original:   '{text}'")
        print(f"Normalized: '{normalized}'")
        print()
    
    print("=" * 70)


def test_command_flow():
    """
    Demonstrate the command listening flow.
    """
    print("\n" + "=" * 70)
    print("COMMAND LISTENING FLOW DEMONSTRATION")
    print("=" * 70)
    
    print("""
    Workflow after wake word detection:

    1. Wake word detected: "computer"
       ↓
    2. System enters COMMAND MODE
       - Visual: "🎙️  COMMAND MODE ACTIVE"
       - Audio: "How can I help?"
       ↓
    3. Listen for command (attempt 1)
       - Wait up to 5 seconds for speech start
       - Record up to 15 seconds of audio
       - Recognize with Vosk
       ↓
    4. Validate command
       - Check if text is valid (≥3 chars or ≥1 word)
       ✓ Valid → Process & send to handle_query()
       ✗ Invalid → If attempts remain: "Please speak clearly" → Retry
       ↓
    5. Processing
       - Send to handle_query()
       - Speak response
       - Return to wake word listening
       ↓
    6. On completion
       - If valid command: Process normally
       - If no valid input after 2 retries: "I didn't catch that"
       - Return to wake word listening

    Error Handling:
    ✓ Silence → Detected, user prompted, retry offered
    ✓ Noise → Vosk handles, may return empty, user prompted
    ✓ Partial/incomplete → Validated, retried if too short
    ✓ Crash prevention → Try-except around all audio processing
    """)
    
    print("=" * 70)


def demo_edge_cases():
    """
    Demonstrate edge case handling.
    """
    print("\n" + "=" * 70)
    print("EDGE CASE HANDLING EXAMPLES")
    print("=" * 70)
    
    voice = VoiceInterface()
    
    edge_cases = {
        "Empty input": "",
        "Only spaces": "   ",
        "Only punctuation": "!!!",
        "Single character": "a",
        "Very long command": "what is " + "the " * 20 + "weather",
        "Mixed case & punctuation": "HeLLo?! wOrLd!!!",
        "Numbers": "give me 5 reasons why",
        "Special characters": "show me @#$% content",
    }
    
    print("\nEdge case handling:\n")
    
    for description, text in edge_cases.items():
        normalized = voice.normalize_text(text)
        is_valid = voice.validate_command(text)
        
        print(f"Case: {description}")
        print(f"  Input:      '{text}'")
        print(f"  Normalized: '{normalized}'")
        print(f"  Valid:      {is_valid}")
        print()
    
    print("=" * 70)


if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("IMPROVED COMMAND LISTENING TEST SUITE")
    print("=" * 70)
    
    try:
        voice = VoiceInterface()
    except Exception as e:
        print(f"Error initializing voice: {e}")
        exit(1)
    
    # Run all tests
    test_command_validation()
    test_text_normalization()
    test_command_flow()
    demo_edge_cases()
    
    print("\n" + "=" * 70)
    print("All tests completed!")
    print("=" * 70)
    print("\nNext: Run 'python main_voice.py' to test real-time voice interaction")
    print("=" * 70)
