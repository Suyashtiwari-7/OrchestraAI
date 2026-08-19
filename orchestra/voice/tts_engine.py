"""
OrchestraAI — TTS Engine (Text-to-Speech)
==========================================
Streaming text-to-speech with sentence-level chunking.

Primary: Kokoro-82M via kokoro-onnx (local, human-grade, sub-200ms latency).
Fallback: Edge-TTS via edge-tts (online, Microsoft Neural voices).

DESIGN: Instead of waiting for the full LLM response, TTS begins speaking
the first sentence immediately. This creates a natural, live conversation feel.

Dependencies:
    kokoro-onnx>=0.4.0       # Primary: local high-quality TTS
    edge-tts>=6.1.0          # Fallback: online neural TTS
    sounddevice>=0.4.6       # Audio playback
"""

import io
import re
import logging
import threading
import asyncio
from typing import Optional, Callable

logger = logging.getLogger("orchestra.voice.tts")

# Lazy imports
_kokoro = None
_edge_tts = None
_sounddevice = None
_soundfile = None


def _ensure_kokoro() -> bool:
    """Try to load kokoro-onnx."""
    global _kokoro
    if _kokoro is None:
        try:
            import kokoro_onnx
            _kokoro = kokoro_onnx
        except ImportError:
            logger.debug("kokoro-onnx not installed. Will fall back to Edge-TTS.")
            return False
    return True


def _ensure_edge_tts() -> bool:
    """Try to load edge-tts."""
    global _edge_tts
    if _edge_tts is None:
        try:
            import edge_tts
            _edge_tts = edge_tts
        except ImportError:
            logger.warning("edge-tts not installed. TTS disabled.")
            return False
    return True


def _ensure_audio() -> bool:
    """Load sounddevice and soundfile."""
    global _sounddevice, _soundfile
    if _sounddevice is None:
        try:
            import sounddevice
            _sounddevice = sounddevice
        except ImportError:
            logger.warning("sounddevice not installed. TTS audio playback disabled.")
            return False
    if _soundfile is None:
        try:
            import soundfile
            _soundfile = soundfile
        except ImportError:
            # soundfile is optional — we can still use raw PCM
            pass
    return True


def split_into_sentences(text: str) -> list[str]:
    """Split text into sentences for streaming TTS."""
    # Split on sentence-ending punctuation followed by whitespace
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    return [s.strip() for s in sentences if s.strip()]


class TTSEngine:
    """
    Streaming Text-to-Speech engine with sentence-level chunking.

    Speaks text as soon as each sentence is ready, creating a
    natural live conversation feel. Supports interruption.
    """

    def __init__(
        self,
        voice_name: str = "af_heart",  # Kokoro voice name
        edge_voice: str = "en-US-GuyNeural",  # Edge-TTS fallback voice
        on_speaking_start: Optional[Callable[[], None]] = None,
        on_speaking_end: Optional[Callable[[], None]] = None,
    ):
        """
        Args:
            voice_name: Kokoro-82M voice name (e.g., 'af_heart', 'am_adam').
            edge_voice: Edge-TTS voice name for online fallback.
            on_speaking_start: Called when TTS begins speaking.
            on_speaking_end: Called when TTS finishes speaking.
        """
        self.voice_name = voice_name
        self.edge_voice = edge_voice
        self.on_speaking_start = on_speaking_start
        self.on_speaking_end = on_speaking_end
        self._kokoro_model = None
        self._interrupted = False
        self._speaking = False
        self._lock = threading.Lock()

    @property
    def is_speaking(self) -> bool:
        return self._speaking

    def interrupt(self):
        """Stop current speech immediately (e.g., user started talking)."""
        self._interrupted = True
        if _sounddevice:
            try:
                _sounddevice.stop()
            except Exception:
                pass

    def speak_text(self, text: str):
        """
        Speak the given text using sentence-level streaming.

        Splits text into sentences and speaks each one immediately,
        checking for interruption between sentences.
        """
        sentences = split_into_sentences(text)
        if not sentences:
            return

        self._interrupted = False
        self._speaking = True

        if self.on_speaking_start:
            self.on_speaking_start()

        try:
            for sentence in sentences:
                if self._interrupted:
                    logger.info("[TTS] Interrupted — stopping speech.")
                    break

                self._speak_sentence(sentence)
        finally:
            self._speaking = False
            if self.on_speaking_end:
                self.on_speaking_end()

    def speak_text_async(self, text: str):
        """Speak text in a background thread (non-blocking)."""
        thread = threading.Thread(target=self.speak_text, args=(text,), daemon=True)
        thread.start()

    def _speak_sentence(self, sentence: str):
        """Speak a single sentence using Edge-TTS (primary neural) or Kokoro/SAPI (fallback)."""
        # Try Edge-TTS first (Ultra-natural Microsoft Neural Voices)
        if _ensure_edge_tts():
            try:
                self._speak_with_edge_tts(sentence)
                return
            except Exception as e:
                logger.debug(f"[TTS] Edge-TTS failed for sentence, trying Kokoro/offline: {e}")

        # Fallback 1: Kokoro-82M (local offline neural model)
        if _ensure_kokoro():
            try:
                self._speak_with_kokoro(sentence)
                return
            except Exception as e:
                logger.debug(f"[TTS] Kokoro TTS failed: {e}")

        # Fallback 2: Windows native SAPI / pyttsx3 (100% offline system voice)
        try:
            import pyttsx3
            engine = pyttsx3.init()
            engine.say(sentence)
            engine.runAndWait()
            return
        except Exception as e:
            logger.error(f"[TTS] Native offline speech fallback failed: {e}")

        logger.error("[TTS] All TTS engines failed.")

    def _speak_with_kokoro(self, text: str):
        """Generate and play audio using Kokoro-82M."""
        if not _ensure_audio():
            return

        # Initialize model on first use
        if self._kokoro_model is None:
            logger.info("[*] Loading Kokoro-82M TTS model...")
            self._kokoro_model = _kokoro.Kokoro("kokoro-v1.0.onnx", "voices-v1.0.bin")
            logger.info("[+] Kokoro-82M loaded.")

        # Generate audio
        samples, sample_rate = self._kokoro_model.create(
            text,
            voice=self.voice_name,
            speed=1.0,
        )

        if self._interrupted:
            return

        # Play audio through speakers
        _sounddevice.play(samples, samplerate=sample_rate)
        _sounddevice.wait()

    def _speak_with_edge_tts(self, text: str):
        """Generate and play audio using Edge-TTS (async wrapper)."""
        if not _ensure_audio():
            return

        # Edge-TTS is async, so we run it in an event loop
        loop = asyncio.new_event_loop()
        try:
            audio_data = loop.run_until_complete(self._edge_tts_generate(text))
        finally:
            loop.close()

        if not audio_data or self._interrupted:
            return

        # Play the MP3 audio — decode and play
        try:
            audio_buffer = io.BytesIO(audio_data)
            if _soundfile:
                data, sr = _soundfile.read(audio_buffer)
                _sounddevice.play(data, samplerate=sr)
                _sounddevice.wait()
        except Exception as e:
            logger.error(f"[TTS] Edge-TTS playback error: {e}")

    async def _edge_tts_generate(self, text: str) -> Optional[bytes]:
        """Generate audio bytes from Edge-TTS."""
        try:
            communicate = _edge_tts.Communicate(text, self.edge_voice)
            audio_chunks = []
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    audio_chunks.append(chunk["data"])
            return b"".join(audio_chunks) if audio_chunks else None
        except Exception as e:
            logger.error(f"[TTS] Edge-TTS generation error: {e}")
            return None
