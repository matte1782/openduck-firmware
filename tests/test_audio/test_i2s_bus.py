"""Unit tests for I2S Bus Manager.

Tests cover:
- I2SConfig validation and properties
- I2SBusManager singleton pattern
- Thread-safe bus access with context manager
- MockI2SStream read/write operations
- Pin configuration

Total: 18 tests
"""

import pytest
import threading
import time
from unittest.mock import Mock, patch


# =============================================================================
# TestI2SConfig - Configuration validation tests
# =============================================================================

class TestI2SConfig:
    """Test I2SConfig dataclass validation and properties."""

    def test_config_default_values(self):
        """Test I2SConfig initializes with correct defaults."""
        from src.drivers.audio.i2s_bus import I2SConfig

        config = I2SConfig()

        assert config.sample_rate == 16000
        assert config.bit_depth == 16
        assert config.channels == 1
        assert config.buffer_size == 1024

    def test_config_custom_values(self):
        """Test I2SConfig accepts valid custom values."""
        from src.drivers.audio.i2s_bus import I2SConfig

        config = I2SConfig(
            sample_rate=44100,
            bit_depth=32,
            channels=2,
            buffer_size=2048
        )

        assert config.sample_rate == 44100
        assert config.bit_depth == 32
        assert config.channels == 2
        assert config.buffer_size == 2048

    @pytest.mark.parametrize("sample_rate", [8000, 22050, 48000, 96000])
    def test_config_invalid_sample_rate_raises(self, sample_rate):
        """Test I2SConfig rejects invalid sample rates."""
        from src.drivers.audio.i2s_bus import I2SConfig

        with pytest.raises(ValueError, match="sample_rate must be one of"):
            I2SConfig(sample_rate=sample_rate)

    @pytest.mark.parametrize("bit_depth", [8, 24, 64])
    def test_config_invalid_bit_depth_raises(self, bit_depth):
        """Test I2SConfig rejects invalid bit depths."""
        from src.drivers.audio.i2s_bus import I2SConfig

        with pytest.raises(ValueError, match="bit_depth must be one of"):
            I2SConfig(bit_depth=bit_depth)

    @pytest.mark.parametrize("channels", [0, 3, 4, -1])
    def test_config_invalid_channels_raises(self, channels):
        """Test I2SConfig rejects invalid channel counts."""
        from src.drivers.audio.i2s_bus import I2SConfig

        with pytest.raises(ValueError, match="channels must be one of"):
            I2SConfig(channels=channels)

    @pytest.mark.parametrize("buffer_size", [32, 63, 8193, 10000])
    def test_config_invalid_buffer_size_raises(self, buffer_size):
        """Test I2SConfig rejects invalid buffer sizes."""
        from src.drivers.audio.i2s_bus import I2SConfig

        with pytest.raises(ValueError, match="buffer_size must be 64-8192"):
            I2SConfig(buffer_size=buffer_size)

    def test_config_buffer_duration_ms_calculation(self):
        """Test buffer_duration_ms property calculates correctly."""
        from src.drivers.audio.i2s_bus import I2SConfig

        config = I2SConfig(sample_rate=16000, buffer_size=1024)

        # 1024 / 16000 * 1000 = 64.0ms
        assert config.buffer_duration_ms == 64.0

    def test_config_bytes_per_frame_mono_16bit(self):
        """Test bytes_per_frame for mono 16-bit."""
        from src.drivers.audio.i2s_bus import I2SConfig

        config = I2SConfig(bit_depth=16, channels=1)

        # 16 bits = 2 bytes, 1 channel = 2 bytes per frame
        assert config.bytes_per_frame == 2

    def test_config_bytes_per_frame_stereo_32bit(self):
        """Test bytes_per_frame for stereo 32-bit."""
        from src.drivers.audio.i2s_bus import I2SConfig

        config = I2SConfig(sample_rate=44100, bit_depth=32, channels=2)

        # 32 bits = 4 bytes, 2 channels = 8 bytes per frame
        assert config.bytes_per_frame == 8

    def test_config_buffer_bytes_calculation(self):
        """Test buffer_bytes property calculates correctly."""
        from src.drivers.audio.i2s_bus import I2SConfig

        config = I2SConfig(bit_depth=16, channels=1, buffer_size=1024)

        # 1024 frames * 2 bytes/frame = 2048 bytes
        assert config.buffer_bytes == 2048

    def test_config_is_frozen(self):
        """Test I2SConfig is immutable (frozen dataclass)."""
        from src.drivers.audio.i2s_bus import I2SConfig

        config = I2SConfig()

        with pytest.raises(AttributeError):
            config.sample_rate = 44100


# =============================================================================
# TestI2SBusManager - Singleton and thread-safety tests
# =============================================================================

class TestI2SBusManager:
    """Test I2SBusManager singleton pattern and thread safety."""

    def test_singleton_same_instance(self, reset_i2s_singleton):
        """Verify only one I2SBusManager instance exists."""
        from src.drivers.audio.i2s_bus import I2SBusManager

        manager1 = I2SBusManager.get_instance(force_mock=True)
        manager2 = I2SBusManager.get_instance(force_mock=True)

        assert manager1 is manager2, "Singleton pattern violated"

    def test_singleton_thread_safe(self, reset_i2s_singleton):
        """Verify singleton is thread-safe during concurrent init."""
        from src.drivers.audio.i2s_bus import I2SBusManager

        instances = []

        def get_manager():
            instances.append(I2SBusManager.get_instance(force_mock=True))

        threads = [threading.Thread(target=get_manager) for _ in range(10)]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All instances should be identical
        assert len(set(id(inst) for inst in instances)) == 1

    def test_manager_mock_mode_property(self, i2s_manager):
        """Test mock_mode property returns True in test environment."""
        assert i2s_manager.mock_mode is True

    def test_manager_pin_config_property(self, i2s_manager):
        """Test pin_config returns default pin configuration."""
        from src.drivers.audio.i2s_bus import I2SPinConfig

        pin_config = i2s_manager.pin_config

        assert isinstance(pin_config, I2SPinConfig)
        assert pin_config.bck == 18
        assert pin_config.ws == 19
        assert pin_config.data_in == 20
        assert pin_config.data_out == 21

    def test_manager_context_manager_acquires_lock(self, i2s_manager):
        """Test context manager acquires and releases bus lock."""
        from src.drivers.audio.i2s_bus import I2SConfig, I2SDirection

        config = I2SConfig()

        assert not i2s_manager.is_locked()

        with i2s_manager.acquire_bus(I2SDirection.INPUT, config) as stream:
            assert i2s_manager.is_locked()
            assert stream is not None

        assert not i2s_manager.is_locked()

    def test_manager_context_manager_releases_on_exception(self, i2s_manager):
        """Test lock is released even if exception occurs."""
        from src.drivers.audio.i2s_bus import I2SConfig, I2SDirection

        config = I2SConfig()

        try:
            with i2s_manager.acquire_bus(I2SDirection.INPUT, config) as stream:
                assert i2s_manager.is_locked()
                raise RuntimeError("Simulated error")
        except RuntimeError:
            pass

        assert not i2s_manager.is_locked()

    def test_manager_get_active_streams(self, i2s_manager):
        """Test get_active_streams returns current streams."""
        from src.drivers.audio.i2s_bus import I2SConfig, I2SDirection

        config = I2SConfig()

        assert i2s_manager.get_active_streams() == {}

        with i2s_manager.acquire_bus(I2SDirection.INPUT, config):
            active = i2s_manager.get_active_streams()
            assert I2SDirection.INPUT in active
            assert active[I2SDirection.INPUT] == config

    def test_manager_reset_clears_state(self, reset_i2s_singleton):
        """Test reset() clears singleton and state."""
        from src.drivers.audio.i2s_bus import I2SBusManager

        manager1 = I2SBusManager.get_instance(force_mock=True)
        I2SBusManager.reset()
        manager2 = I2SBusManager.get_instance(force_mock=True)

        # Should be different instances after reset
        assert manager1 is not manager2


# =============================================================================
# TestMockI2SStream - Mock stream operation tests
# =============================================================================

class TestMockI2SStream:
    """Test MockI2SStream read/write operations."""

    def test_mock_stream_read_returns_bytes(self, i2s_manager):
        """Test mock stream read returns correct byte count."""
        from src.drivers.audio.i2s_bus import I2SConfig, I2SDirection

        config = I2SConfig(bit_depth=16, channels=1, buffer_size=1024)

        with i2s_manager.acquire_bus(I2SDirection.INPUT, config) as stream:
            data = stream.read(512)

            # 512 frames * 2 bytes/frame = 1024 bytes
            assert len(data) == 1024
            assert isinstance(data, bytes)

    def test_mock_stream_write_returns_frame_count(self, i2s_manager):
        """Test mock stream write returns frames written."""
        from src.drivers.audio.i2s_bus import I2SConfig, I2SDirection

        config = I2SConfig(bit_depth=16, channels=1)

        with i2s_manager.acquire_bus(I2SDirection.OUTPUT, config) as stream:
            # Write 1024 bytes = 512 frames for 16-bit mono
            frames = stream.write(bytes(1024))

            assert frames == 512

    def test_mock_stream_read_from_closed_raises(self, i2s_manager):
        """Test reading from closed stream raises RuntimeError."""
        from src.drivers.audio.i2s_bus import I2SConfig, I2SDirection, MockI2SStream

        config = I2SConfig()
        stream = MockI2SStream(config, I2SDirection.INPUT)
        stream.close()

        with pytest.raises(RuntimeError, match="Cannot read from closed stream"):
            stream.read(1024)

    def test_mock_stream_write_to_closed_raises(self, i2s_manager):
        """Test writing to closed stream raises RuntimeError."""
        from src.drivers.audio.i2s_bus import I2SConfig, I2SDirection, MockI2SStream

        config = I2SConfig()
        stream = MockI2SStream(config, I2SDirection.OUTPUT)
        stream.close()

        with pytest.raises(RuntimeError, match="Cannot write to closed stream"):
            stream.write(bytes(1024))

    def test_mock_stream_read_from_output_only_raises(self):
        """Test reading from OUTPUT-only stream raises ValueError."""
        from src.drivers.audio.i2s_bus import I2SConfig, I2SDirection, MockI2SStream

        config = I2SConfig()
        stream = MockI2SStream(config, I2SDirection.OUTPUT)

        with pytest.raises(ValueError, match="Cannot read from OUTPUT-only stream"):
            stream.read(1024)

    def test_mock_stream_write_to_input_only_raises(self):
        """Test writing to INPUT-only stream raises ValueError."""
        from src.drivers.audio.i2s_bus import I2SConfig, I2SDirection, MockI2SStream

        config = I2SConfig()
        stream = MockI2SStream(config, I2SDirection.INPUT)

        with pytest.raises(ValueError, match="Cannot write to INPUT-only stream"):
            stream.write(bytes(1024))


# =============================================================================
# TestI2SDirection - Direction enum tests
# =============================================================================

class TestI2SDirection:
    """Test I2SDirection enumeration."""

    def test_direction_input_exists(self):
        """Test INPUT direction exists."""
        from src.drivers.audio.i2s_bus import I2SDirection

        assert hasattr(I2SDirection, 'INPUT')

    def test_direction_output_exists(self):
        """Test OUTPUT direction exists."""
        from src.drivers.audio.i2s_bus import I2SDirection

        assert hasattr(I2SDirection, 'OUTPUT')

    def test_direction_duplex_exists(self):
        """Test DUPLEX direction exists."""
        from src.drivers.audio.i2s_bus import I2SDirection

        assert hasattr(I2SDirection, 'DUPLEX')


# =============================================================================
# TestI2SPinConfig - Pin configuration tests
# =============================================================================

class TestI2SPinConfig:
    """Test I2SPinConfig dataclass."""

    def test_pin_config_defaults(self):
        """Test I2SPinConfig has correct default pins."""
        from src.drivers.audio.i2s_bus import I2SPinConfig

        config = I2SPinConfig()

        assert config.bck == 18
        assert config.ws == 19
        assert config.data_in == 20
        assert config.data_out == 21

    def test_pin_config_custom_pins(self):
        """Test I2SPinConfig accepts custom pins."""
        from src.drivers.audio.i2s_bus import I2SPinConfig

        config = I2SPinConfig(bck=12, ws=13, data_in=14, data_out=15)

        assert config.bck == 12
        assert config.ws == 13
        assert config.data_in == 14
        assert config.data_out == 15


# =============================================================================
# TestPreDefinedConfigs - Pre-defined configuration tests
# =============================================================================

class TestPreDefinedConfigs:
    """Test pre-defined I2S configurations."""

    def test_mic_config_16khz(self):
        """Test MIC_CONFIG_16KHZ is configured for speech."""
        from src.drivers.audio.i2s_bus import MIC_CONFIG_16KHZ

        assert MIC_CONFIG_16KHZ.sample_rate == 16000
        assert MIC_CONFIG_16KHZ.bit_depth == 16
        assert MIC_CONFIG_16KHZ.channels == 1
        assert MIC_CONFIG_16KHZ.buffer_size == 1024

    def test_speaker_config_44khz(self):
        """Test SPEAKER_CONFIG_44KHZ is configured for playback."""
        from src.drivers.audio.i2s_bus import SPEAKER_CONFIG_44KHZ

        assert SPEAKER_CONFIG_44KHZ.sample_rate == 44100
        assert SPEAKER_CONFIG_44KHZ.bit_depth == 16
        assert SPEAKER_CONFIG_44KHZ.channels == 2
        assert SPEAKER_CONFIG_44KHZ.buffer_size == 2048

    def test_speaker_config_16khz(self):
        """Test SPEAKER_CONFIG_16KHZ is configured for TTS."""
        from src.drivers.audio.i2s_bus import SPEAKER_CONFIG_16KHZ

        assert SPEAKER_CONFIG_16KHZ.sample_rate == 16000
        assert SPEAKER_CONFIG_16KHZ.bit_depth == 16
        assert SPEAKER_CONFIG_16KHZ.channels == 1


# =============================================================================
# TestConvenienceFunction - Module-level function tests
# =============================================================================

class TestConvenienceFunction:
    """Test get_i2s_bus_manager convenience function."""

    def test_get_i2s_bus_manager_returns_singleton(self, reset_i2s_singleton):
        """Test get_i2s_bus_manager returns singleton instance."""
        from src.drivers.audio.i2s_bus import get_i2s_bus_manager, I2SBusManager

        manager1 = get_i2s_bus_manager(force_mock=True)
        manager2 = I2SBusManager.get_instance(force_mock=True)

        assert manager1 is manager2
