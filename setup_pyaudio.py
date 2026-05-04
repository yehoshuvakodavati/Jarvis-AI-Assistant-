"""
PyAudio setup helper for Windows
Attempts to install PyAudio using the best available method.
"""

import subprocess
import sys
import platform

def install_pyaudio():
    """
    Try to install PyAudio using multiple methods.
    """
    print("=" * 60)
    print("PyAudio Installation Helper for Windows")
    print("=" * 60)
    
    if platform.system() != "Windows":
        print("This script is for Windows. On Linux/Mac, use:")
        print("  pip install pyaudio  OR  pip install sounddevice")
        return False
    
    print(f"\nPython: {sys.version}")
    print(f"Architecture: {sys.maxsize > 2**32 and '64-bit' or '32-bit'}")
    
    # Method 1: Try pipwin
    print("\n[1/2] Attempting installation via pipwin...")
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "pipwin"],
            capture_output=True,
            timeout=30
        )
        if result.returncode == 0:
            print("✓ pipwin installed")
            print("[2/2] Installing PyAudio via pipwin...")
            result = subprocess.run(
                [sys.executable, "-m", "pipwin", "install", "pyaudio"],
                capture_output=True,
                timeout=60
            )
            if result.returncode == 0:
                print("✓ PyAudio installed successfully via pipwin!")
                return True
            else:
                print("✗ pipwin installation failed")
    except Exception as e:
        print(f"✗ Method 1 failed: {e}")
    
    # Method 2: Try standard pip
    print("\n[2/2] Attempting standard pip install...")
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "pyaudio"],
            capture_output=True,
            timeout=60
        )
        if result.returncode == 0:
            print("✓ PyAudio installed successfully!")
            return True
        else:
            print("✗ Standard pip install failed")
    except Exception as e:
        print(f"✗ Method 2 failed: {e}")
    
    # If all methods fail, provide manual instructions
    print("\n" + "=" * 60)
    print("MANUAL INSTALLATION REQUIRED")
    print("=" * 60)
    print("\nSince automatic installation failed, follow these steps:")
    print("\n1. Open: https://www.lfd.uci.edu/~gohlke/pythonlibs/#pyaudio")
    print(f"2. Download the .whl file for Python {sys.version_info.major}.{sys.version_info.minor}")
    print(f"   Architecture: {'64-bit' if sys.maxsize > 2**32 else '32-bit'}")
    print("3. Save it to your downloads folder")
    print(f"4. Run: pip install PATH\\TO\\PyAudio*.whl")
    print("\nOr use conda if you have it:")
    print("   conda install pyaudio")
    
    return False


if __name__ == "__main__":
    success = install_pyaudio()
    sys.exit(0 if success else 1)