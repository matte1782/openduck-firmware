#!/usr/bin/env python3
"""
Test Suite for HIGH Priority Validation Fixes

Tests for:
- HIGH-1: Input validation in estimate_current()
- HIGH-2: Bounds checking on PatternConfig.speed
- HIGH-3: Bounds checking on PatternConfig.brightness
- HIGH-4: Thread safety in PatternBase.render()

Created: 17 January 2026
"""

import pytest
import math
import threading
import time
import sys
from pathlib import Path

# Add firmware/src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'src'))

from led.patterns.base import PatternConfig, PatternBase
from led.patterns.breathing import BreathingPattern
from safety.led_safety import LEDSafetyManager, LEDRingProfile, PowerSource


# =============================================================================
# HIGH-2 and HIGH-3: PatternConfig Validation Tests
# =============================================================================

class TestPatternConfigValidation:
    """Tests for PatternConfig validation (HIGH-2, HIGH-3)."""

    # Speed validation tests (HIGH-2)

    def test_speed_valid_range(self):
        """Valid speed values should be accepted."""
        # Boundary values
        config1 = PatternConfig(speed=0.1)
        assert config1.speed == 0.1

        config2 = PatternConfig(speed=5.0)
        assert config2.speed == 5.0

        # Middle value
        config3 = PatternConfig(speed=2.5)
        assert config3.speed == 2.5

    def test_speed_below_minimum(self):
        """Speed below 0.1 should raise ValueError."""
        with pytest.raises(ValueError, match="speed must be 0.1-5.0, got 0.05"):
            PatternConfig(speed=0.05)

    def test_speed_above_maximum(self):
        """Speed above 5.0 should raise ValueError."""
        with pytest.raises(ValueError, match="speed must be 0.1-5.0, got 10.0"):
            PatternConfig(speed=10.0)

    def test_speed_negative(self):
        """Negative speed should raise ValueError."""
        with pytest.raises(ValueError, match="speed must be 0.1-5.0, got -1.0"):
            PatternConfig(speed=-1.0)

    def test_speed_nan(self):
        """NaN speed should raise ValueError."""
        with pytest.raises(ValueError, match="speed must be finite, got nan"):
            PatternConfig(speed=float('nan'))

    def test_speed_infinity(self):
        """Infinite speed should raise ValueError."""
        with pytest.raises(ValueError, match="speed must be finite, got inf"):
            PatternConfig(speed=float('inf'))

    def test_speed_negative_infinity(self):
        """Negative infinite speed should raise ValueError."""
        with pytest.raises(ValueError, match="speed must be finite, got -inf"):
            PatternConfig(speed=float('-inf'))

    def test_speed_non_numeric(self):
        """Non-numeric speed should raise TypeError."""
        with pytest.raises(TypeError, match="speed must be numeric, got str"):
            PatternConfig(speed="fast")

    # Brightness validation tests (HIGH-3)

    def test_brightness_valid_range(self):
        """Valid brightness values should be accepted."""
        # Boundary values
        config1 = PatternConfig(brightness=0.0)
        assert config1.brightness == 0.0

        config2 = PatternConfig(brightness=1.0)
        assert config2.brightness == 1.0

        # Middle value
        config3 = PatternConfig(brightness=0.5)
        assert config3.brightness == 0.5

    def test_brightness_below_minimum(self):
        """Brightness below 0.0 should raise ValueError."""
        with pytest.raises(ValueError, match="brightness must be 0.0-1.0, got -0.1"):
            PatternConfig(brightness=-0.1)

    def test_brightness_above_maximum(self):
        """Brightness above 1.0 should raise ValueError."""
        with pytest.raises(ValueError, match="brightness must be 0.0-1.0, got 1.5"):
            PatternConfig(brightness=1.5)

    def test_brightness_nan(self):
        """NaN brightness should raise ValueError."""
        with pytest.raises(ValueError, match="brightness must be finite, got nan"):
            PatternConfig(brightness=float('nan'))

    def test_brightness_infinity(self):
        """Infinite brightness should raise ValueError."""
        with pytest.raises(ValueError, match="brightness must be finite, got inf"):
            PatternConfig(brightness=float('inf'))

    def test_brightness_negative_infinity(self):
        """Negative infinite brightness should raise ValueError."""
        with pytest.raises(ValueError, match="brightness must be finite, got -inf"):
            PatternConfig(brightness=float('-inf'))

    def test_brightness_non_numeric(self):
        """Non-numeric brightness should raise TypeError."""
        with pytest.raises(TypeError, match="brightness must be numeric, got str"):
            PatternConfig(brightness="bright")

    # Combined validation tests

    def test_both_invalid(self):
        """Both invalid speed and brightness should fail on first check (speed)."""
        with pytest.raises(ValueError, match="speed"):
            PatternConfig(speed=-1.0, brightness=2.0)

    def test_blend_frames_validation(self):
        """blend_frames validation tests."""
        # Valid
        config = PatternConfig(blend_frames=1)
        assert config.blend_frames == 1

        config = PatternConfig(blend_frames=100)
        assert config.blend_frames == 100

        # Invalid - must be int
        with pytest.raises(TypeError, match="blend_frames must be int"):
            PatternConfig(blend_frames=5.5)

        # Invalid - must be >= 1
        with pytest.raises(ValueError, match="blend_frames must be >= 1, got 0"):
            PatternConfig(blend_frames=0)


# =============================================================================
# HIGH-1: estimate_current() Input Validation Tests
# =============================================================================

class TestEstimateCurrentValidation:
    """Tests for estimate_current() input validation (HIGH-1)."""

    @pytest.fixture
    def manager_with_rings(self):
        """LED safety manager with two registered rings."""
        manager = LEDSafetyManager(power_source=PowerSource.PI_5V_RAIL)
        ring1 = LEDRingProfile(gpio_pin=18, pwm_channel=0, name="Left Eye")
        ring2 = LEDRingProfile(gpio_pin=13, pwm_channel=1, name="Right Eye")
        manager.register_ring("ring1", ring1)
        manager.register_ring("ring2", ring2)
        return manager

    def test_valid_brightness_values(self, manager_with_rings):
        """Valid brightness values should work correctly."""
        # Minimum
        estimate = manager_with_rings.estimate_current({"ring1": 0, "ring2": 0})
        assert estimate.total_ma == 0.0

        # Maximum
        estimate = manager_with_rings.estimate_current({"ring1": 255, "ring2": 255})
        assert estimate.total_ma > 0.0

        # Middle
        estimate = manager_with_rings.estimate_current({"ring1": 128, "ring2": 128})
        assert estimate.total_ma > 0.0

    def test_brightness_negative(self, manager_with_rings):
        """Negative brightness should raise ValueError."""
        with pytest.raises(ValueError, match="Brightness for 'ring1' must be 0-255, got -10"):
            manager_with_rings.estimate_current({"ring1": -10, "ring2": 128})

    def test_brightness_above_255(self, manager_with_rings):
        """Brightness above 255 should raise ValueError."""
        with pytest.raises(ValueError, match="Brightness for 'ring2' must be 0-255, got 300"):
            manager_with_rings.estimate_current({"ring1": 128, "ring2": 300})

    def test_brightness_float(self, manager_with_rings):
        """Float brightness should raise TypeError."""
        with pytest.raises(TypeError, match="Brightness for 'ring1' must be int, got float"):
            manager_with_rings.estimate_current({"ring1": 128.5, "ring2": 128})

    def test_brightness_string(self, manager_with_rings):
        """String brightness should raise TypeError."""
        with pytest.raises(TypeError, match="Brightness for 'ring2' must be int, got str"):
            manager_with_rings.estimate_current({"ring1": 128, "ring2": "bright"})

    def test_brightness_none(self, manager_with_rings):
        """None brightness should raise TypeError."""
        with pytest.raises(TypeError, match="Brightness for 'ring1' must be int, got NoneType"):
            manager_with_rings.estimate_current({"ring1": None, "ring2": 128})

    def test_multiple_invalid_values(self, manager_with_rings):
        """Multiple invalid values should fail on first check."""
        with pytest.raises(ValueError, match="Brightness for 'ring1' must be 0-255"):
            manager_with_rings.estimate_current({"ring1": -10, "ring2": 300})

    def test_boundary_values(self, manager_with_rings):
        """Boundary values should be handled correctly."""
        # 0 should work
        estimate = manager_with_rings.estimate_current({"ring1": 0, "ring2": 0})
        assert estimate.total_ma == 0.0

        # 255 should work
        estimate = manager_with_rings.estimate_current({"ring1": 255, "ring2": 255})
        assert estimate.total_ma > 0.0

        # -1 should fail
        with pytest.raises(ValueError):
            manager_with_rings.estimate_current({"ring1": -1, "ring2": 128})

        # 256 should fail
        with pytest.raises(ValueError):
            manager_with_rings.estimate_current({"ring1": 128, "ring2": 256})


# =============================================================================
# HIGH-4: Thread Safety Tests
# =============================================================================

class TestPatternThreadSafety:
    """Tests for PatternBase.render() thread safety (HIGH-4)."""

    def test_render_lock_exists(self):
        """Pattern should have a render lock."""
        pattern = BreathingPattern(16)
        assert hasattr(pattern, '_render_lock')
        assert isinstance(pattern._render_lock, threading.Lock)

    def test_concurrent_render_calls(self):
        """Multiple threads can call render() without corruption."""
        pattern = BreathingPattern(16)
        base_color = (255, 255, 255)
        results = []
        errors = []

        def render_worker():
            try:
                for _ in range(50):
                    pixels = pattern.render(base_color)
                    # Verify output is valid
                    assert len(pixels) == 16
                    for r, g, b in pixels:
                        assert 0 <= r <= 255
                        assert 0 <= g <= 255
                        assert 0 <= b <= 255
                    results.append(True)
            except Exception as e:
                errors.append(e)

        # Start 5 threads
        threads = [threading.Thread(target=render_worker) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # No errors should occur
        assert len(errors) == 0, f"Errors occurred: {errors}"
        # All renders should succeed
        assert len(results) == 250  # 5 threads × 50 renders

    def test_concurrent_render_and_advance(self):
        """Render and advance can be called concurrently."""
        pattern = BreathingPattern(16)
        base_color = (200, 200, 200)
        errors = []

        def render_worker():
            try:
                for _ in range(100):
                    pattern.render(base_color)
                    time.sleep(0.0001)  # Tiny delay
            except Exception as e:
                errors.append(e)

        def advance_worker():
            try:
                for _ in range(100):
                    pattern.advance()
                    time.sleep(0.0001)  # Tiny delay
            except Exception as e:
                errors.append(e)

        # Start render and advance threads
        render_thread = threading.Thread(target=render_worker)
        advance_thread = threading.Thread(target=advance_worker)

        render_thread.start()
        advance_thread.start()

        render_thread.join()
        advance_thread.join()

        # No errors should occur
        assert len(errors) == 0, f"Errors occurred: {errors}"

    def test_render_preserves_metrics(self):
        """Concurrent renders preserve metrics correctly."""
        pattern = BreathingPattern(16)
        base_color = (150, 150, 150)

        def render_and_check_metrics():
            for i in range(10):
                pattern.render(base_color)
                metrics = pattern.get_metrics()
                # Metrics should always exist after render
                assert metrics is not None
                # Frame number should be current frame
                assert metrics.frame_number == pattern._frame
                pattern.advance()

        # Run in multiple threads
        threads = [threading.Thread(target=render_and_check_metrics) for _ in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

    def test_stress_test_rapid_switching(self):
        """Stress test: rapid pattern creation and rendering."""
        errors = []
        base_color = (100, 100, 100)

        def create_and_render():
            try:
                for _ in range(20):
                    pattern = BreathingPattern(16)
                    for _ in range(10):
                        pixels = pattern.render(base_color)
                        assert len(pixels) == 16
                        pattern.advance()
            except Exception as e:
                errors.append(e)

        # Multiple threads creating and rendering patterns
        threads = [threading.Thread(target=create_and_render) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # No errors should occur
        assert len(errors) == 0, f"Errors occurred: {errors}"


# =============================================================================
# Integration Tests
# =============================================================================

class TestValidationIntegration:
    """Integration tests combining all validation fixes."""

    def test_pattern_with_invalid_config(self):
        """Pattern creation with invalid config should fail immediately."""
        # Invalid speed
        with pytest.raises(ValueError, match="speed"):
            config = PatternConfig(speed=10.0)
            BreathingPattern(16, config)

        # Invalid brightness
        with pytest.raises(ValueError, match="brightness"):
            config = PatternConfig(brightness=2.0)
            BreathingPattern(16, config)

    def test_safety_manager_with_pattern_config(self):
        """Safety manager and pattern config validations work together."""
        manager = LEDSafetyManager(power_source=PowerSource.PI_5V_RAIL)
        ring = LEDRingProfile(gpio_pin=18, pwm_channel=0, name="Eye")
        manager.register_ring("ring1", ring)

        # Valid pattern config
        config = PatternConfig(speed=1.0, brightness=0.5)
        pattern = BreathingPattern(16, config)

        # Valid estimate_current call
        estimate = manager.estimate_current({"ring1": 128})
        assert estimate.total_ma > 0

        # Invalid estimate_current call
        with pytest.raises(ValueError):
            manager.estimate_current({"ring1": -10})

    def test_all_validations_catch_edge_cases(self):
        """All validation fixes catch their respective edge cases."""
        # PatternConfig catches NaN
        with pytest.raises(ValueError, match="must be finite"):
            PatternConfig(speed=float('nan'))

        with pytest.raises(ValueError, match="must be finite"):
            PatternConfig(brightness=float('inf'))

        # estimate_current catches type errors
        manager = LEDSafetyManager()
        ring = LEDRingProfile(gpio_pin=18, pwm_channel=0, name="Eye")
        manager.register_ring("ring1", ring)

        with pytest.raises(TypeError, match="must be int"):
            manager.estimate_current({"ring1": 128.5})

        # Thread safety doesn't break with stress
        pattern = BreathingPattern(16)
        threads = []
        for _ in range(10):
            t = threading.Thread(target=lambda: pattern.render((100, 100, 100)))
            threads.append(t)
            t.start()
        for t in threads:
            t.join()


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
