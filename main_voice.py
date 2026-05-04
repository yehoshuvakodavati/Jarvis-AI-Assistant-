"""
Voice-Controlled Jarvis AI Assistant - Commander Mode
Clean + Fast + Stable Version
"""

import time
from voice import VoiceInterface
from agent import handle_query
import logging

logging.getLogger().setLevel(logging.CRITICAL)
logging.getLogger("comtypes").setLevel(logging.CRITICAL)
logging.getLogger("vosk").setLevel(logging.CRITICAL)
logging.getLogger("urllib3").setLevel(logging.CRITICAL)

def get_commander_action_description(command):
    command_lower = command.lower()

    if 'search' in command_lower:
        return "searching the web for your instructions"
    elif 'open' in command_lower and 'youtube' in command_lower:
        return "opening YouTube for you"
    elif 'note' in command_lower or 'write' in command_lower:
        return "taking notes on your instructions"
    elif 'summarize' in command_lower:
        return "summarizing the information for you"
    elif 'weather' in command_lower:
        return "checking the weather for you"
    else:
        return "executing your instruction"


def is_noise(text):
    return text.strip() in ["", "yes", "hmm", "ok"]


def main_voice_loop():
    try:
        voice = VoiceInterface()
    except Exception as e:
        print(f"Error initializing voice: {e}")
        return

    # ✅ Startup
    voice.speak("Initializing Agent")

    # ✅ Wake instruction
    print("\nWaiting for wake word...")
    voice.speak("Say Hey Jarvis to activate command mode")

    # 🔁 Wake loop
    while True:
        wake = voice.listen_for_wake_word()

        if wake:
            print("\n--- COMMAND MODE ACTIVATED ---")
            voice.speak("Command mode activated, waiting for commander instructions")

            command_mode_loop(voice)
            break


def command_mode_loop(voice):
    while True:
        print("\nListening...")

        command = voice.listen_for_command()

        if not command:
            continue

        print(f"You: {command}")

        if "exit" in command.lower():
            voice.speak("Commander, exiting command mode")
            break

        # Speak BEFORE action
        voice.speak("Commander, executing your instruction")

        response = handle_query(command)

        if response:
            print(f"Jarvis: {response}")
            if len(response) > 200 or "```" in response:
                voice.speak("Commander, I have displayed the result. Any other help you need?")
            else:
                voice.speak(response)


if __name__ == "__main__":
    main_voice_loop()