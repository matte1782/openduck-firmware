"""Wake Word Detection for OpenDuck Mini V3

This module provides wake word detection with:
- Support for custom wake words ("hey openduck", etc.)
- Configurable sensitivity
- Integration with VAD for efficient processing
- Mock mode for development without external dependencies

Production Implementation Options:
1. Porcupine (Picovoice) - Lightweight, offline, commercial
2. Vosk - Offline, open-source, supports custom models
3. Snowboy - Offline, but deprecated
4. OpenWakeWord - Offline, open-source

This module provides a common interface that can wrap any of these backends.
By default, it uses a simple energy-based mock for development.

Example:
    ```python
    from src.voice.wake_word import WakeWordDetector, WakeWordConfig

    # Create detector
    config = WakeWordConfig(wake_words=["hey openduck"], sensitivity=0.5)
    detector = WakeWordDetector(config)

    # Set up callback
    detector.on_wake_word = lambda r: print(f"Detected: {r.wake_word}!")

    # Start listening
    detector.start()

    # Process audio frames
    while True:
        frame = get_audio_frame()
        result = detector.process_frame(frame)
        if result.detected:
            print("Wake word detected!")
            break

    detector.stop()
    ```

Thread Safety:
    WakeWordDetector is NOT thread-safe. Use one instance per thread.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Callable, List, Optional, Any

import numpy as np

_logger = logging.getLogger(__name__)


@dataclass
class WakeWordConfig:
    """Configuration for wake word detection.

    Attributes:
        wake_words: List of wake words to detect (default: ["hey openduck"])
        sensitivity: Detection sensitivity 0.0-1.0 (default: 0.5)
            Higher = more detections (more false positives)
            Lower = fewer detections (more false negatives)
        sample_rate: Audio sample rate in Hz (default: 16000)
        frame_size_ms: Frame size for streaming detection (default: 20)
        backend: Detection backend to use (default: "mock")
            Options: "mock", "porcupine", "vosk", "openwakeword"
    """
    wake_words: List[str] = field(default_factory=lambda: ["hey openduck"])
    sensitivity: float = 0.5
    sample_rate: int = 16000
    frame_size_ms: int = 20
    backend: str = "mock"

    def __post_init__(self) -> None:
        """Validate configuration."""
        if not self.wake_words:
            raise ValueError("wake_words cannot be empty")
        if not (0.0 < self.sensitivity <= 1.0):
            raise ValueError(
                f"sensitivity must be in (0, 1], got {self.sensitivity}"
            )
        if self.sample_rate <= 0:
            raise ValueError(f"sample_rate must be positive, got {self.sample_rate}")

    @property
    def frame_samples(self) -> int:
        """Calculate samples per frame."""
        return int(self.sample_rate * self.frame_size_ms / 1000)


@dataclass
class WakeWordResult:
    """Result from wake word detection.

    Attributes:
        detected: Whether wake word was detected
        wake_word: Which wake word was detected (None if not detected)
        confidence: Detection confidence (0.0 to 1.0)
        timestamp: When detection occurred (monotonic time)
        audio_start_sample: Start sample index in audio buffer
        audio_end_sample: End sample index in audio buffer
    """
    detected: bool
    wake_word: Optional[str]
    confidence: float
    timestamp: float
    audio_start_sample: int = 0
    audio_end_sample: int = 0

    @staticmethod
    def not_detected(timestamp: Optional[float] = None) -> WakeWordResult:
        """Create a non-detection result."""
        return WakeWordResult(
            detected=False,
            wake_word=None,
            confidence=0.0,
            timestamp=timestamp or time.monotonic(),
            audio_start_sample=0,
            audio_end_sample=0
        )


class WakeWordDetector:
    """Wake word detector with multiple backend support.

    Provides a unified interface for wake word detection that can use
    different backends (Porcupine, Vosk, etc.) or a simple mock for testing.

    Attributes:
        config: Wake word configuration
        mock_mode: Whether running in mock mode
        is_listening: Whether detector is actively listening
        on_wake_word: Callback for wake word detection events
    """

    def __init__(
        self,
        config: Optional[WakeWordConfig] = None,
        mock_mode: bool = False
    ) -> None:
        """Initialize wake word detector.

        Args:
            config: Wake word configuration (uses defaults if None)
            mock_mode: Force mock mode regardless of config.backend
        """
        self.config = config or WakeWordConfig()
        self.mock_mode = mock_mode or self.config.backend == "mock"

        self._is_listening = False
        # Use numpy ring buffer for memory efficiency (avoid Python list overhead)
        self._buffer_size = self.config.sample_rate * 3  # 3 sec buffer
        self._audio_buffer = np.zeros(self._buffer_size, dtype=np.float32)
        self._buffer_pos = 0
        self._buffer_filled = 0
        # Use modulo to prevent integer overflow in long-running systems
        self._total_samples_processed = 0
        self._SAMPLE_COUNTER_MAX = 2**30  # ~18.6 hours at 16kHz before wrap

        # Callback
        self.on_wake_word: Optional[Callable[[WakeWordResult], None]] = None

        # Backend-specific initialization
        self._backend = None
        if not self.mock_mode:
            self._init_backend()

        _logger.info(
            f"WakeWordDetector initialized: wake_words={self.config.wake_words}, "
            f"sensitivity={self.config.sensitivity}, mock_mode={self.mock_mode}"
        )

    @property
    def is_listening(self) -> bool:
        """Check if detector is actively listening."""
        return self._is_listening

    def start(self) -> None:
        """Start wake word detection.

        After calling start(), the detector will process audio frames
        and emit callbacks when wake words are detected.
        """
        if self._is_listening:
            _logger.warning("WakeWordDetector already listening")
            return

        self._is_listening = True
        self._audio_buffer.fill(0)
        self._buffer_pos = 0
        self._buffer_filled = 0
        _logger.info("WakeWordDetector started")

    def stop(self) -> None:
        """Stop wake word detection.

        Stops processing and clears the audio buffer.
        """
        if not self._is_listening:
            return

        self._is_listening = False
        _logger.info("WakeWordDetector stopped")

    def reset(self) -> None:
        """Reset detector state.

        Clears audio buffer and resets counters.
        """
        self._audio_buffer.fill(0)
        self._buffer_pos = 0
        self._buffer_filled = 0
        self._total_samples_processed = 0
        self._is_listening = False
        _logger.debug("WakeWordDetector reset")

    def process_audio(self, audio: np.ndarray) -> WakeWordResult:
        """Process a chunk of audio for wake word detection.

        Args:
            audio: Audio samples (float32, -1 to 1 range)

        Returns:
            WakeWordResult indicating if wake word was detected
        """
        if len(audio) == 0:
            return WakeWordResult.not_detected()

        # Normalize input
        audio = self._normalize_input(audio)

        # Add to ring buffer (memory-efficient numpy array)
        n_samples = len(audio)
        if n_samples >= self._buffer_size:
            # Audio larger than buffer - just keep last buffer_size samples
            self._audio_buffer[:] = audio[-self._buffer_size:]
            self._buffer_pos = 0
            self._buffer_filled = self._buffer_size
        else:
            # Add to ring buffer
            end_pos = self._buffer_pos + n_samples
            if end_pos <= self._buffer_size:
                self._audio_buffer[self._buffer_pos:end_pos] = audio
            else:
                # Wrap around
                first_part = self._buffer_size - self._buffer_pos
                self._audio_buffer[self._buffer_pos:] = audio[:first_part]
                self._audio_buffer[:n_samples - first_part] = audio[first_part:]
            self._buffer_pos = end_pos % self._buffer_size
            self._buffer_filled = min(self._buffer_filled + n_samples, self._buffer_size)

        # Update sample counter with wrap-around to prevent overflow
        self._total_samples_processed = (self._total_samples_processed + n_samples) % self._SAMPLE_COUNTER_MAX

        # Run detection
        if self.mock_mode:
            return self._mock_detect(audio)
        else:
            return self._backend_detect(audio)

    def process_frame(self, frame: np.ndarray) -> WakeWordResult:
        """Process a single audio frame (streaming mode).

        Args:
            frame: Audio frame (typically 20ms)

        Returns:
            WakeWordResult
        """
        if not self._is_listening:
            return WakeWordResult.not_detected()

        return self.process_audio(frame)

    def _simulate_detection(self, wake_word: str, confidence: float) -> None:
        """Simulate a wake word detection (for testing).

        Args:
            wake_word: Wake word that was "detected"
            confidence: Simulated confidence
        """
        result = WakeWordResult(
            detected=True,
            wake_word=wake_word,
            confidence=confidence,
            timestamp=time.monotonic(),
            audio_start_sample=max(0, self._total_samples_processed - 16000),
            audio_end_sample=self._total_samples_processed
        )

        if self.on_wake_word:
            try:
                self.on_wake_word(result)
            except Exception as e:
                _logger.error(f"on_wake_word callback error: {e}")

    def _normalize_input(self, audio: np.ndarray) -> np.ndarray:
        """Normalize audio input to float32."""
        if audio.ndim > 1:
            audio = audio.flatten()

        if audio.dtype == np.int16:
            audio = audio.astype(np.float32) / 32768.0
        elif audio.dtype != np.float32:
            audio = audio.astype(np.float32)

        return audio

    def _mock_detect(self, audio: np.ndarray) -> WakeWordResult:
        """Mock detection based on energy (for development).

        In mock mode, we detect "wake word" when:
        1. Audio energy exceeds a threshold
        2. Energy pattern matches speech-like characteristics

        This is NOT accurate - use a real backend for production!
        """
        # Handle NaN in audio
        if np.any(np.isnan(audio)):
            audio = np.nan_to_num(audio, nan=0.0)

        # Calculate energy with safe RMS
        rms = max(np.sqrt(np.mean(audio ** 2)), 1e-10)
        energy_db = 20 * np.log10(rms)

        # Simple heuristic: detect if energy > -30dB and we have enough audio
        # Adjusted by sensitivity
        threshold_db = -30 - (self.config.sensitivity * 20)

        if energy_db > threshold_db and self._buffer_filled > self.config.sample_rate:
            # Get buffer as contiguous array for analysis
            buffer_array = self._get_buffer_contents()[-self.config.sample_rate:]
            frame_energies = []

            for i in range(0, len(buffer_array) - 320, 320):
                frame = buffer_array[i:i+320]
                frame_rms = np.sqrt(np.mean(frame ** 2))
                frame_energies.append(frame_rms)

            if frame_energies:
                energy_variance = np.var(frame_energies)

                # Speech has variance, pure tone doesn't
                if energy_variance > 0.0001:
                    # Fix: ensure confidence is always in [0.0, 1.0]
                    confidence = max(0.0, min(1.0, (energy_db + 50) / 30 * self.config.sensitivity))

                    result = WakeWordResult(
                        detected=True,
                        wake_word=self.config.wake_words[0],  # Mock always detects first word
                        confidence=confidence,
                        timestamp=time.monotonic(),
                        audio_start_sample=max(0, self._total_samples_processed - self.config.sample_rate),
                        audio_end_sample=self._total_samples_processed
                    )

                    # Clear buffer to prevent re-detection
                    self._audio_buffer.fill(0)
                    self._buffer_pos = 0
                    self._buffer_filled = 0

                    if self.on_wake_word:
                        try:
                            self.on_wake_word(result)
                        except Exception as e:
                            _logger.error(f"on_wake_word callback error: {e}")

                    return result

        return WakeWordResult.not_detected()

    def _get_buffer_contents(self) -> np.ndarray:
        """Get buffer contents as contiguous array.

        Returns:
            Numpy array with buffer contents in correct order
        """
        if self._buffer_filled < self._buffer_size:
            # Buffer not full yet - return from start to buffer_pos
            return self._audio_buffer[:self._buffer_filled].copy()
        else:
            # Ring buffer is full - reconstruct in order
            return np.concatenate([
                self._audio_buffer[self._buffer_pos:],
                self._audio_buffer[:self._buffer_pos]
            ])

    def _init_backend(self) -> None:
        """Initialize the specified backend."""
        backend = self.config.backend.lower()

        if backend == "porcupine":
            self._init_porcupine()
        elif backend == "vosk":
            self._init_vosk()
        elif backend == "openwakeword":
            self._init_openwakeword()
        else:
            _logger.warning(f"Unknown backend '{backend}', using mock mode")
            self.mock_mode = True

    def _init_porcupine(self) -> None:
        """Initialize Porcupine backend."""
        try:
            import pvporcupine
            # Note: Requires access key and keyword files
            _logger.info("Porcupine backend not yet implemented, using mock")
            self.mock_mode = True
        except ImportError:
            _logger.warning("Porcupine not installed, using mock mode")
            self.mock_mode = True

    def _init_vosk(self) -> None:
        """Initialize Vosk backend."""
        try:
            import vosk
            _logger.info("Vosk backend not yet implemented, using mock")
            self.mock_mode = True
        except ImportError:
            _logger.warning("Vosk not installed, using mock mode")
            self.mock_mode = True

    def _init_openwakeword(self) -> None:
        """Initialize OpenWakeWord backend.

        OpenWakeWord provides pre-trained models for common wake words
        and supports custom model training. Default models include:
        - "alexa" - Amazon's wake word
        - "hey_jarvis" - Similar to our use case
        - "hey_mycroft" - Open source assistant

        For custom "hey openduck", we'd need to train a model.
        For now, we use "hey_jarvis" as closest match.
        """
        try:
            import openwakeword
            from openwakeword.model import Model

            # Map our wake words to OpenWakeWord models
            # Available: alexa, hey_jarvis, hey_mycroft, etc.
            model_mapping = {
                "hey openduck": "hey_jarvis",  # Closest match
                "hey jarvis": "hey_jarvis",
                "alexa": "alexa",
                "hey mycroft": "hey_mycroft",
            }

            # Find models to load
            models_to_load = []
            for wake_word in self.config.wake_words:
                wake_word_lower = wake_word.lower().strip()
                if wake_word_lower in model_mapping:
                    models_to_load.append(model_mapping[wake_word_lower])
                else:
                    _logger.warning(
                        f"No OpenWakeWord model for '{wake_word}', "
                        f"using 'hey_jarvis' as fallback"
                    )
                    models_to_load.append("hey_jarvis")

            # Remove duplicates while preserving order
            models_to_load = list(dict.fromkeys(models_to_load))

            # Download models if needed and initialize
            _logger.info(f"Loading OpenWakeWord models: {models_to_load}")
            openwakeword.utils.download_models(models_to_load)

            # Create model instance
            # inference_framework can be "onnx" or "tflite"
            self._backend = Model(
                wakeword_models=models_to_load,
                inference_framework="onnx"
            )
            self._oww_models = models_to_load
            self._oww_threshold = 0.5 + (self.config.sensitivity - 0.5) * 0.3

            _logger.info(
                f"OpenWakeWord initialized with models: {models_to_load}, "
                f"threshold: {self._oww_threshold:.2f}"
            )

        except ImportError:
            _logger.warning(
                "OpenWakeWord not installed. Install with: "
                "pip install openwakeword"
            )
            self.mock_mode = True
        except Exception as e:
            _logger.error(f"OpenWakeWord initialization failed: {e}")
            self.mock_mode = True

    def _backend_detect(self, audio: np.ndarray) -> WakeWordResult:
        """Run detection using the configured backend."""
        backend = self.config.backend.lower()

        if backend == "openwakeword" and self._backend is not None:
            return self._openwakeword_detect(audio)

        # Fallback to mock for unimplemented backends
        return self._mock_detect(audio)

    def _openwakeword_detect(self, audio: np.ndarray) -> WakeWordResult:
        """Detect wake word using OpenWakeWord.

        OpenWakeWord expects:
        - 16kHz sample rate
        - Mono audio
        - int16 or float32 format
        - Chunks of 1280 samples (80ms at 16kHz)
        """
        try:
            # OpenWakeWord expects int16 audio
            if audio.dtype == np.float32:
                audio_int16 = (audio * 32767).astype(np.int16)
            else:
                audio_int16 = audio.astype(np.int16)

            # Process audio through OpenWakeWord
            # It processes 80ms chunks internally
            prediction = self._backend.predict(audio_int16)

            # Check each model's prediction
            for model_name in self._oww_models:
                if model_name in prediction:
                    score = prediction[model_name]

                    if score > self._oww_threshold:
                        # Map back to original wake word
                        detected_wake_word = self.config.wake_words[0]  # Default
                        for ww in self.config.wake_words:
                            if model_name in ww.lower().replace(" ", "_"):
                                detected_wake_word = ww
                                break

                        result = WakeWordResult(
                            detected=True,
                            wake_word=detected_wake_word,
                            confidence=float(score),
                            timestamp=time.monotonic(),
                            audio_start_sample=max(0, self._total_samples_processed - self.config.sample_rate),
                            audio_end_sample=self._total_samples_processed
                        )

                        # Reset model state to prevent retriggering
                        self._backend.reset()

                        # Clear buffer
                        self._audio_buffer.fill(0)
                        self._buffer_pos = 0
                        self._buffer_filled = 0

                        # Fire callback
                        if self.on_wake_word:
                            try:
                                self.on_wake_word(result)
                            except Exception as e:
                                _logger.error(f"on_wake_word callback error: {e}")

                        _logger.info(
                            f"Wake word detected: '{detected_wake_word}' "
                            f"(model: {model_name}, score: {score:.3f})"
                        )
                        return result

            return WakeWordResult.not_detected()

        except Exception as e:
            _logger.error(f"OpenWakeWord detection error: {e}")
            return WakeWordResult.not_detected()

    def __repr__(self) -> str:
        """String representation."""
        return (
            f"WakeWordDetector(wake_words={self.config.wake_words}, "
            f"listening={self._is_listening}, mock={self.mock_mode})"
        )
