"""Pytest fixtures for audio subsystem tests.

Provides mock I2S streams, microphone drivers, and test audio data.
All hardware dependencies are mocked to allow testing without Raspberry Pi.
"""

import math
import pytest
import threading
import numpy as np
from dataclasses import dataclass
from typing import Optional, List, Any
from unittest.mock import Mock, MagicMock, patch


# =============================================================================
# Audio Configuration Fixtures
# =============================================================================

@pytest.fixture
def audio_config():
    """Standard audio configuration for testing."""
    return {
        'sample_rate': 16000,
        'bit_depth': 16,
        'channels': 1,
        'buffer_size': 1024,
    }


@pytest.fixture
def high_quality_config():
    """High-quality audio configuration (44.1kHz stereo)."""
    return {
        'sample_rate': 44100,
        'bit_depth': 16,
        'channels': 2,
        'buffer_size': 2048,
    }


# =============================================================================
# Sample Audio Data Fixtures
# =============================================================================

@pytest.fixture
def sample_audio_silence(audio_config):
    """Generate silent audio samples (zeros)."""
    num_samples = audio_config['buffer_size']
    return np.zeros(num_samples, dtype=np.int16)


@pytest.fixture
def sample_audio_sine(audio_config):
    """Generate sine wave audio samples (440Hz tone)."""
    sample_rate = audio_config['sample_rate']
    duration_samples = audio_config['buffer_size']
    frequency = 440.0  # A4 note
    amplitude = 16000  # ~50% of int16 max

    t = np.arange(duration_samples) / sample_rate
    sine_wave = amplitude * np.sin(2 * np.pi * frequency * t)
    return sine_wave.astype(np.int16)


@pytest.fixture
def sample_audio_noise(audio_config):
    """Generate white noise audio samples."""
    num_samples = audio_config['buffer_size']
    # Low amplitude noise to simulate quiet background
    noise = np.random.randint(-1000, 1000, size=num_samples, dtype=np.int16)
    return noise


@pytest.fixture
def sample_audio_speech_level(audio_config):
    """Generate audio samples at typical speech level (-20 dB)."""
    num_samples = audio_config['buffer_size']
    # Speech typically at -20 to -10 dBFS
    # -20 dB = 10^(-20/20) = 0.1 of full scale
    # For int16, full scale = 32767, so 0.1 * 32767 = ~3277
    amplitude = 3277

    # Mix of frequencies to simulate speech
    sample_rate = audio_config['sample_rate']
    t = np.arange(num_samples) / sample_rate

    # Fundamental + harmonics
    wave = (
        0.5 * np.sin(2 * np.pi * 200 * t) +  # Low fundamental
        0.3 * np.sin(2 * np.pi * 400 * t) +  # First harmonic
        0.2 * np.sin(2 * np.pi * 800 * t)    # Second harmonic
    )

    return (amplitude * wave).astype(np.int16)


@pytest.fixture
def sample_audio_float32_normalized():
    """Generate normalized float32 audio samples (-1.0 to 1.0)."""
    num_samples = 1024
    t = np.arange(num_samples) / 16000
    sine = 0.5 * np.sin(2 * np.pi * 440 * t)
    return sine.astype(np.float32)


# =============================================================================
# Mock I2S Stream Fixtures
# =============================================================================

@dataclass
class MockI2SStreamConfig:
    """Configuration for mock I2S stream."""
    sample_rate: int = 16000
    bit_depth: int = 16
    channels: int = 1
    buffer_size: int = 1024
    return_noise: bool = True


class MockI2SStreamFixture:
    """Mock I2S stream for testing without hardware.

    Simulates I2S read/write operations with configurable behavior.
    """

    def __init__(self, config: MockI2SStreamConfig):
        self.config = config
        self.is_open = True
        self._read_count = 0
        self._write_count = 0
        self._read_data: List[bytes] = []
        self._write_data: List[bytes] = []
        self._error_on_read = False
        self._error_on_write = False

    def read(self, frames: int) -> bytes:
        """Read mock audio frames."""
        if not self.is_open:
            raise RuntimeError("Cannot read from closed stream")
        if self._error_on_read:
            raise IOError("Simulated I2S read error")

        self._read_count += frames
        bytes_per_frame = (self.config.bit_depth // 8) * self.config.channels

        if self.config.return_noise:
            # Generate low-level noise
            samples = np.random.randint(
                -500, 500,
                size=frames * self.config.channels,
                dtype=np.int16
            )
            return samples.tobytes()
        else:
            # Return silence
            return bytes(frames * bytes_per_frame)

    def write(self, data: bytes) -> int:
        """Write audio data (discarded in mock)."""
        if not self.is_open:
            raise RuntimeError("Cannot write to closed stream")
        if self._error_on_write:
            raise IOError("Simulated I2S write error")

        bytes_per_frame = (self.config.bit_depth // 8) * self.config.channels
        frames = len(data) // bytes_per_frame
        self._write_count += frames
        self._write_data.append(data)
        return frames

    def close(self) -> None:
        """Close the mock stream."""
        self.is_open = False

    def set_error_on_read(self, enable: bool = True):
        """Configure stream to raise error on next read."""
        self._error_on_read = enable

    def set_error_on_write(self, enable: bool = True):
        """Configure stream to raise error on next write."""
        self._error_on_write = enable


@pytest.fixture
def mock_i2s_stream(audio_config):
    """Create a mock I2S stream for testing."""
    config = MockI2SStreamConfig(
        sample_rate=audio_config['sample_rate'],
        bit_depth=audio_config['bit_depth'],
        channels=audio_config['channels'],
        buffer_size=audio_config['buffer_size']
    )
    return MockI2SStreamFixture(config)


@pytest.fixture
def mock_i2s_stream_stereo(high_quality_config):
    """Create a mock stereo I2S stream."""
    config = MockI2SStreamConfig(
        sample_rate=high_quality_config['sample_rate'],
        bit_depth=high_quality_config['bit_depth'],
        channels=high_quality_config['channels'],
        buffer_size=high_quality_config['buffer_size']
    )
    return MockI2SStreamFixture(config)


# =============================================================================
# Mock INMP441 Driver Fixtures
# =============================================================================

@pytest.fixture
def mock_inmp441():
    """Create a mock INMP441 microphone driver."""
    mock = MagicMock()
    mock.config = MagicMock()
    mock.config.sample_rate = 16000
    mock.config.bit_depth = 16
    mock.config.channels = 1
    mock.config.gain = 1.0
    mock.config.buffer_frames = 512

    mock.is_capturing = False
    mock._current_level_db = -60.0

    def start_capture():
        mock.is_capturing = True
        return True

    def stop_capture():
        mock.is_capturing = False
        return True

    def read_samples(num_samples):
        if not mock.is_capturing:
            raise RuntimeError("Not capturing")
        return np.random.randint(-1000, 1000, size=num_samples, dtype=np.int16)

    def get_level_db():
        return mock._current_level_db

    mock.start_capture = start_capture
    mock.stop_capture = stop_capture
    mock.read_samples = read_samples
    mock.get_level_db = get_level_db

    return mock


# =============================================================================
# Mock Sounddevice Fixtures
# =============================================================================

@pytest.fixture
def mock_sounddevice():
    """Mock sounddevice library for testing without audio hardware."""
    with patch.dict('sys.modules', {'sounddevice': MagicMock()}):
        import sys
        mock_sd = sys.modules['sounddevice']

        # Mock query_devices
        mock_sd.query_devices.return_value = [
            {
                'name': 'Mock Input Device',
                'max_input_channels': 2,
                'max_output_channels': 0,
                'default_samplerate': 16000.0,
            },
            {
                'name': 'Mock Output Device',
                'max_input_channels': 0,
                'max_output_channels': 2,
                'default_samplerate': 44100.0,
            }
        ]

        # Mock InputStream
        mock_stream = MagicMock()
        mock_stream.__enter__ = MagicMock(return_value=mock_stream)
        mock_stream.__exit__ = MagicMock(return_value=False)
        mock_sd.InputStream.return_value = mock_stream

        yield mock_sd


# =============================================================================
# I2S Bus Manager Fixtures
# =============================================================================

@pytest.fixture
def reset_i2s_singleton():
    """Reset I2S bus manager singleton before and after test."""
    # Import and reset before test
    try:
        from src.drivers.audio.i2s_bus import I2SBusManager
        I2SBusManager.reset()
    except ImportError:
        pass

    yield

    # Reset after test
    try:
        from src.drivers.audio.i2s_bus import I2SBusManager
        I2SBusManager.reset()
    except ImportError:
        pass


@pytest.fixture
def i2s_manager(reset_i2s_singleton):
    """Get a fresh I2S bus manager instance (mock mode)."""
    from src.drivers.audio.i2s_bus import I2SBusManager
    return I2SBusManager.get_instance(force_mock=True)


# =============================================================================
# Audio Capture Pipeline Fixtures
# =============================================================================

@pytest.fixture
def ring_buffer():
    """Create an audio ring buffer for testing."""
    from src.drivers.audio.audio_capture import AudioRingBuffer
    return AudioRingBuffer(capacity=4800, channels=1)  # 300ms at 16kHz


@pytest.fixture
def ring_buffer_stereo():
    """Create a stereo audio ring buffer."""
    from src.drivers.audio.audio_capture import AudioRingBuffer
    return AudioRingBuffer(capacity=4800, channels=2)


@pytest.fixture
def vad():
    """Create a voice activity detector for testing."""
    from src.drivers.audio.audio_capture import VoiceActivityDetector
    return VoiceActivityDetector(
        threshold_db=-40.0,
        min_speech_ms=100,
        sample_rate=16000
    )


@pytest.fixture
def capture_config():
    """Create audio capture configuration for testing."""
    from src.drivers.audio.audio_capture import AudioCaptureConfig
    return AudioCaptureConfig(
        sample_rate=16000,
        bit_depth=16,
        channels=1,
        buffer_duration_ms=1000,
        chunk_size_ms=20,
        vad_threshold_db=-40.0,
        vad_min_speech_ms=100
    )


# =============================================================================
# Performance Testing Fixtures
# =============================================================================

@pytest.fixture
def latency_timer():
    """Timer context manager for latency measurements."""
    import time

    class LatencyTimer:
        def __init__(self):
            self.start_time = None
            self.end_time = None
            self.elapsed_ms = None

        def __enter__(self):
            self.start_time = time.perf_counter()
            return self

        def __exit__(self, *args):
            self.end_time = time.perf_counter()
            self.elapsed_ms = (self.end_time - self.start_time) * 1000
            return False

        def assert_under(self, max_ms: float, message: str = ""):
            """Assert elapsed time is under threshold."""
            assert self.elapsed_ms is not None, "Timer not used in context"
            assert self.elapsed_ms < max_ms, (
                f"{message}: {self.elapsed_ms:.2f}ms > {max_ms}ms limit"
            )

    return LatencyTimer


# =============================================================================
# Thread Safety Testing Fixtures
# =============================================================================

@pytest.fixture
def thread_barrier():
    """Create a threading barrier for synchronized test starts."""
    def create_barrier(num_threads: int):
        return threading.Barrier(num_threads)
    return create_barrier


@pytest.fixture
def concurrent_results():
    """Thread-safe results collector for concurrent tests."""
    class ConcurrentResults:
        def __init__(self):
            self._results: List[Any] = []
            self._errors: List[Exception] = []
            self._lock = threading.Lock()

        def add_result(self, result: Any):
            with self._lock:
                self._results.append(result)

        def add_error(self, error: Exception):
            with self._lock:
                self._errors.append(error)

        @property
        def results(self) -> List[Any]:
            with self._lock:
                return list(self._results)

        @property
        def errors(self) -> List[Exception]:
            with self._lock:
                return list(self._errors)

        @property
        def success_count(self) -> int:
            with self._lock:
                return len(self._results)

        @property
        def error_count(self) -> int:
            with self._lock:
                return len(self._errors)

    return ConcurrentResults()
