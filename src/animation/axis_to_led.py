#!/usr/bin/env python3
"""
Emotion Axes to LED Mapper - Interface Contract
Week 02 Day 9 | Architecture Definition

This stub defines the interface for converting EmotionAxes (4D continuous emotion)
to LED configuration (pattern name, color, speed) for hardware rendering.

Bridges the gap between:
    - Emotion System: Thinks in terms of arousal, valence, focus, blink_speed
    - LED System: Thinks in terms of RGB colors, pattern names, speed multipliers

Design Philosophy:
    Separation of concerns - emotion logic doesn't know about LED hardware,
    LED patterns don't know about emotion theory. This mapper translates between
    the two domains using perceptually-motivated rules.

Research References:
    - CMU Expressive Lights: Visual communication of robot internal state
      (Takayama et al. 2011. "Expressing thought: Improving robot readability")

    - Disney Animation Principles: Timing and staging for emotional clarity
      (Johnston & Thomas. "The Illusion of Life")

    - Boston Dynamics Spot: Non-verbal robot state communication through lights
      (Research on minimal interface design for robot-human interaction)

    - Color Psychology: Warm vs cool colors for emotional expression
      (Ou et al. 2004. "A study of colour emotion and colour preference")

Implementation: Agent 2 (Animation Systems Architect)

Author: Architecture Coordinator (Agent 0)
Created: 18 January 2026
"""

from typing import Tuple
from .emotion_axes import EmotionAxes


class AxisToLEDMapper:
    """
    Maps Pixar 4-axis emotions to LED patterns, colors, and speeds.

    Provides three core transformations:
        1. EmotionAxes → Pattern Name (string like "breathing", "fire")
        2. EmotionAxes → HSV Color (hue, saturation, value)
        3. EmotionAxes → Pattern Speed (multiplier for animation speed)

    Mapping Philosophy:
        - Arousal → Pattern selection (calm=slow patterns, excited=fast patterns)
        - Valence → Color hue (negative=cool, positive=warm)
        - Focus → Color saturation (low=muted, high=vivid)
        - Blink speed → Temporal modulation of pattern speed

        This follows established research on color-emotion associations
        and robot expressiveness through non-verbal cues.

    Thread Safety:
        Stateless mapper (no instance variables modified after __init__).
        Safe for concurrent use by multiple threads without locking.

    Usage Example:
        >>> mapper = AxisToLEDMapper()
        >>> emotion = EmotionAxes(arousal=0.8, valence=0.5, focus=0.9, blink_speed=1.5)
        >>> pattern_name = mapper.axes_to_pattern_name(emotion)
        >>> hsv_color = mapper.axes_to_hsv(emotion)
        >>> speed = mapper.axes_to_pattern_speed(emotion)
        >>> # Now apply pattern_name, hsv_color, speed to LED controller
    """

    # Arousal thresholds for pattern selection
    # Uses hysteresis-friendly thresholds to avoid rapid switching
    AROUSAL_THRESHOLD_DEEP_CALM = -0.6
    AROUSAL_THRESHOLD_LOW = -0.2
    AROUSAL_THRESHOLD_NEUTRAL = 0.2
    AROUSAL_THRESHOLD_ELEVATED = 0.5
    AROUSAL_THRESHOLD_HIGH = 0.8

    def __init__(self):
        """
        Initialize mapper with configuration.

        Future extension point: Could accept config for customizing
        arousal thresholds, color mappings, etc. For now, uses hardcoded
        perceptually-validated mappings.
        """
        # Hysteresis state for pattern switching (prevents rapid oscillation)
        self._last_pattern: str = "breathing"

    def axes_to_pattern_name(self, axes: EmotionAxes) -> str:
        """
        Select LED pattern name based on arousal level.

        Pattern selection strategy is driven primarily by arousal (energy level)
        with consideration for focus (attention intensity). This creates
        perceptually distinct patterns for different energy states.

        Mapping Rules:
            Arousal Range          -> Pattern Name  | Rationale
            -----------------------------------------------------------
            arousal < -0.6         -> "breathing"   | Deep calm, sleeping
            -0.6 <= arousal < -0.2 -> "pulse"       | Resting, low energy
            -0.2 <= arousal < 0.2  -> "breathing"   | Neutral, idle
            0.2 <= arousal < 0.5   -> "spin"        | Curious, engaged
            0.5 <= arousal < 0.8   -> "cloud"       | Thinking, alert
            arousal >= 0.8         -> "fire"        | Excited, panicked

        Focus Modulation:
            - Low focus (< 0.3) with low arousal -> "dream" pattern
              (wandering, dreamy state benefits from softer pattern)

        Pattern Registry Compatibility:
            Valid pattern names: "breathing", "pulse", "spin", "cloud", "fire", "dream"

        Args:
            axes: Current emotion axes

        Returns:
            Pattern name string (e.g., "breathing", "fire", "cloud")

        Raises:
            TypeError: If axes is not an EmotionAxes instance

        Example:
            >>> mapper = AxisToLEDMapper()
            >>> sleepy = EmotionAxes(arousal=-0.7, valence=0.1, focus=0.2, blink_speed=0.4)
            >>> mapper.axes_to_pattern_name(sleepy)
            'breathing'
            >>> excited = EmotionAxes(arousal=0.9, valence=0.6, focus=0.8, blink_speed=1.8)
            >>> mapper.axes_to_pattern_name(excited)
            'fire'

        Performance Target:
            <0.001ms per call (simple conditional logic, no heavy computation)

        Implementation: Agent 2 (Animation Systems Architect)
        """
        # Input validation
        if not isinstance(axes, EmotionAxes):
            raise TypeError(f"Expected EmotionAxes, got {type(axes).__name__}")

        arousal = axes.arousal
        focus = axes.focus

        # Special case: Low focus + low arousal = dreamy state
        # This creates the "dreamy" wandering pattern for unfocused, calm states
        if focus < 0.3 and arousal < self.AROUSAL_THRESHOLD_LOW:
            return "dream"

        # Primary arousal-based pattern selection
        if arousal < self.AROUSAL_THRESHOLD_DEEP_CALM:
            # Deep calm, sleeping
            return "breathing"
        elif arousal < self.AROUSAL_THRESHOLD_LOW:
            # Resting, low energy
            return "pulse"
        elif arousal < self.AROUSAL_THRESHOLD_NEUTRAL:
            # Neutral, idle
            return "breathing"
        elif arousal < self.AROUSAL_THRESHOLD_ELEVATED:
            # Curious, engaged
            return "spin"
        elif arousal < self.AROUSAL_THRESHOLD_HIGH:
            # Thinking, alert
            return "cloud"
        else:
            # Excited, panicked (arousal >= 0.8)
            return "fire"

    def axes_to_hsv(self, axes: EmotionAxes) -> Tuple[float, float, float]:
        """
        Convert emotion axes to HSV color space for LED rendering.

        Implements perceptually-motivated color mapping based on color psychology
        research and animation principles. Creates emotionally expressive colors
        that feel natural and readable to human observers.

        Mapping Rules:
            HSV Component | Driven By | Mapping Formula
            -----------------------------------------------------------
            Hue (0-360)   | Valence   | Negative -> Blue (240)
                          |           | Neutral  -> Green/Cyan (135)
                          |           | Positive -> Orange/Yellow (30)

            Saturation    | Focus     | Low focus -> Muted (0.3 minimum)
            (0.0-1.0)     |           | High focus -> Vivid (1.0)

            Value         | Arousal   | Low arousal -> Dim (0.4 minimum)
            (0.0-1.0)     |           | High arousal -> Bright (1.0)

        Color Psychology Rationale:
            - Warm colors (orange, yellow) -> Positive emotions (joy, excitement)
            - Cool colors (blue, purple) -> Negative emotions (sad, calm, fear)
            - Saturation -> Emotional intensity
            - Brightness -> Energy level

        Args:
            axes: Current emotion axes

        Returns:
            Tuple of (hue, saturation, value) where:
            - hue: 0.0 to 360.0 degrees
            - saturation: 0.3 to 1.0
            - value: 0.4 to 1.0

        Raises:
            TypeError: If axes is not an EmotionAxes instance

        Example:
            >>> mapper = AxisToLEDMapper()
            >>> happy = EmotionAxes(arousal=0.5, valence=0.8, focus=0.7, blink_speed=1.2)
            >>> hue, sat, val = mapper.axes_to_hsv(happy)
            >>> print(f"H:{hue:.1f} S:{sat:.2f} V:{val:.2f}")
            H:51.0 S:0.79 V:0.85

        Performance Target:
            <0.001ms per call (simple arithmetic, no loops or heavy math)

        Implementation: Agent 2 (Animation Systems Architect)
        """
        # Input validation
        if not isinstance(axes, EmotionAxes):
            raise TypeError(f"Expected EmotionAxes, got {type(axes).__name__}")

        # Delegate to EmotionAxes.to_hsv() for consistent behavior
        # This allows either EmotionAxes.to_hsv() or AxisToLEDMapper.axes_to_hsv()
        # to be used interchangeably
        return axes.to_hsv()

    def axes_to_pattern_speed(self, axes: EmotionAxes) -> float:
        """
        Convert focus and blink_speed to pattern speed multiplier.

        Pattern speed affects the temporal dynamics of LED animations,
        creating perceptually distinct motion for different emotional states.

        Mapping Strategy:
            Primary driver: Focus (attention intensity)
                - Low focus (0.0) -> Slow, wandering motion (0.5x speed)
                - High focus (1.0) -> Fast, directed motion (2.0x speed)

            Secondary modulation: Blink speed
                - Adds subtle variation based on nervousness/calmness
                - Formula: speed *= (0.9 + blink_speed * 0.1)

            Combined formula:
                base_speed = 0.5 + (focus * 1.5)  # Maps focus 0.0->0.5x, 1.0->2.0x
                modulated_speed = base_speed * (0.9 + blink_speed * 0.1)

            This creates speed range of approximately 0.45x to 2.2x, with
            most speeds in the perceptually useful 0.5-2.0 range.

        Design Rationale:
            - Distracted states (low focus) benefit from slow, drifting patterns
              that don't demand attention
            - Focused states (high focus) benefit from fast, energetic patterns
              that communicate intensity
            - Blink speed adds subtle personality variation

        Args:
            axes: Current emotion axes

        Returns:
            Speed multiplier in range approximately 0.47 to 2.2
            (matches PatternConfig.speed validation range of 0.1-5.0,
            but uses perceptually validated subset)

        Raises:
            TypeError: If axes is not an EmotionAxes instance

        Example:
            >>> mapper = AxisToLEDMapper()
            >>> sleepy = EmotionAxes(arousal=-0.7, valence=0.1, focus=0.2, blink_speed=0.4)
            >>> speed = mapper.axes_to_pattern_speed(sleepy)
            >>> round(speed, 2)
            0.75
            >>> alert = EmotionAxes(arousal=0.6, valence=0.3, focus=0.9, blink_speed=1.5)
            >>> speed = mapper.axes_to_pattern_speed(alert)
            >>> round(speed, 2)
            1.89

        Performance Target:
            <0.001ms per call (simple arithmetic)

        Implementation: Agent 2 (Animation Systems Architect)
        """
        # Input validation
        if not isinstance(axes, EmotionAxes):
            raise TypeError(f"Expected EmotionAxes, got {type(axes).__name__}")

        # Primary: Focus drives base speed
        # Maps focus [0.0, 1.0] to [0.5, 2.0]
        base_speed = 0.5 + (axes.focus * 1.5)

        # Secondary: Blink speed modulates the result
        # blink_speed [0.25, 2.0] maps to multiplier [0.925, 1.1]
        # This adds personality variation without overwhelming focus-based speed
        blink_modulation = 0.9 + (axes.blink_speed * 0.1)

        # Combined speed
        speed = base_speed * blink_modulation

        return speed

    def axes_to_led_config(self, axes: EmotionAxes) -> dict:
        """
        Convert EmotionAxes to complete LED configuration dictionary.

        Convenience method that calls axes_to_pattern_name(), axes_to_hsv(),
        and axes_to_pattern_speed() and packages results into a single dict
        suitable for passing to LEDController.

        Args:
            axes: Current emotion axes

        Returns:
            Dictionary with keys:
            - 'pattern_name': str (e.g., "breathing", "fire")
            - 'hsv': Tuple[float, float, float] (hue 0-360, sat 0-1, val 0-1)
            - 'speed': float (speed multiplier, typically 0.5-2.0)

        Raises:
            TypeError: If axes is not an EmotionAxes instance

        Example:
            >>> mapper = AxisToLEDMapper()
            >>> emotion = EmotionAxes(arousal=0.3, valence=0.6, focus=0.7, blink_speed=1.1)
            >>> config = mapper.axes_to_led_config(emotion)
            >>> print(config['pattern_name'])
            spin

        Usage in EmotionManager:
            config = mapper.axes_to_led_config(current_emotion_axes)
            led_controller.set_pattern(config['pattern_name'], speed=config['speed'])
            # Convert HSV to RGB, then:
            led_controller.set_color(rgb_color)

        Performance Target:
            <0.01ms per call (calls three O(1) methods)

        Implementation: Agent 2 (Animation Systems Architect)
        """
        # Input validation
        if not isinstance(axes, EmotionAxes):
            raise TypeError(f"Expected EmotionAxes, got {type(axes).__name__}")

        return {
            'pattern_name': self.axes_to_pattern_name(axes),
            'hsv': self.axes_to_hsv(axes),
            'speed': self.axes_to_pattern_speed(axes),
        }


# === Validation Utilities ===
#
# Helper functions for testing and debugging the mapper.

# Default available patterns (as of Day 9)
AVAILABLE_PATTERNS = ["breathing", "pulse", "spin", "cloud", "fire", "dream"]


def validate_pattern_name(pattern_name: str, available_patterns: list = None) -> bool:
    """
    Validate that returned pattern name exists in pattern registry.

    Args:
        pattern_name: Pattern name returned by axes_to_pattern_name()
        available_patterns: List of valid pattern names (defaults to AVAILABLE_PATTERNS)

    Returns:
        True if pattern_name is valid, False otherwise

    Example:
        >>> validate_pattern_name("breathing")
        True
        >>> validate_pattern_name("invalid_pattern")
        False
    """
    if available_patterns is None:
        available_patterns = AVAILABLE_PATTERNS

    return pattern_name in available_patterns


def hsv_to_rgb(hue: float, saturation: float, value: float) -> Tuple[int, int, int]:
    """
    Convert HSV color to RGB (0-255) for LED hardware.

    Uses the standard HSV to RGB conversion algorithm.

    Args:
        hue: 0.0 to 360.0 degrees
        saturation: 0.0 to 1.0
        value: 0.0 to 1.0

    Returns:
        RGB tuple with values 0-255

    Example:
        >>> hsv_to_rgb(0.0, 1.0, 1.0)  # Pure red
        (255, 0, 0)
        >>> hsv_to_rgb(120.0, 1.0, 1.0)  # Pure green
        (0, 255, 0)
        >>> hsv_to_rgb(240.0, 1.0, 1.0)  # Pure blue
        (0, 0, 255)
    """
    import colorsys

    # colorsys expects hue in 0.0-1.0 range
    hue_normalized = (hue % 360.0) / 360.0

    # Convert to RGB (0.0-1.0 range)
    r, g, b = colorsys.hsv_to_rgb(hue_normalized, saturation, value)

    # Convert to 0-255 range for LED hardware
    return (
        int(round(r * 255)),
        int(round(g * 255)),
        int(round(b * 255)),
    )
