"""Tests for Robot orchestrator class.

Tests verify:
- Lifecycle management (start/stop/reset)
- State machine transitions
- Control loop operation
- Safety integration
- Arm kinematics integration
"""

import time
from unittest.mock import Mock

import pytest

from src.core.robot import Robot
from src.core.robot_state import (
    RobotState,
    RobotStateError,
    SafetyViolationError,
    HardwareError,
)
from src.safety.current_limiter import StallCondition


# =============================================================================
# Initialization Tests
# =============================================================================


class TestRobotInit:
    """Tests for Robot initialization."""

    def test_init_with_defaults(self, mock_servo_driver, mock_gpio):
        """Verify robot initializes with default parameters."""
        robot = Robot(
            servo_driver=mock_servo_driver,
            gpio_provider=mock_gpio,
            enable_hardware=False,
        )
        assert robot is not None
        assert robot.state == RobotState.INIT

    def test_init_creates_arm_kinematics(self, robot):
        """Verify arm kinematics is created."""
        assert robot.arm is not None
        assert robot.arm.l1 == 80.0
        assert robot.arm.l2 == 60.0

    def test_init_with_custom_arm_lengths(self, mock_servo_driver, mock_gpio):
        """Verify custom arm lengths are applied."""
        robot = Robot(
            servo_driver=mock_servo_driver,
            gpio_provider=mock_gpio,
            arm_l1_mm=100.0,
            arm_l2_mm=80.0,
            enable_hardware=False,
        )
        assert robot.arm.l1 == 100.0
        assert robot.arm.l2 == 80.0

    def test_init_rejects_invalid_hz(self, mock_servo_driver, mock_gpio):
        """Verify zero or negative hz is rejected."""
        with pytest.raises(ValueError, match="positive"):
            Robot(
                servo_driver=mock_servo_driver,
                gpio_provider=mock_gpio,
                control_loop_hz=0,
                enable_hardware=False,
            )

    def test_init_rejects_invalid_timeout(self, mock_servo_driver, mock_gpio):
        """Verify zero or negative timeout is rejected."""
        with pytest.raises(ValueError, match="positive"):
            Robot(
                servo_driver=mock_servo_driver,
                gpio_provider=mock_gpio,
                watchdog_timeout_ms=-1,
                enable_hardware=False,
            )

    def test_init_state_is_init(self, robot):
        """Verify initial state is INIT."""
        assert robot.state == RobotState.INIT

    def test_init_not_operational(self, robot):
        """Verify robot is not operational until started."""
        assert robot.is_operational is False


# =============================================================================
# Lifecycle Tests
# =============================================================================


class TestRobotLifecycle:
    """Tests for start/stop/reset lifecycle."""

    def test_start_returns_true(self, robot):
        """Verify start() returns True on success."""
        result = robot.start()
        assert result is True

    def test_start_transitions_to_ready(self, robot):
        """Verify start() transitions to READY state."""
        robot.start()
        assert robot.state == RobotState.READY

    def test_start_makes_operational(self, robot):
        """Verify start() makes robot operational."""
        robot.start()
        assert robot.is_operational is True

    def test_start_from_ready_raises(self, started_robot):
        """Verify start() raises in READY state."""
        with pytest.raises(RobotStateError):
            started_robot.start()

    def test_stop_from_ready(self, started_robot):
        """Verify stop() from READY state."""
        started_robot.stop()
        # State should be E_STOPPED after stop
        assert started_robot.state in (RobotState.E_STOPPED, RobotState.INIT)

    def test_stop_is_idempotent(self, started_robot):
        """Verify stop() can be called multiple times."""
        started_robot.stop()
        started_robot.stop()  # Should not raise

    def test_emergency_stop_returns_latency(self, started_robot):
        """Verify emergency_stop() returns latency."""
        latency = started_robot.emergency_stop("test")
        assert isinstance(latency, float)

    def test_emergency_stop_transitions_to_estopped(self, started_robot):
        """Verify emergency_stop() transitions to E_STOPPED."""
        started_robot.emergency_stop("test")
        assert started_robot.state == RobotState.E_STOPPED

    def test_emergency_stop_makes_not_operational(self, started_robot):
        """Verify emergency_stop() makes robot not operational."""
        started_robot.emergency_stop("test")
        assert started_robot.is_operational is False

    def test_reset_from_estopped(self, started_robot):
        """Verify reset() from E_STOPPED state."""
        started_robot.emergency_stop("test")
        result = started_robot.reset()
        assert result is True
        assert started_robot.state == RobotState.READY

    def test_reset_from_ready_raises(self, started_robot):
        """Verify reset() raises in READY state."""
        with pytest.raises(RobotStateError):
            started_robot.reset()


# =============================================================================
# Context Manager Tests
# =============================================================================


class TestRobotContextManager:
    """Tests for context manager protocol."""

    def test_context_manager_returns_robot(self, mock_servo_driver, mock_gpio):
        """Verify __enter__ returns robot instance."""
        with Robot(
            servo_driver=mock_servo_driver,
            gpio_provider=mock_gpio,
            enable_hardware=False,
        ) as robot:
            assert isinstance(robot, Robot)

    def test_context_manager_does_not_auto_start(self, mock_servo_driver, mock_gpio):
        """Verify __enter__ does not auto-start."""
        with Robot(
            servo_driver=mock_servo_driver,
            gpio_provider=mock_gpio,
            enable_hardware=False,
        ) as robot:
            assert robot.state == RobotState.INIT

    def test_context_manager_stops_on_exit(self, mock_servo_driver, mock_gpio):
        """Verify __exit__ stops robot."""
        with Robot(
            servo_driver=mock_servo_driver,
            gpio_provider=mock_gpio,
            enable_hardware=False,
        ) as robot:
            robot.start()
        # After exit, should not be operational
        assert not robot.is_operational

    def test_context_manager_stops_on_exception(self, mock_servo_driver, mock_gpio):
        """Verify __exit__ stops even on exception."""
        with pytest.raises(RuntimeError):
            with Robot(
                servo_driver=mock_servo_driver,
                gpio_provider=mock_gpio,
                enable_hardware=False,
            ) as robot:
                robot.start()
                raise RuntimeError("Test error")
        assert not robot.is_operational


# =============================================================================
# Control Loop Tests
# =============================================================================


class TestRobotControlLoop:
    """Tests for control loop operation."""

    def test_step_returns_true_when_ready(self, started_robot):
        """Verify step() returns True in READY state."""
        result = started_robot.step()
        assert result is True

    def test_step_returns_false_when_not_ready(self, robot):
        """Verify step() returns False in INIT state."""
        result = robot.step()
        assert result is False

    def test_control_loop_respects_max_iterations(self, started_robot):
        """Verify max_iterations is respected."""
        iterations = []

        def callback(r):
            iterations.append(1)

        started_robot.run_control_loop(
            iteration_callback=callback,
            max_iterations=5,
        )
        assert len(iterations) == 5

    def test_control_loop_calls_callback(self, started_robot):
        """Verify callback is called each iteration."""
        called = []

        def callback(r):
            called.append(r.state)

        started_robot.run_control_loop(
            iteration_callback=callback,
            max_iterations=3,
        )
        assert len(called) == 3
        assert all(s == RobotState.READY for s in called)

    def test_control_loop_callback_exception_triggers_estop(self, started_robot):
        """Verify callback exception triggers E-stop."""
        def bad_callback(r):
            raise ValueError("Test error")

        started_robot.run_control_loop(
            iteration_callback=bad_callback,
            max_iterations=10,
        )
        assert started_robot.state == RobotState.E_STOPPED

    def test_control_loop_requires_ready_state(self, robot):
        """Verify control loop raises in INIT state."""
        with pytest.raises(RobotStateError):
            robot.run_control_loop(max_iterations=1)


# =============================================================================
# Servo Command Tests
# =============================================================================


class TestRobotServoCommands:
    """Tests for servo command methods."""

    def test_set_servo_angle_in_ready(self, started_robot, mock_servo_driver):
        """Verify set_servo_angle() works in READY state."""
        result = started_robot.set_servo_angle(0, 90.0)
        assert result is True
        assert (0, 90.0) in mock_servo_driver.set_servo_angle_calls

    def test_set_servo_angle_in_init_raises(self, robot):
        """Verify set_servo_angle() raises in INIT state."""
        with pytest.raises(RobotStateError):
            robot.set_servo_angle(0, 90.0)

    def test_set_servo_angle_in_estopped_raises(self, started_robot):
        """Verify set_servo_angle() raises in E_STOPPED state."""
        started_robot.emergency_stop("test")
        with pytest.raises(RobotStateError):
            started_robot.set_servo_angle(0, 90.0)

    def test_set_arm_position_valid(self, started_robot, mock_servo_driver):
        """Verify set_arm_position() with reachable position."""
        # Position within arm reach (80 + 60 = 140mm max)
        result = started_robot.set_arm_position(100.0, 50.0)
        assert result is True
        # Should have set two servos
        assert len(mock_servo_driver.set_servo_angle_calls) >= 2

    def test_set_arm_position_unreachable(self, started_robot):
        """Verify set_arm_position() returns False for unreachable."""
        # Position outside reach
        result = started_robot.set_arm_position(200.0, 200.0)
        assert result is False


# =============================================================================
# Safety Integration Tests
# =============================================================================


class TestRobotSafetyIntegration:
    """Tests for safety system integration."""

    def test_stall_triggers_estop_via_feed(self, started_robot):
        """Verify stall condition triggers E-stop via feed_watchdog."""
        # Simulate stall
        started_robot._safety._current_limiter._channel_states[0].is_moving = True
        started_robot._safety._current_limiter._channel_states[0].stall_condition = (
            StallCondition.CONFIRMED
        )

        # Step should trigger E-stop via feed_watchdog
        result = started_robot.step()
        assert result is False
        assert started_robot.state == RobotState.E_STOPPED

    def test_imu_failure_is_nonfatal(self, started_robot, mock_imu):
        """Verify IMU failure doesn't trigger E-stop."""
        mock_imu.should_fail = True

        # Step should succeed despite IMU failure
        result = started_robot.step()
        assert result is True
        assert started_robot.state == RobotState.READY


# =============================================================================
# Diagnostics Tests
# =============================================================================


class TestRobotDiagnostics:
    """Tests for diagnostic methods."""

    def test_get_diagnostics_returns_dict(self, started_robot):
        """Verify get_diagnostics() returns dictionary."""
        diag = started_robot.get_diagnostics()
        assert isinstance(diag, dict)

    def test_get_diagnostics_includes_state(self, started_robot):
        """Verify diagnostics includes state."""
        diag = started_robot.get_diagnostics()
        assert "state" in diag
        assert diag["state"] == "READY"

    def test_get_diagnostics_includes_arm(self, started_robot):
        """Verify diagnostics includes arm info."""
        diag = started_robot.get_diagnostics()
        assert "arm" in diag
        assert "l1_mm" in diag["arm"]

    def test_get_diagnostics_includes_safety(self, started_robot):
        """Verify diagnostics includes safety info."""
        diag = started_robot.get_diagnostics()
        assert "safety" in diag


# =============================================================================
# Repr Test
# =============================================================================


class TestRobotRepr:
    """Tests for __repr__ method."""

    def test_repr_shows_state(self, robot):
        """Verify repr shows current state."""
        r = repr(robot)
        assert "INIT" in r

    def test_repr_shows_operational(self, started_robot):
        """Verify repr shows operational status."""
        r = repr(started_robot)
        assert "operational=True" in r
