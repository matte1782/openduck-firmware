"""
Arm Joint Safety System for OpenDuck Mini V3.

Provides static and conditional joint limit enforcement for the 3-DOF arms
(shoulder_yaw, shoulder_pitch, elbow) to prevent:
  1. Mechanical damage from exceeding servo travel limits
  2. Arm-head collision when arm is in the forward zone (UPWARD pitch only)

Design Decision — Conditional Forward-Zone Limiting:
  When shoulder_yaw is within [-30, +30] (forward zone), the arm could
  physically strike the head if pitched upward. In this zone,
  shoulder_pitch_max is reduced from 90 to 30 degrees.
  Outside this zone, full pitch range is allowed.

  NOTE: Only UPWARD pitch (> forward_pitch_max) is constrained in the
  forward zone. Downward pitch (toward shoulder_pitch_min = -10) is NOT
  constrained by the forward zone because the head is above the arm rest
  plane and a downward arm motion cannot reach it. If the head mount
  geometry changes, this assumption must be re-evaluated.

Velocity enforcement is NOT yet implemented — only static position limits
are checked. Velocity checking will be added when the arm controller is
implemented (requires previous-position tracking).

Follows the same patterns as head_safety.py:
  - Validation functions return (clamped_value, Optional[SafetyEvent])
  - Never raise on invalid input — clamp and log
  - Thread-safe via atomic reads + double-check under lock
  - Bounded event history (deque maxlen=100)

Created: Day 47 Phase 4 (2 March 2026)
CAD Error Reference: ERRORE 1 in CAD_V3_CRITICAL_EVALUATION.md
Hostile Review: Day 47 — 2 CRITICAL + 4 HIGH fixed
"""

from __future__ import annotations

import enum
import logging
import math
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Deque, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ============================================================================
# JOINT LIMIT CONSTANTS (degrees)
# ============================================================================
# Source: robot_config.yaml arms.limits + CAD analysis

# Shoulder yaw (horizontal rotation)
SHOULDER_YAW_HARD_MIN: float = -120.0
SHOULDER_YAW_HARD_MAX: float = 120.0

# Shoulder pitch (elevation)
SHOULDER_PITCH_HARD_MIN: float = -10.0
SHOULDER_PITCH_HARD_MAX: float = 90.0

# Elbow (flexion only, no hyperextension)
ELBOW_HARD_MIN: float = 0.0
ELBOW_HARD_MAX: float = 135.0

# Forward collision zone — when yaw in this range, UPWARD pitch is capped
FORWARD_ZONE_YAW_MIN: float = -30.0
FORWARD_ZONE_YAW_MAX: float = 30.0
FORWARD_ZONE_PITCH_MAX: float = 30.0  # Reduced from 90 to avoid head

# Soft limit margin (degrees inside hard limits for early warning)
SOFT_LIMIT_MARGIN: float = 5.0

# Event history cap
MAX_EVENT_HISTORY: int = 100


# ============================================================================
# ENUMS
# ============================================================================

class ArmSafetyViolationType(enum.Enum):
    """Types of arm safety violations."""
    HARD_LIMIT_CLAMPED = "hard_limit_clamped"
    SOFT_LIMIT_WARNING = "soft_limit_warning"
    FORWARD_ZONE_PITCH_CLAMPED = "forward_zone_pitch_clamped"
    COLLISION_ZONE_REJECTED = "collision_zone_rejected"
    EMERGENCY_STOPPED = "emergency_stopped"
    INVALID_INPUT = "invalid_input"


class ArmSide(enum.Enum):
    """Which arm."""
    LEFT = "left"
    RIGHT = "right"


# ============================================================================
# DATA CLASSES
# ============================================================================

@dataclass
class ArmSafetyEvent:
    """Record of an arm safety event."""
    violation_type: ArmSafetyViolationType
    joint_name: str
    requested_value: float
    actual_value: float
    arm_side: ArmSide = ArmSide.LEFT
    timestamp: float = field(default_factory=time.monotonic)
    message: str = ""

    def __post_init__(self) -> None:
        if self.message:
            # CRITICAL-2 fix: INVALID_INPUT and EMERGENCY_STOPPED use critical level
            if self.violation_type in (
                ArmSafetyViolationType.INVALID_INPUT,
                ArmSafetyViolationType.EMERGENCY_STOPPED,
            ):
                logger.critical(
                    "ArmSafety CRITICAL: %s — %s",
                    self.violation_type.value, self.message,
                )
            else:
                logger.warning(
                    "ArmSafety: %s — %s",
                    self.violation_type.value, self.message,
                )


@dataclass
class ArmJointLimits:
    """Arm joint limit configuration.

    Validates all relationships in __post_init__, including that the forward
    zone is contained within the hard yaw limits and forward_pitch_max is
    within the hard pitch range.
    """
    shoulder_yaw_min: float = SHOULDER_YAW_HARD_MIN
    shoulder_yaw_max: float = SHOULDER_YAW_HARD_MAX
    shoulder_pitch_min: float = SHOULDER_PITCH_HARD_MIN
    shoulder_pitch_max: float = SHOULDER_PITCH_HARD_MAX
    elbow_min: float = ELBOW_HARD_MIN
    elbow_max: float = ELBOW_HARD_MAX

    # Forward collision zone
    forward_yaw_min: float = FORWARD_ZONE_YAW_MIN
    forward_yaw_max: float = FORWARD_ZONE_YAW_MAX
    forward_pitch_max: float = FORWARD_ZONE_PITCH_MAX

    def __post_init__(self) -> None:
        if self.shoulder_yaw_min >= self.shoulder_yaw_max:
            raise ValueError(
                f"shoulder_yaw_min ({self.shoulder_yaw_min}) must be < "
                f"shoulder_yaw_max ({self.shoulder_yaw_max})"
            )
        if self.shoulder_pitch_min >= self.shoulder_pitch_max:
            raise ValueError(
                f"shoulder_pitch_min ({self.shoulder_pitch_min}) must be < "
                f"shoulder_pitch_max ({self.shoulder_pitch_max})"
            )
        if self.elbow_min >= self.elbow_max:
            raise ValueError(
                f"elbow_min ({self.elbow_min}) must be < elbow_max ({self.elbow_max})"
            )
        if self.forward_yaw_min >= self.forward_yaw_max:
            raise ValueError(
                f"forward_yaw_min ({self.forward_yaw_min}) must be < "
                f"forward_yaw_max ({self.forward_yaw_max})"
            )
        if self.forward_pitch_max <= 0:
            raise ValueError(
                f"forward_pitch_max must be > 0, got {self.forward_pitch_max}"
            )
        # HIGH-2 fix: forward zone must be contained within hard yaw limits
        if not (self.shoulder_yaw_min <= self.forward_yaw_min
                < self.forward_yaw_max <= self.shoulder_yaw_max):
            raise ValueError(
                f"forward zone [{self.forward_yaw_min}, {self.forward_yaw_max}] "
                f"must be within shoulder_yaw limits "
                f"[{self.shoulder_yaw_min}, {self.shoulder_yaw_max}]"
            )
        if self.forward_pitch_max > self.shoulder_pitch_max:
            raise ValueError(
                f"forward_pitch_max ({self.forward_pitch_max}) must be <= "
                f"shoulder_pitch_max ({self.shoulder_pitch_max})"
            )


# ============================================================================
# VALIDATION FUNCTIONS
# ============================================================================

def _is_valid_angle(value: float) -> bool:
    """Check if a value is a valid finite number."""
    if not isinstance(value, (int, float)):
        return False
    if math.isnan(value) or math.isinf(value):
        return False
    return True


def _in_forward_zone(yaw: float, limits: ArmJointLimits) -> bool:
    """Check if yaw is inside the forward collision zone.

    Shared between enforce_forward_zone and validate_ik_solution to prevent
    logic divergence (HIGH-4 fix).
    """
    return limits.forward_yaw_min <= yaw <= limits.forward_yaw_max


def clamp_joint(
    value: float,
    joint_name: str,
    hard_min: float,
    hard_max: float,
    arm_side: ArmSide = ArmSide.LEFT,
) -> Tuple[float, List[ArmSafetyEvent]]:
    """Clamp a joint angle to hard limits.

    Returns:
        (clamped_value, list_of_events). Events are empty if no clamping needed.
    """
    events: List[ArmSafetyEvent] = []

    if not _is_valid_angle(value):
        events.append(ArmSafetyEvent(
            violation_type=ArmSafetyViolationType.INVALID_INPUT,
            joint_name=joint_name,
            requested_value=float('nan'),
            actual_value=0.0,
            arm_side=arm_side,
            message=f"Invalid {joint_name} value, clamped to 0.0",
        ))
        return 0.0, events

    clamped = max(hard_min, min(hard_max, value))
    if clamped != value:
        events.append(ArmSafetyEvent(
            violation_type=ArmSafetyViolationType.HARD_LIMIT_CLAMPED,
            joint_name=joint_name,
            requested_value=value,
            actual_value=clamped,
            arm_side=arm_side,
            message=f"{joint_name} clamped from {value:.1f} to {clamped:.1f} deg",
        ))

    return clamped, events


def check_soft_limits(
    value: float,
    joint_name: str,
    hard_min: float,
    hard_max: float,
    margin: float = SOFT_LIMIT_MARGIN,
    arm_side: ArmSide = ArmSide.LEFT,
) -> List[ArmSafetyEvent]:
    """Check if a joint angle is within soft limit margin. Returns warnings only."""
    events: List[ArmSafetyEvent] = []
    if not _is_valid_angle(value):
        return events

    soft_min = hard_min + margin
    soft_max = hard_max - margin

    if value < soft_min or value > soft_max:
        events.append(ArmSafetyEvent(
            violation_type=ArmSafetyViolationType.SOFT_LIMIT_WARNING,
            joint_name=joint_name,
            requested_value=value,
            actual_value=value,
            arm_side=arm_side,
            message=f"{joint_name} at {value:.1f} deg near hard limit",
        ))
    return events


def enforce_forward_zone(
    shoulder_yaw: float,
    shoulder_pitch: float,
    limits: ArmJointLimits,
    arm_side: ArmSide = ArmSide.LEFT,
) -> Tuple[float, List[ArmSafetyEvent]]:
    """Enforce reduced UPWARD pitch when yaw is in the forward collision zone.

    Only caps pitch ABOVE forward_pitch_max. Downward pitch is not constrained
    by the forward zone because the head is above the arm rest plane.

    If shoulder_yaw is within [forward_yaw_min, forward_yaw_max], cap
    shoulder_pitch at forward_pitch_max (upward direction only).

    Returns:
        (possibly_clamped_pitch, events)
    """
    events: List[ArmSafetyEvent] = []

    if not _is_valid_angle(shoulder_yaw) or not _is_valid_angle(shoulder_pitch):
        return shoulder_pitch, events

    if _in_forward_zone(shoulder_yaw, limits) and shoulder_pitch > limits.forward_pitch_max:
        clamped_pitch = limits.forward_pitch_max
        events.append(ArmSafetyEvent(
            violation_type=ArmSafetyViolationType.FORWARD_ZONE_PITCH_CLAMPED,
            joint_name="shoulder_pitch",
            requested_value=shoulder_pitch,
            actual_value=clamped_pitch,
            arm_side=arm_side,
            message=(
                f"Yaw={shoulder_yaw:.1f} deg in forward zone "
                f"[{limits.forward_yaw_min}, {limits.forward_yaw_max}] — "
                f"pitch clamped from {shoulder_pitch:.1f} to {clamped_pitch:.1f} deg "
                f"(upward only, head collision avoidance)"
            ),
        ))
        return clamped_pitch, events

    return shoulder_pitch, events


def validate_arm_target(
    shoulder_yaw: float,
    shoulder_pitch: float,
    elbow: float,
    limits: Optional[ArmJointLimits] = None,
    arm_side: ArmSide = ArmSide.LEFT,
) -> Tuple[Tuple[float, float, float], List[ArmSafetyEvent]]:
    """Validate and clamp a full arm target (3 joints).

    Pipeline:
        1. Clamp each joint to hard limits
        2. Enforce forward-zone upward pitch reduction
        3. Collect soft-limit warnings

    Returns:
        ((clamped_yaw, clamped_pitch, clamped_elbow), all_events)
    """
    if limits is None:
        limits = ArmJointLimits()

    all_events: List[ArmSafetyEvent] = []

    # 1. Hard-limit clamping
    yaw, yaw_events = clamp_joint(
        shoulder_yaw, "shoulder_yaw",
        limits.shoulder_yaw_min, limits.shoulder_yaw_max, arm_side,
    )
    all_events.extend(yaw_events)

    pitch, pitch_events = clamp_joint(
        shoulder_pitch, "shoulder_pitch",
        limits.shoulder_pitch_min, limits.shoulder_pitch_max, arm_side,
    )
    all_events.extend(pitch_events)

    elbow_val, elbow_events = clamp_joint(
        elbow, "elbow",
        limits.elbow_min, limits.elbow_max, arm_side,
    )
    all_events.extend(elbow_events)

    # 2. Forward-zone conditional pitch limiting (upward only)
    pitch, fz_events = enforce_forward_zone(yaw, pitch, limits, arm_side)
    all_events.extend(fz_events)

    # 3. Soft-limit warnings
    all_events.extend(check_soft_limits(
        yaw, "shoulder_yaw", limits.shoulder_yaw_min, limits.shoulder_yaw_max,
        arm_side=arm_side,
    ))
    all_events.extend(check_soft_limits(
        pitch, "shoulder_pitch", limits.shoulder_pitch_min, limits.shoulder_pitch_max,
        arm_side=arm_side,
    ))
    all_events.extend(check_soft_limits(
        elbow_val, "elbow", limits.elbow_min, limits.elbow_max,
        arm_side=arm_side,
    ))

    return (yaw, pitch, elbow_val), all_events


# ============================================================================
# ARM SAFETY COORDINATOR
# ============================================================================

class ArmSafetyCoordinator:
    """Coordinates arm safety validation with emergency stop integration.

    Thread-safe. Uses atomic threading.Event for e-stop flag.
    Double-checks e-stop under lock before returning angles (HIGH-3 TOCTOU fix).
    """

    def __init__(
        self,
        limits: Optional[ArmJointLimits] = None,
    ) -> None:
        self._limits = limits or ArmJointLimits()
        self._is_stopped = threading.Event()  # Atomic flag
        self._event_history: Deque[ArmSafetyEvent] = deque(maxlen=MAX_EVENT_HISTORY)
        self._lock = threading.RLock()

    @property
    def is_stopped(self) -> bool:
        """Check if emergency stop is active (lock-free atomic read)."""
        return self._is_stopped.is_set()

    @property
    def limits(self) -> ArmJointLimits:
        return self._limits

    @property
    def event_history(self) -> List[ArmSafetyEvent]:
        with self._lock:
            return list(self._event_history)

    def clear_history(self) -> None:
        with self._lock:
            self._event_history.clear()

    def trigger_stop(self) -> None:
        """Activate emergency stop for arms."""
        self._is_stopped.set()
        event = ArmSafetyEvent(
            violation_type=ArmSafetyViolationType.EMERGENCY_STOPPED,
            joint_name="all",
            requested_value=0.0,
            actual_value=0.0,
            message="Arm emergency stop triggered",
        )
        with self._lock:
            self._event_history.append(event)

    def reset_stop(self) -> None:
        """Clear emergency stop flag."""
        self._is_stopped.clear()

    def validate_target(
        self,
        shoulder_yaw: float,
        shoulder_pitch: float,
        elbow: float,
        arm_side: ArmSide = ArmSide.LEFT,
    ) -> Tuple[Optional[Tuple[float, float, float]], List[ArmSafetyEvent]]:
        """Validate an arm target. Returns None if e-stopped.

        Uses double-check pattern: fast lock-free check first, then
        re-checks under lock before returning angles to close TOCTOU window.

        Returns:
            (clamped_angles_or_None, events)
        """
        # Fast path: early reject if already stopped
        if self._is_stopped.is_set():
            event = ArmSafetyEvent(
                violation_type=ArmSafetyViolationType.EMERGENCY_STOPPED,
                joint_name="all",
                requested_value=0.0,
                actual_value=0.0,
                arm_side=arm_side,
                message="Arm target rejected — emergency stop active",
            )
            with self._lock:
                self._event_history.append(event)
            return None, [event]

        angles, events = validate_arm_target(
            shoulder_yaw, shoulder_pitch, elbow, self._limits, arm_side,
        )

        # Double-check under lock: close TOCTOU window (HIGH-3 fix)
        with self._lock:
            for e in events:
                self._event_history.append(e)

            if self._is_stopped.is_set():
                # E-stop was triggered during validation — discard angles
                estop_event = ArmSafetyEvent(
                    violation_type=ArmSafetyViolationType.EMERGENCY_STOPPED,
                    joint_name="all",
                    requested_value=0.0,
                    actual_value=0.0,
                    arm_side=arm_side,
                    message="Arm target discarded — emergency stop during validation",
                )
                self._event_history.append(estop_event)
                return None, events + [estop_event]

        return angles, events


# ============================================================================
# IK INTEGRATION HELPER
# ============================================================================

def validate_ik_solution(
    shoulder_yaw: float,
    shoulder_pitch: float,
    elbow: float,
    limits: Optional[ArmJointLimits] = None,
) -> bool:
    """Check if an IK solution satisfies all constraints (including forward zone).

    Returns True if the solution is valid without any clamping.
    Use this to reject IK solutions that would require safety intervention.

    Uses shared _in_forward_zone helper (HIGH-4 fix) to prevent logic
    divergence with enforce_forward_zone.
    """
    if limits is None:
        limits = ArmJointLimits()

    # Check hard limits
    if not (limits.shoulder_yaw_min <= shoulder_yaw <= limits.shoulder_yaw_max):
        return False
    if not (limits.shoulder_pitch_min <= shoulder_pitch <= limits.shoulder_pitch_max):
        return False
    if not (limits.elbow_min <= elbow <= limits.elbow_max):
        return False

    # Check forward-zone constraint (upward pitch only)
    if _in_forward_zone(shoulder_yaw, limits) and shoulder_pitch > limits.forward_pitch_max:
        return False

    return True


__all__ = [
    # Constants
    "SHOULDER_YAW_HARD_MIN", "SHOULDER_YAW_HARD_MAX",
    "SHOULDER_PITCH_HARD_MIN", "SHOULDER_PITCH_HARD_MAX",
    "ELBOW_HARD_MIN", "ELBOW_HARD_MAX",
    "FORWARD_ZONE_YAW_MIN", "FORWARD_ZONE_YAW_MAX", "FORWARD_ZONE_PITCH_MAX",
    "SOFT_LIMIT_MARGIN", "MAX_EVENT_HISTORY",
    # Enums
    "ArmSafetyViolationType", "ArmSide",
    # Data classes
    "ArmSafetyEvent", "ArmJointLimits",
    # Functions
    "clamp_joint", "check_soft_limits", "enforce_forward_zone",
    "validate_arm_target", "validate_ik_solution",
    # Classes
    "ArmSafetyCoordinator",
]
