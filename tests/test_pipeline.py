"""Tests for Production Wake Word Pipeline

Tests the integrated pipeline components:
- AudioPreprocessor: resampling, normalization
- NoiseCalibrator: EMA tracking, adaptive thresholds
- MultiFrameConfirmer: sliding window confirmation
- PipelineConfig: validation

Created: 26 January 2026
"""

import pytest
import numpy as np
import time

# Add firmware to path
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.voice.pipeline import (
    PipelineConfig,
    PipelineState,
    DetectionResult,
    AudioPreprocessor,
    NoiseCalibrator,
    MultiFrameConfirmer,
)


# =============================================================================
# PipelineConfig Tests
# =============================================================================

class TestPipelineConfig:
    """Tests for PipelineConfig validation."""

    def test_default_config(self):
        """Test default configuration values."""
        config = PipelineConfig()

        assert config.input_sample_rate == 48000
        assert config.output_sample_rate == 16000
        assert config.chunk_ms == 80
        assert config.threshold == 0.82
        assert config.confirm_window == 5
        assert config.confirm_required == 3

    def test_output_chunk_samples(self):
        """Test output chunk samples calculation."""
        config = PipelineConfig()

        # 80ms at 16kHz = 1280 samples
        assert config.output_chunk_samples == 1280

    def test_input_chunk_samples(self):
        """Test input chunk samples calculation."""
        config = PipelineConfig()

        # 80ms at 48kHz = 3840 samples
        assert config.input_chunk_samples == 3840

    def test_invalid_threshold(self):
        """Test that invalid threshold raises error."""
        with pytest.raises(ValueError, match="threshold must be in"):
            PipelineConfig(threshold=1.5)

        with pytest.raises(ValueError, match="threshold must be in"):
            PipelineConfig(threshold=0.0)

    def test_invalid_confirm_required(self):
        """Test that confirm_required > confirm_window raises error."""
        with pytest.raises(ValueError, match="confirm_required.*cannot exceed"):
            PipelineConfig(confirm_window=3, confirm_required=5)

    def test_invalid_ema_alpha(self):
        """Test that invalid EMA alpha raises error."""
        with pytest.raises(ValueError, match="score_ema_alpha must be in"):
            PipelineConfig(score_ema_alpha=1.5)


# =============================================================================
# AudioPreprocessor Tests
# =============================================================================

class TestAudioPreprocessor:
    """Tests for AudioPreprocessor."""

    @pytest.fixture
    def preprocessor(self):
        """Create preprocessor with default config."""
        config = PipelineConfig()
        return AudioPreprocessor(config)

    def test_stereo_to_mono_extraction(self, preprocessor):
        """Test left channel extraction from stereo."""
        # Create fake S32_LE stereo data
        # Left channel: 1000, Right channel: 2000 (interleaved)
        left_samples = np.array([1000, 3000, 5000], dtype=np.int32)
        right_samples = np.array([2000, 4000, 6000], dtype=np.int32)

        # Interleave
        stereo = np.empty(6, dtype=np.int32)
        stereo[0::2] = left_samples
        stereo[1::2] = right_samples

        raw_bytes = stereo.tobytes()

        # Process
        result = preprocessor.process(raw_bytes)

        # Should only have left channel (after resampling)
        # With 3 samples and 3:1 ratio, we get 1 output sample
        assert len(result) == 1

    def test_s32_le_normalization(self, preprocessor):
        """Test S32_LE to float32 normalization."""
        # Full scale S32_LE = 2147483647
        max_val = np.array([2147483647, 0], dtype=np.int32)  # stereo pair
        raw_bytes = max_val.tobytes()

        result = preprocessor.process(raw_bytes)

        # Should be normalized close to 1.0
        # With 1 sample pair and 3:1 ratio, result has 0 samples
        # Need at least 3 sample pairs for 3:1 decimation
        # Let's test with more samples

        max_vals = np.array([2147483647, 0] * 3, dtype=np.int32)
        raw_bytes = max_vals.tobytes()

        result = preprocessor.process(raw_bytes)

        # After averaging, should be close to 1.0
        assert len(result) == 1
        assert result[0] > 0.99  # Close to 1.0

    def test_resample_48k_to_16k(self, preprocessor):
        """Test 48kHz to 16kHz resampling (3:1 ratio)."""
        # 48 samples at 48kHz should become 16 at 16kHz
        # For stereo, we need 48 sample pairs = 96 int32 values
        samples = np.zeros(96, dtype=np.int32)
        raw_bytes = samples.tobytes()

        result = preprocessor.process(raw_bytes)

        # 48 mono samples / 3 = 16 samples
        assert len(result) == 16

    def test_handles_nan_inf(self, preprocessor):
        """Test that NaN/Inf values are handled."""
        # Create data that might produce NaN
        # (not easy with int32, but we can test the handling logic)
        samples = np.zeros(24, dtype=np.int32)  # 12 stereo pairs -> 4 output
        raw_bytes = samples.tobytes()

        result = preprocessor.process(raw_bytes)

        # Should not contain NaN or Inf
        assert not np.any(np.isnan(result))
        assert not np.any(np.isinf(result))

    def test_process_int16_output(self, preprocessor):
        """Test int16 output for OpenWakeWord."""
        # Create stereo data
        samples = np.array([100000000, 0] * 6, dtype=np.int32)
        raw_bytes = samples.tobytes()

        result = preprocessor.process_int16(raw_bytes)

        # Should be int16
        assert result.dtype == np.int16
        assert len(result) == 2  # 6 / 3 = 2


# =============================================================================
# NoiseCalibrator Tests
# =============================================================================

class TestNoiseCalibrator:
    """Tests for NoiseCalibrator."""

    @pytest.fixture
    def calibrator(self):
        """Create calibrator with default config."""
        config = PipelineConfig()
        return NoiseCalibrator(config)

    def test_initial_state(self, calibrator):
        """Test initial calibrator state."""
        assert calibrator.noise_floor_db == -60.0
        assert not calibrator.is_calibrated

    def test_calibration_samples(self, calibrator):
        """Test adding calibration samples."""
        calibrator.add_calibration_sample(-45.0)
        calibrator.add_calibration_sample(-42.0)
        calibrator.add_calibration_sample(-48.0)

        noise_floor = calibrator.complete_calibration()

        # Should be median: -45.0
        assert noise_floor == -45.0
        assert calibrator.is_calibrated

    def test_calibration_outlier_rejection(self, calibrator):
        """Test that median rejects outliers."""
        # Add samples with an outlier
        calibrator.add_calibration_sample(-45.0)
        calibrator.add_calibration_sample(-45.0)
        calibrator.add_calibration_sample(-45.0)
        calibrator.add_calibration_sample(-10.0)  # Loud outlier
        calibrator.add_calibration_sample(-45.0)

        noise_floor = calibrator.complete_calibration()

        # Median should reject the -10 outlier
        assert noise_floor == -45.0

    def test_noise_floor_ema_update(self, calibrator):
        """Test EMA update of noise floor during silence."""
        # Complete calibration first
        calibrator.add_calibration_sample(-50.0)
        calibrator.complete_calibration()

        initial_floor = calibrator.noise_floor_db

        # Update during silence
        calibrator.update_noise_floor(-40.0, is_silence=True)

        # Floor should have moved toward -40
        assert calibrator.noise_floor_db > initial_floor

    def test_noise_floor_not_updated_during_speech(self, calibrator):
        """Test that noise floor doesn't update during speech."""
        calibrator.add_calibration_sample(-50.0)
        calibrator.complete_calibration()

        initial_floor = calibrator.noise_floor_db

        # Update during speech
        calibrator.update_noise_floor(-20.0, is_silence=False)

        # Floor should not change
        assert calibrator.noise_floor_db == initial_floor

    def test_score_ema_smoothing(self, calibrator):
        """Test EMA smoothing of detection scores."""
        # First score
        smoothed1 = calibrator.update_score(0.5)
        # EMA = 0.3 * 0.5 + 0.7 * 0 = 0.15
        assert abs(smoothed1 - 0.15) < 0.01

        # Second score
        smoothed2 = calibrator.update_score(0.8)
        # EMA = 0.3 * 0.8 + 0.7 * 0.15 = 0.24 + 0.105 = 0.345
        assert abs(smoothed2 - 0.345) < 0.01

    def test_adaptive_threshold_noisy_environment(self, calibrator):
        """Test adaptive threshold in noisy environment."""
        # Simulate noisy environment (noise floor > -35 dB)
        calibrator.add_calibration_sample(-30.0)
        calibrator.complete_calibration()

        threshold = calibrator.get_adaptive_threshold()

        # Should be higher than base threshold (0.82)
        assert threshold > 0.82

    def test_reset(self, calibrator):
        """Test calibrator reset."""
        calibrator.add_calibration_sample(-40.0)
        calibrator.complete_calibration()
        calibrator.update_score(0.5)

        calibrator.reset()

        assert calibrator.noise_floor_db == -60.0
        assert not calibrator.is_calibrated


# =============================================================================
# MultiFrameConfirmer Tests
# =============================================================================

class TestMultiFrameConfirmer:
    """Tests for MultiFrameConfirmer."""

    @pytest.fixture
    def confirmer(self):
        """Create confirmer with default config (3/5 frames)."""
        config = PipelineConfig()
        return MultiFrameConfirmer(config)

    def test_initial_state(self, confirmer):
        """Test initial confirmer state."""
        assert not confirmer.is_in_cooldown()

    def test_single_frame_not_confirmed(self, confirmer):
        """Test that single high score doesn't confirm."""
        # Single frame above threshold
        confirmed = confirmer.is_confirmed(0.9)

        assert not confirmed

    def test_confirm_after_three_frames(self, confirmer):
        """Test confirmation after 3/5 frames above threshold."""
        # Add 3 frames above threshold
        confirmer.is_confirmed(0.85)  # 1
        confirmer.is_confirmed(0.86)  # 2
        confirmed = confirmer.is_confirmed(0.87)  # 3

        assert confirmed

    def test_mixed_frames_confirmation(self, confirmer):
        """Test confirmation with mixed scores."""
        # Pattern: high, low, high, high, high -> should confirm at 4th high
        confirmer.is_confirmed(0.85)  # above
        confirmer.is_confirmed(0.50)  # below
        confirmer.is_confirmed(0.85)  # above
        confirmer.is_confirmed(0.85)  # above (3rd above, should confirm)

        confirmed = confirmer.is_confirmed(0.85)  # above (checking state)

        # Now we have 4/5 above threshold
        assert confirmed

    def test_cooldown_activation(self, confirmer):
        """Test that detection triggers cooldown."""
        assert not confirmer.is_in_cooldown()

        confirmer.record_detection()

        assert confirmer.is_in_cooldown()

    def test_cooldown_expiration(self, confirmer):
        """Test cooldown expiration."""
        # Use a short cooldown for testing
        confirmer.config.cooldown_seconds = 0.1

        confirmer.record_detection()
        assert confirmer.is_in_cooldown()

        # Wait for cooldown
        time.sleep(0.15)

        assert not confirmer.is_in_cooldown()

    def test_window_sliding(self, confirmer):
        """Test that window slides correctly."""
        # Fill window with 5 low scores
        for _ in range(5):
            confirmer.add_score(0.1)

        # Window should be full of low scores
        count = confirmer.add_score(0.9)  # Add one high, remove oldest low
        assert count == 1  # Only the new high score

        # Add two more high
        confirmer.add_score(0.9)
        count = confirmer.add_score(0.9)
        assert count == 3  # Three high scores

    def test_reset_clears_window(self, confirmer):
        """Test that reset clears the window."""
        # Add some scores
        confirmer.add_score(0.9)
        confirmer.add_score(0.9)
        confirmer.record_detection()

        confirmer.reset()

        # Should start fresh
        assert not confirmer.is_in_cooldown()
        count = confirmer.add_score(0.9)
        assert count == 1  # Only one score in window


# =============================================================================
# DetectionResult Tests
# =============================================================================

class TestDetectionResult:
    """Tests for DetectionResult dataclass."""

    def test_not_detected_factory(self):
        """Test not_detected factory method."""
        result = DetectionResult.not_detected()

        assert not result.detected
        assert result.wake_word is None
        assert result.raw_score == 0.0
        assert result.smoothed_score == 0.0
        assert result.confirm_count == 0

    def test_detection_result_creation(self):
        """Test creating a detection result."""
        result = DetectionResult(
            detected=True,
            wake_word="hey openduck",
            raw_score=0.92,
            smoothed_score=0.88,
            confirm_count=4,
            noise_floor=-45.0,
            vad_active=True,
            timestamp=time.monotonic()
        )

        assert result.detected
        assert result.wake_word == "hey openduck"
        assert result.raw_score == 0.92
        assert result.confirm_count == 4


# =============================================================================
# Integration Tests
# =============================================================================

class TestPipelineIntegration:
    """Integration tests for pipeline components working together."""

    def test_preprocessor_to_calibrator_flow(self):
        """Test data flow from preprocessor through calibrator."""
        config = PipelineConfig()
        preprocessor = AudioPreprocessor(config)
        calibrator = NoiseCalibrator(config)

        # Simulate audio processing
        samples = np.zeros(96, dtype=np.int32)  # Silent audio
        raw_bytes = samples.tobytes()

        audio_16k = preprocessor.process(raw_bytes)

        # Calculate energy
        rms = np.sqrt(np.mean(audio_16k ** 2))
        energy_db = 20 * np.log10(max(rms, 1e-10))

        # Add to calibrator
        calibrator.add_calibration_sample(energy_db)

        # Should have added sample
        assert len(calibrator._noise_samples) == 1

    def test_confirmer_blocks_single_spike(self):
        """Test that confirmer blocks single-frame spikes."""
        config = PipelineConfig()
        confirmer = MultiFrameConfirmer(config)

        # Simulate pattern: low, low, HIGH, low, low
        # This is a false positive spike that should be blocked

        results = []
        scores = [0.1, 0.2, 0.95, 0.1, 0.2]

        for score in scores:
            confirmed = confirmer.is_confirmed(score)
            results.append(confirmed)

        # Should never confirm (only 1 frame above threshold)
        assert not any(results)

    def test_confirmer_passes_sustained_speech(self):
        """Test that confirmer passes sustained above-threshold scores."""
        config = PipelineConfig()
        confirmer = MultiFrameConfirmer(config)

        # Simulate sustained high scores
        scores = [0.85, 0.87, 0.86, 0.88, 0.85]

        results = []
        for score in scores:
            confirmed = confirmer.is_confirmed(score)
            results.append(confirmed)

        # Should confirm after 3rd frame (3/5 above threshold)
        assert results[2]  # 3rd frame should confirm


# =============================================================================
# Main
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
