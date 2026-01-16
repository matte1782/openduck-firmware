"""Emergency Stop System for OpenDuck Mini V3.

This module provides a safety-critical emergency stop system that monitors
a physical GPIO button and can disable all servo outputs within <5ms latency.

Hardware Configuration:
    - GPIO 26 (Physical pin 37) - Emergency stop button
    - Active LOW (button press = LOW signal)
    - Internal pull-up resistor enabled
    - 50ms debounce time (configurable)

Safety Features:
    - Thread-safe state machine with proper transitions
    - <5ms latency target for servo disable
    - Callback registration for state change notifications
    - Integration with PCA9685Driver.disable_all()
    - Mock-friendly design for testing

State Machine:
    INIT -> RUNNING: start() called
    RUNNING -> E_STOP: trigger() called or GPIO interrupt
    E_STOP -> RESET_REQUIRED: always (auto-transition)
    RESET_REQUIRED -> RUNNING: reset() called (if auto_reset=True)
    RESET_REQUIRED -> INIT: reset() with restart required

Example Usage:
    >>> from src.drivers.servo.pca9685 import PCA9685Driver
    >>> from src.safety.emergency_stop import EmergencyStop, SafetyState
    >>>
    >>> # Initialize with servo driver
    >>> servo_driver = PCA9685Driver()
    >>> e_stop = EmergencyStop(servo_driver, gpio_pin=26)
    >>>
    >>> # Register callback for state changes
    >>> e_stop.register_callback(lambda old, new, src: print(f"{old} -> {new}"))
    >>>
    >>> # Start monitoring
    >>> e_stop.start()
    >>> assert e_stop.state == SafetyState.RUNNING
    >>>
    >>> # Manual trigger (or wait for GPIO interrupt)
    >>> latency = e_stop.trigger(source="manual")
    >>> print(f"Shutdown latency: {latency:.2f}ms")
"""

import time
import logging
import threading
from enum import Enum, auto
from typing import Optional, Callable, List, Any, Protocol
from dataclasses import dataclass

# Module logger for safety-critical logging
_logger = logging.getLogger(__name__)


class SafetyState(Enum):
    """Safety system state enumeration.

    States:
        INIT: System initialized but not started. Servos should be disabled.
        RUNNING: Normal operation. Servos enabled, monitoring active.
        E_STOP: Emergency stop triggered. All servos disabled immediately.
        RESET_REQUIRED: E-stop acknowledged, manual reset required to continue.
    """
    INIT = auto()
    RUNNING = auto()
    E_STOP = auto()
    RESET_REQUIRED = auto()


class GPIOProvider(Protocol):
    """Protocol for GPIO operations (allows dependency injection for testing).

    This protocol defines the interface for GPIO operations, allowing
    the EmergencyStop class to work with either real RPi.GPIO or mock
    implementations for testing.
    """

    BCM: int
    IN: int
    PUD_UP: int
    FALLING: int

    def setmode(self, mode: int) -> None:
        """Set GPIO pin numbering mode."""
        ...

    def setup(self, pin: int, direction: int, pull_up_down: int) -> None:
        """Configure a GPIO pin."""
        ...

    def input(self, pin: int) -> int:
        """Read GPIO pin state."""
        ...

    def add_event_detect(
        self,
        pin: int,
        edge: int,
        callback: Callable,
        bouncetime: int
    ) -> None:
        """Add edge detection callback."""
        ...

    def remove_event_detect(self, pin: int) -> None:
        """Remove edge detection callback."""
        ...

    def cleanup(self, pin: Optional[int] = None) -> None:
        """Clean up GPIO resources."""
        ...


class ServoDriverProtocol(Protocol):
    """Protocol for servo driver operations.

    Defines the minimal interface required from a servo driver for
    emergency stop functionality.
    """

    def disable_all(self) -> None:
        """Disable all servo channels immediately (emergency stop)."""
        ...


@dataclass
class EmergencyStopEvent:
    """Event data for emergency stop triggers.

    Attributes:
        timestamp: Unix timestamp when event occurred
        source: Source of the trigger (e.g., "gpio", "manual", "software")
        latency_ms: Time from trigger to servo disable completion
        previous_state: State before the trigger
    """
    timestamp: float
    source: str
    latency_ms: float
    previous_state: SafetyState


# Type alias for state change callbacks
StateChangeCallback = Callable[[SafetyState, SafetyState, str], None]


class EmergencyStop:
    """Emergency stop safety system for OpenDuck Mini V3.

    Monitors a physical GPIO button and provides software-triggered emergency
    stop capability. When triggered, immediately disables all servo outputs
    and transitions to a safe state.

    Thread Safety:
        All public methods are thread-safe. Uses threading.RLock (reentrant lock)
        to protect state transitions and callback invocations. The reentrant lock
        allows callbacks to safely call EmergencyStop methods without deadlocking.
        The lock is acquired before any state modification and held during callback
        execution to ensure consistent state observation.

    Performance:
        Target latency from trigger to servo disable: <5ms
        Actual performance depends on I2C bus speed and PCA9685 driver.

    Attributes:
        servo_driver: Reference to PCA9685Driver for servo control
        gpio_pin: GPIO pin number for emergency stop button
        debounce_ms: Debounce time in milliseconds
        auto_reset: If True, allows direct RESET_REQUIRED -> RUNNING transition

    Example:
        >>> # With mock GPIO for testing
        >>> class MockGPIO:
        ...     BCM = 11
        ...     IN = 1
        ...     PUD_UP = 22
        ...     FALLING = 32
        ...     def setmode(self, mode): pass
        ...     def setup(self, pin, direction, pull_up_down): pass
        ...     def input(self, pin): return 1
        ...     def add_event_detect(self, pin, edge, callback, bouncetime): pass
        ...     def remove_event_detect(self, pin): pass
        ...     def cleanup(self, pin=None): pass
        >>>
        >>> e_stop = EmergencyStop(mock_servo, gpio_provider=MockGPIO())
    """

    # Maximum number of events to store in history (Issue #6: prevent unbounded growth)
    MAX_EVENT_HISTORY = 100

    # Valid state transitions
    _VALID_TRANSITIONS = {
        SafetyState.INIT: {SafetyState.RUNNING, SafetyState.E_STOP},
        SafetyState.RUNNING: {SafetyState.E_STOP},
        SafetyState.E_STOP: {SafetyState.RESET_REQUIRED},
        SafetyState.RESET_REQUIRED: {SafetyState.RUNNING, SafetyState.INIT},
    }

    def __init__(
        self,
        servo_driver: ServoDriverProtocol,
        gpio_pin: int = 26,
        gpio_provider: Optional[Any] = None,
        debounce_ms: int = 50,
        auto_reset: bool = False
    ) -> None:
        """Initialize emergency stop system.

        Args:
            servo_driver: PCA9685Driver instance or compatible servo driver
                that implements disable_all() method.
            gpio_pin: GPIO pin number for emergency stop button (BCM numbering).
                Default: 26 (as per hardware_config.yaml).
            gpio_provider: GPIO implementation (RPi.GPIO compatible).
                If None, attempts to import RPi.GPIO. Provide mock for testing.
            debounce_ms: Button debounce time in milliseconds. Default: 50ms.
            auto_reset: If True, reset() transitions directly to RUNNING.
                If False, reset() transitions to INIT requiring start() call.

        Raises:
            ValueError: If debounce_ms < 0 or gpio_pin out of valid range.

        Note:
            The system starts in INIT state with GPIO monitoring NOT active.
            Call start() to begin monitoring and transition to RUNNING state.
        """
        # Validate inputs
        if debounce_ms < 0:
            raise ValueError(f"debounce_ms must be non-negative, got {debounce_ms}")
        if not 0 <= gpio_pin <= 27:
            raise ValueError(f"gpio_pin must be 0-27 (BCM), got {gpio_pin}")

        # Store configuration
        self._servo_driver = servo_driver
        self._gpio_pin = gpio_pin
        self._debounce_ms = debounce_ms
        self._auto_reset = auto_reset

        # Thread safety - RLock allows recursive calls from callbacks (Issue #2)
        self._lock = threading.RLock()

        # State management
        self._state = SafetyState.INIT
        self._callbacks: List[StateChangeCallback] = []
        self._event_history: List[EmergencyStopEvent] = []
        self._gpio_monitoring_active = False
        self._disable_succeeded: bool = True  # Issue #1: Track if disable_all() succeeded

        # GPIO provider (dependency injection for testing)
        self._gpio: Optional[Any] = None
        self._gpio_available = False

        if gpio_provider is not None:
            self._gpio = gpio_provider
            self._gpio_available = True
        else:
            # Try to import RPi.GPIO
            try:
                import RPi.GPIO as GPIO
                self._gpio = GPIO
                self._gpio_available = True
            except ImportError:
                # Running on non-Pi system (development/testing)
                self._gpio = None
                self._gpio_available = False

    @property
    def state(self) -> SafetyState:
        """Get current safety state (thread-safe).

        Returns:
            Current SafetyState value.
        """
        with self._lock:
            return self._state

    @property
    def is_safe(self) -> bool:
        """Check if system is in a safe operational state.

        Returns:
            True if state is RUNNING (normal operation allowed).
            False for INIT, E_STOP, or RESET_REQUIRED states.
        """
        with self._lock:
            return self._state == SafetyState.RUNNING

    @property
    def gpio_available(self) -> bool:
        """Check if GPIO hardware is available.

        Returns:
            True if GPIO provider is available and can be used.
        """
        return self._gpio_available

    @property
    def event_history(self) -> List[EmergencyStopEvent]:
        """Get copy of emergency stop event history (thread-safe).

        Returns:
            List of EmergencyStopEvent objects, oldest first.
        """
        with self._lock:
            return self._event_history.copy()

    @property
    def disable_succeeded(self) -> bool:
        """Check if the last servo disable operation succeeded (Issue #1).

        This is a safety-critical property. If False after an E-STOP trigger,
        servos may still be running despite the E_STOP state. Operators should
        treat this as a critical failure requiring immediate physical intervention.

        Returns:
            True if disable_all() succeeded on last trigger.
            False if an exception occurred during disable_all().
        """
        with self._lock:
            return self._disable_succeeded

    def _validate_transition(self, new_state: SafetyState) -> bool:
        """Check if state transition is valid.

        Args:
            new_state: Target state to transition to.

        Returns:
            True if transition is valid, False otherwise.

        Note:
            Must be called with lock held.
        """
        valid_targets = self._VALID_TRANSITIONS.get(self._state, set())
        return new_state in valid_targets

    def _set_state(self, new_state: SafetyState, source: str = "internal") -> bool:
        """Set new state with validation and callbacks.

        Args:
            new_state: Target state to transition to.
            source: Source of the state change for logging/callbacks.

        Returns:
            True if state changed successfully, False if transition invalid.

        Note:
            Must be called with lock held. Callbacks are invoked under lock
            to ensure they observe consistent state.
        """
        if not self._validate_transition(new_state):
            return False

        old_state = self._state
        self._state = new_state

        # Invoke callbacks (still under lock for consistency)
        for callback in self._callbacks:
            try:
                callback(old_state, new_state, source)
            except Exception:
                # Don't let callback errors affect safety system
                pass

        return True

    def start(self) -> bool:
        """Start the emergency stop monitoring system.

        Transitions from INIT to RUNNING state and begins GPIO monitoring
        if hardware is available.

        Returns:
            True if successfully started (state changed to RUNNING).
            False if already running or transition invalid.

        Raises:
            RuntimeError: If GPIO setup fails (logged, not raised in production).

        Example:
            >>> e_stop = EmergencyStop(servo_driver)
            >>> assert e_stop.state == SafetyState.INIT
            >>> e_stop.start()
            True
            >>> assert e_stop.state == SafetyState.RUNNING
        """
        with self._lock:
            if self._state != SafetyState.INIT:
                return False

            # Setup GPIO monitoring if available
            if self._gpio_available and self._gpio is not None:
                try:
                    self._setup_gpio()
                except Exception:
                    # GPIO setup failed - mark as unavailable
                    # Software triggers still work, but no hardware E-STOP
                    self._gpio_monitoring_active = False
                    self._gpio_available = False
                    # In production, this should go to a proper logger
                    pass

            # Transition to RUNNING
            return self._set_state(SafetyState.RUNNING, source="start")

    def _setup_gpio(self) -> None:
        """Configure GPIO for emergency stop monitoring.

        Sets up GPIO pin with internal pull-up and falling edge detection.

        Note:
            Must be called with lock held.

        Raises:
            RuntimeError: If GPIO configuration fails.
        """
        if self._gpio is None:
            return

        try:
            # Set BCM pin numbering mode
            self._gpio.setmode(self._gpio.BCM)

            # Configure pin as input with pull-up (active LOW button)
            self._gpio.setup(
                self._gpio_pin,
                self._gpio.IN,
                pull_up_down=self._gpio.PUD_UP
            )

            # Add falling edge detection with debounce
            self._gpio.add_event_detect(
                self._gpio_pin,
                self._gpio.FALLING,
                callback=self._gpio_callback,
                bouncetime=self._debounce_ms
            )

            self._gpio_monitoring_active = True

        except Exception as e:
            self._gpio_monitoring_active = False
            raise RuntimeError(f"GPIO setup failed: {e}")

    def _gpio_callback(self, channel: int) -> None:
        """GPIO interrupt callback for emergency stop button.

        Called by RPi.GPIO when falling edge detected on e-stop pin.
        Triggers emergency stop with GPIO as source.

        Args:
            channel: GPIO channel that triggered the interrupt.

        Note:
            This runs in GPIO callback thread, so must be thread-safe.
            Verifies pin is actually LOW to filter spurious edge detections
            that may occur despite hardware debounce.
        """
        # Verify pin is actually LOW (debounce verification)
        # This guards against spurious edge detections from noise
        if self._gpio is not None and self._gpio.input(self._gpio_pin) != 0:
            return  # Pin is HIGH, spurious trigger - ignore

        # Trigger with GPIO source
        self.trigger(source="gpio")

    def trigger(self, source: str = "manual") -> float:
        """Trigger emergency stop.

        Immediately disables all servos and transitions to E_STOP state.
        This is the primary safety function and is designed for minimum latency.

        Args:
            source: Source of the trigger for logging/diagnostics.
                Common values: "gpio", "manual", "software", "watchdog".

        Returns:
            Latency in milliseconds from call to servo disable completion.
            Returns 0.0 if already in E_STOP or RESET_REQUIRED state.

        Thread Safety:
            This method is thread-safe and can be called from any thread,
            including GPIO interrupt handlers.

        Performance:
            Target: <5ms from call to servo disable completion.
            Actual performance depends on I2C bus and PCA9685 driver.

        Example:
            >>> latency = e_stop.trigger(source="manual")
            >>> print(f"Shutdown completed in {latency:.2f}ms")
            >>> assert e_stop.state == SafetyState.E_STOP
        """
        start_time = time.perf_counter()

        with self._lock:
            # Check if already stopped
            if self._state in (SafetyState.E_STOP, SafetyState.RESET_REQUIRED):
                return 0.0

            # Store previous state for event record
            previous_state = self._state

            # CRITICAL: Disable servos FIRST for minimum latency
            # This is the safety-critical operation
            try:
                self._servo_driver.disable_all()
                self._disable_succeeded = True  # Issue #1: Track success
            except Exception as e:
                # Issue #1: Track failure and log the exception
                self._disable_succeeded = False
                _logger.critical(
                    "SAFETY CRITICAL: disable_all() failed during E-STOP! "
                    "Servos may still be running. Exception: %s",
                    e,
                    exc_info=True
                )
                # Continue with state transition - state should reflect E_STOP
                # even though physical stop may have failed

            # Calculate latency (servo disable is the critical path)
            latency_ms = (time.perf_counter() - start_time) * 1000

            # Transition to E_STOP state
            self._set_state(SafetyState.E_STOP, source=source)

            # Auto-transition to RESET_REQUIRED
            self._set_state(SafetyState.RESET_REQUIRED, source=source)

            # Record event
            event = EmergencyStopEvent(
                timestamp=time.time(),
                source=source,
                latency_ms=latency_ms,
                previous_state=previous_state
            )
            self._event_history.append(event)

            # Issue #6: Trim event history if it exceeds maximum size
            if len(self._event_history) > self.MAX_EVENT_HISTORY:
                self._event_history = self._event_history[-self.MAX_EVENT_HISTORY:]

            return latency_ms

    def reset(self) -> bool:
        """Reset the emergency stop system after a trigger.

        Allows the system to return to operational state after an emergency
        stop has been acknowledged and cleared.

        Returns:
            True if reset successful and system ready for operation.
            False if reset not allowed (not in RESET_REQUIRED state).

        Behavior:
            - If auto_reset=True: Transitions directly to RUNNING state.
            - If auto_reset=False: Transitions to INIT, requiring start() call.

        Example:
            >>> # After emergency stop triggered
            >>> assert e_stop.state == SafetyState.RESET_REQUIRED
            >>> e_stop.reset()
            True
            >>> if e_stop._auto_reset:
            ...     assert e_stop.state == SafetyState.RUNNING
            ... else:
            ...     assert e_stop.state == SafetyState.INIT
            ...     e_stop.start()  # Required if auto_reset=False
        """
        with self._lock:
            if self._state != SafetyState.RESET_REQUIRED:
                return False

            if self._auto_reset:
                # Direct transition to RUNNING
                return self._set_state(SafetyState.RUNNING, source="reset")
            else:
                # Transition to INIT, requiring explicit start()
                # First cleanup GPIO if active
                if self._gpio_monitoring_active and self._gpio is not None:
                    try:
                        self._gpio.remove_event_detect(self._gpio_pin)
                    except Exception:
                        pass
                    self._gpio_monitoring_active = False

                return self._set_state(SafetyState.INIT, source="reset")

    def register_callback(self, callback: StateChangeCallback) -> None:
        """Register a callback for state change notifications.

        Callbacks are invoked synchronously when state changes occur,
        under the internal lock. Keep callbacks fast to avoid blocking
        the safety system.

        Args:
            callback: Function with signature (old_state, new_state, source).
                - old_state: SafetyState before the transition
                - new_state: SafetyState after the transition
                - source: String describing what triggered the change

        Example:
            >>> def on_state_change(old, new, source):
            ...     print(f"State: {old.name} -> {new.name} ({source})")
            ...
            >>> e_stop.register_callback(on_state_change)

        Note:
            Callbacks are invoked under a reentrant lock (RLock), so calling
            other EmergencyStop methods from within a callback is safe and will
            not cause deadlocks. However, do NOT perform long-running operations
            in callbacks as this blocks the safety system.
        """
        with self._lock:
            self._callbacks.append(callback)

    def unregister_callback(self, callback: StateChangeCallback) -> bool:
        """Unregister a previously registered callback.

        Args:
            callback: The callback function to remove.

        Returns:
            True if callback was found and removed, False otherwise.
        """
        with self._lock:
            try:
                self._callbacks.remove(callback)
                return True
            except ValueError:
                return False

    def cleanup(self) -> None:
        """Clean up GPIO resources and stop monitoring.

        Should be called when the EmergencyStop system is no longer needed.
        After cleanup, the instance should not be used.

        This method is safe to call multiple times.
        """
        with self._lock:
            if self._gpio_monitoring_active and self._gpio is not None:
                try:
                    self._gpio.remove_event_detect(self._gpio_pin)
                    self._gpio.cleanup(self._gpio_pin)
                except Exception:
                    pass
                self._gpio_monitoring_active = False

            # Clear callbacks
            self._callbacks.clear()

    def __enter__(self) -> "EmergencyStop":
        """Context manager entry.

        Returns:
            Self for use in with statement.

        Example:
            >>> with EmergencyStop(servo_driver) as e_stop:
            ...     e_stop.start()
            ...     # Use e_stop
        """
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Context manager exit - ensures cleanup."""
        self.cleanup()

    def __repr__(self) -> str:
        """String representation for debugging."""
        return (
            f"EmergencyStop("
            f"state={self._state.name}, "
            f"gpio_pin={self._gpio_pin}, "
            f"gpio_available={self._gpio_available}, "
            f"auto_reset={self._auto_reset})"
        )
