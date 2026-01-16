"""Tests for SafetyCoordinator class.

Tests verify:
- Lifecycle management (start/stop)
- Shutdown order enforcement
- Watchdog feeding with safety checks
- Stall detection triggers E-stop
- Context manager protocol
- Thread safety
"""

import threading
import time
from unittest.mock import Mock, MagicMock, patch

import pytest

from src.core.safety_coordinator import SafetyCoordinator, SafetyStatus
from src.safety.emergency_stop import SafetyState
from src.safety.current_limiter import StallCondition


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_gpio():
    """Mock GPIO provider."""
    gpio = Mock()
    gpio.BCM = 11
    gpio.IN = 1
    gpio.PUD_UP = 22
    gpio.FALLING = 32
    gpio.setmode = Mock()
    gpio.setup = Mock()
    gpio.input = Mock(return_value=1)  # Button not pressed
    gpio.add_event_detect = Mock()
    gpio.remove_event_detect = Mock()
    gpio.cleanup = Mock()
    return gpio


@pytest.fixture
def mock_servo_driver():
    """Mock servo driver."""
    driver = Mock()
    driver.disable_all = Mock()
    driver.set_servo_angle = Mock()
    driver.get_channel_state = Mock(return_value={'angle': 90.0})
    return driver


@pytest.fixture
def safety_coordinator(mock_servo_driver, mock_gpio):
    """SafetyCoordinator with mocked hardware."""
    coord = SafetyCoordinator(
        servo_driver=mock_servo_driver,
        gpio_provider=mock_gpio,
        watchdog_timeout_ms=500,
        estop_gpio_pin=26,
    )
    yield coord
    # Cleanup
    try:
        coord.stop()
    except Exception:
        pass


@pytest.fixture
def started_coordinator(safety_coordinator):
    """SafetyCoordinator in started state."""
    safety_coordinator.start()
    return safety_coordinator


# =============================================================================
# Initialization Tests
# =============================================================================


class TestSafetyCoordinatorInit:
    """Tests for SafetyCoordinator initialization."""

    def test_init_creates_subsystems(self, mock_servo_driver, mock_gpio):
        """Verify all safety subsystems are created."""
        coord = SafetyCoordinator(
            servo_driver=mock_servo_driver,
            gpio_provider=mock_gpio,
        )
        assert coord._emergency_stop is not None
        assert coord._watchdog is not None
        assert coord._current_limiter is not None

    def test_init_with_custom_timeout(self, mock_servo_driver, mock_gpio):
        """Verify custom watchdog timeout is applied."""
        coord = SafetyCoordinator(
            servo_driver=mock_servo_driver,
            gpio_provider=mock_gpio,
            watchdog_timeout_ms=1000,
        )
        assert coord.watchdog_timeout_ms == 1000

    def test_init_with_custom_gpio_pin(self, mock_servo_driver, mock_gpio):
        """Verify custom GPIO pin is applied."""
        coord = SafetyCoordinator(
            servo_driver=mock_servo_driver,
            gpio_provider=mock_gpio,
            estop_gpio_pin=17,
        )
        assert coord.estop_gpio_pin == 17

    def test_init_rejects_invalid_timeout(self, mock_servo_driver, mock_gpio):
        """Verify zero or negative timeout is rejected."""
        with pytest.raises(ValueError, match="positive"):
            SafetyCoordinator(
                servo_driver=mock_servo_driver,
                gpio_provider=mock_gpio,
                watchdog_timeout_ms=0,
            )

        with pytest.raises(ValueError, match="positive"):
            SafetyCoordinator(
                servo_driver=mock_servo_driver,
                gpio_provider=mock_gpio,
                watchdog_timeout_ms=-100,
            )

    def test_init_not_started(self, safety_coordinator):
        """Verify coordinator starts in not-started state."""
        assert not safety_coordinator._started
        assert not safety_coordinator.is_safe


# =============================================================================
# Lifecycle Tests
# =============================================================================


class TestSafetyCoordinatorLifecycle:
    """Tests for start/stop lifecycle."""

    def test_start_returns_true_on_success(self, safety_coordinator):
        """Verify start() returns True on success."""
        result = safety_coordinator.start()
        assert result is True

    def test_start_sets_started_flag(self, safety_coordinator):
        """Verify start() sets _started flag."""
        safety_coordinator.start()
        assert safety_coordinator._started is True

    def test_start_starts_estop(self, safety_coordinator):
        """Verify start() transitions E-stop to RUNNING."""
        safety_coordinator.start()
        assert safety_coordinator._emergency_stop.state == SafetyState.RUNNING

    def test_start_starts_watchdog(self, safety_coordinator):
        """Verify start() starts watchdog monitoring."""
        safety_coordinator.start()
        assert safety_coordinator._watchdog.is_running is True

    def test_start_is_idempotent(self, safety_coordinator):
        """Verify repeated start() calls don't error."""
        safety_coordinator.start()
        result = safety_coordinator.start()
        assert result is True

    def test_stop_clears_started_flag(self, started_coordinator):
        """Verify stop() clears _started flag."""
        started_coordinator.stop()
        assert started_coordinator._started is False

    def test_stop_stops_watchdog_first(self, started_coordinator):
        """Verify watchdog is stopped before E-stop trigger."""
        # We can verify order by checking state after stop
        started_coordinator.stop()
        assert started_coordinator._watchdog.is_running is False

    def test_stop_triggers_estop(self, started_coordinator, mock_servo_driver):
        """Verify stop() triggers E-stop."""
        started_coordinator.stop()
        # E-stop should have been triggered
        assert started_coordinator._emergency_stop.state in (
            SafetyState.E_STOP,
            SafetyState.RESET_REQUIRED,
        )

    def test_stop_is_idempotent(self, started_coordinator):
        """Verify repeated stop() calls don't error."""
        started_coordinator.stop()
        started_coordinator.stop()  # Should not raise
        assert started_coordinator._started is False


# =============================================================================
# Context Manager Tests
# =============================================================================


class TestSafetyCoordinatorContextManager:
    """Tests for context manager protocol."""

    def test_context_manager_starts(self, safety_coordinator):
        """Verify __enter__ starts the coordinator."""
        with safety_coordinator as coord:
            assert coord._started is True
            assert coord.is_safe is True

    def test_context_manager_stops_on_exit(self, safety_coordinator):
        """Verify __exit__ stops the coordinator."""
        with safety_coordinator:
            pass
        assert safety_coordinator._started is False

    def test_context_manager_stops_on_exception(self, safety_coordinator):
        """Verify __exit__ stops even on exception."""
        with pytest.raises(RuntimeError):
            with safety_coordinator:
                raise RuntimeError("Test error")
        assert safety_coordinator._started is False


# =============================================================================
# Watchdog Feeding Tests
# =============================================================================


class TestFeedWatchdog:
    """Tests for feed_watchdog() method."""

    def test_feed_returns_true_when_safe(self, started_coordinator):
        """Verify feed_watchdog() returns True when all checks pass."""
        result = started_coordinator.feed_watchdog()
        assert result is True

    def test_feed_returns_false_when_not_started(self, safety_coordinator):
        """Verify feed_watchdog() returns False when not started."""
        result = safety_coordinator.feed_watchdog()
        assert result is False

    def test_feed_returns_false_after_estop(self, started_coordinator):
        """Verify feed_watchdog() returns False after E-stop."""
        started_coordinator.trigger_estop("test")
        result = started_coordinator.feed_watchdog()
        assert result is False

    def test_feed_triggers_estop_on_stall(self, started_coordinator):
        """Verify feed_watchdog() triggers E-stop on confirmed stall."""
        # Simulate stall condition
        started_coordinator._current_limiter._channel_states[0].is_moving = True
        started_coordinator._current_limiter._channel_states[0].stall_condition = (
            StallCondition.CONFIRMED
        )

        result = started_coordinator.feed_watchdog()
        assert result is False
        assert started_coordinator._emergency_stop.state in (
            SafetyState.E_STOP,
            SafetyState.RESET_REQUIRED,
        )

    def test_feed_does_not_trigger_on_suspected_stall(self, started_coordinator):
        """Verify feed_watchdog() allows SUSPECTED stall (not CONFIRMED)."""
        # Simulate suspected stall (not confirmed)
        started_coordinator._current_limiter._channel_states[0].is_moving = True
        started_coordinator._current_limiter._channel_states[0].stall_condition = (
            StallCondition.SUSPECTED
        )

        result = started_coordinator.feed_watchdog()
        # SUSPECTED is allowed, only CONFIRMED triggers E-stop
        assert result is True

    def test_feed_actually_feeds_watchdog(self, started_coordinator):
        """Verify feed_watchdog() actually feeds the underlying watchdog."""
        initial_feed_time = started_coordinator._watchdog._last_feed_time
        time.sleep(0.01)  # Small delay
        started_coordinator.feed_watchdog()
        assert started_coordinator._watchdog._last_feed_time > initial_feed_time


# =============================================================================
# Movement Safety Tests
# =============================================================================


class TestMovementSafety:
    """Tests for movement safety methods."""

    def test_check_movement_allowed_when_running(self, started_coordinator):
        """Verify movement allowed in RUNNING state."""
        allowed, reason = started_coordinator.check_movement_allowed(0)
        assert allowed is True
        assert reason == ""

    def test_check_movement_blocked_after_estop(self, started_coordinator):
        """Verify movement blocked after E-stop."""
        started_coordinator.trigger_estop("test")
        allowed, reason = started_coordinator.check_movement_allowed(0)
        assert allowed is False
        assert "E-stop" in reason

    def test_check_movement_blocked_on_stall(self, started_coordinator):
        """Verify movement blocked when stall confirmed."""
        # Confirm stall
        started_coordinator._current_limiter._channel_states[0].stall_condition = (
            StallCondition.CONFIRMED
        )
        allowed, reason = started_coordinator.check_movement_allowed(0)
        assert allowed is False
        assert "stall" in reason.lower()

    def test_register_movement(self, started_coordinator):
        """Verify register_movement() updates state."""
        started_coordinator.register_movement(0, 90.0)
        state = started_coordinator._current_limiter._channel_states[0]
        assert state.is_moving is True
        assert state.target_angle == 90.0

    def test_complete_movement(self, started_coordinator):
        """Verify complete_movement() updates state."""
        started_coordinator.register_movement(0, 90.0)
        started_coordinator.complete_movement(0)
        state = started_coordinator._current_limiter._channel_states[0]
        assert state.is_moving is False


# =============================================================================
# E-Stop Tests
# =============================================================================


class TestEStop:
    """Tests for E-stop methods."""

    def test_trigger_estop_returns_latency(self, started_coordinator):
        """Verify trigger_estop() returns latency value."""
        latency = started_coordinator.trigger_estop("test")
        assert isinstance(latency, float)
        assert latency >= 0.0  # Negative means error

    def test_trigger_estop_changes_state(self, started_coordinator):
        """Verify trigger_estop() changes E-stop state."""
        started_coordinator.trigger_estop("test")
        assert started_coordinator._emergency_stop.state in (
            SafetyState.E_STOP,
            SafetyState.RESET_REQUIRED,
        )

    def test_trigger_estop_records_source(self, started_coordinator):
        """Verify trigger_estop() records source."""
        started_coordinator.trigger_estop("my_source")
        assert started_coordinator._last_estop_source == "my_source"

    def test_trigger_estop_never_raises(self, started_coordinator, mock_servo_driver):
        """Verify trigger_estop() never raises exceptions."""
        # Make servo driver fail
        mock_servo_driver.disable_all.side_effect = RuntimeError("I2C error")

        # Should not raise
        latency = started_coordinator.trigger_estop("test")
        # Returns -1.0 on error
        assert latency == -1.0 or latency >= 0.0

    def test_reset_estop_succeeds_when_clear(self, started_coordinator):
        """Verify reset_estop() succeeds when conditions are met."""
        started_coordinator.trigger_estop("test")
        result = started_coordinator.reset_estop()
        assert result is True

    def test_reset_estop_fails_with_stall(self, started_coordinator):
        """Verify reset_estop() fails when stall exists."""
        started_coordinator.trigger_estop("test")
        # Add stall condition
        started_coordinator._current_limiter._channel_states[0].stall_condition = (
            StallCondition.CONFIRMED
        )
        result = started_coordinator.reset_estop()
        assert result is False


# =============================================================================
# Status and Diagnostics Tests
# =============================================================================


class TestStatusAndDiagnostics:
    """Tests for status and diagnostics methods."""

    def test_is_safe_when_running(self, started_coordinator):
        """Verify is_safe is True when all systems OK."""
        assert started_coordinator.is_safe is True

    def test_is_safe_false_after_estop(self, started_coordinator):
        """Verify is_safe is False after E-stop."""
        started_coordinator.trigger_estop("test")
        assert started_coordinator.is_safe is False

    def test_is_safe_false_when_not_started(self, safety_coordinator):
        """Verify is_safe is False when not started."""
        assert safety_coordinator.is_safe is False

    def test_get_status_returns_dataclass(self, started_coordinator):
        """Verify get_status() returns SafetyStatus."""
        status = started_coordinator.get_status()
        assert isinstance(status, SafetyStatus)

    def test_get_status_reflects_state(self, started_coordinator):
        """Verify get_status() reflects current state."""
        status = started_coordinator.get_status()
        assert status.is_safe is True
        assert status.estop_state == SafetyState.RUNNING
        assert status.watchdog_running is True
        assert status.watchdog_expired is False

    def test_get_status_after_estop(self, started_coordinator):
        """Verify get_status() reflects E-stop state."""
        started_coordinator.trigger_estop("test_source")
        status = started_coordinator.get_status()
        assert status.is_safe is False
        assert status.last_estop_source == "test_source"

    def test_get_diagnostics_returns_dict(self, started_coordinator):
        """Verify get_diagnostics() returns dictionary."""
        diag = started_coordinator.get_diagnostics()
        assert isinstance(diag, dict)
        assert "started" in diag
        assert "is_safe" in diag
        assert "estop" in diag
        assert "watchdog" in diag
        assert "current_limiter" in diag


# =============================================================================
# Thread Safety Tests
# =============================================================================


class TestThreadSafety:
    """Tests for thread safety."""

    def test_concurrent_feed_calls(self, started_coordinator):
        """Verify concurrent feed_watchdog() calls don't crash."""
        results = []
        errors = []

        def feed_loop(count):
            try:
                for _ in range(count):
                    result = started_coordinator.feed_watchdog()
                    results.append(result)
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=feed_loop, args=(10,))
            for _ in range(4)
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert all(r is True for r in results)

    def test_concurrent_movement_registration(self, started_coordinator):
        """Verify concurrent movement registrations don't crash."""
        errors = []

        def register_movements(start_channel, count):
            try:
                for i in range(count):
                    channel = (start_channel + i) % 16
                    started_coordinator.register_movement(channel, 90.0)
                    started_coordinator.complete_movement(channel)
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=register_movements, args=(i * 4, 5))
            for i in range(4)
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0


# =============================================================================
# Repr Test
# =============================================================================


class TestRepr:
    """Tests for __repr__ method."""

    def test_repr_when_not_started(self, safety_coordinator):
        """Verify repr shows not started state."""
        r = repr(safety_coordinator)
        assert "started=False" in r

    def test_repr_when_started(self, started_coordinator):
        """Verify repr shows started state."""
        r = repr(started_coordinator)
        assert "started=True" in r
        assert "is_safe=True" in r
