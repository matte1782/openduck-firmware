# Day 11 Architecture Specification
## OpenDuck Mini V3 - Head Controller & Color Utilities

**Document Version:** 1.0
**Created:** 18 January 2026
**Author:** Agent 0 (Chief Orchestrator)
**Quality Standard:** Boston Dynamics / Pixar / DeepMind Grade

---

## Table of Contents

1. [Overview](#1-overview)
2. [Dependency Graph](#2-dependency-graph)
3. [HeadController Interface](#3-headcontroller-interface)
4. [Color Utilities Interface](#4-color-utilities-interface)
5. [Integration Points](#5-integration-points)
6. [File Locations](#6-file-locations)
7. [Coding Standards](#7-coding-standards)
8. [Test Requirements](#8-test-requirements)

---

## 1. Overview

### 1.1 Purpose

Day 11 delivers two foundational modules:

1. **HeadController** - 2-DOF pan/tilt head control with expressive movements (nod, shake, glance, curious tilt)
2. **Color Utilities** - HSV/RGB conversion and color interpolation for smooth LED transitions

These modules integrate with existing animation and servo systems to enable:
- Expressive head movements coordinated with emotions
- Smooth color transitions for LED patterns
- Foundation for future eye-tracking and attention behaviors

### 1.2 Design Principles

| Principle | Application |
|-----------|-------------|
| **Disney Animation** | Head movements use ease_in_out for natural motion; "Anticipation" before major movements |
| **Zero Allocation** | Pre-allocated buffers for real-time performance |
| **Thread Safety** | All public methods thread-safe using existing lock patterns |
| **Fail Safe** | Emergency stop always available; invalid inputs clamped, not crashed |
| **Type Safety** | Full type hints; dataclasses for configurations |

### 1.3 Existing Patterns to Follow

From analysis of the codebase:

- **Dataclass patterns:** `EmotionConfig`, `PatternConfig`, `Keyframe` (with `__post_init__` validation)
- **Enum patterns:** `EmotionState` with string values
- **Driver patterns:** `PCA9685Driver` with `_lock` for thread safety
- **Animation patterns:** `AnimationSequence` with keyframes, `AnimationPlayer` with real-time timing
- **LUT patterns:** Pre-computed lookup tables (easing, sine) for O(1) performance

---

## 2. Dependency Graph

```
                    +------------------+
                    |  robot_config    |
                    |     (YAML)       |
                    +--------+---------+
                             |
                             v
+----------------+   +------------------+   +------------------+
|   easing.py    |   |   pca9685.py     |   |   emotions.py    |
| (LUT easing)   |   |  (servo driver)  |   | (EmotionState)   |
+-------+--------+   +--------+---------+   +--------+---------+
        |                     |                      |
        v                     v                      |
+-------+---------------------+---------+            |
|                                       |            |
|         head_controller.py            |<-----------+
|         (NEW - Day 11)                |
|                                       |
+---------------------------------------+
        |
        | Uses for movement interpolation
        v
+------------------+
|  color_utils.py  |
|  (NEW - Day 11)  |
+------------------+
        |
        | Used by LED patterns
        v
+------------------+
|  patterns/*.py   |
| (existing LED)   |
+------------------+
```

---

## 3. HeadController Interface

### 3.1 Data Structures

```python
# File: firmware/src/control/head_controller.py

from dataclasses import dataclass, field
from typing import Optional, Tuple, Callable
from enum import Enum


class HeadMovementType(Enum):
    """Types of head movements for animation coordination."""
    LOOK = "look"           # Direct pan/tilt positioning
    NOD = "nod"             # Vertical affirmation
    SHAKE = "shake"         # Horizontal negation
    TILT = "tilt"           # Curious head tilt
    GLANCE = "glance"       # Quick look and return
    RESET = "reset"         # Return to center


@dataclass
class HeadLimits:
    """Hardware limits for head servos.

    All angles in degrees. Center position is 0.0 for both axes.

    Attributes:
        pan_min: Minimum pan angle (negative = left)
        pan_max: Maximum pan angle (positive = right)
        tilt_min: Minimum tilt angle (negative = down)
        tilt_max: Maximum tilt angle (positive = up)
        pan_center: Center/home position for pan (usually 0.0)
        tilt_center: Center/home position for tilt (usually 0.0)
    """
    pan_min: float = -90.0
    pan_max: float = 90.0
    tilt_min: float = -45.0
    tilt_max: float = 45.0
    pan_center: float = 0.0
    tilt_center: float = 0.0

    def __post_init__(self):
        """Validate limit configuration."""
        if self.pan_min >= self.pan_max:
            raise ValueError(f"pan_min ({self.pan_min}) must be < pan_max ({self.pan_max})")
        if self.tilt_min >= self.tilt_max:
            raise ValueError(f"tilt_min ({self.tilt_min}) must be < tilt_max ({self.tilt_max})")
        if not (self.pan_min <= self.pan_center <= self.pan_max):
            raise ValueError(f"pan_center ({self.pan_center}) must be within pan limits")
        if not (self.tilt_min <= self.tilt_center <= self.tilt_max):
            raise ValueError(f"tilt_center ({self.tilt_center}) must be within tilt limits")


@dataclass
class HeadConfig:
    """Configuration for HeadController.

    Attributes:
        pan_channel: PCA9685 channel for pan servo (0-15)
        tilt_channel: PCA9685 channel for tilt servo (0-15)
        limits: HeadLimits instance defining movement bounds
        pan_inverted: If True, invert pan servo direction
        tilt_inverted: If True, invert tilt servo direction
        default_speed_ms: Default movement duration in milliseconds
        easing: Default easing function name ('ease_in_out', 'ease_in', etc.)
    """
    pan_channel: int
    tilt_channel: int
    limits: HeadLimits = field(default_factory=HeadLimits)
    pan_inverted: bool = False
    tilt_inverted: bool = False
    default_speed_ms: int = 300
    easing: str = 'ease_in_out'

    def __post_init__(self):
        """Validate configuration."""
        if not (0 <= self.pan_channel <= 15):
            raise ValueError(f"pan_channel must be 0-15, got {self.pan_channel}")
        if not (0 <= self.tilt_channel <= 15):
            raise ValueError(f"tilt_channel must be 0-15, got {self.tilt_channel}")
        if self.pan_channel == self.tilt_channel:
            raise ValueError(f"pan_channel and tilt_channel must differ, both are {self.pan_channel}")
        if self.default_speed_ms <= 0:
            raise ValueError(f"default_speed_ms must be > 0, got {self.default_speed_ms}")
        # Note: easing validation happens at runtime when used


@dataclass
class HeadState:
    """Current state of the head position.

    Immutable snapshot of head state for reading current position.

    Attributes:
        pan: Current pan angle in degrees
        tilt: Current tilt angle in degrees
        is_moving: True if head is currently in motion
        target_pan: Target pan angle (if moving)
        target_tilt: Target tilt angle (if moving)
        movement_type: Current movement type (if moving)
    """
    pan: float
    tilt: float
    is_moving: bool = False
    target_pan: Optional[float] = None
    target_tilt: Optional[float] = None
    movement_type: Optional[HeadMovementType] = None
```

### 3.2 HeadController Class Interface

```python
class HeadController:
    """2-DOF pan/tilt head controller with expressive movements.

    Provides smooth, animation-quality head movements with:
    - Direct positioning (look_at)
    - Expressive gestures (nod, shake, glance, tilt)
    - Emergency stop capability
    - Thread-safe operation

    Disney Animation Principles Applied:
    - Anticipation: Slight opposite movement before major motion
    - Follow-through: Natural settling at end of motion
    - Timing: Easing functions for natural acceleration/deceleration
    - Secondary Action: Micro-movements for liveliness

    Thread Safety:
        All public methods are thread-safe. Uses internal lock to protect
        servo commands and state updates.

    Example:
        >>> from src.drivers.servo.pca9685 import PCA9685Driver
        >>> driver = PCA9685Driver()
        >>> config = HeadConfig(pan_channel=12, tilt_channel=13)
        >>> head = HeadController(driver, config)
        >>> head.look_at(pan=30, tilt=15, duration_ms=500)
        >>> head.nod(count=2, amplitude=15, speed_ms=200)
        >>> position = head.get_current_position()
        >>> print(f"Pan: {position[0]}, Tilt: {position[1]}")

    Attributes:
        driver: PCA9685Driver instance for servo control
        config: HeadConfig with channel mappings and limits
        state: Current HeadState (read via get_state())
    """

    def __init__(
        self,
        servo_driver: 'PCA9685Driver',
        config: HeadConfig
    ) -> None:
        """Initialize HeadController.

        Args:
            servo_driver: Configured PCA9685Driver instance
            config: HeadConfig with channel mappings and limits

        Raises:
            ValueError: If config is invalid
            RuntimeError: If servo driver communication fails
        """
        ...

    def look_at(
        self,
        pan: float,
        tilt: float,
        duration_ms: Optional[int] = None,
        easing: Optional[str] = None,
        blocking: bool = False
    ) -> bool:
        """Move head to specified pan/tilt position.

        Smoothly interpolates from current position to target using
        the specified easing function.

        Args:
            pan: Target pan angle in degrees (clamped to limits)
            tilt: Target tilt angle in degrees (clamped to limits)
            duration_ms: Movement duration (None = use config default)
            easing: Easing function name (None = use config default)
            blocking: If True, wait for movement to complete

        Returns:
            True if movement initiated successfully

        Note:
            Values outside limits are clamped, not rejected.
            Use get_state() to check actual target after clamping.
        """
        ...

    def nod(
        self,
        count: int = 2,
        amplitude: float = 15.0,
        speed_ms: int = 200,
        blocking: bool = False
    ) -> bool:
        """Perform nodding gesture (vertical yes motion).

        Creates a natural nodding motion with:
        - Slight anticipation (up) before first nod down
        - Smooth sine-wave motion
        - Gradual amplitude decay for natural feel

        Args:
            count: Number of nod cycles (1-5, clamped)
            amplitude: Peak tilt angle change in degrees (clamped to limits)
            speed_ms: Duration of one nod cycle in milliseconds
            blocking: If True, wait for animation to complete

        Returns:
            True if nod animation started

        Raises:
            ValueError: If currently in emergency stop state
        """
        ...

    def shake(
        self,
        count: int = 2,
        amplitude: float = 20.0,
        speed_ms: int = 200,
        blocking: bool = False
    ) -> bool:
        """Perform head shake gesture (horizontal no motion).

        Creates a natural head shake with:
        - Slight anticipation before first shake
        - Smooth sine-wave pan motion
        - Gradual amplitude decay for natural feel

        Args:
            count: Number of shake cycles (1-5, clamped)
            amplitude: Peak pan angle change in degrees (clamped to limits)
            speed_ms: Duration of one shake cycle in milliseconds
            blocking: If True, wait for animation to complete

        Returns:
            True if shake animation started
        """
        ...

    def random_glance(
        self,
        max_deviation: float = 30.0,
        hold_ms: int = 500,
        blocking: bool = False
    ) -> bool:
        """Perform quick random glance and return.

        Simulates curious/alert behavior:
        1. Quick movement to random offset
        2. Brief hold (as if observing)
        3. Smooth return to original position

        Args:
            max_deviation: Maximum angle offset from current position
            hold_ms: Duration to hold at glance position
            blocking: If True, wait for complete glance cycle

        Returns:
            True if glance started
        """
        ...

    def tilt_curious(
        self,
        direction: str = 'right',
        angle: float = 20.0,
        duration_ms: int = 400,
        blocking: bool = False
    ) -> bool:
        """Tilt head curiously to one side.

        Disney-style curious pose with combined pan and tilt
        for expressive questioning look.

        Args:
            direction: 'left' or 'right'
            angle: Tilt angle in degrees
            duration_ms: Movement duration
            blocking: If True, wait for movement to complete

        Returns:
            True if tilt started

        Raises:
            ValueError: If direction is not 'left' or 'right'
        """
        ...

    def reset_to_center(
        self,
        duration_ms: Optional[int] = None,
        blocking: bool = False
    ) -> bool:
        """Return head to center/home position.

        Args:
            duration_ms: Movement duration (None = use default)
            blocking: If True, wait for movement to complete

        Returns:
            True if reset initiated
        """
        ...

    def emergency_stop(self) -> None:
        """Immediately stop all head movement.

        SAFETY CRITICAL: This method:
        1. Cancels any active animation
        2. Disables both servo channels immediately
        3. Sets internal emergency stop flag

        Call reset_emergency() before resuming normal operation.

        Thread Safety: Can be called from any thread at any time.
        """
        ...

    def reset_emergency(self) -> bool:
        """Clear emergency stop state and re-enable servos.

        Must be called explicitly after emergency_stop() before
        any movement commands will be accepted.

        Returns:
            True if emergency state cleared successfully
        """
        ...

    def get_current_position(self) -> Tuple[float, float]:
        """Get current head position as (pan, tilt) tuple.

        Returns:
            Tuple of (pan_angle, tilt_angle) in degrees

        Note:
            If head is moving, returns last commanded position,
            not necessarily actual physical position.
        """
        ...

    def get_state(self) -> HeadState:
        """Get complete current head state.

        Returns:
            HeadState snapshot with all current values
        """
        ...

    def is_moving(self) -> bool:
        """Check if head is currently in motion.

        Returns:
            True if any movement animation is active
        """
        ...

    def wait_for_completion(self, timeout_ms: Optional[int] = None) -> bool:
        """Block until current movement completes.

        Args:
            timeout_ms: Maximum wait time (None = wait indefinitely)

        Returns:
            True if movement completed, False if timeout
        """
        ...

    def set_on_movement_complete(
        self,
        callback: Optional[Callable[[HeadMovementType], None]]
    ) -> None:
        """Set callback for movement completion events.

        Args:
            callback: Function called with movement type when motion ends.
                     Pass None to clear callback.
        """
        ...
```

### 3.3 Internal Implementation Notes

**Movement Animation Loop:**
- Use `time.monotonic()` for timing (matches AnimationPlayer)
- 50Hz update rate (20ms per frame)
- Pre-compute movement trajectory at start
- Apply easing via `ease()` function from `animation.easing`

**Servo Angle Conversion:**
- Config angles are logical (-90 to +90 for pan)
- Convert to servo angles (0-180) accounting for inversion
- Use formula: `servo_angle = center_servo + (logical_angle * direction)`

**Thread Safety:**
- Single `threading.RLock` for all state modifications
- Emergency stop uses atomic flag (can be checked without lock)

---

## 4. Color Utilities Interface

### 4.1 Type Definitions

```python
# File: firmware/src/led/color_utils.py

from typing import Tuple, Optional
from dataclasses import dataclass

# Type aliases for clarity
RGB = Tuple[int, int, int]      # (0-255, 0-255, 0-255)
HSV = Tuple[float, float, float]  # (0-360, 0-1, 0-1)
```

### 4.2 Conversion Functions

```python
def rgb_to_hsv(rgb: RGB) -> HSV:
    """Convert RGB color to HSV color space.

    Args:
        rgb: RGB tuple (0-255 per channel)

    Returns:
        HSV tuple (hue: 0-360, saturation: 0-1, value: 0-1)

    Raises:
        ValueError: If RGB values outside 0-255 range

    Example:
        >>> rgb_to_hsv((255, 0, 0))  # Pure red
        (0.0, 1.0, 1.0)
        >>> rgb_to_hsv((128, 128, 128))  # Gray
        (0.0, 0.0, 0.502)
    """
    ...


def hsv_to_rgb(h: float, s: float, v: float) -> RGB:
    """Convert HSV color to RGB color space.

    Args:
        h: Hue (0-360 degrees, wraps around)
        s: Saturation (0-1, clamped)
        v: Value/brightness (0-1, clamped)

    Returns:
        RGB tuple (0-255 per channel)

    Example:
        >>> hsv_to_rgb(0, 1.0, 1.0)  # Pure red
        (255, 0, 0)
        >>> hsv_to_rgb(120, 1.0, 1.0)  # Pure green
        (0, 255, 0)
    """
    ...
```

### 4.3 Interpolation Functions

```python
def color_interpolate(
    start: RGB,
    end: RGB,
    t: float
) -> RGB:
    """Linear RGB interpolation between two colors.

    Direct RGB interpolation - fast but can produce muddy
    colors when interpolating across hue boundaries.

    Args:
        start: Starting RGB color
        end: Ending RGB color
        t: Interpolation factor (0.0 = start, 1.0 = end, clamped)

    Returns:
        Interpolated RGB color

    Example:
        >>> color_interpolate((255, 0, 0), (0, 0, 255), 0.5)
        (127, 0, 127)  # Purple (direct path through RGB space)
    """
    ...


def color_arc_interpolate(
    start: RGB,
    end: RGB,
    t: float,
    direction: str = 'short'
) -> RGB:
    """HSV-based color interpolation following hue wheel.

    Interpolates through HSV space for more natural color transitions
    that follow the rainbow/hue wheel.

    Args:
        start: Starting RGB color
        end: Ending RGB color
        t: Interpolation factor (0.0 = start, 1.0 = end, clamped)
        direction: 'short' for shortest arc, 'long' for longest arc,
                  'cw' for clockwise, 'ccw' for counter-clockwise

    Returns:
        Interpolated RGB color

    Example:
        >>> color_arc_interpolate((255, 0, 0), (0, 0, 255), 0.5)
        (0, 255, 0)  # Green (via hue wheel, not purple)

    Note:
        For grayscale colors (s=0), falls back to RGB interpolation
        since hue is undefined.
    """
    ...
```

### 4.4 ColorTransition Class

```python
@dataclass
class ColorTransitionConfig:
    """Configuration for color transition animation.

    Attributes:
        duration_ms: Total transition duration in milliseconds
        easing: Easing function name
        use_hsv: If True, use HSV arc interpolation
        hsv_direction: Direction for HSV interpolation
    """
    duration_ms: int = 500
    easing: str = 'ease_in_out'
    use_hsv: bool = True
    hsv_direction: str = 'short'

    def __post_init__(self):
        if self.duration_ms <= 0:
            raise ValueError(f"duration_ms must be > 0, got {self.duration_ms}")


class ColorTransition:
    """Animated transition between two colors.

    Handles smooth color interpolation with:
    - Configurable duration
    - Easing functions
    - HSV or RGB interpolation modes
    - Real-time elapsed time tracking

    Thread Safety:
        Not thread-safe. Use external synchronization if needed.

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
    """

    def __init__(
        self,
        start: RGB,
        end: RGB,
        config: Optional[ColorTransitionConfig] = None
    ) -> None:
        """Initialize color transition.

        Args:
            start: Starting RGB color
            end: Ending RGB color
            config: Transition configuration (uses defaults if None)
        """
        ...

    def start(self) -> None:
        """Start the transition timer.

        Resets elapsed time to zero and begins tracking.
        """
        ...

    def get_color(self, elapsed_ms: Optional[int] = None) -> RGB:
        """Get interpolated color at current or specified time.

        Args:
            elapsed_ms: Override elapsed time (None = use actual elapsed)

        Returns:
            Interpolated RGB color for current time

        Note:
            If elapsed_ms exceeds duration, returns end color.
            If called before start(), returns start color.
        """
        ...

    def get_progress(self) -> float:
        """Get normalized progress (0.0 to 1.0).

        Returns:
            Progress through transition (clamped to 1.0 at end)
        """
        ...

    def is_complete(self) -> bool:
        """Check if transition has completed.

        Returns:
            True if elapsed time >= duration
        """
        ...

    def reset(self) -> None:
        """Reset transition to beginning."""
        ...

    def reverse(self) -> None:
        """Reverse transition direction (swap start/end)."""
        ...
```

### 4.5 Pre-computed LUT (Performance Optimization)

```python
# Module-level pre-computed lookup tables for O(1) HSV conversion
# Follows pattern from easing.py

_HSV_TO_RGB_LUT: Optional[List[RGB]] = None  # 360 entries for each hue degree
_HSV_LUT_INITIALIZED: bool = False
_HSV_LUT_LOCK: threading.Lock = threading.Lock()

def _init_hsv_lut() -> None:
    """Initialize HSV lookup table (called once on first use).

    Pre-computes RGB values for hue 0-359 at full saturation/value.
    Actual colors are then scaled by saturation and value.
    """
    ...
```

---

## 5. Integration Points

### 5.1 HeadController Integration

#### With PCA9685Driver
```python
# HeadController uses existing driver interface
from src.drivers.servo.pca9685 import PCA9685Driver

# No modifications to PCA9685Driver needed
# HeadController calls:
#   driver.set_servo_angle(channel, angle)
#   driver.disable_channel(channel)
#   driver.get_channel_state(channel)
```

#### With AnimationSequence (Future)
```python
# HeadController can be driven by AnimationSequence keyframes
# Add 'head_pan' and 'head_tilt' to Keyframe metadata

# Example in Keyframe:
kf = Keyframe(
    time_ms=500,
    color=(255, 200, 100),
    metadata={'head_pan': 30.0, 'head_tilt': 15.0}
)
```

#### With EmotionManager
```python
# Emotion callbacks can trigger head movements
emotions.on_enter_callback = lambda e: head.react_to_emotion(e)

# HeadController.react_to_emotion() maps emotions to head poses
# HAPPY -> slight upward tilt
# CURIOUS -> side tilt
# SAD -> downward, slow
# etc.
```

### 5.2 Color Utilities Integration

#### With PatternBase
```python
# Replace _blend_colors in PatternBase with color_utils functions
# Current: Linear RGB interpolation only
# New: Option for HSV arc interpolation

from src.led.color_utils import color_interpolate, color_arc_interpolate

# In PatternBase subclasses:
blended = color_arc_interpolate(color1, color2, t)
```

#### With AnimationSequence
```python
# AnimationSequence._interpolate_color can be enhanced
# Currently: Linear RGB
# Optional: HSV arc for rainbow transitions

# No interface change needed - internal implementation detail
```

### 5.3 Configuration Integration

Add to `robot_config.yaml`:
```yaml
# =================================================================
# HEAD CONTROLLER (Day 11)
# =================================================================
head:
  enabled: true
  pan_channel: 12      # PCA9685 channel for pan servo
  tilt_channel: 13     # PCA9685 channel for tilt servo

  limits:
    pan_min: -90
    pan_max: 90
    tilt_min: -45
    tilt_max: 45
    pan_center: 0
    tilt_center: 0

  servo_config:
    pan_inverted: false
    tilt_inverted: false

  animation:
    default_speed_ms: 300
    easing: 'ease_in_out'
    nod_amplitude: 15
    shake_amplitude: 20
```

---

## 6. File Locations

### 6.1 New Files (Day 11)

```
firmware/
  src/
    control/
      __init__.py          # Update exports
      head_controller.py   # NEW: HeadController, HeadConfig, HeadState
    led/
      color_utils.py       # NEW: RGB/HSV conversion, ColorTransition
  tests/
    control/
      test_head_controller.py  # NEW: HeadController tests
    led/
      test_color_utils.py      # NEW: Color utility tests
```

### 6.2 Existing Files to Update

| File | Update Required |
|------|-----------------|
| `firmware/src/control/__init__.py` | Add HeadController exports |
| `firmware/src/led/__init__.py` | Add color_utils exports |
| `firmware/config/robot_config.yaml` | Add head configuration section |

### 6.3 Import Patterns

```python
# HeadController imports
from src.control.head_controller import (
    HeadController,
    HeadConfig,
    HeadState,
    HeadLimits,
    HeadMovementType,
)

# Color utilities imports
from src.led.color_utils import (
    RGB,
    HSV,
    rgb_to_hsv,
    hsv_to_rgb,
    color_interpolate,
    color_arc_interpolate,
    ColorTransition,
    ColorTransitionConfig,
)
```

---

## 7. Coding Standards

### 7.1 Style Requirements

| Aspect | Requirement |
|--------|-------------|
| **Type Hints** | All public methods fully typed |
| **Docstrings** | Google-style, with Args/Returns/Raises/Example |
| **Line Length** | 100 characters max |
| **Imports** | stdlib, then third-party, then local (src.) |
| **Constants** | UPPER_SNAKE_CASE |
| **Classes** | PascalCase |
| **Methods** | snake_case |

### 7.2 Documentation Templates

**Class Docstring:**
```python
class ClassName:
    """Brief one-line description.

    Detailed explanation of purpose and behavior.

    Disney Animation Principles Applied:
    - Principle: How it's applied

    Thread Safety:
        Description of thread safety guarantees.

    Example:
        >>> code example

    Attributes:
        attr1: Description
        attr2: Description
    """
```

**Method Docstring:**
```python
def method_name(self, arg1: Type1, arg2: Type2) -> ReturnType:
    """Brief one-line description.

    Detailed explanation if needed.

    Args:
        arg1: Description of arg1
        arg2: Description of arg2

    Returns:
        Description of return value

    Raises:
        ErrorType: When this error occurs

    Note:
        Any important notes or caveats
    """
```

### 7.3 Safety Patterns

**Input Validation:**
```python
# Clamp to limits (don't crash on out-of-range)
pan = max(self.config.limits.pan_min, min(self.config.limits.pan_max, pan))

# Validate required constraints (crash if violated)
if not isinstance(config, HeadConfig):
    raise TypeError(f"Expected HeadConfig, got {type(config).__name__}")
```

**Thread Safety:**
```python
# Use RLock for methods that might call other methods
self._lock = threading.RLock()

# Atomic flag for emergency stop
self._emergency_stopped = threading.Event()

# Lock pattern
with self._lock:
    # Critical section
    pass
```

---

## 8. Test Requirements

### 8.1 HeadController Tests

| Test Category | Tests |
|---------------|-------|
| **Initialization** | Valid config, invalid config, channel validation |
| **look_at** | Basic movement, limit clamping, duration override |
| **nod** | Single nod, multiple nods, amplitude validation |
| **shake** | Single shake, multiple shakes, amplitude validation |
| **random_glance** | Movement generation, return to original |
| **tilt_curious** | Left tilt, right tilt, invalid direction |
| **reset_to_center** | Returns to center, respects duration |
| **emergency_stop** | Immediate stop, requires reset |
| **Thread Safety** | Concurrent calls, emergency during movement |

**Minimum Test Count:** 25 tests
**Coverage Target:** 90%

### 8.2 Color Utilities Tests

| Test Category | Tests |
|---------------|-------|
| **rgb_to_hsv** | Primary colors, grayscale, edge cases |
| **hsv_to_rgb** | Full spectrum, saturation/value variations |
| **Roundtrip** | RGB -> HSV -> RGB consistency |
| **color_interpolate** | Boundary values, midpoints |
| **color_arc_interpolate** | All directions, grayscale fallback |
| **ColorTransition** | Basic use, completion detection, reset |

**Minimum Test Count:** 20 tests
**Coverage Target:** 95%

### 8.3 Performance Tests

```python
def test_hsv_conversion_performance():
    """HSV conversion must complete in <1ms for 256 colors."""
    start = time.monotonic()
    for i in range(256):
        rgb_to_hsv((i, 255-i, 128))
    elapsed_ms = (time.monotonic() - start) * 1000
    assert elapsed_ms < 1.0

def test_head_movement_latency():
    """Head movement must initiate within 5ms of call."""
    # Measure time from look_at() call to first servo update
    ...
```

---

## Appendix A: Servo Angle Mapping Reference

```
Logical Angle (degrees)    Servo Angle (degrees)
-----------------------    ---------------------
Pan:
  -90 (full left)    ->    0   (servo min)
    0 (center)       ->    90  (servo center)
  +90 (full right)   ->    180 (servo max)

Tilt:
  -45 (full down)    ->    45  (90 - 45)
    0 (center)       ->    90  (servo center)
  +45 (full up)      ->    135 (90 + 45)

Formula:
  servo_angle = 90 + (logical_angle * (1 if not inverted else -1))
```

---

## Appendix B: HSV Color Space Reference

```
Hue (degrees):
  0   = Red
  60  = Yellow
  120 = Green
  180 = Cyan
  240 = Blue
  300 = Magenta
  360 = Red (wraps)

Saturation (0-1):
  0 = Grayscale (white/gray/black based on value)
  1 = Full color

Value (0-1):
  0 = Black (regardless of hue/saturation)
  1 = Full brightness
```

---

**End of Architecture Specification**

*This document defines contracts only. Implementation is delegated to specialized agents.*

---

**Document Control:**
- Version 1.0: Initial specification (18 Jan 2026)
- Review Required: Before implementation begins
- Approval: Chief Orchestrator (Agent 0)
