#!/usr/bin/env python3
"""
AURORA Pattern - Northern Lights Multi-Band Animation
OpenDuck Mini V3 | Week 02 Day 9 (FINAL REDESIGN)

Boston Dynamics / Google DeepMind Robotics Quality

Creates stunning aurora borealis effect with:
- 3 color bands (green, cyan, magenta) traveling at different speeds
- Breathing amplitude modulation for organic pulsing
- Traveling bright pulses that sweep around the ring
- Additive color blending for ethereal glow
- Deep darkness (near-black) for maximum contrast

Performance: Target avg <2ms, max <15ms per frame

Author: Animation Designer - Engineering Council
Created: 17 January 2026
"""

import math
import random
from dataclasses import dataclass
from typing import List, Optional, Tuple

from noise import pnoise2

from .base import PatternBase, PatternConfig, RGB


@dataclass
class AuroraPulse:
    """Traveling bright pulse."""
    position: float  # 0-1 around ring
    speed: float     # How fast it travels
    width: float     # How wide the pulse is
    intensity: float # Peak brightness


class DreamPattern(PatternBase):
    """AURORA: Northern Lights with traveling color bands.

    Creates breathtaking aurora effect by combining:
    1. Three color bands (green/cyan/magenta) at different speeds
    2. Global breathing modulation for organic feel
    3. Traveling bright pulses that sweep the ring
    4. Additive RGB blending for ethereal color mixing
    """

    NAME = "dream"  # Keep name for compatibility
    DESCRIPTION = "Northern lights with traveling color bands"
    DEFAULT_SPEED = 1.0

    # === COLOR BAND SYSTEM ===
    # Band 1: Green aurora (classic)
    BAND1_COLOR = (0.2, 1.0, 0.3)    # Bright green
    BAND1_SPEED = 1.0                 # Base speed
    BAND1_WIDTH = 0.4                 # Fraction of ring
    BAND1_INTENSITY = 0.7

    # Band 2: Cyan transition
    BAND2_COLOR = (0.1, 0.9, 1.0)    # Cyan
    BAND2_SPEED = 1.3                 # Slightly faster
    BAND2_WIDTH = 0.35
    BAND2_INTENSITY = 0.6

    # Band 3: Magenta highlights
    BAND3_COLOR = (1.0, 0.2, 0.8)    # Magenta/pink
    BAND3_SPEED = 0.7                 # Slower for contrast
    BAND3_WIDTH = 0.25
    BAND3_INTENSITY = 0.5

    BAND_CYCLE_FRAMES = 60           # Frames per complete band cycle

    # === BREATHING MODULATION ===
    BREATH_CYCLE_FRAMES = 100        # 2 seconds at 50Hz
    BREATH_MIN = 0.4                 # Minimum amplitude multiplier
    BREATH_MAX = 1.0                 # Maximum amplitude multiplier

    # === TRAVELING PULSE SYSTEM ===
    MAX_PULSES = 2
    PULSE_SPAWN_CHANCE = 0.03        # 3% per frame
    PULSE_MIN_SPEED = 0.05
    PULSE_MAX_SPEED = 0.12
    PULSE_WIDTH = 0.15               # Narrow bright pulse
    PULSE_INTENSITY = 0.8

    # === BRIGHTNESS RANGE ===
    MIN_BRIGHTNESS = 0.02            # Near black sky
    MAX_BRIGHTNESS = 1.0             # Brilliant aurora peak
    BASE_BRIGHTNESS = 0.05           # Very dark base

    # === NOISE SHIMMER ===
    NOISE_AMPLITUDE = 0.15
    NOISE_TIME_SCALE = 0.08

    def __init__(self, num_pixels: int = 16, config: Optional[PatternConfig] = None):
        super().__init__(num_pixels, config)

        # Validate BREATH_CYCLE_FRAMES to prevent division by zero
        if self.BREATH_CYCLE_FRAMES <= 0:
            raise ValueError(f"BREATH_CYCLE_FRAMES must be positive, got {self.BREATH_CYCLE_FRAMES}")

        self._rng = random.Random(321)
        self._active_pulses: List[AuroraPulse] = []

        # Pre-compute LED angles
        self._led_angles = [i / num_pixels for i in range(num_pixels)]

        # Band positions (0-1 around ring)
        self._band_positions = [0.0, 0.33, 0.67]

    def _get_breath_multiplier(self) -> float:
        """Get current breathing amplitude multiplier."""
        progress = self.get_progress(self.BREATH_CYCLE_FRAMES)
        # Smooth sine breathing
        breath = (math.sin(progress * 2 * math.pi) + 1) * 0.5
        return self.BREATH_MIN + breath * (self.BREATH_MAX - self.BREATH_MIN)

    def _calculate_band_contribution(self, led_pos: float, band_center: float,
                                      band_width: float, intensity: float) -> float:
        """Calculate how much a color band contributes to this LED.

        Uses smooth gaussian-like falloff from band center.
        """
        # Circular distance (0-0.5 max)
        dist = abs(led_pos - band_center)
        if dist > 0.5:
            dist = 1.0 - dist

        # Gaussian falloff
        half_width = band_width / 2
        if dist < half_width:
            # Inside the band
            falloff = math.cos((dist / half_width) * math.pi / 2)
            return intensity * falloff
        return 0.0

    def _update_pulses(self):
        """Update traveling pulses - move existing, spawn new."""
        # Move existing pulses
        for pulse in self._active_pulses:
            pulse.position = (pulse.position + pulse.speed * self.config.speed) % 1.0

        # Remove pulses that have completed a full cycle (optional cleanup)
        # For now, keep them traveling

        # Maybe spawn new pulse
        if (len(self._active_pulses) < self.MAX_PULSES
                and self._rng.random() < self.PULSE_SPAWN_CHANCE):
            self._active_pulses.append(AuroraPulse(
                position=self._rng.random(),
                speed=self._rng.uniform(self.PULSE_MIN_SPEED, self.PULSE_MAX_SPEED),
                width=self.PULSE_WIDTH,
                intensity=self.PULSE_INTENSITY
            ))

        # Limit total pulses
        if len(self._active_pulses) > self.MAX_PULSES:
            self._active_pulses = self._active_pulses[-self.MAX_PULSES:]

    def _get_pulse_brightness(self, led_pos: float) -> float:
        """Get brightness contribution from all active pulses."""
        total = 0.0
        for pulse in self._active_pulses:
            dist = abs(led_pos - pulse.position)
            if dist > 0.5:
                dist = 1.0 - dist

            if dist < pulse.width / 2:
                # Smooth pulse shape
                t = dist / (pulse.width / 2)
                contribution = pulse.intensity * (1.0 - t * t)  # Quadratic falloff
                total += contribution

        return min(1.0, total)

    def _compute_frame(self, base_color: RGB) -> List[RGB]:
        """Compute stunning aurora effect."""
        time = self._frame * self.config.speed
        breath = self._get_breath_multiplier()

        # Update band positions (traveling)
        band1_pos = (time * self.BAND1_SPEED * 0.01) % 1.0
        band2_pos = (time * self.BAND2_SPEED * 0.01 + 0.33) % 1.0
        band3_pos = (time * self.BAND3_SPEED * 0.01 + 0.67) % 1.0

        # Update pulses
        self._update_pulses()

        for i in range(self.num_pixels):
            led_pos = self._led_angles[i]

            # Calculate each band's contribution
            b1 = self._calculate_band_contribution(
                led_pos, band1_pos, self.BAND1_WIDTH, self.BAND1_INTENSITY
            )
            b2 = self._calculate_band_contribution(
                led_pos, band2_pos, self.BAND2_WIDTH, self.BAND2_INTENSITY
            )
            b3 = self._calculate_band_contribution(
                led_pos, band3_pos, self.BAND3_WIDTH, self.BAND3_INTENSITY
            )

            # Get pulse brightness
            pulse = self._get_pulse_brightness(led_pos)

            # Apply breathing modulation
            b1 *= breath
            b2 *= breath
            b3 *= breath

            # Add noise shimmer
            noise_val = pnoise2(
                math.cos(led_pos * 2 * math.pi) * 0.5 + time * self.NOISE_TIME_SCALE,
                math.sin(led_pos * 2 * math.pi) * 0.5 + time * self.NOISE_TIME_SCALE * 0.7,
                octaves=2,
                persistence=0.5,
                lacunarity=2.0,
                repeatx=1024,
                repeaty=1024,
            )
            noise_mod = 1.0 + noise_val * self.NOISE_AMPLITUDE

            # ADDITIVE color blending (key to aurora look)
            r = (b1 * self.BAND1_COLOR[0] +
                 b2 * self.BAND2_COLOR[0] +
                 b3 * self.BAND3_COLOR[0])
            g = (b1 * self.BAND1_COLOR[1] +
                 b2 * self.BAND2_COLOR[1] +
                 b3 * self.BAND3_COLOR[1])
            b = (b1 * self.BAND1_COLOR[2] +
                 b2 * self.BAND2_COLOR[2] +
                 b3 * self.BAND3_COLOR[2])

            # Add pulse (white-ish boost)
            r += pulse * 0.8
            g += pulse * 0.9
            b += pulse * 1.0

            # Apply noise modulation
            r *= noise_mod
            g *= noise_mod
            b *= noise_mod

            # Add base brightness and clamp
            total_brightness = max(b1, b2, b3, pulse)
            if total_brightness < 0.1:
                # In dark areas, add subtle base glow
                r = max(r, self.BASE_BRIGHTNESS * 0.1)
                g = max(g, self.BASE_BRIGHTNESS * 0.3)
                b = max(b, self.BASE_BRIGHTNESS * 0.2)

            # Scale to 0-255 and apply base color influence
            r_out = int(min(255, max(0, r * base_color[0])))
            g_out = int(min(255, max(0, g * base_color[1])))
            b_out = int(min(255, max(0, b * base_color[2])))

            self._pixel_buffer[i] = (r_out, g_out, b_out)

        return self._pixel_buffer

    def get_current_breath_phase(self) -> float:
        """Get current position in breath cycle (0.0 to 1.0)."""
        return self.get_progress(self.BREATH_CYCLE_FRAMES)

    def get_breath_cycle_duration(self) -> float:
        """Get breath cycle duration in seconds."""
        if self.config.speed <= 0:
            raise ValueError(f"config.speed must be positive, got {self.config.speed}")
        return self.BREATH_CYCLE_FRAMES / 50 / self.config.speed

    def get_drift_rate(self) -> float:
        """Get effective band drift rate."""
        return 50 / self.BAND_CYCLE_FRAMES * self.config.speed

    def get_active_pulse_count(self) -> int:
        """Get number of currently active pulses."""
        return len(self._active_pulses)
