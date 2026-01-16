"""Pytest fixtures for safety module tests.

This module provides mock fixtures for testing safety systems without
requiring actual hardware. Includes mocks for:
- RPi.GPIO (mock_gpio)
- ServoDriver (mock_servo_driver)
- PCA9685 hardware (mock_hardware)
- GPIO trigger simulator (gpio_trigger_simulator)
"""

import threading
import time
from typing import Callable, Optional, List, Any
from unittest.mock import Mock, MagicMock, patch

import pytest


class MockGPIO:
    """Mock RPi.GPIO module for testing without hardware.

    Provides all necessary GPIO constants and methods used by EmergencyStop.
    Tracks all method calls for verification in tests.

    Attributes:
        BCM: BCM pin numbering mode constant
        IN: Input direction constant
        PUD_UP: Pull-up resistor constant
        FALLING: Falling edge detection constant
        callbacks: Dictionary mapping pins to registered callbacks
        pin_states: Dictionary mapping pins to current state values
        setmode_calls: List of mode arguments passed to setmode()
        setup_calls: List of (pin, direction, pull_up_down) tuples
    """

    BCM: int = 11
    BOARD: int = 10
    IN: int = 1
    OUT: int = 0
    PUD_UP: int = 22
    PUD_DOWN: int = 21
    PUD_OFF: int = 20
    RISING: int = 31
    FALLING: int = 32
    BOTH: int = 33

    def __init__(self) -> None:
        """Initialize mock GPIO with default states."""
        self.callbacks: dict[int, Callable] = {}
        self.pin_states: dict[int, int] = {}
        self.setmode_calls: List[int] = []
        self.setup_calls: List[tuple] = []
        self.add_event_detect_calls: List[tuple] = []
        self.remove_event_detect_calls: List[int] = []
        self.cleanup_calls: List[Optional[int]] = []
        self._mode: Optional[int] = None

    def reset(self) -> None:
        """Reset all tracked calls and states."""
        self.callbacks.clear()
        self.pin_states.clear()
        self.setmode_calls.clear()
        self.setup_calls.clear()
        self.add_event_detect_calls.clear()
        self.remove_event_detect_calls.clear()
        self.cleanup_calls.clear()
        self._mode = None

    def setmode(self, mode: int) -> None:
        """Set GPIO pin numbering mode."""
        self.setmode_calls.append(mode)
        self._mode = mode

    def setup(self, pin: int, direction: int, pull_up_down: int = PUD_OFF) -> None:
        """Configure a GPIO pin."""
        self.setup_calls.append((pin, direction, pull_up_down))
        # Default state: HIGH (pull-up, button not pressed)
        if pin not in self.pin_states:
            self.pin_states[pin] = 1

    def input(self, pin: int) -> int:
        """Read GPIO pin state."""
        return self.pin_states.get(pin, 1)

    def add_event_detect(
        self,
        pin: int,
        edge: int,
        callback: Optional[Callable] = None,
        bouncetime: int = 0
    ) -> None:
        """Add edge detection callback."""
        self.add_event_detect_calls.append((pin, edge, callback, bouncetime))
        if callback is not None:
            self.callbacks[pin] = callback

    def remove_event_detect(self, pin: int) -> None:
        """Remove edge detection callback."""
        self.remove_event_detect_calls.append(pin)
        self.callbacks.pop(pin, None)

    def cleanup(self, pin: Optional[int] = None) -> None:
        """Clean up GPIO resources."""
        self.cleanup_calls.append(pin)
        if pin is not None:
            self.callbacks.pop(pin, None)
            self.pin_states.pop(pin, None)
        else:
            self.callbacks.clear()
            self.pin_states.clear()

    def simulate_button_press(self, pin: int) -> None:
        """Simulate a button press (falling edge) on a pin.

        Sets pin state to LOW and triggers callback if registered.

        Args:
            pin: GPIO pin number to simulate press on.
        """
        self.pin_states[pin] = 0
        if pin in self.callbacks:
            self.callbacks[pin](pin)

    def simulate_button_release(self, pin: int) -> None:
        """Simulate a button release (rising edge) on a pin.

        Sets pin state to HIGH.

        Args:
            pin: GPIO pin number to simulate release on.
        """
        self.pin_states[pin] = 1


class MockServoDriver:
    """Mock servo driver implementing ServoDriverProtocol.

    Tracks disable_all() calls for verification in tests.
    Can be configured to raise exceptions or add latency.

    Attributes:
        disable_all_calls: Number of times disable_all() was called
        disable_all_timestamps: List of timestamps when disable_all() was called
        raise_on_disable: If True, disable_all() raises RuntimeError
        disable_latency_ms: Artificial latency to add to disable_all()
    """

    def __init__(self) -> None:
        """Initialize mock servo driver."""
        self.disable_all_calls: int = 0
        self.disable_all_timestamps: List[float] = []
        self.raise_on_disable: bool = False
        self.disable_latency_ms: float = 0.0
        self._lock = threading.Lock()

    def reset(self) -> None:
        """Reset call tracking."""
        with self._lock:
            self.disable_all_calls = 0
            self.disable_all_timestamps.clear()
            self.raise_on_disable = False
            self.disable_latency_ms = 0.0

    def disable_all(self) -> None:
        """Disable all servo channels (mock implementation).

        Raises:
            RuntimeError: If raise_on_disable is True.
        """
        with self._lock:
            self.disable_all_timestamps.append(time.perf_counter())
            self.disable_all_calls += 1

            if self.disable_latency_ms > 0:
                time.sleep(self.disable_latency_ms / 1000.0)

            if self.raise_on_disable:
                raise RuntimeError("Simulated servo driver error")


class GPIOTriggerSimulator:
    """Utility class for simulating GPIO button triggers in tests.

    Provides methods to simulate button presses with timing control,
    useful for testing debounce behavior and rapid triggers.

    Attributes:
        gpio: Reference to MockGPIO instance
        pin: GPIO pin to simulate triggers on
    """

    def __init__(self, gpio: MockGPIO, pin: int = 26) -> None:
        """Initialize trigger simulator.

        Args:
            gpio: MockGPIO instance to use for simulation.
            pin: GPIO pin number to simulate on.
        """
        self.gpio = gpio
        self.pin = pin

    def trigger(self) -> None:
        """Simulate a single button press."""
        self.gpio.simulate_button_press(self.pin)

    def trigger_rapid(self, count: int, interval_ms: float = 10.0) -> None:
        """Simulate rapid button presses.

        Args:
            count: Number of button presses to simulate.
            interval_ms: Interval between presses in milliseconds.
        """
        for _ in range(count):
            self.gpio.simulate_button_press(self.pin)
            time.sleep(interval_ms / 1000.0)
            self.gpio.simulate_button_release(self.pin)

    def trigger_async(self, delay_ms: float = 0.0) -> threading.Thread:
        """Trigger button press asynchronously.

        Args:
            delay_ms: Delay before trigger in milliseconds.

        Returns:
            Thread object that will trigger the button.
        """
        def _delayed_trigger():
            if delay_ms > 0:
                time.sleep(delay_ms / 1000.0)
            self.trigger()

        thread = threading.Thread(target=_delayed_trigger, daemon=True)
        thread.start()
        return thread


@pytest.fixture
def mock_gpio() -> MockGPIO:
    """Provide mock RPi.GPIO for testing.

    Creates a fresh MockGPIO instance for each test.

    Yields:
        MockGPIO instance ready for use.
    """
    gpio = MockGPIO()
    yield gpio
    gpio.reset()


@pytest.fixture
def mock_servo_driver() -> MockServoDriver:
    """Provide mock servo driver for testing.

    Creates a fresh MockServoDriver instance for each test.

    Yields:
        MockServoDriver instance ready for use.
    """
    driver = MockServoDriver()
    yield driver
    driver.reset()


@pytest.fixture
def mock_hardware():
    """Mock hardware dependencies for PCA9685 testing.

    Patches board, busio, and PCA9685 modules to allow testing
    without actual hardware present.

    Yields:
        Dictionary containing mock objects:
        - board: Mock board module
        - busio: Mock busio module
        - pca9685_class: Mock PCA9685 class
        - pca: Mock PCA9685 instance
        - i2c: Mock I2C bus
    """
    with patch('src.drivers.servo.pca9685.board') as mock_board, \
         patch('src.drivers.servo.pca9685.busio') as mock_busio, \
         patch('src.drivers.servo.pca9685.PCA9685') as mock_pca9685_class, \
         patch('src.drivers.i2c_bus_manager.board') as mock_mgr_board, \
         patch('src.drivers.i2c_bus_manager.busio') as mock_mgr_busio:

        # Configure mocks
        mock_board.SCL = Mock()
        mock_board.SDA = Mock()
        mock_mgr_board.SCL = Mock()
        mock_mgr_board.SDA = Mock()

        mock_i2c = Mock()
        mock_busio.I2C.return_value = mock_i2c
        mock_mgr_busio.I2C.return_value = mock_i2c

        mock_pca = MagicMock()
        mock_pca9685_class.return_value = mock_pca

        # Mock channels
        mock_pca.channels = {i: Mock(duty_cycle=0) for i in range(16)}

        # Mock hardware sleep method
        mock_pca.sleep = Mock()

        # Reset I2C Bus Manager before each test
        try:
            from src.drivers.i2c_bus_manager import I2CBusManager
            I2CBusManager.reset()
        except ImportError:
            pass

        yield {
            'board': mock_board,
            'busio': mock_busio,
            'pca9685_class': mock_pca9685_class,
            'pca': mock_pca,
            'i2c': mock_i2c
        }

        # Cleanup
        try:
            from src.drivers.i2c_bus_manager import I2CBusManager
            I2CBusManager.reset()
        except ImportError:
            pass


@pytest.fixture
def gpio_trigger_simulator(mock_gpio: MockGPIO) -> GPIOTriggerSimulator:
    """Provide GPIO trigger simulator for testing.

    Creates a trigger simulator linked to the mock_gpio fixture.

    Args:
        mock_gpio: MockGPIO fixture instance.

    Yields:
        GPIOTriggerSimulator instance ready for use.
    """
    return GPIOTriggerSimulator(mock_gpio, pin=26)


@pytest.fixture
def emergency_stop_factory(mock_gpio: MockGPIO, mock_servo_driver: MockServoDriver):
    """Factory fixture for creating EmergencyStop instances.

    Returns a factory function that creates EmergencyStop instances
    with pre-configured mocks.

    Args:
        mock_gpio: MockGPIO fixture instance.
        mock_servo_driver: MockServoDriver fixture instance.

    Yields:
        Factory function that accepts optional kwargs and returns EmergencyStop.
    """
    from src.safety.emergency_stop import EmergencyStop

    instances: List[EmergencyStop] = []

    def _factory(**kwargs):
        defaults = {
            'servo_driver': mock_servo_driver,
            'gpio_provider': mock_gpio,
            'gpio_pin': 26,
            'debounce_ms': 50,
            'auto_reset': False,
        }
        defaults.update(kwargs)
        instance = EmergencyStop(**defaults)
        instances.append(instance)
        return instance

    yield _factory

    # Cleanup all created instances
    for instance in instances:
        try:
            instance.cleanup()
        except Exception:
            pass
