#!/usr/bin/env python3
"""
OCEAN Pattern - Pacifica-Inspired 4-Layer Wave System
OpenDuck Mini V3 | Week 02 Day 9 (FINAL REDESIGN)

Boston Dynamics / Google DeepMind Robotics Quality

Inspired by FastLED's legendary Pacifica algorithm:
- 4 independent wave layers at different frequencies
- Counter-rotating waves create mesmerizing interference
- beatsin16()-style smooth modulation
- Whitecap highlights where waves constructively interfere
- Deep ocean depths for maximum contrast

Performance: Target avg <2ms, max <15ms per frame

Author: Animation Designer - Engineering Council
Created: 17 January 2026
"""

import math
import random
from typing import List, Optional, Tuple

try:
    from noise import pnoise2
except (ImportError, ModuleNotFoundError):
    # Fallback to pure Python implementation
    try:
        from src.noise import pnoise2
    except ImportError:
        from perlin_noise import PerlinNoise
        import functools
        
        @functools.lru_cache(maxsize=4)
        def _get_noise(octaves):
            return PerlinNoise(octaves=octaves)
        
        def pnoise2(x, y, octaves=1, persistence=0.5, lacunarity=2.0, repeatx=1024, repeaty=1024, base=0):
            noise_gen = _get_noise(octaves)
            return noise_gen([x, y])

from .base import PatternBase, PatternConfig, RGB


class CloudPattern(PatternBase):
    """OCEAN: Pacifica-inspired 4-layer wave interference.

    Creates stunning ocean wave effect by combining:
    1. Four wave layers at prime-ratio frequencies (no repetition)
    2. Counter-rotating directions for dynamic interference
    3. Whitecap system where waves constructively align
    4. Deep ocean floor (near-black) for maximum contrast
    """

    NAME = "cloud"  # Keep name for compatibility
    DESCRIPTION = "Pacifica-inspired ocean waves with whitecaps"
    DEFAULT_SPEED = 1.0

    # === FOUR-LAYER WAVE SYSTEM (Pacifica-inspired) ===
    # Layer 1: Deep slow swell
    WAVE1_FREQ = 1.0            # Base frequency
    WAVE1_AMPLITUDE = 0.30
    WAVE1_DIRECTION = 1         # Clockwise
    WAVE1_PHASE_OFFSET = 0.0

    # Layer 2: Medium counter-wave
    WAVE2_FREQ = 1.618          # Golden ratio - never repeats with wave1
    WAVE2_AMPLITUDE = 0.25
    WAVE2_DIRECTION = -1        # Counter-clockwise
    WAVE2_PHASE_OFFSET = 0.33

    # Layer 3: Fast surface ripple
    WAVE3_FREQ = 2.236          # sqrt(5) - irrational, organic
    WAVE3_AMPLITUDE = 0.20
    WAVE3_DIRECTION = 1
    WAVE3_PHASE_OFFSET = 0.67

    # Layer 4: Ultra-fast shimmer
    WAVE4_FREQ = 3.14159        # Pi - irrational
    WAVE4_AMPLITUDE = 0.12
    WAVE4_DIRECTION = -1
    WAVE4_PHASE_OFFSET = 0.5

    WAVE_CYCLE_FRAMES = 50      # Faster base cycle for visible motion

    # === BRIGHTNESS RANGE (Deep contrast) ===
    MIN_BRIGHTNESS = 0.02       # Deep ocean floor - near black
    MAX_BRIGHTNESS = 1.0        # Whitecap peaks
    BASE_BRIGHTNESS = 0.08      # Low base for maximum dynamic range

    # === WHITECAP SYSTEM ===
    WHITECAP_THRESHOLD = 0.75   # When combined waves exceed this, add whitecap
    WHITECAP_BOOST = 0.35       # Extra brightness for whitecaps
    WHITECAP_FADE = 0.85        # How fast whitecaps fade

    # === COLOR PALETTE (Ocean) ===
    DEEP_COLOR = (0.1, 0.3, 0.8)     # Deep blue
    MID_COLOR = (0.2, 0.6, 0.9)      # Mid ocean
    SURFACE_COLOR = (0.4, 0.8, 1.0)  # Bright surface
    WHITECAP_COLOR = (0.9, 0.95, 1.0) # Near-white foam

    def __init__(self, num_pixels: int = 16, config: Optional[PatternConfig] = None):
        super().__init__(num_pixels, config)

        self._rng = random.Random(789)
        self._whitecap_state = [0.0] * num_pixels

        # Pre-compute LED angles
        self._led_angles = [
            (i / num_pixels) * 2 * math.pi for i in range(num_pixels)
        ]

    def _beatsin(self, bpm: float, low: float, high: float, time_offset: float, phase: float) -> float:
        """Emulate FastLED's beatsin16 - smooth oscillation.

        Args:
            bpm: Beats per minute (wave frequency)
            low: Minimum output value
            high: Maximum output value
            time_offset: Current time position
            phase: Phase offset (0-1)
        """
        # Convert to radians with phase
        angle = (time_offset * bpm / 60.0 + phase) * 2 * math.pi
        # Smooth sine oscillation mapped to range
        wave = (math.sin(angle) + 1) * 0.5
        return low + wave * (high - low)

    def _calculate_wave_layer(self, led_idx: int, freq: float, amplitude: float,
                               direction: int, phase_offset: float, time: float) -> float:
        """Calculate single wave layer contribution."""
        spatial = self._led_angles[led_idx]
        temporal = time * freq * direction * 0.1  # Scale for visible speed

        wave = math.sin(spatial * 2 + temporal + phase_offset * 2 * math.pi)
        return (wave + 1) * 0.5 * amplitude

    def _compute_frame(self, base_color: RGB) -> List[RGB]:
        """Compute Pacifica-inspired ocean effect."""
        time = self._frame * self.config.speed

        for i in range(self.num_pixels):
            # Calculate all four wave layers
            w1 = self._calculate_wave_layer(
                i, self.WAVE1_FREQ, self.WAVE1_AMPLITUDE,
                self.WAVE1_DIRECTION, self.WAVE1_PHASE_OFFSET, time
            )
            w2 = self._calculate_wave_layer(
                i, self.WAVE2_FREQ, self.WAVE2_AMPLITUDE,
                self.WAVE2_DIRECTION, self.WAVE2_PHASE_OFFSET, time
            )
            w3 = self._calculate_wave_layer(
                i, self.WAVE3_FREQ, self.WAVE3_AMPLITUDE,
                self.WAVE3_DIRECTION, self.WAVE3_PHASE_OFFSET, time
            )
            w4 = self._calculate_wave_layer(
                i, self.WAVE4_FREQ, self.WAVE4_AMPLITUDE,
                self.WAVE4_DIRECTION, self.WAVE4_PHASE_OFFSET, time
            )

            # Combine waves
            wave_total = w1 + w2 + w3 + w4

            # Whitecap detection and update
            if wave_total > self.WHITECAP_THRESHOLD:
                self._whitecap_state[i] = min(1.0,
                    self._whitecap_state[i] + self.WHITECAP_BOOST
                )
            else:
                self._whitecap_state[i] *= self.WHITECAP_FADE

            whitecap = self._whitecap_state[i]

            # Calculate brightness
            brightness = self.BASE_BRIGHTNESS + wave_total
            brightness = max(self.MIN_BRIGHTNESS, min(self.MAX_BRIGHTNESS, brightness))

            # Color blending based on depth (wave height)
            depth_factor = wave_total / (self.WAVE1_AMPLITUDE + self.WAVE2_AMPLITUDE +
                                         self.WAVE3_AMPLITUDE + self.WAVE4_AMPLITUDE)
            depth_factor = max(0.0, min(1.0, depth_factor))

            # Blend from deep to surface color
            if depth_factor < 0.5:
                t = depth_factor * 2
                r_mult = self.DEEP_COLOR[0] + t * (self.MID_COLOR[0] - self.DEEP_COLOR[0])
                g_mult = self.DEEP_COLOR[1] + t * (self.MID_COLOR[1] - self.DEEP_COLOR[1])
                b_mult = self.DEEP_COLOR[2] + t * (self.MID_COLOR[2] - self.DEEP_COLOR[2])
            else:
                t = (depth_factor - 0.5) * 2
                r_mult = self.MID_COLOR[0] + t * (self.SURFACE_COLOR[0] - self.MID_COLOR[0])
                g_mult = self.MID_COLOR[1] + t * (self.SURFACE_COLOR[1] - self.MID_COLOR[1])
                b_mult = self.MID_COLOR[2] + t * (self.SURFACE_COLOR[2] - self.MID_COLOR[2])

            # Add whitecap color
            if whitecap > 0.1:
                r_mult = r_mult + whitecap * (self.WHITECAP_COLOR[0] - r_mult)
                g_mult = g_mult + whitecap * (self.WHITECAP_COLOR[1] - g_mult)
                b_mult = b_mult + whitecap * (self.WHITECAP_COLOR[2] - b_mult)
                brightness = min(1.0, brightness + whitecap * 0.3)

            # Apply final color
            r = int(min(255, base_color[0] * brightness * r_mult))
            g = int(min(255, base_color[1] * brightness * g_mult))
            b = int(min(255, base_color[2] * brightness * b_mult))

            self._pixel_buffer[i] = (r, g, b)

        return self._pixel_buffer

    def get_layer_contributions(self) -> dict:
        """Get current wave contributions for debugging."""
        time = self._frame * self.config.speed
        contributions = {
            'wave1': [], 'wave2': [], 'wave3': [], 'wave4': [],
            'combined': [], 'whitecap': []
        }

        for i in range(self.num_pixels):
            w1 = self._calculate_wave_layer(i, self.WAVE1_FREQ, self.WAVE1_AMPLITUDE,
                                           self.WAVE1_DIRECTION, self.WAVE1_PHASE_OFFSET, time)
            w2 = self._calculate_wave_layer(i, self.WAVE2_FREQ, self.WAVE2_AMPLITUDE,
                                           self.WAVE2_DIRECTION, self.WAVE2_PHASE_OFFSET, time)
            w3 = self._calculate_wave_layer(i, self.WAVE3_FREQ, self.WAVE3_AMPLITUDE,
                                           self.WAVE3_DIRECTION, self.WAVE3_PHASE_OFFSET, time)
            w4 = self._calculate_wave_layer(i, self.WAVE4_FREQ, self.WAVE4_AMPLITUDE,
                                           self.WAVE4_DIRECTION, self.WAVE4_PHASE_OFFSET, time)

            contributions['wave1'].append(w1)
            contributions['wave2'].append(w2)
            contributions['wave3'].append(w3)
            contributions['wave4'].append(w4)
            contributions['combined'].append(w1 + w2 + w3 + w4)
            contributions['whitecap'].append(self._whitecap_state[i])

        return contributions

    def get_drift_rate(self) -> float:
        """Get effective wave drift rate."""
        return 50 / self.WAVE_CYCLE_FRAMES * self.config.speed
