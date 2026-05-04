# 🤖 Jarvis - AI Agent System

A Python-based AI agent that performs intelligent web searches, content summarization, and note-taking using a local LLM.

## ✨ Features

- **Smart Decision Making**: Automatically determines if a web search is needed
- **Web Search & Scraping**: Uses DuckDuckGo (with Wikipedia fallback)
- **Content Cleaning**: Removes ads, scripts, navigation, and boilerplate text
- **AI Summarization**: Generates meaningful bullet points using Mistral LLM
- **Note Management**: Saves summaries with timestamps and source URLs
- **Error Handling**: Graceful fallbacks for network issues, empty content, and invalid responses
- **Local LLM**: Uses Ollama with Mistral model (no API costs)

## 🏗️ Architecture

```
jarvis/
├── main.py           → User interaction loop
├── brain.py          → LLM communication (Ollama Mistral)
├── agent.py          → Decision logic & pipeline orchestration
├── notes.txt         → Saved notes database
└── tools/
    ├── browser.py    → Web search & content fetching
    └── notes.py      → Note saving & retrieval
```

## 📋 Requirements

### System Requirements

- Python 3.8+
- Ollama running locally on port 11434
- Mistral model installed in Ollama: `ollama pull mistral`

### Python Dependencies

```bash
pip install -r requirements.txt
```

Required packages:

- `requests` - HTTP library
- `beautifulsoup4` - HTML parsing & content extraction

## 🚀 Quick Start

### 1. Install Ollama

Download from https://ollama.ai

### 2. Pull Mistral Model

```bash
ollama pull mistral
```

### 3. Start Ollama Server

```bash
ollama serve
```

The server will run on `http://localhost:11434`

### 4. Install Dependencies

```bash
cd c:\ProjectAgent\jarvis
pip install -r requirements.txt
```

### 5. Run Jarvis

```bash
python main.py
```

## 💬 Usage Examples

### Direct Question (No Search)

```
You: What is machine learning?
Jarvis: Machine learning is... [LLM response]
```

### Search & Summarize

```
You: Search for information about Python async programming
Jarvis: 📝 **Summary saved!** Here are the key points:
- Async programming enables concurrent execution...
- asyncio is Python's built-in async library...
✅ Notes saved to notes.txt
```

### View Saved Notes

```
You: notes
Jarvis: [Displays all saved notes with topics, dates, and sources]
```

### Exit

```
You: exit
Jarvis: Goodbye! 👋
```

## 🔧 Configuration

### Change Ollama URL (if not localhost:11434)

Edit `brain.py`:

```python
OLLAMA_URL = "http://your-host:11434/api/generate"
```

### Change Notes File Location

Edit `tools/notes.py`:

```python
NOTES_FILE = "/path/to/notes.txt"
```

### Adjust Search Behavior

Keywords that trigger search in `brain.py`:

```python
search_keywords = [
    "search", "look up", "find", "what is", "tell me about",
    "explain", "summary", "summarize", ...
]
```

## 🛡️ Error Handling

The system handles:

- ✅ Network timeouts (Ollama unreachable, search timeout)
- ✅ No search results found (fallback to Wikipedia, then error)
- ✅ Empty or invalid content (skip and report)
- ✅ LLM returning unparseable JSON (use fallback)
- ✅ File I/O errors (logging without crash)
- ✅ Invalid URLs and HTML parsing errors

## 📝 Output Format

Saved notes follow this structure:

```
======================================================================
TOPIC: Your search topic
DATE: 2024-01-15 14:32:45
SOURCE: https://example.com/article
======================================================================
- First key point
- Second key point
- Third key point


```

## 🔍 How It Works

### Decision Phase

1. Analyzes user query for search keywords
2. Checks for question marks and explicit search terms
3. Decides: Direct response OR Search+Summarize

### Search & Summarize Phase (if needed)

1. **Search**: DuckDuckGo finds first relevant link
2. **Fallback**: If DuckDuckGo fails, try Wikipedia
3. **Fetch**: Downloads page and extracts content with BeautifulSoup
4. **Clean**: Removes scripts, ads, navigation, boilerplate
5. **Summarize**: Sends to Mistral LLM for bullet points
6. **Save**: Stores formatted notes with metadata

### Direct Response Phase (if no search needed)

1. Sends query directly to Mistral LLM
2. Returns concise answer from general knowledge

## 🧪 Testing

Test the system:

```bash
# Test 1: Direct response
You: Tell me a joke

# Test 2: Search trigger
You: What is cloud computing?

# Test 3: Explicit search
You: Search for latest AI developments

# Test 4: View notes
You: notes

# Test 5: Exit
You: exit
```

## 📊 Logging

Enable debug logging by changing `brain.py`:

```python
logging.basicConfig(level=logging.DEBUG)
```

Logs show:

- Search queries and links found
- Content fetched (size)
- Bullet points generated
- Errors and fallbacks

## ⚠️ Troubleshooting

### "Cannot connect to Ollama"

- Ensure Ollama is running: `ollama serve`
- Check it's on localhost:11434
- Verify Mistral is installed: `ollama list`

### "No valid links found"

- Try different search terms
- Wikipedia fallback may work better for specific topics
- Some sites may block requests

### "Content too short"

- Page might have minimal text or heavy JavaScript
- Try a different search result
- Some paywalled content won't be accessible

### "LLM returning invalid JSON"

- Mistral model might be generating extra text
- Try a longer prompt context
- Restart Ollama server

## 📄 License

Open source - use freely.

## 🤝 Contributing

Improvements welcome! Consider adding:

- PDF content extraction
- YouTube transcript summarization
- Multi-language support
- Database backend for notes
- Web UI interface

---

**Happy researching with Jarvis!** 🚀
