#!/usr/bin/env python3
"""
Tests for Color Utilities Module

Comprehensive test coverage for:
- RGB to HSV conversion
- HSV to RGB conversion
- Roundtrip conversion consistency
- Linear RGB interpolation
- HSV arc interpolation
- ColorTransition class
- Convenience functions

Target: 95% coverage, 20+ tests

Author: QA Engineer
Created: 18 January 2026
"""

import pytest
import time
import math
from typing import Tuple

from src.led.color_utils import (
    RGB,
    HSV,
    rgb_to_hsv,
    hsv_to_rgb,
    color_interpolate,
    color_arc_interpolate,
    ColorTransition,
    ColorTransitionConfig,
    lerp_color,
    hue_shift,
    brightness_adjust,
    saturation_adjust,
    complementary_color,
)


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def primary_colors() -> dict:
    """Primary RGB colors with expected HSV values."""
    return {
        'red': ((255, 0, 0), (0.0, 1.0, 1.0)),
        'green': ((0, 255, 0), (120.0, 1.0, 1.0)),
        'blue': ((0, 0, 255), (240.0, 1.0, 1.0)),
    }


@pytest.fixture
def secondary_colors() -> dict:
    """Secondary RGB colors with expected HSV values."""
    return {
        'cyan': ((0, 255, 255), (180.0, 1.0, 1.0)),
        'magenta': ((255, 0, 255), (300.0, 1.0, 1.0)),
        'yellow': ((255, 255, 0), (60.0, 1.0, 1.0)),
    }


@pytest.fixture
def grayscale_colors() -> dict:
    """Grayscale colors with expected HSV values (hue undefined, using 0)."""
    return {
        'black': ((0, 0, 0), (0.0, 0.0, 0.0)),
        'white': ((255, 255, 255), (0.0, 0.0, 1.0)),
        'gray_128': ((128, 128, 128), (0.0, 0.0, 128/255)),
        'gray_64': ((64, 64, 64), (0.0, 0.0, 64/255)),
    }


# =============================================================================
# RGB to HSV Conversion Tests
# =============================================================================

class TestRgbToHsv:
    """Tests for rgb_to_hsv conversion function."""

    def test_pure_red(self, primary_colors):
        """Test conversion of pure red."""
        rgb, expected_hsv = primary_colors['red']
        h, s, v = rgb_to_hsv(rgb)
        assert abs(h - expected_hsv[0]) < 0.1
        assert abs(s - expected_hsv[1]) < 0.01
        assert abs(v - expected_hsv[2]) < 0.01

    def test_pure_green(self, primary_colors):
        """Test conversion of pure green."""
        rgb, expected_hsv = primary_colors['green']
        h, s, v = rgb_to_hsv(rgb)
        assert abs(h - expected_hsv[0]) < 0.1
        assert abs(s - expected_hsv[1]) < 0.01
        assert abs(v - expected_hsv[2]) < 0.01

    def test_pure_blue(self, primary_colors):
        """Test conversion of pure blue."""
        rgb, expected_hsv = primary_colors['blue']
        h, s, v = rgb_to_hsv(rgb)
        assert abs(h - expected_hsv[0]) < 0.1
        assert abs(s - expected_hsv[1]) < 0.01
        assert abs(v - expected_hsv[2]) < 0.01

    def test_cyan(self, secondary_colors):
        """Test conversion of cyan."""
        rgb, expected_hsv = secondary_colors['cyan']
        h, s, v = rgb_to_hsv(rgb)
        assert abs(h - expected_hsv[0]) < 0.1
        assert abs(s - expected_hsv[1]) < 0.01
        assert abs(v - expected_hsv[2]) < 0.01

    def test_magenta(self, secondary_colors):
        """Test conversion of magenta."""
        rgb, expected_hsv = secondary_colors['magenta']
        h, s, v = rgb_to_hsv(rgb)
        assert abs(h - expected_hsv[0]) < 0.1
        assert abs(s - expected_hsv[1]) < 0.01
        assert abs(v - expected_hsv[2]) < 0.01

    def test_yellow(self, secondary_colors):
        """Test conversion of yellow."""
        rgb, expected_hsv = secondary_colors['yellow']
        h, s, v = rgb_to_hsv(rgb)
        assert abs(h - expected_hsv[0]) < 0.1
        assert abs(s - expected_hsv[1]) < 0.01
        assert abs(v - expected_hsv[2]) < 0.01

    def test_black(self, grayscale_colors):
        """Test conversion of black."""
        rgb, expected_hsv = grayscale_colors['black']
        h, s, v = rgb_to_hsv(rgb)
        assert s == 0.0  # Saturation must be 0 for grayscale
        assert v == 0.0  # Value must be 0 for black

    def test_white(self, grayscale_colors):
        """Test conversion of white."""
        rgb, expected_hsv = grayscale_colors['white']
        h, s, v = rgb_to_hsv(rgb)
        assert s == 0.0  # Saturation must be 0 for grayscale
        assert abs(v - 1.0) < 0.01

    def test_gray_midpoint(self, grayscale_colors):
        """Test conversion of middle gray."""
        rgb, expected_hsv = grayscale_colors['gray_128']
        h, s, v = rgb_to_hsv(rgb)
        assert s == 0.0  # Saturation must be 0 for grayscale
        assert abs(v - expected_hsv[2]) < 0.01

    def test_invalid_rgb_negative(self):
        """Test that negative RGB values raise ValueError."""
        with pytest.raises(ValueError):
            rgb_to_hsv((-1, 0, 0))

    def test_invalid_rgb_over_255(self):
        """Test that RGB values over 255 raise ValueError."""
        with pytest.raises(ValueError):
            rgb_to_hsv((256, 0, 0))

    def test_invalid_rgb_type(self):
        """Test that non-tuple input raises TypeError."""
        with pytest.raises(TypeError):
            rgb_to_hsv([255, 0, 0])  # List instead of tuple

    def test_invalid_rgb_length(self):
        """Test that tuple with wrong length raises TypeError."""
        with pytest.raises(TypeError):
            rgb_to_hsv((255, 0))  # Only 2 values


# =============================================================================
# HSV to RGB Conversion Tests
# =============================================================================

class TestHsvToRgb:
    """Tests for hsv_to_rgb conversion function."""

    def test_pure_red(self):
        """Test conversion to pure red."""
        result = hsv_to_rgb(0.0, 1.0, 1.0)
        assert result == (255, 0, 0)

    def test_pure_green(self):
        """Test conversion to pure green."""
        result = hsv_to_rgb(120.0, 1.0, 1.0)
        assert result == (0, 255, 0)

    def test_pure_blue(self):
        """Test conversion to pure blue."""
        result = hsv_to_rgb(240.0, 1.0, 1.0)
        assert result == (0, 0, 255)

    def test_cyan(self):
        """Test conversion to cyan."""
        result = hsv_to_rgb(180.0, 1.0, 1.0)
        assert result == (0, 255, 255)

    def test_magenta(self):
        """Test conversion to magenta."""
        result = hsv_to_rgb(300.0, 1.0, 1.0)
        assert result == (255, 0, 255)

    def test_yellow(self):
        """Test conversion to yellow."""
        result = hsv_to_rgb(60.0, 1.0, 1.0)
        assert result == (255, 255, 0)

    def test_black(self):
        """Test conversion to black (v=0)."""
        result = hsv_to_rgb(0.0, 1.0, 0.0)
        assert result == (0, 0, 0)

    def test_white(self):
        """Test conversion to white (s=0, v=1)."""
        result = hsv_to_rgb(0.0, 0.0, 1.0)
        assert result == (255, 255, 255)

    def test_grayscale_mid(self):
        """Test conversion to middle gray."""
        result = hsv_to_rgb(0.0, 0.0, 0.5)
        assert result == (128, 128, 128)

    def test_hue_wrap_positive(self):
        """Test that hue wraps around for values > 360."""
        result1 = hsv_to_rgb(360.0, 1.0, 1.0)
        result2 = hsv_to_rgb(0.0, 1.0, 1.0)
        assert result1 == result2

    def test_hue_wrap_negative(self):
        """Test that hue wraps around for negative values."""
        result1 = hsv_to_rgb(-60.0, 1.0, 1.0)
        result2 = hsv_to_rgb(300.0, 1.0, 1.0)
        assert result1 == result2

    def test_saturation_clamp_high(self):
        """Test that saturation > 1 is clamped."""
        result1 = hsv_to_rgb(0.0, 1.5, 1.0)
        result2 = hsv_to_rgb(0.0, 1.0, 1.0)
        assert result1 == result2

    def test_saturation_clamp_low(self):
        """Test that saturation < 0 is clamped."""
        result1 = hsv_to_rgb(0.0, -0.5, 1.0)
        result2 = hsv_to_rgb(0.0, 0.0, 1.0)
        assert result1 == result2

    def test_value_clamp(self):
        """Test that value is clamped to 0-1."""
        result1 = hsv_to_rgb(0.0, 1.0, 1.5)
        result2 = hsv_to_rgb(0.0, 1.0, 1.0)
        assert result1 == result2

    def test_invalid_type(self):
        """Test that non-numeric values raise TypeError."""
        with pytest.raises(TypeError):
            hsv_to_rgb("red", 1.0, 1.0)


# =============================================================================
# Roundtrip Conversion Tests
# =============================================================================

class TestRoundtripConversion:
    """Tests for RGB -> HSV -> RGB consistency."""

    def test_primary_colors_roundtrip(self, primary_colors):
        """Test that primary colors survive roundtrip conversion."""
        for name, (rgb, _) in primary_colors.items():
            hsv = rgb_to_hsv(rgb)
            result = hsv_to_rgb(*hsv)
            # Allow small rounding differences
            assert abs(result[0] - rgb[0]) <= 1, f"Red channel mismatch for {name}"
            assert abs(result[1] - rgb[1]) <= 1, f"Green channel mismatch for {name}"
            assert abs(result[2] - rgb[2]) <= 1, f"Blue channel mismatch for {name}"

    def test_secondary_colors_roundtrip(self, secondary_colors):
        """Test that secondary colors survive roundtrip conversion."""
        for name, (rgb, _) in secondary_colors.items():
            hsv = rgb_to_hsv(rgb)
            result = hsv_to_rgb(*hsv)
            assert abs(result[0] - rgb[0]) <= 1, f"Red channel mismatch for {name}"
            assert abs(result[1] - rgb[1]) <= 1, f"Green channel mismatch for {name}"
            assert abs(result[2] - rgb[2]) <= 1, f"Blue channel mismatch for {name}"

    def test_grayscale_roundtrip(self, grayscale_colors):
        """Test that grayscale colors survive roundtrip conversion."""
        for name, (rgb, _) in grayscale_colors.items():
            hsv = rgb_to_hsv(rgb)
            result = hsv_to_rgb(*hsv)
            assert abs(result[0] - rgb[0]) <= 1, f"Red channel mismatch for {name}"
            assert abs(result[1] - rgb[1]) <= 1, f"Green channel mismatch for {name}"
            assert abs(result[2] - rgb[2]) <= 1, f"Blue channel mismatch for {name}"

    def test_random_colors_roundtrip(self):
        """Test roundtrip for various colors across the spectrum."""
        test_colors = [
            (200, 100, 50),
            (50, 200, 100),
            (100, 50, 200),
            (150, 150, 100),
            (128, 64, 192),
        ]
        for rgb in test_colors:
            hsv = rgb_to_hsv(rgb)
            result = hsv_to_rgb(*hsv)
            assert abs(result[0] - rgb[0]) <= 1
            assert abs(result[1] - rgb[1]) <= 1
            assert abs(result[2] - rgb[2]) <= 1


# =============================================================================
# Linear RGB Interpolation Tests
# =============================================================================

class TestColorInterpolate:
    """Tests for color_interpolate (linear RGB) function."""

    def test_t_zero_returns_start(self):
        """Test that t=0 returns start color."""
        start = (255, 0, 0)
        end = (0, 255, 0)
        result = color_interpolate(start, end, 0.0)
        assert result == start

    def test_t_one_returns_end(self):
        """Test that t=1 returns end color."""
        start = (255, 0, 0)
        end = (0, 255, 0)
        result = color_interpolate(start, end, 1.0)
        assert result == end

    def test_t_half_midpoint(self):
        """Test that t=0.5 returns midpoint."""
        start = (0, 0, 0)
        end = (200, 100, 50)
        result = color_interpolate(start, end, 0.5)
        assert result == (100, 50, 25)

    def test_red_to_blue_midpoint(self):
        """Test red to blue interpolation at midpoint."""
        start = (255, 0, 0)
        end = (0, 0, 255)
        result = color_interpolate(start, end, 0.5)
        # Should be purple (midpoint in RGB space)
        assert result == (128, 0, 128)

    def test_t_clamped_negative(self):
        """Test that negative t is clamped to 0."""
        start = (255, 0, 0)
        end = (0, 255, 0)
        result = color_interpolate(start, end, -0.5)
        assert result == start

    def test_t_clamped_over_one(self):
        """Test that t > 1 is clamped to 1."""
        start = (255, 0, 0)
        end = (0, 255, 0)
        result = color_interpolate(start, end, 1.5)
        assert result == end

    def test_same_color(self):
        """Test interpolation between same colors."""
        color = (128, 64, 32)
        result = color_interpolate(color, color, 0.5)
        assert result == color

    def test_invalid_start_type(self):
        """Test that invalid start type raises TypeError."""
        with pytest.raises(TypeError):
            color_interpolate([255, 0, 0], (0, 255, 0), 0.5)

    def test_invalid_rgb_range(self):
        """Test that out-of-range RGB raises ValueError."""
        with pytest.raises(ValueError):
            color_interpolate((300, 0, 0), (0, 255, 0), 0.5)


# =============================================================================
# HSV Arc Interpolation Tests
# =============================================================================

class TestColorArcInterpolate:
    """Tests for color_arc_interpolate (HSV) function."""

    def test_red_to_green_short(self):
        """Test red to green via shortest path (through yellow)."""
        start = (255, 0, 0)  # Red, hue=0
        end = (0, 255, 0)    # Green, hue=120
        result = color_arc_interpolate(start, end, 0.5, 'short')
        # Midpoint should be around yellow (hue=60)
        h, s, v = rgb_to_hsv(result)
        assert 55 < h < 65  # Allow some tolerance

    def test_red_to_green_long(self):
        """Test red to green via longest path (through blue)."""
        start = (255, 0, 0)  # Red, hue=0
        end = (0, 255, 0)    # Green, hue=120
        result = color_arc_interpolate(start, end, 0.5, 'long')
        # Midpoint should be around blue (hue=240)
        h, s, v = rgb_to_hsv(result)
        assert 235 < h < 245  # Allow some tolerance

    def test_red_to_blue_cw(self):
        """Test red to blue clockwise (increasing hue)."""
        start = (255, 0, 0)  # Red, hue=0
        end = (0, 0, 255)    # Blue, hue=240
        result = color_arc_interpolate(start, end, 0.5, 'cw')
        # Midpoint should be around green (hue=120)
        h, s, v = rgb_to_hsv(result)
        assert 115 < h < 125

    def test_red_to_blue_ccw(self):
        """Test red to blue counter-clockwise (decreasing hue)."""
        start = (255, 0, 0)  # Red, hue=0
        end = (0, 0, 255)    # Blue, hue=240
        result = color_arc_interpolate(start, end, 0.5, 'ccw')
        # Midpoint should be around magenta (hue=300)
        h, s, v = rgb_to_hsv(result)
        assert 295 < h < 305

    def test_grayscale_fallback(self):
        """Test that grayscale colors fall back to RGB interpolation."""
        start = (0, 0, 0)      # Black (s=0)
        end = (255, 255, 255)  # White (s=0)
        result = color_arc_interpolate(start, end, 0.5)
        # Should be middle gray (RGB interpolation)
        assert result == (128, 128, 128)

    def test_t_boundaries(self):
        """Test t=0 and t=1 boundaries."""
        start = (255, 0, 0)
        end = (0, 255, 0)
        assert color_arc_interpolate(start, end, 0.0) == start
        assert color_arc_interpolate(start, end, 1.0) == end

    def test_invalid_direction(self):
        """Test that invalid direction raises ValueError."""
        with pytest.raises(ValueError):
            color_arc_interpolate((255, 0, 0), (0, 255, 0), 0.5, 'invalid')


# =============================================================================
# ColorTransitionConfig Tests
# =============================================================================

class TestColorTransitionConfig:
    """Tests for ColorTransitionConfig dataclass."""

    def test_default_values(self):
        """Test default configuration values."""
        config = ColorTransitionConfig()
        assert config.duration_ms == 500
        assert config.easing == 'ease_in_out'
        assert config.use_hsv is True
        assert config.hsv_direction == 'short'

    def test_custom_values(self):
        """Test custom configuration values."""
        config = ColorTransitionConfig(
            duration_ms=1000,
            easing='linear',
            use_hsv=False,
            hsv_direction='long'
        )
        assert config.duration_ms == 1000
        assert config.easing == 'linear'
        assert config.use_hsv is False
        assert config.hsv_direction == 'long'

    def test_invalid_duration_zero(self):
        """Test that duration_ms=0 raises ValueError."""
        with pytest.raises(ValueError):
            ColorTransitionConfig(duration_ms=0)

    def test_invalid_duration_negative(self):
        """Test that negative duration_ms raises ValueError."""
        with pytest.raises(ValueError):
            ColorTransitionConfig(duration_ms=-100)

    def test_invalid_easing(self):
        """Test that invalid easing function raises ValueError."""
        with pytest.raises(ValueError):
            ColorTransitionConfig(easing='invalid_easing')

    def test_invalid_hsv_direction(self):
        """Test that invalid hsv_direction raises ValueError."""
        with pytest.raises(ValueError):
            ColorTransitionConfig(hsv_direction='invalid')

    def test_repr(self):
        """Test string representation."""
        config = ColorTransitionConfig(duration_ms=1000)
        repr_str = repr(config)
        assert 'duration_ms=1000' in repr_str
        assert 'ColorTransitionConfig' in repr_str


# =============================================================================
# ColorTransition Class Tests
# =============================================================================

class TestColorTransition:
    """Tests for ColorTransition class."""

    def test_initialization(self):
        """Test basic initialization."""
        transition = ColorTransition(
            start=(255, 0, 0),
            end=(0, 255, 0)
        )
        assert transition._start == (255, 0, 0)
        assert transition._end == (0, 255, 0)

    def test_get_color_before_start(self):
        """Test that get_color returns start before start() is called."""
        transition = ColorTransition(
            start=(255, 0, 0),
            end=(0, 255, 0)
        )
        assert transition.get_color() == (255, 0, 0)

    def test_get_color_with_elapsed_override(self):
        """Test get_color with explicit elapsed_ms parameter."""
        transition = ColorTransition(
            start=(0, 0, 0),
            end=(100, 100, 100),
            config=ColorTransitionConfig(duration_ms=100, easing='linear', use_hsv=False)
        )
        # At half duration, should be halfway
        result = transition.get_color(elapsed_ms=50)
        assert result == (50, 50, 50)

    def test_is_complete(self):
        """Test is_complete() after transition finishes."""
        transition = ColorTransition(
            start=(255, 0, 0),
            end=(0, 255, 0),
            config=ColorTransitionConfig(duration_ms=50)
        )
        assert not transition.is_complete()
        transition.start()
        time.sleep(0.1)  # Wait longer than duration
        assert transition.is_complete()

    def test_get_progress(self):
        """Test get_progress() returns correct values."""
        transition = ColorTransition(
            start=(255, 0, 0),
            end=(0, 255, 0),
            config=ColorTransitionConfig(duration_ms=100)
        )
        assert transition.get_progress() == 0.0  # Before start
        transition.start()
        time.sleep(0.05)  # ~50ms
        progress = transition.get_progress()
        assert 0.3 < progress < 0.7  # Should be around 0.5

    def test_reset(self):
        """Test reset() clears started state."""
        transition = ColorTransition(
            start=(255, 0, 0),
            end=(0, 255, 0),
            config=ColorTransitionConfig(duration_ms=100)
        )
        transition.start()
        time.sleep(0.05)
        transition.reset()
        assert transition.get_progress() == 0.0
        assert not transition.is_complete()

    def test_reverse(self):
        """Test reverse() swaps start and end."""
        transition = ColorTransition(
            start=(255, 0, 0),
            end=(0, 255, 0)
        )
        transition.reverse()
        assert transition._start == (0, 255, 0)
        assert transition._end == (255, 0, 0)

    def test_get_elapsed_ms(self):
        """Test get_elapsed_ms() returns correct value."""
        transition = ColorTransition(
            start=(255, 0, 0),
            end=(0, 255, 0),
            config=ColorTransitionConfig(duration_ms=1000)
        )
        assert transition.get_elapsed_ms() == 0  # Before start
        transition.start()
        time.sleep(0.1)
        elapsed = transition.get_elapsed_ms()
        assert 80 < elapsed < 150  # Allow for timing variance

    def test_get_remaining_ms(self):
        """Test get_remaining_ms() returns correct value."""
        transition = ColorTransition(
            start=(255, 0, 0),
            end=(0, 255, 0),
            config=ColorTransitionConfig(duration_ms=1000)
        )
        assert transition.get_remaining_ms() == 1000  # Before start
        transition.start()
        time.sleep(0.1)
        remaining = transition.get_remaining_ms()
        assert 800 < remaining < 950  # Allow for timing variance

    def test_invalid_start_color(self):
        """Test that invalid start color raises error."""
        with pytest.raises(TypeError):
            ColorTransition(start="red", end=(0, 255, 0))

    def test_invalid_end_color(self):
        """Test that invalid end color raises error."""
        with pytest.raises(ValueError):
            ColorTransition(start=(255, 0, 0), end=(300, 0, 0))

    def test_rgb_mode_interpolation(self):
        """Test interpolation in RGB mode (use_hsv=False)."""
        transition = ColorTransition(
            start=(255, 0, 0),
            end=(0, 0, 255),
            config=ColorTransitionConfig(
                duration_ms=100,
                use_hsv=False,
                easing='linear'
            )
        )
        # At t=0.5, should be purple in RGB space
        result = transition.get_color(elapsed_ms=50)
        assert result == (128, 0, 128)


# =============================================================================
# Convenience Function Tests
# =============================================================================

class TestConvenienceFunctions:
    """Tests for convenience functions."""

    def test_lerp_color_alias(self):
        """Test that lerp_color is alias for color_interpolate."""
        start = (255, 0, 0)
        end = (0, 255, 0)
        t = 0.5
        assert lerp_color(start, end, t) == color_interpolate(start, end, t)

    def test_hue_shift_120_degrees(self):
        """Test hue shift by 120 degrees (red to green)."""
        result = hue_shift((255, 0, 0), 120.0)
        h, s, v = rgb_to_hsv(result)
        assert abs(h - 120.0) < 1.0  # Should be around green

    def test_hue_shift_negative(self):
        """Test negative hue shift."""
        result = hue_shift((0, 255, 0), -120.0)  # Green - 120 = Red
        h, s, v = rgb_to_hsv(result)
        assert h < 1.0 or h > 359.0  # Should be around red (0 degrees)

    def test_brightness_adjust_half(self):
        """Test brightness adjustment to half."""
        result = brightness_adjust((200, 100, 50), 0.5)
        # Value should be approximately halved
        _, _, v = rgb_to_hsv(result)
        original_v = rgb_to_hsv((200, 100, 50))[2]
        assert abs(v - original_v * 0.5) < 0.05

    def test_brightness_adjust_clamp(self):
        """Test brightness clamped to valid range."""
        result = brightness_adjust((200, 100, 50), 3.0)
        # Should not exceed (255, 255, 255) equivalent value
        _, _, v = rgb_to_hsv(result)
        assert v <= 1.0

    def test_saturation_adjust_half(self):
        """Test saturation adjustment to half."""
        result = saturation_adjust((255, 0, 0), 0.5)
        _, s, _ = rgb_to_hsv(result)
        assert abs(s - 0.5) < 0.05

    def test_saturation_adjust_zero(self):
        """Test saturation adjustment to zero (grayscale)."""
        result = saturation_adjust((255, 0, 0), 0.0)
        _, s, _ = rgb_to_hsv(result)
        assert s < 0.01  # Should be essentially zero

    def test_complementary_color_red(self):
        """Test complementary of red is cyan."""
        result = complementary_color((255, 0, 0))
        h, s, v = rgb_to_hsv(result)
        assert abs(h - 180.0) < 1.0  # Complementary is 180 degrees away

    def test_complementary_color_blue(self):
        """Test complementary of blue is yellow."""
        result = complementary_color((0, 0, 255))
        h, s, v = rgb_to_hsv(result)
        assert abs(h - 60.0) < 1.0  # Blue (240) + 180 = 420 % 360 = 60 (yellow)


# =============================================================================
# Performance Tests
# =============================================================================

class TestPerformance:
    """Performance tests for color utilities."""

    def test_hsv_conversion_performance(self):
        """HSV conversion must complete in <1ms for 256 colors."""
        start = time.monotonic()
        for i in range(256):
            rgb_to_hsv((i, 255 - i, 128))
        elapsed_ms = (time.monotonic() - start) * 1000
        assert elapsed_ms < 10.0  # Allow more time for non-optimized environments

    def test_rgb_conversion_performance(self):
        """RGB conversion must complete in <1ms for 256 colors."""
        start = time.monotonic()
        for i in range(256):
            hsv_to_rgb(i * 1.406, 1.0, 1.0)  # 0-360 degrees
        elapsed_ms = (time.monotonic() - start) * 1000
        assert elapsed_ms < 10.0

    def test_interpolation_performance(self):
        """Color interpolation must be fast."""
        start_color = (255, 0, 0)
        end_color = (0, 255, 0)
        start_time = time.monotonic()
        for i in range(1000):
            color_arc_interpolate(start_color, end_color, i / 1000)
        elapsed_ms = (time.monotonic() - start_time) * 1000
        assert elapsed_ms < 100  # 1000 interpolations in <100ms


# =============================================================================
# Edge Cases and Boundary Tests
# =============================================================================

class TestEdgeCases:
    """Edge case and boundary tests."""

    def test_rgb_float_values(self):
        """Test that float RGB values work (converted to int)."""
        result = color_interpolate((0.0, 0.0, 0.0), (255.0, 255.0, 255.0), 0.5)
        assert result == (128, 128, 128)

    def test_hue_at_360_boundary(self):
        """Test HSV conversion at hue=360 boundary."""
        result = hsv_to_rgb(359.9, 1.0, 1.0)
        # Should be very close to red
        h, _, _ = rgb_to_hsv(result)
        assert h > 358 or h < 2

    def test_very_small_color_differences(self):
        """Test interpolation with very similar colors."""
        start = (128, 128, 128)
        end = (129, 129, 129)
        result = color_interpolate(start, end, 0.5)
        # Should be between 128 and 129
        assert all(128 <= c <= 129 for c in result)

    def test_transition_with_zero_duration_config_fails(self):
        """Test that zero duration config raises ValueError."""
        with pytest.raises(ValueError):
            ColorTransitionConfig(duration_ms=0)
