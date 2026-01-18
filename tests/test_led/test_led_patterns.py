#!/usr/bin/env python3
"""
Comprehensive Test Suite for LED Patterns

Tests all LED patterns for OpenDuck Mini V3:
- BreathingPattern (sine wave idle)
- PulsePattern (heartbeat alert)
- SpinPattern (rotating comet)

Coverage includes:
1. Pattern initialization and configuration
2. Color output validation (brightness bounds)
3. Timing accuracy (cycle duration)
4. Smooth transitions (no jumps)
5. Speed multiplier functionality
6. Performance (<10ms render time for 50Hz)
7. Edge cases and error handling

Run with: pytest tests/test_led/test_led_patterns.py -v
Coverage: pytest tests/test_led/test_led_patterns.py --cov=src.led.patterns --cov-report=term-missing

Author: Boston Dynamics Test Engineer
Created: 17 January 2026
"""

import math
import time
from typing import Tuple

import pytest

# Mock types for pre-implementation testing
RGB = Tuple[int, int, int]


# =============================================================================
# Test Utilities
# =============================================================================

def calculate_brightness(color: RGB) -> float:
    """Calculate brightness from RGB color (0.0-1.0).

    Uses max channel for simplicity (matches human perception better
    than average for saturated colors).
    """
    return max(color) / 255.0


def calculate_color_distance(c1: RGB, c2: RGB) -> float:
    """Calculate Euclidean distance between two RGB colors."""
    return math.sqrt(sum((a - b) ** 2 for a, b in zip(c1, c2)))


# =============================================================================
# PatternBase Tests (Base Class Functionality)
# =============================================================================

class TestPatternBaseClass:
    """Tests for PatternBase abstract class and helpers."""

    @pytest.mark.skip(reason="Implementation pending - Saturday 18 Jan")
    def test_pattern_base_initialization(self):
        """PatternBase initializes with correct defaults."""
        from src.led.patterns.base import PatternBase, PatternConfig

        # PatternBase is abstract, test via concrete subclass
        # This will be implemented with BreathingPattern
        pass

    @pytest.mark.skip(reason="Implementation pending - Saturday 18 Jan")
    def test_pattern_config_defaults(self):
        """PatternConfig has sensible defaults."""
        from src.led.patterns.base import PatternConfig

        config = PatternConfig()
        assert config.speed == 1.0
        assert config.brightness == 1.0
        assert config.reverse is False
        assert config.blend_frames == 10

    @pytest.mark.skip(reason="Implementation pending - Saturday 18 Jan")
    def test_pattern_config_custom_values(self):
        """PatternConfig accepts custom values."""
        from src.led.patterns.base import PatternConfig

        config = PatternConfig(speed=2.0, brightness=0.5, reverse=True, blend_frames=5)
        assert config.speed == 2.0
        assert config.brightness == 0.5
        assert config.reverse is True
        assert config.blend_frames == 5

    @pytest.mark.skip(reason="Implementation pending - Saturday 18 Jan")
    def test_scale_color_helper_full_brightness(self):
        """_scale_color at factor=1.0 returns original color."""
        from src.led.patterns.base import PatternBase

        result = PatternBase._scale_color((100, 150, 200), 1.0)
        assert result == (100, 150, 200)

    @pytest.mark.skip(reason="Implementation pending - Saturday 18 Jan")
    def test_scale_color_helper_half_brightness(self):
        """_scale_color at factor=0.5 halves all channels."""
        from src.led.patterns.base import PatternBase

        result = PatternBase._scale_color((100, 150, 200), 0.5)
        assert result == (50, 75, 100)

    @pytest.mark.skip(reason="Implementation pending - Saturday 18 Jan")
    def test_scale_color_helper_zero_brightness(self):
        """_scale_color at factor=0.0 returns black."""
        from src.led.patterns.base import PatternBase

        result = PatternBase._scale_color((100, 150, 200), 0.0)
        assert result == (0, 0, 0)

    @pytest.mark.skip(reason="Implementation pending - Saturday 18 Jan")
    def test_scale_color_clamps_to_255(self):
        """_scale_color clamps values to max 255."""
        from src.led.patterns.base import PatternBase

        result = PatternBase._scale_color((200, 200, 200), 1.5)
        assert all(c <= 255 for c in result)
        assert result == (255, 255, 255)

    @pytest.mark.skip(reason="Implementation pending - Saturday 18 Jan")
    def test_blend_colors_start(self):
        """_blend_colors at t=0 returns color1."""
        from src.led.patterns.base import PatternBase

        result = PatternBase._blend_colors((0, 0, 0), (255, 255, 255), 0.0)
        assert result == (0, 0, 0)

    @pytest.mark.skip(reason="Implementation pending - Saturday 18 Jan")
    def test_blend_colors_end(self):
        """_blend_colors at t=1.0 returns color2."""
        from src.led.patterns.base import PatternBase

        result = PatternBase._blend_colors((0, 0, 0), (255, 255, 255), 1.0)
        assert result == (255, 255, 255)

    @pytest.mark.skip(reason="Implementation pending - Saturday 18 Jan")
    def test_blend_colors_midpoint(self):
        """_blend_colors at t=0.5 returns midpoint."""
        from src.led.patterns.base import PatternBase

        result = PatternBase._blend_colors((0, 0, 0), (100, 200, 100), 0.5)
        assert result == (50, 100, 50)

    @pytest.mark.skip(reason="Implementation pending - Saturday 18 Jan")
    def test_blend_colors_clamps_t(self):
        """_blend_colors clamps t to 0.0-1.0 range."""
        from src.led.patterns.base import PatternBase

        # t < 0 should behave like t=0
        result1 = PatternBase._blend_colors((0, 0, 0), (255, 255, 255), -0.5)
        assert result1 == (0, 0, 0)

        # t > 1 should behave like t=1
        result2 = PatternBase._blend_colors((0, 0, 0), (255, 255, 255), 1.5)
        assert result2 == (255, 255, 255)


# =============================================================================
# BreathingPattern Tests
# =============================================================================

class TestBreathingPattern:
    """Tests for BreathingPattern (slow sine wave for idle state)."""

    @pytest.mark.skip(reason="Implementation pending - Saturday 18 Jan")
    def test_breathing_initialization(self, pattern_test_colors):
        """BreathingPattern initializes with correct defaults."""
        from src.led.patterns import BreathingPattern, PatternConfig

        config = PatternConfig()
        pattern = BreathingPattern(num_pixels=16, config=config)

        assert pattern.num_pixels == 16
        assert pattern.NAME == "breathing"
        assert pattern.CYCLE_FRAMES == 200  # 4 seconds at 50Hz
        assert pattern._frame == 0

    @pytest.mark.skip(reason="Implementation pending - Saturday 18 Jan")
    def test_breathing_brightness_within_bounds(self, pattern_test_colors):
        """Brightness stays within MIN_INTENSITY to MAX_INTENSITY."""
        from src.led.patterns import BreathingPattern, PatternConfig

        pattern = BreathingPattern(16, PatternConfig())
        base_color = pattern_test_colors['white']

        min_brightness = float('inf')
        max_brightness = 0.0

        # Run through 2 full cycles (400 frames)
        for _ in range(400):
            pixels = pattern.render(base_color)
            pattern.advance()

            # Check all pixel brightnesses
            for pixel in pixels:
                brightness = calculate_brightness(pixel)
                min_brightness = min(min_brightness, brightness)
                max_brightness = max(max_brightness, brightness)

        # Verify bounds (MIN_INTENSITY = 0.3, MAX_INTENSITY = 1.0)
        assert min_brightness >= 0.29  # Allow small tolerance
        assert max_brightness <= 1.01
        assert max_brightness >= 0.99  # Should reach full brightness

    @pytest.mark.skip(reason="Implementation pending - Saturday 18 Jan")
    def test_breathing_cycle_duration(self, pattern_test_colors):
        """Full breath cycle completes in CYCLE_FRAMES."""
        from src.led.patterns import BreathingPattern, PatternConfig

        pattern = BreathingPattern(16, PatternConfig())
        base_color = pattern_test_colors['soft_blue']

        # Get initial brightness
        initial_pixels = pattern.render(base_color)
        initial_brightness = calculate_brightness(initial_pixels[0])

        # Advance through one full cycle
        for _ in range(pattern.CYCLE_FRAMES):
            pattern.advance()

        # Get final brightness
        final_pixels = pattern.render(base_color)
        final_brightness = calculate_brightness(final_pixels[0])

        # Should be approximately the same (within 5%)
        assert abs(final_brightness - initial_brightness) < initial_brightness * 0.05

    @pytest.mark.skip(reason="Implementation pending - Saturday 18 Jan")
    def test_breathing_smooth_transitions(self, pattern_test_colors):
        """No sudden brightness jumps between frames."""
        from src.led.patterns import BreathingPattern, PatternConfig

        pattern = BreathingPattern(16, PatternConfig())
        base_color = pattern_test_colors['white']

        prev_brightness = None
        max_jump = 0.0

        for _ in range(200):  # One full cycle
            pixels = pattern.render(base_color)
            pattern.advance()

            brightness = calculate_brightness(pixels[0])

            if prev_brightness is not None:
                jump = abs(brightness - prev_brightness)
                max_jump = max(max_jump, jump)

            prev_brightness = brightness

        # Maximum jump should be small (smooth sine wave)
        # At 50Hz with 200 frame cycle, max jump ~= 0.03
        assert max_jump < 0.05, f"Brightness jump too large: {max_jump}"

    @pytest.mark.skip(reason="Implementation pending - Saturday 18 Jan")
    def test_breathing_all_pixels_uniform(self, pattern_test_colors):
        """All pixels have identical brightness (uniform breath)."""
        from src.led.patterns import BreathingPattern, PatternConfig

        pattern = BreathingPattern(16, PatternConfig())
        base_color = pattern_test_colors['purple']

        for _ in range(50):
            pixels = pattern.render(base_color)
            pattern.advance()

            # All pixels should be identical
            first_pixel = pixels[0]
            for pixel in pixels[1:]:
                assert pixel == first_pixel

    @pytest.mark.skip(reason="Implementation pending - Saturday 18 Jan")
    def test_breathing_speed_multiplier(self, pattern_test_colors):
        """Speed config doubles cycle speed at 2x."""
        from src.led.patterns import BreathingPattern, PatternConfig

        config = PatternConfig(speed=2.0)
        pattern = BreathingPattern(16, config)
        base_color = pattern_test_colors['blue']

        # At 2x speed, half cycle should show full brightness range
        half_cycle_frames = pattern.CYCLE_FRAMES // 2

        brightnesses = []
        for _ in range(half_cycle_frames):
            pixels = pattern.render(base_color)
            pattern.advance()
            brightnesses.append(calculate_brightness(pixels[0]))

        # Should have significant brightness variation
        brightness_range = max(brightnesses) - min(brightnesses)
        assert brightness_range > 0.5  # At least 50% brightness swing

    @pytest.mark.skip(reason="Implementation pending - Saturday 18 Jan")
    def test_breathing_intensity_helper(self, pattern_test_colors):
        """get_current_intensity() returns correct value."""
        from src.led.patterns import BreathingPattern, PatternConfig

        pattern = BreathingPattern(16, PatternConfig())

        # At frame 0, should be around mid-intensity
        intensity = pattern.get_current_intensity()
        assert 0.3 <= intensity <= 1.0

        # After quarter cycle, should be near max or min
        for _ in range(pattern.CYCLE_FRAMES // 4):
            pattern.advance()

        intensity = pattern.get_current_intensity()
        assert 0.3 <= intensity <= 1.0


# =============================================================================
# PulsePattern Tests
# =============================================================================

class TestPulsePattern:
    """Tests for PulsePattern (heartbeat double-pulse for alert)."""

    @pytest.mark.skip(reason="Implementation pending - Saturday 18 Jan")
    def test_pulse_initialization(self):
        """PulsePattern initializes correctly."""
        from src.led.patterns import PulsePattern, PatternConfig

        pattern = PulsePattern(16, PatternConfig())
        assert pattern.num_pixels == 16
        assert pattern.NAME == "pulse"
        assert pattern.CYCLE_FRAMES == 50  # 1 second at 50Hz

    @pytest.mark.skip(reason="Implementation pending - Saturday 18 Jan")
    def test_pulse_double_beat_timing(self, pattern_test_colors):
        """Two distinct pulses occur within cycle."""
        from src.led.patterns import PulsePattern, PatternConfig

        pattern = PulsePattern(16, PatternConfig())
        base_color = pattern_test_colors['red']

        # Collect brightnesses over first 20 frames
        brightnesses = []
        for _ in range(20):
            pixels = pattern.render(base_color)
            pattern.advance()
            brightnesses.append(calculate_brightness(pixels[0]))

        # Find local maxima (peaks)
        peaks = []
        for i in range(1, len(brightnesses) - 1):
            if brightnesses[i] > brightnesses[i-1] and brightnesses[i] > brightnesses[i+1]:
                peaks.append(i)

        # Should have 2 peaks (double pulse)
        assert len(peaks) >= 2, f"Expected 2 peaks, found {len(peaks)}"

    @pytest.mark.skip(reason="Implementation pending - Saturday 18 Jan")
    def test_pulse_second_beat_weaker(self, pattern_test_colors):
        """Second pulse has lower intensity than first."""
        from src.led.patterns import PulsePattern, PatternConfig

        pattern = PulsePattern(16, PatternConfig())
        base_color = pattern_test_colors['white']

        brightnesses = []
        for _ in range(20):
            pixels = pattern.render(base_color)
            pattern.advance()
            brightnesses.append(calculate_brightness(pixels[0]))

        # First pulse peak (frames 0-8)
        first_pulse_max = max(brightnesses[0:8])

        # Second pulse peak (frames 10-18)
        second_pulse_max = max(brightnesses[10:18])

        assert second_pulse_max < first_pulse_max, \
            f"Second pulse ({second_pulse_max:.2f}) should be weaker than first ({first_pulse_max:.2f})"

    @pytest.mark.skip(reason="Implementation pending - Saturday 18 Jan")
    def test_pulse_rest_period(self, pattern_test_colors):
        """700ms rest between pulse pairs (frames 15-50)."""
        from src.led.patterns import PulsePattern, PatternConfig

        pattern = PulsePattern(16, PatternConfig())
        base_color = pattern_test_colors['red']

        # Advance to rest period
        for i in range(50):
            pixels = pattern.render(base_color)
            pattern.advance()

            if 20 <= i <= 45:
                # Should be at rest intensity (0.3)
                brightness = calculate_brightness(pixels[0])
                assert abs(brightness - 0.3) < 0.1, \
                    f"Frame {i}: expected rest intensity ~0.3, got {brightness:.2f}"

    @pytest.mark.skip(reason="Implementation pending - Saturday 18 Jan")
    def test_pulse_heart_rate_calculation(self):
        """Heart rate BPM calculation is correct."""
        from src.led.patterns import PulsePattern, PatternConfig

        # Default speed = 60 BPM
        pattern = PulsePattern(16, PatternConfig(speed=1.0))
        assert pattern.get_heart_rate_bpm() == 60.0

        # Double speed = 120 BPM
        pattern_fast = PulsePattern(16, PatternConfig(speed=2.0))
        assert pattern_fast.get_heart_rate_bpm() == 120.0

        # Half speed = 30 BPM
        pattern_slow = PulsePattern(16, PatternConfig(speed=0.5))
        assert pattern_slow.get_heart_rate_bpm() == 30.0

    @pytest.mark.skip(reason="Implementation pending - Saturday 18 Jan")
    def test_pulse_envelope_smoothness(self, pattern_test_colors):
        """Pulse envelope uses smooth curve (no harsh edges)."""
        from src.led.patterns import PulsePattern, PatternConfig

        pattern = PulsePattern(16, PatternConfig())
        base_color = pattern_test_colors['orange']

        # During first pulse (frames 0-5), check for smooth rise
        brightnesses = []
        for _ in range(6):
            pixels = pattern.render(base_color)
            pattern.advance()
            brightnesses.append(calculate_brightness(pixels[0]))

        # Check that brightness increases smoothly
        for i in range(1, len(brightnesses) - 1):
            # No brightness should be more than 2x the next
            ratio = brightnesses[i] / max(brightnesses[i+1], 0.01)
            assert ratio < 2.0, f"Harsh brightness transition at frame {i}"


# =============================================================================
# SpinPattern Tests
# =============================================================================

class TestSpinPattern:
    """Tests for SpinPattern (rotating comet for thinking state)."""

    @pytest.mark.skip(reason="Implementation pending - Saturday 18 Jan")
    def test_spin_initialization(self):
        """SpinPattern initializes correctly."""
        from src.led.patterns import SpinPattern, PatternConfig

        pattern = SpinPattern(16, PatternConfig())
        assert pattern.num_pixels == 16
        assert pattern.NAME == "spin"
        assert pattern.TAIL_LENGTH == 4
        assert pattern.CYCLE_FRAMES == 32

    @pytest.mark.skip(reason="Implementation pending - Saturday 18 Jan")
    def test_spin_head_rotates_clockwise(self):
        """Comet head moves clockwise (increasing pixel index)."""
        from src.led.patterns import SpinPattern, PatternConfig

        pattern = SpinPattern(16, PatternConfig())

        positions = []
        for _ in range(pattern.CYCLE_FRAMES // 2):
            pos = pattern.get_head_position()
            positions.append(pos)
            pattern.advance()

        # Most transitions should be increasing (with wraparound at 15->0)
        increasing_count = 0
        for i in range(1, len(positions)):
            if positions[i] > positions[i-1] or (positions[i-1] == 15 and positions[i] == 0):
                increasing_count += 1

        assert increasing_count > len(positions) * 0.7, \
            "Head should mostly move clockwise"

    @pytest.mark.skip(reason="Implementation pending - Saturday 18 Jan")
    def test_spin_tail_fades(self, pattern_test_colors):
        """Tail pixels fade with distance from head."""
        from src.led.patterns import SpinPattern, PatternConfig

        pattern = SpinPattern(16, PatternConfig())
        base_color = pattern_test_colors['white']

        # Advance to middle of animation
        for _ in range(10):
            pattern.advance()

        pixels = pattern.render(base_color)
        head_pos = pattern.get_head_position()

        # Get brightness of head and tail pixels
        head_brightness = calculate_brightness(pixels[head_pos])
        tail1_pos = (head_pos - 1) % 16
        tail1_brightness = calculate_brightness(pixels[tail1_pos])
        tail2_pos = (head_pos - 2) % 16
        tail2_brightness = calculate_brightness(pixels[tail2_pos])

        # Each should be dimmer than the previous
        assert tail1_brightness < head_brightness, \
            f"Tail1 ({tail1_brightness:.2f}) should be dimmer than head ({head_brightness:.2f})"
        assert tail2_brightness < tail1_brightness, \
            f"Tail2 ({tail2_brightness:.2f}) should be dimmer than tail1 ({tail1_brightness:.2f})"

    @pytest.mark.skip(reason="Implementation pending - Saturday 18 Jan")
    def test_spin_full_rotation_timing(self):
        """Complete rotation in CYCLE_FRAMES."""
        from src.led.patterns import SpinPattern, PatternConfig

        pattern = SpinPattern(16, PatternConfig())

        initial_pos = pattern.get_head_position()

        # Advance through full cycle
        for _ in range(pattern.CYCLE_FRAMES):
            pattern.advance()

        final_pos = pattern.get_head_position()

        # Should be back at start (or very close)
        assert final_pos == initial_pos, \
            f"After full cycle, expected pos {initial_pos}, got {final_pos}"

    @pytest.mark.skip(reason="Implementation pending - Saturday 18 Jan")
    def test_spin_background_glow(self, pattern_test_colors):
        """Background pixels have subtle glow (not black)."""
        from src.led.patterns import SpinPattern, PatternConfig

        pattern = SpinPattern(16, PatternConfig())
        base_color = pattern_test_colors['white']

        # Advance to get comet away from pixel 0
        for _ in range(8):
            pattern.advance()

        pixels = pattern.render(base_color)
        head_pos = pattern.get_head_position()

        # Find pixel opposite to head (far from comet)
        background_pos = (head_pos + 8) % 16
        background_brightness = calculate_brightness(pixels[background_pos])

        # Should have subtle glow (BACKGROUND_INTENSITY = 0.1)
        expected_min = 0.05  # At least 5% brightness
        assert background_brightness >= expected_min, \
            f"Background should have glow, got {background_brightness:.2f}"

    @pytest.mark.skip(reason="Implementation pending - Saturday 18 Jan")
    def test_spin_reverse_direction(self):
        """Reverse config makes comet spin counter-clockwise."""
        from src.led.patterns import SpinPattern, PatternConfig

        config = PatternConfig(reverse=True)
        pattern = SpinPattern(16, config)

        positions = []
        for _ in range(pattern.CYCLE_FRAMES // 2):
            pos = pattern.get_head_position()
            positions.append(pos)
            pattern.advance()

        # Most transitions should be decreasing (with wraparound at 0->15)
        decreasing_count = 0
        for i in range(1, len(positions)):
            if positions[i] < positions[i-1] or (positions[i-1] == 0 and positions[i] == 15):
                decreasing_count += 1

        assert decreasing_count > len(positions) * 0.7, \
            "Head should mostly move counter-clockwise in reverse mode"

    @pytest.mark.skip(reason="Implementation pending - Saturday 18 Jan")
    def test_spin_rotation_speed_calculation(self):
        """get_rotation_speed_rps() returns correct RPS."""
        from src.led.patterns import SpinPattern, PatternConfig

        # Default speed
        pattern = SpinPattern(16, PatternConfig(speed=1.0))
        base_rps = 50 / pattern.CYCLE_FRAMES  # ~1.56 RPS
        assert abs(pattern.get_rotation_speed_rps() - base_rps) < 0.01

        # Double speed
        pattern_fast = SpinPattern(16, PatternConfig(speed=2.0))
        assert abs(pattern_fast.get_rotation_speed_rps() - base_rps * 2) < 0.01


# =============================================================================
# Performance Tests
# =============================================================================

class TestLEDPatternPerformance:
    """Performance tests - all patterns must render in <10ms for 50Hz."""

    @pytest.mark.skip(reason="Implementation pending - Saturday 18 Jan")
    @pytest.mark.parametrize("pattern_name", ["breathing", "pulse", "spin"])
    def test_render_time_under_10ms(self, pattern_name, pattern_test_colors,
                                     performance_threshold):
        """Pattern renders in under 10ms (50Hz budget = 20ms per frame)."""
        from src.led.patterns import BreathingPattern, PulsePattern, SpinPattern, PatternConfig

        pattern_classes = {
            'breathing': BreathingPattern,
            'pulse': PulsePattern,
            'spin': SpinPattern,
        }

        pattern_class = pattern_classes[pattern_name]
        pattern = pattern_class(16, PatternConfig())
        base_color = pattern_test_colors['soft_blue']

        # Warm up (JIT compilation, cache warming)
        for _ in range(10):
            pattern.render(base_color)
            pattern.advance()

        # Measure 100 frames
        start = time.perf_counter()
        for _ in range(100):
            pattern.render(base_color)
            pattern.advance()
        elapsed = time.perf_counter() - start

        avg_ms = (elapsed / 100) * 1000

        max_time = performance_threshold['max_render_time_ms']
        assert avg_ms < max_time, \
            f"{pattern_name} avg render {avg_ms:.2f}ms exceeds {max_time}ms budget"

    @pytest.mark.skip(reason="Implementation pending - Saturday 18 Jan")
    @pytest.mark.parametrize("pattern_name", ["breathing", "pulse", "spin"])
    def test_metrics_recorded(self, pattern_name, pattern_test_colors):
        """Pattern records frame metrics correctly."""
        from src.led.patterns import BreathingPattern, PulsePattern, SpinPattern, PatternConfig

        pattern_classes = {
            'breathing': BreathingPattern,
            'pulse': PulsePattern,
            'spin': SpinPattern,
        }

        pattern_class = pattern_classes[pattern_name]
        pattern = pattern_class(16, PatternConfig())
        base_color = pattern_test_colors['blue']

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

class TestLEDPatternIntegration:
    """Integration tests for pattern switching and transitions."""

    @pytest.mark.skip(reason="Implementation pending - Saturday 18 Jan")
    def test_pattern_reset(self, pattern_test_colors):
        """Pattern reset returns to initial state."""
        from src.led.patterns import BreathingPattern, PatternConfig

        pattern = BreathingPattern(16, PatternConfig())
        base_color = pattern_test_colors['white']

        # Advance some frames
        for _ in range(50):
            pattern.render(base_color)
            pattern.advance()

        # Reset
        pattern.reset()

        # Should be back to frame 0
        assert pattern._frame == 0
        assert pattern.get_elapsed_time() < 0.1  # Just reset

    @pytest.mark.skip(reason="Implementation pending - Saturday 18 Jan")
    def test_rapid_pattern_switching(self, pattern_test_colors):
        """Can rapidly switch between patterns without errors."""
        from src.led.patterns import BreathingPattern, PulsePattern, SpinPattern, PatternConfig

        patterns = [
            BreathingPattern(16, PatternConfig()),
            PulsePattern(16, PatternConfig()),
            SpinPattern(16, PatternConfig()),
        ]
        base_color = pattern_test_colors['soft_blue']

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

    @pytest.mark.skip(reason="Implementation pending - Saturday 18 Jan")
    def test_brightness_config_affects_all_patterns(self, pattern_test_colors):
        """Brightness config scales output for all patterns."""
        from src.led.patterns import BreathingPattern, PulsePattern, SpinPattern, PatternConfig

        half_brightness_config = PatternConfig(brightness=0.5)

        patterns = [
            BreathingPattern(16, half_brightness_config),
            PulsePattern(16, half_brightness_config),
            SpinPattern(16, half_brightness_config),
        ]

        base_color = pattern_test_colors['white']  # (255, 255, 255)

        for pattern in patterns:
            pixels = pattern.render(base_color)

            # All pixels should be scaled down (max ~= 127)
            max_channel = max(max(p) for p in pixels)
            assert max_channel <= 128, \
                f"{pattern.NAME}: brightness config not applied, max_channel={max_channel}"


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
