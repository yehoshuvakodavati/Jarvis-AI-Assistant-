"""
One-line PyAudio installer for Windows Python 3.14 64-bit

This downloads and installs the pre-built PyAudio wheel from the trusted source.
"""

import subprocess
import sys
import urllib.request
import os
from pathlib import Path

def download_and_install():
    """Download and install PyAudio wheel for Python 3.14 Windows 64-bit."""
    
    print("=" * 70)
    print("PyAudio Installer for Windows (Python 3.14 64-bit)")
    print("=" * 70)
    
    # Verify Python version
    if sys.version_info < (3, 13):
        print("ERROR: Python 3.13+ is required")
        return False
    
    if sys.maxsize <= 2**32:
        print("ERROR: This script requires 64-bit Python")
        return False
    
    print(f"\n✓ Python version: {sys.version_info.major}.{sys.version_info.minor} 64-bit (compatible)")
    
    # Try to download from Christoph Gohlke's site (usually has wheels before PyPI)
    # For Python 3.14, fall back to 3.13 wheel if available
    wheel_options = [
        ("PyAudio-0.2.13-cp314-cp314-win_amd64.whl", "https://download.lfd.uci.edu/pythonlibs/static/PyAudio-0.2.13-cp314-cp314-win_amd64.whl"),
        ("PyAudio-0.2.13-cp313-cp313-win_amd64.whl", "https://download.lfd.uci.edu/pythonlibs/static/PyAudio-0.2.13-cp313-cp313-win_amd64.whl"),
        ("PyAudio-0.2.12-cp313-cp313-win_amd64.whl", "https://download.lfd.uci.edu/pythonlibs/static/PyAudio-0.2.12-cp313-cp313-win_amd64.whl"),
    ]
    
    wheel_path = None
    for wheel_name, wheel_url in wheel_options:
        print(f"\n📥 Trying {wheel_name}...")
        wheel_file = Path.home() / "Downloads" / wheel_name
        
        try:
            print(f"   Downloading from: {wheel_url}")
            urllib.request.urlretrieve(wheel_url, wheel_file)
            print(f"   ✓ Downloaded to: {wheel_file}")
            wheel_path = wheel_file
            break
        except Exception as e:
            print(f"   ✗ Failed: {e}")
            continue
    
    if not wheel_path:
        print("\n" + "=" * 70)
        print("MANUAL INSTALLATION REQUIRED")
        print("=" * 70)
        print("\nAutomatic download failed. Please manually install:\\n")
        print("1. Visit the Gohlke wheels site:")
        print("   https://www.lfd.uci.edu/~gohlke/pythonlibs/#pyaudio")
        print("\n2. Download the PyAudio wheel for your Python version:")
        print(f"   - Look for: PyAudio-0.2.13-cp314-cp314-win_amd64.whl (Python 3.14)")
        print(f"   - Or: PyAudio-0.2.13-cp313-cp313-win_amd64.whl (Python 3.13)")
        print("\n3. Save to Downloads folder, then run:")
        print("   pip install \"{path_to_downloads}/PyAudio-*.whl\"")
        print("   python -c \"import pyaudio; print('Success!')\"")
        return False
    
    # Install wheel
    print(f"\n📦 Installing {wheel_path.name}...")
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", str(wheel_path)],
            capture_output=True,
            text=True,
            timeout=60
        )
        
        if result.returncode == 0:
            print("✓ PyAudio installed successfully!")
            print("\n✅ You can now run: python main_voice.py")
            return True
        else:
            print(f"✗ Installation failed")
            print(result.stderr)
            return False
            
    except subprocess.TimeoutExpired:
        print("✗ Installation timed out")
        return False
    except Exception as e:
        print(f"✗ Installation error: {e}")


if __name__ == "__main__":
    success = download_and_install()
    sys.exit(0 if success else 1)