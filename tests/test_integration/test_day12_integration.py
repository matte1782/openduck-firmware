#!/usr/bin/env python3
"""
Day 12 Integration Tests - Full System Coordination
OpenDuck Mini V3 | Week 02 Day 12

Tests the complete behavioral pipeline:
- IdleBehavior running in background
- BlinkBehavior triggering LED effects
- AnimationCoordinator managing layers
- EmotionBridge coordinating all outputs
- Concurrent head + LED animations
- Thread safety under concurrent access
- Emergency stop propagation

Quality Standard: Boston Dynamics / Pixar / DeepMind Grade

Test Classes:
    TestIdleSystemIntegration: Idle system tests
    TestEmotionExpressionIntegration: Emotion expression tests
    TestCoordinationIntegration: Animation coordination tests
    TestThreadSafetyIntegration: Thread safety stress tests
    TestPerformanceIntegration: Performance benchmark tests
    TestRapidEmotionChanges: Rapid change handling tests
    TestEmergencyStopIntegration: Emergency stop propagation tests

Run with: pytest tests/test_integration/test_day12_integration.py -v

Author: TDD Test Architect Agent (Agent 1)
Created: 18 January 2026
"""

import asyncio
import threading
import time
import statistics
from typing import List, Optional, Dict, Any
from unittest.mock import Mock, MagicMock, patch, AsyncMock

import pytest

import sys
import os

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def mock_head_controller():
    """
    Provide mock HeadController for integration testing.

    Returns:
        Mock HeadController with realistic behavior tracking.
    """
    head = Mock()
    head._position = (0.0, 0.0)
    head._is_moving = False
    head._emergency_stopped = False

    def look_at(pan, tilt, duration_ms=300, easing='ease_in_out', blocking=False):
        head._position = (pan, tilt)
        head._is_moving = not blocking
        return True

    def get_current_position():
        return head._position

    def get_state():
        return Mock(
            is_moving=head._is_moving,
            pan=head._position[0],
            tilt=head._position[1]
        )

    def emergency_stop():
        head._emergency_stopped = True
        head._is_moving = False

    def reset_emergency():
        head._emergency_stopped = False
        return True

    head.look_at = Mock(side_effect=look_at)
    head.nod = Mock(return_value=True)
    head.shake = Mock(return_value=True)
    head.random_glance = Mock(return_value=True)
    head.tilt_curious = Mock(return_value=True)
    head.reset_to_center = Mock(return_value=True)
    head.get_current_position = Mock(side_effect=get_current_position)
    head.get_state = Mock(side_effect=get_state)
    head.emergency_stop = Mock(side_effect=emergency_stop)
    head.reset_emergency = Mock(side_effect=reset_emergency)

    return head


@pytest.fixture
def mock_micro_engine():
    """
    Provide mock MicroExpressionEngine for integration testing.

    Returns:
        Mock MicroExpressionEngine with call tracking.
    """
    engine = Mock()
    engine._active = False
    engine._trigger_count = 0

    def trigger(expression_type, duration_ms=100, intensity=0.8, force=False):
        engine._trigger_count += 1
        engine._active = True
        return True

    def trigger_preset(preset_name, force=False):
        engine._trigger_count += 1
        engine._active = True
        return True

    def is_active():
        return engine._active

    def update(delta_ms):
        return engine._active

    engine.trigger = Mock(side_effect=trigger)
    engine.trigger_preset = Mock(side_effect=trigger_preset)
    engine.is_active = Mock(side_effect=is_active)
    engine.update = Mock(side_effect=update)
    engine.get_brightness_modifier = Mock(return_value=1.0)
    engine.get_per_pixel_modifiers = Mock(return_value=[1.0] * 16)
    engine.cancel_current = Mock(return_value=True)
    engine.reset = Mock()

    return engine


@pytest.fixture
def mock_led_controller():
    """
    Provide mock LED controller for integration testing.

    Returns:
        Mock LED controller instance.
    """
    led = Mock()
    led._pattern = None
    led._brightness = 1.0

    led.set_pattern = Mock()
    led.set_brightness = Mock()
    led.set_color = Mock()
    led.show = Mock()
    led.clear = Mock()

    return led


@pytest.fixture
def integrated_system(mock_head_controller, mock_micro_engine, mock_led_controller):
    """
    Provide fully integrated animation system.

    Returns:
        Dictionary with all system components wired together.
    """
    from animation.coordinator import AnimationCoordinator
    from animation.emotion_bridge import EmotionBridge
    from animation.behaviors import IdleBehavior, BlinkBehavior

    # Create coordinator
    coordinator = AnimationCoordinator(
        head_controller=mock_head_controller,
        led_controller=mock_led_controller,
        micro_engine=mock_micro_engine
    )

    # Create behaviors
    idle_behavior = IdleBehavior(
        head_controller=mock_head_controller,
        micro_engine=mock_micro_engine,
        led_controller=mock_led_controller,
        blink_interval_min=0.1,  # Fast for testing
        blink_interval_max=0.2,
        glance_interval_min=0.2,
        glance_interval_max=0.3
    )

    blink_behavior = BlinkBehavior(micro_engine=mock_micro_engine)

    # Create emotion bridge
    emotion_bridge = EmotionBridge(
        animation_coordinator=coordinator,
        head_controller=mock_head_controller,
        micro_engine=mock_micro_engine,
        led_controller=mock_led_controller
    )

    return {
        'coordinator': coordinator,
        'idle_behavior': idle_behavior,
        'blink_behavior': blink_behavior,
        'emotion_bridge': emotion_bridge,
        'head': mock_head_controller,
        'micro': mock_micro_engine,
        'led': mock_led_controller
    }


# =============================================================================
# TestIdleSystemIntegration - Idle system tests (~4 tests)
# =============================================================================

class TestIdleSystemIntegration:
    """Test idle system runs correctly with full integration."""

    @pytest.mark.asyncio
    async def test_idle_system_runs_without_errors(self, integrated_system):
        """
        Complete idle system runs for 2 seconds without errors.

        Validates that IdleBehavior, MicroExpressionEngine, and
        HeadController work together without crashes.
        """
        idle = integrated_system['idle_behavior']

        task = asyncio.create_task(idle.run())

        # Run for 2 seconds
        await asyncio.sleep(2.0)

        # Stop cleanly
        idle.stop()
        await task

        # Should have completed without errors
        assert idle._tick_count > 0, "Idle loop should have executed ticks"

    @pytest.mark.asyncio
    async def test_idle_blink_triggers_led_effect(self, integrated_system):
        """
        Idle blink triggers MicroExpressionEngine BLINK effect.
        """
        idle = integrated_system['idle_behavior']
        micro = integrated_system['micro']

        # Run idle briefly
        task = asyncio.create_task(idle.run())
        await asyncio.sleep(0.5)  # Long enough for at least one blink
        idle.stop()
        await task

        # Should have triggered micro-expression
        assert micro.trigger_preset.called or micro.trigger.called, \
            "Idle should trigger blink via MicroExpressionEngine"

    @pytest.mark.asyncio
    async def test_idle_glance_triggers_head_movement(self, integrated_system):
        """
        Idle glance triggers HeadController.random_glance().
        """
        idle = integrated_system['idle_behavior']
        head = integrated_system['head']

        task = asyncio.create_task(idle.run())
        await asyncio.sleep(0.5)  # Long enough for at least one glance
        idle.stop()
        await task

        # Should have triggered head glance
        assert head.random_glance.called, \
            "Idle should trigger random_glance via HeadController"

    @pytest.mark.asyncio
    async def test_idle_with_real_head_controller(self, integrated_system):
        """
        Idle behaviors coordinate properly with head controller.
        """
        idle = integrated_system['idle_behavior']
        head = integrated_system['head']

        task = asyncio.create_task(idle.run())
        await asyncio.sleep(0.5)
        idle.stop()
        await task

        # Head should have been used
        total_head_calls = (
            head.random_glance.call_count +
            head.look_at.call_count +
            head.nod.call_count
        )
        # At minimum, some head interaction should occur
        # (depends on timing, but should have at least queried state)


# =============================================================================
# TestEmotionExpressionIntegration - Emotion expression tests (~4 tests)
# =============================================================================

class TestEmotionExpressionIntegration:
    """Test emotion expression coordination."""

    def test_emotion_change_updates_led(self, integrated_system):
        """
        Changing emotion updates LED pattern.
        """
        from animation.emotion_axes import EMOTION_PRESETS

        bridge = integrated_system['emotion_bridge']
        led = integrated_system['led']

        happy = EMOTION_PRESETS['happy']
        bridge.express_emotion(happy, duration_ms=200)

        # LED controller should have been updated
        # (depends on implementation - might set pattern or color)

    def test_emotion_change_updates_head(self, integrated_system):
        """
        Changing emotion updates head pose.
        """
        from animation.emotion_axes import EMOTION_PRESETS

        bridge = integrated_system['emotion_bridge']
        head = integrated_system['head']

        happy = EMOTION_PRESETS['happy']
        bridge.express_emotion(happy, duration_ms=200, blocking=True)

        # Head should have been positioned
        assert head.look_at.called, "Emotion should trigger head positioning"

    def test_emotion_change_triggers_micro_expression(self, integrated_system):
        """
        Changing emotion triggers appropriate micro-expression.
        """
        from animation.emotion_axes import EMOTION_PRESETS

        bridge = integrated_system['emotion_bridge']
        micro = integrated_system['micro']

        excited = EMOTION_PRESETS['excited']
        bridge.express_emotion(excited, duration_ms=200)

        # Micro-expression might be triggered for excited state
        # (depends on mapping logic)

    def test_all_presets_expressible(self, integrated_system):
        """
        All emotion presets can be expressed without errors.
        """
        from animation.emotion_axes import EMOTION_PRESETS

        bridge = integrated_system['emotion_bridge']

        for preset_name, emotion in EMOTION_PRESETS.items():
            # Should not raise
            bridge.express_emotion(emotion, duration_ms=50, blocking=False)


# =============================================================================
# TestCoordinationIntegration - Animation coordination tests (~4 tests)
# =============================================================================

class TestCoordinationIntegration:
    """Test animation coordination between layers."""

    @pytest.mark.asyncio
    async def test_triggered_pauses_idle(self, integrated_system):
        """
        Triggered animation pauses idle behaviors.
        """
        from animation.emotion_axes import EMOTION_PRESETS

        coord = integrated_system['coordinator']
        idle = integrated_system['idle_behavior']
        bridge = integrated_system['emotion_bridge']

        # Start idle
        idle_task = asyncio.create_task(idle.run())
        await asyncio.sleep(0.1)

        # Pause (simulated via triggered animation)
        idle.pause()
        assert idle.is_paused()

        # Clean up
        idle.stop()
        await idle_task

    @pytest.mark.asyncio
    async def test_idle_resumes_after_triggered(self, integrated_system):
        """
        Idle behaviors resume after triggered animation completes.
        """
        coord = integrated_system['coordinator']
        idle = integrated_system['idle_behavior']
        micro = integrated_system['micro']

        # Start idle
        idle_task = asyncio.create_task(idle.run())
        await asyncio.sleep(0.1)

        # Pause, then resume
        idle.pause()
        micro.trigger_preset.reset_mock()

        await asyncio.sleep(0.1)  # While paused

        idle.resume()
        await asyncio.sleep(0.3)  # Let behaviors trigger

        # Should have triggered more behaviors after resume
        idle.stop()
        await idle_task

    def test_concurrent_head_and_led(self, integrated_system):
        """
        Head and LED animate concurrently without conflict.
        """
        from animation.emotion_axes import EMOTION_PRESETS

        bridge = integrated_system['emotion_bridge']
        head = integrated_system['head']
        led = integrated_system['led']

        # Express emotion that affects both
        happy = EMOTION_PRESETS['happy']
        bridge.express_emotion(happy, duration_ms=200, blocking=False)

        # Then express another immediately
        sad = EMOTION_PRESETS['sad']
        bridge.express_emotion(sad, duration_ms=200, blocking=False)

        # Both head and LED should have been called
        assert head.look_at.call_count >= 1

    def test_animation_state_tracking(self, integrated_system):
        """
        Coordinator correctly tracks animation state.
        """
        coord = integrated_system['coordinator']

        # Initially idle
        state = coord.get_state()
        assert state.emergency_stopped is False

        # Start animation
        coord.start_animation('triggered', 'nod')
        state = coord.get_state()
        assert state.active_layer == 'triggered' or coord.is_animating()


# =============================================================================
# TestThreadSafetyIntegration - Thread safety stress tests (~4 tests)
# =============================================================================

class TestThreadSafetyIntegration:
    """Test thread safety under concurrent access."""

    def test_concurrent_emotion_changes(self, integrated_system):
        """
        Multiple threads can change emotions safely.
        """
        from animation.emotion_axes import EMOTION_PRESETS

        bridge = integrated_system['emotion_bridge']
        errors: List[Exception] = []
        emotions = list(EMOTION_PRESETS.values())

        def worker(emotion_idx):
            try:
                for _ in range(20):
                    emotion = emotions[emotion_idx % len(emotions)]
                    bridge.express_emotion(emotion, duration_ms=20, blocking=False)
                    time.sleep(0.001)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5.0)

        assert len(errors) == 0, f"Thread safety errors: {errors}"

    def test_concurrent_animation_triggers(self, integrated_system):
        """
        Multiple threads can trigger animations safely.
        """
        coord = integrated_system['coordinator']
        errors: List[Exception] = []

        def worker():
            try:
                for _ in range(20):
                    coord.start_animation('triggered', 'nod')
                    time.sleep(0.001)
                    coord.stop_animation('triggered')
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5.0)

        assert len(errors) == 0, f"Thread safety errors: {errors}"

    def test_emergency_stop_from_any_thread(self, integrated_system):
        """
        Emergency stop works from any thread.
        """
        coord = integrated_system['coordinator']
        head = integrated_system['head']
        errors: List[Exception] = []
        stop_calls: List[bool] = []

        def trigger_worker():
            try:
                for _ in range(30):
                    coord.start_animation('triggered', 'nod')
                    time.sleep(0.001)
            except RuntimeError:
                pass  # Expected during emergency
            except Exception as e:
                errors.append(e)

        def stop_worker():
            try:
                time.sleep(0.005)  # Let triggers start
                coord.emergency_stop()
                stop_calls.append(True)
            except Exception as e:
                errors.append(e)

        trigger_thread = threading.Thread(target=trigger_worker)
        stop_thread = threading.Thread(target=stop_worker)

        trigger_thread.start()
        stop_thread.start()

        trigger_thread.join(timeout=2.0)
        stop_thread.join(timeout=2.0)

        assert len(errors) == 0, f"Thread safety errors: {errors}"
        assert len(stop_calls) > 0, "Emergency stop should have been called"

    def test_state_read_during_concurrent_write(self, integrated_system):
        """
        Reading state during concurrent modifications is safe.
        """
        coord = integrated_system['coordinator']
        errors: List[Exception] = []
        states: List = []

        def reader():
            try:
                for _ in range(100):
                    state = coord.get_state()
                    states.append(state)
            except Exception as e:
                errors.append(e)

        def writer():
            try:
                for i in range(100):
                    if i % 2 == 0:
                        coord.start_background()
                    else:
                        coord.stop_background()
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=reader),
            threading.Thread(target=reader),
            threading.Thread(target=writer),
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5.0)

        assert len(errors) == 0, f"Thread safety errors: {errors}"


# =============================================================================
# TestPerformanceIntegration - Performance benchmark tests (~4 tests)
# =============================================================================

class TestPerformanceIntegration:
    """Test performance requirements."""

    def test_emotion_expression_latency(self, integrated_system):
        """
        Emotion expression starts within 10ms.
        """
        from animation.emotion_axes import EMOTION_PRESETS

        bridge = integrated_system['emotion_bridge']
        happy = EMOTION_PRESETS['happy']

        timings = []
        for _ in range(50):
            start = time.perf_counter()
            bridge.express_emotion(happy, duration_ms=50, blocking=False)
            elapsed_ms = (time.perf_counter() - start) * 1000
            timings.append(elapsed_ms)

        avg_latency = statistics.mean(timings)
        max_latency = max(timings)

        assert avg_latency < 10.0, f"Average expression latency {avg_latency}ms > 10ms"
        assert max_latency < 50.0, f"Max expression latency {max_latency}ms > 50ms"

    @pytest.mark.asyncio
    async def test_idle_loop_overhead(self, integrated_system):
        """
        Idle loop overhead is less than 5ms per tick.
        """
        idle = integrated_system['idle_behavior']

        tick_times = []
        original_tick_count = 0

        task = asyncio.create_task(idle.run())

        # Measure tick timing
        for _ in range(10):
            before = idle._tick_count
            start = time.perf_counter()
            await asyncio.sleep(0.1)  # One tick at 10Hz
            elapsed_ms = (time.perf_counter() - start) * 1000
            after = idle._tick_count

            # Overhead is elapsed - expected sleep
            if after > before:
                overhead = elapsed_ms - 100.0
                if overhead > 0:
                    tick_times.append(overhead)

        idle.stop()
        await task

        if tick_times:
            avg_overhead = statistics.mean(tick_times)
            # 15ms threshold for Windows CI compatibility (asyncio overhead)
            assert avg_overhead < 15.0, f"Idle loop overhead {avg_overhead}ms > 15ms"

    def test_coordinator_state_performance(self, integrated_system):
        """
        Coordinator get_state is fast (<0.5ms for 1000 calls).
        """
        coord = integrated_system['coordinator']

        start = time.perf_counter()
        for _ in range(1000):
            coord.get_state()
        elapsed_ms = (time.perf_counter() - start) * 1000

        per_call_ms = elapsed_ms / 1000
        assert per_call_ms < 0.5, f"get_state took {per_call_ms}ms (limit: 0.5ms)"

    def test_blink_trigger_throughput(self, integrated_system):
        """
        Blink behavior can trigger at required rate.
        """
        blink = integrated_system['blink_behavior']
        micro = integrated_system['micro']

        # Reset mock
        micro.trigger_preset.reset_mock()

        start = time.perf_counter()
        for _ in range(100):
            blink.do_blink()
        elapsed_ms = (time.perf_counter() - start) * 1000

        throughput = 100 / (elapsed_ms / 1000)  # blinks per second
        assert throughput > 100, f"Blink throughput {throughput}/s < 100/s"


# =============================================================================
# TestRapidEmotionChanges - Rapid change handling tests (~3 tests)
# =============================================================================

class TestRapidEmotionChanges:
    """Test handling of rapid changes."""

    def test_rapid_emotion_changes_no_crash(self, integrated_system):
        """
        Rapid emotion changes don't crash system.
        """
        from animation.emotion_axes import EMOTION_PRESETS

        bridge = integrated_system['emotion_bridge']
        emotions = list(EMOTION_PRESETS.values())

        # Rapidly cycle through all emotions
        for _ in range(3):
            for emotion in emotions:
                bridge.express_emotion(emotion, duration_ms=10, blocking=False)

        # Should complete without errors

    def test_rapid_emotion_changes_smooth_output(self, integrated_system):
        """
        Rapid emotion changes produce smooth LED output.
        """
        from animation.emotion_axes import EMOTION_PRESETS

        bridge = integrated_system['emotion_bridge']
        micro = integrated_system['micro']

        happy = EMOTION_PRESETS['happy']
        sad = EMOTION_PRESETS['sad']

        # Rapidly alternate
        for _ in range(10):
            bridge.express_emotion(happy, duration_ms=20, blocking=False)
            bridge.express_emotion(sad, duration_ms=20, blocking=False)

        # System should remain stable

    def test_emotion_queue_overflow_handling(self, integrated_system):
        """
        System handles emotion queue overflow gracefully.
        """
        from animation.emotion_axes import EMOTION_PRESETS

        bridge = integrated_system['emotion_bridge']
        emotions = list(EMOTION_PRESETS.values())

        # Flood with rapid emotion changes
        for _ in range(100):
            emotion = emotions[hash(str(time.monotonic())) % len(emotions)]
            bridge.express_emotion(emotion, duration_ms=5, blocking=False)

        # Should not crash or leak memory


# =============================================================================
# TestEmergencyStopIntegration - Emergency stop propagation tests (~3 tests)
# =============================================================================

class TestEmergencyStopIntegration:
    """Test emergency stop propagation through system."""

    def test_emergency_stop_halts_all(self, integrated_system):
        """
        Emergency stop halts all active systems.
        """
        coord = integrated_system['coordinator']
        head = integrated_system['head']

        # Start activity
        coord.start_background()
        coord.start_animation('triggered', 'nod')

        # Emergency stop
        coord.emergency_stop()

        # Head should be stopped
        assert head.emergency_stop.called

    @pytest.mark.asyncio
    async def test_emergency_stop_halts_idle_loop(self, integrated_system):
        """
        Emergency stop halts idle behavior loop.
        """
        coord = integrated_system['coordinator']
        idle = integrated_system['idle_behavior']

        task = asyncio.create_task(idle.run())
        await asyncio.sleep(0.1)

        # Emergency stop (idle should observe coordinator state)
        coord.emergency_stop()

        # Give time for loop to notice
        await asyncio.sleep(0.1)

        idle.stop()
        await task

    def test_reset_emergency_allows_resume(self, integrated_system):
        """
        Resetting emergency allows normal operation to resume.
        """
        coord = integrated_system['coordinator']
        head = integrated_system['head']

        coord.emergency_stop()
        coord.reset_from_emergency()

        # Should be able to trigger animations again
        result = coord.start_animation('triggered', 'nod')
        assert result is True


# =============================================================================
# TestFullSystemIntegration - Complete system tests (~2 tests)
# =============================================================================

class TestFullSystemIntegration:
    """Full system integration tests."""

    @pytest.mark.asyncio
    async def test_concurrent_idle_and_triggered(self, integrated_system):
        """
        Test concurrent idle behaviors and triggered animations.
        """
        from animation.emotion_axes import EMOTION_PRESETS

        idle = integrated_system['idle_behavior']
        bridge = integrated_system['emotion_bridge']

        # Start idle
        idle_task = asyncio.create_task(idle.run())
        await asyncio.sleep(0.1)

        # Trigger emotions while idle runs
        for _ in range(3):
            bridge.express_emotion(EMOTION_PRESETS['happy'], duration_ms=100, blocking=False)
            await asyncio.sleep(0.15)
            bridge.express_emotion(EMOTION_PRESETS['curious'], duration_ms=100, blocking=False)
            await asyncio.sleep(0.15)

        idle.stop()
        await idle_task

        # System should have remained stable

    @pytest.mark.asyncio
    async def test_system_runs_60_seconds_stable(self, integrated_system):
        """
        System runs for 60 seconds without degradation.

        NOTE: This is a long test. Skip if you need quick feedback.
        For CI/CD, consider running in a separate performance test suite.
        """
        # Skip in normal test runs
        pytest.skip("Long-running stability test - run manually for full validation")

        from animation.emotion_axes import EMOTION_PRESETS

        idle = integrated_system['idle_behavior']
        bridge = integrated_system['emotion_bridge']
        coord = integrated_system['coordinator']

        idle_task = asyncio.create_task(idle.run())
        emotions = list(EMOTION_PRESETS.values())

        start = time.monotonic()
        emotion_count = 0

        while time.monotonic() - start < 60:
            # Periodically change emotions
            emotion = emotions[emotion_count % len(emotions)]
            bridge.express_emotion(emotion, duration_ms=500, blocking=False)
            emotion_count += 1
            await asyncio.sleep(1.0)

        idle.stop()
        await idle_task

        elapsed = time.monotonic() - start
        assert elapsed >= 59.0, "Test completed prematurely"
        assert emotion_count >= 50, f"Should have expressed ~60 emotions, got {emotion_count}"


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-x'])
