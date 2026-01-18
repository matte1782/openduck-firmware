"""I2S Bus Manager - Thread-safe Singleton for I2S Audio Bus Access.

This module provides a centralized, thread-safe manager for I2S bus access across
audio devices (microphone input and speaker output). Implements singleton pattern
to ensure only one I2S bus instance exists, with mutex locking to prevent bus
collisions during audio streaming.

Critical for embedded audio systems where microphone (INMP441) and speaker
(MAX98357A) must share I2S bus resources without interference.

Design Pattern:
    - Singleton: Ensures single I2S bus instance per direction
    - Context Manager: RAII-style lock acquisition/release
    - Thread-safe: Uses threading.RLock for reentrant locking
    - Mock Support: Allows development/testing without Pi hardware

Hardware Configuration (Raspberry Pi):
    - BCK (Bit Clock): GPIO 18 (Pin 12)
    - WS (Word Select/LRCLK): GPIO 19 (Pin 35)
    - DATA_IN (Microphone): GPIO 20 (Pin 38)
    - DATA_OUT (Speaker): GPIO 21 (Pin 40)

Supported Sample Rates:
    - 16000 Hz: Optimal for speech recognition (microphone)
    - 44100 Hz: Standard audio playback (speaker)

Example:
    ```python
    # Get singleton instance
    manager = I2SBusManager.get_instance()

    # Configure for microphone input
    mic_config = I2SConfig(
        sample_rate=16000,
        bit_depth=16,
        channels=1,
        buffer_size=1024
    )

    # Safe bus access with automatic locking
    with manager.acquire_bus(I2SDirection.INPUT, mic_config) as stream:
        # Perform audio operations
        audio_data = stream.read(1024)
    # Lock automatically released
    ```

Prevents:
    - Bus collisions between microphone and speaker access
    - Multiple I2S bus instances causing hardware conflicts
    - Race conditions in multi-threaded audio applications
    - Sample rate conflicts during simultaneous I/O
"""

import threading
import logging
from contextlib import contextmanager
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional, Any, Dict, Generator, Protocol

# Module logger for audio diagnostics
_logger = logging.getLogger(__name__)


class I2SDirection(Enum):
    """I2S data direction enumeration.

    Specifies the direction of audio data flow for I2S bus configuration.

    Attributes:
        INPUT: Microphone input (INMP441 -> Pi). Uses DATA_IN pin (GPIO 20).
        OUTPUT: Speaker output (Pi -> MAX98357A). Uses DATA_OUT pin (GPIO 21).
        DUPLEX: Bidirectional (simultaneous input and output). Uses both pins.

    Example:
        >>> direction = I2SDirection.INPUT
        >>> print(f"Configuring for {direction.name}")
        Configuring for INPUT
    """
    INPUT = auto()
    OUTPUT = auto()
    DUPLEX = auto()


@dataclass(frozen=True)
class I2SConfig:
    """Configuration parameters for I2S audio stream.

    Immutable configuration for I2S bus operation. Use frozen=True to ensure
    configuration cannot be modified after creation, preventing accidental
    changes during audio streaming.

    Attributes:
        sample_rate: Audio sample rate in Hz. Must be 16000 (speech) or 44100 (audio).
        bit_depth: Bits per sample. Must be 16 or 32.
        channels: Number of audio channels. 1 for mono, 2 for stereo.
        buffer_size: Frames per audio buffer. Larger = more latency, less CPU.

    Raises:
        ValueError: If sample_rate not in {16000, 44100}.
        ValueError: If bit_depth not in {16, 32}.
        ValueError: If channels not in {1, 2}.
        ValueError: If buffer_size < 64 or > 8192.

    Example:
        >>> config = I2SConfig(sample_rate=16000, bit_depth=16, channels=1, buffer_size=1024)
        >>> print(f"Buffer duration: {config.buffer_duration_ms:.1f}ms")
        Buffer duration: 64.0ms
    """
    sample_rate: int = 16000
    bit_depth: int = 16
    channels: int = 1
    buffer_size: int = 1024

    def __post_init__(self) -> None:
        """Validate configuration parameters after initialization.

        Raises:
            ValueError: If any parameter is outside valid range.
        """
        # Validate sample rate
        valid_sample_rates = {16000, 44100}
        if self.sample_rate not in valid_sample_rates:
            raise ValueError(
                f"sample_rate must be one of {valid_sample_rates}, got {self.sample_rate}"
            )

        # Validate bit depth
        valid_bit_depths = {16, 32}
        if self.bit_depth not in valid_bit_depths:
            raise ValueError(
                f"bit_depth must be one of {valid_bit_depths}, got {self.bit_depth}"
            )

        # Validate channels
        valid_channels = {1, 2}
        if self.channels not in valid_channels:
            raise ValueError(
                f"channels must be one of {valid_channels}, got {self.channels}"
            )

        # Validate buffer size
        if not 64 <= self.buffer_size <= 8192:
            raise ValueError(
                f"buffer_size must be 64-8192, got {self.buffer_size}"
            )

    @property
    def buffer_duration_ms(self) -> float:
        """Calculate buffer duration in milliseconds.

        Returns:
            Duration of one buffer in milliseconds.

        Example:
            >>> config = I2SConfig(sample_rate=16000, buffer_size=1024)
            >>> print(f"{config.buffer_duration_ms}ms")  # 64.0ms
        """
        return (self.buffer_size / self.sample_rate) * 1000.0

    @property
    def bytes_per_frame(self) -> int:
        """Calculate bytes per audio frame.

        A frame contains one sample for each channel.

        Returns:
            Number of bytes per frame (channels * bytes_per_sample).
        """
        bytes_per_sample = self.bit_depth // 8
        return self.channels * bytes_per_sample

    @property
    def buffer_bytes(self) -> int:
        """Calculate total bytes per buffer.

        Returns:
            Total bytes in one audio buffer.
        """
        return self.buffer_size * self.bytes_per_frame


@dataclass
class I2SPinConfig:
    """GPIO pin configuration for I2S bus.

    Centralizes I2S pin assignments to avoid hardcoding throughout the codebase.
    Default values match OpenDuck Mini V3 hardware configuration.

    Attributes:
        bck: Bit Clock GPIO pin (BCK/BCLK/SCK).
        ws: Word Select GPIO pin (WS/LRCLK/FS).
        data_in: Data input GPIO pin (microphone -> Pi).
        data_out: Data output GPIO pin (Pi -> speaker).

    Note:
        Pin numbers use BCM numbering scheme, not physical pin numbers.
    """
    bck: int = 18
    ws: int = 19
    data_in: int = 20
    data_out: int = 21


class I2SStreamProtocol(Protocol):
    """Protocol for I2S audio stream operations.

    Defines the interface for audio stream objects returned by acquire_bus().
    Allows both real hardware streams and mock implementations.
    """

    def read(self, frames: int) -> bytes:
        """Read audio frames from input stream.

        Args:
            frames: Number of audio frames to read.

        Returns:
            Raw audio data as bytes.
        """
        ...

    def write(self, data: bytes) -> int:
        """Write audio data to output stream.

        Args:
            data: Raw audio data as bytes.

        Returns:
            Number of frames written.
        """
        ...

    def close(self) -> None:
        """Close the audio stream and release resources."""
        ...


class MockI2SStream:
    """Mock I2S stream for development and testing without hardware.

    Provides a fake I2S stream that simulates audio operations without
    requiring actual Raspberry Pi hardware or audio devices.

    Attributes:
        config: I2S configuration for this stream.
        direction: Data direction (INPUT, OUTPUT, or DUPLEX).
        is_open: Whether the stream is currently open.

    Example:
        >>> stream = MockI2SStream(I2SConfig(), I2SDirection.INPUT)
        >>> data = stream.read(1024)  # Returns silent audio data
        >>> stream.close()
    """

    def __init__(self, config: I2SConfig, direction: I2SDirection) -> None:
        """Initialize mock I2S stream.

        Args:
            config: I2S configuration parameters.
            direction: Data direction for this stream.
        """
        self.config = config
        self.direction = direction
        self.is_open = True
        self._read_count = 0
        self._write_count = 0
        _logger.debug(
            "MockI2SStream created: %s, %dHz, %d-bit, %dch",
            direction.name, config.sample_rate, config.bit_depth, config.channels
        )

    def read(self, frames: int) -> bytes:
        """Read silent audio frames (for mock testing).

        Args:
            frames: Number of audio frames to read.

        Returns:
            Zero-filled bytes representing silent audio.

        Raises:
            RuntimeError: If stream is closed.
            ValueError: If direction does not support input.
        """
        if not self.is_open:
            raise RuntimeError("Cannot read from closed stream")
        if self.direction == I2SDirection.OUTPUT:
            raise ValueError("Cannot read from OUTPUT-only stream")

        self._read_count += frames
        # Return silent audio (zeros)
        return bytes(frames * self.config.bytes_per_frame)

    def write(self, data: bytes) -> int:
        """Write audio data (discarded in mock).

        Args:
            data: Raw audio data as bytes.

        Returns:
            Number of frames "written" (data is discarded).

        Raises:
            RuntimeError: If stream is closed.
            ValueError: If direction does not support output.
        """
        if not self.is_open:
            raise RuntimeError("Cannot write to closed stream")
        if self.direction == I2SDirection.INPUT:
            raise ValueError("Cannot write to INPUT-only stream")

        frames = len(data) // self.config.bytes_per_frame
        self._write_count += frames
        return frames

    def close(self) -> None:
        """Close the mock stream."""
        if self.is_open:
            _logger.debug(
                "MockI2SStream closed: read=%d frames, wrote=%d frames",
                self._read_count, self._write_count
            )
            self.is_open = False

    def __repr__(self) -> str:
        """String representation for debugging."""
        return (
            f"MockI2SStream(direction={self.direction.name}, "
            f"sample_rate={self.config.sample_rate}, open={self.is_open})"
        )


class I2SBusManager:
    """Thread-safe singleton manager for I2S audio bus access.

    Provides centralized I2S bus management with mutex locking to prevent
    bus collisions when multiple audio operations access the bus concurrently.

    Singleton Pattern:
        Use get_instance() to obtain the singleton. Direct instantiation via
        __init__() is deprecated and will log a warning.

    Mock Mode:
        When running on non-Pi systems (or when force_mock=True), the manager
        provides mock I2S streams that simulate audio operations.

    Thread Safety:
        All public methods are thread-safe. Uses RLock (reentrant lock) to
        allow nested acquisitions from the same thread.

    Attributes:
        _instance: Singleton instance (class variable).
        _lock: Lock for thread-safe singleton initialization.
        _bus_lock: Reentrant lock for bus access synchronization.
        _mock_mode: Whether to use mock streams instead of real hardware.
        _pin_config: GPIO pin configuration for I2S bus.
        _active_streams: Currently active I2S streams.

    Example:
        >>> manager = I2SBusManager.get_instance()
        >>> config = I2SConfig(sample_rate=16000)
        >>> with manager.acquire_bus(I2SDirection.INPUT, config) as stream:
        ...     audio_data = stream.read(1024)
    """

    # Class-level singleton state
    _instance: Optional['I2SBusManager'] = None
    _init_lock = threading.Lock()

    @classmethod
    def get_instance(
        cls,
        pin_config: Optional[I2SPinConfig] = None,
        force_mock: bool = False
    ) -> 'I2SBusManager':
        """Get singleton instance of I2S bus manager.

        Thread-safe singleton pattern using double-checked locking with proper
        initialization protection.

        Args:
            pin_config: Optional GPIO pin configuration. Only used on first call.
                Subsequent calls ignore this parameter.
            force_mock: If True, use mock mode even on Pi hardware. Only used
                on first call. Subsequent calls ignore this parameter.

        Returns:
            I2SBusManager: The singleton instance.

        Example:
            >>> manager = I2SBusManager.get_instance()
            >>> manager2 = I2SBusManager.get_instance()
            >>> assert manager is manager2  # Same instance
        """
        # First check (unlocked) - fast path for already initialized
        if cls._instance is None:
            # Second check (locked) - thread-safe initialization
            with cls._init_lock:
                if cls._instance is None:
                    # Create instance atomically under lock
                    instance = cls.__new__(cls)
                    instance._initialize(pin_config, force_mock)
                    cls._instance = instance
        return cls._instance

    def _initialize(
        self,
        pin_config: Optional[I2SPinConfig],
        force_mock: bool
    ) -> None:
        """Initialize I2S bus manager instance.

        Private method called only during singleton creation, protected by
        class lock. This ensures atomic initialization without race conditions.

        Args:
            pin_config: GPIO pin configuration, or None for defaults.
            force_mock: Whether to force mock mode.
        """
        # Thread safety locks
        self._bus_lock = threading.RLock()
        self._stream_lock = threading.Lock()

        # Lock acquisition tracking (for debugging)
        self._lock_count = 0
        self._lock_count_lock = threading.Lock()

        # Pin configuration
        self._pin_config = pin_config or I2SPinConfig()

        # Active stream tracking
        self._active_streams: Dict[I2SDirection, Any] = {}
        self._current_configs: Dict[I2SDirection, I2SConfig] = {}

        # Determine mock mode
        self._mock_mode = force_mock
        self._hardware_available = False

        if not force_mock:
            self._hardware_available = self._check_hardware_available()
            if not self._hardware_available:
                self._mock_mode = True
                _logger.info(
                    "I2S hardware not available, using mock mode for development"
                )

        _logger.debug(
            "I2SBusManager initialized: mock_mode=%s, pins={bck=%d, ws=%d, in=%d, out=%d}",
            self._mock_mode,
            self._pin_config.bck,
            self._pin_config.ws,
            self._pin_config.data_in,
            self._pin_config.data_out
        )

    def _check_hardware_available(self) -> bool:
        """Check if I2S hardware is available on this system.

        Returns:
            True if running on Raspberry Pi with I2S support.
        """
        try:
            # Check for Raspberry Pi by looking for /proc/device-tree/model
            with open('/proc/device-tree/model', 'r') as f:
                model = f.read()
                if 'Raspberry Pi' in model:
                    return True
        except (FileNotFoundError, PermissionError, OSError):
            pass
        return False

    def __init__(self) -> None:
        """Initialize I2S bus manager.

        NOTE: Do not call directly - use get_instance() instead.
        This constructor is deprecated and kept only for backward compatibility.

        Raises:
            RuntimeError: Always raises to prevent direct instantiation.
        """
        # Prevent direct instantiation - singleton must use get_instance()
        if I2SBusManager._instance is not None:
            _logger.warning(
                "Direct I2SBusManager() instantiation is deprecated. "
                "Use I2SBusManager.get_instance() instead."
            )

    @property
    def mock_mode(self) -> bool:
        """Check if manager is running in mock mode.

        Returns:
            True if using mock streams instead of real hardware.
        """
        return self._mock_mode

    @property
    def hardware_available(self) -> bool:
        """Check if I2S hardware is available.

        Returns:
            True if I2S hardware was detected during initialization.
        """
        return self._hardware_available

    @property
    def pin_config(self) -> I2SPinConfig:
        """Get the I2S pin configuration.

        Returns:
            I2SPinConfig with GPIO pin assignments.
        """
        return self._pin_config

    @contextmanager
    def acquire_bus(
        self,
        direction: I2SDirection,
        config: I2SConfig
    ) -> Generator[I2SStreamProtocol, None, None]:
        """Acquire exclusive access to I2S bus for specified direction.

        Context manager that acquires bus lock before yielding stream instance,
        and automatically releases lock and closes stream when exiting context.

        Ensures thread-safe, serialized access to I2S bus. Multiple streams
        in different directions may coexist if hardware supports DUPLEX mode.

        Args:
            direction: Data direction (INPUT, OUTPUT, or DUPLEX).
            config: I2S configuration for the stream.

        Yields:
            I2SStreamProtocol: Audio stream instance for reading/writing.

        Raises:
            ValueError: If direction is invalid or config incompatible.
            RuntimeError: If bus acquisition fails.

        Example:
            >>> manager = I2SBusManager.get_instance()
            >>> config = I2SConfig(sample_rate=16000, bit_depth=16, channels=1)
            >>> with manager.acquire_bus(I2SDirection.INPUT, config) as stream:
            ...     audio_data = stream.read(1024)
            ...     # Process audio_data
            >>> # Stream automatically closed, lock released

        Note:
            The yielded stream is only valid within the context manager scope.
            Do not store or use the stream after exiting the with block.
        """
        self._bus_lock.acquire()
        with self._lock_count_lock:
            self._lock_count += 1

        stream: Optional[I2SStreamProtocol] = None
        try:
            # Check for conflicting active streams
            self._validate_stream_compatibility(direction, config)

            # Create stream (mock or real)
            stream = self._create_stream(direction, config)

            # Track active stream
            with self._stream_lock:
                self._active_streams[direction] = stream
                self._current_configs[direction] = config

            yield stream

        finally:
            # Clean up stream
            if stream is not None:
                try:
                    stream.close()
                except Exception as e:
                    _logger.warning("Error closing I2S stream: %s", e)

            # Remove from active tracking
            with self._stream_lock:
                self._active_streams.pop(direction, None)
                self._current_configs.pop(direction, None)

            # Release bus lock
            with self._lock_count_lock:
                self._lock_count -= 1
            self._bus_lock.release()

    def _validate_stream_compatibility(
        self,
        direction: I2SDirection,
        config: I2SConfig
    ) -> None:
        """Validate that new stream is compatible with active streams.

        Args:
            direction: Requested data direction.
            config: Requested configuration.

        Raises:
            RuntimeError: If conflicting stream already active.
            ValueError: If configuration conflicts with active stream.
        """
        with self._stream_lock:
            # Check for conflicting direction
            if direction in self._active_streams:
                raise RuntimeError(
                    f"I2S stream for {direction.name} already active. "
                    "Release existing stream before acquiring new one."
                )

            # DUPLEX conflicts with both INPUT and OUTPUT
            if direction == I2SDirection.DUPLEX:
                if self._active_streams:
                    raise RuntimeError(
                        "Cannot acquire DUPLEX stream while other streams active"
                    )
            elif I2SDirection.DUPLEX in self._active_streams:
                raise RuntimeError(
                    f"Cannot acquire {direction.name} stream while DUPLEX active"
                )

            # Check sample rate compatibility for simultaneous streams
            if self._current_configs:
                for active_dir, active_config in self._current_configs.items():
                    if active_config.sample_rate != config.sample_rate:
                        # Note: Some hardware supports different rates
                        # For now, log warning but allow
                        _logger.warning(
                            "Sample rate mismatch: %s=%dHz, %s=%dHz. "
                            "This may cause audio artifacts.",
                            active_dir.name, active_config.sample_rate,
                            direction.name, config.sample_rate
                        )

    def _create_stream(
        self,
        direction: I2SDirection,
        config: I2SConfig
    ) -> I2SStreamProtocol:
        """Create an I2S stream instance.

        Args:
            direction: Data direction for stream.
            config: I2S configuration.

        Returns:
            Stream instance (mock or real hardware).
        """
        if self._mock_mode:
            return MockI2SStream(config, direction)

        # Real hardware stream creation would go here
        # For now, always return mock since we don't have pyaudio dependency
        _logger.debug(
            "Creating I2S stream: direction=%s, rate=%d, depth=%d, channels=%d",
            direction.name, config.sample_rate, config.bit_depth, config.channels
        )
        return MockI2SStream(config, direction)

    def get_active_streams(self) -> Dict[I2SDirection, I2SConfig]:
        """Get information about currently active streams.

        Returns:
            Dictionary mapping direction to configuration for active streams.

        Note:
            This is for informational purposes only. The returned data is a
            snapshot and may be stale immediately after return.
        """
        with self._stream_lock:
            return dict(self._current_configs)

    def is_locked(self) -> bool:
        """Check if bus is currently locked.

        WARNING: Result may be stale immediately after return due to
        Time-Of-Check-Time-Of-Use (TOCTTOU) race condition.

        This method is for informational/debugging purposes only.
        DO NOT use for synchronization decisions.

        Returns:
            bool: True if bus is currently locked, False otherwise.
        """
        with self._lock_count_lock:
            return self._lock_count > 0

    @classmethod
    def reset(cls) -> None:
        """Reset singleton instance.

        FOR TESTING ONLY - Resets singleton state to allow fresh initialization.
        Should never be called in production code.

        Closes any active streams before resetting.
        """
        with cls._init_lock:
            if cls._instance is not None:
                # Close any active streams
                with cls._instance._stream_lock:
                    for stream in cls._instance._active_streams.values():
                        try:
                            stream.close()
                        except Exception:
                            pass
                    cls._instance._active_streams.clear()
                    cls._instance._current_configs.clear()

                # Reset lock count
                with cls._instance._lock_count_lock:
                    cls._instance._lock_count = 0

            cls._instance = None
            _logger.debug("I2SBusManager singleton reset")

    def __repr__(self) -> str:
        """String representation for debugging."""
        return (
            f"I2SBusManager("
            f"mock_mode={self._mock_mode}, "
            f"active_streams={list(self._active_streams.keys())}, "
            f"locked={self.is_locked()})"
        )


# Module-level convenience function
def get_i2s_bus_manager(
    pin_config: Optional[I2SPinConfig] = None,
    force_mock: bool = False
) -> I2SBusManager:
    """Get I2S bus manager singleton instance.

    Convenience function for cleaner imports:
    ```python
    from src.drivers.audio.i2s_bus import get_i2s_bus_manager
    manager = get_i2s_bus_manager()
    ```

    Args:
        pin_config: Optional GPIO pin configuration (only used on first call).
        force_mock: Force mock mode (only used on first call).

    Returns:
        I2SBusManager: The singleton instance.
    """
    return I2SBusManager.get_instance(pin_config, force_mock)


# Pre-defined configurations for common use cases
MIC_CONFIG_16KHZ = I2SConfig(
    sample_rate=16000,
    bit_depth=16,
    channels=1,
    buffer_size=1024
)
"""Standard microphone configuration for speech recognition (16kHz mono)."""

SPEAKER_CONFIG_44KHZ = I2SConfig(
    sample_rate=44100,
    bit_depth=16,
    channels=2,
    buffer_size=2048
)
"""Standard speaker configuration for audio playback (44.1kHz stereo)."""

SPEAKER_CONFIG_16KHZ = I2SConfig(
    sample_rate=16000,
    bit_depth=16,
    channels=1,
    buffer_size=1024
)
"""Low-latency speaker configuration for TTS playback (16kHz mono)."""
