#!/usr/bin/env python3
"""
Debug script to test content extraction from a URL
"""

import logging
from tools.browser import fetch_page_content, get_first_link

# Setup logging to see everything
logging.basicConfig(
    level=logging.DEBUG,
    format='%(name)s - %(levelname)s - %(message)s'
)

print("=" * 70)
print("🔧 JARVIS Content Extraction Debugger")
print("=" * 70)

# Test 1: Search for a link
query = input("\nEnter search query: ").strip()

if not query:
    query = "Python programming"
    print(f"Using default query: {query}")

print(f"\n🔍 Searching for: {query}")
link = get_first_link(query)

if not link:
    print("❌ No link found!")
    exit(1)

print(f"✓ Found link: {link}\n")

# Test 2: Fetch content
print("=" * 70)
print("📄 Attempting content extraction...\n")

content = fetch_page_content(link)

print("\n" + "=" * 70)

if content:
    print(f"✅ SUCCESS! Extracted {len(content)} characters\n")
    print("📝 First 500 characters:")
    print("-" * 70)
    print(content[:500])
    print("-" * 70)
else:
    print("❌ FAILED! No content extracted.")
    print("\nTroubles hooting tips:")
    print("1. Try a different query")
    print("2. Check if the website is accessible")
    print("3. The website might block automated requests")
    print("4. Try Wikipedia queries (more reliable)")

print("\n" + "=" * 70)
