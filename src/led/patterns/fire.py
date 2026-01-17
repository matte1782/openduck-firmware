#!/usr/bin/env python3
"""
Fire Pattern - SPECTACULAR Traveling Flame Animation
OpenDuck Mini V3 | Week 02 Day 9 (REDESIGNED)

Creates dramatic fire effect with:
- Multiple traveling flame hotspots with comet-like tails
- Dark embers contrasting with bright flame peaks
- Organic movement using Perlin noise modulation
- ACTUAL VISUAL MOVEMENT - not just brightness modulation!

Performance: Target avg <2ms, max <15ms per frame

Author: Engineering Council Redesign
Created: 17 January 2026
"""

import math
import random
from typing import List, Optional, Tuple

from noise import pnoise2

from .base import PatternBase, PatternConfig, RGB


class FirePattern(PatternBase):
    """Spectacular fire effect with traveling flame hotspots.

    Creates dramatic, visually impressive fire animation by combining:
    1. Multiple flame "comets" that travel around the ring
    2. Exponential decay tails for natural flame appearance
    3. Perlin noise for organic flickering overlay
    4. Dark embers as background for maximum contrast
    """

    NAME = "fire"
    DESCRIPTION = "Spectacular traveling flames with comet tails"
    DEFAULT_SPEED = 1.0

    # === FLAME HOTSPOT PARAMETERS ===
    NUM_FLAMES = 3              # Number of flame hotspots traveling around
    FLAME_TAIL_LENGTH = 5       # LEDs in the comet tail
    FLAME_DECAY = 0.55          # Exponential decay factor (lower = faster fade)
    FLAME_HEAD_BRIGHTNESS = 1.0 # Full brightness at flame head

    # Flame travel speeds (different for organic feel)
    FLAME_SPEEDS = [1.0, 0.7, 1.3]  # Relative speeds for each flame
    FLAME_CYCLE_FRAMES = 40     # Frames for one complete rotation (at speed 1.0)

    # === EMBER BACKGROUND ===
    EMBER_MIN = 0.02            # Very dark embers
    EMBER_MAX = 0.15            # Subtle ember glow
    EMBER_FLICKER_SPEED = 0.08  # Perlin time scale for ember flicker

    # === NOISE OVERLAY ===
    NOISE_SCALE = 0.5           # Spatial frequency
    NOISE_AMPLITUDE = 0.15      # How much noise affects brightness
    NOISE_TIME_SCALE = 0.12     # Animation speed

    # === COLOR MODULATION ===
    # Fire colors: bright flames are yellow-white, tails are orange-red
    HEAD_COLOR_MULT = (1.0, 0.9, 0.4)   # Yellow-white at head
    TAIL_COLOR_MULT = (1.2, 0.5, 0.1)   # Deep orange-red in tail
    EMBER_COLOR_MULT = (1.0, 0.3, 0.05) # Dark red embers

    def __init__(self, num_pixels: int = 16, config: Optional[PatternConfig] = None):
        super().__init__(num_pixels, config)

        # Initialize flame positions with random starting points
        self._rng = random.Random(42)  # Seeded for reproducibility
        self._flame_offsets = [
            self._rng.uniform(0, 1.0) for _ in range(self.NUM_FLAMES)
        ]

        # Pre-compute LED positions for noise sampling
        self._angle_step = (2 * math.pi) / self.num_pixels
        self._led_positions: List[Tuple[float, float]] = []
        for i in range(self.num_pixels):
            angle = i * self._angle_step
            x = math.cos(angle) * self.NOISE_SCALE
            y = math.sin(angle) * self.NOISE_SCALE
            self._led_positions.append((x, y))

    def _get_flame_position(self, flame_idx: int) -> float:
        """Get current position of a flame hotspot (0.0 to 1.0 around ring)."""
        speed = self.FLAME_SPEEDS[flame_idx % len(self.FLAME_SPEEDS)]
        offset = self._flame_offsets[flame_idx]

        # Calculate position based on frame, speed, and offset
        progress = (self._frame * self.config.speed * speed / self.FLAME_CYCLE_FRAMES) + offset
        return progress % 1.0

    def _calculate_flame_contribution(self, led_idx: int, flame_pos: float) -> float:
        """Calculate brightness contribution from a flame at given position.

        Uses exponential decay for comet-like tail effect.
        """
        # Convert flame position (0-1) to LED index
        flame_led = flame_pos * self.num_pixels

        # Calculate circular distance (how far behind the flame head)
        distance = (flame_led - led_idx) % self.num_pixels

        # Only contribute if within tail length
        if distance < self.FLAME_TAIL_LENGTH:
            # Exponential decay: head is brightest, tail fades
            intensity = self.FLAME_HEAD_BRIGHTNESS * (self.FLAME_DECAY ** distance)
            return intensity

        return 0.0

    def _get_ember_brightness(self, led_idx: int, time_offset: float) -> float:
        """Get flickering ember brightness using Perlin noise."""
        x, y = self._led_positions[led_idx]

        noise_val = pnoise2(
            x + time_offset * self.EMBER_FLICKER_SPEED,
            y + time_offset * self.EMBER_FLICKER_SPEED * 0.7,
            octaves=2,
            persistence=0.5,
            lacunarity=2.0,
            repeatx=1024,
            repeaty=1024,
        )

        # Map noise (-1, 1) to ember brightness range
        return self.EMBER_MIN + (noise_val + 1) * 0.5 * (self.EMBER_MAX - self.EMBER_MIN)

    def _compute_frame(self, base_color: RGB) -> List[RGB]:
        """Compute spectacular fire effect with traveling flames."""
        time_offset = (self._frame * self.config.speed) % 10000.0

        for i in range(self.num_pixels):
            # Start with dark ember background
            ember_brightness = self._get_ember_brightness(i, time_offset)

            # Calculate total flame contribution from all flame hotspots
            flame_brightness = 0.0
            flame_position_factor = 0.0  # Track how close to flame head (for color)

            for flame_idx in range(self.NUM_FLAMES):
                flame_pos = self._get_flame_position(flame_idx)
                contribution = self._calculate_flame_contribution(i, flame_pos)

                if contribution > flame_brightness:
                    # Track position for color blending
                    flame_led = flame_pos * self.num_pixels
                    distance = (flame_led - i) % self.num_pixels
                    flame_position_factor = 1.0 - (distance / self.FLAME_TAIL_LENGTH)

                flame_brightness = max(flame_brightness, contribution)

            # Add subtle noise overlay for organic feel
            x, y = self._led_positions[i]
            noise_val = pnoise2(
                x + time_offset * self.NOISE_TIME_SCALE,
                y + time_offset * self.NOISE_TIME_SCALE * 0.5,
                octaves=2,
                persistence=0.5,
                lacunarity=2.0,
                repeatx=1024,
                repeaty=1024,
            )
            noise_mod = 1.0 + noise_val * self.NOISE_AMPLITUDE

            # Combine ember and flame brightness
            total_brightness = max(ember_brightness, flame_brightness * noise_mod)
            total_brightness = max(0.0, min(1.0, total_brightness))

            # Color blending: head is yellow-white, tail is orange-red, embers are dark red
            if flame_brightness > ember_brightness:
                # Blend between head and tail color based on position
                t = max(0.0, min(1.0, flame_position_factor))
                r_mult = self.TAIL_COLOR_MULT[0] + t * (self.HEAD_COLOR_MULT[0] - self.TAIL_COLOR_MULT[0])
                g_mult = self.TAIL_COLOR_MULT[1] + t * (self.HEAD_COLOR_MULT[1] - self.TAIL_COLOR_MULT[1])
                b_mult = self.TAIL_COLOR_MULT[2] + t * (self.HEAD_COLOR_MULT[2] - self.TAIL_COLOR_MULT[2])
            else:
                # Ember color
                r_mult, g_mult, b_mult = self.EMBER_COLOR_MULT

            # Apply color modulation
            r = int(min(255, base_color[0] * total_brightness * r_mult))
            g = int(min(255, base_color[1] * total_brightness * g_mult))
            b = int(min(255, base_color[2] * total_brightness * b_mult))

            self._pixel_buffer[i] = (r, g, b)

        return self._pixel_buffer

    def get_current_noise_values(self) -> List[float]:
        """Get raw noise values for debugging."""
        time_offset = (self._frame * self.config.speed) % 10000.0
        values = []
        for i in range(self.num_pixels):
            x, y = self._led_positions[i]
            noise_val = pnoise2(
                x + time_offset * self.NOISE_TIME_SCALE,
                y + time_offset * self.NOISE_TIME_SCALE * 0.5,
                octaves=2, persistence=0.5, lacunarity=2.0,
                repeatx=1024, repeaty=1024,
            )
            values.append(noise_val)
        return values

    def get_flicker_rate(self) -> float:
        """Get effective flicker rate."""
        return 50 * self.NOISE_TIME_SCALE * self.config.speed
