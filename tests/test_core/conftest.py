"""Pytest fixtures for core robot tests.

Provides mock fixtures for testing the Robot orchestrator
without requiring actual hardware.
"""

import threading
import time
from typing import List
from unittest.mock import Mock, MagicMock

import pytest


class MockGPIO:
    """Mock RPi.GPIO for testing."""

    BCM: int = 11
    IN: int = 1
    PUD_UP: int = 22
    FALLING: int = 32

    def __init__(self):
        self.callbacks = {}
        self.pin_states = {}

    def setmode(self, mode: int) -> None:
        pass

    def setup(self, pin: int, direction: int, pull_up_down: int = 0) -> None:
        self.pin_states[pin] = 1  # Default HIGH

    def input(self, pin: int) -> int:
        return self.pin_states.get(pin, 1)

    def add_event_detect(self, pin: int, edge: int, callback=None, bouncetime: int = 0) -> None:
        if callback:
            self.callbacks[pin] = callback

    def remove_event_detect(self, pin: int) -> None:
        self.callbacks.pop(pin, None)

    def cleanup(self, pin: int = None) -> None:
        if pin:
            self.callbacks.pop(pin, None)
        else:
            self.callbacks.clear()

    def simulate_button_press(self, pin: int) -> None:
        self.pin_states[pin] = 0
        if pin in self.callbacks:
            self.callbacks[pin](pin)


class MockServoDriver:
    """Mock PCA9685 servo driver for testing."""

    def __init__(self):
        self.disable_all_calls = 0
        self.set_servo_angle_calls: List[tuple] = []
        self.channel_states = {i: {'angle': 90.0} for i in range(16)}
        self._lock = threading.Lock()

    def disable_all(self) -> None:
        with self._lock:
            self.disable_all_calls += 1
            for ch in self.channel_states:
                self.channel_states[ch]['angle'] = None

    def set_servo_angle(self, channel: int, angle: float) -> None:
        with self._lock:
            self.set_servo_angle_calls.append((channel, angle))
            self.channel_states[channel]['angle'] = angle

    def get_channel_state(self, channel: int) -> dict:
        with self._lock:
            return self.channel_states.get(channel, {'angle': 90.0})


class MockIMU:
    """Mock BNO085 IMU for testing."""

    def __init__(self):
        self.read_orientation_calls = 0
        self.should_fail = False

    def read_orientation(self):
        self.read_orientation_calls += 1
        if self.should_fail:
            raise RuntimeError("IMU read error")
        return Mock(heading=0.0, roll=0.0, pitch=0.0)


@pytest.fixture
def mock_gpio():
    """Provide mock GPIO for testing."""
    gpio = MockGPIO()
    yield gpio


@pytest.fixture
def mock_servo_driver():
    """Provide mock servo driver for testing."""
    driver = MockServoDriver()
    yield driver


@pytest.fixture
def mock_imu():
    """Provide mock IMU for testing."""
    imu = MockIMU()
    yield imu


@pytest.fixture
def robot(mock_servo_driver, mock_gpio, mock_imu):
    """Robot with mocked hardware.

    Uses very long watchdog timeout (60 seconds) since tests don't
    feed the watchdog continuously like real control loops.
    """
    from src.core.robot import Robot

    r = Robot(
        servo_driver=mock_servo_driver,
        imu=mock_imu,
        gpio_provider=mock_gpio,
        enable_hardware=False,
        control_loop_hz=50,
        watchdog_timeout_ms=60000,  # 60 second timeout for tests
    )
    yield r
    try:
        r.stop()
    except Exception:
        pass


@pytest.fixture
def started_robot(robot):
    """Robot in READY state."""
    robot.start()
    return robot
