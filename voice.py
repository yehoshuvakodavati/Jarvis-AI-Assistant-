"""
Voice Interface using Faster-Whisper (High Accuracy)
Handles:
- Wake word (clap detection)
- Voice command input
- Text-to-speech output
"""

import sounddevice as sd
import numpy as np
from scipy.io.wavfile import write
import tempfile
import time
from faster_whisper import WhisperModel


class VoiceInterface:

    def __init__(self):
        print("Loading Whisper model...")
        self.model = WhisperModel(
             "base",
             device="cpu",
             compute_type="int8_float32"
        )  # change to small/medium for more accuracy
        print("Voice model ready!")

    # ---------------------------
    # 🔊 TEXT TO SPEECH
    # ---------------------------
    def speak(self, text):
        import pyttsx3

        clean_text = text.strip()
        print(f"Jarvis: {clean_text}")

        try:
            engine = pyttsx3.init()
            engine.setProperty('rate', 170)
            engine.setProperty('volume', 1.0)

            engine.say(clean_text)
            engine.runAndWait()
            engine.stop()

            time.sleep(0.2)

        except Exception as e:
            print("Voice error:", e)

    # ---------------------------
    # 👏 CLAP DETECTION
    # ---------------------------
    def listen_for_wake_word(self, timeout=5):
        print("Listening for clap wake word...")

        samplerate = 16000
        duration = timeout

        audio = sd.rec(int(samplerate * duration),
                       samplerate=samplerate,
                       channels=1,
                       dtype='int16')
        sd.wait()

        audio = np.abs(audio)

        threshold = 10000  # adjust if needed
        clap_times = []

        for i in range(len(audio)):
            if audio[i] > threshold:
                clap_times.append(i / samplerate)

        # detect two claps close together
        for i in range(len(clap_times) - 1):
            if 0.1 < clap_times[i+1] - clap_times[i] < 1.0:
                print("Clap detected!")
                return True

        return False

    # ---------------------------
    # 🎤 VOICE INPUT (WHISPER)
    # ---------------------------
    def listen_for_command(self):
        print("\nListening...")

        samplerate = 16000
        duration = 4  # seconds

        audio = sd.rec(int(duration * samplerate),
                       samplerate=samplerate,
                       channels=1)
        sd.wait()

        audio = (audio * 32767).astype(np.int16)

        # save temp file
        temp_file = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        write(temp_file.name, samplerate, audio)

        # transcribe
        segments, _ = self.model.transcribe(temp_file.name)

        text = ""
        for segment in segments:
            text += segment.text

        text = text.strip().lower()

        # 🔥 clean common noise words
        text = text.replace("jarvis", "").strip()

        print("You said:", text)

        # ignore useless input
        if len(text) < 2:
            return ""

        return text