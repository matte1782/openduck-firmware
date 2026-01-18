"""Unit tests for Audio Capture Pipeline.

Tests cover:
- AudioRingBuffer write/read/overflow operations
- VoiceActivityDetector threshold and probability
- AudioCapturePipeline start/stop/callbacks
- Latency verification (<50ms budget)
- AudioCaptureConfig validation

Total: 25 tests
"""

import pytest
import threading
import time
import math
import numpy as np
from unittest.mock import Mock, MagicMock, patch


# =============================================================================
# TestAudioCaptureConfig - Configuration validation tests
# =============================================================================

class TestAudioCaptureConfig:
    """Test AudioCaptureConfig validation."""

    def test_config_default_values(self):
        """Test AudioCaptureConfig has correct defaults."""
        from src.drivers.audio.audio_capture import AudioCaptureConfig

        config = AudioCaptureConfig()

        assert config.sample_rate == 16000
        assert config.bit_depth == 16
        assert config.channels == 1
        assert config.buffer_duration_ms == 1000
        assert config.chunk_size_ms == 20
        assert config.vad_threshold_db == -40.0
        assert config.vad_min_speech_ms == 100

    def test_config_samples_per_buffer(self):
        """Test samples_per_buffer property calculation."""
        from src.drivers.audio.audio_capture import AudioCaptureConfig

        config = AudioCaptureConfig(sample_rate=16000, buffer_duration_ms=1000)

        # 16000 * 1000 / 1000 = 16000 samples
        assert config.samples_per_buffer == 16000

    def test_config_samples_per_chunk(self):
        """Test samples_per_chunk property calculation."""
        from src.drivers.audio.audio_capture import AudioCaptureConfig

        config = AudioCaptureConfig(sample_rate=16000, chunk_size_ms=20)

        # 16000 * 20 / 1000 = 320 samples
        assert config.samples_per_chunk == 320

    @pytest.mark.parametrize("sample_rate", [0, -1, -16000])
    def test_config_invalid_sample_rate_raises(self, sample_rate):
        """Test invalid sample rates raise ValueError."""
        from src.drivers.audio.audio_capture import AudioCaptureConfig

        with pytest.raises(ValueError, match="sample_rate must be positive"):
            AudioCaptureConfig(sample_rate=sample_rate)

    @pytest.mark.parametrize("bit_depth", [4, 12, 48, 0])
    def test_config_invalid_bit_depth_raises(self, bit_depth):
        """Test invalid bit depths raise ValueError."""
        from src.drivers.audio.audio_capture import AudioCaptureConfig

        with pytest.raises(ValueError, match="bit_depth must be"):
            AudioCaptureConfig(bit_depth=bit_depth)

    def test_config_invalid_buffer_duration_raises(self):
        """Test buffer_duration_ms < 100 raises ValueError."""
        from src.drivers.audio.audio_capture import AudioCaptureConfig

        with pytest.raises(ValueError, match="buffer_duration_ms must be at least 100"):
            AudioCaptureConfig(buffer_duration_ms=50)

    def test_config_invalid_vad_threshold_raises(self):
        """Test positive vad_threshold_db raises ValueError."""
        from src.drivers.audio.audio_capture import AudioCaptureConfig

        with pytest.raises(ValueError, match="vad_threshold_db must be <= 0"):
            AudioCaptureConfig(vad_threshold_db=5.0)


# =============================================================================
# TestAudioRingBuffer - Ring buffer tests
# =============================================================================

class TestAudioRingBuffer:
    """Test AudioRingBuffer operations."""

    def test_buffer_creation(self, ring_buffer):
        """Test ring buffer initializes correctly."""
        assert ring_buffer.capacity == 4800
        assert ring_buffer.channels == 1

    def test_buffer_write_simple(self, ring_buffer):
        """Test writing samples to buffer."""
        samples = np.ones(1000, dtype=np.float32) * 0.5
        written = ring_buffer.write(samples)

        assert written == 1000
        assert ring_buffer.get_available() == 1000

    def test_buffer_read_returns_data(self, ring_buffer):
        """Test reading samples from buffer."""
        samples = np.random.randn(1000).astype(np.float32)
        ring_buffer.write(samples)

        read_data = ring_buffer.read(500)

        assert len(read_data) == 500
        assert read_data.shape[1] == 1  # Mono channel

    def test_buffer_read_returns_newest_samples(self, ring_buffer):
        """Test read returns most recent samples."""
        # Write samples with known values
        samples1 = np.ones(500, dtype=np.float32) * 0.1
        samples2 = np.ones(500, dtype=np.float32) * 0.9
        ring_buffer.write(samples1)
        ring_buffer.write(samples2)

        # Read last 500 samples - should be the 0.9 values
        read_data = ring_buffer.read(500)

        assert np.allclose(read_data.flatten(), 0.9, atol=0.01)

    def test_buffer_overflow_drops_oldest(self, ring_buffer):
        """Test overflow drops oldest samples."""
        # Write in chunks that eventually overflow
        # Buffer capacity is 4800, write 3000 twice = 6000 total
        samples1 = np.random.randn(3000).astype(np.float32)
        samples2 = np.random.randn(3000).astype(np.float32)
        ring_buffer.write(samples1)
        ring_buffer.write(samples2)  # This should cause overflow

        # Should only have capacity available
        assert ring_buffer.get_available() == ring_buffer.capacity
        assert ring_buffer.overflow_count > 0

    def test_buffer_wraparound(self, ring_buffer):
        """Test buffer handles wraparound correctly."""
        # Fill buffer
        samples1 = np.ones(4000, dtype=np.float32) * 0.5
        ring_buffer.write(samples1)

        # Write more to cause wraparound
        samples2 = np.ones(2000, dtype=np.float32) * 0.8
        ring_buffer.write(samples2)

        # Should still work correctly
        read_data = ring_buffer.read(1000)
        assert len(read_data) == 1000

    def test_buffer_clear(self, ring_buffer):
        """Test buffer clear removes all samples."""
        samples = np.random.randn(1000).astype(np.float32)
        ring_buffer.write(samples)

        ring_buffer.clear()

        assert ring_buffer.get_available() == 0

    def test_buffer_read_empty_returns_empty(self, ring_buffer):
        """Test reading from empty buffer returns empty array."""
        read_data = ring_buffer.read(100)

        assert len(read_data) == 0

    def test_buffer_invalid_capacity_raises(self):
        """Test invalid capacity raises ValueError."""
        from src.drivers.audio.audio_capture import AudioRingBuffer

        with pytest.raises(ValueError, match="capacity must be positive"):
            AudioRingBuffer(capacity=0)

    def test_buffer_invalid_channels_raises(self):
        """Test invalid channels raises ValueError."""
        from src.drivers.audio.audio_capture import AudioRingBuffer

        with pytest.raises(ValueError, match="channels must be at least 1"):
            AudioRingBuffer(capacity=1000, channels=0)

    def test_buffer_read_and_consume(self, ring_buffer):
        """Test read_and_consume removes samples."""
        samples = np.random.randn(1000).astype(np.float32)
        ring_buffer.write(samples)

        ring_buffer.read_and_consume(500)

        assert ring_buffer.get_available() == 500


# =============================================================================
# TestVoiceActivityDetector - VAD tests
# =============================================================================

class TestVoiceActivityDetector:
    """Test VoiceActivityDetector."""

    def test_vad_creation(self, vad):
        """Test VAD initializes correctly."""
        assert vad.threshold_db == -40.0
        assert vad._min_speech_ms == 100

    def test_vad_get_energy_db_silence(self, vad):
        """Test energy calculation for silence."""
        silence = np.zeros(320, dtype=np.float32)

        energy = vad.get_energy_db(silence)

        # Should be very low (near -100 dB floor)
        assert energy < -80

    def test_vad_get_energy_db_full_scale(self, vad):
        """Test energy calculation for full scale signal."""
        # Full scale sine wave (amplitude 1.0)
        t = np.arange(320) / 16000
        full_scale = np.sin(2 * np.pi * 440 * t).astype(np.float32)

        energy = vad.get_energy_db(full_scale)

        # RMS of sine wave is amplitude / sqrt(2), so ~-3 dB for amplitude 1.0
        assert -5 < energy < 0

    def test_vad_is_speech_below_threshold(self, vad):
        """Test is_speech returns False for quiet signal."""
        quiet = np.random.randn(320).astype(np.float32) * 0.001

        # Need to call multiple times to simulate duration
        for _ in range(10):
            result = vad.is_speech(quiet)

        # Signal is below threshold
        assert result is False

    def test_vad_is_speech_above_threshold(self, vad):
        """Test is_speech returns True for loud signal after min duration."""
        # Loud signal (above -40 dB)
        loud = np.random.randn(320).astype(np.float32) * 0.2

        # Call multiple times to exceed min_speech_ms
        start = time.monotonic()
        while time.monotonic() - start < 0.15:  # > 100ms
            result = vad.is_speech(loud)
            time.sleep(0.01)

        assert result is True

    def test_vad_probability_range(self, vad):
        """Test update_probability returns value in 0-1 range."""
        samples = np.random.randn(320).astype(np.float32) * 0.1

        prob = vad.update_probability(samples)

        assert 0.0 <= prob <= 1.0

    def test_vad_reset_clears_state(self, vad):
        """Test reset clears VAD state."""
        loud = np.random.randn(320).astype(np.float32) * 0.2

        # Build up state
        for _ in range(20):
            vad.is_speech(loud)
            time.sleep(0.01)

        vad.reset()

        assert vad._is_speaking is False
        assert vad._speech_start_time is None

    def test_vad_threshold_setter(self, vad):
        """Test threshold_db setter validates value."""
        vad.threshold_db = -50.0
        assert vad.threshold_db == -50.0

        with pytest.raises(ValueError, match="threshold_db must be <= 0"):
            vad.threshold_db = 5.0


# =============================================================================
# TestAudioCapturePipeline - Pipeline tests (mocked sounddevice)
# =============================================================================

class TestAudioCapturePipeline:
    """Test AudioCapturePipeline (with mocked sounddevice)."""

    def test_pipeline_creation(self, capture_config):
        """Test pipeline creates with config."""
        with patch.dict('sys.modules', {'sounddevice': MagicMock()}):
            from src.drivers.audio.audio_capture import AudioCapturePipeline

            pipeline = AudioCapturePipeline(capture_config)

            assert pipeline.config == capture_config
            assert pipeline.vad is not None

    def test_pipeline_state_stopped_initially(self, capture_config):
        """Test pipeline state is STOPPED initially."""
        with patch.dict('sys.modules', {'sounddevice': MagicMock()}):
            from src.drivers.audio.audio_capture import (
                AudioCapturePipeline, AudioCaptureState
            )

            pipeline = AudioCapturePipeline(capture_config)

            assert pipeline.state == AudioCaptureState.STOPPED

    def test_pipeline_get_audio_validates_duration(self, capture_config):
        """Test get_audio validates duration_ms parameter."""
        with patch.dict('sys.modules', {'sounddevice': MagicMock()}):
            from src.drivers.audio.audio_capture import AudioCapturePipeline

            pipeline = AudioCapturePipeline(capture_config)

            with pytest.raises(ValueError, match="duration_ms must be positive"):
                pipeline.get_audio(duration_ms=0)

    def test_pipeline_add_callback(self, capture_config):
        """Test callback can be added."""
        with patch.dict('sys.modules', {'sounddevice': MagicMock()}):
            from src.drivers.audio.audio_capture import AudioCapturePipeline

            pipeline = AudioCapturePipeline(capture_config)
            callback = Mock()

            pipeline.add_callback(callback)

            assert callback in pipeline._callbacks

    def test_pipeline_remove_callback(self, capture_config):
        """Test callback can be removed."""
        with patch.dict('sys.modules', {'sounddevice': MagicMock()}):
            from src.drivers.audio.audio_capture import AudioCapturePipeline

            pipeline = AudioCapturePipeline(capture_config)
            callback = Mock()

            pipeline.add_callback(callback)
            pipeline.remove_callback(callback)

            assert callback not in pipeline._callbacks

    def test_pipeline_clear_buffer(self, capture_config):
        """Test clear_buffer clears ring buffer."""
        with patch.dict('sys.modules', {'sounddevice': MagicMock()}):
            from src.drivers.audio.audio_capture import AudioCapturePipeline

            pipeline = AudioCapturePipeline(capture_config)

            # Write some data directly to ring buffer
            samples = np.random.randn(1000).astype(np.float32)
            pipeline._ring_buffer.write(samples)

            pipeline.clear_buffer()

            assert pipeline._ring_buffer.get_available() == 0

    def test_pipeline_get_level_db_returns_float(self, capture_config):
        """Test get_level_db returns float."""
        with patch.dict('sys.modules', {'sounddevice': MagicMock()}):
            from src.drivers.audio.audio_capture import AudioCapturePipeline

            pipeline = AudioCapturePipeline(capture_config)

            level = pipeline.get_level_db()

            assert isinstance(level, float)


# =============================================================================
# TestLatency - Latency verification tests
# =============================================================================

class TestLatency:
    """Test latency requirements (<50ms budget)."""

    def test_ring_buffer_write_latency(self, ring_buffer, latency_timer):
        """Test ring buffer write completes in <5ms."""
        samples = np.random.randn(1600).astype(np.float32)  # 100ms of audio

        with latency_timer() as timer:
            for _ in range(10):  # 10 writes
                ring_buffer.write(samples)

        # 10 writes should complete in <50ms total (<5ms each)
        timer.assert_under(50.0, "Ring buffer write latency")

    def test_ring_buffer_read_latency(self, ring_buffer, latency_timer):
        """Test ring buffer read completes in <5ms."""
        # Pre-fill buffer
        samples = np.random.randn(4000).astype(np.float32)
        ring_buffer.write(samples)

        with latency_timer() as timer:
            for _ in range(10):
                ring_buffer.read(320)

        timer.assert_under(50.0, "Ring buffer read latency")

    def test_vad_processing_latency(self, vad, latency_timer):
        """Test VAD processing completes in <10ms per chunk."""
        samples = np.random.randn(320).astype(np.float32)

        with latency_timer() as timer:
            for _ in range(100):  # 100 VAD checks
                vad.is_speech(samples)

        # 100 checks should complete in <1000ms (<10ms each)
        timer.assert_under(1000.0, "VAD processing latency")


# =============================================================================
# TestAudioSample - AudioSample dataclass tests
# =============================================================================

class TestAudioSample:
    """Test AudioSample dataclass."""

    def test_audio_sample_creation(self):
        """Test AudioSample can be created."""
        from src.drivers.audio.audio_capture import AudioSample

        samples = np.random.randn(1600).astype(np.float32)
        audio = AudioSample(
            samples=samples,
            sample_rate=16000,
            channels=1,
            timestamp=time.monotonic(),
            duration_ms=100.0
        )

        assert len(audio.samples) == 1600
        assert audio.sample_rate == 16000
        assert audio.channels == 1
        assert audio.duration_ms == 100.0

    def test_audio_sample_duration_auto_calculation(self):
        """Test AudioSample calculates duration if not provided."""
        from src.drivers.audio.audio_capture import AudioSample

        # 1600 samples at 16000 Hz = 100ms
        samples = np.random.randn(1600).astype(np.float32)
        audio = AudioSample(
            samples=samples,
            sample_rate=16000,
            channels=1,
            timestamp=time.monotonic(),
            duration_ms=0  # Will be calculated
        )

        assert audio.duration_ms == pytest.approx(100.0, abs=0.1)


# =============================================================================
# TestConvenienceFunction - Factory function tests
# =============================================================================

class TestConvenienceFunction:
    """Test create_capture_pipeline factory function."""

    def test_factory_creates_pipeline(self):
        """Test factory function creates valid pipeline."""
        with patch.dict('sys.modules', {'sounddevice': MagicMock()}):
            from src.drivers.audio.audio_capture import create_capture_pipeline

            pipeline = create_capture_pipeline(
                sample_rate=16000,
                buffer_duration_ms=2000,
                vad_threshold_db=-35.0
            )

            assert pipeline is not None
            assert pipeline.config.sample_rate == 16000
            assert pipeline.config.buffer_duration_ms == 2000
            assert pipeline.config.vad_threshold_db == -35.0


# =============================================================================
# TestAudioCaptureState - State enum tests
# =============================================================================

class TestAudioCaptureState:
    """Test AudioCaptureState enumeration."""

    def test_state_stopped_exists(self):
        """Test STOPPED state exists."""
        from src.drivers.audio.audio_capture import AudioCaptureState

        assert hasattr(AudioCaptureState, 'STOPPED')

    def test_state_running_exists(self):
        """Test RUNNING state exists."""
        from src.drivers.audio.audio_capture import AudioCaptureState

        assert hasattr(AudioCaptureState, 'RUNNING')

    def test_state_error_exists(self):
        """Test ERROR state exists."""
        from src.drivers.audio.audio_capture import AudioCaptureState

        assert hasattr(AudioCaptureState, 'ERROR')
