#!/usr/bin/env python3
"""OpenDuck Mini V3 — Main Entry Point.

Boots the robot by loading config, creating all subsystem drivers,
wiring them into the Robot orchestrator, and running the control loop.

Usage (on Raspberry Pi):
    python3 main.py
    python3 main.py --config configs/robot_config.yaml
    python3 main.py --mock    # Run with mock hardware (for testing)

Shutdown:
    Ctrl+C or SIGTERM triggers graceful shutdown:
    1. HeadController emergency stop (cancel animations)
    2. STS3215 torque_disable_all (broadcast, <1ms)
    3. PCA9685 disable_all (16 channels zeroed)
    4. Safety systems stopped
    5. Clean exit

Subsystem Routing:
    PCA9685 (I2C, PWM) → Head servos (ch 0-3)
    STS3215 (UART, serial) → Arm/leg bus servos
    BNO085 (I2C) → IMU orientation
    INMP441 (I2S) → Microphone (not wired into main loop yet)
"""

import argparse
import logging
import signal
import sys
import threading
from pathlib import Path
from typing import Optional

from src.core.config_loader import ConfigLoader, ConfigError
from src.core.robot import Robot
from src.core.robot_state import RobotState

_logger = logging.getLogger("openduck")

# Sentinel for shutdown coordination
_shutdown_event = threading.Event()


def _setup_logging(verbose: bool = False) -> None:
    """Configure logging for console output."""
    level = logging.DEBUG if verbose else logging.INFO
    fmt = "%(asctime)s [%(levelname)-7s] %(name)s: %(message)s"
    datefmt = "%H:%M:%S"
    logging.basicConfig(level=level, format=fmt, datefmt=datefmt)


def _parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="OpenDuck Mini V3 — Robot Main Controller",
    )
    parser.add_argument(
        "--config",
        type=str,
        default=str(Path(__file__).parent / "configs" / "robot_config.yaml"),
        help="Path to robot_config.yaml (default: configs/robot_config.yaml)",
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Run with mock hardware (no real I2C/UART/GPIO)",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable debug logging",
    )
    return parser.parse_args()


def _create_pca9685(config: ConfigLoader, mock: bool) -> Optional[object]:
    """Create PCA9685 servo driver for head servos."""
    if mock:
        _logger.info("PCA9685: mock mode (no hardware)")
        return _MockServoDriver()

    try:
        from src.drivers.servo.pca9685 import PCA9685Driver
        driver = PCA9685Driver(
            address=config.pca9685_address,
            frequency=config.pca9685_frequency,
        )
        _logger.info(
            "PCA9685: initialized at 0x%02X, %dHz",
            config.pca9685_address,
            config.pca9685_frequency,
        )
        return driver
    except Exception as e:
        _logger.error("PCA9685: failed to initialize: %s", e)
        return None


def _create_sts3215(mock: bool) -> Optional[object]:
    """Create STS3215 bus servo driver for arm/leg servos."""
    if mock:
        _logger.info("STS3215: mock mode (no hardware)")
        return _MockBusServoDriver()

    try:
        from src.drivers.servo.sts3215 import STS3215Driver
        driver = STS3215Driver()
        _logger.info("STS3215: initialized on %s", driver._port if hasattr(driver, '_port') else "/dev/ttyUSB0")
        return driver
    except Exception as e:
        _logger.warning("STS3215: not available (arm/leg servos disabled): %s", e)
        return None


def _create_head_controller(servo_driver: object, config: ConfigLoader) -> Optional[object]:
    """Create HeadController from config."""
    try:
        from src.control.head_controller import HeadController, HeadConfig

        head_config = HeadConfig(**config.make_head_config())

        controller = HeadController(servo_driver, head_config)
        _logger.info(
            "HeadController: 4-DOF (ch %d,%d,%d,%d)",
            head_config.neck_pitch_channel,
            head_config.head_pitch_channel,
            head_config.head_yaw_channel,
            head_config.head_roll_channel,
        )
        return controller
    except Exception as e:
        _logger.error("HeadController: failed to create: %s", e)
        return None


def _create_imu(mock: bool) -> Optional[object]:
    """Create BNO085 IMU driver."""
    if mock:
        _logger.info("BNO085: mock mode (no hardware)")
        return None

    try:
        from src.drivers.sensor.imu.bno085 import BNO085Driver
        imu = BNO085Driver()
        _logger.info("BNO085: initialized at 0x4A")
        return imu
    except Exception as e:
        _logger.warning("BNO085: not available (IMU disabled): %s", e)
        return None


def _signal_handler(signum: int, frame) -> None:
    """Handle SIGINT/SIGTERM for graceful shutdown.

    Only sets the event — no logging here (not async-signal-safe).
    """
    _shutdown_event.set()


class _MockServoDriver:
    """Minimal mock PCA9685 for testing without hardware."""

    def set_servo_angle(self, channel: int, angle: float) -> None:
        _logger.debug("MockPCA9685: ch%d → %.1f°", channel, angle)

    def disable_all(self) -> None:
        _logger.debug("MockPCA9685: all channels disabled")

    def get_channel_state(self, channel: int) -> dict:
        return {"enabled": False, "angle": 0.0}


class _MockGPIOProvider:
    """Mock GPIO provider that prevents real GPIO access in mock mode."""

    BCM = 11
    IN = 1
    PUD_UP = 22
    FALLING = 32

    def setmode(self, mode): pass
    def setup(self, pin, direction, pull_up_down=None): pass
    def input(self, pin): return 1  # Not pressed
    def add_event_detect(self, pin, edge, callback=None, bouncetime=None): pass
    def remove_event_detect(self, pin): pass
    def cleanup(self, pin=None): pass


class _MockBusServoDriver:
    """Minimal mock STS3215 for testing without hardware."""

    def set_position(self, servo_id: int, degrees: float) -> bool:
        _logger.debug("MockSTS3215: id%d → %.1f°", servo_id, degrees)
        return True

    def torque_disable_all(self, servo_ids=None) -> None:
        _logger.debug("MockSTS3215: all torque disabled")

    def ping(self, servo_id: int) -> bool:
        return True

    def deinit(self) -> None:
        pass


def main() -> int:
    """Main entry point. Returns exit code."""
    args = _parse_args()
    _setup_logging(verbose=args.verbose)

    _logger.info("=" * 60)
    _logger.info("OpenDuck Mini V3 — Starting up")
    _logger.info("=" * 60)

    # Register signal handlers
    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)

    # Load config
    try:
        config = ConfigLoader.from_file(args.config)
        _logger.info("Config loaded: %s", config)
    except ConfigError as e:
        _logger.error("Config error: %s", e)
        return 1

    # Create drivers
    servo_driver = _create_pca9685(config, mock=args.mock)
    if servo_driver is None:
        _logger.error("Cannot start without PCA9685 servo driver")
        return 1

    bus_servo_driver = _create_sts3215(mock=args.mock)
    head_controller = _create_head_controller(servo_driver, config)
    imu = _create_imu(mock=args.mock)

    # Create Robot (C5 fix: pass mock GPIO provider in mock mode)
    robot = None
    try:
        robot = Robot(
            servo_driver=servo_driver,
            bus_servo_driver=bus_servo_driver,
            head_controller=head_controller,
            imu=imu,
            gpio_provider=_MockGPIOProvider() if args.mock else None,
            control_loop_hz=50,
            watchdog_timeout_ms=config.watchdog_timeout_ms,
            enable_hardware=not args.mock,
            bus_servo_ids=config.bus_servo_ids,
        )
        _logger.info("Robot created: %s", robot)

        # Start
        if not robot.start():
            _logger.error("Robot failed to start")
            return 1

        _logger.info("Robot is READY — entering control loop")
        _logger.info("Press Ctrl+C to shutdown gracefully")

        # Control loop with shutdown check
        class _ShutdownRequested(Exception):
            """Raised in callback to request clean shutdown."""

        def _loop_callback(r: Robot) -> None:
            if _shutdown_event.is_set():
                raise _ShutdownRequested()

        try:
            robot.run_control_loop(
                iteration_callback=_loop_callback,
                max_iterations=None,
            )
        except _ShutdownRequested:
            pass

    except KeyboardInterrupt:
        _logger.info("Shutdown signal received")
    finally:
        _logger.info("Shutting down...")
        if robot is not None:
            robot.stop()

        # Clean up bus servo driver
        if bus_servo_driver is not None and hasattr(bus_servo_driver, 'deinit'):
            try:
                bus_servo_driver.deinit()
            except Exception:
                pass

        _logger.info("=" * 60)
        _logger.info("OpenDuck Mini V3 — Shutdown complete")
        _logger.info("=" * 60)

    return 0


if __name__ == "__main__":
    sys.exit(main())
