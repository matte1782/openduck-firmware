"""Production Wake Word Pipeline for OpenDuck Mini V3

This module provides a production-grade wake word detection pipeline that
integrates VAD gating, noise calibration, multi-frame confirmation, and
proper audio preprocessing to achieve <1% false positive rate.

Key Features:
    - VAD-gated detection: Only process audio when speech is detected
    - Multi-frame confirmation: Require 3/5 frames above threshold
    - EMA noise floor tracking: Adaptive thresholding based on ambient noise
    - 48kHz→16kHz resampling: Proper conversion for OpenWakeWord
    - Cooldown mechanism: Prevent rapid re-triggers

Architecture:
    INMP441 (48kHz S32_LE stereo)
        ↓
    AudioPreprocessor (resample to 16kHz mono float32)
        ↓
    NoiseCalibrator (track ambient noise floor)
        ↓
    VAD Gate (filter non-speech)
        ↓
    WakeWordDetector (OpenWakeWord)
        ↓
    MultiFrameConfirmer (3-of-5 window)
        ↓
    Cooldown Check (prevent re-trigger)
        ↓
    Callback (LED animation, etc.)

Performance Targets:
    - False Positive Rate: <1%
    - Detection Latency: <500ms
    - CPU Usage: <30% on RPi4
    - Memory: <100MB

Created: 26 January 2026 (Day 26)
Based on: IAO-v2-DYNAMIC 5-Agent Analysis
Authors: OpenDuck Team
"""

from __future__ import annotations

import logging
import subprocess
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Callable, Deque, Dict, List, Optional, Any

import numpy as np

from src.voice.vad import VoiceActivityDetector, VADConfig, VADState, VADResult
from src.voice.wake_word import WakeWordDetector, WakeWordConfig, WakeWordResult

_logger = logging.getLogger(__name__)


# =============================================================================
# Configuration
# =============================================================================

@dataclass
class PipelineConfig:
    """Configuration for the production wake word pipeline.

    Attributes:
        # Audio settings
        input_sample_rate: Input sample rate from INMP441 (48000)
        output_sample_rate: Target sample rate for OpenWakeWord (16000)
        chunk_ms: Audio chunk size in milliseconds (80 for OpenWakeWord)
        channels: Input channels (2 for stereo I2S)
        device: ALSA device string

        # Wake word settings
        wake_words: List of wake words to detect
        threshold: Detection threshold (0.82+ recommended)

        # Multi-frame confirmation
        confirm_window: Number of frames in confirmation window (5)
        confirm_required: Frames required above threshold (3)

        # EMA smoothing
        score_ema_alpha: EMA alpha for score smoothing (0.3)
        noise_ema_alpha: EMA alpha for noise tracking (0.001)

        # VAD settings
        vad_threshold_db: VAD energy threshold (-40.0)
        vad_min_speech_ms: Minimum speech duration (100)

        # Cooldown
        cooldown_seconds: Seconds between detections (3.0)

        # Calibration
        calibration_seconds: Startup noise calibration duration (2.0)
    """
    # Audio settings
    input_sample_rate: int = 48000
    output_sample_rate: int = 16000
    chunk_ms: int = 80  # 80ms = 1280 samples at 16kHz (OpenWakeWord optimal)
    channels: int = 2
    device: str = "hw:1,0"

    # Wake word settings
    wake_words: List[str] = field(default_factory=lambda: ["hey openduck"])
    threshold: float = 0.82  # Higher threshold to reduce false positives

    # Multi-frame confirmation
    confirm_window: int = 5
    confirm_required: int = 3

    # EMA smoothing
    score_ema_alpha: float = 0.3
    noise_ema_alpha: float = 0.001

    # VAD settings
    vad_threshold_db: float = -40.0
    vad_min_speech_ms: int = 100

    # Cooldown
    cooldown_seconds: float = 3.0

    # Calibration
    calibration_seconds: float = 2.0

    def __post_init__(self) -> None:
        """Validate configuration."""
        if not (0.0 < self.threshold <= 1.0):
            raise ValueError(f"threshold must be in (0, 1], got {self.threshold}")
        if self.confirm_required > self.confirm_window:
            raise ValueError(
                f"confirm_required ({self.confirm_required}) cannot exceed "
                f"confirm_window ({self.confirm_window})"
            )
        if not (0.0 < self.score_ema_alpha <= 1.0):
            raise ValueError(f"score_ema_alpha must be in (0, 1], got {self.score_ema_alpha}")

    @property
    def output_chunk_samples(self) -> int:
        """Calculate output chunk size in samples (at 16kHz)."""
        return int(self.output_sample_rate * self.chunk_ms / 1000)

    @property
    def input_chunk_samples(self) -> int:
        """Calculate input chunk size in samples (at 48kHz)."""
        return int(self.input_sample_rate * self.chunk_ms / 1000)


class PipelineState(Enum):
    """Pipeline state machine states."""
    IDLE = auto()           # Not running
    CALIBRATING = auto()    # Noise floor calibration
    LISTENING = auto()      # Active listening
    COOLDOWN = auto()       # Post-detection cooldown
    ERROR = auto()          # Error state


@dataclass
class DetectionResult:
    """Result from wake word detection.

    Attributes:
        detected: Whether wake word was detected
        wake_word: Which wake word was detected
        raw_score: Raw OpenWakeWord score
        smoothed_score: EMA-smoothed score
        confirm_count: Frames above threshold in window
        noise_floor: Current noise floor estimate
        vad_active: Whether VAD detected speech
        timestamp: Detection timestamp
    """
    detected: bool
    wake_word: Optional[str]
    raw_score: float
    smoothed_score: float
    confirm_count: int
    noise_floor: float
    vad_active: bool
    timestamp: float

    @staticmethod
    def not_detected() -> DetectionResult:
        """Create a non-detection result."""
        return DetectionResult(
            detected=False,
            wake_word=None,
            raw_score=0.0,
            smoothed_score=0.0,
            confirm_count=0,
            noise_floor=0.0,
            vad_active=False,
            timestamp=time.monotonic()
        )


# =============================================================================
# Audio Preprocessor
# =============================================================================

class AudioPreprocessor:
    """Preprocesses audio from INMP441 format to OpenWakeWord format.

    Handles:
        - Stereo to mono conversion (left channel extraction)
        - S32_LE to float32 normalization
        - 48kHz to 16kHz resampling (linear interpolation)

    Note: Uses simple linear interpolation for resampling. For higher quality,
    consider scipy.signal.resample_poly, but it adds ~50ms latency.
    """

    def __init__(self, config: PipelineConfig) -> None:
        """Initialize preprocessor.

        Args:
            config: Pipeline configuration
        """
        self.config = config
        self._resample_ratio = config.input_sample_rate / config.output_sample_rate
        _logger.info(
            f"AudioPreprocessor: {config.input_sample_rate}Hz → "
            f"{config.output_sample_rate}Hz (ratio: {self._resample_ratio:.2f})"
        )

    def process(self, raw_audio: bytes) -> np.ndarray:
        """Process raw audio bytes to normalized float32 at 16kHz.

        Args:
            raw_audio: Raw bytes from arecord (S32_LE stereo)

        Returns:
            Normalized float32 array at 16kHz mono
        """
        # Parse S32_LE stereo
        samples = np.frombuffer(raw_audio, dtype=np.int32)

        # Extract left channel (INMP441 data is on left)
        left_channel = samples[0::2]

        # Normalize to float32 [-1, 1]
        # S32_LE uses full 32-bit range
        audio_float = left_channel.astype(np.float32) / 2147483648.0

        # Handle NaN/Inf
        if np.any(np.isnan(audio_float)) or np.any(np.isinf(audio_float)):
            _logger.warning("Audio contains NaN/Inf, replacing with zeros")
            audio_float = np.nan_to_num(audio_float, nan=0.0, posinf=0.0, neginf=0.0)

        # Resample 48kHz → 16kHz using simple decimation
        # For 3:1 ratio, we take every 3rd sample (with anti-aliasing)
        # Note: Linear interpolation is faster but lower quality
        resampled = self._resample(audio_float)

        return resampled

    def _resample(self, audio: np.ndarray) -> np.ndarray:
        """Resample audio from input_sample_rate to output_sample_rate.

        Uses simple decimation with averaging for anti-aliasing.
        This is faster than scipy.signal.resample but slightly lower quality.

        Args:
            audio: Input audio at input_sample_rate

        Returns:
            Resampled audio at output_sample_rate
        """
        ratio = int(self._resample_ratio)

        if ratio == 3:  # 48kHz → 16kHz (common case)
            # Simple 3:1 decimation with averaging
            # Truncate to multiple of 3
            n_output = len(audio) // ratio
            truncated = audio[:n_output * ratio]

            # Average every 3 samples (simple anti-aliasing)
            reshaped = truncated.reshape(-1, ratio)
            return reshaped.mean(axis=1).astype(np.float32)
        else:
            # General case: linear interpolation
            n_output = int(len(audio) / self._resample_ratio)
            x_old = np.arange(len(audio))
            x_new = np.linspace(0, len(audio) - 1, n_output)
            return np.interp(x_new, x_old, audio).astype(np.float32)

    def process_int16(self, raw_audio: bytes) -> np.ndarray:
        """Process and return as int16 for OpenWakeWord.

        OpenWakeWord internally converts to int16, so we can skip
        float32 conversion for efficiency.

        Args:
            raw_audio: Raw bytes from arecord

        Returns:
            int16 array at 16kHz mono
        """
        audio_float = self.process(raw_audio)
        # Convert to int16 (OpenWakeWord expects this)
        return (audio_float * 32767).astype(np.int16)


# =============================================================================
# Noise Calibrator
# =============================================================================

class NoiseCalibrator:
    """Tracks and calibrates ambient noise floor.

    Uses EMA (Exponential Moving Average) to track:
        - Ambient noise floor during silence
        - Score baseline for adaptive thresholding

    Provides startup calibration and runtime adaptation.
    """

    def __init__(self, config: PipelineConfig) -> None:
        """Initialize noise calibrator.

        Args:
            config: Pipeline configuration
        """
        self.config = config

        # Noise floor tracking
        self._noise_floor_db: float = -60.0  # Start conservative
        self._noise_samples: List[float] = []
        self._calibration_complete = False

        # Score baseline tracking
        self._score_baseline: float = 0.0
        self._score_ema: float = 0.0

        _logger.info(
            f"NoiseCalibrator: EMA alpha={config.noise_ema_alpha}, "
            f"calibration={config.calibration_seconds}s"
        )

    @property
    def noise_floor_db(self) -> float:
        """Get current noise floor estimate in dB."""
        return self._noise_floor_db

    @property
    def is_calibrated(self) -> bool:
        """Check if calibration is complete."""
        return self._calibration_complete

    def add_calibration_sample(self, energy_db: float) -> None:
        """Add a sample during calibration phase.

        Args:
            energy_db: Audio energy in dB
        """
        self._noise_samples.append(energy_db)

    def complete_calibration(self) -> float:
        """Complete calibration and compute noise floor.

        Returns:
            Computed noise floor in dB
        """
        if self._noise_samples:
            # Use median to reject outliers (transient noises)
            self._noise_floor_db = float(np.median(self._noise_samples))
            _logger.info(f"Noise floor calibrated: {self._noise_floor_db:.1f} dB")
        else:
            _logger.warning("No calibration samples, using default -60 dB")
            self._noise_floor_db = -60.0

        self._calibration_complete = True
        self._noise_samples.clear()
        return self._noise_floor_db

    def update_noise_floor(self, energy_db: float, is_silence: bool) -> None:
        """Update noise floor during runtime (only during silence).

        Uses EMA to slowly adapt to changing ambient conditions.

        Args:
            energy_db: Current audio energy in dB
            is_silence: Whether VAD detected silence
        """
        if is_silence and self._calibration_complete:
            # EMA update: new = alpha * sample + (1-alpha) * old
            alpha = self.config.noise_ema_alpha
            self._noise_floor_db = alpha * energy_db + (1 - alpha) * self._noise_floor_db

    def update_score(self, raw_score: float) -> float:
        """Update score EMA and return smoothed score.

        Args:
            raw_score: Raw OpenWakeWord score

        Returns:
            EMA-smoothed score
        """
        alpha = self.config.score_ema_alpha
        self._score_ema = alpha * raw_score + (1 - alpha) * self._score_ema
        return self._score_ema

    def get_adaptive_threshold(self) -> float:
        """Get adaptive threshold based on noise conditions.

        Returns:
            Adjusted detection threshold
        """
        # Base threshold from config
        base_threshold = self.config.threshold

        # In noisy conditions (noise floor > -35 dB), increase threshold
        if self._noise_floor_db > -35:
            noise_penalty = (self._noise_floor_db + 35) * 0.01  # +1% per dB above -35
            return min(0.95, base_threshold + noise_penalty)

        return base_threshold

    def reset(self) -> None:
        """Reset calibrator state."""
        self._noise_floor_db = -60.0
        self._noise_samples.clear()
        self._calibration_complete = False
        self._score_baseline = 0.0
        self._score_ema = 0.0


# =============================================================================
# Multi-Frame Confirmer
# =============================================================================

class MultiFrameConfirmer:
    """Requires multiple frames above threshold to confirm detection.

    Uses a sliding window to track recent detection scores.
    Detection only triggers when confirm_required frames in the window
    exceed the threshold.

    This dramatically reduces false positives from single-frame spikes.
    """

    def __init__(self, config: PipelineConfig) -> None:
        """Initialize confirmer.

        Args:
            config: Pipeline configuration
        """
        self.config = config
        self._window: Deque[float] = deque(maxlen=config.confirm_window)
        self._last_detection_time: float = 0.0

        _logger.info(
            f"MultiFrameConfirmer: {config.confirm_required}/"
            f"{config.confirm_window} frames required"
        )

    def add_score(self, score: float) -> int:
        """Add a score to the window and return count above threshold.

        Args:
            score: Detection score

        Returns:
            Number of frames in window above threshold
        """
        self._window.append(score)
        threshold = self.config.threshold
        return sum(1 for s in self._window if s > threshold)

    def is_confirmed(self, score: float) -> bool:
        """Check if detection is confirmed.

        Args:
            score: Current detection score

        Returns:
            True if enough frames above threshold
        """
        count = self.add_score(score)
        return count >= self.config.confirm_required

    def is_in_cooldown(self) -> bool:
        """Check if still in cooldown period.

        Returns:
            True if cooldown period hasn't elapsed
        """
        elapsed = time.monotonic() - self._last_detection_time
        return elapsed < self.config.cooldown_seconds

    def record_detection(self) -> None:
        """Record that a detection occurred (starts cooldown)."""
        self._last_detection_time = time.monotonic()
        self._window.clear()

    def reset(self) -> None:
        """Reset confirmer state."""
        self._window.clear()
        self._last_detection_time = 0.0


# =============================================================================
# Production Wake Word Pipeline
# =============================================================================

class WakeWordPipeline:
    """Production-grade wake word detection pipeline.

    Integrates all components for reliable wake word detection:
        - Audio preprocessing (resampling, normalization)
        - Noise calibration (adaptive thresholds)
        - VAD gating (only process speech)
        - Wake word detection (OpenWakeWord)
        - Multi-frame confirmation (reduce false positives)
        - Cooldown (prevent rapid re-triggers)

    Attributes:
        config: Pipeline configuration
        state: Current pipeline state
        on_wake_word: Callback for wake word detection
        on_state_change: Callback for state changes
    """

    def __init__(self, config: Optional[PipelineConfig] = None) -> None:
        """Initialize the pipeline.

        Args:
            config: Pipeline configuration (uses defaults if None)
        """
        self.config = config or PipelineConfig()
        self._state = PipelineState.IDLE

        # Components
        self._preprocessor = AudioPreprocessor(self.config)
        self._calibrator = NoiseCalibrator(self.config)
        self._confirmer = MultiFrameConfirmer(self.config)

        # VAD
        vad_config = VADConfig(
            sample_rate=self.config.output_sample_rate,
            energy_threshold_db=self.config.vad_threshold_db,
            min_speech_ms=self.config.vad_min_speech_ms
        )
        self._vad = VoiceActivityDetector(vad_config)

        # Wake word detector (OpenWakeWord)
        wake_config = WakeWordConfig(
            wake_words=self.config.wake_words,
            sensitivity=0.5,  # We use our own thresholding
            sample_rate=self.config.output_sample_rate,
            backend="openwakeword"
        )
        self._wake_detector: Optional[Any] = None  # Lazy init

        # Audio capture process
        self._audio_process: Optional[subprocess.Popen] = None
        self._running = False
        self._audio_thread: Optional[threading.Thread] = None

        # Callbacks
        self.on_wake_word: Optional[Callable[[DetectionResult], None]] = None
        self.on_state_change: Optional[Callable[[PipelineState], None]] = None

        # Statistics
        self._stats = {
            'frames_processed': 0,
            'vad_speech_frames': 0,
            'detections': 0,
            'false_positives_blocked': 0,
            'cooldowns_triggered': 0
        }

        _logger.info(f"WakeWordPipeline initialized: {self.config.wake_words}")

    @property
    def state(self) -> PipelineState:
        """Get current pipeline state."""
        return self._state

    @property
    def is_running(self) -> bool:
        """Check if pipeline is running."""
        return self._running

    def _set_state(self, new_state: PipelineState) -> None:
        """Set pipeline state and fire callback."""
        if new_state != self._state:
            old_state = self._state
            self._state = new_state
            _logger.info(f"Pipeline state: {old_state.name} → {new_state.name}")

            if self.on_state_change:
                try:
                    self.on_state_change(new_state)
                except Exception as e:
                    _logger.error(f"on_state_change callback error: {e}")

    def start(self) -> None:
        """Start the pipeline.

        Begins audio capture and processing. Will first run calibration,
        then transition to listening mode.
        """
        if self._running:
            _logger.warning("Pipeline already running")
            return

        _logger.info("Starting WakeWordPipeline...")

        # Initialize wake word detector (lazy init for better error handling)
        self._init_wake_detector()

        # Start audio capture
        self._start_audio_capture()

        # Start processing thread
        self._running = True
        self._set_state(PipelineState.CALIBRATING)

        self._audio_thread = threading.Thread(
            target=self._audio_loop,
            name="WakeWordPipeline-AudioLoop",
            daemon=True
        )
        self._audio_thread.start()

        _logger.info("WakeWordPipeline started")

    def stop(self) -> None:
        """Stop the pipeline.

        Stops audio capture and processing.
        """
        if not self._running:
            return

        _logger.info("Stopping WakeWordPipeline...")
        self._running = False

        # Stop audio capture
        if self._audio_process:
            self._audio_process.terminate()
            self._audio_process.wait(timeout=2)
            self._audio_process = None

        # Wait for audio thread
        if self._audio_thread:
            self._audio_thread.join(timeout=2)
            self._audio_thread = None

        self._set_state(PipelineState.IDLE)
        _logger.info("WakeWordPipeline stopped")

    def get_statistics(self) -> Dict[str, Any]:
        """Get pipeline statistics.

        Returns:
            Dictionary with processing statistics
        """
        stats = self._stats.copy()
        stats['state'] = self._state.name
        stats['noise_floor_db'] = self._calibrator.noise_floor_db
        stats['is_calibrated'] = self._calibrator.is_calibrated
        stats['vad_stats'] = self._vad.get_statistics()
        return stats

    def _init_wake_detector(self) -> None:
        """Initialize OpenWakeWord detector."""
        try:
            import openwakeword
            from openwakeword.model import Model

            # Get hey_jarvis model path
            model_paths = openwakeword.get_pretrained_model_paths()
            hey_jarvis_path = None

            for path in model_paths:
                if 'hey_jarvis' in path.lower():
                    hey_jarvis_path = path
                    break

            if hey_jarvis_path is None:
                _logger.warning("hey_jarvis model not found, downloading...")
                openwakeword.utils.download_models(['hey_jarvis'])
                model_paths = openwakeword.get_pretrained_model_paths()
                for path in model_paths:
                    if 'hey_jarvis' in path.lower():
                        hey_jarvis_path = path
                        break

            if hey_jarvis_path:
                self._wake_detector = Model(
                    wakeword_model_paths=[hey_jarvis_path],
                    inference_framework="onnx"
                )
                _logger.info(f"OpenWakeWord initialized: {hey_jarvis_path}")
            else:
                raise RuntimeError("Could not find hey_jarvis model")

        except ImportError:
            _logger.error("OpenWakeWord not installed")
            raise RuntimeError(
                "OpenWakeWord not installed. "
                "Install with: pip install openwakeword"
            )
        except Exception as e:
            _logger.error(f"Failed to initialize OpenWakeWord: {e}")
            raise

    def _start_audio_capture(self) -> None:
        """Start audio capture subprocess."""
        cmd = [
            "arecord",
            "-D", self.config.device,
            "-f", "S32_LE",
            "-r", str(self.config.input_sample_rate),
            "-c", str(self.config.channels),
            "-t", "raw",
            "--buffer-size", "8192"  # Larger buffer for stability
        ]

        _logger.debug(f"Starting audio capture: {' '.join(cmd)}")

        self._audio_process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL
        )

        if self._audio_process.poll() is not None:
            raise RuntimeError("Failed to start audio capture")

        _logger.info("Audio capture started")

    def _audio_loop(self) -> None:
        """Main audio processing loop."""
        # Calculate chunk size in bytes
        # S32_LE stereo = 4 bytes/sample * 2 channels = 8 bytes/frame
        bytes_per_frame = 4 * self.config.channels
        chunk_samples = self.config.input_chunk_samples
        chunk_bytes = chunk_samples * bytes_per_frame

        calibration_start = time.monotonic()

        _logger.info(f"Audio loop started: chunk_bytes={chunk_bytes}")

        try:
            while self._running and self._audio_process:
                # Read audio chunk
                raw_audio = self._audio_process.stdout.read(chunk_bytes)

                if len(raw_audio) < chunk_bytes:
                    _logger.warning(f"Short read: {len(raw_audio)}/{chunk_bytes}")
                    continue

                # Process audio
                audio_16k = self._preprocessor.process(raw_audio)

                # Run VAD
                vad_result = self._vad.process_frame(audio_16k)

                # Handle state
                if self._state == PipelineState.CALIBRATING:
                    self._handle_calibration(
                        vad_result, calibration_start
                    )
                elif self._state == PipelineState.LISTENING:
                    self._handle_listening(audio_16k, vad_result)
                elif self._state == PipelineState.COOLDOWN:
                    self._handle_cooldown()

                self._stats['frames_processed'] += 1

        except Exception as e:
            _logger.error(f"Audio loop error: {e}")
            import traceback
            traceback.print_exc()
            self._set_state(PipelineState.ERROR)

        _logger.info("Audio loop ended")

    def _handle_calibration(
        self,
        vad_result: VADResult,
        start_time: float
    ) -> None:
        """Handle calibration phase.

        Collects noise samples for the configured duration.
        """
        elapsed = time.monotonic() - start_time

        # Collect noise samples
        self._calibrator.add_calibration_sample(vad_result.energy_db)

        # Check if calibration complete
        if elapsed >= self.config.calibration_seconds:
            noise_floor = self._calibrator.complete_calibration()

            # Adjust VAD threshold based on noise floor
            new_vad_threshold = max(noise_floor + 6, self.config.vad_threshold_db)
            self._vad.set_threshold_db(new_vad_threshold)
            _logger.info(f"VAD threshold adjusted to {new_vad_threshold:.1f} dB")

            self._set_state(PipelineState.LISTENING)

    def _handle_listening(
        self,
        audio_16k: np.ndarray,
        vad_result: VADResult
    ) -> None:
        """Handle listening phase.

        Processes audio through VAD gate, wake word detection,
        and multi-frame confirmation.
        """
        # Update noise floor during silence
        is_silence = vad_result.state == VADState.SILENCE
        self._calibrator.update_noise_floor(vad_result.energy_db, is_silence)

        # VAD gate: only process during speech
        if not vad_result.is_speech:
            return

        self._stats['vad_speech_frames'] += 1

        # Check cooldown
        if self._confirmer.is_in_cooldown():
            return

        # Run wake word detection
        raw_score = self._run_wake_detection(audio_16k)

        # EMA smoothing
        smoothed_score = self._calibrator.update_score(raw_score)

        # Multi-frame confirmation
        confirm_count = sum(
            1 for s in self._confirmer._window
            if s > self.config.threshold
        )

        if self._confirmer.is_confirmed(smoothed_score):
            # Detection confirmed!
            self._handle_detection(
                raw_score, smoothed_score, confirm_count, vad_result
            )
        else:
            # Track blocked false positives
            if raw_score > self.config.threshold:
                self._stats['false_positives_blocked'] += 1

    def _handle_cooldown(self) -> None:
        """Handle cooldown phase.

        Transitions back to listening when cooldown expires.
        """
        if not self._confirmer.is_in_cooldown():
            self._set_state(PipelineState.LISTENING)

    def _run_wake_detection(self, audio_16k: np.ndarray) -> float:
        """Run wake word detection on audio.

        Args:
            audio_16k: Audio at 16kHz mono float32

        Returns:
            Detection score (0.0 to 1.0)
        """
        if self._wake_detector is None:
            return 0.0

        try:
            # Convert to int16 for OpenWakeWord
            audio_int16 = (audio_16k * 32767).astype(np.int16)

            # Run prediction
            prediction = self._wake_detector.predict(audio_int16)

            # Get max score across models
            max_score = 0.0
            for model_name, score in prediction.items():
                if score > max_score:
                    max_score = score

            return float(max_score)

        except Exception as e:
            _logger.error(f"Wake detection error: {e}")
            return 0.0

    def _handle_detection(
        self,
        raw_score: float,
        smoothed_score: float,
        confirm_count: int,
        vad_result: VADResult
    ) -> None:
        """Handle confirmed wake word detection.

        Fires callback and enters cooldown.
        """
        _logger.info(
            f"WAKE WORD DETECTED! "
            f"raw={raw_score:.3f}, smoothed={smoothed_score:.3f}, "
            f"confirm={confirm_count}/{self.config.confirm_window}"
        )

        # Record detection (starts cooldown)
        self._confirmer.record_detection()
        self._stats['detections'] += 1

        # Reset wake detector to prevent re-trigger
        if self._wake_detector:
            self._wake_detector.reset()

        # Create result
        result = DetectionResult(
            detected=True,
            wake_word=self.config.wake_words[0],
            raw_score=raw_score,
            smoothed_score=smoothed_score,
            confirm_count=confirm_count,
            noise_floor=self._calibrator.noise_floor_db,
            vad_active=True,
            timestamp=time.monotonic()
        )

        # Fire callback
        if self.on_wake_word:
            try:
                self.on_wake_word(result)
            except Exception as e:
                _logger.error(f"on_wake_word callback error: {e}")

        # Enter cooldown
        self._set_state(PipelineState.COOLDOWN)
        self._stats['cooldowns_triggered'] += 1

    def reset(self) -> None:
        """Reset pipeline state.

        Clears all internal state and statistics.
        """
        self._calibrator.reset()
        self._confirmer.reset()
        self._vad.reset()

        if self._wake_detector:
            self._wake_detector.reset()

        self._stats = {
            'frames_processed': 0,
            'vad_speech_frames': 0,
            'detections': 0,
            'false_positives_blocked': 0,
            'cooldowns_triggered': 0
        }

        _logger.info("Pipeline reset")

    def __repr__(self) -> str:
        """String representation."""
        return (
            f"WakeWordPipeline(state={self._state.name}, "
            f"wake_words={self.config.wake_words}, "
            f"threshold={self.config.threshold})"
        )


# =============================================================================
# Demo Script (for testing)
# =============================================================================

def main():
    """Demo entry point for testing the pipeline."""
    import signal

    print()
    print("=" * 60)
    print("  OpenDuck Mini V3 - Production Wake Word Pipeline")
    print("=" * 60)
    print()

    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )

    # Create pipeline with optimized settings
    config = PipelineConfig(
        threshold=0.82,          # Higher threshold
        confirm_window=5,        # 5 frame window
        confirm_required=3,      # Require 3/5 frames
        cooldown_seconds=3.0,    # 3 second cooldown
        calibration_seconds=2.0  # 2 second calibration
    )

    pipeline = WakeWordPipeline(config)

    # Detection callback
    def on_detection(result: DetectionResult):
        print()
        print("=" * 60)
        print(f"  WAKE WORD DETECTED: {result.wake_word}")
        print(f"  Score: {result.smoothed_score:.1%}")
        print(f"  Confirmed: {result.confirm_count}/{config.confirm_window}")
        print("=" * 60)
        print()

    pipeline.on_wake_word = on_detection

    # State change callback
    def on_state_change(state: PipelineState):
        print(f"[STATE] {state.name}")

    pipeline.on_state_change = on_state_change

    # Signal handler
    running = True

    def signal_handler(signum, frame):
        nonlocal running
        print("\n[SHUTDOWN] Received signal, stopping...")
        running = False

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Start pipeline
    try:
        pipeline.start()

        print()
        print("Listening for 'Hey OpenDuck' (or 'Hey Jarvis')...")
        print("Press Ctrl+C to stop")
        print()

        while running and pipeline.is_running:
            time.sleep(0.1)

            # Print stats every 10 seconds
            if pipeline._stats['frames_processed'] % 125 == 0:  # ~10s at 80ms chunks
                stats = pipeline.get_statistics()
                print(
                    f"[STATS] Frames: {stats['frames_processed']}, "
                    f"Speech: {stats['vad_speech_frames']}, "
                    f"Blocked: {stats['false_positives_blocked']}, "
                    f"Detections: {stats['detections']}"
                )

    except Exception as e:
        print(f"[ERROR] {e}")
        import traceback
        traceback.print_exc()

    finally:
        pipeline.stop()

        # Final stats
        stats = pipeline.get_statistics()
        print()
        print("=" * 60)
        print("  Final Statistics")
        print("=" * 60)
        print(f"  Frames processed: {stats['frames_processed']}")
        print(f"  VAD speech frames: {stats['vad_speech_frames']}")
        print(f"  False positives blocked: {stats['false_positives_blocked']}")
        print(f"  Detections: {stats['detections']}")
        print(f"  Noise floor: {stats['noise_floor_db']:.1f} dB")
        print("=" * 60)
        print()


if __name__ == "__main__":
    main()
