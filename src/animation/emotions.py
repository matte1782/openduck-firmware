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

    Categories:
    - Primary (8): Core emotional states
    - Social (4): Connection-building emotions (Agent 2, Week 02)
    """
    # === Primary Emotions (8) ===
    IDLE = "idle"           # Default resting state
    HAPPY = "happy"         # Joy, success, greeting
    CURIOUS = "curious"     # Interest, investigation
    ALERT = "alert"         # Warning, attention needed
    SAD = "sad"             # Disappointment, failure
    SLEEPY = "sleepy"       # Low energy, shutting down
    EXCITED = "excited"     # High energy, anticipation
    THINKING = "thinking"   # Processing, computing

    # === Social Emotions (4) - Connection-Building ===
    # Added by Agent 2 (Social Emotion Implementation Specialist)
    # Research: Anki Cozmo/Vector, color psychology, social HRI
    PLAYFUL = "playful"         # Mischievous, bouncy, invites play
    AFFECTIONATE = "affectionate"  # Warm, nurturing, bonding
    EMPATHETIC = "empathetic"   # Mirroring, supportive, understanding
    GRATEFUL = "grateful"       # Appreciative, thankful, acknowledging


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
#
# Psychology-Grounded Configurations v2.0 - Agent 1 Primary Emotion Refinement
# Research basis: PMC color psychology, cardiac psychophysiology, Disney 12 Principles
#
# Color Temperature Reference (research-validated):
#   - 2200K = Candlelight (very warm orange) - maximum excitement
#   - 2700K = Warm incandescent - sleep, relaxation
#   - 2800K = Warm white - happiness, joy
#   - 5500K = Daylight (neutral) - calm awareness, curiosity
#   - 7000K = Cool daylight - cognitive processing
#   - 9000K = Very cool blue - sadness, withdrawal
#
# BPM Reference (cardiac psychophysiology):
#   - 6 BPM = Near-sleep breathing rate
#   - 7.5 BPM = Low energy, sad
#   - 12 BPM = Relaxed breathing (Apple Watch validated)
#   - 24 BPM = Thoughtful, curious
#   - 33 BPM = Deliberate processing
#   - 50 BPM = Elevated heartbeat (joy)
#   - 100 BPM = High excitement
#   - 171 BPM = Fight-or-flight
#
# Sources:
#   - Color psychology: PMC4383146, Frontiers fpsyg.2022.515215
#   - Cardiac arousal: PMC8237168, PMC5761738
#   - Disney timing: "The Illusion of Life" Johnston & Thomas 1981

EMOTION_CONFIGS: Dict[EmotionState, EmotionConfig] = {
    # IDLE: Alive readiness with micro life signs
    # Color: Neutral-warm blue (5500K) - approachable calm
    # Timing: 12 BPM breathing - validated by Apple Watch research
    # Disney: Slow In/Out, Secondary Action, Appeal
    EmotionState.IDLE: EmotionConfig(
        led_color=(100, 160, 255),         # Neutral-warm blue (5500K equiv)
        led_pattern='breathing',           # Gaussian breathing with micro-movements
        led_brightness=128,                # Medium - alive but not demanding
        pattern_speed=0.5,                 # 5.0s cycle = 12 BPM
        transition_ms=800,                 # Gradual settling
    ),

    # HAPPY: Genuine warmth with anticipation sparkles
    # Color: Soft warm yellow (2800K) - joy, sunshine
    # Timing: 50 BPM pulse - elevated heartbeat during joy
    # Disney: Anticipation, Exaggeration, Secondary Action
    EmotionState.HAPPY: EmotionConfig(
        led_color=(255, 210, 80),          # Soft warm yellow (2800K equiv)
        led_pattern='pulse',               # Quick pulse with anticipation dip
        led_brightness=200,                # Bright - open expression
        pattern_speed=1.5,                 # 1.2s cycle = 50 BPM
        transition_ms=400,                 # Quick - eager to express
    ),

    # CURIOUS: Active searching with variable scan speed
    # Color: Pure teal-cyan (5500K) - intellectual focus
    # Timing: 24 BPM scanning - thoughtful, not rushed
    # Disney: Follow Through, Timing, Staging
    EmotionState.CURIOUS: EmotionConfig(
        led_color=(30, 240, 200),          # Pure teal-cyan (5500K equiv)
        led_pattern='breathing',           # Scanning rotation with variable speed
        led_brightness=160,                # Medium-high - engaged
        pattern_speed=0.7,                 # 2.5s cycle = 24 BPM
        transition_ms=500,                 # Medium - considering
    ),

    # ALERT: Urgent attention without anxiety
    # Color: Saturated red-orange (1800K) - urgency, warning
    # Timing: 171 BPM pulse - fight-or-flight response
    # Disney: Timing, Anticipation, Appeal
    EmotionState.ALERT: EmotionConfig(
        led_color=(255, 70, 40),           # Saturated red-orange (1800K)
        led_pattern='pulse',               # Fast pulse with ramp-up
        led_brightness=220,                # High - demanding attention
        pattern_speed=2.0,                 # 0.35s cycle = 171 BPM
        transition_ms=200,                 # Very fast - immediate
    ),

    # SAD: Authentic melancholy with droop gradient
    # Color: Deep desaturated blue (9000K) - withdrawal, introspection
    # Timing: 7.5 BPM breathing - low energy, reluctant
    # Disney: Appeal (vulnerability), Secondary Action, Exaggeration
    EmotionState.SAD: EmotionConfig(
        led_color=(70, 90, 160),           # Deep desaturated blue (9000K)
        led_pattern='breathing',           # Slow breathing with quadratic droop
        led_brightness=80,                 # Dim - withdrawn
        pattern_speed=0.25,                # 8.0s cycle = 7.5 BPM
        transition_ms=1000,                # Slow - reluctant
    ),

    # SLEEPY: Peaceful drowsiness fighting sleep
    # Color: Soft lavender (2700K) - melatonin-associated warmth
    # Timing: 6 BPM breathing - near-sleep rate
    # Disney: Straight Ahead, Secondary Action, Timing
    EmotionState.SLEEPY: EmotionConfig(
        led_color=(140, 110, 190),         # Soft lavender (2700K equiv)
        led_pattern='breathing',           # Ultra-slow with irregular blinks
        led_brightness=60,                 # Very dim - shutting down
        pattern_speed=0.2,                 # 10.0s cycle = 6 BPM
        transition_ms=1500,                # Very slow - gradual
    ),

    # EXCITED: Barely contained energy with rainbow bursts
    # Color: Bright orange (2200K) - maximum warmth, enthusiasm
    # Timing: 100 BPM spin - maximum sustainable excitement
    # Disney: Squash & Stretch, Exaggeration, Secondary Action
    EmotionState.EXCITED: EmotionConfig(
        led_color=(255, 140, 40),          # Bright orange (2200K equiv)
        led_pattern='spin',                # Fast spin with sparkle bursts
        led_brightness=230,                # Very bright - maximum expression
        pattern_speed=2.5,                 # 0.6s cycle = 100 BPM
        transition_ms=300,                 # Quick - bursting forth
    ),

    # THINKING: Visible processing with deliberate rhythm
    # Color: Cool blue-white (7000K) - cognitive enhancement
    # Timing: 33 BPM rotation - deliberate, mechanical
    # Disney: Staging, Timing, Anticipation
    EmotionState.THINKING: EmotionConfig(
        led_color=(170, 190, 255),         # Cool blue-white (7000K equiv)
        led_pattern='spin',                # Step-wise rotation
        led_brightness=150,                # Medium - focused
        pattern_speed=0.9,                 # 1.8s cycle = 33 BPM
        transition_ms=400,                 # Medium - shifting focus
    ),

    # === Social Emotions (4) - Connection-Building ===
    # Added by Agent 2 (Social Emotion Implementation Specialist)
    # Research: Anki Cozmo/Vector emotion engine, color psychology, social HRI

    EmotionState.PLAYFUL: EmotionConfig(
        led_color=(255, 180, 100),        # Warm orange - energetic, fun
        led_pattern='playful',            # Bouncy asymmetric with sparkles
        led_brightness=200,               # Bright - inviting engagement
        pattern_speed=1.4,                # Fast - mischievous energy
        transition_ms=300,                # Quick - eager to play
        # Psychology: Play signal reduces social tension, invites interaction
        # Disney: EXAGGERATION, SECONDARY ACTION (sparkles), variable TIMING
    ),

    EmotionState.AFFECTIONATE: EmotionConfig(
        led_color=(255, 150, 180),        # Warm pink-coral - nurturing
        led_pattern='affectionate',       # Heartbeat pulse at 72 BPM
        led_brightness=180,               # Warm - not overwhelming
        pattern_speed=1.0,                # Natural heartbeat rhythm
        transition_ms=600,                # Gradual - warmth builds slowly
        # Psychology: Triggers oxytocin bonding response
        # Color: Pink = unconditional love, nurturing, warmth
        # Disney: TIMING (heartbeat), SLOW IN/SLOW OUT, APPEAL
    ),

    EmotionState.EMPATHETIC: EmotionConfig(
        led_color=(180, 180, 220),        # Soft lavender-blue - receptive
        led_pattern='empathetic',         # Mirroring breathing rhythm
        led_brightness=140,               # Soft - non-threatening
        pattern_speed=0.8,                # Slow - calming presence
        transition_ms=500,                # Medium - natural shift
        # Psychology: Mirroring triggers connection through perceived understanding
        # Disney: TIMING, FOLLOW THROUGH, APPEAL
    ),

    EmotionState.GRATEFUL: EmotionConfig(
        led_color=(255, 200, 100),        # Golden amber - appreciation
        led_pattern='grateful',           # Brightness surge (like a bow)
        led_brightness=190,               # Bright - expressing appreciation
        pattern_speed=1.0,                # Natural timing
        transition_ms=400,                # Medium - acknowledgment pace
        # Psychology: Communicates appreciation and acknowledgment
        # Color: Gold = value, warmth, gratitude
        # Disney: ANTICIPATION, FOLLOW THROUGH, EXAGGERATION
    ),
}


# === Valid Transitions Matrix ===
#
# Defines valid emotional state transitions based on psychological naturalism.
# Updated to include social emotions (Agent 2, Week 02).
#
# Design Philosophy:
# - All emotions can transition to/from IDLE (universal reset)
# - Social emotions flow naturally from positive states
# - Empathetic can be reached from any state (always receptive)
# - Grateful typically follows positive interactions

VALID_TRANSITIONS: Dict[EmotionState, Set[EmotionState]] = {
    EmotionState.IDLE: {
        EmotionState.HAPPY,
        EmotionState.CURIOUS,
        EmotionState.ALERT,
        EmotionState.SAD,
        EmotionState.SLEEPY,
        EmotionState.EXCITED,
        EmotionState.THINKING,
        # Social emotions - IDLE can transition to any
        EmotionState.PLAYFUL,       # Starting to play
        EmotionState.AFFECTIONATE,  # Feeling warmth
        EmotionState.EMPATHETIC,    # Being supportive
        EmotionState.GRATEFUL,      # Expressing thanks
    },

    EmotionState.HAPPY: {
        EmotionState.IDLE,
        EmotionState.CURIOUS,
        EmotionState.EXCITED,
        EmotionState.ALERT,      # Can be startled while happy
        EmotionState.THINKING,   # Pondering something
        # Social emotions - HAPPY flows naturally to positive social states
        EmotionState.PLAYFUL,       # Joy leads to play
        EmotionState.AFFECTIONATE,  # Happiness deepens to affection
        EmotionState.GRATEFUL,      # Happy about something = grateful
    },

    EmotionState.CURIOUS: {
        EmotionState.IDLE,
        EmotionState.HAPPY,      # Discovery leads to joy
        EmotionState.ALERT,      # Found something concerning
        EmotionState.THINKING,   # Processing what was found
        EmotionState.SAD,        # Disappointment
        # Social emotions
        EmotionState.PLAYFUL,       # Curious play
        EmotionState.EMPATHETIC,    # Curious about feelings
    },

    EmotionState.ALERT: {
        EmotionState.IDLE,       # False alarm
        EmotionState.CURIOUS,    # Investigating
        EmotionState.HAPPY,      # Resolved positively
        EmotionState.SAD,        # Resolved negatively
        EmotionState.THINKING,   # Processing the situation
        # Social emotions
        EmotionState.EMPATHETIC,    # Alert to emotional needs
        EmotionState.GRATEFUL,      # Grateful for help
    },

    EmotionState.SAD: {
        EmotionState.IDLE,       # Moving on
        EmotionState.HAPPY,      # Cheered up
        EmotionState.ALERT,      # Something demands attention
        EmotionState.CURIOUS,    # Distracted by something
        EmotionState.SLEEPY,     # Giving up, rest
        # Social emotions
        EmotionState.EMPATHETIC,    # Sad but supportive
        EmotionState.GRATEFUL,      # Grateful for comfort
        EmotionState.AFFECTIONATE,  # Seeking connection
    },

    EmotionState.SLEEPY: {
        EmotionState.IDLE,       # Waking up gently
        EmotionState.ALERT,      # Startled awake (always allowed)
        EmotionState.CURIOUS,    # Something interesting
        # Social emotions
        EmotionState.AFFECTIONATE,  # Sleepy cuddles
    },

    EmotionState.EXCITED: {
        EmotionState.IDLE,       # Calming down
        EmotionState.HAPPY,      # Settling into joy
        EmotionState.ALERT,      # Excitement becomes concern
        EmotionState.CURIOUS,    # Excited about something specific
        EmotionState.THINKING,   # Processing the excitement
        # Social emotions - excited leads to playful engagement
        EmotionState.PLAYFUL,       # Excitement -> play
        EmotionState.AFFECTIONATE,  # Excited love
        EmotionState.GRATEFUL,      # Excited gratitude
    },

    EmotionState.THINKING: {
        EmotionState.IDLE,       # Finished thinking
        EmotionState.HAPPY,      # Good conclusion
        EmotionState.SAD,        # Bad conclusion
        EmotionState.ALERT,      # Realized something urgent
        EmotionState.CURIOUS,    # Need more information
        EmotionState.EXCITED,    # Eureka!
        # Social emotions
        EmotionState.EMPATHETIC,    # Thinking about others
        EmotionState.GRATEFUL,      # Realized something to be thankful for
    },

    # === Social Emotion Transitions ===
    # Added by Agent 2 (Social Emotion Implementation Specialist)

    EmotionState.PLAYFUL: {
        EmotionState.IDLE,       # Play session ends
        EmotionState.HAPPY,      # Play leads to joy
        EmotionState.EXCITED,    # Play escalates
        EmotionState.CURIOUS,    # Playful investigation
        EmotionState.ALERT,      # Play interrupted
        # Social emotion flows
        EmotionState.AFFECTIONATE,  # Playful -> affection (deepening bond)
        EmotionState.GRATEFUL,      # Grateful for play partner
    },

    EmotionState.AFFECTIONATE: {
        EmotionState.IDLE,       # Returning to neutral
        EmotionState.HAPPY,      # Warm happiness
        EmotionState.SLEEPY,     # Comfortable drowsiness
        EmotionState.SAD,        # Missing someone
        EmotionState.ALERT,      # Something demands attention (always reachable)
        # Social emotion flows
        EmotionState.PLAYFUL,       # Affectionate play
        EmotionState.EMPATHETIC,    # Deep understanding
        EmotionState.GRATEFUL,      # Grateful for connection
    },

    EmotionState.EMPATHETIC: {
        EmotionState.IDLE,       # Returning to neutral
        EmotionState.HAPPY,      # Shared joy
        EmotionState.SAD,        # Shared sadness
        EmotionState.CURIOUS,    # Wanting to understand more
        EmotionState.THINKING,   # Processing feelings
        EmotionState.ALERT,      # Something demands attention (always reachable)
        # Social emotion flows
        EmotionState.AFFECTIONATE,  # Empathy -> affection
        EmotionState.GRATEFUL,      # Grateful to help
    },

    EmotionState.GRATEFUL: {
        EmotionState.IDLE,       # Gratitude expressed, settling
        EmotionState.HAPPY,      # Gratitude -> happiness
        EmotionState.CURIOUS,    # Looking for more to appreciate
        EmotionState.ALERT,      # Something demands attention (always reachable)
        # Social emotion flows
        EmotionState.AFFECTIONATE,  # Deep gratitude -> affection
        EmotionState.PLAYFUL,       # Joyful gratitude -> playfulness
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
