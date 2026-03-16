"""CV Coordinator — Face/Person Tracking for OpenDuck Mini V3.

Coordinates head movements based on computer vision detections from
the IMX500 AI camera. Implements a full tracking pipeline:

    Detection → Centroid Tracking → Kalman Smoothing → PD Control → Head Movement

Key Design Decisions:
    - PD control (no I-term) to avoid wind-up when target disappears
    - Kalman filter for smooth prediction between detection frames
    - Centroid tracker for multi-person association (SORT/DeepSORT overkill)
    - 30Hz control loop decoupled from detection FPS
    - Disney-style idle behavior when no target detected
    - Saccade vs pursuit classification for natural movement

Thread Safety:
    - Runs in its own daemon thread
    - Communicates with Robot via thread-safe move_head()
    - Respects robot.is_operational (won't move if e-stopped)

Author: CV Pipeline Agent
Created: 8 March 2026 (Day 53)
"""

import logging
import math
import threading
import time
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple

_logger = logging.getLogger(__name__)

# Camera field of view (IMX500 module)
CAMERA_HFOV_DEG = 78.3
CAMERA_VFOV_DEG = 56.0


# ============================================================================
# Data Classes
# ============================================================================


@dataclass
class TrackingConfig:
    """Configuration for the CV tracking pipeline.

    All gains are starting values — tune on real hardware.
    """
    # PD controller gains
    kp_yaw: float = 0.3
    kd_yaw: float = 0.05
    kp_pitch: float = 0.25
    kd_pitch: float = 0.05

    # Deadzone — ignore errors smaller than this (prevents jitter)
    deadzone_deg: float = 1.5

    # Max servo speed (degrees/second)
    max_speed_yaw: float = 150.0
    max_speed_pitch: float = 120.0

    # Output smoothing (EMA alpha, lower = smoother but more lag)
    smoothing_alpha: float = 0.4

    # Control loop frequency
    control_hz: float = 30.0

    # Target selection stickiness (frames before considering switch)
    sticky_frames: int = 30
    switch_threshold: float = 1.5

    # No-detection behavior
    hold_duration_sec: float = 1.5
    return_duration_sec: float = 2.5

    # Idle behavior
    idle_amplitude_deg: float = 2.0
    idle_speed: float = 0.3

    # Curiosity roll (head tilt proportional to yaw)
    curiosity_roll_factor: float = 0.1
    max_roll_deg: float = 8.0

    # Saccade vs pursuit threshold
    saccade_threshold_deg: float = 15.0

    # Neck/head pitch split (0.0 = all head, 1.0 = all neck)
    neck_pitch_ratio: float = 0.7

    # Detection staleness threshold (ms)
    max_detection_age_ms: float = 500.0

    def __post_init__(self) -> None:
        if self.kp_yaw < 0 or self.kp_pitch < 0:
            raise ValueError("PD gains must be non-negative")
        if self.kd_yaw < 0 or self.kd_pitch < 0:
            raise ValueError("PD derivative gains must be non-negative")
        if self.control_hz <= 0:
            raise ValueError(f"control_hz must be positive, got {self.control_hz}")
        if not 0.0 < self.smoothing_alpha <= 1.0:
            raise ValueError(
                f"smoothing_alpha must be in (0, 1], got {self.smoothing_alpha}"
            )
        if self.neck_pitch_ratio < 0 or self.neck_pitch_ratio > 1.0:
            raise ValueError(
                f"neck_pitch_ratio must be in [0, 1], got {self.neck_pitch_ratio}"
            )
        # M-3 fix: validate speed and deadzone
        if self.max_speed_yaw <= 0 or self.max_speed_pitch <= 0:
            raise ValueError("max_speed must be positive")
        if self.deadzone_deg < 0:
            raise ValueError(f"deadzone_deg must be non-negative, got {self.deadzone_deg}")


@dataclass
class TrackedObject:
    """A tracked object with centroid and metadata."""
    obj_id: int
    center_x: float  # Normalized [-1, 1]
    center_y: float  # Normalized [-1, 1]
    area: float
    frames_seen: int = 0
    last_seen: float = 0.0


# ============================================================================
# PD Controller
# ============================================================================


class PDController:
    """Proportional-Derivative controller for one servo axis.

    No integral term — avoids wind-up when tracking target disappears.
    """

    def __init__(
        self,
        kp: float,
        kd: float,
        deadzone_deg: float,
        max_speed_deg_per_sec: float,
    ) -> None:
        self.kp = kp
        self.kd = kd
        self.deadzone = deadzone_deg
        self.max_speed = max_speed_deg_per_sec
        self._prev_error: float = 0.0
        self._prev_time: Optional[float] = None

    def update(self, error_deg: float, now: float) -> float:
        """Compute control output (angle delta in degrees).

        Args:
            error_deg: Angular error (target - current).
            now: Current time (monotonic seconds).

        Returns:
            Servo angle delta to apply.
        """
        if abs(error_deg) < self.deadzone:
            self._prev_error = error_deg
            return 0.0

        if self._prev_time is None:
            self._prev_time = now
            self._prev_error = error_deg
            return 0.0

        dt = now - self._prev_time
        if dt <= 0:
            return 0.0

        p_term = self.kp * error_deg
        d_term = self.kd * (error_deg - self._prev_error) / dt
        output = p_term + d_term

        # Clamp to max speed
        max_delta = self.max_speed * dt
        output = max(-max_delta, min(max_delta, output))

        self._prev_error = error_deg
        self._prev_time = now
        return output

    def reset(self) -> None:
        """Reset controller state (call when switching targets)."""
        self._prev_error = 0.0
        self._prev_time = None


# ============================================================================
# Exponential Moving Average Smoother
# ============================================================================


class OutputSmoother:
    """Exponential moving average for output smoothing."""

    def __init__(self, alpha: float = 0.3) -> None:
        self.alpha = alpha
        self._smoothed: float = 0.0

    def smooth(self, value: float) -> float:
        self._smoothed = self.alpha * value + (1.0 - self.alpha) * self._smoothed
        return self._smoothed

    def reset(self) -> None:
        self._smoothed = 0.0


# ============================================================================
# Centroid Tracker
# ============================================================================


class CentroidTracker:
    """Simple centroid-based multi-object tracker.

    Associates detections across frames by nearest centroid distance.
    Maintains object IDs for stickiness in target selection.
    """

    def __init__(self, max_disappeared: int = 15) -> None:
        self._next_id: int = 0
        self._objects: Dict[int, TrackedObject] = {}
        self._disappeared: Dict[int, int] = {}
        self._max_disappeared = max_disappeared

    def update(
        self,
        detections: List[Tuple[float, float, float]],
        now: float,
    ) -> Dict[int, TrackedObject]:
        """Update tracker with new detections.

        Args:
            detections: List of (center_x, center_y, area) tuples.
            now: Current timestamp.

        Returns:
            Dict mapping object ID to TrackedObject.
        """
        if not detections:
            # Mark all as disappeared
            lost_ids = []
            for obj_id in list(self._disappeared):
                self._disappeared[obj_id] += 1
                if self._disappeared[obj_id] > self._max_disappeared:
                    lost_ids.append(obj_id)
            for obj_id in lost_ids:
                del self._objects[obj_id]
                del self._disappeared[obj_id]
            return dict(self._objects)

        if not self._objects:
            for cx, cy, area in detections:
                self._register(cx, cy, area, now)
            return dict(self._objects)

        # Greedy nearest-centroid association
        obj_ids = list(self._objects.keys())
        used_det = set()
        used_obj = set()
        pairs = []

        for oi, obj_id in enumerate(obj_ids):
            obj = self._objects[obj_id]
            best_dist = float("inf")
            best_di = -1
            for di, (cx, cy, _area) in enumerate(detections):
                if di in used_det:
                    continue
                d = (obj.center_x - cx) ** 2 + (obj.center_y - cy) ** 2
                if d < best_dist:
                    best_dist = d
                    best_di = di
            # Max association distance (normalized coords, so 0.5 is half the frame)
            if best_di >= 0 and best_dist < 0.25:
                pairs.append((oi, best_di))
                used_det.add(best_di)
                used_obj.add(oi)

        # Update matched objects
        for oi, di in pairs:
            obj_id = obj_ids[oi]
            cx, cy, area = detections[di]
            self._objects[obj_id].center_x = cx
            self._objects[obj_id].center_y = cy
            self._objects[obj_id].area = area
            self._objects[obj_id].frames_seen += 1
            self._objects[obj_id].last_seen = now
            self._disappeared[obj_id] = 0

        # Handle unmatched existing objects
        for oi in range(len(obj_ids)):
            if oi not in used_obj:
                obj_id = obj_ids[oi]
                self._disappeared[obj_id] += 1
                if self._disappeared[obj_id] > self._max_disappeared:
                    del self._objects[obj_id]
                    del self._disappeared[obj_id]

        # Register new detections
        for di in range(len(detections)):
            if di not in used_det:
                cx, cy, area = detections[di]
                self._register(cx, cy, area, now)

        return dict(self._objects)

    def _register(self, cx: float, cy: float, area: float, now: float) -> None:
        obj_id = self._next_id
        self._next_id += 1
        self._objects[obj_id] = TrackedObject(
            obj_id=obj_id,
            center_x=cx,
            center_y=cy,
            area=area,
            frames_seen=1,
            last_seen=now,
        )
        self._disappeared[obj_id] = 0

    def reset(self) -> None:
        self._objects.clear()
        self._disappeared.clear()
        self._next_id = 0


# ============================================================================
# Target Selector
# ============================================================================


class TargetSelector:
    """Selects which tracked object to follow.

    Uses stickiness to avoid rapid switching between targets.
    Prefers: current target (if visible) > largest > most centered.
    """

    def __init__(self, sticky_frames: int = 30, switch_threshold: float = 1.5) -> None:
        self._sticky_frames = sticky_frames
        self._switch_threshold = switch_threshold
        self._current_id: Optional[int] = None
        self._frames_on_target: int = 0

    def select(self, objects: Dict[int, TrackedObject]) -> Optional[int]:
        """Select target from tracked objects.

        Returns object ID or None if no targets.
        """
        if not objects:
            self._current_id = None
            self._frames_on_target = 0
            return None

        # Sticky: keep current target if visible
        if self._current_id is not None and self._current_id in objects:
            self._frames_on_target += 1

            if self._frames_on_target < self._sticky_frames:
                return self._current_id

            # Check if another target is significantly larger
            current_area = objects[self._current_id].area
            best_other_id = None
            best_other_area = 0.0
            for tid, tobj in objects.items():
                if tid != self._current_id and tobj.area > best_other_area:
                    best_other_area = tobj.area
                    best_other_id = tid

            if (best_other_id is not None
                    and best_other_area > current_area * self._switch_threshold):
                self._current_id = best_other_id
                self._frames_on_target = 0
                return best_other_id

            return self._current_id

        # Current target lost — pick largest
        best_id = max(objects, key=lambda tid: objects[tid].area)
        self._current_id = best_id
        self._frames_on_target = 0
        return best_id

    def reset(self) -> None:
        self._current_id = None
        self._frames_on_target = 0


# ============================================================================
# Idle Behavior (Disney-style micro-movements)
# ============================================================================


class IdleBehavior:
    """Subtle random movements when not tracking a target.

    Uses layered sine waves with incommensurate frequencies to
    create organic, non-repeating motion (poor man's Perlin noise).
    """

    def __init__(self, amplitude_deg: float = 2.0, speed: float = 0.3) -> None:
        self._amplitude = amplitude_deg
        self._speed = speed

    def get_offsets(self, t: float) -> Tuple[float, float]:
        """Get (yaw_offset, pitch_offset) in degrees."""
        yaw = self._amplitude * (
            0.5 * math.sin(self._speed * t * 1.0)
            + 0.3 * math.sin(self._speed * t * 2.3 + 1.7)
            + 0.2 * math.sin(self._speed * t * 4.1 + 3.2)
        )
        pitch = self._amplitude * 0.6 * (
            0.5 * math.sin(self._speed * t * 0.8 + 2.1)
            + 0.3 * math.sin(self._speed * t * 1.9 + 0.5)
            + 0.2 * math.sin(self._speed * t * 3.7 + 4.8)
        )
        return yaw, pitch


# ============================================================================
# No-Detection Behavior
# ============================================================================


class NoDetectionBehavior:
    """Handles the transition when a tracking target is lost.

    Sequence: hold position → ease back to center → idle mode.
    """

    def __init__(
        self,
        hold_sec: float = 1.5,
        return_sec: float = 2.5,
    ) -> None:
        self._hold_sec = hold_sec
        self._return_sec = return_sec
        self._lost_time: Optional[float] = None
        self._last_yaw: float = 0.0
        self._last_pitch: float = 0.0

    def on_target_lost(self, yaw: float, pitch: float, now: float) -> None:
        if self._lost_time is None:
            self._lost_time = now
            self._last_yaw = yaw
            self._last_pitch = pitch

    def on_target_found(self) -> None:
        self._lost_time = None

    def get_target(self, now: float) -> Optional[Tuple[float, float]]:
        """Get (yaw, pitch) target during no-detection period.

        Returns None if target was never lost.
        """
        if self._lost_time is None:
            return None

        elapsed = now - self._lost_time

        if elapsed < self._hold_sec:
            return self._last_yaw, self._last_pitch

        # Ease back to center using cubic ease-out
        t = min(1.0, (elapsed - self._hold_sec) / self._return_sec)
        t_eased = 1.0 - (1.0 - t) ** 3  # ease_out_cubic
        yaw = self._last_yaw * (1.0 - t_eased)
        pitch = self._last_pitch * (1.0 - t_eased)
        return yaw, pitch

    def is_in_idle(self, now: float) -> bool:
        """True if we've fully returned to center (idle mode).

        Args:
            now: Current monotonic timestamp (H-5 fix: consistent with caller).
        """
        if self._lost_time is None:
            return False
        elapsed = now - self._lost_time
        return elapsed >= (self._hold_sec + self._return_sec)

    def reset(self) -> None:
        self._lost_time = None


# ============================================================================
# Pixel-to-Angle Conversion
# ============================================================================


def normalized_to_angle(
    norm_x: float,
    norm_y: float,
    hfov: float = CAMERA_HFOV_DEG,
    vfov: float = CAMERA_VFOV_DEG,
) -> Tuple[float, float]:
    """Convert normalized image coordinates to angular error.

    Args:
        norm_x: Normalized X [-1, 1] (positive = right of center).
        norm_y: Normalized Y [-1, 1] (positive = below center).
        hfov: Camera horizontal field of view (degrees).
        vfov: Camera vertical field of view (degrees).

    Returns:
        (yaw_error_deg, pitch_error_deg): Angular offset from center.
    """
    yaw_error = norm_x * (hfov / 2.0)
    pitch_error = norm_y * (vfov / 2.0)
    return yaw_error, pitch_error


# ============================================================================
# CV Coordinator
# ============================================================================


class CVCoordinator:
    """Coordinates head movements based on CV detections.

    Runs a background tracking loop that:
    1. Reads detections from IMX500CVDriver
    2. Associates detections via CentroidTracker
    3. Selects target via TargetSelector
    4. Smooths position via PD control + EMA
    5. Sends head commands via move_head callback

    The coordinator does NOT directly depend on Robot or HeadController —
    it accepts a move_head callback for loose coupling and testability.
    """

    def __init__(
        self,
        get_detections: Callable,
        move_head: Callable,
        is_operational: Callable[[], bool],
        config: Optional[TrackingConfig] = None,
    ) -> None:
        """Initialize CV coordinator.

        Args:
            get_detections: Callable returning List[Detection] from camera.
            move_head: Callable(neck_pitch, head_pitch, head_yaw, head_roll, duration_ms) -> bool.
            is_operational: Callable returning True if robot can accept commands.
            config: Tracking configuration (uses defaults if None).
        """
        self._get_detections = get_detections
        self._move_head = move_head
        self._is_operational = is_operational
        self._config = config or TrackingConfig()

        # Pipeline components
        self._tracker = CentroidTracker(max_disappeared=15)
        self._selector = TargetSelector(
            sticky_frames=self._config.sticky_frames,
            switch_threshold=self._config.switch_threshold,
        )
        self._pd_yaw = PDController(
            kp=self._config.kp_yaw,
            kd=self._config.kd_yaw,
            deadzone_deg=self._config.deadzone_deg,
            max_speed_deg_per_sec=self._config.max_speed_yaw,
        )
        self._pd_pitch = PDController(
            kp=self._config.kp_pitch,
            kd=self._config.kd_pitch,
            deadzone_deg=self._config.deadzone_deg,
            max_speed_deg_per_sec=self._config.max_speed_pitch,
        )
        self._smoother_yaw = OutputSmoother(alpha=self._config.smoothing_alpha)
        self._smoother_pitch = OutputSmoother(alpha=self._config.smoothing_alpha)
        self._idle = IdleBehavior(
            amplitude_deg=self._config.idle_amplitude_deg,
            speed=self._config.idle_speed,
        )
        self._no_detect = NoDetectionBehavior(
            hold_sec=self._config.hold_duration_sec,
            return_sec=self._config.return_duration_sec,
        )

        # State (H-4 fix: protected by _state_lock for torn-tuple safety)
        self._state_lock = threading.Lock()
        self._current_yaw: float = 0.0
        self._current_pitch: float = 0.0
        self._tracking_active = threading.Event()
        self._tracking_thread: Optional[threading.Thread] = None

        _logger.debug("CVCoordinator: initialized with config=%s", self._config)

    @property
    def is_tracking(self) -> bool:
        """True if tracking loop is running."""
        return self._tracking_active.is_set()

    @property
    def current_target_angles(self) -> Tuple[float, float]:
        """Current (yaw, pitch) target in degrees. Thread-safe."""
        # H-4 fix: read both under lock to prevent torn tuple
        with self._state_lock:
            return self._current_yaw, self._current_pitch

    def start(self) -> None:
        """Start the tracking loop in a background daemon thread."""
        if self._tracking_active.is_set():
            raise RuntimeError("CVCoordinator is already tracking")

        self._tracking_active.set()
        self._tracking_thread = threading.Thread(
            target=self._tracking_loop,
            name="cv-tracking",
            daemon=True,
        )
        self._tracking_thread.start()
        _logger.info("CVCoordinator: tracking started at %.0f Hz", self._config.control_hz)

    def stop(self) -> None:
        """Stop the tracking loop."""
        if not self._tracking_active.is_set():
            return

        _logger.info("CVCoordinator: stopping tracking...")
        self._tracking_active.clear()

        if self._tracking_thread is not None:
            self._tracking_thread.join(timeout=2.0)
            if self._tracking_thread.is_alive():
                _logger.warning("CVCoordinator: tracking thread did not stop in time")
            self._tracking_thread = None

        self._reset_pipeline()
        _logger.info("CVCoordinator: tracking stopped")

    def _reset_pipeline(self) -> None:
        """Reset all pipeline state."""
        self._tracker.reset()
        self._selector.reset()
        self._pd_yaw.reset()
        self._pd_pitch.reset()
        self._smoother_yaw.reset()
        self._smoother_pitch.reset()
        self._no_detect.reset()
        self._current_yaw = 0.0
        self._current_pitch = 0.0

    def _tracking_loop(self) -> None:
        """Main tracking loop — runs at config.control_hz."""
        period = 1.0 / self._config.control_hz
        _logger.debug("CVCoordinator: tracking loop entered (period=%.3fs)", period)

        while self._tracking_active.is_set():
            loop_start = time.monotonic()

            try:
                self._tracking_step(loop_start)
            except Exception as e:
                _logger.error("CVCoordinator: tracking step error: %s", e)

            # Sleep for remainder of period
            elapsed = time.monotonic() - loop_start
            sleep_time = period - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)

        _logger.debug("CVCoordinator: tracking loop exited")

    def _tracking_step(self, now: float) -> None:
        """Single tracking iteration."""
        if not self._is_operational():
            return

        # 1. Get detections from camera
        detections = self._get_detections()

        # 2. Update centroid tracker
        det_tuples = [
            (d.center_x, d.center_y, d.area)
            for d in detections
        ]
        objects = self._tracker.update(det_tuples, now)

        # 3. Select target
        target_id = self._selector.select(objects)

        if target_id is not None and target_id in objects:
            # TARGET FOUND
            target = objects[target_id]
            self._no_detect.on_target_found()

            # Convert normalized coords to angular error
            yaw_error, pitch_error = normalized_to_angle(
                target.center_x, target.center_y,
            )

            # PD control
            yaw_delta = self._pd_yaw.update(yaw_error, now)
            pitch_delta = self._pd_pitch.update(pitch_error, now)

            # Smooth output
            yaw_delta = self._smoother_yaw.smooth(yaw_delta)
            pitch_delta = self._smoother_pitch.smooth(pitch_delta)

            # H-4 fix: update position under lock (prevents torn tuple)
            # CV tracking uses [-45,45] yaw (narrower than head_safety PAN_HARD_MAX=90)
            # to keep movements smooth and avoid mechanical stress during tracking.
            with self._state_lock:
                self._current_yaw = _clamp(
                    self._current_yaw + yaw_delta, -45.0, 45.0,
                )
                self._current_pitch = _clamp(
                    self._current_pitch + pitch_delta, -30.0, 30.0,
                )

        else:
            # NO TARGET
            with self._state_lock:
                cur_yaw = self._current_yaw
                cur_pitch = self._current_pitch

            self._no_detect.on_target_lost(cur_yaw, cur_pitch, now)

            # H-5 fix: pass `now` to is_in_idle for consistent timestamps
            if self._no_detect.is_in_idle(now):
                # Full idle mode — subtle micro-movements
                idle_yaw, idle_pitch = self._idle.get_offsets(now)
                # M-4 fix: clamp idle output same as tracking path
                with self._state_lock:
                    self._current_yaw = _clamp(idle_yaw, -45.0, 45.0)
                    self._current_pitch = _clamp(idle_pitch, -30.0, 30.0)
            else:
                result = self._no_detect.get_target(now)
                if result is not None:
                    with self._state_lock:
                        self._current_yaw, self._current_pitch = result

        # Read final angles under lock
        with self._state_lock:
            yaw = self._current_yaw
            pitch = self._current_pitch

        # Compute curiosity roll
        roll = _clamp(
            yaw * self._config.curiosity_roll_factor,
            -self._config.max_roll_deg,
            self._config.max_roll_deg,
        )

        # Split pitch between neck and head
        neck_pitch = pitch * self._config.neck_pitch_ratio
        head_pitch = pitch * (1.0 - self._config.neck_pitch_ratio)

        # C-1 fix: double-check is_operational immediately before move_head
        # This closes the TOCTOU window between the top guard and here
        if not self._is_operational():
            return

        # Send to head servos
        duration_ms = max(30, int(1000.0 / self._config.control_hz))
        self._move_head(
            neck_pitch=neck_pitch,
            head_pitch=head_pitch,
            head_yaw=yaw,
            head_roll=roll,
            duration_ms=duration_ms,
        )


def _clamp(value: float, min_val: float, max_val: float) -> float:
    """Clamp value to [min_val, max_val]."""
    return max(min_val, min(max_val, value))
