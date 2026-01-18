"""Safety Coordinator for OpenDuck Mini V3.

This module provides unified coordination of all safety systems:
- EmergencyStop: Physical button and software-triggered E-stop
- ServoWatchdog: Control loop timeout monitoring
- CurrentLimiter: Stall detection and thermal protection

Design Philosophy:
    - Single point of truth for safety status
    - feed_watchdog() integrates safety checks before feeding
    - Shutdown order is enforced: watchdog → estop → cleanup
    - E-stop trigger NEVER raises exceptions (logs and continues)
    - Stall on ANY channel triggers E-stop

Thread Ownership:
    SafetyCoordinator (main thread) OWNS:
    ├── EmergencyStop instance
    │   └── Spawns daemon thread for GPIO monitoring
    ├── ServoWatchdog instance
    │   └── Spawns daemon thread for timeout monitoring
    └── CurrentLimiter instance
        └── No threads (pure computation)

Example:
    >>> from src.drivers.servo.pca9685 import PCA9685Driver
    >>> driver = PCA9685Driver()
    >>> safety = SafetyCoordinator(driver, watchdog_timeout_ms=500)
    >>> safety.start()
    >>> # In control loop:
    >>> while safety.feed_watchdog():
    ...     # All safety checks passed, execute commands
    ...     pass
    >>> safety.stop()
"""

import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Tuple

from safety.emergency_stop import EmergencyStop, SafetyState
from safety.watchdog import ServoWatchdog
from safety.current_limiter import CurrentLimiter, StallCondition

_logger = logging.getLogger(__name__)


@dataclass
class SafetyStatus:
    """Snapshot of safety system status.

    Attributes:
        is_safe: True if all safety systems report safe state.
        estop_state: Current EmergencyStop SafetyState.
        watchdog_running: True if watchdog is actively monitoring.
        watchdog_expired: True if watchdog has timed out.
        stalled_channels: List of channels with confirmed stall.
        thermal_limited_channels: List of channels with thermal limiting.
        last_estop_source: Source of last E-stop trigger (if any).
        timestamp: When this status was captured.
    """
    is_safe: bool
    estop_state: SafetyState
    watchdog_running: bool
    watchdog_expired: bool
    stalled_channels: list = field(default_factory=list)
    thermal_limited_channels: list = field(default_factory=list)
    last_estop_source: Optional[str] = None
    timestamp: float = field(default_factory=time.monotonic)


class SafetyCoordinator:
    """Unified safety system coordinator.

    Coordinates EmergencyStop, ServoWatchdog, and CurrentLimiter into a
    single interface for the Robot orchestrator.

    Thread Safety:
        All public methods are thread-safe. Internal state is protected
        by a lock. However, the control loop should be single-threaded
        for deterministic behavior.

    Attributes:
        watchdog_timeout_ms: Configured watchdog timeout.
        estop_gpio_pin: GPIO pin for emergency stop button.
    """

    # Minimum duty cycle to allow movement (thermal protection)
    MIN_DUTY_CYCLE_THRESHOLD: float = 0.10  # 10%

    def __init__(
        self,
        servo_driver: Any,
        gpio_provider: Optional[Any] = None,
        watchdog_timeout_ms: int = 500,
        estop_gpio_pin: int = 26,
        estop_debounce_ms: int = 50,
    ) -> None:
        """Initialize safety coordinator.

        Args:
            servo_driver: PCA9685Driver instance for servo control.
            gpio_provider: GPIO provider for E-stop button (None for testing).
            watchdog_timeout_ms: Watchdog timeout in milliseconds.
            estop_gpio_pin: GPIO pin for E-stop button.
            estop_debounce_ms: Debounce time for E-stop button.

        Raises:
            ValueError: If watchdog_timeout_ms is not positive.
        """
        if watchdog_timeout_ms <= 0:
            raise ValueError(
                f"watchdog_timeout_ms must be positive, got {watchdog_timeout_ms}"
            )

        self._servo_driver = servo_driver
        self._gpio_provider = gpio_provider
        self._watchdog_timeout_ms = watchdog_timeout_ms
        self._estop_gpio_pin = estop_gpio_pin

        # Thread safety (RLock for reentrant access in get_diagnostics)
        self._lock = threading.RLock()
        self._started = False
        self._last_estop_source: Optional[str] = None

        # Create safety subsystems
        self._emergency_stop = EmergencyStop(
            servo_driver=servo_driver,
            gpio_provider=gpio_provider,
            gpio_pin=estop_gpio_pin,
            debounce_ms=estop_debounce_ms,
            auto_reset=False,  # Require manual reset
        )

        self._watchdog = ServoWatchdog(
            emergency_stop=self._emergency_stop,
            timeout_ms=watchdog_timeout_ms,
        )

        self._current_limiter = CurrentLimiter(
            pca_driver=servo_driver,
        )

        _logger.debug(
            "SafetyCoordinator initialized: watchdog=%dms, estop_pin=%d",
            watchdog_timeout_ms,
            estop_gpio_pin,
        )

    @property
    def watchdog_timeout_ms(self) -> int:
        """Get configured watchdog timeout in milliseconds."""
        return self._watchdog_timeout_ms

    @property
    def estop_gpio_pin(self) -> int:
        """Get GPIO pin used for emergency stop button."""
        return self._estop_gpio_pin

    @property
    def is_safe(self) -> bool:
        """Check if all safety systems report safe state.

        Returns:
            True if E-stop is RUNNING and watchdog hasn't expired.
        """
        with self._lock:
            estop_ok = self._emergency_stop.state == SafetyState.RUNNING
            watchdog_ok = not self._watchdog.is_expired
            return estop_ok and watchdog_ok and self._started

    def start(self) -> bool:
        """Start all safety monitoring systems.

        Starts E-stop monitoring and watchdog timer. After this call,
        feed_watchdog() must be called regularly to prevent timeout.

        Returns:
            True if all systems started successfully, False on failure.

        Note:
            E-stop must transition to RUNNING state for this to succeed.
        """
        with self._lock:
            if self._started:
                _logger.warning("SafetyCoordinator already started")
                return True

            try:
                # Start E-stop monitoring (GPIO interrupt handler)
                self._emergency_stop.start()

                # Verify E-stop is in RUNNING state
                if self._emergency_stop.state != SafetyState.RUNNING:
                    _logger.error(
                        "E-stop failed to reach RUNNING state: %s",
                        self._emergency_stop.state,
                    )
                    return False

                # Start watchdog timer
                self._watchdog.start()

                # Initial feed to prevent immediate timeout
                self._watchdog.feed()

                # Reset current limiter state
                self._current_limiter.reset_all_channels()

                self._started = True
                _logger.info("SafetyCoordinator started successfully")
                return True

            except Exception as e:
                _logger.error("Failed to start safety systems: %s", e)
                # Attempt cleanup
                self._cleanup_on_error()
                return False

    def stop(self) -> None:
        """Stop all safety monitoring systems.

        CRITICAL: Follows shutdown order:
        1. Stop watchdog FIRST (prevent spurious E-stop during shutdown)
        2. Trigger E-stop (ensure servos are disabled)
        3. Cleanup GPIO resources

        Safe to call multiple times (idempotent).
        """
        with self._lock:
            if not self._started:
                return

            _logger.info("SafetyCoordinator stopping...")

            # Step 1: Stop watchdog FIRST
            # Reason: Prevent spurious E-stop during shutdown sequence
            try:
                self._watchdog.stop()
            except Exception as e:
                _logger.warning("Error stopping watchdog: %s", e)

            # Step 2: Trigger E-stop (ensure servos disabled)
            # This is defensive - servos may already be disabled
            try:
                self._emergency_stop.trigger(source="shutdown")
            except Exception as e:
                _logger.warning("Error triggering E-stop during shutdown: %s", e)

            # Step 3: Cleanup GPIO
            try:
                self._emergency_stop.cleanup()
            except Exception as e:
                _logger.warning("Error cleaning up E-stop GPIO: %s", e)

            self._started = False
            _logger.info("SafetyCoordinator stopped")

    def feed_watchdog(self) -> bool:
        """Feed watchdog ONLY if all safety checks pass.

        This is the primary method called by the control loop. It performs
        safety checks and only feeds the watchdog if all checks pass.

        Checks performed (in order):
        1. E-stop state is RUNNING (not triggered)
        2. No CONFIRMED stalls on any channel
        3. No thermal limiting below 10% duty cycle

        If ANY check fails:
        - Trigger E-stop immediately
        - Return False (control loop must stop)

        If ALL checks pass:
        - Feed the actual watchdog
        - Return True (control loop continues)

        Returns:
            True if all checks passed and watchdog was fed.
            False if any check failed (E-stop triggered).

        Note:
            This method NEVER raises exceptions. Errors are logged and
            result in False return value.
        """
        try:
            with self._lock:
                if not self._started:
                    return False

                # Check 1: E-stop state
                if self._emergency_stop.state != SafetyState.RUNNING:
                    _logger.debug(
                        "feed_watchdog: E-stop not RUNNING (state=%s)",
                        self._emergency_stop.state,
                    )
                    return False

                # Check 2: Stall detection
                diagnostics = self._current_limiter.get_system_diagnostics()
                stalled = diagnostics.get("stalled_channels", [])
                if stalled:
                    _logger.warning(
                        "feed_watchdog: Stall detected on channels %s - triggering E-stop",
                        stalled,
                    )
                    self._trigger_estop_internal(
                        f"stall_detected:channels={stalled}"
                    )
                    return False

                # Check 3: Thermal limiting
                thermal_limited = diagnostics.get("thermal_limited_channels", [])
                for channel in thermal_limited:
                    duty = self._current_limiter.get_duty_cycle(channel)
                    if duty < self.MIN_DUTY_CYCLE_THRESHOLD:
                        _logger.warning(
                            "feed_watchdog: Thermal limit critical on channel %d "
                            "(duty=%.1f%%) - triggering E-stop",
                            channel,
                            duty * 100,
                        )
                        self._trigger_estop_internal(
                            f"thermal_limit:channel={channel},duty={duty:.2%}"
                        )
                        return False

                # All checks passed - feed watchdog
                self._watchdog.feed()
                return True

        except Exception as e:
            _logger.error("feed_watchdog error: %s - triggering E-stop", e)
            try:
                self._trigger_estop_internal(f"feed_error:{type(e).__name__}")
            except Exception:
                pass  # E-stop trigger must not raise
            return False

    def check_movement_allowed(self, channel: int) -> Tuple[bool, str]:
        """Check if movement is allowed for a servo channel.

        Combines E-stop state check with CurrentLimiter's safety checks.

        Args:
            channel: Servo channel number.

        Returns:
            Tuple of (allowed: bool, reason: str).
            If allowed is False, reason explains why.
        """
        with self._lock:
            # Check E-stop state first
            if self._emergency_stop.state != SafetyState.RUNNING:
                return (
                    False,
                    f"E-stop active (state={self._emergency_stop.state.name})"
                )

            # Delegate to CurrentLimiter
            return self._current_limiter.is_movement_allowed(channel)

    def register_movement(self, channel: int, target: float) -> None:
        """Register the start of a servo movement.

        Args:
            channel: Servo channel number.
            target: Target angle in degrees.
        """
        with self._lock:
            self._current_limiter.register_movement_start(channel, target)

    def complete_movement(self, channel: int) -> None:
        """Register the completion of a servo movement.

        Args:
            channel: Servo channel number.
        """
        with self._lock:
            self._current_limiter.register_movement_complete(channel)

    def check_stall(
        self,
        channel: int,
        target_angle: Optional[float] = None,
        current_position: Optional[float] = None,
    ) -> StallCondition:
        """Check for stall condition on a servo channel.

        Args:
            channel: Servo channel number.
            target_angle: Target angle the servo is trying to reach.
            current_position: Current servo position in degrees.

        Returns:
            StallCondition indicating current stall detection state.
        """
        with self._lock:
            return self._current_limiter.check_stall(
                channel, target_angle, current_position
            )

    def trigger_estop(self, source: str) -> float:
        """Trigger emergency stop.

        This method NEVER raises exceptions. Errors are logged.

        Args:
            source: Human-readable source identifier.

        Returns:
            Latency in milliseconds, or -1.0 on error.
        """
        try:
            with self._lock:
                return self._trigger_estop_internal(source)
        except Exception as e:
            _logger.error("trigger_estop error: %s", e)
            return -1.0

    def reset_estop(self) -> bool:
        """Attempt to reset from E-stop state.

        Only succeeds if:
        1. E-stop is in RESET_REQUIRED state
        2. All stall conditions are cleared
        3. Thermal limits allow operation

        Returns:
            True if reset successful, False otherwise.
        """
        with self._lock:
            # Check preconditions
            if self._emergency_stop.state not in (
                SafetyState.E_STOP,
                SafetyState.RESET_REQUIRED,
            ):
                _logger.warning(
                    "Cannot reset E-stop from state %s",
                    self._emergency_stop.state,
                )
                return False

            # Check for stalls
            diagnostics = self._current_limiter.get_system_diagnostics()
            if diagnostics.get("stalled_channels"):
                _logger.warning(
                    "Cannot reset E-stop: stalls on channels %s",
                    diagnostics["stalled_channels"],
                )
                return False

            # Reset current limiter state
            self._current_limiter.reset_all_channels()

            # Attempt E-stop reset
            try:
                result = self._emergency_stop.reset()
                if result:
                    # Restart watchdog
                    if not self._watchdog.is_running:
                        self._watchdog.start()
                        self._watchdog.feed()
                    self._started = True
                    _logger.info("E-stop reset successful")
                return result
            except Exception as e:
                _logger.error("E-stop reset failed: %s", e)
                return False

    def get_status(self) -> SafetyStatus:
        """Get snapshot of safety system status.

        Returns:
            SafetyStatus dataclass with current state.
        """
        with self._lock:
            diagnostics = self._current_limiter.get_system_diagnostics()

            return SafetyStatus(
                is_safe=self.is_safe,
                estop_state=self._emergency_stop.state,
                watchdog_running=self._watchdog.is_running,
                watchdog_expired=self._watchdog.is_expired,
                stalled_channels=diagnostics.get("stalled_channels", []),
                thermal_limited_channels=diagnostics.get(
                    "thermal_limited_channels", []
                ),
                last_estop_source=self._last_estop_source,
            )

    def get_diagnostics(self) -> Dict[str, Any]:
        """Get detailed diagnostics for debugging.

        Returns:
            Dictionary with detailed safety system information.
        """
        with self._lock:
            return {
                "started": self._started,
                "is_safe": self.is_safe,
                "estop": {
                    "state": self._emergency_stop.state.name,
                    "gpio_pin": self._estop_gpio_pin,
                },
                "watchdog": {
                    "timeout_ms": self._watchdog_timeout_ms,
                    "running": self._watchdog.is_running,
                    "expired": self._watchdog.is_expired,
                },
                "current_limiter": self._current_limiter.get_system_diagnostics(),
                "last_estop_source": self._last_estop_source,
            }

    def _trigger_estop_internal(self, source: str) -> float:
        """Internal E-stop trigger (assumes lock is held).

        Args:
            source: Source identifier.

        Returns:
            Latency in milliseconds.
        """
        self._last_estop_source = source
        _logger.warning("E-stop triggered: %s", source)

        try:
            latency = self._emergency_stop.trigger(source=source)
            return latency
        except Exception as e:
            _logger.error("E-stop trigger error: %s", e)
            # Try to disable servos directly as fallback
            try:
                self._servo_driver.disable_all()
            except Exception:
                pass  # Best effort
            return -1.0

    def _cleanup_on_error(self) -> None:
        """Cleanup resources after startup failure."""
        try:
            self._watchdog.stop()
        except Exception:
            pass
        try:
            self._emergency_stop.cleanup()
        except Exception:
            pass

    def __repr__(self) -> str:
        with self._lock:
            return (
                f"SafetyCoordinator("
                f"started={self._started}, "
                f"is_safe={self.is_safe}, "
                f"estop_state={self._emergency_stop.state.name})"
            )

    def __enter__(self) -> "SafetyCoordinator":
        """Context manager entry - starts safety systems."""
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit - stops safety systems."""
        self.stop()
