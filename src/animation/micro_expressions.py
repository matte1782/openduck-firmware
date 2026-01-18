#!/usr/bin/env python3
"""
Micro-Expression System - OpenDuck Mini V3
Day 10 Foundation for Day 11 Implementation

Provides subtle LED pattern modifications that add
personality and liveliness to robot expressions.

Disney Animation Principle: Secondary Action
- Small supporting movements enhance main emotion
- Never compete with primary expression

Micro-expressions are brief, subtle changes in LED patterns:
- Eye flicker (surprise/startle)
- Brow raise (interest/curiosity)
- Squint (focus/concentration)
- Eye widening (fear/surprise)
- Narrowing (anger/determination)

Research Foundation:
    - Anki Cozmo Emotion Engine: Continuous subtle behaviors
    - Disney "12 Principles of Animation": Secondary Action
    - Boston Dynamics Spot: Expressive state overlays
    - Paul Ekman FACS: Micro-expression categorization

Author: Boston Dynamics Micro-Expression Architect
Created: 18 January 2026 (Day 10)
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import Optional, List, Callable, Dict, Any
import time
import random
import math


class MicroExpressionType(Enum):
    """
    Types of micro-expressions available.

    Each type corresponds to a distinct visual behavior that can
    overlay on top of the primary emotion pattern.

    Inspired by Paul Ekman's Facial Action Coding System (FACS)
    adapted for LED ring "eyes".
    """
    BLINK = "blink"           # Quick eye close/open (all LEDs dim briefly)
    FLICKER = "flicker"       # Surprised flash (brightness spike)
    SQUINT = "squint"         # Narrow focus (top/bottom LEDs dim, center bright)
    WIDEN = "widen"           # Fear/surprise enlargement (all LEDs brighten)
    GLANCE = "glance"         # Quick directional look (asymmetric brightness)
    TWITCH = "twitch"         # Nervous energy (rapid small variations)
    DROOP = "droop"           # Sadness indicator (top LEDs dim progressively)
    SPARKLE = "sparkle"       # Joy indicator (random LED brightness pops)


@dataclass
class MicroExpression:
    """
    Configuration for a single micro-expression.

    Defines the parameters needed to render a specific micro-expression
    on the LED rings. Immutable after creation for thread safety.

    Attributes:
        expression_type: The type of micro-expression
        duration_ms: How long the expression lasts in milliseconds
        intensity: Strength of the effect (0.0 = invisible, 1.0 = maximum)
        trigger_emotion: Optional emotion name that triggers this expression
        cooldown_ms: Minimum time between repeated triggers
        priority: Higher priority expressions override lower ones

    Validation:
        - duration_ms must be positive (1-5000ms reasonable range)
        - intensity must be 0.0-1.0
        - cooldown_ms must be non-negative
        - priority must be 0-100
    """
    expression_type: MicroExpressionType
    duration_ms: int
    intensity: float
    trigger_emotion: Optional[str] = None
    cooldown_ms: int = 0
    priority: int = 50

    def __post_init__(self):
        """Validate micro-expression configuration."""
        # Validate expression_type
        if not isinstance(self.expression_type, MicroExpressionType):
            raise TypeError(
                f"expression_type must be MicroExpressionType, "
                f"got {type(self.expression_type).__name__}"
            )

        # Validate duration_ms
        if not isinstance(self.duration_ms, int):
            raise TypeError(
                f"duration_ms must be int, got {type(self.duration_ms).__name__}"
            )
        if self.duration_ms <= 0:
            raise ValueError(
                f"duration_ms must be positive, got {self.duration_ms}"
            )
        if self.duration_ms > 5000:
            raise ValueError(
                f"duration_ms exceeds maximum (5000ms), got {self.duration_ms}. "
                f"Micro-expressions should be brief."
            )

        # Validate intensity
        if not isinstance(self.intensity, (int, float)):
            raise TypeError(
                f"intensity must be numeric, got {type(self.intensity).__name__}"
            )
        if math.isnan(self.intensity) or math.isinf(self.intensity):
            raise ValueError(f"intensity must be finite, got {self.intensity}")
        if not 0.0 <= self.intensity <= 1.0:
            raise ValueError(
                f"intensity must be 0.0-1.0, got {self.intensity}"
            )

        # Validate cooldown_ms
        if not isinstance(self.cooldown_ms, int):
            raise TypeError(
                f"cooldown_ms must be int, got {type(self.cooldown_ms).__name__}"
            )
        if self.cooldown_ms < 0:
            raise ValueError(
                f"cooldown_ms must be non-negative, got {self.cooldown_ms}"
            )

        # Validate priority
        if not isinstance(self.priority, int):
            raise TypeError(
                f"priority must be int, got {type(self.priority).__name__}"
            )
        if not 0 <= self.priority <= 100:
            raise ValueError(
                f"priority must be 0-100, got {self.priority}"
            )


# === Micro-Expression Presets ===
#
# Common micro-expression configurations for easy triggering.
# Tuned to feel natural and aligned with Pixar animation principles.

MICRO_EXPRESSION_PRESETS: Dict[str, MicroExpression] = {
    # === Blink Variants ===
    "blink_normal": MicroExpression(
        expression_type=MicroExpressionType.BLINK,
        duration_ms=150,      # Standard human blink duration
        intensity=0.7,        # 70% dim (not fully black)
        cooldown_ms=3000,     # Minimum 3s between blinks
        priority=30,          # Low priority (background behavior)
    ),

    "blink_slow": MicroExpression(
        expression_type=MicroExpressionType.BLINK,
        duration_ms=400,      # Sleepy blink
        intensity=0.8,        # Deeper close
        trigger_emotion="sleepy",
        cooldown_ms=2000,
        priority=30,
    ),

    "blink_rapid": MicroExpression(
        expression_type=MicroExpressionType.BLINK,
        duration_ms=80,       # Quick nervous blink
        intensity=0.5,        # Partial close
        trigger_emotion="anxious",
        cooldown_ms=500,      # Can happen frequently
        priority=40,
    ),

    # === Flicker (Surprise) ===
    "flicker_surprise": MicroExpression(
        expression_type=MicroExpressionType.FLICKER,
        duration_ms=100,      # Very brief flash
        intensity=0.9,        # Strong effect
        trigger_emotion="alert",
        cooldown_ms=1000,
        priority=60,          # Higher priority (attention-grabbing)
    ),

    "flicker_subtle": MicroExpression(
        expression_type=MicroExpressionType.FLICKER,
        duration_ms=50,       # Nearly imperceptible
        intensity=0.3,        # Gentle
        cooldown_ms=500,
        priority=20,
    ),

    # === Squint (Focus/Concentration) ===
    "squint_focus": MicroExpression(
        expression_type=MicroExpressionType.SQUINT,
        duration_ms=800,      # Sustained
        intensity=0.6,        # Moderate effect
        trigger_emotion="thinking",
        cooldown_ms=2000,
        priority=45,
    ),

    "squint_suspicion": MicroExpression(
        expression_type=MicroExpressionType.SQUINT,
        duration_ms=1200,     # Longer hold
        intensity=0.7,        # More pronounced
        trigger_emotion="curious",
        cooldown_ms=3000,
        priority=50,
    ),

    # === Widen (Fear/Surprise) ===
    "widen_fear": MicroExpression(
        expression_type=MicroExpressionType.WIDEN,
        duration_ms=500,      # Quick startle
        intensity=0.8,        # Strong
        trigger_emotion="alert",
        cooldown_ms=1500,
        priority=70,          # High priority (danger response)
    ),

    "widen_interest": MicroExpression(
        expression_type=MicroExpressionType.WIDEN,
        duration_ms=300,      # Brief
        intensity=0.4,        # Gentle widening
        trigger_emotion="curious",
        cooldown_ms=2000,
        priority=40,
    ),

    # === Glance (Directional Look) ===
    "glance_left": MicroExpression(
        expression_type=MicroExpressionType.GLANCE,
        duration_ms=200,      # Quick look
        intensity=0.5,        # Moderate asymmetry
        cooldown_ms=1000,
        priority=35,
    ),

    "glance_right": MicroExpression(
        expression_type=MicroExpressionType.GLANCE,
        duration_ms=200,
        intensity=0.5,
        cooldown_ms=1000,
        priority=35,
    ),

    # === Twitch (Nervous Energy) ===
    "twitch_nervous": MicroExpression(
        expression_type=MicroExpressionType.TWITCH,
        duration_ms=50,       # Very brief
        intensity=0.3,        # Subtle
        trigger_emotion="anxious",
        cooldown_ms=200,      # Can repeat frequently
        priority=25,
    ),

    "twitch_excited": MicroExpression(
        expression_type=MicroExpressionType.TWITCH,
        duration_ms=60,
        intensity=0.4,
        trigger_emotion="excited",
        cooldown_ms=300,
        priority=30,
    ),

    # === Droop (Sadness) ===
    "droop_sad": MicroExpression(
        expression_type=MicroExpressionType.DROOP,
        duration_ms=1500,     # Slow, lingering
        intensity=0.6,        # Noticeable
        trigger_emotion="sad",
        cooldown_ms=5000,
        priority=40,
    ),

    "droop_tired": MicroExpression(
        expression_type=MicroExpressionType.DROOP,
        duration_ms=2000,     # Very slow
        intensity=0.7,
        trigger_emotion="sleepy",
        cooldown_ms=4000,
        priority=35,
    ),

    # === Sparkle (Joy) ===
    "sparkle_happy": MicroExpression(
        expression_type=MicroExpressionType.SPARKLE,
        duration_ms=300,      # Brief twinkle
        intensity=0.6,
        trigger_emotion="happy",
        cooldown_ms=800,
        priority=35,
    ),

    "sparkle_excited": MicroExpression(
        expression_type=MicroExpressionType.SPARKLE,
        duration_ms=200,      # Rapid sparkles
        intensity=0.8,
        trigger_emotion="excited",
        cooldown_ms=400,      # More frequent
        priority=40,
    ),
}


@dataclass
class _ActiveExpression:
    """
    Internal state for a currently playing micro-expression.

    Tracks progress and timing for smooth animation.
    Not part of public API.
    """
    expression: MicroExpression
    start_time: float
    progress: float = 0.0

    @property
    def elapsed_ms(self) -> float:
        """Milliseconds since expression started."""
        return (time.monotonic() - self.start_time) * 1000

    @property
    def is_complete(self) -> bool:
        """Check if expression has finished playing."""
        return self.elapsed_ms >= self.expression.duration_ms


class MicroExpressionEngine:
    """
    Manages and triggers micro-expressions.

    The engine maintains a queue of active micro-expressions and
    blends them with the primary emotion pattern. Handles timing,
    cooldowns, and priority-based expression selection.

    Architecture:
        LEDManager -> PatternRenderer -> MicroExpressionEngine -> LED Output
                                               |
                                        (brightness modulation)

    Usage:
        >>> engine = MicroExpressionEngine(led_controller)
        >>> engine.trigger(MicroExpressionType.BLINK)
        >>> engine.update(delta_ms=20)  # Call every frame
        >>> brightness_mod = engine.get_brightness_modifier()

    Thread Safety Warning:
        ========================================================================
        THIS CLASS IS NOT THREAD-SAFE. All methods must be called from a single
        thread (typically the LED update loop). Concurrent access from multiple
        threads will cause race conditions and undefined behavior.

        For multi-threaded environments, protect all calls with external locking:
            lock = threading.Lock()
            with lock:
                engine.trigger(MicroExpressionType.BLINK)

        Affected state: _active_expression, _expression_queue, _cooldown_timers,
                        _brightness_modifier, _per_pixel_modifiers
        ========================================================================

    Day 11 Implementation Notes:
        - _render_expression() needs pattern-specific implementations
        - LED controller integration needs hardware testing
        - Consider adding expression blending for multiple simultaneous effects
    """

    # Maximum concurrent expressions (performance limit)
    MAX_ACTIVE_EXPRESSIONS = 3

    def __init__(self, led_controller=None, num_leds: int = 16):
        """
        Initialize micro-expression engine.

        Args:
            led_controller: Optional LED controller for direct output
                           (can be None for testing/offline use)
            num_leds: Number of LEDs per eye ring (default 16)
        """
        self.led_controller = led_controller
        self.num_leds = num_leds

        # Active expression tracking
        self._active_expression: Optional[_ActiveExpression] = None
        self._expression_queue: List[MicroExpression] = []

        # Timing
        self._last_update: float = time.monotonic()
        self._cooldown_timers: Dict[MicroExpressionType, float] = {}

        # Output modifiers (computed each update)
        self._brightness_modifier: float = 1.0
        self._per_pixel_modifiers: List[float] = [1.0] * num_leds

        # Callbacks for expression events
        self._callbacks: List[Callable[[MicroExpressionType, str], None]] = []

        # Random number generator (seeded for reproducible tests)
        self._rng = random.Random()

    def trigger(
        self,
        expression_type: MicroExpressionType,
        duration_ms: int = 100,
        intensity: float = 0.8,
        force: bool = False
    ) -> bool:
        """
        Trigger a micro-expression.

        Args:
            expression_type: Type of expression to trigger
            duration_ms: Duration in milliseconds (1-5000)
            intensity: Effect strength (0.0-1.0)
            force: If True, bypass cooldown check

        Returns:
            True if expression was triggered, False if blocked by cooldown

        Raises:
            ValueError: If duration_ms or intensity out of range
        """
        # Create expression config
        try:
            expression = MicroExpression(
                expression_type=expression_type,
                duration_ms=duration_ms,
                intensity=intensity
            )
        except (TypeError, ValueError) as e:
            raise ValueError(f"Invalid expression parameters: {e}")

        return self._trigger_expression(expression, force)

    def trigger_preset(self, preset_name: str, force: bool = False) -> bool:
        """
        Trigger a preset micro-expression by name.

        Args:
            preset_name: Name from MICRO_EXPRESSION_PRESETS
            force: If True, bypass cooldown check

        Returns:
            True if expression was triggered

        Raises:
            KeyError: If preset_name not found
        """
        if preset_name not in MICRO_EXPRESSION_PRESETS:
            available = list(MICRO_EXPRESSION_PRESETS.keys())
            raise KeyError(
                f"Unknown preset: {preset_name}. "
                f"Available: {available}"
            )

        expression = MICRO_EXPRESSION_PRESETS[preset_name]
        return self._trigger_expression(expression, force)

    def _trigger_expression(
        self,
        expression: MicroExpression,
        force: bool
    ) -> bool:
        """
        Internal method to trigger an expression.

        Handles cooldown checking and priority comparison.
        """
        now = time.monotonic()
        expr_type = expression.expression_type

        # Check cooldown (unless forced)
        if not force:
            cooldown_end = self._cooldown_timers.get(expr_type, 0.0)
            if now < cooldown_end:
                return False  # Still in cooldown

        # Check priority against current active expression
        if self._active_expression is not None:
            current_priority = self._active_expression.expression.priority
            if expression.priority < current_priority:
                # Queue it for later
                self._expression_queue.append(expression)
                self._expression_queue.sort(key=lambda e: e.priority, reverse=True)
                # Trim queue if too long
                if len(self._expression_queue) > self.MAX_ACTIVE_EXPRESSIONS:
                    self._expression_queue = self._expression_queue[:self.MAX_ACTIVE_EXPRESSIONS]
                return True

        # Activate the expression
        self._active_expression = _ActiveExpression(
            expression=expression,
            start_time=now
        )

        # Set cooldown timer
        cooldown_s = expression.cooldown_ms / 1000.0
        self._cooldown_timers[expr_type] = now + cooldown_s

        # Fire callbacks
        # FIX H-NEW-003: Log callback errors instead of silent swallow
        for callback in self._callbacks:
            try:
                callback(expr_type, "started")
            except Exception as e:
                _logger.debug(f"Callback error (started): {e}")  # Don't break engine

        return True

    def update(self, delta_ms: float) -> bool:
        """
        Update active micro-expression. Call every frame.

        Args:
            delta_ms: Milliseconds since last update

        Returns:
            True if a micro-expression is currently active
        """
        now = time.monotonic()
        self._last_update = now

        if self._active_expression is None:
            # Check queue for pending expressions
            if self._expression_queue:
                next_expr = self._expression_queue.pop(0)
                return self._trigger_expression(next_expr, force=True)

            # Reset modifiers when nothing active
            self._brightness_modifier = 1.0
            self._per_pixel_modifiers = [1.0] * self.num_leds
            return False

        # Update progress
        active = self._active_expression
        active.progress = min(1.0, active.elapsed_ms / active.expression.duration_ms)

        # Compute brightness modifiers based on expression type
        self._compute_modifiers(active)

        # Check if complete
        if active.is_complete:
            expr_type = active.expression.expression_type

            # Fire completion callbacks
            # FIX H-NEW-003: Log callback errors instead of silent swallow
            for callback in self._callbacks:
                try:
                    callback(expr_type, "completed")
                except Exception as e:
                    _logger.debug(f"Callback error (completed): {e}")

            # Clear active expression
            self._active_expression = None

            # Check queue for next expression
            if self._expression_queue:
                next_expr = self._expression_queue.pop(0)
                self._trigger_expression(next_expr, force=True)

        return self._active_expression is not None

    def _compute_modifiers(self, active: _ActiveExpression) -> None:
        """
        Compute brightness modifiers based on expression type and progress.

        Day 11 Implementation: Add pattern-specific rendering logic here.
        """
        expr = active.expression
        progress = active.progress
        intensity = expr.intensity

        # Apply Disney-style ease curve to progress
        # Slow in, slow out for natural feeling
        eased_progress = self._ease_in_out(progress)

        if expr.expression_type == MicroExpressionType.BLINK:
            # Blink: All LEDs dim during middle of animation
            # Peak darkness at progress=0.5
            blink_amount = math.sin(eased_progress * math.pi)
            self._brightness_modifier = 1.0 - (blink_amount * intensity)
            self._per_pixel_modifiers = [self._brightness_modifier] * self.num_leds

        elif expr.expression_type == MicroExpressionType.FLICKER:
            # Flicker: Quick brightness spike
            # Peak brightness at progress=0.3 (front-loaded)
            if progress < 0.3:
                flicker = progress / 0.3
            else:
                flicker = 1.0 - (progress - 0.3) / 0.7
            self._brightness_modifier = 1.0 + (flicker * intensity * 0.5)
            self._per_pixel_modifiers = [self._brightness_modifier] * self.num_leds

        elif expr.expression_type == MicroExpressionType.SQUINT:
            # Squint: Top and bottom LEDs dim, center stays bright
            # Creates "narrowed eye" appearance
            self._brightness_modifier = 1.0
            for i in range(self.num_leds):
                # Distance from center (normalized 0-1)
                center = self.num_leds / 2
                dist_from_center = abs(i - center) / center
                # Dim edges more than center
                edge_dim = dist_from_center * intensity * eased_progress
                self._per_pixel_modifiers[i] = 1.0 - edge_dim * 0.5

        elif expr.expression_type == MicroExpressionType.WIDEN:
            # Widen: All LEDs brighten (opposite of blink)
            widen_amount = math.sin(eased_progress * math.pi)
            self._brightness_modifier = 1.0 + (widen_amount * intensity * 0.3)
            self._per_pixel_modifiers = [self._brightness_modifier] * self.num_leds

        elif expr.expression_type == MicroExpressionType.GLANCE:
            # Glance: Asymmetric brightness (one side brighter)
            # Direction determined by which half of ring
            self._brightness_modifier = 1.0
            mid = self.num_leds // 2
            glance_intensity = eased_progress * intensity
            for i in range(self.num_leds):
                if i < mid:
                    self._per_pixel_modifiers[i] = 1.0 - glance_intensity * 0.3
                else:
                    self._per_pixel_modifiers[i] = 1.0 + glance_intensity * 0.2

        elif expr.expression_type == MicroExpressionType.TWITCH:
            # Twitch: Small random brightness variations
            # Re-seed for consistency during same expression
            twitch_amount = intensity * 0.15
            self._brightness_modifier = 1.0
            for i in range(self.num_leds):
                # Small random variation per LED
                variation = self._rng.uniform(-twitch_amount, twitch_amount)
                self._per_pixel_modifiers[i] = 1.0 + variation

        elif expr.expression_type == MicroExpressionType.DROOP:
            # Droop: Top LEDs progressively dim (gravity effect)
            self._brightness_modifier = 1.0
            droop_progress = eased_progress * intensity
            for i in range(self.num_leds):
                # Top LEDs (indices 0-4 on 16-LED ring) dim most
                # Bottom LEDs stay brighter
                vertical_pos = i / self.num_leds  # 0=top, 1=bottom
                top_weight = 1.0 - vertical_pos
                dim_amount = top_weight * droop_progress * 0.4
                self._per_pixel_modifiers[i] = 1.0 - dim_amount

        elif expr.expression_type == MicroExpressionType.SPARKLE:
            # Sparkle: Random LEDs get brightness pops
            self._brightness_modifier = 1.0
            sparkle_count = int(self.num_leds * intensity * 0.3) + 1
            sparkle_indices = self._rng.sample(
                range(self.num_leds),
                min(sparkle_count, self.num_leds)
            )
            for i in range(self.num_leds):
                if i in sparkle_indices:
                    # Sparkle peaks mid-animation
                    sparkle_amount = math.sin(eased_progress * math.pi) * 0.4
                    self._per_pixel_modifiers[i] = 1.0 + sparkle_amount
                else:
                    self._per_pixel_modifiers[i] = 1.0

        else:
            # Default: no modification
            self._brightness_modifier = 1.0
            self._per_pixel_modifiers = [1.0] * self.num_leds

    @staticmethod
    def _ease_in_out(t: float) -> float:
        """
        Quadratic ease-in-out curve.

        Matches Disney's "slow in, slow out" principle for natural motion.

        Args:
            t: Progress 0.0-1.0

        Returns:
            Eased progress 0.0-1.0
        """
        if t < 0.5:
            return 2.0 * t * t
        else:
            return 1.0 - pow(-2.0 * t + 2.0, 2) / 2.0

    def is_active(self) -> bool:
        """Check if a micro-expression is currently playing."""
        return self._active_expression is not None

    def get_brightness_modifier(self) -> float:
        """
        Get global brightness modifier (0.0-2.0).

        Multiply with pattern brightness to apply micro-expression effect.

        Returns:
            Brightness multiplier (1.0 = no change)
        """
        return self._brightness_modifier

    def get_per_pixel_modifiers(self) -> List[float]:
        """
        Get per-pixel brightness modifiers.

        For expressions like squint/glance that affect LEDs differently.

        Returns:
            List of brightness multipliers, one per LED
        """
        return self._per_pixel_modifiers.copy()

    def get_active_expression_type(self) -> Optional[MicroExpressionType]:
        """Get currently playing expression type, or None."""
        if self._active_expression:
            return self._active_expression.expression.expression_type
        return None

    def get_active_progress(self) -> float:
        """Get progress of current expression (0.0-1.0), or 0.0 if none."""
        if self._active_expression:
            return self._active_expression.progress
        return 0.0

    def cancel_current(self) -> bool:
        """
        Cancel currently playing expression.

        Returns:
            True if an expression was cancelled
        """
        if self._active_expression:
            self._active_expression = None
            self._brightness_modifier = 1.0
            self._per_pixel_modifiers = [1.0] * self.num_leds
            return True
        return False

    def clear_queue(self) -> int:
        """
        Clear all queued expressions.

        Returns:
            Number of expressions cleared
        """
        count = len(self._expression_queue)
        self._expression_queue.clear()
        return count

    def add_callback(
        self,
        callback: Callable[[MicroExpressionType, str], None]
    ) -> None:
        """
        Add callback for expression events.

        Callback receives (expression_type, event) where event is
        "started" or "completed".

        Args:
            callback: Function to call on expression events
        """
        if callback not in self._callbacks:
            self._callbacks.append(callback)

    def remove_callback(
        self,
        callback: Callable[[MicroExpressionType, str], None]
    ) -> bool:
        """
        Remove a previously added callback.

        Args:
            callback: Function to remove

        Returns:
            True if callback was found and removed
        """
        if callback in self._callbacks:
            self._callbacks.remove(callback)
            return True
        return False

    def seed_rng(self, seed: int) -> None:
        """
        Seed the random number generator for reproducible tests.

        Args:
            seed: Random seed value
        """
        self._rng.seed(seed)

    def reset(self) -> None:
        """Reset engine to initial state (cancel all, clear timers)."""
        self._active_expression = None
        self._expression_queue.clear()
        self._cooldown_timers.clear()
        self._brightness_modifier = 1.0
        self._per_pixel_modifiers = [1.0] * self.num_leds


def get_preset_names() -> List[str]:
    """
    Get list of available preset names.

    Returns:
        List of preset name strings
    """
    return list(MICRO_EXPRESSION_PRESETS.keys())


def get_preset(name: str) -> MicroExpression:
    """
    Get a preset micro-expression by name.

    Args:
        name: Preset name from MICRO_EXPRESSION_PRESETS

    Returns:
        MicroExpression configuration

    Raises:
        KeyError: If preset name not found
    """
    if name not in MICRO_EXPRESSION_PRESETS:
        raise KeyError(f"Unknown preset: {name}")
    return MICRO_EXPRESSION_PRESETS[name]
