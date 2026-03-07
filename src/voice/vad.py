"""Voice Activity Detection (VAD) for OpenDuck Mini V3

This module provides energy-based voice activity detection with:
- Configurable energy threshold
- State machine with hysteresis (prevents rapid toggling)
- Event callbacks for speech start/end
- Streaming frame-by-frame processing
- Statistics tracking

The VAD uses simple energy-based detection which is:
- Fast and low-latency (<2ms per frame)
- No external dependencies (pure numpy)
- Suitable for embedded/edge deployment
- Configurable for different environments

For more accurate VAD in noisy environments, consider using
WebRTC VAD or Silero VAD as drop-in replacements.

Example:
    ```python
    from src.voice.vad import VoiceActivityDetector, VADConfig

    # Create VAD with custom threshold
    vad = VoiceActivityDetector(VADConfig(energy_threshold_db=-35.0))

    # Set up callbacks
    vad.on_speech_start = lambda r: print("Speech started!")
    vad.on_speech_end = lambda r: print("Speech ended!")

    # Process audio frames (20ms at 16kHz = 320 samples)
    while True:
        frame = get_audio_frame()  # Your audio source
        result = vad.process_frame(frame)
        if result.is_speech:
            print(f"Speaking at {result.energy_db:.1f} dB")
    ```

Thread Safety:
    VoiceActivityDetector is NOT thread-safe. Use one instance per thread,
    or protect with external locking if sharing across threads.
"""

from __future__ import annotations

import logging
import math
import time
from collections import deque
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Callable, Dict, List, Optional, Any

import numpy as np

_logger = logging.getLogger(__name__)


class VADState(Enum):
    """Voice Activity Detection state machine states.

    State transitions:
        SILENCE → SPEECH (when energy > threshold for min_speech_ms)
        SPEECH → SILENCE (when energy < threshold for min_silence_ms)
        UNCERTAIN is used during transition periods
    """
    SILENCE = auto()
    SPEECH = auto()
    UNCERTAIN = auto()


class VADEvent(Enum):
    """Events emitted by VAD state machine.

    NONE: No state change
    SPEECH_START: Transition from silence to confirmed speech
    SPEECH_END: Transition from speech to confirmed silence
    """
    NONE = auto()
    SPEECH_START = auto()
    SPEECH_END = auto()


@dataclass
class VADConfig:
    """Configuration for Voice Activity Detection.

    Attributes:
        sample_rate: Audio sample rate in Hz (default: 16000)
        frame_size_ms: Frame size in milliseconds (default: 20)
        energy_threshold_db: dB threshold for speech detection (default: -40.0)
            Lower values = more sensitive, higher values = less sensitive
        min_speech_ms: Minimum duration to confirm speech start (default: 100)
        min_silence_ms: Minimum duration to confirm speech end (default: 300)
        smoothing_frames: Number of frames to average for energy smoothing (default: 3)
        adaptive_threshold: Enable adaptive threshold adjustment (default: False)
    """
    sample_rate: int = 16000
    frame_size_ms: int = 20
    energy_threshold_db: float = -40.0
    min_speech_ms: int = 100
    min_silence_ms: int = 300
    smoothing_frames: int = 3
    adaptive_threshold: bool = False

    def __post_init__(self) -> None:
        """Validate configuration parameters."""
        if self.sample_rate <= 0:
            raise ValueError(f"sample_rate must be positive, got {self.sample_rate}")
        if self.frame_size_ms < 5:
            raise ValueError(f"frame_size_ms must be at least 5ms, got {self.frame_size_ms}")
        if self.energy_threshold_db > 0:
            raise ValueError(
                f"energy_threshold_db must be <= 0 (dB relative to full scale), "
                f"got {self.energy_threshold_db}"
            )
        if self.min_speech_ms < 10:
            raise ValueError(f"min_speech_ms must be at least 10ms, got {self.min_speech_ms}")
        if self.min_silence_ms < 10:
            raise ValueError(f"min_silence_ms must be at least 10ms, got {self.min_silence_ms}")
        if self.smoothing_frames < 1:
            raise ValueError(f"smoothing_frames must be at least 1, got {self.smoothing_frames}")

    @property
    def frame_samples(self) -> int:
        """Calculate number of samples per frame."""
        return int(self.sample_rate * self.frame_size_ms / 1000)

    @property
    def min_speech_frames(self) -> int:
        """Calculate minimum frames to confirm speech."""
        return max(1, int(self.min_speech_ms / self.frame_size_ms))

    @property
    def min_silence_frames(self) -> int:
        """Calculate minimum frames to confirm silence."""
        return max(1, int(self.min_silence_ms / self.frame_size_ms))


@dataclass
class VADResult:
    """Result from processing a single audio frame.

    Attributes:
        is_speech: Whether current frame is detected as speech
        state: Current VAD state machine state
        event: Event triggered by this frame (if any)
        energy_db: Frame energy level in dB (0 dB = full scale)
        confidence: Detection confidence (0.0 to 1.0)
        timestamp: Monotonic timestamp when frame was processed
    """
    is_speech: bool
    state: VADState
    event: VADEvent
    energy_db: float
    confidence: float
    timestamp: float

    @staticmethod
    def silence(energy_db: float = -100.0, timestamp: Optional[float] = None) -> VADResult:
        """Create a silence result."""
        return VADResult(
            is_speech=False,
            state=VADState.SILENCE,
            event=VADEvent.NONE,
            energy_db=energy_db,
            confidence=1.0,
            timestamp=timestamp or time.monotonic()
        )


class VoiceActivityDetector:
    """Energy-based Voice Activity Detection.

    Detects speech vs. silence using RMS energy thresholding with
    hysteresis to prevent rapid state toggling.

    The state machine requires:
    - min_speech_ms of continuous above-threshold energy to trigger SPEECH_START
    - min_silence_ms of continuous below-threshold energy to trigger SPEECH_END

    This provides robust detection that ignores brief noise bursts and
    brief pauses within speech.

    Attributes:
        config: VAD configuration
        state: Current state machine state
        is_speech: Whether currently in speech state
        on_speech_start: Callback for speech start events
        on_speech_end: Callback for speech end events
    """

    def __init__(self, config: Optional[VADConfig] = None) -> None:
        """Initialize Voice Activity Detector.

        Args:
            config: VAD configuration (uses defaults if None)
        """
        self.config = config or VADConfig()

        # State machine
        self._state = VADState.SILENCE
        self._speech_frame_count = 0
        self._silence_frame_count = 0

        # Energy smoothing
        self._energy_history: deque = deque(maxlen=self.config.smoothing_frames)

        # Statistics
        self._total_frames = 0
        self._speech_frames = 0
        self._silence_frames = 0

        # Runtime threshold (can be adjusted)
        self._threshold_db = self.config.energy_threshold_db

        # Callbacks
        self.on_speech_start: Optional[Callable[[VADResult], None]] = None
        self.on_speech_end: Optional[Callable[[VADResult], None]] = None

        # Reentrancy guard to prevent callback corruption
        self._in_callback = False

        _logger.debug(
            f"VAD initialized: threshold={self._threshold_db}dB, "
            f"min_speech={self.config.min_speech_ms}ms, "
            f"min_silence={self.config.min_silence_ms}ms"
        )

    @property
    def state(self) -> VADState:
        """Get current VAD state."""
        return self._state

    @property
    def is_speech(self) -> bool:
        """Check if currently detecting speech."""
        return self._state == VADState.SPEECH

    def get_threshold_db(self) -> float:
        """Get current energy threshold in dB."""
        return self._threshold_db

    def set_threshold_db(self, threshold_db: float) -> None:
        """Set energy threshold at runtime.

        Args:
            threshold_db: New threshold in dB (must be <= 0)

        Raises:
            ValueError: If threshold is positive
        """
        if threshold_db > 0:
            raise ValueError(f"threshold_db must be <= 0, got {threshold_db}")
        self._threshold_db = threshold_db
        _logger.info(f"VAD threshold updated to {threshold_db}dB")

    def reset(self) -> None:
        """Reset VAD to initial state.

        Clears state machine, counters, and energy history.
        Does not clear statistics.
        """
        self._state = VADState.SILENCE
        self._speech_frame_count = 0
        self._silence_frame_count = 0
        self._energy_history.clear()
        _logger.debug("VAD reset to initial state")

    def process_frame(self, frame: np.ndarray) -> VADResult:
        """Process a single audio frame.

        Args:
            frame: Audio samples as numpy array. Accepts:
                - float32 normalized to [-1, 1]
                - int16 (will be converted to float32)
                Shape can be (N,) for mono or (N, 1) for single channel.

        Returns:
            VADResult with detection results and any triggered event

        Raises:
            ValueError: If frame is empty
        """
        # Input validation and conversion
        frame = self._normalize_input(frame)

        if len(frame) == 0:
            raise ValueError("Cannot process empty frame")

        # Calculate energy
        energy_db = self._calculate_energy_db(frame)

        # Apply smoothing
        self._energy_history.append(energy_db)
        smoothed_energy_db = sum(self._energy_history) / len(self._energy_history)

        # Determine if above threshold
        is_above_threshold = smoothed_energy_db > self._threshold_db

        # Update state machine
        event = self._update_state_machine(is_above_threshold)

        # Update statistics
        self._total_frames += 1
        if self._state == VADState.SPEECH:
            self._speech_frames += 1
        else:
            self._silence_frames += 1

        # Calculate confidence based on margin from threshold
        margin = abs(smoothed_energy_db - self._threshold_db)
        confidence = min(1.0, margin / 20.0)  # 20dB margin = full confidence

        # Create result
        result = VADResult(
            is_speech=self._state == VADState.SPEECH,
            state=self._state,
            event=event,
            energy_db=smoothed_energy_db,
            confidence=confidence,
            timestamp=time.monotonic()
        )

        # Fire callbacks with reentrancy protection
        # Prevents callbacks from calling process_frame/reset and corrupting state
        if not self._in_callback:
            self._in_callback = True
            try:
                if event == VADEvent.SPEECH_START and self.on_speech_start:
                    try:
                        self.on_speech_start(result)
                    except Exception as e:
                        _logger.error(f"on_speech_start callback error: {e}")

                elif event == VADEvent.SPEECH_END and self.on_speech_end:
                    try:
                        self.on_speech_end(result)
                    except Exception as e:
                        _logger.error(f"on_speech_end callback error: {e}")
            finally:
                self._in_callback = False

        return result

    def get_statistics(self) -> Dict[str, Any]:
        """Get VAD statistics.

        Returns:
            Dictionary with:
            - total_frames: Total frames processed
            - speech_frames: Frames classified as speech
            - silence_frames: Frames classified as silence
            - speech_ratio: Ratio of speech frames to total
            - current_state: Current state machine state
        """
        speech_ratio = (
            self._speech_frames / self._total_frames
            if self._total_frames > 0 else 0.0
        )

        return {
            'total_frames': self._total_frames,
            'speech_frames': self._speech_frames,
            'silence_frames': self._silence_frames,
            'speech_ratio': speech_ratio,
            'current_state': self._state.name,
            'threshold_db': self._threshold_db,
        }

    def _normalize_input(self, frame: np.ndarray) -> np.ndarray:
        """Normalize input to float32 in [-1, 1] range.

        Args:
            frame: Input audio frame

        Returns:
            Normalized float32 array
        """
        # Handle multi-dimensional input
        if frame.ndim > 1:
            frame = frame.flatten()

        # Convert dtype if needed
        if frame.dtype == np.int16:
            frame = frame.astype(np.float32) / 32768.0
        elif frame.dtype == np.int32:
            frame = frame.astype(np.float32) / 2147483648.0
        elif frame.dtype != np.float32:
            frame = frame.astype(np.float32)

        # Handle NaN and Inf
        if np.any(np.isnan(frame)) or np.any(np.isinf(frame)):
            _logger.warning("Frame contains NaN or Inf values, replacing with zeros")
            frame = np.nan_to_num(frame, nan=0.0, posinf=0.0, neginf=0.0)

        return frame

    def _calculate_energy_db(self, frame: np.ndarray) -> float:
        """Calculate RMS energy in dB.

        Args:
            frame: Normalized audio frame

        Returns:
            Energy level in dB (0 dB = full scale)
        """
        # RMS calculation
        rms = np.sqrt(np.mean(frame ** 2))

        # Convert to dB (with floor to avoid log(0))
        if rms < 1e-10:
            return -100.0

        return 20.0 * np.log10(rms)

    def _update_state_machine(self, is_above_threshold: bool) -> VADEvent:
        """Update VAD state machine based on threshold comparison.

        Args:
            is_above_threshold: Whether current frame energy exceeds threshold

        Returns:
            Event triggered by this state update (or NONE)
        """
        event = VADEvent.NONE

        if self._state == VADState.SILENCE:
            if is_above_threshold:
                self._speech_frame_count += 1
                self._silence_frame_count = 0

                if self._speech_frame_count >= self.config.min_speech_frames:
                    # Confirmed speech start
                    self._state = VADState.SPEECH
                    event = VADEvent.SPEECH_START
                    _logger.debug(
                        f"SPEECH_START after {self._speech_frame_count} frames"
                    )
            else:
                self._speech_frame_count = 0

        elif self._state == VADState.SPEECH:
            if not is_above_threshold:
                self._silence_frame_count += 1
                self._speech_frame_count = 0

                if self._silence_frame_count >= self.config.min_silence_frames:
                    # Confirmed speech end
                    self._state = VADState.SILENCE
                    event = VADEvent.SPEECH_END
                    _logger.debug(
                        f"SPEECH_END after {self._silence_frame_count} silence frames"
                    )
            else:
                self._silence_frame_count = 0

        return event

    def __repr__(self) -> str:
        """String representation."""
        return (
            f"VoiceActivityDetector(state={self._state.name}, "
            f"threshold={self._threshold_db}dB, "
            f"frames_processed={self._total_frames})"
        )
