# PyAudio Installation Guide for Windows

PyAudio is required for microphone access in the voice interface. Installation on Windows requires special handling.

## Solution 1: Using pipwin (Recommended)

`pipwin` provides pre-built PyAudio wheels for Windows:

```bash
# Install pipwin
pip install pipwin

# Install PyAudio via pipwin
pipwin install pyaudio
```

## Solution 2: Download Pre-built Wheels

If pipwin doesn't work, download pre-built wheels directly:

1. Go to: https://www.lfd.uci.edu/~gohlke/pythonlibs/#pyaudio
2. Download the `.whl` file matching your Python version and system (32-bit or 64-bit)
   - Example: `PyAudio‑0.2.13‑cp314‑cp314‑win_amd64.whl` for Python 3.14 64-bit
3. Install it:
   ```bash
   pip install PyAudio‑0.2.13‑cp314‑cp314‑win_amd64.whl
   ```

## Solution 3: Check Your Python Version

Verify your Python version and architecture:

```bash
python --version
python -c "import struct; print(struct.calcsize('P') * 8)"  # Output: 32 or 64
```

## Troubleshooting

If installation still fails:

1. **Update pip, setuptools, wheel:**

   ```bash
   pip install --upgrade pip setuptools wheel
   ```

2. **Use conda** (if you have Anaconda/Miniconda):

   ```bash
   conda install pyaudio
   ```

3. **Install Visual C++ Build Tools** (for compilation):
   - Download from Microsoft: https://visualstudio.microsoft.com/visual-cpp-build-tools/
   - Then try `pip install pyaudio` again

## Verify Installation

Once installed, verify it works:

```bash
python -c "import pyaudio; print('PyAudio installed successfully')"
```

## Alternative: Use Fallback Mode

If PyAudio cannot be installed, you can modify `voice.py` to use alternative audio libraries or skip microphone initialization for testing.
