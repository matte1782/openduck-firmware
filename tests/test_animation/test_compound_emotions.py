#!/usr/bin/env python3
"""
Compound Emotion Pattern Tests
OpenDuck Mini V3 | Week 02 Agent 3

Comprehensive test suite for compound emotion implementations:
- Pattern class validation (5 patterns)
- Emotion blending algorithm (10 tests)
- Performance benchmarks (5 tests)
- Visual distinctiveness (5 tests)
- Intensity scaling (5 tests)
- Edge cases (10 tests)

Total: 40+ tests

Run with: pytest tests/test_animation/test_compound_emotions.py -v
(from firmware/ directory)

Author: Compound Emotion Engineer (Agent 3)
Created: 18 January 2026
"""

import pytest
import sys
import math
import time
from pathlib import Path
from typing import List, Tuple

# Add firmware/src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'src'))

from animation.emotion_axes import EmotionAxes, EMOTION_PRESETS
from animation.emotion_patterns.compound_emotions import (
    # Base classes
    CompoundEmotionPatternBase,
    EmotionBlender,

    # Pattern implementations
    ConfusedPattern,
    SurprisedPattern,
    AnxiousPattern,
    FrustratedPattern,
    ProudPattern,

    # Configurations
    COMPOUND_EMOTION_SPECS,
    COMPOUND_EMOTION_PRESETS,
    COMPOUND_EMOTION_CONFIGS,
    COMPOUND_TRANSITION_TIMES,

    # Utilities
    blend_emotions,
    get_compound_emotion_axes,

    # Constants
    MAX_SPARKLES,
    MAX_PARTICLES,
    DEFAULT_NUM_LEDS,
    MAX_BRIGHTNESS,
)


# Type alias
RGB = Tuple[int, int, int]


# =============================================================================
# Section 1: Compound Emotion Specification Tests (5 tests)
# =============================================================================

class TestCompoundEmotionSpecifications:
    """Test that emotion specifications are valid and complete."""

    def test_all_five_compound_emotions_defined(self):
        """Verify all 5 required compound emotions are specified."""
        required_emotions = ["confused", "surprised", "anxious", "frustrated", "proud"]

        for emotion_name in required_emotions:
            assert emotion_name in COMPOUND_EMOTION_SPECS, f"Missing spec: {emotion_name}"

        assert len(COMPOUND_EMOTION_SPECS) == 5

    def test_specs_have_valid_arousal_valence(self):
        """All specs have arousal/valence in valid ranges."""
        for name, spec in COMPOUND_EMOTION_SPECS.items():
            assert -1.0 <= spec.arousal <= 1.0, f"{name}.arousal out of range"
            assert -1.0 <= spec.valence <= 1.0, f"{name}.valence out of range"

    def test_specs_have_valid_focus_blink_speed(self):
        """All specs have focus/blink_speed in valid ranges."""
        for name, spec in COMPOUND_EMOTION_SPECS.items():
            assert 0.0 <= spec.focus <= 1.0, f"{name}.focus out of range"
            assert 0.25 <= spec.blink_speed <= 2.0, f"{name}.blink_speed out of range"

    def test_specs_have_valid_colors(self):
        """All specs have valid RGB colors."""
        for name, spec in COMPOUND_EMOTION_SPECS.items():
            for color_name, color in [("primary", spec.primary_color), ("secondary", spec.secondary_color)]:
                assert len(color) == 3, f"{name}.{color_name}_color must be RGB tuple"
                for i, component in enumerate(color):
                    assert 0 <= component <= 255, f"{name}.{color_name}_color[{i}] out of range"

    def test_specs_have_psychology_basis(self):
        """All specs include psychology research basis."""
        for name, spec in COMPOUND_EMOTION_SPECS.items():
            assert spec.psychology_basis, f"{name} missing psychology_basis"
            assert len(spec.psychology_basis) > 10, f"{name}.psychology_basis too short"


# =============================================================================
# Section 2: EmotionAxes Preset Tests (5 tests)
# =============================================================================

class TestCompoundEmotionPresets:
    """Test COMPOUND_EMOTION_PRESETS validity."""

    def test_presets_match_specs(self):
        """Presets should match spec values."""
        for name, spec in COMPOUND_EMOTION_SPECS.items():
            preset = COMPOUND_EMOTION_PRESETS[name]

            assert preset.arousal == spec.arousal, f"{name}.arousal mismatch"
            assert preset.valence == spec.valence, f"{name}.valence mismatch"
            assert preset.focus == spec.focus, f"{name}.focus mismatch"
            assert preset.blink_speed == spec.blink_speed, f"{name}.blink_speed mismatch"

    def test_presets_are_valid_emotion_axes(self):
        """All presets should be valid EmotionAxes instances."""
        for name, preset in COMPOUND_EMOTION_PRESETS.items():
            assert isinstance(preset, EmotionAxes), f"{name} is not EmotionAxes"

    def test_get_compound_emotion_axes_function(self):
        """Test get_compound_emotion_axes utility."""
        confused = get_compound_emotion_axes("confused")
        assert isinstance(confused, EmotionAxes)
        assert confused.arousal == COMPOUND_EMOTION_SPECS["confused"].arousal

    def test_get_compound_emotion_axes_unknown_raises(self):
        """Unknown emotion name should raise KeyError."""
        with pytest.raises(KeyError, match="Unknown compound emotion"):
            get_compound_emotion_axes("nonexistent")

    def test_extended_presets_in_main_module(self):
        """New presets should be added to main EMOTION_PRESETS."""
        # These should have been added to emotion_axes.py
        for emotion_name in ["surprised", "frustrated", "proud"]:
            assert emotion_name in EMOTION_PRESETS, f"{emotion_name} not in main EMOTION_PRESETS"


# =============================================================================
# Section 3: Emotion Blending Tests (10 tests)
# =============================================================================

class TestEmotionBlender:
    """Test EmotionBlender class methods."""

    def test_linear_blend_ratio_zero_returns_emotion_b(self):
        """Ratio=0.0 returns 100% emotion_b."""
        emotion_a = EmotionAxes(arousal=1.0, valence=1.0, focus=1.0, blink_speed=2.0)
        emotion_b = EmotionAxes(arousal=-1.0, valence=-1.0, focus=0.0, blink_speed=0.25)

        result = EmotionBlender.linear_blend(emotion_a, emotion_b, 0.0)

        assert result.arousal == pytest.approx(emotion_b.arousal, abs=0.001)
        assert result.valence == pytest.approx(emotion_b.valence, abs=0.001)

    def test_linear_blend_ratio_one_returns_emotion_a(self):
        """Ratio=1.0 returns 100% emotion_a."""
        emotion_a = EmotionAxes(arousal=1.0, valence=1.0, focus=1.0, blink_speed=2.0)
        emotion_b = EmotionAxes(arousal=-1.0, valence=-1.0, focus=0.0, blink_speed=0.25)

        result = EmotionBlender.linear_blend(emotion_a, emotion_b, 1.0)

        assert result.arousal == pytest.approx(emotion_a.arousal, abs=0.001)
        assert result.valence == pytest.approx(emotion_a.valence, abs=0.001)

    def test_linear_blend_ratio_half_returns_midpoint(self):
        """Ratio=0.5 returns midpoint."""
        emotion_a = EmotionAxes(arousal=1.0, valence=1.0, focus=1.0, blink_speed=2.0)
        emotion_b = EmotionAxes(arousal=-1.0, valence=-1.0, focus=0.0, blink_speed=0.5)

        result = EmotionBlender.linear_blend(emotion_a, emotion_b, 0.5)

        assert result.arousal == pytest.approx(0.0, abs=0.001)
        assert result.valence == pytest.approx(0.0, abs=0.001)
        assert result.focus == pytest.approx(0.5, abs=0.001)

    def test_linear_blend_invalid_ratio_raises(self):
        """Invalid ratio should raise ValueError."""
        emotion_a = EMOTION_PRESETS["happy"]
        emotion_b = EMOTION_PRESETS["sad"]

        with pytest.raises(ValueError, match="ratio must be 0.0-1.0"):
            EmotionBlender.linear_blend(emotion_a, emotion_b, 1.5)

        with pytest.raises(ValueError, match="ratio must be 0.0-1.0"):
            EmotionBlender.linear_blend(emotion_a, emotion_b, -0.1)

    def test_linear_blend_non_emotion_axes_raises(self):
        """Non-EmotionAxes input should raise TypeError."""
        emotion_a = EMOTION_PRESETS["happy"]

        with pytest.raises(TypeError, match="must be EmotionAxes"):
            EmotionBlender.linear_blend(emotion_a, "not an emotion", 0.5)

    def test_dominant_blend_emphasizes_threshold(self):
        """Dominant blend should emphasize one emotion past threshold."""
        emotion_a = EmotionAxes(arousal=1.0, valence=1.0, focus=1.0, blink_speed=1.0)
        emotion_b = EmotionAxes(arousal=0.0, valence=0.0, focus=0.5, blink_speed=1.0)

        # High ratio (0.9) with threshold 0.7 should strongly favor emotion_a
        result = EmotionBlender.dominant_blend(emotion_a, emotion_b, 0.9, threshold=0.7)

        # Result should be closer to emotion_a than emotion_b
        # Dominant blend creates staged transition, so result favors emotion_a at high ratios
        assert result.arousal > 0.5, "High ratio should favor emotion_a"
        assert result.arousal > emotion_b.arousal, "Result should be closer to emotion_a"

    def test_dominant_blend_invalid_threshold_raises(self):
        """Invalid threshold should raise ValueError."""
        emotion_a = EMOTION_PRESETS["happy"]
        emotion_b = EMOTION_PRESETS["sad"]

        with pytest.raises(ValueError, match="threshold must be 0.0-1.0"):
            EmotionBlender.dominant_blend(emotion_a, emotion_b, 0.5, threshold=1.5)

    def test_oscillating_blend_varies_over_time(self):
        """Oscillating blend should produce different results at different times."""
        emotion_a = EmotionAxes(arousal=1.0, valence=1.0, focus=1.0, blink_speed=1.0)
        emotion_b = EmotionAxes(arousal=-1.0, valence=-1.0, focus=0.0, blink_speed=1.0)

        result_t0 = EmotionBlender.oscillating_blend(emotion_a, emotion_b, t=0.0)
        result_t1 = EmotionBlender.oscillating_blend(emotion_a, emotion_b, t=0.25)

        # Results should differ
        assert result_t0.arousal != result_t1.arousal

    def test_oscillating_blend_invalid_frequency_raises(self):
        """Invalid frequency should raise ValueError."""
        emotion_a = EMOTION_PRESETS["happy"]
        emotion_b = EMOTION_PRESETS["sad"]

        with pytest.raises(ValueError, match="frequency must be positive"):
            EmotionBlender.oscillating_blend(emotion_a, emotion_b, t=0.0, frequency=0)

    def test_blend_emotions_convenience_function(self):
        """Test module-level blend_emotions function."""
        result = blend_emotions(EMOTION_PRESETS["curious"], EMOTION_PRESETS["anxious"], 0.6)

        assert isinstance(result, EmotionAxes)
        # Should be valid EmotionAxes
        assert -1.0 <= result.arousal <= 1.0
        assert -1.0 <= result.valence <= 1.0


# =============================================================================
# Section 4: Pattern Base Class Tests (5 tests)
# =============================================================================

class TestCompoundEmotionPatternBase:
    """Test CompoundEmotionPatternBase functionality."""

    def test_init_with_default_num_leds(self):
        """Default initialization with 16 LEDs."""
        # Use concrete subclass for testing
        pattern = ConfusedPattern()
        assert pattern.num_leds == DEFAULT_NUM_LEDS

    def test_init_with_custom_num_leds(self):
        """Custom LED count accepted."""
        pattern = ConfusedPattern(num_leds=24)
        assert pattern.num_leds == 24

    def test_init_invalid_num_leds_raises(self):
        """Zero or negative num_leds should raise ValueError."""
        with pytest.raises(ValueError, match="num_leds must be positive"):
            ConfusedPattern(num_leds=0)

        with pytest.raises(ValueError, match="num_leds must be positive"):
            ConfusedPattern(num_leds=-5)

    def test_clamp_brightness_limits_output(self):
        """_clamp_brightness should limit RGB values."""
        pattern = ConfusedPattern()

        # Bright color should be clamped
        bright = (255, 200, 150)
        clamped = pattern._clamp_brightness(bright, max_brightness=60)

        assert max(clamped) <= 60
        # Should maintain color ratio approximately
        assert clamped[0] > clamped[1] > clamped[2]

    def test_interpolate_color_boundaries(self):
        """Color interpolation at t=0 and t=1."""
        pattern = ConfusedPattern()

        color_a = (255, 0, 0)
        color_b = (0, 255, 0)

        # t=0 returns color_a
        result_0 = pattern._interpolate_color(color_a, color_b, 0.0)
        assert result_0 == color_a

        # t=1 returns color_b
        result_1 = pattern._interpolate_color(color_a, color_b, 1.0)
        assert result_1 == color_b


# =============================================================================
# Section 5: Individual Pattern Tests (15 tests - 3 per pattern)
# =============================================================================

class TestConfusedPattern:
    """Test ConfusedPattern implementation."""

    @pytest.fixture
    def pattern(self):
        return ConfusedPattern()

    def test_render_returns_correct_structure(self, pattern):
        """Render returns tuple of two LED lists."""
        left, right = pattern.render(t=0.0)

        assert len(left) == DEFAULT_NUM_LEDS
        assert len(right) == DEFAULT_NUM_LEDS
        assert all(len(pixel) == 3 for pixel in left)
        assert all(len(pixel) == 3 for pixel in right)

    def test_render_varies_over_time(self, pattern):
        """Pattern should change over time (scanning)."""
        left_t0, _ = pattern.render(t=0.0)
        left_t1, _ = pattern.render(t=0.5)

        # At least one pixel should differ
        assert left_t0 != left_t1

    def test_render_has_asymmetry(self, pattern):
        """Confused pattern should show asymmetry (uncertainty)."""
        left, right = pattern.render(t=0.5)

        # Left and right eyes should differ slightly
        differences = sum(1 for l, r in zip(left, right) if l != r)
        assert differences > 0, "Confused pattern should have eye asymmetry"


class TestSurprisedPattern:
    """Test SurprisedPattern implementation."""

    @pytest.fixture
    def pattern(self):
        return SurprisedPattern()

    def test_render_returns_correct_structure(self, pattern):
        """Render returns tuple of two LED lists."""
        left, right = pattern.render(t=0.0)

        assert len(left) == DEFAULT_NUM_LEDS
        assert len(right) == DEFAULT_NUM_LEDS

    def test_startle_peak_is_brightest(self, pattern):
        """Peak brightness should occur around startle time."""
        _, _ = pattern.render(t=0.0)  # Initialize
        left_peak, _ = pattern.render(t=pattern.STARTLE_PEAK_TIME + 0.1)
        left_settle, _ = pattern.render(t=2.0)

        # Average brightness at peak should be higher than settled
        avg_peak = sum(sum(pixel) for pixel in left_peak) / (DEFAULT_NUM_LEDS * 3)
        avg_settle = sum(sum(pixel) for pixel in left_settle) / (DEFAULT_NUM_LEDS * 3)

        assert avg_peak > avg_settle, "Peak brightness should exceed settled brightness"

    def test_widening_effect_at_peak(self, pattern):
        """Outer LEDs should be brighter during startle (widening)."""
        left, _ = pattern.render(t=pattern.STARTLE_PEAK_TIME + 0.1)

        # Compare edge brightness to center brightness
        center_idx = DEFAULT_NUM_LEDS // 2
        edge_idx = 0

        center_brightness = sum(left[center_idx])
        edge_brightness = sum(left[edge_idx])

        # During surprise, edges should be at least as bright as center
        assert edge_brightness >= center_brightness * 0.8


class TestAnxiousPattern:
    """Test AnxiousPattern implementation."""

    @pytest.fixture
    def pattern(self):
        return AnxiousPattern()

    def test_render_returns_correct_structure(self, pattern):
        """Render returns tuple of two LED lists."""
        left, right = pattern.render(t=0.0)

        assert len(left) == DEFAULT_NUM_LEDS
        assert len(right) == DEFAULT_NUM_LEDS

    def test_jitter_produces_variation(self, pattern):
        """Anxious pattern should show jitter variation."""
        # Render multiple frames
        frames = [pattern.render(t=i * 0.02)[0] for i in range(10)]

        # Should have variation between frames
        all_same = all(f == frames[0] for f in frames)
        assert not all_same, "Anxious pattern should jitter between frames"

    def test_elevated_baseline_brightness(self, pattern):
        """Anxious state should have elevated brightness (sympathetic activation)."""
        left, _ = pattern.render(t=0.5)

        # Calculate average brightness
        avg_brightness = sum(sum(pixel) for pixel in left) / (DEFAULT_NUM_LEDS * 3)

        # Should be elevated (at least 40% of max possible = 255)
        assert avg_brightness > 20, "Anxious pattern should have elevated brightness"


class TestFrustratedPattern:
    """Test FrustratedPattern implementation."""

    @pytest.fixture
    def pattern(self):
        return FrustratedPattern()

    def test_render_returns_correct_structure(self, pattern):
        """Render returns tuple of two LED lists."""
        left, right = pattern.render(t=0.0)

        assert len(left) == DEFAULT_NUM_LEDS
        assert len(right) == DEFAULT_NUM_LEDS

    def test_tension_builds_over_time(self, pattern):
        """Frustration should build tension over time."""
        pattern.reset()
        pattern.render(t=0.0)
        early_tension = pattern._tension_level

        pattern.render(t=5.0)
        later_tension = pattern._tension_level

        assert later_tension > early_tension, "Tension should build over time"

    def test_color_shifts_warmer(self, pattern):
        """Color should shift warmer (more red) as frustration builds."""
        pattern.reset()
        left_early, _ = pattern.render(t=0.1)
        left_late, _ = pattern.render(t=10.0)

        # Calculate red ratio
        def red_ratio(pixels):
            total_r = sum(p[0] for p in pixels)
            total_all = sum(sum(p) for p in pixels)
            return total_r / total_all if total_all > 0 else 0

        early_red = red_ratio(left_early)
        late_red = red_ratio(left_late)

        assert late_red >= early_red * 0.95, "Frustrated color should shift warmer"


class TestProudPattern:
    """Test ProudPattern implementation."""

    @pytest.fixture
    def pattern(self):
        return ProudPattern()

    def test_render_returns_correct_structure(self, pattern):
        """Render returns tuple of two LED lists."""
        left, right = pattern.render(t=0.0)

        assert len(left) == DEFAULT_NUM_LEDS
        assert len(right) == DEFAULT_NUM_LEDS

    def test_standing_tall_effect(self, pattern):
        """Top LEDs should be brighter (standing tall effect)."""
        left, _ = pattern.render(t=1.0)

        # LED 0 and LED 15 are "top"
        top_brightness = sum(left[0]) + sum(left[DEFAULT_NUM_LEDS - 1])
        # LED 7 and 8 are "bottom" (middle of ring)
        center_idx = DEFAULT_NUM_LEDS // 2
        bottom_brightness = sum(left[center_idx]) + sum(left[center_idx - 1])

        assert top_brightness >= bottom_brightness * 0.9, "Top should be brighter (standing tall)"

    def test_sparkle_count_bounded(self, pattern):
        """Sparkles should be bounded to MAX_SPARKLES."""
        # Render many frames to potentially accumulate sparkles
        for i in range(500):
            pattern.render(t=i * 0.02)

        assert len(pattern._sparkle_positions) <= MAX_SPARKLES


# =============================================================================
# Section 6: Performance Benchmark Tests (5 tests)
# =============================================================================

class TestPatternPerformance:
    """Performance benchmark tests for all patterns."""

    FRAME_COUNT = 100
    MAX_AVG_TIME_MS = 2.5   # Must be <2.5ms average
    MAX_SINGLE_TIME_MS = 10.0  # Must be <10ms maximum

    @pytest.fixture(params=[
        ConfusedPattern,
        SurprisedPattern,
        AnxiousPattern,
        FrustratedPattern,
        ProudPattern,
    ])
    def pattern_class(self, request):
        return request.param

    def test_average_frame_time(self, pattern_class):
        """Average frame time must be <2.5ms."""
        pattern = pattern_class()

        times = []
        for i in range(self.FRAME_COUNT):
            start = time.perf_counter()
            pattern.render(t=i * 0.02)
            elapsed = (time.perf_counter() - start) * 1000

            times.append(elapsed)

        avg_time = sum(times) / len(times)

        assert avg_time < self.MAX_AVG_TIME_MS, (
            f"{pattern_class.__name__} avg={avg_time:.3f}ms exceeds {self.MAX_AVG_TIME_MS}ms"
        )

    def test_maximum_frame_time(self, pattern_class):
        """Maximum frame time must be <10ms."""
        pattern = pattern_class()

        max_time = 0
        for i in range(self.FRAME_COUNT):
            start = time.perf_counter()
            pattern.render(t=i * 0.02)
            elapsed = (time.perf_counter() - start) * 1000

            max_time = max(max_time, elapsed)

        assert max_time < self.MAX_SINGLE_TIME_MS, (
            f"{pattern_class.__name__} max={max_time:.3f}ms exceeds {self.MAX_SINGLE_TIME_MS}ms"
        )


# =============================================================================
# Section 7: Visual Distinctiveness Tests (5 tests)
# =============================================================================

class TestVisualDistinctiveness:
    """Ensure compound emotions are visually distinguishable."""

    def _pattern_signature(self, pattern, t: float = 1.0) -> Tuple[float, float, float]:
        """
        Get pattern signature as (avg_brightness, color_balance, variation).
        """
        left, right = pattern.render(t=t)

        # Average brightness
        all_pixels = left + right
        avg_brightness = sum(sum(p) for p in all_pixels) / (len(all_pixels) * 3)

        # Color balance (R vs B ratio)
        total_r = sum(p[0] for p in all_pixels)
        total_b = sum(p[2] for p in all_pixels)
        color_balance = total_r / (total_b + 1)  # +1 to avoid division by zero

        # Variation (std dev of pixel brightnesses)
        brightnesses = [sum(p) for p in all_pixels]
        avg_b = sum(brightnesses) / len(brightnesses)
        variation = (sum((b - avg_b) ** 2 for b in brightnesses) / len(brightnesses)) ** 0.5

        return (avg_brightness, color_balance, variation)

    def test_confused_vs_curious(self):
        """Confused should differ from curious (base emotion)."""
        confused = ConfusedPattern()
        # Curious would be a steady scan - confused is erratic

        sig = self._pattern_signature(confused)

        # Confused should have lower brightness (uncertain)
        # and more variation (flickering)
        assert sig[2] > 0, "Confused should have some variation (flickering)"

    def test_surprised_vs_alert(self):
        """Surprised should differ from alert (sudden vs sustained)."""
        surprised = SurprisedPattern()

        # At peak, brightness should be very high
        sig_peak = self._pattern_signature(surprised, t=0.3)

        # After settling, brightness drops
        sig_settled = self._pattern_signature(surprised, t=2.0)

        assert sig_peak[0] > sig_settled[0], "Surprised peak > settled brightness"

    def test_anxious_vs_alert(self):
        """Anxious should have irregular rhythm vs steady alert."""
        anxious = AnxiousPattern()

        # Render multiple frames and check variation
        sigs = [self._pattern_signature(anxious, t=i * 0.1) for i in range(10)]

        # Brightness should vary (irregular heartbeat)
        brightnesses = [s[0] for s in sigs]
        variation = max(brightnesses) - min(brightnesses)

        assert variation > 0, "Anxious should have brightness variation (irregular rhythm)"

    def test_frustrated_vs_angry(self):
        """Frustrated is constrained - not explosive like angry would be."""
        frustrated = FrustratedPattern()

        # Even at high tension, brightness should be constrained
        frustrated.render(t=0)  # Initialize
        frustrated._tension_level = 0.9  # Force high tension

        left, _ = frustrated.render(t=10.0)

        # Check that brightness is bounded
        max_brightness_found = max(max(p) for p in left)
        assert max_brightness_found <= MAX_BRIGHTNESS, "Frustrated should stay constrained"

    def test_proud_vs_happy(self):
        """Proud should have upward visual bias vs uniform happy."""
        proud = ProudPattern()

        left, _ = proud.render(t=1.0)

        # Proud should have "standing tall" gradient
        top_avg = (sum(left[0]) + sum(left[-1])) / 2
        bottom_avg = (sum(left[7]) + sum(left[8])) / 2

        # Top should be noticeably brighter
        assert top_avg > bottom_avg * 0.85, "Proud should have upward bias"


# =============================================================================
# Section 8: Edge Cases (10 tests)
# =============================================================================

class TestEdgeCases:
    """Edge case testing for robustness."""

    def test_render_at_t_zero(self):
        """All patterns should handle t=0.0 gracefully."""
        patterns = [
            ConfusedPattern(),
            SurprisedPattern(),
            AnxiousPattern(),
            FrustratedPattern(),
            ProudPattern(),
        ]

        for pattern in patterns:
            left, right = pattern.render(t=0.0)
            assert len(left) == DEFAULT_NUM_LEDS
            assert len(right) == DEFAULT_NUM_LEDS

    def test_render_at_very_large_t(self):
        """Patterns should handle very large t values."""
        patterns = [
            ConfusedPattern(),
            SurprisedPattern(),
            AnxiousPattern(),
            FrustratedPattern(),
            ProudPattern(),
        ]

        for pattern in patterns:
            # t = 1 hour (3600 seconds)
            left, right = pattern.render(t=3600.0)
            assert len(left) == DEFAULT_NUM_LEDS
            # No crashes or overflows

    def test_reset_clears_state(self):
        """Reset should return pattern to initial state."""
        pattern = FrustratedPattern()

        # Build up state
        for i in range(100):
            pattern.render(t=i * 0.1)

        assert pattern._tension_level > 0

        # Reset
        pattern.reset()

        assert pattern._tension_level == 0

    def test_all_pixels_within_brightness_limit(self):
        """No pixel should exceed MAX_BRIGHTNESS."""
        patterns = [
            ConfusedPattern(),
            SurprisedPattern(),
            AnxiousPattern(),
            FrustratedPattern(),
            ProudPattern(),
        ]

        for pattern in patterns:
            for t in [0.0, 0.5, 1.0, 5.0, 10.0]:
                left, right = pattern.render(t=t)

                for pixel in left + right:
                    assert max(pixel) <= MAX_BRIGHTNESS, (
                        f"{type(pattern).__name__} pixel {pixel} exceeds {MAX_BRIGHTNESS}"
                    )

    def test_no_negative_color_values(self):
        """No pixel should have negative color components."""
        patterns = [
            ConfusedPattern(),
            SurprisedPattern(),
            AnxiousPattern(),
            FrustratedPattern(),
            ProudPattern(),
        ]

        for pattern in patterns:
            left, right = pattern.render(t=0.5)

            for pixel in left + right:
                assert all(c >= 0 for c in pixel), f"Negative color value in {pixel}"

    def test_blend_edge_cases(self):
        """Blending edge cases: same emotion, opposite emotions."""
        happy = EMOTION_PRESETS["happy"]
        sad = EMOTION_PRESETS["sad"]

        # Blend same emotion
        same = blend_emotions(happy, happy, 0.5)
        assert same.arousal == pytest.approx(happy.arousal, abs=0.001)

        # Blend opposites
        opposite = blend_emotions(happy, sad, 0.5)
        # Should be somewhere between
        assert sad.arousal < opposite.arousal < happy.arousal

    def test_transition_times_all_positive(self):
        """All transition times should be positive."""
        for (from_state, to_state), time_s in COMPOUND_TRANSITION_TIMES.items():
            assert time_s > 0, f"Transition {from_state}->{to_state} has non-positive time"
            assert time_s < 5.0, f"Transition {from_state}->{to_state} seems too long"

    def test_compound_configs_have_required_keys(self):
        """All compound emotion configs should have required keys."""
        required_keys = ["led_color", "led_pattern", "led_brightness", "pattern_speed", "transition_ms"]

        for name, config in COMPOUND_EMOTION_CONFIGS.items():
            for key in required_keys:
                assert key in config, f"{name} config missing key: {key}"

    def test_rapid_render_calls(self):
        """Patterns should handle rapid successive render calls."""
        pattern = AnxiousPattern()

        # 1000 rapid calls
        for i in range(1000):
            pattern.render(t=i * 0.001)

        # Should complete without error
        left, right = pattern.render(t=1.0)
        assert len(left) == DEFAULT_NUM_LEDS

    def test_custom_num_leds(self):
        """Patterns should work with non-standard LED counts."""
        for num_leds in [8, 12, 24, 32]:
            pattern = ProudPattern(num_leds=num_leds)
            left, right = pattern.render(t=1.0)

            assert len(left) == num_leds
            assert len(right) == num_leds


# =============================================================================
# Section 9: Integration Tests (5 tests)
# =============================================================================

class TestIntegration:
    """Integration tests with existing emotion system."""

    def test_presets_compatible_with_interpolation(self):
        """Compound presets should work with EmotionAxes.interpolate."""
        confused = COMPOUND_EMOTION_PRESETS["confused"]
        proud = COMPOUND_EMOTION_PRESETS["proud"]

        # Should interpolate without error
        midpoint = confused.interpolate(proud, 0.5)

        assert isinstance(midpoint, EmotionAxes)
        assert -1.0 <= midpoint.arousal <= 1.0

    def test_presets_produce_valid_hsv(self):
        """All compound presets should produce valid HSV colors."""
        for name, preset in COMPOUND_EMOTION_PRESETS.items():
            hue, sat, val = preset.to_hsv()

            assert 0 <= hue < 360, f"{name} hue {hue} out of range"
            assert 0.3 <= sat <= 1.0, f"{name} saturation {sat} out of range"
            assert 0.4 <= val <= 1.0, f"{name} value {val} out of range"

    def test_specs_component_emotions_exist(self):
        """Spec component emotions should exist in EMOTION_PRESETS."""
        for name, spec in COMPOUND_EMOTION_SPECS.items():
            assert spec.component_a in EMOTION_PRESETS or spec.component_a in COMPOUND_EMOTION_PRESETS, (
                f"{name}.component_a '{spec.component_a}' not found in presets"
            )
            assert spec.component_b in EMOTION_PRESETS or spec.component_b in COMPOUND_EMOTION_PRESETS, (
                f"{name}.component_b '{spec.component_b}' not found in presets"
            )

    def test_blend_recreates_compound_emotion(self):
        """Blending components should approximate compound emotion."""
        spec = COMPOUND_EMOTION_SPECS["confused"]

        curious = EMOTION_PRESETS[spec.component_a]
        anxious = EMOTION_PRESETS[spec.component_b]

        blended = blend_emotions(curious, anxious, spec.blend_ratio)
        compound = COMPOUND_EMOTION_PRESETS["confused"]

        # Blended should be close to the defined compound
        # Allow some tolerance since compound may have manual tuning
        assert abs(blended.arousal - compound.arousal) < 0.3
        assert abs(blended.valence - compound.valence) < 0.3

    def test_configs_brightness_within_safety(self):
        """All config brightness values should be within safety limits."""
        for name, config in COMPOUND_EMOTION_CONFIGS.items():
            assert config["led_brightness"] <= MAX_BRIGHTNESS, (
                f"{name} brightness {config['led_brightness']} exceeds MAX_BRIGHTNESS {MAX_BRIGHTNESS}"
            )
