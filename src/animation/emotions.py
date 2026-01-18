"""
Emotion State Machine for OpenDuck Mini V3

Manages robot emotional states with LED pattern integration.
Enforces valid state transitions for natural behavior flow.

Disney Animation Principles Applied:
- Appeal: Each emotion has distinct visual identity
- Timing: Transition speeds match emotional energy
- Staging: Clear, readable emotional expression
"""

from enum import Enum
from dataclasses import dataclass
from typing import Tuple, Dict, Set, Optional, Callable, List
import time


# === Emotion States ===

class EmotionState(Enum):
    """
    Discrete emotional states for the robot.

    Each state maps to specific LED patterns and colors
    for clear, readable expression.
    """
    IDLE = "idle"           # Default resting state
    HAPPY = "happy"         # Joy, success, greeting
    CURIOUS = "curious"     # Interest, investigation
    ALERT = "alert"         # Warning, attention needed
    SAD = "sad"             # Disappointment, failure
    SLEEPY = "sleepy"       # Low energy, shutting down
    EXCITED = "excited"     # High energy, anticipation
    THINKING = "thinking"   # Processing, computing


# === Emotion Configuration ===

@dataclass
class EmotionConfig:
    """
    Configuration for a single emotion state.

    Defines the LED appearance and animation parameters
    for expressing this emotion.

    Attributes:
        led_color: RGB tuple (0-255 each) for base LED color
        led_pattern: Name of LED pattern ('breathing', 'pulse', etc.)
        led_brightness: Overall brightness 0-255
        pattern_speed: Speed multiplier for pattern animation
        transition_ms: Milliseconds for transition into this state
    """
    led_color: Tuple[int, int, int]
    led_pattern: str
    led_brightness: int
    pattern_speed: float
    transition_ms: int

    def __post_init__(self):
        """Validate configuration values."""
        # Validate RGB
        if len(self.led_color) != 3:
            raise ValueError("led_color must be (R, G, B) tuple")
        if not all(0 <= c <= 255 for c in self.led_color):
            raise ValueError("RGB values must be 0-255")

        # Validate brightness
        if not 0 <= self.led_brightness <= 255:
            raise ValueError("led_brightness must be 0-255")

        # Validate speed
        if self.pattern_speed <= 0:
            raise ValueError("pattern_speed must be positive")

        # Validate transition time
        if self.transition_ms < 0:
            raise ValueError("transition_ms must be non-negative")


# === Emotion Configurations Dictionary ===

# NOTE: Only using patterns implemented Saturday: breathing, pulse, spin
# 'sparkle' and 'fade' deferred to Day 9 implementation
EMOTION_CONFIGS: Dict[EmotionState, EmotionConfig] = {
    EmotionState.IDLE: EmotionConfig(
        led_color=(100, 150, 255),       # Soft blue - calm, approachable
        led_pattern='breathing',          # Slow breathing - alive but at rest
        led_brightness=128,               # Medium brightness - not demanding attention
        pattern_speed=0.5,                # Slow - peaceful
        transition_ms=800,                # Gradual - settling down
    ),

    EmotionState.HAPPY: EmotionConfig(
        led_color=(255, 220, 50),         # Warm yellow - joy, warmth
        led_pattern='pulse',              # Quick pulse - energetic (sparkle deferred)
        led_brightness=200,               # Bright - open, expressive
        pattern_speed=1.2,                # Moderate-fast - energetic
        transition_ms=400,                # Quick - eager to express
    ),

    EmotionState.CURIOUS: EmotionConfig(
        led_color=(150, 255, 150),        # Soft green - inquisitive
        led_pattern='breathing',          # Subtle breathing - attentive
        led_brightness=160,               # Medium-high - engaged
        pattern_speed=0.8,                # Moderate - thoughtful
        transition_ms=500,                # Medium - considering
    ),

    EmotionState.ALERT: EmotionConfig(
        led_color=(255, 100, 100),        # Warm red - attention, warning
        led_pattern='pulse',              # Quick pulse - urgent
        led_brightness=220,               # High - demanding attention
        pattern_speed=1.8,                # Fast - urgent
        transition_ms=200,                # Very fast - immediate response
    ),

    EmotionState.SAD: EmotionConfig(
        led_color=(100, 100, 200),        # Muted blue - melancholy
        led_pattern='breathing',          # Slow breathing - drooping (fade deferred)
        led_brightness=80,                # Dim - withdrawn
        pattern_speed=0.3,                # Very slow - low energy
        transition_ms=1000,               # Slow - reluctant
    ),

    EmotionState.SLEEPY: EmotionConfig(
        led_color=(150, 130, 200),        # Lavender - drowsy
        led_pattern='breathing',          # Slow breathing - drifting off (fade deferred)
        led_brightness=60,                # Very dim - shutting down
        pattern_speed=0.25,               # Very slow - nearly asleep
        transition_ms=1500,               # Very slow - gradual
    ),

    EmotionState.EXCITED: EmotionConfig(
        led_color=(255, 150, 50),         # Orange - energy, enthusiasm
        led_pattern='spin',               # Fast spin - bouncing (sparkle deferred)
        led_brightness=230,               # Very bright - maximum expression
        pattern_speed=2.0,                # Very fast - can't contain it
        transition_ms=300,                # Quick - bursting forth
    ),

    EmotionState.THINKING: EmotionConfig(
        led_color=(200, 200, 255),        # White-blue - processing
        led_pattern='spin',               # Rotating - working
        led_brightness=150,               # Medium - focused
        pattern_speed=1.0,                # Steady - consistent work
        transition_ms=400,                # Medium - shifting focus
    ),
}


# === Valid Transitions Matrix ===

VALID_TRANSITIONS: Dict[EmotionState, Set[EmotionState]] = {
    EmotionState.IDLE: {
        EmotionState.HAPPY,
        EmotionState.CURIOUS,
        EmotionState.ALERT,
        EmotionState.SAD,
        EmotionState.SLEEPY,
        EmotionState.EXCITED,
        EmotionState.THINKING,
    },

    EmotionState.HAPPY: {
        EmotionState.IDLE,
        EmotionState.CURIOUS,
        EmotionState.EXCITED,
        EmotionState.ALERT,      # Can be startled while happy
        EmotionState.THINKING,   # Pondering something
    },

    EmotionState.CURIOUS: {
        EmotionState.IDLE,
        EmotionState.HAPPY,      # Discovery leads to joy
        EmotionState.ALERT,      # Found something concerning
        EmotionState.THINKING,   # Processing what was found
        EmotionState.SAD,        # Disappointment
    },

    EmotionState.ALERT: {
        EmotionState.IDLE,       # False alarm
        EmotionState.CURIOUS,    # Investigating
        EmotionState.HAPPY,      # Resolved positively
        EmotionState.SAD,        # Resolved negatively
        EmotionState.THINKING,   # Processing the situation
    },

    EmotionState.SAD: {
        EmotionState.IDLE,       # Moving on
        EmotionState.HAPPY,      # Cheered up
        EmotionState.ALERT,      # Something demands attention
        EmotionState.CURIOUS,    # Distracted by something
        EmotionState.SLEEPY,     # Giving up, rest
    },

    EmotionState.SLEEPY: {
        EmotionState.IDLE,       # Waking up gently
        EmotionState.ALERT,      # Startled awake (always allowed)
        EmotionState.CURIOUS,    # Something interesting
    },

    EmotionState.EXCITED: {
        EmotionState.IDLE,       # Calming down
        EmotionState.HAPPY,      # Settling into joy
        EmotionState.ALERT,      # Excitement becomes concern
        EmotionState.CURIOUS,    # Excited about something specific
        EmotionState.THINKING,   # Processing the excitement
    },

    EmotionState.THINKING: {
        EmotionState.IDLE,       # Finished thinking
        EmotionState.HAPPY,      # Good conclusion
        EmotionState.SAD,        # Bad conclusion
        EmotionState.ALERT,      # Realized something urgent
        EmotionState.CURIOUS,    # Need more information
        EmotionState.EXCITED,    # Eureka!
    },
}


# === Custom Exception ===

class InvalidTransitionError(Exception):
    """Raised when attempting an invalid emotion transition."""

    def __init__(self, from_state: EmotionState, to_state: EmotionState):
        self.from_state = from_state
        self.to_state = to_state
        super().__init__(
            f"Invalid transition: {from_state.name} -> {to_state.name}. "
            f"Valid targets: {[s.name for s in VALID_TRANSITIONS.get(from_state, set())]}"
        )


# === Emotion Manager ===

class EmotionManager:
    """
    Manages robot emotional state with LED integration.

    Enforces valid state transitions and coordinates with
    LED controller for visual expression.

    Example:
        >>> led = LEDController()
        >>> animator = AnimationPlayer()
        >>> emotions = EmotionManager(led, animator)
        >>> emotions.set_emotion(EmotionState.HAPPY)
        >>> print(emotions.current_emotion)
        EmotionState.HAPPY
    """

    def __init__(self, led_controller, animator):
        """
        Initialize EmotionManager.

        Args:
            led_controller: LED controller for pattern output
            animator: Animation player for servo coordination
        """
        self.led_controller = led_controller
        self.animator = animator

        self._current_emotion: EmotionState = EmotionState.IDLE
        self._transition_start: float = 0.0
        self._in_transition: bool = False

        # Callbacks
        self.on_enter_callback: Optional[Callable[[EmotionState], None]] = None
        self.on_exit_callback: Optional[Callable[[EmotionState], None]] = None

        # Apply initial state
        self._apply_emotion_config(self._current_emotion)

    @property
    def current_emotion(self) -> EmotionState:
        """Get current emotional state."""
        return self._current_emotion

    def can_transition(self, target: EmotionState) -> bool:
        """
        Check if transition to target state is valid.

        Args:
            target: Desired target emotion

        Returns:
            True if transition is allowed
        """
        if target == self._current_emotion:
            return False  # No self-transitions

        valid_targets = VALID_TRANSITIONS.get(self._current_emotion, set())
        return target in valid_targets

    def get_available_transitions(self) -> List[EmotionState]:
        """
        Get list of valid transition targets from current state.

        Returns:
            List of EmotionState values that can be transitioned to
        """
        return list(VALID_TRANSITIONS.get(self._current_emotion, set()))

    def get_current_config(self) -> EmotionConfig:
        """
        Get configuration for current emotion.

        Returns:
            EmotionConfig for current state
        """
        return EMOTION_CONFIGS[self._current_emotion]

    def set_emotion(self, emotion: EmotionState, force: bool = False) -> bool:
        """
        Transition to a new emotional state.

        Args:
            emotion: Target emotional state
            force: If True, bypass transition validation (emergency use)

        Returns:
            True if transition occurred

        Raises:
            InvalidTransitionError: If transition is not valid and force=False
            TypeError: If emotion is not an EmotionState
        """
        # Type check
        if not isinstance(emotion, EmotionState):
            raise TypeError(f"Expected EmotionState, got {type(emotion).__name__}")

        # Same state is a no-op
        if emotion == self._current_emotion:
            return False

        # Check validity (unless forced)
        if not force and not self.can_transition(emotion):
            raise InvalidTransitionError(self._current_emotion, emotion)

        # Perform transition
        old_emotion = self._current_emotion

        # Exit callback
        if self.on_exit_callback:
            self.on_exit_callback(old_emotion)

        # Update state
        self._current_emotion = emotion
        self._transition_start = time.monotonic()

        # Apply new config
        self._apply_emotion_config(emotion)

        # Enter callback
        if self.on_enter_callback:
            self.on_enter_callback(emotion)

        return True

    def _apply_emotion_config(self, emotion: EmotionState):
        """Apply LED configuration for emotion."""
        config = EMOTION_CONFIGS[emotion]

        # Set LED pattern and color
        self.led_controller.set_pattern(
            config.led_pattern,
            speed=config.pattern_speed
        )
        self.led_controller.set_color(config.led_color)
        self.led_controller.set_brightness(config.led_brightness)

    def reset_to_idle(self):
        """Reset to IDLE state (always valid)."""
        self._current_emotion = EmotionState.IDLE
        self._apply_emotion_config(EmotionState.IDLE)

    # === Emotion Bridge Methods (Discrete <-> Continuous) ===

    def get_emotion_axes(self) -> 'EmotionAxes':
        """
        Get current emotion as continuous 4D representation.

        Bridges the discrete EmotionState enum to the continuous
        EmotionAxes system for seamless integration with Pixar-style
        animation interpolation.

        Returns:
            EmotionAxes for current state using EMOTION_PRESETS mapping.
            Falls back to 'idle' preset if no exact match exists.

        Example:
            >>> manager = EmotionManager(led, animator)
            >>> manager.set_emotion(EmotionState.HAPPY)
            >>> axes = manager.get_emotion_axes()
            >>> print(axes.valence)  # Should be positive (happy)
            0.8
        """
        from .emotion_axes import EMOTION_PRESETS
        return EMOTION_PRESETS.get(self._current_emotion.value, EMOTION_PRESETS['idle'])

    def set_emotion_from_axes(self, axes: 'EmotionAxes', threshold: float = 0.3) -> bool:
        """
        Set emotion by finding closest matching preset to given axes.

        Bridges the continuous EmotionAxes system back to discrete
        EmotionState, enabling animation systems to drive emotion
        state changes.

        Args:
            axes: Continuous emotion coordinates (4D point in emotion space)
            threshold: Maximum Euclidean distance to accept a match.
                       Default 0.3 provides reasonable tolerance for
                       interpolated emotions near preset boundaries.

        Returns:
            True if emotion was changed to a matching preset.
            False if:
            - No preset is within threshold distance
            - Closest preset maps to current state (no change)
            - Closest preset has no EmotionState equivalent

        Raises:
            ValueError: If threshold is not a non-negative number

        Note:
            Only matches against 8 basic EmotionState values, not
            compound presets (anxious, confused, playful, etc.)
            which exist only in the continuous space.

        Example:
            >>> manager = EmotionManager(led, animator)
            >>> happy_axes = EmotionAxes(arousal=0.4, valence=0.8, focus=0.5, blink_speed=1.2)
            >>> manager.set_emotion_from_axes(happy_axes)
            True
            >>> manager.current_emotion
            EmotionState.HAPPY
        """
        # H-004: Validate threshold parameter
        if not isinstance(threshold, (int, float)) or threshold < 0:
            raise ValueError("threshold must be a non-negative number")

        from .emotion_axes import EMOTION_PRESETS

        best_match = None
        best_distance = float('inf')

        for name, preset in EMOTION_PRESETS.items():
            distance = self._axes_distance(axes, preset)
            if distance < best_distance:
                best_distance = distance
                best_match = name

        if best_distance > threshold or best_match is None:
            return False

        # Map preset name to EmotionState
        try:
            target_state = EmotionState(best_match)
            return self.set_emotion(target_state)
        except ValueError:
            # Preset exists but has no EmotionState equivalent (compound emotions)
            return False

    def _axes_distance(self, a: 'EmotionAxes', b: 'EmotionAxes') -> float:
        """
        Calculate Euclidean distance between two EmotionAxes.

        Uses 3D distance (arousal, valence, focus) rather than 4D
        because blink_speed is more of a temporal expression parameter
        than a core emotion dimension.

        Args:
            a: First emotion axes
            b: Second emotion axes

        Returns:
            Euclidean distance in 3D emotion space (0.0 to ~3.46 max)
        """
        return ((a.arousal - b.arousal) ** 2 +
                (a.valence - b.valence) ** 2 +
                (a.focus - b.focus) ** 2) ** 0.5
