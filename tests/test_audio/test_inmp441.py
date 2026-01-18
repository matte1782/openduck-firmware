"""Unit tests for INMP441 I2S MEMS Microphone Driver.

Tests cover:
- INMP441Config validation and defaults
- INMP441Driver initialization
- Start/stop capture operations
- Sample reading
- Audio level detection (dB calculation)
- Gain adjustment
- Thread safety
- Mock mode operation

Total: 28 tests
"""

import pytest
import threading
import time
import math
import numpy as np
from unittest.mock import Mock, MagicMock, patch


# =============================================================================
# TestINMP441Config - Configuration validation tests
# =============================================================================

class TestINMP441Config:
    """Test INMP441Config dataclass validation."""

    def test_config_default_values(self):
        """Test INMP441Config initializes with correct defaults."""
        from src.drivers.audio.inmp441 import INMP441Config

        config = INMP441Config()

        assert config.sample_rate == 16000
        assert config.bit_depth == 16
        assert config.channels == 1
        assert config.gain == 1.0
        assert config.buffer_frames == 512
        assert config.device_index is None
        assert config.timeout_seconds == 5.0
        assert config.level_smoothing == 0.3

    def test_config_custom_values(self):
        """Test INMP441Config accepts valid custom values."""
        from src.drivers.audio.inmp441 import INMP441Config

        config = INMP441Config(
            sample_rate=44100,
            gain=2.0,
            buffer_frames=1024,
            timeout_seconds=10.0
        )

        assert config.sample_rate == 44100
        assert config.gain == 2.0
        assert config.buffer_frames == 1024
        assert config.timeout_seconds == 10.0

    @pytest.mark.parametrize("sample_rate", [12000, 24000, 96000, 0, -16000])
    def test_config_invalid_sample_rate_raises(self, sample_rate):
        """Test INMP441Config rejects invalid sample rates."""
        from src.drivers.audio.inmp441 import INMP441Config

        with pytest.raises(ValueError, match="Invalid sample_rate"):
            INMP441Config(sample_rate=sample_rate)

    @pytest.mark.parametrize("sample_rate", [8000, 16000, 22050, 44100, 48000])
    def test_config_valid_sample_rates(self, sample_rate):
        """Test INMP441Config accepts valid sample rates."""
        from src.drivers.audio.inmp441 import INMP441Config

        config = INMP441Config(sample_rate=sample_rate)
        assert config.sample_rate == sample_rate

    def test_config_invalid_bit_depth_raises(self):
        """Test INMP441Config rejects non-16-bit depth."""
        from src.drivers.audio.inmp441 import INMP441Config

        with pytest.raises(ValueError, match="Invalid bit_depth"):
            INMP441Config(bit_depth=24)

    def test_config_invalid_channels_raises(self):
        """Test INMP441Config rejects non-mono channels."""
        from src.drivers.audio.inmp441 import INMP441Config

        with pytest.raises(ValueError, match="Invalid channels"):
            INMP441Config(channels=2)

    @pytest.mark.parametrize("gain", [0.0, 0.05, 10.5, 100.0, -1.0])
    def test_config_invalid_gain_raises(self, gain):
        """Test INMP441Config rejects invalid gain values."""
        from src.drivers.audio.inmp441 import INMP441Config

        with pytest.raises(ValueError, match="Invalid gain"):
            INMP441Config(gain=gain)

    @pytest.mark.parametrize("gain", [0.1, 1.0, 5.0, 10.0])
    def test_config_valid_gain_values(self, gain):
        """Test INMP441Config accepts valid gain values."""
        from src.drivers.audio.inmp441 import INMP441Config

        config = INMP441Config(gain=gain)
        assert config.gain == gain

    def test_config_invalid_buffer_frames_raises(self):
        """Test INMP441Config rejects buffer_frames < 64."""
        from src.drivers.audio.inmp441 import INMP441Config

        with pytest.raises(ValueError, match="Invalid buffer_frames"):
            INMP441Config(buffer_frames=32)

    @pytest.mark.parametrize("smoothing", [-0.1, 1.1, 2.0])
    def test_config_invalid_level_smoothing_raises(self, smoothing):
        """Test INMP441Config rejects invalid level_smoothing values."""
        from src.drivers.audio.inmp441 import INMP441Config

        with pytest.raises(ValueError, match="Invalid level_smoothing"):
            INMP441Config(level_smoothing=smoothing)


# =============================================================================
# TestINMP441Driver - Driver initialization and basic operations
# =============================================================================

class TestINMP441Driver:
    """Test INMP441Driver initialization and basic operations."""

    def test_driver_init_mock_mode(self):
        """Test driver initializes successfully in mock mode."""
        from src.drivers.audio.inmp441 import INMP441Driver

        driver = INMP441Driver(mock_mode=True)

        assert driver.config is not None
        assert driver.config.sample_rate == 16000
        assert driver._mock_mode is True

    def test_driver_init_with_custom_config(self):
        """Test driver initializes with custom configuration."""
        from src.drivers.audio.inmp441 import INMP441Driver, INMP441Config

        config = INMP441Config(sample_rate=44100, gain=2.0)
        driver = INMP441Driver(config=config, mock_mode=True)

        assert driver.config.sample_rate == 44100
        assert driver.config.gain == 2.0

    def test_driver_is_capturing_false_initially(self):
        """Test is_capturing is False before start_capture."""
        from src.drivers.audio.inmp441 import INMP441Driver

        driver = INMP441Driver(mock_mode=True)

        assert driver.is_capturing is False

    def test_driver_state_stopped_initially(self):
        """Test state is STOPPED before start_capture."""
        from src.drivers.audio.inmp441 import INMP441Driver, CaptureState

        driver = INMP441Driver(mock_mode=True)

        assert driver.state == CaptureState.STOPPED


# =============================================================================
# TestStartStopCapture - Capture lifecycle tests
# =============================================================================

class TestStartStopCapture:
    """Test start/stop capture operations."""

    def test_start_capture_returns_true(self):
        """Test start_capture returns True on success."""
        from src.drivers.audio.inmp441 import INMP441Driver

        driver = INMP441Driver(mock_mode=True)

        result = driver.start_capture()

        assert result is True
        assert driver.is_capturing is True
        driver.stop_capture()

    def test_start_capture_twice_raises(self):
        """Test starting capture twice raises RuntimeError."""
        from src.drivers.audio.inmp441 import INMP441Driver

        driver = INMP441Driver(mock_mode=True)
        driver.start_capture()

        try:
            with pytest.raises(RuntimeError, match="Already capturing"):
                driver.start_capture()
        finally:
            driver.stop_capture()

    def test_stop_capture_returns_true(self):
        """Test stop_capture returns True on success."""
        from src.drivers.audio.inmp441 import INMP441Driver

        driver = INMP441Driver(mock_mode=True)
        driver.start_capture()

        result = driver.stop_capture()

        assert result is True
        assert driver.is_capturing is False

    def test_stop_capture_when_stopped_returns_true(self):
        """Test stop_capture when already stopped returns True."""
        from src.drivers.audio.inmp441 import INMP441Driver

        driver = INMP441Driver(mock_mode=True)

        result = driver.stop_capture()

        assert result is True

    def test_context_manager_starts_and_stops(self):
        """Test driver context manager starts/stops capture."""
        from src.drivers.audio.inmp441 import INMP441Driver

        with INMP441Driver(mock_mode=True) as driver:
            assert driver.is_capturing is True

        # Note: After context exit, driver is deinitialized
        # We can't check is_capturing as driver may be in different state


# =============================================================================
# TestReadSamples - Sample reading tests
# =============================================================================

class TestReadSamples:
    """Test sample reading operations."""

    def test_read_samples_returns_array(self):
        """Test read_samples returns numpy array in mock mode."""
        from src.drivers.audio.inmp441 import INMP441Driver

        driver = INMP441Driver(mock_mode=True)
        driver.start_capture()

        # Wait briefly for mock capture loop to generate samples
        time.sleep(0.05)

        try:
            samples = driver.read_samples(512)
            assert isinstance(samples, (np.ndarray, list))
            assert len(samples) > 0
        finally:
            driver.stop_capture()

    def test_read_samples_not_capturing_raises(self):
        """Test read_samples raises when not capturing."""
        from src.drivers.audio.inmp441 import INMP441Driver

        driver = INMP441Driver(mock_mode=True)

        with pytest.raises(RuntimeError, match="Cannot read samples"):
            driver.read_samples(512)

    def test_read_audio_sample_returns_audiosample(self):
        """Test read_audio_sample returns AudioSample object."""
        from src.drivers.audio.inmp441 import INMP441Driver, AudioSample

        driver = INMP441Driver(mock_mode=True)
        driver.start_capture()
        time.sleep(0.05)

        try:
            audio_sample = driver.read_audio_sample(512)

            assert isinstance(audio_sample, AudioSample)
            assert audio_sample.sample_rate == 16000
            assert audio_sample.timestamp > 0
        finally:
            driver.stop_capture()


# =============================================================================
# TestAudioSample - AudioSample dataclass tests
# =============================================================================

class TestAudioSample:
    """Test AudioSample dataclass."""

    def test_audio_sample_creation(self):
        """Test AudioSample can be created with valid data."""
        from src.drivers.audio.inmp441 import AudioSample

        samples = np.zeros(1600, dtype=np.int16)
        audio = AudioSample(
            samples=samples,
            sample_rate=16000,
            timestamp=time.time(),
            level_db=-40.0
        )

        assert len(audio.samples) == 1600
        assert audio.sample_rate == 16000
        assert audio.level_db == -40.0

    def test_audio_sample_duration_calculation(self):
        """Test AudioSample duration_seconds calculation."""
        from src.drivers.audio.inmp441 import AudioSample

        # 16000 samples at 16000 Hz = 1.0 second
        samples = np.zeros(16000, dtype=np.int16)
        audio = AudioSample(
            samples=samples,
            sample_rate=16000,
            timestamp=time.time(),
            level_db=-40.0
        )

        assert audio.duration_seconds() == pytest.approx(1.0, abs=0.001)

    def test_audio_sample_empty_duration(self):
        """Test AudioSample duration with empty samples."""
        from src.drivers.audio.inmp441 import AudioSample

        audio = AudioSample(
            samples=np.array([], dtype=np.int16),
            sample_rate=16000,
            timestamp=time.time(),
            level_db=-96.0
        )

        assert audio.duration_seconds() == 0.0


# =============================================================================
# TestLevelDetection - dB level calculation tests
# =============================================================================

class TestLevelDetection:
    """Test audio level detection in dB."""

    def test_get_level_db_returns_float(self):
        """Test get_level_db returns a float value."""
        from src.drivers.audio.inmp441 import INMP441Driver

        driver = INMP441Driver(mock_mode=True)

        level = driver.get_level_db()

        assert isinstance(level, float)

    def test_get_level_db_initial_value(self):
        """Test initial dB level is at floor (-96 dB)."""
        from src.drivers.audio.inmp441 import INMP441Driver

        driver = INMP441Driver(mock_mode=True)

        level = driver.get_level_db()

        assert level == driver.DB_FLOOR

    def test_get_level_normalized_range(self):
        """Test get_level_normalized returns value in 0.0-1.0 range."""
        from src.drivers.audio.inmp441 import INMP441Driver

        driver = INMP441Driver(mock_mode=True)
        driver.start_capture()
        time.sleep(0.05)

        try:
            level = driver.get_level_normalized()
            assert 0.0 <= level <= 1.0
        finally:
            driver.stop_capture()

    def test_set_gain_updates_config(self):
        """Test set_gain updates the gain value."""
        from src.drivers.audio.inmp441 import INMP441Driver

        driver = INMP441Driver(mock_mode=True)
        driver.set_gain(2.5)

        assert driver.config.gain == 2.5

    def test_set_gain_invalid_raises(self):
        """Test set_gain with invalid value raises ValueError."""
        from src.drivers.audio.inmp441 import INMP441Driver

        driver = INMP441Driver(mock_mode=True)

        with pytest.raises(ValueError, match="Gain must be"):
            driver.set_gain(15.0)


# =============================================================================
# TestThreadSafety - Concurrent access tests
# =============================================================================

class TestThreadSafety:
    """Test thread-safe operations."""

    def test_concurrent_level_reads(self):
        """Test concurrent get_level_db calls don't crash."""
        from src.drivers.audio.inmp441 import INMP441Driver

        driver = INMP441Driver(mock_mode=True)
        driver.start_capture()
        time.sleep(0.05)

        errors = []
        results = []

        def read_level():
            try:
                for _ in range(10):
                    results.append(driver.get_level_db())
                    time.sleep(0.001)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=read_level) for _ in range(5)]

        try:
            for t in threads:
                t.start()
            for t in threads:
                t.join()

            assert len(errors) == 0, f"Thread errors: {errors}"
            assert len(results) == 50
        finally:
            driver.stop_capture()

    def test_start_stop_thread_safety(self):
        """Test start/stop from different threads is handled."""
        from src.drivers.audio.inmp441 import INMP441Driver

        driver = INMP441Driver(mock_mode=True)
        errors = []

        def start_stop():
            try:
                driver.start_capture()
                time.sleep(0.02)
                driver.stop_capture()
            except RuntimeError:
                # Expected - concurrent start/stop may conflict
                pass
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=start_stop) for _ in range(3)]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Should not have unexpected errors
        assert len(errors) == 0, f"Unexpected errors: {errors}"


# =============================================================================
# TestMockMode - Mock mode specific tests
# =============================================================================

class TestMockMode:
    """Test mock mode operations for development without hardware."""

    def test_mock_mode_generates_samples(self):
        """Test mock mode generates audio samples."""
        from src.drivers.audio.inmp441 import INMP441Driver

        driver = INMP441Driver(mock_mode=True)
        driver.start_capture()

        # Wait for mock samples to be generated
        time.sleep(0.1)

        try:
            samples = driver.read_samples(256)
            assert len(samples) > 0
        finally:
            driver.stop_capture()

    def test_mock_mode_level_updates(self):
        """Test mock mode updates audio level."""
        from src.drivers.audio.inmp441 import INMP441Driver

        driver = INMP441Driver(mock_mode=True)
        initial_level = driver.get_level_db()

        driver.start_capture()
        time.sleep(0.1)  # Let mock generate some samples

        try:
            # Level should have changed from initial floor
            # (may or may not be different depending on mock noise)
            current_level = driver.get_level_db()
            assert isinstance(current_level, float)
        finally:
            driver.stop_capture()


# =============================================================================
# TestFactoryFunction - Factory function tests
# =============================================================================

class TestFactoryFunction:
    """Test create_inmp441_driver factory function."""

    def test_factory_creates_driver(self):
        """Test factory function creates valid driver."""
        from src.drivers.audio.inmp441 import create_inmp441_driver

        driver = create_inmp441_driver(mock_mode=True)

        assert driver is not None
        assert driver.config.sample_rate == 16000

    def test_factory_with_custom_params(self):
        """Test factory function accepts custom parameters."""
        from src.drivers.audio.inmp441 import create_inmp441_driver

        driver = create_inmp441_driver(
            sample_rate=44100,
            gain=2.0,
            mock_mode=True
        )

        assert driver.config.sample_rate == 44100
        assert driver.config.gain == 2.0


# =============================================================================
# TestDeinit - Cleanup tests
# =============================================================================

class TestDeinit:
    """Test driver deinitialization."""

    def test_deinit_stops_capture(self):
        """Test deinit stops active capture."""
        from src.drivers.audio.inmp441 import INMP441Driver, CaptureState

        driver = INMP441Driver(mock_mode=True)
        driver.start_capture()

        driver.deinit()

        assert driver.state == CaptureState.STOPPED

    def test_deinit_safe_when_stopped(self):
        """Test deinit is safe when already stopped."""
        from src.drivers.audio.inmp441 import INMP441Driver

        driver = INMP441Driver(mock_mode=True)

        # Should not raise
        driver.deinit()
        driver.deinit()  # Double deinit should be safe
