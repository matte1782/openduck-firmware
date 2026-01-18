#!/usr/bin/env python3
"""
Easing Functions for Animation Timing

Standard easing curves for smooth animation transitions:
- linear: Constant speed (no easing)
- ease_in: Start slow, end fast (quadratic)
- ease_out: Start fast, end slow (quadratic)
- ease_in_out: Slow at both ends, fast in middle (quadratic)

All functions use pre-computed lookup tables for O(1) performance.

Author: Boston Dynamics Animation Systems Engineer
Created: 18 January 2026
"""

from typing import List, Callable, Dict

# Lookup table size (0-100 = 101 entries for integer percentage lookup)
LUT_SIZE = 101


def _compute_linear(t: float) -> float:
    """Linear easing (no easing)."""
    return t


def _compute_ease_in(t: float) -> float:
    """Quadratic ease-in: slow start, fast end."""
    return t * t


def _compute_ease_out(t: float) -> float:
    """Quadratic ease-out: fast start, slow end."""
    return 1 - (1 - t) ** 2


def _compute_ease_in_out(t: float) -> float:
    """Quadratic ease-in-out: slow at both ends."""
    if t < 0.5:
        return 2 * t * t
    else:
        return 1 - (-2 * t + 2) ** 2 / 2


# Pre-computed lookup tables
LINEAR_LUT: List[float] = [_compute_linear(i / 100) for i in range(LUT_SIZE)]
EASE_IN_LUT: List[float] = [_compute_ease_in(i / 100) for i in range(LUT_SIZE)]
EASE_OUT_LUT: List[float] = [_compute_ease_out(i / 100) for i in range(LUT_SIZE)]
EASE_IN_OUT_LUT: List[float] = [_compute_ease_in_out(i / 100) for i in range(LUT_SIZE)]

# LUT registry for fast lookup
EASING_LUTS: Dict[str, List[float]] = {
    'linear': LINEAR_LUT,
    'ease_in': EASE_IN_LUT,
    'ease_out': EASE_OUT_LUT,
    'ease_in_out': EASE_IN_OUT_LUT,
}


def ease(t: float, easing_type: str = 'ease_in_out') -> float:
    """Apply easing function to input value.

    Uses pre-computed lookup tables for O(1) performance.

    Args:
        t: Input value (0.0 to 1.0)
        easing_type: One of 'linear', 'ease_in', 'ease_out', 'ease_in_out'

    Returns:
        Eased output value (0.0 to 1.0)

    Raises:
        ValueError: If easing_type is not recognized
    """
    if easing_type not in EASING_LUTS:
        raise ValueError(f"Unknown easing type: {easing_type}. "
                        f"Valid types: {list(EASING_LUTS.keys())}")

    # Clamp input to valid range
    t = max(0.0, min(1.0, t))

    # Convert to LUT index (0-100)
    index = int(t * 100)

    return EASING_LUTS[easing_type][index]


def ease_linear(t: float) -> float:
    """Linear easing - O(1) lookup."""
    return LINEAR_LUT[int(max(0.0, min(1.0, t)) * 100)]


def ease_in(t: float) -> float:
    """Ease-in (quadratic) - O(1) lookup."""
    return EASE_IN_LUT[int(max(0.0, min(1.0, t)) * 100)]


def ease_out(t: float) -> float:
    """Ease-out (quadratic) - O(1) lookup."""
    return EASE_OUT_LUT[int(max(0.0, min(1.0, t)) * 100)]


def ease_in_out(t: float) -> float:
    """Ease-in-out (quadratic) - O(1) lookup."""
    return EASE_IN_OUT_LUT[int(max(0.0, min(1.0, t)) * 100)]


# Export easing functions by name
EASING_FUNCTIONS: Dict[str, Callable[[float], float]] = {
    'linear': ease_linear,
    'ease_in': ease_in,
    'ease_out': ease_out,
    'ease_in_out': ease_in_out,
}
