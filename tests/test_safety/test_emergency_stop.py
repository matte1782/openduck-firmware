"""Comprehensive unit tests for EmergencyStop safety system.

Tests cover:
- Initialization and configuration
- State machine transitions
- Latency requirements (<5ms)
- Callback invocation
- Thread safety guarantees
- GPIO integration
- Error handling

Test Classes:
    TestEmergencyStopInitialization: Constructor and configuration tests
    TestStateMachine: State transition validation tests
    TestLatency: Performance and timing tests
    TestCallbacks: Callback registration and invocation tests
    TestThreadSafety: Concurrent access tests
    TestGPIOIntegration: Hardware simulation tests
"""

import threading
import time
from typing import List, Tuple, Any
from unittest.mock import Mock, patch

import pytest

from src.safety.emergency_stop import EmergencyStop, SafetyState


class TestEmergencyStopInitialization:
    """Tests for EmergencyStop constructor and initial configuration."""

    def test_default_state_is_init(
        self, mock_gpio, mock_servo_driver
    ) -> None:
        """Test that default state after construction is INIT."""
        e_stop = EmergencyStop(
            servo_driver=mock_servo_driver,
            gpio_provider=mock_gpio
        )
        assert e_stop.state == SafetyState.INIT
        e_stop.cleanup()

    def test_gpio_configuration_called_correctly(
        self, mock_gpio, mock_servo_driver
    ) -> None:
        """Test that GPIO is configured with correct parameters on start()."""
        e_stop = EmergencyStop(
            servo_driver=mock_servo_driver,
            gpio_provider=mock_gpio,
            gpio_pin=26,
            debounce_ms=50
        )
        e_stop.start()

        # Verify setmode was called with BCM
        assert len(mock_gpio.setmode_calls) == 1
        assert mock_gpio.setmode_calls[0] == mock_gpio.BCM

        # Verify setup was called correctly
        assert len(mock_gpio.setup_calls) == 1
        pin, direction, pull_up_down = mock_gpio.setup_calls[0]
        assert pin == 26
        assert direction == mock_gpio.IN
        assert pull_up_down == mock_gpio.PUD_UP

        # Verify event detection was configured
        assert len(mock_gpio.add_event_detect_calls) == 1
        pin, edge, callback, bouncetime = mock_gpio.add_event_detect_calls[0]
        assert pin == 26
        assert edge == mock_gpio.FALLING
        assert callback is not None
        assert bouncetime == 50

        e_stop.cleanup()

    def test_custom_gpio_pin_parameter(
        self, mock_gpio, mock_servo_driver
    ) -> None:
        """Test custom GPIO pin is used correctly."""
        custom_pin = 17
        e_stop = EmergencyStop(
            servo_driver=mock_servo_driver,
            gpio_provider=mock_gpio,
            gpio_pin=custom_pin
        )
        e_stop.start()

        # Verify correct pin was used in setup
        assert len(mock_gpio.setup_calls) == 1
        pin, _, _ = mock_gpio.setup_calls[0]
        assert pin == custom_pin

        e_stop.cleanup()

    def test_mock_gpio_injection_works(
        self, mock_gpio, mock_servo_driver
    ) -> None:
        """Test that mock GPIO is properly injected and used."""
        e_stop = EmergencyStop(
            servo_driver=mock_servo_driver,
            gpio_provider=mock_gpio
        )

        # GPIO should be available
        assert e_stop.gpio_available is True

        # The internal reference should use our mock
        assert e_stop._gpio is mock_gpio

        e_stop.cleanup()

    def test_servo_driver_integration(
        self, mock_gpio, mock_servo_driver
    ) -> None:
        """Test servo driver is stored and accessible."""
        e_stop = EmergencyStop(
            servo_driver=mock_servo_driver,
            gpio_provider=mock_gpio
        )

        # Servo driver should be stored
        assert e_stop._servo_driver is mock_servo_driver

        # Trigger should call servo driver's disable_all
        e_stop.start()
        e_stop.trigger()

        assert mock_servo_driver.disable_all_calls == 1

        e_stop.cleanup()

    def test_invalid_gpio_pin_raises_value_error(
        self, mock_gpio, mock_servo_driver
    ) -> None:
        """Test that invalid GPIO pin raises ValueError."""
        with pytest.raises(ValueError, match="gpio_pin must be 0-27"):
            EmergencyStop(
                servo_driver=mock_servo_driver,
                gpio_provider=mock_gpio,
                gpio_pin=50  # Invalid: BCM pins are 0-27
            )

    def test_negative_debounce_raises_value_error(
        self, mock_gpio, mock_servo_driver
    ) -> None:
        """Test that negative debounce_ms raises ValueError."""
        with pytest.raises(ValueError, match="debounce_ms must be non-negative"):
            EmergencyStop(
                servo_driver=mock_servo_driver,
                gpio_provider=mock_gpio,
                debounce_ms=-10
            )

    def test_repr_string(
        self, mock_gpio, mock_servo_driver
    ) -> None:
        """Test string representation includes key info."""
        e_stop = EmergencyStop(
            servo_driver=mock_servo_driver,
            gpio_provider=mock_gpio,
            gpio_pin=26,
            auto_reset=True
        )

        repr_str = repr(e_stop)
        assert "EmergencyStop" in repr_str
        assert "INIT" in repr_str
        assert "gpio_pin=26" in repr_str
        assert "auto_reset=True" in repr_str

        e_stop.cleanup()


class TestStateMachine:
    """Tests for state machine transitions and validation."""

    def test_init_to_running_transition(
        self, mock_gpio, mock_servo_driver
    ) -> None:
        """Test INIT -> RUNNING transition via start()."""
        e_stop = EmergencyStop(
            servo_driver=mock_servo_driver,
            gpio_provider=mock_gpio
        )

        assert e_stop.state == SafetyState.INIT
        result = e_stop.start()

        assert result is True
        assert e_stop.state == SafetyState.RUNNING

        e_stop.cleanup()

    def test_running_to_estop_transition(
        self, mock_gpio, mock_servo_driver
    ) -> None:
        """Test RUNNING -> E_STOP transition via trigger()."""
        e_stop = EmergencyStop(
            servo_driver=mock_servo_driver,
            gpio_provider=mock_gpio
        )
        e_stop.start()

        assert e_stop.state == SafetyState.RUNNING
        e_stop.trigger(source="test")

        # Should auto-transition through E_STOP to RESET_REQUIRED
        assert e_stop.state == SafetyState.RESET_REQUIRED

        e_stop.cleanup()

    def test_estop_requires_manual_reset(
        self, mock_gpio, mock_servo_driver
    ) -> None:
        """Test E_STOP requires manual reset (auto_reset=False)."""
        e_stop = EmergencyStop(
            servo_driver=mock_servo_driver,
            gpio_provider=mock_gpio,
            auto_reset=False
        )
        e_stop.start()
        e_stop.trigger()

        # State should be RESET_REQUIRED
        assert e_stop.state == SafetyState.RESET_REQUIRED

        # Reset should transition to INIT (not RUNNING)
        e_stop.reset()
        assert e_stop.state == SafetyState.INIT

        # Need to call start() again
        e_stop.start()
        assert e_stop.state == SafetyState.RUNNING

        e_stop.cleanup()

    def test_estop_to_reset_required_transition(
        self, mock_gpio, mock_servo_driver
    ) -> None:
        """Test E_STOP -> RESET_REQUIRED auto-transition."""
        e_stop = EmergencyStop(
            servo_driver=mock_servo_driver,
            gpio_provider=mock_gpio
        )
        e_stop.start()

        # After trigger, should be in RESET_REQUIRED (auto-transitioned from E_STOP)
        e_stop.trigger()
        assert e_stop.state == SafetyState.RESET_REQUIRED

        e_stop.cleanup()

    def test_reset_required_to_running_with_auto_reset(
        self, mock_gpio, mock_servo_driver
    ) -> None:
        """Test RESET_REQUIRED -> RUNNING with auto_reset=True."""
        e_stop = EmergencyStop(
            servo_driver=mock_servo_driver,
            gpio_provider=mock_gpio,
            auto_reset=True
        )
        e_stop.start()
        e_stop.trigger()

        assert e_stop.state == SafetyState.RESET_REQUIRED

        # With auto_reset, reset() should go directly to RUNNING
        result = e_stop.reset()
        assert result is True
        assert e_stop.state == SafetyState.RUNNING

        e_stop.cleanup()

    def test_reset_fails_if_not_in_reset_required(
        self, mock_gpio, mock_servo_driver
    ) -> None:
        """Test reset() fails if not in RESET_REQUIRED state."""
        e_stop = EmergencyStop(
            servo_driver=mock_servo_driver,
            gpio_provider=mock_gpio
        )

        # In INIT state, reset should fail
        result = e_stop.reset()
        assert result is False
        assert e_stop.state == SafetyState.INIT

        # In RUNNING state, reset should fail
        e_stop.start()
        result = e_stop.reset()
        assert result is False
        assert e_stop.state == SafetyState.RUNNING

        e_stop.cleanup()

    def test_invalid_state_transitions_rejected(
        self, mock_gpio, mock_servo_driver
    ) -> None:
        """Test that invalid state transitions are rejected."""
        e_stop = EmergencyStop(
            servo_driver=mock_servo_driver,
            gpio_provider=mock_gpio
        )

        # Can't go from INIT directly to RESET_REQUIRED
        assert e_stop._validate_transition(SafetyState.RESET_REQUIRED) is False

        # Start to get to RUNNING
        e_stop.start()

        # Can't go from RUNNING back to INIT
        assert e_stop._validate_transition(SafetyState.INIT) is False

        e_stop.cleanup()

    def test_start_fails_when_already_running(
        self, mock_gpio, mock_servo_driver
    ) -> None:
        """Test start() returns False when already in RUNNING state."""
        e_stop = EmergencyStop(
            servo_driver=mock_servo_driver,
            gpio_provider=mock_gpio
        )

        # First start should succeed
        assert e_stop.start() is True
        assert e_stop.state == SafetyState.RUNNING

        # Second start should fail (already running)
        assert e_stop.start() is False
        assert e_stop.state == SafetyState.RUNNING

        e_stop.cleanup()

    def test_state_property_is_thread_safe(
        self, mock_gpio, mock_servo_driver
    ) -> None:
        """Test state property access is thread-safe."""
        e_stop = EmergencyStop(
            servo_driver=mock_servo_driver,
            gpio_provider=mock_gpio
        )
        e_stop.start()

        states_read: List[SafetyState] = []
        errors: List[Exception] = []

        def reader_thread():
            try:
                for _ in range(100):
                    states_read.append(e_stop.state)
                    time.sleep(0.001)
            except Exception as e:
                errors.append(e)

        # Start multiple reader threads
        threads = [threading.Thread(target=reader_thread) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=2.0)

        assert len(errors) == 0, f"Thread errors: {errors}"
        assert len(states_read) > 0

        e_stop.cleanup()


class TestLatency:
    """Tests for latency requirements and performance."""

    def test_trigger_latency_under_5ms(
        self, mock_gpio, mock_servo_driver
    ) -> None:
        """Test trigger() returns latency < 5ms."""
        e_stop = EmergencyStop(
            servo_driver=mock_servo_driver,
            gpio_provider=mock_gpio
        )
        e_stop.start()

        latency_ms = e_stop.trigger(source="test")

        # Latency should be under 5ms (with mocked servo driver)
        assert latency_ms < 5.0, f"Latency {latency_ms}ms exceeds 5ms limit"

        e_stop.cleanup()

    def test_disable_all_called_before_state_update(
        self, mock_gpio, mock_servo_driver
    ) -> None:
        """Test disable_all() is called immediately (before state callbacks)."""
        e_stop = EmergencyStop(
            servo_driver=mock_servo_driver,
            gpio_provider=mock_gpio
        )
        e_stop.start()

        call_order: List[str] = []

        def callback(old, new, source):
            call_order.append(f"callback_{new.name}")

        # Track when disable_all is called
        original_disable = mock_servo_driver.disable_all
        def tracked_disable():
            call_order.append("disable_all")
            return original_disable()

        mock_servo_driver.disable_all = tracked_disable

        e_stop.register_callback(callback)
        e_stop.trigger(source="test")

        # disable_all should be called first
        assert len(call_order) >= 1
        assert call_order[0] == "disable_all"

        e_stop.cleanup()

    def test_multiple_rapid_triggers_debounced(
        self, mock_gpio, mock_servo_driver, gpio_trigger_simulator
    ) -> None:
        """Test multiple rapid triggers are debounced (50ms)."""
        e_stop = EmergencyStop(
            servo_driver=mock_servo_driver,
            gpio_provider=mock_gpio,
            debounce_ms=50
        )
        e_stop.start()

        # First trigger should work
        latency1 = e_stop.trigger(source="first")
        assert latency1 > 0

        # Rapid subsequent triggers should return 0 (already stopped)
        latency2 = e_stop.trigger(source="second")
        latency3 = e_stop.trigger(source="third")

        assert latency2 == 0.0
        assert latency3 == 0.0

        # disable_all should only be called once
        assert mock_servo_driver.disable_all_calls == 1

        e_stop.cleanup()

    def test_latency_measurement_accuracy(
        self, mock_gpio, mock_servo_driver
    ) -> None:
        """Test latency measurement is reasonably accurate."""
        # Add known latency to servo driver
        mock_servo_driver.disable_latency_ms = 2.0

        e_stop = EmergencyStop(
            servo_driver=mock_servo_driver,
            gpio_provider=mock_gpio
        )
        e_stop.start()

        latency_ms = e_stop.trigger(source="test")

        # Latency should be at least 2ms (the artificial delay)
        assert latency_ms >= 2.0
        # But not absurdly high
        assert latency_ms < 50.0

        e_stop.cleanup()


class TestCallbacks:
    """Tests for callback registration and invocation."""

    def test_callback_invoked_on_state_change(
        self, mock_gpio, mock_servo_driver
    ) -> None:
        """Test callback is invoked when state changes."""
        e_stop = EmergencyStop(
            servo_driver=mock_servo_driver,
            gpio_provider=mock_gpio
        )

        callback_invocations: List[Tuple[SafetyState, SafetyState, str]] = []

        def callback(old, new, source):
            callback_invocations.append((old, new, source))

        e_stop.register_callback(callback)
        e_stop.start()

        # Should have one invocation for INIT -> RUNNING
        assert len(callback_invocations) == 1
        old, new, source = callback_invocations[0]
        assert old == SafetyState.INIT
        assert new == SafetyState.RUNNING
        assert source == "start"

        e_stop.cleanup()

    def test_multiple_callbacks_all_invoked(
        self, mock_gpio, mock_servo_driver
    ) -> None:
        """Test all registered callbacks are invoked."""
        e_stop = EmergencyStop(
            servo_driver=mock_servo_driver,
            gpio_provider=mock_gpio
        )

        invocation_counts = [0, 0, 0]

        def callback1(old, new, source):
            invocation_counts[0] += 1

        def callback2(old, new, source):
            invocation_counts[1] += 1

        def callback3(old, new, source):
            invocation_counts[2] += 1

        e_stop.register_callback(callback1)
        e_stop.register_callback(callback2)
        e_stop.register_callback(callback3)

        e_stop.start()

        # All three should have been invoked
        assert invocation_counts == [1, 1, 1]

        e_stop.cleanup()

    def test_callback_receives_correct_arguments(
        self, mock_gpio, mock_servo_driver
    ) -> None:
        """Test callback receives (old_state, new_state, source) correctly."""
        e_stop = EmergencyStop(
            servo_driver=mock_servo_driver,
            gpio_provider=mock_gpio
        )

        received_args: List[Tuple] = []

        def callback(old, new, source):
            received_args.append((old, new, source))

        e_stop.register_callback(callback)
        e_stop.start()
        e_stop.trigger(source="manual_test")

        # Should have multiple transitions recorded
        assert len(received_args) >= 3  # start, E_STOP, RESET_REQUIRED

        # Verify the trigger callbacks
        # Find the E_STOP transition
        estop_transition = [t for t in received_args if t[1] == SafetyState.E_STOP]
        assert len(estop_transition) == 1
        old, new, source = estop_transition[0]
        assert old == SafetyState.RUNNING
        assert new == SafetyState.E_STOP
        assert source == "manual_test"

        e_stop.cleanup()

    def test_callback_errors_dont_crash_estop(
        self, mock_gpio, mock_servo_driver
    ) -> None:
        """Test callback errors don't prevent e-stop from completing."""
        e_stop = EmergencyStop(
            servo_driver=mock_servo_driver,
            gpio_provider=mock_gpio
        )

        def bad_callback(old, new, source):
            raise RuntimeError("Callback error!")

        successful_calls = [0]

        def good_callback(old, new, source):
            successful_calls[0] += 1

        # Register bad callback first
        e_stop.register_callback(bad_callback)
        e_stop.register_callback(good_callback)

        # Should not raise, despite bad callback
        e_stop.start()
        e_stop.trigger(source="test")

        # Good callback should still have been invoked
        assert successful_calls[0] >= 1

        # State should still be correct
        assert e_stop.state == SafetyState.RESET_REQUIRED

        # Servo should still be disabled
        assert mock_servo_driver.disable_all_calls == 1

        e_stop.cleanup()

    def test_unregister_callback(
        self, mock_gpio, mock_servo_driver
    ) -> None:
        """Test callback can be unregistered."""
        e_stop = EmergencyStop(
            servo_driver=mock_servo_driver,
            gpio_provider=mock_gpio
        )

        invocation_count = [0]

        def callback(old, new, source):
            invocation_count[0] += 1

        e_stop.register_callback(callback)
        e_stop.start()

        # Should have been called for start()
        assert invocation_count[0] == 1

        # Unregister
        result = e_stop.unregister_callback(callback)
        assert result is True

        # Trigger should not invoke callback
        e_stop.trigger()
        assert invocation_count[0] == 1  # Still 1, not incremented

        e_stop.cleanup()


class TestThreadSafety:
    """Tests for thread safety guarantees."""

    def test_concurrent_triggers_are_safe(
        self, mock_gpio, mock_servo_driver
    ) -> None:
        """Test concurrent trigger() calls don't cause race conditions."""
        e_stop = EmergencyStop(
            servo_driver=mock_servo_driver,
            gpio_provider=mock_gpio
        )
        e_stop.start()

        results: List[float] = []
        errors: List[Exception] = []

        def trigger_thread():
            try:
                latency = e_stop.trigger(source="concurrent")
                results.append(latency)
            except Exception as e:
                errors.append(e)

        # Launch many concurrent trigger attempts
        threads = [threading.Thread(target=trigger_thread) for _ in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=2.0)

        assert len(errors) == 0, f"Thread errors: {errors}"
        assert len(results) == 20

        # Only one should have actually triggered (non-zero latency)
        non_zero = [r for r in results if r > 0]
        assert len(non_zero) == 1

        # disable_all should only be called once
        assert mock_servo_driver.disable_all_calls == 1

        e_stop.cleanup()

    def test_state_reads_during_trigger_are_safe(
        self, mock_gpio, mock_servo_driver
    ) -> None:
        """Test reading state during trigger operations is safe."""
        e_stop = EmergencyStop(
            servo_driver=mock_servo_driver,
            gpio_provider=mock_gpio
        )
        e_stop.start()

        states_observed: List[SafetyState] = []
        errors: List[Exception] = []

        def reader_thread():
            try:
                for _ in range(50):
                    states_observed.append(e_stop.state)
                    time.sleep(0.001)
            except Exception as e:
                errors.append(e)

        def trigger_thread():
            try:
                time.sleep(0.01)  # Short delay before trigger
                e_stop.trigger(source="test")
            except Exception as e:
                errors.append(e)

        # Start reader threads
        readers = [threading.Thread(target=reader_thread) for _ in range(5)]
        for t in readers:
            t.start()

        # Start trigger thread
        trigger = threading.Thread(target=trigger_thread)
        trigger.start()

        # Wait for all threads
        for t in readers:
            t.join(timeout=2.0)
        trigger.join(timeout=2.0)

        assert len(errors) == 0, f"Thread errors: {errors}"
        assert len(states_observed) > 0

        # All observed states should be valid
        valid_states = {SafetyState.RUNNING, SafetyState.E_STOP, SafetyState.RESET_REQUIRED}
        for state in states_observed:
            assert state in valid_states

        e_stop.cleanup()

    def test_cleanup_during_operation_is_safe(
        self, mock_gpio, mock_servo_driver
    ) -> None:
        """Test cleanup() during operation doesn't crash."""
        e_stop = EmergencyStop(
            servo_driver=mock_servo_driver,
            gpio_provider=mock_gpio
        )
        e_stop.start()

        errors: List[Exception] = []

        def cleanup_thread():
            try:
                time.sleep(0.01)
                e_stop.cleanup()
            except Exception as e:
                errors.append(e)

        def trigger_thread():
            try:
                for _ in range(10):
                    e_stop.trigger(source="test")
                    time.sleep(0.001)
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=cleanup_thread),
            threading.Thread(target=trigger_thread),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=2.0)

        # No crashes expected
        assert len(errors) == 0, f"Thread errors: {errors}"


class TestGPIOIntegration:
    """Tests for GPIO hardware simulation and integration."""

    def test_gpio_callback_triggers_estop(
        self, mock_gpio, mock_servo_driver
    ) -> None:
        """Test GPIO falling edge callback triggers emergency stop."""
        e_stop = EmergencyStop(
            servo_driver=mock_servo_driver,
            gpio_provider=mock_gpio,
            gpio_pin=26
        )
        e_stop.start()

        assert e_stop.state == SafetyState.RUNNING

        # Simulate button press
        mock_gpio.simulate_button_press(26)

        # Should now be in RESET_REQUIRED
        assert e_stop.state == SafetyState.RESET_REQUIRED

        # Servo should be disabled
        assert mock_servo_driver.disable_all_calls == 1

        e_stop.cleanup()

    def test_gpio_cleanup_on_destroy(
        self, mock_gpio, mock_servo_driver
    ) -> None:
        """Test GPIO resources are cleaned up properly."""
        e_stop = EmergencyStop(
            servo_driver=mock_servo_driver,
            gpio_provider=mock_gpio,
            gpio_pin=26
        )
        e_stop.start()

        # Cleanup should remove event detection and cleanup pin
        e_stop.cleanup()

        assert 26 in mock_gpio.remove_event_detect_calls
        assert 26 in mock_gpio.cleanup_calls

    def test_gpio_not_available_fallback(
        self, mock_servo_driver
    ) -> None:
        """Test graceful fallback when GPIO is not available."""
        # Don't provide gpio_provider, let it try to import RPi.GPIO
        with patch.dict('sys.modules', {'RPi': None, 'RPi.GPIO': None}):
            e_stop = EmergencyStop(
                servo_driver=mock_servo_driver,
                gpio_provider=None  # Force attempted import
            )

            # Should still be usable (software triggers work)
            assert e_stop.gpio_available is False
            e_stop.start()
            assert e_stop.state == SafetyState.RUNNING

            # Manual trigger should still work
            e_stop.trigger(source="software")
            assert e_stop.state == SafetyState.RESET_REQUIRED

            e_stop.cleanup()

    def test_context_manager_cleanup(
        self, mock_gpio, mock_servo_driver
    ) -> None:
        """Test context manager properly cleans up resources."""
        with EmergencyStop(
            servo_driver=mock_servo_driver,
            gpio_provider=mock_gpio
        ) as e_stop:
            e_stop.start()
            assert e_stop.state == SafetyState.RUNNING

        # After context exit, cleanup should have been called
        assert len(mock_gpio.cleanup_calls) >= 1


class TestEventHistory:
    """Tests for event history tracking."""

    def test_event_recorded_on_trigger(
        self, mock_gpio, mock_servo_driver
    ) -> None:
        """Test emergency stop event is recorded in history."""
        e_stop = EmergencyStop(
            servo_driver=mock_servo_driver,
            gpio_provider=mock_gpio
        )
        e_stop.start()

        # No events initially
        assert len(e_stop.event_history) == 0

        # Trigger
        e_stop.trigger(source="test_source")

        # Should have one event
        events = e_stop.event_history
        assert len(events) == 1

        event = events[0]
        assert event.source == "test_source"
        assert event.previous_state == SafetyState.RUNNING
        assert event.latency_ms >= 0
        assert event.timestamp > 0

        e_stop.cleanup()

    def test_event_history_is_copy(
        self, mock_gpio, mock_servo_driver
    ) -> None:
        """Test event_history returns a copy (not the internal list)."""
        e_stop = EmergencyStop(
            servo_driver=mock_servo_driver,
            gpio_provider=mock_gpio
        )
        e_stop.start()
        e_stop.trigger()

        history1 = e_stop.event_history
        history2 = e_stop.event_history

        # Should be equal but not the same object
        assert history1 == history2
        assert history1 is not history2

        e_stop.cleanup()


class TestIsSafeProperty:
    """Tests for is_safe property."""

    def test_is_safe_false_in_init(
        self, mock_gpio, mock_servo_driver
    ) -> None:
        """Test is_safe is False in INIT state."""
        e_stop = EmergencyStop(
            servo_driver=mock_servo_driver,
            gpio_provider=mock_gpio
        )
        assert e_stop.is_safe is False
        e_stop.cleanup()

    def test_is_safe_true_in_running(
        self, mock_gpio, mock_servo_driver
    ) -> None:
        """Test is_safe is True in RUNNING state."""
        e_stop = EmergencyStop(
            servo_driver=mock_servo_driver,
            gpio_provider=mock_gpio
        )
        e_stop.start()
        assert e_stop.is_safe is True
        e_stop.cleanup()

    def test_is_safe_false_after_trigger(
        self, mock_gpio, mock_servo_driver
    ) -> None:
        """Test is_safe is False after emergency stop triggered."""
        e_stop = EmergencyStop(
            servo_driver=mock_servo_driver,
            gpio_provider=mock_gpio
        )
        e_stop.start()
        e_stop.trigger()
        assert e_stop.is_safe is False
        e_stop.cleanup()


class TestServoDriverFailure:
    """Tests for handling servo driver failures."""

    def test_trigger_completes_despite_servo_error(
        self, mock_gpio, mock_servo_driver
    ) -> None:
        """Test trigger() completes even if servo driver raises."""
        mock_servo_driver.raise_on_disable = True

        e_stop = EmergencyStop(
            servo_driver=mock_servo_driver,
            gpio_provider=mock_gpio
        )
        e_stop.start()

        # Should not raise, despite servo error
        latency = e_stop.trigger(source="test")

        # State should still transition
        assert e_stop.state == SafetyState.RESET_REQUIRED

        # disable_all should have been attempted
        assert mock_servo_driver.disable_all_calls == 1

        e_stop.cleanup()


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_trigger_from_init_state(
        self, mock_gpio, mock_servo_driver
    ) -> None:
        """Test triggering from INIT state works."""
        e_stop = EmergencyStop(
            servo_driver=mock_servo_driver,
            gpio_provider=mock_gpio
        )

        # Should work from INIT (INIT -> E_STOP is valid)
        latency = e_stop.trigger(source="direct")

        assert e_stop.state == SafetyState.RESET_REQUIRED
        assert mock_servo_driver.disable_all_calls == 1

        e_stop.cleanup()

    def test_zero_debounce_time(
        self, mock_gpio, mock_servo_driver
    ) -> None:
        """Test zero debounce time is allowed."""
        e_stop = EmergencyStop(
            servo_driver=mock_servo_driver,
            gpio_provider=mock_gpio,
            debounce_ms=0
        )

        assert e_stop._debounce_ms == 0
        e_stop.start()
        e_stop.cleanup()

    def test_multiple_cleanup_calls_safe(
        self, mock_gpio, mock_servo_driver
    ) -> None:
        """Test calling cleanup() multiple times is safe."""
        e_stop = EmergencyStop(
            servo_driver=mock_servo_driver,
            gpio_provider=mock_gpio
        )
        e_stop.start()

        # Multiple cleanup calls should not raise
        e_stop.cleanup()
        e_stop.cleanup()
        e_stop.cleanup()

    def test_all_valid_gpio_pins(
        self, mock_gpio, mock_servo_driver
    ) -> None:
        """Test all valid GPIO pins (0-27) are accepted."""
        for pin in range(28):
            e_stop = EmergencyStop(
                servo_driver=mock_servo_driver,
                gpio_provider=mock_gpio,
                gpio_pin=pin
            )
            assert e_stop._gpio_pin == pin
            e_stop.cleanup()
            mock_gpio.reset()
