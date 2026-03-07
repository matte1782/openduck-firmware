"""
Emotion System for OpenDuck Mini V3

Provides emotion state management and expression through:
- LED patterns
- Servo movements
- Coordinated transitions

Author: Boston Dynamics Emotion Engineer
Created: 22 January 2026
"""

from .states import EmotionState
from .config import EmotionConfig
from .state_machine import EmotionStateMachine

__all__ = [
    'EmotionState',
    'EmotionConfig',
    'EmotionStateMachine',
]
