# Animation & Controls System - Technical Implementation Plan
## OpenDuck Mini V3 | Week 02 | Senior Controls Engineer Analysis

**Author:** Senior Controls Systems Engineer (Boston Dynamics Atlas Team)
**Date:** 17 January 2026
**Status:** READY FOR IMPLEMENTATION

---

## Executive Summary

This document provides a comprehensive technical plan for implementing the animation timing and servo coordination system for the OpenDuck Mini V3 robot. The plan prioritizes **mock-testable software development** while hardware arrives, ensuring instant activation when servos become available.

### Key Constraints
| Item | Status | Expected |
|------|--------|----------|
| BNO085 IMU | Arriving | Monday (Day 8) |
| MG90S Servos | In hand | Testing blocked by batteries |
| Batteries | Ordered | Mid-Week 2 (~Day 10-11) |
| AI Camera | Not arrived | Week 3 |

### Strategy: Software-First with Hardware Abstraction
All timing, interpolation, and coordination logic will be developed and tested WITHOUT hardware, using dependency injection and mock objects.

---

## System Architecture Overview

```
+------------------------------------------------------------------+
|                    Animation/Controls Stack                       |
+------------------------------------------------------------------+
|  LAYER 4: Behaviors                                               |
|  +------------------+  +------------------+  +-----------------+  |
|  | IdleBehavior     |  | ExpressionPreset |  | ReactiveMotion  |  |
|  +--------+---------+  +--------+---------+  +--------+--------+  |
|           |                     |                     |           |
+------------------------------------------------------------------+
|  LAYER 3: Coordination                                            |
|  +------------------+  +------------------+  +-----------------+  |
|  | HeadController   |  | EmotionCoord     |  | MotionPlanner   |  |
|  +--------+---------+  +--------+---------+  +--------+--------+  |
|           |                     |                     |           |
+------------------------------------------------------------------+
|  LAYER 2: Animation Engine                                        |
|  +------------------+  +------------------+  +-----------------+  |
|  | AnimationPlayer  |  | KeyframeInterp   |  | EasingLibrary   |  |
|  +--------+---------+  +--------+---------+  +--------+--------+  |
|           |                     |                     |           |
+------------------------------------------------------------------+
|  LAYER 1: Hardware Abstraction                                    |
|  +------------------+  +------------------+  +-----------------+  |
|  | ServoChannel     |  | LEDStrip         |  | TimeSource      |  |
|  +--------+---------+  +--------+---------+  +--------+--------+  |
|           |                     |                     |           |
+------------------------------------------------------------------+
|  LAYER 0: Physical Hardware (Mock for Testing)                    |
|  +------------------+  +------------------+  +-----------------+  |
|  | PCA9685Driver    |  | WS2812BDriver    |  | time.monotonic  |  |
|  +------------------+  +------------------+  +-----------------+  |
+------------------------------------------------------------------+
```

---

## Part 1: Keyframe Interpolation System

### 1.1 Requirements

| Requirement | Target | Rationale |
|-------------|--------|-----------|
| Timing accuracy | <1ms jitter | Smooth animation at 50Hz |
| Interpolation rate | 50Hz minimum | Matches control loop |
| Multi-channel sync | <0.5ms skew | Head pan/tilt must move together |
| Memory footprint | <1KB per animation | Limited Pi RAM |

### 1.2 Core Data Structures

```python
# firmware/src/animation/keyframe.py

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable
from enum import Enum
import time

class EasingType(Enum):
    """Supported easing functions (Disney 12 principles compliance)"""
    LINEAR = "linear"
    EASE_IN = "ease_in"           # Slow start (anticipation)
    EASE_OUT = "ease_out"         # Slow end (follow-through)
    EASE_IN_OUT = "ease_in_out"   # Slow start and end (natural motion)
    EASE_OUT_BACK = "ease_out_back"  # Overshoot then settle
    BOUNCE = "bounce"             # Squash and stretch
    ANTICIPATE = "anticipate"     # Pull back before motion


@dataclass(frozen=True)
class Keyframe:
    """Immutable keyframe definition.

    Attributes:
        time_ms: Time offset from animation start in milliseconds
        positions: Dict mapping channel names to target positions (0-180 degrees)
        easing: Easing function to use for interpolation TO this keyframe

    Invariants:
        - time_ms >= 0
        - All positions in range [0, 180]
        - Keyframes are immutable (frozen=True)
    """
    time_ms: int
    positions: Dict[str, float]
    easing: EasingType = EasingType.EASE_IN_OUT

    def __post_init__(self):
        if self.time_ms < 0:
            raise ValueError(f"time_ms must be >= 0, got {self.time_ms}")
        for name, pos in self.positions.items():
            if not 0 <= pos <= 180:
                raise ValueError(f"Position for {name} must be 0-180, got {pos}")


@dataclass
class AnimationSequence:
    """A complete animation sequence with multiple keyframes.

    Thread Safety: NOT thread-safe. Use AnimationPlayer for concurrent access.
    """
    name: str
    keyframes: List[Keyframe] = field(default_factory=list)
    loop: bool = False
    _sorted: bool = field(default=False, repr=False)

    def add_keyframe(self, time_ms: int, positions: Dict[str, float],
                     easing: EasingType = EasingType.EASE_IN_OUT) -> None:
        """Add a keyframe to the sequence."""
        self.keyframes.append(Keyframe(time_ms, positions.copy(), easing))
        self._sorted = False

    def _ensure_sorted(self) -> None:
        """Sort keyframes by time (lazy evaluation)."""
        if not self._sorted:
            self.keyframes.sort(key=lambda k: k.time_ms)
            self._sorted = True

    @property
    def duration_ms(self) -> int:
        """Total duration of animation."""
        if not self.keyframes:
            return 0
        self._ensure_sorted()
        return self.keyframes[-1].time_ms

    @property
    def channels(self) -> set:
        """Set of all channel names used in animation."""
        result = set()
        for kf in self.keyframes:
            result.update(kf.positions.keys())
        return result
```

### 1.3 Interpolation Engine

```python
# firmware/src/animation/interpolator.py

from typing import Dict, Optional, Tuple
import math

class KeyframeInterpolator:
    """High-precision keyframe interpolation engine.

    Design Goals:
        1. Sub-millisecond timing accuracy using monotonic clock
        2. O(log n) keyframe lookup via binary search
        3. Pre-computed easing lookup tables for O(1) evaluation
        4. Zero allocations in hot path (get_positions)

    Thread Safety: NOT thread-safe. Caller must synchronize.
    """

    # Pre-computed lookup table size (101 entries for 0-100%)
    _LUT_SIZE = 101

    def __init__(self, sequence: AnimationSequence,
                 time_source: Optional[Callable[[], float]] = None):
        """Initialize interpolator.

        Args:
            sequence: Animation to interpolate
            time_source: Callable returning current time in seconds.
                         Defaults to time.monotonic for deterministic timing.
        """
        self._sequence = sequence
        self._time_source = time_source or time.monotonic
        self._start_time: Optional[float] = None
        self._paused_at: Optional[float] = None

        # Pre-compute easing lookup tables
        self._easing_luts: Dict[EasingType, List[float]] = {}
        for easing in EasingType:
            self._easing_luts[easing] = self._build_lut(easing)

        # Pre-allocate output buffer (reused to avoid allocations)
        self._output_buffer: Dict[str, float] = {}

    def _build_lut(self, easing: EasingType) -> List[float]:
        """Build lookup table for easing function."""
        lut = []
        for i in range(self._LUT_SIZE):
            t = i / (self._LUT_SIZE - 1)
            lut.append(self._compute_easing(t, easing))
        return lut

    def _compute_easing(self, t: float, easing: EasingType) -> float:
        """Compute easing value (used only for LUT generation)."""
        if easing == EasingType.LINEAR:
            return t
        elif easing == EasingType.EASE_IN:
            return t * t
        elif easing == EasingType.EASE_OUT:
            return 1 - (1 - t) ** 2
        elif easing == EasingType.EASE_IN_OUT:
            if t < 0.5:
                return 2 * t * t
            return 1 - (-2 * t + 2) ** 2 / 2
        elif easing == EasingType.EASE_OUT_BACK:
            c1 = 1.70158
            c3 = c1 + 1
            return 1 + c3 * pow(t - 1, 3) + c1 * pow(t - 1, 2)
        elif easing == EasingType.BOUNCE:
            return self._bounce_ease(t)
        elif easing == EasingType.ANTICIPATE:
            return t * t * ((2.70158 + 1) * t - 2.70158)
        return t  # Fallback to linear

    def _bounce_ease(self, t: float) -> float:
        """Bounce easing (Disney squash & stretch)."""
        n1 = 7.5625
        d1 = 2.75
        if t < 1 / d1:
            return n1 * t * t
        elif t < 2 / d1:
            t -= 1.5 / d1
            return n1 * t * t + 0.75
        elif t < 2.5 / d1:
            t -= 2.25 / d1
            return n1 * t * t + 0.9375
        else:
            t -= 2.625 / d1
            return n1 * t * t + 0.984375

    def _fast_ease(self, t: float, easing: EasingType) -> float:
        """O(1) easing via lookup table interpolation."""
        t = max(0.0, min(1.0, t))  # Clamp to [0, 1]
        lut = self._easing_luts[easing]

        # Linear interpolation between LUT entries
        index_f = t * (self._LUT_SIZE - 1)
        index_low = int(index_f)
        index_high = min(index_low + 1, self._LUT_SIZE - 1)
        frac = index_f - index_low

        return lut[index_low] + (lut[index_high] - lut[index_low]) * frac

    def start(self) -> None:
        """Start or restart animation from beginning."""
        self._start_time = self._time_source()
        self._paused_at = None

    def pause(self) -> None:
        """Pause animation at current position."""
        if self._start_time is not None and self._paused_at is None:
            self._paused_at = self._time_source()

    def resume(self) -> None:
        """Resume paused animation."""
        if self._paused_at is not None and self._start_time is not None:
            pause_duration = self._time_source() - self._paused_at
            self._start_time += pause_duration
            self._paused_at = None

    @property
    def is_playing(self) -> bool:
        """Check if animation is currently playing."""
        return self._start_time is not None and self._paused_at is None

    @property
    def is_finished(self) -> bool:
        """Check if non-looping animation has completed."""
        if self._sequence.loop:
            return False
        elapsed = self._get_elapsed_ms()
        return elapsed >= self._sequence.duration_ms

    def _get_elapsed_ms(self) -> int:
        """Get elapsed time in milliseconds since start."""
        if self._start_time is None:
            return 0

        if self._paused_at is not None:
            current = self._paused_at
        else:
            current = self._time_source()

        elapsed_s = current - self._start_time
        return int(elapsed_s * 1000)

    def get_positions(self) -> Dict[str, float]:
        """Get interpolated positions for current time.

        Returns:
            Dict mapping channel names to current positions (0-180 degrees).
            Returns empty dict if no keyframes or animation not started.

        Performance:
            - O(log n) keyframe lookup
            - O(1) easing computation via LUT
            - Zero allocations (reuses output buffer)
        """
        if not self._sequence.keyframes or self._start_time is None:
            return {}

        self._sequence._ensure_sorted()
        keyframes = self._sequence.keyframes

        elapsed_ms = self._get_elapsed_ms()

        # Handle looping
        if self._sequence.loop and self._sequence.duration_ms > 0:
            elapsed_ms = elapsed_ms % self._sequence.duration_ms

        # Binary search for surrounding keyframes
        kf_before, kf_after = self._find_surrounding_keyframes(elapsed_ms)

        if kf_before is None:
            # Before first keyframe - use first keyframe positions
            self._output_buffer.clear()
            self._output_buffer.update(keyframes[0].positions)
            return self._output_buffer

        if kf_after is None:
            # After last keyframe - use last keyframe positions
            self._output_buffer.clear()
            self._output_buffer.update(keyframes[-1].positions)
            return self._output_buffer

        # Interpolate between keyframes
        return self._interpolate(kf_before, kf_after, elapsed_ms)

    def _find_surrounding_keyframes(self, time_ms: int) -> Tuple[Optional[Keyframe], Optional[Keyframe]]:
        """Find keyframes before and after given time using binary search."""
        keyframes = self._sequence.keyframes

        # Binary search
        left, right = 0, len(keyframes) - 1

        while left <= right:
            mid = (left + right) // 2
            if keyframes[mid].time_ms <= time_ms:
                left = mid + 1
            else:
                right = mid - 1

        # right now points to the last keyframe <= time_ms
        if right < 0:
            return None, keyframes[0] if keyframes else None
        if right >= len(keyframes) - 1:
            return keyframes[-1], None

        return keyframes[right], keyframes[right + 1]

    def _interpolate(self, kf_before: Keyframe, kf_after: Keyframe,
                     time_ms: int) -> Dict[str, float]:
        """Interpolate between two keyframes."""
        self._output_buffer.clear()

        # Calculate normalized time [0, 1] between keyframes
        time_range = kf_after.time_ms - kf_before.time_ms
        if time_range <= 0:
            self._output_buffer.update(kf_after.positions)
            return self._output_buffer

        t = (time_ms - kf_before.time_ms) / time_range

        # Apply easing (use after keyframe's easing for transition TO it)
        t_eased = self._fast_ease(t, kf_after.easing)

        # Get all channels from both keyframes
        all_channels = set(kf_before.positions.keys()) | set(kf_after.positions.keys())

        for channel in all_channels:
            pos_before = kf_before.positions.get(channel)
            pos_after = kf_after.positions.get(channel)

            if pos_before is None:
                pos_before = pos_after
            if pos_after is None:
                pos_after = pos_before

            # Linear interpolation with eased time
            self._output_buffer[channel] = pos_before + (pos_after - pos_before) * t_eased

        return self._output_buffer
```

### 1.4 Test Cases (TDD)

```python
# firmware/tests/test_animation/test_keyframe.py

import pytest
from unittest.mock import MagicMock
from src.animation.keyframe import Keyframe, AnimationSequence, EasingType
from src.animation.interpolator import KeyframeInterpolator


class TestKeyframe:
    """Keyframe data structure tests."""

    def test_creation_valid(self):
        kf = Keyframe(time_ms=0, positions={'pan': 90})
        assert kf.time_ms == 0
        assert kf.positions['pan'] == 90

    def test_creation_negative_time_raises(self):
        with pytest.raises(ValueError, match="time_ms must be >= 0"):
            Keyframe(time_ms=-1, positions={'pan': 90})

    def test_creation_position_out_of_range_raises(self):
        with pytest.raises(ValueError, match="must be 0-180"):
            Keyframe(time_ms=0, positions={'pan': 200})

    def test_immutability(self):
        kf = Keyframe(time_ms=0, positions={'pan': 90})
        with pytest.raises(AttributeError):
            kf.time_ms = 100


class TestAnimationSequence:
    """Animation sequence tests."""

    def test_empty_sequence(self):
        seq = AnimationSequence(name="test")
        assert seq.duration_ms == 0
        assert len(seq.channels) == 0

    def test_add_keyframe(self):
        seq = AnimationSequence(name="test")
        seq.add_keyframe(0, {'pan': 0})
        seq.add_keyframe(1000, {'pan': 90})
        assert seq.duration_ms == 1000
        assert len(seq.keyframes) == 2

    def test_keyframes_sorted(self):
        seq = AnimationSequence(name="test")
        seq.add_keyframe(1000, {'pan': 90})
        seq.add_keyframe(0, {'pan': 0})  # Out of order
        seq.add_keyframe(500, {'pan': 45})

        seq._ensure_sorted()
        assert [kf.time_ms for kf in seq.keyframes] == [0, 500, 1000]

    def test_channels(self):
        seq = AnimationSequence(name="test")
        seq.add_keyframe(0, {'pan': 0, 'tilt': 90})
        seq.add_keyframe(1000, {'pan': 90})
        assert seq.channels == {'pan', 'tilt'}


class TestKeyframeInterpolator:
    """Interpolation engine tests."""

    @pytest.fixture
    def simple_sequence(self):
        seq = AnimationSequence(name="test")
        seq.add_keyframe(0, {'servo1': 0}, EasingType.LINEAR)
        seq.add_keyframe(1000, {'servo1': 100}, EasingType.LINEAR)
        return seq

    @pytest.fixture
    def mock_time_source(self):
        current_time = [0.0]  # Mutable container
        def time_fn():
            return current_time[0]
        return time_fn, current_time

    def test_linear_interpolation_midpoint(self, simple_sequence, mock_time_source):
        time_fn, current_time = mock_time_source
        interp = KeyframeInterpolator(simple_sequence, time_source=time_fn)

        current_time[0] = 0.0
        interp.start()

        current_time[0] = 0.5  # 500ms elapsed
        positions = interp.get_positions()

        assert abs(positions['servo1'] - 50.0) < 0.1

    def test_linear_interpolation_at_keyframe(self, simple_sequence, mock_time_source):
        time_fn, current_time = mock_time_source
        interp = KeyframeInterpolator(simple_sequence, time_source=time_fn)

        current_time[0] = 0.0
        interp.start()

        current_time[0] = 1.0  # 1000ms elapsed - at second keyframe
        positions = interp.get_positions()

        assert abs(positions['servo1'] - 100.0) < 0.1

    def test_ease_in_slower_at_start(self, mock_time_source):
        seq = AnimationSequence(name="test")
        seq.add_keyframe(0, {'servo1': 0}, EasingType.LINEAR)
        seq.add_keyframe(1000, {'servo1': 100}, EasingType.EASE_IN)

        time_fn, current_time = mock_time_source
        interp = KeyframeInterpolator(seq, time_source=time_fn)

        current_time[0] = 0.0
        interp.start()

        current_time[0] = 0.25  # 25% through
        positions = interp.get_positions()

        # Ease-in should be slower at start, so position < 25
        assert positions['servo1'] < 25.0

    def test_ease_out_faster_at_start(self, mock_time_source):
        seq = AnimationSequence(name="test")
        seq.add_keyframe(0, {'servo1': 0}, EasingType.LINEAR)
        seq.add_keyframe(1000, {'servo1': 100}, EasingType.EASE_OUT)

        time_fn, current_time = mock_time_source
        interp = KeyframeInterpolator(seq, time_source=time_fn)

        current_time[0] = 0.0
        interp.start()

        current_time[0] = 0.25  # 25% through
        positions = interp.get_positions()

        # Ease-out should be faster at start, so position > 25
        assert positions['servo1'] > 25.0

    def test_multi_channel_interpolation(self, mock_time_source):
        seq = AnimationSequence(name="test")
        seq.add_keyframe(0, {'pan': 0, 'tilt': 90})
        seq.add_keyframe(1000, {'pan': 90, 'tilt': 45})

        time_fn, current_time = mock_time_source
        interp = KeyframeInterpolator(seq, time_source=time_fn)

        current_time[0] = 0.0
        interp.start()

        current_time[0] = 0.5  # 50% through
        positions = interp.get_positions()

        assert 'pan' in positions
        assert 'tilt' in positions
        assert abs(positions['pan'] - 45.0) < 1.0
        assert abs(positions['tilt'] - 67.5) < 1.0

    def test_looping_animation(self, simple_sequence, mock_time_source):
        simple_sequence.loop = True

        time_fn, current_time = mock_time_source
        interp = KeyframeInterpolator(simple_sequence, time_source=time_fn)

        current_time[0] = 0.0
        interp.start()

        # At 1500ms (500ms into second loop)
        current_time[0] = 1.5
        positions = interp.get_positions()

        assert abs(positions['servo1'] - 50.0) < 0.1

    def test_pause_resume(self, simple_sequence, mock_time_source):
        time_fn, current_time = mock_time_source
        interp = KeyframeInterpolator(simple_sequence, time_source=time_fn)

        current_time[0] = 0.0
        interp.start()

        current_time[0] = 0.3
        interp.pause()

        # Time passes while paused
        current_time[0] = 1.0
        interp.resume()

        # Should still be at 300ms position
        positions = interp.get_positions()
        assert abs(positions['servo1'] - 30.0) < 1.0

    def test_is_finished_non_looping(self, simple_sequence, mock_time_source):
        time_fn, current_time = mock_time_source
        interp = KeyframeInterpolator(simple_sequence, time_source=time_fn)

        current_time[0] = 0.0
        interp.start()

        current_time[0] = 0.5
        assert not interp.is_finished

        current_time[0] = 1.5
        assert interp.is_finished


class TestEasingFunctions:
    """Easing function correctness tests."""

    @pytest.fixture
    def interpolator(self):
        seq = AnimationSequence(name="dummy")
        seq.add_keyframe(0, {'x': 0})
        return KeyframeInterpolator(seq)

    def test_all_easings_range_0_to_1(self, interpolator):
        for easing in EasingType:
            assert abs(interpolator._fast_ease(0.0, easing)) < 0.01
            assert abs(interpolator._fast_ease(1.0, easing) - 1.0) < 0.01

    def test_ease_in_out_symmetric(self, interpolator):
        """Ease-in-out should be symmetric around 0.5"""
        val_25 = interpolator._fast_ease(0.25, EasingType.EASE_IN_OUT)
        val_75 = interpolator._fast_ease(0.75, EasingType.EASE_IN_OUT)
        assert abs(val_25 + val_75 - 1.0) < 0.02

    def test_ease_out_back_overshoots(self, interpolator):
        """Ease-out-back should overshoot 1.0 briefly"""
        # Find max value in range
        max_val = max(
            interpolator._fast_ease(t / 100, EasingType.EASE_OUT_BACK)
            for t in range(101)
        )
        assert max_val > 1.0


class TestTimingAccuracy:
    """Timing precision tests."""

    def test_sub_millisecond_precision(self):
        """Verify interpolator handles sub-millisecond time differences."""
        seq = AnimationSequence(name="test")
        seq.add_keyframe(0, {'servo': 0})
        seq.add_keyframe(100, {'servo': 100})  # 100ms animation

        times = []
        def precise_time():
            return times[0] if times else 0.0

        interp = KeyframeInterpolator(seq, time_source=precise_time)

        times.append(0.0)
        interp.start()

        # Test at 0.5ms increments
        for ms in [0.0, 0.5, 1.0, 1.5, 2.0]:
            times[0] = ms / 1000.0
            positions = interp.get_positions()
            expected = ms  # Linear easing, so position = time
            assert abs(positions['servo'] - expected) < 0.5
```

---

## Part 2: Easing Functions Library

### 2.1 Full Easing Implementation

```python
# firmware/src/animation/easing.py

"""
Easing Functions Library - Disney 12 Principles Compliance

This module provides mathematically correct easing functions for
natural motion that follows Disney's animation principles:

1. Squash & Stretch -> bounce, elastic
2. Anticipation -> anticipate, ease_in_back
3. Follow Through -> ease_out_back, overshoot
4. Slow In/Slow Out -> ease_in_out family
5. Arc -> Handled by path planning, not easing
6. Secondary Action -> Separate animation layer
7. Timing -> Duration parameter, not easing
8. Exaggeration -> Scale factor on easing

All functions:
- Input: t in [0, 1]
- Output: eased value in [0, 1] (may overshoot for some functions)
"""

import math
from typing import Callable, Dict

# Type alias
EasingFunction = Callable[[float], float]


def linear(t: float) -> float:
    """Linear interpolation (no easing)."""
    return t


def ease_in_quad(t: float) -> float:
    """Quadratic ease-in (slow start)."""
    return t * t


def ease_out_quad(t: float) -> float:
    """Quadratic ease-out (slow end)."""
    return 1 - (1 - t) * (1 - t)


def ease_in_out_quad(t: float) -> float:
    """Quadratic ease-in-out (slow start and end)."""
    if t < 0.5:
        return 2 * t * t
    return 1 - (-2 * t + 2) ** 2 / 2


def ease_in_cubic(t: float) -> float:
    """Cubic ease-in (slower start than quad)."""
    return t * t * t


def ease_out_cubic(t: float) -> float:
    """Cubic ease-out (slower end than quad)."""
    return 1 - (1 - t) ** 3


def ease_in_out_cubic(t: float) -> float:
    """Cubic ease-in-out."""
    if t < 0.5:
        return 4 * t * t * t
    return 1 - (-2 * t + 2) ** 3 / 2


def ease_in_sine(t: float) -> float:
    """Sinusoidal ease-in (very gentle start)."""
    return 1 - math.cos(t * math.pi / 2)


def ease_out_sine(t: float) -> float:
    """Sinusoidal ease-out (very gentle end)."""
    return math.sin(t * math.pi / 2)


def ease_in_out_sine(t: float) -> float:
    """Sinusoidal ease-in-out (very gentle)."""
    return -(math.cos(math.pi * t) - 1) / 2


def ease_in_expo(t: float) -> float:
    """Exponential ease-in (dramatic slow start)."""
    if t == 0:
        return 0
    return 2 ** (10 * t - 10)


def ease_out_expo(t: float) -> float:
    """Exponential ease-out (dramatic slow end)."""
    if t == 1:
        return 1
    return 1 - 2 ** (-10 * t)


def ease_in_out_expo(t: float) -> float:
    """Exponential ease-in-out."""
    if t == 0:
        return 0
    if t == 1:
        return 1
    if t < 0.5:
        return 2 ** (20 * t - 10) / 2
    return (2 - 2 ** (-20 * t + 10)) / 2


def ease_out_back(t: float, overshoot: float = 1.70158) -> float:
    """Ease-out with overshoot (follow-through).

    Args:
        t: Progress [0, 1]
        overshoot: Amount of overshoot (default 1.70158 = ~10%)
    """
    c1 = overshoot
    c3 = c1 + 1
    return 1 + c3 * pow(t - 1, 3) + c1 * pow(t - 1, 2)


def ease_in_back(t: float, overshoot: float = 1.70158) -> float:
    """Ease-in with anticipation (pull back before move).

    Args:
        t: Progress [0, 1]
        overshoot: Amount of pullback (default 1.70158 = ~10%)
    """
    c1 = overshoot
    c3 = c1 + 1
    return c3 * t * t * t - c1 * t * t


def ease_in_out_back(t: float, overshoot: float = 1.70158) -> float:
    """Ease-in-out with anticipation and follow-through."""
    c1 = overshoot
    c2 = c1 * 1.525

    if t < 0.5:
        return (pow(2 * t, 2) * ((c2 + 1) * 2 * t - c2)) / 2
    return (pow(2 * t - 2, 2) * ((c2 + 1) * (t * 2 - 2) + c2) + 2) / 2


def bounce_out(t: float) -> float:
    """Bounce ease-out (squash & stretch at end)."""
    n1 = 7.5625
    d1 = 2.75

    if t < 1 / d1:
        return n1 * t * t
    elif t < 2 / d1:
        t -= 1.5 / d1
        return n1 * t * t + 0.75
    elif t < 2.5 / d1:
        t -= 2.25 / d1
        return n1 * t * t + 0.9375
    else:
        t -= 2.625 / d1
        return n1 * t * t + 0.984375


def bounce_in(t: float) -> float:
    """Bounce ease-in (squash & stretch at start)."""
    return 1 - bounce_out(1 - t)


def bounce_in_out(t: float) -> float:
    """Bounce ease-in-out."""
    if t < 0.5:
        return (1 - bounce_out(1 - 2 * t)) / 2
    return (1 + bounce_out(2 * t - 1)) / 2


def elastic_out(t: float, amplitude: float = 1.0, period: float = 0.3) -> float:
    """Elastic ease-out (spring oscillation at end).

    Args:
        t: Progress [0, 1]
        amplitude: Oscillation amplitude (default 1.0)
        period: Oscillation period (default 0.3)
    """
    if t == 0 or t == 1:
        return t

    s = period / (2 * math.pi) * math.asin(1 / amplitude) if amplitude >= 1 else period / 4
    return amplitude * 2 ** (-10 * t) * math.sin((t - s) * (2 * math.pi) / period) + 1


def elastic_in(t: float, amplitude: float = 1.0, period: float = 0.3) -> float:
    """Elastic ease-in (spring oscillation at start)."""
    return 1 - elastic_out(1 - t, amplitude, period)


# Registry of all easing functions
EASING_REGISTRY: Dict[str, EasingFunction] = {
    'linear': linear,
    'ease_in': ease_in_quad,
    'ease_out': ease_out_quad,
    'ease_in_out': ease_in_out_quad,
    'ease_in_quad': ease_in_quad,
    'ease_out_quad': ease_out_quad,
    'ease_in_out_quad': ease_in_out_quad,
    'ease_in_cubic': ease_in_cubic,
    'ease_out_cubic': ease_out_cubic,
    'ease_in_out_cubic': ease_in_out_cubic,
    'ease_in_sine': ease_in_sine,
    'ease_out_sine': ease_out_sine,
    'ease_in_out_sine': ease_in_out_sine,
    'ease_in_expo': ease_in_expo,
    'ease_out_expo': ease_out_expo,
    'ease_in_out_expo': ease_in_out_expo,
    'ease_in_back': ease_in_back,
    'ease_out_back': ease_out_back,
    'ease_in_out_back': ease_in_out_back,
    'bounce_in': bounce_in,
    'bounce_out': bounce_out,
    'bounce_in_out': bounce_in_out,
    'elastic_in': elastic_in,
    'elastic_out': elastic_out,
}


def get_easing(name: str) -> EasingFunction:
    """Get easing function by name.

    Args:
        name: Easing function name (e.g., 'ease_in_out', 'bounce_out')

    Returns:
        Easing function

    Raises:
        KeyError: If easing name not found
    """
    return EASING_REGISTRY[name]
```

---

## Part 3: Multi-Servo Synchronization

### 3.1 Servo Synchronization Requirements

| Requirement | Target | Measurement |
|-------------|--------|-------------|
| Inter-servo skew | <0.5ms | Oscilloscope timing analysis |
| Command latency | <2ms | time.perf_counter() measurement |
| Batch update rate | 50Hz | Control loop timing |
| Simultaneous channels | Up to 8 | Head + 4 servos typical |

### 3.2 Animation Player (Synchronized Execution)

```python
# firmware/src/animation/player.py

"""
Animation Player - Thread-Safe Animation Execution Engine

Provides synchronized multi-servo animation playback with:
- Atomic multi-channel updates
- Priority-based animation layering
- Smooth blending between animations
- Thread-safe queue management
"""

import threading
import time
from typing import Dict, Optional, List, Callable, Any
from dataclasses import dataclass, field
from enum import IntEnum
from queue import PriorityQueue

from .keyframe import AnimationSequence, EasingType
from .interpolator import KeyframeInterpolator


class AnimationPriority(IntEnum):
    """Animation priority levels (higher = more important)."""
    IDLE = 0          # Background idle animations
    EMOTION = 10      # Emotion-triggered animations
    REACTION = 20     # Reactive animations (head tracking, etc.)
    COMMAND = 30      # Explicit user commands
    SAFETY = 100      # Safety overrides (E-stop, etc.)


@dataclass
class AnimationState:
    """State of a playing animation."""
    sequence: AnimationSequence
    interpolator: KeyframeInterpolator
    priority: AnimationPriority
    blend_factor: float = 1.0  # 0.0 = no contribution, 1.0 = full contribution
    on_complete: Optional[Callable[[], None]] = None


@dataclass(order=True)
class AnimationCommand:
    """Queued animation command (priority queue item)."""
    priority: int
    sequence: AnimationSequence = field(compare=False)
    blend_time_ms: int = field(compare=False, default=200)
    on_complete: Optional[Callable[[], None]] = field(compare=False, default=None)


class AnimationPlayer:
    """Thread-safe animation player with priority-based layering.

    Supports:
    - Multiple simultaneous animations on different channels
    - Priority-based animation interruption
    - Smooth blending between animations
    - Callbacks on animation completion

    Thread Safety:
        All public methods are thread-safe. Uses a single lock for
        state modifications and a separate lock for queue access.

    Example:
        >>> player = AnimationPlayer(servo_driver)
        >>> player.play(wave_animation, priority=AnimationPriority.COMMAND)
        >>> while not player.is_idle:
        ...     player.update()  # Call at 50Hz
        ...     time.sleep(0.02)
    """

    DEFAULT_BLEND_TIME_MS = 200

    def __init__(self, servo_output: Callable[[Dict[str, float]], None],
                 time_source: Optional[Callable[[], float]] = None,
                 led_output: Optional[Callable[[Any], None]] = None):
        """Initialize animation player.

        Args:
            servo_output: Callback to send servo positions. Called with
                         dict mapping channel names to angles (0-180).
            time_source: Time source function. Defaults to time.monotonic.
            led_output: Optional callback for LED state output.
        """
        self._servo_output = servo_output
        self._led_output = led_output
        self._time_source = time_source or time.monotonic

        # Thread safety
        self._state_lock = threading.RLock()
        self._queue_lock = threading.Lock()

        # Animation state
        self._active_animations: Dict[str, AnimationState] = {}
        self._channel_positions: Dict[str, float] = {}  # Current positions
        self._command_queue: PriorityQueue[AnimationCommand] = PriorityQueue()

        # Blending state
        self._blending_out: Dict[str, AnimationState] = {}
        self._blend_start_time: Optional[float] = None
        self._blend_duration_s: float = 0.0

    def play(self, sequence: AnimationSequence,
             priority: AnimationPriority = AnimationPriority.COMMAND,
             blend_time_ms: int = DEFAULT_BLEND_TIME_MS,
             on_complete: Optional[Callable[[], None]] = None) -> None:
        """Queue an animation for playback.

        If a higher-priority animation is playing, this animation waits.
        If a lower-priority animation is playing, it blends out.

        Args:
            sequence: Animation to play
            priority: Animation priority level
            blend_time_ms: Crossfade duration in milliseconds
            on_complete: Callback when animation finishes
        """
        with self._queue_lock:
            cmd = AnimationCommand(
                priority=-int(priority),  # Negate for max-heap behavior
                sequence=sequence,
                blend_time_ms=blend_time_ms,
                on_complete=on_complete,
            )
            self._command_queue.put(cmd)

    def stop(self, channels: Optional[List[str]] = None) -> None:
        """Stop animations on specified channels.

        Args:
            channels: Channel names to stop. If None, stops all.
        """
        with self._state_lock:
            if channels is None:
                self._active_animations.clear()
                self._blending_out.clear()
            else:
                for ch in channels:
                    self._active_animations.pop(ch, None)
                    self._blending_out.pop(ch, None)

    def stop_all(self) -> None:
        """Stop all animations immediately."""
        self.stop(None)

    @property
    def is_idle(self) -> bool:
        """Check if no animations are playing."""
        with self._state_lock:
            return len(self._active_animations) == 0 and self._command_queue.empty()

    def update(self) -> Dict[str, float]:
        """Update animation state and output servo positions.

        Call this method at your control loop rate (typically 50Hz).

        Returns:
            Dict of current channel positions (for debugging/logging).
        """
        with self._state_lock:
            # Process queued commands
            self._process_queue()

            # Update blending
            self._update_blending()

            # Get interpolated positions from all active animations
            output_positions: Dict[str, float] = {}

            # First, blending out animations (lower weight)
            for key, state in list(self._blending_out.items()):
                positions = state.interpolator.get_positions()
                for channel, pos in positions.items():
                    if channel not in output_positions:
                        output_positions[channel] = 0.0
                    output_positions[channel] += pos * state.blend_factor

            # Then, active animations (higher weight)
            for key, state in list(self._active_animations.items()):
                if state.interpolator.is_finished and not state.sequence.loop:
                    # Animation complete
                    if state.on_complete:
                        state.on_complete()
                    del self._active_animations[key]
                    continue

                positions = state.interpolator.get_positions()
                for channel, pos in positions.items():
                    if channel not in output_positions:
                        output_positions[channel] = 0.0
                    output_positions[channel] += pos * state.blend_factor

            # Normalize and clamp
            for channel in output_positions:
                output_positions[channel] = max(0.0, min(180.0, output_positions[channel]))

            # Update stored positions
            self._channel_positions.update(output_positions)

            # Output to servos
            if output_positions:
                self._servo_output(output_positions)

            return output_positions

    def _process_queue(self) -> None:
        """Process pending animation commands."""
        with self._queue_lock:
            while not self._command_queue.empty():
                cmd = self._command_queue.get_nowait()
                priority = AnimationPriority(-cmd.priority)

                # Create interpolator
                interp = KeyframeInterpolator(cmd.sequence, self._time_source)
                interp.start()

                state = AnimationState(
                    sequence=cmd.sequence,
                    interpolator=interp,
                    priority=priority,
                    blend_factor=0.0,  # Will blend in
                    on_complete=cmd.on_complete,
                )

                # Check for conflicts with existing animations
                for channel in cmd.sequence.channels:
                    existing = self._active_animations.get(channel)
                    if existing:
                        if priority >= existing.priority:
                            # New animation takes over - blend out existing
                            self._blending_out[channel] = existing
                            self._active_animations[channel] = state
                        # Else: existing higher priority, queue waits
                    else:
                        self._active_animations[channel] = state

                # Start blending
                self._blend_start_time = self._time_source()
                self._blend_duration_s = cmd.blend_time_ms / 1000.0

    def _update_blending(self) -> None:
        """Update blend factors for crossfading."""
        if self._blend_start_time is None:
            return

        elapsed = self._time_source() - self._blend_start_time

        if elapsed >= self._blend_duration_s:
            # Blending complete
            self._blending_out.clear()
            for state in self._active_animations.values():
                state.blend_factor = 1.0
            self._blend_start_time = None
            return

        # Calculate blend progress
        progress = elapsed / self._blend_duration_s

        # Fade in active animations
        for state in self._active_animations.values():
            state.blend_factor = progress

        # Fade out old animations
        for state in self._blending_out.values():
            state.blend_factor = 1.0 - progress

    def get_channel_position(self, channel: str) -> Optional[float]:
        """Get current position of a channel."""
        with self._state_lock:
            return self._channel_positions.get(channel)
```

---

## Part 4: Control Loop Integration

### 4.1 50Hz Control Loop Architecture

```python
# firmware/src/control/control_loop.py

"""
Deterministic Control Loop for Animation System

Provides a 50Hz (20ms) control loop with:
- Deterministic timing using monotonic clock
- Jitter monitoring and logging
- Safety checks every cycle
- Animation player integration
"""

import time
import threading
import logging
from typing import Optional, Callable, Dict
from dataclasses import dataclass
from statistics import mean, stdev

_logger = logging.getLogger(__name__)


@dataclass
class LoopTimingStats:
    """Statistics for control loop timing."""
    target_period_ms: float
    actual_period_ms: float
    jitter_ms: float
    max_jitter_ms: float
    cycle_count: int
    overrun_count: int

    def __str__(self) -> str:
        return (
            f"ControlLoop: {self.cycle_count} cycles, "
            f"period={self.actual_period_ms:.2f}ms (target={self.target_period_ms:.2f}ms), "
            f"jitter={self.jitter_ms:.2f}ms (max={self.max_jitter_ms:.2f}ms), "
            f"overruns={self.overrun_count}"
        )


class ControlLoop:
    """Deterministic 50Hz control loop with jitter monitoring.

    Design Goals:
        1. Consistent 20ms period (+/- 1ms jitter target)
        2. Prioritize timing over computation
        3. Skip expensive operations if behind schedule
        4. Never block on I/O (use async patterns)

    Example:
        >>> def update_callback():
        ...     positions = animation_player.update()
        ...     # Do other work

        >>> loop = ControlLoop(target_hz=50)
        >>> loop.set_callback(update_callback)
        >>> loop.start()  # Runs in background thread
        >>> # ... do other things ...
        >>> loop.stop()
    """

    DEFAULT_HZ = 50
    MAX_JITTER_WARN_MS = 5.0  # Warn if jitter exceeds this

    def __init__(self, target_hz: int = DEFAULT_HZ,
                 time_source: Optional[Callable[[], float]] = None):
        """Initialize control loop.

        Args:
            target_hz: Target frequency in Hz (default: 50)
            time_source: Time source (default: time.monotonic)
        """
        if target_hz <= 0:
            raise ValueError(f"target_hz must be positive, got {target_hz}")

        self._target_hz = target_hz
        self._target_period_s = 1.0 / target_hz
        self._target_period_ms = self._target_period_s * 1000
        self._time_source = time_source or time.monotonic

        # Callbacks
        self._update_callback: Optional[Callable[[], None]] = None
        self._safety_callback: Optional[Callable[[], bool]] = None

        # Thread state
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._stop_event = threading.Event()

        # Timing statistics
        self._cycle_count = 0
        self._overrun_count = 0
        self._jitter_samples: list = []
        self._max_jitter_ms = 0.0
        self._last_cycle_time: Optional[float] = None

    def set_callback(self, callback: Callable[[], None]) -> None:
        """Set the update callback called each cycle."""
        self._update_callback = callback

    def set_safety_callback(self, callback: Callable[[], bool]) -> None:
        """Set safety check callback. Returns False to stop loop."""
        self._safety_callback = callback

    def start(self) -> None:
        """Start control loop in background thread."""
        if self._running:
            return

        self._running = True
        self._stop_event.clear()
        self._cycle_count = 0
        self._overrun_count = 0
        self._jitter_samples.clear()
        self._max_jitter_ms = 0.0

        self._thread = threading.Thread(
            target=self._loop,
            name="ControlLoop",
            daemon=True,
        )
        self._thread.start()
        _logger.info(f"Control loop started at {self._target_hz}Hz")

    def stop(self) -> None:
        """Stop control loop."""
        if not self._running:
            return

        self._running = False
        self._stop_event.set()

        if self._thread:
            self._thread.join(timeout=1.0)
            self._thread = None

        _logger.info(f"Control loop stopped. Stats: {self.get_stats()}")

    def run_once(self) -> None:
        """Execute a single control loop iteration (for testing)."""
        self._execute_cycle()

    def _loop(self) -> None:
        """Main loop running in background thread."""
        next_cycle_time = self._time_source()

        while not self._stop_event.is_set():
            cycle_start = self._time_source()

            # Check if we're behind schedule
            if cycle_start > next_cycle_time + self._target_period_s:
                # We're more than one cycle behind - reset timing
                next_cycle_time = cycle_start
                self._overrun_count += 1
                _logger.warning("Control loop overrun - resetting timing")

            # Execute cycle
            self._execute_cycle()

            # Calculate timing
            cycle_end = self._time_source()
            cycle_duration = cycle_end - cycle_start

            # Record jitter
            if self._last_cycle_time is not None:
                actual_period = cycle_start - self._last_cycle_time
                jitter = abs(actual_period - self._target_period_s) * 1000
                self._jitter_samples.append(jitter)
                self._max_jitter_ms = max(self._max_jitter_ms, jitter)

                if jitter > self.MAX_JITTER_WARN_MS:
                    _logger.warning(f"High jitter: {jitter:.2f}ms")

            self._last_cycle_time = cycle_start
            self._cycle_count += 1

            # Keep only last 1000 jitter samples
            if len(self._jitter_samples) > 1000:
                self._jitter_samples = self._jitter_samples[-1000:]

            # Schedule next cycle
            next_cycle_time += self._target_period_s
            sleep_time = next_cycle_time - self._time_source()

            if sleep_time > 0:
                self._stop_event.wait(sleep_time)

    def _execute_cycle(self) -> None:
        """Execute one control loop cycle."""
        # Safety check first
        if self._safety_callback is not None:
            if not self._safety_callback():
                _logger.error("Safety callback returned False - stopping loop")
                self._running = False
                return

        # Update callback
        if self._update_callback is not None:
            try:
                self._update_callback()
            except Exception as e:
                _logger.error(f"Update callback error: {e}")

    def get_stats(self) -> LoopTimingStats:
        """Get current timing statistics."""
        avg_jitter = mean(self._jitter_samples) if self._jitter_samples else 0.0

        # Calculate actual period
        if len(self._jitter_samples) >= 2:
            actual_period = self._target_period_ms + avg_jitter / 2
        else:
            actual_period = self._target_period_ms

        return LoopTimingStats(
            target_period_ms=self._target_period_ms,
            actual_period_ms=actual_period,
            jitter_ms=avg_jitter,
            max_jitter_ms=self._max_jitter_ms,
            cycle_count=self._cycle_count,
            overrun_count=self._overrun_count,
        )

    @property
    def is_running(self) -> bool:
        """Check if loop is running."""
        return self._running
```

---

## Part 5: Day-by-Day Implementation Schedule

### Week 02 Controls Work Breakdown

| Day | Focus | Classes to Implement | Tests | Hours |
|-----|-------|---------------------|-------|-------|
| Day 8 (Wed) | Keyframe + BNO085 | `Keyframe`, `AnimationSequence`, `KeyframeInterpolator` | 40 | 6 |
| Day 9 (Thu) | Easing + Patterns | `easing.py` (all functions), LED patterns | 30 | 6 |
| Day 10 (Fri) | Sync + Player | `AnimationPlayer`, priority system | 35 | 6 |
| Day 11 (Sat) | Control Loop | `ControlLoop`, timing tests | 25 | 5 |
| Day 12 (Sun) | Integration | Full system integration tests | 30 | 6 |
| Day 13 (Mon) | Polish | Edge cases, hostile review | 15 | 4 |
| Day 14 (Tue) | Closure | Documentation, v0.2.0 tag | 5 | 3 |
| **TOTAL** | | | **180** | **36** |

### Day 8 - Wednesday (Detailed)

**Morning (3 hours): BNO085 + Keyframe Foundation**

1. **BNO085 I2C Connection** (30 min)
   - Follow `PRE_WIRING_CHECKLIST.md`
   - Connect BNO085 to Pi (no batteries needed)
   - Verify `i2cdetect -y 1` shows 0x4A

2. **Keyframe Data Structures** (60 min)
   - Create `firmware/src/animation/__init__.py`
   - Implement `Keyframe` dataclass (frozen, validated)
   - Implement `AnimationSequence` class
   - Write 15 unit tests

3. **BNO085 Driver** (90 min)
   - TDD: Write tests first
   - Implement `OrientationData` dataclass
   - Implement `BNO085Driver.read_orientation()`
   - Hardware test on Pi

**Afternoon (3 hours): Interpolation Engine**

4. **KeyframeInterpolator** (120 min)
   - Binary search for surrounding keyframes
   - Linear interpolation
   - Easing LUT generation
   - 25 unit tests with mock time source

5. **Integration Test** (60 min)
   - Simple animation: servo 0-90-0 over 2 seconds
   - Mock servo output verification
   - Timing accuracy verification

**Evening (1 hour): Documentation**

6. **CHANGELOG update**
7. **Hostile review on interpolator**
8. **Git commit**

### Day 9 - Thursday (Detailed)

**Morning (2 hours): Easing Library**

1. **Core Easing Functions** (60 min)
   - `linear`, `ease_in`, `ease_out`, `ease_in_out`
   - 15 parametrized tests

2. **Advanced Easing** (60 min)
   - `bounce_in/out`, `elastic_in/out`, `ease_*_back`
   - Visual verification script
   - 10 additional tests

**Afternoon (4 hours): LED Pattern Library**

3. **Pattern Base Class** (60 min)
   - `PatternBase` abstract class
   - `render()` contract definition

4. **Core Patterns** (120 min)
   - `BreathingPattern` (idle)
   - `PulsePattern` (alert/heartbeat)
   - `SpinPattern` (thinking)
   - `SparklePattern` (happy)

5. **Hardware Test** (60 min)
   - Run each pattern on LED ring
   - Video recording for documentation
   - Performance timing check

### Day 10 - Friday (Detailed)

**Full Day: Animation Player + Sync**

1. **Animation Priority System** (90 min)
   - `AnimationPriority` enum
   - `AnimationState` dataclass
   - `AnimationCommand` for queue

2. **AnimationPlayer Core** (180 min)
   - Thread-safe queue processing
   - Priority-based interruption
   - Blend factor computation

3. **Multi-Channel Sync Tests** (90 min)
   - Verify <0.5ms inter-servo skew
   - Mock servo output timing tests

### Day 11 - Saturday (Detailed)

**Morning: Control Loop**

1. **ControlLoop Class** (120 min)
   - 50Hz deterministic timing
   - Jitter monitoring
   - Safety callback integration

2. **Timing Tests** (90 min)
   - Mock time source tests
   - Overrun handling tests
   - Statistics accuracy tests

**Afternoon: Head Controller**

3. **HeadController Class** (120 min)
   - `look_at(pan, tilt)` method
   - `random_glance()` for idle behavior
   - Coordinate transformation

### Day 12 - Sunday (Detailed)

**Full Integration Day**

1. **End-to-End Test** (180 min)
   - Emotion -> LED + Head animation
   - BNO085 -> Reactive motion
   - Full mock integration

2. **Performance Profiling** (120 min)
   - Memory allocation analysis
   - CPU usage at 50Hz
   - GC pause impact

### Day 13 - Monday (Detailed)

**Polish + Hostile Review**

1. **Hostile Review** (120 min)
   - Thread safety review
   - Edge case identification
   - Performance bottleneck review

2. **Bug Fixes** (120 min)
   - Address all CRITICAL issues
   - Address all HIGH issues

### Day 14 - Tuesday (Detailed)

**Week 02 Closure**

1. **Test Suite Final Run** (60 min)
2. **Documentation Update** (60 min)
3. **Git Tag v0.2.0** (30 min)
4. **Week 02 Completion Report** (60 min)

---

## Part 6: Performance Requirements

### Timing Budgets (20ms cycle)

| Operation | Budget | Implementation |
|-----------|--------|----------------|
| Safety check | 0.5ms | Simple flag check |
| Keyframe lookup | 0.5ms | Binary search O(log n) |
| Easing computation | 0.2ms | LUT interpolation O(1) |
| Multi-channel interp | 1.0ms | Pre-allocated buffers |
| I2C write (all servos) | 2.0ms | Batch write |
| LED write | 1.0ms | DMA-based |
| IMU read | 1.5ms | Non-blocking |
| **Total used** | **6.7ms** | |
| **Headroom** | **13.3ms** | For unexpected delays |

### Memory Budgets

| Component | Allocation | Notes |
|-----------|------------|-------|
| Easing LUTs | 8.1 KB | 101 floats x 20 functions |
| Animation buffer | 1 KB | Pre-allocated output |
| Keyframe storage | 100 B/kf | Frozen dataclass |
| Max animations | 5 KB | 50 keyframes typical |

---

## Part 7: Mock-Testable Architecture

### Dependency Injection Pattern

```python
# firmware/src/animation/factory.py

"""
Animation System Factory - Dependency Injection

Provides factory functions for creating animation system components
with appropriate dependencies for testing vs production.
"""

from typing import Optional, Callable, Dict
import time


class AnimationSystemFactory:
    """Factory for creating animation system with DI."""

    @staticmethod
    def create_for_testing(
        mock_servo_output: Callable[[Dict[str, float]], None],
        mock_time: Callable[[], float],
    ) -> tuple:
        """Create animation system with mocks for testing.

        Returns:
            (AnimationPlayer, ControlLoop) tuple configured for testing
        """
        from .player import AnimationPlayer
        from ..control.control_loop import ControlLoop

        player = AnimationPlayer(
            servo_output=mock_servo_output,
            time_source=mock_time,
        )

        loop = ControlLoop(
            target_hz=50,
            time_source=mock_time,
        )
        loop.set_callback(player.update)

        return player, loop

    @staticmethod
    def create_for_production(
        servo_driver,
        imu_driver=None,
        led_driver=None,
    ) -> tuple:
        """Create animation system for production hardware.

        Args:
            servo_driver: PCA9685Driver instance
            imu_driver: Optional BNO085Driver instance
            led_driver: Optional LED driver instance
        """
        from .player import AnimationPlayer
        from ..control.control_loop import ControlLoop

        def servo_output(positions: Dict[str, float]) -> None:
            for channel, angle in positions.items():
                if channel.startswith('servo_'):
                    ch_num = int(channel.split('_')[1])
                    servo_driver.set_servo_angle(ch_num, angle)

        player = AnimationPlayer(
            servo_output=servo_output,
            time_source=time.monotonic,
        )

        loop = ControlLoop(target_hz=50)
        loop.set_callback(player.update)

        return player, loop
```

---

## Summary

This technical plan provides a complete implementation roadmap for the animation/controls system with:

1. **Keyframe System**: Immutable data structures, O(log n) lookup, O(1) easing
2. **Easing Library**: 20+ Disney-compliant functions with LUT optimization
3. **Multi-Servo Sync**: <0.5ms skew, priority-based layering, smooth blending
4. **50Hz Control Loop**: Deterministic timing, jitter monitoring, safety integration
5. **Mock-Testable**: Full dependency injection, 180+ planned tests

**Ready for Implementation**: All code structures designed, tests specified, performance budgets allocated.

---

**Document Version:** 1.0
**Created:** 17 January 2026
**Author:** Senior Controls Systems Engineer
**Next Review:** After Day 8 Implementation
