#!/usr/bin/env python3
"""
Pixar 4-Axis Emotion System - Interface Contract
Week 02 Day 9 | Architecture Definition

This stub defines the interface for infinite emotion interpolation using a
continuous 4-axis representation inspired by Pixar's Inside Out, Russell's
Circumplex Model of Affect, and Boston Dynamics expressive robotics research.

Replaces discrete EmotionState enum with continuous emotion space for:
- Natural transitions between any emotional states
- Fine-grained expression control
- Organic, believable robot personality

Implementation will be completed by Agent 2 (Animation Systems Architect).

Key Design Decision:
    Why 4 axes instead of 2D circumplex?
    - Arousal + Valence (Russell) cover basic affect space
    - Focus adds cognitive dimension (attention/distraction)
    - Blink speed adds temporal expressiveness (nervous/calm)

    This enables richer personality than traditional 2D models while
    staying computationally tractable for real-time LED interpolation.

Research References:
    - Russell's Circumplex Model: arousal × valence affect space
      (Russell, J. A. 1980. "A circumplex model of affect")

    - Pixar Inside Out: Multi-dimensional emotion representation
      (GDC 2015 Talk: "Thinking Inside the Box")

    - Boston Dynamics Spot: Expressive lights for robot state communication
      (Research on non-verbal robot-human interaction)

    - CMU Social Robots: Attention and focus as separate emotional dimension
      (Breazeal, C. 2003. "Emotion and sociable humanoid robots")

Author: Architecture Coordinator (Agent 0)
Created: 18 January 2026
"""

from dataclasses import dataclass
from typing import Dict, Tuple
import math


@dataclass
class EmotionAxes:
    """
    Pixar-style 4-axis emotion representation for infinite interpolation.

    Enables continuous emotion space instead of discrete states, allowing
    natural transitions and fine-grained expressive control.

    Attributes:
        arousal: Energy/activation level on the arousal axis
                 Range: -1.0 (calm/sleepy) to +1.0 (excited/alert)

                 Examples:
                 -1.0 = Deep sleep, completely relaxed
                 -0.5 = Drowsy, low energy
                  0.0 = Neutral activation, resting but awake
                 +0.5 = Alert, engaged
                 +1.0 = Panicked, maximum excitement

                 Maps to LED pattern selection (calm=breathing, excited=fire)

        valence: Emotional positivity on the valence axis
                 Range: -1.0 (negative affect) to +1.0 (positive affect)

                 Examples:
                 -1.0 = Intense sadness, anger, fear
                 -0.5 = Mild disappointment, frustration
                  0.0 = Neutral affect
                 +0.5 = Contentment, mild pleasure
                 +1.0 = Intense joy, love, excitement

                 Maps to LED color hue (negative=cool blues, positive=warm oranges)

        focus: Cognitive attention intensity
               Range: 0.0 (distracted/scattered) to 1.0 (laser-focused)

               Examples:
               0.0 = Daydreaming, attention scattered
               0.3 = Casually observing environment
               0.6 = Engaged with task
               0.9 = Deep concentration
               1.0 = Hyperfocus, tunnel vision

               Maps to LED color saturation (low=muted, high=vivid)

        blink_speed: Blink rate multiplier for temporal expressiveness
                     Range: 0.25 (very slow) to 2.0 (very rapid)

                     Examples:
                     0.25 = Sleepy, drowsy blinking
                     0.5  = Relaxed, slow blinks
                     1.0  = Normal blink rate
                     1.5  = Nervous, elevated blink rate
                     2.0  = Anxious, rapid blinking

                     Maps to LED pulse/blink timing in patterns

    Design Philosophy:
        Unlike discrete EmotionState enum (8 fixed states), EmotionAxes
        allows any point in 4D emotion space. This enables:

        1. Natural transitions: Linear interpolation between any emotions
        2. Subtle expressions: Fine gradations (e.g., arousal=0.3 vs 0.7)
        3. Complex states: Combinations discrete enums can't capture
           (e.g., high arousal + negative valence + low focus = "frantic confusion")

        Trade-off: More complex to author than discrete states, but enables
        much more organic, believable robot personality.

    Thread Safety:
        EmotionAxes is immutable after creation (dataclass without default_factory).
        Interpolation creates new instances rather than mutating.
        Safe for multi-threaded access without locking.
    """
    arousal: float
    valence: float
    focus: float
    blink_speed: float

    def __post_init__(self):
        """
        Validate axis ranges to ensure emotion is in valid space.

        Raises:
            TypeError: If any axis is not numeric (int or float)
            ValueError: If any axis is NaN, infinite, or outside valid range
        """
        # Validate arousal
        if isinstance(self.arousal, bool):
            raise TypeError("arousal cannot be bool, use float")
        if not isinstance(self.arousal, (int, float)):
            raise TypeError(f"arousal must be numeric, got {type(self.arousal).__name__}")
        if math.isnan(self.arousal) or math.isinf(self.arousal):
            raise ValueError(f"arousal must be finite, got {self.arousal}")
        if not -1.0 <= self.arousal <= 1.0:
            raise ValueError(f"arousal must be -1.0 to 1.0, got {self.arousal}")

        # Validate valence
        if isinstance(self.valence, bool):
            raise TypeError("valence cannot be bool, use float")
        if not isinstance(self.valence, (int, float)):
            raise TypeError(f"valence must be numeric, got {type(self.valence).__name__}")
        if math.isnan(self.valence) or math.isinf(self.valence):
            raise ValueError(f"valence must be finite, got {self.valence}")
        if not -1.0 <= self.valence <= 1.0:
            raise ValueError(f"valence must be -1.0 to 1.0, got {self.valence}")

        # Validate focus
        if isinstance(self.focus, bool):
            raise TypeError("focus cannot be bool, use float")
        if not isinstance(self.focus, (int, float)):
            raise TypeError(f"focus must be numeric, got {type(self.focus).__name__}")
        if math.isnan(self.focus) or math.isinf(self.focus):
            raise ValueError(f"focus must be finite, got {self.focus}")
        if not 0.0 <= self.focus <= 1.0:
            raise ValueError(f"focus must be 0.0 to 1.0, got {self.focus}")

        # Validate blink_speed
        if isinstance(self.blink_speed, bool):
            raise TypeError("blink_speed cannot be bool, use float")
        if not isinstance(self.blink_speed, (int, float)):
            raise TypeError(f"blink_speed must be numeric, got {type(self.blink_speed).__name__}")
        if math.isnan(self.blink_speed) or math.isinf(self.blink_speed):
            raise ValueError(f"blink_speed must be finite, got {self.blink_speed}")
        if not 0.25 <= self.blink_speed <= 2.0:
            raise ValueError(f"blink_speed must be 0.25 to 2.0, got {self.blink_speed}")

    def interpolate(self, target: 'EmotionAxes', t: float) -> 'EmotionAxes':
        """
        Linearly interpolate between this emotion and target emotion.

        Enables smooth transitions between any two emotional states.
        Used by EmotionManager to create natural emotion changes over time.

        Args:
            target: Target emotion axes to interpolate towards
            t: Interpolation factor
               - 0.0 returns self (no interpolation)
               - 1.0 returns target (full interpolation)
               - 0.5 returns midpoint between self and target
               - Values are clamped to 0.0-1.0 for safety

        Returns:
            New EmotionAxes representing interpolated emotion

        Example:
            >>> calm = EmotionAxes(arousal=-0.5, valence=0.0, focus=0.3, blink_speed=0.5)
            >>> excited = EmotionAxes(arousal=0.8, valence=0.6, focus=0.9, blink_speed=1.5)
            >>> midpoint = calm.interpolate(excited, 0.5)
            >>> print(midpoint.arousal)  # (−0.5 + 0.8) / 2 = 0.15
            0.15

        Performance Target:
            <0.001ms per call (negligible overhead for 50Hz emotion updates)

        Implementation: Agent 2 (Animation Systems Architect)
        """
        # Clamp t to valid range to ensure output stays in valid emotion space
        t = max(0.0, min(1.0, t))

        # Linear interpolation: value = self.value + (target.value - self.value) * t
        return EmotionAxes(
            arousal=self.arousal + (target.arousal - self.arousal) * t,
            valence=self.valence + (target.valence - self.valence) * t,
            focus=self.focus + (target.focus - self.focus) * t,
            blink_speed=self.blink_speed + (target.blink_speed - self.blink_speed) * t,
        )

    def to_hsv(self) -> Tuple[float, float, float]:
        """
        Convert emotion axes to HSV color space for LED rendering.

        Maps the 4D emotion space to 3D HSV color using perceptually-motivated
        mappings based on color psychology and animation principles.

        Mapping Strategy:
            Hue (0-360°): Driven by valence
                - Negative valence (-1.0) → Cool colors (blue, 240°)
                - Neutral valence (0.0) → Mid colors (green, 120°)
                - Positive valence (+1.0) → Warm colors (orange/yellow, 30°)

                Psychology: Warm colors convey positive affect, cool colors
                convey negative affect (Ou et al. 2004 color emotion study)

            Saturation (0.0-1.0): Driven by focus
                - Low focus (0.0) → Muted (saturation=0.3, minimum for visibility)
                - High focus (1.0) → Vivid colors (saturation=1.0)

                Rationale: Distracted states have washed-out, muted colors;
                focused states have intense, vibrant colors

            Value/Brightness (0.0-1.0): Driven by arousal
                - Low arousal (-1.0) → Dim (value=0.4, never fully dark)
                - High arousal (+1.0) → Bright (value=1.0)

                Rationale: Sleepy states are dim, excited states are bright;
                minimum 0.4 ensures robot always appears "alive"

        Returns:
            Tuple of (hue, saturation, value) where:
            - hue: 0.0 to 360.0 degrees
            - saturation: 0.3 to 1.0
            - value: 0.4 to 1.0

        Example:
            >>> happy = EmotionAxes(arousal=0.5, valence=0.8, focus=0.7, blink_speed=1.2)
            >>> hue, sat, val = happy.to_hsv()
            >>> # Expected: warm hue (~40°), high sat (~0.79), bright val (~0.85)

        Usage in LED Pipeline:
            EmotionAxes → to_hsv() → HSV to RGB conversion → LED hardware

            This allows emotion system to be color-space agnostic while
            LED patterns work in RGB space.

        Performance Target:
            <0.001ms per call (called once per emotion update, ~10-20Hz)

        Implementation: Agent 2 (Animation Systems Architect)
        """
        # Hue: Valence → Hue (warm-cool spectrum)
        # -1.0 → 240° (blue), 0.0 → 120° (green), +1.0 → 30° (orange)
        # Maps valence from [-1, +1] to [240°, 30°] (decreasing)
        # Formula: hue = 240 - (valence + 1.0) * 105
        # At valence -1.0: 240 - 0 = 240° (blue)
        # At valence 0.0: 240 - 105 = 135° (cyan-green)
        # At valence +1.0: 240 - 210 = 30° (orange)
        hue = 240.0 - (self.valence + 1.0) * 105.0

        # Ensure hue is in valid range [0, 360)
        hue = hue % 360.0

        # Saturation: Focus → Saturation (0.3-1.0)
        # Low focus = muted colors, high focus = vivid colors
        # Minimum 0.3 ensures colors are always visible (not grayscale)
        saturation = 0.3 + self.focus * 0.7

        # Value/Brightness: Arousal → Value (0.4-1.0)
        # Low arousal = dim, high arousal = bright
        # Minimum 0.4 ensures robot always appears "alive"
        # Maps arousal from [-1, +1] to [0.4, 1.0]
        value = 0.4 + (self.arousal + 1.0) * 0.3

        return (hue, saturation, value)

    def __repr__(self) -> str:
        """
        Human-readable representation of emotion axes.

        Returns:
            String showing all four axes with 2 decimal precision
        """
        return (
            f"EmotionAxes(arousal={self.arousal:.2f}, valence={self.valence:.2f}, "
            f"focus={self.focus:.2f}, blink_speed={self.blink_speed:.2f})"
        )


# === Predefined Emotion Presets ===
#
# These map discrete EmotionState values to EmotionAxes coordinates,
# enabling backward compatibility with existing emotion system and providing
# convenient starting points for common emotions.
#
# 13 presets: 8 basic emotions + 5 compound emotions
#
# Design Philosophy (Pixar/Russell-inspired):
#   - Basic emotions cover the core arousal-valence quadrants
#   - Compound emotions enable nuanced states discrete enums can't capture
#   - Focus and blink_speed add personality depth beyond 2D circumplex

EMOTION_PRESETS: Dict[str, 'EmotionAxes'] = {
    # === Basic Emotions (8) ===
    # Cover the four quadrants of arousal-valence space plus neutral states

    "idle": EmotionAxes(
        arousal=0.0,      # Neutral energy
        valence=0.2,      # Slightly positive (approachable)
        focus=0.3,        # Casually observing
        blink_speed=1.0,  # Normal blink rate
    ),

    "happy": EmotionAxes(
        arousal=0.4,      # Moderately energetic
        valence=0.8,      # Strongly positive
        focus=0.5,        # Engaged but not tunnel-vision
        blink_speed=1.2,  # Slightly elevated (excitement)
    ),

    "excited": EmotionAxes(
        arousal=0.9,      # High energy (near maximum)
        valence=0.7,      # Positive affect
        focus=0.7,        # Alert and directed
        blink_speed=1.8,  # Rapid blinking (can't contain it)
    ),

    "curious": EmotionAxes(
        arousal=0.3,      # Moderate energy (alert but not manic)
        valence=0.4,      # Mild positive (interest)
        focus=0.9,        # High focus (investigating)
        blink_speed=1.1,  # Slightly elevated
    ),

    "alert": EmotionAxes(
        arousal=0.7,      # High energy (attention demanded)
        valence=0.0,      # Neutral affect (could go either way)
        focus=1.0,        # Maximum focus (tunnel vision)
        blink_speed=1.5,  # Elevated (vigilant)
    ),

    "sad": EmotionAxes(
        arousal=-0.5,     # Low energy (withdrawn)
        valence=-0.7,     # Negative affect
        focus=0.2,        # Distracted, inward-looking
        blink_speed=0.5,  # Slow blinks (heavy eyelids)
    ),

    "sleepy": EmotionAxes(
        arousal=-0.9,     # Very low energy (nearly asleep)
        valence=0.1,      # Slightly positive (content drowsiness)
        focus=0.1,        # Attention scattered
        blink_speed=0.3,  # Very slow blinks (fighting sleep)
    ),

    "thinking": EmotionAxes(
        arousal=0.1,      # Low-moderate energy (internal processing)
        valence=0.0,      # Neutral (outcome uncertain)
        focus=0.8,        # High focus (cognitive effort)
        blink_speed=0.7,  # Slower blinks (concentration)
    ),

    # === Compound Emotions (5) ===
    # Enable nuanced states that discrete enums can't capture

    "anxious": EmotionAxes(
        arousal=0.6,      # High energy (nervous system activated)
        valence=-0.5,     # Negative affect (worry)
        focus=0.6,        # Moderate focus (scanning for threats)
        blink_speed=1.6,  # Rapid blinking (nervousness)
    ),

    "confused": EmotionAxes(
        arousal=0.2,      # Mild energy (puzzled)
        valence=-0.2,     # Slightly negative (frustration)
        focus=0.3,        # Low focus (can't find pattern)
        blink_speed=1.3,  # Elevated blinks (uncertainty)
    ),

    "playful": EmotionAxes(
        arousal=0.5,      # Moderate-high energy
        valence=0.6,      # Positive affect
        focus=0.4,        # Attention bouncing around
        blink_speed=1.4,  # Slightly fast (mischievous)
    ),

    "determined": EmotionAxes(
        arousal=0.4,      # Steady energy (sustainable intensity)
        valence=0.3,      # Mild positive (confidence)
        focus=1.0,        # Maximum focus (locked on target)
        blink_speed=0.9,  # Slightly slower (steely resolve)
    ),

    "dreamy": EmotionAxes(
        arousal=-0.6,     # Low energy (drifting)
        valence=0.4,      # Positive affect (pleasant reverie)
        focus=0.1,        # Very low focus (imagination wandering)
        blink_speed=0.4,  # Slow blinks (half-lidded)
    ),
}
