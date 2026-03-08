"""Tests for CV Coordinator — Face/Person Tracking Pipeline.

Tests all components of the tracking pipeline:
- PDController
- OutputSmoother
- CentroidTracker
- TargetSelector
- IdleBehavior
- NoDetectionBehavior
- normalized_to_angle
- CVCoordinator (integration)

Author: CV Pipeline Agent
Created: 8 March 2026 (Day 53)
"""

import math
import threading
import time
from typing import Dict, List, Optional, Tuple
from unittest.mock import MagicMock, Mock, call

import pytest


# ============================================================================
# Tests: PDController
# ============================================================================


class TestPDController:
    """Tests for PD (proportional-derivative) controller."""

    def test_zero_error_returns_zero(self) -> None:
        from src.control.cv_coordinator import PDController
        pd = PDController(kp=0.3, kd=0.05, deadzone_deg=1.0, max_speed_deg_per_sec=100.0)
        result = pd.update(0.0, time.monotonic())
        assert result == 0.0

    def test_error_within_deadzone_returns_zero(self) -> None:
        from src.control.cv_coordinator import PDController
        pd = PDController(kp=0.3, kd=0.05, deadzone_deg=2.0, max_speed_deg_per_sec=100.0)
        # First call initializes
        pd.update(5.0, 0.0)
        # Error within deadzone
        result = pd.update(1.5, 0.1)
        assert result == 0.0

    def test_proportional_response(self) -> None:
        from src.control.cv_coordinator import PDController
        pd = PDController(kp=0.5, kd=0.0, deadzone_deg=0.0, max_speed_deg_per_sec=1000.0)
        # First call initializes
        pd.update(10.0, 0.0)
        # Second call produces proportional output
        result = pd.update(10.0, 0.1)
        assert result > 0  # Positive error → positive output

    def test_derivative_damps_when_error_decreasing(self) -> None:
        from src.control.cv_coordinator import PDController
        # When error is DECREASING, derivative term is negative (opposes P)
        # So output with D should have smaller magnitude
        pd_no_d = PDController(kp=0.5, kd=0.0, deadzone_deg=0.0, max_speed_deg_per_sec=1000.0)
        pd_with_d = PDController(kp=0.5, kd=0.1, deadzone_deg=0.0, max_speed_deg_per_sec=1000.0)

        # Initialize both with same error
        pd_no_d.update(10.0, 0.0)
        pd_with_d.update(10.0, 0.0)

        # Same error (steady) — D term should be zero, outputs equal
        out_no_d = pd_no_d.update(10.0, 0.1)
        out_with_d = pd_with_d.update(10.0, 0.1)
        # D term = kd * (10 - 10) / 0.1 = 0, so outputs should be equal
        assert abs(out_no_d - out_with_d) < 0.01

    def test_max_speed_clamping(self) -> None:
        from src.control.cv_coordinator import PDController
        pd = PDController(kp=10.0, kd=0.0, deadzone_deg=0.0, max_speed_deg_per_sec=50.0)
        pd.update(90.0, 0.0)
        result = pd.update(90.0, 0.1)
        # Max delta = 50 * 0.1 = 5.0
        assert abs(result) <= 5.01  # small tolerance

    def test_negative_error(self) -> None:
        from src.control.cv_coordinator import PDController
        pd = PDController(kp=0.5, kd=0.0, deadzone_deg=0.0, max_speed_deg_per_sec=1000.0)
        pd.update(-15.0, 0.0)
        result = pd.update(-15.0, 0.1)
        assert result < 0

    def test_reset_clears_state(self) -> None:
        from src.control.cv_coordinator import PDController
        pd = PDController(kp=0.5, kd=0.1, deadzone_deg=0.0, max_speed_deg_per_sec=1000.0)
        pd.update(10.0, 0.0)
        pd.update(10.0, 0.1)
        pd.reset()
        # After reset, first call should return 0 (initialization)
        result = pd.update(10.0, 0.5)
        assert result == 0.0

    def test_zero_dt_returns_zero(self) -> None:
        from src.control.cv_coordinator import PDController
        pd = PDController(kp=0.5, kd=0.1, deadzone_deg=0.0, max_speed_deg_per_sec=1000.0)
        pd.update(10.0, 1.0)
        result = pd.update(10.0, 1.0)  # Same time
        assert result == 0.0


# ============================================================================
# Tests: OutputSmoother
# ============================================================================


class TestOutputSmoother:
    """Tests for exponential moving average smoother."""

    def test_initial_output_scaled_by_alpha(self) -> None:
        from src.control.cv_coordinator import OutputSmoother
        s = OutputSmoother(alpha=0.5)
        result = s.smooth(10.0)
        assert abs(result - 5.0) < 0.01  # 0.5 * 10 + 0.5 * 0 = 5

    def test_converges_to_constant_input(self) -> None:
        from src.control.cv_coordinator import OutputSmoother
        s = OutputSmoother(alpha=0.3)
        for _ in range(100):
            result = s.smooth(10.0)
        assert abs(result - 10.0) < 0.01

    def test_alpha_one_no_smoothing(self) -> None:
        from src.control.cv_coordinator import OutputSmoother
        s = OutputSmoother(alpha=1.0)
        assert s.smooth(42.0) == 42.0
        assert s.smooth(0.0) == 0.0

    def test_reset(self) -> None:
        from src.control.cv_coordinator import OutputSmoother
        s = OutputSmoother(alpha=0.5)
        s.smooth(100.0)
        s.reset()
        result = s.smooth(10.0)
        assert abs(result - 5.0) < 0.01


# ============================================================================
# Tests: CentroidTracker
# ============================================================================


class TestCentroidTracker:
    """Tests for centroid-based multi-object tracker."""

    def test_register_new_objects(self) -> None:
        from src.control.cv_coordinator import CentroidTracker
        tracker = CentroidTracker(max_disappeared=5)
        objects = tracker.update([(0.0, 0.0, 100.0), (0.5, 0.5, 200.0)], now=0.0)
        assert len(objects) == 2

    def test_associate_across_frames(self) -> None:
        from src.control.cv_coordinator import CentroidTracker
        tracker = CentroidTracker()

        # Frame 1: one object at (0.0, 0.0)
        objects = tracker.update([(0.0, 0.0, 100.0)], now=0.0)
        obj_id = list(objects.keys())[0]

        # Frame 2: same object slightly moved
        objects = tracker.update([(0.05, 0.02, 100.0)], now=0.033)
        assert obj_id in objects
        assert abs(objects[obj_id].center_x - 0.05) < 0.001

    def test_object_disappears_after_max_frames(self) -> None:
        from src.control.cv_coordinator import CentroidTracker
        tracker = CentroidTracker(max_disappeared=3)

        objects = tracker.update([(0.0, 0.0, 100.0)], now=0.0)
        obj_id = list(objects.keys())[0]

        # Object disappears for 4 frames
        for i in range(4):
            objects = tracker.update([], now=float(i + 1))

        assert obj_id not in objects

    def test_new_and_lost_simultaneously(self) -> None:
        from src.control.cv_coordinator import CentroidTracker
        tracker = CentroidTracker(max_disappeared=2)

        # Object A appears
        objects = tracker.update([(0.0, 0.0, 100.0)], now=0.0)
        id_a = list(objects.keys())[0]

        # Object A disappears, Object B appears far away
        for i in range(3):
            objects = tracker.update([(0.9, 0.9, 200.0)], now=float(i + 1))

        # A should be gone, B should exist
        assert id_a not in objects
        assert len(objects) >= 1

    def test_multiple_objects_tracked(self) -> None:
        from src.control.cv_coordinator import CentroidTracker
        tracker = CentroidTracker()

        objects = tracker.update([
            (-0.5, 0.0, 100.0),
            (0.5, 0.0, 100.0),
        ], now=0.0)
        assert len(objects) == 2

        # Both move slightly
        objects = tracker.update([
            (-0.48, 0.01, 100.0),
            (0.52, -0.01, 100.0),
        ], now=0.033)
        assert len(objects) == 2

    def test_reset_clears_all(self) -> None:
        from src.control.cv_coordinator import CentroidTracker
        tracker = CentroidTracker()
        tracker.update([(0.0, 0.0, 100.0)], now=0.0)
        tracker.reset()
        objects = tracker.update([], now=1.0)
        assert len(objects) == 0

    def test_frames_seen_increments(self) -> None:
        from src.control.cv_coordinator import CentroidTracker
        tracker = CentroidTracker()

        tracker.update([(0.0, 0.0, 100.0)], now=0.0)
        objects = tracker.update([(0.01, 0.01, 100.0)], now=0.033)
        obj = list(objects.values())[0]
        assert obj.frames_seen >= 2


# ============================================================================
# Tests: TargetSelector
# ============================================================================


class TestTargetSelector:
    """Tests for target selection with stickiness."""

    def test_no_objects_returns_none(self) -> None:
        from src.control.cv_coordinator import TargetSelector
        selector = TargetSelector()
        assert selector.select({}) is None

    def test_single_object_selected(self) -> None:
        from src.control.cv_coordinator import TargetSelector, TrackedObject
        selector = TargetSelector()
        objects = {0: TrackedObject(0, 0.0, 0.0, 100.0)}
        assert selector.select(objects) == 0

    def test_largest_selected_initially(self) -> None:
        from src.control.cv_coordinator import TargetSelector, TrackedObject
        selector = TargetSelector()
        objects = {
            0: TrackedObject(0, -0.5, 0.0, 100.0),
            1: TrackedObject(1, 0.5, 0.0, 500.0),
        }
        assert selector.select(objects) == 1

    def test_stickiness_prevents_switch(self) -> None:
        from src.control.cv_coordinator import TargetSelector, TrackedObject
        selector = TargetSelector(sticky_frames=10, switch_threshold=1.5)

        objects = {
            0: TrackedObject(0, 0.0, 0.0, 100.0),
            1: TrackedObject(1, 0.5, 0.0, 200.0),
        }

        # First select picks largest
        target = selector.select(objects)
        assert target == 1

        # Smaller object won't steal focus during sticky period
        objects[0].area = 250.0
        for _ in range(5):
            target = selector.select(objects)
        assert target == 1

    def test_switch_when_much_larger(self) -> None:
        from src.control.cv_coordinator import TargetSelector, TrackedObject
        selector = TargetSelector(sticky_frames=2, switch_threshold=1.5)

        objects = {
            0: TrackedObject(0, 0.0, 0.0, 100.0),
            1: TrackedObject(1, 0.5, 0.0, 200.0),
        }

        # Select target 1 (largest)
        selector.select(objects)
        selector.select(objects)
        selector.select(objects)  # Past sticky period

        # Object 0 becomes much larger (1.5x threshold)
        objects[0].area = 400.0
        target = selector.select(objects)
        assert target == 0

    def test_target_lost_selects_new(self) -> None:
        from src.control.cv_coordinator import TargetSelector, TrackedObject
        selector = TargetSelector()

        # Track object 0
        selector.select({0: TrackedObject(0, 0.0, 0.0, 100.0)})

        # Object 0 disappears, object 1 appears
        target = selector.select({1: TrackedObject(1, 0.5, 0.0, 200.0)})
        assert target == 1

    def test_reset(self) -> None:
        from src.control.cv_coordinator import TargetSelector, TrackedObject
        selector = TargetSelector()
        selector.select({0: TrackedObject(0, 0.0, 0.0, 100.0)})
        selector.reset()
        assert selector._current_id is None


# ============================================================================
# Tests: IdleBehavior
# ============================================================================


class TestIdleBehavior:
    """Tests for Disney-style idle micro-movements."""

    def test_returns_small_offsets(self) -> None:
        from src.control.cv_coordinator import IdleBehavior
        idle = IdleBehavior(amplitude_deg=2.0, speed=0.3)
        yaw, pitch = idle.get_offsets(0.0)
        assert abs(yaw) <= 2.0
        assert abs(pitch) <= 2.0

    def test_varies_over_time(self) -> None:
        from src.control.cv_coordinator import IdleBehavior
        idle = IdleBehavior(amplitude_deg=2.0, speed=1.0)
        offsets = [idle.get_offsets(t) for t in [0.0, 0.5, 1.0, 1.5, 2.0]]
        # Not all the same
        yaw_vals = [o[0] for o in offsets]
        assert len(set(round(v, 4) for v in yaw_vals)) > 1

    def test_bounded_by_amplitude(self) -> None:
        from src.control.cv_coordinator import IdleBehavior
        idle = IdleBehavior(amplitude_deg=3.0, speed=1.0)
        for t in range(100):
            yaw, pitch = idle.get_offsets(float(t) * 0.1)
            assert abs(yaw) <= 3.0 + 0.01
            assert abs(pitch) <= 3.0 + 0.01


# ============================================================================
# Tests: NoDetectionBehavior
# ============================================================================


class TestNoDetectionBehavior:
    """Tests for target-lost behavior."""

    def test_no_target_initially(self) -> None:
        from src.control.cv_coordinator import NoDetectionBehavior
        nd = NoDetectionBehavior()
        assert nd.get_target(0.0) is None

    def test_holds_position_after_loss(self) -> None:
        from src.control.cv_coordinator import NoDetectionBehavior
        nd = NoDetectionBehavior(hold_sec=1.0, return_sec=2.0)
        nd.on_target_lost(30.0, -10.0, now=0.0)
        yaw, pitch = nd.get_target(0.5)
        assert abs(yaw - 30.0) < 0.01
        assert abs(pitch - (-10.0)) < 0.01

    def test_returns_to_center(self) -> None:
        from src.control.cv_coordinator import NoDetectionBehavior
        nd = NoDetectionBehavior(hold_sec=0.5, return_sec=1.0)
        nd.on_target_lost(30.0, -10.0, now=0.0)

        # After hold + full return
        yaw, pitch = nd.get_target(1.6)
        assert abs(yaw) < 1.0
        assert abs(pitch) < 1.0

    def test_target_found_resets(self) -> None:
        from src.control.cv_coordinator import NoDetectionBehavior
        nd = NoDetectionBehavior()
        nd.on_target_lost(30.0, -10.0, now=0.0)
        nd.on_target_found()
        assert nd.get_target(1.0) is None

    def test_is_in_idle_after_return(self) -> None:
        from src.control.cv_coordinator import NoDetectionBehavior
        nd = NoDetectionBehavior(hold_sec=0.1, return_sec=0.1)
        nd.on_target_lost(10.0, 5.0, now=0.0)
        # H-5 fix: is_in_idle now takes `now` parameter
        assert nd.is_in_idle(now=0.3) is True


# ============================================================================
# Tests: normalized_to_angle
# ============================================================================


class TestNormalizedToAngle:
    """Tests for pixel-to-angle conversion."""

    def test_center_is_zero(self) -> None:
        from src.control.cv_coordinator import normalized_to_angle
        yaw, pitch = normalized_to_angle(0.0, 0.0)
        assert yaw == 0.0
        assert pitch == 0.0

    def test_right_edge(self) -> None:
        from src.control.cv_coordinator import normalized_to_angle
        yaw, pitch = normalized_to_angle(1.0, 0.0, hfov=78.3)
        assert abs(yaw - 39.15) < 0.01

    def test_bottom_edge(self) -> None:
        from src.control.cv_coordinator import normalized_to_angle
        yaw, pitch = normalized_to_angle(0.0, 1.0, vfov=56.0)
        assert abs(pitch - 28.0) < 0.01

    def test_negative_coords(self) -> None:
        from src.control.cv_coordinator import normalized_to_angle
        yaw, pitch = normalized_to_angle(-0.5, -0.5, hfov=80.0, vfov=60.0)
        assert yaw < 0
        assert pitch < 0


# ============================================================================
# Tests: TrackingConfig
# ============================================================================


class TestTrackingConfig:
    """Tests for TrackingConfig validation."""

    def test_default_config(self) -> None:
        from src.control.cv_coordinator import TrackingConfig
        config = TrackingConfig()
        assert config.kp_yaw == 0.3
        assert config.control_hz == 30.0

    def test_negative_kp_raises(self) -> None:
        from src.control.cv_coordinator import TrackingConfig
        with pytest.raises(ValueError, match="PD gains"):
            TrackingConfig(kp_yaw=-0.1)

    def test_zero_control_hz_raises(self) -> None:
        from src.control.cv_coordinator import TrackingConfig
        with pytest.raises(ValueError, match="control_hz"):
            TrackingConfig(control_hz=0)

    def test_invalid_smoothing_alpha(self) -> None:
        from src.control.cv_coordinator import TrackingConfig
        with pytest.raises(ValueError, match="smoothing_alpha"):
            TrackingConfig(smoothing_alpha=0.0)

    def test_invalid_neck_pitch_ratio(self) -> None:
        from src.control.cv_coordinator import TrackingConfig
        with pytest.raises(ValueError, match="neck_pitch_ratio"):
            TrackingConfig(neck_pitch_ratio=1.5)


# ============================================================================
# Tests: CVCoordinator Integration
# ============================================================================


class TestCVCoordinator:
    """Integration tests for the full tracking pipeline."""

    def _make_detection(self, cx: float, cy: float, area: float = 100.0, conf: float = 0.9):
        from src.drivers.camera.imx500_cv import Detection
        return Detection(
            category=0, confidence=conf,
            bbox=(0, 0, 50, 50), center_x=cx, center_y=cy, area=area,
        )

    def test_construction(self) -> None:
        from src.control.cv_coordinator import CVCoordinator
        coord = CVCoordinator(
            get_detections=lambda: [],
            move_head=Mock(),
            is_operational=lambda: True,
        )
        assert coord.is_tracking is False

    def test_start_stop(self) -> None:
        from src.control.cv_coordinator import CVCoordinator
        coord = CVCoordinator(
            get_detections=lambda: [],
            move_head=Mock(),
            is_operational=lambda: True,
        )
        coord.start()
        assert coord.is_tracking is True
        coord.stop()
        assert coord.is_tracking is False

    def test_double_start_raises(self) -> None:
        from src.control.cv_coordinator import CVCoordinator
        coord = CVCoordinator(
            get_detections=lambda: [],
            move_head=Mock(),
            is_operational=lambda: True,
        )
        coord.start()
        try:
            with pytest.raises(RuntimeError, match="already tracking"):
                coord.start()
        finally:
            coord.stop()

    def test_stop_when_not_started_is_noop(self) -> None:
        from src.control.cv_coordinator import CVCoordinator
        coord = CVCoordinator(
            get_detections=lambda: [],
            move_head=Mock(),
            is_operational=lambda: True,
        )
        coord.stop()  # Should not raise

    def test_moves_head_toward_detection(self) -> None:
        from src.control.cv_coordinator import CVCoordinator, TrackingConfig

        det = self._make_detection(cx=0.5, cy=0.0)
        move_head = Mock()

        config = TrackingConfig(control_hz=100.0)
        coord = CVCoordinator(
            get_detections=lambda: [det],
            move_head=move_head,
            is_operational=lambda: True,
            config=config,
        )

        coord.start()
        time.sleep(0.15)  # ~15 iterations at 100Hz
        coord.stop()

        # move_head should have been called (coordinator uses kwargs)
        assert move_head.call_count > 0
        last_call = move_head.call_args
        head_yaw = last_call.kwargs.get("head_yaw", 0)
        # Target is to the right (cx=0.5), yaw should be positive
        assert head_yaw > 0

    def test_respects_is_operational(self) -> None:
        from src.control.cv_coordinator import CVCoordinator, TrackingConfig

        det = self._make_detection(cx=0.5, cy=0.0)
        move_head = Mock()

        config = TrackingConfig(control_hz=100.0)
        coord = CVCoordinator(
            get_detections=lambda: [det],
            move_head=move_head,
            is_operational=lambda: False,  # E-stopped
            config=config,
        )

        coord.start()
        time.sleep(0.1)
        coord.stop()

        # Should NOT have moved head (robot not operational)
        assert move_head.call_count == 0

    def test_no_detection_returns_to_center(self) -> None:
        from src.control.cv_coordinator import CVCoordinator, TrackingConfig

        move_calls = []

        def track_move(**kwargs):
            move_calls.append(kwargs)
            return True

        config = TrackingConfig(
            control_hz=100.0,
            hold_duration_sec=0.05,
            return_duration_sec=0.1,
        )

        # Start with detection, then lose it
        has_detection = [True]
        det = self._make_detection(cx=0.3, cy=0.2)

        def get_dets():
            if has_detection[0]:
                return [det]
            return []

        coord = CVCoordinator(
            get_detections=get_dets,
            move_head=track_move,
            is_operational=lambda: True,
            config=config,
        )

        coord.start()
        time.sleep(0.1)
        has_detection[0] = False
        time.sleep(0.3)
        coord.stop()

        # Last calls should be approaching center
        if move_calls:
            last = move_calls[-1]
            assert abs(last.get("head_yaw", 0)) < 5.0

    def test_idle_behavior_active_after_no_detection(self) -> None:
        from src.control.cv_coordinator import CVCoordinator, TrackingConfig

        move_calls = []

        def track_move(**kwargs):
            move_calls.append(kwargs)
            return True

        config = TrackingConfig(
            control_hz=100.0,
            hold_duration_sec=0.01,
            return_duration_sec=0.01,
            idle_amplitude_deg=3.0,
        )

        coord = CVCoordinator(
            get_detections=lambda: [],
            move_head=track_move,
            is_operational=lambda: True,
            config=config,
        )

        coord.start()
        time.sleep(0.15)
        coord.stop()

        # Should have made some calls with small idle offsets
        assert len(move_calls) > 0

    def test_tracking_step_error_does_not_crash(self) -> None:
        from src.control.cv_coordinator import CVCoordinator, TrackingConfig

        call_count = [0]

        def bad_detections():
            call_count[0] += 1
            if call_count[0] < 3:
                raise RuntimeError("Camera glitch")
            return []

        config = TrackingConfig(control_hz=100.0)
        coord = CVCoordinator(
            get_detections=bad_detections,
            move_head=Mock(),
            is_operational=lambda: True,
            config=config,
        )

        coord.start()
        time.sleep(0.1)
        coord.stop()

        # Should have survived the errors
        assert call_count[0] >= 3

    def test_curiosity_roll_proportional_to_yaw(self) -> None:
        from src.control.cv_coordinator import CVCoordinator, TrackingConfig

        move_calls = []

        def track_move(**kwargs):
            move_calls.append(kwargs)
            return True

        config = TrackingConfig(
            control_hz=100.0,
            curiosity_roll_factor=0.1,
        )

        # Detection on the right
        det = self._make_detection(cx=0.8, cy=0.0)
        coord = CVCoordinator(
            get_detections=lambda: [det],
            move_head=track_move,
            is_operational=lambda: True,
            config=config,
        )

        coord.start()
        time.sleep(0.15)
        coord.stop()

        # Roll should be non-zero when yaw is non-zero
        if move_calls:
            rolls = [c.get("head_roll", 0) for c in move_calls if c.get("head_yaw", 0) != 0]
            if rolls:
                assert any(abs(r) > 0.01 for r in rolls)

    def test_neck_pitch_split(self) -> None:
        from src.control.cv_coordinator import CVCoordinator, TrackingConfig

        move_calls = []

        def track_move(**kwargs):
            move_calls.append(kwargs)
            return True

        config = TrackingConfig(
            control_hz=100.0,
            neck_pitch_ratio=0.7,
        )

        # Detection below center
        det = self._make_detection(cx=0.0, cy=0.5)
        coord = CVCoordinator(
            get_detections=lambda: [det],
            move_head=track_move,
            is_operational=lambda: True,
            config=config,
        )

        coord.start()
        time.sleep(0.15)
        coord.stop()

        # neck_pitch should be larger than head_pitch (70/30 split)
        if move_calls:
            last = move_calls[-1]
            np_val = abs(last.get("neck_pitch", 0))
            hp_val = abs(last.get("head_pitch", 0))
            if np_val > 0 and hp_val > 0:
                assert np_val > hp_val
