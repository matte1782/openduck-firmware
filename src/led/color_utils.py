#!/usr/bin/env python3
"""
Color Utilities for OpenDuck Mini V3 LED Animations

Provides HSV/RGB color conversion and interpolation utilities for smooth
LED transitions with Pixar Rendering Team grade quality.

Features:
- O(1) HSV conversion using pre-computed lookup tables
- Linear RGB interpolation (fast, for same-hue transitions)
- HSV arc interpolation (natural, for cross-hue transitions)
- ColorTransition class for animated color changes

Disney Animation Principles Applied:
- Slow In/Slow Out: Easing-aware color transitions
- Follow Through: Smooth color settling

Author: Pixar Rendering Team Engineer
Created: 18 January 2026
"""

import math
import time
import threading
from dataclasses import dataclass, field
from typing import Tuple, Optional, List

# FIX D14-001: Conditional import for both package and path-based usage
# - Package import: from src.led.color_utils (uses src.animation.easing)
# - Path import: when src/ is in sys.path (uses animation.easing)
try:
    from animation.easing import ease, EASING_LUTS
except ImportError:
    from src.animation.easing import ease, EASING_LUTS

# =============================================================================
# Type Definitions
# =============================================================================

# Type aliases for clarity and documentation
RGB = Tuple[int, int, int]       # (0-255, 0-255, 0-255)
HSV = Tuple[float, float, float]  # (0-360, 0-1, 0-1)

# =============================================================================
# Module-Level Constants
# =============================================================================

# Lookup table size for HSV to RGB conversion (one entry per hue degree)
_HSV_LUT_SIZE = 360

# Pre-computed lookup tables for O(1) HSV conversion
_HSV_TO_RGB_LUT: Optional[List[RGB]] = None
_HSV_LUT_INITIALIZED: bool = False
_HSV_LUT_LOCK: threading.Lock = threading.Lock()

# Epsilon for floating point comparisons
_EPSILON = 1e-9


# =============================================================================
# LUT Initialization
# =============================================================================

def _init_hsv_lut() -> None:
    """Initialize HSV lookup table (called once on first use).

    Pre-computes RGB values for hue 0-359 at full saturation/value (s=1, v=1).
    Actual colors are then scaled by saturation and value at runtime.

    Thread Safety:
        Uses module-level lock to ensure single initialization.
    """
    global _HSV_TO_RGB_LUT, _HSV_LUT_INITIALIZED

    with _HSV_LUT_LOCK:
        if _HSV_LUT_INITIALIZED:
            return

        _HSV_TO_RGB_LUT = []

        for h in range(_HSV_LUT_SIZE):
            # Compute RGB for this hue at s=1, v=1
            # Using standard HSV to RGB algorithm
            sector = h / 60.0  # 0-6
            sector_index = int(sector) % 6
            f = sector - int(sector)  # Fractional part

            # At s=1, v=1, the formulas simplify:
            # p = v * (1 - s) = 0
            # q = v * (1 - s * f) = 1 - f
            # t = v * (1 - s * (1 - f)) = f
            p = 0.0
            q = 1.0 - f
            t = f

            if sector_index == 0:
                r, g, b = 1.0, t, p
            elif sector_index == 1:
                r, g, b = q, 1.0, p
            elif sector_index == 2:
                r, g, b = p, 1.0, t
            elif sector_index == 3:
                r, g, b = p, q, 1.0
            elif sector_index == 4:
                r, g, b = t, p, 1.0
            else:  # sector_index == 5
                r, g, b = 1.0, p, q

            _HSV_TO_RGB_LUT.append((
                int(round(r * 255)),
                int(round(g * 255)),
                int(round(b * 255))
            ))

        _HSV_LUT_INITIALIZED = True


def _ensure_lut_initialized() -> None:
    """Ensure LUT is initialized before use.

    FIX H-004: Properly synchronized double-checked locking pattern.
    Always acquire lock before checking the flag to avoid race conditions.
    """
    global _HSV_LUT_INITIALIZED
    with _HSV_LUT_LOCK:
        if not _HSV_LUT_INITIALIZED:
            _init_hsv_lut()


# =============================================================================
# RGB to HSV Conversion
# =============================================================================

def rgb_to_hsv(rgb: RGB) -> HSV:
    """Convert RGB color to HSV color space.

    Algorithm:
    1. Normalize RGB to 0-1 range
    2. Find max and min components
    3. Value = max
    4. Saturation = (max - min) / max (or 0 if max is 0)
    5. Hue based on which component is max:
       - Red max: hue = 60 * ((G - B) / (max - min))
       - Green max: hue = 60 * (2 + (B - R) / (max - min))
       - Blue max: hue = 60 * (4 + (R - G) / (max - min))
    6. Normalize hue to 0-360

    Edge Cases:
    - Black (0,0,0): Return (0.0, 0.0, 0.0) - hue undefined but use 0
    - White (255,255,255): Return (0.0, 0.0, 1.0) - hue undefined but use 0
    - Grayscale: Saturation = 0, hue = 0

    Args:
        rgb: RGB tuple (0-255 per channel)

    Returns:
        HSV tuple (hue: 0-360, saturation: 0-1, value: 0-1)

    Raises:
        ValueError: If RGB values outside 0-255 range
        TypeError: If rgb is not a tuple or has wrong length

    Example:
        >>> rgb_to_hsv((255, 0, 0))  # Pure red
        (0.0, 1.0, 1.0)
        >>> rgb_to_hsv((128, 128, 128))  # Gray
        (0.0, 0.0, 0.502...)
        >>> rgb_to_hsv((0, 255, 0))  # Pure green
        (120.0, 1.0, 1.0)
    """
    # Validate input
    if not isinstance(rgb, tuple) or len(rgb) != 3:
        raise TypeError(f"rgb must be a 3-tuple, got {type(rgb).__name__}")

    r, g, b = rgb

    # Validate range
    for i, c in enumerate((r, g, b)):
        if not isinstance(c, (int, float)):
            raise TypeError(f"RGB channel {i} must be numeric, got {type(c).__name__}")
        if c < 0 or c > 255:
            raise ValueError(f"RGB values must be 0-255, got {rgb}")

    # Normalize to 0-1 range
    r_norm = r / 255.0
    g_norm = g / 255.0
    b_norm = b / 255.0

    max_c = max(r_norm, g_norm, b_norm)
    min_c = min(r_norm, g_norm, b_norm)
    delta = max_c - min_c

    # Value is the maximum component
    v = max_c

    # Handle achromatic (grayscale) case
    if delta < _EPSILON:
        return (0.0, 0.0, v)

    # Saturation
    s = delta / max_c if max_c > _EPSILON else 0.0

    # Hue calculation
    if abs(max_c - r_norm) < _EPSILON:
        # Red is max
        h = 60.0 * ((g_norm - b_norm) / delta)
    elif abs(max_c - g_norm) < _EPSILON:
        # Green is max
        h = 60.0 * (2.0 + (b_norm - r_norm) / delta)
    else:
        # Blue is max
        h = 60.0 * (4.0 + (r_norm - g_norm) / delta)

    # Normalize hue to 0-360 using O(1) approach
    if h < 0:
        h += 360.0
    elif h >= 360.0:
        h -= 360.0

    return (h, s, v)


# =============================================================================
# HSV to RGB Conversion
# =============================================================================

def hsv_to_rgb(h: float, s: float, v: float) -> RGB:
    """Convert HSV color to RGB color space.

    Uses pre-computed LUT for O(1) performance when at full saturation.
    Falls back to direct computation for other saturation levels.

    Algorithm (standard HSV to RGB):
    1. Wrap hue to 0-360
    2. Clamp saturation and value to 0-1
    3. If saturation is 0, return grayscale based on value
    4. Calculate sector (0-5) from hue / 60
    5. Calculate intermediate values
    6. Map to RGB based on sector

    Performance:
    - Uses pre-computed LUT for hue conversion
    - Target: <1ms for 256 conversions

    Args:
        h: Hue (0-360 degrees, wraps around)
        s: Saturation (0-1, clamped)
        v: Value/brightness (0-1, clamped)

    Returns:
        RGB tuple (0-255 per channel)

    Raises:
        TypeError: If arguments are not numeric

    Example:
        >>> hsv_to_rgb(0, 1.0, 1.0)  # Pure red
        (255, 0, 0)
        >>> hsv_to_rgb(120, 1.0, 1.0)  # Pure green
        (0, 255, 0)
        >>> hsv_to_rgb(240, 1.0, 1.0)  # Pure blue
        (0, 0, 255)
    """
    # Validate types
    for name, val in [('h', h), ('s', s), ('v', v)]:
        if not isinstance(val, (int, float)):
            raise TypeError(f"{name} must be numeric, got {type(val).__name__}")
        if math.isnan(val) or math.isinf(val):
            raise ValueError(f"{name} must be finite, got {val}")

    # Wrap hue to 0-360 using O(1) approach
    h = h % 360.0
    if h < 0:
        h += 360.0

    # Clamp saturation and value to 0-1
    s = max(0.0, min(1.0, s))
    v = max(0.0, min(1.0, v))

    # Handle achromatic (grayscale) case
    if s < _EPSILON:
        gray = int(round(v * 255))
        return (gray, gray, gray)

    # Ensure LUT is initialized
    _ensure_lut_initialized()

    # Use LUT for full saturation optimization
    if s >= 1.0 - _EPSILON and v >= 1.0 - _EPSILON:
        hue_index = int(h) % 360
        return _HSV_TO_RGB_LUT[hue_index]

    # Standard HSV to RGB conversion for non-trivial cases
    sector = h / 60.0
    sector_index = int(sector) % 6
    f = sector - int(sector)  # Fractional part within sector

    # Intermediate values
    p = v * (1.0 - s)
    q = v * (1.0 - s * f)
    t = v * (1.0 - s * (1.0 - f))

    # Map to RGB based on sector
    if sector_index == 0:
        r, g, b = v, t, p
    elif sector_index == 1:
        r, g, b = q, v, p
    elif sector_index == 2:
        r, g, b = p, v, t
    elif sector_index == 3:
        r, g, b = p, q, v
    elif sector_index == 4:
        r, g, b = t, p, v
    else:  # sector_index == 5
        r, g, b = v, p, q

    return (
        int(round(r * 255)),
        int(round(g * 255)),
        int(round(b * 255))
    )


# =============================================================================
# Color Interpolation Functions
# =============================================================================

def color_interpolate(start: RGB, end: RGB, t: float) -> RGB:
    """Linear RGB interpolation between two colors.

    Direct RGB interpolation - fast but can produce muddy colors when
    interpolating across hue boundaries (e.g., red to green gives brown,
    not yellow).

    Use this for:
    - Same-hue transitions (brightness changes)
    - Quick transitions where visual quality is less critical
    - When performance is paramount

    Formula:
        result[i] = start[i] + (end[i] - start[i]) * t

    Args:
        start: Starting RGB color
        end: Ending RGB color
        t: Interpolation factor (0.0 = start, 1.0 = end, clamped)

    Returns:
        Interpolated RGB color

    Raises:
        ValueError: If RGB values outside 0-255 range
        TypeError: If inputs are not valid tuples

    Example:
        >>> color_interpolate((255, 0, 0), (0, 0, 255), 0.5)
        (127, 0, 127)  # Purple (direct path through RGB space)
        >>> color_interpolate((100, 100, 100), (200, 200, 200), 0.5)
        (150, 150, 150)  # Grayscale interpolation
    """
    # Validate inputs
    for name, rgb in [('start', start), ('end', end)]:
        if not isinstance(rgb, tuple) or len(rgb) != 3:
            raise TypeError(f"{name} must be a 3-tuple, got {type(rgb).__name__}")
        for i, c in enumerate(rgb):
            if not isinstance(c, (int, float)):
                raise TypeError(f"{name} channel {i} must be numeric")
            if c < 0 or c > 255:
                raise ValueError(f"RGB values must be 0-255, got {name}={rgb}")

    if not isinstance(t, (int, float)):
        raise TypeError(f"t must be numeric, got {type(t).__name__}")

    # Clamp t to 0-1
    t = max(0.0, min(1.0, t))

    # Linear interpolation
    r = start[0] + (end[0] - start[0]) * t
    g = start[1] + (end[1] - start[1]) * t
    b = start[2] + (end[2] - start[2]) * t

    # Round and clamp to valid RGB range
    return (
        int(max(0, min(255, round(r)))),
        int(max(0, min(255, round(g)))),
        int(max(0, min(255, round(b))))
    )


def color_arc_interpolate(
    start: RGB,
    end: RGB,
    t: float,
    direction: str = 'short'
) -> RGB:
    """HSV-based color interpolation following hue wheel.

    Interpolates through HSV space for more natural color transitions
    that follow the rainbow/hue wheel. Much better for transitions
    between different hues.

    Example: Red -> Green goes through Yellow (not muddy brown).

    Directions:
    - 'short': Take shortest path around hue wheel (default)
    - 'long': Take longest path (rainbow effect)
    - 'cw': Clockwise (increasing hue)
    - 'ccw': Counter-clockwise (decreasing hue)

    Algorithm:
    1. Convert start and end to HSV
    2. Handle hue wraparound (0/360 boundary)
    3. Interpolate H, S, V separately
    4. Convert back to RGB

    Edge Cases:
    - If either color is grayscale (s=0), hue is undefined
    - Fall back to RGB interpolation for grayscale

    Args:
        start: Starting RGB color
        end: Ending RGB color
        t: Interpolation factor (0.0 = start, 1.0 = end, clamped)
        direction: 'short' for shortest arc, 'long' for longest arc,
                  'cw' for clockwise, 'ccw' for counter-clockwise

    Returns:
        Interpolated RGB color

    Raises:
        ValueError: If direction is invalid or RGB values out of range
        TypeError: If inputs are not valid types

    Example:
        >>> color_arc_interpolate((255, 0, 0), (0, 255, 0), 0.5)
        (255, 255, 0)  # Yellow (via hue wheel through 60 degrees)
        >>> color_arc_interpolate((255, 0, 0), (0, 0, 255), 0.5, 'cw')
        (0, 255, 0)  # Green (clockwise from red through green to blue)
    """
    # Validate direction
    valid_directions = ('short', 'long', 'cw', 'ccw')
    if direction not in valid_directions:
        raise ValueError(f"direction must be one of {valid_directions}, got '{direction}'")

    # Validate inputs
    for name, rgb in [('start', start), ('end', end)]:
        if not isinstance(rgb, tuple) or len(rgb) != 3:
            raise TypeError(f"{name} must be a 3-tuple, got {type(rgb).__name__}")
        for i, c in enumerate(rgb):
            if not isinstance(c, (int, float)):
                raise TypeError(f"{name} channel {i} must be numeric")
            if c < 0 or c > 255:
                raise ValueError(f"RGB values must be 0-255, got {name}={rgb}")

    if not isinstance(t, (int, float)):
        raise TypeError(f"t must be numeric, got {type(t).__name__}")

    # Clamp t to 0-1
    t = max(0.0, min(1.0, t))

    # Convert to HSV
    start_hsv = rgb_to_hsv(start)
    end_hsv = rgb_to_hsv(end)

    h1, s1, v1 = start_hsv
    h2, s2, v2 = end_hsv

    # Handle grayscale fallback (hue undefined)
    if s1 < _EPSILON or s2 < _EPSILON:
        # One or both colors are grayscale, fall back to RGB interpolation
        return color_interpolate(start, end, t)

    # Calculate hue difference and determine interpolation path
    hue_diff = h2 - h1

    # Normalize difference to -180 to +180 range using O(1) modular arithmetic
    # FIX H-001: Replaces O(n) while-loops that could hang with extreme float values
    hue_diff = ((hue_diff + 180) % 360) - 180

    if direction == 'short':
        # Use the normalized difference (shortest path)
        h_interp = h1 + hue_diff * t
    elif direction == 'long':
        # Take the long way around
        if hue_diff >= 0:
            # Short path is CW, so long path is CCW
            long_diff = hue_diff - 360
        else:
            # Short path is CCW, so long path is CW
            long_diff = hue_diff + 360
        h_interp = h1 + long_diff * t
    elif direction == 'cw':
        # Always go clockwise (increasing hue)
        if hue_diff < 0:
            hue_diff += 360
        h_interp = h1 + hue_diff * t
    else:  # direction == 'ccw'
        # Always go counter-clockwise (decreasing hue)
        if hue_diff > 0:
            hue_diff -= 360
        h_interp = h1 + hue_diff * t

    # Normalize hue to 0-360
    h_interp = h_interp % 360.0
    if h_interp < 0:
        h_interp += 360.0

    # Interpolate saturation and value linearly
    s_interp = s1 + (s2 - s1) * t
    v_interp = v1 + (v2 - v1) * t

    # Convert back to RGB
    return hsv_to_rgb(h_interp, s_interp, v_interp)


# =============================================================================
# ColorTransition Configuration
# =============================================================================

@dataclass
class ColorTransitionConfig:
    """Configuration for color transition animation.

    Attributes:
        duration_ms: Total transition duration in milliseconds
        easing: Easing function name ('linear', 'ease_in', 'ease_out', 'ease_in_out')
        use_hsv: If True, use HSV arc interpolation; if False, use RGB
        hsv_direction: Direction for HSV interpolation ('short', 'long', 'cw', 'ccw')

    Example:
        >>> config = ColorTransitionConfig(duration_ms=1000, easing='ease_in_out')
        >>> config = ColorTransitionConfig(use_hsv=False)  # RGB mode
    """
    duration_ms: int = 500
    easing: str = 'ease_in_out'
    use_hsv: bool = True
    hsv_direction: str = 'short'

    def __post_init__(self):
        """Validate configuration parameters.

        Raises:
            ValueError: If parameters are invalid
            TypeError: If parameters are wrong type
        """
        # Validate duration_ms
        if not isinstance(self.duration_ms, int):
            raise TypeError(f"duration_ms must be int, got {type(self.duration_ms).__name__}")
        if self.duration_ms <= 0:
            raise ValueError(f"duration_ms must be > 0, got {self.duration_ms}")

        # Validate easing
        if not isinstance(self.easing, str):
            raise TypeError(f"easing must be str, got {type(self.easing).__name__}")
        if self.easing not in EASING_LUTS:
            raise ValueError(f"easing must be one of {list(EASING_LUTS.keys())}, got '{self.easing}'")

        # Validate use_hsv
        if not isinstance(self.use_hsv, bool):
            raise TypeError(f"use_hsv must be bool, got {type(self.use_hsv).__name__}")

        # Validate hsv_direction
        valid_directions = ('short', 'long', 'cw', 'ccw')
        if not isinstance(self.hsv_direction, str):
            raise TypeError(f"hsv_direction must be str, got {type(self.hsv_direction).__name__}")
        if self.hsv_direction not in valid_directions:
            raise ValueError(f"hsv_direction must be one of {valid_directions}, got '{self.hsv_direction}'")

    def __repr__(self) -> str:
        """Return string representation for debugging."""
        return (
            f"ColorTransitionConfig(duration_ms={self.duration_ms}, "
            f"easing='{self.easing}', use_hsv={self.use_hsv}, "
            f"hsv_direction='{self.hsv_direction}')"
        )


# =============================================================================
# ColorTransition Class
# =============================================================================

class ColorTransition:
    """Animated transition between two colors.

    Handles smooth color interpolation with:
    - Configurable duration
    - Easing functions for Disney-quality animation
    - HSV or RGB interpolation modes
    - Real-time elapsed time tracking using time.monotonic()

    Thread Safety:
        Not thread-safe. Use external synchronization if needed.
        For concurrent access, wrap calls in a threading.Lock.

    Disney Animation Principles:
    - Slow In/Slow Out: Configurable easing for natural motion
    - Timing: Duration control for appropriate pacing

    Example:
        >>> transition = ColorTransition(
        ...     start=(255, 0, 0),    # Red
        ...     end=(0, 255, 0),      # Green
        ...     config=ColorTransitionConfig(duration_ms=1000)
        ... )
        >>> transition.start()
        >>> while not transition.is_complete():
        ...     color = transition.get_color()
        ...     apply_color(color)
        ...     time.sleep(0.02)  # 50Hz

    Attributes:
        start: Starting RGB color
        end: Ending RGB color
        config: ColorTransitionConfig instance
    """

    def __init__(
        self,
        start: RGB,
        end: RGB,
        config: Optional[ColorTransitionConfig] = None
    ) -> None:
        """Initialize color transition.

        Args:
            start: Starting RGB color (0-255 per channel)
            end: Ending RGB color (0-255 per channel)
            config: Transition configuration (uses defaults if None)

        Raises:
            ValueError: If RGB values are out of range
            TypeError: If inputs are not valid types
        """
        # Validate colors
        for name, rgb in [('start', start), ('end', end)]:
            if not isinstance(rgb, tuple) or len(rgb) != 3:
                raise TypeError(f"{name} must be a 3-tuple, got {type(rgb).__name__}")
            for i, c in enumerate(rgb):
                if not isinstance(c, (int, float)):
                    raise TypeError(f"{name} channel {i} must be numeric")
                if c < 0 or c > 255:
                    raise ValueError(f"RGB values must be 0-255, got {name}={rgb}")

        self._start: RGB = start
        self._end: RGB = end
        self._config: ColorTransitionConfig = config or ColorTransitionConfig()

        # Timing state
        self._start_time: Optional[float] = None
        self._is_started: bool = False

    @property
    def start_color(self) -> RGB:
        """Get starting color."""
        return self._start

    @property
    def end_color(self) -> RGB:
        """Get ending color."""
        return self._end

    @property
    def config(self) -> ColorTransitionConfig:
        """Get transition configuration."""
        return self._config

    def start(self) -> None:
        """Start the transition timer.

        Resets elapsed time to zero and begins tracking.
        Can be called multiple times to restart the transition.
        """
        self._start_time = time.monotonic()
        self._is_started = True

    def get_color(self, elapsed_ms: Optional[int] = None) -> RGB:
        """Get interpolated color at current or specified time.

        If not started yet, returns start color.
        If elapsed exceeds duration, returns end color.

        Args:
            elapsed_ms: Override elapsed time in milliseconds
                       (None = use actual elapsed time from start())

        Returns:
            Interpolated RGB color for current/specified time

        Note:
            If called before start(), returns start color.
            If elapsed_ms is negative, returns start color.
        """
        # Handle not-started case
        if not self._is_started and elapsed_ms is None:
            return self._start

        # Calculate elapsed time
        if elapsed_ms is not None:
            elapsed = max(0, elapsed_ms)
        else:
            current_time = time.monotonic()
            elapsed = (current_time - self._start_time) * 1000  # Convert to ms

        # FIX H-006: Guard against division by zero
        if self._config.duration_ms <= 0:
            return self._end  # Instant transition to end color

        # Calculate raw progress (0.0 to 1.0)
        raw_progress = elapsed / self._config.duration_ms
        raw_progress = max(0.0, min(1.0, raw_progress))

        # Apply easing
        eased_progress = ease(raw_progress, self._config.easing)

        # Interpolate color
        if self._config.use_hsv:
            return color_arc_interpolate(
                self._start,
                self._end,
                eased_progress,
                self._config.hsv_direction
            )
        else:
            return color_interpolate(self._start, self._end, eased_progress)

    def get_progress(self) -> float:
        """Get normalized progress (0.0 to 1.0).

        Returns raw progress without easing applied.

        Returns:
            Progress through transition (clamped to 0.0-1.0)
            Returns 0.0 if not started.
        """
        if not self._is_started:
            return 0.0

        elapsed = (time.monotonic() - self._start_time) * 1000
        progress = elapsed / self._config.duration_ms
        return max(0.0, min(1.0, progress))

    def get_eased_progress(self) -> float:
        """Get eased progress (0.0 to 1.0).

        Returns progress with easing function applied.

        Returns:
            Eased progress through transition
            Returns 0.0 if not started.
        """
        raw = self.get_progress()
        return ease(raw, self._config.easing)

    def is_complete(self) -> bool:
        """Check if transition has completed.

        Returns:
            True if elapsed time >= duration or not started
        """
        if not self._is_started:
            return False

        elapsed = (time.monotonic() - self._start_time) * 1000
        return elapsed >= self._config.duration_ms

    def reset(self) -> None:
        """Reset transition to beginning.

        Clears started state. Must call start() again to begin.
        """
        self._start_time = None
        self._is_started = False

    def reverse(self) -> None:
        """Reverse transition direction (swap start/end).

        Swaps start and end colors. Does not affect current timing.
        """
        self._start, self._end = self._end, self._start

    def get_elapsed_ms(self) -> int:
        """Get elapsed time in milliseconds.

        Returns:
            Elapsed milliseconds since start(), or 0 if not started.
        """
        if not self._is_started:
            return 0

        elapsed = (time.monotonic() - self._start_time) * 1000
        return int(max(0, elapsed))

    def get_remaining_ms(self) -> int:
        """Get remaining time in milliseconds.

        Returns:
            Remaining milliseconds until completion, or full duration if not started.
        """
        elapsed = self.get_elapsed_ms()
        remaining = self._config.duration_ms - elapsed
        return max(0, remaining)

    def __repr__(self) -> str:
        """Return string representation for debugging."""
        return (
            f"ColorTransition(start={self._start}, end={self._end}, "
            f"config={self._config!r}, is_started={self._is_started})"
        )


# =============================================================================
# Convenience Functions
# =============================================================================

def lerp_color(start: RGB, end: RGB, t: float) -> RGB:
    """Alias for color_interpolate (linear RGB interpolation).

    Provided for familiarity with graphics programming conventions.

    Args:
        start: Starting RGB color
        end: Ending RGB color
        t: Interpolation factor (0.0 = start, 1.0 = end)

    Returns:
        Interpolated RGB color
    """
    return color_interpolate(start, end, t)


def hue_shift(rgb: RGB, degrees: float) -> RGB:
    """Shift hue of an RGB color by specified degrees.

    Useful for creating color variations while preserving saturation and value.

    Args:
        rgb: Input RGB color
        degrees: Hue shift in degrees (positive = clockwise)

    Returns:
        RGB color with shifted hue

    Example:
        >>> hue_shift((255, 0, 0), 120)  # Red + 120 degrees
        (0, 255, 0)  # Green
    """
    h, s, v = rgb_to_hsv(rgb)
    new_h = (h + degrees) % 360.0
    if new_h < 0:
        new_h += 360.0
    return hsv_to_rgb(new_h, s, v)


def brightness_adjust(rgb: RGB, factor: float) -> RGB:
    """Adjust brightness of an RGB color.

    Adjusts the V (value) component in HSV space.

    Args:
        rgb: Input RGB color
        factor: Brightness multiplier (0.0 = black, 1.0 = original, 2.0 = double)

    Returns:
        RGB color with adjusted brightness

    Example:
        >>> brightness_adjust((255, 128, 0), 0.5)
        (127, 64, 0)  # Half brightness
    """
    h, s, v = rgb_to_hsv(rgb)
    new_v = max(0.0, min(1.0, v * factor))
    return hsv_to_rgb(h, s, new_v)


def saturation_adjust(rgb: RGB, factor: float) -> RGB:
    """Adjust saturation of an RGB color.

    Adjusts the S (saturation) component in HSV space.

    Args:
        rgb: Input RGB color
        factor: Saturation multiplier (0.0 = grayscale, 1.0 = original)

    Returns:
        RGB color with adjusted saturation

    Example:
        >>> saturation_adjust((255, 0, 0), 0.5)
        (255, 127, 127)  # Half saturation (more pastel)
    """
    h, s, v = rgb_to_hsv(rgb)
    new_s = max(0.0, min(1.0, s * factor))
    return hsv_to_rgb(h, new_s, v)


def complementary_color(rgb: RGB) -> RGB:
    """Get the complementary color (opposite on hue wheel).

    Args:
        rgb: Input RGB color

    Returns:
        RGB color shifted 180 degrees on hue wheel

    Example:
        >>> complementary_color((255, 0, 0))  # Red
        (0, 255, 255)  # Cyan
    """
    return hue_shift(rgb, 180.0)


# =============================================================================
# Module Initialization
# =============================================================================

# Pre-initialize LUT on module load for faster first access
_init_hsv_lut()
