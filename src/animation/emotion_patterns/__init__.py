#!/usr/bin/env python3
"""
Emotion Patterns Module - OpenDuck Mini V3
Week 02 | Compound Emotion Implementation

This module provides specialized LED pattern renderers for complex,
psychology-grounded emotional states beyond the 8 basic emotions.

Pattern Classes:
    - CompoundEmotionPatternBase: Base class with emotion blending
    - ConfusedPattern: Uncertain searching + flickering colors
    - SurprisedPattern: Startle spike + widening effect
    - AnxiousPattern: Nervous jitter + irregular rhythm
    - FrustratedPattern: Building tension + constrained energy
    - ProudPattern: Confident glow + elevated posture

Psychology References:
    - Plutchik's Wheel of Emotions (compound dyads)
    - Russell's Circumplex Model (arousal-valence space)
    - Ekman's Basic Emotions (surprise as universal)
    - Frustration-Aggression Hypothesis (Dollard et al. 1939)

Author: Compound Emotion Engineer (Agent 3)
Created: 18 January 2026
"""

from .compound_emotions import (
    # Base classes
    CompoundEmotionPatternBase,
    EmotionBlender,

    # Pattern implementations
    ConfusedPattern,
    SurprisedPattern,
    AnxiousPattern,
    FrustratedPattern,
    ProudPattern,

    # Emotion configurations
    COMPOUND_EMOTION_CONFIGS,
    COMPOUND_EMOTION_PRESETS,
    COMPOUND_TRANSITION_TIMES,

    # Utility functions
    blend_emotions,
    get_compound_emotion_axes,
)

__all__ = [
    # Base classes
    'CompoundEmotionPatternBase',
    'EmotionBlender',

    # Pattern implementations
    'ConfusedPattern',
    'SurprisedPattern',
    'AnxiousPattern',
    'FrustratedPattern',
    'ProudPattern',

    # Emotion configurations
    'COMPOUND_EMOTION_CONFIGS',
    'COMPOUND_EMOTION_PRESETS',
    'COMPOUND_TRANSITION_TIMES',

    # Utility functions
    'blend_emotions',
    'get_compound_emotion_axes',
]
