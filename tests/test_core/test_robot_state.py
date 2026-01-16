"""Tests for RobotState enum and exception classes.

Tests verify:
- All state values are distinct
- Transition validator works correctly
- Exception classes include context for debugging
- Edge cases and error paths
"""

import pytest

from src.core.robot_state import (
    RobotState,
    VALID_TRANSITIONS,
    validate_transition,
    get_allowed_transitions,
    RobotError,
    RobotStateError,
    SafetyViolationError,
    HardwareError,
)


class TestRobotStateEnum:
    """Tests for RobotState enum definition."""

    def test_has_init_state(self):
        """Verify INIT state exists."""
        assert RobotState.INIT is not None

    def test_has_ready_state(self):
        """Verify READY state exists."""
        assert RobotState.READY is not None

    def test_has_estopped_state(self):
        """Verify E_STOPPED state exists."""
        assert RobotState.E_STOPPED is not None

    def test_exactly_three_states(self):
        """Verify exactly 3 states defined (no extra states)."""
        assert len(RobotState) == 3

    def test_states_are_distinct(self):
        """Verify all states have unique values."""
        values = [s.value for s in RobotState]
        assert len(values) == len(set(values))

    def test_states_are_comparable(self):
        """Verify states can be compared for equality."""
        assert RobotState.INIT == RobotState.INIT
        assert RobotState.INIT != RobotState.READY

    def test_state_name_property(self):
        """Verify .name property returns string name."""
        assert RobotState.INIT.name == "INIT"
        assert RobotState.READY.name == "READY"
        assert RobotState.E_STOPPED.name == "E_STOPPED"


class TestValidTransitions:
    """Tests for VALID_TRANSITIONS constant."""

    def test_all_states_have_transition_entry(self):
        """Verify every state has an entry in VALID_TRANSITIONS."""
        for state in RobotState:
            assert state in VALID_TRANSITIONS

    def test_init_can_transition_to_ready(self):
        """Verify INIT -> READY is valid."""
        assert RobotState.READY in VALID_TRANSITIONS[RobotState.INIT]

    def test_init_can_transition_to_estopped(self):
        """Verify INIT -> E_STOPPED IS valid (for safety during initialization)."""
        assert RobotState.E_STOPPED in VALID_TRANSITIONS[RobotState.INIT]

    def test_ready_can_transition_to_estopped(self):
        """Verify READY -> E_STOPPED is valid."""
        assert RobotState.E_STOPPED in VALID_TRANSITIONS[RobotState.READY]

    def test_ready_cannot_transition_to_init(self):
        """Verify READY -> INIT is NOT valid (no going back)."""
        assert RobotState.INIT not in VALID_TRANSITIONS[RobotState.READY]

    def test_estopped_can_transition_to_ready(self):
        """Verify E_STOPPED -> READY is valid (reset)."""
        assert RobotState.READY in VALID_TRANSITIONS[RobotState.E_STOPPED]

    def test_estopped_cannot_transition_to_init(self):
        """Verify E_STOPPED -> INIT is NOT valid."""
        assert RobotState.INIT not in VALID_TRANSITIONS[RobotState.E_STOPPED]


class TestValidateTransition:
    """Tests for validate_transition() function."""

    def test_valid_init_to_ready(self):
        """Verify INIT -> READY returns True."""
        assert validate_transition(RobotState.INIT, RobotState.READY) is True

    def test_valid_ready_to_estopped(self):
        """Verify READY -> E_STOPPED returns True."""
        assert validate_transition(RobotState.READY, RobotState.E_STOPPED) is True

    def test_valid_estopped_to_ready(self):
        """Verify E_STOPPED -> READY returns True."""
        assert validate_transition(RobotState.E_STOPPED, RobotState.READY) is True

    def test_valid_init_to_estopped(self):
        """Verify INIT -> E_STOPPED returns True (safety during initialization)."""
        assert validate_transition(RobotState.INIT, RobotState.E_STOPPED) is True

    def test_invalid_ready_to_init(self):
        """Verify READY -> INIT returns False."""
        assert validate_transition(RobotState.READY, RobotState.INIT) is False

    def test_invalid_self_transition_init(self):
        """Verify INIT -> INIT returns False (no self-loops)."""
        assert validate_transition(RobotState.INIT, RobotState.INIT) is False

    def test_invalid_self_transition_ready(self):
        """Verify READY -> READY returns False."""
        assert validate_transition(RobotState.READY, RobotState.READY) is False

    def test_invalid_self_transition_estopped(self):
        """Verify E_STOPPED -> E_STOPPED returns False."""
        assert validate_transition(RobotState.E_STOPPED, RobotState.E_STOPPED) is False


class TestGetAllowedTransitions:
    """Tests for get_allowed_transitions() function."""

    def test_returns_set(self):
        """Verify returns a set type."""
        result = get_allowed_transitions(RobotState.INIT)
        assert isinstance(result, set)

    def test_returns_copy(self):
        """Verify returns a copy (modifying result doesn't affect original)."""
        result = get_allowed_transitions(RobotState.INIT)
        original_size = len(VALID_TRANSITIONS[RobotState.INIT])
        result.add(RobotState.INIT)  # Add self-transition (never valid)
        assert len(VALID_TRANSITIONS[RobotState.INIT]) == original_size

    def test_init_transitions(self):
        """Verify INIT allowed transitions (includes E_STOPPED for safety)."""
        result = get_allowed_transitions(RobotState.INIT)
        assert result == {RobotState.READY, RobotState.E_STOPPED}

    def test_ready_transitions(self):
        """Verify READY allowed transitions."""
        result = get_allowed_transitions(RobotState.READY)
        assert result == {RobotState.E_STOPPED}

    def test_estopped_transitions(self):
        """Verify E_STOPPED allowed transitions."""
        result = get_allowed_transitions(RobotState.E_STOPPED)
        assert result == {RobotState.READY}


class TestRobotError:
    """Tests for RobotError base exception class."""

    def test_simple_message(self):
        """Verify simple error message works."""
        error = RobotError("Something went wrong")
        assert str(error) == "Something went wrong"
        assert error.message == "Something went wrong"

    def test_with_context(self):
        """Verify context is included in string representation."""
        error = RobotError("Failed", context={"key": "value"})
        assert "key=value" in str(error)
        assert error.context["key"] == "value"

    def test_inherits_from_exception(self):
        """Verify RobotError inherits from Exception."""
        assert issubclass(RobotError, Exception)

    def test_empty_context_default(self):
        """Verify empty context defaults to empty dict."""
        error = RobotError("Test")
        assert error.context == {}

    def test_can_be_raised_and_caught(self):
        """Verify exception can be raised and caught."""
        with pytest.raises(RobotError) as exc_info:
            raise RobotError("Test error")
        assert "Test error" in str(exc_info.value)


class TestRobotStateError:
    """Tests for RobotStateError exception class."""

    def test_inherits_from_robot_error(self):
        """Verify inherits from RobotError."""
        assert issubclass(RobotStateError, RobotError)

    def test_simple_message(self):
        """Verify simple error message works."""
        error = RobotStateError("Invalid transition")
        assert "Invalid transition" in str(error)

    def test_with_states(self):
        """Verify states are included in context."""
        error = RobotStateError(
            "Cannot transition",
            from_state=RobotState.INIT,
            to_state=RobotState.E_STOPPED
        )
        assert error.from_state == RobotState.INIT
        assert error.to_state == RobotState.E_STOPPED
        assert "from_state=INIT" in str(error)
        assert "to_state=E_STOPPED" in str(error)

    def test_with_additional_context(self):
        """Verify additional context is preserved."""
        error = RobotStateError(
            "Error",
            from_state=RobotState.READY,
            context={"extra": "data"}
        )
        assert "extra=data" in str(error)
        assert error.context["extra"] == "data"

    def test_can_be_caught_as_robot_error(self):
        """Verify can be caught with except RobotError."""
        with pytest.raises(RobotError):
            raise RobotStateError("Test")


class TestSafetyViolationError:
    """Tests for SafetyViolationError exception class."""

    def test_inherits_from_robot_error(self):
        """Verify inherits from RobotError."""
        assert issubclass(SafetyViolationError, RobotError)

    def test_simple_message(self):
        """Verify simple error message works."""
        error = SafetyViolationError("Movement blocked")
        assert "Movement blocked" in str(error)

    def test_with_reason(self):
        """Verify reason is included in context."""
        error = SafetyViolationError(
            "Movement blocked",
            reason="Current limit exceeded"
        )
        assert error.reason == "Current limit exceeded"
        assert "safety_reason=Current limit exceeded" in str(error)

    def test_with_additional_context(self):
        """Verify additional context is preserved."""
        error = SafetyViolationError(
            "Blocked",
            reason="stall",
            context={"channel": 0}
        )
        assert error.context["channel"] == 0

    def test_can_be_caught_as_robot_error(self):
        """Verify can be caught with except RobotError."""
        with pytest.raises(RobotError):
            raise SafetyViolationError("Test")


class TestHardwareError:
    """Tests for HardwareError exception class."""

    def test_inherits_from_robot_error(self):
        """Verify inherits from RobotError."""
        assert issubclass(HardwareError, RobotError)

    def test_simple_message(self):
        """Verify simple error message works."""
        error = HardwareError("I2C error")
        assert "I2C error" in str(error)

    def test_with_device(self):
        """Verify device is included in context."""
        error = HardwareError("Read failed", device="PCA9685")
        assert error.device == "PCA9685"
        assert "device=PCA9685" in str(error)

    def test_with_additional_context(self):
        """Verify additional context is preserved."""
        error = HardwareError(
            "Communication error",
            device="BNO085",
            context={"address": "0x4A"}
        )
        assert error.context["address"] == "0x4A"

    def test_can_be_caught_as_robot_error(self):
        """Verify can be caught with except RobotError."""
        with pytest.raises(RobotError):
            raise HardwareError("Test")


class TestExceptionHierarchy:
    """Tests for exception class hierarchy."""

    def test_all_exceptions_inherit_from_robot_error(self):
        """Verify all custom exceptions inherit from RobotError."""
        assert issubclass(RobotStateError, RobotError)
        assert issubclass(SafetyViolationError, RobotError)
        assert issubclass(HardwareError, RobotError)

    def test_catching_robot_error_catches_all(self):
        """Verify catching RobotError catches all subclasses."""
        exceptions = [
            RobotStateError("state error"),
            SafetyViolationError("safety error"),
            HardwareError("hardware error"),
        ]
        for exc in exceptions:
            try:
                raise exc
            except RobotError:
                pass  # Should catch all
            else:
                pytest.fail(f"{type(exc).__name__} not caught by RobotError")

    def test_specific_exceptions_are_distinct(self):
        """Verify each exception type can be caught specifically."""
        with pytest.raises(RobotStateError):
            raise RobotStateError("test")

        with pytest.raises(SafetyViolationError):
            raise SafetyViolationError("test")

        with pytest.raises(HardwareError):
            raise HardwareError("test")
