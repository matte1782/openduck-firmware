#!/usr/bin/env python3
"""
HeadController - 2-DOF Pan/Tilt Head Control with Disney Animation Principles

Provides smooth, expressive head movements for the OpenDuck Mini V3 robot
using the 12 Disney Animation Principles for natural, appealing motion.

Disney 12 Principles Applied:
---------------------------------------------------------------------------
1. SQUASH & STRETCH: Timing compression before extension movements
2. ANTICIPATION: Slight opposite movement before major actions
3. STAGING: Clear, readable poses at all times
4. POSE TO POSE: Pre-computed keyframes for predictable motion
5. FOLLOW THROUGH: Movement continues slightly after reaching target
6. SLOW IN / SLOW OUT: Easing functions for natural acceleration
7. ARCS: Natural curved motion paths for organic feel
8. SECONDARY ACTION: Subtle supporting movements (tilt with pan)
9. TIMING: Speed conveys weight and emotion
10. EXAGGERATION: Push poses for clarity (first shake larger)
11. SOLID DRAWING: N/A for servo control
12. APPEAL: Personality and natural variation in every movement

Architecture:
- Keyframe-based animation with pre-computed trajectories
- 50Hz update rate (20ms per frame) for smooth motion
- Thread-safe using RLock for concurrent access
- Emergency stop always available via atomic flag

Author: Agent 2B - Disney Animation Engineer
Created: 18 January 2026
Quality Standard: Pixar Character TD / Disney Animation Grade
"""

from dataclasses import dataclass, field
from typing import Optional, Tuple, Callable, List, Dict, Any
from enum import Enum
import logging
import threading
import time
import math
import random

# FIX H-004: Use relative import for better portability
from ..animation.easing import ease, EASING_LUTS

# Logger for this module
_logger = logging.getLogger(__name__)


# =============================================================================
# CONSTANTS
# =============================================================================

# Animation timing
UPDATE_RATE_HZ = 50  # 50Hz = 20ms per frame
FRAME_TIME_MS = 1000 // UPDATE_RATE_HZ  # 20ms
FRAME_TIME_S = 1.0 / UPDATE_RATE_HZ  # 0.02s

# Disney principle constants
ANTICIPATION_RATIO = 0.10  # 10% of amplitude for anticipation movement
FOLLOW_THROUGH_OVERSHOOT = 0.05  # 5% overshoot before settling
FOLLOW_THROUGH_SETTLE_MS = 100  # Time to settle after overshoot
FIRST_SHAKE_EXAGGERATION = 1.10  # First shake is 110% amplitude
SHAKE_DECAY_FACTOR = 0.90  # Each subsequent shake decays by 10%
SECONDARY_TILT_RATIO = 0.15  # Slight tilt (15%) accompanying pan movements
TIMING_ASYMMETRY_RATIO = 0.6  # Nod: 60% time going down, 40% coming up


# =============================================================================
# DATA STRUCTURES
# =============================================================================

class HeadMovementType(Enum):
    """Types of head movements for animation coordination.

    Used to identify the current movement for:
    - Callback notifications
    - Movement cancellation
    - Animation coordination with other systems
    """
    LOOK = "look"           # Direct pan/tilt positioning
    NOD = "nod"             # Vertical affirmation
    SHAKE = "shake"         # Horizontal negation
    TILT = "tilt"           # Curious head tilt
    GLANCE = "glance"       # Quick look and return
    RESET = "reset"         # Return to center


@dataclass
class HeadLimits:
    """Hardware limits for head servos.

    All angles in degrees. Center position is 0.0 for both axes.
    Positive pan = right, negative pan = left.
    Positive tilt = up, negative tilt = down.

    Attributes:
        pan_min: Minimum pan angle (negative = left)
        pan_max: Maximum pan angle (positive = right)
        tilt_min: Minimum tilt angle (negative = down)
        tilt_max: Maximum tilt angle (positive = up)
        pan_center: Center/home position for pan (usually 0.0)
        tilt_center: Center/home position for tilt (usually 0.0)

    Example:
        >>> limits = HeadLimits(pan_min=-90, pan_max=90, tilt_min=-45, tilt_max=45)
        >>> limits.pan_center
        0.0
    """
    pan_min: float = -90.0
    pan_max: float = 90.0
    tilt_min: float = -45.0
    tilt_max: float = 45.0
    pan_center: float = 0.0
    tilt_center: float = 0.0

    def __post_init__(self):
        """Validate limit configuration."""
        if self.pan_min >= self.pan_max:
            raise ValueError(f"pan_min ({self.pan_min}) must be < pan_max ({self.pan_max})")
        if self.tilt_min >= self.tilt_max:
            raise ValueError(f"tilt_min ({self.tilt_min}) must be < tilt_max ({self.tilt_max})")
        if not (self.pan_min <= self.pan_center <= self.pan_max):
            raise ValueError(f"pan_center ({self.pan_center}) must be within pan limits")
        if not (self.tilt_min <= self.tilt_center <= self.tilt_max):
            raise ValueError(f"tilt_center ({self.tilt_center}) must be within tilt limits")


@dataclass
class HeadConfig:
    """Configuration for HeadController.

    Attributes:
        pan_channel: PCA9685 channel for pan servo (0-15)
        tilt_channel: PCA9685 channel for tilt servo (0-15)
        limits: HeadLimits instance defining movement bounds
        pan_inverted: If True, invert pan servo direction
        tilt_inverted: If True, invert tilt servo direction
        default_speed_ms: Default movement duration in milliseconds
        easing: Default easing function name ('ease_in_out', 'ease_in', etc.)

    Example:
        >>> config = HeadConfig(pan_channel=12, tilt_channel=13)
        >>> config.default_speed_ms
        300
    """
    pan_channel: int
    tilt_channel: int
    limits: HeadLimits = field(default_factory=HeadLimits)
    pan_inverted: bool = False
    tilt_inverted: bool = False
    default_speed_ms: int = 300
    easing: str = 'ease_in_out'

    def __post_init__(self):
        """Validate configuration."""
        if not (0 <= self.pan_channel <= 15):
            raise ValueError(f"pan_channel must be 0-15, got {self.pan_channel}")
        if not (0 <= self.tilt_channel <= 15):
            raise ValueError(f"tilt_channel must be 0-15, got {self.tilt_channel}")
        if self.pan_channel == self.tilt_channel:
            raise ValueError(f"pan_channel and tilt_channel must differ, both are {self.pan_channel}")
        if self.default_speed_ms <= 0:
            raise ValueError(f"default_speed_ms must be > 0, got {self.default_speed_ms}")
        if self.easing not in EASING_LUTS:
            raise ValueError(f"Unknown easing type: {self.easing}. Valid: {list(EASING_LUTS.keys())}")


@dataclass
class HeadState:
    """Current state of the head position.

    Immutable snapshot of head state for reading current position.

    Attributes:
        pan: Current pan angle in degrees
        tilt: Current tilt angle in degrees
        is_moving: True if head is currently in motion
        target_pan: Target pan angle (if moving)
        target_tilt: Target tilt angle (if moving)
        movement_type: Current movement type (if moving)
    """
    pan: float
    tilt: float
    is_moving: bool = False
    target_pan: Optional[float] = None
    target_tilt: Optional[float] = None
    movement_type: Optional[HeadMovementType] = None


@dataclass
class _Keyframe:
    """Internal keyframe for animation trajectory.

    Pre-computed position at a specific time for pose-to-pose animation.

    Attributes:
        time_ms: Time offset from animation start
        pan: Pan angle at this keyframe
        tilt: Tilt angle at this keyframe
        easing: Easing function for interpolation TO this keyframe
    """
    time_ms: int
    pan: float
    tilt: float
    easing: str = 'ease_in_out'


# =============================================================================
# HEAD CONTROLLER CLASS
# =============================================================================

class HeadController:
    """2-DOF pan/tilt head controller with expressive movements.

    Provides smooth, animation-quality head movements with:
    - Direct positioning (look_at)
    - Expressive gestures (nod, shake, glance, tilt)
    - Emergency stop capability
    - Thread-safe operation

    Disney Animation Principles Applied:
    ------------------------------------
    - ANTICIPATION: Slight opposite movement before major motion
      (nod starts with small upward, shake starts opposite direction)
    - FOLLOW-THROUGH: Natural settling at end of motion
      (5% overshoot then ease back to target)
    - TIMING: Easing functions for natural acceleration/deceleration
      (ease_in_out by default, asymmetric timing for nods)
    - SECONDARY ACTION: Micro-movements for liveliness
      (slight tilt accompanying pan movements)
    - EXAGGERATION: Push poses for clarity
      (first shake is 110% amplitude)
    - APPEAL: Personality in every movement
      (natural variation in random_glance)

    Thread Safety:
        All public methods are thread-safe. Uses internal RLock to protect
        servo commands and state updates. Emergency stop uses atomic flag
        that can be checked without acquiring the lock.

    Example:
        >>> from src.drivers.servo.pca9685 import PCA9685Driver
        >>> driver = PCA9685Driver()
        >>> config = HeadConfig(pan_channel=12, tilt_channel=13)
        >>> head = HeadController(driver, config)
        >>> head.look_at(pan=30, tilt=15, duration_ms=500)
        >>> head.nod(count=2, amplitude=15, speed_ms=200)
        >>> position = head.get_current_position()
        >>> print(f"Pan: {position[0]}, Tilt: {position[1]}")

    Attributes:
        driver: PCA9685Driver instance for servo control
        config: HeadConfig with channel mappings and limits
    """

    def __init__(
        self,
        servo_driver: 'PCA9685Driver',
        config: HeadConfig
    ) -> None:
        """Initialize HeadController.

        Args:
            servo_driver: Configured PCA9685Driver instance
            config: HeadConfig with channel mappings and limits

        Raises:
            ValueError: If config is invalid
            TypeError: If servo_driver is None
            RuntimeError: If servo driver communication fails
        """
        if servo_driver is None:
            raise TypeError("servo_driver cannot be None")
        if not isinstance(config, HeadConfig):
            raise TypeError(f"Expected HeadConfig, got {type(config).__name__}")

        self._driver = servo_driver
        self._config = config

        # Thread safety
        self._lock = threading.RLock()
        self._emergency_stopped = threading.Event()

        # Current state
        self._current_pan: float = config.limits.pan_center
        self._current_tilt: float = config.limits.tilt_center

        # Animation state
        self._is_moving: bool = False
        self._movement_type: Optional[HeadMovementType] = None
        self._target_pan: Optional[float] = None
        self._target_tilt: Optional[float] = None

        # Animation trajectory (pre-computed keyframes)
        self._keyframes: List[_Keyframe] = []
        self._animation_start_time: float = 0.0
        self._animation_duration_ms: int = 0

        # Animation thread
        self._animation_thread: Optional[threading.Thread] = None
        self._stop_animation = threading.Event()

        # Callback
        self._on_movement_complete: Optional[Callable[[HeadMovementType], None]] = None

        # Initialize servos to center position
        self._move_servos_to(self._current_pan, self._current_tilt)

    # =========================================================================
    # PUBLIC METHODS - Movement Commands
    # =========================================================================

    def look_at(
        self,
        pan: float,
        tilt: float,
        duration_ms: Optional[int] = None,
        easing: Optional[str] = None,
        blocking: bool = False
    ) -> bool:
        """Move head to specified pan/tilt position.

        Smoothly interpolates from current position to target using
        the specified easing function. Applies Disney principles:

        Disney Principles Applied:
        --------------------------
        - SLOW IN/SLOW OUT: Uses ease_in_out by default for natural motion
        - FOLLOW THROUGH: Adds 5% overshoot then settles to target
        - ARCS: Interpolates pan and tilt with slight curve for organic feel

        Args:
            pan: Target pan angle in degrees (clamped to limits)
            tilt: Target tilt angle in degrees (clamped to limits)
            duration_ms: Movement duration (None = use config default)
            easing: Easing function name (None = use config default)
            blocking: If True, wait for movement to complete

        Returns:
            True if movement initiated successfully

        Note:
            Values outside limits are clamped, not rejected.
            Use get_state() to check actual target after clamping.
        """
        if self._emergency_stopped.is_set():
            return False

        # Apply defaults
        duration_ms = duration_ms if duration_ms is not None else self._config.default_speed_ms
        easing = easing if easing is not None else self._config.easing

        # Validate easing
        if easing not in EASING_LUTS:
            raise ValueError(f"Unknown easing: {easing}. Valid: {list(EASING_LUTS.keys())}")

        # Clamp to limits
        pan = self._clamp_pan(pan)
        tilt = self._clamp_tilt(tilt)

        with self._lock:
            # Cancel any existing animation
            self._cancel_animation_internal()

            # Build keyframes with Disney principles
            keyframes = self._build_look_at_keyframes(
                start_pan=self._current_pan,
                start_tilt=self._current_tilt,
                end_pan=pan,
                end_tilt=tilt,
                duration_ms=duration_ms,
                easing=easing
            )

            # Start animation
            self._start_animation(
                keyframes=keyframes,
                movement_type=HeadMovementType.LOOK,
                target_pan=pan,
                target_tilt=tilt
            )

        if blocking:
            return self.wait_for_completion()

        return True

    def nod(
        self,
        count: int = 2,
        amplitude: float = 15.0,
        speed_ms: int = 200,
        blocking: bool = False
    ) -> bool:
        """Perform nodding gesture (vertical yes motion).

        Creates a natural nodding motion applying Disney principles:

        Disney Principles Applied:
        --------------------------
        - ANTICIPATION: Small upward movement (10% of amplitude) before first nod down
        - TIMING: Asymmetric - fast down (60%), slow up (40%) for weight
        - FOLLOW THROUGH: Final settle slightly past center then back
        - EXAGGERATION: First nod slightly larger for emphasis

        Args:
            count: Number of nod cycles (1-5, clamped)
            amplitude: Peak tilt angle change in degrees (clamped to limits)
            speed_ms: Duration of one nod cycle in milliseconds
            blocking: If True, wait for animation to complete

        Returns:
            True if nod animation started

        Raises:
            RuntimeError: If in emergency stop state
        """
        if self._emergency_stopped.is_set():
            raise RuntimeError("Cannot nod: emergency stop active")

        # Clamp parameters
        count = max(1, min(5, count))

        # Ensure amplitude doesn't exceed tilt limits
        max_amplitude = min(
            self._current_tilt - self._config.limits.tilt_min,
            self._config.limits.tilt_max - self._current_tilt
        )
        amplitude = min(amplitude, max_amplitude)

        with self._lock:
            # Cancel any existing animation
            self._cancel_animation_internal()

            # Build keyframes with Disney nod animation
            keyframes = self._build_nod_keyframes(
                center_tilt=self._current_tilt,
                amplitude=amplitude,
                count=count,
                speed_ms=speed_ms
            )

            # Start animation
            self._start_animation(
                keyframes=keyframes,
                movement_type=HeadMovementType.NOD,
                target_pan=self._current_pan,
                target_tilt=self._current_tilt  # Returns to starting position
            )

        if blocking:
            return self.wait_for_completion()

        return True

    def shake(
        self,
        count: int = 2,
        amplitude: float = 20.0,
        speed_ms: int = 200,
        blocking: bool = False
    ) -> bool:
        """Perform head shake gesture (horizontal no motion).

        Creates a natural head shake applying Disney principles:

        Disney Principles Applied:
        --------------------------
        - ANTICIPATION: Small movement opposite to first shake direction
        - EXAGGERATION: First shake is 110% amplitude, decays to 80%
        - TIMING: Quick snap to position, slower return through center
        - FOLLOW THROUGH: Final settle with small overshoot

        Args:
            count: Number of shake cycles (1-5, clamped)
            amplitude: Peak pan angle change in degrees (clamped to limits)
            speed_ms: Duration of one shake cycle in milliseconds
            blocking: If True, wait for animation to complete

        Returns:
            True if shake animation started
        """
        if self._emergency_stopped.is_set():
            return False

        # Clamp parameters
        count = max(1, min(5, count))

        # Ensure amplitude doesn't exceed pan limits
        max_amplitude = min(
            self._current_pan - self._config.limits.pan_min,
            self._config.limits.pan_max - self._current_pan
        )
        amplitude = min(amplitude, max_amplitude)

        with self._lock:
            # Cancel any existing animation
            self._cancel_animation_internal()

            # Build keyframes with Disney shake animation
            keyframes = self._build_shake_keyframes(
                center_pan=self._current_pan,
                amplitude=amplitude,
                count=count,
                speed_ms=speed_ms
            )

            # Start animation
            self._start_animation(
                keyframes=keyframes,
                movement_type=HeadMovementType.SHAKE,
                target_pan=self._current_pan,
                target_tilt=self._current_tilt  # Returns to starting position
            )

        if blocking:
            return self.wait_for_completion()

        return True

    def random_glance(
        self,
        max_deviation: float = 30.0,
        hold_ms: int = 500,
        blocking: bool = False
    ) -> bool:
        """Perform quick random glance and return.

        Simulates curious/alert behavior:
        1. Quick movement to random offset
        2. Brief hold (as if observing)
        3. Smooth return to original position

        Disney Principles Applied:
        --------------------------
        - APPEAL: Natural variation, never exactly the same
        - SECONDARY ACTION: Slight tilt (15%) accompanying pan
        - TIMING: Quick movement to glance (ease_out), slower return (ease_in_out)
        - ANTICIPATION: Small opposite movement before glance

        Args:
            max_deviation: Maximum angle offset from current position
            hold_ms: Duration to hold at glance position
            blocking: If True, wait for complete glance cycle

        Returns:
            True if glance started
        """
        if self._emergency_stopped.is_set():
            return False

        with self._lock:
            # Cancel any existing animation
            self._cancel_animation_internal()

            # Generate random glance target with natural variation
            # APPEAL principle: Never exactly the same
            pan_offset = random.uniform(-max_deviation, max_deviation)

            # Add slight bias toward larger movements for appeal
            if abs(pan_offset) < max_deviation * 0.3:
                pan_offset *= 1.5

            # SECONDARY ACTION: Slight tilt accompanying pan
            tilt_offset = pan_offset * SECONDARY_TILT_RATIO * random.uniform(0.8, 1.2)

            # Clamp to limits
            glance_pan = self._clamp_pan(self._current_pan + pan_offset)
            glance_tilt = self._clamp_tilt(self._current_tilt + tilt_offset)

            # Build keyframes for glance animation
            keyframes = self._build_glance_keyframes(
                start_pan=self._current_pan,
                start_tilt=self._current_tilt,
                glance_pan=glance_pan,
                glance_tilt=glance_tilt,
                hold_ms=hold_ms
            )

            # Start animation
            self._start_animation(
                keyframes=keyframes,
                movement_type=HeadMovementType.GLANCE,
                target_pan=self._current_pan,
                target_tilt=self._current_tilt  # Returns to starting position
            )

        if blocking:
            return self.wait_for_completion()

        return True

    def tilt_curious(
        self,
        direction: str = 'right',
        angle: float = 20.0,
        duration_ms: int = 400,
        blocking: bool = False
    ) -> bool:
        """Tilt head curiously to one side.

        Disney-style curious pose with combined pan and tilt
        for expressive questioning look (like a curious dog).

        Disney Principles Applied:
        --------------------------
        - APPEAL: Dog-like curious head tilt that's universally endearing
        - ANTICIPATION: Small opposite movement first
        - STAGING: Combined pan+tilt for clear, readable pose
        - SLOW IN/SLOW OUT: Smooth easing into the tilt

        Args:
            direction: 'left' or 'right'
            angle: Tilt angle in degrees
            duration_ms: Movement duration
            blocking: If True, wait for movement to complete

        Returns:
            True if tilt started

        Raises:
            ValueError: If direction is not 'left' or 'right'
        """
        if direction not in ('left', 'right'):
            raise ValueError(f"direction must be 'left' or 'right', got '{direction}'")

        if self._emergency_stopped.is_set():
            return False

        with self._lock:
            # Cancel any existing animation
            self._cancel_animation_internal()

            # Calculate tilt direction
            tilt_sign = 1.0 if direction == 'right' else -1.0

            # STAGING: Combined pan and tilt for clear curious pose
            # Slight pan toward the tilt direction
            pan_offset = angle * 0.3 * tilt_sign

            # Target position
            target_tilt = self._clamp_tilt(self._current_tilt + angle * tilt_sign)
            target_pan = self._clamp_pan(self._current_pan + pan_offset)

            # Build keyframes with anticipation
            keyframes = self._build_curious_tilt_keyframes(
                start_pan=self._current_pan,
                start_tilt=self._current_tilt,
                target_pan=target_pan,
                target_tilt=target_tilt,
                direction=direction,
                duration_ms=duration_ms
            )

            # Start animation
            self._start_animation(
                keyframes=keyframes,
                movement_type=HeadMovementType.TILT,
                target_pan=target_pan,
                target_tilt=target_tilt
            )

        if blocking:
            return self.wait_for_completion()

        return True

    def reset_to_center(
        self,
        duration_ms: Optional[int] = None,
        blocking: bool = False
    ) -> bool:
        """Return head to center/home position.

        Args:
            duration_ms: Movement duration (None = use default)
            blocking: If True, wait for movement to complete

        Returns:
            True if reset initiated
        """
        return self.look_at(
            pan=self._config.limits.pan_center,
            tilt=self._config.limits.tilt_center,
            duration_ms=duration_ms,
            blocking=blocking
        )

    # =========================================================================
    # PUBLIC METHODS - Safety
    # =========================================================================

    def emergency_stop(self) -> None:
        """Immediately stop all head movement.

        SAFETY CRITICAL: This method:
        1. Sets atomic emergency stop flag (checked without lock)
        2. Cancels any active animation
        3. Disables both servo channels immediately

        Call reset_emergency() before resuming normal operation.

        Thread Safety: Can be called from any thread at any time.
        The emergency stop flag is an atomic Event that can be
        set/checked without acquiring the lock.
        """
        # Set atomic flag first (can be checked without lock)
        self._emergency_stopped.set()

        # Stop animation thread
        self._stop_animation.set()

        # FIX H-003: Save thread reference before acquiring lock
        animation_thread = self._animation_thread

        with self._lock:
            # Cancel animation state
            self._is_moving = False
            self._movement_type = None
            self._keyframes.clear()

            # Disable servos immediately
            try:
                self._driver.disable_channel(self._config.pan_channel)
                self._driver.disable_channel(self._config.tilt_channel)
            except Exception:
                # Best effort - don't raise during emergency stop
                pass

        # FIX H-003: Join animation thread after releasing lock to prevent orphans
        if animation_thread is not None and animation_thread.is_alive():
            animation_thread.join(timeout=0.1)  # 100ms timeout to prevent blocking

    def reset_emergency(self) -> bool:
        """Clear emergency stop state and re-enable servos.

        Must be called explicitly after emergency_stop() before
        any movement commands will be accepted.

        Returns:
            True if emergency state cleared successfully
        """
        with self._lock:
            # Clear emergency flag
            self._emergency_stopped.clear()
            self._stop_animation.clear()

            # Re-enable servos at current position
            try:
                self._move_servos_to(self._current_pan, self._current_tilt)
                return True
            except Exception:
                return False

    # =========================================================================
    # PUBLIC METHODS - State Query
    # =========================================================================

    def get_current_position(self) -> Tuple[float, float]:
        """Get current head position as (pan, tilt) tuple.

        Returns:
            Tuple of (pan_angle, tilt_angle) in degrees

        Note:
            If head is moving, returns last commanded position,
            not necessarily actual physical position.
        """
        with self._lock:
            return (self._current_pan, self._current_tilt)

    def get_state(self) -> HeadState:
        """Get complete current head state.

        Returns:
            HeadState snapshot with all current values
        """
        with self._lock:
            return HeadState(
                pan=self._current_pan,
                tilt=self._current_tilt,
                is_moving=self._is_moving,
                target_pan=self._target_pan,
                target_tilt=self._target_tilt,
                movement_type=self._movement_type
            )

    def is_moving(self) -> bool:
        """Check if head is currently in motion.

        Returns:
            True if any movement animation is active
        """
        with self._lock:
            return self._is_moving

    def wait_for_completion(self, timeout_ms: Optional[int] = None) -> bool:
        """Block until current movement completes.

        Args:
            timeout_ms: Maximum wait time (None = wait indefinitely)

        Returns:
            True if movement completed, False if timeout
        """
        if timeout_ms is not None:
            timeout_s = timeout_ms / 1000.0
        else:
            timeout_s = None

        start_time = time.monotonic()

        while True:
            with self._lock:
                if not self._is_moving:
                    return True

            if timeout_s is not None:
                elapsed = time.monotonic() - start_time
                if elapsed >= timeout_s:
                    return False

            # Sleep briefly to avoid busy-waiting
            time.sleep(FRAME_TIME_S)

    def set_on_movement_complete(
        self,
        callback: Optional[Callable[[HeadMovementType], None]]
    ) -> None:
        """Set callback for movement completion events.

        Args:
            callback: Function called with movement type when motion ends.
                     Pass None to clear callback.
        """
        with self._lock:
            self._on_movement_complete = callback

    # =========================================================================
    # PRIVATE METHODS - Keyframe Generation (Disney Principles)
    # =========================================================================

    def _build_look_at_keyframes(
        self,
        start_pan: float,
        start_tilt: float,
        end_pan: float,
        end_tilt: float,
        duration_ms: int,
        easing: str
    ) -> List[_Keyframe]:
        """Build keyframes for look_at movement.

        Disney Principles:
        - SLOW IN/SLOW OUT: Uses specified easing
        - FOLLOW THROUGH: 5% overshoot then settle
        - ARCS: Slight curve in motion path
        """
        keyframes = []

        # Calculate motion deltas
        delta_pan = end_pan - start_pan
        delta_tilt = end_tilt - start_tilt

        # Keyframe 0: Starting position
        keyframes.append(_Keyframe(
            time_ms=0,
            pan=start_pan,
            tilt=start_tilt,
            easing='linear'
        ))

        # FOLLOW THROUGH: Calculate overshoot position
        overshoot_pan = end_pan + delta_pan * FOLLOW_THROUGH_OVERSHOOT
        overshoot_tilt = end_tilt + delta_tilt * FOLLOW_THROUGH_OVERSHOOT

        # Clamp overshoot to limits
        overshoot_pan = self._clamp_pan(overshoot_pan)
        overshoot_tilt = self._clamp_tilt(overshoot_tilt)

        # Keyframe 1: Overshoot position (at 85% of duration)
        overshoot_time = int(duration_ms * 0.85)
        keyframes.append(_Keyframe(
            time_ms=overshoot_time,
            pan=overshoot_pan,
            tilt=overshoot_tilt,
            easing=easing
        ))

        # Keyframe 2: Final settle position
        keyframes.append(_Keyframe(
            time_ms=duration_ms,
            pan=end_pan,
            tilt=end_tilt,
            easing='ease_out'  # Smooth settle
        ))

        return keyframes

    def _build_nod_keyframes(
        self,
        center_tilt: float,
        amplitude: float,
        count: int,
        speed_ms: int
    ) -> List[_Keyframe]:
        """Build keyframes for nod animation.

        Disney Principles:
        - ANTICIPATION: Small upward movement (10%) before first nod
        - TIMING: Asymmetric - fast down (60%), slow up (40%)
        - FOLLOW THROUGH: Final settle past center
        - EXAGGERATION: First nod slightly larger
        """
        keyframes = []
        current_time = 0
        current_pan = self._current_pan

        # Keyframe 0: Starting position
        keyframes.append(_Keyframe(
            time_ms=current_time,
            pan=current_pan,
            tilt=center_tilt,
            easing='linear'
        ))

        # ANTICIPATION: Small upward movement before first nod
        anticipation_tilt = self._clamp_tilt(center_tilt + amplitude * ANTICIPATION_RATIO)
        anticipation_time = int(speed_ms * 0.15)  # Quick anticipation
        current_time += anticipation_time

        keyframes.append(_Keyframe(
            time_ms=current_time,
            pan=current_pan,
            tilt=anticipation_tilt,
            easing='ease_out'
        ))

        # Nod cycles
        for i in range(count):
            # EXAGGERATION: First nod is larger
            if i == 0:
                nod_amplitude = amplitude * 1.1
            else:
                # Gradual decay for natural feel
                nod_amplitude = amplitude * (0.95 ** i)

            # TIMING: Asymmetric - fast down (60%), slow up (40%)
            down_time = int(speed_ms * TIMING_ASYMMETRY_RATIO)
            up_time = speed_ms - down_time

            # Nod down
            nod_down_tilt = self._clamp_tilt(center_tilt - nod_amplitude)
            current_time += down_time
            keyframes.append(_Keyframe(
                time_ms=current_time,
                pan=current_pan,
                tilt=nod_down_tilt,
                easing='ease_in'  # Accelerate into nod
            ))

            # Nod up (through center)
            current_time += up_time
            keyframes.append(_Keyframe(
                time_ms=current_time,
                pan=current_pan,
                tilt=center_tilt,
                easing='ease_out'  # Decelerate at top
            ))

        # FOLLOW THROUGH: Final settle slightly past center then back
        follow_through_tilt = self._clamp_tilt(center_tilt + amplitude * 0.05)
        current_time += FOLLOW_THROUGH_SETTLE_MS // 2
        keyframes.append(_Keyframe(
            time_ms=current_time,
            pan=current_pan,
            tilt=follow_through_tilt,
            easing='ease_out'
        ))

        # Settle to final position
        current_time += FOLLOW_THROUGH_SETTLE_MS // 2
        keyframes.append(_Keyframe(
            time_ms=current_time,
            pan=current_pan,
            tilt=center_tilt,
            easing='ease_in_out'
        ))

        return keyframes

    def _build_shake_keyframes(
        self,
        center_pan: float,
        amplitude: float,
        count: int,
        speed_ms: int
    ) -> List[_Keyframe]:
        """Build keyframes for shake animation.

        Disney Principles:
        - ANTICIPATION: Movement opposite to first shake direction
        - EXAGGERATION: First shake 110%, decay to 80%
        - TIMING: Quick snap, slower return
        - FOLLOW THROUGH: Final settle with overshoot
        """
        keyframes = []
        current_time = 0
        current_tilt = self._current_tilt

        # Determine first shake direction (random for variety)
        first_direction = random.choice([-1, 1])

        # Keyframe 0: Starting position
        keyframes.append(_Keyframe(
            time_ms=current_time,
            pan=center_pan,
            tilt=current_tilt,
            easing='linear'
        ))

        # ANTICIPATION: Small movement opposite to first shake
        anticipation_pan = self._clamp_pan(
            center_pan - first_direction * amplitude * ANTICIPATION_RATIO
        )
        anticipation_time = int(speed_ms * 0.12)
        current_time += anticipation_time

        keyframes.append(_Keyframe(
            time_ms=current_time,
            pan=anticipation_pan,
            tilt=current_tilt,
            easing='ease_out'
        ))

        # Shake cycles
        direction = first_direction
        for i in range(count * 2):  # Each cycle has 2 movements (left-right or right-left)
            # EXAGGERATION: First shake is 110%, then decay
            if i == 0:
                shake_amplitude = amplitude * FIRST_SHAKE_EXAGGERATION
            else:
                # Decay each subsequent shake
                shake_amplitude = amplitude * (SHAKE_DECAY_FACTOR ** (i // 2))

            # TIMING: Quick snap to position
            snap_time = int(speed_ms * 0.35)
            current_time += snap_time

            shake_pan = self._clamp_pan(center_pan + direction * shake_amplitude)
            keyframes.append(_Keyframe(
                time_ms=current_time,
                pan=shake_pan,
                tilt=current_tilt,
                easing='ease_out'  # Quick snap with deceleration
            ))

            direction *= -1  # Alternate direction

        # Return to center with slower movement
        current_time += int(speed_ms * 0.5)
        keyframes.append(_Keyframe(
            time_ms=current_time,
            pan=center_pan,
            tilt=current_tilt,
            easing='ease_in_out'
        ))

        # FOLLOW THROUGH: Small overshoot and settle
        follow_pan = self._clamp_pan(center_pan - direction * amplitude * 0.05)
        current_time += FOLLOW_THROUGH_SETTLE_MS // 2
        keyframes.append(_Keyframe(
            time_ms=current_time,
            pan=follow_pan,
            tilt=current_tilt,
            easing='ease_out'
        ))

        # Final settle
        current_time += FOLLOW_THROUGH_SETTLE_MS // 2
        keyframes.append(_Keyframe(
            time_ms=current_time,
            pan=center_pan,
            tilt=current_tilt,
            easing='ease_in_out'
        ))

        return keyframes

    def _build_glance_keyframes(
        self,
        start_pan: float,
        start_tilt: float,
        glance_pan: float,
        glance_tilt: float,
        hold_ms: int
    ) -> List[_Keyframe]:
        """Build keyframes for glance animation.

        Disney Principles:
        - APPEAL: Natural variation through random elements
        - SECONDARY ACTION: Tilt accompanies pan (calculated in caller)
        - TIMING: Quick to glance, slower return
        - ANTICIPATION: Small opposite movement
        """
        keyframes = []
        current_time = 0

        # Calculate glance direction
        pan_delta = glance_pan - start_pan
        tilt_delta = glance_tilt - start_tilt

        # Keyframe 0: Starting position
        keyframes.append(_Keyframe(
            time_ms=current_time,
            pan=start_pan,
            tilt=start_tilt,
            easing='linear'
        ))

        # ANTICIPATION: Small opposite movement
        anticipation_pan = self._clamp_pan(start_pan - pan_delta * ANTICIPATION_RATIO)
        anticipation_tilt = self._clamp_tilt(start_tilt - tilt_delta * ANTICIPATION_RATIO)
        current_time += 50  # Quick anticipation

        keyframes.append(_Keyframe(
            time_ms=current_time,
            pan=anticipation_pan,
            tilt=anticipation_tilt,
            easing='ease_out'
        ))

        # Quick movement to glance position (TIMING: fast)
        current_time += 150
        keyframes.append(_Keyframe(
            time_ms=current_time,
            pan=glance_pan,
            tilt=glance_tilt,
            easing='ease_out'  # Quick snap
        ))

        # Hold at glance position
        current_time += hold_ms
        keyframes.append(_Keyframe(
            time_ms=current_time,
            pan=glance_pan,
            tilt=glance_tilt,
            easing='linear'  # Hold steady
        ))

        # Slower return to start (TIMING: slower return)
        current_time += 300
        keyframes.append(_Keyframe(
            time_ms=current_time,
            pan=start_pan,
            tilt=start_tilt,
            easing='ease_in_out'  # Smooth return
        ))

        return keyframes

    def _build_curious_tilt_keyframes(
        self,
        start_pan: float,
        start_tilt: float,
        target_pan: float,
        target_tilt: float,
        direction: str,
        duration_ms: int
    ) -> List[_Keyframe]:
        """Build keyframes for curious tilt animation.

        Disney Principles:
        - APPEAL: Dog-like curious pose
        - ANTICIPATION: Small opposite movement
        - STAGING: Combined pan+tilt for clear pose
        """
        keyframes = []
        current_time = 0

        # Calculate movement deltas
        pan_delta = target_pan - start_pan
        tilt_delta = target_tilt - start_tilt

        # Keyframe 0: Starting position
        keyframes.append(_Keyframe(
            time_ms=current_time,
            pan=start_pan,
            tilt=start_tilt,
            easing='linear'
        ))

        # ANTICIPATION: Small opposite movement
        anticipation_time = int(duration_ms * 0.15)
        anticipation_pan = self._clamp_pan(start_pan - pan_delta * ANTICIPATION_RATIO)
        anticipation_tilt = self._clamp_tilt(start_tilt - tilt_delta * ANTICIPATION_RATIO)
        current_time += anticipation_time

        keyframes.append(_Keyframe(
            time_ms=current_time,
            pan=anticipation_pan,
            tilt=anticipation_tilt,
            easing='ease_out'
        ))

        # Main tilt movement with slight overshoot
        overshoot_pan = self._clamp_pan(target_pan + pan_delta * FOLLOW_THROUGH_OVERSHOOT)
        overshoot_tilt = self._clamp_tilt(target_tilt + tilt_delta * FOLLOW_THROUGH_OVERSHOOT)
        main_time = int(duration_ms * 0.7)
        current_time += main_time

        keyframes.append(_Keyframe(
            time_ms=current_time,
            pan=overshoot_pan,
            tilt=overshoot_tilt,
            easing='ease_in_out'
        ))

        # Settle to final position
        settle_time = int(duration_ms * 0.15)
        current_time += settle_time

        keyframes.append(_Keyframe(
            time_ms=current_time,
            pan=target_pan,
            tilt=target_tilt,
            easing='ease_out'
        ))

        return keyframes

    # =========================================================================
    # PRIVATE METHODS - Animation Engine
    # =========================================================================

    def _start_animation(
        self,
        keyframes: List[_Keyframe],
        movement_type: HeadMovementType,
        target_pan: float,
        target_tilt: float
    ) -> None:
        """Start animation with pre-computed keyframes.

        Must be called with lock held.
        """
        self._keyframes = keyframes
        self._movement_type = movement_type
        self._target_pan = target_pan
        self._target_tilt = target_tilt
        self._is_moving = True

        # Calculate total duration
        if keyframes:
            self._animation_duration_ms = keyframes[-1].time_ms
        else:
            self._animation_duration_ms = 0

        # Clear stop flag and start animation thread
        self._stop_animation.clear()
        self._animation_start_time = time.monotonic()

        self._animation_thread = threading.Thread(
            target=self._animation_loop,
            daemon=True
        )
        self._animation_thread.start()

    def _animation_loop(self) -> None:
        """Main animation loop running at 50Hz.

        Runs in separate thread, interpolates between keyframes.
        """
        next_frame_time = time.monotonic()

        while not self._stop_animation.is_set() and not self._emergency_stopped.is_set():
            # Calculate elapsed time
            elapsed_ms = int((time.monotonic() - self._animation_start_time) * 1000)

            # Check if animation complete
            if elapsed_ms >= self._animation_duration_ms:
                self._complete_animation()
                return

            # Interpolate current position
            pan, tilt = self._interpolate_position(elapsed_ms)

            # Update servos
            with self._lock:
                if not self._is_moving:
                    return
                self._move_servos_to(pan, tilt)
                self._current_pan = pan
                self._current_tilt = tilt

            # Frame timing (50Hz)
            next_frame_time += FRAME_TIME_S
            sleep_time = next_frame_time - time.monotonic()
            if sleep_time > 0:
                time.sleep(sleep_time)
            else:
                # Frame overrun - reset timing
                next_frame_time = time.monotonic()

    def _interpolate_position(self, elapsed_ms: int) -> Tuple[float, float]:
        """Interpolate position at given time using keyframes.

        Uses pose-to-pose animation with easing between keyframes.
        """
        if not self._keyframes:
            return (self._current_pan, self._current_tilt)

        # Find surrounding keyframes
        prev_kf = self._keyframes[0]
        next_kf = self._keyframes[-1]

        for i, kf in enumerate(self._keyframes):
            if kf.time_ms >= elapsed_ms:
                next_kf = kf
                if i > 0:
                    prev_kf = self._keyframes[i - 1]
                break

        # Calculate interpolation factor
        if prev_kf.time_ms == next_kf.time_ms:
            t = 1.0
        else:
            t = (elapsed_ms - prev_kf.time_ms) / (next_kf.time_ms - prev_kf.time_ms)
            t = max(0.0, min(1.0, t))

        # Apply easing
        eased_t = ease(t, next_kf.easing)

        # Interpolate pan and tilt
        pan = prev_kf.pan + (next_kf.pan - prev_kf.pan) * eased_t
        tilt = prev_kf.tilt + (next_kf.tilt - prev_kf.tilt) * eased_t

        return (pan, tilt)

    def _complete_animation(self) -> None:
        """Complete the current animation."""
        with self._lock:
            # Move to final position
            if self._keyframes:
                final_kf = self._keyframes[-1]
                self._move_servos_to(final_kf.pan, final_kf.tilt)
                self._current_pan = final_kf.pan
                self._current_tilt = final_kf.tilt

            # Clear animation state
            movement_type = self._movement_type
            self._is_moving = False
            self._movement_type = None
            self._target_pan = None
            self._target_tilt = None
            self._keyframes.clear()

            # Fire callback if set
            callback = self._on_movement_complete

        # Call callback outside lock to prevent deadlocks
        if callback is not None and movement_type is not None:
            try:
                callback(movement_type)
            except Exception as e:
                # FIX H-006: Log callback error for debugging instead of silent swallow
                _logger.warning(f"Movement callback error: {e}", exc_info=True)

    def _cancel_animation_internal(self) -> None:
        """Cancel current animation. Must be called with lock held."""
        if self._animation_thread is not None and self._animation_thread.is_alive():
            self._stop_animation.set()
            # Don't join here - we're holding the lock

        self._is_moving = False
        self._movement_type = None
        self._target_pan = None
        self._target_tilt = None
        self._keyframes.clear()

    # =========================================================================
    # PRIVATE METHODS - Servo Control
    # =========================================================================

    def _move_servos_to(self, pan: float, tilt: float) -> None:
        """Move servos to specified position.

        Converts logical angles to servo angles and commands hardware.
        """
        if self._emergency_stopped.is_set():
            return

        # Convert logical angle to servo angle
        # Formula: servo_angle = 90 + (logical_angle * direction)
        pan_direction = -1.0 if self._config.pan_inverted else 1.0
        tilt_direction = -1.0 if self._config.tilt_inverted else 1.0

        pan_servo_angle = 90.0 + (pan * pan_direction)
        tilt_servo_angle = 90.0 + (tilt * tilt_direction)

        # Clamp to servo range (0-180)
        pan_servo_angle = max(0.0, min(180.0, pan_servo_angle))
        tilt_servo_angle = max(0.0, min(180.0, tilt_servo_angle))

        # Command servos
        try:
            self._driver.set_servo_angle(self._config.pan_channel, pan_servo_angle)
            self._driver.set_servo_angle(self._config.tilt_channel, tilt_servo_angle)
        except Exception as e:
            # FIX H-005: Log error for debugging instead of silent swallow
            _logger.error(f"Servo command failed: {e}", exc_info=True)

    def _clamp_pan(self, pan: float) -> float:
        """Clamp pan angle to configured limits.

        Handles NaN and Infinity by returning center position (safe default).
        """
        if math.isnan(pan) or math.isinf(pan):
            return self._config.limits.pan_center
        return max(self._config.limits.pan_min, min(self._config.limits.pan_max, pan))

    def _clamp_tilt(self, tilt: float) -> float:
        """Clamp tilt angle to configured limits.

        Handles NaN and Infinity by returning center position (safe default).
        """
        if math.isnan(tilt) or math.isinf(tilt):
            return self._config.limits.tilt_center
        return max(self._config.limits.tilt_min, min(self._config.limits.tilt_max, tilt))

    # =========================================================================
    # PROPERTIES
    # =========================================================================

    @property
    def config(self) -> HeadConfig:
        """Get the head configuration."""
        return self._config

    @property
    def driver(self) -> 'PCA9685Driver':
        """Get the servo driver instance."""
        return self._driver
