"""
Animation System for OpenDuck Mini V3

Provides keyframe-based animation with easing functions, emotion systems,
micro-expression support, idle behaviors, animation coordination, and
emotion bridging for lifelike robot behavior.

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
    - IdleBehavior: Background idle behaviors (blinks, glances)
    - BlinkBehavior: Eye blink animations
    - AnimationCoordinator: Layered animation priority system
    - AnimationPriority: Animation layer priorities
    - AnimationLayer: Single animation layer configuration
    - AnimationState: Snapshot of coordinator state
    - EmotionState: Core emotion state enum
    - EmotionPose: Head pose for emotions
    - EmotionExpression: Complete expression configuration
    - EmotionBridge: Bridges emotions to physical behaviors

Author: Boston Dynamics Animation Systems Engineer
Created: 18 January 2026
Updated: 18 January 2026 (Day 12 - Idle behaviors + Animation Coordinator + Emotion Bridge)
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

from .behaviors import (
    IdleBehavior,
    BlinkBehavior,
    create_idle_behavior,
    create_blink_behavior,
)

from .coordinator import (
    AnimationCoordinator,
    AnimationPriority,
    AnimationLayer,
    AnimationState,
)

from .emotion_bridge import (
    EmotionState,
    EmotionPose,
    EmotionExpression,
    EmotionBridge,
    EMOTION_POSES,
    IDLE_PARAMETERS,
    get_available_emotions,
    get_emotion_pose,
    emotion_state_to_axes,
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
    # Idle behaviors (Day 12)
    'IdleBehavior',
    'BlinkBehavior',
    'create_idle_behavior',
    'create_blink_behavior',
    # Animation Coordinator (Day 12)
    'AnimationCoordinator',
    'AnimationPriority',
    'AnimationLayer',
    'AnimationState',
    # Emotion Bridge (Day 12)
    'EmotionState',
    'EmotionPose',
    'EmotionExpression',
    'EmotionBridge',
    'EMOTION_POSES',
    'IDLE_PARAMETERS',
    'get_available_emotions',
    'get_emotion_pose',
    'emotion_state_to_axes',
]
