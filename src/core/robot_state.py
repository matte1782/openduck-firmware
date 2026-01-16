"""Robot State Machine for OpenDuck Mini V3.

This module provides the state machine definitions for the Robot orchestrator.
The RobotState enum defines high-level robot operational states that wrap
the lower-level SafetyState from the emergency stop system.

State Machine Design:
    - RobotState tracks the robot's operational state (not hardware-level safety)
    - Three states: INIT -> READY <-> E_STOPPED
    - Transitions are validated and enforced
    - States determine which operations are allowed

State Invariants:
    INIT:
        - Allowed: start()
        - Blocked: servo commands, arm movement
        - Active: none (hardware not initialized)

    READY:
        - Allowed: servo commands, arm movement, stop(), emergency_stop()
        - Blocked: start() (already started)
        - Active: watchdog, safety monitoring, control loop

    E_STOPPED:
        - Allowed: reset() (if conditions met)
        - Blocked: servo commands, arm movement, start()
        - Active: none (all servos disabled)

Thread Safety:
    The state enum itself is immutable and thread-safe. State transitions
    in the Robot class must be protected by a lock to ensure atomicity
    of check-then-transition operations.

Example:
    >>> from src.core.robot_state import RobotState, validate_transition
    >>> current = RobotState.INIT
    >>> if validate_transition(current, RobotState.READY):
    ...     current = RobotState.READY
"""

from enum import Enum, auto
from typing import Dict, Set, Optional


class RobotState(Enum):
    """High-level robot operational state.

    States:
        INIT: Robot created but not started. Hardware not initialized.
              Call start() to transition to READY.

        READY: All systems operational, accepting commands. Control loop
               can run, servos can be commanded. This is the normal
               operating state.

        E_STOPPED: Emergency stop triggered. All servos disabled, no
                   commands accepted. Must reset() to return to READY.
    """

    INIT = auto()
    READY = auto()
    E_STOPPED = auto()


# Valid state transitions: from_state -> {allowed_to_states}
# O(1) lookup: VALID_TRANSITIONS[from_state] returns set of valid targets
# Note: INIT -> E_STOPPED allows E-stop during initialization (safety critical)
VALID_TRANSITIONS: Dict[RobotState, Set[RobotState]] = {
    RobotState.INIT: {RobotState.READY, RobotState.E_STOPPED},
    RobotState.READY: {RobotState.E_STOPPED},
    RobotState.E_STOPPED: {RobotState.READY},
}


def validate_transition(from_state: RobotState, to_state: RobotState) -> bool:
    """Check if a state transition is valid.

    This is a pure function with O(1) time complexity (set membership check).

    Args:
        from_state: Current robot state.
        to_state: Desired target state.

    Returns:
        True if the transition is valid, False otherwise.

    Example:
        >>> validate_transition(RobotState.INIT, RobotState.READY)
        True
        >>> validate_transition(RobotState.INIT, RobotState.E_STOPPED)
        False
    """
    valid_targets = VALID_TRANSITIONS.get(from_state, set())
    return to_state in valid_targets


def get_allowed_transitions(state: RobotState) -> Set[RobotState]:
    """Get the set of states that can be transitioned to from the given state.

    Args:
        state: Current robot state.

    Returns:
        Set of valid target states. Empty set if state has no valid transitions.
    """
    return VALID_TRANSITIONS.get(state, set()).copy()


# =============================================================================
# Exception Hierarchy
# =============================================================================


class RobotError(Exception):
    """Base exception for all robot-related errors.

    All robot exceptions inherit from this class, allowing callers to catch
    all robot errors with a single except clause if desired.

    Attributes:
        message: Human-readable error description.
        context: Optional dictionary with additional debugging information.
    """

    def __init__(self, message: str, context: Optional[Dict] = None) -> None:
        """Initialize robot error.

        Args:
            message: Human-readable error description.
            context: Optional dict with debugging info (state, values, etc.)
        """
        super().__init__(message)
        self.message = message
        self.context = context or {}

    def __str__(self) -> str:
        if self.context:
            ctx_str = ", ".join(f"{k}={v}" for k, v in self.context.items())
            return f"{self.message} [{ctx_str}]"
        return self.message


class RobotStateError(RobotError):
    """Invalid state transition attempted.

    Raised when an operation is attempted that is not valid for the
    current robot state, or when a state transition is invalid.

    Example:
        >>> raise RobotStateError(
        ...     "Cannot start: already running",
        ...     context={"current_state": "READY", "requested": "start"}
        ... )
    """

    def __init__(
        self,
        message: str,
        from_state: Optional[RobotState] = None,
        to_state: Optional[RobotState] = None,
        context: Optional[Dict] = None
    ) -> None:
        """Initialize state error.

        Args:
            message: Human-readable error description.
            from_state: The state the robot was in when error occurred.
            to_state: The state that was requested (if applicable).
            context: Additional debugging context.
        """
        ctx = context or {}
        if from_state is not None:
            ctx["from_state"] = from_state.name
        if to_state is not None:
            ctx["to_state"] = to_state.name
        super().__init__(message, ctx)
        self.from_state = from_state
        self.to_state = to_state


class SafetyViolationError(RobotError):
    """Safety system blocked an operation.

    Raised when an operation is blocked by the safety system, such as:
    - Movement attempted while E-stopped
    - Movement blocked due to current limiting
    - Stall condition detected

    Example:
        >>> raise SafetyViolationError(
        ...     "Movement blocked: channel stalled",
        ...     context={"channel": 0, "condition": "CONFIRMED_STALL"}
        ... )
    """

    def __init__(
        self,
        message: str,
        reason: Optional[str] = None,
        context: Optional[Dict] = None
    ) -> None:
        """Initialize safety violation error.

        Args:
            message: Human-readable error description.
            reason: Specific reason from safety system.
            context: Additional debugging context.
        """
        ctx = context or {}
        if reason is not None:
            ctx["safety_reason"] = reason
        super().__init__(message, ctx)
        self.reason = reason


class HardwareError(RobotError):
    """Hardware communication or initialization failure.

    Raised when hardware operations fail, such as:
    - I2C communication error
    - GPIO initialization failure
    - Device not responding

    Example:
        >>> raise HardwareError(
        ...     "I2C read failed",
        ...     device="PCA9685",
        ...     context={"address": "0x40", "error": "NACK"}
        ... )
    """

    def __init__(
        self,
        message: str,
        device: Optional[str] = None,
        context: Optional[Dict] = None
    ) -> None:
        """Initialize hardware error.

        Args:
            message: Human-readable error description.
            device: Name of the hardware device that failed.
            context: Additional debugging context.
        """
        ctx = context or {}
        if device is not None:
            ctx["device"] = device
        super().__init__(message, ctx)
        self.device = device
