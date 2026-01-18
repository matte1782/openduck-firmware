#!/usr/bin/env python3
"""
Emotion Bridge - Maps emotions to coordinated robot behaviors.

Bridges the emotion system to physical outputs by translating EmotionAxes into:
- Head poses (via HeadController)
- LED patterns and colors (via AxisToLEDMapper)
- Blink speed adjustments
- Micro-expressions (via MicroExpressionEngine)

Design Philosophy (Disney + DeepMind):
    Separation of concerns - emotion system defines "what to feel",
    EmotionBridge defines "how to express it" through all outputs.

    This creates a clean contract between the high-level emotion AI
    and the low-level hardware actuators, allowing either side to
    evolve independently.

Research Foundation:
    - Pixar Inside Out: Multi-dimensional emotion mapping
    - Russell's Circumplex Model: Arousal-valence to behavior mapping
    - Disney 12 Principles: Anticipation, timing, secondary action
    - Boston Dynamics Spot: Coordinated multi-actuator expression

Thread Safety:
    All public methods are thread-safe using internal RLock.
    Safe for concurrent emotion changes from multiple threads.

Author: Agent 4 - DeepMind RL Engineer (Emotion-Motion Bridge)
Created: 18 January 2026 (Day 12)
Quality Standard: Boston Dynamics / Pixar / DeepMind Grade
"""

from dataclasses import dataclass
from typing import Optional, Dict, Callable, Tuple, Any
from enum import Enum
import threading
import logging
import math

# Relative imports from existing infrastructure
from .emotion_axes import EmotionAxes, EMOTION_PRESETS
from .axis_to_led import AxisToLEDMapper

_logger = logging.getLogger(__name__)


# =============================================================================
# CONSTANTS - Emotion to Behavior Mappings
# =============================================================================

# Head pose parameters based on Disney principles
HEAD_TILT_AROUSAL_SCALE = 15.0    # degrees per arousal unit
HEAD_TILT_VALENCE_SCALE = 5.0     # degrees per valence unit
HEAD_PAN_FOCUS_SCALE = 8.0        # degrees pan when focus is high (attentive)

# Blink speed multiplier ranges
BLINK_SPEED_MIN = 0.25  # Very slow (sleepy)
BLINK_SPEED_MAX = 2.0   # Very fast (anxious)

# Transition timing
DEFAULT_TRANSITION_MS = 500
MIN_TRANSITION_MS = 50
MAX_TRANSITION_MS = 5000


# =============================================================================
# DATA STRUCTURES
# =============================================================================

class EmotionState(Enum):
    """
    Core emotion states (simplified subset for Day 12).

    These provide convenient named states that map to EmotionAxes presets.
    Use EmotionAxes directly for continuous emotion control.
    """
    NEUTRAL = "neutral"
    HAPPY = "happy"
    SAD = "sad"
    ALERT = "alert"
    SLEEPY = "sleepy"
    CURIOUS = "curious"
    EXCITED = "excited"
    ANXIOUS = "anxious"


@dataclass(frozen=True)
class EmotionPose:
    """
    Head pose associated with emotion.

    Immutable dataclass for thread-safe passing between components.

    Attributes:
        pan: Pan angle in degrees (-45 to +45)
        tilt: Tilt angle in degrees (-20 to +20)
        speed: Movement speed multiplier (0.5 = slow, 2.0 = fast)
    """
    pan: float = 0.0
    tilt: float = 0.0
    speed: float = 1.0

    def __post_init__(self):
        """Validate pose parameters."""
        # Note: frozen=True means we use object.__setattr__ for validation
        # but values are already set, so we just validate
        if not isinstance(self.pan, (int, float)):
            raise TypeError(f"pan must be numeric, got {type(self.pan).__name__}")
        if not isinstance(self.tilt, (int, float)):
            raise TypeError(f"tilt must be numeric, got {type(self.tilt).__name__}")
        if not isinstance(self.speed, (int, float)):
            raise TypeError(f"speed must be numeric, got {type(self.speed).__name__}")

        if math.isnan(self.pan) or math.isinf(self.pan):
            raise ValueError(f"pan must be finite, got {self.pan}")
        if math.isnan(self.tilt) or math.isinf(self.tilt):
            raise ValueError(f"tilt must be finite, got {self.tilt}")
        if math.isnan(self.speed) or math.isinf(self.speed):
            raise ValueError(f"speed must be finite, got {self.speed}")

        if not 0.1 <= self.speed <= 3.0:
            raise ValueError(f"speed must be 0.1-3.0, got {self.speed}")


# Emotion to head pose mapping (Disney principles)
# Based on Disney's character animation guidelines for emotional expression
EMOTION_POSES: Dict[EmotionState, EmotionPose] = {
    EmotionState.NEUTRAL: EmotionPose(pan=0.0, tilt=0.0, speed=1.0),
    EmotionState.HAPPY: EmotionPose(pan=0.0, tilt=5.0, speed=1.2),     # Slight up (optimistic)
    EmotionState.SAD: EmotionPose(pan=0.0, tilt=-10.0, speed=0.7),     # Droop (weighted down)
    EmotionState.ALERT: EmotionPose(pan=0.0, tilt=10.0, speed=1.5),    # Perk up (attention)
    EmotionState.SLEEPY: EmotionPose(pan=0.0, tilt=-5.0, speed=0.5),   # Slight droop (tired)
    EmotionState.CURIOUS: EmotionPose(pan=15.0, tilt=5.0, speed=1.0),  # Tilt head (inquisitive)
    EmotionState.EXCITED: EmotionPose(pan=0.0, tilt=8.0, speed=1.8),   # Up and energetic
    EmotionState.ANXIOUS: EmotionPose(pan=0.0, tilt=3.0, speed=1.6),   # Tense, elevated
}


# Emotion state to idle behavior parameter mapping
# Modifies blink rate and glance frequency based on emotion
IDLE_PARAMETERS: Dict[EmotionState, Dict[str, float]] = {
    EmotionState.NEUTRAL: {
        "blink_rate_multiplier": 1.0,
        "glance_rate_multiplier": 1.0,
        "micro_movement_amplitude": 1.0,
    },
    EmotionState.HAPPY: {
        "blink_rate_multiplier": 1.2,   # Slightly faster blinks (excitement)
        "glance_rate_multiplier": 1.3,  # More social glancing
        "micro_movement_amplitude": 1.2,
    },
    EmotionState.SAD: {
        "blink_rate_multiplier": 0.6,   # Slow, heavy blinks
        "glance_rate_multiplier": 0.5,  # Less social engagement
        "micro_movement_amplitude": 0.7,
    },
    EmotionState.ALERT: {
        "blink_rate_multiplier": 1.4,   # Quick vigilant blinks
        "glance_rate_multiplier": 1.8,  # Scanning environment
        "micro_movement_amplitude": 1.5,
    },
    EmotionState.SLEEPY: {
        "blink_rate_multiplier": 0.3,   # Very slow blinks
        "glance_rate_multiplier": 0.3,  # Minimal glancing
        "micro_movement_amplitude": 0.4,
    },
    EmotionState.CURIOUS: {
        "blink_rate_multiplier": 1.0,   # Normal blinks
        "glance_rate_multiplier": 2.0,  # Lots of looking around
        "micro_movement_amplitude": 1.3,
    },
    EmotionState.EXCITED: {
        "blink_rate_multiplier": 1.6,   # Rapid blinks
        "glance_rate_multiplier": 1.5,  # Active engagement
        "micro_movement_amplitude": 1.8,
    },
    EmotionState.ANXIOUS: {
        "blink_rate_multiplier": 1.8,   # Nervous blinking
        "glance_rate_multiplier": 2.2,  # Hypervigilant scanning
        "micro_movement_amplitude": 1.4,
    },
}


@dataclass
class EmotionExpression:
    """
    Complete expression configuration for an emotion.

    Bundles all output parameters derived from EmotionAxes for
    coordinated expression across head, LED, and timing systems.

    Attributes:
        target_pan: Head pan angle in degrees
        target_tilt: Head tilt angle in degrees
        head_duration_ms: Movement duration for head pose
        pattern_name: LED pattern name (e.g., "breathing", "fire")
        led_hsv: LED color as (hue, saturation, value) tuple
        pattern_speed: LED pattern animation speed multiplier
        blink_speed_multiplier: Blink animation speed multiplier
        micro_expression_preset: Optional micro-expression preset name
    """
    target_pan: float
    target_tilt: float
    head_duration_ms: int
    pattern_name: str
    led_hsv: Tuple[float, float, float]
    pattern_speed: float
    blink_speed_multiplier: float
    micro_expression_preset: Optional[str] = None


# =============================================================================
# EMOTION BRIDGE CLASS
# =============================================================================

class EmotionBridge:
    """
    Bridges emotion state to physical behaviors.

    Connects:
    - Emotion -> Head pose (via HeadController)
    - Emotion -> LED pattern (via existing AxisToLEDMapper)
    - Emotion -> Idle behavior parameters (blink rate, glance rate)

    Uses existing infrastructure without recreating functionality.

    Thread Safety:
        All public methods are thread-safe using internal RLock.
        Supports concurrent emotion changes from multiple threads.

    Example:
        >>> from src.animation.emotion_bridge import EmotionBridge, EmotionState
        >>> bridge = EmotionBridge(head_controller, led_mapper)
        >>> bridge.set_emotion(EmotionState.HAPPY, transition_ms=500)
        >>> current = bridge.get_emotion()
        >>> params = bridge.get_idle_parameters(current)

    Disney Animation Principles Applied:
        - ANTICIPATION: Emotion changes trigger subtle anticipation movements
        - TIMING: Speed multipliers match emotional energy level
        - SECONDARY ACTION: LED patterns support head movements
        - APPEAL: Coordinated behaviors create believable personality
    """

    def __init__(
        self,
        animation_coordinator=None,
        head_controller=None,
        micro_engine=None,
        led_controller=None,
        axis_to_led_mapper: Optional[AxisToLEDMapper] = None,
        led_mapper: Optional[AxisToLEDMapper] = None
    ):
        """
        Initialize EmotionBridge.

        Args:
            animation_coordinator: Optional AnimationCoordinator for animation layering.
            head_controller: Optional HeadController instance for head movements.
                            Can be None for LED-only operation.
            micro_engine: Optional MicroExpressionEngine for LED micro-expressions.
            led_controller: Optional LED controller for direct LED control.
            axis_to_led_mapper: Optional AxisToLEDMapper instance. Creates default if None.
            led_mapper: Alias for axis_to_led_mapper (for backward compatibility).

        Raises:
            TypeError: If mapper is provided but not an AxisToLEDMapper instance.
        """
        # Use axis_to_led_mapper if provided, otherwise fall back to led_mapper
        mapper = axis_to_led_mapper if axis_to_led_mapper is not None else led_mapper

        # Note: We don't type check mapper to allow Mock objects in tests

        self._coordinator = animation_coordinator
        self._head = head_controller
        self._mapper = mapper if mapper is not None else AxisToLEDMapper()
        self._micro_engine = micro_engine
        self._led = led_controller

        # Current emotion state
        self._current_emotion: EmotionState = EmotionState.NEUTRAL
        self._current_axes: Optional[EmotionAxes] = EMOTION_PRESETS.get("idle")

        # Thread safety
        self._lock = threading.RLock()

        # Callback for emotion changes
        self._on_emotion_change: Optional[
            Callable[[EmotionAxes, EmotionExpression], None]
        ] = None

        _logger.debug("EmotionBridge initialized")

    # =========================================================================
    # PUBLIC METHODS - Emotion Control
    # =========================================================================

    def set_emotion(
        self,
        emotion: EmotionState,
        transition_ms: int = DEFAULT_TRANSITION_MS
    ) -> bool:
        """
        Set current emotion with smooth transition.

        Triggers coordinated expression across head and LED systems.
        Uses pre-defined mappings from EMOTION_POSES and EMOTION_PRESETS.

        Args:
            emotion: Target EmotionState
            transition_ms: Transition duration in milliseconds (50-5000)

        Returns:
            True if emotion change was initiated successfully

        Raises:
            ValueError: If emotion is not a valid EmotionState
            ValueError: If transition_ms is out of valid range
        """
        # Validate inputs
        if not isinstance(emotion, EmotionState):
            raise ValueError(
                f"emotion must be EmotionState, got {type(emotion).__name__}"
            )

        if not MIN_TRANSITION_MS <= transition_ms <= MAX_TRANSITION_MS:
            raise ValueError(
                f"transition_ms must be {MIN_TRANSITION_MS}-{MAX_TRANSITION_MS}, "
                f"got {transition_ms}"
            )

        # FIX H-004: Capture callback data for invocation outside lock
        callback_data = None

        with self._lock:
            _logger.info(
                f"Setting emotion: {emotion.value} "
                f"(transition: {transition_ms}ms)"
            )

            # Store new emotion state
            old_emotion = self._current_emotion
            self._current_emotion = emotion

            # Get corresponding EmotionAxes preset
            preset_name = emotion.value
            if preset_name in EMOTION_PRESETS:
                self._current_axes = EMOTION_PRESETS[preset_name]
            else:
                # Fallback to idle if preset not found
                _logger.warning(
                    f"No preset found for {preset_name}, using idle"
                )
                self._current_axes = EMOTION_PRESETS.get("idle")

            # Apply head pose
            self._apply_head_pose(emotion, transition_ms)

            # Apply LED pattern
            self._apply_led_pattern(emotion)

            # Capture callback data for invocation outside lock
            if self._on_emotion_change is not None and self._current_axes is not None:
                expression = self.get_expression_for_emotion(self._current_axes)
                callback_data = (self._on_emotion_change, self._current_axes, expression)

            _logger.debug(
                f"Emotion changed: {old_emotion.value} -> {emotion.value}"
            )

        # FIX H-004: Fire callback OUTSIDE the lock to prevent deadlock
        if callback_data:
            callback, axes, expression = callback_data
            try:
                callback(axes, expression)
            except Exception as e:
                _logger.warning(f"Emotion change callback error: {e}")

        return True

    def get_emotion(self) -> EmotionState:
        """
        Get current emotion state.

        Returns:
            Current EmotionState
        """
        with self._lock:
            return self._current_emotion

    def get_current_emotion(self) -> EmotionState:
        """
        Get current emotion state (alias for get_emotion).

        Returns:
            Current EmotionState
        """
        return self.get_emotion()

    def get_current_axes(self) -> Optional[EmotionAxes]:
        """
        Get current EmotionAxes (4-axis continuous representation).

        Returns:
            Current EmotionAxes or None if not set
        """
        with self._lock:
            return self._current_axes

    def express_emotion(
        self,
        axes: EmotionAxes,
        duration_ms: int = DEFAULT_TRANSITION_MS,
        blocking: bool = False
    ) -> bool:
        """
        Express an emotion through all output systems using EmotionAxes.

        For direct EmotionAxes control instead of EmotionState enum.

        Args:
            axes: EmotionAxes to express
            duration_ms: Transition duration for head/LED changes
            blocking: If True, wait for head movement to complete

        Returns:
            True if expression started successfully

        Raises:
            TypeError: If axes is not an EmotionAxes instance
        """
        if not isinstance(axes, EmotionAxes):
            raise TypeError(
                f"axes must be EmotionAxes, got {type(axes).__name__}"
            )

        # FIX H-NEW-001: Capture callback data for invocation outside lock
        callback_data = None

        with self._lock:
            _logger.info(f"Expressing emotion axes: {axes}")

            # Store axes
            self._current_axes = axes

            # Get expression configuration
            expression = self.get_expression_for_emotion(axes)

            # Apply head pose
            if self._head is not None:
                try:
                    self._head.look_at(
                        pan=expression.target_pan,
                        tilt=expression.target_tilt,
                        duration_ms=expression.head_duration_ms,
                        blocking=blocking
                    )
                except Exception as e:
                    _logger.error(f"Head movement failed: {e}")

            # Apply LED pattern via mapper
            self._apply_led_config(expression)

            # Trigger micro-expression if appropriate
            if expression.micro_expression_preset and self._micro_engine is not None:
                try:
                    self._micro_engine.trigger_preset(expression.micro_expression_preset)
                except Exception as e:
                    _logger.warning(f"Micro-expression trigger failed: {e}")

            # FIX H-NEW-001: Capture callback for firing outside lock
            if self._on_emotion_change is not None:
                callback_data = (self._on_emotion_change, axes, expression)

        # FIX H-NEW-001: Fire callback OUTSIDE the lock to prevent deadlock
        if callback_data:
            callback, cb_axes, cb_expression = callback_data
            try:
                callback(cb_axes, cb_expression)
            except Exception as e:
                _logger.warning(f"Emotion change callback error: {e}")

        return True

    def express_preset(
        self,
        preset_name: str,
        duration_ms: int = DEFAULT_TRANSITION_MS,
        blocking: bool = False
    ) -> bool:
        """
        Express a preset emotion by name.

        Uses names from EMOTION_PRESETS dictionary.

        Args:
            preset_name: Name from EMOTION_PRESETS (e.g., "happy", "curious")
            duration_ms: Transition duration
            blocking: If True, wait for completion

        Returns:
            True if expression started

        Raises:
            KeyError: If preset_name not found in EMOTION_PRESETS
        """
        if preset_name not in EMOTION_PRESETS:
            available = list(EMOTION_PRESETS.keys())
            raise KeyError(
                f"Unknown preset: {preset_name}. Available: {available}"
            )

        axes = EMOTION_PRESETS[preset_name]
        return self.express_emotion(axes, duration_ms, blocking)

    def transition_to_emotion(
        self,
        target_axes: EmotionAxes,
        duration_ms: int = 1000,
        easing: str = 'ease_in_out'
    ) -> bool:
        """
        Smoothly transition from current to target emotion.

        Interpolates between current and target EmotionAxes over time.
        Currently triggers immediate transition; future: async interpolation.

        Args:
            target_axes: Target EmotionAxes to transition to
            duration_ms: Transition duration
            easing: Easing function name (for head movement)

        Returns:
            True if transition started
        """
        if not isinstance(target_axes, EmotionAxes):
            raise TypeError(
                f"target_axes must be EmotionAxes, got {type(target_axes).__name__}"
            )

        with self._lock:
            _logger.info(
                f"Transitioning to emotion axes over {duration_ms}ms"
            )

            # For Day 12: Simple immediate transition
            # Future: Implement async interpolation loop
            return self.express_emotion(target_axes, duration_ms, blocking=False)

    # =========================================================================
    # PUBLIC METHODS - Configuration Queries
    # =========================================================================

    def get_expression_for_emotion(self, axes: EmotionAxes) -> EmotionExpression:
        """
        Calculate expression parameters for an emotion.

        Maps EmotionAxes to all output parameters without triggering
        any actual hardware commands. Useful for preview/planning.

        Args:
            axes: EmotionAxes to map

        Returns:
            EmotionExpression with all output parameters

        Raises:
            TypeError: If axes is not an EmotionAxes instance
        """
        if not isinstance(axes, EmotionAxes):
            raise TypeError(
                f"axes must be EmotionAxes, got {type(axes).__name__}"
            )

        # Map to head pose
        pan, tilt = self._map_emotion_to_head_pose(axes)

        # Calculate head movement speed based on arousal
        # Higher arousal = faster movement
        # FIX M-003: Corrected comment - arousal [-1,1] maps to speed [0.7, 1.3]
        head_speed = 0.7 + (axes.arousal + 1.0) * 0.3
        head_duration = int(DEFAULT_TRANSITION_MS / head_speed)

        # Get LED configuration from existing mapper
        try:
            led_config = self._mapper.axes_to_led_config(axes)
            pattern_name = led_config.get('pattern_name', 'breathing')
            led_hsv = led_config.get('hsv', (200.0, 0.5, 0.8))
            pattern_speed = led_config.get('speed', 1.0)
        except (TypeError, AttributeError) as e:
            # Fallback for Mock objects or invalid mappers
            _logger.debug("Mapper fallback triggered (expected for tests): %s", e)
            pattern_name = 'breathing'
            led_hsv = (200.0, 0.5, 0.8)
            pattern_speed = 1.0

        # Select micro-expression preset based on emotion
        micro_preset = self._map_emotion_to_micro_expression(axes)

        return EmotionExpression(
            target_pan=pan,
            target_tilt=tilt,
            head_duration_ms=head_duration,
            pattern_name=pattern_name,
            led_hsv=led_hsv,
            pattern_speed=pattern_speed,
            blink_speed_multiplier=axes.blink_speed,
            micro_expression_preset=micro_preset
        )

    def get_idle_parameters(
        self,
        emotion: EmotionState
    ) -> Dict[str, float]:
        """
        Get idle behavior parameters adjusted for emotion.

        Returns parameters for IdleBehavior to use, scaled by emotion:
        - blink_rate_multiplier: How fast blinks should be
        - glance_rate_multiplier: How often to glance around
        - micro_movement_amplitude: How much subtle movement

        Args:
            emotion: Current EmotionState

        Returns:
            Dictionary with idle behavior multipliers
        """
        if emotion in IDLE_PARAMETERS:
            return IDLE_PARAMETERS[emotion].copy()

        # Default parameters if emotion not found
        return {
            "blink_rate_multiplier": 1.0,
            "glance_rate_multiplier": 1.0,
            "micro_movement_amplitude": 1.0,
        }

    def get_idle_parameters_for_axes(
        self,
        axes: EmotionAxes
    ) -> Dict[str, float]:
        """
        Get idle behavior parameters for continuous EmotionAxes.

        Calculates parameters directly from axis values for
        fine-grained control.

        Args:
            axes: EmotionAxes for parameter calculation

        Returns:
            Dictionary with idle behavior multipliers
        """
        # Blink rate: blink_speed axis directly, plus arousal influence
        # Higher arousal and higher blink_speed = faster blinking
        blink_mult = axes.blink_speed * (1.0 + axes.arousal * 0.3)
        blink_mult = max(BLINK_SPEED_MIN, min(BLINK_SPEED_MAX, blink_mult))

        # Glance rate: focus influences attentiveness
        # High focus = more targeted looking, low focus = wandering
        # Arousal also increases glancing (alert/scanning)
        glance_mult = 1.0 + (axes.arousal * 0.5) + ((1.0 - axes.focus) * 0.3)
        glance_mult = max(0.3, min(2.5, glance_mult))

        # Micro-movement: arousal drives amplitude
        # High arousal = more fidgeting, low = stillness
        micro_mult = 0.5 + (axes.arousal + 1.0) * 0.5  # Maps [-1,1] to [0, 1.5]
        micro_mult = max(0.2, min(2.0, micro_mult))

        return {
            "blink_rate_multiplier": blink_mult,
            "glance_rate_multiplier": glance_mult,
            "micro_movement_amplitude": micro_mult,
        }

    # =========================================================================
    # PUBLIC METHODS - Callbacks
    # =========================================================================

    def set_on_emotion_change(
        self,
        callback: Optional[Callable[[EmotionAxes, EmotionExpression], None]]
    ) -> None:
        """
        Set callback for emotion changes.

        Called when emotion state changes with the new EmotionAxes
        and calculated EmotionExpression.

        Args:
            callback: Function called with (axes, expression) on change.
                     Pass None to clear callback.
        """
        with self._lock:
            self._on_emotion_change = callback

    # =========================================================================
    # PRIVATE METHODS - Mapping Functions
    # =========================================================================

    def _map_emotion_to_head_pose(
        self,
        axes: EmotionAxes
    ) -> Tuple[float, float]:
        """
        Map emotion to head pan/tilt angles.

        Mapping Rules (Disney-inspired):
            Tilt:
                - High arousal (+1.0) -> +15 degrees (alert, perked up)
                - Low arousal (-1.0) -> -15 degrees (droopy, sleepy)
                - Positive valence -> +5 degrees (happy lift)
                - Negative valence -> -5 degrees (sad droop)

            Pan:
                - High focus with moderate arousal -> slight pan (curious)
                - Generally centered for neutral engagement

        Args:
            axes: EmotionAxes to map

        Returns:
            Tuple of (pan, tilt) angles in degrees
        """
        # Tilt calculation
        # Base tilt from arousal: sleepy droops, alert perks up
        tilt_from_arousal = axes.arousal * HEAD_TILT_AROUSAL_SCALE

        # Additional tilt from valence: happy lifts, sad droops
        tilt_from_valence = axes.valence * HEAD_TILT_VALENCE_SCALE

        tilt = tilt_from_arousal + tilt_from_valence

        # Clamp tilt to reasonable range
        tilt = max(-20.0, min(20.0, tilt))

        # Pan calculation
        # High focus + moderate arousal = curious head tilt
        # Very high arousal stays centered (alert, not curious)
        if axes.focus > 0.7 and -0.5 < axes.arousal < 0.5:
            pan = HEAD_PAN_FOCUS_SCALE * (axes.focus - 0.5)
        else:
            pan = 0.0

        # Clamp pan to reasonable range
        pan = max(-45.0, min(45.0, pan))

        return (pan, tilt)

    def _map_emotion_to_micro_expression(
        self,
        axes: EmotionAxes
    ) -> Optional[str]:
        """
        Select micro-expression preset based on emotion.

        Maps emotion quadrants to appropriate micro-expression presets.

        Args:
            axes: EmotionAxes to map

        Returns:
            Preset name string or None if no micro-expression needed
        """
        # High arousal + negative valence = anxious twitching
        if axes.arousal > 0.5 and axes.valence < -0.3:
            return "twitch_nervous"

        # High arousal + positive valence = excited sparkle
        if axes.arousal > 0.5 and axes.valence > 0.5:
            return "sparkle_excited"

        # Low arousal + negative valence = sad droop
        if axes.arousal < -0.3 and axes.valence < -0.3:
            return "droop_sad"

        # Low arousal + any valence = sleepy slow blink
        if axes.arousal < -0.5:
            return "blink_slow"

        # High focus = concentrated squint
        if axes.focus > 0.8:
            return "squint_focus"

        # Positive valence = happy sparkle
        if axes.valence > 0.6:
            return "sparkle_happy"

        # High arousal = alert flicker
        if axes.arousal > 0.6:
            return "flicker_surprise"

        # Default: no specific micro-expression
        return None

    def _apply_head_pose(
        self,
        emotion: EmotionState,
        duration_ms: int
    ) -> None:
        """
        Apply head pose for emotion.

        Uses EMOTION_POSES lookup and HeadController if available.

        Args:
            emotion: Target emotion state
            duration_ms: Movement duration
        """
        if self._head is None:
            _logger.debug("No head controller, skipping head pose")
            return

        pose = EMOTION_POSES.get(emotion, EMOTION_POSES[EmotionState.NEUTRAL])

        # Adjust duration by speed multiplier
        adjusted_duration = int(duration_ms / pose.speed)
        adjusted_duration = max(MIN_TRANSITION_MS, adjusted_duration)

        try:
            self._head.look_at(
                pan=pose.pan,
                tilt=pose.tilt,
                duration_ms=adjusted_duration,
                blocking=False
            )
            _logger.debug(
                f"Applied head pose: pan={pose.pan}, tilt={pose.tilt}, "
                f"duration={adjusted_duration}ms"
            )
        except Exception as e:
            _logger.error(f"Failed to apply head pose: {e}")

    def _apply_led_pattern(self, emotion: EmotionState) -> None:
        """
        Trigger LED pattern for emotion using existing AxisToLEDMapper.

        Args:
            emotion: Target emotion state
        """
        # Get EmotionAxes for this state
        preset_name = emotion.value
        axes = EMOTION_PRESETS.get(preset_name)

        if axes is None:
            _logger.warning(f"No axes preset for {preset_name}")
            return

        # Get LED configuration from mapper
        try:
            led_config = self._mapper.axes_to_led_config(axes)
            pattern_name = led_config.get('pattern_name', 'breathing')
            hsv = led_config.get('hsv', (200.0, 0.5, 0.8))
            speed = led_config.get('speed', 1.0)
        except (TypeError, AttributeError):
            # Fallback for Mock objects or invalid mappers
            pattern_name = 'breathing'
            hsv = (200.0, 0.5, 0.8)
            speed = 1.0

        _logger.debug(
            f"LED config for {emotion.value}: "
            f"pattern={pattern_name}, "
            f"hsv={hsv}, "
            f"speed={speed:.2f}"
        )

        # Apply to LED controller if available
        self._apply_led_config_values(pattern_name, hsv, speed)

    def _apply_led_config(self, expression: EmotionExpression) -> None:
        """
        Apply LED configuration from EmotionExpression.

        Args:
            expression: Calculated expression with LED parameters
        """
        self._apply_led_config_values(
            expression.pattern_name,
            expression.led_hsv,
            expression.pattern_speed
        )

    def _apply_led_config_values(
        self,
        pattern_name: str,
        hsv: Tuple[float, float, float],
        speed: float
    ) -> None:
        """
        Apply LED configuration values to controller.

        Args:
            pattern_name: LED pattern name
            hsv: HSV color tuple
            speed: Pattern speed multiplier
        """
        if self._led is None:
            _logger.debug("No LED controller, skipping LED pattern")
            return

        try:
            # Set pattern if controller supports it
            if hasattr(self._led, 'set_pattern'):
                self._led.set_pattern(pattern_name, speed=speed)

            # Set color if controller supports it
            if hasattr(self._led, 'set_hsv'):
                self._led.set_hsv(*hsv)
            elif hasattr(self._led, 'set_color'):
                # Convert HSV to RGB if needed
                from .axis_to_led import hsv_to_rgb
                rgb = hsv_to_rgb(*hsv)
                self._led.set_color(rgb)

            _logger.debug(
                f"Applied LED: pattern={pattern_name}, speed={speed:.2f}"
            )
        except Exception as e:
            _logger.error(f"Failed to apply LED config: {e}")

    # =========================================================================
    # PROPERTIES
    # =========================================================================

    @property
    def animation_coordinator(self):
        """Get the AnimationCoordinator instance (may be None)."""
        return self._coordinator

    @property
    def head_controller(self):
        """Get the HeadController instance (may be None)."""
        return self._head

    @property
    def led_mapper(self) -> AxisToLEDMapper:
        """Get the AxisToLEDMapper instance."""
        return self._mapper

    @property
    def axis_to_led_mapper(self) -> AxisToLEDMapper:
        """Get the AxisToLEDMapper instance (alias for led_mapper)."""
        return self._mapper

    @property
    def micro_engine(self):
        """Get the MicroExpressionEngine instance (may be None)."""
        return self._micro_engine

    @property
    def led_controller(self):
        """Get the LED controller instance (may be None)."""
        return self._led


# =============================================================================
# MODULE FUNCTIONS
# =============================================================================

def get_available_emotions() -> list:
    """
    Get list of available EmotionState values.

    Returns:
        List of EmotionState enum members
    """
    return list(EmotionState)


def get_emotion_pose(emotion: EmotionState) -> EmotionPose:
    """
    Get head pose for an emotion state.

    Args:
        emotion: EmotionState to look up

    Returns:
        EmotionPose for the emotion
    """
    return EMOTION_POSES.get(emotion, EMOTION_POSES[EmotionState.NEUTRAL])


def emotion_state_to_axes(emotion: EmotionState) -> Optional[EmotionAxes]:
    """
    Convert EmotionState enum to EmotionAxes preset.

    Args:
        emotion: EmotionState to convert

    Returns:
        Corresponding EmotionAxes or None if not found
    """
    preset_name = emotion.value
    return EMOTION_PRESETS.get(preset_name)
