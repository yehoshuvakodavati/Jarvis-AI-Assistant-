# Jarvis Voice System - NO PyAudio Setup Guide

## ✅ Clean Installation (Sound Device + Vosk)

### What You Get:

- **sounddevice** - Pure Python audio recording (no PyAudio!)
- **vosk** - Offline speech recognition (works without internet)
- **pyttsx3** - Text-to-speech (already installed)

### Step 1: Install Required Packages

```powershell
cd c:\ProjectAgent\jarvis
pip install sounddevice vosk numpy
```

**What each does:**

- `sounddevice` - Records audio from microphone (pure Python, no compilation)
- `vosk` - Recognizes speech offline (no Google API needed)
- `numpy` - Audio processing (dependency for sounddevice)

### Step 2: Verify Installation

```powershell
python -c "import sounddevice; print('✓ sounddevice OK')"
python -c "import vosk; print('✓ vosk OK')"
python -c "import pyttsx3; print('✓ pyttsx3 OK')"
```

All should print ✓ (checkmarks).

### Step 3: Run Jarvis Voice System

```powershell
python main_voice.py
```

**What happens:**

1. Jarvis says: "Jarvis voice interface activated. Say 'chinnu' to begin."
2. Says "Yes?" when wake word detected
3. Listens for your command
4. Searches web, summarizes, speaks response

### Step 4: Test It (Optional)

Test without actual voice first:

```powershell
python test_voice.py
```

This simulates voice commands and tests the full pipeline.

---

## 🔧 How It Works

**Audio Flow:**

```
Microphone → sounddevice.rec() → numpy array
    ↓
vosk.KaldiRecognizer → JSON result
    ↓
Extract text → send to handle_query()
    ↓
Response → pyttsx3 speaks it back
```

**Advantages vs PyAudio:**

- ✅ No compilation needed (pure Python)
- ✅ Works on Windows, Mac, Linux without wheels
- ✅ Offline speech recognition (vosk)
- ✅ No internet required for STT
- ✅ Fast installation

---

## 📋 Commands

| Command                | What it does                                |
| ---------------------- | ------------------------------------------- |
| `python main_voice.py` | Run Jarvis in voice mode                    |
| `python main.py`       | Run Jarvis in text mode                     |
| `python test_voice.py` | Test voice pipeline with simulated commands |

---

## ❌ Troubleshooting

### "ModuleNotFoundError: No module named 'sounddevice'"

```powershell
pip install sounddevice vosk numpy
```

### "Vosk model not found"

- Vosk auto-downloads the model on first run
- Make sure you have internet on first startup
- Wait 30 seconds - model downloads in background

### "No audio input device found"

```powershell
# List available audio devices:
python -c "import sounddevice; print(sounddevice.query_devices())"
```

### Speech not recognized (too quiet/noisy)

- Move closer to microphone
- Speak clearly and louder
- Check system volume is not muted
- Try: `python test_voice.py` first

---

## 🎯 You're All Set!

Run this command to start Jarvis voice mode:

```powershell
python main_voice.py
```

No PyAudio. No compilation. Pure Python. **Let's go!** 🚀
