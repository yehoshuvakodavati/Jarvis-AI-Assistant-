"""
One-Command Jarvis Voice Setup
Installs all dependencies: sounddevice, vosk, numpy, pyttsx3
NO PyAudio, NO compilation needed!
"""

import subprocess
import sys

def install_packages():
    """Install all Jarvis voice system dependencies."""
    
    packages = {
        "sounddevice": "Audio recording (replaces PyAudio)",
        "vosk": "Offline speech recognition",
        "numpy": "Audio processing",
        "pyttsx3": "Text-to-speech",
        "requests": "Web requests",
        "beautifulsoup4": "Web scraping",
        "colorama": "Colored output"
    }
    
    print("=" * 70)
    print("Jarvis Voice System - PackageInstaller")
    print("=" * 70)
    print("\nInstalling all dependencies...")
    print("(This may take 1-2 minutes on first run)\n")
    
    all_passed = True
    
    for package, description in packages.items():
        print(f"Installing {package:20} ... {description}")
        
        try:
            result = subprocess.run(
                [sys.executable, "-m", "pip", "install", "-q", package],
                capture_output=True,
                text=True,
                timeout=120
            )
            
            if result.returncode == 0:
                print(f"  ✅ {package} installed")
            else:
                print(f"  ⚠️  {package} installation issue")
                all_passed = False
                
        except Exception as e:
            print(f"  ❌ Error installing {package}: {e}")
            all_passed = False
    
    print("\n" + "=" * 70)
    
    if all_passed:
        print("✅ All packages installed successfully!")
        print("\nYou're ready to use Jarvis voice mode:")
        print("  python main_voice.py")
    else:
        print("⚠️  Some packages may not have installed correctly.")
        print("Try running manually:")
        print("  pip install sounddevice vosk numpy pyttsx3 requests beautifulsoup4 colorama")
    
    print("=" * 70)
    
    return all_passed


if __name__ == "__main__":
    success = install_packages()
    sys.exit(0 if success else 1)