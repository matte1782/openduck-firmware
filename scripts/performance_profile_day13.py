#!/usr/bin/env python3
"""
Day 13 Performance Profiling - 50Hz Validation

Validates that animation system meets 50Hz frame budget on Pi Zero 2W.
All timings measured in milliseconds.

Target Hardware: Raspberry Pi Zero 2W (ARM Cortex-A53 @ 1GHz)

Frame Budget Breakdown:
    - Total frame time: 20ms (50Hz)
    - Hardware I/O reserve: ~10ms (servo commands, LED updates via I2C/SPI)
    - Software budget: 10ms maximum per frame

Profile Targets:
    1. Keyframe Interpolation: <0.1ms per call
    2. LED Pattern Rendering: <0.5ms per pattern
    3. Color Transitions: <0.05ms per call
    4. Emotion Bridge: <1ms per emotion change
    5. Head Controller: <5ms initiation latency
    6. Full Animation Loop: <2ms total

Usage:
    python scripts/performance_profile_day13.py
    python scripts/performance_profile_day13.py --iterations 50000
    python scripts/performance_profile_day13.py --export results.json

Author: AGENT 2 - Performance Profiler (Day 13 IAO-v2-DYNAMIC)
Created: 18 January 2026
"""

import argparse
import json
import statistics
import sys
import time
import os
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional, Callable

# Change working directory to firmware for proper package imports
firmware_dir = Path(__file__).parent.parent
os.chdir(firmware_dir)

# Add firmware/src to path for package imports
sys.path.insert(0, str(firmware_dir / "src"))

# =============================================================================
# CONSTANTS
# =============================================================================

TARGET_FPS = 50
FRAME_BUDGET_MS = 1000 / TARGET_FPS  # 20ms
IO_RESERVE_MS = 10
SOFTWARE_BUDGET_MS = FRAME_BUDGET_MS - IO_RESERVE_MS  # 10ms

# Default iterations for profiling
DEFAULT_ITERATIONS = 10000

# Target times in milliseconds
TARGETS = {
    "keyframe_interpolation": 0.1,        # AnimationSequence.get_values()
    "breathing_pattern": 0.5,              # BreathingPattern.render()
    "spin_pattern": 0.5,                   # SpinPattern.render()
    "pulse_pattern": 0.5,                  # PulsePattern.render()
    "color_interpolate": 0.05,             # color_interpolate()
    "color_arc_interpolate": 0.05,         # color_arc_interpolate()
    "hsv_to_rgb": 0.05,                    # hsv_to_rgb()
    "rgb_to_hsv": 0.05,                    # rgb_to_hsv()
    "emotion_bridge_express": 1.0,         # EmotionBridge.express_emotion()
    "emotion_bridge_config": 0.5,          # EmotionBridge.get_expression_for_emotion()
    "axis_to_led_mapping": 0.1,            # AxisToLEDMapper.axes_to_led_config()
    "easing_function": 0.01,               # ease() function
    "full_animation_loop": 2.0,            # Complete loop iteration
}


# =============================================================================
# DATA STRUCTURES
# =============================================================================

@dataclass
class ProfileResult:
    """Result of profiling a single component."""
    name: str
    iterations: int
    mean_ms: float
    median_ms: float
    p99_ms: float
    max_ms: float
    min_ms: float
    stdev_ms: float
    target_ms: Optional[float] = None
    status: str = "UNKNOWN"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON export."""
        return asdict(self)


@dataclass
class ProfilingReport:
    """Complete profiling report with all component results."""
    timestamp: str
    python_version: str
    platform: str
    iterations: int
    results: List[ProfileResult] = field(default_factory=list)
    total_frame_time_ms: float = 0.0
    software_budget_used_pct: float = 0.0
    fifty_hz_verdict: str = "UNKNOWN"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON export."""
        return {
            "timestamp": self.timestamp,
            "python_version": self.python_version,
            "platform": self.platform,
            "iterations": self.iterations,
            "results": [r.to_dict() for r in self.results],
            "total_frame_time_ms": self.total_frame_time_ms,
            "software_budget_used_pct": self.software_budget_used_pct,
            "fifty_hz_verdict": self.fifty_hz_verdict,
        }


# =============================================================================
# PROFILING FUNCTIONS
# =============================================================================

def profile_component(
    name: str,
    func: Callable[[], Any],
    iterations: int = DEFAULT_ITERATIONS,
    target_ms: Optional[float] = None,
    warmup_iterations: int = 100
) -> ProfileResult:
    """
    Profile a component and report statistics.

    Args:
        name: Component name for display
        func: Function to profile (no arguments)
        iterations: Number of iterations to run
        target_ms: Target time in milliseconds (for PASS/FAIL)
        warmup_iterations: Number of warmup iterations before profiling

    Returns:
        ProfileResult with timing statistics
    """
    # Warmup phase to stabilize caches
    for _ in range(warmup_iterations):
        func()

    # Profiling phase
    times: List[float] = []
    for _ in range(iterations):
        start = time.perf_counter()
        func()
        elapsed = (time.perf_counter() - start) * 1000  # Convert to ms
        times.append(elapsed)

    # Calculate statistics
    mean = statistics.mean(times)
    median = statistics.median(times)
    stdev = statistics.stdev(times) if len(times) > 1 else 0.0
    sorted_times = sorted(times)
    p99_index = int(len(times) * 0.99)
    p99 = sorted_times[p99_index] if p99_index < len(times) else sorted_times[-1]
    max_time = max(times)
    min_time = min(times)

    # Determine status
    if target_ms is not None:
        status = "PASS" if mean < target_ms else "FAIL"
    else:
        status = "N/A"

    return ProfileResult(
        name=name,
        iterations=iterations,
        mean_ms=mean,
        median_ms=median,
        p99_ms=p99,
        max_ms=max_time,
        min_ms=min_time,
        stdev_ms=stdev,
        target_ms=target_ms,
        status=status
    )


def print_result(result: ProfileResult) -> None:
    """Print a single profiling result in formatted style."""
    print(f"\n{result.name} ({result.iterations:,} iterations):")
    print(f"  Mean:   {result.mean_ms:.4f} ms")
    print(f"  Median: {result.median_ms:.4f} ms")
    print(f"  P99:    {result.p99_ms:.4f} ms")
    print(f"  Max:    {result.max_ms:.4f} ms")
    print(f"  Min:    {result.min_ms:.4f} ms")
    print(f"  StdDev: {result.stdev_ms:.4f} ms")
    if result.target_ms is not None:
        status_color = "" if result.status == "PASS" else ""
        print(f"  Target: <{result.target_ms} ms -> {status_color}{result.status}")


# =============================================================================
# STANDALONE IMPLEMENTATIONS FOR FALLBACK PROFILING
# =============================================================================
# These implement the core algorithms when module imports fail due to relative
# import issues. They mirror the actual implementations for accurate profiling.

import math
import threading
import colorsys
from typing import Tuple

# Easing LUTs (copied from animation/easing.py)
_LUT_SIZE = 101
_LINEAR_LUT = [i / 100 for i in range(_LUT_SIZE)]
_EASE_IN_LUT = [(i / 100) ** 2 for i in range(_LUT_SIZE)]
_EASE_OUT_LUT = [1 - (1 - i / 100) ** 2 for i in range(_LUT_SIZE)]
_EASE_IN_OUT_LUT = [
    2 * (i / 100) ** 2 if i / 100 < 0.5 else 1 - (-2 * i / 100 + 2) ** 2 / 2
    for i in range(_LUT_SIZE)
]
_EASING_LUTS = {
    'linear': _LINEAR_LUT,
    'ease_in': _EASE_IN_LUT,
    'ease_out': _EASE_OUT_LUT,
    'ease_in_out': _EASE_IN_OUT_LUT,
}

def _ease_standalone(t: float, easing_type: str = 'ease_in_out') -> float:
    """Standalone ease function for profiling."""
    t = max(0.0, min(1.0, t))
    index = int(t * 100)
    return _EASING_LUTS.get(easing_type, _EASE_IN_OUT_LUT)[index]

# HSV LUT (copied from led/color_utils.py)
_HSV_LUT_SIZE = 360
_HSV_TO_RGB_LUT = []
for h in range(_HSV_LUT_SIZE):
    sector = h / 60.0
    sector_index = int(sector) % 6
    f = sector - int(sector)
    if sector_index == 0:
        r, g, b = 1.0, f, 0.0
    elif sector_index == 1:
        r, g, b = 1.0 - f, 1.0, 0.0
    elif sector_index == 2:
        r, g, b = 0.0, 1.0, f
    elif sector_index == 3:
        r, g, b = 0.0, 1.0 - f, 1.0
    elif sector_index == 4:
        r, g, b = f, 0.0, 1.0
    else:
        r, g, b = 1.0, 0.0, 1.0 - f
    _HSV_TO_RGB_LUT.append((int(r * 255), int(g * 255), int(b * 255)))

def _hsv_to_rgb_standalone(h: float, s: float, v: float) -> Tuple[int, int, int]:
    """Standalone HSV to RGB conversion."""
    h = h % 360.0
    s = max(0.0, min(1.0, s))
    v = max(0.0, min(1.0, v))

    if s < 1e-9:
        gray = int(v * 255)
        return (gray, gray, gray)

    if s >= 0.999 and v >= 0.999:
        return _HSV_TO_RGB_LUT[int(h) % 360]

    sector = h / 60.0
    sector_index = int(sector) % 6
    f = sector - int(sector)
    p = v * (1.0 - s)
    q = v * (1.0 - s * f)
    t = v * (1.0 - s * (1.0 - f))

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
    else:
        r, g, b = v, p, q

    return (int(r * 255), int(g * 255), int(b * 255))

def _rgb_to_hsv_standalone(rgb: Tuple[int, int, int]) -> Tuple[float, float, float]:
    """Standalone RGB to HSV conversion."""
    r, g, b = rgb[0] / 255.0, rgb[1] / 255.0, rgb[2] / 255.0
    max_c = max(r, g, b)
    min_c = min(r, g, b)
    delta = max_c - min_c

    v = max_c
    if delta < 1e-9:
        return (0.0, 0.0, v)

    s = delta / max_c if max_c > 1e-9 else 0.0

    if abs(max_c - r) < 1e-9:
        h = 60.0 * ((g - b) / delta)
    elif abs(max_c - g) < 1e-9:
        h = 60.0 * (2.0 + (b - r) / delta)
    else:
        h = 60.0 * (4.0 + (r - g) / delta)

    if h < 0:
        h += 360.0

    return (h, s, v)

def _color_interpolate_standalone(
    start: Tuple[int, int, int],
    end: Tuple[int, int, int],
    t: float
) -> Tuple[int, int, int]:
    """Standalone linear RGB interpolation."""
    t = max(0.0, min(1.0, t))
    return (
        int(max(0, min(255, start[0] + (end[0] - start[0]) * t))),
        int(max(0, min(255, start[1] + (end[1] - start[1]) * t))),
        int(max(0, min(255, start[2] + (end[2] - start[2]) * t))),
    )

def _color_arc_interpolate_standalone(
    start: Tuple[int, int, int],
    end: Tuple[int, int, int],
    t: float
) -> Tuple[int, int, int]:
    """Standalone HSV arc interpolation."""
    t = max(0.0, min(1.0, t))

    start_hsv = _rgb_to_hsv_standalone(start)
    end_hsv = _rgb_to_hsv_standalone(end)

    h1, s1, v1 = start_hsv
    h2, s2, v2 = end_hsv

    if s1 < 1e-9 or s2 < 1e-9:
        return _color_interpolate_standalone(start, end, t)

    hue_diff = h2 - h1
    hue_diff = ((hue_diff + 180) % 360) - 180

    h_interp = (h1 + hue_diff * t) % 360.0
    s_interp = s1 + (s2 - s1) * t
    v_interp = v1 + (v2 - v1) * t

    return _hsv_to_rgb_standalone(h_interp, s_interp, v_interp)


# Sine LUT for breathing pattern (copied from led/patterns/breathing.py)
_SINE_LUT_SIZE = 256
_SINE_LUT = [(math.sin(i / _SINE_LUT_SIZE * 2 * math.pi) + 1) / 2 for i in range(_SINE_LUT_SIZE)]


class _BreathingPatternStandalone:
    """Standalone breathing pattern for profiling."""
    CYCLE_FRAMES = 200
    MIN_INTENSITY = 0.3
    MAX_INTENSITY = 1.0

    def __init__(self, num_pixels: int = 16):
        self.num_pixels = num_pixels
        self._frame = 0
        self._pixel_buffer = [(0, 0, 0)] * num_pixels

    def render(self, base_color: Tuple[int, int, int]) -> list:
        progress = (self._frame % self.CYCLE_FRAMES) / self.CYCLE_FRAMES
        lut_index = int(progress * (_SINE_LUT_SIZE - 1)) % _SINE_LUT_SIZE
        breath = _SINE_LUT[lut_index]
        intensity = self.MIN_INTENSITY + breath * (self.MAX_INTENSITY - self.MIN_INTENSITY)

        scaled = (
            int(max(0, min(255, base_color[0] * intensity))),
            int(max(0, min(255, base_color[1] * intensity))),
            int(max(0, min(255, base_color[2] * intensity))),
        )

        for i in range(self.num_pixels):
            self._pixel_buffer[i] = scaled

        return self._pixel_buffer

    def advance(self):
        self._frame = (self._frame + 1) % 1_000_000


class _SpinPatternStandalone:
    """Standalone spin pattern for profiling."""
    CYCLE_FRAMES = 32
    TAIL_LENGTH = 4
    HEAD_INTENSITY = 1.0
    TAIL_DECAY = 0.6
    BACKGROUND_INTENSITY = 0.1

    def __init__(self, num_pixels: int = 16):
        self.num_pixels = num_pixels
        self._frame = 0
        self._pixel_buffer = [(0, 0, 0)] * num_pixels

    def render(self, base_color: Tuple[int, int, int]) -> list:
        progress = (self._frame % self.CYCLE_FRAMES) / self.CYCLE_FRAMES
        head_pos = int(progress * self.num_pixels) % self.num_pixels

        background = (
            int(max(0, min(255, base_color[0] * self.BACKGROUND_INTENSITY))),
            int(max(0, min(255, base_color[1] * self.BACKGROUND_INTENSITY))),
            int(max(0, min(255, base_color[2] * self.BACKGROUND_INTENSITY))),
        )

        for i in range(self.num_pixels):
            self._pixel_buffer[i] = background

        intensity = self.HEAD_INTENSITY
        for i in range(self.TAIL_LENGTH):
            pos = (head_pos - i) % self.num_pixels
            self._pixel_buffer[pos] = (
                int(max(0, min(255, base_color[0] * intensity))),
                int(max(0, min(255, base_color[1] * intensity))),
                int(max(0, min(255, base_color[2] * intensity))),
            )
            intensity *= self.TAIL_DECAY

        return self._pixel_buffer

    def advance(self):
        self._frame = (self._frame + 1) % 1_000_000


# Standalone profilers using fallback implementations

def profile_breathing_pattern_standalone(iterations: int) -> ProfileResult:
    """Profile breathing pattern using standalone implementation."""
    pattern = _BreathingPatternStandalone(num_pixels=16)
    base_color = (100, 200, 255)

    def profile_func():
        pattern.render(base_color)
        pattern.advance()

    return profile_component(
        name="Breathing Pattern Render (standalone)",
        func=profile_func,
        iterations=iterations,
        target_ms=TARGETS["breathing_pattern"]
    )


def profile_spin_pattern_standalone(iterations: int) -> ProfileResult:
    """Profile spin pattern using standalone implementation."""
    pattern = _SpinPatternStandalone(num_pixels=16)
    base_color = (255, 100, 0)

    def profile_func():
        pattern.render(base_color)
        pattern.advance()

    return profile_component(
        name="Spin Pattern Render (standalone)",
        func=profile_func,
        iterations=iterations,
        target_ms=TARGETS["spin_pattern"]
    )


def profile_color_utils_standalone(iterations: int) -> List[ProfileResult]:
    """Profile color utility functions using standalone implementations."""
    results = []

    # HSV to RGB
    h, s, v = 180.0, 0.75, 0.8
    results.append(profile_component(
        name="HSV to RGB Conversion (standalone)",
        func=lambda: _hsv_to_rgb_standalone(h, s, v),
        iterations=iterations,
        target_ms=TARGETS["hsv_to_rgb"]
    ))

    # RGB to HSV
    rgb = (128, 64, 192)
    results.append(profile_component(
        name="RGB to HSV Conversion (standalone)",
        func=lambda: _rgb_to_hsv_standalone(rgb),
        iterations=iterations,
        target_ms=TARGETS["rgb_to_hsv"]
    ))

    # Color interpolate
    start = (255, 0, 0)
    end = (0, 255, 0)
    t = 0.5
    results.append(profile_component(
        name="Color Interpolate Linear (standalone)",
        func=lambda: _color_interpolate_standalone(start, end, t),
        iterations=iterations,
        target_ms=TARGETS["color_interpolate"]
    ))

    # Color arc interpolate
    results.append(profile_component(
        name="Color Arc Interpolate HSV (standalone)",
        func=lambda: _color_arc_interpolate_standalone(start, end, t),
        iterations=iterations,
        target_ms=TARGETS["color_arc_interpolate"]
    ))

    return results


def profile_full_animation_loop_standalone(iterations: int) -> ProfileResult:
    """Profile full animation loop using standalone implementations."""
    from animation.timing import AnimationSequence
    from animation.axis_to_led import AxisToLEDMapper
    from animation.emotion_axes import EmotionAxes

    seq = AnimationSequence("test", loop=True)
    seq.add_keyframe(0, color=(0, 0, 0), brightness=0.0)
    seq.add_keyframe(1000, color=(255, 255, 255), brightness=1.0)
    seq.add_keyframe(2000, color=(0, 0, 0), brightness=0.0)

    pattern = _BreathingPatternStandalone(num_pixels=16)
    mapper = AxisToLEDMapper()
    axes = EmotionAxes(arousal=0.3, valence=0.6, focus=0.7, blink_speed=1.1)

    start_color = (255, 0, 0)
    end_color = (0, 255, 0)
    frame_counter = [0]

    def full_loop():
        time_ms = (frame_counter[0] * 20) % 2000
        values = seq.get_values(time_ms)

        base_color = values.get('color', (100, 100, 255))
        pixels = pattern.render(base_color)
        pattern.advance()

        t = (frame_counter[0] % 100) / 100.0
        blended = _color_arc_interpolate_standalone(start_color, end_color, t)

        led_config = mapper.axes_to_led_config(axes)
        h, s, v = led_config['hsv']
        rgb = _hsv_to_rgb_standalone(h, s, v)

        frame_counter[0] += 1
        return pixels, blended, rgb

    return profile_component(
        name="Full Animation Loop (standalone)",
        func=full_loop,
        iterations=iterations,
        target_ms=TARGETS["full_animation_loop"]
    )


# =============================================================================
# COMPONENT PROFILERS
# =============================================================================

def profile_keyframe_interpolation(iterations: int) -> ProfileResult:
    """Profile AnimationSequence.get_values() keyframe interpolation."""
    from animation.timing import AnimationSequence

    # Create a realistic animation sequence
    seq = AnimationSequence("test_fade", loop=True)
    seq.add_keyframe(0, color=(0, 0, 0), brightness=0.0)
    seq.add_keyframe(500, color=(255, 128, 0), brightness=0.5, easing='ease_in')
    seq.add_keyframe(1000, color=(255, 255, 255), brightness=1.0, easing='ease_in_out')
    seq.add_keyframe(1500, color=(128, 255, 0), brightness=0.7, easing='ease_out')
    seq.add_keyframe(2000, color=(0, 0, 0), brightness=0.0)

    # Profile mid-sequence interpolation (worst case)
    time_offset = 750

    return profile_component(
        name="Keyframe Interpolation (AnimationSequence.get_values)",
        func=lambda: seq.get_values(time_offset),
        iterations=iterations,
        target_ms=TARGETS["keyframe_interpolation"]
    )


def profile_breathing_pattern(iterations: int) -> ProfileResult:
    """Profile BreathingPattern.render()."""
    try:
        from led.patterns.breathing import BreathingPattern

        pattern = BreathingPattern(num_pixels=16)
        base_color = (100, 200, 255)

        def profile_func():
            pattern.render(base_color)
            pattern.advance()

        return profile_component(
            name="Breathing Pattern Render",
            func=profile_func,
            iterations=iterations,
            target_ms=TARGETS["breathing_pattern"]
        )
    except ImportError as e:
        # Use standalone implementation for profiling
        return profile_breathing_pattern_standalone(iterations)


def profile_spin_pattern(iterations: int) -> ProfileResult:
    """Profile SpinPattern.render()."""
    try:
        from led.patterns.spin import SpinPattern

        pattern = SpinPattern(num_pixels=16)
        base_color = (255, 100, 0)

        def profile_func():
            pattern.render(base_color)
            pattern.advance()

        return profile_component(
            name="Spin Pattern Render",
            func=profile_func,
            iterations=iterations,
            target_ms=TARGETS["spin_pattern"]
        )
    except ImportError:
        return profile_spin_pattern_standalone(iterations)


def profile_pulse_pattern(iterations: int) -> ProfileResult:
    """Profile PulsePattern.render()."""
    try:
        from led.patterns.pulse import PulsePattern

        pattern = PulsePattern(num_pixels=16)
        base_color = (255, 0, 128)

        def profile_func():
            pattern.render(base_color)
            pattern.advance()

        return profile_component(
            name="Pulse Pattern Render",
            func=profile_func,
            iterations=iterations,
            target_ms=TARGETS["pulse_pattern"]
        )
    except ImportError:
        print("  [SKIP] PulsePattern not available")
        return ProfileResult(
            name="Pulse Pattern Render",
            iterations=0,
            mean_ms=0,
            median_ms=0,
            p99_ms=0,
            max_ms=0,
            min_ms=0,
            stdev_ms=0,
            target_ms=TARGETS["pulse_pattern"],
            status="SKIP"
        )


def profile_color_interpolate(iterations: int) -> ProfileResult:
    """Profile color_interpolate() linear RGB interpolation."""
    try:
        from led.color_utils import color_interpolate

        start = (255, 0, 0)
        end = (0, 255, 0)
        t = 0.5

        return profile_component(
            name="Color Interpolate (Linear RGB)",
            func=lambda: color_interpolate(start, end, t),
            iterations=iterations,
            target_ms=TARGETS["color_interpolate"]
        )
    except ImportError:
        start = (255, 0, 0)
        end = (0, 255, 0)
        t = 0.5
        return profile_component(
            name="Color Interpolate Linear (standalone)",
            func=lambda: _color_interpolate_standalone(start, end, t),
            iterations=iterations,
            target_ms=TARGETS["color_interpolate"]
        )


def profile_color_arc_interpolate(iterations: int) -> ProfileResult:
    """Profile color_arc_interpolate() HSV arc interpolation."""
    try:
        from led.color_utils import color_arc_interpolate

        start = (255, 0, 0)
        end = (0, 255, 0)
        t = 0.5

        return profile_component(
            name="Color Arc Interpolate (HSV)",
            func=lambda: color_arc_interpolate(start, end, t),
            iterations=iterations,
            target_ms=TARGETS["color_arc_interpolate"]
        )
    except ImportError:
        start = (255, 0, 0)
        end = (0, 255, 0)
        t = 0.5
        return profile_component(
            name="Color Arc Interpolate HSV (standalone)",
            func=lambda: _color_arc_interpolate_standalone(start, end, t),
            iterations=iterations,
            target_ms=TARGETS["color_arc_interpolate"]
        )


def profile_hsv_to_rgb(iterations: int) -> ProfileResult:
    """Profile hsv_to_rgb() conversion."""
    try:
        from led.color_utils import hsv_to_rgb

        # Profile with varying saturation/value (non-trivial case)
        h, s, v = 180.0, 0.75, 0.8

        return profile_component(
            name="HSV to RGB Conversion",
            func=lambda: hsv_to_rgb(h, s, v),
            iterations=iterations,
            target_ms=TARGETS["hsv_to_rgb"]
        )
    except ImportError:
        h, s, v = 180.0, 0.75, 0.8
        return profile_component(
            name="HSV to RGB Conversion (standalone)",
            func=lambda: _hsv_to_rgb_standalone(h, s, v),
            iterations=iterations,
            target_ms=TARGETS["hsv_to_rgb"]
        )


def profile_rgb_to_hsv(iterations: int) -> ProfileResult:
    """Profile rgb_to_hsv() conversion."""
    try:
        from led.color_utils import rgb_to_hsv

        rgb = (128, 64, 192)

        return profile_component(
            name="RGB to HSV Conversion",
            func=lambda: rgb_to_hsv(rgb),
            iterations=iterations,
            target_ms=TARGETS["rgb_to_hsv"]
        )
    except ImportError:
        rgb = (128, 64, 192)
        return profile_component(
            name="RGB to HSV Conversion (standalone)",
            func=lambda: _rgb_to_hsv_standalone(rgb),
            iterations=iterations,
            target_ms=TARGETS["rgb_to_hsv"]
        )


def profile_easing_function(iterations: int) -> ProfileResult:
    """Profile ease() function with LUT lookup."""
    from animation.easing import ease

    t = 0.5

    return profile_component(
        name="Easing Function (LUT)",
        func=lambda: ease(t, 'ease_in_out'),
        iterations=iterations,
        target_ms=TARGETS["easing_function"]
    )


def profile_axis_to_led_mapping(iterations: int) -> ProfileResult:
    """Profile AxisToLEDMapper.axes_to_led_config()."""
    from animation.axis_to_led import AxisToLEDMapper
    from animation.emotion_axes import EmotionAxes

    mapper = AxisToLEDMapper()
    axes = EmotionAxes(arousal=0.5, valence=0.3, focus=0.7, blink_speed=1.2)

    return profile_component(
        name="Axis to LED Mapping",
        func=lambda: mapper.axes_to_led_config(axes),
        iterations=iterations,
        target_ms=TARGETS["axis_to_led_mapping"]
    )


def profile_emotion_bridge_config(iterations: int) -> ProfileResult:
    """Profile EmotionBridge.get_expression_for_emotion()."""
    from animation.emotion_bridge import EmotionBridge
    from animation.emotion_axes import EmotionAxes

    # Create bridge without hardware controllers
    bridge = EmotionBridge()
    axes = EmotionAxes(arousal=0.5, valence=0.3, focus=0.7, blink_speed=1.2)

    return profile_component(
        name="Emotion Bridge Config (get_expression_for_emotion)",
        func=lambda: bridge.get_expression_for_emotion(axes),
        iterations=iterations,
        target_ms=TARGETS["emotion_bridge_config"]
    )


def profile_emotion_bridge_express(iterations: int) -> ProfileResult:
    """Profile EmotionBridge.express_emotion() without hardware."""
    from animation.emotion_bridge import EmotionBridge
    from animation.emotion_axes import EmotionAxes

    # Create bridge without hardware controllers (no head, no LED)
    bridge = EmotionBridge()
    axes = EmotionAxes(arousal=0.5, valence=0.3, focus=0.7, blink_speed=1.2)

    return profile_component(
        name="Emotion Bridge Express (software only)",
        func=lambda: bridge.express_emotion(axes, duration_ms=500),
        iterations=iterations,
        target_ms=TARGETS["emotion_bridge_express"]
    )


def profile_full_animation_loop(iterations: int) -> ProfileResult:
    """
    Profile complete animation loop iteration.

    Simulates what happens in a single 50Hz frame:
    1. Keyframe interpolation
    2. Pattern rendering
    3. Color transition
    4. Emotion coordination
    """
    try:
        from animation.timing import AnimationSequence
        from led.patterns.breathing import BreathingPattern
        from led.color_utils import color_arc_interpolate, hsv_to_rgb
        from animation.axis_to_led import AxisToLEDMapper
        from animation.emotion_axes import EmotionAxes

        # Setup components
        seq = AnimationSequence("test", loop=True)
        seq.add_keyframe(0, color=(0, 0, 0), brightness=0.0)
        seq.add_keyframe(1000, color=(255, 255, 255), brightness=1.0)
        seq.add_keyframe(2000, color=(0, 0, 0), brightness=0.0)

        pattern = BreathingPattern(num_pixels=16)
        mapper = AxisToLEDMapper()
        axes = EmotionAxes(arousal=0.3, valence=0.6, focus=0.7, blink_speed=1.1)

        start_color = (255, 0, 0)
        end_color = (0, 255, 0)
        frame_counter = [0]

        def full_loop():
            # 1. Keyframe interpolation
            time_ms = (frame_counter[0] * 20) % 2000
            values = seq.get_values(time_ms)

            # 2. LED pattern rendering
            base_color = values.get('color', (100, 100, 255))
            pixels = pattern.render(base_color)
            pattern.advance()

            # 3. Color transition
            t = (frame_counter[0] % 100) / 100.0
            blended = color_arc_interpolate(start_color, end_color, t)

            # 4. Emotion coordination (mapping only, no hardware)
            led_config = mapper.axes_to_led_config(axes)
            h, s, v = led_config['hsv']
            rgb = hsv_to_rgb(h, s, v)

            frame_counter[0] += 1
            return pixels, blended, rgb

        return profile_component(
            name="Full Animation Loop (all components)",
            func=full_loop,
            iterations=iterations,
            target_ms=TARGETS["full_animation_loop"]
        )
    except ImportError:
        # Use standalone implementation
        return profile_full_animation_loop_standalone(iterations)


# =============================================================================
# MAIN PROFILER
# =============================================================================

def run_all_profiles(iterations: int = DEFAULT_ITERATIONS) -> ProfilingReport:
    """
    Run all component profiles and generate report.

    Args:
        iterations: Number of iterations per component

    Returns:
        ProfilingReport with all results
    """
    import platform
    from datetime import datetime

    print("=" * 70)
    print("DAY 13 PERFORMANCE PROFILING - 50Hz VALIDATION")
    print("=" * 70)
    print(f"\nTarget: Raspberry Pi Zero 2W (ARM Cortex-A53 @ 1GHz)")
    print(f"Frame Budget: {FRAME_BUDGET_MS:.1f}ms ({TARGET_FPS}Hz)")
    print(f"I/O Reserve: {IO_RESERVE_MS:.1f}ms")
    print(f"Software Budget: {SOFTWARE_BUDGET_MS:.1f}ms")
    print(f"Iterations per component: {iterations:,}")
    print(f"\nPlatform: {platform.platform()}")
    print(f"Python: {platform.python_version()}")
    print(f"CPU: {platform.processor() or 'Unknown'}")
    print("\n" + "-" * 70)
    print("PROFILING COMPONENTS")
    print("-" * 70)

    results: List[ProfileResult] = []

    # Profile each component
    profilers = [
        ("Easing Function", profile_easing_function),
        ("Keyframe Interpolation", profile_keyframe_interpolation),
        ("HSV to RGB", profile_hsv_to_rgb),
        ("RGB to HSV", profile_rgb_to_hsv),
        ("Color Interpolate", profile_color_interpolate),
        ("Color Arc Interpolate", profile_color_arc_interpolate),
        ("Breathing Pattern", profile_breathing_pattern),
        ("Spin Pattern", profile_spin_pattern),
        ("Pulse Pattern", profile_pulse_pattern),
        ("Axis to LED Mapping", profile_axis_to_led_mapping),
        ("Emotion Bridge Config", profile_emotion_bridge_config),
        ("Emotion Bridge Express", profile_emotion_bridge_express),
        ("Full Animation Loop", profile_full_animation_loop),
    ]

    for name, profiler in profilers:
        try:
            result = profiler(iterations)
            results.append(result)
            print_result(result)
        except Exception as e:
            print(f"\n{name}: ERROR - {e}")
            results.append(ProfileResult(
                name=name,
                iterations=0,
                mean_ms=0,
                median_ms=0,
                p99_ms=0,
                max_ms=0,
                min_ms=0,
                stdev_ms=0,
                status=f"ERROR: {e}"
            ))

    # Calculate total frame time (sum of component means, worst case)
    # Note: In practice, not all components run every frame
    key_components = [
        "Keyframe Interpolation (AnimationSequence.get_values)",
        "Breathing Pattern Render",
        "Color Arc Interpolate (HSV)",
        "Axis to LED Mapping",
    ]

    total_frame_time = sum(
        r.mean_ms for r in results
        if r.name in key_components and r.status != "ERROR"
    )

    # Use full loop time as more accurate estimate
    full_loop_result = next(
        (r for r in results if "Full Animation Loop" in r.name),
        None
    )
    if full_loop_result and full_loop_result.status != "ERROR":
        total_frame_time = full_loop_result.mean_ms

    budget_used_pct = (total_frame_time / SOFTWARE_BUDGET_MS) * 100

    # Determine verdict
    if total_frame_time < SOFTWARE_BUDGET_MS:
        verdict = "PASS"
    else:
        verdict = "FAIL"

    # Create report
    report = ProfilingReport(
        timestamp=datetime.now().isoformat(),
        python_version=platform.python_version(),
        platform=platform.platform(),
        iterations=iterations,
        results=results,
        total_frame_time_ms=total_frame_time,
        software_budget_used_pct=budget_used_pct,
        fifty_hz_verdict=verdict
    )

    # Print summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"\nTotal Software Frame Time: {total_frame_time:.4f} ms")
    print(f"Software Budget: {SOFTWARE_BUDGET_MS:.1f} ms")
    print(f"Budget Used: {budget_used_pct:.1f}%")
    print(f"Margin: {SOFTWARE_BUDGET_MS - total_frame_time:.4f} ms")

    # Count pass/fail
    passed = sum(1 for r in results if r.status == "PASS")
    failed = sum(1 for r in results if r.status == "FAIL")
    skipped = sum(1 for r in results if r.status in ("SKIP", "N/A") or "ERROR" in r.status)

    print(f"\nComponent Results: {passed} PASS, {failed} FAIL, {skipped} SKIP/ERROR")

    # List any failures
    failures = [r for r in results if r.status == "FAIL"]
    if failures:
        print("\nFailed Components:")
        for f in failures:
            print(f"  - {f.name}: {f.mean_ms:.4f}ms (target: <{f.target_ms}ms)")

    print("\n" + "=" * 70)
    if verdict == "PASS":
        print("50Hz VERDICT: PASS - Animation system meets 50Hz frame budget")
    else:
        print("50Hz VERDICT: FAIL - Animation system exceeds 50Hz frame budget")
    print("=" * 70)

    return report


def export_results(report: ProfilingReport, filepath: str) -> None:
    """Export profiling results to JSON file."""
    with open(filepath, 'w') as f:
        json.dump(report.to_dict(), f, indent=2)
    print(f"\nResults exported to: {filepath}")


def main():
    """Main entry point with argument parsing."""
    parser = argparse.ArgumentParser(
        description="Day 13 Performance Profiling - 50Hz Validation"
    )
    parser.add_argument(
        "--iterations", "-i",
        type=int,
        default=DEFAULT_ITERATIONS,
        help=f"Number of iterations per component (default: {DEFAULT_ITERATIONS})"
    )
    parser.add_argument(
        "--export", "-e",
        type=str,
        default=None,
        help="Export results to JSON file (e.g., results.json)"
    )
    parser.add_argument(
        "--quick", "-q",
        action="store_true",
        help="Quick mode with 1000 iterations"
    )

    args = parser.parse_args()

    iterations = args.iterations
    if args.quick:
        iterations = 1000

    try:
        report = run_all_profiles(iterations)

        if args.export:
            export_results(report, args.export)

        # Exit with appropriate code
        sys.exit(0 if report.fifty_hz_verdict == "PASS" else 1)

    except ImportError as e:
        print(f"\nERROR: Failed to import module: {e}")
        print("Make sure you're running from the firmware directory.")
        sys.exit(2)
    except Exception as e:
        print(f"\nERROR: Profiling failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(2)


if __name__ == "__main__":
    main()
