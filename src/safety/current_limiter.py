"""Current Limiter for OpenDuck Mini V3 Servo Safety System.

This module provides current estimation, stall detection, and thermal protection
for MG90S servo motors controlled via PCA9685. Since the hardware lacks direct
current sensing, this module uses a model-based approach to estimate current
draw based on servo movement state.

Hardware Context:
    - MG90S micro servos (typical specs):
        * Idle current: ~15mA (holding position, no load)
        * No-load current: ~220mA (moving freely)
        * Stall current: ~900mA (blocked movement)
    - PCA9685 16-channel PWM driver
    - 2S LiPo battery (7.4V nominal)

Safety Features:
    1. Per-servo current estimation based on movement state
    2. Stall detection via position monitoring (300ms timeout)
    3. Thermal protection via duty cycle limiting (70% max)
    4. Soft current limits at 80% of hard limits

References:
    - config/safety_config.yaml for current thresholds
    - MG90S datasheet for current specifications

SAFETY CRITICAL: This module prevents servo damage and battery overcurrent.
Do not modify without thorough testing on actual hardware.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import TYPE_CHECKING, Any, Dict, Optional, Tuple

if TYPE_CHECKING:
    from ..drivers.servo.pca9685 import PCA9685Driver


class StallCondition(Enum):
    """Enumeration of servo stall detection states.

    The stall detection system uses a state machine approach:
    - NORMAL: Servo is operating normally
    - SUSPECTED: Position hasn't changed for partial timeout (150ms)
    - CONFIRMED: Position hasn't changed for full timeout (300ms)

    This two-stage approach reduces false positives from brief load spikes
    while still detecting genuine stall conditions quickly enough to prevent
    thermal damage.
    """
    NORMAL = auto()
    SUSPECTED = auto()
    CONFIRMED = auto()


@dataclass
class ServoCurrentProfile:
    """Current profile parameters for a servo motor.

    This dataclass encapsulates the electrical characteristics of a servo
    motor used for current estimation. Default values are calibrated for
    MG90S micro servos commonly used in small robotics projects.

    Attributes:
        idle_ma: Current draw when holding position with no external load.
            This represents the quiescent current of the servo electronics
            and motor holding torque current. Default: 15.0mA

        no_load_ma: Current draw during free movement without external load.
            This is the current required to overcome internal friction and
            accelerate the servo horn. Default: 220.0mA

        stall_ma: Maximum current draw when the servo is blocked and cannot
            reach its target position. This is the limiting factor for
            thermal protection. Default: 900.0mA

        thermal_time_constant_s: Time constant for thermal modeling.
            Represents how quickly the servo heats up under continuous
            stall current. Used to calculate safe duty cycles.
            Default: 30.0 seconds

    Example:
        >>> profile = ServoCurrentProfile()
        >>> profile.stall_ma
        900.0

        >>> custom = ServoCurrentProfile(stall_ma=1200.0)  # For larger servo
        >>> custom.stall_ma
        1200.0
    """
    idle_ma: float = 15.0
    no_load_ma: float = 220.0
    stall_ma: float = 900.0
    thermal_time_constant_s: float = 30.0

    def __post_init__(self):
        if self.idle_ma < 0 or self.no_load_ma < 0 or self.stall_ma < 0:
            raise ValueError("Current values must be non-negative")
        if self.idle_ma >= self.stall_ma:
            raise ValueError(f"idle_ma ({self.idle_ma}) must be less than stall_ma ({self.stall_ma})")
        if self.thermal_time_constant_s <= 0:
            raise ValueError(f"thermal_time_constant_s must be positive, got {self.thermal_time_constant_s}")


@dataclass
class _ChannelState:
    """Internal state tracking for a single servo channel.

    This class maintains all the state needed for current estimation,
    stall detection, and thermal protection for one servo channel.

    Attributes:
        is_moving: Whether the servo is currently commanded to move.
        target_angle: The target angle for the current movement (if any).
        last_position: Last known servo position (for stall detection).
        last_position_time: Timestamp when last_position was recorded.
        movement_start_time: When the current movement command was issued.
        stall_suspected_time: When position stopped changing (for timeout).
        stall_condition: Current stall detection state.
        cumulative_duty: Accumulated duty cycle for thermal tracking.
        last_duty_update: Last time duty cycle was updated.
    """
    is_moving: bool = False
    target_angle: Optional[float] = None
    last_position: Optional[float] = None
    last_position_time: Optional[float] = None
    movement_start_time: Optional[float] = None
    stall_suspected_time: Optional[float] = None
    stall_condition: StallCondition = field(default=StallCondition.NORMAL)
    cumulative_duty: float = 0.0
    last_duty_update: float = field(default_factory=time.monotonic)


class CurrentLimiter:
    """Current limiting and protection system for servo motors.

    This class provides a software-based current limiting system for servo
    motors controlled via PCA9685. Since the hardware lacks direct current
    sensing, it uses a model-based approach combining:

    1. Movement state tracking (idle vs moving)
    2. Stall detection via position monitoring
    3. Thermal modeling for duty cycle limiting

    The current estimation model for MG90S servos:
        I = idle + (stall - idle) * load_factor * movement_factor

    Where:
        - idle: Quiescent current (~15mA)
        - stall: Maximum blocked current (~900mA)
        - load_factor: 0.0 (no load) to 1.0 (full stall)
        - movement_factor: 0.0 (idle) to 1.0 (moving)

    Thread Safety:
        All public methods are thread-safe and can be called from multiple
        threads concurrently. Internal state is protected by a reentrant lock.

    Attributes:
        profile: ServoCurrentProfile with servo electrical characteristics.
        num_channels: Number of servo channels (default: 16 for PCA9685).
        stall_timeout_s: Time without position change to confirm stall.
        max_duty_cycle: Maximum allowed duty cycle for thermal protection.
        soft_limit_factor: Soft limit as fraction of hard limit.

    Example:
        >>> from src.drivers.servo.pca9685 import PCA9685Driver
        >>> driver = PCA9685Driver()
        >>> limiter = CurrentLimiter()
        >>>
        >>> # Before starting movement
        >>> allowed, reason = limiter.is_movement_allowed(channel=0)
        >>> if allowed:
        ...     limiter.register_movement_start(channel=0, target_angle=90.0)
        ...     driver.set_servo_angle(0, 90.0)
        ...
        >>> # After movement completes
        >>> limiter.register_movement_complete(channel=0)
        >>>
        >>> # Check for stall during movement
        >>> condition = limiter.check_stall(channel=0, target_angle=90.0)
        >>> if condition == StallCondition.CONFIRMED:
        ...     driver.disable_channel(0)
    """

    # Default configuration constants
    DEFAULT_NUM_CHANNELS: int = 16
    DEFAULT_STALL_TIMEOUT_S: float = 0.300  # 300ms
    DEFAULT_STALL_SUSPECTED_S: float = 0.150  # 150ms (half of timeout)
    DEFAULT_MAX_DUTY_CYCLE: float = 0.70  # 70% max for thermal protection
    DEFAULT_SOFT_LIMIT_FACTOR: float = 0.80  # Soft limit at 80% of hard limit

    # Position tolerance for stall detection (degrees)
    POSITION_TOLERANCE_DEG: float = 2.0

    # Thermal decay time constant (seconds)
    THERMAL_DECAY_TIME_S: float = 5.0

    # Load factors for current estimation model
    LOAD_FACTOR_NORMAL: float = 0.25  # Typical no-load movement
    LOAD_FACTOR_SUSPECTED: float = 0.60  # Increased resistance detected
    LOAD_FACTOR_STALL: float = 1.0  # Full stall current

    def __init__(
        self,
        profile: Optional[ServoCurrentProfile] = None,
        num_channels: int = DEFAULT_NUM_CHANNELS,
        stall_timeout_s: float = DEFAULT_STALL_TIMEOUT_S,
        max_duty_cycle: float = DEFAULT_MAX_DUTY_CYCLE,
        soft_limit_factor: float = DEFAULT_SOFT_LIMIT_FACTOR,
        pca_driver: Optional["PCA9685Driver"] = None,
    ) -> None:
        """Initialize the current limiter.

        Args:
            profile: Servo current profile. If None, uses default MG90S profile.
            num_channels: Number of servo channels to track (default: 16).
            stall_timeout_s: Time in seconds without position change to confirm
                stall condition (default: 0.300s = 300ms).
            max_duty_cycle: Maximum duty cycle allowed for thermal protection.
                Value between 0.0 and 1.0 (default: 0.70 = 70%).
            soft_limit_factor: Soft current limit as fraction of hard limit.
                Warnings are issued at this threshold (default: 0.80 = 80%).
            pca_driver: Optional PCA9685Driver instance for direct position
                queries. If None, position must be provided to check_stall().

        Raises:
            ValueError: If num_channels < 1, or if max_duty_cycle or
                soft_limit_factor are outside valid range [0.0, 1.0].
        """
        # Validate parameters
        if num_channels < 1:
            raise ValueError(f"num_channels must be >= 1, got {num_channels}")
        if not 0.0 <= max_duty_cycle <= 1.0:
            raise ValueError(
                f"max_duty_cycle must be in [0.0, 1.0], got {max_duty_cycle}"
            )
        if not 0.0 <= soft_limit_factor <= 1.0:
            raise ValueError(
                f"soft_limit_factor must be in [0.0, 1.0], got {soft_limit_factor}"
            )
        if stall_timeout_s <= 0:
            raise ValueError(f"stall_timeout_s must be positive, got {stall_timeout_s}")
        if num_channels > 256:
            raise ValueError(f"num_channels must be <= 256, got {num_channels}")

        # Store configuration
        self.profile = profile if profile is not None else ServoCurrentProfile()
        self.num_channels = num_channels
        self.stall_timeout_s = stall_timeout_s
        self.max_duty_cycle = max_duty_cycle
        self.soft_limit_factor = soft_limit_factor
        self._pca_driver = pca_driver

        # Initialize per-channel state
        self._channel_states: Dict[int, _ChannelState] = {
            ch: _ChannelState() for ch in range(num_channels)
        }

        # Thread safety lock (reentrant for nested calls)
        self._lock = threading.RLock()

    def estimate_current(self, channel: int) -> float:
        """Estimate current draw for a servo channel in milliamps.

        Uses the current estimation model based on movement state and
        stall condition:

            I = idle + (stall - idle) * load_factor * movement_factor

        Where:
            - movement_factor is 0.0 when idle, 1.0 when moving
            - load_factor depends on stall condition:
                * NORMAL: 0.25 (typical no-load movement)
                * SUSPECTED: 0.60 (increased load)
                * CONFIRMED: 1.0 (full stall)

        Args:
            channel: Servo channel number (0 to num_channels-1).

        Returns:
            Estimated current in milliamps (mA).

        Raises:
            ValueError: If channel is out of valid range.

        Example:
            >>> limiter = CurrentLimiter()
            >>> limiter.estimate_current(0)  # Idle servo
            15.0
            >>> limiter.register_movement_start(0, 90.0)
            >>> limiter.estimate_current(0)  # Moving servo
            236.25
        """
        self._validate_channel(channel)

        with self._lock:
            state = self._channel_states[channel]

            # Base case: idle servo
            if not state.is_moving:
                return self.profile.idle_ma

            # Determine load factor based on stall condition
            load_factor: float
            if state.stall_condition == StallCondition.NORMAL:
                # Normal movement: assume 25% of max load (typical no-load)
                load_factor = self.LOAD_FACTOR_NORMAL
            elif state.stall_condition == StallCondition.SUSPECTED:
                # Suspected stall: assume 60% load (increased resistance)
                load_factor = self.LOAD_FACTOR_SUSPECTED
            else:  # CONFIRMED
                # Confirmed stall: full stall current
                load_factor = self.LOAD_FACTOR_STALL

            # Movement factor is 1.0 since we know servo is moving
            movement_factor = 1.0

            # Calculate estimated current
            # I = idle + (stall - idle) * load_factor * movement_factor
            current_range = self.profile.stall_ma - self.profile.idle_ma
            estimated_ma = (
                self.profile.idle_ma +
                current_range * load_factor * movement_factor
            )

            return estimated_ma

    def get_total_current(self) -> float:
        """Get total estimated current across all servo channels.

        Sums the estimated current for all channels. This is useful for
        battery current budget monitoring and overall system power management.

        Returns:
            Total estimated current in milliamps (mA).

        Example:
            >>> limiter = CurrentLimiter(num_channels=4)
            >>> # All servos idle
            >>> limiter.get_total_current()
            60.0  # 4 * 15mA
            >>> # Start one servo moving
            >>> limiter.register_movement_start(0, 90.0)
            >>> limiter.get_total_current()
            281.25  # 236.25 + 3 * 15.0
        """
        with self._lock:
            return sum(
                self.estimate_current(ch)
                for ch in range(self.num_channels)
            )

    def check_stall(
        self,
        channel: int,
        target_angle: Optional[float] = None,
        current_position: Optional[float] = None,
    ) -> StallCondition:
        """Check for stall condition on a servo channel.

        Stall detection works by monitoring whether the servo position
        is changing while commanded to move. If position doesn't change
        for the stall timeout period, a stall is confirmed.

        The detection uses a two-stage state machine:
        1. NORMAL -> SUSPECTED: Position unchanged for 150ms
        2. SUSPECTED -> CONFIRMED: Position unchanged for 300ms total

        This approach reduces false positives from brief load spikes.

        Args:
            channel: Servo channel number (0 to num_channels-1).
            target_angle: Target angle the servo is trying to reach.
                If provided, updates the internal target tracking.
            current_position: Current servo position in degrees.
                If None and pca_driver was provided, queries the driver.
                If None and no driver, uses last known position.

        Returns:
            StallCondition indicating current stall detection state.

        Raises:
            ValueError: If channel is out of valid range.

        Example:
            >>> limiter = CurrentLimiter()
            >>> limiter.register_movement_start(0, 90.0)
            >>>
            >>> # During movement, check for stall
            >>> condition = limiter.check_stall(0, target_angle=90.0, current_position=45.0)
            >>> condition
            StallCondition.NORMAL
            >>>
            >>> # If position stuck at 45.0 for 300ms
            >>> time.sleep(0.3)
            >>> condition = limiter.check_stall(0, target_angle=90.0, current_position=45.0)
            >>> condition
            StallCondition.CONFIRMED
        """
        self._validate_channel(channel)

        with self._lock:
            state = self._channel_states[channel]
            now = time.monotonic()

            # Update target angle if provided
            if target_angle is not None:
                state.target_angle = target_angle

            # Get current position
            position = current_position
            if position is None and self._pca_driver is not None:
                # Try to get position from driver
                try:
                    channel_state = self._pca_driver.get_channel_state(channel)
                    position = channel_state.get('angle')
                except Exception:
                    position = None

            if position is None:
                position = state.last_position

            # If not moving, always NORMAL
            if not state.is_moving:
                state.stall_condition = StallCondition.NORMAL
                state.stall_suspected_time = None
                return StallCondition.NORMAL

            # If no target or position, cannot detect stall
            if state.target_angle is None or position is None:
                state.last_position = position
                return state.stall_condition

            # Check if position is close to target (movement complete)
            if abs(position - state.target_angle) < self.POSITION_TOLERANCE_DEG:
                state.stall_condition = StallCondition.NORMAL
                state.stall_suspected_time = None
                state.last_position = position
                return StallCondition.NORMAL

            # Check if position has changed since last check
            if state.last_position is not None:
                position_changed = abs(position - state.last_position) >= self.POSITION_TOLERANCE_DEG
            else:
                # First position reading - don't start stall timer yet
                # Just record position and wait for next reading
                state.last_position = position
                state.last_position_time = now
                return StallCondition.NORMAL

            if position_changed:
                # Position is changing, reset stall detection
                state.stall_condition = StallCondition.NORMAL
                state.stall_suspected_time = None
            else:
                # Position not changing (or first reading)
                if state.stall_suspected_time is None:
                    # Start the stall timer from when the last position was recorded
                    # This accounts for the time between calls where position was stuck
                    if state.last_position_time is not None:
                        state.stall_suspected_time = state.last_position_time
                    else:
                        state.stall_suspected_time = now

                # Check how long position has been stuck
                stuck_duration = now - state.stall_suspected_time

                # Calculate suspected threshold as 50% of configured stall timeout
                # This scales properly with custom stall_timeout_s values
                stall_suspected_threshold = self.stall_timeout_s * 0.5

                if stuck_duration >= self.stall_timeout_s:
                    state.stall_condition = StallCondition.CONFIRMED
                elif stuck_duration >= stall_suspected_threshold:
                    state.stall_condition = StallCondition.SUSPECTED
                else:
                    state.stall_condition = StallCondition.NORMAL

            # Update last position and timestamp
            state.last_position = position
            state.last_position_time = now

            return state.stall_condition

    def get_duty_cycle(self, channel: int) -> float:
        """Get allowed duty cycle for a servo channel.

        Returns a value between 0.0 and 1.0 indicating what fraction of
        time the servo should be allowed to draw current. This implements
        thermal protection by limiting continuous operation.

        The duty cycle is calculated based on:
        1. Base max duty cycle (default 70%)
        2. Current stall condition (reduced if stalled)
        3. Cumulative thermal load

        Args:
            channel: Servo channel number (0 to num_channels-1).

        Returns:
            Duty cycle between 0.0 (fully limited) and 1.0 (unlimited).
            The actual maximum is capped at max_duty_cycle (default 0.70).

        Raises:
            ValueError: If channel is out of valid range.

        Example:
            >>> limiter = CurrentLimiter()
            >>> limiter.get_duty_cycle(0)  # Idle servo
            0.7  # Full allowed duty cycle
            >>>
            >>> # If stall detected
            >>> limiter._channel_states[0].stall_condition = StallCondition.CONFIRMED
            >>> limiter.get_duty_cycle(0)
            0.35  # Reduced to 50% of max
        """
        self._validate_channel(channel)

        with self._lock:
            state = self._channel_states[channel]
            now = time.monotonic()

            # Update cumulative duty tracking
            time_delta = now - state.last_duty_update
            state.last_duty_update = now

            # Decay cumulative duty over time
            decay_factor = max(0.0, 1.0 - time_delta / self.THERMAL_DECAY_TIME_S)
            state.cumulative_duty *= decay_factor

            # If moving, accumulate duty
            if state.is_moving:
                # Weight by estimated load factor
                if state.stall_condition == StallCondition.CONFIRMED:
                    load_weight = 1.0
                elif state.stall_condition == StallCondition.SUSPECTED:
                    load_weight = 0.6
                else:
                    load_weight = 0.25

                state.cumulative_duty += time_delta * load_weight

            # Calculate allowed duty cycle
            base_duty = self.max_duty_cycle

            # Reduce duty cycle based on stall condition
            if state.stall_condition == StallCondition.CONFIRMED:
                # Severe reduction during confirmed stall
                base_duty *= 0.5
            elif state.stall_condition == StallCondition.SUSPECTED:
                # Moderate reduction during suspected stall
                base_duty *= 0.75

            # Further reduce based on thermal accumulation
            thermal_factor = max(
                0.0,
                1.0 - state.cumulative_duty / self.profile.thermal_time_constant_s
            )

            return base_duty * thermal_factor

    def is_movement_allowed(self, channel: int) -> Tuple[bool, str]:
        """Check if movement is allowed for a servo channel.

        This method implements the safety decision logic that determines
        whether a new movement command should be allowed. It checks:

        1. Duty cycle availability (thermal protection)
        2. Current stall condition
        3. Soft current limits

        Args:
            channel: Servo channel number (0 to num_channels-1).

        Returns:
            Tuple of (allowed: bool, reason: str).
            - If allowed is True, reason is empty string.
            - If allowed is False, reason explains why.

        Raises:
            ValueError: If channel is out of valid range.

        Example:
            >>> limiter = CurrentLimiter()
            >>> allowed, reason = limiter.is_movement_allowed(0)
            >>> allowed
            True
            >>> reason
            ''
            >>>
            >>> # After stall detected
            >>> limiter._channel_states[0].stall_condition = StallCondition.CONFIRMED
            >>> allowed, reason = limiter.is_movement_allowed(0)
            >>> allowed
            False
            >>> reason
            'Servo stall confirmed on channel 0 - clear obstruction before retrying'
        """
        self._validate_channel(channel)

        with self._lock:
            state = self._channel_states[channel]

            # Check 1: Confirmed stall blocks all movement
            if state.stall_condition == StallCondition.CONFIRMED:
                return (
                    False,
                    f"Servo stall confirmed on channel {channel} - "
                    "clear obstruction before retrying"
                )

            # Check 2: Duty cycle availability
            duty_cycle = self.get_duty_cycle(channel)
            min_duty_threshold = 0.1  # Minimum 10% duty cycle required

            if duty_cycle < min_duty_threshold:
                return (
                    False,
                    f"Thermal limit reached on channel {channel} - "
                    f"duty cycle {duty_cycle:.1%} below minimum {min_duty_threshold:.1%}"
                )

            # Check 3: Total system current (soft limit)
            total_current = self.get_total_current()
            # Add estimated current for this movement
            estimated_additional = self.profile.no_load_ma - self.profile.idle_ma
            projected_current = total_current + estimated_additional

            # Calculate soft limit (80% of max servo current * active channels)
            soft_limit_ma = (
                self.profile.stall_ma *
                self.num_channels *
                self.soft_limit_factor
            )

            if projected_current > soft_limit_ma:
                return (
                    False,
                    f"Current soft limit reached - projected {projected_current:.0f}mA "
                    f"exceeds soft limit {soft_limit_ma:.0f}mA"
                )

            # All checks passed
            return (True, "")

    def register_movement_start(
        self,
        channel: int,
        target_angle: float
    ) -> None:
        """Register the start of a servo movement.

        Call this method when commanding a servo to move to a new position.
        It updates the internal state for current estimation and stall
        detection.

        Args:
            channel: Servo channel number (0 to num_channels-1).
            target_angle: Target angle in degrees.

        Raises:
            ValueError: If channel is out of valid range.

        Example:
            >>> limiter = CurrentLimiter()
            >>> limiter.register_movement_start(0, 90.0)
            >>> limiter._channel_states[0].is_moving
            True
            >>> limiter._channel_states[0].target_angle
            90.0
        """
        self._validate_channel(channel)

        with self._lock:
            state = self._channel_states[channel]
            state.is_moving = True
            state.target_angle = target_angle
            state.movement_start_time = time.monotonic()
            state.stall_suspected_time = None
            state.stall_condition = StallCondition.NORMAL

    def register_movement_complete(self, channel: int) -> None:
        """Register the completion of a servo movement.

        Call this method when a servo has reached its target position or
        when the movement command is cancelled. It resets the movement
        state for accurate current estimation.

        Args:
            channel: Servo channel number (0 to num_channels-1).

        Raises:
            ValueError: If channel is out of valid range.

        Example:
            >>> limiter = CurrentLimiter()
            >>> limiter.register_movement_start(0, 90.0)
            >>> # ... movement happens ...
            >>> limiter.register_movement_complete(0)
            >>> limiter._channel_states[0].is_moving
            False
        """
        self._validate_channel(channel)

        with self._lock:
            state = self._channel_states[channel]
            state.is_moving = False
            state.movement_start_time = None
            state.stall_suspected_time = None
            state.stall_condition = StallCondition.NORMAL

    def reset_channel(self, channel: int) -> None:
        """Reset all state for a servo channel.

        This method clears all accumulated state including thermal
        tracking. Use after clearing a stall condition or performing
        maintenance.

        Args:
            channel: Servo channel number (0 to num_channels-1).

        Raises:
            ValueError: If channel is out of valid range.
        """
        self._validate_channel(channel)

        with self._lock:
            self._channel_states[channel] = _ChannelState()

    def reset_all_channels(self) -> None:
        """Reset all state for all servo channels.

        Clears all accumulated state including thermal tracking for
        all channels. Use during system initialization or after
        emergency stop.
        """
        with self._lock:
            for channel in range(self.num_channels):
                self._channel_states[channel] = _ChannelState()

    def get_channel_diagnostics(self, channel: int) -> Dict[str, Any]:
        """Get diagnostic information for a servo channel.

        Returns detailed state information useful for debugging and
        monitoring. This is intended for logging and diagnostic display,
        not for control decisions.

        Args:
            channel: Servo channel number (0 to num_channels-1).

        Returns:
            Dictionary containing:
            - estimated_current_ma: Current estimate in mA
            - is_moving: Whether servo is commanded to move
            - target_angle: Target position (if moving)
            - last_position: Last known position
            - stall_condition: Current stall detection state
            - duty_cycle: Current allowed duty cycle
            - cumulative_duty: Thermal accumulation value

        Raises:
            ValueError: If channel is out of valid range.
        """
        self._validate_channel(channel)

        with self._lock:
            state = self._channel_states[channel]

            return {
                "estimated_current_ma": self.estimate_current(channel),
                "is_moving": state.is_moving,
                "target_angle": state.target_angle,
                "last_position": state.last_position,
                "stall_condition": state.stall_condition.name,
                "duty_cycle": self.get_duty_cycle(channel),
                "cumulative_duty": state.cumulative_duty,
                "movement_start_time": state.movement_start_time,
                "stall_suspected_time": state.stall_suspected_time,
            }

    def get_system_diagnostics(self) -> Dict[str, Any]:
        """Get system-wide diagnostic information.

        Returns aggregate diagnostic data for the entire servo system.
        Useful for monitoring overall system health and current budget.

        Returns:
            Dictionary containing:
            - total_current_ma: Total estimated current across all channels
            - active_channels: Number of channels currently moving
            - stalled_channels: List of channels with confirmed stall
            - suspected_stall_channels: List of channels with suspected stall
            - thermal_limited_channels: List of channels with reduced duty cycle
        """
        with self._lock:
            active_channels = []
            stalled_channels = []
            suspected_channels = []
            thermal_limited = []

            for channel in range(self.num_channels):
                state = self._channel_states[channel]

                if state.is_moving:
                    active_channels.append(channel)

                if state.stall_condition == StallCondition.CONFIRMED:
                    stalled_channels.append(channel)
                elif state.stall_condition == StallCondition.SUSPECTED:
                    suspected_channels.append(channel)

                # Check if duty cycle is below 50% of max
                if self.get_duty_cycle(channel) < self.max_duty_cycle * 0.5:
                    thermal_limited.append(channel)

            return {
                "total_current_ma": self.get_total_current(),
                "active_channels": active_channels,
                "active_count": len(active_channels),
                "stalled_channels": stalled_channels,
                "suspected_stall_channels": suspected_channels,
                "thermal_limited_channels": thermal_limited,
                "profile": {
                    "idle_ma": self.profile.idle_ma,
                    "no_load_ma": self.profile.no_load_ma,
                    "stall_ma": self.profile.stall_ma,
                    "thermal_time_constant_s": self.profile.thermal_time_constant_s,
                },
            }

    def _validate_channel(self, channel: int) -> None:
        """Validate that a channel number is within valid range.

        Args:
            channel: Channel number to validate.

        Raises:
            ValueError: If channel is out of valid range.
        """
        if not 0 <= channel < self.num_channels:
            raise ValueError(
                f"Channel must be 0-{self.num_channels - 1}, got {channel}"
            )

    def __repr__(self) -> str:
        return (
            f"CurrentLimiter(num_channels={self.num_channels}, "
            f"stall_timeout_s={self.stall_timeout_s}, "
            f"max_duty_cycle={self.max_duty_cycle})"
        )
