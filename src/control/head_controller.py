#!/usr/bin/env python3
"""
HeadController - 4-DOF Head Control with Disney Animation Principles

Provides smooth, expressive head movements for the OpenDuck Mini V3 robot
using the 12 Disney Animation Principles for natural, appealing motion.

4-DOF Configuration (V2-Compatible):
------------------------------------
- neck_pitch: Base neck up/down movement (PCA9685 ch 10)
- head_pitch: Head nod forward/back (PCA9685 ch 11)
- head_yaw: Head rotate left/right (PCA9685 ch 12)
- head_roll: Head tilt side-to-side (PCA9685 ch 13) - "Pixar secret!"

Disney 12 Principles Applied:
---------------------------------------------------------------------------
1. SQUASH & STRETCH: Timing compression before extension movements
2. ANTICIPATION: Slight opposite movement before major actions
3. STAGING: Clear, readable poses at all times
4. POSE TO POSE: Pre-computed keyframes for predictable motion
5. FOLLOW THROUGH: Movement continues slightly after reaching target
6. SLOW IN / SLOW OUT: Easing functions for natural acceleration
7. ARCS: Natural curved motion paths for organic feel
8. SECONDARY ACTION: Subtle supporting movements (roll with yaw)
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
Created: 18 January 2026 (2-DOF version)
Updated: 19 January 2026 (4-DOF V2-compatible version)
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

# FIX D14-001: Conditional import for both package and path-based usage
# - Package import: from src.led.color_utils (uses src.animation.easing)
# - Path import: when src/ is in sys.path (uses animation.easing)
try:
    from animation.easing import ease, EASING_LUTS
except ImportError:
    from src.animation.easing import ease, EASING_LUTS

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
    """Hardware limits for 4-DOF head servos.

    All angles in degrees. Center position is 0.0 for all axes.

    Coordinate System:
    - neck_pitch: Positive = neck up, negative = neck down
    - head_pitch: Positive = look up, negative = nod down
    - head_yaw: Positive = rotate right, negative = rotate left
    - head_roll: Positive = tilt right, negative = tilt left

    Attributes:
        neck_pitch_min: Minimum neck pitch angle (default: -20°)
        neck_pitch_max: Maximum neck pitch angle (default: +65°)
        head_pitch_min: Minimum head pitch angle (default: -45°)
        head_pitch_max: Maximum head pitch angle (default: +45°)
        head_yaw_min: Minimum head yaw angle (default: -90°, MG90S servo limit)
        head_yaw_max: Maximum head yaw angle (default: +90°, MG90S servo limit)
        head_roll_min: Minimum head roll angle (default: -30°)
        head_roll_max: Maximum head roll angle (default: +30°)
        neck_pitch_center: Center position for neck pitch (default: 0.0)
        head_pitch_center: Center position for head pitch (default: 0.0)
        head_yaw_center: Center position for head yaw (default: 0.0)
        head_roll_center: Center position for head roll (default: 0.0)

    Example:
        >>> limits = HeadLimits(
        ...     neck_pitch_min=-20, neck_pitch_max=65,
        ...     head_pitch_min=-45, head_pitch_max=45,
        ...     head_yaw_min=-90, head_yaw_max=90,
        ...     head_roll_min=-30, head_roll_max=30
        ... )
        >>> limits.head_yaw_center
        0.0
    """
    # Neck pitch limits (base neck movement)
    neck_pitch_min: float = -20.0
    neck_pitch_max: float = 65.0
    neck_pitch_center: float = 0.0

    # Head pitch limits (nod)
    head_pitch_min: float = -45.0
    head_pitch_max: float = 45.0
    head_pitch_center: float = 0.0

    # Head yaw limits (pan/rotate) - MG90S servo physical limit is ±90°
    head_yaw_min: float = -90.0
    head_yaw_max: float = 90.0
    head_yaw_center: float = 0.0

    # Head roll limits (tilt side-to-side)
    head_roll_min: float = -30.0
    head_roll_max: float = 30.0
    head_roll_center: float = 0.0

    def __post_init__(self):
        """Validate limit configuration."""
        # Validate neck_pitch
        if self.neck_pitch_min >= self.neck_pitch_max:
            raise ValueError(f"neck_pitch_min ({self.neck_pitch_min}) must be < neck_pitch_max ({self.neck_pitch_max})")
        if not (self.neck_pitch_min <= self.neck_pitch_center <= self.neck_pitch_max):
            raise ValueError(f"neck_pitch_center ({self.neck_pitch_center}) must be within neck_pitch limits")

        # Validate head_pitch
        if self.head_pitch_min >= self.head_pitch_max:
            raise ValueError(f"head_pitch_min ({self.head_pitch_min}) must be < head_pitch_max ({self.head_pitch_max})")
        if not (self.head_pitch_min <= self.head_pitch_center <= self.head_pitch_max):
            raise ValueError(f"head_pitch_center ({self.head_pitch_center}) must be within head_pitch limits")

        # Validate head_yaw
        if self.head_yaw_min >= self.head_yaw_max:
            raise ValueError(f"head_yaw_min ({self.head_yaw_min}) must be < head_yaw_max ({self.head_yaw_max})")
        if not (self.head_yaw_min <= self.head_yaw_center <= self.head_yaw_max):
            raise ValueError(f"head_yaw_center ({self.head_yaw_center}) must be within head_yaw limits")

        # Validate head_roll
        if self.head_roll_min >= self.head_roll_max:
            raise ValueError(f"head_roll_min ({self.head_roll_min}) must be < head_roll_max ({self.head_roll_max})")
        if not (self.head_roll_min <= self.head_roll_center <= self.head_roll_max):
            raise ValueError(f"head_roll_center ({self.head_roll_center}) must be within head_roll limits")


@dataclass
class HeadConfig:
    """Configuration for 4-DOF HeadController.

    Attributes:
        neck_pitch_channel: PCA9685 channel for neck pitch servo (0-15, default: 10)
        head_pitch_channel: PCA9685 channel for head pitch servo (0-15, default: 11)
        head_yaw_channel: PCA9685 channel for head yaw servo (0-15, default: 12)
        head_roll_channel: PCA9685 channel for head roll servo (0-15, default: 13)
        limits: HeadLimits instance defining movement bounds
        neck_pitch_inverted: If True, invert neck pitch servo direction
        head_pitch_inverted: If True, invert head pitch servo direction
        head_yaw_inverted: If True, invert head yaw servo direction
        head_roll_inverted: If True, invert head roll servo direction
        default_speed_ms: Default movement duration in milliseconds
        easing: Default easing function name ('ease_in_out', 'ease_in', etc.)

    Example:
        >>> config = HeadConfig(
        ...     neck_pitch_channel=10,
        ...     head_pitch_channel=11,
        ...     head_yaw_channel=12,
        ...     head_roll_channel=13
        ... )
        >>> config.default_speed_ms
        300
    """
    neck_pitch_channel: int
    head_pitch_channel: int
    head_yaw_channel: int
    head_roll_channel: int
    limits: HeadLimits = field(default_factory=HeadLimits)
    neck_pitch_inverted: bool = False
    head_pitch_inverted: bool = False
    head_yaw_inverted: bool = False
    head_roll_inverted: bool = False
    default_speed_ms: int = 300
    easing: str = 'ease_in_out'

    def __post_init__(self):
        """Validate configuration."""
        channels = [
            self.neck_pitch_channel,
            self.head_pitch_channel,
            self.head_yaw_channel,
            self.head_roll_channel
        ]
        channel_names = [
            "neck_pitch_channel",
            "head_pitch_channel",
            "head_yaw_channel",
            "head_roll_channel"
        ]

        # Validate channel ranges
        for ch, name in zip(channels, channel_names):
            if not (0 <= ch <= 15):
                raise ValueError(f"{name} must be 0-15, got {ch}")

        # Validate uniqueness
        if len(set(channels)) != 4:
            raise ValueError(f"All channels must be unique. Got: {dict(zip(channel_names, channels))}")

        if self.default_speed_ms <= 0:
            raise ValueError(f"default_speed_ms must be > 0, got {self.default_speed_ms}")
        if self.easing not in EASING_LUTS:
            raise ValueError(f"Unknown easing type: {self.easing}. Valid: {list(EASING_LUTS.keys())}")


@dataclass
class HeadState:
    """Current state of the 4-DOF head position.

    Immutable snapshot of head state for reading current position.

    Attributes:
        neck_pitch: Current neck pitch angle in degrees
        head_pitch: Current head pitch angle in degrees
        head_yaw: Current head yaw angle in degrees
        head_roll: Current head roll angle in degrees
        is_moving: True if head is currently in motion
        target_neck_pitch: Target neck pitch angle (if moving)
        target_head_pitch: Target head pitch angle (if moving)
        target_head_yaw: Target head yaw angle (if moving)
        target_head_roll: Target head roll angle (if moving)
        movement_type: Current movement type (if moving)
    """
    neck_pitch: float
    head_pitch: float
    head_yaw: float
    head_roll: float
    is_moving: bool = False
    target_neck_pitch: Optional[float] = None
    target_head_pitch: Optional[float] = None
    target_head_yaw: Optional[float] = None
    target_head_roll: Optional[float] = None
    movement_type: Optional[HeadMovementType] = None


@dataclass
class _Keyframe:
    """Internal keyframe for 4-DOF animation trajectory.

    Pre-computed position at a specific time for pose-to-pose animation.

    Attributes:
        time_ms: Time offset from animation start
        neck_pitch: Neck pitch angle at this keyframe
        head_pitch: Head pitch angle at this keyframe
        head_yaw: Head yaw angle at this keyframe
        head_roll: Head roll angle at this keyframe
        easing: Easing function for interpolation TO this keyframe
    """
    time_ms: int
    neck_pitch: float
    head_pitch: float
    head_yaw: float
    head_roll: float
    easing: str = 'ease_in_out'


# =============================================================================
# HEAD CONTROLLER CLASS
# =============================================================================

class HeadController:
    """4-DOF head controller with expressive movements (V2-compatible).

    Provides smooth, animation-quality head movements using 4 degrees of freedom:
    - neck_pitch: Base neck up/down movement
    - head_pitch: Head nod forward/back
    - head_yaw: Head rotate left/right
    - head_roll: Head tilt side-to-side (Pixar secret!)

    Features:
    - Direct positioning (move_to, look_at for backwards compatibility)
    - Expressive gestures (nod, shake, glance, tilt_curious)
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
      (slight roll accompanying yaw movements)
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
        >>> config = HeadConfig(
        ...     neck_pitch_channel=10,
        ...     head_pitch_channel=11,
        ...     head_yaw_channel=12,
        ...     head_roll_channel=13
        ... )
        >>> head = HeadController(driver, config)
        >>> head.move_to(neck_pitch=10, head_pitch=0, head_yaw=30, head_roll=5)
        >>> head.nod(count=2, amplitude=15, speed_ms=200)
        >>> state = head.get_state()
        >>> print(f"Yaw: {state.head_yaw}, Pitch: {state.head_pitch}")

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

        # Current state (4 DOF)
        self._current_neck_pitch: float = config.limits.neck_pitch_center
        self._current_head_pitch: float = config.limits.head_pitch_center
        self._current_head_yaw: float = config.limits.head_yaw_center
        self._current_head_roll: float = config.limits.head_roll_center

        # Animation state
        self._is_moving: bool = False
        self._movement_type: Optional[HeadMovementType] = None
        self._target_neck_pitch: Optional[float] = None
        self._target_head_pitch: Optional[float] = None
        self._target_head_yaw: Optional[float] = None
        self._target_head_roll: Optional[float] = None

        # Animation trajectory (pre-computed keyframes)
        self._keyframes: List[_Keyframe] = []
        self._animation_start_time: float = 0.0
        self._animation_duration_ms: int = 0

        # Animation thread
        self._animation_thread: Optional[threading.Thread] = None
        self._stop_animation = threading.Event()
        self._animation_complete = threading.Event()  # FIX H-005: Signal for wait_for_completion
        self._animation_complete.set()  # Initially complete (not animating)
        # FIX C-1: Generation counter prevents zombie threads from writing stale positions
        self._animation_generation: int = 0

        # Callback (class-level)
        self._on_movement_complete: Optional[Callable[[HeadMovementType], None]] = None
        # Per-call callback (for on_complete parameter)
        self._pending_on_complete: Optional[Callable[[bool], None]] = None

        # FIX H-NEW-004: Thread-safe private RNG instance
        self._rng = random.Random()

        # Initialize servos to center position
        self._move_servos_to(
            self._current_neck_pitch,
            self._current_head_pitch,
            self._current_head_yaw,
            self._current_head_roll
        )

    # =========================================================================
    # PUBLIC METHODS - Movement Commands
    # =========================================================================

    def move_to(
        self,
        neck_pitch: Optional[float] = None,
        head_pitch: Optional[float] = None,
        head_yaw: Optional[float] = None,
        head_roll: Optional[float] = None,
        duration_ms: Optional[int] = None,
        easing: Optional[str] = None,
        blocking: bool = False,
        on_complete: Optional[Callable[[bool], None]] = None
    ) -> bool:
        """Move head to specified 4-DOF position.

        Smoothly interpolates from current position to target using
        the specified easing function. Omitted parameters hold their current values.

        Disney Principles Applied:
        --------------------------
        - SLOW IN/SLOW OUT: Uses ease_in_out by default for natural motion
        - FOLLOW THROUGH: Adds 5% overshoot then settles to target
        - ARCS: Interpolates all 4 DOF with slight curve for organic feel

        Args:
            neck_pitch: Target neck pitch angle (None = hold current)
            head_pitch: Target head pitch angle (None = hold current)
            head_yaw: Target head yaw angle (None = hold current)
            head_roll: Target head roll angle (None = hold current)
            duration_ms: Movement duration (None = use config default)
            easing: Easing function name (None = use config default)
            blocking: If True, wait for movement to complete
            on_complete: Optional callback called with True on success, False on interrupt

        Returns:
            True if movement initiated successfully

        Note:
            Values outside limits are clamped, not rejected.
            Use get_state() to check actual target after clamping.

        Raises:
            ValueError: If any angle value is NaN or Inf

        Example:
            >>> # Move just yaw (pan), hold everything else
            >>> head.move_to(head_yaw=30)
            >>> # Move to full expressive pose
            >>> head.move_to(neck_pitch=10, head_pitch=-5, head_yaw=30, head_roll=10)
        """
        # Validate inputs for NaN/Inf
        for name, value in [("neck_pitch", neck_pitch), ("head_pitch", head_pitch),
                            ("head_yaw", head_yaw), ("head_roll", head_roll)]:
            if value is not None:
                if math.isnan(value):
                    if on_complete:
                        on_complete(False)
                    raise ValueError(f"{name} is NaN - invalid angle value")
                if math.isinf(value):
                    if on_complete:
                        on_complete(False)
                    raise ValueError(f"{name} is Inf - invalid angle value")

        if self._emergency_stopped.is_set():
            if on_complete:
                on_complete(False)
            return False

        # Apply defaults
        duration_ms = duration_ms if duration_ms is not None else self._config.default_speed_ms
        easing = easing if easing is not None else self._config.easing

        # Validate easing
        if easing not in EASING_LUTS:
            if on_complete:
                on_complete(False)
            raise ValueError(f"Unknown easing: {easing}. Valid: {list(EASING_LUTS.keys())}")

        with self._lock:
            # Use current values if not specified
            target_neck_pitch = neck_pitch if neck_pitch is not None else self._current_neck_pitch
            target_head_pitch = head_pitch if head_pitch is not None else self._current_head_pitch
            target_head_yaw = head_yaw if head_yaw is not None else self._current_head_yaw
            target_head_roll = head_roll if head_roll is not None else self._current_head_roll

            # Clamp to limits
            target_neck_pitch = self._clamp_neck_pitch(target_neck_pitch)
            target_head_pitch = self._clamp_head_pitch(target_head_pitch)
            target_head_yaw = self._clamp_head_yaw(target_head_yaw)
            target_head_roll = self._clamp_head_roll(target_head_roll)

            # Cancel any existing animation
            self._cancel_animation_internal()

            # Build keyframes with Disney principles
            keyframes = self._build_move_to_keyframes(
                start_neck_pitch=self._current_neck_pitch,
                start_head_pitch=self._current_head_pitch,
                start_head_yaw=self._current_head_yaw,
                start_head_roll=self._current_head_roll,
                end_neck_pitch=target_neck_pitch,
                end_head_pitch=target_head_pitch,
                end_head_yaw=target_head_yaw,
                end_head_roll=target_head_roll,
                duration_ms=duration_ms,
                easing=easing
            )

            # Store per-call callback for non-blocking completion notification
            self._pending_on_complete = on_complete

            # Start animation
            self._start_animation(
                keyframes=keyframes,
                movement_type=HeadMovementType.LOOK,
                target_neck_pitch=target_neck_pitch,
                target_head_pitch=target_head_pitch,
                target_head_yaw=target_head_yaw,
                target_head_roll=target_head_roll
            )

        if blocking:
            # FIX H-2: Clear pending callback so _complete_animation doesn't also fire it
            # We'll call it ourselves after wait_for_completion returns
            with self._lock:
                self._pending_on_complete = None
            result = self.wait_for_completion()
            if on_complete is not None:
                try:
                    on_complete(result)
                except Exception as e:
                    _logger.warning(f"on_complete callback error: {e}", exc_info=True)
            return result

        return True

    def look_at(
        self,
        pan: float,
        tilt: float,
        duration_ms: Optional[int] = None,
        easing: Optional[str] = None,
        blocking: bool = False,
        on_complete: Optional[Callable[[bool], None]] = None,
        timeout_ms: Optional[int] = None
    ) -> bool:
        """Move head to specified pan/tilt position (backwards-compatible 2-DOF API).

        DEPRECATED: This method provides backwards compatibility with 2-DOF code.
        New code should use move_to() for full 4-DOF control.

        Maps 2-DOF coordinates to 4-DOF system:
        - pan → head_yaw (rotate left/right)
        - tilt → head_pitch (nod up/down)
        - neck_pitch → holds current value
        - head_roll → holds current value

        Disney Principles Applied:
        --------------------------
        - SLOW IN/SLOW OUT: Uses ease_in_out by default for natural motion
        - FOLLOW THROUGH: Adds 5% overshoot then settles to target
        - ARCS: Interpolates all DOF with slight curve for organic feel

        Args:
            pan: Target pan angle in degrees (mapped to head_yaw)
            tilt: Target tilt angle in degrees (mapped to head_pitch)
            duration_ms: Movement duration (None = use config default)
            easing: Easing function name (None = use config default)
            blocking: If True, wait for movement to complete
            on_complete: Optional callback called with True on success, False on interrupt
            timeout_ms: Maximum time to wait if blocking (None = wait indefinitely)

        Returns:
            True if movement initiated/completed successfully

        Raises:
            ValueError: If pan or tilt is NaN or Inf

        Note:
            Values outside limits are clamped, not rejected.
            For full 4-DOF control, use move_to() instead.

        Example:
            >>> # Old 2-DOF style (still works)
            >>> head.look_at(pan=30, tilt=15)
            >>> # New 4-DOF style (recommended)
            >>> head.move_to(head_yaw=30, head_pitch=15)
        """
        # Validate inputs for NaN/Inf - call on_complete before raising
        if math.isnan(pan):
            if on_complete:
                on_complete(False)
            raise ValueError("pan is NaN - invalid angle value")
        if math.isinf(pan):
            if on_complete:
                on_complete(False)
            raise ValueError("pan is Inf - invalid angle value")
        if math.isnan(tilt):
            if on_complete:
                on_complete(False)
            raise ValueError("tilt is NaN - invalid angle value")
        if math.isinf(tilt):
            if on_complete:
                on_complete(False)
            raise ValueError("tilt is Inf - invalid angle value")

        # For blocking calls with timeout, handle manually instead of through move_to
        if blocking and timeout_ms is not None:
            # Start movement without blocking
            started = self.move_to(
                neck_pitch=None,
                head_pitch=tilt,
                head_yaw=pan,
                head_roll=None,
                duration_ms=duration_ms,
                easing=easing,
                blocking=False,
                on_complete=None  # We handle callback manually
            )
            if not started:
                if on_complete:
                    on_complete(False)
                return False

            # Wait with timeout
            result = self.wait_for_completion(timeout_ms=timeout_ms)
            if on_complete:
                try:
                    on_complete(result)
                except Exception as e:
                    _logger.warning(f"on_complete callback error: {e}", exc_info=True)
            return result

        # Map 2-DOF to 4-DOF: pan→head_yaw, tilt→head_pitch
        return self.move_to(
            neck_pitch=None,  # Hold current
            head_pitch=tilt,  # Map tilt to head_pitch
            head_yaw=pan,     # Map pan to head_yaw
            head_roll=None,   # Hold current
            duration_ms=duration_ms,
            easing=easing,
            blocking=blocking,
            on_complete=on_complete
        )

    def nod(
        self,
        count: int = 2,
        amplitude: float = 15.0,
        speed_ms: int = 500,
        blocking: bool = False
    ) -> bool:
        """Perform nodding gesture (vertical affirmation).

        Disney Principles Applied:
        --------------------------
        - ANTICIPATION: Slight upward movement before nodding down
        - TIMING ASYMMETRY: Faster down (gravity), slower up (natural physics)
        - FOLLOW THROUGH: Slight overshoot at bottom, smooth settle

        This creates a natural "yes" head nod that feels alive and organic.

        Args:
            count: Number of nod cycles (1-5, clamped, typically 1-2)
            amplitude: Peak head pitch angle in degrees (typically 15-20)
            speed_ms: Duration of one complete nod cycle in milliseconds (typically 500)
            blocking: If True, wait for animation to complete

        Returns:
            True if nod animation started

        Raises:
            RuntimeError: If in emergency stop state

        Example:
            >>> # Single affirmative nod
            >>> head.nod(count=1, amplitude=20.0, speed_ms=500)
            >>> # Enthusiastic double nod
            >>> head.nod(count=2, amplitude=25.0, speed_ms=400)
        """
        if self._emergency_stopped.is_set():
            raise RuntimeError("Cannot nod: emergency stop active")

        # Clamp parameters
        count = max(1, min(5, count))
        if amplitude <= 0:
            raise ValueError(f"amplitude must be > 0, got {amplitude}")
        amplitude = max(1.0, min(45.0, amplitude))  # Clamp to 1-45° range

        with self._lock:
            # Cancel any existing animation
            self._cancel_animation_internal()

            # Build keyframes with Disney principles
            keyframes = self._build_nod_keyframes(count, amplitude, speed_ms)

            # Start animation
            self._start_animation(
                keyframes=keyframes,
                movement_type=HeadMovementType.NOD,
                target_neck_pitch=self._current_neck_pitch,  # Hold
                target_head_pitch=0.0,  # Return to center
                target_head_yaw=self._current_head_yaw,  # Hold
                target_head_roll=self._current_head_roll  # Hold
            )

        if blocking:
            return self.wait_for_completion()

        return True

    def shake(
        self,
        count: int = 2,
        amplitude: float = 25.0,
        speed_ms: int = 400,
        blocking: bool = False
    ) -> bool:
        """Perform head shake gesture (horizontal negation).

        Disney Principles Applied:
        --------------------------
        - ANTICIPATION: Slight opposite turn before main shake
        - EXAGGERATION: First shake is 110% amplitude for clarity
        - DECAY: Each subsequent shake reduces by 10% (natural deceleration)

        This creates a natural "no" head shake with personality and appeal.

        Args:
            count: Number of shake cycles (1-5, clamped, typically 2-3)
            amplitude: Peak head yaw angle in degrees (typically 20-25)
            speed_ms: Duration of one complete shake cycle in milliseconds (typically 400)
            blocking: If True, wait for animation to complete

        Returns:
            True if shake animation started

        Example:
            >>> # Standard "no" shake
            >>> head.shake(count=2, amplitude=25.0, speed_ms=400)
            >>> # Emphatic rejection
            >>> head.shake(count=3, amplitude=30.0, speed_ms=300)

        Raises:
            RuntimeError: If emergency stop is active
        """
        # FIX H-4: Consistent with nod() - raise RuntimeError, don't silently return False
        if self._emergency_stopped.is_set():
            raise RuntimeError("Cannot shake: emergency stop active")

        # Clamp parameters
        count = max(1, min(5, count))
        if amplitude <= 0:
            raise ValueError(f"amplitude must be > 0, got {amplitude}")
        amplitude = max(1.0, min(90.0, amplitude))  # Clamp to 1-90° range (MG90S limit)

        with self._lock:
            # Cancel any existing animation
            self._cancel_animation_internal()

            # Build keyframes with Disney principles
            keyframes = self._build_shake_keyframes(count, amplitude, speed_ms)

            # Start animation
            self._start_animation(
                keyframes=keyframes,
                movement_type=HeadMovementType.SHAKE,
                target_neck_pitch=self._current_neck_pitch,  # Hold
                target_head_pitch=self._current_head_pitch,  # Hold
                target_head_yaw=0.0,  # Return to center
                target_head_roll=self._current_head_roll  # Hold
            )

        if blocking:
            return self.wait_for_completion()

        return True

    def random_glance(
        self,
        hold_ms: int = 500,
        return_speed_ms: int = 400,
        blocking: bool = False
    ) -> bool:
        """Perform quick random glance and return.

        Disney Principles Applied:
        --------------------------
        - APPEAL: Natural variation, never exactly the same (random left/right)
        - SECONDARY ACTION: head_roll follows head_yaw with 150ms lag (weight shift)
        - TIMING: Quick snap to target, slower return

        This simulates alert/curious behavior with organic weight transfer.

        Args:
            hold_ms: Duration to hold at glance position (typically 500ms)
            return_speed_ms: Time to return to center (typically 400ms)
            blocking: If True, wait for complete glance cycle

        Returns:
            True if glance started

        Raises:
            RuntimeError: If emergency stop is active

        Example:
            >>> # Quick alert glance
            >>> head.random_glance(hold_ms=500, return_speed_ms=400)
        """
        # FIX H-4: Consistent with nod() - raise RuntimeError
        if self._emergency_stopped.is_set():
            raise RuntimeError("Cannot random_glance: emergency stop active")

        with self._lock:
            # Generate random glance target (left or right, 30° typical)
            target_yaw = self._rng.choice([-30.0, 30.0])

            # Cancel any existing animation
            self._cancel_animation_internal()

            # Build keyframes with Disney principles
            keyframes = self._build_glance_keyframes(target_yaw, hold_ms, return_speed_ms)

            # Start animation
            self._start_animation(
                keyframes=keyframes,
                movement_type=HeadMovementType.GLANCE,
                target_neck_pitch=self._current_neck_pitch,  # Hold
                target_head_pitch=self._current_head_pitch,  # Hold
                target_head_yaw=0.0,  # Return to center
                target_head_roll=0.0  # Return to center
            )

        if blocking:
            return self.wait_for_completion()

        return True

    def tilt_curious(
        self,
        direction: str = 'right',
        angle: float = 20.0,
        duration_ms: int = 600,
        blocking: bool = False
    ) -> bool:
        """Tilt head curiously to one side (Pixar-style using head_roll!).

        This is the SIGNATURE 4-DOF movement that showcases head_roll.
        Creates that universally endearing "curious dog" head tilt.

        Disney Principles Applied:
        --------------------------
        - STAGING: head_roll is PRIMARY action (clear readable pose)
        - SECONDARY ACTION: head_yaw follows 150ms later (supporting motion)
        - ANTICIPATION: Slight opposite tilt before main movement
        - APPEAL: Dog-like curious head tilt (universally endearing)

        Args:
            direction: 'left' or 'right' tilt direction
            angle: Head roll tilt angle in degrees (typically 15-25)
            duration_ms: Total animation time in milliseconds (typically 600)
            blocking: If True, wait for movement to complete

        Returns:
            True if tilt started

        Raises:
            ValueError: If direction is not 'left' or 'right'
            RuntimeError: If emergency stop is active

        Example:
            >>> # Classic curious tilt
            >>> head.tilt_curious(direction='right', angle=20.0, duration_ms=600)
        """
        if direction not in ('left', 'right'):
            raise ValueError(f"direction must be 'left' or 'right', got '{direction}'")

        # FIX H-4: Consistent with nod() - raise RuntimeError
        if self._emergency_stopped.is_set():
            raise RuntimeError("Cannot tilt_curious: emergency stop active")

        with self._lock:
            # Cancel any existing animation
            self._cancel_animation_internal()

            # Build keyframes with Disney principles
            keyframes = self._build_curious_tilt_keyframes(direction, angle, duration_ms)

            # Start animation
            self._start_animation(
                keyframes=keyframes,
                movement_type=HeadMovementType.TILT,
                target_neck_pitch=self._current_neck_pitch,  # Hold
                target_head_pitch=self._current_head_pitch,  # Hold
                target_head_yaw=angle * 0.3 * (1.0 if direction == 'right' else -1.0),
                target_head_roll=angle * (1.0 if direction == 'right' else -1.0)
            )

        if blocking:
            return self.wait_for_completion()

        return True

    def reset_to_center(
        self,
        duration_ms: Optional[int] = None,
        blocking: bool = False
    ) -> bool:
        """Return head to center/home position (all 4 DOF).

        Args:
            duration_ms: Movement duration (None = use default)
            blocking: If True, wait for movement to complete

        Returns:
            True if reset initiated
        """
        return self.move_to(
            neck_pitch=self._config.limits.neck_pitch_center,
            head_pitch=self._config.limits.head_pitch_center,
            head_yaw=self._config.limits.head_yaw_center,
            head_roll=self._config.limits.head_roll_center,
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

            # Get per-call callback to notify of interruption
            per_call_callback = self._pending_on_complete
            self._pending_on_complete = None

            # HOLD current position - keep PWM active to prevent servo going limp
            # FIX C-4: disable_channel cuts PWM, causing MG90S to lose torque
            # and the head to drop under gravity. Instead, command servos to
            # hold their current position (active braking).
            try:
                self._move_servos_to(
                    self._current_neck_pitch,
                    self._current_head_pitch,
                    self._current_head_yaw,
                    self._current_head_roll
                )
            except Exception:
                # Best effort - don't raise during emergency stop
                pass

        # Signal completion for wait_for_completion()
        self._animation_complete.set()

        # FIX H-003: Join animation thread after releasing lock to prevent orphans
        if animation_thread is not None and animation_thread.is_alive():
            animation_thread.join(timeout=0.1)  # 100ms timeout to prevent blocking

        # Call per-call callback with False (interrupted)
        if per_call_callback is not None:
            try:
                per_call_callback(False)
            except Exception as e:
                _logger.warning(f"on_complete callback error during emergency: {e}", exc_info=True)

    def reset_emergency(self) -> bool:
        """Clear emergency stop state and re-enable all 4 servos.

        Must be called explicitly after emergency_stop() before
        any movement commands will be accepted.

        Returns:
            True if emergency state cleared successfully
        """
        with self._lock:
            # Clear emergency flag
            self._emergency_stopped.clear()
            self._stop_animation.clear()

            # Re-enable all servos at current position
            try:
                self._move_servos_to(
                    self._current_neck_pitch,
                    self._current_head_pitch,
                    self._current_head_yaw,
                    self._current_head_roll
                )
                return True
            except Exception:
                return False

    def power_off(self) -> None:
        """Cut PWM to all servos - servos will go limp.

        WARNING: Only call this when the robot is in a safe position
        (e.g., head resting on a surface). Servos will lose all torque
        and the head will drop under gravity.

        Use emergency_stop() for normal stopping - it holds position.
        Use power_off() only for shutdown or maintenance.
        """
        self.emergency_stop()
        with self._lock:
            try:
                self._driver.disable_channel(self._config.neck_pitch_channel)
                self._driver.disable_channel(self._config.head_pitch_channel)
                self._driver.disable_channel(self._config.head_yaw_channel)
                self._driver.disable_channel(self._config.head_roll_channel)
            except Exception:
                pass

    # =========================================================================
    # PUBLIC METHODS - State Query
    # =========================================================================

    def get_current_position(self) -> Tuple[float, float, float, float]:
        """Get current head position as 4-DOF tuple.

        Returns:
            Tuple of (neck_pitch, head_pitch, head_yaw, head_roll) in degrees

        Note:
            If head is moving, returns last commanded position,
            not necessarily actual physical position.

        Example:
            >>> neck_p, head_p, head_y, head_r = head.get_current_position()
            >>> print(f"Yaw: {head_y}, Pitch: {head_p}")
        """
        with self._lock:
            return (
                self._current_neck_pitch,
                self._current_head_pitch,
                self._current_head_yaw,
                self._current_head_roll
            )

    def get_state(self) -> HeadState:
        """Get complete current 4-DOF head state.

        Returns:
            HeadState snapshot with all current 4-DOF values

        Example:
            >>> state = head.get_state()
            >>> if state.is_moving:
            ...     print(f"Moving to yaw={state.target_head_yaw}")
        """
        with self._lock:
            return HeadState(
                neck_pitch=self._current_neck_pitch,
                head_pitch=self._current_head_pitch,
                head_yaw=self._current_head_yaw,
                head_roll=self._current_head_roll,
                is_moving=self._is_moving,
                target_neck_pitch=self._target_neck_pitch,
                target_head_pitch=self._target_head_pitch,
                target_head_yaw=self._target_head_yaw,
                target_head_roll=self._target_head_roll,
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
        # FIX H-005: Use Event-based waiting instead of busy-wait polling
        if timeout_ms is not None:
            timeout_s = timeout_ms / 1000.0
        else:
            timeout_s = None

        # Wait on the completion event (set when animation finishes)
        completed = self._animation_complete.wait(timeout=timeout_s)
        return completed

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

    def _build_move_to_keyframes(
        self,
        start_neck_pitch: float,
        start_head_pitch: float,
        start_head_yaw: float,
        start_head_roll: float,
        end_neck_pitch: float,
        end_head_pitch: float,
        end_head_yaw: float,
        end_head_roll: float,
        duration_ms: int,
        easing: str
    ) -> List[_Keyframe]:
        """Build keyframes for 4-DOF move_to movement.

        Disney Principles:
        - SLOW IN/SLOW OUT: Uses specified easing
        - FOLLOW THROUGH: 5% overshoot then settle
        - ARCS: Slight curve in motion path for all 4 DOF
        """
        keyframes = []

        # Calculate motion deltas
        delta_neck_pitch = end_neck_pitch - start_neck_pitch
        delta_head_pitch = end_head_pitch - start_head_pitch
        delta_head_yaw = end_head_yaw - start_head_yaw
        delta_head_roll = end_head_roll - start_head_roll

        # Keyframe 0: Starting position
        keyframes.append(_Keyframe(
            time_ms=0,
            neck_pitch=start_neck_pitch,
            head_pitch=start_head_pitch,
            head_yaw=start_head_yaw,
            head_roll=start_head_roll,
            easing='linear'
        ))

        # FOLLOW THROUGH: Calculate overshoot position
        overshoot_neck_pitch = end_neck_pitch + delta_neck_pitch * FOLLOW_THROUGH_OVERSHOOT
        overshoot_head_pitch = end_head_pitch + delta_head_pitch * FOLLOW_THROUGH_OVERSHOOT
        overshoot_head_yaw = end_head_yaw + delta_head_yaw * FOLLOW_THROUGH_OVERSHOOT
        overshoot_head_roll = end_head_roll + delta_head_roll * FOLLOW_THROUGH_OVERSHOOT

        # Clamp overshoot to limits
        overshoot_neck_pitch = self._clamp_neck_pitch(overshoot_neck_pitch)
        overshoot_head_pitch = self._clamp_head_pitch(overshoot_head_pitch)
        overshoot_head_yaw = self._clamp_head_yaw(overshoot_head_yaw)
        overshoot_head_roll = self._clamp_head_roll(overshoot_head_roll)

        # Keyframe 1: Overshoot position (at 85% of duration)
        overshoot_time = int(duration_ms * 0.85)
        keyframes.append(_Keyframe(
            time_ms=overshoot_time,
            neck_pitch=overshoot_neck_pitch,
            head_pitch=overshoot_head_pitch,
            head_yaw=overshoot_head_yaw,
            head_roll=overshoot_head_roll,
            easing=easing
        ))

        # Keyframe 2: Final settle position
        keyframes.append(_Keyframe(
            time_ms=duration_ms,
            neck_pitch=end_neck_pitch,
            head_pitch=end_head_pitch,
            head_yaw=end_head_yaw,
            head_roll=end_head_roll,
            easing='ease_out'  # Smooth settle
        ))

        return keyframes

    def _build_nod_keyframes(
        self,
        count: int,
        amplitude: float,
        speed_ms: int
    ) -> List[_Keyframe]:
        """Build keyframes for vertical affirmation (nod) gesture.

        Disney Principles: ANTICIPATION, TIMING ASYMMETRY, FOLLOW THROUGH

        The nod movement showcases natural head motion with:
        1. ANTICIPATION: Slight upward movement before nodding down (10% amplitude)
        2. TIMING ASYMMETRY: Faster down (60% time), slower up (40% time) - gravity!
        3. FOLLOW THROUGH: Slight overshoot at bottom, smooth settle

        This mimics how real heads nod: gravity accelerates the downward motion,
        then momentum carries it slightly past, then muscles slow the return.

        Args:
            count: Number of nod cycles (typically 1-3)
            amplitude: Nod angle in degrees (typically 15-20, down is negative pitch)
            speed_ms: Time per complete nod cycle in milliseconds (typically 500)

        Returns:
            List of keyframes for complete nod sequence

        Example:
            >>> # Single affirmative nod
            >>> keyframes = self._build_nod_keyframes(
            ...     count=1,
            ...     amplitude=20.0,
            ...     speed_ms=500
            ... )
            >>> # Results in: anticipation up → fast nod down → overshoot → slow return
        """
        keyframes = []
        t = 0

        # Get current position for hold DOFs
        hold_neck_pitch = self._current_neck_pitch
        hold_head_yaw = self._current_head_yaw
        hold_head_roll = self._current_head_roll

        # FIX C-3: Each nod cycle gets its own anticipation + timing budget
        # Previously anticipation was subtracted once from total, causing
        # multi-nod animations to be ~10% shorter than expected.
        # Now each cycle = speed_ms, with anticipation inside the cycle.

        for i in range(count):
            cycle_start = t

            # ANTICIPATION: Slight upward movement before nod (Disney Principle #2)
            # 10% of amplitude, opposite direction (up before down)
            # First cycle gets full anticipation, subsequent cycles get reduced
            anticipation_scale = 1.0 if i == 0 else 0.5  # Reduced for follow-up nods
            anticipation_angle = amplitude * ANTICIPATION_RATIO * anticipation_scale
            anticipation_angle = self._clamp_head_pitch(anticipation_angle)

            anticipation_time = int(speed_ms * 0.15)

            keyframes.append(_Keyframe(
                time_ms=t,
                neck_pitch=hold_neck_pitch,
                head_pitch=anticipation_angle,  # Slight up before down
                head_yaw=hold_head_yaw,
                head_roll=hold_head_roll,
                easing='ease_in'
            ))
            t += anticipation_time

            # NOD CYCLES with TIMING ASYMMETRY (Disney Principle #9)
            # Down motion: 60% of remaining time (faster - gravity assists)
            # Up motion: 40% of remaining time (slower - fighting gravity)
            remaining_time = speed_ms - anticipation_time

            # DOWNWARD NOD (fast - gravity assisted)
            down_time = int(remaining_time * TIMING_ASYMMETRY_RATIO)

            # Calculate down position with FOLLOW THROUGH overshoot
            down_angle = -amplitude * (1.0 + FOLLOW_THROUGH_OVERSHOOT)
            down_angle = self._clamp_head_pitch(down_angle)

            keyframes.append(_Keyframe(
                time_ms=t,
                neck_pitch=hold_neck_pitch,
                head_pitch=down_angle,  # Fast down with overshoot
                head_yaw=hold_head_yaw,
                head_roll=hold_head_roll,
                easing='ease_in'  # Accelerate into the nod (gravity!)
            ))
            t += down_time

            # SETTLE at bottom (FOLLOW THROUGH - remove overshoot)
            settle_angle = self._clamp_head_pitch(-amplitude)
            settle_time = int(remaining_time * 0.1)

            keyframes.append(_Keyframe(
                time_ms=t,
                neck_pitch=hold_neck_pitch,
                head_pitch=settle_angle,  # Settle to target (no overshoot)
                head_yaw=hold_head_yaw,
                head_roll=hold_head_roll,
                easing='ease_out'  # Smooth deceleration
            ))
            t += settle_time

            # UPWARD RETURN (slower - fighting gravity)
            up_time = int(remaining_time * (1.0 - TIMING_ASYMMETRY_RATIO - 0.1))

            keyframes.append(_Keyframe(
                time_ms=t,
                neck_pitch=hold_neck_pitch,
                head_pitch=0.0,  # Return to center
                head_yaw=hold_head_yaw,
                head_roll=hold_head_roll,
                easing='ease_out'  # Slow deceleration at top
            ))

            # Advance exactly one speed_ms per cycle for predictable timing
            t = cycle_start + speed_ms

        return keyframes

    def _build_shake_keyframes(
        self,
        count: int,
        amplitude: float,
        speed_ms: int
    ) -> List[_Keyframe]:
        """Build keyframes for horizontal negation (shake) gesture.

        Disney Principles: ANTICIPATION, EXAGGERATION, DECAY

        Args:
            count: Number of shakes (typically 2)
            amplitude: Shake angle in degrees (typically 20.0)
            speed_ms: Time per shake cycle in milliseconds (typically 200)

        Returns:
            List of keyframes for complete shake sequence
        """
        keyframes = []
        t = 0
        current_amp = amplitude * FIRST_SHAKE_EXAGGERATION

        # Get current position for hold DOFs
        hold_neck_pitch = self._current_neck_pitch
        hold_head_pitch = self._current_head_pitch
        hold_head_roll = self._current_head_roll

        # ANTICIPATION: Slight opposite turn before main shake (Disney Principle #2)
        anticipation_angle = self._clamp_head_yaw(amplitude * ANTICIPATION_RATIO)
        keyframes.append(_Keyframe(
            time_ms=t,
            neck_pitch=hold_neck_pitch,
            head_pitch=hold_head_pitch,
            head_yaw=anticipation_angle,
            head_roll=hold_head_roll,
            easing='ease_in'
        ))

        # Time for anticipation (10% of shake cycle)
        t += int(speed_ms * 0.1)

        # SHAKE CYCLES with EXAGGERATION and DECAY (Disney Principles #10, #9)
        for i in range(count):
            # Left shake
            left_angle = self._clamp_head_yaw(-current_amp)
            keyframes.append(_Keyframe(
                time_ms=t,
                neck_pitch=hold_neck_pitch,
                head_pitch=hold_head_pitch,
                head_yaw=left_angle,
                head_roll=hold_head_roll,
                easing='ease_in_out'
            ))
            t += speed_ms // 2

            # Right shake
            right_angle = self._clamp_head_yaw(current_amp)
            keyframes.append(_Keyframe(
                time_ms=t,
                neck_pitch=hold_neck_pitch,
                head_pitch=hold_head_pitch,
                head_yaw=right_angle,
                head_roll=hold_head_roll,
                easing='ease_in_out'
            ))
            t += speed_ms // 2

            # DECAY: Reduce amplitude for next shake (Disney Principle #9)
            current_amp *= SHAKE_DECAY_FACTOR

        # RETURN TO CENTER: Smooth settle to neutral position
        keyframes.append(_Keyframe(
            time_ms=t,
            neck_pitch=hold_neck_pitch,
            head_pitch=hold_head_pitch,
            head_yaw=0.0,
            head_roll=hold_head_roll,
            easing='ease_in_out'
        ))

        return keyframes

    def _build_glance_keyframes(
        self,
        target_yaw: float,
        hold_ms: int,
        return_speed_ms: int
    ) -> List[_Keyframe]:
        """Build keyframes for quick glance with SECONDARY ACTION.

        Disney Principles Applied:
        --------------------------
        - SECONDARY ACTION: head_roll follows head_yaw with 150ms lag (natural weight shift)
        - STAGING: Primary action (head_yaw) is clear and readable
        - TIMING: Quick snap to target, slower return

        The glance movement showcases how SECONDARY ACTION creates natural motion:
        1. head_yaw snaps to target (PRIMARY - instant attention)
        2. head_roll follows 150ms later (SECONDARY - weight/inertia simulation)
        3. Hold position briefly (staging for readability)
        4. Return: head_roll leads (SECONDARY returns first)
        5. head_yaw follows (PRIMARY completes the cycle)

        This mimics how a real head moves: the rotation happens first,
        then the weight shift (tilt) catches up due to inertia.

        Args:
            target_yaw: Target look angle in degrees (positive = right, negative = left)
            hold_ms: How long to hold the glance position (typically 500ms)
            return_speed_ms: Time to return to center (typically 300ms)

        Returns:
            List of keyframes for complete glance sequence

        Example:
            >>> # Quick glance right with 500ms hold
            >>> keyframes = self._build_glance_keyframes(
            ...     target_yaw=30.0,
            ...     hold_ms=500,
            ...     return_speed_ms=300
            ... )
            >>> # Results in: snap right → tilt catches up → hold → untilt → return center
        """
        keyframes = []

        # Clamp target_yaw to hardware limits
        target_yaw = self._clamp_head_yaw(target_yaw)

        # FIX C-2: Preserve current neck_pitch and head_pitch during glance
        # Previously hardcoded to 0.0, causing neck/pitch to snap to zero
        hold_neck_pitch = self._current_neck_pitch
        hold_head_pitch = self._current_head_pitch

        # SECONDARY ACTION: Calculate head_roll (15% of yaw for natural weight shift)
        roll_amount = target_yaw * SECONDARY_TILT_RATIO
        roll_amount = self._clamp_head_roll(roll_amount)

        # Keyframe 0: Starting position
        # This is implicit - animation engine starts from current position

        # Keyframe 1: PRIMARY ACTION - Quick snap to target (head_yaw only)
        # TIMING: Fast snap (ease_out) for alert attention behavior
        # STAGING: Only yaw moves - makes primary action clear
        keyframes.append(_Keyframe(
            time_ms=0,
            neck_pitch=hold_neck_pitch,
            head_pitch=hold_head_pitch,
            head_yaw=target_yaw,  # PRIMARY: Instant yaw rotation
            head_roll=0.0,        # SECONDARY: Not moved yet (lag simulates inertia)
            easing='ease_out'     # Fast deceleration for snappy attention
        ))

        # Keyframe 2: SECONDARY ACTION - head_roll follows 150ms later
        # TIMING: 150ms lag simulates natural head weight/inertia
        # This is the "Pixar secret" - the delayed tilt makes it feel alive
        keyframes.append(_Keyframe(
            time_ms=150,
            neck_pitch=hold_neck_pitch,
            head_pitch=hold_head_pitch,
            head_yaw=target_yaw,    # PRIMARY: Held at target
            head_roll=roll_amount,  # SECONDARY: NOW it tilts (weight catches up)
            easing='ease_in_out'    # Smooth secondary motion
        ))

        # Keyframe 3 (implicit): Hold at glance position
        # The animation engine automatically holds the last keyframe
        # for the specified hold_ms duration

        # Keyframe 4: Return sequence - STAGING: roll leads, yaw follows
        # This is the reverse of the initial motion for natural feel
        t_return = 150 + hold_ms
        keyframes.append(_Keyframe(
            time_ms=t_return,
            neck_pitch=hold_neck_pitch,
            head_pitch=hold_head_pitch,
            head_yaw=target_yaw,  # PRIMARY: Still looking at target
            head_roll=0.0,        # SECONDARY: Roll returns first (leads the return)
            easing='ease_in'      # Accelerate into return motion
        ))

        # Keyframe 5: Complete return to center
        # Both yaw and roll are now at center (0.0)
        keyframes.append(_Keyframe(
            time_ms=t_return + return_speed_ms,
            neck_pitch=hold_neck_pitch,
            head_pitch=hold_head_pitch,
            head_yaw=0.0,   # PRIMARY: Now yaw returns to center
            head_roll=0.0,  # SECONDARY: Already at center (arrived first)
            easing='ease_in_out'  # Smooth settle to center
        ))

        return keyframes

    def _build_curious_tilt_keyframes(
        self,
        direction: str,
        angle: float,
        duration_ms: int
    ) -> List[_Keyframe]:
        """Build keyframes for Pixar-style curious head tilt.

        Disney Principles: STAGING (roll primary), SECONDARY ACTION, APPEAL

        Args:
            direction: 'left' or 'right' tilt direction
            angle: Tilt angle in degrees (typically 20.0)
            duration_ms: Total animation time (typically 400)

        Returns:
            List of keyframes for curious tilt sequence
        """
        keyframes = []

        # Direction sign
        roll_sign = 1.0 if direction == 'right' else -1.0

        # FIX C-2: Preserve current neck_pitch and head_pitch during tilt
        hold_neck_pitch = self._current_neck_pitch
        hold_head_pitch = self._current_head_pitch
        hold_head_yaw = self._current_head_yaw

        # FIX H-5: Ensure duration_ms is sufficient for all keyframes
        # Minimum duration = anticipation(80) + secondary(150) + overshoot(100) + settle(50)
        min_duration = 380
        effective_duration = max(duration_ms, min_duration)

        # Anticipation - slight tilt opposite (10% of amplitude, 80ms)
        anticipation = angle * ANTICIPATION_RATIO * (-roll_sign)
        anticipation = self._clamp_head_roll(anticipation)
        keyframes.append(_Keyframe(
            time_ms=0,
            neck_pitch=hold_neck_pitch,
            head_pitch=hold_head_pitch,
            head_yaw=hold_head_yaw,
            head_roll=anticipation,
            easing='ease_in'
        ))

        # Main tilt - PRIMARY ACTION (head_roll)
        t_main = 80
        main_roll = self._clamp_head_roll(angle * roll_sign)
        keyframes.append(_Keyframe(
            time_ms=t_main,
            neck_pitch=hold_neck_pitch,
            head_pitch=hold_head_pitch,
            head_yaw=hold_head_yaw,  # Yaw hasn't moved yet
            head_roll=main_roll,
            easing='ease_in_out'
        ))

        # SECONDARY ACTION - head_yaw follows 150ms later
        yaw_support = (angle * roll_sign) * 0.3  # 30% of roll angle
        yaw_support = self._clamp_head_yaw(yaw_support)
        t_secondary = t_main + 150
        keyframes.append(_Keyframe(
            time_ms=t_secondary,
            neck_pitch=hold_neck_pitch,
            head_pitch=hold_head_pitch,
            head_yaw=yaw_support,  # NOW yaw engages
            head_roll=main_roll,
            easing='ease_in_out'
        ))

        # Settle with slight overshoot (APPEAL)
        overshoot = self._clamp_head_roll((angle * roll_sign) * 1.05)
        t_overshoot = t_secondary + 100
        keyframes.append(_Keyframe(
            time_ms=t_overshoot,
            neck_pitch=hold_neck_pitch,
            head_pitch=hold_head_pitch,
            head_yaw=yaw_support,
            head_roll=overshoot,
            easing='ease_out'
        ))

        # Final settle
        keyframes.append(_Keyframe(
            time_ms=effective_duration,
            neck_pitch=hold_neck_pitch,
            head_pitch=hold_head_pitch,
            head_yaw=yaw_support,
            head_roll=main_roll,
            easing='ease_in_out'
        ))

        return keyframes

    # =========================================================================
    # PRIVATE METHODS - Animation Engine
    # =========================================================================

    def _start_animation(
        self,
        keyframes: List[_Keyframe],
        movement_type: HeadMovementType,
        target_neck_pitch: float,
        target_head_pitch: float,
        target_head_yaw: float,
        target_head_roll: float
    ) -> None:
        """Start animation with pre-computed 4-DOF keyframes.

        Must be called with lock held.
        """
        self._keyframes = keyframes
        self._movement_type = movement_type
        self._target_neck_pitch = target_neck_pitch
        self._target_head_pitch = target_head_pitch
        self._target_head_yaw = target_head_yaw
        self._target_head_roll = target_head_roll
        self._is_moving = True

        # Calculate total duration
        if keyframes:
            self._animation_duration_ms = keyframes[-1].time_ms
        else:
            self._animation_duration_ms = 0

        # FIX C-1: Increment generation to invalidate any zombie threads
        self._animation_generation += 1

        # Clear stop flag and start animation thread
        self._stop_animation.clear()
        self._animation_complete.clear()  # FIX H-005: Mark animation as in-progress
        self._animation_start_time = time.monotonic()

        # Pass current generation to animation thread
        current_gen = self._animation_generation
        self._animation_thread = threading.Thread(
            target=self._animation_loop,
            args=(current_gen,),
            daemon=True
        )
        self._animation_thread.start()

    def _animation_loop(self, generation: int) -> None:
        """Main animation loop running at 50Hz.

        Runs in separate thread, interpolates between keyframes.
        Exits immediately if generation counter has been incremented
        (meaning a new animation has started).
        """
        next_frame_time = time.monotonic()

        while (not self._stop_animation.is_set()
               and not self._emergency_stopped.is_set()
               and generation == self._animation_generation):
            # Calculate elapsed time
            elapsed_ms = int((time.monotonic() - self._animation_start_time) * 1000)

            # Check if animation complete
            if elapsed_ms >= self._animation_duration_ms:
                self._complete_animation()
                return

            # FIX H-3: Interpolate under lock to prevent reading stale/cleared keyframes
            with self._lock:
                if not self._is_moving:
                    return
                neck_pitch, head_pitch, head_yaw, head_roll = self._interpolate_position(elapsed_ms)
                self._move_servos_to(neck_pitch, head_pitch, head_yaw, head_roll)
                self._current_neck_pitch = neck_pitch
                self._current_head_pitch = head_pitch
                self._current_head_yaw = head_yaw
                self._current_head_roll = head_roll

            # Frame timing (50Hz)
            next_frame_time += FRAME_TIME_S
            sleep_time = next_frame_time - time.monotonic()
            if sleep_time > 0:
                time.sleep(sleep_time)
            else:
                # Frame overrun - reset timing
                next_frame_time = time.monotonic()

    def _interpolate_position(self, elapsed_ms: int) -> Tuple[float, float, float, float]:
        """Interpolate 4-DOF position at given time using keyframes.

        Uses pose-to-pose animation with easing between keyframes.

        Returns:
            Tuple of (neck_pitch, head_pitch, head_yaw, head_roll)
        """
        if not self._keyframes:
            return (
                self._current_neck_pitch,
                self._current_head_pitch,
                self._current_head_yaw,
                self._current_head_roll
            )

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

        # Interpolate all 4 DOF
        neck_pitch = prev_kf.neck_pitch + (next_kf.neck_pitch - prev_kf.neck_pitch) * eased_t
        head_pitch = prev_kf.head_pitch + (next_kf.head_pitch - prev_kf.head_pitch) * eased_t
        head_yaw = prev_kf.head_yaw + (next_kf.head_yaw - prev_kf.head_yaw) * eased_t
        head_roll = prev_kf.head_roll + (next_kf.head_roll - prev_kf.head_roll) * eased_t

        return (neck_pitch, head_pitch, head_yaw, head_roll)

    def _complete_animation(self) -> None:
        """Complete the current 4-DOF animation."""
        with self._lock:
            # Move to final position
            if self._keyframes:
                final_kf = self._keyframes[-1]
                self._move_servos_to(
                    final_kf.neck_pitch,
                    final_kf.head_pitch,
                    final_kf.head_yaw,
                    final_kf.head_roll
                )
                self._current_neck_pitch = final_kf.neck_pitch
                self._current_head_pitch = final_kf.head_pitch
                self._current_head_yaw = final_kf.head_yaw
                self._current_head_roll = final_kf.head_roll

            # Clear animation state
            movement_type = self._movement_type
            self._is_moving = False
            self._movement_type = None
            self._target_neck_pitch = None
            self._target_head_pitch = None
            self._target_head_yaw = None
            self._target_head_roll = None
            self._keyframes.clear()

            # Fire callback if set (class-level callback)
            callback = self._on_movement_complete
            # Get per-call callback (only for non-blocking calls without wait_for_completion)
            per_call_callback = self._pending_on_complete
            self._pending_on_complete = None  # Clear after retrieving

        # FIX H-005: Signal animation complete for wait_for_completion()
        self._animation_complete.set()

        # Call class-level callback outside lock to prevent deadlocks
        if callback is not None and movement_type is not None:
            try:
                callback(movement_type)
            except Exception as e:
                # FIX H-006: Log callback error for debugging instead of silent swallow
                _logger.warning(f"Movement callback error: {e}", exc_info=True)

        # Call per-call callback with success=True (animation completed normally)
        if per_call_callback is not None:
            try:
                per_call_callback(True)
            except Exception as e:
                _logger.warning(f"on_complete callback error: {e}", exc_info=True)

    def _cancel_animation_internal(self) -> None:
        """Cancel current 4-DOF animation. Must be called with lock held."""
        if self._animation_thread is not None and self._animation_thread.is_alive():
            self._stop_animation.set()
            # Don't join here - we're holding the lock

        self._is_moving = False
        self._movement_type = None
        self._target_neck_pitch = None
        self._target_head_pitch = None
        self._target_head_yaw = None
        self._target_head_roll = None
        self._keyframes.clear()

        # FIX H-001/H-005: Signal completion on cancel too
        self._animation_complete.set()

    # =========================================================================
    # PRIVATE METHODS - Servo Control
    # =========================================================================

    def _move_servos_to(
        self,
        neck_pitch: float,
        head_pitch: float,
        head_yaw: float,
        head_roll: float
    ) -> None:
        """Move all 4 servos to specified 4-DOF position.

        Converts logical angles to servo angles and commands hardware.
        """
        if self._emergency_stopped.is_set():
            return

        # Convert logical angle to servo angle
        # Formula: servo_angle = 90 + (logical_angle * direction)
        neck_pitch_direction = -1.0 if self._config.neck_pitch_inverted else 1.0
        head_pitch_direction = -1.0 if self._config.head_pitch_inverted else 1.0
        head_yaw_direction = -1.0 if self._config.head_yaw_inverted else 1.0
        head_roll_direction = -1.0 if self._config.head_roll_inverted else 1.0

        neck_pitch_servo = 90.0 + (neck_pitch * neck_pitch_direction)
        head_pitch_servo = 90.0 + (head_pitch * head_pitch_direction)
        head_yaw_servo = 90.0 + (head_yaw * head_yaw_direction)
        head_roll_servo = 90.0 + (head_roll * head_roll_direction)

        # Clamp to servo range (0-180)
        neck_pitch_servo = max(0.0, min(180.0, neck_pitch_servo))
        head_pitch_servo = max(0.0, min(180.0, head_pitch_servo))
        head_yaw_servo = max(0.0, min(180.0, head_yaw_servo))
        head_roll_servo = max(0.0, min(180.0, head_roll_servo))

        # Command all 4 servos
        try:
            self._driver.set_servo_angle(self._config.neck_pitch_channel, neck_pitch_servo)
            self._driver.set_servo_angle(self._config.head_pitch_channel, head_pitch_servo)
            self._driver.set_servo_angle(self._config.head_yaw_channel, head_yaw_servo)
            self._driver.set_servo_angle(self._config.head_roll_channel, head_roll_servo)
        except Exception as e:
            # FIX H-005: Log error for debugging instead of silent swallow
            _logger.error(f"Servo command failed: {e}", exc_info=True)

    def _clamp_neck_pitch(self, neck_pitch: float) -> float:
        """Clamp neck pitch angle to configured limits.

        Handles NaN and Infinity by returning center position (safe default).
        """
        if math.isnan(neck_pitch) or math.isinf(neck_pitch):
            return self._config.limits.neck_pitch_center
        return max(
            self._config.limits.neck_pitch_min,
            min(self._config.limits.neck_pitch_max, neck_pitch)
        )

    def _clamp_head_pitch(self, head_pitch: float) -> float:
        """Clamp head pitch angle to configured limits.

        Handles NaN and Infinity by returning center position (safe default).
        """
        if math.isnan(head_pitch) or math.isinf(head_pitch):
            return self._config.limits.head_pitch_center
        return max(
            self._config.limits.head_pitch_min,
            min(self._config.limits.head_pitch_max, head_pitch)
        )

    def _clamp_head_yaw(self, head_yaw: float) -> float:
        """Clamp head yaw angle to configured limits.

        Handles NaN and Infinity by returning center position (safe default).
        """
        if math.isnan(head_yaw) or math.isinf(head_yaw):
            return self._config.limits.head_yaw_center
        return max(
            self._config.limits.head_yaw_min,
            min(self._config.limits.head_yaw_max, head_yaw)
        )

    def _clamp_head_roll(self, head_roll: float) -> float:
        """Clamp head roll angle to configured limits.

        Handles NaN and Infinity by returning center position (safe default).
        """
        if math.isnan(head_roll) or math.isinf(head_roll):
            return self._config.limits.head_roll_center
        return max(
            self._config.limits.head_roll_min,
            min(self._config.limits.head_roll_max, head_roll)
        )

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
