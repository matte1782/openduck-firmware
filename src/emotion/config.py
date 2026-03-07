"""
Emotion Configuration for OpenDuck Mini V3

Provides configuration options for the emotion system.

Author: Boston Dynamics Emotion Engineer
Created: 22 January 2026
"""

from dataclasses import dataclass


@dataclass
class EmotionConfig:
    """Configuration for emotion state machine.

    Attributes:
        transition_duration_ms: Duration of state transitions in milliseconds
        idle_timeout_ms: Time before auto-returning to IDLE state
        default_brightness: Default LED brightness (0.0-1.0)
        max_intensity: Maximum emotion intensity (0.0-1.0)
    """
    transition_duration_ms: int = 500
    idle_timeout_ms: int = 5000
    default_brightness: float = 0.8
    max_intensity: float = 1.0

    def __post_init__(self):
        """Validate configuration values."""
        # Validate brightness
        if self.default_brightness < 0.0 or self.default_brightness > 1.0:
            raise ValueError(
                f"default_brightness must be 0.0-1.0, got {self.default_brightness}"
            )

        # Validate max_intensity
        if self.max_intensity < 0.0 or self.max_intensity > 1.0:
            raise ValueError(
                f"max_intensity must be 0.0-1.0, got {self.max_intensity}"
            )

        # Validate durations
        if self.transition_duration_ms <= 0:
            raise ValueError(
                f"transition_duration_ms must be > 0, got {self.transition_duration_ms}"
            )

        if self.idle_timeout_ms <= 0:
            raise ValueError(
                f"idle_timeout_ms must be > 0, got {self.idle_timeout_ms}"
            )
