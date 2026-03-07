"""Speech-to-Text (STT) for OpenDuck Mini V3

This module provides speech-to-text transcription with:
- Support for multiple backends (Whisper, Vosk, Google)
- Streaming and batch transcription modes
- Multi-language support
- Mock mode for development without external dependencies

Production Implementation Options:
1. Whisper (OpenAI) - High accuracy, offline capable, GPU accelerated
2. Vosk - Offline, lightweight, good for edge deployment
3. Google Speech API - Cloud-based, high accuracy, requires internet
4. Whisper.cpp - Optimized C++ port for CPU inference

This module provides a common interface that can wrap any of these backends.
By default, it uses a mock mode for development.

Example:
    ```python
    from src.voice.stt import SpeechToText, STTConfig

    # Create STT engine
    config = STTConfig(language="en", backend="whisper")
    stt = SpeechToText(config)

    # Batch transcription
    result = stt.transcribe(audio_samples)
    print(f"Transcribed: {result.text} (confidence: {result.confidence})")

    # Streaming mode
    stt.start_streaming()
    while audio_available:
        chunk = get_audio_chunk()
        partial = stt.process_chunk(chunk)
        if partial.text:
            print(f"Partial: {partial.text}")
    final = stt.finalize()
    print(f"Final: {final.text}")
    ```

Thread Safety:
    SpeechToText is NOT thread-safe. Use one instance per thread.
"""

from __future__ import annotations

import logging
import time
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, List, Optional, Any

import numpy as np

_logger = logging.getLogger(__name__)


class STTBackend(Enum):
    """Available STT backends.

    MOCK: Development/testing mode, returns placeholder text
    WHISPER: OpenAI Whisper model (local or API)
    VOSK: Offline speech recognition
    GOOGLE: Google Cloud Speech API
    """
    MOCK = "mock"
    WHISPER = "whisper"
    VOSK = "vosk"
    GOOGLE = "google"


@dataclass
class STTConfig:
    """Configuration for Speech-to-Text.

    Attributes:
        language: Language code for transcription (default: "en")
            Use "auto" for automatic language detection
        sample_rate: Audio sample rate in Hz (default: 16000)
        backend: STT backend to use (default: "mock")
        model_size: Model size for Whisper backend (default: "base")
            Options: "tiny", "base", "small", "medium", "large"
        max_audio_length_seconds: Maximum audio length to process (default: 30)
        vad_filter: Apply VAD filtering before transcription (default: True)
    """
    language: str = "en"
    sample_rate: int = 16000
    backend: str = "mock"
    model_size: str = "base"
    max_audio_length_seconds: float = 30.0
    vad_filter: bool = True

    def __post_init__(self) -> None:
        """Validate configuration."""
        if self.sample_rate <= 0:
            raise ValueError(f"sample_rate must be positive, got {self.sample_rate}")
        if self.max_audio_length_seconds <= 0:
            raise ValueError(
                f"max_audio_length_seconds must be positive, got {self.max_audio_length_seconds}"
            )


@dataclass
class STTResult:
    """Result from speech-to-text transcription.

    Attributes:
        text: Transcribed text
        confidence: Transcription confidence (0.0 to 1.0)
        language: Detected or specified language
        duration_seconds: Duration of processed audio
        is_final: Whether this is a final or partial result
        words: Individual word timings (if available)
        alternatives: Alternative transcriptions (if available)
    """
    text: str
    confidence: float
    language: str
    duration_seconds: float
    is_final: bool
    words: List[dict] = field(default_factory=list)
    alternatives: List[str] = field(default_factory=list)

    @staticmethod
    def empty(language: str = "en") -> STTResult:
        """Create an empty result for no speech detected."""
        return STTResult(
            text="",
            confidence=0.0,
            language=language,
            duration_seconds=0.0,
            is_final=True,
            words=[],
            alternatives=[]
        )


class SpeechToText:
    """Speech-to-Text transcription engine.

    Provides unified interface for speech transcription with support
    for multiple backends (Whisper, Vosk, Google) and both batch
    and streaming modes.

    Attributes:
        config: STT configuration
        mock_mode: Whether running in mock mode
        is_ready: Whether engine is ready for transcription
        is_streaming: Whether currently in streaming mode
        on_result: Callback for transcription results
        on_partial: Callback for partial results (streaming mode)
    """

    def __init__(
        self,
        config: Optional[STTConfig] = None,
        mock_mode: bool = False
    ) -> None:
        """Initialize Speech-to-Text engine.

        Args:
            config: STT configuration (uses defaults if None)
            mock_mode: Force mock mode regardless of config.backend
        """
        self.config = config or STTConfig()
        self.mock_mode = mock_mode or self.config.backend == "mock"

        self._is_ready = False
        self._is_streaming = False
        # Bounded buffer: max 60 seconds of audio to prevent memory leak
        max_stream_samples = int(self.config.sample_rate * 60)
        self._stream_buffer: deque = deque(maxlen=max_stream_samples)
        self._stream_text_buffer: List[str] = []

        # Callbacks
        self.on_result: Optional[Callable[[STTResult], None]] = None
        self.on_partial: Optional[Callable[[STTResult], None]] = None

        # Backend-specific initialization
        self._backend = None
        if not self.mock_mode:
            self._init_backend()
        else:
            self._is_ready = True

        _logger.info(
            f"SpeechToText initialized: language={self.config.language}, "
            f"backend={self.config.backend}, mock_mode={self.mock_mode}"
        )

    @property
    def is_ready(self) -> bool:
        """Check if engine is ready for transcription."""
        return self._is_ready

    @property
    def is_streaming(self) -> bool:
        """Check if currently in streaming mode."""
        return self._is_streaming

    def transcribe(self, audio: np.ndarray) -> STTResult:
        """Transcribe audio to text (batch mode).

        Args:
            audio: Audio samples (float32, -1 to 1 range)

        Returns:
            STTResult with transcription and metadata
        """
        if len(audio) == 0:
            return STTResult.empty(self.config.language)

        # Normalize input
        audio = self._normalize_input(audio)

        # Calculate duration
        duration = len(audio) / self.config.sample_rate

        # Truncate if too long
        max_samples = int(self.config.max_audio_length_seconds * self.config.sample_rate)
        if len(audio) > max_samples:
            _logger.warning(
                f"Audio truncated from {duration:.1f}s to {self.config.max_audio_length_seconds}s"
            )
            audio = audio[:max_samples]
            duration = self.config.max_audio_length_seconds

        # Run transcription
        if self.mock_mode:
            result = self._mock_transcribe(audio, duration)
        else:
            result = self._backend_transcribe(audio, duration)

        # Fire callback
        if self.on_result:
            try:
                self.on_result(result)
            except Exception as e:
                _logger.error(f"on_result callback error: {e}")

        return result

    def start_streaming(self) -> None:
        """Start streaming transcription session.

        In streaming mode, audio is processed incrementally and
        partial results are emitted as recognition progresses.
        """
        if self._is_streaming:
            _logger.warning("Already in streaming mode")
            return

        self._is_streaming = True
        self._stream_buffer.clear()
        self._stream_text_buffer.clear()
        _logger.info("Streaming transcription started")

    def stop_streaming(self) -> None:
        """Stop streaming transcription session."""
        if not self._is_streaming:
            return

        self._is_streaming = False
        _logger.info("Streaming transcription stopped")

    def process_chunk(self, chunk: np.ndarray) -> STTResult:
        """Process a streaming audio chunk.

        Args:
            chunk: Audio chunk (typically 100ms)

        Returns:
            STTResult (may be partial or final)
        """
        if not self._is_streaming:
            # Auto-start streaming if not started
            self.start_streaming()

        # Normalize input
        chunk = self._normalize_input(chunk)

        # Add to buffer
        self._stream_buffer.extend(chunk.tolist())

        # Process when we have enough audio (e.g., 500ms)
        min_samples = int(0.5 * self.config.sample_rate)

        if len(self._stream_buffer) >= min_samples:
            # Get audio from buffer
            audio = np.array(list(self._stream_buffer), dtype=np.float32)
            duration = len(audio) / self.config.sample_rate

            # Run transcription
            if self.mock_mode:
                result = self._mock_transcribe(audio, duration, is_final=False)
            else:
                result = self._backend_transcribe(audio, duration, is_final=False)

            # Store partial text
            if result.text:
                self._stream_text_buffer.append(result.text)

            # Fire partial callback
            if self.on_partial and not result.is_final:
                try:
                    self.on_partial(result)
                except Exception as e:
                    _logger.error(f"on_partial callback error: {e}")

            return result

        # Not enough audio yet
        return STTResult(
            text="",
            confidence=0.0,
            language=self.config.language,
            duration_seconds=len(self._stream_buffer) / self.config.sample_rate,
            is_final=False
        )

    def finalize(self) -> STTResult:
        """Finalize streaming and get final result.

        Returns:
            Final STTResult combining all streaming chunks
        """
        if not self._is_streaming and len(self._stream_buffer) == 0:
            return STTResult.empty(self.config.language)

        # Process any remaining audio
        if len(self._stream_buffer) > 0:
            audio = np.array(list(self._stream_buffer), dtype=np.float32)
            duration = len(audio) / self.config.sample_rate

            if self.mock_mode:
                result = self._mock_transcribe(audio, duration, is_final=True)
            else:
                result = self._backend_transcribe(audio, duration, is_final=True)
        else:
            # Combine buffered text
            combined_text = " ".join(self._stream_text_buffer)
            result = STTResult(
                text=combined_text,
                confidence=0.8 if combined_text else 0.0,
                language=self.config.language,
                duration_seconds=0.0,
                is_final=True
            )

        # Clear state
        self._stream_buffer.clear()
        self._stream_text_buffer.clear()
        self._is_streaming = False

        # Fire callback
        if self.on_result:
            try:
                self.on_result(result)
            except Exception as e:
                _logger.error(f"on_result callback error: {e}")

        return result

    def _normalize_input(self, audio: np.ndarray) -> np.ndarray:
        """Normalize audio input to float32."""
        if audio.ndim > 1:
            audio = audio.flatten()

        if audio.dtype == np.int16:
            audio = audio.astype(np.float32) / 32768.0
        elif audio.dtype != np.float32:
            audio = audio.astype(np.float32)

        return audio

    def _mock_transcribe(
        self,
        audio: np.ndarray,
        duration: float,
        is_final: bool = True
    ) -> STTResult:
        """Mock transcription for development.

        In mock mode, generates placeholder text based on audio characteristics.
        """
        # Calculate energy to simulate confidence
        rms = np.sqrt(np.mean(audio ** 2))
        energy_db = 20 * np.log10(rms + 1e-10)

        # Generate mock text based on energy
        if energy_db < -50:
            # Very quiet - no speech
            text = ""
            confidence = 0.0
        elif energy_db < -30:
            # Low energy - uncertain
            text = "[inaudible]" if is_final else ""
            confidence = 0.3
        else:
            # Normal speech - mock transcription
            if is_final:
                # Simulate realistic phrases for mock mode
                mock_phrases = [
                    "hello openduck",
                    "what time is it",
                    "turn on the lights",
                    "play some music",
                    "tell me a joke",
                ]
                # Use audio characteristics to select phrase (deterministic)
                phrase_idx = int(abs(audio[0] * 1000)) % len(mock_phrases)
                text = mock_phrases[phrase_idx]
                confidence = min(0.95, 0.5 + (energy_db + 50) / 40)
            else:
                # Partial result
                text = "hello..."
                confidence = 0.6

        return STTResult(
            text=text,
            confidence=confidence,
            language=self.config.language,
            duration_seconds=duration,
            is_final=is_final
        )

    def _init_backend(self) -> None:
        """Initialize the specified backend."""
        backend = self.config.backend.lower()

        if backend == "whisper":
            self._init_whisper()
        elif backend == "vosk":
            self._init_vosk()
        elif backend == "google":
            self._init_google()
        else:
            _logger.warning(f"Unknown backend '{backend}', using mock mode")
            self.mock_mode = True
            self._is_ready = True

    def _init_whisper(self) -> None:
        """Initialize Whisper backend.

        Tries faster-whisper first (optimized for CPU/edge deployment),
        falls back to openai-whisper if not available.

        faster-whisper advantages:
        - 4x faster on CPU via CTranslate2
        - Lower memory usage
        - Better for Raspberry Pi deployment
        """
        # Try faster-whisper first (preferred for Pi)
        try:
            from faster_whisper import WhisperModel

            # Model size mapping for faster-whisper
            # tiny, base, small, medium, large-v2, large-v3
            model_size = self.config.model_size
            if model_size == "large":
                model_size = "large-v3"

            _logger.info(f"Loading faster-whisper model: {model_size}")

            # For Raspberry Pi, use int8 quantization for speed
            # compute_type options: float32, float16, int8, int8_float16
            self._backend = WhisperModel(
                model_size,
                device="cpu",
                compute_type="int8",  # Optimized for Pi CPU
                cpu_threads=4,  # Pi 4 has 4 cores
                download_root=None  # Use default cache
            )
            self._backend_type = "faster-whisper"
            self._is_ready = True
            _logger.info(f"faster-whisper initialized: {model_size} (int8)")
            return

        except ImportError:
            _logger.info("faster-whisper not installed, trying openai-whisper")
        except Exception as e:
            _logger.warning(f"faster-whisper init failed: {e}, trying openai-whisper")

        # Fallback to openai-whisper
        try:
            import whisper
            _logger.info(f"Loading openai-whisper model: {self.config.model_size}")
            self._backend = whisper.load_model(self.config.model_size)
            self._backend_type = "openai-whisper"
            self._is_ready = True
            _logger.info("openai-whisper backend initialized")
        except ImportError:
            _logger.warning(
                "Neither faster-whisper nor openai-whisper installed. "
                "Install with: pip install faster-whisper"
            )
            self.mock_mode = True
            self._is_ready = True
        except Exception as e:
            _logger.error(f"Whisper initialization failed: {e}")
            self.mock_mode = True
            self._is_ready = True

    def _init_vosk(self) -> None:
        """Initialize Vosk backend."""
        try:
            import vosk
            _logger.info("Vosk backend not yet fully implemented, using mock")
            self.mock_mode = True
            self._is_ready = True
        except ImportError:
            _logger.warning("Vosk not installed, using mock mode")
            self.mock_mode = True
            self._is_ready = True

    def _init_google(self) -> None:
        """Initialize Google Speech backend."""
        try:
            import google.cloud.speech
            _logger.info("Google Speech backend not yet fully implemented, using mock")
            self.mock_mode = True
            self._is_ready = True
        except ImportError:
            _logger.warning("Google Cloud Speech not installed, using mock mode")
            self.mock_mode = True
            self._is_ready = True

    def _backend_transcribe(
        self,
        audio: np.ndarray,
        duration: float,
        is_final: bool = True
    ) -> STTResult:
        """Run transcription using the configured backend."""
        backend = self.config.backend.lower()

        if backend == "whisper" and self._backend is not None:
            return self._whisper_transcribe(audio, duration, is_final)

        # Fallback to mock for unimplemented backends
        return self._mock_transcribe(audio, duration, is_final)

    def _whisper_transcribe(
        self,
        audio: np.ndarray,
        duration: float,
        is_final: bool = True
    ) -> STTResult:
        """Transcribe using Whisper (faster-whisper or openai-whisper)."""
        backend_type = getattr(self, '_backend_type', 'openai-whisper')

        if backend_type == "faster-whisper":
            return self._faster_whisper_transcribe(audio, duration, is_final)
        else:
            return self._openai_whisper_transcribe(audio, duration, is_final)

    def _faster_whisper_transcribe(
        self,
        audio: np.ndarray,
        duration: float,
        is_final: bool = True
    ) -> STTResult:
        """Transcribe using faster-whisper (CTranslate2 backend)."""
        try:
            # faster-whisper expects float32 audio at 16kHz
            if audio.dtype != np.float32:
                audio = audio.astype(np.float32)

            # Transcribe with faster-whisper
            language = None if self.config.language == "auto" else self.config.language

            segments, info = self._backend.transcribe(
                audio,
                language=language,
                beam_size=5,
                vad_filter=self.config.vad_filter,
                vad_parameters={
                    "min_silence_duration_ms": 500,
                    "speech_pad_ms": 200,
                }
            )

            # Collect segments
            text_parts = []
            words_list = []
            total_confidence = 0.0
            segment_count = 0

            for segment in segments:
                text_parts.append(segment.text.strip())
                segment_count += 1

                # Collect word timings if available
                if hasattr(segment, 'words') and segment.words:
                    for word in segment.words:
                        words_list.append({
                            "word": word.word,
                            "start": word.start,
                            "end": word.end,
                            "probability": word.probability
                        })
                        total_confidence += word.probability

            # Calculate average confidence
            if words_list:
                avg_confidence = total_confidence / len(words_list)
            elif segment_count > 0:
                avg_confidence = 0.85  # Default for segments without word timing
            else:
                avg_confidence = 0.0

            full_text = " ".join(text_parts).strip()

            return STTResult(
                text=full_text,
                confidence=avg_confidence,
                language=info.language if info.language else self.config.language,
                duration_seconds=duration,
                is_final=is_final,
                words=words_list
            )

        except Exception as e:
            _logger.error(f"faster-whisper transcription failed: {e}")
            return self._mock_transcribe(audio, duration, is_final)

    def _openai_whisper_transcribe(
        self,
        audio: np.ndarray,
        duration: float,
        is_final: bool = True
    ) -> STTResult:
        """Transcribe using openai-whisper."""
        try:
            # Whisper expects float32 audio
            result = self._backend.transcribe(
                audio,
                language=None if self.config.language == "auto" else self.config.language,
                fp16=False  # Use FP32 for CPU
            )

            return STTResult(
                text=result["text"].strip(),
                confidence=0.9,  # Whisper doesn't provide confidence
                language=result.get("language", self.config.language),
                duration_seconds=duration,
                is_final=is_final
            )
        except Exception as e:
            _logger.error(f"openai-whisper transcription failed: {e}")
            return self._mock_transcribe(audio, duration, is_final)

    def __repr__(self) -> str:
        """String representation."""
        return (
            f"SpeechToText(language={self.config.language}, "
            f"backend={self.config.backend}, ready={self._is_ready}, "
            f"streaming={self._is_streaming})"
        )
