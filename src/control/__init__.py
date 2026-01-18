"""Control Layer - Kinematics, Motion Planning, and Head Control

This module provides high-level control abstractions for the OpenDuck Mini V3:
- HeadController: 2-DOF pan/tilt head control with Disney animation principles
- HeadSafety: Bulletproof safety constraints (limits, velocity, emergency stop)
- Future: Arm kinematics, leg control, gait planning
"""

from .head_controller import (
    HeadController,
    HeadConfig,
    HeadState,
    HeadLimits,
    HeadMovementType,
)

from .head_safety import (
    # Safety Constants
    PAN_HARD_MIN, PAN_HARD_MAX, PAN_SOFT_MIN, PAN_SOFT_MAX,
    TILT_HARD_MIN, TILT_HARD_MAX, TILT_SOFT_MIN, TILT_SOFT_MAX,
    MAX_VELOCITY_DEG_PER_SEC, MAX_ACCELERATION_DEG_PER_SEC2,
    MIN_DURATION_MS, MAX_DURATION_MS, DEFAULT_DURATION_MS,
    # Enums
    SafetyViolationType, HeadEmergencyState,
    # Dataclasses
    SafetyEvent, SafetyLimits,
    # Validation functions
    clamp_to_hard_limits, check_soft_limits,
    validate_duration, validate_gesture_count, validate_amplitude,
    # Velocity/acceleration functions
    calculate_safe_duration, apply_s_curve_profile, apply_smoother_s_curve,
    generate_trajectory_points,
    # Emergency stop
    HeadEmergencyStop,
    # Coordinator
    HeadSafetyCoordinator,
)

__all__ = [
    # HeadController
    'HeadController',
    'HeadConfig',
    'HeadState',
    'HeadLimits',
    'HeadMovementType',
    # Safety Constants
    'PAN_HARD_MIN', 'PAN_HARD_MAX', 'PAN_SOFT_MIN', 'PAN_SOFT_MAX',
    'TILT_HARD_MIN', 'TILT_HARD_MAX', 'TILT_SOFT_MIN', 'TILT_SOFT_MAX',
    'MAX_VELOCITY_DEG_PER_SEC', 'MAX_ACCELERATION_DEG_PER_SEC2',
    'MIN_DURATION_MS', 'MAX_DURATION_MS', 'DEFAULT_DURATION_MS',
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
