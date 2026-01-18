#!/usr/bin/env python3
"""
Spin Pattern - Rotating comet with tail for thinking/processing states

Disney Animation Principle: Arc (movement follows curves, not straight lines)

Creates a "thinking" indicator with a bright head and fading tail
that rotates around the ring. Speed indicates processing intensity.

Author: Boston Dynamics Animation Systems Engineer
Created: 18 January 2026
"""

from typing import List, Optional
from .base import PatternBase, RGB, PatternConfig


class SpinPattern(PatternBase):
    """Rotating comet pattern - thinking/processing state.

    The comet head is brightest, with a trail of decreasing brightness
    behind it. Rotation direction indicates:
    - Clockwise (default): Normal processing
    - Counter-clockwise (reverse=True): Error/issue state

    Rotation speed indicates processing intensity.
    """

    NAME = "spin"
    DESCRIPTION = "Rotating comet pattern for thinking/processing"
    DEFAULT_SPEED = 1.0

    # Spin parameters
    CYCLE_FRAMES = 32           # ~0.64 seconds per rotation at 50Hz
    TAIL_LENGTH = 4             # Number of pixels in the comet tail
    HEAD_INTENSITY = 1.0        # Full brightness at head
    TAIL_DECAY = 0.6            # Each tail pixel is 60% of previous
    BACKGROUND_INTENSITY = 0.1  # Subtle background glow (10%)

    def __init__(self, num_pixels: int = 16, config: Optional[PatternConfig] = None):
        """Initialize spin pattern.

        Args:
            num_pixels: Number of LEDs (default: 16)
            config: Optional PatternConfig (speed affects rotation speed)
        """
        super().__init__(num_pixels, config)

    def _compute_frame(self, base_color: RGB) -> List[RGB]:
        """Compute spinning comet for current frame.

        Args:
            base_color: Base RGB color for the comet

        Returns:
            List of RGB tuples with comet head and tail
        """
        # Get head position (0 to num_pixels-1)
        progress = self.get_progress(self.CYCLE_FRAMES)
        head_pos = int(progress * self.num_pixels) % self.num_pixels

        # Initialize all pixels with background glow
        background = self._scale_color(base_color, self.BACKGROUND_INTENSITY)
        for i in range(self.num_pixels):
            self._pixel_buffer[i] = background

        # Draw comet: head + fading tail
        intensity = self.HEAD_INTENSITY
        for i in range(self.TAIL_LENGTH):
            # Calculate pixel position (wrapping around ring)
            pos = (head_pos - i) % self.num_pixels

            # Set pixel with current intensity
            self._pixel_buffer[pos] = self._scale_color(base_color, intensity)

            # Decay intensity for next tail pixel
            intensity *= self.TAIL_DECAY

        return self._pixel_buffer

    def get_head_position(self) -> int:
        """Get current head position (for debugging/testing).

        Returns:
            Pixel index of comet head (0 to num_pixels-1)
        """
        progress = self.get_progress(self.CYCLE_FRAMES)
        return int(progress * self.num_pixels) % self.num_pixels

    def get_rotation_speed_rps(self) -> float:
        """Get effective rotation speed in rotations per second.

        Returns:
            Rotations per second
        """
        # CYCLE_FRAMES at 50Hz = CYCLE_FRAMES/50 seconds per rotation
        base_rps = 50 / self.CYCLE_FRAMES  # ~1.56 RPS at default
        return base_rps * self.config.speed
