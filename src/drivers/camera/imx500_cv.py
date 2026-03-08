"""IMX500 Computer Vision Driver for OpenDuck Mini V3.

Wraps the Sony IMX500 AI camera sensor via picamera2 to provide
on-chip inference for person/face detection. The IMX500 has a 4 TOPS
AI accelerator that runs inference on-sensor, keeping Pi CPU free.

Hardware:
    - Sony IMX500 AI camera on CSI interface
    - 4056x3040 sensor, fixed focus
    - On-chip inference: ~30 FPS, ~19ms end-to-end latency
    - Install: sudo apt install imx500-all && sudo reboot

Models (pre-installed in /usr/share/imx500-models/):
    - imx500_network_yolo11n_pp.rpk       (best accuracy, mAP 0.374)
    - imx500_network_ssd_mobilenetv2_fpnlite_320x320_pp.rpk (fastest)

Thread Safety:
    - get_detections() is thread-safe (reads from lock-protected cache)
    - start()/stop() must be called from the same thread
    - _parse_detections() guards hardware refs with _running check

Hostile Review Fixes (Day 53 R1):
    - C-2: bbox normalization uses input_w for X, input_h for Y
    - C-3: copy.copy() on NetworkIntrinsics before mutation
    - H-1: start() cleans up on _init_hardware() failure
    - H-2: _deinit_hardware() skipped if capture thread still alive
    - H-3: camera_configuration() hoisted out of per-detection loop
    - M-1: consecutive_none warning repeats every 300 frames
    - M-2: input_w now used for correct X-axis normalization

Author: CV Pipeline Agent
Created: 8 March 2026 (Day 53)
"""

import copy
import logging
import threading
import time
from dataclasses import dataclass
from typing import List, Optional, Tuple

_logger = logging.getLogger(__name__)

# Default model paths (installed by imx500-all package)
DEFAULT_MODEL_PATH = "/usr/share/imx500-models/imx500_network_ssd_mobilenetv2_fpnlite_320x320_pp.rpk"
YOLO11N_MODEL_PATH = "/usr/share/imx500-models/imx500_network_yolo11n_pp.rpk"

# COCO class indices
COCO_PERSON_CLASS = 0

# Camera field of view (IMX500 module)
CAMERA_HFOV_DEG = 78.3
CAMERA_VFOV_DEG = 56.0


@dataclass(frozen=True)
class Detection:
    """A single detection result from the IMX500.

    Attributes:
        category: COCO class index (0 = person).
        confidence: Detection confidence [0.0, 1.0].
        bbox: Bounding box as (x, y, width, height) in pixel coords.
        center_x: Normalized center X [-1.0, 1.0] (0 = frame center).
        center_y: Normalized center Y [-1.0, 1.0] (0 = frame center).
        area: Bounding box area in pixels (for target selection).
    """
    category: int
    confidence: float
    bbox: Tuple[float, float, float, float]
    center_x: float
    center_y: float
    area: float


class IMX500CVDriver:
    """On-chip AI camera driver for person detection.

    Provides non-blocking access to detection results from the IMX500
    AI camera sensor. Inference runs entirely on-sensor; this driver
    only reads metadata from picamera2.

    Usage:
        driver = IMX500CVDriver(model_path=DEFAULT_MODEL_PATH)
        driver.start()
        detections = driver.get_detections()  # Non-blocking
        driver.stop()
    """

    def __init__(
        self,
        model_path: str = DEFAULT_MODEL_PATH,
        confidence_threshold: float = 0.55,
        max_detections: int = 10,
        iou_threshold: float = 0.65,
        target_fps: float = 30.0,
        person_only: bool = True,
    ) -> None:
        """Initialize IMX500 CV driver.

        Args:
            model_path: Path to .rpk model file.
            confidence_threshold: Minimum detection confidence [0.0, 1.0].
            max_detections: Maximum detections per frame.
            iou_threshold: Non-maximum suppression IoU threshold.
            target_fps: Target camera frame rate.
            person_only: If True, filter for COCO person class only.

        Raises:
            ValueError: If threshold/fps parameters are out of range.
        """
        if not 0.0 < confidence_threshold <= 1.0:
            raise ValueError(
                f"confidence_threshold must be in (0, 1], got {confidence_threshold}"
            )
        if not 0.0 < iou_threshold <= 1.0:
            raise ValueError(
                f"iou_threshold must be in (0, 1], got {iou_threshold}"
            )
        if max_detections < 1:
            raise ValueError(
                f"max_detections must be >= 1, got {max_detections}"
            )
        if target_fps <= 0:
            raise ValueError(f"target_fps must be positive, got {target_fps}")

        self._model_path = model_path
        self._confidence_threshold = confidence_threshold
        self._max_detections = max_detections
        self._iou_threshold = iou_threshold
        self._target_fps = target_fps
        self._person_only = person_only

        # Lazy-loaded hardware references
        self._imx500 = None
        self._picam2 = None
        self._intrinsics = None

        # Detection cache (thread-safe via lock)
        self._lock = threading.Lock()
        self._last_detections: List[Detection] = []
        self._last_detection_time: float = 0.0
        self._frame_count: int = 0

        # Capture thread
        self._running = threading.Event()
        self._capture_thread: Optional[threading.Thread] = None

        _logger.debug(
            "IMX500CVDriver: model=%s, conf=%.2f, max=%d, fps=%.0f",
            model_path, confidence_threshold, max_detections, target_fps,
        )

    @property
    def is_running(self) -> bool:
        """True if capture loop is active."""
        return self._running.is_set()

    @property
    def frame_count(self) -> int:
        """Number of frames processed since start."""
        with self._lock:
            return self._frame_count

    def start(self) -> None:
        """Start camera capture and inference loop.

        Loads the model onto the IMX500 sensor and starts a background
        thread that continuously reads inference metadata.

        Raises:
            RuntimeError: If already running or hardware init fails.
        """
        if self._running.is_set():
            raise RuntimeError("IMX500CVDriver is already running")

        _logger.info("IMX500CVDriver: initializing camera...")
        # H-1 fix: clean up on init failure to avoid wedged state
        try:
            self._init_hardware()
        except Exception:
            self._deinit_hardware()
            raise

        self._running.set()
        self._capture_thread = threading.Thread(
            target=self._capture_loop,
            name="imx500-capture",
            daemon=True,
        )
        self._capture_thread.start()
        _logger.info("IMX500CVDriver: capture loop started")

    def stop(self) -> None:
        """Stop capture loop and release camera resources."""
        if not self._running.is_set():
            return

        _logger.info("IMX500CVDriver: stopping...")
        self._running.clear()

        if self._capture_thread is not None:
            self._capture_thread.join(timeout=3.0)
            # H-2 fix: only deinit hardware if capture thread has exited
            if self._capture_thread.is_alive():
                _logger.warning(
                    "IMX500CVDriver: capture thread did not stop in time, "
                    "deferring hardware cleanup"
                )
            else:
                self._deinit_hardware()
            self._capture_thread = None
        else:
            self._deinit_hardware()

        _logger.info("IMX500CVDriver: stopped")

    def get_detections(self) -> List[Detection]:
        """Get the most recent detection results.

        Returns a cached copy of the last valid detections. This method
        is non-blocking and thread-safe.

        Returns:
            List of Detection objects (may be empty if no detections).
        """
        with self._lock:
            return list(self._last_detections)

    def get_detection_age_ms(self) -> float:
        """How old the cached detections are, in milliseconds."""
        with self._lock:
            if self._last_detection_time == 0.0:
                return float("inf")
            return (time.monotonic() - self._last_detection_time) * 1000.0

    def _init_hardware(self) -> None:
        """Initialize picamera2 and IMX500 AI pipeline."""
        from picamera2 import Picamera2
        from picamera2.devices import IMX500
        from picamera2.devices.imx500 import NetworkIntrinsics

        self._imx500 = IMX500(self._model_path)

        # C-3 fix: copy intrinsics before mutating (shared SDK object)
        raw_intrinsics = self._imx500.network_intrinsics
        self._intrinsics = copy.copy(raw_intrinsics) if raw_intrinsics else NetworkIntrinsics()
        self._intrinsics.task = "object detection"
        if hasattr(self._intrinsics, 'update_with_defaults'):
            self._intrinsics.update_with_defaults()

        self._picam2 = Picamera2(self._imx500.camera_num)
        config = self._picam2.create_preview_configuration(
            controls={"FrameRate": self._target_fps},
            buffer_count=12,
        )

        self._imx500.show_network_fw_progress_bar()
        self._picam2.start(config, show_preview=False)

        _logger.info(
            "IMX500CVDriver: camera started (model=%s, fps=%.0f)",
            self._model_path, self._target_fps,
        )

    def _deinit_hardware(self) -> None:
        """Release camera resources."""
        if self._picam2 is not None:
            try:
                self._picam2.stop()
                self._picam2.close()
            except Exception as e:
                _logger.warning("IMX500CVDriver: cleanup error: %s", e)
            finally:
                self._picam2 = None
                self._imx500 = None
                self._intrinsics = None

    def _capture_loop(self) -> None:
        """Background capture loop — reads metadata and parses detections."""
        _logger.debug("IMX500CVDriver: capture loop entered")
        consecutive_none = 0

        while self._running.is_set():
            try:
                # H-2 fix: guard hardware access with _running check
                picam2 = self._picam2
                if picam2 is None:
                    break

                metadata = picam2.capture_metadata()
                detections = self._parse_detections(metadata)

                if detections is not None:
                    with self._lock:
                        self._last_detections = detections
                        self._last_detection_time = time.monotonic()
                        self._frame_count += 1
                    consecutive_none = 0
                else:
                    consecutive_none += 1
                    # M-1 fix: repeat warning every 300 frames
                    if consecutive_none >= 100 and consecutive_none % 300 == 0:
                        _logger.warning(
                            "IMX500CVDriver: %d consecutive frames with no "
                            "inference output", consecutive_none,
                        )

            except Exception as e:
                if self._running.is_set():
                    _logger.error("IMX500CVDriver: capture error: %s", e)
                    time.sleep(0.1)

        _logger.debug("IMX500CVDriver: capture loop exited")

    def _parse_detections(self, metadata: dict) -> Optional[List[Detection]]:
        """Parse raw IMX500 inference output into Detection objects.

        Returns None if inference output is not yet available for this frame.
        """
        # H-2 fix: snapshot hardware refs (avoid use-after-null)
        imx500 = self._imx500
        picam2 = self._picam2
        intrinsics = self._intrinsics
        if imx500 is None or picam2 is None:
            return None

        np_outputs = imx500.get_outputs(metadata, add_batch=True)
        if np_outputs is None:
            return None

        # C-2 + M-2 fix: use both input_w and input_h for correct normalization
        input_w, input_h = imx500.get_input_size()

        # Determine post-processing method
        if (hasattr(intrinsics, 'postprocess')
                and intrinsics.postprocess == "nanodet"):
            from picamera2.devices.imx500 import postprocess_nanodet_detection
            boxes, scores, classes = postprocess_nanodet_detection(
                outputs=np_outputs[0],
                conf=self._confidence_threshold,
                iou_thres=self._iou_threshold,
                max_out_dets=self._max_detections,
            )[0]
        else:
            boxes = np_outputs[0][0]
            scores = np_outputs[1][0]
            classes = np_outputs[2][0]

            # C-2 fix: normalize X by input_w, Y by input_h (not both by input_h)
            if (hasattr(intrinsics, 'bbox_normalization')
                    and intrinsics.bbox_normalization):
                if len(boxes.shape) >= 2 and boxes.shape[-1] >= 4:
                    # boxes format: [y1, x1, y2, x2] or [x1, y1, x2, y2]
                    # Normalize each axis by its correct dimension
                    scale = [input_h, input_w, input_h, input_w]
                    import numpy as np
                    boxes = boxes / np.array(scale, dtype=boxes.dtype)

        # Convert bbox_order if needed
        if (hasattr(intrinsics, 'bbox_order')
                and intrinsics.bbox_order == "xy"):
            boxes = boxes[:, [1, 0, 3, 2]]

        # H-3 fix: hoist camera_configuration() out of per-detection loop
        output_size = picam2.camera_configuration()["main"]["size"]
        frame_w, frame_h = output_size[0], output_size[1]

        detections = []
        for box, score, cls in zip(boxes, scores, classes):
            score_f = float(score)
            cls_i = int(cls)

            if score_f < self._confidence_threshold:
                continue
            if self._person_only and cls_i != COCO_PERSON_CLASS:
                continue

            # Convert inference coords to image coords
            img_box = imx500.convert_inference_coords(
                box, metadata, picam2,
            )
            x, y, w, h = float(img_box[0]), float(img_box[1]), float(img_box[2]), float(img_box[3])

            # Normalize center to [-1, 1]
            cx = ((x + w / 2.0) / frame_w) * 2.0 - 1.0
            cy = ((y + h / 2.0) / frame_h) * 2.0 - 1.0

            detections.append(Detection(
                category=cls_i,
                confidence=score_f,
                bbox=(x, y, w, h),
                center_x=cx,
                center_y=cy,
                area=w * h,
            ))

        return detections[:self._max_detections]
