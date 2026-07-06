"""
Voice Interface for Jarvis Multi-Agent AI Operating System.

Wraps Faster-Whisper (STT) and pyttsx3 (TTS) with integration
to the SystemState for live status updates.

Preserves all existing functionality:
- Faster-Whisper transcription
- Text-to-speech output
- Clap wake word detection
- Configurable model sizes

Enhancements:
- SystemState integration (listening/speaking states)
- Error resilience
- Graceful degradation if packages unavailable
"""

from __future__ import annotations

import logging
import tempfile
import time
from pathlib import Path
from typing import Optional

from config import (
    VOICE_MODEL_SIZE,
    VOICE_DEVICE,
    VOICE_COMPUTE_TYPE,
    VOICE_SAMPLE_RATE,
    VOICE_RECORD_DURATION,
    VOICE_TTS_RATE,
    VOICE_WAKE_WORD_TIMEOUT,
    VOICE_CLAP_THRESHOLD,
)
from core.state import SystemState

logger = logging.getLogger(__name__)


class VoiceInterface:
    """
    Voice interface with STT (Faster-Whisper) and TTS (pyttsx3).

    Usage:
        voice = VoiceInterface()
        text = voice.transcribe("recording.wav")
        voice.speak("Hello Commander")
    """

    def __init__(self) -> None:
        self._whisper_model: Optional[Any] = None  # type: ignore
        self._tts_engine: Optional[Any] = None  # type: ignore
        self.state = SystemState()
        self._init_whisper()
        self._init_tts()

    def _init_whisper(self) -> None:
        """Lazy-load the Whisper model."""
        try:
            from faster_whisper import WhisperModel
            logger.info(f"Loading Whisper model '{VOICE_MODEL_SIZE}'...")
            self._whisper_model = WhisperModel(
                VOICE_MODEL_SIZE,
                device=VOICE_DEVICE,
                compute_type=VOICE_COMPUTE_TYPE,
            )
            logger.info("Whisper model ready")
        except Exception as e:
            logger.error(f"Failed to load Whisper: {e}")
            self._whisper_model = None

    def _init_tts(self) -> None:
        """Lazy-load the TTS engine."""
        try:
            import pyttsx3
            self._tts_engine = pyttsx3.init()
            self._tts_engine.setProperty("rate", VOICE_TTS_RATE)
            self._tts_engine.setProperty("volume", 1.0)
            logger.info("TTS engine ready")
        except Exception as e:
            logger.error(f"Failed to init TTS: {e}")
            self._tts_engine = None

    # -------------------------------------------------------------------------
    # SPEECH-TO-TEXT
    # -------------------------------------------------------------------------

    def transcribe(self, audio_path: str) -> str:
        """
        Transcribe audio file to text.

        Args:
            audio_path: Path to WAV audio file.

        Returns:
            Transcribed text, or empty string on failure.
        """
        if self._whisper_model is None:
            logger.warning("Whisper not available, cannot transcribe")
            return ""

        try:
            self.state.set_session_meta("voice_state", "transcribing")
            segments, _ = self._whisper_model.transcribe(audio_path)
            text = "".join(seg.text for seg in segments).strip()
            # Clean common artifacts
            text = text.replace("Jarvis", "").strip()
            text = text.replace("jarvis", "").strip()
            logger.info(f"Transcribed: '{text}'")
            return text
        except Exception as e:
            logger.error(f"Transcription failed: {e}")
            return ""
        finally:
            self.state.set_session_meta("voice_state", "idle")

    def transcribe_bytes(self, audio_bytes: bytes) -> str:
        """Transcribe from raw audio bytes (saves to temp file first)."""
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            f.write(audio_bytes)
            return self.transcribe(f.name)

    # -------------------------------------------------------------------------
    # TEXT-TO-SPEECH
    # -------------------------------------------------------------------------

    def speak(self, text: str) -> None:
        """
        Speak text aloud using TTS.

        Args:
            text: Text to speak.
        """
        if not text or not text.strip():
            return

        clean = text.strip()
        logger.info(f"TTS: {clean[:80]}")

        if self._tts_engine is None:
            logger.warning("TTS not available")
            print(f"Jarvis: {clean}")
            return

        try:
            self.state.set_session_meta("voice_state", "speaking")
            self._tts_engine.say(clean)
            self._tts_engine.runAndWait()
            time.sleep(0.2)
        except Exception as e:
            logger.error(f"TTS error: {e}")
            print(f"Jarvis: {clean}")
        finally:
            self.state.set_session_meta("voice_state", "idle")

    # -------------------------------------------------------------------------
    # WAKE WORD
    # -------------------------------------------------------------------------

    def listen_for_wake_word(self, timeout: int = VOICE_WAKE_WORD_TIMEOUT) -> bool:
        """
        Listen for clap wake word.

        Args:
            timeout: Seconds to listen.

        Returns:
            True if wake word detected.
        """
        try:
            import sounddevice as sd
            import numpy as np

            logger.info("Listening for wake word...")
            self.state.set_session_meta("voice_state", "listening_wake")

            audio = sd.rec(int(VOICE_SAMPLE_RATE * timeout), samplerate=VOICE_SAMPLE_RATE, channels=1, dtype="int16")
            sd.wait()

            audio = np.abs(audio)
            threshold = VOICE_CLAP_THRESHOLD
            clap_times = []

            for i in range(len(audio)):
                if audio[i] > threshold:
                    clap_times.append(i / VOICE_SAMPLE_RATE)

            # Detect two claps close together
            for i in range(len(clap_times) - 1):
                if 0.1 < clap_times[i + 1] - clap_times[i] < 1.0:
                    logger.info("Wake word (clap) detected!")
                    return True

            return False
        except Exception as e:
            logger.error(f"Wake word detection failed: {e}")
            return False
        finally:
            self.state.set_session_meta("voice_state", "idle")

    # -------------------------------------------------------------------------
    # VOICE RECORDING
    # -------------------------------------------------------------------------

    def record_audio(self, duration: int = VOICE_RECORD_DURATION) -> str:
        """
        Record audio and return path to saved WAV file.

        Args:
            duration: Recording duration in seconds.

        Returns:
            Path to temporary WAV file.
        """
        try:
            import sounddevice as sd
            from scipy.io.wavfile import write
            import numpy as np

            self.state.set_session_meta("voice_state", "recording")
            logger.info(f"Recording for {duration}s...")

            audio = sd.rec(int(duration * VOICE_SAMPLE_RATE), samplerate=VOICE_SAMPLE_RATE, channels=1)
            sd.wait()

            audio = (audio * 32767).astype(np.int16)

            temp_file = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
            write(temp_file.name, VOICE_SAMPLE_RATE, audio)

            return temp_file.name
        except Exception as e:
            logger.error(f"Recording failed: {e}")
            return ""
        finally:
            self.state.set_session_meta("voice_state", "idle")

    # -------------------------------------------------------------------------
    # AVAILABILITY
    # -------------------------------------------------------------------------

    @property
    def stt_available(self) -> bool:
        """Whether speech-to-text is available."""
        return self._whisper_model is not None

    @property
    def tts_available(self) -> bool:
        """Whether text-to-speech is available."""
        return self._tts_engine is not None

    @property
    def available(self) -> bool:
        """Whether any voice capability is available."""
        return self.stt_available or self.tts_available
