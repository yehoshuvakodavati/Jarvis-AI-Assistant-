# Quick Reference - Command Listening System

## Quick Start

```bash
python main_voice.py
```

## Wake Word & Command Mode

### Say This:

```
User: "computer"
     ↓
System: [COMMAND MODE ACTIVE] "How can I help?"
     ↓
User: "Search for Python tutorials"
     ↓
System: [Processing...] "Here are the top tutorials..."
```

## Command Rules

### ✓ Valid Commands

- **Minimum**: 3 characters OR 1+ meaningful words
- **Examples**:
  - "help"
  - "what time is it"
  - "search for AI"
  - "give me 5 reasons why"

### ✗ Invalid Commands

- Empty ("" - just silence)
- Too short ("a", "hi" - less than 3 chars)
- Punctuation only ("!!!")

## If System Doesn't Understand

**Retry happens automatically (up to 2 times)**

| What Happens                | System Says            | Your Action          |
| --------------------------- | ---------------------- | -------------------- |
| No speech detected          | "Please speak clearly" | Speak louder/clearer |
| Partial input               | "Please speak clearly" | Continue speaking    |
| Still fails after 2 retries | "I didn't catch that"  | Say "computer" again |

## Tips for Best Results

1. **Wait for audio cue**: Listen for "How can I help?" before speaking
2. **Speak clearly**: Use normal volume and pace
3. **Complete sentences**: "Search for..." works better than just "search"
4. **Natural speech**: No need to be robotic
5. **One command at a time**: Ask one thing, wait for response

## Keyboard Commands

- **Ctrl+C**: Stop the system (shows statistics)
- **Speak normally**: Let the voice interface do its job

## Troubleshooting

| Issue                             | Solution                                   |
| --------------------------------- | ------------------------------------------ |
| Wake word not detected            | Speak clearly: "computer"                  |
| Command rejected                  | Make sure it's 3+ characters               |
| System says "I didn't catch that" | Try again after "computer"                 |
| Nothing happens                   | Wait for "How can I help?" before speaking |
| Repeated retries                  | Check microphone, try adjusting volume     |

## Session Info (after Ctrl+C)

```
Total listening attempts: 45
Successful activations: 8
Activation success rate: 17.8%
Commands processed: 6
Empty/unclear commands: 2
```

## File Overview

| File                         | Purpose                           |
| ---------------------------- | --------------------------------- |
| `main_voice.py`              | Main voice loop (run this)        |
| `voice.py`                   | Voice interface (STT/TTS engine)  |
| `test_command_listening.py`  | Test suite for command validation |
| `COMMAND_LISTENING_GUIDE.md` | detailed documentation            |

## Key Features

- ✅ Offline speech recognition (no internet)
- ✅ Wake word detection ("computer")
- ✅ Intelligent retry (auto-retry on unclear input)
- ✅ Silence/noise handling (smart filtering)
- ✅ No crashes (robust error handling)
- ✅ Real-time feedback (audio + visual)

## Next Level

- Edit `voice.py` to adjust timeout values
- Edit `agent.py` to add custom commands
- Use logging levels (DEBUG for troubleshooting)

---

**Status**: Ready to Use ✓
