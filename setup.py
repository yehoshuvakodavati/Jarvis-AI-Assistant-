#!/usr/bin/env python3
"""
Jarvis Installation and Setup Script
"""

import os
import sys
import subprocess
import platform


def print_header(text):
    print("\n" + "=" * 70)
    print(f"  {text}")
    print("=" * 70 + "\n")


def check_python():
    """Check if Python version is 3.8+"""
    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 8):
        print("❌ Python 3.8+ is required")
        return False
    print(f"✅ Python {version.major}.{version.minor} detected")
    return True


def install_dependencies():
    """Install required Python packages"""
    print_header("Installing Dependencies")
    
    requirements = [
        "requests>=2.28.0",
        "beautifulsoup4>=4.11.0"
    ]
    
    print("Installing packages...")
    for package in requirements:
        try:
            subprocess.check_call(
                [sys.executable, "-m", "pip", "install", package],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            print(f"✅ {package}")
        except subprocess.CalledProcessError:
            print(f"❌ Failed to install {package}")
            return False
    
    return True


def check_ollama():
    """Check if Ollama is installed and running"""
    print_header("Checking Ollama")
    
    try:
        import requests
        response = requests.get("http://localhost:11434/api/tags", timeout=2)
        if response.status_code == 200:
            print("✅ Ollama is running on localhost:11434")
            
            # Check for Mistral model
            try:
                models = response.json().get("models", [])
                mistral_found = any("mistral" in m.get("name", "").lower() for m in models)
                
                if mistral_found:
                    print("✅ Mistral model is installed")
                    return True
                else:
                    print("⚠️  Mistral model not found. Run: ollama pull mistral")
                    print("   Model will be pulled automatically on first use if specified")
                    return True
            except:
                return True
        else:
            print("❌ Ollama is not responding correctly")
            return False
    except requests.exceptions.ConnectionError:
        print("❌ Ollama is not running on localhost:11434")
        print("\n   Please install Ollama and start the server:")
        print("   1. Download: https://ollama.ai")
        print("   2. Run: ollama serve")
        print("   3. In another terminal: ollama pull mistral")
        return False
    except Exception as e:
        print(f"⚠️  Error checking Ollama: {str(e)}")
        return False


def create_venv():
    """Optionally create a virtual environment"""
    print_header("Virtual Environment")
    
    response = input("Create a virtual environment? (y/n): ").strip().lower()
    if response != "y":
        return True
    
    venv_name = "venv"
    try:
        subprocess.check_call([sys.executable, "-m", "venv", venv_name])
        print(f"✅ Virtual environment created: {venv_name}/")
        
        # Print activation instructions
        if platform.system() == "Windows":
            activate_cmd = f"{venv_name}\\Scripts\\activate"
        else:
            activate_cmd = f"source {venv_name}/bin/activate"
        
        print(f"\n   Activate with: {activate_cmd}")
        print(f"   Then run: pip install -r requirements.txt")
        return True
    except Exception as e:
        print(f"❌ Error creating venv: {str(e)}")
        return False


def test_system():
    """Run a simple test to verify everything works"""
    print_header("Testing System")
    
    try:
        from brain import ask_llm
        print("Testing LLM connection...")
        
        response = ask_llm("Say 'Hello' and nothing else.")
        
        if response:
            print(f"✅ LLM test successful!")
            print(f"   Response: {response[:50]}...")
            return True
        else:
            print("❌ LLM test failed - no response")
            return False
    except Exception as e:
        print(f"❌ Test failed: {str(e)}")
        return False


def main():
    """Main setup flow"""
    print_header("JARVIS Setup Wizard")
    
    # Check Python version
    if not check_python():
        sys.exit(1)
    
    # Create venv (optional)
    create_venv()
    
    # Install dependencies
    if not install_dependencies():
        print("\n❌ Dependency installation failed")
        sys.exit(1)
    
    # Check Ollama
    ollama_ok = check_ollama()
    
    # Summary
    print_header("Setup Summary")
    
    if ollama_ok:
        print("✅ All checks passed! System is ready.\n")
        print("Start Jarvis with: python main.py\n")
        
        response = input("Run Jarvis now? (y/n): ").strip().lower()
        if response == "y":
            try:
                from main import main
                main()
            except KeyboardInterrupt:
                print("\nGoodbye!")
    else:
        print("⚠️  Some requirements missing. Please fix and try again.\n")
        print("Quick checklist:")
        print("1. Install Ollama: https://ollama.ai")
        print("2. Run: ollama serve")
        print("3. Run: ollama pull mistral")
        print("4. Run: python setup.py")


if __name__ == "__main__":
    main()
