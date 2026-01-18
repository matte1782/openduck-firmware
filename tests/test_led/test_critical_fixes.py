#!/usr/bin/env python3
"""
Critical Security Fixes Test Suite for LED System

Tests for the 3 CRITICAL issues fixed on Day 3 (18 Jan 2026):
1. CRITICAL-1: Division by zero in PatternBase.get_progress()
2. CRITICAL-2: Integer overflow in frame counter
3. CRITICAL-3: Race condition in LEDSafetyManager GPIO initialization

These tests ensure the fixes work correctly and prevent regressions.

Author: Boston Dynamics Security Team
Created: 18 January 2026
"""

import pytest
import sys
import threading
import time
from pathlib import Path

# Add firmware/src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'src'))

from led.patterns import PatternBase, PatternConfig, BreathingPattern
from safety.led_safety import LEDSafetyManager, PowerSource, LEDRingProfile


# =============================================================================
# CRITICAL-1: Division by Zero Fix Tests
# =============================================================================

class TestCritical1DivisionByZeroFix:
    """Tests for CRITICAL-1: Division by zero in get_progress().

    Issue: If cycle_frames == 0, crashes with ZeroDivisionError
    Fix: Added validation to raise ValueError for cycle_frames <= 0
    """

    def test_get_progress_zero_cycle_frames_raises_error(self):
        """get_progress() with cycle_frames=0 raises ValueError."""
        pattern = BreathingPattern(16)

        with pytest.raises(ValueError, match="cycle_frames must be positive, got 0"):
            pattern.get_progress(0)

    def test_get_progress_negative_cycle_frames_raises_error(self):
        """get_progress() with negative cycle_frames raises ValueError."""
        pattern = BreathingPattern(16)

        with pytest.raises(ValueError, match="cycle_frames must be positive, got -10"):
            pattern.get_progress(-10)

    def test_get_progress_positive_cycle_frames_works(self):
        """get_progress() with positive cycle_frames returns valid result."""
        pattern = BreathingPattern(16)

        # Should work without error
        progress = pattern.get_progress(100)

        # Progress should be in range [0.0, 1.0)
        assert 0.0 <= progress < 1.0

    def test_get_progress_does_not_divide_by_zero(self):
        """get_progress() never performs division by zero."""
        pattern = BreathingPattern(16)

        # Try various invalid values - all should raise ValueError, not ZeroDivisionError
        for invalid_frames in [0, -1, -100]:
            with pytest.raises(ValueError):
                pattern.get_progress(invalid_frames)


# =============================================================================
# CRITICAL-2: Integer Overflow Fix Tests
# =============================================================================

class TestCritical2IntegerOverflowFix:
    """Tests for CRITICAL-2: Integer overflow in frame counter.

    Issue: _frame counter unbounded, causes precision loss after 49+ days
    Fix: Wrap frame counter to 0 when abs(_frame) > 1_000_000
    """

    def test_frame_counter_wraps_at_threshold_forward(self):
        """Frame counter wraps to 0 when reaching 1,000,000 (forward)."""
        pattern = BreathingPattern(16)

        # Set frame to last valid value before wrapping
        pattern._frame = 999_999

        # Advance one frame
        pattern.advance()

        # Should wrap to 0 smoothly (1,000,000 % 1,000,000 = 0)
        assert pattern._frame == 0

    def test_frame_counter_wraps_at_threshold_reverse(self):
        """Frame counter wraps to 999,999 when going below 0 (reverse)."""
        config = PatternConfig(reverse=True)
        pattern = BreathingPattern(16, config)

        # Set frame to 0
        pattern._frame = 0

        # Advance one frame in reverse (decrement)
        pattern.advance()

        # Should wrap to 999,999 smoothly ((-1) % 1,000,000 = 999,999)
        assert pattern._frame == 999_999

    def test_frame_counter_stays_below_threshold(self):
        """Frame counter stays below 1,000,000 during normal operation."""
        pattern = BreathingPattern(16)

        # Advance many frames (simulate long runtime)
        for _ in range(10_000):
            pattern.advance()

        # Should still be manageable
        assert abs(pattern._frame) <= 1_000_000

    def test_no_precision_loss_after_wrap(self):
        """Pattern continues to work correctly after frame wrap."""
        pattern = BreathingPattern(16)
        base_color = (255, 0, 0)

        # Set to last frame before wrapping
        pattern._frame = 999_999
        pattern.advance()

        # Should have wrapped to 0 smoothly
        assert pattern._frame == 0

        # Pattern should still render correctly after wrap
        pixels = pattern.render(base_color)
        assert len(pixels) == 16
        assert all(0 <= r <= 255 and 0 <= g <= 255 and 0 <= b <= 255
                   for r, g, b in pixels)

    def test_frame_counter_wraps_exactly_at_boundary(self):
        """Frame counter wraps exactly at boundary (999,999 → 0)."""
        pattern = BreathingPattern(16)

        # Test exact boundary: last valid frame before wrap
        pattern._frame = 999_999

        pattern.advance()
        assert pattern._frame == 0  # Wrapped smoothly to 0


# =============================================================================
# CRITICAL-3: Race Condition Fix Tests
# =============================================================================

class TestCritical3RaceConditionFix:
    """Tests for CRITICAL-3: Race condition in GPIO initialization.

    Issue: GPIO initialization outside lock, thread-unsafe
    Fix: Moved GPIO initialization inside lock
    """

    def test_gpio_initialization_thread_safe(self):
        """GPIO initialization is thread-safe (no race condition)."""
        results = []
        errors = []

        def create_manager():
            try:
                # Create manager (will initialize GPIO)
                manager = LEDSafetyManager(power_source=PowerSource.PI_5V_RAIL)
                results.append(manager.gpio_available)
            except Exception as e:
                errors.append(e)

        # Create multiple managers simultaneously from different threads
        threads = [threading.Thread(target=create_manager) for _ in range(10)]

        for t in threads:
            t.start()

        for t in threads:
            t.join()

        # All threads should complete without errors
        assert len(errors) == 0, f"Errors occurred: {errors}"

        # All threads should get consistent results
        assert len(results) == 10
        # All should be False (no RPi.GPIO on dev machine) or all True (on Pi)
        assert len(set(results)) == 1, "Inconsistent GPIO availability across threads"

    def test_gpio_initialization_with_mock_provider(self):
        """GPIO initialization works correctly with mock provider."""
        class MockGPIO:
            BCM = 11
            OUT = 1
            def setmode(self, mode): pass
            def setup(self, pin, direction): pass
            def cleanup(self, pin=None): pass

        mock_gpio = MockGPIO()

        # Should initialize without error
        manager = LEDSafetyManager(gpio_provider=mock_gpio)

        # GPIO should be available
        assert manager.gpio_available is True
        assert manager._gpio is mock_gpio

    def test_gpio_initialization_concurrent_reads(self):
        """GPIO availability can be checked concurrently after initialization."""
        manager = LEDSafetyManager(power_source=PowerSource.PI_5V_RAIL)

        results = []

        def check_gpio():
            for _ in range(100):
                results.append(manager.gpio_available)

        # Multiple threads checking GPIO availability
        threads = [threading.Thread(target=check_gpio) for _ in range(5)]

        for t in threads:
            t.start()

        for t in threads:
            t.join()

        # All reads should return the same value
        assert len(set(results)) == 1, "Inconsistent GPIO availability reads"

    def test_no_race_in_gpio_provider_assignment(self):
        """GPIO provider assignment is atomic and thread-safe."""
        class MockGPIO:
            BCM = 11
            OUT = 1
            def setmode(self, mode): pass
            def setup(self, pin, direction): pass
            def cleanup(self, pin=None): pass

        managers = []

        def create_with_mock():
            mock = MockGPIO()
            manager = LEDSafetyManager(gpio_provider=mock)
            managers.append(manager)

        # Create managers concurrently
        threads = [threading.Thread(target=create_with_mock) for _ in range(5)]

        for t in threads:
            t.start()

        for t in threads:
            t.join()

        # All managers should have their own GPIO provider
        assert len(managers) == 5
        for manager in managers:
            assert manager.gpio_available is True
            assert manager._gpio is not None


# =============================================================================
# Integration Tests - All 3 Fixes Together
# =============================================================================

class TestAllCriticalFixesIntegration:
    """Integration tests to ensure all 3 fixes work together."""

    def test_pattern_with_safety_manager_long_runtime(self):
        """Pattern and safety manager work correctly during long runtime."""
        # Setup
        manager = LEDSafetyManager(power_source=PowerSource.PI_5V_RAIL)
        ring = LEDRingProfile(gpio_pin=18, pwm_channel=0, name="Test Ring")
        manager.register_ring("test", ring)

        pattern = BreathingPattern(16)
        base_color = (255, 0, 0)

        # Simulate very long runtime (force frame wrap)
        pattern._frame = 999_999

        # Run through wrap and beyond
        for i in range(100):
            # Check safety
            valid, reason = manager.validate_gpio_available("test")
            assert valid, f"Safety check failed at frame {i}: {reason}"

            # Render pattern
            pixels = pattern.render(base_color)
            assert len(pixels) == 16

            # Get progress (test CRITICAL-1 fix)
            progress = pattern.get_progress(200)  # Valid cycle_frames
            assert 0.0 <= progress < 1.0

            # Advance (test CRITICAL-2 fix)
            pattern.advance()

            # Verify frame wrapped if necessary
            assert abs(pattern._frame) <= 1_000_000

    def test_all_fixes_under_concurrent_load(self):
        """All fixes work correctly under concurrent load."""
        manager = LEDSafetyManager(power_source=PowerSource.PI_5V_RAIL)
        ring = LEDRingProfile(gpio_pin=18, pwm_channel=0, name="Test Ring")
        manager.register_ring("test", ring)

        pattern = BreathingPattern(16)
        base_color = (100, 150, 200)

        errors = []

        def worker():
            try:
                for _ in range(1000):
                    # Test all critical fixes
                    pixels = pattern.render(base_color)
                    pattern.advance()

                    # Test CRITICAL-1 (valid call)
                    progress = pattern.get_progress(100)
                    assert 0.0 <= progress < 1.0

                    # Test CRITICAL-3 (concurrent safety checks)
                    valid, _ = manager.validate_gpio_available("test")
            except Exception as e:
                errors.append(e)

        # Run multiple workers concurrently
        threads = [threading.Thread(target=worker) for _ in range(3)]

        for t in threads:
            t.start()

        for t in threads:
            t.join()

        # No errors should occur
        assert len(errors) == 0, f"Errors during concurrent operation: {errors}"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
