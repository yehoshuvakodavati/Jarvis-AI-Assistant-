"""
Test the clap-based wake word detection algorithm.
"""

import numpy as np
from unittest.mock import patch
from voice import VoiceInterface


class DummyEngine:
    def setProperty(self, name, value):
        pass

    def say(self, text):
        pass

    def runAndWait(self):
        pass


def generate_synthetic_clap_audio(sample_rate=16000, duration=2, clap_times=(0.5, 1.0), clap_width=0.01, amplitude=30000):
    num_samples = int(sample_rate * duration)
    audio = np.zeros((num_samples, 1), dtype=np.int16)
    width = int(sample_rate * clap_width)

    for clap_time in clap_times:
        start = int(clap_time * sample_rate)
        end = min(start + width, num_samples)
        audio[start:end, 0] = amplitude

    return audio


def test_clap_wake_word_detection():
    audio = generate_synthetic_clap_audio()

    with patch('voice.sd.rec', return_value=audio), patch('voice.sd.wait', return_value=None), patch('voice.pyttsx3.init', return_value=DummyEngine()):
        vi = VoiceInterface()
        activated = vi.listen_for_wake_word(timeout=2)
        print('Clap wake word detected:', activated)


if __name__ == '__main__':
    test_clap_wake_word_detection()
