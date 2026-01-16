"""Application Layer - Robot Core and State Machine.

This package provides the high-level robot orchestration layer:
- RobotState: State machine for robot lifecycle
- SafetyCoordinator: Unified safety system interface
- Robot: Main orchestrator class (to be implemented)
"""

from .robot_state import (
    RobotState,
    VALID_TRANSITIONS,
    validate_transition,
    get_allowed_transitions,
    RobotError,
    RobotStateError,
    SafetyViolationError,
    HardwareError,
)

from .safety_coordinator import (
    SafetyCoordinator,
    SafetyStatus,
)

from .robot import Robot

__all__ = [
    # State machine
    "RobotState",
    "VALID_TRANSITIONS",
    "validate_transition",
    "get_allowed_transitions",
    # Exceptions
    "RobotError",
    "RobotStateError",
    "SafetyViolationError",
    "HardwareError",
    # Safety coordination
    "SafetyCoordinator",
    "SafetyStatus",
    # Robot orchestrator
    "Robot",
]
