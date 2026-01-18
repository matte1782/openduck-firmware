#!/usr/bin/env python3
"""
Base Pattern Class for OpenDuck Mini V3 LED Animations

Disney Animation Principles Applied:
- Timing: Speed variations for emotion
- Slow In/Slow Out: Easing functions
- Secondary Action: Subtle background variations

Author: Boston Dynamics Animation Systems Engineer
Created: 18 January 2026
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Tuple, Optional
import math
import threading
import time

# Type alias for RGB color tuples
RGB = Tuple[int, int, int]


@dataclass
class PatternConfig:
    """Configuration for pattern behavior."""
    speed: float = 1.0          # Multiplier for animation speed (0.1-5.0)
    brightness: float = 1.0     # Overall brightness (0.0-1.0)
    reverse: bool = False       # Play pattern in reverse
    blend_frames: int = 10      # Frames for pattern transitions

    def __post_init__(self):
        """Validate configuration parameters.

        Raises:
            TypeError: If speed or brightness are not numeric types
            ValueError: If speed or brightness are NaN, infinite, or out of bounds
        """
        # Validate speed
        if not isinstance(self.speed, (int, float)):
            raise TypeError(f"speed must be numeric, got {type(self.speed).__name__}")
        if math.isnan(self.speed) or math.isinf(self.speed):
            raise ValueError(f"speed must be finite, got {self.speed}")
        if self.speed < 0.1 or self.speed > 5.0:
            raise ValueError(f"speed must be 0.1-5.0, got {self.speed}")

        # Validate brightness
        if not isinstance(self.brightness, (int, float)):
            raise TypeError(f"brightness must be numeric, got {type(self.brightness).__name__}")
        if math.isnan(self.brightness) or math.isinf(self.brightness):
            raise ValueError(f"brightness must be finite, got {self.brightness}")
        if self.brightness < 0.0 or self.brightness > 1.0:
            raise ValueError(f"brightness must be 0.0-1.0, got {self.brightness}")

        # Validate blend_frames
        if not isinstance(self.blend_frames, int):
            raise TypeError(f"blend_frames must be int, got {type(self.blend_frames).__name__}")
        if self.blend_frames < 1:
            raise ValueError(f"blend_frames must be >= 1, got {self.blend_frames}")


@dataclass
class FrameMetrics:
    """Performance metrics for a single frame."""
    frame_number: int
    render_time_us: int         # Microseconds to render
    timestamp: float            # time.monotonic()


class PatternBase(ABC):
    """Abstract base class for all LED patterns.

    All patterns must:
    1. Implement _compute_frame() to generate pixel colors
    2. Use self._pixel_buffer for zero-allocation rendering
    3. Call advance() between frames

    Performance target: <10ms render time for 50Hz refresh.

    Thread Safety:
        The render() method is thread-safe using threading.Lock.
        Pattern state (_frame, _pixel_buffer) is protected during rendering.
        However, for best performance, use patterns in a single-threaded context.
    """

    # Class constants (override in subclasses)
    NAME: str = "base"
    DESCRIPTION: str = "Base pattern class"
    DEFAULT_SPEED: float = 1.0
    MIN_BRIGHTNESS: float = 0.0
    MAX_BRIGHTNESS: float = 1.0

    def __init__(self, num_pixels: int = 16, config: Optional[PatternConfig] = None):
        """Initialize pattern with pixel count and optional config.

        Args:
            num_pixels: Number of LEDs in the ring (default: 16)
            config: Optional PatternConfig for customization

        Raises:
            ValueError: If num_pixels is not positive
        """
        if num_pixels <= 0:
            raise ValueError(f"num_pixels must be positive, got {num_pixels}")

        self.num_pixels = num_pixels
        self.config = config or PatternConfig()
        self._frame = 0
        self._start_time = time.monotonic()
        self._last_metrics: Optional[FrameMetrics] = None

        # Pre-allocate pixel buffer (avoid allocations in render loop)
        self._pixel_buffer: List[RGB] = [(0, 0, 0)] * num_pixels

        # Thread safety lock for render operations
        self._render_lock = threading.Lock()

    @abstractmethod
    def _compute_frame(self, base_color: RGB) -> List[RGB]:
        """Compute pixel values for current frame.

        Must be overridden by subclasses.
        Should modify self._pixel_buffer in place for best performance.

        Args:
            base_color: Base RGB color for the pattern

        Returns:
            List of RGB tuples for each pixel
        """
        pass

    def render(self, base_color: RGB) -> List[RGB]:
        """Render current frame with timing metrics.

        Thread-safe: Uses internal lock to protect pattern state during rendering.

        Args:
            base_color: Base RGB color (0-255 per channel)

        Returns:
            List of RGB tuples for all pixels
        """
        with self._render_lock:
            start = time.monotonic()

            # Apply brightness scaling to base color
            scaled_color = self._scale_color(base_color, self.config.brightness)

            # Compute frame (subclass implementation)
            result = self._compute_frame(scaled_color)

            # Record metrics
            end = time.monotonic()
            self._last_metrics = FrameMetrics(
                frame_number=self._frame,
                render_time_us=int((end - start) * 1_000_000),
                timestamp=end,
            )

            return result

    def advance(self):
        """Advance to next frame with thread safety and smooth wrapping."""
        with self._render_lock:
            if self.config.reverse:
                self._frame = (self._frame - 1) % 1_000_000
            else:
                self._frame = (self._frame + 1) % 1_000_000

    def reset(self):
        """Reset pattern to initial state."""
        self._frame = 0
        self._start_time = time.monotonic()

    def get_elapsed_time(self) -> float:
        """Get elapsed time since pattern start."""
        return time.monotonic() - self._start_time

    def get_progress(self, cycle_frames: int) -> float:
        """Get normalized progress through cycle (0.0-1.0).

        Args:
            cycle_frames: Number of frames in one complete cycle

        Returns:
            Progress value between 0.0 and 1.0

        Raises:
            ValueError: If cycle_frames is not positive
        """
        if cycle_frames <= 0:
            raise ValueError(f"cycle_frames must be positive, got {cycle_frames}")

        effective_frame = int(self._frame * self.config.speed)
        return (effective_frame % cycle_frames) / cycle_frames

    def get_metrics(self) -> Optional[FrameMetrics]:
        """Get last frame's performance metrics."""
        return self._last_metrics

    @staticmethod
    def _scale_color(color: RGB, factor: float) -> RGB:
        """Scale RGB color by brightness factor.

        Args:
            color: Input RGB tuple (0-255 per channel)
            factor: Scale factor (0.0-2.0)

        Returns:
            Scaled RGB tuple

        Raises:
            ValueError: If color values are not in 0-255 range or factor not in 0.0-2.0
        """
        if any(not 0 <= c <= 255 for c in color):
            raise ValueError(f"RGB values must be 0-255, got {color}")
        if not 0.0 <= factor <= 2.0:
            raise ValueError(f"factor must be 0.0-2.0, got {factor}")

        return (
            int(max(0, min(255, color[0] * factor))),
            int(max(0, min(255, color[1] * factor))),
            int(max(0, min(255, color[2] * factor))),
        )

    @staticmethod
    def _blend_colors(color1: RGB, color2: RGB, t: float) -> RGB:
        """Linear blend between two colors.

        Args:
            color1: Start color
            color2: End color
            t: Blend factor (0.0 = color1, 1.0 = color2)

        Returns:
            Blended RGB tuple
        """
        t = max(0.0, min(1.0, t))
        return (
            int(color1[0] + (color2[0] - color1[0]) * t),
            int(color1[1] + (color2[1] - color1[1]) * t),
            int(color1[2] + (color2[2] - color1[2]) * t),
        )
