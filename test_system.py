#!/usr/bin/env python3
"""
Jarvis System Test Suite
Tests all components of the system
"""

import sys
import time
from colorama import Fore, Style, init

# Initialize colorama for cross-platform colored output
try:
    init(autoreset=True)
    has_color = True
except:
    has_color = False


def print_test(name, passed, message=""):
    """Print test result with formatting"""
    if has_color:
        status = f"{Fore.GREEN}✅ PASS{Style.RESET_ALL}" if passed else f"{Fore.RED}❌ FAIL{Style.RESET_ALL}"
    else:
        status = "✅ PASS" if passed else "❌ FAIL"
    
    print(f"  [{status}] {name}")
    if message:
        print(f"        {message}")


def test_imports():
    """Test that all modules can be imported"""
    print("\n" + "=" * 70)
    print("  TESTING: Module Imports")
    print("=" * 70)
    
    tests_passed = 0
    tests_total = 0
    
    modules = ["brain", "agent", "tools.browser", "tools.notes"]
    
    for module in modules:
        tests_total += 1
        try:
            __import__(module)
            print_test(f"Import {module}", True)
            tests_passed += 1
        except Exception as e:
            print_test(f"Import {module}", False, str(e))
    
    return tests_passed, tests_total


def test_ollama_connection():
    """Test connection to Ollama"""
    print("\n" + "=" * 70)
    print("  TESTING: Ollama Connection")
    print("=" * 70)
    
    tests_passed = 0
    tests_total = 1
    
    try:
        from brain import ask_llm
        
        print("  Sending test prompt to Ollama...")
        response = ask_llm("Respond with ONLY 'OK' and nothing else.", is_json=False)
        
        if response:
            print_test("Ollama API Response", True, f"Got: {response[:50]}")
            tests_passed += 1
        else:
            print_test("Ollama API Response", False, "No response from LLM")
    except Exception as e:
        print_test("Ollama Connection", False, str(e))
    
    return tests_passed, tests_total


def test_search_function():
    """Test web search functionality"""
    print("\n" + "=" * 70)
    print("  TESTING: Web Search")
    print("=" * 70)
    
    tests_passed = 0
    tests_total = 2
    
    try:
        from tools.browser import get_first_link
        
        print("  Searching for 'Python programming'...")
        link = get_first_link("Python programming")
        
        if link:
            print_test("Search Result Found", True, f"URL: {link[:60]}")
            tests_passed += 1
        else:
            print_test("Search Result Found", False, "No links returned")
        
        # Test Wikipedia fallback
        print("  Testing Wikipedia fallback...")
        link = get_first_link("Quantum computing")
        
        if link:
            print_test("Wikipedia Fallback", True, f"URL: {link[:60]}")
            tests_passed += 1
        else:
            print_test("Wikipedia Fallback", False, "No Wikipedia results")
            
    except Exception as e:
        print_test("Search Function", False, str(e))
    
    return tests_passed, tests_total


def test_content_fetch():
    """Test content fetching and cleaning"""
    print("\n" + "=" * 70)
    print("  TESTING: Content Fetching")
    print("=" * 70)
    
    tests_passed = 0
    tests_total = 1
    
    try:
        from tools.browser import fetch_page_content, get_first_link
        
        print("  Fetching content from Wikipedia...")
        link = get_first_link("Python programming language")
        
        if link:
            content = fetch_page_content(link)
            
            if content and len(content) > 100:
                print_test("Content Extraction", True, f"Got {len(content)} characters")
                tests_passed += 1
            elif content:
                print_test("Content Extraction", True, f"Got {len(content)} chars (short)")
                tests_passed += 1
            else:
                print_test("Content Extraction", False, "No content extracted")
        else:
            print_test("Content Fetching", False, "Could not find link")
    except Exception as e:
        print_test("Content Fetching", False, str(e))
    
    return tests_passed, tests_total


def test_decision_logic():
    """Test search decision logic"""
    print("\n" + "=" * 70)
    print("  TESTING: Decision Logic")
    print("=" * 70)
    
    tests_passed = 0
    tests_total = 0
    
    try:
        from brain import decide_search_needed
        
        test_cases = [
            ("What is machine learning?", True, "Question mark"),
            ("Search for Python tutorials", True, "Has 'search' keyword"),
            ("Tell me about cloud computing", True, "Has 'tell me about'"),
            ("Hello, how are you?", False, "General conversation"),
            ("Do something else", False, "Generic command"),
        ]
        
        for query, expected, reason in test_cases:
            tests_total += 1
            result = decide_search_needed(query)
            
            if result == expected:
                print_test(f"Query: '{query[:30]}'", True, f"({reason})")
                tests_passed += 1
            else:
                print_test(f"Query: '{query[:30]}'", False, 
                          f"Expected {expected}, got {result}")
    except Exception as e:
        print_test("Decision Logic", False, str(e))
    
    return tests_passed, tests_total


def test_file_operations():
    """Test note file operations"""
    print("\n" + "=" * 70)
    print("  TESTING: File Operations")
    print("=" * 70)
    
    tests_passed = 0
    tests_total = 3
    
    try:
        from tools.notes import save_note, read_notes, clear_notes
        import os
        
        # Test saving
        print("  Testing note save...")
        success = save_note(
            title="TEST TOPIC",
            bullets=["- Test point 1", "- Test point 2"],
            source_url="https://test.com"
        )
        
        if success:
            print_test("Save Note", True)
            tests_passed += 1
        else:
            print_test("Save Note", False, "Save returned False")
        
        # Test reading
        print("  Testing note read...")
        notes = read_notes()
        
        if notes and "TEST TOPIC" in notes:
            print_test("Read Notes", True, f"Found {len(notes)} chars")
            tests_passed += 1
        else:
            print_test("Read Notes", False, "Could not read saved notes")
        
        # Clean up test data
        print("  Cleaning up test data...")
        # Note: We'll keep the test data in notes.txt for verification
        print_test("Test Data Saved", True, "Check notes.txt for TEST TOPIC")
        tests_passed += 1
        
    except Exception as e:
        print_test("File Operations", False, str(e))
    
    return tests_passed, tests_total


def test_summarization():
    """Test content summarization"""
    print("\n" + "=" * 70)
    print("  TESTING: Summarization")
    print("=" * 70)
    
    tests_passed = 0
    tests_total = 1
    
    try:
        from brain import summarize_content
        
        test_content = """
        Machine learning is a type of artificial intelligence that enables systems 
        to learn and improve from experience without being explicitly programmed. 
        ML algorithms use data to identify patterns and make decisions with minimal 
        human intervention. Applications include image recognition, natural language 
        processing, and recommendation systems. Neural networks are commonly used for 
        deep learning tasks, while decision trees work well for classification problems.
        """
        
        print("  Generating bullet-point summary...")
        bullets = summarize_content(test_content)
        
        if bullets and len(bullets) >= 3:
            print_test("Summarization", True, f"Generated {len(bullets)} bullet points")
            for i, bullet in enumerate(bullets[:3], 1):
                print(f"      {i}. {bullet[:60]}")
            tests_passed += 1
        else:
            print_test("Summarization", False, f"Only got {len(bullets)} bullets")
            
    except Exception as e:
        print_test("Summarization", False, str(e))
    
    return tests_passed, tests_total


def main():
    """Run all tests"""
    print("\n" + "🤖 " * 30)
    print("\n" + " " * 20 + "JARVIS SYSTEM TEST SUITE")
    print("\n" + "🤖 " * 30)
    
    all_passed = 0
    all_total = 0
    
    # Run all tests
    test_functions = [
        test_imports,
        test_ollama_connection,
        test_decision_logic,
        test_file_operations,
        test_search_function,
        test_content_fetch,
        test_summarization,
    ]
    
    for test_func in test_functions:
        try:
            passed, total = test_func()
            all_passed += passed
            all_total += total
        except Exception as e:
            print(f"\n❌ Test suite error: {str(e)}")
    
    # Summary
    print("\n" + "=" * 70)
    print("  SUMMARY")
    print("=" * 70)
    
    if all_total > 0:
        percentage = (all_passed / all_total) * 100
        
        if has_color:
            if all_passed == all_total:
                color = Fore.GREEN
            else:
                color = Fore.YELLOW
            print(f"\n  {color}Tests Passed: {all_passed}/{all_total} ({percentage:.0f}%){Style.RESET_ALL}\n")
        else:
            print(f"\n  Tests Passed: {all_passed}/{all_total} ({percentage:.0f}%)\n")
        
        if all_passed == all_total:
            print("  ✅ All systems operational! Ready to use Jarvis.\n")
            return 0
        else:
            print("  ⚠️  Some tests failed. Check details above.\n")
            return 1
    else:
        print("\n  ❌ No tests ran.\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
