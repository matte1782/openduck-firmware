#!/usr/bin/env python3
"""
Enhanced Micro-Expression System - OpenDuck Mini V3
Agent 4: Micro-Expression Enhancement

Boston Dynamics / Pixar / DeepMind Quality Standard

This module provides advanced micro-expression systems that add life and
personality to the robot's LED eye expressions:

1. BLINK SYSTEM - Natural blinking with emotional modulation
2. BREATHING OVERLAY - Subtle brightness modulation creating "alive" baseline
3. SACCADE SYSTEM - Quick eye movements simulating attention shifts
4. PUPIL DILATION - Center-weighted brightness for arousal/interest
5. MICRO-TREMORS - Tiny random variations preventing "dead" appearance

Research Foundation:
    - Blink Rate: 15-20 per minute baseline, doubles under stress
      Source: https://psychology.arizona.edu/news/blinking-offers-clues-human-response-under-stress
    - Pupil Dilation: Reflects emotional arousal via sympathetic nervous system
      Source: https://pmc.ncbi.nlm.nih.gov/articles/PMC3612940/
    - Saccades: Quick eye movements for attention allocation
      Source: https://pmc.ncbi.nlm.nih.gov/articles/PMC3623695/
    - FACS: Facial Action Coding System by Paul Ekman
      Source: https://www.paulekman.com/facial-action-coding-system/

Performance Constraint: Total micro-expression overhead <0.5ms per frame.

Disney Animation Principles Applied:
    - Secondary Action: Micro-expressions support main emotion
    - Follow Through: Subtle movements continue after main action
    - Timing: Speed matches emotional energy

Author: Specialist Agent 4 - Micro-Expression Engineer
Created: 18 January 2026 (Day 10)
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Tuple, Callable
import time
import math
import random

# Type aliases
RGB = Tuple[int, int, int]


# ============================================================================
# CONSTANTS - Research-based parameters
# ============================================================================

# Blink rate research: 15-20 blinks/minute at rest, doubles under stress
# Source: https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0338262
BLINK_BASE_RATE_PER_MINUTE = 17.0  # Average of 15-20 range
BLINK_MIN_RATE = 6.0   # Very sleepy/calm
BLINK_MAX_RATE = 40.0  # High anxiety/stress (nearly doubled)

# Blink duration research: 100-150ms typical human blink
BLINK_DURATION_MIN_MS = 80   # Quick nervous blink
BLINK_DURATION_NORMAL_MS = 150  # Standard blink
BLINK_DURATION_SLOW_MS = 400    # Sleepy/trust blink
BLINK_DURATION_MAX_MS = 600     # Extended "slow blink" (cat trust signal)

# Breathing rate: 12-20 breaths/minute typical adult
BREATHING_BASE_RATE = 15.0  # breaths per minute
BREATHING_MIN_RATE = 6.0    # Near-sleep (sleepy emotion)
BREATHING_MAX_RATE = 24.0   # Excited/anxious

# Saccade parameters (eye dart movements)
# Saccades occur 3-4 times per second during active visual search
SACCADE_BASE_RATE = 0.5     # per second during idle (lower for robot)
SACCADE_MAX_RATE = 2.0      # per second during alert/curious
SACCADE_DURATION_MS = 50    # 50-100ms typical saccade
SACCADE_RETURN_DELAY_MS = 200  # Time before returning to center

# Pupil dilation: Larger pupils = higher arousal/interest
PUPIL_DILATION_MAX = 0.4    # Maximum brightness increase for center LEDs
PUPIL_CONSTRICTION_MAX = 0.3  # Maximum brightness decrease (fear response)

# Micro-tremor parameters
TREMOR_AMPLITUDE_MIN = 0.01   # Barely perceptible
TREMOR_AMPLITUDE_MAX = 0.08   # Noticeable but subtle
TREMOR_FREQUENCY_HZ = 8.0     # ~8Hz natural physiological tremor

# LED ring geometry (16 LEDs per ring)
NUM_LEDS = 16
# Center LEDs for pupil simulation (indices for 16-LED ring)
# Assuming LEDs 7, 8, 9 are "center" region
CENTER_LED_INDICES = [7, 8, 9]
# Top LEDs (for droop effect)
TOP_LED_INDICES = [0, 1, 2, 14, 15]
# Bottom LEDs
BOTTOM_LED_INDICES = [6, 7, 8, 9, 10]

# Performance budget
MAX_MICRO_EXPRESSION_TIME_MS = 0.5


# ============================================================================
# EMOTION-BASED MODULATION PARAMETERS
# ============================================================================

@dataclass(frozen=True)
class EmotionMicroParams:
    """
    Micro-expression parameters modulated by emotion.

    These values adjust the base micro-expression rates based on
    the current emotional state, following psychological research.

    Attributes:
        blink_rate_modifier: Multiplier for base blink rate (-1 to +1)
            Positive = more blinks, Negative = fewer blinks
        blink_duration_modifier: Multiplier for blink duration (-1 to +1)
            Positive = longer blinks, Negative = quicker blinks
        breathing_rate_modifier: Multiplier for breathing rate (-1 to +1)
        saccade_rate_modifier: Multiplier for eye dart frequency (-1 to +1)
        pupil_dilation: Direct pupil state (-1 to +1)
            Positive = dilated (interest), Negative = constricted (fear)
        tremor_amplitude: Tremor intensity (0 to 1)
    """
    blink_rate_modifier: float = 0.0
    blink_duration_modifier: float = 0.0
    breathing_rate_modifier: float = 0.0
    saccade_rate_modifier: float = 0.0
    pupil_dilation: float = 0.0
    tremor_amplitude: float = 0.3


# Emotion-specific micro-expression parameters
# Based on psychological research on blink rate, pupil dilation, and arousal
EMOTION_MICRO_PARAMS: Dict[str, EmotionMicroParams] = {
    # IDLE: Relaxed, neutral state
    "idle": EmotionMicroParams(
        blink_rate_modifier=0.0,      # Normal blink rate
        blink_duration_modifier=0.0,   # Normal duration
        breathing_rate_modifier=0.0,   # Normal breathing
        saccade_rate_modifier=-0.3,    # Few eye movements (relaxed)
        pupil_dilation=0.0,            # Neutral pupil
        tremor_amplitude=0.2,          # Minimal tremor
    ),

    # HAPPY: Positive arousal, engaged
    "happy": EmotionMicroParams(
        blink_rate_modifier=0.1,       # Slightly more blinks (expressive)
        blink_duration_modifier=-0.2,  # Quicker blinks (energetic)
        breathing_rate_modifier=0.2,   # Slightly elevated breathing
        saccade_rate_modifier=0.2,     # More eye movement (engaged)
        pupil_dilation=0.3,            # Dilated (positive arousal)
        tremor_amplitude=0.3,          # Moderate liveliness
    ),

    # CURIOUS: Interested, investigating
    "curious": EmotionMicroParams(
        blink_rate_modifier=-0.3,      # Fewer blinks (focused attention)
        blink_duration_modifier=-0.1,  # Slightly quicker
        breathing_rate_modifier=0.1,   # Slightly elevated
        saccade_rate_modifier=0.8,     # Many eye darts (scanning)
        pupil_dilation=0.5,            # Very dilated (high interest)
        tremor_amplitude=0.4,          # Alert tremor
    ),

    # ALERT: High arousal, attention demanded
    "alert": EmotionMicroParams(
        blink_rate_modifier=-0.5,      # Very few blinks (vigilant)
        blink_duration_modifier=-0.3,  # Very quick blinks
        breathing_rate_modifier=0.5,   # Rapid breathing
        saccade_rate_modifier=1.0,     # Maximum scanning
        pupil_dilation=0.6,            # Very dilated (threat assessment)
        tremor_amplitude=0.5,          # High tremor (adrenaline)
    ),

    # SAD: Low arousal, withdrawal
    "sad": EmotionMicroParams(
        blink_rate_modifier=-0.2,      # Fewer blinks (withdrawn)
        blink_duration_modifier=0.4,   # Longer blinks (droopy)
        breathing_rate_modifier=-0.4,  # Slow breathing (sighing)
        saccade_rate_modifier=-0.6,    # Few eye movements (disengaged)
        pupil_dilation=-0.2,           # Slightly constricted
        tremor_amplitude=0.1,          # Minimal tremor (low energy)
    ),

    # SLEEPY: Very low arousal, rest
    "sleepy": EmotionMicroParams(
        blink_rate_modifier=-0.4,      # Slow blink rate
        blink_duration_modifier=0.8,   # Very long blinks (slow blink = trust)
        breathing_rate_modifier=-0.6,  # Very slow breathing
        saccade_rate_modifier=-0.8,    # Almost no eye movement
        pupil_dilation=-0.1,           # Slightly constricted (low light)
        tremor_amplitude=0.05,         # Minimal tremor
    ),

    # EXCITED: Very high positive arousal
    "excited": EmotionMicroParams(
        blink_rate_modifier=0.6,       # Rapid blinking (can't contain it)
        blink_duration_modifier=-0.4,  # Very quick blinks
        breathing_rate_modifier=0.7,   # Rapid breathing
        saccade_rate_modifier=0.7,     # Lots of eye movement
        pupil_dilation=0.7,            # Very dilated (high arousal)
        tremor_amplitude=0.7,          # High tremor (excitement)
    ),

    # THINKING: Cognitive processing
    "thinking": EmotionMicroParams(
        blink_rate_modifier=-0.4,      # Fewer blinks (concentration)
        blink_duration_modifier=0.1,   # Slightly longer (thoughtful)
        breathing_rate_modifier=0.0,   # Normal breathing
        saccade_rate_modifier=-0.5,    # Reduced scanning (internal focus)
        pupil_dilation=0.2,            # Slightly dilated (cognitive effort)
        tremor_amplitude=0.2,          # Minimal tremor
    ),

    # ANXIOUS: High negative arousal (compound emotion)
    "anxious": EmotionMicroParams(
        blink_rate_modifier=0.8,       # Near-double blink rate (stress)
        blink_duration_modifier=-0.3,  # Quick nervous blinks
        breathing_rate_modifier=0.6,   # Rapid shallow breathing
        saccade_rate_modifier=0.9,     # Hypervigilant scanning
        pupil_dilation=0.4,            # Dilated (fear response)
        tremor_amplitude=0.6,          # High nervous tremor
    ),

    # PLAYFUL: Fun, mischievous
    "playful": EmotionMicroParams(
        blink_rate_modifier=0.3,       # Animated blinking
        blink_duration_modifier=-0.2,  # Quick playful blinks
        breathing_rate_modifier=0.3,   # Elevated (fun)
        saccade_rate_modifier=0.5,     # Darting playful looks
        pupil_dilation=0.4,            # Dilated (engagement)
        tremor_amplitude=0.5,          # Bouncy energy
    ),

    # AFFECTIONATE: Warm, bonding
    "affectionate": EmotionMicroParams(
        blink_rate_modifier=-0.1,      # Slower, more deliberate
        blink_duration_modifier=0.5,   # Long slow blinks (trust signal)
        breathing_rate_modifier=-0.2,  # Calm deep breathing
        saccade_rate_modifier=-0.4,    # Soft gaze, few darts
        pupil_dilation=0.6,            # Very dilated (attraction/bonding)
        tremor_amplitude=0.2,          # Gentle tremor
    ),

    # CONFUSED: Uncertain, searching
    "confused": EmotionMicroParams(
        blink_rate_modifier=0.4,       # Increased blinking (uncertainty)
        blink_duration_modifier=0.0,   # Normal duration
        breathing_rate_modifier=0.1,   # Slightly elevated
        saccade_rate_modifier=0.6,     # Searching eye movements
        pupil_dilation=0.2,            # Slightly dilated (effort)
        tremor_amplitude=0.4,          # Uncertain tremor
    ),

    # SURPRISED: Sudden high arousal
    "surprised": EmotionMicroParams(
        blink_rate_modifier=-0.8,      # Eyes wide, minimal blinking
        blink_duration_modifier=-0.5,  # If blink, very quick
        breathing_rate_modifier=0.4,   # Gasp
        saccade_rate_modifier=0.0,     # Frozen gaze initially
        pupil_dilation=0.8,            # Maximum dilation (startle)
        tremor_amplitude=0.3,          # Brief tremor
    ),
}


# ============================================================================
# BLINK CONTROLLER - Research-Based Natural Blinking
# ============================================================================

class BlinkState(Enum):
    """States for the blink state machine."""
    OPEN = "open"           # Eyes fully open
    CLOSING = "closing"     # Eyelid descending
    CLOSED = "closed"       # Brief closed moment
    OPENING = "opening"     # Eyelid ascending


@dataclass
class BlinkController:
    """
    Controls natural blinking with emotion-based modulation.

    Research basis:
    - Human blink rate: 15-20 per minute at rest
    - Stress nearly doubles blink rate
    - Blink duration: 100-150ms typical
    - "Slow blink" (300-600ms) is a trust signal (cat research applicable)

    Sources:
    - https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0338262
    - https://psychology.arizona.edu/news/blinking-offers-clues-human-response-under-stress

    Disney Principle: Timing - Blink speed matches emotional energy.

    Attributes:
        base_rate: Blinks per minute at neutral state
        arousal_modifier: Current arousal level (-1 to +1)
        last_blink_time: Timestamp of last blink start
        blink_state: Current state in blink cycle
        blink_progress: Progress through current blink (0-1)
    """
    base_rate: float = BLINK_BASE_RATE_PER_MINUTE
    arousal_modifier: float = 0.0
    duration_modifier: float = 0.0

    # Internal state - using accumulated time instead of wall clock for testability
    _accumulated_time_ms: float = 0.0  # Total simulated time in ms
    _last_blink_time_ms: float = 0.0   # Time of last blink in ms
    _blink_state: BlinkState = field(default=BlinkState.OPEN)
    _blink_progress: float = 0.0
    _current_blink_duration_ms: int = BLINK_DURATION_NORMAL_MS
    _next_blink_interval_ms: float = 0.0  # Now in milliseconds
    _rng: random.Random = field(default_factory=random.Random)

    def __post_init__(self):
        """Initialize with randomized first blink time."""
        self._schedule_next_blink()

    def _schedule_next_blink(self) -> None:
        """Schedule the next blink with natural variation."""
        # Calculate effective blink rate based on arousal
        # Positive arousal = more blinks, negative = fewer
        rate_modifier = 1.0 + (self.arousal_modifier * 0.5)
        effective_rate = self.base_rate * rate_modifier
        effective_rate = max(BLINK_MIN_RATE, min(BLINK_MAX_RATE, effective_rate))

        # Convert rate to interval (milliseconds between blinks)
        mean_interval_ms = 60000.0 / effective_rate  # 60 seconds in ms

        # Add natural variation (20-30% randomness)
        variation = self._rng.uniform(0.7, 1.3)
        self._next_blink_interval_ms = mean_interval_ms * variation

    def _calculate_blink_duration(self) -> int:
        """Calculate blink duration based on emotional state."""
        # Base duration
        base_duration = BLINK_DURATION_NORMAL_MS

        # Apply duration modifier
        # Positive modifier = longer blinks, negative = quicker
        if self.duration_modifier > 0:
            # Interpolate toward slow blink
            extra = (BLINK_DURATION_SLOW_MS - base_duration) * self.duration_modifier
        else:
            # Interpolate toward quick blink
            extra = (base_duration - BLINK_DURATION_MIN_MS) * self.duration_modifier

        duration = int(base_duration + extra)
        return max(BLINK_DURATION_MIN_MS, min(BLINK_DURATION_MAX_MS, duration))

    def set_emotion_params(self, params: EmotionMicroParams) -> None:
        """Update blink parameters from emotion."""
        self.arousal_modifier = params.blink_rate_modifier
        self.duration_modifier = params.blink_duration_modifier

    def update(self, delta_ms: float) -> bool:
        """
        Update blink state machine.

        Args:
            delta_ms: Milliseconds since last update

        Returns:
            True if currently in a blink (not fully open)
        """
        self._accumulated_time_ms += delta_ms

        if self._blink_state == BlinkState.OPEN:
            # Check if it's time for a new blink
            time_since_last = self._accumulated_time_ms - self._last_blink_time_ms
            if time_since_last >= self._next_blink_interval_ms:
                # Start a new blink
                self._blink_state = BlinkState.CLOSING
                self._blink_progress = 0.0
                self._current_blink_duration_ms = self._calculate_blink_duration()
                self._last_blink_time_ms = self._accumulated_time_ms
            return False

        elif self._blink_state == BlinkState.CLOSING:
            # Closing phase: 0% to 50% of duration
            close_duration = self._current_blink_duration_ms * 0.4  # 40% for close
            self._blink_progress += (delta_ms / close_duration)

            if self._blink_progress >= 1.0:
                self._blink_state = BlinkState.CLOSED
                self._blink_progress = 0.0
            return True

        elif self._blink_state == BlinkState.CLOSED:
            # Brief closed moment: 10% of duration
            closed_duration = self._current_blink_duration_ms * 0.1
            self._blink_progress += (delta_ms / closed_duration)

            if self._blink_progress >= 1.0:
                self._blink_state = BlinkState.OPENING
                self._blink_progress = 0.0
            return True

        elif self._blink_state == BlinkState.OPENING:
            # Opening phase: 50% of duration
            open_duration = self._current_blink_duration_ms * 0.5
            self._blink_progress += (delta_ms / open_duration)

            if self._blink_progress >= 1.0:
                self._blink_state = BlinkState.OPEN
                self._blink_progress = 0.0
                self._schedule_next_blink()
            return True

        return False

    def should_blink(self, delta_ms: float) -> bool:
        """
        Legacy interface: Check if a blink should start this frame.

        Args:
            delta_ms: Milliseconds since last check

        Returns:
            True if blink should trigger this frame
        """
        time_since_last = self._accumulated_time_ms - self._last_blink_time_ms
        return time_since_last >= self._next_blink_interval_ms

    def get_blink_duration(self) -> int:
        """
        Get current blink duration in milliseconds.

        Returns:
            Duration for current blink type
        """
        return self._calculate_blink_duration()

    def get_brightness_modifier(self) -> float:
        """
        Get current brightness modifier for blink effect.

        Returns:
            Multiplier 0.0 (closed) to 1.0 (open)
        """
        if self._blink_state == BlinkState.OPEN:
            return 1.0
        elif self._blink_state == BlinkState.CLOSING:
            # Ease-in closing (accelerate)
            return 1.0 - (self._blink_progress ** 2)
        elif self._blink_state == BlinkState.CLOSED:
            return 0.1  # Never fully black (some ambient glow)
        elif self._blink_state == BlinkState.OPENING:
            # Ease-out opening (decelerate)
            return 0.1 + 0.9 * (1.0 - (1.0 - self._blink_progress) ** 2)
        return 1.0

    def force_blink(self, duration_ms: Optional[int] = None) -> None:
        """Force an immediate blink."""
        self._blink_state = BlinkState.CLOSING
        self._blink_progress = 0.0
        self._current_blink_duration_ms = duration_ms or self._calculate_blink_duration()
        self._last_blink_time_ms = self._accumulated_time_ms

    def is_blinking(self) -> bool:
        """Check if currently in a blink."""
        return self._blink_state != BlinkState.OPEN

    def seed_rng(self, seed: int) -> None:
        """Seed RNG for reproducible tests."""
        self._rng.seed(seed)


# ============================================================================
# BREATHING OVERLAY - Universal Liveliness Layer
# ============================================================================

@dataclass
class BreathingController:
    """
    Provides subtle breathing-like brightness modulation.

    Creates "alive" baseline that runs on ALL emotions.
    Based on human breathing patterns (12-20 breaths/minute).

    Disney Principle: Secondary Action - Breathing supports main emotion
    without competing for attention.

    Attributes:
        base_rate: Breaths per minute at neutral
        rate_modifier: Arousal-based rate adjustment (-1 to +1)
        amplitude: Brightness variation amplitude (0-1)
    """
    base_rate: float = BREATHING_BASE_RATE
    rate_modifier: float = 0.0
    amplitude: float = 0.08  # 8% brightness variation (subtle)

    # Internal state
    _phase: float = 0.0  # 0-2*pi

    def set_emotion_params(self, params: EmotionMicroParams) -> None:
        """Update breathing from emotion parameters."""
        self.rate_modifier = params.breathing_rate_modifier
        # Amplitude can vary with arousal
        self.amplitude = 0.05 + abs(params.breathing_rate_modifier) * 0.05

    def update(self, delta_ms: float) -> float:
        """
        Update breathing phase and return brightness modifier.

        Args:
            delta_ms: Milliseconds since last update

        Returns:
            Brightness modifier centered around 1.0
        """
        # Calculate effective rate
        effective_rate = self.base_rate * (1.0 + self.rate_modifier * 0.5)
        effective_rate = max(BREATHING_MIN_RATE, min(BREATHING_MAX_RATE, effective_rate))

        # Convert to phase increment
        # Rate in breaths/minute -> radians per millisecond
        radians_per_breath = 2.0 * math.pi
        radians_per_minute = effective_rate * radians_per_breath
        radians_per_ms = radians_per_minute / 60000.0

        # Update phase
        self._phase += delta_ms * radians_per_ms
        if self._phase > 2.0 * math.pi:
            self._phase -= 2.0 * math.pi

        # Breathing curve: inhale rises (0 to pi), exhale falls (pi to 2*pi)
        # Use sine wave with slight asymmetry (inhale faster than exhale)
        if self._phase < math.pi:
            # Inhale phase - slightly faster rise
            normalized_phase = self._phase / math.pi
            sin_val = math.sin(normalized_phase * math.pi / 2.0)
            # Use abs to avoid complex numbers with fractional exponents
            breath_value = abs(sin_val) ** 0.8 if sin_val >= 0 else -(abs(sin_val) ** 0.8)
        else:
            # Exhale phase - slower fall
            normalized_phase = (self._phase - math.pi) / math.pi
            cos_val = math.cos(normalized_phase * math.pi / 2.0)
            # Use abs to avoid complex numbers with fractional exponents
            breath_value = abs(cos_val) ** 1.2 if cos_val >= 0 else -(abs(cos_val) ** 1.2)

        # Convert to brightness modifier (centered on 1.0)
        return 1.0 + (breath_value - 0.5) * self.amplitude * 2.0

    def get_phase(self) -> float:
        """Get current breath phase (0 to 2*pi)."""
        return self._phase

    def reset(self) -> None:
        """Reset breathing to start of cycle."""
        self._phase = 0.0


# ============================================================================
# SACCADE SYSTEM - Eye Dart Movements
# ============================================================================

class SaccadeDirection(Enum):
    """Direction of eye dart movement."""
    NONE = "none"
    LEFT = "left"
    RIGHT = "right"
    UP = "up"
    DOWN = "down"


@dataclass
class SaccadeController:
    """
    Simulates quick eye movements (saccades) for attention shifts.

    Saccades are rapid eye movements that shift gaze between fixation
    points. In LED rings, this is simulated by shifting brightness
    around the ring briefly before returning.

    Research:
    - Saccades take 50-100ms
    - Frequency increases with arousal/alertness
    - Direction randomized but weighted by attention focus

    Source: https://pmc.ncbi.nlm.nih.gov/articles/PMC3623695/

    Disney Principle: Timing - Quick movements suggest alertness.
    """
    base_rate: float = SACCADE_BASE_RATE  # per second
    rate_modifier: float = 0.0

    # Internal state - using accumulated time for testability
    _accumulated_time_ms: float = 0.0
    _last_saccade_time_ms: float = 0.0
    _current_direction: SaccadeDirection = field(default=SaccadeDirection.NONE)
    _saccade_progress: float = 0.0
    _in_saccade: bool = False
    _in_return: bool = False
    _next_saccade_interval_ms: float = 2000.0  # In milliseconds
    _rng: random.Random = field(default_factory=random.Random)

    def __post_init__(self):
        """Initialize with randomized timing."""
        self._schedule_next_saccade()

    def _schedule_next_saccade(self) -> None:
        """Schedule next saccade with natural variation."""
        effective_rate = self.base_rate * (1.0 + self.rate_modifier)
        effective_rate = max(0.1, min(SACCADE_MAX_RATE, effective_rate))

        # Mean interval in milliseconds
        mean_interval_ms = 1000.0 / effective_rate
        variation = self._rng.uniform(0.5, 1.5)
        self._next_saccade_interval_ms = mean_interval_ms * variation

    def set_emotion_params(self, params: EmotionMicroParams) -> None:
        """Update saccade parameters from emotion."""
        self.rate_modifier = params.saccade_rate_modifier

    def update(self, delta_ms: float) -> bool:
        """
        Update saccade state.

        Args:
            delta_ms: Milliseconds since last update

        Returns:
            True if currently in a saccade movement
        """
        self._accumulated_time_ms += delta_ms

        if not self._in_saccade and not self._in_return:
            # Check if time for new saccade
            time_since_last = self._accumulated_time_ms - self._last_saccade_time_ms
            if time_since_last >= self._next_saccade_interval_ms:
                self._start_saccade()
            return False

        if self._in_saccade:
            # Progress through saccade
            self._saccade_progress += delta_ms / SACCADE_DURATION_MS
            if self._saccade_progress >= 1.0:
                self._in_saccade = False
                self._in_return = True
                self._saccade_progress = 0.0
            return True

        if self._in_return:
            # Return to center after delay
            self._saccade_progress += delta_ms / SACCADE_RETURN_DELAY_MS
            if self._saccade_progress >= 1.0:
                self._in_return = False
                self._current_direction = SaccadeDirection.NONE
                self._saccade_progress = 0.0
                self._last_saccade_time_ms = self._accumulated_time_ms
                self._schedule_next_saccade()
            return True

        return False

    def _start_saccade(self) -> None:
        """Start a new saccade in random direction."""
        directions = [
            SaccadeDirection.LEFT,
            SaccadeDirection.RIGHT,
            SaccadeDirection.UP,
            SaccadeDirection.DOWN,
        ]
        self._current_direction = self._rng.choice(directions)
        self._in_saccade = True
        self._saccade_progress = 0.0

    def get_per_pixel_modifiers(self, num_leds: int = NUM_LEDS) -> List[float]:
        """
        Get per-LED brightness modifiers for current saccade.

        Args:
            num_leds: Number of LEDs in ring

        Returns:
            List of brightness multipliers per LED
        """
        modifiers = [1.0] * num_leds

        if self._current_direction == SaccadeDirection.NONE:
            return modifiers

        # Calculate saccade intensity based on progress
        if self._in_saccade:
            # Quick movement
            intensity = self._saccade_progress
        elif self._in_return:
            # Slower return
            intensity = 1.0 - self._saccade_progress
        else:
            return modifiers

        # Apply direction-based brightness shift
        # LED ring indices: 0 at top, going clockwise
        # Left = indices 11-14 brighter, Right = indices 2-5 brighter
        # Up = indices 14-1 brighter, Down = indices 6-9 brighter

        shift_amount = 0.2 * intensity  # 20% max brightness shift

        if self._current_direction == SaccadeDirection.LEFT:
            bright_indices = [11, 12, 13, 14]
            dim_indices = [2, 3, 4, 5]
        elif self._current_direction == SaccadeDirection.RIGHT:
            bright_indices = [2, 3, 4, 5]
            dim_indices = [11, 12, 13, 14]
        elif self._current_direction == SaccadeDirection.UP:
            bright_indices = [14, 15, 0, 1]
            dim_indices = [6, 7, 8, 9]
        elif self._current_direction == SaccadeDirection.DOWN:
            bright_indices = [6, 7, 8, 9]
            dim_indices = [14, 15, 0, 1]
        else:
            return modifiers

        for i in bright_indices:
            if i < num_leds:
                modifiers[i] = 1.0 + shift_amount
        for i in dim_indices:
            if i < num_leds:
                modifiers[i] = 1.0 - shift_amount

        return modifiers

    def is_active(self) -> bool:
        """Check if saccade is currently happening."""
        return self._in_saccade or self._in_return

    def get_direction(self) -> SaccadeDirection:
        """Get current saccade direction."""
        return self._current_direction

    def seed_rng(self, seed: int) -> None:
        """Seed RNG for reproducible tests."""
        self._rng.seed(seed)


# ============================================================================
# PUPIL DILATION SIMULATION
# ============================================================================

@dataclass
class PupilController:
    """
    Simulates pupil dilation through center-weighted LED brightness.

    Research: Pupil dilation reflects emotional arousal via sympathetic
    nervous system. Larger pupils = higher arousal/interest.

    Source: https://pmc.ncbi.nlm.nih.gov/articles/PMC3612940/

    Implementation:
    - DILATED: Center LEDs brighter (interest, arousal, attraction)
    - CONSTRICTED: Center LEDs dimmer (fear response, bright light)

    Disney Principle: Exaggeration - Pupil changes more pronounced than real.
    """
    dilation: float = 0.0  # -1 (constricted) to +1 (dilated)
    transition_speed: float = 0.3  # Dilation change per second

    # Internal state
    _current_dilation: float = 0.0

    def set_emotion_params(self, params: EmotionMicroParams) -> None:
        """Update target dilation from emotion."""
        self.dilation = params.pupil_dilation

    def update(self, delta_ms: float) -> None:
        """
        Update pupil dilation state.

        Args:
            delta_ms: Milliseconds since last update
        """
        # Smooth transition toward target dilation
        delta_s = delta_ms / 1000.0
        max_change = self.transition_speed * delta_s

        diff = self.dilation - self._current_dilation
        if abs(diff) <= max_change:
            self._current_dilation = self.dilation
        else:
            self._current_dilation += max_change if diff > 0 else -max_change

    def get_per_pixel_modifiers(self, num_leds: int = NUM_LEDS) -> List[float]:
        """
        Get per-LED brightness modifiers for pupil effect.

        Center LEDs are modified based on dilation level.

        Args:
            num_leds: Number of LEDs in ring

        Returns:
            List of brightness multipliers per LED
        """
        modifiers = [1.0] * num_leds

        if abs(self._current_dilation) < 0.01:
            return modifiers

        # Center LED indices (for 16-LED ring)
        # These represent the "pupil" area
        center_indices = CENTER_LED_INDICES if num_leds >= 16 else [num_leds // 2]

        # Calculate modifier for center
        if self._current_dilation > 0:
            # Dilated: center brighter
            center_mod = 1.0 + (self._current_dilation * PUPIL_DILATION_MAX)
        else:
            # Constricted: center dimmer
            center_mod = 1.0 + (self._current_dilation * PUPIL_CONSTRICTION_MAX)

        # Apply with falloff from center
        for i in range(num_leds):
            if i in center_indices:
                modifiers[i] = center_mod
            else:
                # Gradual falloff from center
                # Find distance to nearest center LED
                min_dist = min(abs(i - c) for c in center_indices)
                min_dist = min(min_dist, num_leds - min_dist)  # Handle ring wrap

                # Falloff over 2-3 LEDs
                falloff = max(0.0, 1.0 - min_dist / 3.0)
                modifiers[i] = 1.0 + (center_mod - 1.0) * falloff

        return modifiers

    def get_dilation(self) -> float:
        """Get current dilation level (-1 to +1)."""
        return self._current_dilation


# ============================================================================
# MICRO-TREMOR SYSTEM
# ============================================================================

@dataclass
class TremorController:
    """
    Adds tiny random brightness variations to prevent "dead" appearance.

    Physiological tremor in humans occurs at ~8Hz with very small amplitude.
    For LED eyes, this creates subtle "aliveness" without being distracting.

    Disney Principle: Secondary Action - Tremor adds life without
    competing with main expression.
    """
    amplitude: float = 0.03  # 3% default variation
    frequency_hz: float = TREMOR_FREQUENCY_HZ

    # Internal state
    _phases: List[float] = field(default_factory=list)
    _rng: random.Random = field(default_factory=random.Random)

    def __post_init__(self):
        """Initialize per-LED random phases."""
        self._phases = [self._rng.uniform(0, 2 * math.pi) for _ in range(NUM_LEDS)]

    def set_emotion_params(self, params: EmotionMicroParams) -> None:
        """Update tremor amplitude from emotion."""
        self.amplitude = TREMOR_AMPLITUDE_MIN + (
            params.tremor_amplitude * (TREMOR_AMPLITUDE_MAX - TREMOR_AMPLITUDE_MIN)
        )

    def update(self, delta_ms: float) -> None:
        """Update tremor phases."""
        phase_increment = 2 * math.pi * self.frequency_hz * delta_ms / 1000.0

        for i in range(len(self._phases)):
            self._phases[i] += phase_increment
            if self._phases[i] > 2 * math.pi:
                self._phases[i] -= 2 * math.pi

    def get_per_pixel_modifiers(self, num_leds: int = NUM_LEDS) -> List[float]:
        """
        Get per-LED brightness modifiers for tremor effect.

        Args:
            num_leds: Number of LEDs in ring

        Returns:
            List of brightness multipliers per LED
        """
        modifiers = []
        for i in range(num_leds):
            phase = self._phases[i] if i < len(self._phases) else 0
            # Use multiple sine waves for more natural tremor
            tremor = (
                math.sin(phase) * 0.6 +
                math.sin(phase * 2.3 + 1.0) * 0.3 +
                math.sin(phase * 0.7 + 2.0) * 0.1
            )
            modifiers.append(1.0 + tremor * self.amplitude)
        return modifiers

    def seed_rng(self, seed: int) -> None:
        """Seed RNG and reinitialize phases."""
        self._rng.seed(seed)
        self._phases = [self._rng.uniform(0, 2 * math.pi) for _ in range(NUM_LEDS)]


# ============================================================================
# ENHANCED MICRO-EXPRESSION ENGINE
# ============================================================================

class EnhancedMicroExpressionEngine:
    """
    Unified micro-expression engine combining all subsystems.

    Integrates:
    1. BlinkController - Natural blinking with emotional modulation
    2. BreathingController - Subtle breathing overlay
    3. SaccadeController - Eye dart movements
    4. PupilController - Pupil dilation simulation
    5. TremorController - Micro-tremor for liveliness

    All systems layer ON TOP of base emotion patterns.
    Total processing time budget: <0.5ms per frame.

    Thread Safety Warning:
        NOT THREAD-SAFE. All methods must be called from single thread.

    Usage:
        >>> engine = EnhancedMicroExpressionEngine()
        >>> engine.set_emotion("happy")
        >>> engine.update(20.0)  # 20ms delta
        >>> global_mod = engine.get_brightness_modifier()
        >>> per_pixel = engine.get_per_pixel_modifiers()
    """

    def __init__(self, num_leds: int = NUM_LEDS):
        """
        Initialize enhanced micro-expression engine.

        Args:
            num_leds: Number of LEDs per eye ring
        """
        if num_leds <= 0:
            raise ValueError("num_leds must be positive")

        self.num_leds = num_leds

        # Subsystem controllers
        self.blink = BlinkController()
        self.breathing = BreathingController()
        self.saccade = SaccadeController()
        self.pupil = PupilController()
        self.tremor = TremorController()

        # Current emotion
        self._current_emotion: str = "idle"

        # Cached modifiers (updated each frame)
        self._global_modifier: float = 1.0
        self._per_pixel_modifiers: List[float] = [1.0] * num_leds

        # Performance tracking
        self._last_update_time_ms: float = 0.0

        # Apply initial emotion
        self._apply_emotion_params()

    def set_emotion(self, emotion: str) -> None:
        """
        Set current emotion for micro-expression modulation.

        Args:
            emotion: Emotion name (must exist in EMOTION_MICRO_PARAMS)
        """
        emotion_lower = emotion.lower()
        if emotion_lower in EMOTION_MICRO_PARAMS:
            self._current_emotion = emotion_lower
            self._apply_emotion_params()
        else:
            # Fall back to idle for unknown emotions
            self._current_emotion = "idle"
            self._apply_emotion_params()

    def _apply_emotion_params(self) -> None:
        """Apply emotion parameters to all subsystems."""
        params = EMOTION_MICRO_PARAMS.get(self._current_emotion, EMOTION_MICRO_PARAMS["idle"])

        self.blink.set_emotion_params(params)
        self.breathing.set_emotion_params(params)
        self.saccade.set_emotion_params(params)
        self.pupil.set_emotion_params(params)
        self.tremor.set_emotion_params(params)

    def update(self, delta_ms: float) -> None:
        """
        Update all micro-expression subsystems.

        MUST be called every frame for smooth animation.

        Args:
            delta_ms: Milliseconds since last update

        Performance:
            Target <0.5ms execution time
        """
        start_time = time.perf_counter()

        # Update all subsystems
        self.blink.update(delta_ms)
        breathing_mod = self.breathing.update(delta_ms)
        self.saccade.update(delta_ms)
        self.pupil.update(delta_ms)
        self.tremor.update(delta_ms)

        # Compute combined modifiers
        self._compute_combined_modifiers(breathing_mod)

        # Track performance
        end_time = time.perf_counter()
        self._last_update_time_ms = (end_time - start_time) * 1000

    def _compute_combined_modifiers(self, breathing_mod: float) -> None:
        """
        Combine all subsystem modifiers into final values.

        Modifiers are MULTIPLIED together for natural layering.
        """
        # Global modifier: blink * breathing
        blink_mod = self.blink.get_brightness_modifier()
        self._global_modifier = blink_mod * breathing_mod

        # Per-pixel modifiers: saccade * pupil * tremor
        saccade_mods = self.saccade.get_per_pixel_modifiers(self.num_leds)
        pupil_mods = self.pupil.get_per_pixel_modifiers(self.num_leds)
        tremor_mods = self.tremor.get_per_pixel_modifiers(self.num_leds)

        for i in range(self.num_leds):
            self._per_pixel_modifiers[i] = (
                saccade_mods[i] * pupil_mods[i] * tremor_mods[i]
            )

    def get_brightness_modifier(self) -> float:
        """
        Get global brightness modifier.

        Apply to ALL pixels: final_brightness = base * modifier

        Returns:
            Brightness multiplier (typically 0.1-1.3)
        """
        return self._global_modifier

    def get_per_pixel_modifiers(self) -> List[float]:
        """
        Get per-pixel brightness modifiers.

        Apply AFTER global modifier for full effect:
            final[i] = base[i] * global_mod * per_pixel[i]

        Returns:
            List of multipliers, one per LED
        """
        return self._per_pixel_modifiers.copy()

    def apply_to_pixels(self, pixels: List[RGB]) -> List[RGB]:
        """
        Convenience method: Apply all modifiers to pixel list.

        Args:
            pixels: List of RGB tuples to modify

        Returns:
            Modified pixel list with micro-expressions applied
        """
        if len(pixels) != self.num_leds:
            raise ValueError(f"Expected {self.num_leds} pixels, got {len(pixels)}")

        result = []
        global_mod = self._global_modifier

        for i, (r, g, b) in enumerate(pixels):
            combined_mod = global_mod * self._per_pixel_modifiers[i]
            result.append((
                max(0, min(255, int(r * combined_mod))),
                max(0, min(255, int(g * combined_mod))),
                max(0, min(255, int(b * combined_mod))),
            ))

        return result

    def force_blink(self, duration_ms: Optional[int] = None) -> None:
        """Force an immediate blink."""
        self.blink.force_blink(duration_ms)

    def is_blinking(self) -> bool:
        """Check if currently blinking."""
        return self.blink.is_blinking()

    def get_last_update_time_ms(self) -> float:
        """Get execution time of last update in milliseconds."""
        return self._last_update_time_ms

    def reset(self) -> None:
        """Reset all subsystems to initial state."""
        self.blink = BlinkController()
        self.breathing = BreathingController()
        self.saccade = SaccadeController()
        self.pupil = PupilController()
        self.tremor = TremorController()
        self._current_emotion = "idle"
        self._global_modifier = 1.0
        self._per_pixel_modifiers = [1.0] * self.num_leds
        self._apply_emotion_params()

    def seed_all_rng(self, seed: int) -> None:
        """Seed all RNGs for reproducible tests."""
        self.blink.seed_rng(seed)
        self.saccade.seed_rng(seed + 1)
        self.tremor.seed_rng(seed + 2)

    def get_debug_state(self) -> Dict[str, any]:
        """Get detailed state for debugging."""
        return {
            "emotion": self._current_emotion,
            "global_modifier": self._global_modifier,
            "blink_state": self.blink._blink_state.value,
            "blink_modifier": self.blink.get_brightness_modifier(),
            "breathing_phase": self.breathing.get_phase(),
            "saccade_active": self.saccade.is_active(),
            "saccade_direction": self.saccade.get_direction().value,
            "pupil_dilation": self.pupil.get_dilation(),
            "last_update_ms": self._last_update_time_ms,
        }


# ============================================================================
# INTEGRATION HELPERS
# ============================================================================

def create_micro_expression_engine(num_leds: int = NUM_LEDS) -> EnhancedMicroExpressionEngine:
    """
    Factory function to create a configured micro-expression engine.

    Args:
        num_leds: LEDs per ring

    Returns:
        Configured EnhancedMicroExpressionEngine instance
    """
    return EnhancedMicroExpressionEngine(num_leds)


def get_available_emotions() -> List[str]:
    """
    Get list of emotions with micro-expression parameters.

    Returns:
        List of emotion names that have micro-expression configs
    """
    return list(EMOTION_MICRO_PARAMS.keys())


def get_emotion_params(emotion: str) -> Optional[EmotionMicroParams]:
    """
    Get micro-expression parameters for an emotion.

    Args:
        emotion: Emotion name

    Returns:
        EmotionMicroParams or None if not found
    """
    return EMOTION_MICRO_PARAMS.get(emotion.lower())
