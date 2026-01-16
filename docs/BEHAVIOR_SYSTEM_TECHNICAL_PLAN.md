# Behavior System Technical Plan - Week 02
## OpenDuck Mini V3 - Emotion & Personality Implementation

**Version:** 1.0
**Created:** 22 January 2026
**Author:** Research Engineer - Applied Robotics (Google DeepMind)
**Status:** READY FOR IMPLEMENTATION

---

## Executive Summary

This document provides a comprehensive technical implementation plan for the OpenDuck Mini V3 behavior system. The goal is to create a robot that **feels alive** through subtle LED expressions and simulated head movement, applying Disney/Pixar animation principles to embedded robotics.

### Key Deliverables
1. EmotionManager class with 8 emotion states
2. IdleBehavior async implementation with Disney-style micro-animations
3. Behavior tree architecture for state management
4. Emotion triggers from sensor input (IMU, voice, system events)
5. Smooth HSV-based color transitions
6. Mock head movement (prepared for servo integration)
7. Comprehensive test suite (target: 150+ tests)

---

## Part 1: Architecture Overview

### System Layers

```
┌─────────────────────────────────────────────────────────────────┐
│                    APPLICATION LAYER                             │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │               BehaviorCoordinator                        │    │
│  │  - Orchestrates emotions, idle behaviors, head movement  │    │
│  │  - Handles sensor-to-emotion mapping                     │    │
│  └──────────────────────┬──────────────────────────────────┘    │
│                         │                                        │
│  ┌──────────────────────┼──────────────────────────────────┐    │
│  │                      │                                   │    │
│  ▼                      ▼                                   ▼    │
│ ┌────────────┐  ┌───────────────┐  ┌────────────────────┐       │
│ │ Emotion    │  │ Idle          │  │ Head               │       │
│ │ Manager    │  │ Behavior      │  │ Controller         │       │
│ │            │  │ Engine        │  │ (Mock → Real)      │       │
│ └─────┬──────┘  └───────┬───────┘  └─────────┬──────────┘       │
│       │                 │                     │                  │
└───────┼─────────────────┼─────────────────────┼──────────────────┘
        │                 │                     │
┌───────┼─────────────────┼─────────────────────┼──────────────────┐
│       │     ANIMATION LAYER                   │                  │
│  ┌────▼─────────────────▼─────────────────────▼────────────┐    │
│  │                  AnimationEngine                         │    │
│  │  - 50Hz render loop                                      │    │
│  │  - Pattern compositing                                   │    │
│  │  - Easing functions (Disney slow-in/slow-out)           │    │
│  └──────────────────────┬──────────────────────────────────┘    │
│                         │                                        │
│  ┌──────────────────────┼──────────────────────────────────┐    │
│  │                      │                                   │    │
│  ▼                      ▼                                   ▼    │
│ ┌────────────┐  ┌───────────────┐  ┌────────────────────┐       │
│ │ Pattern    │  │ Color         │  │ Transition         │       │
│ │ Library    │  │ Manager       │  │ Controller         │       │
│ │ (5 types)  │  │ (HSV-based)   │  │ (with anticipation)│       │
│ └────────────┘  └───────────────┘  └────────────────────┘       │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
        │
┌───────┼──────────────────────────────────────────────────────────┐
│       │             HARDWARE ABSTRACTION LAYER                   │
│  ┌────▼─────────────────────────────────────────────────────┐    │
│  │                  LEDController                            │    │
│  │  - WS2812B driver wrapper                                 │    │
│  │  - Pixel buffer management                                │    │
│  │  - Power-safe brightness limiting                         │    │
│  └──────────────────────────────────────────────────────────┘    │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

### Thread Model

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   Main Thread   │     │ Animation Thread│     │  Sensor Thread  │
│                 │     │                 │     │                 │
│ - State machine │     │ - 50Hz render   │     │ - IMU polling   │
│ - User commands │────▶│ - Pattern calc  │     │ - Voice detect  │
│ - Event dispatch│     │ - LED writes    │◀────│ - Touch sense   │
│                 │     │                 │     │                 │
└────────┬────────┘     └────────┬────────┘     └────────┬────────┘
         │                       │                       │
         │                       │                       │
         ▼                       ▼                       ▼
    ┌────────────────────────────────────────────────────────┐
    │              Thread-Safe Event Queue                    │
    │  - Emotion change requests                              │
    │  - Sensor events (movement detected, voice heard)       │
    │  - System events (low battery, error states)            │
    └────────────────────────────────────────────────────────┘
```

---

## Part 2: EmotionManager Class Design

### Class Definition

```python
# src/behavior/emotion_manager.py

"""
EmotionManager - Disney-Quality Emotion State Machine

Design Philosophy:
    - Emotions are states, not animations
    - Transitions follow Disney's anticipation principle
    - Every emotion has a "heartbeat" (base pattern)
    - Intensity modulates all parameters
"""

from enum import Enum, auto
from dataclasses import dataclass, field
from typing import Optional, Callable, List, Dict, Tuple
import asyncio
import time
import threading
import math
import logging

_logger = logging.getLogger(__name__)


class EmotionState(Enum):
    """Primary emotion states with unique characteristics."""
    IDLE = auto()       # Default resting state
    HAPPY = auto()      # Positive, warm, energetic
    CURIOUS = auto()    # Interested, engaged, questioning
    ALERT = auto()      # Attention-seeking, important notification
    SAD = auto()        # Low energy, seeking comfort
    SLEEPY = auto()     # Low energy, preparing for sleep
    EXCITED = auto()    # High energy, anticipation
    THINKING = auto()   # Processing, computing


@dataclass(frozen=True)
class EmotionConfig:
    """Immutable configuration for each emotion state.

    Based on Disney 12 principles and color psychology research.
    """
    # Color (RGB tuple, warm-shifted for appeal)
    color: Tuple[int, int, int]

    # Timing (milliseconds)
    transition_in_ms: int       # Time to enter this emotion
    transition_out_ms: int      # Time to exit this emotion
    pattern_speed: float        # Animation speed multiplier (1.0 = normal)

    # Brightness modulation
    min_brightness: float       # Minimum brightness (0-1)
    max_brightness: float       # Maximum brightness (0-1)

    # Pattern type
    pattern: str               # breathing, pulse, spin, sparkle, fade

    # Disney principles
    exaggeration: float        # Brightness multiplier for emphasis
    anticipation_ms: int       # Anticipation duration before transition
    follow_through_ms: int     # Settle time after transition

    # Head pose (pan, tilt in degrees) - for when servos arrive
    head_pose: Tuple[float, float] = (90.0, 90.0)


# Emotion configurations based on LED_ANIMATION_SYSTEM_DESIGN.md
EMOTION_CONFIGS: Dict[EmotionState, EmotionConfig] = {
    EmotionState.IDLE: EmotionConfig(
        color=(100, 150, 255),        # Soft blue - calm, neutral
        transition_in_ms=800,
        transition_out_ms=400,
        pattern_speed=0.5,
        min_brightness=0.3,
        max_brightness=1.0,
        pattern="breathing",
        exaggeration=1.0,
        anticipation_ms=100,
        follow_through_ms=200,
        head_pose=(90.0, 90.0),       # Center
    ),

    EmotionState.HAPPY: EmotionConfig(
        color=(255, 220, 50),         # Warm yellow - joy, warmth
        transition_in_ms=400,
        transition_out_ms=600,
        pattern_speed=1.2,
        min_brightness=0.5,
        max_brightness=1.0,
        pattern="sparkle",
        exaggeration=1.3,             # 30% brighter
        anticipation_ms=80,
        follow_through_ms=150,
        head_pose=(90.0, 80.0),       # Slight upward tilt
    ),

    EmotionState.CURIOUS: EmotionConfig(
        color=(150, 255, 150),        # Soft green - interest, growth
        transition_in_ms=300,
        transition_out_ms=400,
        pattern_speed=1.0,
        min_brightness=0.4,
        max_brightness=0.9,
        pattern="breathing",
        exaggeration=1.1,
        anticipation_ms=50,
        follow_through_ms=100,
        head_pose=(70.0, 85.0),       # Head tilt (curious look)
    ),

    EmotionState.ALERT: EmotionConfig(
        color=(255, 100, 100),        # Warm red - attention (NOT aggressive)
        transition_in_ms=150,         # Fast transition - urgency
        transition_out_ms=300,
        pattern_speed=2.0,
        min_brightness=0.4,
        max_brightness=1.0,
        pattern="pulse",
        exaggeration=1.4,
        anticipation_ms=30,           # Minimal anticipation - immediate
        follow_through_ms=100,
        head_pose=(90.0, 90.0),       # Straight ahead - focused
    ),

    EmotionState.SAD: EmotionConfig(
        color=(100, 100, 200),        # Muted blue - melancholy
        transition_in_ms=1200,        # Slow transition - reluctant
        transition_out_ms=800,
        pattern_speed=0.3,
        min_brightness=0.2,
        max_brightness=0.6,
        pattern="fade",
        exaggeration=0.6,             # 40% dimmer
        anticipation_ms=200,
        follow_through_ms=400,
        head_pose=(90.0, 110.0),      # Looking down
    ),

    EmotionState.SLEEPY: EmotionConfig(
        color=(150, 130, 200),        # Lavender - drowsy, calm
        transition_in_ms=1500,        # Very slow - drifting off
        transition_out_ms=1000,
        pattern_speed=0.2,
        min_brightness=0.1,
        max_brightness=0.4,
        pattern="fade",
        exaggeration=0.4,             # Very dim
        anticipation_ms=300,
        follow_through_ms=500,
        head_pose=(90.0, 100.0),      # Slight droop
    ),

    EmotionState.EXCITED: EmotionConfig(
        color=(255, 150, 50),         # Orange - energy, enthusiasm
        transition_in_ms=200,
        transition_out_ms=400,
        pattern_speed=1.8,
        min_brightness=0.6,
        max_brightness=1.0,
        pattern="sparkle",
        exaggeration=1.5,             # 50% more intense
        anticipation_ms=50,
        follow_through_ms=100,
        head_pose=(90.0, 75.0),       # Upward - eager
    ),

    EmotionState.THINKING: EmotionConfig(
        color=(200, 200, 255),        # White-blue - processing
        transition_in_ms=500,
        transition_out_ms=400,
        pattern_speed=0.8,
        min_brightness=0.4,
        max_brightness=0.8,
        pattern="spin",               # Rotating indicator
        exaggeration=1.0,
        anticipation_ms=100,
        follow_through_ms=150,
        head_pose=(85.0, 95.0),       # Slight tilt - pondering
    ),
}


# Valid state transitions (Finite State Machine)
VALID_TRANSITIONS: Dict[EmotionState, List[EmotionState]] = {
    EmotionState.IDLE: [
        EmotionState.HAPPY, EmotionState.CURIOUS,
        EmotionState.ALERT, EmotionState.SLEEPY,
        EmotionState.THINKING
    ],
    EmotionState.HAPPY: [
        EmotionState.IDLE, EmotionState.EXCITED,
        EmotionState.CURIOUS
    ],
    EmotionState.CURIOUS: [
        EmotionState.IDLE, EmotionState.HAPPY,
        EmotionState.ALERT, EmotionState.THINKING
    ],
    EmotionState.ALERT: [
        EmotionState.IDLE, EmotionState.CURIOUS,
        EmotionState.SAD
    ],
    EmotionState.EXCITED: [
        EmotionState.HAPPY, EmotionState.IDLE
    ],
    EmotionState.THINKING: [
        EmotionState.CURIOUS, EmotionState.IDLE,
        EmotionState.HAPPY  # Eureka moment!
    ],
    EmotionState.SAD: [
        EmotionState.IDLE, EmotionState.SLEEPY
    ],
    EmotionState.SLEEPY: [
        EmotionState.IDLE, EmotionState.SAD
    ],
}


@dataclass
class TransitionState:
    """Tracks in-progress emotion transition."""
    from_emotion: EmotionState
    to_emotion: EmotionState
    start_time: float
    duration_ms: int
    phase: str  # "anticipation", "main", "follow_through"
    progress: float = 0.0


class EmotionManager:
    """Manages emotion state machine with Disney-quality transitions.

    Thread Safety:
        All public methods are thread-safe. Internal state protected by RLock.

    Usage:
        >>> manager = EmotionManager(led_controller)
        >>> manager.start()
        >>> manager.set_emotion(EmotionState.HAPPY)
        >>> # ... later
        >>> manager.stop()
    """

    # Animation update rate
    UPDATE_HZ: int = 50
    UPDATE_PERIOD_S: float = 1.0 / UPDATE_HZ

    def __init__(
        self,
        led_controller: Optional['LEDController'] = None,
        head_controller: Optional['HeadController'] = None,
        initial_emotion: EmotionState = EmotionState.IDLE,
    ):
        """Initialize EmotionManager.

        Args:
            led_controller: LED controller for visual output.
            head_controller: Head servo controller (can be None/mock).
            initial_emotion: Starting emotion state.
        """
        self._led = led_controller
        self._head = head_controller

        # State machine
        self._lock = threading.RLock()
        self._current_emotion = initial_emotion
        self._target_emotion: Optional[EmotionState] = None
        self._transition: Optional[TransitionState] = None
        self._intensity: float = 1.0  # 0.0-1.0, modulates all parameters

        # Animation state
        self._running = False
        self._animation_thread: Optional[threading.Thread] = None
        self._frame_count: int = 0

        # Event callbacks
        self._on_emotion_change: List[Callable[[EmotionState, EmotionState], None]] = []
        self._on_transition_complete: List[Callable[[EmotionState], None]] = []

        # Performance metrics
        self._last_frame_time: float = 0.0
        self._frame_times: List[float] = []

        _logger.debug("EmotionManager initialized: initial=%s", initial_emotion.name)

    # =========================================================================
    # Properties
    # =========================================================================

    @property
    def current_emotion(self) -> EmotionState:
        """Get current emotion state."""
        with self._lock:
            return self._current_emotion

    @property
    def is_transitioning(self) -> bool:
        """Check if currently transitioning between emotions."""
        with self._lock:
            return self._transition is not None

    @property
    def intensity(self) -> float:
        """Get current intensity level (0.0-1.0)."""
        with self._lock:
            return self._intensity

    @intensity.setter
    def intensity(self, value: float) -> None:
        """Set intensity level (clamped to 0.0-1.0)."""
        with self._lock:
            self._intensity = max(0.0, min(1.0, value))

    @property
    def config(self) -> EmotionConfig:
        """Get current emotion configuration."""
        with self._lock:
            return EMOTION_CONFIGS[self._current_emotion]

    # =========================================================================
    # Lifecycle Methods
    # =========================================================================

    def start(self) -> bool:
        """Start emotion animation loop.

        Returns:
            True if started successfully.
        """
        with self._lock:
            if self._running:
                _logger.warning("EmotionManager already running")
                return False

            self._running = True
            self._animation_thread = threading.Thread(
                target=self._animation_loop,
                name="EmotionAnimation",
                daemon=True,
            )
            self._animation_thread.start()

            _logger.info("EmotionManager started")
            return True

    def stop(self) -> None:
        """Stop emotion animation loop."""
        with self._lock:
            self._running = False

        if self._animation_thread is not None:
            self._animation_thread.join(timeout=1.0)
            self._animation_thread = None

        _logger.info("EmotionManager stopped")

    # =========================================================================
    # Emotion Control
    # =========================================================================

    def set_emotion(
        self,
        emotion: EmotionState,
        force: bool = False,
        immediate: bool = False,
    ) -> bool:
        """Request emotion state change.

        Args:
            emotion: Target emotion state.
            force: If True, allow invalid transitions.
            immediate: If True, skip anticipation phase.

        Returns:
            True if transition started, False if blocked.
        """
        with self._lock:
            # Already in target state
            if emotion == self._current_emotion and self._transition is None:
                return True

            # Validate transition
            if not force:
                if emotion not in VALID_TRANSITIONS.get(self._current_emotion, []):
                    _logger.warning(
                        "Invalid transition: %s -> %s",
                        self._current_emotion.name, emotion.name
                    )
                    return False

            # Cancel any in-progress transition
            if self._transition is not None:
                _logger.debug("Cancelling in-progress transition")

            # Get target config
            target_config = EMOTION_CONFIGS[emotion]

            # Start new transition
            self._target_emotion = emotion
            self._transition = TransitionState(
                from_emotion=self._current_emotion,
                to_emotion=emotion,
                start_time=time.monotonic(),
                duration_ms=target_config.transition_in_ms,
                phase="anticipation" if not immediate else "main",
            )

            _logger.info(
                "Emotion transition: %s -> %s (duration=%dms)",
                self._current_emotion.name, emotion.name, target_config.transition_in_ms
            )

            # Notify callbacks
            for callback in self._on_emotion_change:
                try:
                    callback(self._current_emotion, emotion)
                except Exception as e:
                    _logger.error("Emotion change callback error: %s", e)

            return True

    def get_blended_color(self) -> Tuple[int, int, int]:
        """Get current color, blended during transitions.

        Returns:
            RGB tuple of current display color.
        """
        with self._lock:
            if self._transition is None:
                config = EMOTION_CONFIGS[self._current_emotion]
                return config.color

            # Blend between source and target colors
            from_config = EMOTION_CONFIGS[self._transition.from_emotion]
            to_config = EMOTION_CONFIGS[self._transition.to_emotion]

            # Use HSV interpolation for smoother color arcs
            return self._blend_colors_hsv(
                from_config.color,
                to_config.color,
                self._transition.progress,
            )

    def _blend_colors_hsv(
        self,
        color1: Tuple[int, int, int],
        color2: Tuple[int, int, int],
        progress: float,
    ) -> Tuple[int, int, int]:
        """Blend two colors through HSV color space.

        Disney principle #7 (Arc): Colors transition through the color
        wheel rather than directly through RGB space.
        """
        # Convert RGB to HSV
        h1, s1, v1 = self._rgb_to_hsv(color1)
        h2, s2, v2 = self._rgb_to_hsv(color2)

        # Interpolate hue (circular)
        h = self._interpolate_circular(h1, h2, progress)
        s = s1 + (s2 - s1) * progress
        v = v1 + (v2 - v1) * progress

        # Convert back to RGB
        return self._hsv_to_rgb((h, s, v))

    @staticmethod
    def _rgb_to_hsv(rgb: Tuple[int, int, int]) -> Tuple[float, float, float]:
        """Convert RGB (0-255) to HSV (0-1)."""
        r, g, b = rgb[0] / 255.0, rgb[1] / 255.0, rgb[2] / 255.0
        mx = max(r, g, b)
        mn = min(r, g, b)
        diff = mx - mn

        # Hue calculation
        if mx == mn:
            h = 0.0
        elif mx == r:
            h = (60 * ((g - b) / diff) + 360) % 360
        elif mx == g:
            h = (60 * ((b - r) / diff) + 120) % 360
        else:
            h = (60 * ((r - g) / diff) + 240) % 360

        h /= 360.0  # Normalize to 0-1
        s = 0 if mx == 0 else diff / mx
        v = mx

        return (h, s, v)

    @staticmethod
    def _hsv_to_rgb(hsv: Tuple[float, float, float]) -> Tuple[int, int, int]:
        """Convert HSV (0-1) to RGB (0-255)."""
        h, s, v = hsv
        h *= 360.0

        c = v * s
        x = c * (1 - abs((h / 60) % 2 - 1))
        m = v - c

        if 0 <= h < 60:
            r, g, b = c, x, 0
        elif 60 <= h < 120:
            r, g, b = x, c, 0
        elif 120 <= h < 180:
            r, g, b = 0, c, x
        elif 180 <= h < 240:
            r, g, b = 0, x, c
        elif 240 <= h < 300:
            r, g, b = x, 0, c
        else:
            r, g, b = c, 0, x

        return (
            int((r + m) * 255),
            int((g + m) * 255),
            int((b + m) * 255),
        )

    @staticmethod
    def _interpolate_circular(a: float, b: float, t: float) -> float:
        """Interpolate between two values on a circle (0-1 range)."""
        diff = b - a

        # Take the shorter path around the circle
        if diff > 0.5:
            diff -= 1.0
        elif diff < -0.5:
            diff += 1.0

        result = a + diff * t
        return result % 1.0

    # =========================================================================
    # Animation Loop
    # =========================================================================

    def _animation_loop(self) -> None:
        """Main animation loop (runs in separate thread)."""
        _logger.debug("Animation loop started")

        while self._running:
            frame_start = time.monotonic()

            try:
                self._update_frame()
            except Exception as e:
                _logger.error("Animation frame error: %s", e)

            # Maintain target frame rate
            elapsed = time.monotonic() - frame_start
            sleep_time = self.UPDATE_PERIOD_S - elapsed

            if sleep_time > 0:
                time.sleep(sleep_time)

            # Track frame time
            self._last_frame_time = time.monotonic() - frame_start
            self._frame_times.append(self._last_frame_time)
            if len(self._frame_times) > 100:
                self._frame_times.pop(0)

            self._frame_count += 1

        _logger.debug("Animation loop stopped")

    def _update_frame(self) -> None:
        """Update single animation frame."""
        with self._lock:
            # Update transition progress
            if self._transition is not None:
                self._update_transition()

            # Get current config and color
            config = self.config
            color = self.get_blended_color()

            # Calculate pattern output
            pattern_output = self._calculate_pattern(config)

            # Apply to LED controller
            if self._led is not None:
                self._led.set_all_pixels(
                    color,
                    brightness=pattern_output * config.exaggeration * self._intensity,
                )

            # Update head position (if controller available)
            if self._head is not None:
                pan, tilt = config.head_pose
                self._head.set_position(pan, tilt)

    def _update_transition(self) -> None:
        """Update transition state and progress."""
        if self._transition is None:
            return

        elapsed_ms = (time.monotonic() - self._transition.start_time) * 1000
        from_config = EMOTION_CONFIGS[self._transition.from_emotion]
        to_config = EMOTION_CONFIGS[self._transition.to_emotion]

        # Phase state machine: anticipation -> main -> follow_through -> complete
        if self._transition.phase == "anticipation":
            anticipation_ms = to_config.anticipation_ms
            if elapsed_ms >= anticipation_ms:
                self._transition.phase = "main"
                self._transition.start_time = time.monotonic()
                elapsed_ms = 0
            else:
                # Anticipation: slight dim before transition
                self._transition.progress = 0.0
                return

        if self._transition.phase == "main":
            main_duration = self._transition.duration_ms
            if elapsed_ms >= main_duration:
                self._transition.phase = "follow_through"
                self._transition.start_time = time.monotonic()
                self._transition.progress = 1.0
                self._current_emotion = self._transition.to_emotion
            else:
                # Apply easing (Disney slow-in/slow-out)
                linear_progress = elapsed_ms / main_duration
                self._transition.progress = self._ease_in_out(linear_progress)
                return

        if self._transition.phase == "follow_through":
            follow_through_ms = to_config.follow_through_ms
            if elapsed_ms >= follow_through_ms:
                # Transition complete
                self._transition = None
                self._target_emotion = None

                # Notify callbacks
                for callback in self._on_transition_complete:
                    try:
                        callback(self._current_emotion)
                    except Exception as e:
                        _logger.error("Transition complete callback error: %s", e)

    @staticmethod
    def _ease_in_out(t: float) -> float:
        """Disney-style ease-in-out function.

        More frames at start and end of movement (principle #6).
        """
        if t < 0.5:
            return 2 * t * t
        else:
            return 1 - ((-2 * t + 2) ** 2) / 2

    def _calculate_pattern(self, config: EmotionConfig) -> float:
        """Calculate pattern brightness for current frame.

        Returns:
            Brightness value 0.0-1.0.
        """
        t = self._frame_count / self.UPDATE_HZ  # Time in seconds
        speed = config.pattern_speed

        if config.pattern == "breathing":
            # Smooth sine wave (Disney principle: never static)
            cycle = math.sin(t * speed * math.pi * 0.5) * 0.5 + 0.5
            return config.min_brightness + cycle * (config.max_brightness - config.min_brightness)

        elif config.pattern == "pulse":
            # Heartbeat pattern (double-pulse)
            cycle_pos = (t * speed) % 1.0
            if cycle_pos < 0.1:
                return config.max_brightness * math.sin(cycle_pos / 0.1 * math.pi)
            elif cycle_pos < 0.2:
                return config.min_brightness
            elif cycle_pos < 0.3:
                return config.max_brightness * 0.7 * math.sin((cycle_pos - 0.2) / 0.1 * math.pi)
            else:
                return config.min_brightness

        elif config.pattern == "spin":
            # Will be implemented with per-pixel control
            # For now, return breathing fallback
            cycle = math.sin(t * speed * math.pi * 0.5) * 0.5 + 0.5
            return config.min_brightness + cycle * (config.max_brightness - config.min_brightness)

        elif config.pattern == "sparkle":
            # Base brightness with random variation (per-frame)
            base = config.min_brightness + 0.3 * (config.max_brightness - config.min_brightness)
            # Note: Full sparkle needs per-pixel random - simplified here
            return base

        elif config.pattern == "fade":
            # Slow continuous dim (for sad/sleepy)
            return config.min_brightness + 0.1 * math.sin(t * speed * 0.5)

        else:
            return config.min_brightness

    # =========================================================================
    # Callbacks
    # =========================================================================

    def on_emotion_change(self, callback: Callable[[EmotionState, EmotionState], None]) -> None:
        """Register callback for emotion change events.

        Args:
            callback: Function called with (from_emotion, to_emotion).
        """
        self._on_emotion_change.append(callback)

    def on_transition_complete(self, callback: Callable[[EmotionState], None]) -> None:
        """Register callback for transition completion.

        Args:
            callback: Function called with new emotion state.
        """
        self._on_transition_complete.append(callback)

    # =========================================================================
    # Diagnostics
    # =========================================================================

    def get_diagnostics(self) -> Dict[str, any]:
        """Get diagnostic information."""
        with self._lock:
            avg_frame_time = (
                sum(self._frame_times) / len(self._frame_times)
                if self._frame_times else 0.0
            )

            return {
                "current_emotion": self._current_emotion.name,
                "target_emotion": self._target_emotion.name if self._target_emotion else None,
                "is_transitioning": self._transition is not None,
                "transition_phase": self._transition.phase if self._transition else None,
                "transition_progress": self._transition.progress if self._transition else 0.0,
                "intensity": self._intensity,
                "frame_count": self._frame_count,
                "avg_frame_time_ms": avg_frame_time * 1000,
                "target_frame_time_ms": self.UPDATE_PERIOD_S * 1000,
                "running": self._running,
            }
```

---

## Part 3: IdleBehavior Async Implementation

### Design Philosophy

The IdleBehavior system makes the robot feel **alive** even when no explicit actions are occurring. Drawing from Disney/Pixar principles:

1. **Never truly static** - Always subtle movement
2. **Micro-expressions** - Small blinks, glances, weight shifts
3. **Variation** - Randomized timing to avoid mechanical feel
4. **Anticipation** - Brief preparation before larger movements

### Class Definition

```python
# src/behavior/idle_behavior.py

"""
IdleBehavior - Disney-Quality Idle Animations

"The illusion of life is not about complexity, but about timing and anticipation."
— Frank Thomas & Ollie Johnston

This module implements the "living" behaviors that make the robot feel
sentient even when idle. Key behaviors:

1. Breathing LED pattern (4-second cycle)
2. Random micro-glances (head movement)
3. Occasional blinks (LED dim)
4. Attention shifts (look around)
5. Settling movements (weight shifts)
"""

import asyncio
import random
import math
import time
import logging
from dataclasses import dataclass
from typing import Optional, Callable, List, Tuple
from enum import Enum, auto

_logger = logging.getLogger(__name__)


class IdleState(Enum):
    """Sub-states within idle behavior."""
    BREATHING = auto()      # Default: gentle breathing animation
    GLANCING = auto()       # Quick look to the side
    BLINKING = auto()       # Brief LED dim (eye blink)
    SETTLING = auto()       # Weight shift / head settle
    ATTENTION = auto()      # Look around (scanning)


@dataclass
class IdleTiming:
    """Timing parameters for idle behaviors (in seconds)."""

    # Breathing
    breath_cycle_sec: float = 4.0
    breath_min_brightness: float = 0.3

    # Glancing
    glance_interval_min: float = 3.0
    glance_interval_max: float = 8.0
    glance_duration: float = 0.5
    glance_hold: float = 0.3
    glance_return: float = 0.4

    # Blinking
    blink_interval_min: float = 2.0
    blink_interval_max: float = 6.0
    blink_duration: float = 0.15
    double_blink_chance: float = 0.2

    # Settling
    settle_interval_min: float = 10.0
    settle_interval_max: float = 20.0
    settle_duration: float = 1.5

    # Attention
    attention_interval_min: float = 15.0
    attention_interval_max: float = 45.0
    attention_duration: float = 3.0


class IdleBehavior:
    """Manages idle-state micro-animations for lifelike appearance.

    Uses asyncio for non-blocking animation coordination. Multiple
    behaviors can run concurrently (e.g., breathing + occasional blink).

    Thread Safety:
        Designed to run in its own asyncio event loop. Communication
        with main thread via thread-safe callbacks.

    Usage:
        >>> idle = IdleBehavior(emotion_manager, head_controller)
        >>> await idle.start()
        >>> # Robot now exhibits idle behaviors
        >>> await idle.stop()
    """

    def __init__(
        self,
        emotion_manager: Optional['EmotionManager'] = None,
        head_controller: Optional['HeadController'] = None,
        timing: Optional[IdleTiming] = None,
    ):
        """Initialize idle behavior engine.

        Args:
            emotion_manager: For LED pattern control.
            head_controller: For head movement (can be mock).
            timing: Custom timing parameters.
        """
        self._emotion = emotion_manager
        self._head = head_controller
        self._timing = timing or IdleTiming()

        # State
        self._running = False
        self._current_state = IdleState.BREATHING
        self._tasks: List[asyncio.Task] = []

        # Home position (center)
        self._home_pan = 90.0
        self._home_tilt = 90.0

        # Behavior suppression (when higher-priority action occurs)
        self._suppressed = False

        _logger.debug("IdleBehavior initialized")

    # =========================================================================
    # Lifecycle
    # =========================================================================

    async def start(self) -> None:
        """Start idle behavior loops."""
        if self._running:
            return

        self._running = True

        # Start concurrent behavior tasks
        self._tasks = [
            asyncio.create_task(self._breathing_loop(), name="breathing"),
            asyncio.create_task(self._glance_loop(), name="glance"),
            asyncio.create_task(self._blink_loop(), name="blink"),
            asyncio.create_task(self._settle_loop(), name="settle"),
            asyncio.create_task(self._attention_loop(), name="attention"),
        ]

        _logger.info("IdleBehavior started with %d tasks", len(self._tasks))

    async def stop(self) -> None:
        """Stop all idle behavior loops."""
        self._running = False

        # Cancel all tasks
        for task in self._tasks:
            task.cancel()

        # Wait for cancellation
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)

        self._tasks = []
        _logger.info("IdleBehavior stopped")

    def suppress(self) -> None:
        """Temporarily suppress idle behaviors (for explicit actions)."""
        self._suppressed = True
        _logger.debug("IdleBehavior suppressed")

    def unsuppress(self) -> None:
        """Resume idle behaviors."""
        self._suppressed = False
        _logger.debug("IdleBehavior unsuppressed")

    # =========================================================================
    # Behavior Loops
    # =========================================================================

    async def _breathing_loop(self) -> None:
        """Continuous breathing animation.

        Disney principle: Never truly static. The breathing creates
        the illusion that the robot is alive and aware.
        """
        _logger.debug("Breathing loop started")

        while self._running:
            if self._suppressed:
                await asyncio.sleep(0.1)
                continue

            # Breathing is handled by EmotionManager pattern
            # This loop just ensures we're in breathing state
            self._current_state = IdleState.BREATHING
            await asyncio.sleep(0.5)

    async def _glance_loop(self) -> None:
        """Occasional quick glances to the side.

        Disney principle: Secondary action. Small movements that
        don't distract from the main behavior but add life.
        """
        _logger.debug("Glance loop started")

        while self._running:
            # Random interval before next glance
            interval = random.uniform(
                self._timing.glance_interval_min,
                self._timing.glance_interval_max,
            )
            await asyncio.sleep(interval)

            if self._suppressed or not self._running:
                continue

            self._current_state = IdleState.GLANCING

            # Choose random glance direction
            glance_pan = self._home_pan + random.uniform(-20, 20)
            glance_tilt = self._home_tilt + random.uniform(-10, 10)

            # Execute glance: quick look, hold, return
            await self._smooth_head_move(glance_pan, glance_tilt, self._timing.glance_duration)
            await asyncio.sleep(self._timing.glance_hold)
            await self._smooth_head_move(self._home_pan, self._home_tilt, self._timing.glance_return)

            self._current_state = IdleState.BREATHING

    async def _blink_loop(self) -> None:
        """Occasional eye blinks (LED dim).

        Disney principle: Squash and stretch applied to brightness.
        Brief dimming mimics eye blinks in cartoon characters.
        """
        _logger.debug("Blink loop started")

        while self._running:
            # Random interval before next blink
            interval = random.uniform(
                self._timing.blink_interval_min,
                self._timing.blink_interval_max,
            )
            await asyncio.sleep(interval)

            if self._suppressed or not self._running:
                continue

            self._current_state = IdleState.BLINKING

            # Execute blink
            await self._do_blink()

            # Chance of double-blink
            if random.random() < self._timing.double_blink_chance:
                await asyncio.sleep(0.1)
                await self._do_blink()

            self._current_state = IdleState.BREATHING

    async def _do_blink(self) -> None:
        """Execute single blink animation."""
        if self._emotion is not None:
            # Quick dim to simulate blink
            original_intensity = self._emotion.intensity

            # Rapid dim down
            for i in range(5):
                self._emotion.intensity = original_intensity * (1 - i * 0.2)
                await asyncio.sleep(self._timing.blink_duration / 10)

            # Rapid brighten back
            for i in range(5):
                self._emotion.intensity = original_intensity * (i * 0.2)
                await asyncio.sleep(self._timing.blink_duration / 10)

            self._emotion.intensity = original_intensity

    async def _settle_loop(self) -> None:
        """Occasional settling movements (weight shifts).

        Disney principle: Follow-through and overlapping action.
        After larger movements, there's a settling period.
        """
        _logger.debug("Settle loop started")

        while self._running:
            # Random interval before next settle
            interval = random.uniform(
                self._timing.settle_interval_min,
                self._timing.settle_interval_max,
            )
            await asyncio.sleep(interval)

            if self._suppressed or not self._running:
                continue

            self._current_state = IdleState.SETTLING

            # Small weight shift (slight tilt variation)
            settle_tilt = self._home_tilt + random.uniform(-3, 3)
            await self._smooth_head_move(self._home_pan, settle_tilt, self._timing.settle_duration * 0.4)
            await asyncio.sleep(self._timing.settle_duration * 0.2)
            await self._smooth_head_move(self._home_pan, self._home_tilt, self._timing.settle_duration * 0.4)

            self._current_state = IdleState.BREATHING

    async def _attention_loop(self) -> None:
        """Occasional attention shifts (look around).

        Disney principle: Staging. The robot occasionally "surveys"
        its environment, suggesting awareness.
        """
        _logger.debug("Attention loop started")

        while self._running:
            # Longer interval for attention shifts
            interval = random.uniform(
                self._timing.attention_interval_min,
                self._timing.attention_interval_max,
            )
            await asyncio.sleep(interval)

            if self._suppressed or not self._running:
                continue

            self._current_state = IdleState.ATTENTION

            # Look sequence: left, right, back to center
            positions = [
                (self._home_pan - 30, self._home_tilt),
                (self._home_pan + 30, self._home_tilt),
                (self._home_pan, self._home_tilt),
            ]

            for pan, tilt in positions:
                await self._smooth_head_move(pan, tilt, self._timing.attention_duration / 4)
                await asyncio.sleep(self._timing.attention_duration / 6)

            self._current_state = IdleState.BREATHING

    # =========================================================================
    # Head Movement Utilities
    # =========================================================================

    async def _smooth_head_move(
        self,
        target_pan: float,
        target_tilt: float,
        duration: float,
    ) -> None:
        """Move head smoothly to target position with easing.

        Disney principle: Slow in and slow out. Natural movements
        accelerate and decelerate rather than constant speed.
        """
        if self._head is None:
            # Mock mode - just wait for duration
            await asyncio.sleep(duration)
            return

        # Get current position
        current_pan, current_tilt = self._head.get_position()

        # Animate with easing
        steps = int(duration * 50)  # 50Hz
        for i in range(steps):
            if not self._running or self._suppressed:
                break

            # Ease-in-out progress
            t = i / max(steps - 1, 1)
            eased = self._ease_in_out(t)

            # Interpolate position
            pan = current_pan + (target_pan - current_pan) * eased
            tilt = current_tilt + (target_tilt - current_tilt) * eased

            self._head.set_position(pan, tilt)
            await asyncio.sleep(duration / steps)

    @staticmethod
    def _ease_in_out(t: float) -> float:
        """Disney-style ease-in-out."""
        if t < 0.5:
            return 2 * t * t
        else:
            return 1 - ((-2 * t + 2) ** 2) / 2

    # =========================================================================
    # Diagnostics
    # =========================================================================

    def get_state(self) -> dict:
        """Get current idle behavior state."""
        return {
            "running": self._running,
            "suppressed": self._suppressed,
            "current_state": self._current_state.name,
            "active_tasks": len([t for t in self._tasks if not t.done()]),
        }
```

---

## Part 4: Behavior Tree Architecture

### Design Overview

A simplified behavior tree provides structured decision-making for complex behaviors while maintaining code clarity.

```python
# src/behavior/behavior_tree.py

"""
Behavior Tree for Robot Decision Making

Structure:
    - Selector: Try children in order, succeed on first success
    - Sequence: Run children in order, fail on first failure
    - Decorator: Modify child behavior (inverter, repeater, etc.)
    - Leaf: Actual behavior implementation
"""

from abc import ABC, abstractmethod
from enum import Enum, auto
from typing import List, Optional, Callable, Any
import logging

_logger = logging.getLogger(__name__)


class NodeStatus(Enum):
    """Result status of behavior tree node execution."""
    SUCCESS = auto()
    FAILURE = auto()
    RUNNING = auto()


class BehaviorNode(ABC):
    """Abstract base class for behavior tree nodes."""

    def __init__(self, name: str = ""):
        self.name = name or self.__class__.__name__

    @abstractmethod
    def tick(self, context: dict) -> NodeStatus:
        """Execute node and return status.

        Args:
            context: Shared context dictionary for data passing.

        Returns:
            NodeStatus indicating result.
        """
        pass

    def reset(self) -> None:
        """Reset node state for next execution."""
        pass


class Selector(BehaviorNode):
    """Try children in order, succeed on first success (OR logic)."""

    def __init__(self, name: str, children: List[BehaviorNode]):
        super().__init__(name)
        self.children = children
        self._running_child: Optional[int] = None

    def tick(self, context: dict) -> NodeStatus:
        start_index = self._running_child or 0

        for i in range(start_index, len(self.children)):
            child = self.children[i]
            status = child.tick(context)

            if status == NodeStatus.RUNNING:
                self._running_child = i
                return NodeStatus.RUNNING
            elif status == NodeStatus.SUCCESS:
                self._running_child = None
                return NodeStatus.SUCCESS

        self._running_child = None
        return NodeStatus.FAILURE

    def reset(self) -> None:
        self._running_child = None
        for child in self.children:
            child.reset()


class Sequence(BehaviorNode):
    """Run children in order, fail on first failure (AND logic)."""

    def __init__(self, name: str, children: List[BehaviorNode]):
        super().__init__(name)
        self.children = children
        self._running_child: Optional[int] = None

    def tick(self, context: dict) -> NodeStatus:
        start_index = self._running_child or 0

        for i in range(start_index, len(self.children)):
            child = self.children[i]
            status = child.tick(context)

            if status == NodeStatus.RUNNING:
                self._running_child = i
                return NodeStatus.RUNNING
            elif status == NodeStatus.FAILURE:
                self._running_child = None
                return NodeStatus.FAILURE

        self._running_child = None
        return NodeStatus.SUCCESS

    def reset(self) -> None:
        self._running_child = None
        for child in self.children:
            child.reset()


class Condition(BehaviorNode):
    """Check condition and return SUCCESS/FAILURE."""

    def __init__(self, name: str, check: Callable[[dict], bool]):
        super().__init__(name)
        self.check = check

    def tick(self, context: dict) -> NodeStatus:
        if self.check(context):
            return NodeStatus.SUCCESS
        return NodeStatus.FAILURE


class Action(BehaviorNode):
    """Execute action and return status."""

    def __init__(self, name: str, action: Callable[[dict], NodeStatus]):
        super().__init__(name)
        self.action = action

    def tick(self, context: dict) -> NodeStatus:
        return self.action(context)


# =========================================================================
# Example Behavior Tree for Robot
# =========================================================================

def create_emotion_behavior_tree(emotion_manager: 'EmotionManager') -> BehaviorNode:
    """Create behavior tree for emotion state decisions.

    Tree Structure:
        Selector "EmotionResponse"
        ├── Sequence "HandleAlert"
        │   ├── Condition "ObstacleDetected"
        │   └── Action "SetAlertEmotion"
        ├── Sequence "HandleVoice"
        │   ├── Condition "VoiceDetected"
        │   └── Action "SetCuriousEmotion"
        ├── Sequence "HandleLowBattery"
        │   ├── Condition "BatteryLow"
        │   └── Action "SetSleepyEmotion"
        └── Action "SetIdleEmotion"
    """
    from .emotion_manager import EmotionState

    return Selector("EmotionResponse", [
        # Priority 1: Alert on obstacle
        Sequence("HandleAlert", [
            Condition("ObstacleDetected",
                lambda ctx: ctx.get("obstacle_distance", 999) < 30),
            Action("SetAlertEmotion",
                lambda ctx: (
                    emotion_manager.set_emotion(EmotionState.ALERT),
                    NodeStatus.SUCCESS
                )[1]),
        ]),

        # Priority 2: Curious on voice
        Sequence("HandleVoice", [
            Condition("VoiceDetected",
                lambda ctx: ctx.get("voice_detected", False)),
            Action("SetCuriousEmotion",
                lambda ctx: (
                    emotion_manager.set_emotion(EmotionState.CURIOUS),
                    NodeStatus.SUCCESS
                )[1]),
        ]),

        # Priority 3: Sleepy on low battery
        Sequence("HandleLowBattery", [
            Condition("BatteryLow",
                lambda ctx: ctx.get("battery_percent", 100) < 20),
            Action("SetSleepyEmotion",
                lambda ctx: (
                    emotion_manager.set_emotion(EmotionState.SLEEPY),
                    NodeStatus.SUCCESS
                )[1]),
        ]),

        # Default: Idle
        Action("SetIdleEmotion",
            lambda ctx: (
                emotion_manager.set_emotion(EmotionState.IDLE)
                if emotion_manager.current_emotion != EmotionState.IDLE
                else None,
                NodeStatus.SUCCESS
            )[1]),
    ])
```

---

## Part 5: Emotion Triggers from Sensor Input

### Trigger Mapping

```python
# src/behavior/emotion_triggers.py

"""
EmotionTriggers - Sensor-to-Emotion Mapping

Maps robot sensor inputs and system events to appropriate emotion
responses. Designed for extensibility as new sensors are added.
"""

from dataclasses import dataclass
from typing import Dict, Callable, Optional, Any
from enum import Enum
import logging

from .emotion_manager import EmotionManager, EmotionState

_logger = logging.getLogger(__name__)


class TriggerType(Enum):
    """Categories of emotion triggers."""
    SENSOR = "sensor"       # Physical sensor input
    SYSTEM = "system"       # System events (battery, errors)
    VOICE = "voice"         # Voice/audio detection
    TOUCH = "touch"         # Touch sensor (future)
    TIMER = "timer"         # Time-based triggers


@dataclass
class EmotionTrigger:
    """Definition of an emotion trigger."""
    name: str
    trigger_type: TriggerType
    target_emotion: EmotionState
    condition: Callable[[Dict[str, Any]], bool]
    priority: int = 5  # 1=highest, 10=lowest
    cooldown_sec: float = 1.0  # Minimum time between triggers


# Standard trigger definitions
STANDARD_TRIGGERS: list[EmotionTrigger] = [
    # High priority: Safety triggers
    EmotionTrigger(
        name="obstacle_close",
        trigger_type=TriggerType.SENSOR,
        target_emotion=EmotionState.ALERT,
        condition=lambda ctx: ctx.get("obstacle_distance_cm", 999) < 30,
        priority=1,
        cooldown_sec=0.5,
    ),

    EmotionTrigger(
        name="collision_detected",
        trigger_type=TriggerType.SENSOR,
        target_emotion=EmotionState.ALERT,
        condition=lambda ctx: ctx.get("collision_detected", False),
        priority=1,
        cooldown_sec=0.3,
    ),

    # Medium priority: Interaction triggers
    EmotionTrigger(
        name="voice_command",
        trigger_type=TriggerType.VOICE,
        target_emotion=EmotionState.CURIOUS,
        condition=lambda ctx: ctx.get("voice_command_received", False),
        priority=3,
        cooldown_sec=1.0,
    ),

    EmotionTrigger(
        name="wake_word",
        trigger_type=TriggerType.VOICE,
        target_emotion=EmotionState.HAPPY,
        condition=lambda ctx: ctx.get("wake_word_detected", False),
        priority=2,
        cooldown_sec=2.0,
    ),

    EmotionTrigger(
        name="movement_detected",
        trigger_type=TriggerType.SENSOR,
        target_emotion=EmotionState.CURIOUS,
        condition=lambda ctx: ctx.get("movement_in_fov", False),
        priority=4,
        cooldown_sec=2.0,
    ),

    # Task completion triggers
    EmotionTrigger(
        name="task_complete",
        trigger_type=TriggerType.SYSTEM,
        target_emotion=EmotionState.HAPPY,
        condition=lambda ctx: ctx.get("task_just_completed", False),
        priority=3,
        cooldown_sec=3.0,
    ),

    EmotionTrigger(
        name="processing",
        trigger_type=TriggerType.SYSTEM,
        target_emotion=EmotionState.THINKING,
        condition=lambda ctx: ctx.get("is_processing", False),
        priority=5,
        cooldown_sec=0.5,
    ),

    # Low priority: State triggers
    EmotionTrigger(
        name="battery_low",
        trigger_type=TriggerType.SYSTEM,
        target_emotion=EmotionState.SLEEPY,
        condition=lambda ctx: ctx.get("battery_percent", 100) < 15,
        priority=6,
        cooldown_sec=30.0,
    ),

    EmotionTrigger(
        name="error_state",
        trigger_type=TriggerType.SYSTEM,
        target_emotion=EmotionState.SAD,
        condition=lambda ctx: ctx.get("error_count", 0) > 3,
        priority=5,
        cooldown_sec=10.0,
    ),

    EmotionTrigger(
        name="idle_timeout",
        trigger_type=TriggerType.TIMER,
        target_emotion=EmotionState.SLEEPY,
        condition=lambda ctx: ctx.get("idle_time_sec", 0) > 300,  # 5 minutes
        priority=8,
        cooldown_sec=60.0,
    ),
]


class EmotionTriggerProcessor:
    """Processes sensor context and triggers appropriate emotions."""

    def __init__(
        self,
        emotion_manager: EmotionManager,
        triggers: Optional[list[EmotionTrigger]] = None,
    ):
        self._emotion_manager = emotion_manager
        self._triggers = triggers or STANDARD_TRIGGERS
        self._last_trigger_times: Dict[str, float] = {}

    def process(self, context: Dict[str, Any]) -> Optional[EmotionState]:
        """Process sensor context and trigger emotion if conditions met.

        Args:
            context: Dictionary of sensor values and system state.

        Returns:
            Triggered emotion state, or None if no trigger fired.
        """
        import time
        current_time = time.monotonic()

        # Sort by priority (lowest number = highest priority)
        sorted_triggers = sorted(self._triggers, key=lambda t: t.priority)

        for trigger in sorted_triggers:
            # Check cooldown
            last_time = self._last_trigger_times.get(trigger.name, 0)
            if current_time - last_time < trigger.cooldown_sec:
                continue

            # Check condition
            try:
                if trigger.condition(context):
                    _logger.info(
                        "Trigger fired: %s -> %s",
                        trigger.name, trigger.target_emotion.name
                    )

                    self._emotion_manager.set_emotion(trigger.target_emotion)
                    self._last_trigger_times[trigger.name] = current_time

                    return trigger.target_emotion
            except Exception as e:
                _logger.error("Trigger condition error [%s]: %s", trigger.name, e)

        return None
```

---

## Part 6: Mock Head Controller

### Design for Hardware Independence

```python
# src/behavior/head_controller.py

"""
HeadController - Mock/Real Head Movement Control

Provides unified interface for head servo control. In mock mode,
logs movements and tracks position. In real mode, drives actual servos.

This allows full behavior system testing before servos arrive.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Tuple, Optional, Callable
import logging
import threading

_logger = logging.getLogger(__name__)


@dataclass
class HeadPosition:
    """Head position in degrees."""
    pan: float      # Left/right (-90 to 90, 0 = center)
    tilt: float     # Up/down (-45 to 45, 0 = level)


class HeadControllerBase(ABC):
    """Abstract base class for head controllers."""

    @abstractmethod
    def set_position(self, pan: float, tilt: float) -> bool:
        """Set head position.

        Args:
            pan: Pan angle in degrees.
            tilt: Tilt angle in degrees.

        Returns:
            True if command accepted.
        """
        pass

    @abstractmethod
    def get_position(self) -> Tuple[float, float]:
        """Get current head position.

        Returns:
            Tuple of (pan, tilt) in degrees.
        """
        pass

    @abstractmethod
    def home(self) -> bool:
        """Move head to home/center position."""
        pass


class MockHeadController(HeadControllerBase):
    """Mock head controller for testing without hardware.

    Logs all movements and tracks virtual position.
    Useful for development and unit testing.
    """

    def __init__(
        self,
        home_pan: float = 90.0,
        home_tilt: float = 90.0,
        log_movements: bool = True,
    ):
        self._pan = home_pan
        self._tilt = home_tilt
        self._home_pan = home_pan
        self._home_tilt = home_tilt
        self._log = log_movements
        self._lock = threading.Lock()

        # Movement callback for testing
        self._on_move: Optional[Callable[[float, float], None]] = None

        _logger.debug("MockHeadController initialized at (%.1f, %.1f)", home_pan, home_tilt)

    def set_position(self, pan: float, tilt: float) -> bool:
        with self._lock:
            # Clamp to valid range
            self._pan = max(0, min(180, pan))
            self._tilt = max(45, min(135, tilt))

            if self._log:
                _logger.debug("MockHead: set_position(%.1f, %.1f)", self._pan, self._tilt)

            if self._on_move is not None:
                self._on_move(self._pan, self._tilt)

            return True

    def get_position(self) -> Tuple[float, float]:
        with self._lock:
            return (self._pan, self._tilt)

    def home(self) -> bool:
        return self.set_position(self._home_pan, self._home_tilt)

    def on_move(self, callback: Callable[[float, float], None]) -> None:
        """Register callback for movement events (for testing)."""
        self._on_move = callback


class RealHeadController(HeadControllerBase):
    """Real head controller using servo driver.

    Uses PCA9685 PWM driver for actual servo control.
    """

    # Default servo channels
    PAN_CHANNEL = 12
    TILT_CHANNEL = 13

    def __init__(
        self,
        servo_driver: 'PCA9685Driver',
        pan_channel: int = PAN_CHANNEL,
        tilt_channel: int = TILT_CHANNEL,
        home_pan: float = 90.0,
        home_tilt: float = 90.0,
    ):
        self._servo = servo_driver
        self._pan_ch = pan_channel
        self._tilt_ch = tilt_channel
        self._home_pan = home_pan
        self._home_tilt = home_tilt
        self._pan = home_pan
        self._tilt = home_tilt
        self._lock = threading.Lock()

        _logger.info(
            "RealHeadController initialized: pan=ch%d, tilt=ch%d",
            pan_channel, tilt_channel
        )

    def set_position(self, pan: float, tilt: float) -> bool:
        with self._lock:
            try:
                # Clamp to servo limits
                pan = max(0, min(180, pan))
                tilt = max(45, min(135, tilt))

                self._servo.set_servo_angle(self._pan_ch, pan)
                self._servo.set_servo_angle(self._tilt_ch, tilt)

                self._pan = pan
                self._tilt = tilt
                return True

            except Exception as e:
                _logger.error("Head movement failed: %s", e)
                return False

    def get_position(self) -> Tuple[float, float]:
        with self._lock:
            return (self._pan, self._tilt)

    def home(self) -> bool:
        return self.set_position(self._home_pan, self._home_tilt)
```

---

## Part 7: Test Cases

### Test Structure

```python
# tests/test_behavior/test_emotion_manager.py

"""
Test suite for EmotionManager - targeting 50+ tests.
"""

import pytest
import time
import threading
from unittest.mock import MagicMock, patch

# Assuming src path is configured
from src.behavior.emotion_manager import (
    EmotionManager,
    EmotionState,
    EmotionConfig,
    EMOTION_CONFIGS,
    VALID_TRANSITIONS,
)


class TestEmotionState:
    """Tests for EmotionState enum and configurations."""

    def test_all_states_have_configs(self):
        """Every EmotionState must have a corresponding config."""
        for state in EmotionState:
            assert state in EMOTION_CONFIGS, f"Missing config for {state.name}"

    def test_all_configs_have_valid_colors(self):
        """All colors must be valid RGB tuples."""
        for state, config in EMOTION_CONFIGS.items():
            assert len(config.color) == 3
            for c in config.color:
                assert 0 <= c <= 255, f"Invalid color value in {state.name}"

    def test_all_configs_have_valid_timing(self):
        """All timing values must be positive."""
        for state, config in EMOTION_CONFIGS.items():
            assert config.transition_in_ms > 0
            assert config.transition_out_ms > 0
            assert config.anticipation_ms >= 0
            assert config.follow_through_ms >= 0

    def test_all_configs_have_valid_brightness(self):
        """Brightness values must be in valid range."""
        for state, config in EMOTION_CONFIGS.items():
            assert 0 <= config.min_brightness <= 1
            assert 0 <= config.max_brightness <= 1
            assert config.min_brightness <= config.max_brightness


class TestValidTransitions:
    """Tests for state transition validity."""

    def test_all_states_have_transitions(self):
        """Every state must have at least one valid transition."""
        for state in EmotionState:
            assert state in VALID_TRANSITIONS
            assert len(VALID_TRANSITIONS[state]) > 0

    def test_idle_can_reach_all_states(self):
        """IDLE should be able to reach most states (hub state)."""
        idle_transitions = VALID_TRANSITIONS[EmotionState.IDLE]
        # IDLE should reach at least 4 states directly
        assert len(idle_transitions) >= 4

    def test_all_states_can_return_to_idle(self):
        """All states should have a path back to IDLE."""
        for state in EmotionState:
            if state == EmotionState.IDLE:
                continue
            # Direct transition to IDLE
            if EmotionState.IDLE in VALID_TRANSITIONS[state]:
                continue
            # One-hop to IDLE (through intermediate state)
            found_path = False
            for intermediate in VALID_TRANSITIONS[state]:
                if EmotionState.IDLE in VALID_TRANSITIONS.get(intermediate, []):
                    found_path = True
                    break
            assert found_path, f"No path from {state.name} to IDLE"


class TestEmotionManagerInit:
    """Tests for EmotionManager initialization."""

    def test_init_default(self):
        """Test default initialization."""
        manager = EmotionManager()
        assert manager.current_emotion == EmotionState.IDLE
        assert not manager.is_transitioning
        assert manager.intensity == 1.0

    def test_init_custom_emotion(self):
        """Test initialization with custom starting emotion."""
        manager = EmotionManager(initial_emotion=EmotionState.HAPPY)
        assert manager.current_emotion == EmotionState.HAPPY

    def test_init_with_led_controller(self):
        """Test initialization with LED controller."""
        mock_led = MagicMock()
        manager = EmotionManager(led_controller=mock_led)
        assert manager._led is mock_led


class TestEmotionManagerTransitions:
    """Tests for emotion state transitions."""

    def test_valid_transition(self):
        """Test valid emotion transition."""
        manager = EmotionManager()
        result = manager.set_emotion(EmotionState.HAPPY)
        assert result is True
        # Note: actual transition may not be instant

    def test_invalid_transition(self):
        """Test invalid transition is blocked."""
        manager = EmotionManager()  # Starts at IDLE
        # IDLE -> EXCITED is not valid (must go through HAPPY)
        result = manager.set_emotion(EmotionState.EXCITED)
        assert result is False
        assert manager.current_emotion == EmotionState.IDLE

    def test_forced_invalid_transition(self):
        """Test force flag bypasses transition validation."""
        manager = EmotionManager()
        result = manager.set_emotion(EmotionState.EXCITED, force=True)
        assert result is True

    def test_immediate_transition(self):
        """Test immediate flag skips anticipation."""
        manager = EmotionManager()
        manager.set_emotion(EmotionState.HAPPY, immediate=True)
        # Transition should start in 'main' phase, not 'anticipation'
        if manager._transition:
            assert manager._transition.phase == "main"


class TestEmotionManagerAnimation:
    """Tests for animation loop."""

    def test_start_stop(self):
        """Test start and stop lifecycle."""
        manager = EmotionManager()

        result = manager.start()
        assert result is True
        assert manager._running is True

        manager.stop()
        assert manager._running is False

    def test_double_start(self):
        """Test double start returns False."""
        manager = EmotionManager()
        manager.start()
        result = manager.start()
        assert result is False
        manager.stop()

    def test_animation_runs_at_target_rate(self):
        """Test animation maintains target frame rate."""
        manager = EmotionManager()
        manager.start()

        # Let it run for 100ms
        time.sleep(0.1)

        # Should have ~5 frames at 50Hz
        assert manager._frame_count >= 3  # Allow some variance
        assert manager._frame_count <= 10

        manager.stop()


class TestColorBlending:
    """Tests for HSV color blending."""

    def test_rgb_to_hsv_red(self):
        """Test RGB to HSV conversion for red."""
        h, s, v = EmotionManager._rgb_to_hsv((255, 0, 0))
        assert abs(h) < 0.01 or abs(h - 1.0) < 0.01  # Red at 0 or 1
        assert abs(s - 1.0) < 0.01
        assert abs(v - 1.0) < 0.01

    def test_hsv_to_rgb_red(self):
        """Test HSV to RGB conversion for red."""
        r, g, b = EmotionManager._hsv_to_rgb((0.0, 1.0, 1.0))
        assert r == 255
        assert g == 0
        assert b == 0

    def test_blend_same_color(self):
        """Blending same color returns that color."""
        manager = EmotionManager()
        result = manager._blend_colors_hsv((255, 0, 0), (255, 0, 0), 0.5)
        assert result == (255, 0, 0)

    def test_blend_progress_zero(self):
        """Progress 0 returns first color."""
        manager = EmotionManager()
        result = manager._blend_colors_hsv((255, 0, 0), (0, 255, 0), 0.0)
        assert result[0] > 200  # Should be mostly red


class TestIntensity:
    """Tests for intensity modulation."""

    def test_intensity_default(self):
        """Default intensity is 1.0."""
        manager = EmotionManager()
        assert manager.intensity == 1.0

    def test_intensity_set_valid(self):
        """Set valid intensity value."""
        manager = EmotionManager()
        manager.intensity = 0.5
        assert manager.intensity == 0.5

    def test_intensity_clamp_high(self):
        """Intensity above 1.0 is clamped."""
        manager = EmotionManager()
        manager.intensity = 1.5
        assert manager.intensity == 1.0

    def test_intensity_clamp_low(self):
        """Intensity below 0.0 is clamped."""
        manager = EmotionManager()
        manager.intensity = -0.5
        assert manager.intensity == 0.0


class TestCallbacks:
    """Tests for event callbacks."""

    def test_on_emotion_change_callback(self):
        """Test emotion change callback is called."""
        manager = EmotionManager()
        callback_data = []

        manager.on_emotion_change(
            lambda from_e, to_e: callback_data.append((from_e, to_e))
        )

        manager.set_emotion(EmotionState.HAPPY)

        assert len(callback_data) == 1
        assert callback_data[0] == (EmotionState.IDLE, EmotionState.HAPPY)


class TestDiagnostics:
    """Tests for diagnostic output."""

    def test_diagnostics_structure(self):
        """Test diagnostics returns expected keys."""
        manager = EmotionManager()
        diag = manager.get_diagnostics()

        assert "current_emotion" in diag
        assert "is_transitioning" in diag
        assert "intensity" in diag
        assert "frame_count" in diag
        assert "running" in diag


# Similar test classes for IdleBehavior, BehaviorTree, etc.
```

---

## Part 8: Day-by-Day Work Breakdown

### Week 02 Schedule

| Day | Date | Focus | Deliverables | Tests Added |
|-----|------|-------|--------------|-------------|
| **8** | Mon 22 Jan | Core classes | EmotionManager, EmotionConfig | +50 |
| **9** | Tue 23 Jan | Animation engine | ColorManager, PatternLibrary | +35 |
| **10** | Wed 24 Jan | Idle behaviors | IdleBehavior async loops | +30 |
| **11** | Thu 25 Jan | Behavior tree | BehaviorTree, Triggers | +25 |
| **12** | Fri 26 Jan | Integration | BehaviorCoordinator, HeadController | +20 |
| **13** | Sat 27 Jan | Hardware test | Servo integration (if arrived) | +10 |
| **14** | Sun 28 Jan | Polish & docs | Final testing, documentation | +10 |

---

### Day 8 (Monday): Core Classes

**Morning (4 hours):**
1. Create `src/behavior/` package structure
2. Implement `EmotionState` enum and `EmotionConfig` dataclass
3. Implement `EMOTION_CONFIGS` dictionary with all 8 emotions
4. Write unit tests for emotion configs

**Afternoon (4 hours):**
1. Implement `EmotionManager` class skeleton
2. Add state machine with `VALID_TRANSITIONS`
3. Implement `set_emotion()` with transition validation
4. Write tests for state transitions

**Evening (2 hours):**
1. Hostile review of EmotionManager
2. Fix any critical issues
3. Update CHANGELOG

**Deliverables:**
- `src/behavior/__init__.py`
- `src/behavior/emotion_manager.py` (~400 lines)
- `tests/test_behavior/test_emotion_manager.py` (~50 tests)

---

### Day 9 (Tuesday): Animation Engine

**Morning (4 hours):**
1. Implement HSV color conversion utilities
2. Implement color blending with arc interpolation
3. Implement `_animation_loop()` at 50Hz
4. Write color conversion tests

**Afternoon (4 hours):**
1. Implement pattern calculations (breathing, pulse, spin, sparkle, fade)
2. Implement transition phases (anticipation, main, follow_through)
3. Implement easing functions (slow-in/slow-out)
4. Write pattern tests

**Evening (2 hours):**
1. Integration test: EmotionManager + LED controller (mock)
2. Verify 50Hz timing accuracy
3. Update CHANGELOG

**Deliverables:**
- Enhanced `emotion_manager.py` (+200 lines)
- `tests/test_behavior/test_patterns.py` (~35 tests)

---

### Day 10 (Wednesday): Idle Behaviors

**Morning (4 hours):**
1. Create `idle_behavior.py` with async structure
2. Implement `_breathing_loop()` (continuous)
3. Implement `_blink_loop()` (random interval)
4. Write async tests with pytest-asyncio

**Afternoon (4 hours):**
1. Implement `_glance_loop()` (head movement)
2. Implement `_settle_loop()` (weight shifts)
3. Implement `_attention_loop()` (look around)
4. Add suppression mechanism for explicit actions

**Evening (2 hours):**
1. Integration test: IdleBehavior + EmotionManager
2. Verify timing randomization (no mechanical feel)
3. Update CHANGELOG

**Deliverables:**
- `src/behavior/idle_behavior.py` (~300 lines)
- `tests/test_behavior/test_idle_behavior.py` (~30 tests)

---

### Day 11 (Thursday): Behavior Tree

**Morning (4 hours):**
1. Implement `behavior_tree.py` base classes
2. Implement Selector and Sequence composites
3. Implement Condition and Action leaves
4. Write behavior tree tests

**Afternoon (4 hours):**
1. Create `emotion_triggers.py`
2. Define standard triggers (obstacle, voice, battery, etc.)
3. Implement `EmotionTriggerProcessor`
4. Write trigger tests

**Evening (2 hours):**
1. Build emotion behavior tree
2. Test sensor context processing
3. Update CHANGELOG

**Deliverables:**
- `src/behavior/behavior_tree.py` (~200 lines)
- `src/behavior/emotion_triggers.py` (~200 lines)
- `tests/test_behavior/test_behavior_tree.py` (~25 tests)

---

### Day 12 (Friday): Integration

**Morning (4 hours):**
1. Create `head_controller.py` with mock/real interface
2. Implement `MockHeadController` for testing
3. Implement `RealHeadController` (for when servos arrive)
4. Write head controller tests

**Afternoon (4 hours):**
1. Create `behavior_coordinator.py` (top-level orchestrator)
2. Wire EmotionManager + IdleBehavior + HeadController
3. Add integration with existing Robot class
4. Write integration tests

**Evening (2 hours):**
1. End-to-end test on Raspberry Pi (LED only)
2. Verify Disney animation quality
3. Update CHANGELOG

**Deliverables:**
- `src/behavior/head_controller.py` (~150 lines)
- `src/behavior/behavior_coordinator.py` (~200 lines)
- Integration tests (~20 tests)

---

### Day 13 (Saturday): Hardware Test

**Morning (4 hours):**
1. If servos arrived: Connect and test head movement
2. If no servos: Extended LED pattern testing
3. Calibrate head servo home positions
4. Test emotion → head pose coordination

**Afternoon (4 hours):**
1. Full behavior system test on hardware
2. Performance profiling (CPU, memory)
3. Fix any hardware-specific issues
4. Document servo calibration values

**Evening (2 hours):**
1. Hostile review of full behavior system
2. Fix critical issues
3. Update CHANGELOG

**Deliverables:**
- Calibration data in YAML
- Performance metrics documented
- ~10 hardware validation tests

---

### Day 14 (Sunday): Polish & Documentation

**Morning (4 hours):**
1. Code cleanup and refactoring
2. Add comprehensive docstrings
3. Update type hints throughout
4. Final test run (target: 180+ tests)

**Afternoon (4 hours):**
1. Create usage examples
2. Update README with behavior system docs
3. Create video demo of behaviors (if possible)
4. Week 02 completion report

**Evening (2 hours):**
1. Git tag v0.2.0
2. Final CHANGELOG update
3. Plan Week 03 priorities

**Deliverables:**
- Clean, documented codebase
- Usage examples
- Week 02 completion report
- v0.2.0 release tag

---

## Part 9: Success Metrics

### Quantitative

| Metric | Target | Measurement |
|--------|--------|-------------|
| Test count | 180+ | `pytest --collect-only` |
| Test pass rate | 95%+ | `pytest --tb=no` |
| Code coverage | 85%+ | `pytest --cov=src/behavior` |
| Animation frame rate | 50Hz ±5% | Performance profiling |
| Emotion transition latency | <100ms | Timing measurements |
| Idle behavior variety | 5+ distinct behaviors | Visual inspection |

### Qualitative

1. **Feels alive**: Robot exhibits constant subtle motion
2. **Not mechanical**: Timing variation prevents robotic feel
3. **Emotionally expressive**: Clear emotional states via LED color/pattern
4. **Responsive**: Emotion triggers react appropriately to context
5. **Disney quality**: Follows animation principles (slow-in/out, anticipation)

---

## Part 10: Risk Mitigation

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Servos don't arrive | Medium | Low | Mock controller allows full testing |
| LED flicker at 50Hz | Low | Medium | Pre-allocated buffers, minimal allocation |
| Asyncio complexity | Medium | Medium | Simple task structure, comprehensive tests |
| Color transitions harsh | Medium | Medium | HSV interpolation, easing functions |
| CPU overload on Pi | Low | High | Performance profiling, optimization |

---

## Appendix: Disney 12 Principles Quick Reference

1. **Squash & Stretch**: Brightness compression during transitions
2. **Anticipation**: Brief dim/shift before emotion change
3. **Staging**: One dominant effect per emotion
4. **Straight Ahead/Pose-to-Pose**: Idle (spontaneous) vs scripted (planned)
5. **Follow Through**: Color "echo" and brightness settling
6. **Slow In/Slow Out**: Easing on all transitions
7. **Arc**: Color transitions through HSV, not linear RGB
8. **Secondary Action**: Subtle patterns under primary color
9. **Timing**: Different durations = different weights
10. **Exaggeration**: Amplified saturation/brightness for emotions
11. **Solid Drawing**: Consistent color temperature per emotion family
12. **Appeal**: Warm, desaturated, friendly colors

---

**Document Version:** 1.0
**Last Updated:** 22 January 2026
**Approved By:** DeepMind Applied Robotics Standards
**Next Review:** After Day 14 (Week 02 Complete)
