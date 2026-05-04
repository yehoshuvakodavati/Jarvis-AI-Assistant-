# 🚀 Jarvis Quick Start Guide

## 30-Second Setup

```bash
# 1. Make sure Ollama is running in another terminal
ollama serve

# 2. Install dependencies (one time)
pip install -r requirements.txt

# 3. Run Jarvis
python main.py
```

## Common Commands

### Regular Questions (Auto-processes with LLM)

```
You: Tell me a joke
You: What's the capital of France?
You: How do I learn Python?
```

### Search & Summarize (Auto-triggered by keywords)

```
You: Search for machine learning
You: What is blockchain technology?
You: Find information about quantum computing
You: Explain climate change
```

### View Saved Notes

```
You: notes
```

### Exit

```
You: exit
```

---

## Prerequisites

✅ **Python 3.8+**
✅ **Ollama Running** (`ollama serve`)
✅ **Mistral Model** (`ollama pull mistral`)
✅ **Dependencies** (`pip install -r requirements.txt`)

---

## What Gets Installed

```
requests         → HTTP requests for web searching
beautifulsoup4   → HTML parsing and content extraction
colorama         → Colored console output (optional)
```

---

## File Locations

- **Notes**: `notes.txt` (created automatically)
- **Config**: `config.py` (customize here)
- **Logs**: Console output (can redirect)

---

## Typical Workflow

```
1. User asks question
2. System decides: Search needed?
   - YES: Do web search → fetch page → summarize → save notes
   - NO: Direct LLM response
3. Show result to user
4. Notes saved automatically
5. Repeat for next query
```

---

## Testing

Run the system test:

```bash
python test_system.py
```

Expected output:

- ✅ PASS for all modules and tests
- Confirms Ollama is working
- Validates search functionality
- Verifies summarization

---

## Customization

Edit `config.py` to change:

```python
# Ollama settings
OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "mistral"

# Timeouts (in seconds)
SEARCH_TIMEOUT = 10
CONTENT_FETCH_TIMEOUT = 15

# Content limits
MAX_CONTENT_LENGTH = 5000
MAX_BULLETS = 10

# LLM behavior
TEMP_JSON_MODE = 0.3
TEMP_CONVERSATIONAL = 0.7
```

---

## Example Session

```
🤖 JARVIS - AI Agent System
================================================

You: What is machine learning?
Jarvis: Processing...

Jarvis: Machine learning is a subset of artificial intelligence that...
[Direct LLM response - no search needed]

You: Search for Python async programming
Jarvis: Processing...

Jarvis: 📝 **Summary saved!** Here are the key points:
- Async programming enables concurrent code execution
- asyncio is Python's built-in async library
- Use 'async def' to define coroutines
- 'await' keyword pauses execution until completion
- Better for I/O-bound tasks than threading
- Event loop manages task scheduling

✅ Notes saved to notes.txt | Source: https://en.wikipedia.org/wiki/Asynchronous_I/O

You: notes
Jarvis: Retrieving your notes...

[Shows all saved notes with timestamps and sources]

You: exit
Jarvis: Goodbye! 👋
```

---

## Troubleshooting

### Error: "Cannot connect to Ollama"

→ Run `ollama serve` in another terminal

### Error: "No valid links found"

→ Try different search terms
→ Wikipedia fallback will be attempted

### Error: "LLM timeout"

→ Increase `OLLAMA_TIMEOUT` in config.py
→ Check Ollama server is responsive

### File permission errors

→ Ensure jarvis/ directory is writable
→ Check notes.txt permissions

---

## File Structure Explained

```
jarvis/
├── main.py              ← START HERE: User interaction
├── brain.py             ← LLM communication
├── agent.py             ← Decision & orchestration
├── config.py            ← EDIT HERE: Settings
├── notes.txt            ← Auto-created: Saved notes
├── tools/
│   ├── browser.py       ← Web search & fetching
│   └── notes.py         ← Note file management
├── README.md            ← Full documentation
├── setup.py             ← Installation wizard
└── test_system.py       ← Test suite
```

---

## Quick Config Changes

### Slower LLM? Increase timeout

```python
# config.py
OLLAMA_TIMEOUT = 120  # seconds
```

### Different Ollama location?

```python
# config.py
OLLAMA_URL = "http://192.168.1.100:11434/api/generate"
```

### Want longer summaries?

```python
# config.py
MAX_BULLETS = 15
SUMMARY_MAX_CHARS = 5000
```

### Disable certain search terms?

```python
# config.py
SEARCH_KEYWORDS = [
    "search", "look up", "find", "what is",
    # Remove terms you don't want
]
```

---

## Performance Tips

- First query takes longer due to LLM warmup
- Subsequent queries are faster
- Use specific search terms for better results
- Wikipedia fallback is reliable for general topics
- Local LLM averages 5-10 seconds per prompt

---

## Getting Help

Check these files:

- `README.md` - Full feature documentation
- `IMPLEMENTATION.md` - Technical details
- `config.py` - All configuration options
- `test_system.py` - Verify system health

---

## Common Use Cases

### Research Topic

```
You: Search for machine learning applications
→ Gets latest info → Saves to notes → Ready for review
```

### Learn Something New

```
You: What is blockchain?
→ LLM explains clearly → No search needed → Quick answer
```

### Build Knowledge Base

```
You: Search for [topic 1]
You: Search for [topic 2]
You: notes
→ Review all summaries together
```

### Daily Research

```
You: Search for latest AI news
You: Tell me about React hooks
You: Find information on cloud computing
→ Multiple topics saved in notes.txt
```

---

## Next Steps

1. ✅ Install dependencies: `pip install -r requirements.txt`
2. ✅ Start Ollama: `ollama serve`
3. ✅ Test system: `python test_system.py`
4. ✅ Run Jarvis: `python main.py`
5. ✅ Try a search: `Search for Python`
6. ✅ View notes: `notes` command

---

**Happy researching with Jarvis!** 🚀
