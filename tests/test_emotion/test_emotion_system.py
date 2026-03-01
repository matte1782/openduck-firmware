#!/usr/bin/env python3
"""
Comprehensive Test Suite for Emotion System

Tests emotion state machine and transitions for OpenDuck Mini V3:
- Emotion states (idle, happy, thinking, alert, error)
- State transitions and timing
- LED pattern + servo coordination
- Intensity modulation
- Error recovery

Coverage includes:
1. State machine initialization and validation
2. Transition logic and timing
3. Intensity/arousal mapping
4. LED and servo coordination
5. Error handling and recovery
6. Performance (state transitions <50ms)

Run with: pytest tests/test_emotion/test_emotion_system.py -v
Coverage: pytest tests/test_emotion --cov=src.emotion --cov-report=term-missing

Author: Boston Dynamics Test Engineer
Created: 17 January 2026
"""

import time
from typing import Dict
from unittest.mock import Mock, call

import pytest


# =============================================================================
# EmotionState Tests
# =============================================================================

class TestEmotionState:
    """Tests for EmotionState enum or class."""

    def test_emotion_states_defined(self):
        """All standard emotion states are defined."""
        from src.emotion.states import EmotionState

        # Standard emotions
        assert hasattr(EmotionState, 'IDLE')
        assert hasattr(EmotionState, 'HAPPY')
        assert hasattr(EmotionState, 'THINKING')
        assert hasattr(EmotionState, 'ALERT')
        assert hasattr(EmotionState, 'ERROR')

    def test_emotion_state_unique_values(self):
        """Each emotion state has unique value."""
        from src.emotion.states import EmotionState

        states = [
            EmotionState.IDLE,
            EmotionState.HAPPY,
            EmotionState.THINKING,
            EmotionState.ALERT,
            EmotionState.ERROR,
        ]

        # All values should be unique
        assert len(states) == len(set(states))

    def test_emotion_state_string_representation(self):
        """Emotion states have readable string representations."""
        from src.emotion.states import EmotionState

        assert 'IDLE' in str(EmotionState.IDLE)
        assert 'HAPPY' in str(EmotionState.HAPPY)


# =============================================================================
# EmotionConfig Tests
# =============================================================================

class TestEmotionConfig:
    """Tests for emotion configuration dataclass."""

    def test_emotion_config_defaults(self, emotion_config):
        """EmotionConfig has sensible defaults."""
        from src.emotion.config import EmotionConfig

        config = EmotionConfig()
        assert config.transition_duration_ms > 0
        assert 0.0 <= config.default_brightness <= 1.0

    def test_emotion_config_custom_values(self):
        """EmotionConfig accepts custom values."""
        from src.emotion.config import EmotionConfig

        config = EmotionConfig(
            transition_duration_ms=1000,
            idle_timeout_ms=10000,
            default_brightness=0.5
        )

        assert config.transition_duration_ms == 1000
        assert config.idle_timeout_ms == 10000
        assert config.default_brightness == 0.5

    def test_emotion_config_validates_brightness(self):
        """EmotionConfig validates brightness range."""
        from src.emotion.config import EmotionConfig

        # Out of range should raise
        with pytest.raises(ValueError):
            EmotionConfig(default_brightness=1.5)

        with pytest.raises(ValueError):
            EmotionConfig(default_brightness=-0.1)


# =============================================================================
# EmotionStateMachine Tests
# =============================================================================

class TestEmotionStateMachine:
    """Tests for main emotion state machine."""

    def test_state_machine_initialization(self, mock_led_controller,
                                          mock_servo_controller, emotion_config):
        """State machine initializes in IDLE state."""
        from src.emotion.state_machine import EmotionStateMachine
        from src.emotion.states import EmotionState

        sm = EmotionStateMachine(
            led_controller=mock_led_controller,
            servo_controller=mock_servo_controller,
            config=emotion_config
        )

        assert sm.current_state == EmotionState.IDLE
        assert not sm.is_transitioning()

    def test_transition_to_new_state(self, mock_led_controller,
                                     mock_servo_controller, emotion_definitions):
        """Transition to new state triggers LED and servo changes."""
        from src.emotion.state_machine import EmotionStateMachine
        from src.emotion.states import EmotionState

        sm = EmotionStateMachine(
            led_controller=mock_led_controller,
            servo_controller=mock_servo_controller
        )

        # Transition to HAPPY
        sm.set_emotion(EmotionState.HAPPY)

        # Should call LED controller
        mock_led_controller.set_pattern.assert_called()
        mock_led_controller.set_color.assert_called()

        # Should call servo controller
        mock_servo_controller.set_position.assert_called()

    def test_transition_timing(self, mock_led_controller,
                                mock_servo_controller, emotion_config):
        """Transition completes within configured duration."""
        from src.emotion.state_machine import EmotionStateMachine
        from src.emotion.states import EmotionState

        config = emotion_config.copy()
        config['transition_duration_ms'] = 500

        sm = EmotionStateMachine(
            led_controller=mock_led_controller,
            servo_controller=mock_servo_controller,
            config=config
        )

        start = time.monotonic()
        sm.set_emotion(EmotionState.HAPPY)

        # Wait for transition to complete
        while sm.is_transitioning():
            sm.update()
            time.sleep(0.01)

        elapsed_ms = (time.monotonic() - start) * 1000

        # Should complete within configured time (allow 10% tolerance)
        assert elapsed_ms < config['transition_duration_ms'] * 1.1

    def test_can_override_transition_during_transition(self, mock_led_controller,
                                                        mock_servo_controller):
        """New emotion overrides current transition (responsive design)."""
        from src.emotion.state_machine import EmotionStateMachine
        from src.emotion.states import EmotionState

        sm = EmotionStateMachine(
            led_controller=mock_led_controller,
            servo_controller=mock_servo_controller
        )

        # Start transition to HAPPY
        sm.set_emotion(EmotionState.HAPPY)

        # Override with ALERT (should succeed, not raise)
        sm.set_emotion(EmotionState.ALERT)

        # Should now be in ALERT state
        assert sm.get_current_emotion() == EmotionState.ALERT

    def test_same_state_is_noop(self, mock_led_controller,
                                 mock_servo_controller):
        """Setting same state twice is no-op."""
        from src.emotion.state_machine import EmotionStateMachine
        from src.emotion.states import EmotionState

        sm = EmotionStateMachine(
            led_controller=mock_led_controller,
            servo_controller=mock_servo_controller
        )

        # Set to IDLE (already in IDLE)
        sm.set_emotion(EmotionState.IDLE)

        # Should not trigger changes
        mock_led_controller.set_pattern.assert_not_called()

    def test_intensity_modulation(self, mock_led_controller,
                                   mock_servo_controller):
        """Intensity parameter modulates emotion expression."""
        from src.emotion.state_machine import EmotionStateMachine
        from src.emotion.states import EmotionState

        sm = EmotionStateMachine(
            led_controller=mock_led_controller,
            servo_controller=mock_servo_controller
        )

        # Set HAPPY with different intensities
        sm.set_emotion(EmotionState.HAPPY, intensity=0.5)
        low_intensity_calls = len(mock_led_controller.set_brightness.call_args_list)

        sm.wait_for_transition()
        sm.set_emotion(EmotionState.IDLE)
        sm.wait_for_transition()

        sm.set_emotion(EmotionState.HAPPY, intensity=1.0)
        high_intensity_calls = len(mock_led_controller.set_brightness.call_args_list)

        # Should have called brightness setter with different values
        assert high_intensity_calls > low_intensity_calls

    def test_update_progresses_transition(self, mock_led_controller,
                                          mock_servo_controller):
        """update() progresses transition animation."""
        from src.emotion.state_machine import EmotionStateMachine
        from src.emotion.states import EmotionState

        sm = EmotionStateMachine(
            led_controller=mock_led_controller,
            servo_controller=mock_servo_controller
        )

        sm.set_emotion(EmotionState.HAPPY)

        initial_transitioning = sm.is_transitioning()

        # Call update multiple times
        for _ in range(100):
            sm.update()
            time.sleep(0.01)

        final_transitioning = sm.is_transitioning()

        # Should have progressed from transitioning to not transitioning
        assert initial_transitioning is True
        assert final_transitioning is False

    def test_get_current_emotion(self, mock_led_controller,
                                  mock_servo_controller):
        """get_current_emotion() returns current state."""
        from src.emotion.state_machine import EmotionStateMachine
        from src.emotion.states import EmotionState

        sm = EmotionStateMachine(
            led_controller=mock_led_controller,
            servo_controller=mock_servo_controller
        )

        assert sm.get_current_emotion() == EmotionState.IDLE

        sm.set_emotion(EmotionState.THINKING)
        sm.wait_for_transition()

        assert sm.get_current_emotion() == EmotionState.THINKING

    def test_auto_return_to_idle(self, mock_led_controller,
                                  mock_servo_controller, emotion_config):
        """After idle_timeout, returns to IDLE state."""
        from src.emotion.state_machine import EmotionStateMachine
        from src.emotion.states import EmotionState

        config = emotion_config.copy()
        config['idle_timeout_ms'] = 100  # Short timeout for testing

        sm = EmotionStateMachine(
            led_controller=mock_led_controller,
            servo_controller=mock_servo_controller,
            config=config,
            auto_idle=True
        )

        # Set to HAPPY
        sm.set_emotion(EmotionState.HAPPY)
        sm.wait_for_transition()

        assert sm.get_current_emotion() == EmotionState.HAPPY

        # Wait for timeout + some margin
        time.sleep(0.15)
        sm.update()

        # Should have auto-transitioned to IDLE
        assert sm.get_current_emotion() == EmotionState.IDLE


# =============================================================================
# Emotion Definitions Tests
# =============================================================================

class TestEmotionDefinitions:
    """Tests for emotion definition mappings."""

    def test_all_standard_emotions_defined(self, emotion_definitions):
        """All standard emotions have definitions."""
        from src.emotion.definitions import EMOTION_DEFINITIONS

        required_emotions = ['idle', 'happy', 'thinking', 'alert', 'error']

        for emotion in required_emotions:
            assert emotion in EMOTION_DEFINITIONS

    def test_emotion_definition_has_required_fields(self):
        """Each emotion definition has required fields."""
        from src.emotion.definitions import EMOTION_DEFINITIONS

        required_fields = ['pattern', 'color', 'speed']

        for emotion_name, definition in EMOTION_DEFINITIONS.items():
            for field in required_fields:
                assert field in definition, \
                    f"Emotion '{emotion_name}' missing field '{field}'"

    def test_emotion_colors_valid_rgb(self):
        """All emotion colors are valid RGB tuples."""
        from src.emotion.definitions import EMOTION_DEFINITIONS

        for emotion_name, definition in EMOTION_DEFINITIONS.items():
            color = definition['color']
            assert isinstance(color, tuple)
            assert len(color) == 3
            for channel in color:
                assert 0 <= channel <= 255, \
                    f"Invalid color channel in '{emotion_name}': {channel}"

    def test_emotion_speeds_positive(self):
        """All emotion speeds are positive."""
        from src.emotion.definitions import EMOTION_DEFINITIONS

        for emotion_name, definition in EMOTION_DEFINITIONS.items():
            speed = definition['speed']
            assert speed > 0, f"Invalid speed in '{emotion_name}': {speed}"


# =============================================================================
# Error Handling Tests
# =============================================================================

class TestEmotionErrorHandling:
    """Tests for error handling and recovery."""

    def test_invalid_emotion_state_raises(self, mock_led_controller,
                                          mock_servo_controller):
        """Setting invalid emotion state raises ValueError."""
        from src.emotion.state_machine import EmotionStateMachine

        sm = EmotionStateMachine(
            led_controller=mock_led_controller,
            servo_controller=mock_servo_controller
        )

        with pytest.raises(ValueError, match="Invalid emotion"):
            sm.set_emotion("INVALID_EMOTION")

    def test_led_controller_failure_handled(self, mock_servo_controller):
        """LED controller failure doesn't crash state machine."""
        from src.emotion.state_machine import EmotionStateMachine
        from src.emotion.states import EmotionState

        # Mock LED controller that raises exceptions
        failing_led = Mock()
        failing_led.set_pattern.side_effect = RuntimeError("LED hardware error")

        sm = EmotionStateMachine(
            led_controller=failing_led,
            servo_controller=mock_servo_controller
        )

        # Should not raise, just log error
        sm.set_emotion(EmotionState.HAPPY)
        sm.update()

    def test_servo_controller_failure_handled(self, mock_led_controller):
        """Servo controller failure doesn't crash state machine."""
        from src.emotion.state_machine import EmotionStateMachine
        from src.emotion.states import EmotionState

        # Mock servo controller that raises exceptions
        failing_servo = Mock()
        failing_servo.set_position.side_effect = RuntimeError("Servo error")

        sm = EmotionStateMachine(
            led_controller=mock_led_controller,
            servo_controller=failing_servo
        )

        # Should not raise, just log error
        sm.set_emotion(EmotionState.ALERT)
        sm.update()


# =============================================================================
# Performance Tests
# =============================================================================

class TestEmotionSystemPerformance:
    """Performance tests for emotion system."""

    def test_state_transition_fast(self, mock_led_controller,
                                    mock_servo_controller):
        """State transition initiation is fast (<50ms)."""
        from src.emotion.state_machine import EmotionStateMachine
        from src.emotion.states import EmotionState

        sm = EmotionStateMachine(
            led_controller=mock_led_controller,
            servo_controller=mock_servo_controller
        )

        start = time.perf_counter()
        sm.set_emotion(EmotionState.HAPPY)
        elapsed = time.perf_counter() - start

        elapsed_ms = elapsed * 1000

        assert elapsed_ms < 50, \
            f"State transition too slow: {elapsed_ms:.2f}ms"

    def test_update_fast(self, mock_led_controller,
                         mock_servo_controller):
        """update() call is fast (<10ms)."""
        from src.emotion.state_machine import EmotionStateMachine
        from src.emotion.states import EmotionState

        sm = EmotionStateMachine(
            led_controller=mock_led_controller,
            servo_controller=mock_servo_controller
        )

        sm.set_emotion(EmotionState.THINKING)

        # Measure 100 update calls
        iterations = 100
        start = time.perf_counter()
        for _ in range(iterations):
            sm.update()
        elapsed = time.perf_counter() - start

        avg_ms = (elapsed / iterations) * 1000

        assert avg_ms < 10, \
            f"update() too slow: {avg_ms:.2f}ms avg"


# =============================================================================
# Integration Tests
# =============================================================================

class TestEmotionSystemIntegration:
    """Integration tests for complete emotion workflows."""

    def test_emotion_sequence(self, mock_led_controller,
                               mock_servo_controller):
        """Can sequence through multiple emotions."""
        from src.emotion.state_machine import EmotionStateMachine
        from src.emotion.states import EmotionState

        sm = EmotionStateMachine(
            led_controller=mock_led_controller,
            servo_controller=mock_servo_controller
        )

        emotions = [
            EmotionState.IDLE,
            EmotionState.HAPPY,
            EmotionState.THINKING,
            EmotionState.ALERT,
            EmotionState.IDLE,
        ]

        for emotion in emotions:
            sm.set_emotion(emotion)
            sm.wait_for_transition()
            assert sm.get_current_emotion() == emotion

    def test_rapid_emotion_changes(self, mock_led_controller,
                                    mock_servo_controller):
        """Handle rapid emotion changes gracefully."""
        from src.emotion.state_machine import EmotionStateMachine
        from src.emotion.states import EmotionState

        sm = EmotionStateMachine(
            led_controller=mock_led_controller,
            servo_controller=mock_servo_controller,
            config={'transition_duration_ms': 100}  # Fast transitions
        )

        # Rapidly change emotions
        for i in range(10):
            if i % 2 == 0:
                sm.set_emotion(EmotionState.HAPPY)
            else:
                sm.set_emotion(EmotionState.THINKING)

            time.sleep(0.05)  # 50ms between changes
            sm.update()

        # Should eventually settle
        assert sm.get_current_emotion() in [EmotionState.HAPPY, EmotionState.THINKING]


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
