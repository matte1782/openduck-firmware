"""
Emotion States for OpenDuck Mini V3

Defines the core emotion states that the robot can express.

Author: Boston Dynamics Emotion Engineer
Created: 22 January 2026
"""

from enum import Enum, auto


class EmotionState(Enum):
    """Core emotion states for OpenDuck Mini V3.

    Each state maps to:
    - LED pattern (breathing, pulse, spin, etc.)
    - LED color
    - Servo position/sequence
    - Animation speed

    States:
        IDLE: Default calm state (breathing pattern, soft blue)
        HAPPY: Positive response (pulse pattern, warm yellow)
        THINKING: Processing/working (spin pattern, cool blue)
        ALERT: Attention needed (fast pulse, orange/red)
        ERROR: Error condition (rapid pulse, red)
    """
    IDLE = auto()
    HAPPY = auto()
    THINKING = auto()
    ALERT = auto()
    ERROR = auto()

    def __str__(self) -> str:
        """Return human-readable string representation."""
        return f"EmotionState.{self.name}"

    def __repr__(self) -> str:
        """Return detailed string representation."""
        return f"<EmotionState.{self.name}: {self.value}>"
