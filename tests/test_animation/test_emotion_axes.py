#!/usr/bin/env python3
"""
Pixar 4-Axis Emotion System Tests
OpenDuck Mini V3 | Week 02 Day 9

Comprehensive test suite for EmotionAxes and AxisToLEDMapper:
- EmotionAxes validation (10 tests)
- Interpolation correctness (10 tests)
- HSV conversion (10 tests)
- Preset validity (5 tests)
- Edge cases (5 tests)

Total: 40 tests

Run with: pytest tests/test_animation/test_emotion_axes.py -v
(from firmware/ directory)

Author: Animation Systems Architect (Agent 2)
Created: 18 January 2026
"""

import pytest
import sys
import math
from pathlib import Path

# Add firmware/src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'src'))

from animation.emotion_axes import EmotionAxes, EMOTION_PRESETS
from animation.axis_to_led import (
    AxisToLEDMapper,
    validate_pattern_name,
    hsv_to_rgb,
    AVAILABLE_PATTERNS,
)


# =============================================================================
# Section 1: EmotionAxes Validation Tests (10 tests)
# =============================================================================

class TestEmotionAxesValidation:
    """Test EmotionAxes dataclass validation."""

    def test_valid_emotion_axes_creation(self):
        """Test creating valid EmotionAxes with typical values."""
        axes = EmotionAxes(arousal=0.5, valence=0.3, focus=0.7, blink_speed=1.2)

        assert axes.arousal == 0.5
        assert axes.valence == 0.3
        assert axes.focus == 0.7
        assert axes.blink_speed == 1.2

    def test_arousal_min_boundary(self):
        """Test arousal at minimum boundary (-1.0)."""
        axes = EmotionAxes(arousal=-1.0, valence=0.0, focus=0.5, blink_speed=1.0)
        assert axes.arousal == -1.0

    def test_arousal_max_boundary(self):
        """Test arousal at maximum boundary (+1.0)."""
        axes = EmotionAxes(arousal=1.0, valence=0.0, focus=0.5, blink_speed=1.0)
        assert axes.arousal == 1.0

    def test_arousal_out_of_range_raises_error(self):
        """Test arousal outside valid range raises ValueError."""
        with pytest.raises(ValueError, match="arousal must be -1.0 to 1.0"):
            EmotionAxes(arousal=1.5, valence=0.0, focus=0.5, blink_speed=1.0)

        with pytest.raises(ValueError, match="arousal must be -1.0 to 1.0"):
            EmotionAxes(arousal=-1.5, valence=0.0, focus=0.5, blink_speed=1.0)

    def test_valence_boundaries(self):
        """Test valence at min and max boundaries."""
        axes_min = EmotionAxes(arousal=0.0, valence=-1.0, focus=0.5, blink_speed=1.0)
        axes_max = EmotionAxes(arousal=0.0, valence=1.0, focus=0.5, blink_speed=1.0)

        assert axes_min.valence == -1.0
        assert axes_max.valence == 1.0

    def test_focus_boundaries(self):
        """Test focus at min (0.0) and max (1.0) boundaries."""
        axes_min = EmotionAxes(arousal=0.0, valence=0.0, focus=0.0, blink_speed=1.0)
        axes_max = EmotionAxes(arousal=0.0, valence=0.0, focus=1.0, blink_speed=1.0)

        assert axes_min.focus == 0.0
        assert axes_max.focus == 1.0

    def test_focus_out_of_range_raises_error(self):
        """Test focus outside valid range raises ValueError."""
        with pytest.raises(ValueError, match="focus must be 0.0 to 1.0"):
            EmotionAxes(arousal=0.0, valence=0.0, focus=-0.1, blink_speed=1.0)

        with pytest.raises(ValueError, match="focus must be 0.0 to 1.0"):
            EmotionAxes(arousal=0.0, valence=0.0, focus=1.5, blink_speed=1.0)

    def test_blink_speed_boundaries(self):
        """Test blink_speed at min (0.25) and max (2.0) boundaries."""
        axes_min = EmotionAxes(arousal=0.0, valence=0.0, focus=0.5, blink_speed=0.25)
        axes_max = EmotionAxes(arousal=0.0, valence=0.0, focus=0.5, blink_speed=2.0)

        assert axes_min.blink_speed == 0.25
        assert axes_max.blink_speed == 2.0

    def test_blink_speed_out_of_range_raises_error(self):
        """Test blink_speed outside valid range raises ValueError."""
        with pytest.raises(ValueError, match="blink_speed must be 0.25 to 2.0"):
            EmotionAxes(arousal=0.0, valence=0.0, focus=0.5, blink_speed=0.1)

        with pytest.raises(ValueError, match="blink_speed must be 0.25 to 2.0"):
            EmotionAxes(arousal=0.0, valence=0.0, focus=0.5, blink_speed=3.0)

    def test_non_numeric_values_raise_type_error(self):
        """Test that non-numeric values raise TypeError."""
        with pytest.raises(TypeError, match="arousal must be numeric"):
            EmotionAxes(arousal="high", valence=0.0, focus=0.5, blink_speed=1.0)

        with pytest.raises(TypeError, match="valence must be numeric"):
            EmotionAxes(arousal=0.0, valence=None, focus=0.5, blink_speed=1.0)

    def test_boolean_arousal_rejected(self):
        """Boolean values should raise TypeError for arousal (bool is subclass of int)."""
        with pytest.raises(TypeError, match="arousal cannot be bool"):
            EmotionAxes(arousal=True, valence=0.0, focus=0.5, blink_speed=1.0)

        with pytest.raises(TypeError, match="arousal cannot be bool"):
            EmotionAxes(arousal=False, valence=0.0, focus=0.5, blink_speed=1.0)

    def test_boolean_valence_rejected(self):
        """Boolean values should raise TypeError for valence."""
        with pytest.raises(TypeError, match="valence cannot be bool"):
            EmotionAxes(arousal=0.0, valence=True, focus=0.5, blink_speed=1.0)

    def test_boolean_focus_rejected(self):
        """Boolean values should raise TypeError for focus."""
        with pytest.raises(TypeError, match="focus cannot be bool"):
            EmotionAxes(arousal=0.0, valence=0.0, focus=True, blink_speed=1.0)

    def test_boolean_blink_speed_rejected(self):
        """Boolean values should raise TypeError for blink_speed."""
        with pytest.raises(TypeError, match="blink_speed cannot be bool"):
            EmotionAxes(arousal=0.0, valence=0.0, focus=0.5, blink_speed=True)


# =============================================================================
# Section 2: Interpolation Correctness Tests (10 tests)
# =============================================================================

class TestEmotionAxesInterpolation:
    """Test EmotionAxes interpolation method."""

    def test_interpolate_t_zero_returns_self(self):
        """Interpolation with t=0.0 returns original values."""
        start = EmotionAxes(arousal=-0.5, valence=0.0, focus=0.3, blink_speed=0.5)
        end = EmotionAxes(arousal=0.8, valence=0.6, focus=0.9, blink_speed=1.5)

        result = start.interpolate(end, 0.0)

        assert result.arousal == start.arousal
        assert result.valence == start.valence
        assert result.focus == start.focus
        assert result.blink_speed == start.blink_speed

    def test_interpolate_t_one_returns_target(self):
        """Interpolation with t=1.0 returns target values."""
        start = EmotionAxes(arousal=-0.5, valence=0.0, focus=0.3, blink_speed=0.5)
        end = EmotionAxes(arousal=0.8, valence=0.6, focus=0.9, blink_speed=1.5)

        result = start.interpolate(end, 1.0)

        # Use pytest.approx for floating point comparisons
        assert result.arousal == pytest.approx(end.arousal, abs=0.0001)
        assert result.valence == pytest.approx(end.valence, abs=0.0001)
        assert result.focus == pytest.approx(end.focus, abs=0.0001)
        assert result.blink_speed == pytest.approx(end.blink_speed, abs=0.0001)

    def test_interpolate_t_half_returns_midpoint(self):
        """Interpolation with t=0.5 returns midpoint."""
        start = EmotionAxes(arousal=-0.5, valence=0.0, focus=0.3, blink_speed=0.5)
        end = EmotionAxes(arousal=0.8, valence=0.6, focus=0.9, blink_speed=1.5)

        result = start.interpolate(end, 0.5)

        # Midpoint calculation: start + (end - start) * 0.5
        assert result.arousal == pytest.approx(0.15, abs=0.001)  # (-0.5 + 0.8) / 2
        assert result.valence == pytest.approx(0.3, abs=0.001)   # (0.0 + 0.6) / 2
        assert result.focus == pytest.approx(0.6, abs=0.001)     # (0.3 + 0.9) / 2
        assert result.blink_speed == pytest.approx(1.0, abs=0.001)  # (0.5 + 1.5) / 2

    def test_interpolate_quarter_way(self):
        """Interpolation with t=0.25 returns quarter-way point."""
        start = EmotionAxes(arousal=0.0, valence=0.0, focus=0.0, blink_speed=1.0)
        end = EmotionAxes(arousal=1.0, valence=1.0, focus=1.0, blink_speed=2.0)

        result = start.interpolate(end, 0.25)

        assert result.arousal == pytest.approx(0.25, abs=0.001)
        assert result.valence == pytest.approx(0.25, abs=0.001)
        assert result.focus == pytest.approx(0.25, abs=0.001)
        assert result.blink_speed == pytest.approx(1.25, abs=0.001)

    def test_interpolate_negative_t_clamped_to_zero(self):
        """Negative t values are clamped to 0.0."""
        start = EmotionAxes(arousal=0.0, valence=0.0, focus=0.5, blink_speed=1.0)
        end = EmotionAxes(arousal=1.0, valence=1.0, focus=1.0, blink_speed=2.0)

        result = start.interpolate(end, -0.5)

        # Should behave as t=0.0
        assert result.arousal == start.arousal
        assert result.valence == start.valence

    def test_interpolate_t_greater_than_one_clamped(self):
        """t values greater than 1.0 are clamped to 1.0."""
        start = EmotionAxes(arousal=0.0, valence=0.0, focus=0.5, blink_speed=1.0)
        end = EmotionAxes(arousal=0.5, valence=0.5, focus=1.0, blink_speed=1.5)

        result = start.interpolate(end, 1.5)

        # Should behave as t=1.0
        assert result.arousal == end.arousal
        assert result.valence == end.valence

    def test_interpolate_returns_new_instance(self):
        """Interpolation creates new instance, doesn't mutate originals."""
        start = EmotionAxes(arousal=0.0, valence=0.0, focus=0.5, blink_speed=1.0)
        end = EmotionAxes(arousal=1.0, valence=1.0, focus=1.0, blink_speed=2.0)

        result = start.interpolate(end, 0.5)

        # Result is different object
        assert result is not start
        assert result is not end

        # Originals unchanged
        assert start.arousal == 0.0
        assert end.arousal == 1.0

    def test_interpolate_same_emotion_returns_same_values(self):
        """Interpolating between same emotion returns same values."""
        emotion = EmotionAxes(arousal=0.5, valence=0.5, focus=0.5, blink_speed=1.0)

        for t in [0.0, 0.25, 0.5, 0.75, 1.0]:
            result = emotion.interpolate(emotion, t)
            assert result.arousal == emotion.arousal
            assert result.valence == emotion.valence
            assert result.focus == emotion.focus
            assert result.blink_speed == emotion.blink_speed

    def test_interpolate_multiple_steps(self):
        """Sequential interpolations produce consistent results."""
        start = EmotionAxes(arousal=0.0, valence=0.0, focus=0.5, blink_speed=1.0)
        end = EmotionAxes(arousal=1.0, valence=1.0, focus=1.0, blink_speed=2.0)

        # Interpolate in two steps: 0 -> 0.5 -> 1.0
        halfway = start.interpolate(end, 0.5)
        final = halfway.interpolate(end, 1.0)

        # Final should match end
        assert final.arousal == pytest.approx(end.arousal, abs=0.001)
        assert final.valence == pytest.approx(end.valence, abs=0.001)

    def test_interpolate_preset_emotions(self):
        """Test interpolation between preset emotions."""
        idle = EMOTION_PRESETS["idle"]
        excited = EMOTION_PRESETS["excited"]

        midpoint = idle.interpolate(excited, 0.5)

        # Midpoint should be valid EmotionAxes
        assert -1.0 <= midpoint.arousal <= 1.0
        assert -1.0 <= midpoint.valence <= 1.0
        assert 0.0 <= midpoint.focus <= 1.0
        assert 0.25 <= midpoint.blink_speed <= 2.0


# =============================================================================
# Section 3: HSV Conversion Tests (10 tests)
# =============================================================================

class TestEmotionAxesToHSV:
    """Test EmotionAxes to HSV color conversion."""

    def test_to_hsv_returns_tuple(self):
        """to_hsv() returns (hue, saturation, value) tuple."""
        axes = EmotionAxes(arousal=0.0, valence=0.0, focus=0.5, blink_speed=1.0)
        result = axes.to_hsv()

        assert isinstance(result, tuple)
        assert len(result) == 3

    def test_to_hsv_hue_range(self):
        """Hue is in valid range 0-360 degrees."""
        for valence in [-1.0, -0.5, 0.0, 0.5, 1.0]:
            axes = EmotionAxes(arousal=0.0, valence=valence, focus=0.5, blink_speed=1.0)
            hue, _, _ = axes.to_hsv()

            assert 0 <= hue < 360, f"Hue {hue} out of range for valence {valence}"

    def test_to_hsv_saturation_range(self):
        """Saturation is in valid range 0.3-1.0 (never fully desaturated)."""
        for focus in [0.0, 0.25, 0.5, 0.75, 1.0]:
            axes = EmotionAxes(arousal=0.0, valence=0.0, focus=focus, blink_speed=1.0)
            _, saturation, _ = axes.to_hsv()

            assert 0.3 <= saturation <= 1.0, f"Saturation {saturation} out of range for focus {focus}"

    def test_to_hsv_value_range(self):
        """Value/brightness is in valid range 0.4-1.0 (never fully dark)."""
        for arousal in [-1.0, -0.5, 0.0, 0.5, 1.0]:
            axes = EmotionAxes(arousal=arousal, valence=0.0, focus=0.5, blink_speed=1.0)
            _, _, value = axes.to_hsv()

            assert 0.4 <= value <= 1.0, f"Value {value} out of range for arousal {arousal}"

    def test_negative_valence_produces_blue_hue(self):
        """Negative valence produces cool (blue) hue around 240 degrees."""
        axes = EmotionAxes(arousal=0.0, valence=-1.0, focus=0.5, blink_speed=1.0)
        hue, _, _ = axes.to_hsv()

        # Negative valence should produce blue (around 240 degrees)
        assert 200 <= hue <= 260, f"Negative valence should produce blue, got hue={hue}"

    def test_positive_valence_produces_warm_hue(self):
        """Positive valence produces warm (orange/yellow) hue around 30-60 degrees."""
        axes = EmotionAxes(arousal=0.0, valence=1.0, focus=0.5, blink_speed=1.0)
        hue, _, _ = axes.to_hsv()

        # Positive valence should produce warm colors (orange ~30 degrees)
        assert 0 <= hue <= 60 or hue >= 330, f"Positive valence should produce warm colors, got hue={hue}"

    def test_low_focus_produces_low_saturation(self):
        """Low focus produces low (but minimum 0.3) saturation."""
        axes = EmotionAxes(arousal=0.0, valence=0.0, focus=0.0, blink_speed=1.0)
        _, saturation, _ = axes.to_hsv()

        assert saturation == pytest.approx(0.3, abs=0.01)

    def test_high_focus_produces_high_saturation(self):
        """High focus produces high saturation (1.0)."""
        axes = EmotionAxes(arousal=0.0, valence=0.0, focus=1.0, blink_speed=1.0)
        _, saturation, _ = axes.to_hsv()

        assert saturation == pytest.approx(1.0, abs=0.01)

    def test_low_arousal_produces_dim_value(self):
        """Low arousal produces dim (but minimum 0.4) value."""
        axes = EmotionAxes(arousal=-1.0, valence=0.0, focus=0.5, blink_speed=1.0)
        _, _, value = axes.to_hsv()

        assert value == pytest.approx(0.4, abs=0.01)

    def test_high_arousal_produces_bright_value(self):
        """High arousal produces bright value (1.0)."""
        axes = EmotionAxes(arousal=1.0, valence=0.0, focus=0.5, blink_speed=1.0)
        _, _, value = axes.to_hsv()

        assert value == pytest.approx(1.0, abs=0.01)


# =============================================================================
# Section 4: Preset Validity Tests (5 tests)
# =============================================================================

class TestEmotionPresets:
    """Test EMOTION_PRESETS dictionary."""

    def test_all_13_presets_exist(self):
        """Verify all 13 emotion presets are defined."""
        expected_presets = [
            # Basic emotions (8)
            "idle", "happy", "excited", "curious", "alert", "sad", "sleepy", "thinking",
            # Compound emotions (5)
            "anxious", "confused", "playful", "determined", "dreamy",
        ]

        for preset_name in expected_presets:
            assert preset_name in EMOTION_PRESETS, f"Missing preset: {preset_name}"

        # Updated: 8 basic + 8 compound/extended + 3 social (Agent 2) = 19
        # Note: Agent 3 added surprised, frustrated, proud; Agent 2 added affectionate, empathetic, grateful
        assert len(EMOTION_PRESETS) >= 19, f"Expected at least 19 presets, got {len(EMOTION_PRESETS)}"

    def test_all_presets_are_valid_emotion_axes(self):
        """All presets should be valid EmotionAxes instances."""
        for name, preset in EMOTION_PRESETS.items():
            assert isinstance(preset, EmotionAxes), f"Preset {name} is not EmotionAxes"

            # Validate ranges
            assert -1.0 <= preset.arousal <= 1.0, f"{name}.arousal out of range"
            assert -1.0 <= preset.valence <= 1.0, f"{name}.valence out of range"
            assert 0.0 <= preset.focus <= 1.0, f"{name}.focus out of range"
            assert 0.25 <= preset.blink_speed <= 2.0, f"{name}.blink_speed out of range"

    def test_preset_arousal_valence_quadrants(self):
        """Presets should cover all four arousal-valence quadrants."""
        # High arousal + positive valence (excited)
        excited = EMOTION_PRESETS["excited"]
        assert excited.arousal > 0.5 and excited.valence > 0.5

        # Low arousal + negative valence (sad)
        sad = EMOTION_PRESETS["sad"]
        assert sad.arousal < 0 and sad.valence < 0

        # High arousal + negative valence (anxious)
        anxious = EMOTION_PRESETS["anxious"]
        assert anxious.arousal > 0 and anxious.valence < 0

        # Low arousal + positive valence (dreamy)
        dreamy = EMOTION_PRESETS["dreamy"]
        assert dreamy.arousal < 0 and dreamy.valence > 0

    def test_idle_preset_is_neutral(self):
        """Idle preset should be approximately neutral."""
        idle = EMOTION_PRESETS["idle"]

        assert -0.5 <= idle.arousal <= 0.5  # Near neutral arousal
        assert -0.5 <= idle.valence <= 0.5  # Near neutral valence

    def test_presets_produce_valid_hsv(self):
        """All presets should produce valid HSV colors."""
        for name, preset in EMOTION_PRESETS.items():
            hue, sat, val = preset.to_hsv()

            assert 0 <= hue < 360, f"{name} hue {hue} out of range"
            assert 0.3 <= sat <= 1.0, f"{name} saturation {sat} out of range"
            assert 0.4 <= val <= 1.0, f"{name} value {val} out of range"


# =============================================================================
# Section 5: AxisToLEDMapper Tests (5 tests)
# =============================================================================

class TestAxisToLEDMapper:
    """Test AxisToLEDMapper class."""

    @pytest.fixture
    def mapper(self):
        """Create mapper instance for tests."""
        return AxisToLEDMapper()

    def test_pattern_selection_by_arousal(self, mapper):
        """Pattern selection follows arousal-based rules."""
        # Very low arousal -> breathing
        sleepy = EmotionAxes(arousal=-0.9, valence=0.0, focus=0.5, blink_speed=1.0)
        assert mapper.axes_to_pattern_name(sleepy) in ["breathing", "dream"]

        # High arousal -> fire
        excited = EmotionAxes(arousal=0.9, valence=0.5, focus=0.7, blink_speed=1.5)
        assert mapper.axes_to_pattern_name(excited) == "fire"

        # Moderate arousal -> spin or cloud
        curious = EmotionAxes(arousal=0.3, valence=0.4, focus=0.6, blink_speed=1.1)
        assert mapper.axes_to_pattern_name(curious) in ["spin", "cloud"]

    def test_pattern_names_are_valid(self, mapper):
        """All returned pattern names should be in AVAILABLE_PATTERNS."""
        test_cases = [
            EmotionAxes(arousal=-0.9, valence=0.0, focus=0.5, blink_speed=1.0),
            EmotionAxes(arousal=-0.4, valence=0.0, focus=0.5, blink_speed=1.0),
            EmotionAxes(arousal=0.0, valence=0.0, focus=0.5, blink_speed=1.0),
            EmotionAxes(arousal=0.4, valence=0.0, focus=0.5, blink_speed=1.0),
            EmotionAxes(arousal=0.7, valence=0.0, focus=0.5, blink_speed=1.0),
            EmotionAxes(arousal=0.95, valence=0.0, focus=0.5, blink_speed=1.0),
        ]

        for axes in test_cases:
            pattern = mapper.axes_to_pattern_name(axes)
            assert validate_pattern_name(pattern), f"Invalid pattern: {pattern}"

    def test_pattern_speed_driven_by_focus(self, mapper):
        """Pattern speed should increase with focus."""
        low_focus = EmotionAxes(arousal=0.0, valence=0.0, focus=0.0, blink_speed=1.0)
        high_focus = EmotionAxes(arousal=0.0, valence=0.0, focus=1.0, blink_speed=1.0)

        low_speed = mapper.axes_to_pattern_speed(low_focus)
        high_speed = mapper.axes_to_pattern_speed(high_focus)

        assert high_speed > low_speed, "Higher focus should produce higher speed"

    def test_led_config_contains_all_keys(self, mapper):
        """axes_to_led_config returns dict with all required keys."""
        axes = EmotionAxes(arousal=0.5, valence=0.5, focus=0.5, blink_speed=1.0)
        config = mapper.axes_to_led_config(axes)

        assert 'pattern_name' in config
        assert 'hsv' in config
        assert 'speed' in config

        assert isinstance(config['pattern_name'], str)
        assert isinstance(config['hsv'], tuple)
        assert len(config['hsv']) == 3
        assert isinstance(config['speed'], float)

    def test_hsv_to_rgb_conversion(self):
        """Test hsv_to_rgb utility function."""
        # Pure red (hue=0, full saturation, full value)
        r, g, b = hsv_to_rgb(0.0, 1.0, 1.0)
        assert r == 255 and g == 0 and b == 0

        # Pure green (hue=120)
        r, g, b = hsv_to_rgb(120.0, 1.0, 1.0)
        assert r == 0 and g == 255 and b == 0

        # Pure blue (hue=240)
        r, g, b = hsv_to_rgb(240.0, 1.0, 1.0)
        assert r == 0 and g == 0 and b == 255

        # White (no saturation)
        r, g, b = hsv_to_rgb(0.0, 0.0, 1.0)
        assert r == 255 and g == 255 and b == 255


# =============================================================================
# Section 6: Edge Cases (5 tests)
# =============================================================================

class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_nan_values_rejected(self):
        """NaN values should raise ValueError."""
        with pytest.raises(ValueError, match="must be finite"):
            EmotionAxes(arousal=float('nan'), valence=0.0, focus=0.5, blink_speed=1.0)

    def test_inf_values_rejected(self):
        """Infinite values should raise ValueError."""
        with pytest.raises(ValueError, match="must be finite"):
            EmotionAxes(arousal=float('inf'), valence=0.0, focus=0.5, blink_speed=1.0)

        with pytest.raises(ValueError, match="must be finite"):
            EmotionAxes(arousal=float('-inf'), valence=0.0, focus=0.5, blink_speed=1.0)

    def test_integer_values_accepted(self):
        """Integer values should be accepted (coerced to float)."""
        axes = EmotionAxes(arousal=0, valence=0, focus=1, blink_speed=1)

        assert axes.arousal == 0
        assert axes.valence == 0
        assert axes.focus == 1
        assert axes.blink_speed == 1

    def test_repr_format(self):
        """__repr__ should return readable string."""
        axes = EmotionAxes(arousal=0.5, valence=-0.3, focus=0.7, blink_speed=1.2)
        repr_str = repr(axes)

        assert "EmotionAxes" in repr_str
        assert "arousal=0.50" in repr_str
        assert "valence=-0.30" in repr_str
        assert "focus=0.70" in repr_str
        assert "blink_speed=1.20" in repr_str

    def test_validate_pattern_name_utility(self):
        """Test validate_pattern_name utility function."""
        assert validate_pattern_name("breathing") is True
        assert validate_pattern_name("fire") is True
        assert validate_pattern_name("invalid_pattern") is False
        assert validate_pattern_name("") is False

        # With custom list
        custom_patterns = ["custom1", "custom2"]
        assert validate_pattern_name("custom1", custom_patterns) is True
        assert validate_pattern_name("breathing", custom_patterns) is False
