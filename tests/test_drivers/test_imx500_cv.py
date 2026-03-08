"""Tests for IMX500 CV Driver.

Tests the IMX500CVDriver class with mocked picamera2/IMX500 hardware.
All tests run without actual camera hardware.

Author: CV Pipeline Agent
Created: 8 March 2026 (Day 53)
"""

import threading
import time
from typing import List, Optional, Tuple
from unittest.mock import MagicMock, Mock, patch, PropertyMock

import pytest

# We import inside tests to avoid picamera2 dependency at module level


# ============================================================================
# Mock helpers
# ============================================================================


class MockIMX500:
    """Mock IMX500 device class."""

    def __init__(self, model_path: str):
        self.model_path = model_path
        self.camera_num = 0
        self.network_intrinsics = None
        self._outputs = None

    def get_outputs(self, metadata, add_batch=True):
        return self._outputs

    def get_input_size(self):
        return (320, 320)

    def convert_inference_coords(self, box, metadata, picam2):
        # Pass through for testing (x, y, w, h)
        return box

    def show_network_fw_progress_bar(self):
        pass

    def set_outputs(self, outputs):
        """Test helper to inject inference outputs."""
        self._outputs = outputs


class MockPicamera2:
    """Mock Picamera2 class."""

    def __init__(self, camera_num=0):
        self.camera_num = camera_num
        self._config = {
            "main": {"size": (640, 480)},
        }
        self._metadata = {}
        self._started = False

    def create_preview_configuration(self, **kwargs):
        return self._config

    def start(self, config, show_preview=False):
        self._started = True

    def stop(self):
        self._started = False

    def close(self):
        pass

    def capture_metadata(self):
        return self._metadata

    def camera_configuration(self):
        return self._config


class MockNetworkIntrinsics:
    """Mock NetworkIntrinsics."""

    def __init__(self):
        self.task = ""
        self.postprocess = None
        self.bbox_normalization = False
        self.bbox_order = "yx"

    def update_with_defaults(self):
        pass


# ============================================================================
# Tests: Detection dataclass
# ============================================================================


class TestDetection:
    """Tests for Detection dataclass."""

    def test_detection_creation(self) -> None:
        from src.drivers.camera.imx500_cv import Detection

        det = Detection(
            category=0,
            confidence=0.85,
            bbox=(100.0, 50.0, 200.0, 300.0),
            center_x=0.25,
            center_y=-0.1,
            area=60000.0,
        )
        assert det.category == 0
        assert det.confidence == 0.85
        assert det.bbox == (100.0, 50.0, 200.0, 300.0)
        assert det.center_x == 0.25
        assert det.center_y == -0.1
        assert det.area == 60000.0

    def test_detection_is_frozen(self) -> None:
        from src.drivers.camera.imx500_cv import Detection

        det = Detection(0, 0.9, (0, 0, 10, 10), 0.0, 0.0, 100.0)
        with pytest.raises(AttributeError):
            det.confidence = 0.5


# ============================================================================
# Tests: Constructor validation
# ============================================================================


class TestIMX500CVDriverInit:
    """Tests for IMX500CVDriver constructor validation."""

    def test_default_construction(self) -> None:
        from src.drivers.camera.imx500_cv import IMX500CVDriver
        driver = IMX500CVDriver()
        assert driver.is_running is False
        assert driver.frame_count == 0

    def test_invalid_confidence_threshold_zero(self) -> None:
        from src.drivers.camera.imx500_cv import IMX500CVDriver
        with pytest.raises(ValueError, match="confidence_threshold"):
            IMX500CVDriver(confidence_threshold=0.0)

    def test_invalid_confidence_threshold_negative(self) -> None:
        from src.drivers.camera.imx500_cv import IMX500CVDriver
        with pytest.raises(ValueError, match="confidence_threshold"):
            IMX500CVDriver(confidence_threshold=-0.5)

    def test_invalid_confidence_threshold_over_one(self) -> None:
        from src.drivers.camera.imx500_cv import IMX500CVDriver
        with pytest.raises(ValueError, match="confidence_threshold"):
            IMX500CVDriver(confidence_threshold=1.5)

    def test_valid_confidence_threshold_one(self) -> None:
        from src.drivers.camera.imx500_cv import IMX500CVDriver
        driver = IMX500CVDriver(confidence_threshold=1.0)
        assert driver is not None

    def test_invalid_iou_threshold(self) -> None:
        from src.drivers.camera.imx500_cv import IMX500CVDriver
        with pytest.raises(ValueError, match="iou_threshold"):
            IMX500CVDriver(iou_threshold=0.0)

    def test_invalid_max_detections(self) -> None:
        from src.drivers.camera.imx500_cv import IMX500CVDriver
        with pytest.raises(ValueError, match="max_detections"):
            IMX500CVDriver(max_detections=0)

    def test_invalid_target_fps_zero(self) -> None:
        from src.drivers.camera.imx500_cv import IMX500CVDriver
        with pytest.raises(ValueError, match="target_fps"):
            IMX500CVDriver(target_fps=0)

    def test_invalid_target_fps_negative(self) -> None:
        from src.drivers.camera.imx500_cv import IMX500CVDriver
        with pytest.raises(ValueError, match="target_fps"):
            IMX500CVDriver(target_fps=-10)

    def test_custom_parameters(self) -> None:
        from src.drivers.camera.imx500_cv import IMX500CVDriver
        driver = IMX500CVDriver(
            model_path="/test/model.rpk",
            confidence_threshold=0.8,
            max_detections=5,
            iou_threshold=0.5,
            target_fps=15.0,
            person_only=False,
        )
        assert driver.is_running is False


# ============================================================================
# Tests: Detection cache (thread-safety)
# ============================================================================


class TestDetectionCache:
    """Tests for get_detections() thread safety and caching."""

    def test_empty_detections_initially(self) -> None:
        from src.drivers.camera.imx500_cv import IMX500CVDriver
        driver = IMX500CVDriver()
        assert driver.get_detections() == []

    def test_detection_age_inf_initially(self) -> None:
        from src.drivers.camera.imx500_cv import IMX500CVDriver
        driver = IMX500CVDriver()
        assert driver.get_detection_age_ms() == float("inf")

    def test_get_detections_returns_copy(self) -> None:
        from src.drivers.camera.imx500_cv import IMX500CVDriver, Detection
        driver = IMX500CVDriver()

        # Inject detections via internal state
        det = Detection(0, 0.9, (0, 0, 100, 200), 0.0, 0.0, 20000.0)
        with driver._lock:
            driver._last_detections = [det]
            driver._last_detection_time = time.monotonic()

        result = driver.get_detections()
        assert len(result) == 1
        assert result[0] is det

        # Modifying returned list doesn't affect internal state
        result.clear()
        assert len(driver.get_detections()) == 1

    def test_concurrent_get_detections(self) -> None:
        from src.drivers.camera.imx500_cv import IMX500CVDriver, Detection
        driver = IMX500CVDriver()

        det = Detection(0, 0.9, (0, 0, 100, 200), 0.0, 0.0, 20000.0)
        with driver._lock:
            driver._last_detections = [det]
            driver._last_detection_time = time.monotonic()

        results = []
        errors = []

        def reader():
            try:
                for _ in range(100):
                    dets = driver.get_detections()
                    results.append(len(dets))
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=reader) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5.0)

        assert not errors
        assert all(r == 1 for r in results)


# ============================================================================
# Tests: Start/stop lifecycle
# ============================================================================


class TestLifecycle:
    """Tests for start/stop lifecycle management."""

    def test_double_start_raises(self) -> None:
        from src.drivers.camera.imx500_cv import IMX500CVDriver
        driver = IMX500CVDriver()
        driver._running.set()
        with pytest.raises(RuntimeError, match="already running"):
            driver.start()
        driver._running.clear()

    def test_stop_when_not_running_is_noop(self) -> None:
        from src.drivers.camera.imx500_cv import IMX500CVDriver
        driver = IMX500CVDriver()
        driver.stop()  # Should not raise

    @patch("src.drivers.camera.imx500_cv.IMX500CVDriver._init_hardware")
    def test_start_sets_running(self, mock_init) -> None:
        from src.drivers.camera.imx500_cv import IMX500CVDriver
        driver = IMX500CVDriver()

        # Mock the capture loop to exit immediately
        original_loop = driver._capture_loop

        def quick_loop():
            time.sleep(0.05)

        driver._capture_loop = quick_loop
        driver.start()
        assert driver.is_running is True
        driver.stop()
        assert driver.is_running is False

    @patch("src.drivers.camera.imx500_cv.IMX500CVDriver._init_hardware")
    def test_stop_cleans_up_thread(self, mock_init) -> None:
        from src.drivers.camera.imx500_cv import IMX500CVDriver
        driver = IMX500CVDriver()
        driver._capture_loop = lambda: time.sleep(0.05)
        driver.start()
        assert driver._capture_thread is not None
        driver.stop()
        assert driver._capture_thread is None


# ============================================================================
# Tests: Parse detections
# ============================================================================


class TestParseDetections:
    """Tests for detection parsing logic."""

    def test_none_output_returns_none(self) -> None:
        from src.drivers.camera.imx500_cv import IMX500CVDriver
        driver = IMX500CVDriver()

        mock_imx = MockIMX500("/test.rpk")
        mock_imx.set_outputs(None)
        driver._imx500 = mock_imx
        driver._picam2 = MockPicamera2()
        driver._intrinsics = MockNetworkIntrinsics()

        result = driver._parse_detections({})
        assert result is None

    def test_parse_person_detection(self) -> None:
        import numpy as np
        from src.drivers.camera.imx500_cv import IMX500CVDriver

        driver = IMX500CVDriver(confidence_threshold=0.5, person_only=True)

        mock_imx = MockIMX500("/test.rpk")
        # Standard pp model output: [batch_boxes], [batch_scores], [batch_classes]
        # Each has a batch dimension: np_outputs[0][0] indexes into batch
        boxes = np.array([[[100, 50, 200, 300]]])  # (1, N, 4)
        scores = np.array([[0.85]])                  # (1, N)
        classes = np.array([[0]])                     # (1, N) person
        mock_imx.set_outputs([boxes, scores, classes])

        driver._imx500 = mock_imx
        driver._picam2 = MockPicamera2()
        driver._intrinsics = MockNetworkIntrinsics()

        result = driver._parse_detections({})
        assert result is not None
        assert len(result) == 1
        assert result[0].category == 0
        assert result[0].confidence == 0.85

    def test_filter_non_person_when_person_only(self) -> None:
        import numpy as np
        from src.drivers.camera.imx500_cv import IMX500CVDriver

        driver = IMX500CVDriver(confidence_threshold=0.3, person_only=True)

        mock_imx = MockIMX500("/test.rpk")
        boxes = np.array([[[100, 50, 200, 300], [10, 20, 30, 40]]])
        scores = np.array([[0.85, 0.90]])
        classes = np.array([[0, 2]])  # person + car
        mock_imx.set_outputs([boxes, scores, classes])

        driver._imx500 = mock_imx
        driver._picam2 = MockPicamera2()
        driver._intrinsics = MockNetworkIntrinsics()

        result = driver._parse_detections({})
        assert len(result) == 1
        assert result[0].category == 0

    def test_allow_all_classes_when_not_person_only(self) -> None:
        import numpy as np
        from src.drivers.camera.imx500_cv import IMX500CVDriver

        driver = IMX500CVDriver(confidence_threshold=0.3, person_only=False)

        mock_imx = MockIMX500("/test.rpk")
        boxes = np.array([[[100, 50, 200, 300], [10, 20, 30, 40]]])
        scores = np.array([[0.85, 0.90]])
        classes = np.array([[0, 2]])  # person + car
        mock_imx.set_outputs([boxes, scores, classes])

        driver._imx500 = mock_imx
        driver._picam2 = MockPicamera2()
        driver._intrinsics = MockNetworkIntrinsics()

        result = driver._parse_detections({})
        assert len(result) == 2

    def test_filter_low_confidence(self) -> None:
        import numpy as np
        from src.drivers.camera.imx500_cv import IMX500CVDriver

        driver = IMX500CVDriver(confidence_threshold=0.7, person_only=False)

        mock_imx = MockIMX500("/test.rpk")
        boxes = np.array([[[100, 50, 200, 300], [10, 20, 30, 40]]])
        scores = np.array([[0.85, 0.30]])
        classes = np.array([[0, 0]])
        mock_imx.set_outputs([boxes, scores, classes])

        driver._imx500 = mock_imx
        driver._picam2 = MockPicamera2()
        driver._intrinsics = MockNetworkIntrinsics()

        result = driver._parse_detections({})
        assert len(result) == 1
        assert result[0].confidence == 0.85

    def test_max_detections_limit(self) -> None:
        import numpy as np
        from src.drivers.camera.imx500_cv import IMX500CVDriver

        driver = IMX500CVDriver(
            confidence_threshold=0.1, max_detections=2, person_only=False,
        )

        mock_imx = MockIMX500("/test.rpk")
        boxes = np.array([[[i * 10, i * 10, i * 10 + 50, i * 10 + 50] for i in range(5)]])
        scores = np.array([[0.9, 0.8, 0.7, 0.6, 0.5]])
        classes = np.array([[0, 0, 0, 0, 0]])
        mock_imx.set_outputs([boxes, scores, classes])

        driver._imx500 = mock_imx
        driver._picam2 = MockPicamera2()
        driver._intrinsics = MockNetworkIntrinsics()

        result = driver._parse_detections({})
        assert len(result) <= 2

    def test_center_normalization(self) -> None:
        import numpy as np
        from src.drivers.camera.imx500_cv import IMX500CVDriver

        driver = IMX500CVDriver(confidence_threshold=0.1, person_only=False)

        mock_imx = MockIMX500("/test.rpk")
        # Box at exact center of 640x480 frame: x=270, y=190, w=100, h=100
        # Center: (320, 240) → normalized (0, 0)
        boxes = np.array([[[270, 190, 100, 100]]])  # convert_inference_coords passes through
        scores = np.array([[0.9]])
        classes = np.array([[0]])
        mock_imx.set_outputs([boxes, scores, classes])

        # Mock convert_inference_coords to return (x, y, w, h)
        mock_imx.convert_inference_coords = lambda box, meta, cam: box

        driver._imx500 = mock_imx
        driver._picam2 = MockPicamera2()
        driver._intrinsics = MockNetworkIntrinsics()

        result = driver._parse_detections({})
        assert len(result) == 1
        # Center at (270+50=320, 190+50=240) on 640x480 → (0, 0)
        assert abs(result[0].center_x) < 0.01
        assert abs(result[0].center_y) < 0.01

    def test_detection_area_calculated(self) -> None:
        import numpy as np
        from src.drivers.camera.imx500_cv import IMX500CVDriver

        driver = IMX500CVDriver(confidence_threshold=0.1, person_only=False)

        mock_imx = MockIMX500("/test.rpk")
        boxes = np.array([[[0, 0, 100, 200]]])
        scores = np.array([[0.9]])
        classes = np.array([[0]])
        mock_imx.set_outputs([boxes, scores, classes])
        mock_imx.convert_inference_coords = lambda box, meta, cam: box

        driver._imx500 = mock_imx
        driver._picam2 = MockPicamera2()
        driver._intrinsics = MockNetworkIntrinsics()

        result = driver._parse_detections({})
        assert result[0].area == 100.0 * 200.0


# ============================================================================
# Tests: Capture loop error handling
# ============================================================================


class TestCaptureLoop:
    """Tests for capture loop resilience."""

    def test_capture_loop_handles_exception(self) -> None:
        from src.drivers.camera.imx500_cv import IMX500CVDriver
        driver = IMX500CVDriver()
        driver._running.set()

        call_count = 0

        def failing_capture():
            nonlocal call_count
            call_count += 1
            if call_count >= 3:
                driver._running.clear()
            raise RuntimeError("Camera error")

        mock_picam2 = MockPicamera2()
        mock_picam2.capture_metadata = failing_capture
        driver._picam2 = mock_picam2

        driver._capture_loop()
        assert call_count >= 3  # Loop continued despite errors

    def test_frame_count_increments(self) -> None:
        import numpy as np
        from src.drivers.camera.imx500_cv import IMX500CVDriver

        driver = IMX500CVDriver(confidence_threshold=0.1, person_only=False)
        driver._running.set()

        mock_imx = MockIMX500("/test.rpk")
        boxes = np.array([[[0, 0, 50, 50]]])
        scores = np.array([[0.9]])
        classes = np.array([[0]])
        mock_imx.set_outputs([boxes, scores, classes])
        mock_imx.convert_inference_coords = lambda box, meta, cam: box

        driver._imx500 = mock_imx
        driver._intrinsics = MockNetworkIntrinsics()

        mock_picam = MockPicamera2()
        call_count = 0

        def counting_capture():
            nonlocal call_count
            call_count += 1
            if call_count >= 5:
                driver._running.clear()
            return {}

        mock_picam.capture_metadata = counting_capture
        driver._picam2 = mock_picam

        driver._capture_loop()
        assert driver.frame_count >= 4
