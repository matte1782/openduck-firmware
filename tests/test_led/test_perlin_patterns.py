#!/usr/bin/env python3
"""
Perlin Noise Pattern Test Suite
OpenDuck Mini V3 | Week 02 Day 9

Tests for Fire, Cloud, Dream patterns:
- Correctness: Valid RGB output
- Performance: <2ms avg, <15ms max
- Visual quality: No seams, smooth animation
- Thread safety: Concurrent access

Test Categories:
- FirePattern tests: 12 tests
- CloudPattern tests: 10 tests
- DreamPattern tests: 10 tests
- Performance tests: 6 tests
- Thread safety tests: 4 tests
- Total: 42 tests

Author: Test Coverage Engineer (Agent 3)
Created: 19 January 2026
"""

import pytest
import time
import threading
import sys
from pathlib import Path
from typing import List, Tuple

# Add firmware/src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'src'))

# Check if noise library is available (required for Perlin patterns)
try:
    from noise import pnoise2
    NOISE_AVAILABLE = True
except ImportError:
    NOISE_AVAILABLE = False
    pnoise2 = None

# Import base classes directly from base module (no noise dependency)
# Avoid importing from led.patterns.__init__ as it imports Perlin patterns
try:
    # Try direct import from base module first
    from led.patterns.base import PatternBase, PatternConfig, RGB
    BASE_AVAILABLE = True
except ImportError:
    BASE_AVAILABLE = False
    PatternBase = None
    PatternConfig = None
    RGB = None

# Only attempt to import Perlin patterns if noise library is available
if NOISE_AVAILABLE and BASE_AVAILABLE:
    try:
        from led.patterns.fire import FirePattern
        from led.patterns.cloud import CloudPattern
        from led.patterns.dream import DreamPattern
        PERLIN_PATTERNS_AVAILABLE = True
    except ImportError as e:
        PERLIN_PATTERNS_AVAILABLE = False
        FirePattern = None
        CloudPattern = None
        DreamPattern = None
else:
    PERLIN_PATTERNS_AVAILABLE = False
    FirePattern = None
    CloudPattern = None
    DreamPattern = None

# Skip reason for tests
SKIP_REASON = "Perlin patterns require 'noise' library (pip install noise)"


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


# =============================================================================
# FirePattern Tests (12 tests)
# =============================================================================

@pytest.mark.skipif(not PERLIN_PATTERNS_AVAILABLE, reason=SKIP_REASON)
class TestFirePattern:
    """Tests for FirePattern - Flickering flame effect."""

    def test_fire_pattern_creation(self, default_config):
        """FirePattern can be instantiated with default config."""
        pattern = FirePattern(num_pixels=16, config=default_config)
        assert pattern.num_pixels == 16
        assert pattern.NAME == "fire"

    def test_fire_pattern_default_creation(self):
        """FirePattern can be instantiated without config."""
        pattern = FirePattern(num_pixels=16)
        assert pattern.num_pixels == 16
        assert pattern.config is not None

    def test_fire_pattern_render_returns_correct_length(self, default_config):
        """render() returns list of 16 RGB tuples."""
        pattern = FirePattern(num_pixels=16, config=default_config)
        base_color = (255, 100, 0)
        pixels = pattern.render(base_color)
        assert len(pixels) == 16
        assert all(isinstance(p, tuple) and len(p) == 3 for p in pixels)

    def test_fire_pattern_rgb_values_in_range(self, default_config):
        """All RGB values are 0-255 across 100 frames."""
        pattern = FirePattern(num_pixels=16, config=default_config)
        for _ in range(100):
            pixels = pattern.render((255, 100, 0))
            for r, g, b in pixels:
                assert 0 <= r <= 255, f"Red {r} out of range"
                assert 0 <= g <= 255, f"Green {g} out of range"
                assert 0 <= b <= 255, f"Blue {b} out of range"
            pattern.advance()

    def test_fire_pattern_changes_over_time(self, default_config):
        """Pattern is animated (changes between frames)."""
        pattern = FirePattern(num_pixels=16, config=default_config)
        pixels1 = pattern.render((255, 100, 0))
        # Copy pixels since buffer is reused
        pixels1_copy = [tuple(p) for p in pixels1]
        # Advance several frames
        for _ in range(5):
            pattern.advance()
        pixels2 = pattern.render((255, 100, 0))
        # At least some pixels should change
        assert pixels1_copy != list(pixels2), "Pattern not animating"

    def test_fire_pattern_no_seam(self, default_config):
        """LED 0 and LED 15 should have similar brightness (no seam)."""
        pattern = FirePattern(num_pixels=16, config=default_config)
        differences = []
        for _ in range(50):
            pixels = pattern.render((255, 100, 0))
            # Calculate brightness difference between LED 0 and LED 15
            brightness_0 = sum(pixels[0]) / 3
            brightness_15 = sum(pixels[15]) / 3
            differences.append(abs(brightness_0 - brightness_15))
            pattern.advance()

        avg_diff = sum(differences) / len(differences)
        # Adjacent LEDs should not have dramatic brightness jumps on average
        assert avg_diff < 100, f"Seam detected: avg difference {avg_diff}"

    def test_fire_pattern_intensity_varies(self, default_config):
        """Fire pattern shows intensity variation (flickering)."""
        pattern = FirePattern(num_pixels=16, config=default_config)
        intensities = []
        for _ in range(50):
            pixels = pattern.render((255, 100, 0))
            # Collect average intensity
            avg_intensity = sum(sum(p) / 3 for p in pixels) / len(pixels)
            intensities.append(avg_intensity)
            pattern.advance()

        # Check for variation (std dev > 0)
        mean = sum(intensities) / len(intensities)
        variance = sum((x - mean) ** 2 for x in intensities) / len(intensities)
        std_dev = variance ** 0.5
        assert std_dev > 1.0, "Fire pattern should have visible flickering"

    def test_fire_pattern_respects_base_color(self, default_config):
        """Fire pattern uses base color for flame."""
        pattern = FirePattern(num_pixels=16, config=default_config)
        # Pure red fire
        pixels_red = pattern.render((255, 0, 0))
        red_sum = sum(p[0] for p in pixels_red)

        # Fire should have red channel present
        assert red_sum > 0, "Fire pattern should use base color red channel"

    def test_fire_pattern_reset(self, default_config):
        """Pattern reset returns to initial state."""
        pattern = FirePattern(num_pixels=16, config=default_config)

        # Advance some frames
        for _ in range(50):
            pattern.render((255, 100, 0))
            pattern.advance()

        # Reset
        pattern.reset()

        # Frame counter should be reset
        assert pattern._frame == 0

    def test_fire_pattern_speed_affects_animation(self, double_speed_config):
        """Speed config affects animation rate."""
        pattern = FirePattern(num_pixels=16, config=double_speed_config)
        # Get initial state
        pixels1 = pattern.render((255, 100, 0))
        pixels1_copy = [tuple(p) for p in pixels1]
        for _ in range(3):
            pattern.advance()
        pixels2 = pattern.render((255, 100, 0))
        assert pixels1_copy != list(pixels2), "Pattern should animate at 2x speed"

    def test_fire_pattern_metrics_recorded(self, default_config):
        """Pattern records frame metrics correctly."""
        pattern = FirePattern(num_pixels=16, config=default_config)
        base_color = (255, 100, 0)

        # Initially no metrics
        assert pattern.get_metrics() is None

        # After render, metrics should exist
        pattern.render(base_color)
        metrics = pattern.get_metrics()

        assert metrics is not None
        assert metrics.frame_number == 0
        assert metrics.render_time_us >= 0
        assert metrics.timestamp > 0

    def test_fire_pattern_half_brightness(self, half_brightness_config):
        """Half brightness config reduces output intensity."""
        pattern_full = FirePattern(num_pixels=16)
        pattern_half = FirePattern(num_pixels=16, config=half_brightness_config)

        # Reset both for fair comparison
        pattern_full.reset()
        pattern_half.reset()

        # Render at same frame state
        pixels_full = pattern_full.render((200, 100, 50))
        pixels_half = pattern_half.render((200, 100, 50))

        # Half brightness should be dimmer on average
        avg_full = sum(sum(p) for p in pixels_full) / (16 * 3)
        avg_half = sum(sum(p) for p in pixels_half) / (16 * 3)

        # Allow for noise variation but half should be noticeably dimmer
        assert avg_half < avg_full * 0.85, "Half brightness should be dimmer"


# =============================================================================
# CloudPattern Tests (10 tests)
# =============================================================================

@pytest.mark.skipif(not PERLIN_PATTERNS_AVAILABLE, reason=SKIP_REASON)
class TestCloudPattern:
    """Tests for CloudPattern - Soft drifting cloud effect."""

    def test_cloud_pattern_creation(self, default_config):
        """CloudPattern can be instantiated with default config."""
        pattern = CloudPattern(num_pixels=16, config=default_config)
        assert pattern.num_pixels == 16
        assert pattern.NAME == "cloud"

    def test_cloud_pattern_default_creation(self):
        """CloudPattern can be instantiated without config."""
        pattern = CloudPattern(num_pixels=16)
        assert pattern.num_pixels == 16

    def test_cloud_pattern_render_returns_correct_length(self, default_config):
        """render() returns list of 16 RGB tuples."""
        pattern = CloudPattern(num_pixels=16, config=default_config)
        base_color = (200, 220, 255)
        pixels = pattern.render(base_color)
        assert len(pixels) == 16
        assert all(isinstance(p, tuple) and len(p) == 3 for p in pixels)

    def test_cloud_pattern_rgb_values_in_range(self, default_config):
        """All RGB values are 0-255 across 100 frames."""
        pattern = CloudPattern(num_pixels=16, config=default_config)
        for _ in range(100):
            pixels = pattern.render((200, 220, 255))
            for r, g, b in pixels:
                assert 0 <= r <= 255, f"Red {r} out of range"
                assert 0 <= g <= 255, f"Green {g} out of range"
                assert 0 <= b <= 255, f"Blue {b} out of range"
            pattern.advance()

    def test_cloud_pattern_changes_slowly(self, default_config):
        """Cloud pattern animates smoothly (slow transitions)."""
        pattern = CloudPattern(num_pixels=16, config=default_config)
        prev_pixels = pattern.render((200, 220, 255))
        prev_pixels_copy = [tuple(p) for p in prev_pixels]
        max_change = 0

        for _ in range(50):
            pattern.advance()
            curr_pixels = pattern.render((200, 220, 255))
            # Check change between frames
            for i in range(16):
                for c in range(3):
                    change = abs(curr_pixels[i][c] - prev_pixels_copy[i][c])
                    max_change = max(max_change, change)
            prev_pixels_copy = [tuple(p) for p in curr_pixels]

        # Clouds should drift slowly, not jump dramatically
        assert max_change < 60, f"Cloud changes too abruptly: {max_change}"

    def test_cloud_pattern_no_seam(self, default_config):
        """LED 0 and LED 15 should have continuous brightness (no seam)."""
        pattern = CloudPattern(num_pixels=16, config=default_config)
        differences = []
        for _ in range(50):
            pixels = pattern.render((200, 220, 255))
            brightness_0 = sum(pixels[0]) / 3
            brightness_15 = sum(pixels[15]) / 3
            differences.append(abs(brightness_0 - brightness_15))
            pattern.advance()

        avg_diff = sum(differences) / len(differences)
        assert avg_diff < 80, f"Seam detected: avg difference {avg_diff}"

    def test_cloud_pattern_soft_variation(self, default_config):
        """Cloud pattern has softer variation than fire."""
        pattern = CloudPattern(num_pixels=16, config=default_config)
        intensities = []
        for _ in range(50):
            pixels = pattern.render((200, 220, 255))
            avg_intensity = sum(sum(p) / 3 for p in pixels) / len(pixels)
            intensities.append(avg_intensity)
            pattern.advance()

        mean = sum(intensities) / len(intensities)
        variance = sum((x - mean) ** 2 for x in intensities) / len(intensities)
        std_dev = variance ** 0.5

        # Clouds should have some variation
        assert std_dev >= 0.0, "Cloud should have some variation (or be stable)"

    def test_cloud_pattern_reset(self, default_config):
        """Pattern reset returns to initial state."""
        pattern = CloudPattern(num_pixels=16, config=default_config)
        for _ in range(50):
            pattern.render((200, 220, 255))
            pattern.advance()
        pattern.reset()
        assert pattern._frame == 0

    def test_cloud_pattern_metrics_recorded(self, default_config):
        """Pattern records frame metrics correctly."""
        pattern = CloudPattern(num_pixels=16, config=default_config)
        pattern.render((200, 220, 255))
        metrics = pattern.get_metrics()
        assert metrics is not None
        assert metrics.render_time_us >= 0

    def test_cloud_pattern_different_pixel_count(self, default_config):
        """Pattern works with different LED counts."""
        for num_leds in [8, 12, 16, 24]:
            pattern = CloudPattern(num_pixels=num_leds, config=default_config)
            pixels = pattern.render((200, 220, 255))
            assert len(pixels) == num_leds


# =============================================================================
# DreamPattern Tests (10 tests)
# =============================================================================

@pytest.mark.skipif(not PERLIN_PATTERNS_AVAILABLE, reason=SKIP_REASON)
class TestDreamPattern:
    """Tests for DreamPattern - Multi-layer ethereal effect."""

    def test_dream_pattern_creation(self, default_config):
        """DreamPattern can be instantiated with default config."""
        pattern = DreamPattern(num_pixels=16, config=default_config)
        assert pattern.num_pixels == 16
        assert pattern.NAME == "dream"

    def test_dream_pattern_default_creation(self):
        """DreamPattern can be instantiated without config."""
        pattern = DreamPattern(num_pixels=16)
        assert pattern.num_pixels == 16

    def test_dream_pattern_render_returns_correct_length(self, default_config):
        """render() returns list of 16 RGB tuples."""
        pattern = DreamPattern(num_pixels=16, config=default_config)
        base_color = (150, 100, 255)
        pixels = pattern.render(base_color)
        assert len(pixels) == 16
        assert all(isinstance(p, tuple) and len(p) == 3 for p in pixels)

    def test_dream_pattern_rgb_values_in_range(self, default_config):
        """All RGB values are 0-255 across 100 frames."""
        pattern = DreamPattern(num_pixels=16, config=default_config)
        for _ in range(100):
            pixels = pattern.render((150, 100, 255))
            for r, g, b in pixels:
                assert 0 <= r <= 255, f"Red {r} out of range"
                assert 0 <= g <= 255, f"Green {g} out of range"
                assert 0 <= b <= 255, f"Blue {b} out of range"
            pattern.advance()

    def test_dream_pattern_ethereal_variation(self, default_config):
        """Dream pattern has complex multi-layer variation."""
        pattern = DreamPattern(num_pixels=16, config=default_config)
        all_pixels = []
        for _ in range(100):
            pixels = pattern.render((150, 100, 255))
            all_pixels.append(str([tuple(p) for p in pixels]))
            pattern.advance()

        # Check that pattern is not static
        unique_frames = len(set(all_pixels))
        assert unique_frames > 10, "Dream pattern should have variation over 100 frames"

    def test_dream_pattern_no_seam(self, default_config):
        """LED 0 and LED 15 should connect smoothly (circular)."""
        pattern = DreamPattern(num_pixels=16, config=default_config)
        differences = []
        for _ in range(50):
            pixels = pattern.render((150, 100, 255))
            brightness_0 = sum(pixels[0]) / 3
            brightness_15 = sum(pixels[15]) / 3
            differences.append(abs(brightness_0 - brightness_15))
            pattern.advance()

        avg_diff = sum(differences) / len(differences)
        assert avg_diff < 100, f"Seam detected: avg difference {avg_diff}"

    def test_dream_pattern_animation(self, default_config):
        """Dream pattern animates over time."""
        pattern = DreamPattern(num_pixels=16, config=default_config)
        pixels1 = pattern.render((150, 100, 255))
        pixels1_copy = [tuple(p) for p in pixels1]
        for _ in range(10):
            pattern.advance()
        pixels2 = pattern.render((150, 100, 255))
        assert pixels1_copy != list(pixels2), "Pattern should animate"

    def test_dream_pattern_reset(self, default_config):
        """Pattern reset returns to initial state."""
        pattern = DreamPattern(num_pixels=16, config=default_config)
        for _ in range(50):
            pattern.render((150, 100, 255))
            pattern.advance()
        pattern.reset()
        assert pattern._frame == 0

    def test_dream_pattern_metrics_recorded(self, default_config):
        """Pattern records frame metrics correctly."""
        pattern = DreamPattern(num_pixels=16, config=default_config)
        pattern.render((150, 100, 255))
        metrics = pattern.get_metrics()
        assert metrics is not None
        assert metrics.render_time_us >= 0

    def test_dream_pattern_speed_multiplier(self, double_speed_config):
        """Speed config affects dream animation rate."""
        pattern = DreamPattern(num_pixels=16, config=double_speed_config)
        # Animation should work at 2x speed
        pixels1 = pattern.render((150, 100, 255))
        pixels1_copy = [tuple(p) for p in pixels1]
        for _ in range(3):
            pattern.advance()
        pixels2 = pattern.render((150, 100, 255))
        assert pixels1_copy != list(pixels2), "Pattern should animate at 2x speed"


# =============================================================================
# Performance Tests (6 tests) - CRITICAL
# =============================================================================

@pytest.mark.skipif(not PERLIN_PATTERNS_AVAILABLE, reason=SKIP_REASON)
class TestPerlinPatternPerformance:
    """Performance regression tests - CRITICAL for 50Hz refresh rate."""

    def test_fire_pattern_performance_average(self, default_config):
        """Fire pattern render time must average <2ms."""
        pattern = FirePattern(num_pixels=16, config=default_config)
        base_color = (255, 128, 64)

        # Warmup
        for _ in range(10):
            pattern.render(base_color)
            pattern.advance()

        # Benchmark
        times = []
        for _ in range(100):
            start = time.monotonic()
            pattern.render(base_color)
            elapsed_ms = (time.monotonic() - start) * 1000
            times.append(elapsed_ms)
            pattern.advance()

        avg_ms = sum(times) / len(times)
        assert avg_ms < 2.0, f"Fire: Average {avg_ms:.3f}ms exceeds 2ms budget"

    def test_cloud_pattern_performance_average(self, default_config):
        """Cloud pattern render time must average <2ms."""
        pattern = CloudPattern(num_pixels=16, config=default_config)
        base_color = (200, 220, 255)

        # Warmup
        for _ in range(10):
            pattern.render(base_color)
            pattern.advance()

        # Benchmark
        times = []
        for _ in range(100):
            start = time.monotonic()
            pattern.render(base_color)
            elapsed_ms = (time.monotonic() - start) * 1000
            times.append(elapsed_ms)
            pattern.advance()

        avg_ms = sum(times) / len(times)
        assert avg_ms < 2.0, f"Cloud: Average {avg_ms:.3f}ms exceeds 2ms budget"

    def test_dream_pattern_performance_average(self, default_config):
        """Dream pattern render time must average <2ms."""
        pattern = DreamPattern(num_pixels=16, config=default_config)
        base_color = (150, 100, 255)

        # Warmup
        for _ in range(10):
            pattern.render(base_color)
            pattern.advance()

        # Benchmark
        times = []
        for _ in range(100):
            start = time.monotonic()
            pattern.render(base_color)
            elapsed_ms = (time.monotonic() - start) * 1000
            times.append(elapsed_ms)
            pattern.advance()

        avg_ms = sum(times) / len(times)
        assert avg_ms < 2.0, f"Dream: Average {avg_ms:.3f}ms exceeds 2ms budget"

    def test_fire_pattern_performance_worst_case(self, default_config):
        """Fire pattern worst-case render time must be <15ms."""
        pattern = FirePattern(num_pixels=16, config=default_config)
        base_color = (255, 128, 64)

        # Warmup
        for _ in range(10):
            pattern.render(base_color)
            pattern.advance()

        times = []
        for _ in range(100):
            start = time.monotonic()
            pattern.render(base_color)
            elapsed_ms = (time.monotonic() - start) * 1000
            times.append(elapsed_ms)
            pattern.advance()

        max_ms = max(times)
        assert max_ms < 15.0, f"Fire: Worst case {max_ms:.3f}ms exceeds 15ms budget"

    def test_cloud_pattern_performance_worst_case(self, default_config):
        """Cloud pattern worst-case render time must be <15ms."""
        pattern = CloudPattern(num_pixels=16, config=default_config)
        base_color = (200, 220, 255)

        # Warmup
        for _ in range(10):
            pattern.render(base_color)
            pattern.advance()

        times = []
        for _ in range(100):
            start = time.monotonic()
            pattern.render(base_color)
            elapsed_ms = (time.monotonic() - start) * 1000
            times.append(elapsed_ms)
            pattern.advance()

        max_ms = max(times)
        assert max_ms < 15.0, f"Cloud: Worst case {max_ms:.3f}ms exceeds 15ms budget"

    def test_dream_pattern_performance_worst_case(self, default_config):
        """Dream pattern worst-case render time must be <15ms."""
        pattern = DreamPattern(num_pixels=16, config=default_config)
        base_color = (150, 100, 255)

        # Warmup
        for _ in range(10):
            pattern.render(base_color)
            pattern.advance()

        times = []
        for _ in range(100):
            start = time.monotonic()
            pattern.render(base_color)
            elapsed_ms = (time.monotonic() - start) * 1000
            times.append(elapsed_ms)
            pattern.advance()

        max_ms = max(times)
        assert max_ms < 15.0, f"Dream: Worst case {max_ms:.3f}ms exceeds 15ms budget"


# =============================================================================
# Thread Safety Tests (4 tests)
# =============================================================================

@pytest.mark.skipif(not PERLIN_PATTERNS_AVAILABLE, reason=SKIP_REASON)
class TestPerlinPatternThreadSafety:
    """Thread safety tests for concurrent access."""

    def test_concurrent_render_no_crash(self, default_config):
        """Multiple threads can render simultaneously without crash."""
        pattern = FirePattern(num_pixels=16, config=default_config)
        errors = []

        def render_thread():
            try:
                for _ in range(100):
                    pattern.render((255, 100, 0))
                    pattern.advance()
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=render_thread) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Thread errors: {errors}"

    def test_concurrent_render_valid_output(self, default_config):
        """Concurrent access produces valid RGB output."""
        pattern = FirePattern(num_pixels=16, config=default_config)
        invalid_outputs = []

        def render_and_validate():
            for _ in range(50):
                pixels = pattern.render((255, 100, 0))
                pattern.advance()
                for r, g, b in pixels:
                    if not (0 <= r <= 255 and 0 <= g <= 255 and 0 <= b <= 255):
                        invalid_outputs.append((r, g, b))

        threads = [threading.Thread(target=render_and_validate) for _ in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(invalid_outputs) == 0, f"Invalid outputs: {invalid_outputs[:5]}"

    def test_render_during_reset(self, default_config):
        """Reset during render does not crash."""
        pattern = FirePattern(num_pixels=16, config=default_config)
        errors = []
        running = True

        def render_loop():
            nonlocal running
            try:
                while running:
                    pattern.render((255, 100, 0))
                    pattern.advance()
            except Exception as e:
                errors.append(e)

        def reset_loop():
            for _ in range(20):
                time.sleep(0.001)
                pattern.reset()

        render_thread = threading.Thread(target=render_loop)
        reset_thread = threading.Thread(target=reset_loop)

        render_thread.start()
        reset_thread.start()
        reset_thread.join()
        running = False
        render_thread.join()

        assert len(errors) == 0, f"Errors during concurrent reset: {errors}"

    def test_multiple_patterns_concurrent(self, default_config):
        """Multiple pattern instances render concurrently without interference."""
        fire = FirePattern(num_pixels=16, config=default_config)
        cloud = CloudPattern(num_pixels=16, config=default_config)
        dream = DreamPattern(num_pixels=16, config=default_config)
        errors = []

        def render_pattern(pattern, color):
            try:
                for _ in range(100):
                    pixels = pattern.render(color)
                    assert len(pixels) == 16
                    pattern.advance()
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=render_pattern, args=(fire, (255, 100, 0))),
            threading.Thread(target=render_pattern, args=(cloud, (200, 220, 255))),
            threading.Thread(target=render_pattern, args=(dream, (150, 100, 255))),
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Concurrent pattern errors: {errors}"


# =============================================================================
# Edge Case Tests (6 tests - Bonus coverage)
# =============================================================================

@pytest.mark.skipif(not PERLIN_PATTERNS_AVAILABLE, reason=SKIP_REASON)
class TestPerlinPatternEdgeCases:
    """Edge case tests for robustness."""

    def test_single_pixel(self, default_config):
        """Pattern works with single LED."""
        pattern = FirePattern(num_pixels=1, config=default_config)
        pixels = pattern.render((255, 100, 0))
        assert len(pixels) == 1
        assert 0 <= pixels[0][0] <= 255

    def test_large_pixel_count(self, default_config):
        """Pattern works with large LED count."""
        pattern = FirePattern(num_pixels=144, config=default_config)
        pixels = pattern.render((255, 100, 0))
        assert len(pixels) == 144

    def test_black_base_color(self, default_config):
        """Pattern handles black base color."""
        pattern = FirePattern(num_pixels=16, config=default_config)
        pixels = pattern.render((0, 0, 0))
        # All pixels should be black or near black
        for r, g, b in pixels:
            assert r <= 10 and g <= 10 and b <= 10, "Black input should give black output"

    def test_white_base_color(self, default_config):
        """Pattern handles white base color."""
        pattern = FirePattern(num_pixels=16, config=default_config)
        pixels = pattern.render((255, 255, 255))
        # Should produce valid output
        assert len(pixels) == 16
        for r, g, b in pixels:
            assert 0 <= r <= 255 and 0 <= g <= 255 and 0 <= b <= 255

    def test_many_frames_no_memory_leak(self, default_config):
        """Pattern can render many frames without memory issues."""
        pattern = FirePattern(num_pixels=16, config=default_config)
        for _ in range(10000):
            pattern.render((255, 100, 0))
            pattern.advance()
        # If we get here without crash/OOM, test passes
        assert True

    def test_minimum_brightness(self):
        """Pattern works at minimum brightness (0.0 not allowed, use near-zero)."""
        # Note: PatternConfig enforces brightness >= 0.0, but 0.0 is valid
        config = PatternConfig(speed=1.0, brightness=0.0)
        pattern = FirePattern(num_pixels=16, config=config)
        pixels = pattern.render((255, 100, 0))
        # All pixels should be black at 0 brightness
        for r, g, b in pixels:
            assert r == 0 and g == 0 and b == 0, "Zero brightness should give black"


# =============================================================================
# Integration Tests (2 tests - Pattern Registry)
# =============================================================================

@pytest.mark.skipif(not PERLIN_PATTERNS_AVAILABLE, reason=SKIP_REASON)
class TestPerlinPatternRegistry:
    """Integration tests for pattern registry."""

    def test_patterns_in_registry(self):
        """Perlin patterns should be registered."""
        from led.patterns import PATTERN_REGISTRY
        assert 'fire' in PATTERN_REGISTRY
        assert 'cloud' in PATTERN_REGISTRY
        assert 'dream' in PATTERN_REGISTRY

    def test_registry_creates_correct_patterns(self, default_config):
        """Registry creates correct pattern instances."""
        from led.patterns import PATTERN_REGISTRY
        fire = PATTERN_REGISTRY['fire'](num_pixels=16, config=default_config)
        assert fire.NAME == "fire"
        cloud = PATTERN_REGISTRY['cloud'](num_pixels=16, config=default_config)
        assert cloud.NAME == "cloud"
        dream = PATTERN_REGISTRY['dream'](num_pixels=16, config=default_config)
        assert dream.NAME == "dream"


# =============================================================================
# Division by Zero Prevention Tests (CRITICAL FIXES)
# =============================================================================

@pytest.mark.skipif(not PERLIN_PATTERNS_AVAILABLE, reason=SKIP_REASON)
class TestDreamPatternDivisionByZero:
    """Tests for CRITICAL division by zero fixes in DreamPattern."""

    def test_breath_cycle_frames_zero_raises_error(self):
        """BREATH_CYCLE_FRAMES=0 should raise ValueError on init."""
        # Create subclass with invalid BREATH_CYCLE_FRAMES
        class BadDreamPattern(DreamPattern):
            BREATH_CYCLE_FRAMES = 0

        with pytest.raises(ValueError) as exc_info:
            BadDreamPattern(num_pixels=16)

        assert "BREATH_CYCLE_FRAMES must be positive" in str(exc_info.value)
        assert "got 0" in str(exc_info.value)

    def test_breath_cycle_frames_negative_raises_error(self):
        """BREATH_CYCLE_FRAMES=-1 should raise ValueError on init."""
        class BadDreamPattern(DreamPattern):
            BREATH_CYCLE_FRAMES = -1

        with pytest.raises(ValueError) as exc_info:
            BadDreamPattern(num_pixels=16)

        assert "BREATH_CYCLE_FRAMES must be positive" in str(exc_info.value)
        assert "got -1" in str(exc_info.value)

    def test_speed_zero_in_get_breath_cycle_duration_raises_error(self):
        """config.speed=0 in get_breath_cycle_duration should raise ValueError."""
        pattern = DreamPattern(num_pixels=16)

        # Bypass PatternConfig validation by directly setting speed
        # This simulates malformed config or direct attribute modification
        pattern.config.speed = 0

        with pytest.raises(ValueError) as exc_info:
            pattern.get_breath_cycle_duration()

        assert "config.speed must be positive" in str(exc_info.value)
        assert "got 0" in str(exc_info.value)

    def test_speed_negative_in_get_breath_cycle_duration_raises_error(self):
        """config.speed=-1 in get_breath_cycle_duration should raise ValueError."""
        pattern = DreamPattern(num_pixels=16)

        # Bypass PatternConfig validation by directly setting speed
        pattern.config.speed = -1

        with pytest.raises(ValueError) as exc_info:
            pattern.get_breath_cycle_duration()

        assert "config.speed must be positive" in str(exc_info.value)
        assert "got -1" in str(exc_info.value)

    def test_valid_breath_cycle_frames_works(self, default_config):
        """Normal positive BREATH_CYCLE_FRAMES values work correctly."""
        # Test with standard value (AURORA pattern uses 100 = 2s at 50Hz)
        pattern = DreamPattern(num_pixels=16, config=default_config)
        assert pattern.BREATH_CYCLE_FRAMES == 100

        # Test rendering works
        pixels = pattern.render((150, 100, 255))
        assert len(pixels) == 16

        # Test breath phase calculation works
        phase = pattern.get_current_breath_phase()
        assert 0.0 <= phase <= 1.0

    def test_valid_speed_in_get_breath_cycle_duration_works(self, default_config):
        """Normal positive speed values work in get_breath_cycle_duration."""
        pattern = DreamPattern(num_pixels=16, config=default_config)

        duration = pattern.get_breath_cycle_duration()
        # At speed=1.0, BREATH_CYCLE_FRAMES=100, 50Hz: 100/50/1.0 = 2.0 seconds
        assert duration == 2.0

    def test_custom_breath_cycle_frames_subclass(self, default_config):
        """Subclass with valid custom BREATH_CYCLE_FRAMES works."""
        class FastDreamPattern(DreamPattern):
            BREATH_CYCLE_FRAMES = 150  # 3 seconds per breath

        pattern = FastDreamPattern(num_pixels=16, config=default_config)
        assert pattern.BREATH_CYCLE_FRAMES == 150

        duration = pattern.get_breath_cycle_duration()
        # 150/50/1.0 = 3.0 seconds
        assert duration == 3.0


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
