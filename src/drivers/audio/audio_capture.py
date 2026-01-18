"""Audio Capture Pipeline for INMP441 I2S Microphone

This module provides a complete audio capture pipeline with thread-safe ring buffer,
continuous background capture, and foundation voice activity detection (VAD).

Hardware:
    - INMP441 MEMS I2S Microphone
    - Sample Rate: 16kHz (configurable, default for speech)
    - Bit Depth: 16-bit
    - Channels: Mono (1 channel)

Latency Target: <50ms end-to-end

Connections (I2S):
    - BCLK: GPIO 18 (Pin 12) - Bit Clock
    - LRCLK/WS: GPIO 19 (Pin 35) - Word Select (Left/Right Clock)
    - DOUT: GPIO 20 (Pin 38) - Data Out from microphone

Thread Safety:
    All public methods are thread-safe using appropriate locking mechanisms.
    The capture runs in a dedicated background thread to avoid blocking.

Example:
    ```python
    from src.drivers.audio.audio_capture import AudioCapturePipeline, AudioCaptureConfig

    # Create pipeline with default config
    config = AudioCaptureConfig()
    pipeline = AudioCapturePipeline(config)

    # Start capture
    pipeline.start()

    # Get 500ms of recent audio
    audio = pipeline.get_audio(duration_ms=500)
    print(f"Got {len(audio.samples)} samples at {audio.sample_rate}Hz")

    # Check current level
    level_db = pipeline.get_level_db()
    print(f"Current level: {level_db:.1f} dB")

    # Stop capture
    pipeline.stop()
    ```
"""

from __future__ import annotations

import math
import threading
import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Callable, List, Optional, Tuple

import numpy as np

# I2S audio library imports (platform-specific)
try:
    import sounddevice as sd
    SOUNDDEVICE_AVAILABLE = True
except ImportError:
    sd = None
    SOUNDDEVICE_AVAILABLE = False


class AudioCaptureState(Enum):
    """State machine for audio capture pipeline."""
    STOPPED = auto()
    STARTING = auto()
    RUNNING = auto()
    STOPPING = auto()
    ERROR = auto()


@dataclass
class AudioCaptureConfig:
    """Configuration for audio capture pipeline.

    Attributes:
        sample_rate: Audio sample rate in Hz (default: 16000 for speech)
        bit_depth: Bits per sample (default: 16)
        channels: Number of audio channels (default: 1 for mono)
        buffer_duration_ms: Ring buffer duration in milliseconds (default: 1000)
        chunk_size_ms: Size of audio chunks for processing in ms (default: 20)
        vad_threshold_db: Voice activity detection threshold in dB (default: -40.0)
        vad_min_speech_ms: Minimum speech duration for VAD trigger (default: 100)
        device_index: Audio device index (None for default)
    """
    sample_rate: int = 16000
    bit_depth: int = 16
    channels: int = 1
    buffer_duration_ms: int = 1000
    chunk_size_ms: int = 20
    vad_threshold_db: float = -40.0
    vad_min_speech_ms: int = 100
    device_index: Optional[int] = None

    def __post_init__(self) -> None:
        """Validate configuration parameters."""
        if self.sample_rate <= 0:
            raise ValueError(f"sample_rate must be positive, got {self.sample_rate}")
        if self.bit_depth not in (8, 16, 24, 32):
            raise ValueError(f"bit_depth must be 8, 16, 24, or 32, got {self.bit_depth}")
        if self.channels < 1:
            raise ValueError(f"channels must be at least 1, got {self.channels}")
        if self.buffer_duration_ms < 100:
            raise ValueError(f"buffer_duration_ms must be at least 100ms, got {self.buffer_duration_ms}")
        if self.chunk_size_ms < 5:
            raise ValueError(f"chunk_size_ms must be at least 5ms, got {self.chunk_size_ms}")
        if self.vad_threshold_db > 0:
            raise ValueError(f"vad_threshold_db must be <= 0, got {self.vad_threshold_db}")
        if self.vad_min_speech_ms < 10:
            raise ValueError(f"vad_min_speech_ms must be at least 10ms, got {self.vad_min_speech_ms}")

    @property
    def samples_per_buffer(self) -> int:
        """Calculate total samples in buffer."""
        return int(self.sample_rate * self.buffer_duration_ms / 1000)

    @property
    def samples_per_chunk(self) -> int:
        """Calculate samples per audio chunk."""
        return int(self.sample_rate * self.chunk_size_ms / 1000)


@dataclass
class AudioSample:
    """Container for audio sample data.

    Attributes:
        samples: NumPy array of audio samples (float32, normalized -1.0 to 1.0)
        sample_rate: Sample rate in Hz
        channels: Number of channels
        timestamp: Timestamp when capture started (time.monotonic())
        duration_ms: Duration of audio in milliseconds
    """
    samples: np.ndarray
    sample_rate: int
    channels: int
    timestamp: float
    duration_ms: float

    def __post_init__(self) -> None:
        """Calculate duration if not provided."""
        if self.duration_ms == 0 and len(self.samples) > 0:
            self.duration_ms = len(self.samples) / self.sample_rate * 1000


class AudioRingBuffer:
    """Thread-safe circular buffer for audio samples.

    Implements a lock-free write, lock-protected read ring buffer optimized
    for continuous audio capture with low latency.

    The buffer stores float32 audio samples normalized to -1.0 to 1.0 range.

    Thread Safety:
        - write(): Thread-safe, uses atomic operations where possible
        - read(): Thread-safe, returns a copy of data
        - get_available(): Thread-safe snapshot (may be stale)
        - clear(): Thread-safe

    Attributes:
        capacity: Maximum number of samples the buffer can hold
        dtype: NumPy data type for samples (float32)
    """

    def __init__(self, capacity: int, channels: int = 1) -> None:
        """Initialize ring buffer.

        Args:
            capacity: Maximum number of samples to store
            channels: Number of audio channels (default: 1)

        Raises:
            ValueError: If capacity <= 0 or channels < 1
        """
        if capacity <= 0:
            raise ValueError(f"capacity must be positive, got {capacity}")
        if channels < 1:
            raise ValueError(f"channels must be at least 1, got {channels}")

        self._capacity = capacity
        self._channels = channels
        self._buffer = np.zeros((capacity, channels), dtype=np.float32)
        self._write_pos = 0
        self._read_pos = 0
        self._available = 0
        self._lock = threading.Lock()
        self._total_written = 0
        self._overflow_count = 0

    @property
    def capacity(self) -> int:
        """Return buffer capacity in samples."""
        return self._capacity

    @property
    def channels(self) -> int:
        """Return number of channels."""
        return self._channels

    @property
    def overflow_count(self) -> int:
        """Return number of overflow events (oldest data dropped)."""
        with self._lock:
            return self._overflow_count

    def write(self, samples: np.ndarray) -> int:
        """Write samples to the buffer, overwriting oldest data if full.

        Thread-safe. If buffer is full, oldest samples are overwritten.

        Args:
            samples: NumPy array of audio samples. Shape should be (N,) for mono
                    or (N, channels) for multi-channel. Values should be normalized
                    to -1.0 to 1.0 range.

        Returns:
            Number of samples actually written (may be less if buffer smaller than input)

        Raises:
            ValueError: If sample shape incompatible with buffer channels
        """
        # Normalize input shape
        if samples.ndim == 1:
            samples = samples.reshape(-1, 1)

        if samples.shape[1] != self._channels:
            raise ValueError(
                f"Sample channels ({samples.shape[1]}) doesn't match "
                f"buffer channels ({self._channels})"
            )

        num_samples = len(samples)
        if num_samples == 0:
            return 0

        # If input larger than capacity, only keep the newest samples
        if num_samples > self._capacity:
            samples = samples[-self._capacity:]
            num_samples = self._capacity

        with self._lock:
            # Calculate how much will fit before wraparound
            space_to_end = self._capacity - self._write_pos

            if num_samples <= space_to_end:
                # Simple case: fits without wraparound
                self._buffer[self._write_pos:self._write_pos + num_samples] = samples
            else:
                # Need to wrap around
                self._buffer[self._write_pos:] = samples[:space_to_end]
                remaining = num_samples - space_to_end
                self._buffer[:remaining] = samples[space_to_end:]

            # Update write position
            old_write_pos = self._write_pos
            self._write_pos = (self._write_pos + num_samples) % self._capacity

            # Check for overflow (write position passed read position)
            old_available = self._available
            self._available = min(self._available + num_samples, self._capacity)

            if old_available + num_samples > self._capacity:
                overflow_samples = (old_available + num_samples) - self._capacity
                self._overflow_count += 1
                # Move read position forward to maintain buffer integrity
                self._read_pos = self._write_pos

            self._total_written += num_samples

        return num_samples

    def read(self, num_samples: int) -> np.ndarray:
        """Read samples from the buffer.

        Thread-safe. Returns a copy of the data to prevent race conditions.
        Does not remove data from buffer (peek behavior).

        Args:
            num_samples: Number of samples to read. If more than available,
                        returns all available samples.

        Returns:
            NumPy array of shape (N, channels) with the requested samples.
            May be shorter than requested if insufficient data available.
        """
        with self._lock:
            actual_samples = min(num_samples, self._available)

            if actual_samples == 0:
                return np.zeros((0, self._channels), dtype=np.float32)

            # Calculate read position for the most recent samples
            # We want the NEWEST samples, so read from (write_pos - actual_samples)
            start_pos = (self._write_pos - actual_samples) % self._capacity

            if start_pos + actual_samples <= self._capacity:
                # Simple case: no wraparound
                result = self._buffer[start_pos:start_pos + actual_samples].copy()
            else:
                # Wraparound case
                first_part = self._buffer[start_pos:]
                second_part_len = actual_samples - len(first_part)
                second_part = self._buffer[:second_part_len]
                result = np.vstack([first_part, second_part])

            return result

    def read_and_consume(self, num_samples: int) -> np.ndarray:
        """Read and remove samples from the buffer.

        Thread-safe. Returns a copy of the data and removes it from buffer.

        Args:
            num_samples: Number of samples to read and remove.

        Returns:
            NumPy array of shape (N, channels) with the consumed samples.
        """
        with self._lock:
            actual_samples = min(num_samples, self._available)

            if actual_samples == 0:
                return np.zeros((0, self._channels), dtype=np.float32)

            if self._read_pos + actual_samples <= self._capacity:
                result = self._buffer[self._read_pos:self._read_pos + actual_samples].copy()
            else:
                first_part = self._buffer[self._read_pos:]
                second_part_len = actual_samples - len(first_part)
                second_part = self._buffer[:second_part_len]
                result = np.vstack([first_part, second_part])

            self._read_pos = (self._read_pos + actual_samples) % self._capacity
            self._available -= actual_samples

            return result

    def get_available(self) -> int:
        """Get number of samples available for reading.

        Thread-safe but result may be stale immediately after return.

        Returns:
            Number of samples currently available in buffer
        """
        with self._lock:
            return self._available

    def clear(self) -> None:
        """Clear the buffer, discarding all samples.

        Thread-safe. Resets read and write positions.
        """
        with self._lock:
            self._write_pos = 0
            self._read_pos = 0
            self._available = 0
            # Note: We don't zero the buffer for performance, data will be overwritten


class VoiceActivityDetector:
    """Simple energy-based Voice Activity Detection (VAD).

    Foundation VAD using signal energy analysis. Does NOT use ML libraries.
    Suitable for basic speech detection before passing to more sophisticated
    speech recognition systems.

    Algorithm:
        1. Calculate RMS energy of audio frame
        2. Convert to dB scale
        3. Compare against threshold
        4. Apply minimum duration filter to avoid false positives

    Thread Safety:
        All public methods are thread-safe.

    Attributes:
        threshold_db: Energy threshold in dB for speech detection
        min_speech_ms: Minimum continuous speech duration for positive detection
    """

    # Constants for dB calculation
    EPSILON = 1e-10  # Prevent log(0)
    REFERENCE_AMPLITUDE = 1.0  # Reference for dB calculation (normalized audio)

    def __init__(
        self,
        threshold_db: float = -40.0,
        min_speech_ms: int = 100,
        sample_rate: int = 16000
    ) -> None:
        """Initialize voice activity detector.

        Args:
            threshold_db: Energy threshold in dB (default: -40.0)
            min_speech_ms: Minimum speech duration in ms (default: 100)
            sample_rate: Sample rate for duration calculations (default: 16000)

        Raises:
            ValueError: If parameters are out of valid range
        """
        if threshold_db > 0:
            raise ValueError(f"threshold_db must be <= 0, got {threshold_db}")
        if min_speech_ms < 10:
            raise ValueError(f"min_speech_ms must be >= 10, got {min_speech_ms}")
        if sample_rate <= 0:
            raise ValueError(f"sample_rate must be positive, got {sample_rate}")

        self._threshold_db = threshold_db
        self._min_speech_ms = min_speech_ms
        self._sample_rate = sample_rate
        self._min_speech_samples = int(sample_rate * min_speech_ms / 1000)

        # State tracking for continuous detection
        self._lock = threading.Lock()
        self._speech_start_time: Optional[float] = None
        self._last_speech_probability = 0.0
        self._is_speaking = False

    @property
    def threshold_db(self) -> float:
        """Current threshold in dB."""
        return self._threshold_db

    @threshold_db.setter
    def threshold_db(self, value: float) -> None:
        """Set threshold in dB."""
        if value > 0:
            raise ValueError(f"threshold_db must be <= 0, got {value}")
        with self._lock:
            self._threshold_db = value

    def _calculate_rms(self, samples: np.ndarray) -> float:
        """Calculate RMS (Root Mean Square) energy of samples.

        Args:
            samples: Audio samples array

        Returns:
            RMS value (0.0 to 1.0 for normalized audio)
        """
        if len(samples) == 0:
            return 0.0

        # Flatten if multi-channel
        if samples.ndim > 1:
            samples = samples.flatten()

        # Calculate RMS
        rms = np.sqrt(np.mean(samples ** 2))
        return float(rms)

    def _rms_to_db(self, rms: float) -> float:
        """Convert RMS amplitude to decibels.

        Args:
            rms: RMS amplitude value

        Returns:
            Level in dB (negative values, 0 dB = full scale)
        """
        # Prevent log(0)
        rms = max(rms, self.EPSILON)
        return 20.0 * math.log10(rms / self.REFERENCE_AMPLITUDE)

    def get_energy_db(self, samples: np.ndarray) -> float:
        """Calculate energy level of audio samples in dB.

        Args:
            samples: Audio samples (normalized -1.0 to 1.0)

        Returns:
            Energy level in dB (typically -60 to 0 dB)
        """
        rms = self._calculate_rms(samples)
        return self._rms_to_db(rms)

    def is_speech(self, samples: np.ndarray) -> bool:
        """Detect if samples contain speech.

        Simple energy-based detection. Returns True if:
        1. Energy exceeds threshold AND
        2. Speech has been continuous for min_speech_ms

        Thread-safe.

        Args:
            samples: Audio samples to analyze

        Returns:
            True if speech detected, False otherwise
        """
        energy_db = self.get_energy_db(samples)
        current_time = time.monotonic()

        with self._lock:
            if energy_db >= self._threshold_db:
                if self._speech_start_time is None:
                    self._speech_start_time = current_time

                elapsed_ms = (current_time - self._speech_start_time) * 1000
                self._is_speaking = elapsed_ms >= self._min_speech_ms
            else:
                self._speech_start_time = None
                self._is_speaking = False

            return self._is_speaking

    def get_speech_probability(self) -> float:
        """Get probability that current audio contains speech.

        Returns a value between 0.0 and 1.0 based on energy level relative
        to threshold. This is a simple linear mapping, not a true probability.

        Thread-safe.

        Returns:
            Speech probability (0.0 to 1.0)
        """
        with self._lock:
            return self._last_speech_probability

    def update_probability(self, samples: np.ndarray) -> float:
        """Update and return speech probability.

        Maps energy to a 0.0-1.0 probability score:
        - Below (threshold - 20dB): 0.0
        - At threshold: 0.5
        - Above (threshold + 10dB): 1.0

        Thread-safe.

        Args:
            samples: Audio samples to analyze

        Returns:
            Updated speech probability (0.0 to 1.0)
        """
        energy_db = self.get_energy_db(samples)

        # Linear mapping with some headroom
        lower_bound = self._threshold_db - 20.0
        upper_bound = self._threshold_db + 10.0

        probability = (energy_db - lower_bound) / (upper_bound - lower_bound)
        probability = max(0.0, min(1.0, probability))

        with self._lock:
            self._last_speech_probability = probability

        return probability

    def reset(self) -> None:
        """Reset VAD state.

        Thread-safe. Call when starting new utterance detection.
        """
        with self._lock:
            self._speech_start_time = None
            self._last_speech_probability = 0.0
            self._is_speaking = False


class AudioCapturePipeline:
    """Continuous audio capture pipeline with VAD support.

    Provides background audio capture from INMP441 microphone with:
    - Thread-safe ring buffer for sample storage
    - Continuous background capture thread
    - Voice activity detection
    - Callback support for real-time processing

    Latency: Designed for <50ms end-to-end latency

    Thread Safety:
        All public methods are thread-safe. Capture runs in dedicated thread.

    Example:
        ```python
        config = AudioCaptureConfig(
            sample_rate=16000,
            buffer_duration_ms=2000,
            vad_threshold_db=-35.0
        )

        pipeline = AudioCapturePipeline(config)
        pipeline.add_callback(my_audio_processor)
        pipeline.start()

        # ... application runs ...

        pipeline.stop()
        ```
    """

    def __init__(self, config: Optional[AudioCaptureConfig] = None) -> None:
        """Initialize audio capture pipeline.

        Args:
            config: Audio capture configuration (uses defaults if None)
        """
        self._config = config or AudioCaptureConfig()

        # Initialize ring buffer
        buffer_samples = self._config.samples_per_buffer
        self._ring_buffer = AudioRingBuffer(buffer_samples, self._config.channels)

        # Initialize VAD
        self._vad = VoiceActivityDetector(
            threshold_db=self._config.vad_threshold_db,
            min_speech_ms=self._config.vad_min_speech_ms,
            sample_rate=self._config.sample_rate
        )

        # Thread management
        self._state = AudioCaptureState.STOPPED
        self._state_lock = threading.Lock()
        self._capture_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

        # Callbacks for new audio chunks
        self._callbacks: List[Callable[[np.ndarray], None]] = []
        self._callbacks_lock = threading.Lock()

        # Current audio level (thread-safe)
        self._current_level_db = -100.0
        self._level_lock = threading.Lock()

        # Audio stream (sounddevice)
        self._stream: Optional['sd.InputStream'] = None

    @property
    def state(self) -> AudioCaptureState:
        """Current pipeline state."""
        with self._state_lock:
            return self._state

    @property
    def config(self) -> AudioCaptureConfig:
        """Current configuration (read-only)."""
        return self._config

    @property
    def vad(self) -> VoiceActivityDetector:
        """Voice activity detector instance."""
        return self._vad

    def start(self) -> None:
        """Start audio capture.

        Begins continuous capture in background thread.

        Raises:
            RuntimeError: If already running or sounddevice unavailable
        """
        with self._state_lock:
            if self._state == AudioCaptureState.RUNNING:
                return  # Already running, ignore

            if self._state == AudioCaptureState.STARTING:
                raise RuntimeError("Pipeline is already starting")

            if not SOUNDDEVICE_AVAILABLE:
                raise RuntimeError(
                    "sounddevice library not available. "
                    "Install with: pip install sounddevice"
                )

            self._state = AudioCaptureState.STARTING

        try:
            self._stop_event.clear()
            self._capture_thread = threading.Thread(
                target=self._capture_loop,
                name="AudioCapture",
                daemon=True
            )
            self._capture_thread.start()

            with self._state_lock:
                self._state = AudioCaptureState.RUNNING

        except Exception as e:
            with self._state_lock:
                self._state = AudioCaptureState.ERROR
            raise RuntimeError(f"Failed to start audio capture: {e}")

    def stop(self) -> None:
        """Stop audio capture.

        Signals capture thread to stop and waits for completion.
        """
        with self._state_lock:
            if self._state == AudioCaptureState.STOPPED:
                return  # Already stopped

            if self._state == AudioCaptureState.STOPPING:
                return  # Already stopping

            self._state = AudioCaptureState.STOPPING

        self._stop_event.set()

        if self._capture_thread is not None and self._capture_thread.is_alive():
            self._capture_thread.join(timeout=2.0)
            if self._capture_thread.is_alive():
                # FIX H-HIGH-001: Log error and set ERROR state when thread fails to stop
                _logger.error("Capture thread failed to stop within 2.0s timeout")
                with self._state_lock:
                    self._state = AudioCaptureState.ERROR
                return False

        with self._state_lock:
            self._state = AudioCaptureState.STOPPED

    def _capture_loop(self) -> None:
        """Background capture loop.

        Runs in dedicated thread, captures audio chunks and writes to ring buffer.
        """
        chunk_samples = self._config.samples_per_chunk

        def audio_callback(indata: np.ndarray, frames: int, time_info, status) -> None:
            """Sounddevice callback for incoming audio."""
            if status:
                # Log status (overflow, underflow, etc.) - non-blocking
                pass

            # Convert to float32 if needed and normalize
            audio_data = indata.astype(np.float32)

            # Write to ring buffer
            self._ring_buffer.write(audio_data)

            # Update current level
            rms = np.sqrt(np.mean(audio_data ** 2))
            level_db = 20.0 * math.log10(max(rms, 1e-10))
            with self._level_lock:
                self._current_level_db = level_db

            # Update VAD probability
            self._vad.update_probability(audio_data)

            # Call registered callbacks
            with self._callbacks_lock:
                for callback in self._callbacks:
                    try:
                        callback(audio_data)
                    except Exception as e:
                        # FIX H-MED-001: Log callback errors instead of silent swallow
                        _logger.warning(f"Audio callback error: {e}")

        try:
            # Open audio stream
            self._stream = sd.InputStream(
                samplerate=self._config.sample_rate,
                channels=self._config.channels,
                dtype=np.float32,
                blocksize=chunk_samples,
                device=self._config.device_index,
                callback=audio_callback
            )

            with self._stream:
                # Wait for stop signal
                while not self._stop_event.is_set():
                    self._stop_event.wait(timeout=0.1)

        except Exception as e:
            with self._state_lock:
                self._state = AudioCaptureState.ERROR
        finally:
            self._stream = None

    def get_audio(self, duration_ms: int) -> AudioSample:
        """Get recent audio samples.

        Thread-safe. Returns the most recent audio from the ring buffer.

        Args:
            duration_ms: Duration of audio to retrieve in milliseconds

        Returns:
            AudioSample containing the requested audio data

        Raises:
            ValueError: If duration_ms is invalid
        """
        if duration_ms <= 0:
            raise ValueError(f"duration_ms must be positive, got {duration_ms}")

        num_samples = int(self._config.sample_rate * duration_ms / 1000)
        samples = self._ring_buffer.read(num_samples)

        # Flatten to 1D if mono
        if self._config.channels == 1 and samples.ndim > 1:
            samples = samples.flatten()

        return AudioSample(
            samples=samples,
            sample_rate=self._config.sample_rate,
            channels=self._config.channels,
            timestamp=time.monotonic(),
            duration_ms=len(samples) / self._config.sample_rate * 1000
        )

    def get_level_db(self) -> float:
        """Get current audio level in decibels.

        Thread-safe. Returns the level from the most recent audio chunk.

        Returns:
            Audio level in dB (typically -60 to 0 dB, -100 if silent)
        """
        with self._level_lock:
            return self._current_level_db

    def is_speech_detected(self) -> bool:
        """Check if speech is currently detected.

        Thread-safe. Uses VAD to determine speech presence.

        Returns:
            True if speech is detected, False otherwise
        """
        # Get recent audio (one chunk worth)
        audio = self.get_audio(self._config.chunk_size_ms)
        return self._vad.is_speech(audio.samples)

    def add_callback(self, callback: Callable[[np.ndarray], None]) -> None:
        """Add callback for new audio chunks.

        Callback is called for each new audio chunk captured.
        Callbacks should be fast to avoid blocking capture.

        Thread-safe.

        Args:
            callback: Function taking np.ndarray of audio samples
        """
        with self._callbacks_lock:
            if callback not in self._callbacks:
                self._callbacks.append(callback)

    def remove_callback(self, callback: Callable[[np.ndarray], None]) -> None:
        """Remove a registered callback.

        Thread-safe.

        Args:
            callback: Callback function to remove
        """
        with self._callbacks_lock:
            if callback in self._callbacks:
                self._callbacks.remove(callback)

    def clear_buffer(self) -> None:
        """Clear the audio ring buffer.

        Thread-safe. Discards all captured audio.
        """
        self._ring_buffer.clear()


# Module-level convenience functions

def create_capture_pipeline(
    sample_rate: int = 16000,
    buffer_duration_ms: int = 1000,
    vad_threshold_db: float = -40.0
) -> AudioCapturePipeline:
    """Create audio capture pipeline with common settings.

    Convenience function for quick setup.

    Args:
        sample_rate: Audio sample rate (default: 16000 for speech)
        buffer_duration_ms: Buffer duration (default: 1000ms)
        vad_threshold_db: VAD threshold (default: -40 dB)

    Returns:
        Configured AudioCapturePipeline instance
    """
    config = AudioCaptureConfig(
        sample_rate=sample_rate,
        buffer_duration_ms=buffer_duration_ms,
        vad_threshold_db=vad_threshold_db
    )
    return AudioCapturePipeline(config)
