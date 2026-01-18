"""
LED Pattern Library for OpenDuck Mini V3

Exports all pattern classes for easy import:
    from src.led.patterns import BreathingPattern, PulsePattern, SpinPattern
    from src.led.patterns import FirePattern, CloudPattern, DreamPattern
    from src.led.patterns import PlayfulPattern, AffectionatePattern, EmpatheticPattern, GratefulPattern

Pattern Categories:
- Basic: BreathingPattern, PulsePattern, SpinPattern
- Perlin Noise: FirePattern, CloudPattern, DreamPattern
- Social Emotions: PlayfulPattern, AffectionatePattern, EmpatheticPattern, GratefulPattern

Author: Boston Dynamics Animation Systems Engineer
Updated: 18 January 2026 (Social emotion patterns added by Agent 2)
"""

from .base import PatternBase, PatternConfig, FrameMetrics, RGB
from .breathing import BreathingPattern
from .pulse import PulsePattern
from .spin import SpinPattern
from .fire import FirePattern
from .cloud import CloudPattern
from .dream import DreamPattern
from .social_emotions import (
    PlayfulPattern,
    AffectionatePattern,
    EmpatheticPattern,
    GratefulPattern,
    SOCIAL_PATTERN_REGISTRY,
    SOCIAL_EMOTION_COLORS,
)

PATTERN_REGISTRY = {
    # Basic patterns
    'breathing': BreathingPattern,
    'pulse': PulsePattern,
    'spin': SpinPattern,
    # Perlin noise patterns (organic movement)
    'fire': FirePattern,
    'cloud': CloudPattern,
    'dream': DreamPattern,
    # Social emotion patterns (connection-building)
    'playful': PlayfulPattern,
    'affectionate': AffectionatePattern,
    'empathetic': EmpatheticPattern,
    'grateful': GratefulPattern,
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
    # Social emotion patterns
    'PlayfulPattern',
    'AffectionatePattern',
    'EmpatheticPattern',
    'GratefulPattern',
    'SOCIAL_PATTERN_REGISTRY',
    'SOCIAL_EMOTION_COLORS',
    # Registry
    'PATTERN_REGISTRY',
]
