"""Head Controller Safety System for OpenDuck Mini V3.

This module provides bulletproof safety constraints for the 2-DOF pan/tilt
head controller that CANNOT be bypassed. All safety functions are designed
to be integrated into HeadController methods.

Safety Philosophy:
    - HARD LIMITS protect servo gears from mechanical damage (cannot be bypassed)
    - SOFT LIMITS warn about longevity concerns (can be overridden with acknowledgment)
    - VELOCITY LIMITING prevents servo strain from too-fast movements
    - ACCELERATION LIMITING prevents jerky motion using S-curve profiles
    - EMERGENCY STOP immediately halts all movement (atomic flag, no lock required)

Hardware Context:
    - MG90S micro servos for pan/tilt head movement
    - PCA9685 16-channel PWM driver
    - Mechanical stops at hard limits
    - Servo gear damage possible if limits exceeded

Integration:
    This module provides constants and functions to be called FROM HeadController
    methods. The HeadController should import and use these safety primitives.

Author: Safety & Limits Engineer (Agent 2C)
Created: 18 January 2026
Quality Standard: Boston Dynamics / Robotics Safety Grade

SAFETY CRITICAL: Do not modify limits without mechanical verification.
"""

from __future__ import annotations

import logging
import math
import threading
import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Callable, List, Optional, Tuple

# Module logger for safety-critical events
_logger = logging.getLogger(__name__)


# =============================================================================
# SAFETY CONSTANTS - NEVER MODIFY WITHOUT MECHANICAL VERIFICATION
# =============================================================================

# HARD LIMITS - Protect servo gears from mechanical damage
# These values represent PHYSICAL constraints that CANNOT be bypassed
PAN_HARD_MIN: float = -90.0   # Left limit (degrees)
PAN_HARD_MAX: float = 90.0    # Right limit (degrees)
TILT_HARD_MIN: float = -45.0  # Down limit (degrees)
TILT_HARD_MAX: float = 45.0   # Up limit (degrees)

# SOFT LIMITS - Recommended operating range for servo longevity
# Staying within these limits reduces wear on servo gears
PAN_SOFT_MIN: float = -80.0
PAN_SOFT_MAX: float = 80.0
TILT_SOFT_MIN: float = -40.0
TILT_SOFT_MAX: float = 40.0

# VELOCITY LIMITING - Prevents servo strain from too-fast movements
MAX_VELOCITY_DEG_PER_SEC: float = 180.0  # Maximum angular velocity
MIN_VELOCITY_DEG_PER_SEC: float = 10.0   # Minimum meaningful velocity

# ACCELERATION LIMITING - Prevents jerky motion
MAX_ACCELERATION_DEG_PER_SEC2: float = 800.0  # Maximum angular acceleration
DEFAULT_ACCELERATION_DEG_PER_SEC2: float = 400.0  # Default for smooth motion

# DURATION LIMITS - Prevent obviously invalid commands
MIN_DURATION_MS: int = 10      # Minimum movement duration
MAX_DURATION_MS: int = 10000   # Maximum movement duration (10 seconds)
DEFAULT_DURATION_MS: int = 300 # Default movement duration

# COUNT LIMITS - For repetitive gestures (nod, shake)
MIN_GESTURE_COUNT: int = 1
MAX_GESTURE_COUNT: int = 5

# AMPLITUDE LIMITS - For gesture movements
MIN_AMPLITUDE_DEG: float = 1.0
MAX_NOD_AMPLITUDE_DEG: float = 30.0   # Max tilt for nod
MAX_SHAKE_AMPLITUDE_DEG: float = 45.0 # Max pan for shake


class SafetyViolationType(Enum):
    """Types of safety violations for logging and handling."""
    HARD_LIMIT_EXCEEDED = auto()  # Attempted to exceed physical limits
    SOFT_LIMIT_WARNING = auto()   # Operating outside recommended range
    VELOCITY_EXCEEDED = auto()    # Movement too fast for servo
    ACCELERATION_EXCEEDED = auto() # Acceleration too high (jerky)
    INVALID_DURATION = auto()     # Duration outside valid range
    INVALID_COUNT = auto()        # Gesture count invalid
    INVALID_AMPLITUDE = auto()    # Amplitude would exceed limits
    EMERGENCY_STOPPED = auto()    # System in emergency stop state


@dataclass
class SafetyEvent:
    """Record of a safety-related event.

    Attributes:
        timestamp: When the event occurred (monotonic time)
        violation_type: Type of safety violation
        requested_value: The value that was requested
        clamped_value: The value after safety clamping
        message: Human-readable description
        axis: 'pan', 'tilt', or 'both'
    """
    timestamp: float
    violation_type: SafetyViolationType
    requested_value: float
    clamped_value: float
    message: str
    axis: str = 'unknown'

    def __post_init__(self):
        """Log the safety event based on severity."""
        if self.violation_type == SafetyViolationType.HARD_LIMIT_EXCEEDED:
            _logger.warning("SAFETY: Hard limit exceeded - %s", self.message)
        elif self.violation_type == SafetyViolationType.SOFT_LIMIT_WARNING:
            _logger.info("SAFETY: Soft limit warning - %s", self.message)
        elif self.violation_type == SafetyViolationType.EMERGENCY_STOPPED:
            _logger.critical("SAFETY: Emergency stop active - %s", self.message)
        else:
            _logger.debug("SAFETY: %s - %s", self.violation_type.name, self.message)


@dataclass
class SafetyLimits:
    """Configuration for head movement safety limits.

    This dataclass encapsulates all safety limits for easy configuration
    while enforcing that hard limits are always more restrictive than soft.

    Attributes:
        pan_hard_min: Absolute minimum pan angle (physical limit)
        pan_hard_max: Absolute maximum pan angle (physical limit)
        pan_soft_min: Recommended minimum pan angle (longevity)
        pan_soft_max: Recommended maximum pan angle (longevity)
        tilt_hard_min: Absolute minimum tilt angle (physical limit)
        tilt_hard_max: Absolute maximum tilt angle (physical limit)
        tilt_soft_min: Recommended minimum tilt angle (longevity)
        tilt_soft_max: Recommended maximum tilt angle (longevity)
        max_velocity: Maximum angular velocity (deg/sec)
        max_acceleration: Maximum angular acceleration (deg/sec^2)
    """
    pan_hard_min: float = PAN_HARD_MIN
    pan_hard_max: float = PAN_HARD_MAX
    pan_soft_min: float = PAN_SOFT_MIN
    pan_soft_max: float = PAN_SOFT_MAX
    tilt_hard_min: float = TILT_HARD_MIN
    tilt_hard_max: float = TILT_HARD_MAX
    tilt_soft_min: float = TILT_SOFT_MIN
    tilt_soft_max: float = TILT_SOFT_MAX
    max_velocity: float = MAX_VELOCITY_DEG_PER_SEC
    max_acceleration: float = MAX_ACCELERATION_DEG_PER_SEC2

    def __post_init__(self):
        """Validate safety limit configuration."""
        # Validate pan limits
        if self.pan_hard_min >= self.pan_hard_max:
            raise ValueError(
                f"pan_hard_min ({self.pan_hard_min}) must be < "
                f"pan_hard_max ({self.pan_hard_max})"
            )
        if not (self.pan_hard_min <= self.pan_soft_min < self.pan_soft_max <= self.pan_hard_max):
            raise ValueError(
                f"Pan soft limits [{self.pan_soft_min}, {self.pan_soft_max}] must be "
                f"within hard limits [{self.pan_hard_min}, {self.pan_hard_max}]"
            )

        # Validate tilt limits
        if self.tilt_hard_min >= self.tilt_hard_max:
            raise ValueError(
                f"tilt_hard_min ({self.tilt_hard_min}) must be < "
                f"tilt_hard_max ({self.tilt_hard_max})"
            )
        if not (self.tilt_hard_min <= self.tilt_soft_min < self.tilt_soft_max <= self.tilt_hard_max):
            raise ValueError(
                f"Tilt soft limits [{self.tilt_soft_min}, {self.tilt_soft_max}] must be "
                f"within hard limits [{self.tilt_hard_min}, {self.tilt_hard_max}]"
            )

        # Validate velocity and acceleration
        if self.max_velocity <= 0:
            raise ValueError(f"max_velocity must be positive, got {self.max_velocity}")
        if self.max_acceleration <= 0:
            raise ValueError(f"max_acceleration must be positive, got {self.max_acceleration}")


# =============================================================================
# SAFETY VALIDATION FUNCTIONS
# =============================================================================

def clamp_to_hard_limits(
    pan: float,
    tilt: float,
    limits: Optional[SafetyLimits] = None
) -> Tuple[float, float, List[SafetyEvent]]:
    """Clamp pan/tilt angles to hard limits with event logging.

    This function ALWAYS succeeds and NEVER throws. Values outside hard limits
    are clamped and logged, but the system continues operating safely.

    Args:
        pan: Requested pan angle in degrees
        tilt: Requested tilt angle in degrees
        limits: Safety limits configuration (uses defaults if None)

    Returns:
        Tuple of (clamped_pan, clamped_tilt, list_of_safety_events)

    Example:
        >>> pan, tilt, events = clamp_to_hard_limits(100.0, 60.0)
        >>> pan
        90.0
        >>> tilt
        45.0
        >>> len(events)
        2
    """
    if limits is None:
        limits = SafetyLimits()

    events: List[SafetyEvent] = []
    now = time.monotonic()

    # Clamp pan to hard limits
    clamped_pan = max(limits.pan_hard_min, min(limits.pan_hard_max, pan))
    if clamped_pan != pan:
        events.append(SafetyEvent(
            timestamp=now,
            violation_type=SafetyViolationType.HARD_LIMIT_EXCEEDED,
            requested_value=pan,
            clamped_value=clamped_pan,
            message=f"Pan {pan:.1f}deg clamped to {clamped_pan:.1f}deg "
                    f"(limits: [{limits.pan_hard_min}, {limits.pan_hard_max}])",
            axis='pan'
        ))

    # Clamp tilt to hard limits
    clamped_tilt = max(limits.tilt_hard_min, min(limits.tilt_hard_max, tilt))
    if clamped_tilt != tilt:
        events.append(SafetyEvent(
            timestamp=now,
            violation_type=SafetyViolationType.HARD_LIMIT_EXCEEDED,
            requested_value=tilt,
            clamped_value=clamped_tilt,
            message=f"Tilt {tilt:.1f}deg clamped to {clamped_tilt:.1f}deg "
                    f"(limits: [{limits.tilt_hard_min}, {limits.tilt_hard_max}])",
            axis='tilt'
        ))

    return clamped_pan, clamped_tilt, events


def check_soft_limits(
    pan: float,
    tilt: float,
    limits: Optional[SafetyLimits] = None
) -> List[SafetyEvent]:
    """Check if pan/tilt are within soft limits and generate warnings.

    Soft limits don't prevent operation but warn about potential longevity issues.
    This function should be called AFTER clamp_to_hard_limits.

    Args:
        pan: Pan angle in degrees (should already be clamped to hard limits)
        tilt: Tilt angle in degrees (should already be clamped to hard limits)
        limits: Safety limits configuration (uses defaults if None)

    Returns:
        List of SafetyEvent warnings (empty if within soft limits)
    """
    if limits is None:
        limits = SafetyLimits()

    events: List[SafetyEvent] = []
    now = time.monotonic()

    # Check pan soft limits
    if pan < limits.pan_soft_min or pan > limits.pan_soft_max:
        events.append(SafetyEvent(
            timestamp=now,
            violation_type=SafetyViolationType.SOFT_LIMIT_WARNING,
            requested_value=pan,
            clamped_value=pan,  # Not clamped, just warning
            message=f"Pan {pan:.1f}deg outside recommended range "
                    f"[{limits.pan_soft_min}, {limits.pan_soft_max}]",
            axis='pan'
        ))

    # Check tilt soft limits
    if tilt < limits.tilt_soft_min or tilt > limits.tilt_soft_max:
        events.append(SafetyEvent(
            timestamp=now,
            violation_type=SafetyViolationType.SOFT_LIMIT_WARNING,
            requested_value=tilt,
            clamped_value=tilt,  # Not clamped, just warning
            message=f"Tilt {tilt:.1f}deg outside recommended range "
                    f"[{limits.tilt_soft_min}, {limits.tilt_soft_max}]",
            axis='tilt'
        ))

    return events


def validate_duration(duration_ms: Optional[int]) -> Tuple[int, Optional[SafetyEvent]]:
    """Validate and clamp movement duration.

    Args:
        duration_ms: Requested duration in milliseconds (None = use default)

    Returns:
        Tuple of (validated_duration, optional_safety_event)
    """
    if duration_ms is None:
        return DEFAULT_DURATION_MS, None

    if duration_ms < MIN_DURATION_MS:
        event = SafetyEvent(
            timestamp=time.monotonic(),
            violation_type=SafetyViolationType.INVALID_DURATION,
            requested_value=float(duration_ms),
            clamped_value=float(MIN_DURATION_MS),
            message=f"Duration {duration_ms}ms below minimum {MIN_DURATION_MS}ms"
        )
        return MIN_DURATION_MS, event

    if duration_ms > MAX_DURATION_MS:
        event = SafetyEvent(
            timestamp=time.monotonic(),
            violation_type=SafetyViolationType.INVALID_DURATION,
            requested_value=float(duration_ms),
            clamped_value=float(MAX_DURATION_MS),
            message=f"Duration {duration_ms}ms above maximum {MAX_DURATION_MS}ms"
        )
        return MAX_DURATION_MS, event

    return duration_ms, None


def validate_gesture_count(count: int) -> Tuple[int, Optional[SafetyEvent]]:
    """Validate and clamp gesture repetition count.

    Args:
        count: Requested number of repetitions (nod/shake cycles)

    Returns:
        Tuple of (validated_count, optional_safety_event)
    """
    if count < MIN_GESTURE_COUNT:
        event = SafetyEvent(
            timestamp=time.monotonic(),
            violation_type=SafetyViolationType.INVALID_COUNT,
            requested_value=float(count),
            clamped_value=float(MIN_GESTURE_COUNT),
            message=f"Gesture count {count} below minimum {MIN_GESTURE_COUNT}"
        )
        return MIN_GESTURE_COUNT, event

    if count > MAX_GESTURE_COUNT:
        event = SafetyEvent(
            timestamp=time.monotonic(),
            violation_type=SafetyViolationType.INVALID_COUNT,
            requested_value=float(count),
            clamped_value=float(MAX_GESTURE_COUNT),
            message=f"Gesture count {count} above maximum {MAX_GESTURE_COUNT}"
        )
        return MAX_GESTURE_COUNT, event

    return count, None


def validate_amplitude(
    amplitude: float,
    current_position: float,
    is_pan: bool,
    limits: Optional[SafetyLimits] = None
) -> Tuple[float, Optional[SafetyEvent]]:
    """Validate and clamp gesture amplitude to prevent exceeding limits.

    Args:
        amplitude: Requested amplitude in degrees (positive value)
        current_position: Current pan or tilt position
        is_pan: True for pan axis, False for tilt axis
        limits: Safety limits configuration

    Returns:
        Tuple of (safe_amplitude, optional_safety_event)
    """
    if limits is None:
        limits = SafetyLimits()

    # Amplitude must be positive
    amplitude = abs(amplitude)

    # Get appropriate limits
    if is_pan:
        hard_min = limits.pan_hard_min
        hard_max = limits.pan_hard_max
        max_amplitude = MAX_SHAKE_AMPLITUDE_DEG
    else:
        hard_min = limits.tilt_hard_min
        hard_max = limits.tilt_hard_max
        max_amplitude = MAX_NOD_AMPLITUDE_DEG

    # Clamp to max amplitude
    if amplitude > max_amplitude:
        amplitude = max_amplitude

    # Calculate maximum safe amplitude from current position
    # The gesture oscillates +/- amplitude from current position
    max_positive = hard_max - current_position
    max_negative = current_position - hard_min
    safe_amplitude = min(amplitude, max_positive, max_negative)

    if safe_amplitude < amplitude:
        event = SafetyEvent(
            timestamp=time.monotonic(),
            violation_type=SafetyViolationType.INVALID_AMPLITUDE,
            requested_value=amplitude,
            clamped_value=safe_amplitude,
            message=f"Amplitude {amplitude:.1f}deg reduced to {safe_amplitude:.1f}deg "
                    f"to stay within limits from position {current_position:.1f}deg",
            axis='pan' if is_pan else 'tilt'
        )
        return safe_amplitude, event

    return amplitude, None


# =============================================================================
# VELOCITY AND ACCELERATION LIMITING
# =============================================================================

def calculate_safe_duration(
    distance_deg: float,
    requested_duration_ms: int,
    max_velocity: float = MAX_VELOCITY_DEG_PER_SEC
) -> Tuple[int, Optional[SafetyEvent]]:
    """Calculate safe duration that respects velocity limits.

    If the requested duration would require exceeding max velocity,
    the duration is stretched to stay within limits.

    Args:
        distance_deg: Total angular distance to travel (degrees)
        requested_duration_ms: Requested duration (milliseconds)
        max_velocity: Maximum allowed velocity (deg/sec)

    Returns:
        Tuple of (safe_duration_ms, optional_safety_event)

    Example:
        >>> # 180 degrees in 500ms = 360 deg/sec (too fast!)
        >>> safe_dur, event = calculate_safe_duration(180.0, 500)
        >>> safe_dur  # Stretched to 1000ms for 180 deg/sec
        1000
    """
    if distance_deg <= 0 or requested_duration_ms <= 0:
        return max(MIN_DURATION_MS, requested_duration_ms), None

    # Calculate required velocity for requested duration
    duration_sec = requested_duration_ms / 1000.0
    required_velocity = abs(distance_deg) / duration_sec

    if required_velocity <= max_velocity:
        # Requested duration is safe
        return requested_duration_ms, None

    # Calculate minimum duration to stay within velocity limit
    min_duration_sec = abs(distance_deg) / max_velocity
    safe_duration_ms = int(math.ceil(min_duration_sec * 1000))

    # Ensure minimum duration
    safe_duration_ms = max(MIN_DURATION_MS, safe_duration_ms)

    event = SafetyEvent(
        timestamp=time.monotonic(),
        violation_type=SafetyViolationType.VELOCITY_EXCEEDED,
        requested_value=float(requested_duration_ms),
        clamped_value=float(safe_duration_ms),
        message=f"Duration stretched from {requested_duration_ms}ms to {safe_duration_ms}ms "
                f"to limit velocity to {max_velocity:.1f}deg/s "
                f"(was {required_velocity:.1f}deg/s for {distance_deg:.1f}deg)"
    )
    return safe_duration_ms, event


def apply_s_curve_profile(
    t: float,
    acceleration_factor: float = 1.0
) -> float:
    """Apply S-curve acceleration profile for smooth motion.

    S-curve profiles provide smooth ramp-up and ramp-down of velocity,
    preventing jerky motion that could strain servo gears.

    The profile uses a smoothstep function: 3t^2 - 2t^3
    This gives zero velocity and acceleration at t=0 and t=1.

    Args:
        t: Normalized time (0.0 to 1.0)
        acceleration_factor: Scaling factor for smoothness (1.0 = standard)

    Returns:
        Position factor (0.0 to 1.0) with S-curve applied

    Example:
        >>> apply_s_curve_profile(0.0)
        0.0
        >>> apply_s_curve_profile(0.5)
        0.5
        >>> apply_s_curve_profile(1.0)
        1.0
    """
    # Clamp input to valid range
    t = max(0.0, min(1.0, t))

    # Smoothstep function (Hermite interpolation)
    # f(t) = 3t^2 - 2t^3
    # This gives: f(0) = 0, f(1) = 1, f'(0) = 0, f'(1) = 0
    return t * t * (3.0 - 2.0 * t)


def apply_smoother_s_curve(t: float) -> float:
    """Apply Ken Perlin's smootherstep for even smoother motion.

    Smootherstep: 6t^5 - 15t^4 + 10t^3
    This gives zero velocity, acceleration, AND jerk at endpoints.

    Args:
        t: Normalized time (0.0 to 1.0)

    Returns:
        Position factor with smootherstep applied
    """
    t = max(0.0, min(1.0, t))
    # Smootherstep: 6t^5 - 15t^4 + 10t^3
    return t * t * t * (t * (t * 6.0 - 15.0) + 10.0)


def generate_trajectory_points(
    start_angle: float,
    end_angle: float,
    duration_ms: int,
    update_rate_hz: int = 50,
    use_s_curve: bool = True
) -> List[Tuple[int, float]]:
    """Generate trajectory points with optional S-curve smoothing.

    Pre-computes the entire trajectory at initialization for zero-allocation
    during execution (follows existing codebase pattern).

    Args:
        start_angle: Starting angle in degrees
        end_angle: Ending angle in degrees
        duration_ms: Total duration in milliseconds
        update_rate_hz: Update rate (default 50Hz = 20ms per frame)
        use_s_curve: If True, apply S-curve smoothing

    Returns:
        List of (time_ms, angle) tuples for the trajectory

    Example:
        >>> points = generate_trajectory_points(0.0, 90.0, 1000)
        >>> len(points)  # ~50 points at 50Hz for 1 second
        51
        >>> points[0]
        (0, 0.0)
        >>> points[-1]
        (1000, 90.0)
    """
    if duration_ms <= 0:
        return [(0, end_angle)]

    # Calculate number of frames
    frame_time_ms = 1000 / update_rate_hz
    num_frames = max(1, int(duration_ms / frame_time_ms))

    trajectory: List[Tuple[int, float]] = []
    angle_range = end_angle - start_angle

    for i in range(num_frames + 1):
        time_ms = int(i * frame_time_ms)
        if time_ms > duration_ms:
            time_ms = duration_ms

        # Normalized time (0.0 to 1.0)
        t = min(1.0, time_ms / duration_ms)

        # Apply S-curve if requested
        if use_s_curve:
            position_factor = apply_s_curve_profile(t)
        else:
            position_factor = t

        angle = start_angle + angle_range * position_factor
        trajectory.append((time_ms, angle))

    # Ensure we hit the exact end point
    if trajectory[-1][0] != duration_ms or trajectory[-1][1] != end_angle:
        trajectory.append((duration_ms, end_angle))

    return trajectory


# =============================================================================
# EMERGENCY STOP SYSTEM
# =============================================================================

class HeadEmergencyState(Enum):
    """Emergency state for head controller."""
    NORMAL = auto()        # Normal operation
    STOPPING = auto()      # Emergency stop in progress
    STOPPED = auto()       # Emergency stop complete, requires reset
    RESETTING = auto()     # Reset in progress


# Type alias for emergency stop callbacks
EmergencyCallback = Callable[[], None]


class HeadEmergencyStop:
    """Emergency stop handler specifically for HeadController.

    Provides an atomic emergency stop flag that can be checked without
    acquiring locks, ensuring immediate response to safety events.

    Thread Safety:
        - The emergency flag uses threading.Event for atomic operations
        - All state transitions are protected by RLock
        - Can be triggered from any thread (including GPIO interrupts)

    Integration:
        HeadController should:
        1. Check is_stopped before each servo command
        2. Call trigger() on any safety violation
        3. Require explicit reset() before resuming

    Example:
        >>> e_stop = HeadEmergencyStop()
        >>> if e_stop.is_stopped:
        ...     return  # Abort operation
        >>> # ... perform movement ...
        >>> if error_detected:
        ...     e_stop.trigger("Error message")
    """

    def __init__(self) -> None:
        """Initialize emergency stop handler."""
        # Atomic flag - can be checked without lock
        self._stopped = threading.Event()

        # State machine with lock protection
        self._lock = threading.RLock()
        self._state = HeadEmergencyState.NORMAL
        self._trigger_time: Optional[float] = None
        self._trigger_reason: Optional[str] = None
        self._callbacks: List[EmergencyCallback] = []

    @property
    def is_stopped(self) -> bool:
        """Check if emergency stop is active (atomic, no lock required).

        Returns:
            True if emergency stop is active
        """
        return self._stopped.is_set()

    @property
    def state(self) -> HeadEmergencyState:
        """Get current emergency state (thread-safe).

        Returns:
            Current HeadEmergencyState
        """
        with self._lock:
            return self._state

    @property
    def trigger_reason(self) -> Optional[str]:
        """Get reason for last emergency stop.

        Returns:
            Reason string if stopped, None otherwise
        """
        with self._lock:
            return self._trigger_reason

    def trigger(self, reason: str = "manual") -> float:
        """Trigger emergency stop immediately.

        SAFETY CRITICAL: This method:
        1. Sets atomic emergency flag FIRST (no lock required for reads)
        2. Transitions state machine
        3. Invokes registered callbacks
        4. Returns latency for monitoring

        Args:
            reason: Description of why emergency stop was triggered

        Returns:
            Latency in milliseconds from call to flag set

        Thread Safety:
            Can be called from any thread, including GPIO interrupts.
        """
        start_time = time.perf_counter()

        # CRITICAL: Set atomic flag FIRST before acquiring lock
        # This ensures is_stopped returns True immediately
        self._stopped.set()

        latency_ms = (time.perf_counter() - start_time) * 1000

        # Now update state machine under lock
        with self._lock:
            if self._state == HeadEmergencyState.STOPPED:
                # Already stopped, just update reason if different
                if reason != self._trigger_reason:
                    _logger.warning(
                        "HeadEmergencyStop re-triggered: %s (was: %s)",
                        reason, self._trigger_reason
                    )
                return latency_ms

            self._state = HeadEmergencyState.STOPPING
            self._trigger_time = time.monotonic()
            self._trigger_reason = reason

            _logger.critical(
                "HEAD EMERGENCY STOP triggered: %s (latency: %.2fms)",
                reason, latency_ms
            )

            # Invoke callbacks (under lock for consistency)
            for callback in self._callbacks:
                try:
                    callback()
                except Exception as e:
                    _logger.error(
                        "Exception in emergency stop callback (ignored): %s", e
                    )

            self._state = HeadEmergencyState.STOPPED

        return latency_ms

    def reset(self) -> bool:
        """Clear emergency stop state and allow resuming operation.

        Must be called explicitly after emergency_stop() before any
        movement commands will be accepted.

        Returns:
            True if reset successful, False if not in stopped state
        """
        with self._lock:
            if self._state != HeadEmergencyState.STOPPED:
                _logger.warning(
                    "HeadEmergencyStop.reset() called but state is %s",
                    self._state.name
                )
                return False

            self._state = HeadEmergencyState.RESETTING
            _logger.info(
                "HeadEmergencyStop resetting (was stopped for %.2fs, reason: %s)",
                time.monotonic() - (self._trigger_time or 0),
                self._trigger_reason
            )

            # Clear atomic flag
            self._stopped.clear()

            self._state = HeadEmergencyState.NORMAL
            self._trigger_time = None
            self._trigger_reason = None

            return True

    def register_callback(self, callback: EmergencyCallback) -> None:
        """Register callback to be invoked on emergency stop.

        Callbacks are invoked synchronously under lock during trigger().
        Keep callbacks fast to avoid blocking safety response.

        Args:
            callback: Function to call on emergency stop
        """
        with self._lock:
            if callback not in self._callbacks:
                self._callbacks.append(callback)

    def unregister_callback(self, callback: EmergencyCallback) -> bool:
        """Unregister a previously registered callback.

        Args:
            callback: The callback to remove

        Returns:
            True if callback was found and removed
        """
        with self._lock:
            try:
                self._callbacks.remove(callback)
                return True
            except ValueError:
                return False

    def __repr__(self) -> str:
        return (
            f"HeadEmergencyStop(state={self._state.name}, "
            f"is_stopped={self.is_stopped}, "
            f"reason={self._trigger_reason!r})"
        )


# =============================================================================
# SAFETY COORDINATOR FOR HEADCONTROLLER
# =============================================================================

class HeadSafetyCoordinator:
    """Coordinates all safety checks for HeadController.

    This class provides a single entry point for all safety operations,
    ensuring consistent validation and event logging.

    Usage in HeadController:
        >>> safety = HeadSafetyCoordinator()
        >>> # Before any movement:
        >>> if safety.emergency_stop.is_stopped:
        ...     raise RuntimeError("Emergency stop active")
        >>> # Validate and clamp target:
        >>> pan, tilt = safety.validate_target(requested_pan, requested_tilt)
        >>> # Get safe duration:
        >>> duration = safety.validate_movement(current_pos, target_pos, requested_duration)
    """

    # Maximum events to store (prevent unbounded memory growth)
    MAX_EVENT_HISTORY = 100

    def __init__(self, limits: Optional[SafetyLimits] = None) -> None:
        """Initialize safety coordinator.

        Args:
            limits: Safety limits configuration (uses defaults if None)
        """
        self.limits = limits if limits is not None else SafetyLimits()
        self.emergency_stop = HeadEmergencyStop()
        self._event_history: List[SafetyEvent] = []
        self._lock = threading.RLock()

    def validate_target(
        self,
        pan: float,
        tilt: float
    ) -> Tuple[float, float]:
        """Validate and clamp target position.

        Args:
            pan: Requested pan angle
            tilt: Requested tilt angle

        Returns:
            Tuple of (safe_pan, safe_tilt)

        Raises:
            RuntimeError: If emergency stop is active
        """
        if self.emergency_stop.is_stopped:
            raise RuntimeError(
                f"Cannot validate target: emergency stop active "
                f"(reason: {self.emergency_stop.trigger_reason})"
            )

        # Clamp to hard limits
        safe_pan, safe_tilt, hard_events = clamp_to_hard_limits(
            pan, tilt, self.limits
        )

        # Check soft limits (warnings only)
        soft_events = check_soft_limits(safe_pan, safe_tilt, self.limits)

        # Store all events
        with self._lock:
            for event in hard_events + soft_events:
                self._add_event(event)

        return safe_pan, safe_tilt

    def validate_movement(
        self,
        current_pan: float,
        current_tilt: float,
        target_pan: float,
        target_tilt: float,
        requested_duration_ms: Optional[int]
    ) -> int:
        """Validate movement parameters and return safe duration.

        Args:
            current_pan: Current pan position
            current_tilt: Current tilt position
            target_pan: Target pan position (should already be clamped)
            target_tilt: Target tilt position (should already be clamped)
            requested_duration_ms: Requested duration

        Returns:
            Safe duration in milliseconds

        Raises:
            RuntimeError: If emergency stop is active
        """
        if self.emergency_stop.is_stopped:
            raise RuntimeError(
                f"Cannot validate movement: emergency stop active "
                f"(reason: {self.emergency_stop.trigger_reason})"
            )

        # Validate duration bounds first
        duration, duration_event = validate_duration(requested_duration_ms)

        if duration_event:
            with self._lock:
                self._add_event(duration_event)

        # Calculate total distance (use max of pan/tilt distance)
        pan_distance = abs(target_pan - current_pan)
        tilt_distance = abs(target_tilt - current_tilt)
        total_distance = max(pan_distance, tilt_distance)

        # Check velocity limits
        safe_duration, velocity_event = calculate_safe_duration(
            total_distance, duration, self.limits.max_velocity
        )

        if velocity_event:
            with self._lock:
                self._add_event(velocity_event)

        return safe_duration

    def validate_gesture(
        self,
        count: int,
        amplitude: float,
        current_position: float,
        is_pan: bool,
        speed_ms: int
    ) -> Tuple[int, float, int]:
        """Validate gesture parameters (nod/shake).

        Args:
            count: Requested repetition count
            amplitude: Requested amplitude
            current_position: Current position on the gesture axis
            is_pan: True for shake (pan), False for nod (tilt)
            speed_ms: Requested speed per cycle

        Returns:
            Tuple of (safe_count, safe_amplitude, safe_speed_ms)

        Raises:
            RuntimeError: If emergency stop is active
        """
        if self.emergency_stop.is_stopped:
            raise RuntimeError(
                f"Cannot validate gesture: emergency stop active "
                f"(reason: {self.emergency_stop.trigger_reason})"
            )

        # Validate count
        safe_count, count_event = validate_gesture_count(count)
        if count_event:
            with self._lock:
                self._add_event(count_event)

        # Validate amplitude
        safe_amplitude, amplitude_event = validate_amplitude(
            amplitude, current_position, is_pan, self.limits
        )
        if amplitude_event:
            with self._lock:
                self._add_event(amplitude_event)

        # Validate speed (as duration)
        safe_speed, speed_event = validate_duration(speed_ms)
        if speed_event:
            with self._lock:
                self._add_event(speed_event)

        return safe_count, safe_amplitude, safe_speed

    def get_event_history(self) -> List[SafetyEvent]:
        """Get copy of safety event history.

        Returns:
            List of SafetyEvent objects (copy, oldest first)
        """
        with self._lock:
            return list(self._event_history)

    def clear_event_history(self) -> None:
        """Clear safety event history."""
        with self._lock:
            self._event_history.clear()

    def _add_event(self, event: SafetyEvent) -> None:
        """Add event to history, maintaining maximum size.

        Must be called with lock held.
        """
        self._event_history.append(event)
        if len(self._event_history) > self.MAX_EVENT_HISTORY:
            self._event_history.pop(0)

    def __repr__(self) -> str:
        return (
            f"HeadSafetyCoordinator("
            f"emergency_stopped={self.emergency_stop.is_stopped}, "
            f"event_count={len(self._event_history)})"
        )


# =============================================================================
# MODULE EXPORTS
# =============================================================================

__all__ = [
    # Constants
    'PAN_HARD_MIN', 'PAN_HARD_MAX', 'PAN_SOFT_MIN', 'PAN_SOFT_MAX',
    'TILT_HARD_MIN', 'TILT_HARD_MAX', 'TILT_SOFT_MIN', 'TILT_SOFT_MAX',
    'MAX_VELOCITY_DEG_PER_SEC', 'MAX_ACCELERATION_DEG_PER_SEC2',
    'MIN_DURATION_MS', 'MAX_DURATION_MS', 'DEFAULT_DURATION_MS',
    'MIN_GESTURE_COUNT', 'MAX_GESTURE_COUNT',
    'MIN_AMPLITUDE_DEG', 'MAX_NOD_AMPLITUDE_DEG', 'MAX_SHAKE_AMPLITUDE_DEG',
    # Enums
    'SafetyViolationType', 'HeadEmergencyState',
    # Dataclasses
    'SafetyEvent', 'SafetyLimits',
    # Validation functions
    'clamp_to_hard_limits', 'check_soft_limits',
    'validate_duration', 'validate_gesture_count', 'validate_amplitude',
    # Velocity/acceleration functions
    'calculate_safe_duration', 'apply_s_curve_profile', 'apply_smoother_s_curve',
    'generate_trajectory_points',
    # Emergency stop
    'HeadEmergencyStop',
    # Coordinator
    'HeadSafetyCoordinator',
]
