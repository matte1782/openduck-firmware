#!/usr/bin/env python3
"""
Breathing Pattern - Slow sine wave brightness for idle/calm states

Disney Animation Principle: Timing (slow = calm, fast = anxious)

Creates the illusion of a living, breathing entity through subtle
brightness variations. The breath cycle is tuned to match comfortable
human breathing rates (4 seconds per cycle).

Author: Boston Dynamics Animation Systems Engineer
Created: 18 January 2026
"""

import math
import threading
from typing import List, Optional
from .base import PatternBase, RGB, PatternConfig


class BreathingPattern(PatternBase):
    """Slow sine wave brightness - the pulse of life.

    Performance: Uses pre-computed sine lookup table for O(1) brightness
    calculation. Target render time: <1ms at 50Hz.
    """

    NAME = "breathing"
    DESCRIPTION = "Slow sine wave brightness for idle/calm states"
    DEFAULT_SPEED = 1.0

    # Breathing parameters
    CYCLE_FRAMES = 200          # 4 seconds at 50Hz (comfortable breathing rate)
    MIN_INTENSITY = 0.3         # Never fully dim (30% - looks dead if too dim)
    MAX_INTENSITY = 1.0         # Full brightness at peak

    # Pre-computed sine table for performance (256 entries)
    _SINE_LUT: List[float] = []
    _LUT_LOCK = threading.Lock()  # MEDIUM Issue #1: Race condition protection
    _LUT_SIZE = 256
    _LUT_INITIALIZED = False

    def __init__(self, num_pixels: int = 16, config: Optional[PatternConfig] = None):
        """Initialize breathing pattern with optional config.

        Args:
            num_pixels: Number of LEDs (default: 16)
            config: Optional PatternConfig
        """
        super().__init__(num_pixels, config)
        self._init_sine_lut()

    @classmethod
    def _init_sine_lut(cls):
        """Initialize sine lookup table (once per class, not per instance).

        MEDIUM Issue #1: Thread-safe initialization with lock.
        """
        with cls._LUT_LOCK:
            if cls._LUT_INITIALIZED:
                return

            # Pre-compute 256 sine values (covers one full cycle)
            # Maps 0-255 to sine wave normalized to 0.0-1.0
            cls._SINE_LUT = [
                (math.sin(i / cls._LUT_SIZE * 2 * math.pi) + 1) / 2
                for i in range(cls._LUT_SIZE)
            ]
            cls._LUT_INITIALIZED = True

    def _compute_frame(self, base_color: RGB) -> List[RGB]:
        """Compute breathing brightness for current frame.

        Args:
            base_color: Base RGB color for the breath

        Returns:
            List of RGB tuples (all pixels same brightness)
        """
        # Get normalized progress through cycle (0.0-1.0)
        progress = self.get_progress(self.CYCLE_FRAMES)

        # Look up sine value (O(1) vs math.sin O(n) for trig)
        lut_index = int(progress * (self._LUT_SIZE - 1)) % self._LUT_SIZE
        breath = self._SINE_LUT[lut_index]

        # Scale to min/max intensity range
        # breath=0 -> MIN_INTENSITY, breath=1 -> MAX_INTENSITY
        intensity = self.MIN_INTENSITY + breath * (self.MAX_INTENSITY - self.MIN_INTENSITY)

        # Apply intensity to base color and fill all pixels
        scaled = self._scale_color(base_color, intensity)
        for i in range(self.num_pixels):
            self._pixel_buffer[i] = scaled

        return self._pixel_buffer

    def get_current_intensity(self) -> float:
        """Get current brightness intensity (for debugging/testing).

        Returns:
            Current intensity value (MIN_INTENSITY to MAX_INTENSITY)
        """
        progress = self.get_progress(self.CYCLE_FRAMES)
        lut_index = int(progress * (self._LUT_SIZE - 1)) % self._LUT_SIZE
        breath = self._SINE_LUT[lut_index]
        return self.MIN_INTENSITY + breath * (self.MAX_INTENSITY - self.MIN_INTENSITY)
