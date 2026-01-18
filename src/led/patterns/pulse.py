#!/usr/bin/env python3
"""
Pulse Pattern - Heartbeat double-pulse for alert/excited states

Disney Animation Principle: Anticipation + Follow-through

Double-pulse pattern mimics a realistic heartbeat:
1. Strong beat (100ms) - The "lub"
2. Short rest (100ms)
3. Weaker beat (100ms) - The "dub"
4. Long rest (700ms) - Between heartbeats

Total cycle: 1 second (60 BPM baseline, adjustable via speed)

Author: Boston Dynamics Animation Systems Engineer
Created: 18 January 2026
"""

import math
from typing import List, Optional
from .base import PatternBase, RGB, PatternConfig


class PulsePattern(PatternBase):
    """Quick heartbeat pulse - alert/excited states.

    The double-pulse creates anticipation (first beat) and follow-through
    (second, weaker beat). Speed multiplier affects heart rate:
    - speed=0.5: 30 BPM (calm)
    - speed=1.0: 60 BPM (normal)
    - speed=2.0: 120 BPM (excited/alert)
    """

    NAME = "pulse"
    DESCRIPTION = "Double-pulse heartbeat pattern for alert states"
    DEFAULT_SPEED = 1.0

    # Timing in frames at 50Hz (total cycle = 50 frames = 1 second)
    CYCLE_FRAMES = 50           # 1 second total at 50Hz
    PULSE1_START = 0            # First pulse starts at frame 0
    PULSE1_END = 5              # First pulse ends at frame 5 (100ms)
    REST1_END = 10              # Rest period ends at frame 10 (100ms rest)
    PULSE2_START = 10           # Second pulse starts
    PULSE2_END = 15             # Second pulse ends at frame 15 (100ms)
    # Frames 15-50 are long rest (700ms)

    # Intensity levels
    PULSE1_INTENSITY = 1.0      # Full intensity for first beat
    PULSE2_INTENSITY = 0.7      # Weaker second beat (follow-through)
    REST_INTENSITY = 0.3        # Baseline between beats

    def __init__(self, num_pixels: int = 16, config: Optional[PatternConfig] = None):
        """Initialize pulse pattern.

        Args:
            num_pixels: Number of LEDs (default: 16)
            config: Optional PatternConfig (speed affects heart rate)
        """
        super().__init__(num_pixels, config)

    def _compute_frame(self, base_color: RGB) -> List[RGB]:
        """Compute heartbeat pulse for current frame.

        Args:
            base_color: Base RGB color for the pulse

        Returns:
            List of RGB tuples (all pixels same intensity)
        """
        # Get frame within cycle (0 to CYCLE_FRAMES-1)
        # MEDIUM Issue #8: Use abs() to prevent signed integer arithmetic issues
        frame_in_cycle = abs(int(self._frame * self.config.speed)) % self.CYCLE_FRAMES

        # Determine intensity based on which phase we're in
        if frame_in_cycle < self.PULSE1_END:
            # First pulse (strong beat) - smooth envelope
            t = frame_in_cycle / self.PULSE1_END
            envelope = self._pulse_envelope(t)
            intensity = self.REST_INTENSITY + (self.PULSE1_INTENSITY - self.REST_INTENSITY) * envelope

        elif frame_in_cycle < self.REST1_END:
            # Rest between pulses
            intensity = self.REST_INTENSITY

        elif frame_in_cycle < self.PULSE2_END:
            # Second pulse (weaker beat) - follow-through
            t = (frame_in_cycle - self.PULSE2_START) / (self.PULSE2_END - self.PULSE2_START)
            envelope = self._pulse_envelope(t)
            intensity = self.REST_INTENSITY + (self.PULSE2_INTENSITY - self.REST_INTENSITY) * envelope

        else:
            # Long rest until next heartbeat
            intensity = self.REST_INTENSITY

        # Apply intensity to all pixels
        scaled = self._scale_color(base_color, intensity)
        for i in range(self.num_pixels):
            self._pixel_buffer[i] = scaled

        return self._pixel_buffer

    @staticmethod
    def _pulse_envelope(t: float) -> float:
        """Smooth pulse envelope (0->1->0 over t=0->1).

        Uses sine envelope for natural organic feel.

        Args:
            t: Progress through pulse (0.0 to 1.0)

        Returns:
            Envelope value (0.0 at start/end, 1.0 at peak)
        """
        return math.sin(t * math.pi)

    def get_current_intensity(self) -> float:
        """Get current intensity (for debugging/testing).

        Returns:
            Current intensity value
        """
        # MEDIUM Issue #8: Use abs() to prevent signed integer arithmetic issues
        frame_in_cycle = abs(int(self._frame * self.config.speed)) % self.CYCLE_FRAMES

        if frame_in_cycle < self.PULSE1_END:
            t = frame_in_cycle / self.PULSE1_END
            envelope = self._pulse_envelope(t)
            return self.REST_INTENSITY + (self.PULSE1_INTENSITY - self.REST_INTENSITY) * envelope
        elif frame_in_cycle < self.REST1_END:
            return self.REST_INTENSITY
        elif frame_in_cycle < self.PULSE2_END:
            t = (frame_in_cycle - self.PULSE2_START) / (self.PULSE2_END - self.PULSE2_START)
            envelope = self._pulse_envelope(t)
            return self.REST_INTENSITY + (self.PULSE2_INTENSITY - self.REST_INTENSITY) * envelope
        else:
            return self.REST_INTENSITY

    def get_heart_rate_bpm(self) -> float:
        """Get effective heart rate in BPM based on speed setting.

        Returns:
            Heart rate in beats per minute
        """
        return 60 * self.config.speed
