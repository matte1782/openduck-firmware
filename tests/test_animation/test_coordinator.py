#!/usr/bin/env python3
"""
Tests for AnimationCoordinator class.

Verifies layered animation coordination including:
- Layer priority management
- Background idle behaviors
- Triggered animation handling
- Emergency stop functionality
- Thread safety

Test Count: 25+
Coverage Target: 90%

Author: Agent 3 - Pixar Technical Director
Created: 18 January 2026 (Day 12)
"""

import pytest
import asyncio
import threading
import time
from unittest.mock import Mock, MagicMock, patch, AsyncMock
from dataclasses import dataclass

import sys
import os

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from animation.coordinator import (
    AnimationCoordinator,
    AnimationPriority,
    AnimationLayer,
    AnimationState,
    SUPPORTED_ANIMATIONS,
)


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def mock_head_controller():
    """Create a mock HeadController."""
    head = Mock()
    head.nod = Mock(return_value=True)
    head.shake = Mock(return_value=True)
    head.tilt_curious = Mock(return_value=True)
    head.random_glance = Mock(return_value=True)
    head.look_at = Mock(return_value=True)
    head.reset_to_center = Mock(return_value=True)
    head.emergency_stop = Mock()
    head.reset_emergency = Mock()
    head.get_state = Mock(return_value=Mock(is_moving=False, pan=0, tilt=0))
    return head


@pytest.fixture
def mock_led_controller():
    """Create a mock LED controller."""
    led = Mock()
    led.set_color = Mock()
    led.set_pattern = Mock()
    led.clear = Mock()
    return led


@pytest.fixture
def mock_micro_engine():
    """Create a mock MicroExpressionEngine."""
    engine = Mock()
    engine.trigger = Mock(return_value=True)
    engine.trigger_preset = Mock(return_value=True)
    engine.is_active = Mock(return_value=False)
    engine.update = Mock()
    return engine


@pytest.fixture
def coordinator(mock_head_controller, mock_led_controller, mock_micro_engine):
    """Create AnimationCoordinator with mock controllers."""
    return AnimationCoordinator(
        head_controller=mock_head_controller,
        led_controller=mock_led_controller,
        micro_engine=mock_micro_engine
    )


@pytest.fixture
def coordinator_no_head():
    """Create AnimationCoordinator without head controller."""
    return AnimationCoordinator(
        head_controller=None,
        led_controller=None,
        micro_engine=None
    )


# =============================================================================
# INITIALIZATION TESTS
# =============================================================================

class TestAnimationCoordinatorInit:
    """Initialization tests."""

    def test_init_with_all_controllers(
        self, mock_head_controller, mock_led_controller, mock_micro_engine
    ):
        """Coordinator initializes with all controllers."""
        coord = AnimationCoordinator(
            head_controller=mock_head_controller,
            led_controller=mock_led_controller,
            micro_engine=mock_micro_engine
        )

        assert coord._head is mock_head_controller
        assert coord._led is mock_led_controller
        assert coord._micro_engine is mock_micro_engine
        assert not coord._running
        assert not coord._emergency_stopped

    def test_init_without_optional_controllers(self):
        """Coordinator works without optional controllers."""
        coord = AnimationCoordinator(
            head_controller=None,
            led_controller=None,
            micro_engine=None
        )

        assert coord._head is None
        assert coord._led is None
        assert coord._micro_engine is None
        assert len(coord._layers) == 4  # Default layers still created

    def test_init_registers_default_layers(self, coordinator):
        """Coordinator registers four default layers."""
        assert "background" in coordinator._layers
        assert "triggered" in coordinator._layers
        assert "reaction" in coordinator._layers
        assert "critical" in coordinator._layers

    def test_init_layer_priorities_correct(self, coordinator):
        """Default layers have correct priority order."""
        assert coordinator._layers["background"].priority == AnimationPriority.BACKGROUND
        assert coordinator._layers["triggered"].priority == AnimationPriority.TRIGGERED
        assert coordinator._layers["reaction"].priority == AnimationPriority.REACTION
        assert coordinator._layers["critical"].priority == AnimationPriority.CRITICAL

    def test_init_all_layers_inactive(self, coordinator):
        """All layers start inactive."""
        for layer in coordinator._layers.values():
            assert not layer.active
            assert layer.current_animation is None


# =============================================================================
# ANIMATION LAYER DATA CLASS TESTS
# =============================================================================

class TestAnimationLayer:
    """Tests for AnimationLayer dataclass."""

    def test_layer_creation_valid(self):
        """AnimationLayer creates with valid parameters."""
        layer = AnimationLayer(
            name="test_layer",
            priority=AnimationPriority.TRIGGERED
        )
        assert layer.name == "test_layer"
        assert layer.priority == AnimationPriority.TRIGGERED
        assert not layer.active
        assert layer.current_animation is None

    def test_layer_creation_empty_name_raises(self):
        """AnimationLayer rejects empty name."""
        with pytest.raises(ValueError, match="name cannot be empty"):
            AnimationLayer(name="", priority=AnimationPriority.BACKGROUND)

    def test_layer_creation_with_active_state(self):
        """AnimationLayer can be created with active state."""
        layer = AnimationLayer(
            name="active_layer",
            priority=AnimationPriority.TRIGGERED,
            active=True,
            current_animation="nod"
        )
        assert layer.active
        assert layer.current_animation == "nod"


# =============================================================================
# LAYER MANAGEMENT TESTS
# =============================================================================

class TestLayerManagement:
    """Tests for layer management methods."""

    def test_get_layer_returns_existing(self, coordinator):
        """get_layer returns existing layer."""
        layer = coordinator.get_layer("background")
        assert layer is not None
        assert layer.name == "background"

    def test_get_layer_returns_none_for_unknown(self, coordinator):
        """get_layer returns None for unknown layer."""
        layer = coordinator.get_layer("nonexistent")
        assert layer is None

    def test_get_active_layer_none_when_all_inactive(self, coordinator):
        """get_active_layer returns None when no layers active."""
        active = coordinator.get_active_layer()
        assert active is None

    def test_get_active_layer_returns_highest_priority(self, coordinator):
        """get_active_layer returns highest priority active layer."""
        # Activate multiple layers
        coordinator._layers["background"].active = True
        coordinator._layers["triggered"].active = True

        active = coordinator.get_active_layer()
        assert active.name == "triggered"
        assert active.priority > AnimationPriority.BACKGROUND

    def test_get_all_layers_sorted_by_priority(self, coordinator):
        """get_all_layers returns layers sorted by priority descending."""
        layers = coordinator.get_all_layers()

        priorities = [layer.priority for layer in layers]
        assert priorities == sorted(priorities, reverse=True)

    def test_register_layer_duplicate_raises(self, coordinator):
        """_register_layer raises for duplicate name."""
        with pytest.raises(ValueError, match="already registered"):
            coordinator._register_layer("background", AnimationPriority.BACKGROUND)


# =============================================================================
# ANIMATION CONTROL TESTS
# =============================================================================

class TestAnimationControl:
    """Tests for animation start/stop methods."""

    def test_start_animation_known_name(self, coordinator, mock_head_controller):
        """start_animation accepts known animation names."""
        result = coordinator.start_animation("triggered", "nod")

        assert result is True
        assert coordinator._layers["triggered"].active
        assert coordinator._layers["triggered"].current_animation == "nod"

    def test_start_animation_unknown_layer_raises(self, coordinator):
        """start_animation raises for unknown layer."""
        with pytest.raises(ValueError, match="Unknown layer"):
            coordinator.start_animation("invalid_layer", "nod")

    def test_start_animation_unknown_name_raises(self, coordinator):
        """start_animation raises for unknown animation names."""
        with pytest.raises(ValueError, match="Unknown animation"):
            coordinator.start_animation("triggered", "invalid_animation")

    def test_start_animation_calls_head_controller(
        self, coordinator, mock_head_controller
    ):
        """start_animation calls appropriate HeadController method."""
        coordinator.start_animation("triggered", "nod", blocking=False)

        mock_head_controller.nod.assert_called_once()

    def test_start_animation_shake_calls_shake(
        self, coordinator, mock_head_controller
    ):
        """start_animation 'shake' calls HeadController.shake()."""
        coordinator.start_animation("triggered", "shake", blocking=False)

        mock_head_controller.shake.assert_called_once()

    def test_start_animation_blocked_during_emergency(self, coordinator):
        """start_animation returns False during emergency stop."""
        coordinator.emergency_stop()

        result = coordinator.start_animation("triggered", "nod")

        assert result is False

    def test_start_animation_blocked_by_higher_priority(self, coordinator):
        """start_animation blocked when higher priority layer active."""
        # Activate critical layer (highest priority)
        coordinator._layers["critical"].active = True
        coordinator._layers["critical"].current_animation = "emergency"

        # Try to start triggered animation (lower priority)
        result = coordinator.start_animation("triggered", "nod")

        assert result is False

    def test_start_animation_pauses_lower_priority(self, coordinator):
        """start_animation pauses lower priority active layers."""
        # Start background
        coordinator.start_background()
        assert coordinator._layers["background"].active

        # Start triggered animation
        coordinator.start_animation("triggered", "nod")

        # Background should be paused
        assert "background" in coordinator._paused_layers

    def test_stop_animation_deactivates_layer(self, coordinator):
        """stop_animation deactivates specified layer."""
        coordinator.start_animation("triggered", "nod")
        assert coordinator._layers["triggered"].active

        result = coordinator.stop_animation("triggered")

        assert result is True
        assert not coordinator._layers["triggered"].active
        assert coordinator._layers["triggered"].current_animation is None

    def test_stop_animation_unknown_layer_returns_false(self, coordinator):
        """stop_animation returns False for unknown layer."""
        result = coordinator.stop_animation("nonexistent")
        assert result is False

    def test_stop_animation_inactive_layer_returns_false(self, coordinator):
        """stop_animation returns False for already inactive layer."""
        result = coordinator.stop_animation("triggered")
        assert result is False

    def test_stop_animation_resumes_paused_layers(self, coordinator):
        """stop_animation resumes paused lower-priority layers."""
        # Start background, then triggered
        coordinator.start_background()
        coordinator.start_animation("triggered", "nod")
        assert "background" in coordinator._paused_layers

        # Stop triggered
        coordinator.stop_animation("triggered")

        # Background should resume
        assert "background" not in coordinator._paused_layers
        assert coordinator._layers["background"].active

    def test_stop_all_animations(self, coordinator):
        """stop_all_animations stops all active layers."""
        # Activate multiple layers
        coordinator.start_background()
        coordinator.start_animation("triggered", "nod")

        count = coordinator.stop_all_animations()

        assert count >= 1  # At least triggered was active
        for layer in coordinator._layers.values():
            assert not layer.active


# =============================================================================
# BACKGROUND CONTROL TESTS
# =============================================================================

class TestBackgroundControl:
    """Tests for background layer control."""

    def test_start_background_starts_idle(self, coordinator):
        """start_background starts background layer."""
        result = coordinator.start_background()

        assert result is True
        assert coordinator._layers["background"].active
        assert coordinator._layers["background"].current_animation == "idle"

    def test_start_background_blocked_during_emergency(self, coordinator):
        """start_background blocked during emergency stop."""
        coordinator.emergency_stop()

        result = coordinator.start_background()

        assert result is False

    def test_start_background_already_running_returns_true(self, coordinator):
        """start_background returns True if already running."""
        coordinator.start_background()
        result = coordinator.start_background()

        assert result is True

    def test_stop_background_stops_idle(self, coordinator):
        """stop_background stops background layer."""
        coordinator.start_background()

        result = coordinator.stop_background()

        assert result is True
        assert not coordinator._layers["background"].active

    def test_stop_background_not_running_returns_false(self, coordinator):
        """stop_background returns False if not running."""
        result = coordinator.stop_background()
        assert result is False

    def test_is_background_running_true_when_active(self, coordinator):
        """is_background_running returns True when active."""
        coordinator.start_background()
        assert coordinator.is_background_running() is True

    def test_is_background_running_false_when_inactive(self, coordinator):
        """is_background_running returns False when inactive."""
        assert coordinator.is_background_running() is False

    def test_background_pauses_during_triggered(self, coordinator):
        """Background pauses when triggered animation starts."""
        coordinator.start_background()
        coordinator.start_animation("triggered", "nod")

        # Background should be paused (in paused_layers list)
        assert "background" in coordinator._paused_layers


# =============================================================================
# EMERGENCY CONTROL TESTS
# =============================================================================

class TestEmergencyControl:
    """Tests for emergency stop functionality."""

    def test_emergency_stop_sets_flag(self, coordinator):
        """emergency_stop sets emergency flag."""
        coordinator.emergency_stop()

        assert coordinator._emergency_stopped is True

    def test_emergency_stop_stops_all_layers(self, coordinator):
        """emergency_stop stops all active layers."""
        coordinator.start_background()
        coordinator.start_animation("triggered", "nod")

        coordinator.emergency_stop()

        # All layers except critical should be inactive
        assert not coordinator._layers["background"].active
        assert not coordinator._layers["triggered"].active

    def test_emergency_stop_calls_head_controller(
        self, coordinator, mock_head_controller
    ):
        """emergency_stop calls HeadController.emergency_stop()."""
        coordinator.emergency_stop()

        mock_head_controller.emergency_stop.assert_called_once()

    def test_emergency_stop_activates_critical_layer(self, coordinator):
        """emergency_stop activates critical layer."""
        coordinator.emergency_stop()

        critical = coordinator._layers["critical"]
        assert critical.active
        assert critical.current_animation == "emergency_stop"

    def test_reset_from_emergency_clears_flag(self, coordinator):
        """reset_from_emergency clears emergency flag."""
        coordinator.emergency_stop()
        assert coordinator._emergency_stopped

        result = coordinator.reset_from_emergency()

        assert result is True
        assert not coordinator._emergency_stopped

    def test_reset_from_emergency_when_not_stopped_returns_false(self, coordinator):
        """reset_from_emergency returns False if not in emergency."""
        result = coordinator.reset_from_emergency()
        assert result is False

    def test_reset_from_emergency_deactivates_critical(self, coordinator):
        """reset_from_emergency deactivates critical layer."""
        coordinator.emergency_stop()

        coordinator.reset_from_emergency()

        assert not coordinator._layers["critical"].active

    def test_is_emergency_stopped_reflects_state(self, coordinator):
        """is_emergency_stopped reflects emergency state."""
        assert coordinator.is_emergency_stopped() is False

        coordinator.emergency_stop()
        assert coordinator.is_emergency_stopped() is True

        coordinator.reset_from_emergency()
        assert coordinator.is_emergency_stopped() is False


# =============================================================================
# STATE QUERY TESTS
# =============================================================================

class TestStateQueries:
    """Tests for state query methods."""

    def test_get_state_returns_animation_state(self, coordinator):
        """get_state returns AnimationState dataclass."""
        state = coordinator.get_state()

        assert isinstance(state, AnimationState)
        assert state.active_layer is None
        assert state.background_running is False
        assert state.emergency_stopped is False

    def test_get_state_reflects_active_layer(self, coordinator):
        """get_state reflects currently active layer."""
        coordinator.start_animation("triggered", "nod")

        state = coordinator.get_state()

        assert state.active_layer == "triggered"
        assert state.triggered_animation == "nod"

    def test_get_state_reflects_emergency(self, coordinator):
        """get_state reflects emergency stop state."""
        coordinator.emergency_stop()

        state = coordinator.get_state()

        assert state.emergency_stopped is True

    def test_is_animating_false_when_idle(self, coordinator):
        """is_animating returns False when only background runs."""
        coordinator.start_background()

        assert coordinator.is_animating() is False

    def test_is_animating_true_when_triggered(self, coordinator):
        """is_animating returns True when triggered animation active."""
        coordinator.start_animation("triggered", "nod")

        assert coordinator.is_animating() is True

    def test_is_running_reflects_loop_state(self, coordinator):
        """is_running reflects coordinator loop state."""
        assert coordinator.is_running() is False

        coordinator._running = True
        assert coordinator.is_running() is True


# =============================================================================
# CALLBACK TESTS
# =============================================================================

class TestCallbacks:
    """Tests for callback functionality."""

    def test_set_on_animation_complete_callback(self, coordinator):
        """set_on_animation_complete sets callback."""
        callback = Mock()
        coordinator.set_on_animation_complete(callback)

        assert coordinator._on_animation_complete is callback

    def test_set_on_animation_complete_none_clears(self, coordinator):
        """set_on_animation_complete(None) clears callback."""
        coordinator.set_on_animation_complete(Mock())
        coordinator.set_on_animation_complete(None)

        assert coordinator._on_animation_complete is None

    def test_animation_complete_callback_fired(self, coordinator):
        """Animation complete callback is fired."""
        callback = Mock()
        coordinator.set_on_animation_complete(callback)

        # Manually trigger completion
        coordinator._layers["triggered"].active = True
        coordinator._layers["triggered"].current_animation = "nod"
        coordinator._on_animation_finished("triggered", "nod")

        callback.assert_called_once_with("nod")

    def test_callback_error_does_not_crash(self, coordinator):
        """Callback error does not crash coordinator."""
        callback = Mock(side_effect=RuntimeError("callback error"))
        coordinator.set_on_animation_complete(callback)

        # Should not raise
        coordinator._layers["triggered"].active = True
        coordinator._layers["triggered"].current_animation = "nod"
        coordinator._on_animation_finished("triggered", "nod")


# =============================================================================
# ASYNC RUN LOOP TESTS
# =============================================================================

class TestAsyncRunLoop:
    """Tests for async coordination loop."""

    @pytest.mark.asyncio
    async def test_run_sets_running_flag(self, coordinator):
        """run() sets running flag."""
        task = asyncio.create_task(coordinator.run())

        await asyncio.sleep(0.05)  # Let it start

        assert coordinator._running is True

        coordinator.stop()
        await task

    @pytest.mark.asyncio
    async def test_run_increments_tick(self, coordinator):
        """run() executes tick loop."""
        # Patch _tick to track calls
        tick_count = [0]
        original_tick = coordinator._tick

        async def counting_tick():
            tick_count[0] += 1
            await original_tick()

        coordinator._tick = counting_tick

        task = asyncio.create_task(coordinator.run())
        await asyncio.sleep(0.25)  # ~2 ticks at 10Hz

        coordinator.stop()
        await task

        assert tick_count[0] >= 1

    @pytest.mark.asyncio
    async def test_stop_terminates_loop(self, coordinator):
        """stop() terminates run loop."""
        task = asyncio.create_task(coordinator.run())
        await asyncio.sleep(0.05)

        coordinator.stop()
        await asyncio.wait_for(task, timeout=1.0)

        assert coordinator._running is False

    @pytest.mark.asyncio
    async def test_run_already_running_returns(self, coordinator):
        """run() returns immediately if already running."""
        task1 = asyncio.create_task(coordinator.run())
        await asyncio.sleep(0.05)

        # Second run should return immediately
        await coordinator.run()

        coordinator.stop()
        await task1


# =============================================================================
# THREAD SAFETY TESTS
# =============================================================================

class TestThreadSafety:
    """Tests for thread safety."""

    def test_concurrent_start_stop_no_crash(self, coordinator):
        """Concurrent start/stop calls don't crash."""
        errors = []

        def worker():
            try:
                for _ in range(50):
                    coordinator.start_background()
                    coordinator.stop_background()
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker) for _ in range(5)]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0

    def test_concurrent_emergency_stop(self, coordinator):
        """Emergency stop from multiple threads is safe."""
        errors = []

        def worker():
            try:
                for _ in range(20):
                    coordinator.emergency_stop()
                    coordinator.reset_from_emergency()
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker) for _ in range(5)]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0

    def test_get_state_thread_safe(self, coordinator):
        """get_state() is thread-safe."""
        errors = []
        states = []

        def reader():
            try:
                for _ in range(50):
                    state = coordinator.get_state()
                    states.append(state)
            except Exception as e:
                errors.append(e)

        def writer():
            try:
                for _ in range(50):
                    coordinator.start_background()
                    coordinator.stop_background()
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
            t.join()

        assert len(errors) == 0
        assert len(states) == 100


# =============================================================================
# UTILITY METHOD TESTS
# =============================================================================

class TestUtilityMethods:
    """Tests for utility methods."""

    def test_trigger_emotion_activates_reaction_layer(self, coordinator):
        """trigger_emotion activates reaction layer."""
        emotion = Mock()

        result = coordinator.trigger_emotion(emotion, duration_ms=500)

        assert result is True
        assert coordinator._layers["reaction"].active

    def test_trigger_emotion_blocked_during_emergency(self, coordinator):
        """trigger_emotion blocked during emergency."""
        coordinator.emergency_stop()

        result = coordinator.trigger_emotion(Mock())

        assert result is False

    def test_trigger_emotion_calls_micro_engine(
        self, coordinator, mock_micro_engine
    ):
        """trigger_emotion triggers micro-expression."""
        emotion = Mock()

        coordinator.trigger_emotion(emotion)

        mock_micro_engine.trigger_preset.assert_called()

    def test_repr_includes_state(self, coordinator):
        """__repr__ includes useful state info."""
        repr_str = repr(coordinator)

        assert "AnimationCoordinator" in repr_str
        assert "layers=" in repr_str
        assert "running=" in repr_str

    def test_wait_for_completion_returns_true_when_idle(self, coordinator):
        """wait_for_completion returns True immediately when idle."""
        result = coordinator.wait_for_completion(timeout_ms=100)
        assert result is True

    def test_wait_for_completion_timeout(self, coordinator):
        """wait_for_completion respects timeout."""
        # Keep triggered layer active
        coordinator._layers["triggered"].active = True
        coordinator._layers["triggered"].current_animation = "long_animation"

        result = coordinator.wait_for_completion(timeout_ms=50)

        assert result is False


# =============================================================================
# EDGE CASES
# =============================================================================

class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_animation_without_head_controller(self, coordinator_no_head):
        """Animation works without head controller."""
        result = coordinator_no_head.start_animation("triggered", "nod")

        assert result is True

    def test_emergency_stop_without_head_controller(self, coordinator_no_head):
        """Emergency stop works without head controller."""
        coordinator_no_head.emergency_stop()

        assert coordinator_no_head._emergency_stopped is True

    def test_supported_animations_complete(self):
        """All expected animations are in SUPPORTED_ANIMATIONS."""
        expected = ['nod', 'shake', 'curious', 'glance', 'look_at', 'reset']

        for anim in expected:
            assert anim in SUPPORTED_ANIMATIONS


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
