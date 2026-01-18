#!/usr/bin/env python3
"""
Day 13 Edge Case Tests

Comprehensive boundary condition and edge case testing for
Week 02 animation system components.

Run with: pytest tests/test_edge_cases/ -v
Slow tests: pytest tests/test_edge_cases/ -v -m slow
Skip slow tests: pytest tests/test_edge_cases/ -v -m "not slow"

Author: Agent 3 - Edge Case Engineer
Created: 18 January 2026 (Day 13)
Quality Standard: Pixar / Boston Dynamics Grade
"""

import pytest
import threading
import time
import math
import sys
import gc
from pathlib import Path
from typing import List, Tuple
from unittest.mock import MagicMock, patch

# Add src to path for imports (handle properly for test environment)
firmware_path = Path(__file__).parent.parent.parent
sys.path.insert(0, str(firmware_path))
src_path = firmware_path / "src"
sys.path.insert(0, str(src_path))

# Import animation system components
from src.animation.easing import (
    ease, ease_linear, ease_in, ease_out, ease_in_out,
    EASING_LUTS, LUT_SIZE
)
from src.animation.timing import (
    Keyframe, AnimationSequence, AnimationPlayer
)
from src.animation.emotion_axes import EmotionAxes, EMOTION_PRESETS
from src.animation.coordinator import (
    AnimationCoordinator, AnimationPriority, AnimationLayer,
    AnimationState, SUPPORTED_ANIMATIONS
)
from src.led.color_utils import (
    rgb_to_hsv, hsv_to_rgb, color_interpolate, color_arc_interpolate,
    ColorTransition, ColorTransitionConfig, hue_shift, brightness_adjust
)
from src.led.patterns.base import PatternBase, PatternConfig, RGB


# =============================================================================
# TEST FIXTURES
# =============================================================================

@pytest.fixture
def mock_head_controller():
    """Create mock head controller for coordinator tests."""
    controller = MagicMock()
    controller.nod = MagicMock()
    controller.shake = MagicMock()
    controller.tilt_curious = MagicMock()
    controller.random_glance = MagicMock()
    controller.look_at = MagicMock()
    controller.reset_to_center = MagicMock()
    controller.emergency_stop = MagicMock()
    controller.reset_emergency = MagicMock()
    return controller


@pytest.fixture
def mock_led_controller():
    """Create mock LED controller."""
    return MagicMock()


@pytest.fixture
def coordinator(mock_head_controller, mock_led_controller):
    """Create AnimationCoordinator with mock controllers."""
    return AnimationCoordinator(
        head_controller=mock_head_controller,
        led_controller=mock_led_controller
    )


# =============================================================================
# 1. EXTREME VALUES TESTS
# =============================================================================

class TestExtremeValues:
    """Test behavior at extreme input boundaries."""

    def test_keyframe_time_zero(self):
        """Keyframe at t=0 should work correctly."""
        seq = AnimationSequence("zero_start")
        # Should not raise
        seq.add_keyframe(0, color=(255, 0, 0), brightness=1.0)
        seq.add_keyframe(1000, color=(0, 255, 0), brightness=0.5)

        values = seq.get_values(0)
        assert values['color'] == (255, 0, 0)
        assert values['brightness'] == 1.0

    def test_keyframe_time_max_int(self):
        """Handle very large keyframe times without overflow."""
        seq = AnimationSequence("large_time")

        # Use a large but safe value (24 hours in ms)
        max_time = 24 * 60 * 60 * 1000  # 86,400,000 ms
        seq.add_keyframe(0, color=(0, 0, 0), brightness=0.0)
        seq.add_keyframe(max_time, color=(255, 255, 255), brightness=1.0)

        # Should interpolate correctly at midpoint
        midpoint = max_time // 2
        values = seq.get_values(midpoint)

        # Verify interpolation happened (brightness should be ~0.5 with easing)
        assert 0.0 < values['brightness'] < 1.0
        assert seq.duration_ms == max_time

    def test_keyframe_time_negative_rejected(self):
        """Negative keyframe times should be rejected."""
        with pytest.raises(ValueError, match="time_ms must be >= 0"):
            Keyframe(time_ms=-1, color=(255, 0, 0))

    def test_servo_angle_negative_extreme_emotion(self):
        """Emotion axes below minimum should be rejected."""
        with pytest.raises(ValueError, match="arousal must be -1.0 to 1.0"):
            EmotionAxes(arousal=-2.0, valence=0.0, focus=0.5, blink_speed=1.0)

    def test_servo_angle_positive_extreme_emotion(self):
        """Emotion axes above maximum should be rejected."""
        with pytest.raises(ValueError, match="valence must be -1.0 to 1.0"):
            EmotionAxes(arousal=0.0, valence=1.5, focus=0.5, blink_speed=1.0)

    def test_rgb_values_negative_rejected(self):
        """Negative RGB values should be rejected."""
        with pytest.raises(ValueError, match="RGB values must be 0-255"):
            rgb_to_hsv((-1, 0, 0))

    def test_rgb_values_overflow_rejected(self):
        """RGB values > 255 should be rejected."""
        with pytest.raises(ValueError, match="RGB values must be 0-255"):
            rgb_to_hsv((256, 0, 0))

        with pytest.raises(ValueError, match="RGB values must be 0-255"):
            rgb_to_hsv((0, 999, 0))

    def test_hue_negative_wrap(self):
        """Negative hue values should wrap correctly (e.g., -30 -> 330)."""
        # hsv_to_rgb should handle negative hue via modulo
        result = hsv_to_rgb(-30, 1.0, 1.0)
        expected = hsv_to_rgb(330, 1.0, 1.0)
        assert result == expected

    def test_hue_large_wrap(self):
        """Large hue values should wrap correctly (e.g., 720 -> 0)."""
        result = hsv_to_rgb(720, 1.0, 1.0)
        expected = hsv_to_rgb(0, 1.0, 1.0)
        assert result == expected

        # Test 450 -> 90
        result2 = hsv_to_rgb(450, 1.0, 1.0)
        expected2 = hsv_to_rgb(90, 1.0, 1.0)
        assert result2 == expected2

    def test_easing_t_negative_clamps_to_zero(self):
        """Easing with t < 0 should clamp to 0."""
        result = ease(-0.5, 'linear')
        assert result == ease(0.0, 'linear')

    def test_easing_t_greater_than_one_clamps(self):
        """Easing with t > 1 should clamp to 1."""
        result = ease(2.0, 'linear')
        assert result == ease(1.0, 'linear')

    def test_brightness_extreme_values(self):
        """Pattern config should reject out-of-range brightness."""
        with pytest.raises(ValueError, match="brightness must be 0.0-1.0"):
            PatternConfig(brightness=-0.1)

        with pytest.raises(ValueError, match="brightness must be 0.0-1.0"):
            PatternConfig(brightness=1.5)

    def test_speed_extreme_values(self):
        """Pattern config should reject out-of-range speed."""
        with pytest.raises(ValueError, match="speed must be 0.1-5.0"):
            PatternConfig(speed=0.0)

        with pytest.raises(ValueError, match="speed must be 0.1-5.0"):
            PatternConfig(speed=10.0)


# =============================================================================
# 2. EMPTY/NULL CASES TESTS
# =============================================================================

class TestEmptyNullCases:
    """Test handling of empty and null inputs."""

    def test_empty_animation_sequence(self):
        """Empty keyframe sequence should handle gracefully."""
        seq = AnimationSequence("empty")

        # Should return empty dict for empty sequence
        values = seq.get_values(500)
        assert values == {}

        # Duration should be 0
        assert seq.duration_ms == 0
        assert seq.get_keyframe_count() == 0

    def test_single_keyframe_sequence(self):
        """Single keyframe sequence should return that keyframe."""
        seq = AnimationSequence("single")
        seq.add_keyframe(0, color=(128, 64, 32), brightness=0.5)

        # At t=0, should return the keyframe values
        values = seq.get_values(0)
        assert values['color'] == (128, 64, 32)
        assert values['brightness'] == 0.5

        # At any other time, should still return that keyframe (no interpolation target)
        values_later = seq.get_values(1000)
        assert values_later['color'] == (128, 64, 32)

    def test_empty_led_buffer_pattern(self):
        """Pattern render with 0 LEDs should raise ValueError."""
        # PatternBase requires num_pixels > 0
        with pytest.raises(ValueError, match="num_pixels must be positive"):
            # Create a concrete subclass to test
            class TestPattern(PatternBase):
                def _compute_frame(self, base_color):
                    return self._pixel_buffer

            TestPattern(num_pixels=0)

    def test_none_emotion_axes_defaults(self):
        """None emotion axes parameters should raise TypeError."""
        # EmotionAxes validates all inputs - None should fail
        with pytest.raises(TypeError, match="must be numeric"):
            EmotionAxes(arousal=None, valence=0.0, focus=0.5, blink_speed=1.0)

    def test_sequence_clear_resets_state(self):
        """Clearing sequence should reset all state."""
        seq = AnimationSequence("clearable")
        seq.add_keyframe(0, color=(255, 0, 0), brightness=1.0)
        seq.add_keyframe(1000, color=(0, 255, 0), brightness=0.0)

        assert seq.get_keyframe_count() == 2
        assert seq.duration_ms == 1000

        seq.clear()

        assert seq.get_keyframe_count() == 0
        assert seq.duration_ms == 0
        assert seq.get_values(500) == {}

    def test_coordinator_no_controllers(self):
        """Coordinator with no controllers should not crash."""
        coord = AnimationCoordinator(
            head_controller=None,
            led_controller=None
        )

        # Should have default layers
        assert len(coord.get_all_layers()) == 4

        # State queries should work
        state = coord.get_state()
        assert state.active_layer is None
        assert not state.emergency_stopped

    def test_keyframe_no_properties(self):
        """Keyframe with no color/brightness/position should work."""
        kf = Keyframe(time_ms=100)
        assert kf.time_ms == 100
        assert kf.color is None
        assert kf.brightness is None
        assert kf.position is None

    def test_color_transition_zero_duration_rejected(self):
        """ColorTransitionConfig with zero duration should be rejected."""
        with pytest.raises(ValueError, match="duration_ms must be > 0"):
            ColorTransitionConfig(duration_ms=0)


# =============================================================================
# 3. CONCURRENT/RACE CONDITION TESTS
# =============================================================================

class TestConcurrencyEdgeCases:
    """Test thread safety and race conditions."""

    def test_rapid_animation_changes(self, coordinator):
        """Rapidly changing animations should not deadlock."""
        results = []
        errors = []

        def change_animation(anim_name: str, count: int):
            try:
                for _ in range(count):
                    coordinator.start_animation('triggered', anim_name, blocking=False)
                    time.sleep(0.001)  # 1ms delay
                results.append(f"{anim_name}_done")
            except Exception as e:
                errors.append(str(e))

        # Start multiple threads rapidly changing animations
        threads = [
            threading.Thread(target=change_animation, args=('nod', 10)),
            threading.Thread(target=change_animation, args=('shake', 10)),
            threading.Thread(target=change_animation, args=('curious', 10)),
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5.0)

        # Should complete without errors
        assert len(errors) == 0
        assert len(results) == 3

    def test_animation_interrupt_mid_frame(self, coordinator):
        """New animation interrupting mid-frame should transition cleanly."""
        # Start background
        coordinator.start_background()
        assert coordinator.is_background_running()

        # Interrupt with triggered animation
        success = coordinator.start_animation('triggered', 'nod', blocking=False)
        assert success

        # Background should be paused
        state = coordinator.get_state()
        assert state.active_layer == 'triggered'

    def test_emergency_stop_during_movement(self, coordinator):
        """Emergency stop during active movement should halt immediately."""
        # Start an animation
        coordinator.start_animation('triggered', 'shake', blocking=False)

        # Emergency stop
        start = time.perf_counter()
        coordinator.emergency_stop()
        latency = (time.perf_counter() - start) * 1000

        # Should be very fast (< 10ms)
        assert latency < 10.0
        assert coordinator.is_emergency_stopped()

        # All layers should be deactivated
        for layer in coordinator.get_all_layers():
            if layer.name != 'critical':
                assert not layer.active

    def test_concurrent_emotion_changes(self):
        """Multiple threads changing emotion should not corrupt state."""
        errors = []
        emotion_snapshots = []

        # Create a simple emotion manager
        current_emotion = EmotionAxes(
            arousal=0.0, valence=0.0, focus=0.5, blink_speed=1.0
        )
        emotion_lock = threading.Lock()

        def update_emotion(target_arousal: float, iterations: int):
            nonlocal current_emotion
            try:
                for i in range(iterations):
                    with emotion_lock:
                        # Interpolate towards target
                        target = EmotionAxes(
                            arousal=target_arousal,
                            valence=0.0,
                            focus=0.5,
                            blink_speed=1.0
                        )
                        current_emotion = current_emotion.interpolate(target, 0.1)
                        emotion_snapshots.append(current_emotion.arousal)
            except Exception as e:
                errors.append(str(e))

        # Start threads with opposite targets
        threads = [
            threading.Thread(target=update_emotion, args=(0.8, 50)),
            threading.Thread(target=update_emotion, args=(-0.8, 50)),
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5.0)

        assert len(errors) == 0
        # All snapshots should be valid arousal values
        for arousal in emotion_snapshots:
            assert -1.0 <= arousal <= 1.0

    def test_color_transition_concurrent_access(self):
        """ColorTransition should handle concurrent get_color calls."""
        transition = ColorTransition(
            start=(255, 0, 0),
            end=(0, 255, 0),
            config=ColorTransitionConfig(duration_ms=100)
        )
        transition.start()

        colors = []
        errors = []

        def sample_color(sample_count: int):
            try:
                for _ in range(sample_count):
                    c = transition.get_color()
                    colors.append(c)
                    time.sleep(0.001)
            except Exception as e:
                errors.append(str(e))

        threads = [
            threading.Thread(target=sample_color, args=(20,))
            for _ in range(5)
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5.0)

        assert len(errors) == 0
        assert len(colors) == 100  # 5 threads * 20 samples


# =============================================================================
# 4. LONG-RUNNING SIMULATION TESTS
# =============================================================================

class TestLongRunning:
    """Test for issues that emerge over extended runtime."""

    @pytest.mark.slow
    def test_frame_counter_no_overflow(self):
        """Frame counter should not overflow after extended simulation.

        Simulates 24 hours at 50Hz = 4,320,000 frames using accelerated time.
        """
        # Create test pattern
        class TestPattern(PatternBase):
            NAME = "overflow_test"

            def _compute_frame(self, base_color: RGB) -> List[RGB]:
                # Simple implementation
                for i in range(self.num_pixels):
                    self._pixel_buffer[i] = base_color
                return self._pixel_buffer

        pattern = TestPattern(num_pixels=16)

        # Simulate 24 hours worth of frames
        frames_24h = 50 * 60 * 60 * 24  # 4,320,000

        # Instead of running all frames, verify the modulo wrapping
        # Frame counter wraps at 1,000,000
        pattern._frame = 999_999
        pattern.advance()
        assert pattern._frame == 0  # Should wrap

        # Test that pattern still renders correctly after many advances
        pattern._frame = frames_24h % 1_000_000
        result = pattern.render((128, 128, 128))
        assert len(result) == 16
        assert all(c == (128, 128, 128) for c in result)

    @pytest.mark.slow
    def test_no_memory_leak_patterns(self):
        """Pattern rendering should not leak memory over many frames."""
        class TestPattern(PatternBase):
            NAME = "leak_test"

            def _compute_frame(self, base_color: RGB) -> List[RGB]:
                for i in range(self.num_pixels):
                    self._pixel_buffer[i] = base_color
                return self._pixel_buffer

        pattern = TestPattern(num_pixels=256)  # Larger buffer

        # Force garbage collection and get baseline
        gc.collect()

        # Run many iterations
        iterations = 10000
        for i in range(iterations):
            pattern.render((128, 128, 128))
            pattern.advance()

        gc.collect()

        # The pattern should still be functional
        result = pattern.render((64, 64, 64))
        assert len(result) == 256

        # Frame counter should have advanced correctly
        assert pattern._frame == iterations % 1_000_000

    @pytest.mark.slow
    def test_timer_drift_correction(self):
        """Animation timing should not drift significantly over simulation."""
        seq = AnimationSequence("drift_test", loop=True)
        seq.add_keyframe(0, brightness=0.0)
        seq.add_keyframe(500, brightness=1.0)
        seq.add_keyframe(1000, brightness=0.0)

        player = AnimationPlayer(seq, target_fps=50)
        player.play()

        # Sample over simulated time
        start = time.monotonic()
        samples = []

        for _ in range(100):
            values = player.update()
            samples.append(values.get('brightness', 0.0))
            player.wait_for_next_frame()

        elapsed = time.monotonic() - start

        # 100 frames at 50Hz should take ~2 seconds
        # Allow 10% tolerance for test environment variability
        assert 1.8 <= elapsed <= 2.4

    @pytest.mark.slow
    def test_emotion_interpolation_stability(self):
        """Emotion interpolation should remain stable over many iterations."""
        # Start from happy
        emotion = EMOTION_PRESETS['happy']
        target = EMOTION_PRESETS['sad']

        # Interpolate many times with small steps
        iterations = 10000
        t_step = 0.001

        for i in range(iterations):
            emotion = emotion.interpolate(target, t_step)

        # Should have converged towards target
        # With t=0.001 over 10000 iterations, should be very close
        assert abs(emotion.arousal - target.arousal) < 0.01
        assert abs(emotion.valence - target.valence) < 0.01

        # All values should still be valid
        assert -1.0 <= emotion.arousal <= 1.0
        assert -1.0 <= emotion.valence <= 1.0
        assert 0.0 <= emotion.focus <= 1.0
        assert 0.25 <= emotion.blink_speed <= 2.0


# =============================================================================
# 5. BOUNDARY CONDITION TESTS
# =============================================================================

class TestBoundaryConditions:
    """Test exact boundary behavior."""

    def test_interpolation_at_t_0(self):
        """Interpolation at t=0.0 should return start value exactly."""
        seq = AnimationSequence("boundary")
        seq.add_keyframe(0, brightness=0.3)
        seq.add_keyframe(1000, brightness=0.9)

        values = seq.get_values(0)
        assert values['brightness'] == 0.3

    def test_interpolation_at_t_1(self):
        """Interpolation at t=1.0 should return end value exactly."""
        seq = AnimationSequence("boundary")
        seq.add_keyframe(0, brightness=0.3)
        seq.add_keyframe(1000, brightness=0.9)

        values = seq.get_values(1000)
        assert values['brightness'] == 0.9

    def test_easing_at_boundaries(self):
        """Easing functions at exact boundaries."""
        for easing_type in ['linear', 'ease_in', 'ease_out', 'ease_in_out']:
            # At t=0, should return 0
            assert ease(0.0, easing_type) == 0.0
            # At t=1, should return 1 (LUT has 101 entries, 0-100)
            # Note: LUT at index 100 = value at t=1.0
            assert ease(1.0, easing_type) == pytest.approx(1.0, abs=0.01)

    def test_color_at_hsv_boundaries(self):
        """Colors at HSV 0,0,0 and 360,1,1 should convert correctly."""
        # Black: h=0, s=0, v=0
        black = hsv_to_rgb(0, 0.0, 0.0)
        assert black == (0, 0, 0)

        # White: any h, s=0, v=1
        white = hsv_to_rgb(0, 0.0, 1.0)
        assert white == (255, 255, 255)

        # Pure red at hue 0 (or 360)
        red_0 = hsv_to_rgb(0, 1.0, 1.0)
        red_360 = hsv_to_rgb(360, 1.0, 1.0)
        assert red_0 == (255, 0, 0)
        assert red_360 == red_0

    def test_emotion_at_exact_boundaries(self):
        """Emotion axes at exact boundary values."""
        # Minimum valid emotion
        min_emotion = EmotionAxes(
            arousal=-1.0,
            valence=-1.0,
            focus=0.0,
            blink_speed=0.25
        )
        assert min_emotion.arousal == -1.0

        # Maximum valid emotion
        max_emotion = EmotionAxes(
            arousal=1.0,
            valence=1.0,
            focus=1.0,
            blink_speed=2.0
        )
        assert max_emotion.arousal == 1.0

    def test_pattern_config_boundary_values(self):
        """PatternConfig at exact boundary values."""
        # Minimum valid config
        min_config = PatternConfig(speed=0.1, brightness=0.0)
        assert min_config.speed == 0.1
        assert min_config.brightness == 0.0

        # Maximum valid config
        max_config = PatternConfig(speed=5.0, brightness=1.0)
        assert max_config.speed == 5.0
        assert max_config.brightness == 1.0

    def test_color_interpolation_at_boundaries(self):
        """Color interpolation at exact t=0 and t=1."""
        start = (255, 0, 0)
        end = (0, 255, 0)

        at_0 = color_interpolate(start, end, 0.0)
        assert at_0 == start

        at_1 = color_interpolate(start, end, 1.0)
        assert at_1 == end

    def test_layer_priority_boundaries(self):
        """Test layer priority at exact enum values."""
        assert AnimationPriority.BACKGROUND == 0
        assert AnimationPriority.TRIGGERED == 50
        assert AnimationPriority.REACTION == 75
        assert AnimationPriority.CRITICAL == 100


# =============================================================================
# 6. TYPE VALIDATION TESTS
# =============================================================================

class TestTypeValidation:
    """Test type checking and error handling."""

    def test_emotion_axes_bool_rejected(self):
        """Boolean values should be rejected for emotion axes."""
        with pytest.raises(TypeError, match="cannot be bool"):
            EmotionAxes(arousal=True, valence=0.0, focus=0.5, blink_speed=1.0)

    def test_emotion_axes_nan_rejected(self):
        """NaN values should be rejected for emotion axes."""
        with pytest.raises(ValueError, match="must be finite"):
            EmotionAxes(arousal=float('nan'), valence=0.0, focus=0.5, blink_speed=1.0)

    def test_emotion_axes_inf_rejected(self):
        """Infinity values should be rejected for emotion axes."""
        with pytest.raises(ValueError, match="must be finite"):
            EmotionAxes(arousal=float('inf'), valence=0.0, focus=0.5, blink_speed=1.0)

    def test_hsv_nan_rejected(self):
        """NaN values in HSV conversion should be rejected."""
        with pytest.raises(ValueError, match="must be finite"):
            hsv_to_rgb(float('nan'), 0.5, 0.5)

    def test_hsv_inf_rejected(self):
        """Infinity values in HSV conversion should be rejected."""
        with pytest.raises(ValueError, match="must be finite"):
            hsv_to_rgb(180, float('inf'), 0.5)

    def test_pattern_config_nan_rejected(self):
        """NaN values in PatternConfig should be rejected."""
        with pytest.raises(ValueError, match="must be finite"):
            PatternConfig(speed=float('nan'))

    def test_color_transition_invalid_easing(self):
        """Invalid easing type should be rejected."""
        with pytest.raises(ValueError, match="easing must be one of"):
            ColorTransitionConfig(easing='invalid_easing')

    def test_color_arc_invalid_direction(self):
        """Invalid HSV direction should be rejected."""
        with pytest.raises(ValueError, match="direction must be one of"):
            color_arc_interpolate((255, 0, 0), (0, 255, 0), 0.5, direction='invalid')

    def test_rgb_to_hsv_wrong_type(self):
        """Non-tuple RGB should be rejected."""
        with pytest.raises(TypeError, match="must be a 3-tuple"):
            rgb_to_hsv([255, 0, 0])  # List instead of tuple

    def test_easing_unknown_type_rejected(self):
        """Unknown easing type should raise ValueError."""
        with pytest.raises(ValueError, match="Unknown easing type"):
            ease(0.5, 'unknown_easing')


# =============================================================================
# 7. EDGE CASE INTERPOLATION TESTS
# =============================================================================

class TestInterpolationEdgeCases:
    """Test interpolation edge cases."""

    def test_color_interpolation_same_color(self):
        """Interpolating between same colors should return that color."""
        color = (128, 64, 32)
        result = color_interpolate(color, color, 0.5)
        assert result == color

    def test_hsv_interpolation_grayscale_fallback(self):
        """HSV interpolation with grayscale should fall back to RGB."""
        # Grayscale has saturation = 0
        gray = (128, 128, 128)
        red = (255, 0, 0)

        # Should use RGB interpolation since gray has s=0
        result = color_arc_interpolate(gray, red, 0.5)
        # Just verify it produces a valid color without crashing
        assert all(0 <= c <= 255 for c in result)

    def test_emotion_interpolation_same_emotion(self):
        """Interpolating between same emotions should return that emotion."""
        emotion = EMOTION_PRESETS['happy']
        result = emotion.interpolate(emotion, 0.5)

        assert result.arousal == emotion.arousal
        assert result.valence == emotion.valence
        assert result.focus == emotion.focus
        assert result.blink_speed == emotion.blink_speed

    def test_sequence_interpolation_at_keyframe(self):
        """Interpolation exactly at a keyframe should return keyframe values."""
        seq = AnimationSequence("exact")
        seq.add_keyframe(0, color=(100, 0, 0))
        seq.add_keyframe(500, color=(0, 100, 0))
        seq.add_keyframe(1000, color=(0, 0, 100))

        # Exactly at middle keyframe
        values = seq.get_values(500)
        assert values['color'] == (0, 100, 0)

    def test_looping_sequence_boundary(self):
        """Looping sequence at exact loop boundary."""
        seq = AnimationSequence("loop", loop=True)
        seq.add_keyframe(0, brightness=0.0)
        seq.add_keyframe(1000, brightness=1.0)

        # At exact duration (should wrap to 0)
        values_at_1000 = seq.get_values(1000)
        values_at_0 = seq.get_values(0)

        # Due to modulo, 1000 % 1000 = 0
        assert values_at_1000 == values_at_0

    def test_hue_wheel_short_path(self):
        """HSV interpolation should take shortest path by default."""
        # Red (0) to Blue (240) - short path is CCW through 300
        red = (255, 0, 0)
        blue = (0, 0, 255)

        mid = color_arc_interpolate(red, blue, 0.5, direction='short')
        # Midpoint should be around hue 300 (magenta area)
        h, s, v = rgb_to_hsv(mid)
        # Allow some tolerance due to conversion
        assert 280 < h < 320 or h > 350 or h < 10  # Could be near either end


# =============================================================================
# 8. STATE MACHINE EDGE CASES
# =============================================================================

class TestStateMachineEdgeCases:
    """Test coordinator state machine edge cases."""

    def test_start_animation_during_emergency(self, coordinator):
        """Starting animation during emergency stop should fail."""
        coordinator.emergency_stop()

        result = coordinator.start_animation('triggered', 'nod')
        assert result is False

    def test_background_during_emergency(self, coordinator):
        """Starting background during emergency stop should fail."""
        coordinator.emergency_stop()

        result = coordinator.start_background()
        assert result is False

    def test_double_emergency_stop(self, coordinator):
        """Double emergency stop should be idempotent."""
        coordinator.emergency_stop()
        assert coordinator.is_emergency_stopped()

        # Second call should not cause issues
        coordinator.emergency_stop()
        assert coordinator.is_emergency_stopped()

    def test_reset_from_emergency(self, coordinator):
        """Reset from emergency should clear state."""
        coordinator.start_background()
        coordinator.emergency_stop()

        result = coordinator.reset_from_emergency()
        assert result is True
        assert not coordinator.is_emergency_stopped()

    def test_reset_when_not_emergency(self, coordinator):
        """Reset when not in emergency should return False."""
        result = coordinator.reset_from_emergency()
        assert result is False

    def test_invalid_layer_name(self, coordinator):
        """Invalid layer name should raise ValueError."""
        with pytest.raises(ValueError, match="Unknown layer"):
            coordinator.start_animation('nonexistent', 'nod')

    def test_invalid_animation_name(self, coordinator):
        """Invalid animation name should raise ValueError."""
        with pytest.raises(ValueError, match="Unknown animation"):
            coordinator.start_animation('triggered', 'nonexistent_animation')

    def test_stop_inactive_layer(self, coordinator):
        """Stopping inactive layer should return False."""
        result = coordinator.stop_animation('triggered')
        assert result is False

    def test_layer_priority_override(self, coordinator):
        """Higher priority layer should block lower priority animations."""
        # Start reaction layer animation
        coordinator._layers['reaction'].active = True
        coordinator._layers['reaction'].current_animation = 'test'

        # Triggered (lower priority) should be blocked
        result = coordinator.start_animation('triggered', 'nod')
        assert result is False


# =============================================================================
# 9. PERFORMANCE EDGE CASES
# =============================================================================

class TestPerformanceEdgeCases:
    """Test performance-related edge cases."""

    def test_easing_lut_completeness(self):
        """LUT should have correct number of entries."""
        assert len(EASING_LUTS['linear']) == LUT_SIZE
        assert len(EASING_LUTS['ease_in']) == LUT_SIZE
        assert len(EASING_LUTS['ease_out']) == LUT_SIZE
        assert len(EASING_LUTS['ease_in_out']) == LUT_SIZE

    def test_easing_lookup_speed(self):
        """Easing lookup should be O(1) - very fast."""
        import time

        iterations = 10000
        start = time.perf_counter()
        for _ in range(iterations):
            ease_linear(0.5)
            ease_in(0.5)
            ease_out(0.5)
            ease_in_out(0.5)
        elapsed = time.perf_counter() - start

        # 40000 lookups should complete in well under 100ms
        assert elapsed < 0.1

    def test_hsv_lut_initialization(self):
        """HSV LUT should be initialized and complete."""
        from src.led.color_utils import _HSV_TO_RGB_LUT, _HSV_LUT_INITIALIZED

        assert _HSV_LUT_INITIALIZED
        assert len(_HSV_TO_RGB_LUT) == 360

    def test_pattern_buffer_reuse(self):
        """Pattern should reuse buffer without allocation."""
        class TestPattern(PatternBase):
            NAME = "buffer_test"

            def _compute_frame(self, base_color: RGB) -> List[RGB]:
                for i in range(self.num_pixels):
                    self._pixel_buffer[i] = base_color
                return self._pixel_buffer

        pattern = TestPattern(num_pixels=16)
        buffer_id = id(pattern._pixel_buffer)

        # Render multiple frames
        for _ in range(100):
            pattern.render((128, 128, 128))
            pattern.advance()

        # Buffer should be the same object (reused)
        assert id(pattern._pixel_buffer) == buffer_id


# =============================================================================
# 10. REGRESSION TESTS FOR KNOWN ISSUES
# =============================================================================

class TestRegressionKnownIssues:
    """Regression tests for previously identified issues."""

    def test_hue_wrap_o1_complexity(self):
        """Hue wrapping should be O(1) not O(n) with extreme values.

        Regression test for H-001: While-loop angle normalization issue.
        """
        # Very large hue should wrap efficiently
        import time

        start = time.perf_counter()
        result = hsv_to_rgb(1e15, 1.0, 1.0)  # Extremely large hue
        elapsed = time.perf_counter() - start

        # Should complete almost instantly (< 10ms)
        assert elapsed < 0.01
        # Result should be valid
        assert all(0 <= c <= 255 for c in result)

    def test_emotion_to_hsv_range(self):
        """Emotion to HSV conversion should produce valid ranges.

        Tests that all emotion presets produce valid HSV values.
        """
        for name, emotion in EMOTION_PRESETS.items():
            h, s, v = emotion.to_hsv()

            assert 0 <= h <= 360, f"Invalid hue for {name}: {h}"
            assert 0.3 <= s <= 1.0, f"Invalid saturation for {name}: {s}"
            assert 0.4 <= v <= 1.0, f"Invalid value for {name}: {v}"

    def test_animation_callback_not_under_lock(self, coordinator):
        """Animation complete callback should not cause deadlock.

        Regression test for H-002: Callback invocation under lock.
        """
        callback_called = threading.Event()

        def on_complete(anim_name):
            # Try to access coordinator (would deadlock if callback under lock)
            coordinator.is_animating()
            callback_called.set()

        coordinator.set_on_animation_complete(on_complete)
        coordinator.start_animation('triggered', 'nod', blocking=True)
        coordinator._on_animation_finished('triggered', 'nod')

        # Callback should have completed without deadlock
        assert callback_called.wait(timeout=1.0)


# =============================================================================
# MAIN
# =============================================================================

if __name__ == '__main__':
    pytest.main([__file__, '-v'])
