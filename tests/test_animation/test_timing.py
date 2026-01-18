#!/usr/bin/env python3
"""
TDD Test Suite for Animation Timing System

Tests keyframes, sequences, and easing functions.

Run with: pytest tests/test_animation/test_timing.py -v

Author: Boston Dynamics Animation Systems Engineer
Created: 18 January 2026
"""

import pytest
import time
import sys
from pathlib import Path

# Add firmware/src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'src'))

from animation.easing import (
    ease, ease_linear, ease_in, ease_out, ease_in_out,
    EASING_LUTS
)
from animation.timing import Keyframe, AnimationSequence, AnimationPlayer


# =============================================================================
# Easing Function Tests
# =============================================================================

class TestEasingFunctions:
    """Tests for easing function module."""

    def test_linear_at_zero(self):
        """Linear easing at t=0 returns 0."""
        assert ease_linear(0.0) == 0.0

    def test_linear_at_one(self):
        """Linear easing at t=1 returns 1."""
        assert ease_linear(1.0) == 1.0

    def test_linear_at_half(self):
        """Linear easing at t=0.5 returns 0.5."""
        assert ease_linear(0.5) == 0.5

    def test_ease_in_slow_start(self):
        """Ease-in is slower than linear at t=0.25."""
        linear_val = ease_linear(0.25)
        ease_in_val = ease_in(0.25)
        assert ease_in_val < linear_val

    def test_ease_out_fast_start(self):
        """Ease-out is faster than linear at t=0.25."""
        linear_val = ease_linear(0.25)
        ease_out_val = ease_out(0.25)
        assert ease_out_val > linear_val

    def test_ease_in_out_symmetric(self):
        """Ease-in-out is 0.5 at midpoint."""
        assert abs(ease_in_out(0.5) - 0.5) < 0.01

    def test_ease_in_out_slow_at_start(self):
        """Ease-in-out is slower than linear at start."""
        assert ease_in_out(0.25) < ease_linear(0.25)

    def test_ease_in_out_slow_at_end(self):
        """Ease-in-out is slower than linear near end."""
        assert ease_in_out(0.75) > ease_linear(0.75)

    def test_ease_function_clamps_input(self):
        """Ease function clamps input to 0-1."""
        assert ease(-0.5, 'linear') == 0.0
        assert ease(1.5, 'linear') == 1.0

    def test_ease_function_validates_type(self):
        """Ease function raises error for invalid type."""
        with pytest.raises(ValueError):
            ease(0.5, 'invalid_easing')

    def test_all_easing_types_in_luts(self):
        """All documented easing types have lookup tables."""
        expected_types = ['linear', 'ease_in', 'ease_out', 'ease_in_out']
        for etype in expected_types:
            assert etype in EASING_LUTS
            assert len(EASING_LUTS[etype]) == 101  # 0-100 = 101 entries


# =============================================================================
# Keyframe Tests
# =============================================================================

class TestKeyframe:
    """Tests for Keyframe dataclass."""

    def test_basic_keyframe_with_color(self):
        """Create basic keyframe with color."""
        kf = Keyframe(time_ms=100, color=(255, 128, 64))
        assert kf.time_ms == 100
        assert kf.color == (255, 128, 64)
        assert kf.easing == 'ease_in_out'  # Default

    def test_keyframe_with_brightness(self):
        """Create keyframe with brightness."""
        kf = Keyframe(time_ms=200, brightness=0.75)
        assert kf.brightness == 0.75

    def test_keyframe_with_position(self):
        """Create keyframe with position."""
        kf = Keyframe(time_ms=300, position=(0.5, -0.3))
        assert kf.position == (0.5, -0.3)

    def test_keyframe_with_easing(self):
        """Create keyframe with custom easing."""
        kf = Keyframe(time_ms=200, color=(100, 100, 100), easing='linear')
        assert kf.easing == 'linear'

    def test_keyframe_negative_time_raises(self):
        """Negative time raises ValueError."""
        with pytest.raises(ValueError):
            Keyframe(time_ms=-100)

    def test_keyframe_invalid_easing_raises(self):
        """Invalid easing type raises ValueError."""
        with pytest.raises(ValueError):
            Keyframe(time_ms=100, easing='invalid')

    def test_keyframe_invalid_brightness_raises(self):
        """Invalid brightness raises ValueError."""
        with pytest.raises(ValueError):
            Keyframe(time_ms=100, brightness=1.5)

    def test_keyframe_invalid_color_raises(self):
        """Invalid color raises ValueError."""
        with pytest.raises(ValueError):
            Keyframe(time_ms=100, color=(256, 128, 64))

    def test_keyframe_with_metadata(self):
        """Keyframe can have custom metadata."""
        kf = Keyframe(time_ms=500, metadata={'pattern': 'spin', 'speed': 2.0})
        assert kf.metadata['pattern'] == 'spin'
        assert kf.metadata['speed'] == 2.0


# =============================================================================
# AnimationSequence Tests
# =============================================================================

class TestAnimationSequence:
    """Tests for AnimationSequence class."""

    def test_empty_sequence_returns_empty(self):
        """Empty sequence returns empty dict."""
        seq = AnimationSequence("test")
        assert seq.get_values(0) == {}
        assert seq.get_values(100) == {}

    def test_single_keyframe_returns_values(self):
        """Single keyframe returns its values at all times."""
        seq = AnimationSequence("test")
        seq.add_keyframe(0, color=(255, 0, 0))

        assert seq.get_values(0)['color'] == (255, 0, 0)
        assert seq.get_values(100)['color'] == (255, 0, 0)
        assert seq.get_values(1000)['color'] == (255, 0, 0)

    def test_color_interpolation_linear(self):
        """Linear easing interpolates colors linearly."""
        seq = AnimationSequence("test")
        seq.add_keyframe(0, color=(0, 0, 0), easing='linear')
        seq.add_keyframe(100, color=(100, 200, 50), easing='linear')

        # At midpoint, should be halfway
        values = seq.get_values(50)
        assert abs(values['color'][0] - 50) < 1
        assert abs(values['color'][1] - 100) < 1
        assert abs(values['color'][2] - 25) < 1

    def test_brightness_interpolation(self):
        """Brightness interpolates correctly."""
        seq = AnimationSequence("test")
        seq.add_keyframe(0, brightness=0.0, easing='linear')
        seq.add_keyframe(100, brightness=1.0, easing='linear')

        values = seq.get_values(50)
        assert abs(values['brightness'] - 0.5) < 0.01

    def test_position_interpolation(self):
        """Position interpolates correctly."""
        seq = AnimationSequence("test")
        seq.add_keyframe(0, position=(0.0, 0.0), easing='linear')
        seq.add_keyframe(100, position=(1.0, 2.0), easing='linear')

        values = seq.get_values(50)
        assert abs(values['position'][0] - 0.5) < 0.01
        assert abs(values['position'][1] - 1.0) < 0.01

    def test_ease_in_slower_at_start(self):
        """Ease-in interpolation is below linear at start."""
        seq = AnimationSequence("test")
        seq.add_keyframe(0, brightness=0.0, easing='ease_in')
        seq.add_keyframe(100, brightness=1.0, easing='ease_in')

        # At 25%, should be less than 0.25
        values = seq.get_values(25)
        assert values['brightness'] < 0.25

    def test_ease_out_faster_at_start(self):
        """Ease-out interpolation is above linear at start."""
        seq = AnimationSequence("test")
        seq.add_keyframe(0, brightness=0.0, easing='ease_out')
        seq.add_keyframe(100, brightness=1.0, easing='ease_out')

        # At 25%, should be more than 0.25
        values = seq.get_values(25)
        assert values['brightness'] > 0.25

    def test_ease_in_out_symmetric(self):
        """Ease-in-out is at midpoint at 50%."""
        seq = AnimationSequence("test")
        seq.add_keyframe(0, brightness=0.0)  # Default ease_in_out
        seq.add_keyframe(100, brightness=1.0)

        values = seq.get_values(50)
        assert abs(values['brightness'] - 0.5) < 0.05

    def test_multiple_keyframes(self):
        """Sequence interpolates through multiple keyframes."""
        seq = AnimationSequence("test")
        seq.add_keyframe(0, brightness=0.0, easing='linear')
        seq.add_keyframe(100, brightness=0.5, easing='linear')
        seq.add_keyframe(200, brightness=1.0, easing='linear')

        # Check interpolation at various points
        assert abs(seq.get_values(0)['brightness'] - 0.0) < 0.01
        assert abs(seq.get_values(50)['brightness'] - 0.25) < 0.01
        assert abs(seq.get_values(100)['brightness'] - 0.5) < 0.01
        assert abs(seq.get_values(150)['brightness'] - 0.75) < 0.01
        assert abs(seq.get_values(200)['brightness'] - 1.0) < 0.01

    def test_keyframes_auto_sort(self):
        """Keyframes are sorted by time regardless of add order."""
        seq = AnimationSequence("test")
        seq.add_keyframe(200, brightness=1.0, easing='linear')
        seq.add_keyframe(0, brightness=0.0, easing='linear')
        seq.add_keyframe(100, brightness=0.5, easing='linear')

        # Should still interpolate correctly
        assert abs(seq.get_values(50)['brightness'] - 0.25) < 0.01

    def test_multiple_properties(self):
        """Interpolates multiple properties independently."""
        seq = AnimationSequence("test")
        seq.add_keyframe(0, color=(0, 0, 0), brightness=0.0, easing='linear')
        seq.add_keyframe(100, color=(100, 200, 50), brightness=1.0, easing='linear')

        values = seq.get_values(50)
        assert abs(values['color'][0] - 50) < 1
        assert abs(values['brightness'] - 0.5) < 0.01

    def test_looping_sequence(self):
        """Looping sequence wraps time."""
        seq = AnimationSequence("test", loop=True)
        seq.add_keyframe(0, brightness=0.0, easing='linear')
        seq.add_keyframe(100, brightness=1.0, easing='linear')

        # At 150ms with 100ms loop, should be at 50ms position
        values = seq.get_values(150)
        assert abs(values['brightness'] - 0.5) < 0.01

    def test_duration_property(self):
        """Duration reflects last keyframe time."""
        seq = AnimationSequence("test")
        seq.add_keyframe(0, brightness=0.0)
        seq.add_keyframe(500, brightness=0.5)
        seq.add_keyframe(1000, brightness=1.0)

        assert seq.duration_ms == 1000

    def test_method_chaining(self):
        """add_keyframe returns self for chaining."""
        seq = AnimationSequence("test")
        result = seq.add_keyframe(0, brightness=0.0)
        assert result is seq

        # Can chain
        seq.add_keyframe(100, brightness=0.5).add_keyframe(200, brightness=1.0)
        assert seq.get_keyframe_count() == 3

    def test_clear_sequence(self):
        """Clear removes all keyframes."""
        seq = AnimationSequence("test")
        seq.add_keyframe(0, brightness=0.0)
        seq.add_keyframe(100, brightness=1.0)

        seq.clear()

        assert seq.get_keyframe_count() == 0
        assert seq.duration_ms == 0


# =============================================================================
# AnimationPlayer Tests
# =============================================================================

class TestAnimationPlayer:
    """Tests for AnimationPlayer class."""

    @pytest.fixture
    def simple_sequence(self):
        """Create a simple test sequence."""
        seq = AnimationSequence("test")
        seq.add_keyframe(0, brightness=0.0, easing='linear')
        seq.add_keyframe(1000, brightness=1.0, easing='linear')
        return seq

    def test_initial_state(self, simple_sequence):
        """Player starts in stopped state."""
        player = AnimationPlayer(simple_sequence)
        assert not player.is_playing()
        assert player.get_current_time_ms() == 0

    def test_play_starts_playback(self, simple_sequence):
        """Play method starts playback."""
        player = AnimationPlayer(simple_sequence)
        player.play()
        assert player.is_playing()

    def test_pause_stops_playback(self, simple_sequence):
        """Pause method stops playback."""
        player = AnimationPlayer(simple_sequence)
        player.play()
        player.pause()
        assert not player.is_playing()

    def test_stop_resets_to_beginning(self, simple_sequence):
        """Stop method resets to beginning."""
        player = AnimationPlayer(simple_sequence)
        player.play()
        time.sleep(0.1)
        player.stop()

        assert not player.is_playing()
        assert player.get_current_time_ms() == 0

    def test_update_returns_interpolated_values(self, simple_sequence):
        """Update returns current interpolated positions."""
        player = AnimationPlayer(simple_sequence)
        player.play()

        # Wait a bit
        time.sleep(0.1)

        values = player.update()
        assert 'brightness' in values
        # Should have progressed from 0
        assert values['brightness'] > 0

    def test_non_looping_sequence_stops_at_end(self, simple_sequence):
        """Non-looping sequence stops at end."""
        player = AnimationPlayer(simple_sequence)
        player.play(speed=100.0)  # Fast playback

        # Wait for sequence to complete
        time.sleep(0.1)
        player.update()

        # Should have stopped
        assert not player.is_playing()

    def test_speed_multiplier(self, simple_sequence):
        """Speed multiplier affects playback rate."""
        player = AnimationPlayer(simple_sequence)
        player.play(speed=2.0)

        time.sleep(0.05)  # 50ms

        # At 2x speed, should have advanced ~100ms worth
        time_ms = player.get_current_time_ms()
        assert time_ms > 80  # Allow for timing variance

    def test_frame_perfect_timing(self, simple_sequence):
        """wait_for_next_frame maintains precise timing."""
        player = AnimationPlayer(simple_sequence, target_fps=50)
        player.play()

        # Measure 10 frames
        start = time.monotonic()
        for _ in range(10):
            player.update()
            player.wait_for_next_frame()
        elapsed = time.monotonic() - start

        # Should be very close to 10 * (1/50) = 0.2 seconds
        expected = 10 / 50
        # Windows timing is less precise, allow 20ms tolerance
        assert abs(elapsed - expected) < 0.02  # Within 20ms


# =============================================================================
# Performance Tests
# =============================================================================

class TestAnimationPerformance:
    """Performance tests for animation system."""

    def test_easing_lookup_performance(self):
        """Easing lookup is fast (O(1))."""
        start = time.monotonic()

        for _ in range(10000):
            ease_in_out(0.5)

        elapsed = time.monotonic() - start
        avg_us = (elapsed / 10000) * 1_000_000

        # Should be very fast (<10us per lookup)
        assert avg_us < 10, f"Easing lookup too slow: {avg_us:.2f}us"

    def test_sequence_interpolation_performance(self):
        """Sequence interpolation is fast."""
        seq = AnimationSequence("test")
        seq.add_keyframe(0, color=(0, 0, 0), brightness=0.0, position=(0, 0))
        seq.add_keyframe(500, color=(128, 128, 128), brightness=0.5, position=(0.5, 0.5))
        seq.add_keyframe(1000, color=(255, 255, 255), brightness=1.0, position=(1, 1))

        start = time.monotonic()

        for i in range(1000):
            seq.get_values(i)

        elapsed = time.monotonic() - start
        avg_us = (elapsed / 1000) * 1_000_000

        # Should be under 100us per interpolation
        assert avg_us < 100, f"Interpolation too slow: {avg_us:.2f}us"


# =============================================================================
# Integration Tests
# =============================================================================

class TestIntegration:
    """Integration tests for complete animation workflows."""

    def test_color_fade_animation(self):
        """Create a color fade animation sequence."""
        seq = AnimationSequence("fade")
        seq.add_keyframe(0, color=(0, 0, 0), brightness=0.0, easing='ease_in')
        seq.add_keyframe(1000, color=(255, 255, 255), brightness=1.0, easing='ease_out')

        player = AnimationPlayer(seq, target_fps=50)
        player.play()

        # Sample at various points
        for _ in range(10):
            values = player.update()
            assert 'color' in values
            assert 'brightness' in values
            player.wait_for_next_frame()

        player.stop()

    def test_looping_pulse_animation(self):
        """Create a looping pulse animation."""
        seq = AnimationSequence("pulse", loop=True)
        seq.add_keyframe(0, brightness=0.3, easing='ease_in_out')
        seq.add_keyframe(500, brightness=1.0, easing='ease_in_out')
        seq.add_keyframe(1000, brightness=0.3, easing='ease_in_out')

        player = AnimationPlayer(seq)
        player.play()

        # Should loop indefinitely
        time.sleep(0.05)
        assert player.is_playing()

        player.stop()


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
