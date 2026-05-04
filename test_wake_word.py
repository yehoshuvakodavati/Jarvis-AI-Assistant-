"""
Test and demonstrate improved wake word detection

Tests the new wake word detection system:
- Text normalization
- Multiple wake word variations
- Debug logging
- False trigger prevention
"""

import logging
from voice import VoiceInterface

# Setup logging with DEBUG level to see all detection details
logging.basicConfig(
    level=logging.DEBUG,
    format='%(levelname)-8s | %(message)s'
)
logger = logging.getLogger(__name__)


def test_wake_word_detection():
    """
    Test the improved wake word detection system.
    """
    
    print("=" * 70)
    print("Jarvis - Wake Word Detection Test")
    print("=" * 70)
    print()
    
    # Initialize voice interface
    try:
        voice = VoiceInterface()
    except Exception as e:
        print(f"Error initializing voice: {e}")
        return
    
    # Test cases: (input_text, should_trigger, description)
    test_cases = [
        # Positive cases - should trigger
        ("computer", True, "Exact match: computer"),
        ("Computer", True, "Capitalized: Computer"),
        ("COMPUTER", True, "All caps: COMPUTER"),
        ("computer please", True, "With extra words: computer please"),
        ("computer can you help", True, "Command-like: computer can you help"),
        
        # Negative cases - should NOT trigger
        ("hello world", False, "No wake word: hello world"),
        ("please help me", False, "No wake word: please help me"),
        ("my name is computer", False, "Computer in phrase but not activation"),
        ("i like computers", False, "Similar word but not exact: computers"),
        ("my friend jerry", False, "Similar sounding: jerry"),
        ("", False, "Empty string"),
        (None, False, "None value"),
    ]
    
    print("Running wake word detection tests...\n")
    
    wake_words = ["computer"]
    passed = 0
    failed = 0
    
    for input_text, should_trigger, description in test_cases:
        print(f"\nTest: {description}")
        print(f"Input: {input_text}")
        print("-" * 70)
        
        # Run detection
        is_detected = voice.check_wake_word(input_text, wake_words)
        
        # Check result
        if is_detected == should_trigger:
            status = "[PASS]"
            passed += 1
        else:
            status = "[FAIL]"
            failed += 1
        
        print(f"Expected: {should_trigger}, Got: {is_detected} - {status}")
    
    # Summary
    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)
    print(f"Total tests: {len(test_cases)}")
    print(f"Passed: {passed} [OK]")
    print(f"Failed: {failed} [FAIL]")
    
    if failed == 0:
        print("\n*** All tests passed! ***")
    else:
        print(f"\n*** {failed} test(s) failed ***")
    
    print("=" * 70)
    print()
    print("Wake word detection system ready for use!")
    print("Supported wake word: 'computer'")
    print("To use: python main_voice.py")
    print("=" * 70)


def demo_normalization():
    """
    Demonstrate text normalization.
    """
    print("\n" + "=" * 70)
    print("TEXT NORMALIZATION DEMO")
    print("=" * 70)
    
    voice = VoiceInterface()
    
    test_texts = [
        "Chinnu",
        "CHINNU!!",
        "chinnu",
        "Chinnu?",
        "JARVIS",
        "  jarvis  ",
    ]
    
    for text in test_texts:
        normalized = voice.normalize_text(text)
        print(f"\nOriginal:   '{text}'")
        print(f"Normalized: '{normalized}'")
    
    print("\n" + "=" * 70)


if __name__ == "__main__":
    # Run tests
    test_wake_word_detection()
    
    # Show normalization demo
    demo_normalization()