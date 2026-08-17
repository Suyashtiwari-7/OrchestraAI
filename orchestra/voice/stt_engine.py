"""
OrchestraAI — STT Engine (Speech-to-Text)
==========================================
Real-time speech transcription using Faster-Whisper with Silero VAD.
Streams audio from the microphone and returns transcribed text segments.

Dependencies:
    faster-whisper>=1.0.0
    sounddevice>=0.4.6
"""

import logging
import threading
import queue
import numpy as np
from typing import Callable, Optional

logger = logging.getLogger("orchestra.voice.stt")

# Lazy imports to avoid crash if dependencies missing
_faster_whisper = None
_sounddevice = None


def _ensure_imports() -> bool:
    """Lazy-load faster-whisper and sounddevice."""
    global _faster_whisper, _sounddevice
    if _faster_whisper is None:
        try:
            import faster_whisper
            _faster_whisper = faster_whisper
        except ImportError:
            logger.warning("faster-whisper not installed. STT disabled.")
            return False
    if _sounddevice is None:
        try:
            import sounddevice
            _sounddevice = sounddevice
        except ImportError:
            logger.warning("sounddevice not installed. STT disabled.")
            return False
    return True


class STTEngine:
    """
    Real-time Speech-to-Text engine using Faster-Whisper.

    Uses Voice Activity Detection (VAD) to detect speech boundaries
    without requiring push-to-talk. Transcribes spoken audio into text
    segments that are delivered via callback.
    """

    # Audio parameters
    SAMPLE_RATE = 16000     # 16kHz mono for Whisper
    CHUNK_DURATION = 0.5    # 500ms audio chunks
    SILENCE_TIMEOUT = 1.5   # Seconds of silence before considering speech done

    def __init__(
        self,
        model_size: str = "base",
        on_transcript: Optional[Callable[[str], None]] = None,
        on_partial: Optional[Callable[[str], None]] = None,
    ):
        """
        Args:
            model_size: Faster-Whisper model size ('tiny', 'base', 'small', 'medium').
            on_transcript: Called with final transcribed text when speech segment ends.
            on_partial: Called with partial transcription updates during speech.
        """
        self.model_size = model_size
        self.on_transcript = on_transcript
        self.on_partial = on_partial
        self._model = None
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._audio_queue: queue.Queue = queue.Queue()

    def start(self):
        """Start listening to the microphone for speech."""
        if not _ensure_imports():
            logger.error("Cannot start STT: missing dependencies.")
            return

        if self._running:
            return

        # Load Whisper model on first use
        if self._model is None:
            logger.info(f"[*] Loading Faster-Whisper model: {self.model_size}")
            self._model = _faster_whisper.WhisperModel(
                self.model_size,
                device="cpu",
                compute_type="int8",
            )
            logger.info("[+] Faster-Whisper model loaded.")

        self._running = True
        self._thread = threading.Thread(target=self._listen_loop, daemon=True)
        self._thread.start()
        logger.info("[*] STT engine started — listening for speech.")

    def stop(self):
        """Stop listening."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=3.0)
            self._thread = None
        logger.info("[*] STT engine stopped.")

    def _listen_loop(self):
        """Main loop: capture audio, detect speech, transcribe."""
        chunk_samples = int(self.SAMPLE_RATE * self.CHUNK_DURATION)
        audio_buffer = []
        silence_chunks = 0
        max_silence_chunks = int(self.SILENCE_TIMEOUT / self.CHUNK_DURATION)
        is_speaking = False

        def audio_callback(indata, frames, time_info, status):
            """Sounddevice callback — pushes audio chunks to queue."""
            if status:
                logger.debug(f"Audio status: {status}")
            self._audio_queue.put(indata.copy())

        try:
            with _sounddevice.InputStream(
                samplerate=self.SAMPLE_RATE,
                channels=1,
                dtype="float32",
                blocksize=chunk_samples,
                callback=audio_callback,
            ):
                while self._running:
                    try:
                        chunk = self._audio_queue.get(timeout=1.0)
                    except queue.Empty:
                        continue

                    # Simple energy-based VAD
                    energy = np.sqrt(np.mean(chunk ** 2))
                    speech_threshold = 0.01  # Configurable noise floor

                    if energy > speech_threshold:
                        is_speaking = True
                        silence_chunks = 0
                        audio_buffer.append(chunk)
                    elif is_speaking:
                        silence_chunks += 1
                        audio_buffer.append(chunk)

                        if silence_chunks >= max_silence_chunks:
                            # Speech segment ended — transcribe the buffer
                            self._transcribe_buffer(audio_buffer)
                            audio_buffer = []
                            is_speaking = False
                            silence_chunks = 0

        except Exception as e:
            logger.error(f"[!] STT listen loop error: {e}")

    def _transcribe_buffer(self, audio_chunks: list):
        """Concatenate audio chunks and run Whisper transcription."""
        if not audio_chunks or not self._model:
            return

        # Concatenate all chunks into a single numpy array
        audio = np.concatenate(audio_chunks, axis=0).flatten()

        try:
            segments, info = self._model.transcribe(
                audio,
                beam_size=3,
                language="en",
                vad_filter=True,
            )

            # Collect transcribed text
            full_text = ""
            for segment in segments:
                full_text += segment.text

            full_text = full_text.strip()
            if full_text and self.on_transcript:
                logger.info(f"[STT] Transcribed: {full_text}")
                self.on_transcript(full_text)

        except Exception as e:
            logger.error(f"[!] Transcription error: {e}")
