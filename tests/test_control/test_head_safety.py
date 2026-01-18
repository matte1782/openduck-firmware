"""Comprehensive Test Suite for Head Safety Module.

Tests all safety-critical functions for the HeadController:
- Hard limit clamping
- Soft limit warnings
- Velocity limiting
- Acceleration/S-curve profiles
- Emergency stop functionality
- Duration and count validation
- Amplitude validation
- Safety coordinator integration

Test Coverage Target: 90%+
Quality Standard: Boston Dynamics / Robotics Safety Grade

Author: Safety & Limits Engineer (Agent 2C)
Created: 18 January 2026
"""

import math
import threading
import time
from typing import List
from unittest.mock import MagicMock, patch

import pytest

from src.control.head_safety import (
    # Constants
    PAN_HARD_MIN, PAN_HARD_MAX, PAN_SOFT_MIN, PAN_SOFT_MAX,
    TILT_HARD_MIN, TILT_HARD_MAX, TILT_SOFT_MIN, TILT_SOFT_MAX,
    MAX_VELOCITY_DEG_PER_SEC, MAX_ACCELERATION_DEG_PER_SEC2,
    MIN_DURATION_MS, MAX_DURATION_MS, DEFAULT_DURATION_MS,
    MIN_GESTURE_COUNT, MAX_GESTURE_COUNT,
    MIN_AMPLITUDE_DEG, MAX_NOD_AMPLITUDE_DEG, MAX_SHAKE_AMPLITUDE_DEG,
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


# =============================================================================
# TEST FIXTURES
# =============================================================================

@pytest.fixture
def default_limits() -> SafetyLimits:
    """Create default safety limits for testing."""
    return SafetyLimits()


@pytest.fixture
def emergency_stop() -> HeadEmergencyStop:
    """Create fresh emergency stop instance for testing."""
    return HeadEmergencyStop()


@pytest.fixture
def safety_coordinator() -> HeadSafetyCoordinator:
    """Create fresh safety coordinator for testing."""
    return HeadSafetyCoordinator()


# =============================================================================
# SAFETY CONSTANTS TESTS
# =============================================================================

class TestSafetyConstants:
    """Test that safety constants are properly defined."""

    def test_pan_hard_limits_valid(self):
        """Pan hard limits should define valid range."""
        assert PAN_HARD_MIN < PAN_HARD_MAX
        assert PAN_HARD_MIN == -90.0
        assert PAN_HARD_MAX == 90.0

    def test_tilt_hard_limits_valid(self):
        """Tilt hard limits should define valid range."""
        assert TILT_HARD_MIN < TILT_HARD_MAX
        assert TILT_HARD_MIN == -45.0
        assert TILT_HARD_MAX == 45.0

    def test_soft_limits_within_hard_limits(self):
        """Soft limits should be within hard limits."""
        assert PAN_HARD_MIN <= PAN_SOFT_MIN < PAN_SOFT_MAX <= PAN_HARD_MAX
        assert TILT_HARD_MIN <= TILT_SOFT_MIN < TILT_SOFT_MAX <= TILT_HARD_MAX

    def test_velocity_limit_positive(self):
        """Velocity limit should be positive."""
        assert MAX_VELOCITY_DEG_PER_SEC > 0
        assert MAX_VELOCITY_DEG_PER_SEC == 180.0

    def test_acceleration_limit_positive(self):
        """Acceleration limit should be positive."""
        assert MAX_ACCELERATION_DEG_PER_SEC2 > 0
        assert MAX_ACCELERATION_DEG_PER_SEC2 == 800.0

    def test_duration_limits_valid(self):
        """Duration limits should be valid."""
        assert MIN_DURATION_MS > 0
        assert MIN_DURATION_MS < MAX_DURATION_MS
        assert MIN_DURATION_MS <= DEFAULT_DURATION_MS <= MAX_DURATION_MS

    def test_gesture_count_limits_valid(self):
        """Gesture count limits should be valid."""
        assert MIN_GESTURE_COUNT > 0
        assert MIN_GESTURE_COUNT < MAX_GESTURE_COUNT
        assert MAX_GESTURE_COUNT == 5

    def test_amplitude_limits_valid(self):
        """Amplitude limits should be valid."""
        assert MIN_AMPLITUDE_DEG > 0
        assert MAX_NOD_AMPLITUDE_DEG > MIN_AMPLITUDE_DEG
        assert MAX_SHAKE_AMPLITUDE_DEG > MIN_AMPLITUDE_DEG


# =============================================================================
# SAFETY LIMITS DATACLASS TESTS
# =============================================================================

class TestSafetyLimits:
    """Test SafetyLimits dataclass validation."""

    def test_default_limits_valid(self, default_limits: SafetyLimits):
        """Default limits should be valid."""
        assert default_limits.pan_hard_min == PAN_HARD_MIN
        assert default_limits.pan_hard_max == PAN_HARD_MAX
        assert default_limits.max_velocity == MAX_VELOCITY_DEG_PER_SEC

    def test_custom_limits_valid(self):
        """Custom valid limits should be accepted."""
        limits = SafetyLimits(
            pan_hard_min=-60.0,
            pan_hard_max=60.0,
            pan_soft_min=-50.0,
            pan_soft_max=50.0,
            tilt_hard_min=-30.0,
            tilt_hard_max=30.0,
            tilt_soft_min=-25.0,
            tilt_soft_max=25.0,
        )
        assert limits.pan_hard_max == 60.0

    def test_invalid_pan_hard_limits_raises(self):
        """Pan hard min >= max should raise ValueError."""
        with pytest.raises(ValueError, match="pan_hard_min"):
            SafetyLimits(pan_hard_min=90.0, pan_hard_max=-90.0)

    def test_invalid_tilt_hard_limits_raises(self):
        """Tilt hard min >= max should raise ValueError."""
        with pytest.raises(ValueError, match="tilt_hard_min"):
            SafetyLimits(tilt_hard_min=45.0, tilt_hard_max=-45.0)

    def test_pan_soft_outside_hard_raises(self):
        """Pan soft limits outside hard limits should raise."""
        with pytest.raises(ValueError, match="Pan soft limits"):
            SafetyLimits(
                pan_hard_min=-90.0,
                pan_hard_max=90.0,
                pan_soft_min=-100.0,  # Outside hard limit
                pan_soft_max=80.0,
            )

    def test_tilt_soft_outside_hard_raises(self):
        """Tilt soft limits outside hard limits should raise."""
        with pytest.raises(ValueError, match="Tilt soft limits"):
            SafetyLimits(
                tilt_hard_min=-45.0,
                tilt_hard_max=45.0,
                tilt_soft_min=-40.0,
                tilt_soft_max=50.0,  # Outside hard limit
            )

    def test_zero_velocity_raises(self):
        """Zero velocity should raise ValueError."""
        with pytest.raises(ValueError, match="max_velocity"):
            SafetyLimits(max_velocity=0.0)

    def test_negative_acceleration_raises(self):
        """Negative acceleration should raise ValueError."""
        with pytest.raises(ValueError, match="max_acceleration"):
            SafetyLimits(max_acceleration=-100.0)


# =============================================================================
# HARD LIMIT CLAMPING TESTS
# =============================================================================

class TestClampToHardLimits:
    """Test hard limit clamping functionality."""

    def test_values_within_limits_unchanged(self, default_limits: SafetyLimits):
        """Values within limits should not be modified."""
        pan, tilt, events = clamp_to_hard_limits(0.0, 0.0, default_limits)
        assert pan == 0.0
        assert tilt == 0.0
        assert len(events) == 0

    def test_pan_clamped_to_max(self, default_limits: SafetyLimits):
        """Pan exceeding max should be clamped."""
        pan, tilt, events = clamp_to_hard_limits(100.0, 0.0, default_limits)
        assert pan == PAN_HARD_MAX
        assert tilt == 0.0
        assert len(events) == 1
        assert events[0].violation_type == SafetyViolationType.HARD_LIMIT_EXCEEDED
        assert events[0].axis == 'pan'

    def test_pan_clamped_to_min(self, default_limits: SafetyLimits):
        """Pan below min should be clamped."""
        pan, tilt, events = clamp_to_hard_limits(-100.0, 0.0, default_limits)
        assert pan == PAN_HARD_MIN
        assert len(events) == 1

    def test_tilt_clamped_to_max(self, default_limits: SafetyLimits):
        """Tilt exceeding max should be clamped."""
        pan, tilt, events = clamp_to_hard_limits(0.0, 60.0, default_limits)
        assert tilt == TILT_HARD_MAX
        assert len(events) == 1
        assert events[0].axis == 'tilt'

    def test_tilt_clamped_to_min(self, default_limits: SafetyLimits):
        """Tilt below min should be clamped."""
        pan, tilt, events = clamp_to_hard_limits(0.0, -60.0, default_limits)
        assert tilt == TILT_HARD_MIN
        assert len(events) == 1

    def test_both_axes_clamped(self, default_limits: SafetyLimits):
        """Both axes should be clamped independently."""
        pan, tilt, events = clamp_to_hard_limits(200.0, -100.0, default_limits)
        assert pan == PAN_HARD_MAX
        assert tilt == TILT_HARD_MIN
        assert len(events) == 2

    def test_exact_limit_values_no_event(self, default_limits: SafetyLimits):
        """Values exactly at limits should not generate events."""
        pan, tilt, events = clamp_to_hard_limits(
            PAN_HARD_MAX, TILT_HARD_MIN, default_limits
        )
        assert pan == PAN_HARD_MAX
        assert tilt == TILT_HARD_MIN
        assert len(events) == 0

    def test_extreme_values_clamped(self, default_limits: SafetyLimits):
        """Extreme values (inf, large numbers) should be clamped."""
        pan, tilt, events = clamp_to_hard_limits(float('inf'), -float('inf'))
        assert pan == PAN_HARD_MAX
        assert tilt == TILT_HARD_MIN
        assert len(events) == 2

    def test_default_limits_used_when_none(self):
        """Default limits should be used when not specified."""
        pan, tilt, events = clamp_to_hard_limits(100.0, 0.0, None)
        assert pan == PAN_HARD_MAX


# =============================================================================
# SOFT LIMIT WARNING TESTS
# =============================================================================

class TestCheckSoftLimits:
    """Test soft limit warning functionality."""

    def test_within_soft_limits_no_warning(self, default_limits: SafetyLimits):
        """Values within soft limits should not generate warnings."""
        events = check_soft_limits(0.0, 0.0, default_limits)
        assert len(events) == 0

    def test_pan_outside_soft_generates_warning(self, default_limits: SafetyLimits):
        """Pan outside soft limits should generate warning."""
        events = check_soft_limits(85.0, 0.0, default_limits)  # Outside soft max
        assert len(events) == 1
        assert events[0].violation_type == SafetyViolationType.SOFT_LIMIT_WARNING
        assert events[0].axis == 'pan'

    def test_tilt_outside_soft_generates_warning(self, default_limits: SafetyLimits):
        """Tilt outside soft limits should generate warning."""
        events = check_soft_limits(0.0, -42.0, default_limits)  # Outside soft min
        assert len(events) == 1
        assert events[0].axis == 'tilt'

    def test_both_outside_soft_two_warnings(self, default_limits: SafetyLimits):
        """Both axes outside soft limits should generate two warnings."""
        events = check_soft_limits(85.0, 42.0, default_limits)
        assert len(events) == 2

    def test_at_soft_limit_no_warning(self, default_limits: SafetyLimits):
        """Values exactly at soft limits should not generate warnings."""
        events = check_soft_limits(PAN_SOFT_MAX, TILT_SOFT_MIN, default_limits)
        assert len(events) == 0


# =============================================================================
# DURATION VALIDATION TESTS
# =============================================================================

class TestValidateDuration:
    """Test duration validation functionality."""

    def test_none_returns_default(self):
        """None duration should return default."""
        duration, event = validate_duration(None)
        assert duration == DEFAULT_DURATION_MS
        assert event is None

    def test_valid_duration_unchanged(self):
        """Valid duration should not be modified."""
        duration, event = validate_duration(500)
        assert duration == 500
        assert event is None

    def test_below_minimum_clamped(self):
        """Duration below minimum should be clamped."""
        duration, event = validate_duration(5)
        assert duration == MIN_DURATION_MS
        assert event is not None
        assert event.violation_type == SafetyViolationType.INVALID_DURATION

    def test_above_maximum_clamped(self):
        """Duration above maximum should be clamped."""
        duration, event = validate_duration(20000)
        assert duration == MAX_DURATION_MS
        assert event is not None

    def test_exact_minimum_valid(self):
        """Exact minimum duration should be valid."""
        duration, event = validate_duration(MIN_DURATION_MS)
        assert duration == MIN_DURATION_MS
        assert event is None

    def test_exact_maximum_valid(self):
        """Exact maximum duration should be valid."""
        duration, event = validate_duration(MAX_DURATION_MS)
        assert duration == MAX_DURATION_MS
        assert event is None


# =============================================================================
# GESTURE COUNT VALIDATION TESTS
# =============================================================================

class TestValidateGestureCount:
    """Test gesture count validation."""

    def test_valid_count_unchanged(self):
        """Valid count should not be modified."""
        count, event = validate_gesture_count(3)
        assert count == 3
        assert event is None

    def test_below_minimum_clamped(self):
        """Count below minimum should be clamped."""
        count, event = validate_gesture_count(0)
        assert count == MIN_GESTURE_COUNT
        assert event is not None
        assert event.violation_type == SafetyViolationType.INVALID_COUNT

    def test_above_maximum_clamped(self):
        """Count above maximum should be clamped."""
        count, event = validate_gesture_count(10)
        assert count == MAX_GESTURE_COUNT
        assert event is not None

    def test_negative_count_clamped(self):
        """Negative count should be clamped."""
        count, event = validate_gesture_count(-5)
        assert count == MIN_GESTURE_COUNT
        assert event is not None


# =============================================================================
# AMPLITUDE VALIDATION TESTS
# =============================================================================

class TestValidateAmplitude:
    """Test amplitude validation."""

    def test_valid_amplitude_unchanged(self, default_limits: SafetyLimits):
        """Valid amplitude should not be modified."""
        amplitude, event = validate_amplitude(15.0, 0.0, False, default_limits)
        assert amplitude == 15.0
        assert event is None

    def test_amplitude_exceeds_max_nod(self, default_limits: SafetyLimits):
        """Amplitude exceeding max nod should be clamped."""
        amplitude, event = validate_amplitude(50.0, 0.0, False, default_limits)
        assert amplitude <= MAX_NOD_AMPLITUDE_DEG

    def test_amplitude_exceeds_max_shake(self, default_limits: SafetyLimits):
        """Amplitude exceeding max shake should be clamped."""
        amplitude, event = validate_amplitude(60.0, 0.0, True, default_limits)
        assert amplitude <= MAX_SHAKE_AMPLITUDE_DEG

    def test_amplitude_limited_by_position(self, default_limits: SafetyLimits):
        """Amplitude should be limited based on current position."""
        # At pan = 80, max amplitude toward 90 is only 10 degrees
        amplitude, event = validate_amplitude(30.0, 80.0, True, default_limits)
        assert amplitude == 10.0  # Limited by distance to hard limit
        assert event is not None
        assert event.violation_type == SafetyViolationType.INVALID_AMPLITUDE

    def test_amplitude_at_limit_zero(self, default_limits: SafetyLimits):
        """At hard limit, amplitude should be clamped to safe value."""
        amplitude, event = validate_amplitude(20.0, PAN_HARD_MAX, True, default_limits)
        assert amplitude == 0.0  # Can only go one direction, but symmetric amplitude

    def test_negative_amplitude_made_positive(self, default_limits: SafetyLimits):
        """Negative amplitude should be made positive."""
        amplitude, event = validate_amplitude(-15.0, 0.0, False, default_limits)
        assert amplitude == 15.0


# =============================================================================
# VELOCITY LIMITING TESTS
# =============================================================================

class TestCalculateSafeDuration:
    """Test velocity limiting and duration calculation."""

    def test_slow_movement_unchanged(self):
        """Slow movements should not have duration modified."""
        # 90 degrees in 1000ms = 90 deg/s (below 180 limit)
        duration, event = calculate_safe_duration(90.0, 1000)
        assert duration == 1000
        assert event is None

    def test_fast_movement_stretched(self):
        """Fast movements should have duration stretched."""
        # 180 degrees in 500ms = 360 deg/s (exceeds 180 limit)
        duration, event = calculate_safe_duration(180.0, 500)
        assert duration >= 1000  # Should be at least 1000ms for 180 deg at 180 deg/s
        assert event is not None
        assert event.violation_type == SafetyViolationType.VELOCITY_EXCEEDED

    def test_exact_velocity_limit(self):
        """Movement at exactly max velocity should not be modified."""
        # 180 degrees in 1000ms = 180 deg/s (exactly at limit)
        duration, event = calculate_safe_duration(180.0, 1000)
        assert duration == 1000
        assert event is None

    def test_zero_distance_unchanged(self):
        """Zero distance should not modify duration."""
        duration, event = calculate_safe_duration(0.0, 500)
        assert duration == 500
        assert event is None

    def test_minimum_duration_enforced(self):
        """Minimum duration should be enforced."""
        duration, event = calculate_safe_duration(1.0, 5)  # Very short
        assert duration >= MIN_DURATION_MS

    def test_custom_velocity_limit(self):
        """Custom velocity limit should be respected."""
        # 90 degrees in 500ms = 180 deg/s, but limit is 100
        duration, event = calculate_safe_duration(90.0, 500, max_velocity=100.0)
        assert duration >= 900  # 90 deg at 100 deg/s = 900ms
        assert event is not None


# =============================================================================
# S-CURVE PROFILE TESTS
# =============================================================================

class TestSCurveProfile:
    """Test S-curve acceleration profiles."""

    def test_s_curve_endpoints(self):
        """S-curve should start at 0 and end at 1."""
        assert apply_s_curve_profile(0.0) == pytest.approx(0.0)
        assert apply_s_curve_profile(1.0) == pytest.approx(1.0)

    def test_s_curve_midpoint(self):
        """S-curve midpoint should be 0.5."""
        assert apply_s_curve_profile(0.5) == pytest.approx(0.5)

    def test_s_curve_symmetry(self):
        """S-curve should be symmetric around midpoint."""
        for t in [0.1, 0.2, 0.3, 0.4]:
            left = apply_s_curve_profile(t)
            right = 1.0 - apply_s_curve_profile(1.0 - t)
            assert left == pytest.approx(right, abs=1e-10)

    def test_s_curve_monotonic(self):
        """S-curve should be monotonically increasing."""
        prev = -1.0
        for i in range(101):
            t = i / 100.0
            val = apply_s_curve_profile(t)
            assert val >= prev
            prev = val

    def test_s_curve_clamps_input(self):
        """S-curve should clamp input to [0, 1]."""
        assert apply_s_curve_profile(-0.5) == pytest.approx(0.0)
        assert apply_s_curve_profile(1.5) == pytest.approx(1.0)

    def test_smoother_s_curve_endpoints(self):
        """Smootherstep should start at 0 and end at 1."""
        assert apply_smoother_s_curve(0.0) == pytest.approx(0.0)
        assert apply_smoother_s_curve(1.0) == pytest.approx(1.0)

    def test_smoother_s_curve_midpoint(self):
        """Smootherstep midpoint should be 0.5."""
        assert apply_smoother_s_curve(0.5) == pytest.approx(0.5)

    def test_smoother_s_curve_monotonic(self):
        """Smootherstep should be monotonically increasing."""
        prev = -1.0
        for i in range(101):
            t = i / 100.0
            val = apply_smoother_s_curve(t)
            assert val >= prev
            prev = val


# =============================================================================
# TRAJECTORY GENERATION TESTS
# =============================================================================

class TestGenerateTrajectoryPoints:
    """Test trajectory point generation."""

    def test_trajectory_endpoints(self):
        """Trajectory should start and end at correct angles."""
        points = generate_trajectory_points(0.0, 90.0, 1000)
        assert points[0] == (0, 0.0)
        assert points[-1][0] == 1000
        assert points[-1][1] == pytest.approx(90.0)

    def test_trajectory_point_count(self):
        """Trajectory should have approximately correct number of points."""
        # 1000ms at 50Hz = 50 frames + endpoints
        points = generate_trajectory_points(0.0, 90.0, 1000, update_rate_hz=50)
        assert len(points) >= 50

    def test_trajectory_monotonic_with_s_curve(self):
        """Trajectory angles should be monotonically increasing."""
        points = generate_trajectory_points(0.0, 90.0, 1000, use_s_curve=True)
        prev_angle = -float('inf')
        for time_ms, angle in points:
            assert angle >= prev_angle - 0.001  # Small tolerance for floating point
            prev_angle = angle

    def test_trajectory_without_s_curve(self):
        """Trajectory without S-curve should be linear."""
        points = generate_trajectory_points(0.0, 90.0, 1000, use_s_curve=False)
        # Middle point should be exactly 45 degrees at 500ms
        mid_point = [p for p in points if 490 <= p[0] <= 510]
        assert len(mid_point) > 0
        assert mid_point[0][1] == pytest.approx(45.0, abs=1.0)

    def test_trajectory_zero_duration(self):
        """Zero duration should return single endpoint."""
        points = generate_trajectory_points(0.0, 90.0, 0)
        assert len(points) == 1
        assert points[0][1] == 90.0

    def test_trajectory_negative_movement(self):
        """Trajectory should handle movement in negative direction."""
        points = generate_trajectory_points(90.0, 0.0, 1000)
        assert points[0][1] == 90.0
        assert points[-1][1] == pytest.approx(0.0)


# =============================================================================
# EMERGENCY STOP TESTS
# =============================================================================

class TestHeadEmergencyStop:
    """Test emergency stop functionality."""

    def test_initial_state_normal(self, emergency_stop: HeadEmergencyStop):
        """Emergency stop should start in normal state."""
        assert emergency_stop.state == HeadEmergencyState.NORMAL
        assert not emergency_stop.is_stopped
        assert emergency_stop.trigger_reason is None

    def test_trigger_sets_stopped(self, emergency_stop: HeadEmergencyStop):
        """Trigger should set stopped flag immediately."""
        emergency_stop.trigger("test reason")
        assert emergency_stop.is_stopped
        assert emergency_stop.state == HeadEmergencyState.STOPPED
        assert emergency_stop.trigger_reason == "test reason"

    def test_trigger_returns_latency(self, emergency_stop: HeadEmergencyStop):
        """Trigger should return latency in milliseconds."""
        latency = emergency_stop.trigger("test")
        assert isinstance(latency, float)
        assert latency >= 0
        assert latency < 100  # Should be very fast

    def test_reset_clears_stopped(self, emergency_stop: HeadEmergencyStop):
        """Reset should clear stopped flag."""
        emergency_stop.trigger("test")
        assert emergency_stop.is_stopped
        result = emergency_stop.reset()
        assert result is True
        assert not emergency_stop.is_stopped
        assert emergency_stop.state == HeadEmergencyState.NORMAL

    def test_reset_requires_stopped_state(self, emergency_stop: HeadEmergencyStop):
        """Reset should fail if not in stopped state."""
        result = emergency_stop.reset()
        assert result is False
        assert emergency_stop.state == HeadEmergencyState.NORMAL

    def test_callback_invoked_on_trigger(self, emergency_stop: HeadEmergencyStop):
        """Registered callback should be invoked on trigger."""
        callback_called = threading.Event()

        def callback():
            callback_called.set()

        emergency_stop.register_callback(callback)
        emergency_stop.trigger("test")
        assert callback_called.is_set()

    def test_multiple_callbacks_all_invoked(self, emergency_stop: HeadEmergencyStop):
        """All registered callbacks should be invoked."""
        call_count = [0]

        def callback1():
            call_count[0] += 1

        def callback2():
            call_count[0] += 1

        emergency_stop.register_callback(callback1)
        emergency_stop.register_callback(callback2)
        emergency_stop.trigger("test")
        assert call_count[0] == 2

    def test_callback_exception_does_not_block(self, emergency_stop: HeadEmergencyStop):
        """Exception in callback should not block emergency stop."""
        def bad_callback():
            raise RuntimeError("Callback error")

        def good_callback():
            pass

        emergency_stop.register_callback(bad_callback)
        emergency_stop.register_callback(good_callback)

        # Should not raise
        emergency_stop.trigger("test")
        assert emergency_stop.is_stopped

    def test_unregister_callback(self, emergency_stop: HeadEmergencyStop):
        """Unregistered callback should not be invoked."""
        call_count = [0]

        def callback():
            call_count[0] += 1

        emergency_stop.register_callback(callback)
        result = emergency_stop.unregister_callback(callback)
        assert result is True

        emergency_stop.trigger("test")
        assert call_count[0] == 0

    def test_unregister_nonexistent_callback(self, emergency_stop: HeadEmergencyStop):
        """Unregistering non-existent callback should return False."""
        def callback():
            pass

        result = emergency_stop.unregister_callback(callback)
        assert result is False

    def test_is_stopped_atomic(self, emergency_stop: HeadEmergencyStop):
        """is_stopped should be readable without lock (atomic).

        This tests that is_stopped can be read very quickly without blocking,
        even if another thread triggers the emergency stop.
        """
        # First verify that is_stopped starts as False
        assert not emergency_stop.is_stopped

        # Trigger and verify it becomes True immediately
        emergency_stop.trigger("test")
        assert emergency_stop.is_stopped

        # Now test that we can read is_stopped rapidly from another thread
        # while the main thread has triggered the stop
        results = []

        def reader():
            for _ in range(1000):
                results.append(emergency_stop.is_stopped)

        thread = threading.Thread(target=reader)
        thread.start()
        thread.join()

        # All results should be True since trigger already happened
        assert all(results), "All reads should see is_stopped=True after trigger"

        # Also verify the flag is truly atomic by checking read performance
        start = time.perf_counter()
        for _ in range(10000):
            _ = emergency_stop.is_stopped
        elapsed_ms = (time.perf_counter() - start) * 1000

        # Reading is_stopped 10000 times should take well under 10ms
        assert elapsed_ms < 10.0, f"Atomic read took {elapsed_ms}ms for 10000 reads"

    def test_thread_safety_multiple_triggers(self, emergency_stop: HeadEmergencyStop):
        """Multiple simultaneous triggers should not cause issues."""
        def trigger_repeatedly():
            for i in range(100):
                emergency_stop.trigger(f"thread trigger {i}")

        threads = [threading.Thread(target=trigger_repeatedly) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Should still be in stopped state
        assert emergency_stop.is_stopped


# =============================================================================
# SAFETY COORDINATOR TESTS
# =============================================================================

class TestHeadSafetyCoordinator:
    """Test safety coordinator integration."""

    def test_validate_target_clamps_to_limits(self, safety_coordinator: HeadSafetyCoordinator):
        """validate_target should clamp to hard limits."""
        pan, tilt = safety_coordinator.validate_target(100.0, -60.0)
        assert pan == PAN_HARD_MAX
        assert tilt == TILT_HARD_MIN

    def test_validate_target_stores_events(self, safety_coordinator: HeadSafetyCoordinator):
        """validate_target should store safety events."""
        safety_coordinator.validate_target(100.0, 0.0)
        events = safety_coordinator.get_event_history()
        assert len(events) >= 1

    def test_validate_target_raises_when_stopped(self, safety_coordinator: HeadSafetyCoordinator):
        """validate_target should raise when emergency stopped."""
        safety_coordinator.emergency_stop.trigger("test")
        with pytest.raises(RuntimeError, match="emergency stop active"):
            safety_coordinator.validate_target(0.0, 0.0)

    def test_validate_movement_returns_safe_duration(self, safety_coordinator: HeadSafetyCoordinator):
        """validate_movement should return velocity-limited duration."""
        # 180 degrees in 500ms is too fast
        duration = safety_coordinator.validate_movement(0.0, 0.0, 180.0, 0.0, 500)
        assert duration >= 1000

    def test_validate_movement_raises_when_stopped(self, safety_coordinator: HeadSafetyCoordinator):
        """validate_movement should raise when emergency stopped."""
        safety_coordinator.emergency_stop.trigger("test")
        with pytest.raises(RuntimeError, match="emergency stop active"):
            safety_coordinator.validate_movement(0.0, 0.0, 90.0, 0.0, 500)

    def test_validate_gesture_returns_safe_values(self, safety_coordinator: HeadSafetyCoordinator):
        """validate_gesture should return validated parameters."""
        count, amplitude, speed = safety_coordinator.validate_gesture(
            count=10,  # Exceeds max
            amplitude=100.0,  # Exceeds max
            current_position=0.0,
            is_pan=True,
            speed_ms=5  # Below min
        )
        assert count == MAX_GESTURE_COUNT
        assert amplitude <= MAX_SHAKE_AMPLITUDE_DEG
        assert speed >= MIN_DURATION_MS

    def test_validate_gesture_raises_when_stopped(self, safety_coordinator: HeadSafetyCoordinator):
        """validate_gesture should raise when emergency stopped."""
        safety_coordinator.emergency_stop.trigger("test")
        with pytest.raises(RuntimeError, match="emergency stop active"):
            safety_coordinator.validate_gesture(2, 15.0, 0.0, True, 200)

    def test_event_history_limit(self, safety_coordinator: HeadSafetyCoordinator):
        """Event history should not exceed max size."""
        # Generate more events than the max
        for i in range(150):
            safety_coordinator.validate_target(100.0 + i, 0.0)

        events = safety_coordinator.get_event_history()
        assert len(events) <= safety_coordinator.MAX_EVENT_HISTORY

    def test_clear_event_history(self, safety_coordinator: HeadSafetyCoordinator):
        """clear_event_history should remove all events."""
        safety_coordinator.validate_target(100.0, 0.0)
        assert len(safety_coordinator.get_event_history()) > 0

        safety_coordinator.clear_event_history()
        assert len(safety_coordinator.get_event_history()) == 0


# =============================================================================
# SAFETY EVENT TESTS
# =============================================================================

class TestSafetyEvent:
    """Test SafetyEvent dataclass."""

    def test_safety_event_logging(self, caplog):
        """SafetyEvent should log on creation based on severity."""
        import logging
        with caplog.at_level(logging.WARNING):
            event = SafetyEvent(
                timestamp=time.monotonic(),
                violation_type=SafetyViolationType.HARD_LIMIT_EXCEEDED,
                requested_value=100.0,
                clamped_value=90.0,
                message="Test hard limit",
                axis='pan'
            )
        assert "SAFETY" in caplog.text
        assert "Hard limit" in caplog.text


# =============================================================================
# INTEGRATION TESTS
# =============================================================================

class TestSafetyIntegration:
    """Integration tests for complete safety workflow."""

    def test_complete_look_at_workflow(self, safety_coordinator: HeadSafetyCoordinator):
        """Test complete safety validation for look_at movement."""
        # 1. Validate target (clamps to limits)
        target_pan, target_tilt = safety_coordinator.validate_target(100.0, -60.0)

        # 2. Validate movement (ensures safe velocity)
        current_pan, current_tilt = 0.0, 0.0
        duration = safety_coordinator.validate_movement(
            current_pan, current_tilt,
            target_pan, target_tilt,
            300  # Fast movement
        )

        # 3. Generate trajectory
        points = generate_trajectory_points(
            current_pan, target_pan, duration
        )

        # Verify safety constraints
        assert target_pan == PAN_HARD_MAX
        assert target_tilt == TILT_HARD_MIN
        assert duration >= 300  # May be stretched for velocity
        assert len(points) > 0

    def test_complete_gesture_workflow(self, safety_coordinator: HeadSafetyCoordinator):
        """Test complete safety validation for gesture movement."""
        # 1. Validate gesture parameters
        count, amplitude, speed = safety_coordinator.validate_gesture(
            count=3,
            amplitude=20.0,
            current_position=70.0,  # Near pan limit
            is_pan=True,
            speed_ms=200
        )

        # Amplitude should be limited due to proximity to limit
        assert amplitude <= 20.0  # May be reduced
        assert count == 3
        assert speed >= MIN_DURATION_MS

    def test_emergency_stop_blocks_all_operations(self, safety_coordinator: HeadSafetyCoordinator):
        """Emergency stop should block all validation operations."""
        safety_coordinator.emergency_stop.trigger("safety test")

        with pytest.raises(RuntimeError):
            safety_coordinator.validate_target(0.0, 0.0)

        with pytest.raises(RuntimeError):
            safety_coordinator.validate_movement(0.0, 0.0, 0.0, 0.0, 100)

        with pytest.raises(RuntimeError):
            safety_coordinator.validate_gesture(1, 10.0, 0.0, True, 100)

    def test_reset_allows_operations(self, safety_coordinator: HeadSafetyCoordinator):
        """Reset should allow operations to resume."""
        safety_coordinator.emergency_stop.trigger("test")
        safety_coordinator.emergency_stop.reset()

        # Should not raise
        pan, tilt = safety_coordinator.validate_target(45.0, 20.0)
        assert pan == 45.0
        assert tilt == 20.0


# =============================================================================
# PERFORMANCE TESTS
# =============================================================================

class TestSafetyPerformance:
    """Performance tests for safety-critical operations."""

    def test_emergency_stop_latency(self, emergency_stop: HeadEmergencyStop):
        """Emergency stop should trigger in under 1ms."""
        latencies = []
        for _ in range(100):
            e_stop = HeadEmergencyStop()
            latency = e_stop.trigger("perf test")
            latencies.append(latency)

        avg_latency = sum(latencies) / len(latencies)
        max_latency = max(latencies)

        # Average should be well under 1ms
        assert avg_latency < 1.0, f"Average latency {avg_latency}ms exceeds 1ms"
        # Max should be under 5ms (accounting for OS scheduling)
        assert max_latency < 5.0, f"Max latency {max_latency}ms exceeds 5ms"

    def test_clamp_performance(self, default_limits: SafetyLimits):
        """Clamping should complete in under 0.1ms per call.

        Note: We test with values within limits to measure pure clamping
        performance without logging overhead. Logging is tested separately.
        """
        iterations = 10000
        start = time.perf_counter()
        for i in range(iterations):
            # Use values within limits to avoid logging overhead
            clamp_to_hard_limits(
                (i % 180) - 90,  # -90 to 89
                (i % 90) - 45,   # -45 to 44
                default_limits
            )
        elapsed_ms = (time.perf_counter() - start) * 1000

        avg_per_call = elapsed_ms / iterations
        assert avg_per_call < 0.1, f"Avg {avg_per_call}ms per clamp exceeds 0.1ms"

    def test_s_curve_performance(self):
        """S-curve calculation should complete in under 0.01ms per call."""
        iterations = 100000
        start = time.perf_counter()
        for i in range(iterations):
            apply_s_curve_profile(i / iterations)
        elapsed_ms = (time.perf_counter() - start) * 1000

        avg_per_call = elapsed_ms / iterations
        assert avg_per_call < 0.01, f"Avg {avg_per_call}ms per s-curve exceeds 0.01ms"

    def test_trajectory_generation_performance(self):
        """Trajectory generation should complete in under 5ms for 1 second movement."""
        iterations = 100
        start = time.perf_counter()
        for _ in range(iterations):
            generate_trajectory_points(0.0, 90.0, 1000)
        elapsed_ms = (time.perf_counter() - start) * 1000

        avg_per_call = elapsed_ms / iterations
        assert avg_per_call < 5.0, f"Avg {avg_per_call}ms per trajectory exceeds 5ms"


# =============================================================================
# EDGE CASE TESTS
# =============================================================================

class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_nan_values_handled(self, default_limits: SafetyLimits):
        """NaN values should be clamped safely."""
        pan, tilt, events = clamp_to_hard_limits(float('nan'), float('nan'), default_limits)
        # NaN comparison is always False, so should clamp to some limit
        assert not math.isnan(pan)
        assert not math.isnan(tilt)

    def test_very_small_duration(self):
        """Very small duration should be handled."""
        duration, event = validate_duration(1)
        assert duration == MIN_DURATION_MS

    def test_very_large_values(self, default_limits: SafetyLimits):
        """Very large values should be clamped."""
        pan, tilt, events = clamp_to_hard_limits(1e10, -1e10, default_limits)
        assert pan == PAN_HARD_MAX
        assert tilt == TILT_HARD_MIN

    def test_zero_amplitude(self, default_limits: SafetyLimits):
        """Zero amplitude should be valid."""
        amplitude, event = validate_amplitude(0.0, 0.0, True, default_limits)
        assert amplitude == 0.0
        assert event is None

    def test_trajectory_same_start_end(self):
        """Trajectory with same start/end should work."""
        points = generate_trajectory_points(45.0, 45.0, 1000)
        assert len(points) >= 1
        assert all(p[1] == pytest.approx(45.0) for p in points)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
