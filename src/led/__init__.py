"""
LED control and patterns for OpenDuck Mini V3

Author: Boston Dynamics Animation Systems Engineer
Created: 18 January 2026
"""

# Color utilities exports
from .color_utils import (
    # Type aliases
    RGB,
    HSV,
    # Conversion functions
    rgb_to_hsv,
    hsv_to_rgb,
    # Interpolation functions
    color_interpolate,
    color_arc_interpolate,
    lerp_color,
    # Color manipulation functions
    hue_shift,
    brightness_adjust,
    saturation_adjust,
    complementary_color,
    # Classes
    ColorTransition,
    ColorTransitionConfig,
)

__all__ = [
    # Type aliases
    'RGB',
    'HSV',
    # Conversion functions
    'rgb_to_hsv',
    'hsv_to_rgb',
    # Interpolation functions
    'color_interpolate',
    'color_arc_interpolate',
    'lerp_color',
    # Color manipulation functions
    'hue_shift',
    'brightness_adjust',
    'saturation_adjust',
    'complementary_color',
    # Classes
    'ColorTransition',
    'ColorTransitionConfig',
]
