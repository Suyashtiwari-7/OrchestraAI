"""
OrchestraAI — Live Voice Session Manager
==========================================
Orchestrates the full-duplex voice loop:
    1. VAD detects user speaking → Faster-Whisper transcribes
    2. Transcribed text → sent to LLM router
    3. LLM response → streamed sentence-by-sentence to TTS → audio plays

Supports interruption: if user speaks while DARKI is talking,
audio playback stops instantly and DARKI listens to the new input.
"""

import logging
import threading
from typing import Callable, Optional
from enum import Enum

from .stt_engine import STTEngine
from .tts_engine import TTSEngine

logger = logging.getLogger("orchestra.voice.live_session")


class VoiceState(Enum):
    """State machine for the voice session."""
    IDLE = "idle"
    LISTENING = "listening"
    THINKING = "thinking"
    SPEAKING = "speaking"


class LiveVoiceSession:
    """
    Manages real-time bidirectional voice conversation with DARKI.

    Architecture:
        Microphone → STT (Faster-Whisper) → LLM Router → TTS (Kokoro-82M) → Speaker

    The session handles:
    - Automatic wake word detection (optional)
    - Continuous speech recognition with VAD
    - LLM response streaming with sentence-level TTS
    - Interruption handling (user speaks → DARKI stops talking → listens)
    - State management (idle / listening / thinking / speaking)
    """

    def __init__(
        self,
        on_command: Callable[[str], str],
        on_state_change: Optional[Callable[[VoiceState], None]] = None,
        stt_model_size: str = "base",
        tts_voice: str = "af_heart",
        edge_voice: str = "en-US-GuyNeural",
    ):
        """
        Args:
            on_command: Callback that takes user speech text and returns DARKI's
                        text response. This is the LLM processing function.
            on_state_change: Called when voice state changes (for UI updates).
            stt_model_size: Faster-Whisper model size.
            tts_voice: Kokoro-82M voice name.
            edge_voice: Edge-TTS fallback voice name.
        """
        self.on_command = on_command
        self.on_state_change = on_state_change
        self._state = VoiceState.IDLE
        self._lock = threading.Lock()

        # Initialize engines
        self.stt = STTEngine(
            model_size=stt_model_size,
            on_transcript=self._handle_transcript,
        )
        self.tts = TTSEngine(
            voice_name=tts_voice,
            edge_voice=edge_voice,
            on_speaking_start=lambda: self._set_state(VoiceState.SPEAKING),
            on_speaking_end=lambda: self._set_state(VoiceState.LISTENING),
        )

    @property
    def state(self) -> VoiceState:
        return self._state

    @property
    def is_active(self) -> bool:
        return self._state != VoiceState.IDLE

    def start(self):
        """Start the live voice session — begin listening."""
        logger.info("[*] Starting live voice session...")
        self._set_state(VoiceState.LISTENING)
        self.stt.start()

    def stop(self):
        """Stop the live voice session."""
        logger.info("[*] Stopping live voice session...")
        self.stt.stop()
        self.tts.interrupt()
        self._set_state(VoiceState.IDLE)

    def _set_state(self, new_state: VoiceState):
        """Update state and notify UI."""
        with self._lock:
            old_state = self._state
            self._state = new_state

        if old_state != new_state:
            logger.info(f"[Voice] State: {old_state.value} → {new_state.value}")
            if self.on_state_change:
                try:
                    self.on_state_change(new_state)
                except Exception as e:
                    logger.error(f"[!] State change callback error: {e}")

    # Supported wake word variations
    WAKE_PHRASES = [
        "hey darki", "hey darky", "hey darkee", "hey darkey",
        "darki", "darky", "darkee", "darkey",
        "yo darki", "yo darky", "ok darki", "ok darky",
        "jarvis"
    ]

    def _extract_wake_command(self, text: str) -> tuple[bool, str]:
        """
        Check if speech contains a wake word.
        Returns (is_wake, command_text).
        """
        lower = text.lower().strip()

        # Check exact wake words
        for phrase in self.WAKE_PHRASES:
            if lower == phrase or lower == f"{phrase}.":
                return True, ""  # Just wake word, no extra command

            if lower.startswith(f"{phrase} ") or lower.startswith(f"{phrase},"):
                cmd = text[len(phrase):].strip(" ,.:!?")
                return True, cmd

            # Also detect if wake word is mentioned inside sentence
            if phrase in lower:
                idx = lower.find(phrase)
                cmd = text[idx + len(phrase):].strip(" ,.:!?")
                return True, cmd

        return False, text

    def _handle_transcript(self, text: str):
        """
        Called by STT when a speech segment is transcribed.
        Interrupts any ongoing TTS and processes wake word or direct command.
        """
        if not text or len(text.strip()) < 2:
            return

        logger.info(f"[Voice] Transcribed: '{text}'")

        # If DARKI is currently speaking, interrupt it
        if self.tts.is_speaking:
            logger.info("[Voice] Interrupting DARKI's speech — user started talking.")
            self.tts.interrupt()

        is_wake, command = self._extract_wake_command(text)

        # If wake word detected or already in an active interactive session
        if is_wake:
            logger.info(f"[Voice] WAKE WORD DETECTED! Command: '{command}'")
            thread = threading.Thread(
                target=self._process_command,
                args=(command, True),
                daemon=True,
            )
            thread.start()
        elif self.state == VoiceState.LISTENING and len(text.split()) >= 2:
            # Active conversation mode
            thread = threading.Thread(
                target=self._process_command,
                args=(text, False),
                daemon=True,
            )
            thread.start()

    def _process_command(self, command: str, was_wake_word: bool = False):
        """Process a transcribed command through the LLM and speak the response."""
        self._set_state(VoiceState.THINKING)

        try:
            # If user only said "Hey DARKI" without a command, acknowledge warmly
            if was_wake_word and not command:
                greeting = "Yes Suyash? I'm listening!"
                self.tts.speak_text(greeting)
                self._set_state(VoiceState.LISTENING)
                return

            # Send actual command to LLM
            response_text = self.on_command(command)

            if response_text:
                self.tts.speak_text(response_text)
            else:
                self._set_state(VoiceState.LISTENING)

        except Exception as e:
            logger.error(f"[!] Voice command processing error: {e}")
            self._set_state(VoiceState.LISTENING)
