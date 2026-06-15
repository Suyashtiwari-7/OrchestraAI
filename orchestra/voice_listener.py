"""
OrchestraAI — DARKI Voice Listener
=====================================
Background thread that continuously listens for the wake word "Hey DARKI"
using the system microphone. When detected, captures the following command
and sends it to the DARKI widget for processing.
"""

import threading
import logging
import time
from typing import Callable, Optional

logger = logging.getLogger("orchestra.voice")

# Lazy imports to avoid crashing if dependencies missing
_speech_recognition = None
_pyaudio = None


def _ensure_imports():
    """Lazy-load speech_recognition and pyaudio."""
    global _speech_recognition, _pyaudio
    if _speech_recognition is None:
        try:
            import speech_recognition as sr
            _speech_recognition = sr
        except ImportError:
            logger.warning("speech_recognition not installed. Voice disabled.")
            return False
    try:
        import pyaudio
        _pyaudio = pyaudio
    except ImportError:
        logger.warning("pyaudio not installed. Voice may not work.")
    return True


class VoiceListener:
    """
    Background voice listener for wake word detection.
    
    Continuously listens via the microphone for "Hey DARKI" (or variants).
    On detection, captures the command spoken after the wake word and
    calls the provided callback.
    """

    WAKE_WORDS = ["hey darki", "hi darki", "okay darki", "ok darki", "hey ducky", "hey docky"]

    def __init__(self, on_command: Callable[[str], None], on_wake: Optional[Callable[[], None]] = None):
        """
        Args:
            on_command: Called with the recognized command text after wake word.
            on_wake: Called when wake word is detected (for UI feedback).
        """
        self.on_command = on_command
        self.on_wake = on_wake
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._enabled = True

    def start(self):
        """Start listening in a background daemon thread."""
        if not _ensure_imports():
            logger.error("Cannot start voice listener — missing dependencies.")
            return

        if self._running:
            return

        self._running = True
        self._thread = threading.Thread(target=self._listen_loop, daemon=True, name="DarkiVoice")
        self._thread.start()
        logger.info("DARKI Voice Listener started.")

    def stop(self):
        """Stop the listener."""
        self._running = False
        logger.info("DARKI Voice Listener stopped.")

    def set_enabled(self, enabled: bool):
        """Enable/disable listening without stopping the thread."""
        self._enabled = enabled

    def _listen_loop(self):
        """Main listening loop — runs in background thread."""
        sr = _speech_recognition
        recognizer = sr.Recognizer()
        recognizer.energy_threshold = 300  # Adjust for ambient noise
        recognizer.dynamic_energy_threshold = True
        recognizer.pause_threshold = 0.8

        try:
            mic = sr.Microphone()
        except Exception as e:
            logger.error(f"Could not access microphone: {e}")
            self._running = False
            return

        with mic as source:
            # Calibrate for ambient noise
            logger.info("Calibrating microphone for ambient noise...")
            recognizer.adjust_for_ambient_noise(source, duration=1.5)
            logger.info("Microphone calibrated. Listening for 'Hey DARKI'...")

        while self._running:
            if not self._enabled:
                time.sleep(0.5)
                continue

            try:
                with mic as source:
                    # Listen with timeout to allow checking self._running
                    audio = recognizer.listen(source, timeout=5, phrase_time_limit=8)

                # Recognize speech
                try:
                    text = recognizer.recognize_google(audio).lower().strip()
                    logger.debug(f"Heard: {text}")
                except sr.UnknownValueError:
                    continue  # Didn't understand — keep listening
                except sr.RequestError as e:
                    logger.warning(f"Speech recognition API error: {e}")
                    time.sleep(2)
                    continue

                # Check for wake word
                command = self._extract_command(text)
                if command is not None:
                    logger.info(f"Wake word detected! Command: '{command}'")

                    if self.on_wake:
                        self.on_wake()

                    if command and len(command) > 2:
                        # Command was spoken along with wake word
                        self.on_command(command)
                    else:
                        # Wake word only — listen for the follow-up command
                        logger.info("Listening for follow-up command...")
                        try:
                            with mic as source:
                                follow_audio = recognizer.listen(source, timeout=5, phrase_time_limit=15)
                            follow_text = recognizer.recognize_google(follow_audio).strip()
                            if follow_text:
                                logger.info(f"Follow-up command: '{follow_text}'")
                                self.on_command(follow_text)
                        except (sr.WaitTimeoutError, sr.UnknownValueError):
                            logger.debug("No follow-up command detected.")
                        except sr.RequestError as e:
                            logger.warning(f"Follow-up recognition failed: {e}")

            except sr.WaitTimeoutError:
                continue  # Timeout — no speech detected, loop back
            except Exception as e:
                logger.error(f"Voice listener error: {e}")
                time.sleep(1)

    def _extract_command(self, text: str) -> Optional[str]:
        """
        Check if text contains a wake word.
        Returns the command portion after the wake word, or None if no wake word found.
        """
        for wake in self.WAKE_WORDS:
            if wake in text:
                idx = text.index(wake) + len(wake)
                command = text[idx:].strip()
                # Clean up common speech artifacts
                for prefix in [",", ".", "!"]:
                    command = command.lstrip(prefix).strip()
                return command
        return None
