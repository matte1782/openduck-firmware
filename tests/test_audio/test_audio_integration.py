#!/usr/bin/env python3
"""
Audio Full Loop Integration Tests for OpenDuck Mini V3

Tests the complete audio pipeline for hardware validation:
- INMP441 microphone capture
- AudioCapturePipeline with VAD
- TTS engine processing
- MAX98357A speaker output

All tests use mock I2S bus for development machine testing.
Ready for hardware validation when components are soldered.

Run with: pytest tests/test_audio/test_audio_integration.py -v
Coverage: pytest tests/test_audio --cov=src.drivers.audio --cov-report=term-missing

Author: Boston Dynamics Audio Integration Engineer
Created: 22 January 2026
"""

import time
import threading
from typing import List, Optional
from unittest.mock import Mock, patch, MagicMock

import pytest


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def audio_config():
    """Standard audio configuration for testing."""
    return {
        'sample_rate': 16000,
        'channels': 1,
        'bits_per_sample': 16,
        'buffer_size': 1024,
    }


# =============================================================================
# Component Import Tests
# =============================================================================

class TestAudioComponentImports:
    """Verify all audio components can be imported."""

    def test_import_inmp441(self):
        """INMP441 driver can be imported."""
        from src.drivers.audio import INMP441Driver, INMP441Config
        assert INMP441Driver is not None
        assert INMP441Config is not None

    def test_import_audio_capture(self):
        """AudioCapturePipeline can be imported."""
        from src.drivers.audio import (
            AudioCapturePipeline,
            AudioCaptureConfig,
            VoiceActivityDetector,
        )
        assert AudioCapturePipeline is not None
        assert AudioCaptureConfig is not None
        assert VoiceActivityDetector is not None

    def test_import_tts_engine(self):
        """TTS engine can be imported."""
        from src.drivers.audio import (
            TTSEngine,
            TTSSpeaker,
            TTSVoiceConfig,
        )
        assert TTSEngine is not None
        assert TTSSpeaker is not None
        assert TTSVoiceConfig is not None

    def test_import_max98357a(self):
        """MAX98357A driver can be imported."""
        from src.drivers.audio import MAX98357ADriver, MAX98357AConfig
        assert MAX98357ADriver is not None
        assert MAX98357AConfig is not None

    def test_import_i2s_bus(self):
        """I2S bus manager can be imported."""
        from src.drivers.audio import (
            I2SBusManager,
            get_i2s_bus_manager,
            I2SDirection,
        )
        assert I2SBusManager is not None
        assert get_i2s_bus_manager is not None
        assert I2SDirection is not None


# =============================================================================
# Full Loop Integration Tests (Mock Mode)
# =============================================================================

class TestAudioFullLoopIntegration:
    """Integration tests for full audio pipeline using mock mode."""

    def test_mic_to_vad_pipeline(self):
        """Test microphone capture to VAD detection pipeline."""
        from src.drivers.audio import (
            INMP441Driver,
            INMP441Config,
            VoiceActivityDetector,
        )

        # Create mic driver in mock mode
        config = INMP441Config(sample_rate=16000, bit_depth=16)
        mic = INMP441Driver(config=config, mock_mode=True)

        # Create VAD
        vad = VoiceActivityDetector(threshold_db=-35.0)

        # Start capture
        mic.start_capture()

        # Read samples (no timeout param - uses internal buffering)
        samples = mic.read_samples(num_samples=1024)

        # Should get some samples (mock data)
        assert samples is not None
        assert len(samples) > 0

        # VAD should be able to process the samples
        is_speech = vad.is_speech(samples)
        assert isinstance(is_speech, bool)

        # Clean up
        mic.stop_capture()

    def test_tts_engine_synthesis(self):
        """Test TTS engine can synthesize text."""
        from src.drivers.audio import TTSEngine, TTSBackend

        # Create TTS engine with mock backend
        engine = TTSEngine(backend=TTSBackend.MOCK)

        # Synthesize text
        audio_bytes = engine.synthesize("Hello, I am OpenDuck")

        # Should get audio data
        assert audio_bytes is not None
        assert len(audio_bytes) > 0

    def test_full_loop_components_initialize(self):
        """Test all audio components can initialize together."""
        from src.drivers.audio import (
            INMP441Driver,
            INMP441Config,
            VoiceActivityDetector,
            TTSEngine,
            TTSBackend,
            MAX98357ADriver,
            MAX98357AConfig,
        )

        # Initialize all components
        mic_config = INMP441Config(sample_rate=16000, bit_depth=16)
        mic = INMP441Driver(config=mic_config, mock_mode=True)

        vad = VoiceActivityDetector(threshold_db=-35.0)

        tts = TTSEngine(backend=TTSBackend.MOCK)

        speaker_config = MAX98357AConfig(sample_rate=16000)
        speaker = MAX98357ADriver(config=speaker_config)

        # All components should initialize without error
        assert mic is not None
        assert vad is not None
        assert tts is not None
        assert speaker is not None


# =============================================================================
# Sample Rate Consistency Tests
# =============================================================================

class TestSampleRateConsistency:
    """Tests to ensure 16kHz sample rate throughout pipeline."""

    def test_mic_sample_rate(self):
        """Microphone uses 16kHz sample rate."""
        from src.drivers.audio import INMP441Driver, INMP441Config

        config = INMP441Config(sample_rate=16000)
        mic = INMP441Driver(config=config, mock_mode=True)

        assert mic.config.sample_rate == 16000

    def test_speaker_sample_rate(self):
        """Speaker can be configured with 16kHz sample rate."""
        from src.drivers.audio import MAX98357AConfig

        config = MAX98357AConfig(sample_rate=16000)
        assert config.sample_rate == 16000


# =============================================================================
# Latency Tests
# =============================================================================

class TestAudioLatency:
    """Tests for audio pipeline latency."""

    def test_capture_latency(self):
        """Audio capture completes quickly in mock mode."""
        from src.drivers.audio import INMP441Driver, INMP441Config

        config = INMP441Config(sample_rate=16000)
        mic = INMP441Driver(config=config, mock_mode=True)

        mic.start_capture()

        start = time.perf_counter()
        samples = mic.read_samples(num_samples=1024)
        elapsed_ms = (time.perf_counter() - start) * 1000

        mic.stop_capture()

        # Mock mode should be very fast
        assert elapsed_ms < 500, f"Capture took {elapsed_ms:.2f}ms"
        assert samples is not None

    def test_tts_synthesis_reasonable_time(self):
        """TTS synthesis completes in reasonable time."""
        from src.drivers.audio import TTSEngine, TTSBackend

        tts = TTSEngine(backend=TTSBackend.MOCK)

        start = time.perf_counter()
        audio = tts.synthesize("Test message")
        elapsed_ms = (time.perf_counter() - start) * 1000

        # Mock mode should be very fast
        assert elapsed_ms < 500, f"TTS took {elapsed_ms:.2f}ms"


# =============================================================================
# Thread Safety Tests
# =============================================================================

class TestAudioThreadSafety:
    """Tests for thread-safe audio operations."""

    def test_concurrent_mic_capture(self):
        """Microphone handles concurrent read requests."""
        from src.drivers.audio import INMP441Driver, INMP441Config

        config = INMP441Config(sample_rate=16000)
        mic = INMP441Driver(config=config, mock_mode=True)

        mic.start_capture()

        results = []
        errors = []

        def read_samples():
            try:
                samples = mic.read_samples(num_samples=512)
                results.append(samples is not None)
            except Exception as e:
                errors.append(str(e))

        # Launch multiple concurrent reads
        threads = [threading.Thread(target=read_samples) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=2.0)

        # Verify all threads completed (didn't deadlock)
        for t in threads:
            assert not t.is_alive(), "Thread did not complete in time - possible deadlock"

        mic.stop_capture()

        # Should handle without crashing
        assert len(errors) == 0 or all("empty" in e.lower() or "timeout" in e.lower() for e in errors), \
            f"Unexpected errors: {errors}"


# =============================================================================
# Hardware Validation Preparation Tests
# =============================================================================

class TestHardwareValidationPrep:
    """Tests to prepare for hardware validation."""

    def test_inmp441_driver_ready(self):
        """INMP441 driver is ready for hardware testing."""
        from src.drivers.audio import INMP441Driver, INMP441Config, CaptureState

        config = INMP441Config(
            sample_rate=16000,
            bit_depth=16,
        )
        mic = INMP441Driver(config=config, mock_mode=True)

        # Verify state transitions
        assert mic.state == CaptureState.STOPPED

        mic.start_capture()
        assert mic.state == CaptureState.CAPTURING

        mic.stop_capture()
        assert mic.state == CaptureState.STOPPED

    def test_max98357a_config_ready(self):
        """MAX98357A configuration is ready for hardware testing."""
        from src.drivers.audio import MAX98357AConfig

        config = MAX98357AConfig(
            sample_rate=16000,
            volume=0.8,
        )

        # Config should have correct values
        assert config.sample_rate == 16000
        assert config.volume == 0.8

    def test_tts_engine_ready(self):
        """TTS engine is ready for hardware testing."""
        from src.drivers.audio import TTSEngine, TTSBackend

        tts = TTSEngine(backend=TTSBackend.MOCK)

        # Should be able to synthesize
        audio = tts.synthesize("Hardware test")
        assert audio is not None
        assert len(audio) > 0

    def test_vad_ready(self):
        """Voice Activity Detector is ready for hardware testing."""
        from src.drivers.audio import VoiceActivityDetector
        import numpy as np

        vad = VoiceActivityDetector(threshold_db=-35.0)

        # Create mock audio data
        mock_samples = np.zeros(1024, dtype=np.int16)

        # VAD should be able to process
        is_speech = vad.is_speech(mock_samples)
        assert isinstance(is_speech, bool)
        # Silent samples should not be detected as speech
        assert is_speech is False


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
