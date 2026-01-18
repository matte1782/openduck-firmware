#!/usr/bin/env python3
"""
Compound Emotion Patterns for OpenDuck Mini V3
Week 02 | Boston Dynamics / Pixar / DeepMind Quality Standard

Implements 5 compound emotions with psychology-grounded visual representations:
1. CONFUSED  - Uncertain scanning + color flickering (CURIOUS + ANXIOUS blend)
2. SURPRISED - Startle spike + widening effect (universal Ekman emotion)
3. ANXIOUS   - Nervous jitter + irregular rhythm (elevated HRV, sympathetic activation)
4. FRUSTRATED - Building tension + constrained energy (goal blockage, Dollard 1939)
5. PROUD     - Confident glow + elevated posture (achievement recognition)

Psychology Research Foundation:
- Plutchik's Wheel: Compound emotions as dyad combinations
- Russell's Circumplex: Arousal-valence mapping to LED brightness-color
- Ekman's Basic Emotions: Surprise as universal, rapid facial response
- Frustration-Aggression Hypothesis: Building tension, constrained energy
- Heart Rate Variability: Anxiety correlates with reduced HRV, irregular rhythm

Performance Constraints:
- Frame time: <2ms average, <10ms maximum
- Memory: Bounded lists (MAX_PARTICLES=100)
- CPU: <10% sustained

Disney Animation Principles Applied:
- Anticipation: Pre-action cues before emotion peaks
- Timing: Speed matches emotional energy level
- Exaggeration: Colors more saturated than realistic
- Secondary Action: Sparkles, micro-variations support main emotion
- Squash & Stretch: Brightness compression during transitions

Author: Compound Emotion Engineer (Agent 3)
Created: 18 January 2026
"""

import math
import random
from dataclasses import dataclass
from typing import Tuple, List, Dict, Optional
from enum import Enum

# Import parent module components
# NOTE: sys.path manipulation required for standalone script execution and pytest.
# This module lives at firmware/src/animation/emotion_patterns/ but needs to import
# from firmware/src/animation/. When run directly or via pytest from project root,
# the parent packages may not be on sys.path. This ensures imports work in all contexts.
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from animation.emotion_axes import EmotionAxes, EMOTION_PRESETS


# =============================================================================
# Type Aliases
# =============================================================================

RGB = Tuple[int, int, int]


# =============================================================================
# Constants - Performance & Safety Limits
# =============================================================================

# H-001: Prevent unbounded memory growth
MAX_SPARKLES = 50
MAX_PARTICLES = 100

# LED hardware constraints
DEFAULT_NUM_LEDS = 16
MAX_BRIGHTNESS = 60  # Power safety limit (60/255)

# Animation timing constants (research-backed)
HUMAN_BLINK_DURATION_MS = 300  # Average human blink
STARTLE_RESPONSE_MS = 200      # Pupil dilation peak latency
HEARTBEAT_NORMAL_BPM = 72      # Resting heart rate
HEARTBEAT_ANXIOUS_BPM = 100    # Elevated anxiety heart rate

# Frame timing
TARGET_FRAME_TIME_MS = 2.0
MAX_FRAME_TIME_MS = 10.0


# =============================================================================
# Compound Emotion Specifications
# =============================================================================

@dataclass(frozen=True)
class CompoundEmotionSpec:
    """
    Specification for a compound emotion with psychology grounding.

    Attributes:
        name: Emotion identifier string
        component_a: First component emotion name (from EMOTION_PRESETS)
        component_b: Second component emotion name (from EMOTION_PRESETS)
        blend_ratio: Ratio of component_a to component_b (0.0-1.0)
        arousal: Energy level (-1.0 to +1.0)
        valence: Positivity (-1.0 to +1.0)
        focus: Attention intensity (0.0 to 1.0)
        blink_speed: Blink rate multiplier (0.25 to 2.0)
        primary_color: Main LED color RGB (0-255 each)
        secondary_color: Accent LED color RGB
        cycle_duration_s: Animation cycle time in seconds
        psychology_basis: Research reference for validation
    """
    name: str
    component_a: str
    component_b: str
    blend_ratio: float
    arousal: float
    valence: float
    focus: float
    blink_speed: float
    primary_color: RGB
    secondary_color: RGB
    cycle_duration_s: float
    psychology_basis: str


# Psychology-grounded compound emotion specifications
# Each emotion has research backing for arousal/valence/visual mapping
COMPOUND_EMOTION_SPECS: Dict[str, CompoundEmotionSpec] = {
    "confused": CompoundEmotionSpec(
        name="confused",
        component_a="curious",      # Interest in understanding
        component_b="anxious",      # Inability to comprehend
        blend_ratio=0.6,            # 60% curious, 40% anxious
        arousal=0.2,                # Mild energy (puzzled, not panicked)
        valence=-0.2,               # Slightly negative (frustrated by confusion)
        focus=0.3,                  # Low focus (can't find pattern)
        blink_speed=1.3,            # Elevated blinks (uncertainty)
        primary_color=(140, 100, 200),   # Purple-violet (uncertain)
        secondary_color=(80, 180, 180),   # Cyan (searching)
        cycle_duration_s=2.5,       # Irregular, searching rhythm
        psychology_basis="Plutchik dyad: Interest blocked by inability"
    ),

    "surprised": CompoundEmotionSpec(
        name="surprised",
        component_a="alert",        # Sudden attention capture
        component_b="curious",      # What is this?
        blend_ratio=0.7,            # 70% alert, 30% curious
        arousal=0.8,                # High energy (startle response)
        valence=0.0,                # Neutral (could be positive or negative)
        focus=1.0,                  # Maximum focus (orienting response)
        blink_speed=0.3,            # Frozen momentarily (wide eyes)
        primary_color=(255, 255, 255),   # Bright white (flash)
        secondary_color=(100, 200, 255), # Cyan (settle color)
        cycle_duration_s=0.5,       # Quick flash then settle
        psychology_basis="Ekman universal emotion: Orienting response, pupil dilation"
    ),

    "anxious": CompoundEmotionSpec(
        name="anxious",
        component_a="alert",        # Threat monitoring
        component_b="sad",          # Anticipated negative outcome
        blend_ratio=0.6,            # 60% alert, 40% sad
        arousal=0.6,                # Elevated (sympathetic activation)
        valence=-0.5,               # Negative (worry)
        focus=0.6,                  # Moderate focus (scanning for threats)
        blink_speed=1.6,            # Rapid (nervousness indicator)
        primary_color=(100, 140, 200),   # Cool blue (worry)
        secondary_color=(180, 120, 100), # Warm flicker (nervous energy)
        cycle_duration_s=1.2,       # Irregular, arrhythmic (reduced HRV)
        psychology_basis="HRV research: Reduced variability, sympathetic dominance"
    ),

    "frustrated": CompoundEmotionSpec(
        name="frustrated",
        component_a="alert",        # Goal-directed energy
        component_b="sad",          # Blocked outcome
        blend_ratio=0.5,            # Equal parts blocked energy and disappointment
        arousal=0.5,                # Building tension (not explosive yet)
        valence=-0.4,               # Negative (goal blocked)
        focus=0.8,                  # High focus on obstacle
        blink_speed=1.4,            # Accelerating rhythm
        primary_color=(255, 140, 80),    # Orange-red (warming toward anger)
        secondary_color=(255, 80, 60),   # Red tinge (building heat)
        cycle_duration_s=1.0,       # Accelerating pulses
        psychology_basis="Frustration-Aggression Hypothesis: Blocked goal arousal"
    ),

    "proud": CompoundEmotionSpec(
        name="proud",
        component_a="happy",        # Achievement satisfaction
        component_b="alert",        # Confident attention
        blend_ratio=0.7,            # 70% happy, 30% alert
        arousal=0.4,                # Moderate energy (confident, not manic)
        valence=0.6,                # Positive (achievement recognition)
        focus=0.7,                  # Focused but open
        blink_speed=0.9,            # Steady, slower (confidence)
        primary_color=(255, 200, 100),   # Warm golden (triumph)
        secondary_color=(255, 220, 150), # Brighter gold (highlights)
        cycle_duration_s=2.0,       # Steady, strong rhythm
        psychology_basis="Ekman expansion emotion: Self-evaluative, achievement"
    ),
}


# =============================================================================
# EmotionAxes Presets for Compound Emotions
# =============================================================================

# These extend the EMOTION_PRESETS from emotion_axes.py
COMPOUND_EMOTION_PRESETS: Dict[str, EmotionAxes] = {
    spec.name: EmotionAxes(
        arousal=spec.arousal,
        valence=spec.valence,
        focus=spec.focus,
        blink_speed=spec.blink_speed,
    )
    for spec in COMPOUND_EMOTION_SPECS.values()
}


# =============================================================================
# Emotion Blending Algorithm
# =============================================================================

class EmotionBlender:
    """
    Blends two EmotionAxes instances to create compound emotions.

    Supports multiple blending strategies:
    - Linear: Simple weighted average (default)
    - Dominant: One emotion dominates until threshold
    - Oscillating: Blends oscillate over time

    Thread Safety:
        Stateless - safe for concurrent use.

    Performance:
        O(1) per blend operation, <0.01ms typical.
    """

    @staticmethod
    def linear_blend(
        emotion_a: EmotionAxes,
        emotion_b: EmotionAxes,
        ratio: float
    ) -> EmotionAxes:
        """
        Linearly interpolate between two emotions.

        Args:
            emotion_a: First emotion (weight = ratio)
            emotion_b: Second emotion (weight = 1 - ratio)
            ratio: Blend ratio 0.0-1.0 (0 = all B, 1 = all A)

        Returns:
            Blended EmotionAxes

        Raises:
            TypeError: If emotions are not EmotionAxes instances
            ValueError: If ratio is not in [0.0, 1.0]

        Example:
            >>> curious = EMOTION_PRESETS["curious"]
            >>> anxious = EMOTION_PRESETS["anxious"]
            >>> confused = EmotionBlender.linear_blend(curious, anxious, 0.6)
        """
        # H-002: Validate inputs
        if not isinstance(emotion_a, EmotionAxes):
            raise TypeError(f"emotion_a must be EmotionAxes, got {type(emotion_a).__name__}")
        if not isinstance(emotion_b, EmotionAxes):
            raise TypeError(f"emotion_b must be EmotionAxes, got {type(emotion_b).__name__}")
        if not isinstance(ratio, (int, float)):
            raise TypeError(f"ratio must be numeric, got {type(ratio).__name__}")
        if not 0.0 <= ratio <= 1.0:
            raise ValueError(f"ratio must be 0.0-1.0, got {ratio}")

        # Use EmotionAxes.interpolate (already validated, O(1))
        # Note: interpolate goes from self toward target, so we invert ratio
        return emotion_b.interpolate(emotion_a, ratio)

    @staticmethod
    def dominant_blend(
        emotion_a: EmotionAxes,
        emotion_b: EmotionAxes,
        ratio: float,
        threshold: float = 0.7
    ) -> EmotionAxes:
        """
        Blend where one emotion dominates until ratio crosses threshold.

        Creates more dramatic emotion transitions - one emotion "wins"
        rather than gradual mixing.

        Args:
            emotion_a: First emotion
            emotion_b: Second emotion
            ratio: Blend ratio 0.0-1.0
            threshold: Dominance threshold (default 0.7)

        Returns:
            Blended EmotionAxes with dominant bias

        Disney Principle: STAGING - Clear emotional read
        """
        # H-003: Validate threshold
        if not 0.0 <= threshold <= 1.0:
            raise ValueError(f"threshold must be 0.0-1.0, got {threshold}")

        # Apply dominance curve: remaps ratio to emphasize one side
        if ratio > threshold:
            # emotion_a dominates - amplify toward 1.0
            remapped = 0.5 + (ratio - threshold) / (2 * (1 - threshold))
        elif ratio < (1 - threshold):
            # emotion_b dominates - compress toward 0.0
            remapped = ratio / (2 * (1 - threshold))
        else:
            # Transition zone - linear through middle
            remapped = 0.5

        return EmotionBlender.linear_blend(emotion_a, emotion_b, remapped)

    @staticmethod
    def oscillating_blend(
        emotion_a: EmotionAxes,
        emotion_b: EmotionAxes,
        t: float,
        frequency: float = 1.0,
        base_ratio: float = 0.5
    ) -> EmotionAxes:
        """
        Blend that oscillates between emotions over time.

        Useful for emotions like CONFUSED (uncertain, shifting)
        or ANXIOUS (nervous fluctuations).

        Args:
            emotion_a: First emotion
            emotion_b: Second emotion
            t: Time in seconds
            frequency: Oscillation frequency in Hz
            base_ratio: Center point of oscillation (default 0.5)

        Returns:
            Time-varying blended EmotionAxes

        Disney Principle: TIMING - Speed matches nervous energy
        """
        # H-004: Validate frequency (prevent division by zero)
        if frequency <= 0:
            raise ValueError(f"frequency must be positive, got {frequency}")

        # Sinusoidal oscillation: varies blend ratio over time
        # Performance: O(1) using math.sin
        oscillation = math.sin(2 * math.pi * frequency * t) * 0.3  # +/- 0.3 swing
        ratio = max(0.0, min(1.0, base_ratio + oscillation))

        return EmotionBlender.linear_blend(emotion_a, emotion_b, ratio)


def blend_emotions(
    emotion_a: EmotionAxes,
    emotion_b: EmotionAxes,
    ratio: float
) -> EmotionAxes:
    """
    Module-level convenience function for emotion blending.

    See EmotionBlender.linear_blend for full documentation.
    """
    return EmotionBlender.linear_blend(emotion_a, emotion_b, ratio)


def get_compound_emotion_axes(emotion_name: str) -> EmotionAxes:
    """
    Get EmotionAxes for a compound emotion by name.

    Args:
        emotion_name: Name of compound emotion (confused, surprised, etc.)

    Returns:
        EmotionAxes for the requested emotion

    Raises:
        KeyError: If emotion_name not found in compound presets

    Example:
        >>> axes = get_compound_emotion_axes("confused")
        >>> print(axes.arousal)  # 0.2
    """
    if emotion_name not in COMPOUND_EMOTION_PRESETS:
        raise KeyError(
            f"Unknown compound emotion: '{emotion_name}'. "
            f"Available: {list(COMPOUND_EMOTION_PRESETS.keys())}"
        )
    return COMPOUND_EMOTION_PRESETS[emotion_name]


# =============================================================================
# Base Pattern Class
# =============================================================================

class CompoundEmotionPatternBase:
    """
    Base class for compound emotion LED patterns.

    Provides common functionality:
    - LED ring rendering (16 LEDs per eye)
    - Color interpolation
    - Brightness scaling with power limits
    - Frame time tracking for performance monitoring

    Subclasses implement render() with specific visual behaviors.

    Thread Safety:
        WARNING: Instance methods are NOT thread-safe. This class is designed
        for single-threaded use only (one pattern instance per LED controller).
        If multi-threaded access is required, callers MUST provide external
        synchronization (e.g., threading.Lock around render() calls).
        This is intentional to avoid lock overhead in the hot path.

    Performance Target:
        render() MUST complete in <2.5ms average, <10ms maximum.
    """

    def __init__(self, num_leds: int = DEFAULT_NUM_LEDS):
        """
        Initialize pattern renderer.

        Args:
            num_leds: Number of LEDs per ring (default 16)

        Raises:
            ValueError: If num_leds <= 0
        """
        # H-005: Validate num_leds to prevent division by zero
        if num_leds <= 0:
            raise ValueError(f"num_leds must be positive, got {num_leds}")

        self.num_leds = num_leds

        # State for pattern animation
        self._start_time: float = 0.0
        self._last_frame_time_ms: float = 0.0

        # Random state for reproducible variations (useful for testing)
        self._random = random.Random()

    def render(self, t: float) -> Tuple[List[RGB], List[RGB]]:
        """
        Render pattern at time t. Override in subclasses.

        Args:
            t: Time in seconds since emotion started

        Returns:
            Tuple of (left_eye_pixels, right_eye_pixels)
            Each is a list of num_leds RGB tuples

        Performance:
            MUST complete in <2.5ms average, <10ms maximum
        """
        raise NotImplementedError("Subclasses must implement render()")

    def reset(self) -> None:
        """Reset pattern state (call when transitioning TO this emotion)."""
        self._start_time = 0.0
        self._random.seed()  # Re-seed for new random variations

    def _clamp_brightness(self, color: RGB, max_brightness: int = MAX_BRIGHTNESS) -> RGB:
        """
        Clamp color brightness to power safety limit.

        Args:
            color: Input RGB tuple
            max_brightness: Maximum allowed value (default 60)

        Returns:
            Brightness-limited RGB tuple
        """
        r, g, b = color
        # Scale if any component exceeds max
        max_component = max(r, g, b)
        if max_component > max_brightness:
            scale = max_brightness / max_component
            return (
                int(r * scale),
                int(g * scale),
                int(b * scale),
            )
        return color

    def _interpolate_color(self, color_a: RGB, color_b: RGB, t: float) -> RGB:
        """
        Linear interpolation between two colors.

        Args:
            color_a: Start color
            color_b: End color
            t: Interpolation factor 0.0-1.0

        Returns:
            Interpolated RGB tuple

        Performance: O(1)
        """
        t = max(0.0, min(1.0, t))
        return (
            int(color_a[0] + (color_b[0] - color_a[0]) * t),
            int(color_a[1] + (color_b[1] - color_a[1]) * t),
            int(color_a[2] + (color_b[2] - color_a[2]) * t),
        )

    def _ease_in_out(self, t: float) -> float:
        """
        Smooth ease-in-out curve (sine-based).

        Disney Principle: SLOW IN / SLOW OUT

        Args:
            t: Linear time 0.0-1.0

        Returns:
            Eased time 0.0-1.0

        Performance: O(1)
        """
        # Sine-based easing: slow at start and end, fast in middle
        return 0.5 * (1 - math.cos(math.pi * t))

    def _create_ring_gradient(
        self,
        center_color: RGB,
        edge_color: RGB,
        center_brightness: float = 1.0
    ) -> List[RGB]:
        """
        Create radial gradient from center to edge of LED ring.

        Args:
            center_color: Color at ring center (brighter)
            edge_color: Color at ring edge (dimmer)
            center_brightness: Brightness multiplier for center

        Returns:
            List of num_leds RGB tuples

        Disney Principle: STAGING - Clear visual hierarchy
        """
        pixels = []
        for i in range(self.num_leds):
            # Distance from "center" (LED 0 and num_leds-1 are "top")
            # This creates a gradient that's brighter at top
            distance = abs(i - self.num_leds // 2) / (self.num_leds // 2)
            t = 1.0 - distance  # Invert so center is bright

            # Apply center brightness boost
            brightness = center_brightness * t + (1 - center_brightness) * (1 - t)

            color = self._interpolate_color(edge_color, center_color, t)
            color = (
                int(color[0] * brightness),
                int(color[1] * brightness),
                int(color[2] * brightness),
            )
            pixels.append(self._clamp_brightness(color))

        return pixels


# =============================================================================
# CONFUSED Pattern Implementation
# =============================================================================

class ConfusedPattern(CompoundEmotionPatternBase):
    """
    CONFUSED emotion pattern: Uncertain scanning + color flickering.

    Visual Characteristics:
    - Irregular scanning pattern (not smooth like CURIOUS)
    - Flickering between colors (can't decide)
    - Tilted/asymmetric brightness
    - Hesitant, incomplete rotations

    Component Blend: CURIOUS (0.6) + ANXIOUS (0.4)
    Psychology: Interest blocked by inability to comprehend
    Arousal: 0.2 (mild, puzzled)
    Valence: -0.2 (slightly negative, frustrated)

    Disney Principles:
    - TIMING: Irregular rhythm shows uncertainty
    - SECONDARY ACTION: Color flickers support confusion
    - ANTICIPATION: Hesitation before direction changes
    """

    def __init__(self, num_leds: int = DEFAULT_NUM_LEDS):
        super().__init__(num_leds)

        spec = COMPOUND_EMOTION_SPECS["confused"]
        self.primary_color = spec.primary_color
        self.secondary_color = spec.secondary_color
        self.cycle_duration = spec.cycle_duration_s

        # Confusion-specific state
        self._scan_position: float = 0.0
        self._scan_direction: int = 1
        self._flicker_phase: float = 0.0
        self._hesitation_timer: float = 0.0

    def render(self, t: float) -> Tuple[List[RGB], List[RGB]]:
        """
        Render confused pattern with irregular scanning and flickering.

        Args:
            t: Time in seconds since emotion started

        Returns:
            (left_eye_pixels, right_eye_pixels)

        Performance: O(num_leds), <2ms typical
        """
        # Update scan position with irregular speed
        # Confusion = variable speed, sometimes stalling
        speed_variation = 0.5 + 0.5 * math.sin(t * 3.7)  # Irregular
        self._scan_position += self._scan_direction * speed_variation * 0.03

        # Hesitation: sometimes pause and reverse
        self._hesitation_timer += 0.02
        if self._hesitation_timer > 0.8 + self._random.random() * 0.5:
            self._hesitation_timer = 0.0
            self._scan_direction *= -1  # Reverse direction

        # Keep scan position bounded (incomplete rotations)
        if self._scan_position > 0.7:  # Doesn't complete full scan
            self._scan_direction = -1
            self._scan_position = 0.7
        elif self._scan_position < 0.0:
            self._scan_direction = 1
            self._scan_position = 0.0

        # Color flickering: can't decide between colors
        self._flicker_phase += 0.05 + self._random.random() * 0.03
        flicker_t = 0.5 + 0.5 * math.sin(self._flicker_phase * 5.3)

        # Sometimes snap between colors (uncertainty)
        if self._random.random() < 0.02:
            flicker_t = 1.0 if flicker_t > 0.5 else 0.0

        current_color = self._interpolate_color(
            self.primary_color, self.secondary_color, flicker_t
        )

        # Generate LED patterns
        left_pixels = []
        right_pixels = []

        for i in range(self.num_leds):
            # Scanning highlight position
            led_pos = i / self.num_leds
            scan_distance = abs(led_pos - self._scan_position)

            # Brightness follows scan position (uncertain spotlight)
            brightness = max(0.3, 1.0 - scan_distance * 2.0)

            # Add asymmetry (tilted confusion)
            if i < self.num_leds // 2:
                brightness *= 0.85  # Dimmer on one side

            # Apply brightness to color
            pixel = (
                int(current_color[0] * brightness),
                int(current_color[1] * brightness),
                int(current_color[2] * brightness),
            )
            pixel = self._clamp_brightness(pixel)

            left_pixels.append(pixel)
            # Right eye slightly offset (asymmetric confusion)
            right_pixels.append(self._clamp_brightness((
                int(current_color[0] * brightness * 0.95),
                int(current_color[1] * brightness * 0.95),
                int(current_color[2] * brightness),
            )))

        return left_pixels, right_pixels

    def reset(self) -> None:
        super().reset()
        self._scan_position = 0.0
        self._scan_direction = 1
        self._flicker_phase = 0.0
        self._hesitation_timer = 0.0


# =============================================================================
# SURPRISED Pattern Implementation
# =============================================================================

class SurprisedPattern(CompoundEmotionPatternBase):
    """
    SURPRISED emotion pattern: Startle spike + widening effect.

    Visual Characteristics:
    - Sudden brightness spike (startle response)
    - Eyes "widen" effect (outer LEDs brighter)
    - Quick transition, then settle to calmer state
    - Flash white, settle to cyan

    Component Blend: ALERT (0.7) + CURIOUS (0.3)
    Psychology: Universal Ekman emotion, orienting response
    Arousal: 0.8 (high, startle)
    Valence: 0.0 (neutral, could be positive or negative)

    Research: Pupil dilation peaks ~200ms after stimulus
             (Frontiers in Neuroscience, pupil dilation studies)

    Disney Principles:
    - ANTICIPATION: N/A (surprise is instantaneous)
    - SQUASH & STRETCH: Brightness compression then expansion
    - TIMING: Fast onset, slower decay
    """

    # Startle response timing (research-backed)
    STARTLE_PEAK_TIME = 0.2      # 200ms to peak (pupil dilation latency)
    STARTLE_HOLD_TIME = 0.3     # Hold at peak
    SETTLE_TIME = 1.0           # Time to settle to curious state

    def __init__(self, num_leds: int = DEFAULT_NUM_LEDS):
        super().__init__(num_leds)

        spec = COMPOUND_EMOTION_SPECS["surprised"]
        self.flash_color = spec.primary_color     # White flash
        self.settle_color = spec.secondary_color  # Cyan settle

    def render(self, t: float) -> Tuple[List[RGB], List[RGB]]:
        """
        Render surprised pattern with startle spike and settle.

        Args:
            t: Time in seconds since emotion started

        Returns:
            (left_eye_pixels, right_eye_pixels)

        Performance: O(num_leds), <1.5ms typical (simpler pattern)
        """
        # Phase calculation
        if t < self.STARTLE_PEAK_TIME:
            # Rising to peak - fast exponential
            phase = "rising"
            progress = t / self.STARTLE_PEAK_TIME
            brightness = 0.4 + 0.6 * (1 - math.exp(-5 * progress))
            color_blend = 0.0  # Pure flash color
        elif t < self.STARTLE_PEAK_TIME + self.STARTLE_HOLD_TIME:
            # Hold at peak (frozen surprise)
            phase = "peak"
            brightness = 1.0
            color_blend = 0.0
        else:
            # Settling down
            phase = "settling"
            settle_progress = (t - self.STARTLE_PEAK_TIME - self.STARTLE_HOLD_TIME) / self.SETTLE_TIME
            settle_progress = min(1.0, settle_progress)
            # Ease out the brightness decay
            brightness = 1.0 - self._ease_in_out(settle_progress) * 0.4
            color_blend = self._ease_in_out(settle_progress)

        # Interpolate color from flash to settle
        current_color = self._interpolate_color(
            self.flash_color, self.settle_color, color_blend
        )

        # "Widening" effect: outer LEDs brighter during surprise
        # This mimics eyes widening (more visible sclera)
        left_pixels = []
        right_pixels = []

        for i in range(self.num_leds):
            # Distance from center (0 = center, 1 = edge)
            center = self.num_leds // 2
            distance_from_center = abs(i - center) / center

            # During surprise, outer LEDs are brighter (widening)
            if phase in ("rising", "peak"):
                # Edges 20% brighter than center
                position_brightness = 0.8 + 0.2 * distance_from_center
            else:
                # Settling: return to normal (center brighter)
                settle_factor = min(1.0, (t - self.STARTLE_PEAK_TIME - self.STARTLE_HOLD_TIME) / self.SETTLE_TIME)
                widening = 0.2 * (1 - settle_factor)
                position_brightness = (0.8 + widening) + (0.2 - widening) * (1 - distance_from_center)

            final_brightness = brightness * position_brightness

            pixel = (
                int(current_color[0] * final_brightness),
                int(current_color[1] * final_brightness),
                int(current_color[2] * final_brightness),
            )
            pixel = self._clamp_brightness(pixel)

            left_pixels.append(pixel)
            right_pixels.append(pixel)  # Symmetric for surprise

        return left_pixels, right_pixels


# =============================================================================
# ANXIOUS Pattern Implementation
# =============================================================================

class AnxiousPattern(CompoundEmotionPatternBase):
    """
    ANXIOUS emotion pattern: Nervous jitter + irregular rhythm.

    Visual Characteristics:
    - Rapid micro-movements (nervous jitter)
    - Slightly elevated brightness (sympathetic activation)
    - Irregular rhythm (arrhythmic, reduced HRV)
    - Cool colors with warm flickers (conflict)

    Component Blend: ALERT (0.6) + SAD (0.4)
    Psychology: Worry + anticipated negative outcome
    Arousal: 0.6 (elevated, nervous system activated)
    Valence: -0.5 (negative, worry)

    Research: Anxiety correlates with reduced heart rate variability
             (BMC Psychology, HRV studies)

    Disney Principles:
    - TIMING: Irregular, unpredictable rhythm
    - SECONDARY ACTION: Warm flickers show nervous energy
    - EXAGGERATION: More jitter than realistic
    """

    # Timing constants (based on HRV research)
    BASE_CYCLE_MS = 600  # ~100 BPM (anxious heart rate)
    VARIABILITY_RANGE = 0.15  # Reduced HRV = less variation

    def __init__(self, num_leds: int = DEFAULT_NUM_LEDS):
        super().__init__(num_leds)

        spec = COMPOUND_EMOTION_SPECS["anxious"]
        self.primary_color = spec.primary_color    # Cool blue
        self.secondary_color = spec.secondary_color  # Warm flicker

        # Anxiety-specific state
        self._jitter_offsets: List[float] = [0.0] * num_leds
        self._next_beat_time: float = 0.0
        self._current_beat_intensity: float = 0.5

    def render(self, t: float) -> Tuple[List[RGB], List[RGB]]:
        """
        Render anxious pattern with nervous jitter and irregular rhythm.

        Args:
            t: Time in seconds since emotion started

        Returns:
            (left_eye_pixels, right_eye_pixels)

        Performance: O(num_leds), <2ms typical
        """
        # Irregular heartbeat rhythm (reduced HRV = less predictable)
        if t >= self._next_beat_time:
            # Schedule next beat with slight randomness
            base_interval = self.BASE_CYCLE_MS / 1000.0
            variation = (self._random.random() - 0.5) * self.VARIABILITY_RANGE * base_interval
            self._next_beat_time = t + base_interval + variation

            # Beat intensity varies (sometimes harder, sometimes softer)
            self._current_beat_intensity = 0.6 + self._random.random() * 0.4

        # Calculate current pulse phase
        time_since_beat = t - (self._next_beat_time - self.BASE_CYCLE_MS / 1000.0)
        beat_progress = time_since_beat / (self.BASE_CYCLE_MS / 1000.0)
        beat_progress = max(0.0, min(1.0, beat_progress))

        # Pulse shape: quick rise, slow decay (like anxious heartbeat)
        if beat_progress < 0.15:
            pulse = beat_progress / 0.15 * self._current_beat_intensity
        else:
            pulse = self._current_beat_intensity * (1.0 - (beat_progress - 0.15) / 0.85)

        # Base brightness elevated (sympathetic activation)
        base_brightness = 0.6 + pulse * 0.3

        # Update jitter offsets (nervous micro-movements)
        for i in range(self.num_leds):
            # Small random changes to each LED's offset
            self._jitter_offsets[i] += (self._random.random() - 0.5) * 0.1
            # Decay toward zero (bounded jitter)
            self._jitter_offsets[i] *= 0.95
            # H-002: Clamp jitter to prevent unbounded accumulation over long runs
            self._jitter_offsets[i] = max(-1.0, min(1.0, self._jitter_offsets[i]))

        # Occasional warm flicker (nervous energy spike)
        warm_flicker = 0.0
        if self._random.random() < 0.03:  # 3% chance per frame
            warm_flicker = 0.3 + self._random.random() * 0.3

        # Generate LED patterns
        left_pixels = []
        right_pixels = []

        for i in range(self.num_leds):
            # Apply jitter to brightness
            jitter_brightness = base_brightness + self._jitter_offsets[i] * 0.2
            jitter_brightness = max(0.4, min(1.0, jitter_brightness))

            # Blend in warm flicker if active
            color = self._interpolate_color(
                self.primary_color, self.secondary_color, warm_flicker
            )

            pixel = (
                int(color[0] * jitter_brightness),
                int(color[1] * jitter_brightness),
                int(color[2] * jitter_brightness),
            )
            pixel = self._clamp_brightness(pixel)

            left_pixels.append(pixel)
            # Right eye has slightly different jitter (asymmetric anxiety)
            right_jitter = jitter_brightness + (self._random.random() - 0.5) * 0.05
            right_pixel = (
                int(color[0] * right_jitter),
                int(color[1] * right_jitter),
                int(color[2] * right_jitter),
            )
            right_pixels.append(self._clamp_brightness(right_pixel))

        return left_pixels, right_pixels

    def reset(self) -> None:
        super().reset()
        self._jitter_offsets = [0.0] * self.num_leds
        self._next_beat_time = 0.0
        self._current_beat_intensity = 0.5


# =============================================================================
# FRUSTRATED Pattern Implementation
# =============================================================================

class FrustratedPattern(CompoundEmotionPatternBase):
    """
    FRUSTRATED emotion pattern: Building tension + constrained energy.

    Visual Characteristics:
    - Pulsing that accelerates over time
    - Warmer colors trending toward red
    - Constrained energy (not explosive like ANGRY)
    - Building tension visualization

    Component Blend: ALERT (0.5) + SAD (0.5)
    Psychology: Goal blockage, building aggression potential
    Arousal: 0.5 (building, not peaked)
    Valence: -0.4 (negative, blocked)

    Research: Frustration-Aggression Hypothesis (Dollard et al. 1939)
             Goal blockage creates arousal that seeks outlet

    Disney Principles:
    - ANTICIPATION: Tension builds before (potential) release
    - TIMING: Accelerating rhythm shows building frustration
    - SQUASH & STRETCH: Pulse amplitude increases over time
    """

    # Frustration timing
    INITIAL_PULSE_PERIOD = 1.2  # Start slow
    MIN_PULSE_PERIOD = 0.4      # Accelerate to this
    ACCELERATION_TIME = 8.0     # Time to reach min period

    def __init__(self, num_leds: int = DEFAULT_NUM_LEDS):
        super().__init__(num_leds)

        spec = COMPOUND_EMOTION_SPECS["frustrated"]
        self.primary_color = spec.primary_color    # Orange-red
        self.secondary_color = spec.secondary_color  # Red tinge

        # Frustration builds over time
        self._tension_level: float = 0.0
        self._pulse_phase: float = 0.0

    def render(self, t: float) -> Tuple[List[RGB], List[RGB]]:
        """
        Render frustrated pattern with building tension and accelerating pulses.

        Args:
            t: Time in seconds since emotion started

        Returns:
            (left_eye_pixels, right_eye_pixels)

        Performance: O(num_leds), <1.5ms typical
        """
        # Tension builds over time (capped at 1.0)
        self._tension_level = min(1.0, t / self.ACCELERATION_TIME)

        # Pulse period accelerates as tension builds
        current_period = self.INITIAL_PULSE_PERIOD - (
            self.INITIAL_PULSE_PERIOD - self.MIN_PULSE_PERIOD
        ) * self._tension_level

        # H-006: Prevent division by zero
        if current_period <= 0:
            current_period = self.MIN_PULSE_PERIOD

        # Update pulse phase
        self._pulse_phase += 1.0 / (current_period * 50)  # Assuming 50Hz
        if self._pulse_phase > 1.0:
            self._pulse_phase -= 1.0

        # Pulse shape: sharp rise, slow decay (frustrated heartbeat)
        if self._pulse_phase < 0.2:
            # Quick rise (building)
            pulse_value = self._pulse_phase / 0.2
        else:
            # Slow decay (constrained, can't release)
            pulse_value = 1.0 - (self._pulse_phase - 0.2) / 0.8

        # Apply tension to pulse amplitude (more tension = stronger pulses)
        pulse_amplitude = 0.3 + self._tension_level * 0.5
        pulse = pulse_value * pulse_amplitude

        # Color shifts warmer as frustration builds
        color_shift = self._tension_level * 0.6
        current_color = self._interpolate_color(
            self.primary_color, self.secondary_color, color_shift
        )

        # Brightness: elevated baseline + pulse
        base_brightness = 0.5 + self._tension_level * 0.2
        brightness = base_brightness + pulse * 0.3

        # Generate LED patterns
        left_pixels = []
        right_pixels = []

        for i in range(self.num_leds):
            # Slight variation across ring (constrained energy trying to escape)
            position_var = math.sin(i * 0.8 + t * 3) * 0.05 * self._tension_level
            final_brightness = max(0.3, min(1.0, brightness + position_var))

            pixel = (
                int(current_color[0] * final_brightness),
                int(current_color[1] * final_brightness),
                int(current_color[2] * final_brightness),
            )
            pixel = self._clamp_brightness(pixel)

            left_pixels.append(pixel)
            right_pixels.append(pixel)  # Symmetric (focused frustration)

        return left_pixels, right_pixels

    def reset(self) -> None:
        super().reset()
        self._tension_level = 0.0
        self._pulse_phase = 0.0


# =============================================================================
# PROUD Pattern Implementation
# =============================================================================

class ProudPattern(CompoundEmotionPatternBase):
    """
    PROUD emotion pattern: Confident glow + elevated posture.

    Visual Characteristics:
    - Steady, strong rhythm (confidence)
    - Warm golden tones (triumph, achievement)
    - "Standing tall" effect (top LEDs brighter)
    - Subtle sparkle highlights (pride moments)

    Component Blend: HAPPY (0.7) + ALERT (0.3)
    Psychology: Achievement recognition, self-evaluative emotion
    Arousal: 0.4 (moderate, confident not manic)
    Valence: 0.6 (positive, satisfied)

    Research: Ekman expansion emotion (pride in 1990s additions)
             Associated with upright posture, chin-up gesture

    Disney Principles:
    - STAGING: Clear upward visual bias
    - TIMING: Steady, confident rhythm
    - APPEAL: Warm, inviting golden glow
    """

    def __init__(self, num_leds: int = DEFAULT_NUM_LEDS):
        super().__init__(num_leds)

        spec = COMPOUND_EMOTION_SPECS["proud"]
        self.primary_color = spec.primary_color      # Warm gold
        self.secondary_color = spec.secondary_color  # Brighter gold
        self.cycle_duration = spec.cycle_duration_s

        # Pride sparkle state
        self._sparkle_positions: List[Tuple[int, float]] = []  # (led_index, intensity)

    def render(self, t: float) -> Tuple[List[RGB], List[RGB]]:
        """
        Render proud pattern with confident glow and upward bias.

        Args:
            t: Time in seconds since emotion started

        Returns:
            (left_eye_pixels, right_eye_pixels)

        Performance: O(num_leds + sparkles), <2ms typical
        """
        # Steady pulse (confident heartbeat, ~72 BPM)
        pulse_phase = (t % self.cycle_duration) / self.cycle_duration
        pulse = 0.5 + 0.5 * math.sin(2 * math.pi * pulse_phase)

        # Apply easing for smooth, confident rhythm
        pulse = self._ease_in_out(pulse)

        # Occasionally add sparkle (pride highlight)
        # H-007: Bound sparkle list
        if self._random.random() < 0.02 and len(self._sparkle_positions) < MAX_SPARKLES:
            sparkle_led = self._random.randint(0, self.num_leds - 1)
            self._sparkle_positions.append((sparkle_led, 1.0))

        # Decay and remove sparkles
        new_sparkles = []
        for led_idx, intensity in self._sparkle_positions:
            new_intensity = intensity - 0.05
            if new_intensity > 0.1:
                new_sparkles.append((led_idx, new_intensity))
        self._sparkle_positions = new_sparkles

        # Create sparkle brightness map
        sparkle_map = {led_idx: intensity for led_idx, intensity in self._sparkle_positions}

        # Generate LED patterns
        left_pixels = []
        right_pixels = []

        for i in range(self.num_leds):
            # "Standing tall" effect: top LEDs brighter
            # LED 0 and num_leds-1 are "top" of the ring
            # Calculate distance from top
            top_distance = min(i, self.num_leds - 1 - i) / (self.num_leds // 2)
            upward_bias = 1.0 - top_distance * 0.25  # Top is up to 25% brighter

            # Base brightness with pulse
            brightness = 0.6 + pulse * 0.25

            # Apply upward bias
            brightness *= upward_bias

            # Apply any sparkle
            sparkle_boost = sparkle_map.get(i, 0.0)
            if sparkle_boost > 0:
                brightness = min(1.0, brightness + sparkle_boost * 0.3)
                # Sparkle shifts color slightly brighter
                color = self._interpolate_color(
                    self.primary_color, self.secondary_color, sparkle_boost
                )
            else:
                color = self.primary_color

            pixel = (
                int(color[0] * brightness),
                int(color[1] * brightness),
                int(color[2] * brightness),
            )
            pixel = self._clamp_brightness(pixel)

            left_pixels.append(pixel)
            right_pixels.append(pixel)  # Symmetric (confident)

        return left_pixels, right_pixels

    def reset(self) -> None:
        super().reset()
        self._sparkle_positions = []


# =============================================================================
# Emotion Configuration Entries
# =============================================================================

# These can be added to EMOTION_CONFIGS in emotions.py
# Kept here for reference and integration
COMPOUND_EMOTION_CONFIGS: Dict[str, dict] = {
    "confused": {
        "led_color": COMPOUND_EMOTION_SPECS["confused"].primary_color,
        "led_pattern": "compound_confused",
        "led_brightness": 45,  # Muted (uncertainty)
        "pattern_speed": 0.9,
        "transition_ms": 600,
    },
    "surprised": {
        "led_color": COMPOUND_EMOTION_SPECS["surprised"].primary_color,
        "led_pattern": "compound_surprised",
        "led_brightness": 60,  # Maximum (startle)
        "pattern_speed": 2.0,  # Fast
        "transition_ms": 150,  # Instant onset
    },
    "anxious": {
        "led_color": COMPOUND_EMOTION_SPECS["anxious"].primary_color,
        "led_pattern": "compound_anxious",
        "led_brightness": 50,
        "pattern_speed": 1.4,  # Elevated
        "transition_ms": 400,
    },
    "frustrated": {
        "led_color": COMPOUND_EMOTION_SPECS["frustrated"].primary_color,
        "led_pattern": "compound_frustrated",
        "led_brightness": 52,
        "pattern_speed": 1.2,  # Building
        "transition_ms": 500,
    },
    "proud": {
        "led_color": COMPOUND_EMOTION_SPECS["proud"].primary_color,
        "led_pattern": "compound_proud",
        "led_brightness": 55,  # Confident brightness
        "pattern_speed": 0.8,  # Steady
        "transition_ms": 700,  # Dignified transition
    },
}


# =============================================================================
# Transition Time Matrix Extensions
# =============================================================================

# Transition times TO compound emotions (in seconds)
# These should be merged with TRANSITION_TIMES in emotions.py
COMPOUND_TRANSITION_TIMES: Dict[Tuple[str, str], float] = {
    # TO confused
    ("idle", "confused"): 0.6,
    ("curious", "confused"): 0.4,  # Natural progression
    ("thinking", "confused"): 0.3,  # Quick to confusion from thinking
    ("alert", "confused"): 0.5,

    # TO surprised (instant - startle response)
    ("idle", "surprised"): 0.15,
    ("happy", "surprised"): 0.15,
    ("curious", "surprised"): 0.15,
    ("thinking", "surprised"): 0.15,
    ("sleepy", "surprised"): 0.1,  # Startled awake is fastest

    # TO anxious
    ("idle", "anxious"): 0.5,
    ("alert", "anxious"): 0.3,  # Alert easily becomes anxious
    ("thinking", "anxious"): 0.4,
    ("confused", "anxious"): 0.3,

    # TO frustrated
    ("idle", "frustrated"): 0.6,
    ("thinking", "frustrated"): 0.4,
    ("alert", "frustrated"): 0.5,
    ("confused", "frustrated"): 0.4,  # Confusion can lead to frustration
    ("anxious", "frustrated"): 0.3,

    # TO proud
    ("happy", "proud"): 0.5,  # Natural progression from happiness
    ("excited", "proud"): 0.6,
    ("thinking", "proud"): 0.8,  # Realization of achievement
    ("idle", "proud"): 0.7,

    # FROM compound emotions (returning to basics)
    ("confused", "idle"): 0.6,
    ("confused", "curious"): 0.4,
    ("confused", "thinking"): 0.5,

    ("surprised", "idle"): 0.8,  # Slow recovery from surprise
    ("surprised", "curious"): 0.5,  # "What was that?"
    ("surprised", "alert"): 0.3,
    ("surprised", "happy"): 0.6,  # Pleasant surprise

    ("anxious", "idle"): 0.8,  # Slow calming
    ("anxious", "alert"): 0.3,
    ("anxious", "sad"): 0.5,

    ("frustrated", "idle"): 0.7,
    ("frustrated", "sad"): 0.5,  # Giving up
    ("frustrated", "alert"): 0.3,  # Frustration to action

    ("proud", "idle"): 0.8,  # Slow fade from pride
    ("proud", "happy"): 0.4,  # Pride settles to happiness
}
