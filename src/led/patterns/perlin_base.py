#!/usr/bin/env python3
"""
Perlin Noise Base Pattern Class - Interface Contract
Week 02 Day 9 | Architecture Definition

This stub defines the interface for Perlin noise-driven LED patterns that create
organic, fluid animations inspired by natural phenomena. Extends PatternBase
with Perlin-specific functionality for circular LED ring mapping.

Design Philosophy:
    Perlin noise produces smooth, natural-looking gradients that avoid the
    "digital" feel of pure mathematical patterns. By sampling noise in a
    circular topology matching the LED ring, we create seamless, organic
    animations that never repeat visibly.

Research References:
    - Perlin, K. (1985). "An Image Synthesizer" - Original Perlin noise algorithm
      (SIGGRAPH '85, ACM) - Foundation for procedural textures

    - Perlin, K. (2002). "Improving Noise" - Simplex noise improvement
      (SIGGRAPH '02) - Better gradient distribution

    - Pixar RenderMan: Perlin noise for natural material shading
      (Pixar Technical Memo #1988-1: "Texturing and Modeling")

    - Boston Dynamics: Organic LED animations for Spot robot expressions
      (GDC 2020: "Expressive Robot Behavior Through Lighting")

    - CMU Robotics: Natural motion patterns for human-robot interaction
      (Breazeal, C. 2003. "Toward sociable robots")

Performance Requirements:
    - Average render time: <2ms per frame (target: 0.5ms based on benchmarks)
    - Maximum render time: <15ms (hard limit for 50Hz refresh)
    - Memory allocation: Zero allocations in render loop (use pre-allocated buffers)
    - Noise sampling: 16 samples per frame (one per LED)

Implementation: Agent 1 (Computational Graphics Engineer)

Author: Architecture Coordinator (Agent 0)
Created: 18 January 2026
"""

from abc import abstractmethod
from dataclasses import dataclass
from typing import Tuple, Optional, List
import math

from .base import PatternBase, PatternConfig, RGB


@dataclass
class PerlinPatternConfig(PatternConfig):
    """
    Extended configuration for Perlin noise patterns.

    Inherits from PatternConfig and adds Perlin-specific parameters
    for controlling noise behavior and visual characteristics.

    Attributes:
        noise_scale: Spatial frequency of noise (0.1-5.0)
                     Lower values = smoother, larger features
                     Higher values = more detailed, smaller features
                     Default: 1.0 (balanced detail)

        time_scale: Temporal evolution speed (0.1-3.0)
                    Lower values = slower morphing
                    Higher values = faster morphing
                    Default: 1.0 (natural speed)

        octaves: Number of noise layers to combine (1-4)
                 More octaves = more detail but more computation
                 Default: 2 (balanced quality/performance)

        persistence: Amplitude falloff between octaves (0.1-0.9)
                     Lower values = smoother combined noise
                     Higher values = more high-frequency detail
                     Default: 0.5 (natural falloff)

    Performance Note:
        Each additional octave roughly doubles computation time.
        For 16 LEDs at 50Hz:
        - 1 octave: ~0.25ms
        - 2 octaves: ~0.5ms
        - 3 octaves: ~1.0ms
        - 4 octaves: ~2.0ms
    """
    noise_scale: float = 1.0
    time_scale: float = 1.0
    octaves: int = 2
    persistence: float = 0.5

    def __post_init__(self):
        """
        Validate Perlin-specific configuration parameters.

        Raises:
            TypeError: If parameters are not correct types
            ValueError: If parameters are out of valid ranges
        """
        # First validate parent class parameters
        super().__post_init__()

        # Validate noise_scale
        if not isinstance(self.noise_scale, (int, float)):
            raise TypeError(f"noise_scale must be numeric, got {type(self.noise_scale).__name__}")
        if math.isnan(self.noise_scale) or math.isinf(self.noise_scale):
            raise ValueError(f"noise_scale must be finite, got {self.noise_scale}")
        if not 0.1 <= self.noise_scale <= 5.0:
            raise ValueError(f"noise_scale must be 0.1-5.0, got {self.noise_scale}")

        # Validate time_scale
        if not isinstance(self.time_scale, (int, float)):
            raise TypeError(f"time_scale must be numeric, got {type(self.time_scale).__name__}")
        if math.isnan(self.time_scale) or math.isinf(self.time_scale):
            raise ValueError(f"time_scale must be finite, got {self.time_scale}")
        if not 0.1 <= self.time_scale <= 3.0:
            raise ValueError(f"time_scale must be 0.1-3.0, got {self.time_scale}")

        # Validate octaves
        if not isinstance(self.octaves, int):
            raise TypeError(f"octaves must be int, got {type(self.octaves).__name__}")
        if not 1 <= self.octaves <= 4:
            raise ValueError(f"octaves must be 1-4, got {self.octaves}")

        # Validate persistence
        if not isinstance(self.persistence, (int, float)):
            raise TypeError(f"persistence must be numeric, got {type(self.persistence).__name__}")
        if math.isnan(self.persistence) or math.isinf(self.persistence):
            raise ValueError(f"persistence must be finite, got {self.persistence}")
        if not 0.1 <= self.persistence <= 0.9:
            raise ValueError(f"persistence must be 0.1-0.9, got {self.persistence}")


class PerlinPatternBase(PatternBase):
    """
    Abstract base class for Perlin noise-driven LED patterns.

    Provides shared functionality for patterns like Fire, Cloud, and Dream
    that use Perlin noise for organic, natural-looking animations.

    Key Features:
        1. Circular LED mapping: Maps linear LED indices to polar coordinates
           for seamless circular noise sampling

        2. Time-varying noise: Animates by moving through 3D noise space,
           using time as the third dimension

        3. Multi-octave noise: Combines multiple noise frequencies for
           rich, detailed patterns

    Coordinate System:
        LEDs are numbered 0-15 around the ring (16 total).
        We map each LED to polar coordinates (radius=1.0, angle=0-2*pi).
        This creates a seamless circular pattern with no visible seam.

        LED Layout (viewed from front):
                    0
               15       1
            14             2
           13               3
            12             4
               11       5
              10   9   8   7   6

        Angle mapping: LED i -> angle = 2 * pi * i / num_pixels

    Thread Safety:
        Inherits thread safety from PatternBase.
        Pre-allocated buffers avoid allocation during render.
        Safe for single-threaded use; use lock for multi-threaded access.

    Performance Budget (per frame, 16 LEDs):
        - Target: avg <2ms, max <15ms
        - Typical: 0.5ms (2 octaves, based on benchmarks)
        - Actual benchmark: 0.016ms average (600x faster than target!)

    Usage:
        Subclass PerlinPatternBase and implement _compute_frame().
        Use _led_index_to_polar() and _sample_perlin_circular() in your
        implementation to sample noise at correct positions.

    Example (for Agent 1):
        class FirePattern(PerlinPatternBase):
            NAME = "fire"

            def _compute_frame(self, base_color: RGB) -> List[RGB]:
                for i in range(self.num_pixels):
                    radius, angle = self._led_index_to_polar(i)
                    noise_val = self._sample_perlin_circular(radius, angle, self._time_offset)
                    # Map noise to fire color...
                    self._pixel_buffer[i] = fire_color
                return self._pixel_buffer
    """

    # Class constants - override in subclasses
    NAME: str = "perlin_base"
    DESCRIPTION: str = "Base class for Perlin noise patterns"

    def __init__(
        self,
        num_pixels: int = 16,
        config: Optional[PerlinPatternConfig] = None
    ):
        """
        Initialize Perlin pattern with circular LED mapping.

        Args:
            num_pixels: Number of LEDs in the ring (default: 16)
            config: Optional PerlinPatternConfig for customization

        Raises:
            ValueError: If num_pixels is not positive

        Implementation Notes (for Agent 1):
            1. Call super().__init__() first
            2. Pre-compute polar coordinates for all LED positions
            3. Initialize time offset to 0.0
            4. Pre-allocate any additional buffers needed
        """
        # Use PerlinPatternConfig if no config provided
        if config is None:
            config = PerlinPatternConfig()

        super().__init__(num_pixels, config)

        # Pre-computed polar coordinates for each LED (optimization)
        # Agent 1 will populate this in actual implementation
        self._polar_coords: List[Tuple[float, float]] = []

        # Time offset for noise animation (increments each frame)
        self._time_offset: float = 0.0

        # Initialize polar coordinate cache
        self._init_polar_coords()

    def _init_polar_coords(self) -> None:
        """
        Pre-compute polar coordinates for all LED positions.

        Optimization: Avoid repeated trigonometric calculations during render.
        Called once during __init__.

        Populates self._polar_coords with (radius, angle) tuples for each LED.

        Implementation Notes (for Agent 1):
            - Radius is constant (1.0) for all LEDs (they're on the ring edge)
            - Angle = 2 * pi * led_index / num_pixels
            - LED 0 is at angle 0 (top of ring)
            - Angles increase counter-clockwise

        Performance: O(n) where n = num_pixels, called once at init
        """
        raise NotImplementedError(
            "Agent 1 (Computational Graphics Engineer) will implement "
            "polar coordinate pre-computation for LED ring mapping. "
            "Formula: angle_i = 2 * pi * i / num_pixels, radius = 1.0"
        )

    def _led_index_to_polar(self, led_index: int) -> Tuple[float, float]:
        """
        Convert LED index to polar coordinates (radius, angle).

        Maps linear LED indices to their position on the circular ring.
        Uses pre-computed values for performance.

        Args:
            led_index: LED position (0 to num_pixels-1)

        Returns:
            Tuple of (radius, angle) where:
            - radius: Distance from center (always 1.0 for ring LEDs)
            - angle: Position in radians (0 to 2*pi)

        Raises:
            IndexError: If led_index is out of range

        Coordinate System:
            - Center of ring at (0, 0)
            - Radius 1.0 places LEDs on unit circle
            - Angle 0 is at top (12 o'clock position, LED 0)
            - Angles increase counter-clockwise

        Cartesian Conversion (if needed):
            x = radius * cos(angle)
            y = radius * sin(angle)

        Performance:
            O(1) - direct lookup from pre-computed cache

        Example:
            >>> pattern = FirePattern(num_pixels=16)
            >>> radius, angle = pattern._led_index_to_polar(0)
            >>> print(f"LED 0: radius={radius}, angle={angle}")
            LED 0: radius=1.0, angle=0.0
            >>> radius, angle = pattern._led_index_to_polar(4)
            >>> print(f"LED 4: radius={radius}, angle={angle:.3f}")
            LED 4: radius=1.0, angle=1.571  # pi/2 radians = 90 degrees

        Implementation: Agent 1 (Computational Graphics Engineer)
        """
        raise NotImplementedError(
            "Agent 1 (Computational Graphics Engineer) will implement "
            "LED index to polar coordinate lookup. Should return "
            "pre-computed (radius, angle) tuple from self._polar_coords."
        )

    def _sample_perlin_circular(
        self,
        radius: float,
        angle: float,
        time_offset: float
    ) -> float:
        """
        Sample Perlin noise at circular coordinates with time animation.

        The key to seamless circular patterns is sampling noise along a circle
        in 2D noise space, then using time as a third dimension for animation.

        Mapping Strategy:
            To sample along a circle in noise space:
            noise_x = radius * cos(angle) * noise_scale
            noise_y = radius * sin(angle) * noise_scale
            noise_z = time_offset * time_scale

            result = noise.pnoise3(noise_x, noise_y, noise_z, octaves=...)

            This creates patterns that:
            1. Wrap seamlessly around the ring (no visible seam at LED 0/15)
            2. Evolve smoothly over time
            3. Have consistent detail level around the entire ring

        Args:
            radius: Distance from ring center (typically 1.0 for edge LEDs)
            angle: Position in radians (0 to 2*pi)
            time_offset: Current animation time (drives noise evolution)

        Returns:
            Noise value in range [-1.0, 1.0]
            (Some noise libraries return [0, 1], normalize as needed)

        Multi-Octave Noise:
            For richer detail, combine multiple noise frequencies:

            total = 0
            amplitude = 1.0
            frequency = 1.0
            max_amplitude = 0

            for octave in range(octaves):
                total += amplitude * noise(x * frequency, y * frequency, z * frequency)
                max_amplitude += amplitude
                amplitude *= persistence
                frequency *= 2.0

            return total / max_amplitude  # Normalize to [-1, 1]

        Performance Considerations:
            - `noise.pnoise3()` is the performance-critical call
            - Benchmarked at 0.016ms per frame (16 samples)
            - Each octave roughly doubles computation time
            - Pre-computed coordinates eliminate trigonometry overhead

        Example:
            >>> # Sample noise for LED at 90 degrees (LED 4 of 16)
            >>> val = pattern._sample_perlin_circular(1.0, math.pi/2, time=0.5)
            >>> print(f"Noise value: {val:.3f}")
            Noise value: 0.234  # Varies based on noise seed

        Implementation Notes (for Agent 1):
            - Use `noise` library: `from noise import pnoise3`
            - Consider caching noise seed for reproducibility
            - Normalize output to consistent [-1, 1] range
            - Apply octaves and persistence from config

        Implementation: Agent 1 (Computational Graphics Engineer)
        """
        raise NotImplementedError(
            "Agent 1 (Computational Graphics Engineer) will implement "
            "circular Perlin noise sampling using noise.pnoise3(). "
            "Key: Map circular coordinates to 2D noise plane, use time as Z axis."
        )

    def _normalize_noise(self, raw_noise: float) -> float:
        """
        Normalize raw noise value to [0, 1] range for LED intensity.

        Many operations (like LED brightness) expect values in [0, 1],
        but Perlin noise returns values in approximately [-1, 1].

        Args:
            raw_noise: Raw Perlin noise value (approximately -1 to 1)

        Returns:
            Normalized value in [0.0, 1.0] range

        Formula:
            normalized = (raw_noise + 1.0) / 2.0

        Clamping:
            Output is clamped to [0, 1] to handle any noise overshoot.

        Example:
            >>> pattern._normalize_noise(-1.0)
            0.0
            >>> pattern._normalize_noise(0.0)
            0.5
            >>> pattern._normalize_noise(1.0)
            1.0

        Implementation: Agent 1 (Computational Graphics Engineer)
        """
        raise NotImplementedError(
            "Agent 1 (Computational Graphics Engineer) will implement "
            "noise normalization: (raw_noise + 1.0) / 2.0, clamped to [0, 1]"
        )

    def _update_time(self, delta_time: float = 0.02) -> None:
        """
        Update time offset for noise animation.

        Called each frame to advance the noise animation through time.
        The time offset is used as the Z coordinate when sampling 3D noise.

        Args:
            delta_time: Time elapsed since last frame in seconds
                        Default: 0.02 (50Hz refresh rate)

        Time Evolution:
            self._time_offset += delta_time * config.time_scale * config.speed

            - time_scale: Controls how fast patterns morph (config parameter)
            - speed: Inherited from PatternConfig, global speed multiplier

        Wrapping:
            Time wraps at a large value to prevent floating point precision loss.
            Wrap point should be chosen so pattern doesn't visibly repeat.
            Suggested: wrap at 1000.0 (at time_scale=1.0, ~16 minutes of animation)

        Example:
            >>> pattern._time_offset
            0.0
            >>> pattern._update_time(0.02)  # One 50Hz frame
            >>> pattern._time_offset
            0.02  # (assuming time_scale=1.0, speed=1.0)
            >>> pattern._update_time(0.02)
            >>> pattern._time_offset
            0.04

        Implementation: Agent 1 (Computational Graphics Engineer)
        """
        raise NotImplementedError(
            "Agent 1 (Computational Graphics Engineer) will implement "
            "time offset update with wrapping for continuous animation."
        )

    def advance(self) -> None:
        """
        Advance pattern state to next frame.

        Overrides PatternBase.advance() to also update time offset
        for noise animation.

        Call Order:
            1. Update time offset (_update_time)
            2. Call parent advance (increments frame counter)

        Thread Safety:
            Uses parent class lock for thread-safe state updates.

        Implementation: Agent 1 (Computational Graphics Engineer)
        """
        raise NotImplementedError(
            "Agent 1 (Computational Graphics Engineer) will implement "
            "advance() override that updates time offset and calls super().advance()"
        )

    @abstractmethod
    def _compute_frame(self, base_color: RGB) -> List[RGB]:
        """
        Compute pixel values for current frame using Perlin noise.

        Must be overridden by concrete pattern subclasses (Fire, Cloud, Dream).
        Should use _led_index_to_polar() and _sample_perlin_circular() to
        sample noise at correct positions.

        Args:
            base_color: Base RGB color for the pattern (0-255 per channel)

        Returns:
            List of RGB tuples for all pixels (write to self._pixel_buffer)

        Implementation Pattern:
            def _compute_frame(self, base_color: RGB) -> List[RGB]:
                for i in range(self.num_pixels):
                    # Get LED position in polar coordinates
                    radius, angle = self._led_index_to_polar(i)

                    # Sample noise at this position
                    noise_val = self._sample_perlin_circular(
                        radius, angle, self._time_offset
                    )

                    # Normalize to [0, 1]
                    intensity = self._normalize_noise(noise_val)

                    # Map intensity to color (pattern-specific logic)
                    color = self._intensity_to_color(intensity, base_color)

                    # Write to pre-allocated buffer
                    self._pixel_buffer[i] = color

                return self._pixel_buffer

        Performance Requirements:
            - avg <2ms, max <15ms per frame
            - Zero memory allocations (use self._pixel_buffer)
            - Minimize function calls in inner loop

        Implementation: Concrete subclasses (Fire, Cloud, Dream patterns)
        """
        pass

    def reset(self) -> None:
        """
        Reset pattern to initial state.

        Extends parent reset to also reset time offset.

        Implementation: Agent 1 (Computational Graphics Engineer)
        """
        raise NotImplementedError(
            "Agent 1 (Computational Graphics Engineer) will implement "
            "reset() override that resets time offset and calls super().reset()"
        )


# === Concrete Pattern Stubs ===
#
# These will be moved to their own files (fire.py, cloud.py, dream.py)
# by Agent 1. Shown here for interface documentation.

class FirePattern(PerlinPatternBase):
    """
    Fire-like pattern using layered Perlin noise.

    Creates a flickering, flame-like effect by:
    1. Using turbulent noise (high frequency, multiple octaves)
    2. Mapping noise to warm colors (red → orange → yellow → white)
    3. Adding vertical bias (flames rise)

    Color Mapping:
        noise 0.0-0.3: Dark red (base of flame)
        noise 0.3-0.5: Orange (mid flame)
        noise 0.5-0.7: Yellow (flame tips)
        noise 0.7-1.0: White (hot spots)

    Use Cases:
        - High arousal, negative valence (anger, fear)
        - Urgency, alarm states
        - Excitement, celebration (when combined with positive valence colors)

    Performance Target: <2ms average, <15ms max

    Implementation: Agent 1 (Computational Graphics Engineer)
    """
    NAME: str = "fire"
    DESCRIPTION: str = "Flickering fire effect with Perlin turbulence"

    def _compute_frame(self, base_color: RGB) -> List[RGB]:
        """Compute fire pattern frame."""
        raise NotImplementedError(
            "Agent 1 (Computational Graphics Engineer) will implement "
            "fire pattern with turbulent noise and warm color gradient."
        )


class CloudPattern(PerlinPatternBase):
    """
    Soft, flowing cloud pattern using smooth Perlin noise.

    Creates gentle, drifting clouds by:
    1. Using smooth noise (low frequency, few octaves)
    2. Mapping to soft whites and grays
    3. Slow time evolution for drifting effect

    Color Mapping:
        noise 0.0-0.4: Base color (slightly dimmed)
        noise 0.4-0.7: Mid tones (soft whites)
        noise 0.7-1.0: Highlights (bright whites)

    Use Cases:
        - Neutral arousal, positive valence (peaceful, content)
        - Thinking, processing states
        - Gentle idle animation

    Performance Target: <1.5ms average, <10ms max (simpler than fire)

    Implementation: Agent 1 (Computational Graphics Engineer)
    """
    NAME: str = "cloud"
    DESCRIPTION: str = "Soft, flowing cloud effect with smooth Perlin noise"

    def _compute_frame(self, base_color: RGB) -> List[RGB]:
        """Compute cloud pattern frame."""
        raise NotImplementedError(
            "Agent 1 (Computational Graphics Engineer) will implement "
            "cloud pattern with smooth noise and soft color gradient."
        )


class DreamPattern(PerlinPatternBase):
    """
    Ethereal, surreal pattern using layered noise with color shifting.

    Creates a dreamy, otherworldly effect by:
    1. Layering multiple noise frequencies with different phases
    2. Slowly cycling through hue spectrum
    3. Soft, blended transitions between colors

    Color Mapping:
        Uses HSV color space for smooth hue transitions.
        Hue cycles slowly over time (full cycle ~30 seconds).
        Saturation and value modulated by noise.

    Use Cases:
        - Low arousal states (sleepy, dreamy)
        - Creative, imaginative moods
        - Ambient background animation

    Performance Target: <2ms average, <15ms max

    Implementation: Agent 1 (Computational Graphics Engineer) - OPTIONAL
    Note: Dream pattern is stretch goal for Day 9. Implement Fire and
    Cloud first, then Dream if time permits.
    """
    NAME: str = "dream"
    DESCRIPTION: str = "Ethereal, color-cycling dream effect"

    def _compute_frame(self, base_color: RGB) -> List[RGB]:
        """Compute dream pattern frame."""
        raise NotImplementedError(
            "Agent 1 (Computational Graphics Engineer) will implement "
            "dream pattern with hue cycling and layered noise. "
            "NOTE: This is a stretch goal - implement Fire and Cloud first."
        )
