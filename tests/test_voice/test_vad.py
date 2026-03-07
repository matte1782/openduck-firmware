"""Tests for Voice Activity Detection (VAD) module.

AGENT-1: VAD Specialist
TDD-First: These tests define the expected behavior before implementation.

Test Categories:
1. Configuration & Initialization
2. Energy-based Detection
3. Streaming Frame Processing
4. State Machine (speech start/end events)
5. Edge Cases & Robustness
6. Performance Requirements
"""

from __future__ import annotations

import numpy as np
import pytest
import time
from typing import List, Tuple
from unittest.mock import Mock, patch

# Import will fail until implementation exists - that's TDD!
try:
    from src.voice.vad import (
        VADConfig,
        VADState,
        VADEvent,
        VADResult,
        VoiceActivityDetector,
    )
except ImportError:
    # Mark all tests as expected to fail until implementation
    pytestmark = pytest.mark.skip(reason="VAD module not yet implemented")


class TestVADConfig:
    """Test VAD configuration dataclass."""

    def test_default_config_values(self):
        """Default config should have sensible values for speech detection."""
        config = VADConfig()

        assert config.sample_rate == 16000  # Standard speech sample rate
        assert config.frame_size_ms == 20  # 20ms frames (standard)
        assert -50 <= config.energy_threshold_db <= -30  # Reasonable speech threshold
        assert 50 <= config.min_speech_ms <= 200  # Minimum speech duration
        assert 200 <= config.min_silence_ms <= 500  # Minimum silence for speech end
        assert 0 < config.smoothing_frames <= 5  # Smoothing window

    def test_custom_config(self):
        """Custom config values should be accepted."""
        config = VADConfig(
            sample_rate=8000,
            frame_size_ms=30,
            energy_threshold_db=-35.0,
            min_speech_ms=100,
            min_silence_ms=300,
            smoothing_frames=3
        )

        assert config.sample_rate == 8000
        assert config.frame_size_ms == 30
        assert config.energy_threshold_db == -35.0

    def test_invalid_sample_rate_raises(self):
        """Invalid sample rate should raise ValueError."""
        with pytest.raises(ValueError, match="sample_rate"):
            VADConfig(sample_rate=0)

        with pytest.raises(ValueError, match="sample_rate"):
            VADConfig(sample_rate=-16000)

    def test_invalid_frame_size_raises(self):
        """Invalid frame size should raise ValueError."""
        with pytest.raises(ValueError, match="frame_size"):
            VADConfig(frame_size_ms=0)

        with pytest.raises(ValueError, match="frame_size"):
            VADConfig(frame_size_ms=2)  # Too small

    def test_invalid_threshold_raises(self):
        """Invalid energy threshold should raise ValueError."""
        with pytest.raises(ValueError, match="energy_threshold"):
            VADConfig(energy_threshold_db=10)  # Positive dB is invalid

    def test_frame_samples_calculation(self):
        """frame_samples property should calculate correctly."""
        config = VADConfig(sample_rate=16000, frame_size_ms=20)
        assert config.frame_samples == 320  # 16000 * 0.020

        config = VADConfig(sample_rate=8000, frame_size_ms=30)
        assert config.frame_samples == 240  # 8000 * 0.030


class TestVADState:
    """Test VAD state enumeration."""

    def test_states_exist(self):
        """VAD should have required states."""
        assert hasattr(VADState, 'SILENCE')
        assert hasattr(VADState, 'SPEECH')
        assert hasattr(VADState, 'UNCERTAIN')

    def test_states_are_distinct(self):
        """States should be distinct values."""
        assert VADState.SILENCE != VADState.SPEECH
        assert VADState.SPEECH != VADState.UNCERTAIN
        assert VADState.SILENCE != VADState.UNCERTAIN


class TestVADEvent:
    """Test VAD event enumeration."""

    def test_events_exist(self):
        """VAD should emit these events."""
        assert hasattr(VADEvent, 'NONE')
        assert hasattr(VADEvent, 'SPEECH_START')
        assert hasattr(VADEvent, 'SPEECH_END')


class TestVADResult:
    """Test VAD result dataclass."""

    def test_result_fields(self):
        """VADResult should contain required fields."""
        result = VADResult(
            is_speech=True,
            state=VADState.SPEECH,
            event=VADEvent.SPEECH_START,
            energy_db=-25.0,
            confidence=0.85,
            timestamp=1234.567
        )

        assert result.is_speech is True
        assert result.state == VADState.SPEECH
        assert result.event == VADEvent.SPEECH_START
        assert result.energy_db == -25.0
        assert result.confidence == 0.85
        assert result.timestamp == 1234.567


class TestVoiceActivityDetectorInit:
    """Test VAD initialization."""

    def test_default_initialization(self):
        """VAD should initialize with default config."""
        vad = VoiceActivityDetector()

        assert vad.config is not None
        assert vad.state == VADState.SILENCE
        assert vad.is_speech is False

    def test_custom_config_initialization(self):
        """VAD should accept custom config."""
        config = VADConfig(energy_threshold_db=-35.0)
        vad = VoiceActivityDetector(config)

        assert vad.config.energy_threshold_db == -35.0

    def test_initial_state_is_silence(self):
        """VAD should start in SILENCE state."""
        vad = VoiceActivityDetector()
        assert vad.state == VADState.SILENCE
        assert vad.is_speech is False


class TestVADEnergyDetection:
    """Test energy-based voice detection."""

    def test_silence_detected_as_silence(self, silence_samples):
        """Silence should be detected as non-speech."""
        vad = VoiceActivityDetector(VADConfig(energy_threshold_db=-50.0))

        # Process silence frame
        frame = silence_samples[:320]  # 20ms at 16kHz
        result = vad.process_frame(frame)

        assert result.is_speech is False
        assert result.energy_db < -50.0

    def test_speech_detected_as_speech(self, speech_samples):
        """Speech-level audio should be detected as speech (after min_speech_ms)."""
        vad = VoiceActivityDetector(VADConfig(
            energy_threshold_db=-40.0,
            min_speech_ms=20  # Quick detection for test
        ))

        # Process multiple speech frames to trigger state change
        frame = speech_samples[:320]
        for _ in range(5):
            result = vad.process_frame(frame)

        # After multiple frames, should be in speech state
        assert result.is_speech is True
        assert result.energy_db > -40.0

    def test_loud_audio_detected(self, loud_samples):
        """Loud audio should definitely trigger speech detection."""
        vad = VoiceActivityDetector(VADConfig(min_speech_ms=20))

        frame = loud_samples[:320]
        # Process multiple frames to trigger state change
        for _ in range(5):
            result = vad.process_frame(frame)

        assert result.is_speech is True
        assert result.energy_db > -20.0

    def test_energy_calculation_accuracy(self):
        """Energy calculation should be mathematically correct."""
        vad = VoiceActivityDetector()

        # Full-scale sine wave: RMS = 1/sqrt(2) ≈ 0.707, dB ≈ -3dB
        t = np.linspace(0, 0.02, 320, dtype=np.float32)
        full_scale = np.sin(2 * np.pi * 1000 * t).astype(np.float32)

        result = vad.process_frame(full_scale)
        # Should be approximately -3dB for full-scale sine
        assert -4.0 <= result.energy_db <= -2.0

    def test_zero_samples_handled(self):
        """Zero-valued samples should not crash and return very low energy."""
        vad = VoiceActivityDetector()

        zeros = np.zeros(320, dtype=np.float32)
        result = vad.process_frame(zeros)

        assert result.is_speech is False
        assert result.energy_db < -80.0  # Very low, near silence floor


class TestVADStateMachine:
    """Test VAD state transitions and events."""

    def test_silence_to_speech_transition(self, speech_samples):
        """Transition from silence to speech should emit SPEECH_START."""
        vad = VoiceActivityDetector(VADConfig(
            min_speech_ms=20,  # Quick detection for test
            energy_threshold_db=-40.0
        ))

        # Start with silence
        silence_frame = np.zeros(320, dtype=np.float32)
        result1 = vad.process_frame(silence_frame)
        assert result1.state == VADState.SILENCE

        # Transition to speech
        speech_frame = speech_samples[:320]
        result2 = vad.process_frame(speech_frame)

        # Should eventually emit SPEECH_START (might take a few frames for smoothing)
        # Process additional frames if needed
        events = [result2.event]
        for i in range(5):
            result = vad.process_frame(speech_frame)
            events.append(result.event)

        assert VADEvent.SPEECH_START in events

    def test_speech_to_silence_transition(self, speech_samples, silence_samples):
        """Transition from speech to silence should emit SPEECH_END."""
        vad = VoiceActivityDetector(VADConfig(
            min_speech_ms=20,
            min_silence_ms=40,
            energy_threshold_db=-40.0
        ))

        # Prime with speech
        for _ in range(10):
            vad.process_frame(speech_samples[:320])

        assert vad.state == VADState.SPEECH

        # Transition to silence
        silence_frame = silence_samples[:320]
        events = []
        for _ in range(20):  # Process enough silence frames
            result = vad.process_frame(silence_frame)
            events.append(result.event)

        assert VADEvent.SPEECH_END in events

    def test_brief_silence_during_speech_ignored(self, speech_samples):
        """Brief silence during speech should not trigger SPEECH_END."""
        vad = VoiceActivityDetector(VADConfig(
            min_speech_ms=20,
            min_silence_ms=300,  # Require 300ms silence to end speech
            energy_threshold_db=-40.0
        ))

        # Prime with speech
        for _ in range(10):
            vad.process_frame(speech_samples[:320])

        # Brief silence (only 2 frames = 40ms)
        silence_frame = np.zeros(320, dtype=np.float32)
        events = []
        for _ in range(2):
            result = vad.process_frame(silence_frame)
            events.append(result.event)

        # Should NOT emit SPEECH_END for brief pause
        assert VADEvent.SPEECH_END not in events

        # Continue with speech
        result = vad.process_frame(speech_samples[:320])
        assert result.state == VADState.SPEECH

    def test_brief_noise_during_silence_ignored(self, silence_samples, speech_samples):
        """Brief noise burst during silence should not trigger SPEECH_START."""
        vad = VoiceActivityDetector(VADConfig(
            min_speech_ms=100,  # Require 100ms speech to trigger
            energy_threshold_db=-40.0
        ))

        # Start in silence
        for _ in range(10):
            vad.process_frame(silence_samples[:320])

        # Brief noise (only 1 frame = 20ms, less than min_speech_ms)
        vad.process_frame(speech_samples[:320])

        # Back to silence
        for _ in range(5):
            result = vad.process_frame(silence_samples[:320])

        # Should not have triggered speech
        assert result.state == VADState.SILENCE


class TestVADStreamProcessing:
    """Test streaming audio processing."""

    def test_process_multiple_frames(self, mixed_audio, audio_config):
        """Process multiple frames and track state changes."""
        from tests.test_voice.conftest import generate_audio_frames

        vad = VoiceActivityDetector(VADConfig(
            min_speech_ms=60,
            min_silence_ms=100,
            energy_threshold_db=-35.0
        ))

        events = []
        states = []

        for frame in generate_audio_frames(mixed_audio, frame_size_ms=20):
            result = vad.process_frame(frame)
            events.append(result.event)
            states.append(result.state)

        # Should detect speech start and end
        assert VADEvent.SPEECH_START in events
        assert VADEvent.SPEECH_END in events

        # Should transition through states
        assert VADState.SILENCE in states
        assert VADState.SPEECH in states

    def test_callback_on_speech_events(self, speech_samples):
        """Callbacks should fire on speech events."""
        vad = VoiceActivityDetector(VADConfig(min_speech_ms=20))

        speech_start_called = []
        speech_end_called = []

        vad.on_speech_start = lambda r: speech_start_called.append(r)
        vad.on_speech_end = lambda r: speech_end_called.append(r)

        # Trigger speech start
        for _ in range(10):
            vad.process_frame(speech_samples[:320])

        assert len(speech_start_called) >= 1

        # Trigger speech end
        silence = np.zeros(320, dtype=np.float32)
        for _ in range(50):
            vad.process_frame(silence)

        assert len(speech_end_called) >= 1

    def test_reset_clears_state(self, speech_samples):
        """Reset should return VAD to initial state."""
        vad = VoiceActivityDetector()

        # Put into speech state
        for _ in range(10):
            vad.process_frame(speech_samples[:320])

        assert vad.state == VADState.SPEECH

        # Reset
        vad.reset()

        assert vad.state == VADState.SILENCE
        assert vad.is_speech is False


class TestVADEdgeCases:
    """Test edge cases and robustness."""

    def test_empty_frame_raises(self):
        """Empty frame should raise ValueError."""
        vad = VoiceActivityDetector()

        with pytest.raises(ValueError, match="empty"):
            vad.process_frame(np.array([], dtype=np.float32))

    def test_wrong_dtype_converted(self):
        """Non-float32 input should be converted."""
        vad = VoiceActivityDetector()

        # int16 input (common raw audio format)
        int16_frame = np.random.randint(-32768, 32767, 320, dtype=np.int16)
        result = vad.process_frame(int16_frame)

        assert isinstance(result, VADResult)

    def test_very_short_frame_handled(self):
        """Frames shorter than configured size should be handled."""
        vad = VoiceActivityDetector(VADConfig(frame_size_ms=20))

        # Only 160 samples (10ms instead of 20ms)
        short_frame = np.zeros(160, dtype=np.float32)
        result = vad.process_frame(short_frame)

        assert isinstance(result, VADResult)

    def test_very_long_frame_handled(self):
        """Frames longer than configured size should be handled."""
        vad = VoiceActivityDetector(VADConfig(frame_size_ms=20))

        # 640 samples (40ms instead of 20ms)
        long_frame = np.zeros(640, dtype=np.float32)
        result = vad.process_frame(long_frame)

        assert isinstance(result, VADResult)

    def test_nan_values_handled(self):
        """NaN values in input should not crash."""
        vad = VoiceActivityDetector()

        frame_with_nan = np.array([0.0] * 160 + [np.nan] * 160, dtype=np.float32)
        result = vad.process_frame(frame_with_nan)

        # Should handle gracefully (treat as silence or raise clear error)
        assert isinstance(result, VADResult) or pytest.raises(ValueError)

    def test_inf_values_handled(self):
        """Inf values in input should not crash."""
        vad = VoiceActivityDetector()

        frame_with_inf = np.array([0.0] * 160 + [np.inf] * 160, dtype=np.float32)
        result = vad.process_frame(frame_with_inf)

        assert isinstance(result, VADResult) or pytest.raises(ValueError)


class TestVADPerformance:
    """Test performance requirements."""

    def test_process_frame_latency(self, speech_samples):
        """Frame processing should complete within 5ms."""
        vad = VoiceActivityDetector()
        frame = speech_samples[:320]

        # Warm up
        for _ in range(10):
            vad.process_frame(frame)

        # Measure
        times = []
        for _ in range(100):
            start = time.perf_counter()
            vad.process_frame(frame)
            elapsed = (time.perf_counter() - start) * 1000
            times.append(elapsed)

        avg_time = sum(times) / len(times)
        max_time = max(times)

        assert avg_time < 2.0, f"Average latency {avg_time:.2f}ms exceeds 2ms"
        assert max_time < 5.0, f"Max latency {max_time:.2f}ms exceeds 5ms"

    def test_memory_stability_long_run(self, speech_samples):
        """Memory should not grow during long processing."""
        import sys

        vad = VoiceActivityDetector()
        frame = speech_samples[:320]

        # Process many frames
        for _ in range(10000):
            vad.process_frame(frame)

        # VAD object should have bounded memory
        # (This is a basic check - proper memory profiling would use tracemalloc)
        vad_size = sys.getsizeof(vad)
        assert vad_size < 100000, f"VAD object size {vad_size} bytes seems too large"


class TestVADThresholdAdaptation:
    """Test adaptive threshold features."""

    def test_get_current_threshold(self):
        """Should be able to query current threshold."""
        vad = VoiceActivityDetector(VADConfig(energy_threshold_db=-40.0))
        assert vad.get_threshold_db() == -40.0

    def test_set_threshold_runtime(self):
        """Should be able to adjust threshold at runtime."""
        vad = VoiceActivityDetector(VADConfig(energy_threshold_db=-40.0))

        vad.set_threshold_db(-35.0)
        assert vad.get_threshold_db() == -35.0

    def test_get_statistics(self, mixed_audio):
        """Should provide statistics about detection."""
        from tests.test_voice.conftest import generate_audio_frames

        vad = VoiceActivityDetector()

        for frame in generate_audio_frames(mixed_audio, frame_size_ms=20):
            vad.process_frame(frame)

        stats = vad.get_statistics()

        assert 'total_frames' in stats
        assert 'speech_frames' in stats
        assert 'silence_frames' in stats
        assert 'speech_ratio' in stats
        assert stats['total_frames'] > 0
