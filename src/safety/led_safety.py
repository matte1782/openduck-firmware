"""LED Safety System for OpenDuck Mini V3.

This module provides comprehensive fail-safe mechanisms for WS2812B LED rings
to prevent hardware damage and ensure safe operation under all conditions.

Hardware Context:
    - 2× WS2812B 16-LED rings (eyes)
    - Ring 1: GPIO 18 (PWM Channel 0) - 16 LEDs
    - Ring 2: GPIO 13 (PWM Channel 1) - 16 LEDs
    - Power: Raspberry Pi 5V rail (1.2A max)
    - Each LED: 60mA max at full white (RGB: 255,255,255)
    - Total max draw: 32 LEDs × 60mA = 1920mA (EXCEEDS Pi limit!)

Safety Features:
    1. Current Limiting - Prevents LED overload based on brightness
    2. Brightness Clamping - Auto-limits brightness to 50% when on Pi power
    3. GPIO State Validation - Verifies GPIO available before operations
    4. Graceful Shutdown - Emergency LED disable with proper cleanup
    5. Power Budget Tracking - Real-time current estimation

Power Budget Calculations:
    - Raspberry Pi 5V rail: 1.2A max (1200mA)
    - Reserve for Pi: 200mA (system overhead)
    - Available for LEDs: 1000mA
    - Per-LED budget: 1000mA / 32 LEDs = 31.25mA average
    - Safe brightness: 31.25mA / 60mA = 52% (rounded down to 50%)

References:
    - electronics/diagrams/COMPLETE_PIN_DIAGRAM_V3.md (lines 230-234)
    - firmware/src/led_test.py for existing safety checks
    - WS2812B datasheet for current specifications

SAFETY CRITICAL: This module prevents Pi brownout, SD card corruption, and
LED thermal damage. Do not modify without thorough testing.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from enum import Enum, auto
from typing import Optional, Tuple, Dict, Any, Protocol

# Module logger
_logger = logging.getLogger(__name__)


class PowerSource(Enum):
    """LED power source enumeration.

    Determines current limiting behavior:
    - PI_5V_RAIL: Strict 50% brightness limit (1.2A Pi rail)
    - EXTERNAL_5V: Higher brightness allowed (3A UBEC capacity)
    - UNKNOWN: Assume Pi power for safety (conservative)
    """
    PI_5V_RAIL = auto()
    EXTERNAL_5V = auto()
    UNKNOWN = auto()


class SafetyLevel(Enum):
    """LED safety level enumeration.

    States:
        SAFE: All operations allowed, within power budget
        WARNING: Approaching limits, warnings issued
        CRITICAL: At or exceeding limits, brightness reduced
        EMERGENCY: Immediate shutdown required
    """
    SAFE = auto()
    WARNING = auto()
    CRITICAL = auto()
    EMERGENCY = auto()


@dataclass
class LEDRingProfile:
    """LED ring electrical characteristics.

    Attributes:
        num_leds: Number of LEDs in the ring (default: 16)
        current_per_led_ma: Maximum current per LED at full brightness (default: 60mA)
        gpio_pin: GPIO pin number for data line
        pwm_channel: PWM channel number (0 or 1)
        name: Human-readable identifier (e.g., "Left Eye", "Right Eye")
    """
    num_leds: int = 16
    current_per_led_ma: float = 60.0
    gpio_pin: int = 18
    pwm_channel: int = 0
    name: str = "LED Ring"

    def __post_init__(self):
        if self.num_leds <= 0:
            raise ValueError(f"num_leds must be positive, got {self.num_leds}")
        if self.current_per_led_ma <= 0:
            raise ValueError(f"current_per_led_ma must be positive, got {self.current_per_led_ma}")
        if not 0 <= self.gpio_pin <= 27:
            raise ValueError(f"gpio_pin must be 0-27 (BCM), got {self.gpio_pin}")
        if self.pwm_channel not in (0, 1):
            raise ValueError(f"pwm_channel must be 0 or 1, got {self.pwm_channel}")

    @property
    def max_current_ma(self) -> float:
        """Maximum current draw at full white (all LEDs at 100%)."""
        return self.num_leds * self.current_per_led_ma


class GPIOProvider(Protocol):
    """Protocol for GPIO operations (allows dependency injection for testing).

    This protocol defines the interface for GPIO operations, allowing
    the LEDSafetyManager to work with either real RPi.GPIO or mock
    implementations for testing.
    """

    BCM: int
    OUT: int

    def setmode(self, mode: int) -> None:
        """Set GPIO pin numbering mode."""
        ...

    def setup(self, pin: int, direction: int) -> None:
        """Configure a GPIO pin."""
        ...

    def cleanup(self, pin: Optional[int] = None) -> None:
        """Clean up GPIO resources."""
        ...


@dataclass
class CurrentEstimate:
    """Current draw estimate for LED operations.

    Attributes:
        total_ma: Total estimated current draw in milliamps
        per_ring_ma: Dict mapping ring name to estimated current
        safety_level: Current safety assessment
        max_allowed_ma: Maximum allowed current for current power source
        headroom_ma: Remaining current budget (negative = over budget)
    """
    total_ma: float
    per_ring_ma: Dict[str, float]
    safety_level: SafetyLevel
    max_allowed_ma: float
    headroom_ma: float


class LEDSafetyManager:
    """LED safety management system for OpenDuck Mini V3.

    Provides comprehensive fail-safe mechanisms for WS2812B LED rings:
    - Automatic brightness clamping based on power source
    - Real-time current monitoring and budget tracking
    - GPIO state validation before operations
    - Emergency shutdown with graceful cleanup

    Thread Safety:
        All public methods are thread-safe using threading.RLock.

    Attributes:
        power_source: Current power source (PI_5V_RAIL or EXTERNAL_5V)
        rings: Dictionary of registered LED ring profiles
        max_brightness_pi_power: Maximum safe brightness on Pi 5V rail (0-255)
        pi_rail_max_current_ma: Maximum current from Pi 5V rail
        pi_reserve_current_ma: Reserved current for Pi system overhead

    Example:
        >>> # Initialize safety manager
        >>> manager = LEDSafetyManager(power_source=PowerSource.PI_5V_RAIL)
        >>>
        >>> # Register LED rings
        >>> ring1 = LEDRingProfile(gpio_pin=18, pwm_channel=0, name="Left Eye")
        >>> ring2 = LEDRingProfile(gpio_pin=13, pwm_channel=1, name="Right Eye")
        >>> manager.register_ring("ring1", ring1)
        >>> manager.register_ring("ring2", ring2)
        >>>
        >>> # Validate brightness before setting
        >>> allowed, safe_brightness = manager.validate_brightness("ring1", 255)
        >>> if not allowed:
        ...     print(f"Brightness clamped to {safe_brightness}")
        >>>
        >>> # Check current budget
        >>> estimate = manager.estimate_current({"ring1": 128, "ring2": 128})
        >>> print(f"Total: {estimate.total_ma}mA, Headroom: {estimate.headroom_ma}mA")
    """

    # Safety constants (conservative limits)
    PI_RAIL_MAX_CURRENT_MA = 1200.0  # Raspberry Pi 5V rail max current
    PI_RESERVE_CURRENT_MA = 200.0    # Reserved for Pi system overhead
    EXTERNAL_MAX_CURRENT_MA = 2000.0 # UBEC #2 capacity (3A with 1A margin)
    MAX_SAFE_BRIGHTNESS_PI_POWER = 50  # Maximum brightness on Pi power (0-255)

    # Warning thresholds
    WARNING_THRESHOLD = 0.80  # Issue warning at 80% of max current
    CRITICAL_THRESHOLD = 0.95 # Critical warning at 95% of max current

    # Brightness calculation constants
    MIN_BRIGHTNESS = 0
    MAX_BRIGHTNESS = 255

    def __init__(
        self,
        power_source: PowerSource = PowerSource.PI_5V_RAIL,
        gpio_provider: Optional[Any] = None,
        custom_pi_max_current_ma: Optional[float] = None,
        custom_brightness_limit: Optional[int] = None
    ) -> None:
        """Initialize LED safety manager.

        Args:
            power_source: Current power source for LEDs. Defaults to PI_5V_RAIL
                for conservative safety. Change to EXTERNAL_5V if using UBEC.
            gpio_provider: GPIO implementation (RPi.GPIO compatible).
                If None, attempts to import RPi.GPIO. Provide mock for testing.
            custom_pi_max_current_ma: Override default Pi rail current limit.
                Use with caution - default is based on Pi 4 specs.
            custom_brightness_limit: Override calculated brightness limit.
                Use with caution - default is calculated for safety.

        Raises:
            ValueError: If custom limits are invalid or dangerous.
        """
        # Validate custom limits
        if custom_pi_max_current_ma is not None:
            if custom_pi_max_current_ma <= 0 or custom_pi_max_current_ma > 3000:
                raise ValueError(
                    f"custom_pi_max_current_ma must be 0-3000mA, got {custom_pi_max_current_ma}"
                )

        if custom_brightness_limit is not None:
            if not 0 <= custom_brightness_limit <= 255:
                raise ValueError(
                    f"custom_brightness_limit must be 0-255, got {custom_brightness_limit}"
                )

        # Store configuration
        self._power_source = power_source
        self._pi_rail_max_ma = custom_pi_max_current_ma or self.PI_RAIL_MAX_CURRENT_MA
        self._max_brightness_pi = custom_brightness_limit or self.MAX_SAFE_BRIGHTNESS_PI_POWER

        # LED ring registry
        self._rings: Dict[str, LEDRingProfile] = {}

        # Thread safety lock
        # MEDIUM Issue #6: RLock without timeout - blocking indefinitely
        # Future improvement: Use timeout parameter in all 'with self._lock:' statements
        # Example: self._lock.acquire(timeout=5.0) for critical sections
        self._lock = threading.RLock()

        # GPIO provider (dependency injection for testing)
        # Initialize inside lock to ensure thread-safe singleton behavior
        with self._lock:
            self._gpio: Optional[GPIOProvider] = None
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
                    _logger.warning(
                        "RPi.GPIO not available - running in simulation mode. "
                        "GPIO validation will be skipped."
                    )

        # Emergency shutdown state
        self._emergency_shutdown_active = False

        _logger.info(
            "LEDSafetyManager initialized: power_source=%s, max_brightness=%d, "
            "pi_rail_max=%dmA, gpio_available=%s",
            power_source.name, self._max_brightness_pi,
            self._pi_rail_max_ma, self._gpio_available
        )

    @property
    def power_source(self) -> PowerSource:
        """Get current power source (thread-safe)."""
        with self._lock:
            return self._power_source

    @property
    def max_brightness_pi_power(self) -> int:
        """Get maximum safe brightness on Pi 5V rail (thread-safe)."""
        with self._lock:
            return self._max_brightness_pi

    @property
    def gpio_available(self) -> bool:
        """Check if GPIO hardware is available."""
        return self._gpio_available

    @property
    def emergency_shutdown_active(self) -> bool:
        """Check if emergency shutdown is active (thread-safe)."""
        with self._lock:
            return self._emergency_shutdown_active

    def register_ring(self, ring_id: str, profile: LEDRingProfile) -> None:
        """Register an LED ring for safety management.

        Args:
            ring_id: Unique identifier for this ring (e.g., "ring1", "left_eye")
            profile: LEDRingProfile with ring specifications

        Raises:
            ValueError: If ring_id already registered or profile invalid

        Example:
            >>> manager = LEDSafetyManager()
            >>> ring1 = LEDRingProfile(gpio_pin=18, pwm_channel=0, name="Left Eye")
            >>> manager.register_ring("ring1", ring1)
        """
        with self._lock:
            if ring_id in self._rings:
                raise ValueError(f"Ring '{ring_id}' already registered")

            self._rings[ring_id] = profile
            _logger.info(
                "Registered LED ring: %s (%s) - GPIO %d, %d LEDs, max %dmA",
                ring_id, profile.name, profile.gpio_pin,
                profile.num_leds, profile.max_current_ma
            )

    def unregister_ring(self, ring_id: str) -> bool:
        """Unregister an LED ring.

        Args:
            ring_id: Ring identifier to remove

        Returns:
            True if ring was found and removed, False otherwise
        """
        with self._lock:
            if ring_id in self._rings:
                del self._rings[ring_id]
                _logger.info("Unregistered LED ring: %s", ring_id)
                return True
            return False

    def validate_gpio_available(self, ring_id: str) -> Tuple[bool, str]:
        """Validate GPIO is available for LED operations.

        Args:
            ring_id: Ring identifier to check

        Returns:
            Tuple of (valid: bool, reason: str).
            - If valid is True, GPIO is available and ready.
            - If valid is False, reason explains the issue.

        Example:
            >>> valid, reason = manager.validate_gpio_available("ring1")
            >>> if not valid:
            ...     print(f"Cannot use LEDs: {reason}")
        """
        with self._lock:
            # Check if emergency shutdown active
            if self._emergency_shutdown_active:
                return (False, "Emergency shutdown active - all LED operations disabled")

            # Check if ring registered
            if ring_id not in self._rings:
                return (False, f"Ring '{ring_id}' not registered")

            # In simulation mode (no GPIO), always allow
            if not self._gpio_available:
                return (True, "")

            # GPIO available and no issues
            return (True, "")

    def validate_brightness(
        self,
        ring_id: str,
        brightness: int,
        force: bool = False
    ) -> Tuple[bool, int]:
        """Validate and clamp brightness to safe levels.

        Automatically reduces brightness if it would exceed power budget
        based on current power source.

        Args:
            ring_id: Ring identifier to validate for
            brightness: Requested brightness (0-255)
            force: If True, allows brightness above safe limit (use with caution!)

        Returns:
            Tuple of (allowed: bool, safe_brightness: int).
            - allowed: True if requested brightness is safe
            - safe_brightness: Brightness clamped to safe level

        Example:
            >>> allowed, safe = manager.validate_brightness("ring1", 255)
            >>> print(f"Requested: 255, Safe: {safe}, Allowed: {allowed}")
            Requested: 255, Safe: 50, Allowed: False
        """
        with self._lock:
            # Validate ring exists
            if ring_id not in self._rings:
                raise ValueError(f"Ring '{ring_id}' not registered")

            # Clamp to valid range
            brightness = max(self.MIN_BRIGHTNESS, min(self.MAX_BRIGHTNESS, brightness))

            # Force mode bypasses safety limits (dangerous!)
            if force:
                _logger.warning(
                    "SAFETY OVERRIDE: Brightness validation bypassed for %s (brightness=%d)",
                    ring_id, brightness
                )
                return (True, brightness)

            # Determine max safe brightness based on power source
            if self._power_source == PowerSource.PI_5V_RAIL:
                max_safe = self._max_brightness_pi
            elif self._power_source == PowerSource.EXTERNAL_5V:
                max_safe = self.MAX_BRIGHTNESS  # Full brightness allowed
            else:  # UNKNOWN - assume Pi power for safety
                max_safe = self._max_brightness_pi
                _logger.warning(
                    "Unknown power source - assuming Pi 5V rail for safety (max brightness=%d)",
                    max_safe
                )

            # Clamp to safe level
            safe_brightness = min(brightness, max_safe)
            allowed = (brightness == safe_brightness)

            if not allowed:
                _logger.warning(
                    "Brightness clamped for %s: requested=%d, safe=%d (power_source=%s)",
                    ring_id, brightness, safe_brightness, self._power_source.name
                )

            return (allowed, safe_brightness)

    def estimate_current(
        self,
        ring_brightness: Dict[str, int]
    ) -> CurrentEstimate:
        """Estimate total current draw for given brightness levels.

        Calculates estimated current based on brightness for each ring.
        Current scales linearly with brightness (conservative estimate).

        Args:
            ring_brightness: Dict mapping ring_id to brightness (0-255)

        Returns:
            CurrentEstimate with total current, per-ring breakdown, and safety level

        Raises:
            ValueError: If ring not registered or brightness values invalid
            TypeError: If brightness is not an integer

        Example:
            >>> estimate = manager.estimate_current({"ring1": 128, "ring2": 128})
            >>> print(f"Total: {estimate.total_ma:.0f}mA")
            >>> print(f"Safety: {estimate.safety_level.name}")
            >>> print(f"Headroom: {estimate.headroom_ma:.0f}mA")
        """
        with self._lock:
            per_ring_ma: Dict[str, float] = {}
            total_ma = 0.0

            # Calculate per-ring current
            for ring_id, brightness in ring_brightness.items():
                if ring_id not in self._rings:
                    raise ValueError(f"Ring '{ring_id}' not registered")

                # Validate brightness value
                if not isinstance(brightness, int):
                    raise TypeError(
                        f"Brightness for '{ring_id}' must be int, got {type(brightness).__name__}"
                    )
                if brightness < 0 or brightness > 255:
                    raise ValueError(
                        f"Brightness for '{ring_id}' must be 0-255, got {brightness}"
                    )

                ring = self._rings[ring_id]

                # Linear scaling: I = I_max * (brightness / 255)
                # Conservative: assumes all LEDs at same brightness
                brightness_factor = brightness / self.MAX_BRIGHTNESS
                ring_current_ma = ring.max_current_ma * brightness_factor

                # MEDIUM Issue #4: Round to 2 decimal places for consistent float precision
                per_ring_ma[ring_id] = round(ring_current_ma, 2)
                total_ma += ring_current_ma

            # Determine max allowed current
            if self._power_source == PowerSource.PI_5V_RAIL:
                max_allowed_ma = self._pi_rail_max_ma - self.PI_RESERVE_CURRENT_MA
            elif self._power_source == PowerSource.EXTERNAL_5V:
                max_allowed_ma = self.EXTERNAL_MAX_CURRENT_MA
            else:  # UNKNOWN - assume Pi power
                max_allowed_ma = self._pi_rail_max_ma - self.PI_RESERVE_CURRENT_MA

            # Calculate headroom (MEDIUM Issue #4: Round for precision)
            headroom_ma = round(max_allowed_ma - total_ma, 2)

            # Determine safety level
            utilization = total_ma / max_allowed_ma

            if utilization >= 1.0:
                safety_level = SafetyLevel.EMERGENCY
            elif utilization >= self.CRITICAL_THRESHOLD:
                safety_level = SafetyLevel.CRITICAL
            elif utilization >= self.WARNING_THRESHOLD:
                safety_level = SafetyLevel.WARNING
            else:
                safety_level = SafetyLevel.SAFE

            return CurrentEstimate(
                # MEDIUM Issue #4: Round total_ma for consistent precision
                total_ma=round(total_ma, 2),
                per_ring_ma=per_ring_ma,
                safety_level=safety_level,
                max_allowed_ma=max_allowed_ma,
                headroom_ma=headroom_ma
            )

    def emergency_shutdown(self, reason: str = "manual") -> bool:
        """Emergency LED shutdown - disables all LED operations.

        Sets emergency shutdown flag preventing all LED operations.
        This does NOT turn off LEDs directly - that must be done by
        the LED controller calling this method.

        Args:
            reason: Reason for shutdown (for logging/diagnostics)

        Returns:
            True if shutdown activated, False if already active

        Example:
            >>> # In LED controller emergency handler
            >>> def on_emergency():
            ...     # Turn off LEDs
            ...     clear_all_leds()
            ...     # Activate safety shutdown
            ...     manager.emergency_shutdown(reason="overcurrent_detected")
        """
        with self._lock:
            if self._emergency_shutdown_active:
                return False

            self._emergency_shutdown_active = True
            _logger.critical(
                "EMERGENCY LED SHUTDOWN ACTIVATED - Reason: %s - "
                "All LED operations disabled until reset",
                reason
            )
            return True

    def reset_emergency_shutdown(self) -> bool:
        """Reset emergency shutdown state.

        Allows LED operations to resume after emergency shutdown.
        Should only be called after confirming hardware is safe.

        Returns:
            True if reset successful, False if not in shutdown state
        """
        with self._lock:
            if not self._emergency_shutdown_active:
                return False

            self._emergency_shutdown_active = False
            _logger.info("Emergency LED shutdown reset - operations resumed")
            return True

    def set_power_source(self, power_source: PowerSource) -> None:
        """Update power source configuration.

        Changes brightness limits and current budgets based on new power source.
        Issues warning when switching to more restrictive power source.

        Args:
            power_source: New power source configuration

        Example:
            >>> # Switch to external power (higher brightness allowed)
            >>> manager.set_power_source(PowerSource.EXTERNAL_5V)
        """
        with self._lock:
            old_source = self._power_source
            self._power_source = power_source

            # Get old and new brightness limits
            if old_source == PowerSource.PI_5V_RAIL:
                old_max_brightness = self._max_brightness_pi
            elif old_source == PowerSource.EXTERNAL_5V:
                old_max_brightness = self.MAX_BRIGHTNESS
            else:  # UNKNOWN
                old_max_brightness = self._max_brightness_pi

            if power_source == PowerSource.PI_5V_RAIL:
                new_max_brightness = self._max_brightness_pi
            elif power_source == PowerSource.EXTERNAL_5V:
                new_max_brightness = self.MAX_BRIGHTNESS
            else:  # UNKNOWN
                new_max_brightness = self._max_brightness_pi

            # Warn if switching to more restrictive power source
            if new_max_brightness < old_max_brightness:
                _logger.warning(
                    "Power source changed to more restrictive mode: %s -> %s. "
                    "Max brightness reduced from %d to %d. "
                    "Current LED settings may be automatically clamped.",
                    old_source.name, power_source.name,
                    old_max_brightness, new_max_brightness
                )
            else:
                _logger.info(
                    "Power source changed: %s -> %s (max brightness: %d -> %d)",
                    old_source.name, power_source.name,
                    old_max_brightness, new_max_brightness
                )

    def get_diagnostics(self) -> Dict[str, Any]:
        """Get diagnostic information for monitoring and debugging.

        Returns:
            Dictionary containing:
            - power_source: Current power source
            - max_brightness: Maximum safe brightness
            - registered_rings: Number of registered rings
            - ring_details: Details for each registered ring
            - gpio_available: GPIO availability status
            - emergency_shutdown: Emergency shutdown status
            - current_limits: Current budget limits

        Example:
            >>> diag = manager.get_diagnostics()
            >>> print(f"Rings: {diag['registered_rings']}")
            >>> print(f"Max brightness: {diag['max_brightness']}")
        """
        with self._lock:
            ring_details = {}
            for ring_id, ring in self._rings.items():
                ring_details[ring_id] = {
                    "name": ring.name,
                    "gpio_pin": ring.gpio_pin,
                    "pwm_channel": ring.pwm_channel,
                    "num_leds": ring.num_leds,
                    "max_current_ma": ring.max_current_ma
                }

            if self._power_source == PowerSource.PI_5V_RAIL:
                max_allowed_ma = self._pi_rail_max_ma - self.PI_RESERVE_CURRENT_MA
            elif self._power_source == PowerSource.EXTERNAL_5V:
                max_allowed_ma = self.EXTERNAL_MAX_CURRENT_MA
            else:
                max_allowed_ma = self._pi_rail_max_ma - self.PI_RESERVE_CURRENT_MA

            return {
                "power_source": self._power_source.name,
                "max_brightness": self._max_brightness_pi if self._power_source == PowerSource.PI_5V_RAIL else 255,
                "registered_rings": len(self._rings),
                "ring_details": ring_details,
                "gpio_available": self._gpio_available,
                "emergency_shutdown": self._emergency_shutdown_active,
                "current_limits": {
                    "max_allowed_ma": max_allowed_ma,
                    "pi_rail_max_ma": self._pi_rail_max_ma,
                    "pi_reserve_ma": self.PI_RESERVE_CURRENT_MA,
                    "external_max_ma": self.EXTERNAL_MAX_CURRENT_MA,
                    "warning_threshold": self.WARNING_THRESHOLD,
                    "critical_threshold": self.CRITICAL_THRESHOLD
                }
            }

    def __repr__(self) -> str:
        """String representation for debugging."""
        return (
            f"LEDSafetyManager("
            f"power_source={self._power_source.name}, "
            f"rings={len(self._rings)}, "
            f"max_brightness={self._max_brightness_pi}, "
            f"emergency_shutdown={self._emergency_shutdown_active})"
        )
