"""End-to-End Integration Tests for Robot Orchestrator.

Tests the full path: ConfigLoader → Robot → HeadController → servos → shutdown.
Uses mock hardware (no real I2C/UART/GPIO) but validates the complete wiring
from config file to servo commands.

Coverage:
- Config → HeadConfig → HeadController creation
- Robot lifecycle: INIT → start() → READY → stop() → E_STOPPED
- Head commands: move_head, nod, shake via HeadController
- Bus servo commands: set_bus_servo_position via STS3215
- Emergency stop: all subsystems disabled
- Reset: HeadController + safety coordinator restored
- Diagnostics: includes head state + subsystem info
- Context manager: graceful cleanup
- Arm IK → bus servo routing (STS3215 path)
- Arm IK → PCA9685 fallback (legacy path)
"""

import time
from pathlib import Path
from unittest.mock import MagicMock, patch, call

import pytest

from src.core.config_loader import ConfigLoader
from src.core.robot import Robot
from src.core.robot_state import RobotState, RobotStateError
from src.control.head_controller import HeadController, HeadConfig, HeadLimits


# =============================================================================
# FIXTURES
# =============================================================================


def _load_config():
    """Load real robot_config.yaml."""
    config_path = Path(__file__).parent.parent.parent / "configs" / "robot_config.yaml"
    return ConfigLoader.from_file(str(config_path))


@pytest.fixture
def config():
    config_path = Path(__file__).parent.parent.parent / "configs" / "robot_config.yaml"
    if not config_path.exists():
        pytest.skip("robot_config.yaml not found")
    return ConfigLoader.from_file(str(config_path))


@pytest.fixture
def mock_pca9685():
    driver = MagicMock()
    driver.set_servo_angle = MagicMock()
    driver.disable_all = MagicMock()
    return driver


@pytest.fixture
def mock_sts3215():
    driver = MagicMock()
    driver.set_position = MagicMock(return_value=True)
    driver.torque_disable_all = MagicMock()
    driver.ping = MagicMock(return_value=True)
    driver.deinit = MagicMock()
    return driver


@pytest.fixture
def mock_safety():
    """Mock GPIO provider that allows SafetyCoordinator to start."""
    gpio = MagicMock()
    gpio.setup = MagicMock()
    gpio.input = MagicMock(return_value=1)  # E-stop not pressed
    gpio.add_event_detect = MagicMock()
    gpio.cleanup = MagicMock()
    return gpio


@pytest.fixture
def head_controller(mock_pca9685, config):
    """Create real HeadController with mock PCA9685."""
    head_limits = HeadLimits(**config.make_head_limits())
    head_cfg_kwargs = config.make_head_config()
    head_cfg_kwargs["limits"] = head_limits
    head_config = HeadConfig(**head_cfg_kwargs)
    return HeadController(mock_pca9685, head_config)


@pytest.fixture
def robot(mock_pca9685, mock_sts3215, head_controller, mock_safety):
    """Create fully wired Robot with mock hardware."""
    r = Robot(
        servo_driver=mock_pca9685,
        bus_servo_driver=mock_sts3215,
        head_controller=head_controller,
        gpio_provider=mock_safety,
        control_loop_hz=50,
        watchdog_timeout_ms=1000,
        enable_hardware=False,
        bus_servo_ids=[2, 3, 4, 5, 6, 7],
    )
    yield r
    r.stop()


# =============================================================================
# CONFIG → HEADCONTROLLER WIRING
# =============================================================================


class TestConfigToHeadController:
    """Verify config values flow through to HeadController."""

    def test_config_produces_valid_head_config(self, config):
        head_cfg_kwargs = config.make_head_config()
        head_limits = HeadLimits(**config.make_head_limits())
        head_cfg_kwargs["limits"] = head_limits
        hc = HeadConfig(**head_cfg_kwargs)
        assert hc.neck_pitch_channel == 0
        assert hc.head_pitch_channel == 1
        assert hc.head_yaw_channel == 2
        assert hc.head_roll_channel == 3

    def test_head_controller_uses_config_channels(self, mock_pca9685, config):
        head_limits = HeadLimits(**config.make_head_limits())
        head_cfg_kwargs = config.make_head_config()
        head_cfg_kwargs["limits"] = head_limits
        hc = HeadConfig(**head_cfg_kwargs)
        ctrl = HeadController(mock_pca9685, hc)

        # HeadController initializes servos to center (90°)
        calls = mock_pca9685.set_servo_angle.call_args_list
        channels_called = [c[0][0] for c in calls]
        assert 0 in channels_called  # neck_pitch
        assert 1 in channels_called  # head_pitch
        assert 2 in channels_called  # head_yaw
        assert 3 in channels_called  # head_roll

    def test_config_limits_match_yaml(self, config):
        lim = config.head_limits
        assert lim.neck_pitch_min == -20.0
        assert lim.neck_pitch_max == 65.0
        assert lim.head_yaw_min == -90.0
        assert lim.head_yaw_max == 90.0


# =============================================================================
# ROBOT LIFECYCLE
# =============================================================================


class TestRobotLifecycle:
    def test_init_state(self, robot):
        assert robot.state == RobotState.INIT

    def test_start_transitions_to_ready(self, robot):
        assert robot.start() is True
        assert robot.state == RobotState.READY
        robot.stop()

    def test_stop_transitions_to_estopped(self, robot):
        robot.start()
        robot.stop()
        assert robot.state == RobotState.E_STOPPED

    def test_context_manager_cleans_up(self, mock_pca9685, mock_sts3215, head_controller, mock_safety):
        with Robot(
            servo_driver=mock_pca9685,
            bus_servo_driver=mock_sts3215,
            head_controller=head_controller,
            gpio_provider=mock_safety,
            enable_hardware=False,
            bus_servo_ids=[2, 3],
        ) as r:
            r.start()
            assert r.state == RobotState.READY
        # After context exit, robot should be stopped
        assert r.state == RobotState.E_STOPPED

    def test_start_requires_servo_driver(self):
        r = Robot(servo_driver=None, enable_hardware=False)
        assert r.start() is False


# =============================================================================
# HEAD COMMANDS VIA ROBOT
# =============================================================================


class TestHeadCommandsE2E:
    def test_move_head_delegates_to_controller(self, robot, mock_pca9685):
        robot.start()
        mock_pca9685.set_servo_angle.reset_mock()

        result = robot.move_head(head_yaw=30.0)
        assert result is True

        # Give animation thread time to execute
        time.sleep(0.1)

        # PCA9685 should have been called with yaw channel (ch 2)
        calls = mock_pca9685.set_servo_angle.call_args_list
        channels = [c[0][0] for c in calls]
        assert 2 in channels  # head_yaw channel
        robot.stop()

    def test_nod_delegates_to_controller(self, robot, mock_pca9685):
        robot.start()
        mock_pca9685.set_servo_angle.reset_mock()

        result = robot.nod(count=1)
        assert result is True

        time.sleep(0.5)
        # Nod should have moved head_pitch (ch 1) and neck_pitch (ch 0)
        calls = mock_pca9685.set_servo_angle.call_args_list
        assert len(calls) > 0
        robot.stop()

    def test_shake_delegates_to_controller(self, robot, mock_pca9685):
        robot.start()
        mock_pca9685.set_servo_angle.reset_mock()

        result = robot.shake(count=1)
        assert result is True

        time.sleep(0.5)
        calls = mock_pca9685.set_servo_angle.call_args_list
        assert len(calls) > 0
        robot.stop()

    def test_move_head_without_controller(self, mock_pca9685, mock_safety):
        r = Robot(
            servo_driver=mock_pca9685,
            head_controller=None,
            gpio_provider=mock_safety,
            enable_hardware=False,
        )
        r.start()
        assert r.move_head(head_yaw=30) is False
        r.stop()

    def test_head_commands_blocked_when_not_ready(self, robot):
        with pytest.raises(RobotStateError):
            robot.move_head(head_yaw=30)


# =============================================================================
# BUS SERVO COMMANDS (STS3215)
# =============================================================================


class TestBusServoE2E:
    def test_set_bus_servo_position(self, robot, mock_sts3215):
        robot.start()
        result = robot.set_bus_servo_position(servo_id=2, degrees=180.0)
        assert result is True
        mock_sts3215.set_position.assert_called_once_with(2, 180.0)
        robot.stop()

    def test_bus_servo_without_driver(self, mock_pca9685, mock_safety):
        r = Robot(
            servo_driver=mock_pca9685,
            bus_servo_driver=None,
            gpio_provider=mock_safety,
            enable_hardware=False,
        )
        r.start()
        assert r.set_bus_servo_position(5, 90.0) is False
        r.stop()

    def test_bus_servo_blocked_when_not_ready(self, robot):
        with pytest.raises(RobotStateError):
            robot.set_bus_servo_position(2, 90.0)


# =============================================================================
# ARM IK → SERVO ROUTING
# =============================================================================


class TestArmRoutingE2E:
    def test_arm_routes_to_sts3215_when_ids_provided(self, robot, mock_sts3215):
        robot.start()
        # Position within reach of default arm (l1=80, l2=60)
        result = robot.set_arm_position(x=50.0, y=50.0, shoulder_id=2, elbow_id=3)
        assert result is True
        # Should have called STS3215, NOT PCA9685
        assert mock_sts3215.set_position.call_count == 2  # shoulder + elbow via set_bus_servo_position
        robot.stop()

    def test_arm_falls_back_to_pca9685_without_ids(self, robot, mock_pca9685):
        robot.start()
        mock_pca9685.set_servo_angle.reset_mock()
        result = robot.set_arm_position(x=50.0, y=50.0)
        assert result is True
        # Should have called PCA9685 channels 0,1 (legacy fallback)
        calls = mock_pca9685.set_servo_angle.call_args_list
        channels = [c[0][0] for c in calls]
        assert 0 in channels
        assert 1 in channels
        robot.stop()

    def test_arm_unreachable_position(self, robot):
        robot.start()
        result = robot.set_arm_position(x=999.0, y=999.0)
        assert result is False
        robot.stop()


# =============================================================================
# EMERGENCY STOP E2E
# =============================================================================


class TestEmergencyStopE2E:
    def test_estop_disables_all_subsystems(self, robot, mock_sts3215):
        robot.start()
        assert robot.state == RobotState.READY

        latency = robot.emergency_stop(source="test")

        assert robot.state == RobotState.E_STOPPED
        # STS3215 torque_disable_all should have been called (may be >1 due to callback chain)
        assert mock_sts3215.torque_disable_all.call_count >= 1
        robot.stop()

    def test_estop_stops_head_animations(self, robot, mock_pca9685):
        robot.start()
        robot.move_head(head_yaw=45.0)
        time.sleep(0.05)

        robot.emergency_stop(source="test")

        # Head controller should be in emergency state
        assert robot.head_controller._emergency_stopped.is_set()
        robot.stop()

    def test_reset_after_estop(self, robot):
        robot.start()
        robot.emergency_stop(source="test")
        assert robot.state == RobotState.E_STOPPED

        result = robot.reset()
        assert result is True
        assert robot.state == RobotState.READY
        robot.stop()


# =============================================================================
# DIAGNOSTICS
# =============================================================================


class TestDiagnosticsE2E:
    def test_diagnostics_include_subsystems(self, robot):
        robot.start()
        diag = robot.get_diagnostics()

        assert diag["state"] == "READY"
        assert diag["subsystems"]["head_controller"] is True
        assert diag["subsystems"]["bus_servo_driver"] is True
        assert diag["subsystems"]["bus_servo_ids"] == [2, 3, 4, 5, 6, 7]
        robot.stop()

    def test_diagnostics_include_head_state(self, robot):
        robot.start()
        diag = robot.get_diagnostics()

        assert "head" in diag
        assert "head_yaw" in diag["head"]
        assert "is_moving" in diag["head"]
        assert diag["head"]["head_yaw"] == 0.0  # Center position
        robot.stop()


# =============================================================================
# CONTROL LOOP
# =============================================================================


class TestControlLoopE2E:
    def test_control_loop_runs_n_iterations(self, robot):
        robot.start()
        robot.run_control_loop(max_iterations=5)
        assert robot._iteration_count == 5
        robot.stop()

    def test_control_loop_callback_receives_robot(self, robot):
        robot.start()
        received = []

        def cb(r):
            received.append(r.state)

        robot.run_control_loop(iteration_callback=cb, max_iterations=3)
        assert len(received) == 3
        assert all(s == RobotState.READY for s in received)
        robot.stop()

    def test_control_loop_stops_on_estop(self, robot):
        robot.start()
        call_count = [0]

        def cb(r):
            call_count[0] += 1
            if call_count[0] >= 3:
                r.emergency_stop(source="test_callback")

        robot.run_control_loop(iteration_callback=cb, max_iterations=100)
        assert call_count[0] == 3
        assert robot.state == RobotState.E_STOPPED
        robot.stop()


# =============================================================================
# FULL E2E SCENARIO
# =============================================================================


class TestFullE2EScenario:
    """Simulate a realistic robot session: boot → move → nod → e-stop → reset → shutdown."""

    def test_complete_session(self, config, mock_pca9685, mock_sts3215, mock_safety):
        # 1. Create HeadController from config
        head_limits = HeadLimits(**config.make_head_limits())
        head_cfg_kwargs = config.make_head_config()
        head_cfg_kwargs["limits"] = head_limits
        head_config = HeadConfig(**head_cfg_kwargs)
        head_ctrl = HeadController(mock_pca9685, head_config)

        # 2. Create Robot with all subsystems
        with Robot(
            servo_driver=mock_pca9685,
            bus_servo_driver=mock_sts3215,
            head_controller=head_ctrl,
            gpio_provider=mock_safety,
            enable_hardware=False,
            bus_servo_ids=[2, 3, 4, 5],
        ) as robot:
            # 3. Boot
            assert robot.start() is True
            assert robot.state == RobotState.READY

            # 4. Move head
            assert robot.move_head(head_yaw=20, head_pitch=10) is True
            time.sleep(0.1)

            # 5. Nod
            assert robot.nod(count=1) is True
            time.sleep(0.3)

            # 6. Move bus servo (arm)
            assert robot.set_bus_servo_position(2, 90.0) is True

            # 7. Emergency stop
            robot.emergency_stop(source="e2e_test")
            assert robot.state == RobotState.E_STOPPED
            mock_sts3215.torque_disable_all.assert_called()

            # 8. Reset
            assert robot.reset() is True
            assert robot.state == RobotState.READY

            # 9. Run short control loop
            robot.run_control_loop(max_iterations=5)

        # 10. Context manager called stop
        assert robot.state == RobotState.E_STOPPED

    def test_config_to_servo_channel_integrity(self, config, mock_pca9685, mock_safety):
        """Verify config channels (0,1,2,3) reach actual PCA9685 calls."""
        head_limits = HeadLimits(**config.make_head_limits())
        head_cfg_kwargs = config.make_head_config()
        head_cfg_kwargs["limits"] = head_limits
        head_config = HeadConfig(**head_cfg_kwargs)
        head_ctrl = HeadController(mock_pca9685, head_config)

        with Robot(
            servo_driver=mock_pca9685,
            head_controller=head_ctrl,
            gpio_provider=mock_safety,
            enable_hardware=False,
        ) as robot:
            robot.start()
            mock_pca9685.set_servo_angle.reset_mock()

            # Move all 4 DOF
            robot.move_head(neck_pitch=10, head_pitch=5, head_yaw=15, head_roll=3)
            time.sleep(0.15)

            # All 4 channels should appear in PCA9685 calls
            all_channels = {c[0][0] for c in mock_pca9685.set_servo_angle.call_args_list}
            assert 0 in all_channels, "neck_pitch (ch 0) not called"
            assert 1 in all_channels, "head_pitch (ch 1) not called"
            assert 2 in all_channels, "head_yaw (ch 2) not called"
            assert 3 in all_channels, "head_roll (ch 3) not called"


# =============================================================================
# NEGATIVE / ERROR PATH TESTS
# =============================================================================


class TestNegativePaths:
    """Hostile review H4: missing negative tests."""

    def test_bus_servo_returns_false(self, robot, mock_sts3215):
        """STS3215 set_position returning False should propagate."""
        robot.start()
        mock_sts3215.set_position.return_value = False
        result = robot.set_bus_servo_position(2, 90.0)
        assert result is False
        robot.stop()

    def test_bus_servo_exception_triggers_estop(self, robot, mock_sts3215):
        """STS3215 raising should trigger e-stop."""
        robot.start()
        mock_sts3215.set_position.side_effect = IOError("UART timeout")
        with pytest.raises(Exception):
            robot.set_bus_servo_position(2, 90.0)
        assert robot.state == RobotState.E_STOPPED
        robot.stop()

    def test_torque_disable_all_exception_during_estop(self, robot, mock_sts3215):
        """torque_disable_all throwing during e-stop should not prevent state transition."""
        robot.start()
        mock_sts3215.torque_disable_all.side_effect = IOError("bus error")
        latency = robot.emergency_stop(source="test")
        # Should still transition to E_STOPPED despite bus error
        assert robot.state == RobotState.E_STOPPED

    def test_head_controller_reset_failure_blocks_ready(
        self, mock_pca9685, mock_safety, config
    ):
        """HeadController.reset_emergency() failure should keep robot E_STOPPED."""
        head_limits = HeadLimits(**config.make_head_limits())
        head_cfg_kwargs = config.make_head_config()
        head_cfg_kwargs["limits"] = head_limits
        head_config = HeadConfig(**head_cfg_kwargs)
        head_ctrl = HeadController(mock_pca9685, head_config)

        r = Robot(
            servo_driver=mock_pca9685,
            head_controller=head_ctrl,
            gpio_provider=mock_safety,
            enable_hardware=False,
        )
        r.start()
        r.emergency_stop(source="test")
        assert r.state == RobotState.E_STOPPED

        # Make reset_emergency raise
        head_ctrl.reset_emergency = MagicMock(side_effect=RuntimeError("stuck"))
        result = r.reset()
        assert result is False
        assert r.state == RobotState.E_STOPPED
        r.stop()

    def test_move_head_uses_duration_ms_not_speed_ms(
        self, mock_pca9685, mock_safety, config
    ):
        """Verify move_head passes duration_ms (not speed_ms) to HeadController."""
        head_limits = HeadLimits(**config.make_head_limits())
        head_cfg_kwargs = config.make_head_config()
        head_cfg_kwargs["limits"] = head_limits
        head_config = HeadConfig(**head_cfg_kwargs)
        head_ctrl = HeadController(mock_pca9685, head_config)
        head_ctrl.move_to = MagicMock(return_value=True)

        r = Robot(
            servo_driver=mock_pca9685,
            head_controller=head_ctrl,
            gpio_provider=mock_safety,
            enable_hardware=False,
        )
        r.start()
        r.move_head(head_yaw=30, duration_ms=500)

        head_ctrl.move_to.assert_called_once_with(head_yaw=30, duration_ms=500)
        r.stop()


# =============================================================================
# GPIO / EXTERNAL E-STOP PROPAGATION (C1 safety fix)
# =============================================================================


class TestExternalEstopPropagation:
    """Verify GPIO/watchdog e-stop disables bus servos and HeadController."""

    def test_external_estop_disables_bus_servos(
        self, mock_pca9685, mock_sts3215, head_controller, mock_safety
    ):
        """When SafetyCoordinator's EmergencyStop fires, bus servos get disabled."""
        r = Robot(
            servo_driver=mock_pca9685,
            bus_servo_driver=mock_sts3215,
            head_controller=head_controller,
            gpio_provider=mock_safety,
            enable_hardware=False,
            bus_servo_ids=[2, 3, 4, 5],
        )
        r.start()
        assert r.state == RobotState.READY

        # Simulate GPIO/watchdog e-stop by calling the external callback
        r._on_external_estop("gpio")

        assert r.state == RobotState.E_STOPPED
        mock_sts3215.torque_disable_all.assert_called_with([2, 3, 4, 5])
        r.stop()

    def test_external_estop_stops_head_controller(
        self, mock_pca9685, mock_sts3215, head_controller, mock_safety
    ):
        """External e-stop should stop HeadController animations."""
        r = Robot(
            servo_driver=mock_pca9685,
            bus_servo_driver=mock_sts3215,
            head_controller=head_controller,
            gpio_provider=mock_safety,
            enable_hardware=False,
        )
        r.start()
        r._on_external_estop("watchdog")

        assert head_controller._emergency_stopped.is_set()
        r.stop()

    def test_safety_coordinator_registers_callback(
        self, mock_pca9685, mock_sts3215, head_controller, mock_safety
    ):
        """Robot.start() should register an e-stop callback on SafetyCoordinator."""
        r = Robot(
            servo_driver=mock_pca9685,
            bus_servo_driver=mock_sts3215,
            head_controller=head_controller,
            gpio_provider=mock_safety,
            enable_hardware=False,
        )
        r.start()

        # The safety coordinator should have a registered callback
        assert r._safety._external_estop_callback is not None
        r.stop()

    def test_external_estop_idempotent_with_manual_estop(
        self, mock_pca9685, mock_sts3215, head_controller, mock_safety
    ):
        """External e-stop followed by manual e-stop shouldn't crash."""
        r = Robot(
            servo_driver=mock_pca9685,
            bus_servo_driver=mock_sts3215,
            head_controller=head_controller,
            gpio_provider=mock_safety,
            enable_hardware=False,
            bus_servo_ids=[2, 3],
        )
        r.start()
        r._on_external_estop("gpio")
        # Second e-stop should be safe
        r.emergency_stop(source="manual_after_gpio")
        assert r.state == RobotState.E_STOPPED
        r.stop()
