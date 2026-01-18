"""INMP441 I2S MEMS Microphone Driver for OpenDuck Mini V3

This module provides a hardware abstraction layer for the INMP441 I2S MEMS
microphone, enabling high-quality audio capture for voice recognition,
sound detection, and audio processing applications.

The INMP441 is a high-performance, low-power digital microphone with I2S
interface. It features a 24-bit output (truncated to 16-bit for this driver),
61 dB signal-to-noise ratio, and -26 dBFS sensitivity.

Hardware:
    - InvenSense INMP441 MEMS Microphone
    - I2S digital interface (not I2C)
    - 3.3V compatible
    - L/R select pin for channel configuration

Connections (per COMPLETE_PIN_DIAGRAM_V3.md):
    - BCK (Bit Clock)  -> Raspberry Pi GPIO 18 (Pin 12) - I2S BCLK
    - WS (Word Select) -> Raspberry Pi GPIO 19 (Pin 35) - I2S LRCLK
    - SD (Data Out)    -> Raspberry Pi GPIO 20 (Pin 38) - I2S DIN
    - L/R              -> GND (Left channel) or VCC (Right channel)
    - VCC              -> 3.3V (Pi Pin 1 or 17)
    - GND              -> GND (Pi Pin 6, 9, 14, etc.)

Key Features:
    - 16000 Hz sample rate (configured for voice recognition)
    - 16-bit sample depth
    - Mono capture (single microphone)
    - Thread-safe operation with proper locking
    - dB level calculation for volume detection
    - Configurable gain and buffer sizes

Thread Safety:
    All operations use internal locking to prevent race conditions during
    audio capture and buffer access. Safe for multi-threaded applications.

Example:
    ```python
    from src.drivers.audio.inmp441 import INMP441Driver, INMP441Config

    # Initialize with default configuration
    mic = INMP441Driver()

    # Or with custom configuration
    config = INMP441Config(sample_rate=16000, gain=1.5)
    mic = INMP441Driver(config=config)

    # Start capturing audio
    mic.start_capture()

    # Read samples
    samples = mic.read_samples(1024)
    print(f"Captured {len(samples)} samples")

    # Get current audio level
    level_db = mic.get_level_db()
    print(f"Audio level: {level_db:.1f} dB")

    # Stop capture
    mic.stop_capture()
    ```

Note:
    GPIO 18 (I2S BCLK) has a documented conflict with LED Ring 1.
    See GPIO_CONFLICT_RESOLUTION.md for mitigation strategies.
"""

import math
import time
import threading
import queue
from dataclasses import dataclass, field
from typing import Optional, Callable, Any
from enum import Enum

try:
    import numpy as np
except ImportError:
    np = None  # type: ignore

# I2S library imports - platform specific
try:
    # Attempt to import sounddevice for cross-platform I2S/audio support
    import sounddevice as sd
    SOUNDDEVICE_AVAILABLE = True
except ImportError:
    sd = None  # type: ignore
    SOUNDDEVICE_AVAILABLE = False

try:
    # Alternative: direct I2S via pyaudio with ALSA backend
    # Note: Using pyaudio through sounddevice abstraction is preferred
    pass
except ImportError:
    pass


class CaptureState(Enum):
    """Audio capture state enumeration."""
    STOPPED = "stopped"
    STARTING = "starting"
    CAPTURING = "capturing"
    STOPPING = "stopping"
    ERROR = "error"


@dataclass
class INMP441Config:
    """Configuration parameters for INMP441 microphone.

    Attributes:
        sample_rate: Audio sample rate in Hz. Default 16000 for voice.
        bit_depth: Bits per sample. Fixed at 16 for this driver.
        channels: Number of audio channels. Fixed at 1 (mono).
        gain: Software gain multiplier (1.0 = unity gain).
        buffer_frames: Number of frames per buffer chunk.
        device_index: Audio device index (None for default).
        timeout_seconds: Maximum wait time for operations.
        level_smoothing: Exponential smoothing factor for dB level (0-1).

    Example:
        ```python
        config = INMP441Config(
            sample_rate=16000,
            gain=1.5,
            buffer_frames=512
        )
        ```
    """
    sample_rate: int = 16000
    bit_depth: int = 16
    channels: int = 1
    gain: float = 1.0
    buffer_frames: int = 512
    device_index: Optional[int] = None
    timeout_seconds: float = 5.0
    level_smoothing: float = 0.3

    def __post_init__(self):
        """Validate configuration parameters."""
        if self.sample_rate not in (8000, 16000, 22050, 44100, 48000):
            raise ValueError(
                f"Invalid sample_rate {self.sample_rate}. "
                f"Supported: 8000, 16000, 22050, 44100, 48000"
            )
        if self.bit_depth != 16:
            raise ValueError(
                f"Invalid bit_depth {self.bit_depth}. Only 16-bit supported."
            )
        if self.channels != 1:
            raise ValueError(
                f"Invalid channels {self.channels}. Only mono (1) supported."
            )
        if not 0.1 <= self.gain <= 10.0:
            raise ValueError(
                f"Invalid gain {self.gain}. Must be between 0.1 and 10.0"
            )
        if self.buffer_frames < 64:
            raise ValueError(
                f"Invalid buffer_frames {self.buffer_frames}. Minimum is 64."
            )
        if not 0.0 <= self.level_smoothing <= 1.0:
            raise ValueError(
                f"Invalid level_smoothing {self.level_smoothing}. "
                f"Must be between 0.0 and 1.0"
            )


@dataclass
class AudioSample:
    """Container for captured audio samples.

    Attributes:
        samples: NumPy array of int16 audio samples.
        sample_rate: Sample rate in Hz when captured.
        timestamp: Unix timestamp when capture started.
        level_db: Audio level in dB at time of capture.

    Example:
        ```python
        sample = mic.read_audio_sample(1024)
        print(f"Captured at {sample.timestamp}")
        print(f"Level: {sample.level_db:.1f} dB")
        print(f"Duration: {len(sample.samples) / sample.sample_rate:.3f}s")
        ```
    """
    samples: Any  # np.ndarray[np.int16] when numpy available
    sample_rate: int
    timestamp: float
    level_db: float

    def duration_seconds(self) -> float:
        """Calculate duration of audio sample in seconds.

        Returns:
            float: Duration in seconds.
        """
        if self.samples is None or len(self.samples) == 0:
            return 0.0
        return len(self.samples) / self.sample_rate


class INMP441Driver:
    """Driver for INMP441 I2S MEMS Microphone.

    Provides thread-safe audio capture from the INMP441 microphone via I2S
    interface. Supports continuous streaming with configurable buffer sizes
    and real-time audio level monitoring.

    Thread Safety:
        All public methods are thread-safe. Internal state is protected by
        locks, and audio capture runs in a dedicated thread.

    Attributes:
        config: INMP441Config instance with current settings.
        is_capturing: Boolean indicating active capture state.

    Example:
        ```python
        # Basic usage
        mic = INMP441Driver()
        mic.start_capture()

        try:
            while True:
                samples = mic.read_samples(512)
                level = mic.get_level_db()
                if level > -30:  # Sound detected
                    print(f"Sound detected: {level:.1f} dB")
        finally:
            mic.stop_capture()
        ```
    """

    # Reference level for dB calculations (16-bit max amplitude)
    REFERENCE_AMPLITUDE = 32768.0

    # Minimum dB floor to avoid log(0) issues
    DB_FLOOR = -96.0

    # Maximum samples to buffer before dropping old data
    MAX_BUFFER_SAMPLES = 48000  # 3 seconds at 16kHz

    def __init__(
        self,
        config: Optional[INMP441Config] = None,
        mock_mode: bool = False
    ):
        """Initialize INMP441 microphone driver.

        Args:
            config: Optional configuration. Uses defaults if not provided.
            mock_mode: If True, use mock audio for development/testing.

        Raises:
            ImportError: If required libraries not installed.
            RuntimeError: If audio device initialization fails.

        Example:
            ```python
            # Default configuration
            mic = INMP441Driver()

            # Custom configuration
            config = INMP441Config(sample_rate=16000, gain=2.0)
            mic = INMP441Driver(config=config)

            # Mock mode for testing without hardware
            mic = INMP441Driver(mock_mode=True)
            ```
        """
        self.config = config or INMP441Config()
        self._mock_mode = mock_mode

        # Thread synchronization
        self._lock = threading.RLock()
        self._capture_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

        # State tracking
        self._state = CaptureState.STOPPED
        self._current_level_db = self.DB_FLOOR
        self._error_message: Optional[str] = None

        # Audio buffer (thread-safe queue)
        self._sample_queue: queue.Queue = queue.Queue(maxsize=100)

        # Stream reference
        self._stream: Optional[Any] = None

        # Validate dependencies
        if not mock_mode:
            self._validate_dependencies()

        # Initialize device
        self._initialize_device()

    def _validate_dependencies(self):
        """Validate that required libraries are available.

        Raises:
            ImportError: If numpy or sounddevice not available.
        """
        if np is None:
            raise ImportError(
                "NumPy is required for INMP441 driver. "
                "Install with: pip install numpy"
            )

        if not SOUNDDEVICE_AVAILABLE and not self._mock_mode:
            raise ImportError(
                "sounddevice is required for audio capture. "
                "Install with: pip install sounddevice"
            )

    def _initialize_device(self):
        """Initialize audio capture device.

        Configures the I2S input device for the specified sample rate
        and buffer configuration.

        Raises:
            RuntimeError: If device initialization fails.
        """
        if self._mock_mode:
            return

        try:
            # Query available devices
            if sd is not None:
                devices = sd.query_devices()
                # Log available input devices for debugging
                input_devices = [
                    d for d in devices
                    if d.get('max_input_channels', 0) > 0
                ]

                if not input_devices:
                    raise RuntimeError(
                        "No audio input devices found. "
                        "Ensure I2S microphone is properly configured."
                    )

        except Exception as e:
            raise RuntimeError(f"Failed to initialize audio device: {e}")

    @property
    def is_capturing(self) -> bool:
        """Check if audio capture is currently active.

        Returns:
            bool: True if capturing, False otherwise.
        """
        with self._lock:
            return self._state == CaptureState.CAPTURING

    @property
    def state(self) -> CaptureState:
        """Get current capture state.

        Returns:
            CaptureState: Current state of the capture system.
        """
        with self._lock:
            return self._state

    @property
    def error_message(self) -> Optional[str]:
        """Get last error message if state is ERROR.

        Returns:
            Optional[str]: Error message or None.
        """
        with self._lock:
            return self._error_message

    def start_capture(self) -> bool:
        """Begin audio capture from microphone.

        Starts the capture thread and begins buffering audio samples.
        Non-blocking operation - use read_samples() to retrieve data.

        Returns:
            bool: True if capture started successfully.

        Raises:
            RuntimeError: If already capturing or device error.

        Example:
            ```python
            mic = INMP441Driver()
            if mic.start_capture():
                print("Capture started successfully")
            ```
        """
        with self._lock:
            if self._state == CaptureState.CAPTURING:
                raise RuntimeError("Already capturing audio")

            if self._state == CaptureState.STARTING:
                raise RuntimeError("Capture is starting, please wait")

            self._state = CaptureState.STARTING
            self._stop_event.clear()
            self._error_message = None

            # Clear any old samples from queue
            while not self._sample_queue.empty():
                try:
                    self._sample_queue.get_nowait()
                except queue.Empty:
                    break

        # Start capture thread
        self._capture_thread = threading.Thread(
            target=self._capture_loop,
            name="INMP441-Capture",
            daemon=True
        )
        self._capture_thread.start()

        # Wait for capture to actually start (with timeout)
        start_time = time.time()
        while time.time() - start_time < self.config.timeout_seconds:
            with self._lock:
                if self._state == CaptureState.CAPTURING:
                    return True
                if self._state == CaptureState.ERROR:
                    raise RuntimeError(
                        f"Capture failed to start: {self._error_message}"
                    )
            time.sleep(0.01)

        with self._lock:
            self._state = CaptureState.ERROR
            self._error_message = "Capture start timeout"

        raise RuntimeError("Capture start timeout")

    def stop_capture(self) -> bool:
        """Stop audio capture.

        Signals the capture thread to stop and waits for clean shutdown.

        Returns:
            bool: True if capture stopped successfully.

        Example:
            ```python
            mic.stop_capture()
            print("Capture stopped")
            ```
        """
        with self._lock:
            if self._state == CaptureState.STOPPED:
                return True

            if self._state not in (CaptureState.CAPTURING, CaptureState.STARTING):
                return False

            self._state = CaptureState.STOPPING

        # Signal thread to stop
        self._stop_event.set()

        # Wait for thread to finish (with timeout)
        if self._capture_thread is not None:
            self._capture_thread.join(timeout=self.config.timeout_seconds)

            if self._capture_thread.is_alive():
                with self._lock:
                    self._state = CaptureState.ERROR
                    self._error_message = "Capture thread failed to stop"
                return False

        with self._lock:
            self._state = CaptureState.STOPPED
            self._capture_thread = None

        return True

    def _capture_loop(self):
        """Main capture loop running in dedicated thread.

        Reads audio samples from I2S interface and buffers them for
        retrieval via read_samples().
        """
        if self._mock_mode:
            self._mock_capture_loop()
            return

        try:
            # Configure input stream
            def audio_callback(indata, frames, callback_time, status):
                """Callback for incoming audio data."""
                if status:
                    # Log status warnings (e.g., buffer overruns)
                    pass

                if self._stop_event.is_set():
                    return

                # FIX H-MED-003: Cache gain value for thread-safe access
                with self._lock:
                    gain = self.config.gain
                    smoothing = self.config.level_smoothing

                # Apply gain
                samples = indata[:, 0] * gain

                # Convert to int16
                samples_int16 = (samples * 32767).astype(np.int16)

                # Calculate level
                rms = np.sqrt(np.mean(samples.astype(np.float64) ** 2))
                if rms > 0:
                    level_db = 20 * math.log10(rms / 1.0)  # Normalized
                else:
                    level_db = self.DB_FLOOR

                # Update smoothed level (using cached smoothing from H-MED-003 fix)
                with self._lock:
                    self._current_level_db = (
                        smoothing * level_db +
                        (1 - smoothing) * self._current_level_db
                    )

                # Queue samples (drop oldest if full)
                try:
                    self._sample_queue.put_nowait(samples_int16)
                except queue.Full:
                    try:
                        self._sample_queue.get_nowait()
                        self._sample_queue.put_nowait(samples_int16)
                    except queue.Empty:
                        pass

            # Open input stream
            self._stream = sd.InputStream(
                samplerate=self.config.sample_rate,
                blocksize=self.config.buffer_frames,
                device=self.config.device_index,
                channels=self.config.channels,
                dtype='float32',
                callback=audio_callback
            )

            with self._stream:
                with self._lock:
                    self._state = CaptureState.CAPTURING

                # Wait for stop signal
                while not self._stop_event.wait(timeout=0.1):
                    pass

        except Exception as e:
            with self._lock:
                self._state = CaptureState.ERROR
                self._error_message = str(e)

    def _mock_capture_loop(self):
        """Mock capture loop for testing without hardware."""
        with self._lock:
            self._state = CaptureState.CAPTURING

        while not self._stop_event.is_set():
            # Generate mock audio (white noise at low level)
            if np is not None:
                mock_samples = np.random.randint(
                    -1000, 1000,
                    size=self.config.buffer_frames,
                    dtype=np.int16
                )
            else:
                # Fallback without numpy
                import random
                mock_samples = [
                    random.randint(-1000, 1000)
                    for _ in range(self.config.buffer_frames)
                ]

            # Calculate mock level
            if np is not None:
                rms = np.sqrt(np.mean(mock_samples.astype(np.float64) ** 2))
            else:
                rms = math.sqrt(sum(s ** 2 for s in mock_samples) / len(mock_samples))

            if rms > 0:
                level_db = 20 * math.log10(rms / self.REFERENCE_AMPLITUDE)
            else:
                level_db = self.DB_FLOOR

            with self._lock:
                alpha = self.config.level_smoothing
                self._current_level_db = (
                    alpha * level_db +
                    (1 - alpha) * self._current_level_db
                )

            # Queue mock samples
            try:
                if np is not None:
                    self._sample_queue.put_nowait(mock_samples)
                else:
                    self._sample_queue.put_nowait(mock_samples)
            except queue.Full:
                try:
                    self._sample_queue.get_nowait()
                    self._sample_queue.put_nowait(mock_samples)
                except queue.Empty:
                    pass

            # Simulate real-time capture rate
            time.sleep(self.config.buffer_frames / self.config.sample_rate)

    def read_samples(self, num_samples: int) -> Any:
        """Read audio samples from the capture buffer.

        Retrieves the requested number of samples from the internal buffer.
        If not enough samples are available, returns what is available or
        blocks briefly waiting for more data.

        Args:
            num_samples: Number of samples to read.

        Returns:
            np.ndarray: Array of int16 audio samples. May be shorter than
                        requested if not enough data available.

        Raises:
            RuntimeError: If not currently capturing.

        Example:
            ```python
            # Read 1024 samples (64ms at 16kHz)
            samples = mic.read_samples(1024)
            print(f"Got {len(samples)} samples")

            # Process samples
            peak = np.max(np.abs(samples))
            print(f"Peak amplitude: {peak}")
            ```
        """
        if np is None and not self._mock_mode:
            raise RuntimeError("NumPy required for sample reading")

        with self._lock:
            if self._state != CaptureState.CAPTURING:
                raise RuntimeError(
                    f"Cannot read samples in state {self._state.value}"
                )

        # Collect samples from queue
        collected = []
        collected_count = 0

        timeout_deadline = time.time() + self.config.timeout_seconds

        while collected_count < num_samples:
            remaining_time = timeout_deadline - time.time()
            if remaining_time <= 0:
                break

            try:
                chunk = self._sample_queue.get(timeout=min(0.1, remaining_time))
                if np is not None:
                    collected.append(chunk)
                    collected_count += len(chunk)
                else:
                    collected.extend(chunk)
                    collected_count += len(chunk)
            except queue.Empty:
                # No more data available within timeout
                if collected_count > 0:
                    break

        if not collected:
            if np is not None:
                return np.array([], dtype=np.int16)
            else:
                return []

        # Concatenate and trim to requested size
        if np is not None:
            result = np.concatenate(collected)
            return result[:num_samples]
        else:
            return collected[:num_samples]

    def read_audio_sample(self, num_samples: int) -> AudioSample:
        """Read audio samples as an AudioSample object.

        Convenience method that wraps read_samples() and returns a
        structured AudioSample dataclass with metadata.

        Args:
            num_samples: Number of samples to read.

        Returns:
            AudioSample: Structured sample data with metadata.

        Example:
            ```python
            sample = mic.read_audio_sample(1024)
            print(f"Duration: {sample.duration_seconds():.3f}s")
            print(f"Level: {sample.level_db:.1f} dB")
            ```
        """
        timestamp = time.time()
        samples = self.read_samples(num_samples)
        level_db = self.get_level_db()

        return AudioSample(
            samples=samples,
            sample_rate=self.config.sample_rate,
            timestamp=timestamp,
            level_db=level_db
        )

    def get_level_db(self) -> float:
        """Get current audio level in decibels.

        Returns the smoothed RMS level of recent audio in dB relative
        to full scale (dBFS). Typical voice range: -40 to -10 dBFS.

        Returns:
            float: Audio level in dB (negative values, typically -96 to 0).

        Example:
            ```python
            level = mic.get_level_db()
            if level > -30:
                print("Sound detected!")
            elif level > -20:
                print("Loud sound!")
            ```
        """
        with self._lock:
            return self._current_level_db

    def get_level_normalized(self) -> float:
        """Get current audio level normalized to 0.0-1.0 range.

        Convenience method that converts dB level to linear scale.
        Useful for visualization and threshold comparisons.

        Returns:
            float: Normalized level (0.0 = silence, 1.0 = full scale).

        Example:
            ```python
            level = mic.get_level_normalized()
            if level > 0.1:  # About -20 dB
                print("Significant sound detected")
            ```
        """
        db = self.get_level_db()
        # Convert from dB to linear (0 dB = 1.0, -96 dB = 0.0)
        if db <= self.DB_FLOOR:
            return 0.0
        # Map -96dB to 0dB -> 0.0 to 1.0
        return max(0.0, min(1.0, (db - self.DB_FLOOR) / (-self.DB_FLOOR)))

    def set_gain(self, gain: float):
        """Set software gain multiplier.

        Adjusts the gain applied to incoming audio samples.
        Does not require stopping capture.

        Args:
            gain: New gain value (0.1 to 10.0).

        Raises:
            ValueError: If gain out of valid range.

        Example:
            ```python
            mic.set_gain(2.0)  # Double the amplitude
            ```
        """
        if not 0.1 <= gain <= 10.0:
            raise ValueError(f"Gain must be 0.1-10.0, got {gain}")

        with self._lock:
            self.config.gain = gain

    def calibrate_noise_floor(self, duration_seconds: float = 1.0) -> float:
        """Calibrate the ambient noise floor.

        Captures audio for the specified duration and calculates the
        average noise level. Useful for setting detection thresholds.

        Args:
            duration_seconds: Duration to sample for calibration.

        Returns:
            float: Measured noise floor in dB.

        Raises:
            RuntimeError: If not capturing.

        Example:
            ```python
            mic.start_capture()
            noise_floor = mic.calibrate_noise_floor(2.0)
            threshold = noise_floor + 10  # 10 dB above noise
            print(f"Detection threshold: {threshold:.1f} dB")
            ```
        """
        with self._lock:
            if self._state != CaptureState.CAPTURING:
                raise RuntimeError("Must be capturing to calibrate")

        samples_needed = int(self.config.sample_rate * duration_seconds)
        samples = self.read_samples(samples_needed)

        if np is None or len(samples) == 0:
            return self.DB_FLOOR

        # Calculate RMS
        rms = np.sqrt(np.mean(samples.astype(np.float64) ** 2))
        if rms > 0:
            return 20 * math.log10(rms / self.REFERENCE_AMPLITUDE)
        return self.DB_FLOOR

    def wait_for_sound(
        self,
        threshold_db: float = -40.0,
        timeout_seconds: float = 10.0
    ) -> bool:
        """Wait for sound above threshold.

        Blocks until audio level exceeds the specified threshold or
        timeout is reached. Useful for voice activity detection.

        Args:
            threshold_db: Minimum level to trigger (default -40 dB).
            timeout_seconds: Maximum wait time.

        Returns:
            bool: True if sound detected, False if timeout.

        Example:
            ```python
            mic.start_capture()
            print("Listening for sound...")
            if mic.wait_for_sound(threshold_db=-30, timeout_seconds=5):
                print("Sound detected!")
            else:
                print("Timeout - no sound detected")
            ```
        """
        start_time = time.time()

        while time.time() - start_time < timeout_seconds:
            if self.get_level_db() > threshold_db:
                return True
            time.sleep(0.01)  # 10ms polling

        return False

    def deinit(self):
        """Deinitialize driver and release resources.

        Call this method when done with the microphone to ensure
        clean shutdown of audio streams and threads.

        Example:
            ```python
            mic = INMP441Driver()
            try:
                mic.start_capture()
                # ... use microphone ...
            finally:
                mic.deinit()
            ```
        """
        self.stop_capture()

        with self._lock:
            if self._stream is not None:
                try:
                    self._stream.close()
                except Exception:
                    pass
                self._stream = None

            self._state = CaptureState.STOPPED

    def __enter__(self):
        """Context manager entry - starts capture."""
        self.start_capture()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - stops capture and deinitializes."""
        self.deinit()
        return False

    def __del__(self):
        """Destructor - ensure cleanup on garbage collection."""
        try:
            self.deinit()
        except Exception:
            pass


# Factory function for convenience
def create_inmp441_driver(
    sample_rate: int = 16000,
    gain: float = 1.0,
    mock_mode: bool = False
) -> INMP441Driver:
    """Create INMP441 driver with common configuration.

    Convenience factory function for quick driver instantiation.

    Args:
        sample_rate: Sample rate in Hz (default 16000).
        gain: Software gain multiplier (default 1.0).
        mock_mode: Use mock audio for testing (default False).

    Returns:
        INMP441Driver: Configured driver instance.

    Example:
        ```python
        # Quick setup for voice recognition
        mic = create_inmp441_driver(sample_rate=16000)

        # High-quality capture
        mic = create_inmp441_driver(sample_rate=44100, gain=1.5)

        # Testing without hardware
        mic = create_inmp441_driver(mock_mode=True)
        ```
    """
    config = INMP441Config(sample_rate=sample_rate, gain=gain)
    return INMP441Driver(config=config, mock_mode=mock_mode)
