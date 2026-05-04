# Python 3.13 Setup Guide for Jarvis Voice System

## Why Python 3.13?

- PyAudio wheels readily available for 3.13 on Windows
- No compilation needed
- Fully compatible with your existing Jarvis code
- Simple one-time setup

## Step 1: Download Python 3.13

1. Go to: https://www.python.org/downloads/
2. Download **Python 3.13.x** (latest 3.13 version) for Windows 64-bit
3. Run the installer

## Step 2: Important - During Installation

**CHECK THIS BOX:**

- ✅ "Add Python 3.13 to PATH"

**Choose "Install Now" or "Customize Installation"** (either works)

## Step 3: Verify Installation

Open PowerShell and run:

```powershell
py -3.13 --version
```

Should output: `Python 3.13.x`

## Step 4: Install PyAudio for Python 3.13

```powershell
# Download PyAudio wheel for Python 3.13
# Go to: https://www.lfd.uci.edu/~gohlke/pythonlibs/#pyaudio
# Download: PyAudio‑0.2.13‑cp313‑cp313‑win_amd64.whl

# Install it:
py -3.13 -m pip install "C:\Users\YEHOSHUVA\Downloads\PyAudio‑0.2.13‑cp313‑cp313‑win_amd64.whl"
```

## Step 5: Install Jarvis Dependencies with Python 3.13

```powershell
cd C:\ProjectAgent\jarvis
py -3.13 -m pip install requests beautifulsoup4 pyttsx3 speech_recognition
```

## Step 6: Run Jarvis with Python 3.13

**Text Mode (existing):**

```powershell
py -3.13 main.py
```

**Voice Mode (new):**

```powershell
py -3.13 main_voice.py
```

**Test Mode (verify everything works):**

```powershell
py -3.13 test_voice.py
```

## Troubleshooting

### "py -3.13" not recognized

- Python 3.13 wasn't added to PATH during installation
- Reinstall and check "Add Python to PATH"
- Or use full path: `C:\Users\YEHOSHUVA\AppData\Local\Programs\Python\Python313\python.exe`

### PyAudio download link broken

- Visit: https://www.lfd.uci.edu/~gohlke/pythonlibs/#pyaudio
- Search for "PyAudio" on that page
- Download the cp313 version (Python 3.13)

### ModuleNotFoundError after install

```powershell
# Reinstall all dependencies
py -3.13 -m pip install --upgrade pip
py -3.13 -m pip install requests beautifulsoup4 pyttsx3 speech_recognition
```

## Keep Multiple Python Versions

You can safely keep Python 3.14 AND Python 3.13 on your system:

- Python 3.14: `py -3.14 main.py` (text mode)
- Python 3.13: `py -3.13 main_voice.py` (voice mode)

Once Python 3.13 is set up, just let me know and I'll help you test the voice system!
