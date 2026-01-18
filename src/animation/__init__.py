"""
Animation System for OpenDuck Mini V3

Provides keyframe-based animation with easing functions, emotion systems,
and micro-expression support for lifelike robot behavior.

Exports:
    - Keyframe: Single animation keyframe
    - AnimationSequence: Collection of keyframes
    - AnimationPlayer: Real-time playback controller
    - Easing functions: ease, ease_in, ease_out, ease_in_out, ease_linear
    - EmotionAxes: 4-axis continuous emotion representation (Pixar system)
    - EMOTION_PRESETS: Predefined emotion configurations
    - MicroExpressionType: Types of micro-expressions
    - MicroExpression: Configuration for a single micro-expression
    - MicroExpressionEngine: Manages and triggers micro-expressions
    - MICRO_EXPRESSION_PRESETS: Predefined micro-expression configurations

Author: Boston Dynamics Animation Systems Engineer
Created: 18 January 2026
Updated: 18 January 2026 (Day 10 - Micro-expressions)
"""

from .easing import (
    ease,
    ease_linear,
    ease_in,
    ease_out,
    ease_in_out,
    EASING_FUNCTIONS,
    EASING_LUTS,
)

from .timing import (
    Keyframe,
    AnimationSequence,
    AnimationPlayer,
)

from .emotion_axes import (
    EmotionAxes,
    EMOTION_PRESETS,
)

from .micro_expressions import (
    MicroExpressionType,
    MicroExpression,
    MicroExpressionEngine,
    MICRO_EXPRESSION_PRESETS,
    get_preset_names,
    get_preset,
)

__all__ = [
    # Easing
    'ease',
    'ease_linear',
    'ease_in',
    'ease_out',
    'ease_in_out',
    'EASING_FUNCTIONS',
    'EASING_LUTS',
    # Timing
    'Keyframe',
    'AnimationSequence',
    'AnimationPlayer',
    # Emotion Axes (Pixar 4-axis system)
    'EmotionAxes',
    'EMOTION_PRESETS',
    # Micro-expressions
    'MicroExpressionType',
    'MicroExpression',
    'MicroExpressionEngine',
    'MICRO_EXPRESSION_PRESETS',
    'get_preset_names',
    'get_preset',
]
