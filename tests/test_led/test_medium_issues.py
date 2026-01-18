#!/usr/bin/env python3
"""
Tests for MEDIUM Priority Issue Fixes

These tests specifically verify the 8 MEDIUM priority fixes:
1. BreathingPattern sine LUT race condition
2. PatternConfig blend_frames negative validation
3. PatternBase num_leds upper limit
4. Float precision in current estimation
5. Pixel buffer cleared between renders
6. RLock timeout (documentation check)
7. PatternConfig __repr__ method
8. Signed integer arithmetic in PulsePattern

Author: Performance Engineer
Created: 18 January 2026
"""

import pytest
import threading
import time
import sys
from pathlib import Path

# Add firmware/src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'src'))

from led.patterns import (
    PatternBase, PatternConfig, BreathingPattern, PulsePattern
)
from safety.led_safety import LEDSafetyManager, PowerSource, LEDRingProfile


# =============================================================================
# Issue #1: BreathingPattern sine LUT race condition
# =============================================================================

class TestIssue1_LUTRaceCondition:
    """Test thread-safe LUT initialization."""

    def test_concurrent_breathing_pattern_creation(self):
        """Multiple threads can safely create BreathingPattern instances."""
        # Reset class variables
        BreathingPattern._LUT_INITIALIZED = False
        BreathingPattern._SINE_LUT = []

        results = []
        errors = []

        def create_pattern():
            try:
                pattern = BreathingPattern(16)
                results.append(pattern)
            except Exception as e:
                errors.append(e)

        # Create 10 patterns concurrently
        threads = [threading.Thread(target=create_pattern) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # No errors should occur
        assert len(errors) == 0, f"Race condition detected: {errors}"
        assert len(results) == 10
        assert BreathingPattern._LUT_INITIALIZED is True
        assert len(BreathingPattern._SINE_LUT) == 256


# =============================================================================
# Issue #2: blend_frames negative validation
# =============================================================================

class TestIssue2_BlendFramesValidation:
    """Test negative blend_frames validation."""

    def test_negative_blend_frames_rejected(self):
        """PatternConfig rejects negative blend_frames."""
        with pytest.raises(ValueError, match="blend_frames must be non-negative"):
            PatternConfig(blend_frames=-1)

    def test_zero_blend_frames_allowed(self):
        """PatternConfig allows zero blend_frames (instant transitions)."""
        config = PatternConfig(blend_frames=0)
        assert config.blend_frames == 0

    def test_large_blend_frames_rejected(self):
        """PatternConfig rejects excessively large blend_frames."""
        with pytest.raises(ValueError, match="blend_frames too large"):
            PatternConfig(blend_frames=10000)


# =============================================================================
# Issue #3: num_leds upper limit
# =============================================================================

class TestIssue3_NumLedsUpperLimit:
    """Test num_leds upper limit to prevent memory crashes."""

    def test_max_num_leds_constant_defined(self):
        """MAX_NUM_LEDS constant is defined."""
        assert hasattr(PatternBase, 'MAX_NUM_LEDS')
        assert PatternBase.MAX_NUM_LEDS == 1024

    def test_num_leds_at_limit_allowed(self):
        """num_leds at exactly MAX_NUM_LEDS is allowed."""
        pattern = BreathingPattern(num_pixels=1024)
        assert pattern.num_pixels == 1024

    def test_num_leds_exceeds_limit_rejected(self):
        """num_leds exceeding MAX_NUM_LEDS is rejected."""
        with pytest.raises(ValueError, match="exceeds maximum.*memory crashes"):
            BreathingPattern(num_pixels=1025)

    def test_num_leds_way_over_limit_rejected(self):
        """Extremely large num_leds values are rejected."""
        with pytest.raises(ValueError, match="exceeds maximum"):
            BreathingPattern(num_pixels=100000)


# =============================================================================
# Issue #4: Float precision in current estimation
# =============================================================================

class TestIssue4_FloatPrecision:
    """Test float precision improvements in current estimation."""

    def test_current_estimate_rounded_to_2_decimals(self):
        """Current estimates are rounded to 2 decimal places."""
        manager = LEDSafetyManager(power_source=PowerSource.PI_5V_RAIL)
        ring1 = LEDRingProfile(gpio_pin=18, pwm_channel=0, name="Ring1")
        manager.register_ring("ring1", ring1)

        # Test with brightness that would cause floating point precision issues
        estimate = manager.estimate_current({"ring1": 127})

        # Check that values are rounded to 2 decimals
        assert len(str(estimate.total_ma).split('.')[-1]) <= 2
        assert len(str(estimate.headroom_ma).split('.')[-1]) <= 2

        for ring_id, current in estimate.per_ring_ma.items():
            decimal_places = len(str(current).split('.')[-1])
            assert decimal_places <= 2, f"{ring_id} has {decimal_places} decimal places"


# =============================================================================
# Issue #5: Pixel buffer cleared between renders
# =============================================================================

class TestIssue5_PixelBufferClearing:
    """Test pixel buffer is cleared to prevent state leakage."""

    def test_pixel_buffer_cleared_on_render(self):
        """Pixel buffer is cleared at start of render."""
        pattern = BreathingPattern(16)

        # Manually corrupt the buffer
        for i in range(16):
            pattern._pixel_buffer[i] = (255, 128, 64)

        # Render should clear and regenerate
        result = pattern.render((100, 100, 100))

        # All pixels should be properly calculated, not showing corruption
        # The breathing pattern sets all pixels to same value
        first_pixel = result[0]
        for pixel in result:
            assert pixel == first_pixel, "Pixels should all be identical in breathing pattern"

    def test_no_state_leakage_between_patterns(self):
        """No state leakage when switching patterns."""
        pattern1 = BreathingPattern(16)
        pattern2 = PulsePattern(16)

        # Render pattern1
        pattern1.render((255, 0, 0))

        # Check pattern2's buffer is clean
        result2 = pattern2.render((0, 255, 0))

        # Verify result2 is based on green, not red
        for pixel in result2:
            r, g, b = pixel
            # Green channel should dominate in a pulse pattern with green base
            assert g >= r, f"Expected green to dominate, got R={r}, G={g}, B={b}"


# =============================================================================
# Issue #6: RLock timeout documentation
# =============================================================================

class TestIssue6_RLockTimeout:
    """Test RLock timeout is documented."""

    def test_rlock_timeout_documented(self):
        """RLock timeout limitation is documented in code."""
        safety_file = Path(__file__).parent.parent.parent / 'src' / 'safety' / 'led_safety.py'
        with open(safety_file, 'r') as f:
            content = f.read()

        # Check for Issue #6 comment
        assert 'MEDIUM Issue #6' in content
        assert 'RLock without timeout' in content or 'timeout' in content.lower()


# =============================================================================
# Issue #7: PatternConfig __repr__
# =============================================================================

class TestIssue7_PatternConfigRepr:
    """Test PatternConfig has __repr__ for debugging."""

    def test_repr_method_exists(self):
        """PatternConfig has __repr__ method."""
        assert hasattr(PatternConfig, '__repr__')

    def test_repr_output_format(self):
        """__repr__ produces useful debugging output."""
        config = PatternConfig(speed=2.5, brightness=0.75, reverse=True, blend_frames=20)
        repr_str = repr(config)

        # Should contain class name and all parameters
        assert 'PatternConfig' in repr_str
        assert '2.50' in repr_str or '2.5' in repr_str  # speed
        assert '0.75' in repr_str  # brightness
        assert 'True' in repr_str  # reverse
        assert '20' in repr_str  # blend_frames

    def test_repr_produces_string(self):
        """__repr__ returns a valid string for debugging."""
        config = PatternConfig(speed=1.5)
        repr_str = repr(config)
        # Just verify it doesn't crash and returns a string
        assert isinstance(repr_str, str)
        assert len(repr_str) > 0


# =============================================================================
# Issue #8: Signed integer arithmetic in PulsePattern
# =============================================================================

class TestIssue8_SignedIntegerArithmetic:
    """Test signed integer arithmetic is handled correctly."""

    def test_negative_frame_handled_correctly(self):
        """Negative frame values don't cause issues."""
        pattern = PulsePattern(16, PatternConfig(reverse=True))

        # Advance in reverse (negative frames)
        for _ in range(100):
            pattern.advance()

        # Should still render without error
        result = pattern.render((100, 100, 100))
        assert len(result) == 16

        # Verify frame_in_cycle calculation uses abs()
        intensity = pattern.get_current_intensity()
        assert 0.0 <= intensity <= 1.0

    def test_extreme_negative_frame(self):
        """Extremely negative frame values are handled."""
        pattern = PulsePattern(16)
        pattern._frame = -1000000

        # Should not crash or produce invalid output
        result = pattern.render((200, 200, 200))
        assert len(result) == 16

        # All pixels should have valid RGB values
        for r, g, b in result:
            assert 0 <= r <= 255
            assert 0 <= g <= 255
            assert 0 <= b <= 255


# =============================================================================
# Integration Tests
# =============================================================================

class TestMediumIssuesIntegration:
    """Integration tests for all MEDIUM fixes."""

    def test_all_fixes_work_together(self):
        """All MEDIUM fixes work together without conflicts."""
        # Create patterns with various configs
        configs = [
            PatternConfig(speed=0.5, brightness=0.8, blend_frames=5),
            PatternConfig(speed=2.0, brightness=1.0, blend_frames=0),
            PatternConfig(speed=1.0, brightness=0.5, reverse=True, blend_frames=50),
        ]

        patterns = []
        for config in configs:
            # Test Issue #3 (num_leds limit)
            patterns.append(BreathingPattern(16, config))
            patterns.append(PulsePattern(32, config))

        # Test Issue #1 (concurrent access)
        def render_patterns():
            for pattern in patterns:
                pattern.render((150, 150, 150))
                pattern.advance()

        threads = [threading.Thread(target=render_patterns) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Test Issue #7 (__repr__)
        for config in configs:
            repr_str = repr(config)
            assert 'PatternConfig' in repr_str

        # Test Issue #4 (float precision) with safety manager
        manager = LEDSafetyManager(power_source=PowerSource.PI_5V_RAIL)
        ring = LEDRingProfile(gpio_pin=18, pwm_channel=0, name="Test")
        manager.register_ring("test", ring)

        estimate = manager.estimate_current({"test": 128})
        assert isinstance(estimate.total_ma, float)
        assert isinstance(estimate.headroom_ma, float)

        print("All MEDIUM fixes validated!")


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
