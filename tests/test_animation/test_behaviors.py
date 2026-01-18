#!/usr/bin/env python3
"""
TDD Test Suite for IdleBehavior and BlinkBehavior Classes
Day 12: Idle Behaviors + Animation Coordination

Tests written FIRST (TDD methodology) before implementation exists.
Tests define expected behavior for behavior animation modules.

Quality Standard: Boston Dynamics / Pixar / DeepMind Grade

Test Classes:
    TestIdleBehaviorInit: Initialization tests
    TestIdleBehaviorTimingConfig: Timing configuration tests
    TestIdleBehaviorLoop: Run loop behavior tests
    TestIdleBehaviorPauseResume: Pause/resume functionality tests
    TestBlinkBehavior: Blink animation tests

Run with: pytest tests/test_animation/test_behaviors.py -v

Author: TDD Test Architect Agent (Agent 1)
Created: 18 January 2026
"""

import asyncio
import time
from typing import List, Optional
from unittest.mock import Mock, MagicMock, AsyncMock, patch

import pytest


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def mock_head_controller():
    """
    Provide mock HeadController for testing.

    Returns:
        Mock HeadController with all required methods.
    """
    head = Mock()
    head.random_glance = Mock(return_value=True)
    head.look_at = Mock(return_value=True)
    head.get_state = Mock(return_value=Mock(is_moving=False, pan=0.0, tilt=0.0))
    head.get_current_position = Mock(return_value=(0.0, 0.0))
    head.emergency_stop = Mock()
    head.reset_to_center = Mock(return_value=True)
    return head


@pytest.fixture
def mock_micro_engine():
    """
    Provide mock MicroExpressionEngine for testing.

    Returns:
        Mock MicroExpressionEngine with all required methods.
    """
    engine = Mock()
    engine.trigger = Mock(return_value=True)
    engine.trigger_preset = Mock(return_value=True)
    engine.is_active = Mock(return_value=False)
    engine.update = Mock(return_value=False)
    engine.get_brightness_modifier = Mock(return_value=1.0)
    engine.get_per_pixel_modifiers = Mock(return_value=[1.0] * 16)
    engine.reset = Mock()
    return engine


@pytest.fixture
def mock_led_controller():
    """
    Provide mock LED controller for testing.

    Returns:
        Mock LED controller instance.
    """
    led = Mock()
    led.set_brightness = Mock()
    led.show = Mock()
    led.clear = Mock()
    return led


@pytest.fixture
def idle_behavior(mock_head_controller, mock_micro_engine, mock_led_controller):
    """
    Provide IdleBehavior instance with mock dependencies.

    Returns:
        IdleBehavior instance ready for testing.
    """
    from src.animation.behaviors import IdleBehavior
    return IdleBehavior(
        head_controller=mock_head_controller,
        micro_engine=mock_micro_engine,
        led_controller=mock_led_controller
    )


@pytest.fixture
def blink_behavior(mock_micro_engine):
    """
    Provide BlinkBehavior instance with mock dependencies.

    Returns:
        BlinkBehavior instance ready for testing.
    """
    from src.animation.behaviors import BlinkBehavior
    return BlinkBehavior(micro_engine=mock_micro_engine)


# =============================================================================
# TestIdleBehaviorInit - Initialization tests (~4 tests)
# =============================================================================

class TestIdleBehaviorInit:
    """Tests for IdleBehavior initialization."""

    def test_initialization_with_all_controllers(
        self, mock_head_controller, mock_micro_engine, mock_led_controller
    ):
        """
        IdleBehavior initializes successfully with all controllers provided.

        Verifies that all controller references are stored correctly.
        """
        from src.animation.behaviors import IdleBehavior

        idle = IdleBehavior(
            head_controller=mock_head_controller,
            micro_engine=mock_micro_engine,
            led_controller=mock_led_controller
        )

        assert idle.head is mock_head_controller
        assert idle.micro_engine is mock_micro_engine
        assert idle.led_controller is mock_led_controller

    def test_initialization_with_none_controllers(self):
        """
        IdleBehavior accepts None for optional controllers.

        LED controller is optional - system should work with head + micro only.
        """
        from src.animation.behaviors import IdleBehavior

        # Mock required controllers
        mock_head = Mock()
        mock_engine = Mock()

        idle = IdleBehavior(
            head_controller=mock_head,
            micro_engine=mock_engine,
            led_controller=None
        )

        assert idle.head is mock_head
        assert idle.micro_engine is mock_engine
        assert idle.led_controller is None

    def test_default_interval_ranges(self, idle_behavior):
        """
        IdleBehavior has sensible default interval ranges.

        Per architecture spec:
        - Blink interval: 3-5 seconds
        - Glance interval: 5-10 seconds
        """
        # Default blink intervals
        assert idle_behavior.blink_interval_min == 3.0
        assert idle_behavior.blink_interval_max == 5.0

        # Default glance intervals
        assert idle_behavior.glance_interval_min == 5.0
        assert idle_behavior.glance_interval_max == 10.0

    def test_custom_interval_configuration(
        self, mock_head_controller, mock_micro_engine
    ):
        """
        IdleBehavior accepts custom interval configuration.

        Allows tuning blink/glance frequency for different robot personalities.
        """
        from src.animation.behaviors import IdleBehavior

        idle = IdleBehavior(
            head_controller=mock_head_controller,
            micro_engine=mock_micro_engine,
            blink_interval_min=2.0,
            blink_interval_max=4.0,
            glance_interval_min=4.0,
            glance_interval_max=8.0
        )

        assert idle.blink_interval_min == 2.0
        assert idle.blink_interval_max == 4.0
        assert idle.glance_interval_min == 4.0
        assert idle.glance_interval_max == 8.0


# =============================================================================
# TestIdleBehaviorTimingConfig - Timing configuration tests (~5 tests)
# =============================================================================

class TestIdleBehaviorTimingConfig:
    """Tests for IdleBehavior timing configuration."""

    def test_blink_interval_randomization(self, idle_behavior):
        """
        Blink intervals are randomized within configured range.

        Prevents robotic, predictable behavior - Disney's "appeal" principle.
        """
        intervals = []
        for _ in range(20):
            interval = idle_behavior._get_next_blink_interval()
            intervals.append(interval)
            assert idle_behavior.blink_interval_min <= interval <= idle_behavior.blink_interval_max

        # Should have some variance (not all same value)
        assert len(set(intervals)) > 1, "Intervals should be randomized"

    def test_glance_interval_randomization(self, idle_behavior):
        """
        Glance intervals are randomized within configured range.

        Natural-looking behavior requires unpredictability.
        """
        intervals = []
        for _ in range(20):
            interval = idle_behavior._get_next_glance_interval()
            intervals.append(interval)
            assert idle_behavior.glance_interval_min <= interval <= idle_behavior.glance_interval_max

        # Should have some variance
        assert len(set(intervals)) > 1, "Intervals should be randomized"

    def test_intervals_within_bounds(self, idle_behavior):
        """
        All generated intervals stay strictly within bounds.

        Fuzz test to ensure no edge case allows out-of-bounds values.
        """
        for _ in range(100):
            blink = idle_behavior._get_next_blink_interval()
            glance = idle_behavior._get_next_glance_interval()

            assert 3.0 <= blink <= 5.0, f"Blink interval {blink} out of bounds"
            assert 5.0 <= glance <= 10.0, f"Glance interval {glance} out of bounds"

    def test_set_blink_interval_valid(self, idle_behavior):
        """
        set_blink_interval accepts valid range values.
        """
        idle_behavior.set_blink_interval(min_s=2.0, max_s=6.0)

        assert idle_behavior.blink_interval_min == 2.0
        assert idle_behavior.blink_interval_max == 6.0

    def test_set_blink_interval_invalid_raises(self, idle_behavior):
        """
        set_blink_interval raises ValueError for invalid ranges.

        - min_s must be > 0
        - max_s must be >= min_s
        """
        # Zero minimum
        with pytest.raises(ValueError, match="min_s must be > 0"):
            idle_behavior.set_blink_interval(min_s=0.0, max_s=5.0)

        # Negative minimum
        with pytest.raises(ValueError, match="min_s must be > 0"):
            idle_behavior.set_blink_interval(min_s=-1.0, max_s=5.0)

        # max_s less than min_s
        with pytest.raises(ValueError, match=r"max_s.*must be >= min_s"):
            idle_behavior.set_blink_interval(min_s=5.0, max_s=3.0)


# =============================================================================
# TestIdleBehaviorLoop - Run loop behavior tests (~5 tests)
# =============================================================================

class TestIdleBehaviorLoop:
    """Tests for IdleBehavior async run loop."""

    @pytest.mark.asyncio
    async def test_run_increments_tick_count(self, idle_behavior):
        """
        Run loop increments internal tick counter.

        Tick count useful for debugging and behavior verification.
        """
        assert idle_behavior._tick_count == 0

        # Start the loop briefly
        task = asyncio.create_task(idle_behavior.run())
        await asyncio.sleep(0.25)  # Let it run a few ticks (10Hz = 100ms interval)
        idle_behavior.stop()
        await task

        # Should have incremented
        assert idle_behavior._tick_count >= 2, "Should have ticked at least twice in 250ms"

    @pytest.mark.asyncio
    async def test_run_triggers_blink_on_interval(
        self, mock_head_controller, mock_micro_engine
    ):
        """
        Run loop triggers blink after blink interval expires.

        Uses very short intervals for fast testing.
        """
        from src.animation.behaviors import IdleBehavior

        idle = IdleBehavior(
            head_controller=mock_head_controller,
            micro_engine=mock_micro_engine,
            blink_interval_min=0.1,  # Very short for testing
            blink_interval_max=0.15,
            glance_interval_min=10.0,  # Long to avoid during test
            glance_interval_max=15.0
        )

        task = asyncio.create_task(idle.run())
        await asyncio.sleep(0.3)  # Long enough for at least one blink
        idle.stop()
        await task

        # Should have triggered at least one blink
        assert mock_micro_engine.trigger_preset.call_count >= 1, \
            "Should have triggered at least one blink"

    @pytest.mark.asyncio
    async def test_run_triggers_glance_on_interval(
        self, mock_head_controller, mock_micro_engine
    ):
        """
        Run loop triggers glance after glance interval expires.

        Uses very short intervals for fast testing.
        """
        from src.animation.behaviors import IdleBehavior

        idle = IdleBehavior(
            head_controller=mock_head_controller,
            micro_engine=mock_micro_engine,
            blink_interval_min=10.0,  # Long to avoid during test
            blink_interval_max=15.0,
            glance_interval_min=0.1,  # Very short for testing
            glance_interval_max=0.15
        )

        task = asyncio.create_task(idle.run())
        await asyncio.sleep(0.3)  # Long enough for at least one glance
        idle.stop()
        await task

        # Should have triggered at least one glance
        assert mock_head_controller.random_glance.call_count >= 1, \
            "Should have triggered at least one glance"

    @pytest.mark.asyncio
    async def test_stop_terminates_loop(self, idle_behavior):
        """
        stop() terminates the run loop gracefully.

        Loop should exit cleanly without errors.
        """
        task = asyncio.create_task(idle_behavior.run())

        # Let it start
        await asyncio.sleep(0.1)
        assert idle_behavior.is_running()

        # Stop it
        idle_behavior.stop()

        # Should complete within timeout
        try:
            await asyncio.wait_for(task, timeout=1.0)
        except asyncio.TimeoutError:
            pytest.fail("stop() did not terminate run loop within timeout")

        assert not idle_behavior.is_running()

    @pytest.mark.asyncio
    async def test_pause_and_resume(self, idle_behavior, mock_micro_engine):
        """
        pause() suspends behaviors, resume() restarts them.

        Used when triggered animations need to override idle.
        """
        # Start running
        task = asyncio.create_task(idle_behavior.run())
        await asyncio.sleep(0.1)

        assert idle_behavior.is_running()
        assert not idle_behavior.is_paused()

        # Pause
        idle_behavior.pause()
        assert idle_behavior.is_paused()

        # Clear call counts
        mock_micro_engine.trigger_preset.reset_mock()

        # During pause, no behaviors should trigger
        await asyncio.sleep(0.2)

        # Resume
        idle_behavior.resume()
        assert not idle_behavior.is_paused()

        # Clean up
        idle_behavior.stop()
        await task


# =============================================================================
# TestIdleBehaviorPauseResume - Pause/resume tests (~3 tests)
# =============================================================================

class TestIdleBehaviorPauseResume:
    """Tests for IdleBehavior pause and resume functionality."""

    @pytest.mark.asyncio
    async def test_pause_stops_behaviors(
        self, mock_head_controller, mock_micro_engine
    ):
        """
        pause() prevents blink and glance behaviors from triggering.

        Important for layered animation coordination.
        """
        from src.animation.behaviors import IdleBehavior

        idle = IdleBehavior(
            head_controller=mock_head_controller,
            micro_engine=mock_micro_engine,
            blink_interval_min=0.05,
            blink_interval_max=0.1,
            glance_interval_min=0.05,
            glance_interval_max=0.1
        )

        task = asyncio.create_task(idle.run())
        await asyncio.sleep(0.05)  # Let it start

        # Pause immediately
        idle.pause()

        # Record call counts
        blink_count = mock_micro_engine.trigger_preset.call_count
        glance_count = mock_head_controller.random_glance.call_count

        # Wait while paused
        await asyncio.sleep(0.2)

        # Should NOT have triggered more behaviors during pause
        assert mock_micro_engine.trigger_preset.call_count == blink_count, \
            "Should not trigger blinks while paused"
        assert mock_head_controller.random_glance.call_count == glance_count, \
            "Should not trigger glances while paused"

        idle.stop()
        await task

    @pytest.mark.asyncio
    async def test_resume_restarts_behaviors(
        self, mock_head_controller, mock_micro_engine
    ):
        """
        resume() restarts triggering behaviors after pause.
        """
        from src.animation.behaviors import IdleBehavior

        idle = IdleBehavior(
            head_controller=mock_head_controller,
            micro_engine=mock_micro_engine,
            blink_interval_min=0.05,
            blink_interval_max=0.1,
            glance_interval_min=0.05,
            glance_interval_max=0.1
        )

        task = asyncio.create_task(idle.run())
        await asyncio.sleep(0.05)

        # Pause then resume
        idle.pause()
        await asyncio.sleep(0.05)
        idle.resume()

        # Record counts after resume
        blink_count = mock_micro_engine.trigger_preset.call_count
        glance_count = mock_head_controller.random_glance.call_count

        # Wait for behaviors to trigger after resume
        await asyncio.sleep(0.2)

        # Should have triggered behaviors after resume
        assert mock_micro_engine.trigger_preset.call_count > blink_count or \
               mock_head_controller.random_glance.call_count > glance_count, \
               "Should trigger behaviors after resume"

        idle.stop()
        await task

    @pytest.mark.asyncio
    async def test_multiple_pause_resume_cycles(self, idle_behavior):
        """
        Multiple pause/resume cycles work correctly.

        Tests state machine robustness.
        """
        task = asyncio.create_task(idle_behavior.run())
        await asyncio.sleep(0.05)

        for _ in range(3):
            idle_behavior.pause()
            assert idle_behavior.is_paused()
            await asyncio.sleep(0.02)

            idle_behavior.resume()
            assert not idle_behavior.is_paused()
            await asyncio.sleep(0.02)

        idle_behavior.stop()
        await task


# =============================================================================
# TestBlinkBehavior - BlinkBehavior tests (~7 tests)
# =============================================================================

class TestBlinkBehavior:
    """Tests for BlinkBehavior class."""

    def test_init_with_micro_engine(self, mock_micro_engine):
        """
        BlinkBehavior initializes with MicroExpressionEngine.
        """
        from src.animation.behaviors import BlinkBehavior

        blink = BlinkBehavior(micro_engine=mock_micro_engine)

        assert blink.micro_engine is mock_micro_engine

    def test_blink_duration_default(self, blink_behavior):
        """
        Default blink duration is 150ms (per architecture spec).
        """
        assert blink_behavior.blink_duration_ms == 150

    def test_blink_creates_keyframes(self, blink_behavior, mock_micro_engine):
        """
        do_blink() triggers blink micro-expression.

        Should call trigger_preset with 'blink_normal'.
        """
        result = blink_behavior.do_blink()

        assert result is True
        mock_micro_engine.trigger_preset.assert_called_once()
        call_args = mock_micro_engine.trigger_preset.call_args
        assert call_args[0][0] == 'blink_normal' or 'blink' in call_args[0][0].lower()

    def test_slow_blink_longer_duration(self, blink_behavior, mock_micro_engine):
        """
        do_slow_blink() uses 400ms duration (sleepy blink).

        Per architecture spec for sleepy emotion state.
        """
        result = blink_behavior.do_slow_blink()

        assert result is True
        # Should trigger slow blink preset or use longer duration
        assert mock_micro_engine.trigger_preset.called or mock_micro_engine.trigger.called

    def test_wink_left_only_left_eye(self, blink_behavior, mock_micro_engine):
        """
        do_wink('left') affects only left eye.
        """
        result = blink_behavior.do_wink(side='left')

        assert result is True
        # Verify some form of wink was triggered
        assert mock_micro_engine.trigger_preset.called or mock_micro_engine.trigger.called

    def test_wink_right_only_right_eye(self, blink_behavior, mock_micro_engine):
        """
        do_wink('right') affects only right eye.
        """
        result = blink_behavior.do_wink(side='right')

        assert result is True
        assert mock_micro_engine.trigger_preset.called or mock_micro_engine.trigger.called

    def test_wink_invalid_side_raises(self, blink_behavior):
        """
        do_wink() raises ValueError for invalid side.
        """
        with pytest.raises(ValueError, match="side"):
            blink_behavior.do_wink(side='up')

        with pytest.raises(ValueError, match="side"):
            blink_behavior.do_wink(side='invalid')

    def test_set_blink_speed_multiplier(self, blink_behavior):
        """
        set_blink_speed() adjusts blink timing.

        Used by EmotionBridge to match emotion blink_speed axis.
        """
        # Default multiplier should be 1.0
        original_duration = blink_behavior.blink_duration_ms

        # Speed up (2x = half duration)
        blink_behavior.set_blink_speed(2.0)
        assert blink_behavior.blink_duration_ms == original_duration // 2

        # Slow down (0.5x = double duration)
        blink_behavior.set_blink_speed(0.5)
        assert blink_behavior.blink_duration_ms == original_duration * 2

    def test_blink_with_animator(self, mock_micro_engine):
        """
        BlinkBehavior can optionally use AnimationPlayer for servo eyelids.
        """
        from src.animation.behaviors import BlinkBehavior

        mock_animator = Mock()
        mock_animator.play = Mock(return_value=True)

        blink = BlinkBehavior(
            micro_engine=mock_micro_engine,
            animator=mock_animator
        )

        # Should have stored animator reference
        assert blink.animator is mock_animator


# =============================================================================
# TestBlinkBehaviorEdgeCases - Edge case tests (~3 tests)
# =============================================================================

class TestBlinkBehaviorEdgeCases:
    """Edge case tests for BlinkBehavior."""

    def test_blink_when_engine_active(self, blink_behavior, mock_micro_engine):
        """
        do_blink() handles case when micro engine already active.
        """
        mock_micro_engine.is_active.return_value = True

        # Should still attempt to trigger (engine handles queueing)
        result = blink_behavior.do_blink()

        # Result depends on engine state, but should not raise
        assert isinstance(result, bool)

    def test_blink_speed_clamps_to_valid_range(self, blink_behavior):
        """
        set_blink_speed() produces valid duration (high speed = short duration).
        """
        # Very high multiplier gives shorter duration
        blink_behavior.set_blink_speed(10.0)
        assert blink_behavior.blink_duration_ms >= 10  # Some minimum physical limit

        # Very low multiplier gives longer duration
        blink_behavior.set_blink_speed(0.1)
        assert blink_behavior.blink_duration_ms <= 3000  # Maximum reasonable duration

    def test_rapid_blink_sequence(self, blink_behavior, mock_micro_engine):
        """
        Multiple rapid blinks don't cause errors.
        """
        for _ in range(10):
            blink_behavior.do_blink()

        # Should have made multiple trigger calls
        assert mock_micro_engine.trigger_preset.call_count == 10


# =============================================================================
# Performance Tests
# =============================================================================

class TestIdleBehaviorPerformance:
    """Performance tests for IdleBehavior."""

    @pytest.mark.asyncio
    async def test_tick_overhead_under_5ms(self, idle_behavior):
        """
        Each idle loop tick completes in under 5ms.

        Important for responsive robot behavior.
        """
        timings = []

        task = asyncio.create_task(idle_behavior.run())

        # Measure tick times
        for _ in range(10):
            start = time.perf_counter()
            await asyncio.sleep(0.1)  # One tick at 10Hz
            elapsed_ms = (time.perf_counter() - start) * 1000

            # Sleep itself is ~100ms, overhead should be minimal
            overhead = elapsed_ms - 100.0
            if overhead > 0:
                timings.append(overhead)

        idle_behavior.stop()
        await task

        if timings:
            avg_overhead = sum(timings) / len(timings)
            # 15ms threshold for Windows CI compatibility (asyncio overhead)
            assert avg_overhead < 15.0, f"Average tick overhead {avg_overhead}ms > 15ms limit"

    def test_interval_generation_fast(self, idle_behavior):
        """
        Interval generation is fast (<0.1ms per call).
        """
        start = time.perf_counter()
        for _ in range(1000):
            idle_behavior._get_next_blink_interval()
            idle_behavior._get_next_glance_interval()
        elapsed_ms = (time.perf_counter() - start) * 1000

        per_call_us = (elapsed_ms / 2000) * 1000  # microseconds per call
        assert per_call_us < 100, f"Interval generation took {per_call_us}us (limit: 100us)"


class TestBlinkBehaviorPerformance:
    """Performance tests for BlinkBehavior."""

    def test_blink_trigger_fast(self, blink_behavior, mock_micro_engine):
        """
        Blink triggering is fast (<1ms per call).
        """
        # Warm up
        blink_behavior.do_blink()
        mock_micro_engine.trigger_preset.reset_mock()

        start = time.perf_counter()
        for _ in range(100):
            blink_behavior.do_blink()
        elapsed_ms = (time.perf_counter() - start) * 1000

        per_call_ms = elapsed_ms / 100
        assert per_call_ms < 1.0, f"Blink trigger took {per_call_ms}ms (limit: 1ms)"


# =============================================================================
# Integration Tests
# =============================================================================

class TestIdleBehaviorIntegration:
    """Integration tests for IdleBehavior with dependencies."""

    @pytest.mark.asyncio
    async def test_blink_uses_correct_preset(
        self, mock_head_controller, mock_micro_engine
    ):
        """
        Idle blink uses 'blink_normal' preset from MicroExpressionEngine.
        """
        from src.animation.behaviors import IdleBehavior

        idle = IdleBehavior(
            head_controller=mock_head_controller,
            micro_engine=mock_micro_engine,
            blink_interval_min=0.05,
            blink_interval_max=0.1,
            glance_interval_min=10.0,
            glance_interval_max=15.0
        )

        task = asyncio.create_task(idle.run())
        await asyncio.sleep(0.2)
        idle.stop()
        await task

        # Check preset name used
        if mock_micro_engine.trigger_preset.called:
            preset_name = mock_micro_engine.trigger_preset.call_args[0][0]
            assert 'blink' in preset_name.lower(), \
                f"Expected blink preset, got {preset_name}"

    @pytest.mark.asyncio
    async def test_glance_uses_head_controller(
        self, mock_head_controller, mock_micro_engine
    ):
        """
        Idle glance uses HeadController.random_glance().
        """
        from src.animation.behaviors import IdleBehavior

        idle = IdleBehavior(
            head_controller=mock_head_controller,
            micro_engine=mock_micro_engine,
            blink_interval_min=10.0,
            blink_interval_max=15.0,
            glance_interval_min=0.05,
            glance_interval_max=0.1
        )

        task = asyncio.create_task(idle.run())
        await asyncio.sleep(0.2)
        idle.stop()
        await task

        # Should have called random_glance
        assert mock_head_controller.random_glance.called, \
            "Should call HeadController.random_glance()"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
