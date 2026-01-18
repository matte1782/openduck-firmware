"""
LED Pattern Library for OpenDuck Mini V3

Exports all pattern classes for easy import:
    from src.led.patterns import BreathingPattern, PulsePattern, SpinPattern
    from src.led.patterns import FirePattern, CloudPattern, DreamPattern

Pattern Categories:
- Basic: BreathingPattern, PulsePattern, SpinPattern
- Perlin Noise: FirePattern, CloudPattern, DreamPattern

Author: Boston Dynamics Animation Systems Engineer
Updated: 18 January 2026 (Perlin noise patterns added by Agent 1)
"""

from .base import PatternBase, PatternConfig, FrameMetrics, RGB
from .breathing import BreathingPattern
from .pulse import PulsePattern
from .spin import SpinPattern
from .fire import FirePattern
from .cloud import CloudPattern
from .dream import DreamPattern

PATTERN_REGISTRY = {
    # Basic patterns
    'breathing': BreathingPattern,
    'pulse': PulsePattern,
    'spin': SpinPattern,
    # Perlin noise patterns (organic movement)
    'fire': FirePattern,
    'cloud': CloudPattern,
    'dream': DreamPattern,
}

__all__ = [
    # Base classes
    'PatternBase',
    'PatternConfig',
    'FrameMetrics',
    'RGB',
    # Basic patterns
    'BreathingPattern',
    'PulsePattern',
    'SpinPattern',
    # Perlin noise patterns
    'FirePattern',
    'CloudPattern',
    'DreamPattern',
    # Registry
    'PATTERN_REGISTRY',
]
