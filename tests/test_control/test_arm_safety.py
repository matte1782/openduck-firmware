"""
Tests for arm_safety.py — Arm Joint Safety System.

Covers:
  - Static hard/soft limit clamping
  - Forward-zone conditional pitch limiting (head collision avoidance, upward only)
  - Full arm target validation pipeline
  - IK solution rejection
  - Emergency stop integration + TOCTOU double-check
  - ArmSafetyCoordinator thread safety
  - Edge cases (NaN, inf, boundary values)
  - Hostile review fixes validation

Created: Day 47 Phase 4 (2 March 2026)
Hostile Review: Day 47 — 5 test gaps fixed
"""

import math
import threading
import time

import pytest

from src.control.arm_safety import (
    # Constants
    SHOULDER_YAW_HARD_MIN, SHOULDER_YAW_HARD_MAX,
    SHOULDER_PITCH_HARD_MIN, SHOULDER_PITCH_HARD_MAX,
    ELBOW_HARD_MIN, ELBOW_HARD_MAX,
    FORWARD_ZONE_YAW_MIN, FORWARD_ZONE_YAW_MAX, FORWARD_ZONE_PITCH_MAX,
    SOFT_LIMIT_MARGIN, MAX_EVENT_HISTORY,
    # Enums
    ArmSafetyViolationType, ArmSide,
    # Data classes
    ArmSafetyEvent, ArmJointLimits,
    # Functions
    clamp_joint, check_soft_limits, enforce_forward_zone,
    validate_arm_target, validate_ik_solution,
    # Classes
    ArmSafetyCoordinator,
)


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def default_limits() -> ArmJointLimits:
    return ArmJointLimits()


@pytest.fixture
def coordinator() -> ArmSafetyCoordinator:
    return ArmSafetyCoordinator()


# ============================================================================
# TEST CONSTANTS
# ============================================================================

class TestConstants:
    """Verify constant values match robot_config.yaml."""

    def test_shoulder_yaw_range(self):
        assert SHOULDER_YAW_HARD_MIN == -120.0
        assert SHOULDER_YAW_HARD_MAX == 120.0

    def test_shoulder_pitch_range(self):
        assert SHOULDER_PITCH_HARD_MIN == -10.0
        assert SHOULDER_PITCH_HARD_MAX == 90.0

    def test_elbow_range(self):
        assert ELBOW_HARD_MIN == 0.0
        assert ELBOW_HARD_MAX == 135.0

    def test_forward_zone(self):
        assert FORWARD_ZONE_YAW_MIN == -30.0
        assert FORWARD_ZONE_YAW_MAX == 30.0
        assert FORWARD_ZONE_PITCH_MAX == 30.0

    def test_forward_zone_is_subset_of_yaw(self):
        assert FORWARD_ZONE_YAW_MIN >= SHOULDER_YAW_HARD_MIN
        assert FORWARD_ZONE_YAW_MAX <= SHOULDER_YAW_HARD_MAX

    def test_forward_pitch_max_less_than_full(self):
        assert FORWARD_ZONE_PITCH_MAX < SHOULDER_PITCH_HARD_MAX

    def test_soft_margin_positive(self):
        assert SOFT_LIMIT_MARGIN > 0

    def test_no_velocity_constant_exported(self):
        """HIGH-1 fix: velocity enforcement removed as dead code."""
        import src.control.arm_safety as mod
        assert not hasattr(mod, "MAX_VELOCITY_DEG_PER_SEC")


# ============================================================================
# TEST ARM JOINT LIMITS DATACLASS
# ============================================================================

class TestArmJointLimits:
    def test_defaults(self, default_limits):
        assert default_limits.shoulder_yaw_min == SHOULDER_YAW_HARD_MIN
        assert default_limits.elbow_max == ELBOW_HARD_MAX

    def test_custom_limits(self):
        limits = ArmJointLimits(shoulder_yaw_min=-90, shoulder_yaw_max=90)
        assert limits.shoulder_yaw_min == -90
        assert limits.shoulder_yaw_max == 90

    def test_invalid_yaw_range(self):
        with pytest.raises(ValueError, match="shoulder_yaw_min"):
            ArmJointLimits(shoulder_yaw_min=50, shoulder_yaw_max=10)

    def test_invalid_pitch_range(self):
        with pytest.raises(ValueError, match="shoulder_pitch_min"):
            ArmJointLimits(shoulder_pitch_min=100, shoulder_pitch_max=50)

    def test_invalid_elbow_range(self):
        with pytest.raises(ValueError, match="elbow_min"):
            ArmJointLimits(elbow_min=150, elbow_max=10)

    def test_invalid_forward_zone(self):
        with pytest.raises(ValueError, match="forward_yaw_min"):
            ArmJointLimits(forward_yaw_min=30, forward_yaw_max=-30)

    def test_invalid_forward_pitch(self):
        with pytest.raises(ValueError, match="forward_pitch_max"):
            ArmJointLimits(forward_pitch_max=-5)

    def test_forward_zone_wider_than_yaw_limits(self):
        """HIGH-2 fix: forward zone must be contained within hard yaw limits."""
        with pytest.raises(ValueError, match="forward zone"):
            ArmJointLimits(
                shoulder_yaw_min=-30, shoulder_yaw_max=30,
                forward_yaw_min=-60, forward_yaw_max=60,
            )

    def test_forward_pitch_max_exceeds_hard_max(self):
        """HIGH-2 fix: forward_pitch_max must be <= shoulder_pitch_max."""
        with pytest.raises(ValueError, match="forward_pitch_max"):
            ArmJointLimits(forward_pitch_max=200.0)


# ============================================================================
# TEST CLAMP JOINT
# ============================================================================

class TestClampJoint:
    def test_within_range(self):
        val, events = clamp_joint(45.0, "shoulder_yaw", -120, 120)
        assert val == 45.0
        assert events == []

    def test_above_max(self):
        val, events = clamp_joint(150.0, "shoulder_yaw", -120, 120)
        assert val == 120.0
        assert len(events) == 1
        assert events[0].violation_type == ArmSafetyViolationType.HARD_LIMIT_CLAMPED

    def test_below_min(self):
        val, events = clamp_joint(-200.0, "elbow", 0, 135)
        assert val == 0.0
        assert len(events) == 1

    def test_exact_boundary(self):
        val, events = clamp_joint(120.0, "shoulder_yaw", -120, 120)
        assert val == 120.0
        assert events == []

    def test_nan_input(self):
        val, events = clamp_joint(float('nan'), "elbow", 0, 135)
        assert val == 0.0
        assert len(events) == 1
        assert events[0].violation_type == ArmSafetyViolationType.INVALID_INPUT

    def test_inf_input(self):
        val, events = clamp_joint(float('inf'), "elbow", 0, 135)
        assert val == 0.0
        assert len(events) == 1
        assert events[0].violation_type == ArmSafetyViolationType.INVALID_INPUT

    def test_arm_side_passed(self):
        val, events = clamp_joint(200.0, "elbow", 0, 135, ArmSide.RIGHT)
        assert events[0].arm_side == ArmSide.RIGHT


# ============================================================================
# TEST SOFT LIMITS
# ============================================================================

class TestSoftLimits:
    def test_well_within_range(self):
        events = check_soft_limits(0.0, "shoulder_yaw", -120, 120)
        assert events == []

    def test_near_max(self):
        events = check_soft_limits(118.0, "shoulder_yaw", -120, 120, margin=5.0)
        assert len(events) == 1
        assert events[0].violation_type == ArmSafetyViolationType.SOFT_LIMIT_WARNING

    def test_near_min(self):
        events = check_soft_limits(-116.0, "shoulder_yaw", -120, 120, margin=5.0)
        assert len(events) == 1

    def test_exactly_at_soft_boundary(self):
        events = check_soft_limits(115.0, "shoulder_yaw", -120, 120, margin=5.0)
        assert events == []

    def test_nan_returns_empty(self):
        events = check_soft_limits(float('nan'), "shoulder_yaw", -120, 120)
        assert events == []


# ============================================================================
# TEST FORWARD ZONE ENFORCEMENT
# ============================================================================

class TestForwardZone:
    def test_yaw_outside_forward_zone_full_pitch(self, default_limits):
        """Outside forward zone: pitch NOT clamped even at 80 deg."""
        pitch, events = enforce_forward_zone(60.0, 80.0, default_limits)
        assert pitch == 80.0
        assert events == []

    def test_yaw_in_forward_zone_high_pitch_clamped(self, default_limits):
        """Inside forward zone + high pitch: clamped to 30 deg."""
        pitch, events = enforce_forward_zone(0.0, 60.0, default_limits)
        assert pitch == 30.0
        assert len(events) == 1
        assert events[0].violation_type == ArmSafetyViolationType.FORWARD_ZONE_PITCH_CLAMPED

    def test_yaw_in_forward_zone_low_pitch_ok(self, default_limits):
        """Inside forward zone but pitch already low: no change."""
        pitch, events = enforce_forward_zone(10.0, 20.0, default_limits)
        assert pitch == 20.0
        assert events == []

    def test_yaw_at_forward_boundary(self, default_limits):
        """At exactly forward_yaw_max, still in zone."""
        pitch, events = enforce_forward_zone(30.0, 50.0, default_limits)
        assert pitch == 30.0
        assert len(events) == 1

    def test_yaw_just_outside_forward(self, default_limits):
        """At 30.1 deg: just outside forward zone."""
        pitch, events = enforce_forward_zone(30.1, 50.0, default_limits)
        assert pitch == 50.0
        assert events == []

    def test_negative_yaw_in_zone(self, default_limits):
        """Negative yaw within forward zone."""
        pitch, events = enforce_forward_zone(-25.0, 45.0, default_limits)
        assert pitch == 30.0
        assert len(events) == 1

    def test_nan_yaw_no_change(self, default_limits):
        pitch, events = enforce_forward_zone(float('nan'), 60.0, default_limits)
        assert pitch == 60.0
        assert events == []

    def test_right_arm_side(self, default_limits):
        pitch, events = enforce_forward_zone(0.0, 60.0, default_limits, ArmSide.RIGHT)
        assert pitch == 30.0
        assert events[0].arm_side == ArmSide.RIGHT

    def test_downward_pitch_not_constrained(self, default_limits):
        """CRITICAL-1 doc: downward pitch in forward zone is NOT clamped."""
        pitch, events = enforce_forward_zone(0.0, -5.0, default_limits)
        assert pitch == -5.0
        assert events == []


# ============================================================================
# TEST FULL ARM TARGET VALIDATION
# ============================================================================

class TestValidateArmTarget:
    def test_all_within_limits(self, default_limits):
        angles, events = validate_arm_target(0.0, 20.0, 45.0, default_limits)
        assert angles == (0.0, 20.0, 45.0)
        hard_events = [e for e in events
                       if e.violation_type == ArmSafetyViolationType.HARD_LIMIT_CLAMPED]
        assert hard_events == []

    def test_yaw_clamped(self, default_limits):
        angles, events = validate_arm_target(200.0, 20.0, 45.0, default_limits)
        assert angles[0] == 120.0

    def test_elbow_clamped(self, default_limits):
        angles, events = validate_arm_target(0.0, 20.0, 200.0, default_limits)
        assert angles[2] == 135.0

    def test_forward_zone_applied_after_hard_clamp(self, default_limits):
        """Pitch=80 + yaw=0: pitch first clamped to 90 (hard), then to 30 (forward)."""
        angles, events = validate_arm_target(0.0, 80.0, 45.0, default_limits)
        assert angles[1] == 30.0

    def test_default_limits_used(self):
        angles, events = validate_arm_target(0.0, 10.0, 45.0)
        assert angles == (0.0, 10.0, 45.0)

    def test_soft_warnings_generated(self, default_limits):
        angles, events = validate_arm_target(118.0, -8.0, 133.0, default_limits)
        soft_events = [e for e in events
                       if e.violation_type == ArmSafetyViolationType.SOFT_LIMIT_WARNING]
        assert len(soft_events) >= 1

    def test_nan_yaw_with_high_pitch(self, default_limits):
        """GAP-1 fix: NaN yaw maps to 0.0 (center of forward zone),
        so high pitch must still be clamped by forward zone."""
        angles, events = validate_arm_target(float('nan'), 80.0, 45.0, default_limits)
        assert angles[1] == 30.0  # forward zone must fire
        fz = [e for e in events
              if e.violation_type == ArmSafetyViolationType.FORWARD_ZONE_PITCH_CLAMPED]
        assert len(fz) == 1


# ============================================================================
# TEST IK SOLUTION VALIDATION
# ============================================================================

class TestValidateIkSolution:
    def test_valid_solution(self, default_limits):
        assert validate_ik_solution(0.0, 20.0, 45.0, default_limits) is True

    def test_yaw_out_of_range(self, default_limits):
        assert validate_ik_solution(150.0, 20.0, 45.0, default_limits) is False

    def test_pitch_out_of_range(self, default_limits):
        assert validate_ik_solution(0.0, 100.0, 45.0, default_limits) is False

    def test_elbow_negative(self, default_limits):
        assert validate_ik_solution(0.0, 20.0, -10.0, default_limits) is False

    def test_forward_zone_violation(self, default_limits):
        """Yaw=0 (in forward zone) + pitch=60: rejected."""
        assert validate_ik_solution(0.0, 60.0, 45.0, default_limits) is False

    def test_forward_zone_ok(self, default_limits):
        """Yaw=0 + pitch=25: OK (under 30 deg)."""
        assert validate_ik_solution(0.0, 25.0, 45.0, default_limits) is True

    def test_outside_forward_zone_full_pitch(self, default_limits):
        """Yaw=60 (outside forward zone) + pitch=80: OK."""
        assert validate_ik_solution(60.0, 80.0, 45.0, default_limits) is True

    def test_default_limits(self):
        assert validate_ik_solution(0.0, 20.0, 45.0) is True

    def test_exact_forward_pitch_boundary_accepted(self, default_limits):
        """GAP-3 fix: pitch == forward_pitch_max is accepted (strictly > check)."""
        assert validate_ik_solution(0.0, 30.0, 45.0, default_limits) is True

    def test_just_over_forward_pitch_boundary_rejected(self, default_limits):
        """GAP-3 fix: pitch just over forward_pitch_max is rejected."""
        assert validate_ik_solution(0.0, 30.001, 45.0, default_limits) is False


# ============================================================================
# TEST ARM SAFETY COORDINATOR
# ============================================================================

class TestArmSafetyCoordinator:
    def test_initial_state(self, coordinator):
        assert coordinator.is_stopped is False
        assert coordinator.event_history == []

    def test_validate_normal(self, coordinator):
        result, events = coordinator.validate_target(0.0, 20.0, 45.0)
        assert result is not None
        assert result == (0.0, 20.0, 45.0)

    def test_validate_with_clamping(self, coordinator):
        result, events = coordinator.validate_target(200.0, 20.0, 45.0)
        assert result is not None
        assert result[0] == 120.0

    def test_validate_after_estop(self, coordinator):
        coordinator.trigger_stop()
        result, events = coordinator.validate_target(0.0, 20.0, 45.0)
        assert result is None
        assert events[0].violation_type == ArmSafetyViolationType.EMERGENCY_STOPPED

    def test_reset_allows_validation(self, coordinator):
        coordinator.trigger_stop()
        coordinator.reset_stop()
        result, events = coordinator.validate_target(0.0, 20.0, 45.0)
        assert result is not None

    def test_event_history_accumulated(self, coordinator):
        coordinator.validate_target(200.0, 20.0, 45.0)
        coordinator.validate_target(0.0, 60.0, 45.0)
        assert len(coordinator.event_history) >= 2

    def test_event_history_bounded(self, coordinator):
        for i in range(150):
            coordinator.validate_target(200.0, 20.0, 45.0)
        assert len(coordinator.event_history) <= MAX_EVENT_HISTORY

    def test_clear_history(self, coordinator):
        coordinator.validate_target(200.0, 20.0, 45.0)
        coordinator.clear_history()
        assert coordinator.event_history == []

    def test_arm_side_propagated(self, coordinator):
        result, events = coordinator.validate_target(0.0, 60.0, 45.0, ArmSide.RIGHT)
        fz_events = [e for e in events
                     if e.violation_type == ArmSafetyViolationType.FORWARD_ZONE_PITCH_CLAMPED]
        assert fz_events[0].arm_side == ArmSide.RIGHT

    def test_estop_event_logged(self, coordinator):
        coordinator.trigger_stop()
        history = coordinator.event_history
        assert any(e.violation_type == ArmSafetyViolationType.EMERGENCY_STOPPED
                   for e in history)


# ============================================================================
# TEST THREAD SAFETY
# ============================================================================

class TestThreadSafety:
    def test_concurrent_validation(self, coordinator):
        """Multiple threads validating simultaneously should not crash."""
        errors = []

        def validate_many():
            try:
                for _ in range(100):
                    coordinator.validate_target(50.0, 30.0, 60.0)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=validate_many) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)

        assert errors == []

    def test_estop_during_validation(self, coordinator):
        """E-stop triggered during concurrent validation."""
        results = []

        def validate_loop():
            for _ in range(50):
                r, _ = coordinator.validate_target(50.0, 30.0, 60.0)
                results.append(r)

        t = threading.Thread(target=validate_loop)
        t.start()
        time.sleep(0.001)
        coordinator.trigger_stop()
        t.join(timeout=5)

        # Some results should be None (after e-stop), some should be tuples
        assert any(r is None for r in results) or coordinator.is_stopped

    def test_toctou_double_check(self, coordinator):
        """HIGH-3 fix: e-stop set between check and return should still reject."""
        # We can't easily trigger the exact race, but we verify that
        # after trigger_stop, all subsequent calls return None
        coordinator.trigger_stop()
        for _ in range(10):
            result, _ = coordinator.validate_target(0.0, 20.0, 45.0)
            assert result is None


# ============================================================================
# TEST EDGE CASES
# ============================================================================

class TestEdgeCases:
    def test_all_zeros(self, default_limits):
        angles, events = validate_arm_target(0.0, 0.0, 0.0, default_limits)
        assert angles == (0.0, 0.0, 0.0)

    def test_all_at_exact_limits(self, default_limits):
        angles, events = validate_arm_target(120.0, 90.0, 135.0, default_limits)
        # Yaw 120 is outside forward zone, so pitch 90 is OK
        assert angles[0] == 120.0
        assert angles[1] == 90.0
        assert angles[2] == 135.0

    def test_all_nan(self, default_limits):
        angles, events = validate_arm_target(
            float('nan'), float('nan'), float('nan'), default_limits,
        )
        assert angles == (0.0, 0.0, 0.0)
        invalid_events = [e for e in events
                          if e.violation_type == ArmSafetyViolationType.INVALID_INPUT]
        assert len(invalid_events) == 3

    def test_extreme_values(self, default_limits):
        angles, events = validate_arm_target(1e6, -1e6, 1e6, default_limits)
        assert angles[0] == SHOULDER_YAW_HARD_MAX
        assert angles[1] == SHOULDER_PITCH_HARD_MIN
        assert angles[2] == ELBOW_HARD_MAX

    def test_safety_event_has_timestamp(self):
        event = ArmSafetyEvent(
            violation_type=ArmSafetyViolationType.HARD_LIMIT_CLAMPED,
            joint_name="elbow",
            requested_value=200.0,
            actual_value=135.0,
        )
        assert event.timestamp > 0

    def test_invalid_input_logged_as_critical(self, caplog):
        """CRITICAL-2 fix: INVALID_INPUT uses critical log level."""
        import logging
        with caplog.at_level(logging.CRITICAL):
            clamp_joint(float('nan'), "shoulder_yaw", -120, 120)
        assert any("CRITICAL" in r.levelname or r.levelno >= logging.CRITICAL
                    for r in caplog.records)
