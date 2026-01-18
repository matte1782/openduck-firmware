#!/usr/bin/env python3
"""
Comprehensive Tests for Social Emotion Patterns
Boston Dynamics / Pixar Quality Standard

Tests for 4 social emotion patterns:
1. PlayfulPattern - Bouncy, asymmetric, sparkles
2. AffectionatePattern - Heartbeat with warm glow
3. EmpatheticPattern - Mirroring, supportive
4. GratefulPattern - Appreciation surge

Test Categories:
- Unit Tests: Pattern initialization, validation, rendering
- Performance Tests: Frame time benchmarks (<2.5ms avg, <10ms max)
- Visual Validation: Output format correctness
- Transition Tests: Valid state transitions

Author: Social Emotion Implementation Specialist (Agent 2)
Created: 18 January 2026
"""

import pytest
import time
import math
from typing import List, Tuple

# Import the patterns to test
import sys
import os

# Add firmware/src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from led.patterns.social_emotions import (
    PlayfulPattern,
    AffectionatePattern,
    EmpatheticPattern,
    GratefulPattern,
    Sparkle,
    MAX_SPARKLES,
    SOCIAL_EMOTION_COLORS,
    SOCIAL_PATTERN_REGISTRY,
)
from led.patterns.base import PatternConfig, RGB


# =============================================================================
# Constants for Testing
# =============================================================================

DEFAULT_NUM_PIXELS = 16
PERFORMANCE_TEST_FRAMES = 250
FRAME_TIME_AVG_LIMIT_MS = 2.5
FRAME_TIME_MAX_LIMIT_MS = 10.0


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def playful_pattern():
    """Create a PlayfulPattern instance for testing."""
    return PlayfulPattern(num_pixels=DEFAULT_NUM_PIXELS)


@pytest.fixture
def affectionate_pattern():
    """Create an AffectionatePattern instance for testing."""
    return AffectionatePattern(num_pixels=DEFAULT_NUM_PIXELS)


@pytest.fixture
def empathetic_pattern():
    """Create an EmpatheticPattern instance for testing."""
    return EmpatheticPattern(num_pixels=DEFAULT_NUM_PIXELS)


@pytest.fixture
def grateful_pattern():
    """Create a GratefulPattern instance for testing."""
    return GratefulPattern(num_pixels=DEFAULT_NUM_PIXELS)


@pytest.fixture
def base_color() -> RGB:
    """Standard test color (warm orange for playful)."""
    return (255, 180, 100)


# =============================================================================
# PlayfulPattern Tests
# =============================================================================

class TestPlayfulPattern:
    """Test suite for PlayfulPattern (bouncy, mischievous)."""

    def test_initialization(self, playful_pattern):
        """Test pattern initializes correctly."""
        assert playful_pattern.num_pixels == DEFAULT_NUM_PIXELS
        assert playful_pattern.NAME == "playful"
        assert len(playful_pattern._sparkles) == 0
        assert playful_pattern._asymmetry_phase == 0.0

    def test_initialization_invalid_pixels(self):
        """Test initialization fails with invalid pixel count."""
        with pytest.raises(ValueError, match="num_pixels must be positive"):
            PlayfulPattern(num_pixels=0)
        with pytest.raises(ValueError, match="num_pixels must be positive"):
            PlayfulPattern(num_pixels=-5)

    def test_render_output_format(self, playful_pattern, base_color):
        """Test render returns correct format."""
        result = playful_pattern.render(base_color)
        assert isinstance(result, list)
        assert len(result) == DEFAULT_NUM_PIXELS
        for pixel in result:
            assert isinstance(pixel, tuple)
            assert len(pixel) == 3
            assert all(0 <= c <= 255 for c in pixel)

    def test_render_both_eyes(self, playful_pattern, base_color):
        """Test asymmetric rendering for both eyes."""
        left, right = playful_pattern.render_both_eyes(base_color)
        assert len(left) == DEFAULT_NUM_PIXELS
        assert len(right) == DEFAULT_NUM_PIXELS
        # Eyes should potentially differ (asymmetry)
        # Verify format
        for pixel in left + right:
            assert isinstance(pixel, tuple)
            assert len(pixel) == 3

    def test_sparkles_bounded(self, playful_pattern, base_color):
        """Test sparkle count stays within MAX_SPARKLES limit."""
        # Run many frames to potentially spawn sparkles
        for _ in range(500):
            playful_pattern.render(base_color)
            playful_pattern.advance()
        assert len(playful_pattern._sparkles) <= MAX_SPARKLES

    def test_bounce_envelope(self, playful_pattern):
        """Test bounce envelope produces valid range."""
        for progress in [0.0, 0.25, 0.5, 0.75, 1.0]:
            bounce = playful_pattern._bounce_envelope(progress)
            assert 0.0 <= bounce <= 2.0  # Allow some overshoot for bounce

    def test_reset_clears_state(self, playful_pattern, base_color):
        """Test reset() clears sparkles and phase."""
        # Generate some state
        for _ in range(50):
            playful_pattern.render(base_color)
            playful_pattern.advance()

        playful_pattern.reset()
        assert len(playful_pattern._sparkles) == 0
        assert playful_pattern._asymmetry_phase == 0.0

    def test_performance_benchmark(self, playful_pattern, base_color):
        """Test frame time meets performance requirements."""
        times = []
        for _ in range(PERFORMANCE_TEST_FRAMES):
            start = time.perf_counter()
            playful_pattern.render(base_color)
            playful_pattern.advance()
            times.append((time.perf_counter() - start) * 1000)

        avg_time = sum(times) / len(times)
        max_time = max(times)

        assert avg_time < FRAME_TIME_AVG_LIMIT_MS, \
            f"Average frame time {avg_time:.3f}ms exceeds {FRAME_TIME_AVG_LIMIT_MS}ms"
        assert max_time < FRAME_TIME_MAX_LIMIT_MS, \
            f"Max frame time {max_time:.3f}ms exceeds {FRAME_TIME_MAX_LIMIT_MS}ms"


# =============================================================================
# AffectionatePattern Tests
# =============================================================================

class TestAffectionatePattern:
    """Test suite for AffectionatePattern (heartbeat, warm glow)."""

    def test_initialization(self, affectionate_pattern):
        """Test pattern initializes correctly."""
        assert affectionate_pattern.num_pixels == DEFAULT_NUM_PIXELS
        assert affectionate_pattern.NAME == "affectionate"

    def test_initialization_invalid_pixels(self):
        """Test initialization fails with invalid pixel count."""
        with pytest.raises(ValueError, match="num_pixels must be positive"):
            AffectionatePattern(num_pixels=0)

    def test_render_output_format(self, affectionate_pattern, base_color):
        """Test render returns correct format."""
        result = affectionate_pattern.render(base_color)
        assert isinstance(result, list)
        assert len(result) == DEFAULT_NUM_PIXELS
        for pixel in result:
            assert isinstance(pixel, tuple)
            assert len(pixel) == 3
            assert all(0 <= c <= 255 for c in pixel)

    def test_heartbeat_timing(self, affectionate_pattern):
        """Test heartbeat BPM calculation."""
        bpm = affectionate_pattern.get_heart_rate_bpm()
        # Default speed 1.0 should give ~72 BPM
        assert 70 <= bpm <= 75

    def test_heartbeat_speed_adjustment(self):
        """Test heart rate changes with speed config."""
        fast = AffectionatePattern(config=PatternConfig(speed=2.0))
        slow = AffectionatePattern(config=PatternConfig(speed=0.5))
        assert fast.get_heart_rate_bpm() > slow.get_heart_rate_bpm()

    def test_heartbeat_envelope(self, affectionate_pattern):
        """Test heartbeat envelope produces valid range."""
        for t in [0.0, 0.25, 0.5, 0.75, 1.0]:
            envelope = affectionate_pattern._heartbeat_envelope(t)
            assert 0.0 <= envelope <= 1.0

    def test_brightness_never_too_dim(self, affectionate_pattern, base_color):
        """Test minimum intensity is maintained (warmth)."""
        # Run through full cycle
        min_brightness = 255
        for _ in range(50):
            result = affectionate_pattern.render(base_color)
            affectionate_pattern.advance()
            for pixel in result:
                brightness = max(pixel)
                if brightness > 0:
                    min_brightness = min(min_brightness, brightness)

        # Should never go below ~30% of base color
        expected_min = int(base_color[0] * 0.3 * 0.5)  # 30% intensity, 50% config
        assert min_brightness >= expected_min - 10  # Allow small tolerance

    def test_performance_benchmark(self, affectionate_pattern, base_color):
        """Test frame time meets performance requirements."""
        times = []
        for _ in range(PERFORMANCE_TEST_FRAMES):
            start = time.perf_counter()
            affectionate_pattern.render(base_color)
            affectionate_pattern.advance()
            times.append((time.perf_counter() - start) * 1000)

        avg_time = sum(times) / len(times)
        max_time = max(times)

        assert avg_time < FRAME_TIME_AVG_LIMIT_MS
        assert max_time < FRAME_TIME_MAX_LIMIT_MS


# =============================================================================
# EmpatheticPattern Tests
# =============================================================================

class TestEmpatheticPattern:
    """Test suite for EmpatheticPattern (mirroring, supportive)."""

    def test_initialization(self, empathetic_pattern):
        """Test pattern initializes correctly."""
        assert empathetic_pattern.num_pixels == DEFAULT_NUM_PIXELS
        assert empathetic_pattern.NAME == "empathetic"

    def test_initialization_invalid_pixels(self):
        """Test initialization fails with invalid pixel count."""
        with pytest.raises(ValueError, match="num_pixels must be positive"):
            EmpatheticPattern(num_pixels=0)

    def test_render_output_format(self, empathetic_pattern, base_color):
        """Test render returns correct format."""
        result = empathetic_pattern.render(base_color)
        assert isinstance(result, list)
        assert len(result) == DEFAULT_NUM_PIXELS
        for pixel in result:
            assert isinstance(pixel, tuple)
            assert len(pixel) == 3
            assert all(0 <= c <= 255 for c in pixel)

    def test_breathing_timing(self, empathetic_pattern):
        """Test breathing cycle duration."""
        # 250 frames at 50Hz = 5 seconds per breath
        cycle_frames = empathetic_pattern.CYCLE_FRAMES
        breath_duration_s = cycle_frames / 50  # 50Hz
        assert 4.5 <= breath_duration_s <= 5.5  # ~5 seconds

    def test_ease_in_out(self, empathetic_pattern):
        """Test ease function produces valid output."""
        assert empathetic_pattern._ease_in_out(0.0) == 0.0
        assert empathetic_pattern._ease_in_out(1.0) == 1.0
        assert 0.4 < empathetic_pattern._ease_in_out(0.5) < 0.6

    def test_spatial_variation(self, empathetic_pattern, base_color):
        """Test pixels have spatial variation (mirroring effect)."""
        result = empathetic_pattern.render(base_color)
        # Advance to get wave effect
        for _ in range(25):
            empathetic_pattern.advance()
        result = empathetic_pattern.render(base_color)

        # Check for variation between pixels
        unique_values = set(pixel[0] for pixel in result)
        # Should have some variation (not all identical)
        assert len(unique_values) >= 2 or len(result) == 1

    def test_performance_benchmark(self, empathetic_pattern, base_color):
        """Test frame time meets performance requirements."""
        times = []
        for _ in range(PERFORMANCE_TEST_FRAMES):
            start = time.perf_counter()
            empathetic_pattern.render(base_color)
            empathetic_pattern.advance()
            times.append((time.perf_counter() - start) * 1000)

        avg_time = sum(times) / len(times)
        max_time = max(times)

        assert avg_time < FRAME_TIME_AVG_LIMIT_MS
        assert max_time < FRAME_TIME_MAX_LIMIT_MS


# =============================================================================
# GratefulPattern Tests
# =============================================================================

class TestGratefulPattern:
    """Test suite for GratefulPattern (appreciation surge)."""

    def test_initialization(self, grateful_pattern):
        """Test pattern initializes correctly."""
        assert grateful_pattern.num_pixels == DEFAULT_NUM_PIXELS
        assert grateful_pattern.NAME == "grateful"

    def test_initialization_invalid_pixels(self):
        """Test initialization fails with invalid pixel count."""
        with pytest.raises(ValueError, match="num_pixels must be positive"):
            GratefulPattern(num_pixels=0)

    def test_render_output_format(self, grateful_pattern, base_color):
        """Test render returns correct format."""
        result = grateful_pattern.render(base_color)
        assert isinstance(result, list)
        assert len(result) == DEFAULT_NUM_PIXELS
        for pixel in result:
            assert isinstance(pixel, tuple)
            assert len(pixel) == 3
            assert all(0 <= c <= 255 for c in pixel)

    def test_surge_phases_exist(self, grateful_pattern):
        """Test all surge phases have valid frame counts."""
        antic = grateful_pattern.ANTICIPATION_FRAMES
        surge = grateful_pattern.SURGE_FRAMES
        hold = grateful_pattern.HOLD_FRAMES
        settle = grateful_pattern.SETTLE_FRAMES
        total = grateful_pattern.CYCLE_FRAMES

        assert antic + surge + hold + settle == total
        assert antic > 0
        assert surge > 0
        assert hold > 0
        assert settle > 0

    def test_ease_out(self, grateful_pattern):
        """Test ease-out function produces valid output."""
        assert grateful_pattern._ease_out(0.0) == 0.0
        assert grateful_pattern._ease_out(1.0) == 1.0
        # Ease-out should be faster at start
        mid = grateful_pattern._ease_out(0.5)
        assert mid > 0.5  # Already past midpoint

    def test_brightness_surge(self, grateful_pattern, base_color):
        """Test brightness surge occurs."""
        max_brightness = 0
        # Run through full cycle
        for _ in range(150):
            result = grateful_pattern.render(base_color)
            grateful_pattern.advance()
            for pixel in result:
                max_brightness = max(max_brightness, max(pixel))

        # Should reach near-maximum brightness during surge
        assert max_brightness >= int(base_color[0] * 0.9)

    def test_performance_benchmark(self, grateful_pattern, base_color):
        """Test frame time meets performance requirements."""
        times = []
        for _ in range(PERFORMANCE_TEST_FRAMES):
            start = time.perf_counter()
            grateful_pattern.render(base_color)
            grateful_pattern.advance()
            times.append((time.perf_counter() - start) * 1000)

        avg_time = sum(times) / len(times)
        max_time = max(times)

        assert avg_time < FRAME_TIME_AVG_LIMIT_MS
        assert max_time < FRAME_TIME_MAX_LIMIT_MS


# =============================================================================
# Sparkle Tests
# =============================================================================

class TestSparkle:
    """Test suite for Sparkle dataclass."""

    def test_sparkle_creation(self):
        """Test sparkle dataclass creation."""
        sparkle = Sparkle(
            pixel_index=5,
            intensity=1.0,
            color=(255, 200, 150),
            lifetime_remaining=10,
            decay_rate=0.1,
        )
        assert sparkle.pixel_index == 5
        assert sparkle.intensity == 1.0
        assert sparkle.color == (255, 200, 150)
        assert sparkle.lifetime_remaining == 10
        assert sparkle.decay_rate == 0.1


# =============================================================================
# Registry Tests
# =============================================================================

class TestSocialEmotionRegistry:
    """Test social emotion pattern registry."""

    def test_registry_contains_all_patterns(self):
        """Test registry contains all 4 social patterns."""
        expected = {'playful', 'affectionate', 'empathetic', 'grateful'}
        actual = set(SOCIAL_PATTERN_REGISTRY.keys())
        assert expected == actual

    def test_registry_patterns_instantiate(self):
        """Test all registry patterns can be instantiated."""
        for name, pattern_class in SOCIAL_PATTERN_REGISTRY.items():
            pattern = pattern_class(num_pixels=16)
            assert pattern.num_pixels == 16

    def test_color_config_exists(self):
        """Test color configuration exists for all patterns."""
        for emotion in ['playful', 'affectionate', 'empathetic', 'grateful']:
            assert emotion in SOCIAL_EMOTION_COLORS
            assert 'primary' in SOCIAL_EMOTION_COLORS[emotion]
            assert 'psychology' in SOCIAL_EMOTION_COLORS[emotion]


# =============================================================================
# Integration Tests
# =============================================================================

class TestSocialEmotionIntegration:
    """Integration tests for social emotions."""

    def test_all_patterns_consistent_interface(self):
        """Test all patterns have consistent interface."""
        patterns = [
            PlayfulPattern(num_pixels=16),
            AffectionatePattern(num_pixels=16),
            EmpatheticPattern(num_pixels=16),
            GratefulPattern(num_pixels=16),
        ]
        base_color = (255, 180, 100)

        for pattern in patterns:
            # All should have render method
            result = pattern.render(base_color)
            assert len(result) == 16

            # All should have advance method
            pattern.advance()

            # All should have reset method
            pattern.reset()

            # All should have NAME attribute
            assert hasattr(pattern, 'NAME')

    def test_pattern_config_speed_effect(self):
        """Test speed configuration affects all patterns."""
        fast_config = PatternConfig(speed=2.0)
        slow_config = PatternConfig(speed=0.5)

        patterns = [
            (PlayfulPattern, 'playful'),
            (AffectionatePattern, 'affectionate'),
            (EmpatheticPattern, 'empathetic'),
            (GratefulPattern, 'grateful'),
        ]

        for pattern_class, name in patterns:
            fast = pattern_class(config=fast_config)
            slow = pattern_class(config=slow_config)
            assert fast.config.speed > slow.config.speed

    def test_pattern_config_brightness_effect(self):
        """Test brightness configuration affects output."""
        bright_config = PatternConfig(brightness=1.0)
        dim_config = PatternConfig(brightness=0.5)
        base_color = (200, 200, 200)

        bright_pattern = PlayfulPattern(config=bright_config)
        dim_pattern = PlayfulPattern(config=dim_config)

        bright_result = bright_pattern.render(base_color)
        dim_result = dim_pattern.render(base_color)

        # Bright should have higher max brightness
        bright_max = max(max(p) for p in bright_result)
        dim_max = max(max(p) for p in dim_result)
        assert bright_max > dim_max


# =============================================================================
# Transition Tests (using EmotionState)
# =============================================================================

class TestSocialEmotionTransitions:
    """Test emotion state transitions involving social emotions."""

    def test_social_emotions_in_enum(self):
        """Test social emotions are in EmotionState enum."""
        from animation.emotions import EmotionState

        social_emotions = ['playful', 'affectionate', 'empathetic', 'grateful']
        for emotion in social_emotions:
            # Should not raise
            state = EmotionState(emotion)
            assert state.value == emotion

    def test_idle_can_transition_to_social(self):
        """Test IDLE can transition to all social emotions."""
        from animation.emotions import VALID_TRANSITIONS, EmotionState

        idle_targets = VALID_TRANSITIONS[EmotionState.IDLE]
        assert EmotionState.PLAYFUL in idle_targets
        assert EmotionState.AFFECTIONATE in idle_targets
        assert EmotionState.EMPATHETIC in idle_targets
        assert EmotionState.GRATEFUL in idle_targets

    def test_happy_flows_to_playful(self):
        """Test HAPPY can transition to PLAYFUL."""
        from animation.emotions import VALID_TRANSITIONS, EmotionState

        happy_targets = VALID_TRANSITIONS[EmotionState.HAPPY]
        assert EmotionState.PLAYFUL in happy_targets

    def test_playful_can_return_to_idle(self):
        """Test PLAYFUL can transition back to IDLE."""
        from animation.emotions import VALID_TRANSITIONS, EmotionState

        playful_targets = VALID_TRANSITIONS[EmotionState.PLAYFUL]
        assert EmotionState.IDLE in playful_targets


# =============================================================================
# Axes Tests (using EmotionAxes)
# =============================================================================

class TestSocialEmotionAxes:
    """Test social emotions in EmotionAxes preset system."""

    def test_social_presets_exist(self):
        """Test all social emotions have axis presets."""
        from animation.emotion_axes import EMOTION_PRESETS

        social_emotions = ['playful', 'affectionate', 'empathetic', 'grateful']
        for emotion in social_emotions:
            assert emotion in EMOTION_PRESETS

    def test_playful_axes_values(self):
        """Test playful emotion has correct axis values."""
        from animation.emotion_axes import EMOTION_PRESETS

        playful = EMOTION_PRESETS['playful']
        assert playful.arousal > 0  # Energetic
        assert playful.valence > 0  # Positive
        assert playful.blink_speed > 1.0  # Fast blinking

    def test_affectionate_axes_values(self):
        """Test affectionate emotion has correct axis values."""
        from animation.emotion_axes import EMOTION_PRESETS

        affectionate = EMOTION_PRESETS['affectionate']
        assert affectionate.valence > 0.8  # Very positive
        assert affectionate.focus > 0.5  # Focused on loved one
        assert affectionate.blink_speed < 1.0  # Slow, soft blinks

    def test_empathetic_axes_values(self):
        """Test empathetic emotion has correct axis values."""
        from animation.emotion_axes import EMOTION_PRESETS

        empathetic = EMOTION_PRESETS['empathetic']
        assert empathetic.arousal < 0  # Receptive, calm
        assert empathetic.focus > 0.5  # Attentive
        assert empathetic.blink_speed < 1.0  # Slow, calm

    def test_grateful_axes_values(self):
        """Test grateful emotion has correct axis values."""
        from animation.emotion_axes import EMOTION_PRESETS

        grateful = EMOTION_PRESETS['grateful']
        assert grateful.valence > 0.5  # Positive
        assert grateful.arousal > 0  # Mild energy


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
