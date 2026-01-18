#!/usr/bin/env python3
"""
TDD Test Suite for LED Patterns

All patterns are tested for:
1. Correct output ranges (brightness within bounds)
2. Proper timing (cycle duration)
3. Smooth transitions (no sudden jumps)
4. Speed multiplier functionality
5. Performance (<10ms render time)

Run with: pytest tests/test_led/test_patterns.py -v

Author: Boston Dynamics Animation Systems Engineer
Created: 18 January 2026
"""

import pytest
import time
import sys
from pathlib import Path

# Add firmware/src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'src'))

from led.patterns import (
    PatternBase, PatternConfig, FrameMetrics,
    BreathingPattern, PulsePattern, SpinPattern
)


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def default_config():
    """Default pattern configuration."""
    return PatternConfig(speed=1.0, brightness=1.0, reverse=False)


@pytest.fixture
def half_brightness_config():
    """Half brightness configuration."""
    return PatternConfig(speed=1.0, brightness=0.5, reverse=False)


@pytest.fixture
def double_speed_config():
    """Double speed configuration."""
    return PatternConfig(speed=2.0, brightness=1.0, reverse=False)


@pytest.fixture
def reverse_config():
    """Reverse direction configuration."""
    return PatternConfig(speed=1.0, brightness=1.0, reverse=True)


# =============================================================================
# PatternBase Tests
# =============================================================================

class TestPatternConfig:
    """Tests for PatternConfig dataclass."""

    def test_default_values(self):
        """Config has sensible defaults."""
        config = PatternConfig()
        assert config.speed == 1.0
        assert config.brightness == 1.0
        assert config.reverse is False
        assert config.blend_frames == 10

    def test_custom_values(self):
        """Config accepts custom values."""
        config = PatternConfig(speed=2.0, brightness=0.5, reverse=True)
        assert config.speed == 2.0
        assert config.brightness == 0.5
        assert config.reverse is True


class TestPatternBaseHelpers:
    """Tests for PatternBase static helper methods."""

    def test_scale_color_full(self):
        """Scale by 1.0 returns original color."""
        result = PatternBase._scale_color((100, 150, 200), 1.0)
        assert result == (100, 150, 200)

    def test_scale_color_half(self):
        """Scale by 0.5 halves all channels."""
        result = PatternBase._scale_color((100, 150, 200), 0.5)
        assert result == (50, 75, 100)

    def test_scale_color_zero(self):
        """Scale by 0.0 returns black."""
        result = PatternBase._scale_color((100, 150, 200), 0.0)
        assert result == (0, 0, 0)

    def test_scale_color_clamps_to_255(self):
        """Scale doesn't exceed 255."""
        result = PatternBase._scale_color((200, 200, 200), 1.5)
        assert all(c <= 255 for c in result)

    def test_blend_colors_start(self):
        """Blend at t=0 returns color1."""
        result = PatternBase._blend_colors((0, 0, 0), (255, 255, 255), 0.0)
        assert result == (0, 0, 0)

    def test_blend_colors_end(self):
        """Blend at t=1 returns color2."""
        result = PatternBase._blend_colors((0, 0, 0), (255, 255, 255), 1.0)
        assert result == (255, 255, 255)

    def test_blend_colors_middle(self):
        """Blend at t=0.5 returns midpoint."""
        result = PatternBase._blend_colors((0, 0, 0), (100, 200, 100), 0.5)
        assert result == (50, 100, 50)


# =============================================================================
# BreathingPattern Tests
# =============================================================================

class TestBreathingPattern:
    """Tests for BreathingPattern class."""

    def test_initialization(self, default_config):
        """Pattern initializes with correct defaults."""
        pattern = BreathingPattern(16, default_config)
        assert pattern.num_pixels == 16
        assert pattern.NAME == "breathing"
        assert pattern._frame == 0

    def test_brightness_within_range(self, default_config):
        """Brightness stays within MIN_INTENSITY to MAX_INTENSITY."""
        pattern = BreathingPattern(16, default_config)
        base_color = (255, 255, 255)

        min_brightness = float('inf')
        max_brightness = 0

        # Run through 2 full cycles (400 frames)
        for _ in range(400):
            pixels = pattern.render(base_color)
            pattern.advance()

            # Check pixel brightness
            for r, g, b in pixels:
                brightness = max(r, g, b) / 255
                min_brightness = min(min_brightness, brightness)
                max_brightness = max(max_brightness, brightness)

        # Verify bounds (with small tolerance for floating point)
        assert min_brightness >= pattern.MIN_INTENSITY - 0.01
        assert max_brightness <= pattern.MAX_INTENSITY + 0.01

    def test_cycle_duration_correct(self, default_config):
        """Full breath cycle takes CYCLE_FRAMES frames."""
        pattern = BreathingPattern(16, default_config)
        base_color = (100, 150, 255)

        # Get initial state
        initial_pixels = pattern.render(base_color)
        initial_brightness = sum(initial_pixels[0]) / 3

        # Advance through one cycle
        for _ in range(pattern.CYCLE_FRAMES):
            pattern.advance()

        # Get state after one cycle
        final_pixels = pattern.render(base_color)
        final_brightness = sum(final_pixels[0]) / 3

        # Brightness should be approximately the same (within 5%)
        assert abs(final_brightness - initial_brightness) < initial_brightness * 0.05

    def test_smooth_transitions(self, default_config):
        """No sudden brightness jumps between consecutive frames."""
        pattern = BreathingPattern(16, default_config)
        base_color = (255, 255, 255)

        prev_brightness = None
        max_jump = 0

        for _ in range(200):
            pixels = pattern.render(base_color)
            pattern.advance()

            brightness = pixels[0][0] / 255  # Use red channel

            if prev_brightness is not None:
                jump = abs(brightness - prev_brightness)
                max_jump = max(max_jump, jump)

            prev_brightness = brightness

        # Maximum jump should be small (smooth animation)
        # At 50Hz with 200 frames per cycle, max jump ~= 0.03
        assert max_jump < 0.05, f"Brightness jump too large: {max_jump}"

    def test_speed_multiplier(self, double_speed_config):
        """Speed config affects cycle duration."""
        pattern = BreathingPattern(16, double_speed_config)
        base_color = (100, 100, 100)

        # At 2x speed, cycle should complete in half the frames
        half_cycle_frames = pattern.CYCLE_FRAMES // 2

        # Track brightness over half-cycle
        brightnesses = []
        for _ in range(half_cycle_frames):
            pixels = pattern.render(base_color)
            pattern.advance()
            brightnesses.append(pixels[0][0])

        # Should have gone through a full brightness cycle
        # (started mid, went to max, back to mid)
        assert max(brightnesses) > min(brightnesses)

    def test_all_pixels_same_brightness(self, default_config):
        """All pixels have identical brightness (uniform breath)."""
        pattern = BreathingPattern(16, default_config)
        base_color = (100, 150, 200)

        for _ in range(50):
            pixels = pattern.render(base_color)
            pattern.advance()

            # All pixels should be identical
            first_pixel = pixels[0]
            for pixel in pixels[1:]:
                assert pixel == first_pixel


# =============================================================================
# PulsePattern Tests
# =============================================================================

class TestPulsePattern:
    """Tests for PulsePattern class."""

    def test_initialization(self, default_config):
        """Pattern initializes correctly."""
        pattern = PulsePattern(16, default_config)
        assert pattern.num_pixels == 16
        assert pattern.NAME == "pulse"
        assert pattern.CYCLE_FRAMES == 50  # 1 second at 50Hz

    def test_double_pulse_timing(self, default_config):
        """Two pulses occur within first 300ms (15 frames)."""
        pattern = PulsePattern(16, default_config)
        base_color = (255, 0, 0)

        # Track brightness over first 20 frames
        brightnesses = []
        for _ in range(20):
            pixels = pattern.render(base_color)
            pattern.advance()
            brightnesses.append(pixels[0][0] / 255)

        # First pulse should peak around frames 0-5
        first_pulse_max = max(brightnesses[0:8])
        # Second pulse should peak around frames 10-15
        second_pulse_max = max(brightnesses[10:18])
        # Rest period brightness
        rest_brightness = min(brightnesses[7:10])

        # Both pulses should be brighter than rest
        assert first_pulse_max > rest_brightness + 0.2, "First pulse should be significantly brighter than rest"
        assert second_pulse_max > rest_brightness + 0.2, "Second pulse should be significantly brighter than rest"

    def test_second_pulse_weaker(self, default_config):
        """Second pulse has lower intensity than first."""
        pattern = PulsePattern(16, default_config)
        base_color = (255, 255, 255)

        # Collect brightnesses for first 20 frames
        brightnesses = []
        for _ in range(20):
            pixels = pattern.render(base_color)
            pattern.advance()
            brightnesses.append(max(pixels[0]))

        # First peak (around frame 2-3) should be brighter than second (around frame 12-13)
        first_pulse_max = max(brightnesses[0:8])
        second_pulse_max = max(brightnesses[10:18])

        assert second_pulse_max < first_pulse_max, \
            f"Second pulse ({second_pulse_max}) should be weaker than first ({first_pulse_max})"

    def test_long_rest_period(self, default_config):
        """700ms rest between pulse pairs (frames 15-50)."""
        pattern = PulsePattern(16, default_config)
        base_color = (200, 200, 200)

        # Check frames 20-45 (middle of rest period)
        for i in range(50):
            pixels = pattern.render(base_color)
            pattern.advance()

            if 20 <= i <= 45:
                # Should be at rest intensity
                brightness = pixels[0][0] / 200  # Normalize to base color
                expected_rest = pattern.REST_INTENSITY
                assert abs(brightness - expected_rest) < 0.1, \
                    f"Frame {i}: expected rest intensity {expected_rest}, got {brightness}"

    def test_heart_rate_calculation(self, default_config):
        """Heart rate BPM calculation is correct."""
        pattern = PulsePattern(16, default_config)
        assert pattern.get_heart_rate_bpm() == 60.0

        # Double speed = double heart rate
        fast_config = PatternConfig(speed=2.0)
        fast_pattern = PulsePattern(16, fast_config)
        assert fast_pattern.get_heart_rate_bpm() == 120.0


# =============================================================================
# SpinPattern Tests
# =============================================================================

class TestSpinPattern:
    """Tests for SpinPattern class."""

    def test_initialization(self, default_config):
        """Pattern initializes correctly."""
        pattern = SpinPattern(16, default_config)
        assert pattern.num_pixels == 16
        assert pattern.NAME == "spin"
        assert pattern.TAIL_LENGTH == 4

    def test_head_rotates_clockwise(self, default_config):
        """Comet head moves clockwise (increasing pixel index)."""
        pattern = SpinPattern(16, default_config)

        positions = []
        for _ in range(pattern.CYCLE_FRAMES // 2):
            pos = pattern.get_head_position()
            positions.append(pos)
            pattern.advance()

        # Head should move to higher indices (clockwise)
        # Note: wraps around, so we check the general trend
        increasing_count = sum(1 for i in range(1, len(positions))
                               if positions[i] >= positions[i-1] or positions[i] == 0)

        assert increasing_count > len(positions) * 0.8, "Head should mostly increase (clockwise)"

    def test_tail_fades(self, default_config):
        """Tail pixels fade with distance from head."""
        pattern = SpinPattern(16, default_config)
        base_color = (255, 255, 255)

        # Advance to middle of animation
        for _ in range(10):
            pattern.advance()

        pixels = pattern.render(base_color)
        head_pos = pattern.get_head_position()

        # Get brightness of head and tail pixels
        head_brightness = max(pixels[head_pos])
        tail1_pos = (head_pos - 1) % 16
        tail1_brightness = max(pixels[tail1_pos])
        tail2_pos = (head_pos - 2) % 16
        tail2_brightness = max(pixels[tail2_pos])

        # Each should be dimmer than the previous
        assert tail1_brightness < head_brightness, "Tail1 should be dimmer than head"
        assert tail2_brightness < tail1_brightness, "Tail2 should be dimmer than tail1"

    def test_full_rotation_timing(self, default_config):
        """Complete rotation in CYCLE_FRAMES frames."""
        pattern = SpinPattern(16, default_config)

        initial_pos = pattern.get_head_position()

        # Advance through one full cycle
        for _ in range(pattern.CYCLE_FRAMES):
            pattern.advance()

        final_pos = pattern.get_head_position()

        # Position should be back to start (or very close)
        assert final_pos == initial_pos, \
            f"After full cycle, expected pos {initial_pos}, got {final_pos}"

    def test_background_glow_present(self, default_config):
        """Background pixels have subtle glow (not completely black)."""
        pattern = SpinPattern(16, default_config)
        base_color = (255, 255, 255)

        # Advance to get comet away from pixel 0
        for _ in range(8):
            pattern.advance()

        pixels = pattern.render(base_color)
        head_pos = pattern.get_head_position()

        # Find a pixel far from the comet
        background_pos = (head_pos + 8) % 16  # Opposite side of ring
        background_brightness = max(pixels[background_pos])

        # Should have some glow (BACKGROUND_INTENSITY = 0.1)
        expected_min = int(255 * pattern.BACKGROUND_INTENSITY * 0.5)
        assert background_brightness >= expected_min, \
            f"Background should have glow, got {background_brightness}"

    def test_reverse_direction(self, reverse_config):
        """Reverse config makes comet spin counter-clockwise."""
        pattern = SpinPattern(16, reverse_config)

        positions = []
        for _ in range(pattern.CYCLE_FRAMES // 2):
            pos = pattern.get_head_position()
            positions.append(pos)
            pattern.advance()

        # Head should move to lower indices (counter-clockwise)
        decreasing_count = sum(1 for i in range(1, len(positions))
                               if positions[i] <= positions[i-1] or positions[i] == 15)

        assert decreasing_count > len(positions) * 0.8, "Head should mostly decrease (counter-clockwise)"


# =============================================================================
# Performance Tests
# =============================================================================

class TestPatternPerformance:
    """Performance tests - all patterns must render in <10ms."""

    @pytest.mark.parametrize("pattern_class", [
        BreathingPattern,
        PulsePattern,
        SpinPattern,
    ])
    def test_render_time_under_budget(self, pattern_class, default_config):
        """Pattern renders in under 10ms (budget for 50Hz)."""
        pattern = pattern_class(16, default_config)
        base_color = (100, 150, 200)

        # Warm up
        for _ in range(10):
            pattern.render(base_color)
            pattern.advance()

        # Measure 100 frames
        start = time.monotonic()
        for _ in range(100):
            pattern.render(base_color)
            pattern.advance()
        elapsed = time.monotonic() - start

        avg_ms = (elapsed / 100) * 1000

        # Must be under 10ms average
        assert avg_ms < 10.0, f"{pattern_class.NAME} avg render time {avg_ms:.2f}ms exceeds 10ms budget"

    @pytest.mark.parametrize("pattern_class", [
        BreathingPattern,
        PulsePattern,
        SpinPattern,
    ])
    def test_metrics_recorded(self, pattern_class, default_config):
        """Pattern records frame metrics correctly."""
        pattern = pattern_class(16, default_config)
        base_color = (100, 100, 100)

        # Initially no metrics
        assert pattern.get_metrics() is None

        # After render, metrics should exist
        pattern.render(base_color)
        metrics = pattern.get_metrics()

        assert metrics is not None
        assert metrics.frame_number == 0
        assert metrics.render_time_us >= 0
        assert metrics.timestamp > 0


# =============================================================================
# Integration Tests
# =============================================================================

class TestPatternIntegration:
    """Integration tests for pattern switching and transitions."""

    def test_pattern_reset(self, default_config):
        """Pattern reset returns to initial state."""
        pattern = BreathingPattern(16, default_config)
        base_color = (200, 200, 200)

        # Advance some frames
        for _ in range(50):
            pattern.render(base_color)
            pattern.advance()

        # Reset
        pattern.reset()

        # Should be back to frame 0
        assert pattern._frame == 0

    def test_rapid_pattern_switching(self, default_config):
        """Can rapidly switch between patterns without errors."""
        patterns = [
            BreathingPattern(16, default_config),
            PulsePattern(16, default_config),
            SpinPattern(16, default_config),
        ]
        base_color = (150, 150, 150)

        # Rapidly switch between patterns
        for _ in range(100):
            for pattern in patterns:
                pixels = pattern.render(base_color)
                pattern.advance()

                # Verify output is valid
                assert len(pixels) == 16
                for r, g, b in pixels:
                    assert 0 <= r <= 255
                    assert 0 <= g <= 255
                    assert 0 <= b <= 255


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
