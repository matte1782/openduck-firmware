# Day 12 Architecture Specification
## OpenDuck Mini V3 - Idle Behaviors + Animation Coordination + Emotion Bridge

**Document Version:** 1.0
**Created:** 18 January 2026
**Author:** Agent 0 (Chief Architect)
**Quality Standard:** Boston Dynamics / Pixar / DeepMind Grade

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Codebase Audit Results](#2-codebase-audit-results)
3. [Day 12 Objectives](#3-day-12-objectives)
4. [Dependency Analysis](#4-dependency-analysis)
5. [Module Specifications](#5-module-specifications)
6. [Test Specifications](#6-test-specifications)
7. [Integration Points](#7-integration-points)
8. [Agent Assignments](#8-agent-assignments)
9. [Success Criteria](#9-success-criteria)

---

## 1. Executive Summary

### 1.1 Day 12 Mission

Day 12 delivers the **behavioral layer** that brings OpenDuck to life through:

1. **IdleBehavior** - Background personality when robot is idle (blinks, glances)
2. **BlinkBehavior** - Eyelid/LED blink animations
3. **AnimationCoordinator** - Layered animation priority system
4. **EmotionBridge** - Maps emotions to head movements and LED patterns

### 1.2 Key Constraint: Build on Existing Infrastructure

**CRITICAL:** The following modules ALREADY EXIST and must NOT be recreated:

| Module | Location | Status |
|--------|----------|--------|
| HeadController | `src/control/head_controller.py` | COMPLETE (Day 11) |
| ColorUtils | `src/led/color_utils.py` | COMPLETE (Day 11) |
| EmotionAxes | `src/animation/emotion_axes.py` | COMPLETE (Day 9) |
| AxisToLEDMapper | `src/animation/axis_to_led.py` | COMPLETE (Day 9) |
| MicroExpressionEngine | `src/animation/micro_expressions.py` | COMPLETE (Day 10) |
| AnimationSequence | `src/animation/timing.py` | COMPLETE |
| AnimationPlayer | `src/animation/timing.py` | COMPLETE |
| Easing Functions | `src/animation/easing.py` | COMPLETE |

### 1.3 Design Philosophy

**Disney Animation Principles:**
- "Even when waiting, characters are alive" - IdleBehavior
- "Anticipation before action" - HeadController already implements
- "Secondary action supports primary" - MicroExpressions overlay
- "Timing creates emotion" - AnimationCoordinator layers

**Thread Safety Requirements:**
- All public methods thread-safe
- Use existing lock patterns from HeadController
- No race conditions between idle loop and triggered actions

---

## 2. Codebase Audit Results

### 2.1 Files Audited

| File | Lines | Purpose | Relevant to Day 12 |
|------|-------|---------|-------------------|
| `CHANGELOG.md` | 2000+ | Project history | YES - verify completion |
| `src/control/head_controller.py` | 500+ | 2-DOF head control | YES - use, don't recreate |
| `src/led/color_utils.py` | 300+ | HSV/RGB conversion | YES - use for LED colors |
| `src/animation/emotion_axes.py` | 500+ | 4-axis emotion model | YES - input to EmotionBridge |
| `src/animation/axis_to_led.py` | 420+ | Emotion to LED mapping | YES - use in EmotionBridge |
| `src/animation/micro_expressions.py` | 825+ | LED micro-expressions | YES - integrate with coordinator |
| `src/animation/timing.py` | 390+ | Keyframe animation | YES - use for blink sequences |
| `src/animation/easing.py` | 200+ | Easing functions | YES - use existing easing |
| `tests/test_control/test_head_controller.py` | 900+ | Head tests | YES - follow test patterns |
| `tests/test_integration/test_day9_integration.py` | 1100+ | Integration test patterns | YES - follow patterns |

### 2.2 What Exists (DO NOT RECREATE)

**HeadController Capabilities (Day 11 Complete):**
- `look_at(pan, tilt, duration_ms, easing, blocking)` - Direct positioning
- `nod(count, amplitude, speed_ms, blocking)` - Vertical affirmation
- `shake(count, amplitude, speed_ms, blocking)` - Horizontal negation
- `random_glance(max_deviation, hold_ms, blocking)` - Quick look and return
- `tilt_curious(direction, angle, duration_ms, blocking)` - Curious head tilt
- `reset_to_center(duration_ms, blocking)` - Return to home
- `emergency_stop()` / `reset_emergency()` - Safety controls
- `get_current_position()` / `get_state()` - State queries

**EmotionAxes Capabilities (Day 9 Complete):**
- 4-axis emotion model: arousal, valence, focus, blink_speed
- `interpolate(target, t)` - Smooth emotion transitions
- `to_hsv()` - Convert emotion to LED color
- `EMOTION_PRESETS` dictionary with 19 preset emotions

**AxisToLEDMapper Capabilities (Day 9 Complete):**
- `axes_to_pattern_name(axes)` - Select LED pattern
- `axes_to_hsv(axes)` - Get LED color from emotion
- `axes_to_pattern_speed(axes)` - Get animation speed
- `axes_to_led_config(axes)` - Combined configuration dict

**MicroExpressionEngine Capabilities (Day 10 Complete):**
- `trigger(expression_type, duration_ms, intensity)` - Trigger effect
- `trigger_preset(preset_name)` - Trigger named preset
- `update(delta_ms)` - Frame update
- `get_brightness_modifier()` - Global brightness
- `get_per_pixel_modifiers()` - Per-LED brightness
- 16 preset micro-expressions (blink_normal, sparkle_happy, etc.)

### 2.3 Gaps Identified (MUST BUILD)

| Gap | Module | Priority | Reason |
|-----|--------|----------|--------|
| Background idle loop | `IdleBehavior` | HIGH | Robot feels dead without it |
| Blink animation | `BlinkBehavior` | HIGH | Eyes need to blink |
| Animation layering | `AnimationCoordinator` | HIGH | Multiple animations must blend |
| Emotion-to-action mapping | `EmotionBridge` | MEDIUM | Connect emotions to behaviors |
| Integration tests | `test_day12_integration.py` | HIGH | Verify coordination |

### 2.4 Redundancies to Avoid

**DO NOT CREATE:**
- Another emotion-to-LED mapper (use AxisToLEDMapper)
- Another blink system (use MicroExpressionEngine for LED blink)
- Another head controller (use existing HeadController)
- New easing functions (use existing `ease()` from easing.py)
- New timing utilities (use AnimationSequence/AnimationPlayer)

---

## 3. Day 12 Objectives

### 3.1 Primary Deliverables

1. **IdleBehavior Class** - Background personality loop
   - Automatic random blinks every 3-5 seconds
   - Random glances every 5-10 seconds
   - Subtle head micro-movements
   - Runs as async task, cancellable

2. **BlinkBehavior Class** - Eye blink animations
   - Normal blink (150ms)
   - Slow blink (400ms) for sleepy emotion
   - Wink (left/right)
   - Uses MicroExpressionEngine for LED effects
   - Uses eyelid servos if available (future)

3. **AnimationCoordinator Class** - Layered animation system
   - Background layer (IdleBehavior)
   - Triggered layer (emotions, gestures)
   - Priority-based interruption
   - Smooth blending between layers

4. **EmotionBridge Class** - Emotion to behavior mapping
   - Maps EmotionAxes to HeadController poses
   - Maps EmotionAxes to LED patterns (via AxisToLEDMapper)
   - Maps EmotionAxes to blink speed
   - Orchestrates coordinated expressions

5. **Integration Tests** - Full system validation
   - Idle system runs without errors
   - Emotion changes trigger correct behaviors
   - Concurrent head and LED animations
   - No race conditions under load

### 3.2 Stretch Goals (if time permits)

- Emotion transition animations
- Sound-triggered attention behaviors
- Eye tracking (look at sound source)

---

## 4. Dependency Analysis

### 4.1 Dependency Graph

```
                      +-----------------------+
                      |  robot_config.yaml    |
                      |   (head channels,     |
                      |    emotion mappings)  |
                      +----------+------------+
                                 |
        +------------------------+------------------------+
        |                        |                        |
        v                        v                        v
+----------------+    +-------------------+    +------------------+
| HeadController |    |  AxisToLEDMapper  |    | MicroExpression  |
|   (Day 11)     |    |     (Day 9)       |    |   Engine (D10)   |
+-------+--------+    +----------+--------+    +--------+---------+
        |                        |                      |
        |                        |                      |
        v                        v                      v
+-------+------------------------+----------------------+---------+
|                                                                 |
|                    EmotionBridge (NEW - Day 12)                 |
|       Maps EmotionAxes -> HeadController + LED actions          |
|                                                                 |
+------------------------------+----------------------------------+
                               |
                               v
+------------------------------+----------------------------------+
|                                                                 |
|                AnimationCoordinator (NEW - Day 12)              |
|         Manages layers: Background | Triggered | Override       |
|                                                                 |
+------------------------------+----------------------------------+
                               |
           +-------------------+-------------------+
           |                                       |
           v                                       v
+----------+------------+            +-------------+-------------+
|  IdleBehavior (NEW)   |            |   BlinkBehavior (NEW)     |
|  - Random blinks      |            |   - Normal blink          |
|  - Random glances     |            |   - Slow blink            |
|  - Micro-movements    |            |   - Wink                  |
+----------+------------+            +---------------------------+
           |
           | Uses
           v
+----------+------------+
| AnimationSequence     |
| (existing timing.py)  |
+-----------------------+
```

### 4.2 Import Dependencies

```python
# IdleBehavior imports
import asyncio
import random
import time
from typing import Optional, Callable
from ..control.head_controller import HeadController
from .micro_expressions import MicroExpressionEngine, MicroExpressionType

# BlinkBehavior imports
from .timing import AnimationSequence
from .micro_expressions import MicroExpressionEngine

# AnimationCoordinator imports
import threading
from enum import Enum
from typing import List, Dict, Optional
from dataclasses import dataclass

# EmotionBridge imports
from .emotion_axes import EmotionAxes, EMOTION_PRESETS
from .axis_to_led import AxisToLEDMapper
from ..control.head_controller import HeadController
from .micro_expressions import MicroExpressionEngine
```

---

## 5. Module Specifications

### 5.1 IdleBehavior (`src/animation/behaviors.py`)

```python
"""
Idle Behaviors - Background personality when robot is idle.

Disney Animation Principle: "Even when waiting, characters are alive."

Runs as an async task, providing:
- Random blinks (every 3-5 seconds)
- Random glances (every 5-10 seconds)
- Subtle micro-movements (optional)

Thread Safety:
    Designed for single-threaded async operation.
    External synchronization needed if called from multiple threads.
"""

from typing import Optional, Callable
import asyncio
import random
import time


class IdleBehavior:
    """
    Background idle behaviors that give the robot personality.

    Runs blinks, glances, and subtle movements when robot is idle.
    Implements Disney's principle that characters are never truly still.

    Example:
        >>> idle = IdleBehavior(head_controller, micro_engine, led_controller)
        >>> task = asyncio.create_task(idle.run())
        >>> # Later...
        >>> idle.stop()
        >>> await task

    Attributes:
        head: HeadController instance for head movements
        micro_engine: MicroExpressionEngine for LED effects
        led_controller: Optional LED controller for direct LED control

    Timing Configuration:
        blink_interval_min/max: Range for random blink timing (seconds)
        glance_interval_min/max: Range for random glance timing (seconds)
    """

    def __init__(
        self,
        head_controller: 'HeadController',
        micro_engine: 'MicroExpressionEngine',
        led_controller: Optional['LEDController'] = None
    ) -> None:
        """
        Initialize idle behavior system.

        Args:
            head_controller: HeadController for head movements
            micro_engine: MicroExpressionEngine for LED blink effects
            led_controller: Optional direct LED controller
        """
        ...

    @property
    def blink_interval_min(self) -> float:
        """Minimum seconds between blinks (default 3.0)."""
        ...

    @property
    def blink_interval_max(self) -> float:
        """Maximum seconds between blinks (default 5.0)."""
        ...

    @property
    def glance_interval_min(self) -> float:
        """Minimum seconds between glances (default 5.0)."""
        ...

    @property
    def glance_interval_max(self) -> float:
        """Maximum seconds between glances (default 10.0)."""
        ...

    async def run(self) -> None:
        """
        Main idle behavior loop.

        Call this as an async task. Call stop() to terminate.
        Loop runs at 10Hz (100ms intervals).

        Example:
            task = asyncio.create_task(idle.run())
            # ... later ...
            idle.stop()
            await task
        """
        ...

    def stop(self) -> None:
        """Stop the idle behavior loop gracefully."""
        ...

    def pause(self) -> None:
        """Pause idle behaviors (e.g., during triggered animation)."""
        ...

    def resume(self) -> None:
        """Resume idle behaviors after pause."""
        ...

    def is_running(self) -> bool:
        """Check if idle loop is currently running."""
        ...

    def is_paused(self) -> bool:
        """Check if idle behaviors are paused."""
        ...

    def set_blink_interval(self, min_s: float, max_s: float) -> None:
        """
        Set blink interval range.

        Args:
            min_s: Minimum seconds between blinks (must be > 0)
            max_s: Maximum seconds between blinks (must be >= min_s)

        Raises:
            ValueError: If interval values invalid
        """
        ...

    def set_glance_interval(self, min_s: float, max_s: float) -> None:
        """
        Set glance interval range.

        Args:
            min_s: Minimum seconds between glances (must be > 0)
            max_s: Maximum seconds between glances (must be >= min_s)

        Raises:
            ValueError: If interval values invalid
        """
        ...

    async def _do_blink(self) -> None:
        """Perform LED blink via MicroExpressionEngine."""
        ...

    def _do_glance(self) -> None:
        """Perform random head glance via HeadController."""
        ...
```

### 5.2 BlinkBehavior (`src/animation/behaviors.py`)

```python
class BlinkBehavior:
    """
    Eye blink animations for LED rings.

    Provides natural blink animations using MicroExpressionEngine.
    Can also drive eyelid servos if available (future expansion).

    Blink Types:
        - Normal blink: 150ms, 70% dim
        - Slow blink: 400ms, 80% dim (sleepy)
        - Wink: Single eye, 200ms

    Thread Safety:
        Not thread-safe. External synchronization needed.

    Example:
        >>> blink = BlinkBehavior(micro_engine)
        >>> blink.do_blink()
        >>> blink.do_slow_blink()
        >>> blink.do_wink('left')
    """

    # Default timing constants
    NORMAL_BLINK_MS = 150
    SLOW_BLINK_MS = 400
    WINK_MS = 200

    def __init__(
        self,
        micro_engine: 'MicroExpressionEngine',
        animator: Optional['AnimationPlayer'] = None
    ) -> None:
        """
        Initialize blink behavior.

        Args:
            micro_engine: MicroExpressionEngine for LED effects
            animator: Optional AnimationPlayer for servo eyelids
        """
        ...

    @property
    def blink_duration_ms(self) -> int:
        """Current normal blink duration in milliseconds."""
        ...

    def do_blink(self) -> bool:
        """
        Execute normal blink.

        Returns:
            True if blink was triggered
        """
        ...

    def do_slow_blink(self) -> bool:
        """
        Execute slow, sleepy blink.

        Returns:
            True if blink was triggered
        """
        ...

    def do_wink(self, side: str = 'left') -> bool:
        """
        Execute single eye wink.

        Args:
            side: 'left' or 'right'

        Returns:
            True if wink was triggered

        Raises:
            ValueError: If side is not 'left' or 'right'
        """
        ...

    def set_blink_speed(self, multiplier: float) -> None:
        """
        Adjust blink speed based on emotion.

        Args:
            multiplier: Speed multiplier (0.5 = slow, 2.0 = fast)

        Note:
            Called by EmotionBridge when emotion changes.
        """
        ...
```

### 5.3 AnimationCoordinator (`src/animation/coordinator.py`)

```python
"""
Animation Coordinator - Layered animation priority system.

Manages multiple concurrent animation sources:
- Background layer: IdleBehavior (lowest priority)
- Triggered layer: Emotion changes, gestures (medium priority)
- Override layer: Emergency stop, user commands (highest priority)

Design:
    - Higher priority animations interrupt lower priority
    - Smooth blending between layers when possible
    - Thread-safe for concurrent access
"""

from enum import Enum
from dataclasses import dataclass
from typing import Optional, Callable, Dict, Any
import threading


class AnimationLayer(Enum):
    """Animation priority layers."""
    BACKGROUND = 0    # IdleBehavior - lowest priority
    TRIGGERED = 50    # Emotion changes, gestures
    OVERRIDE = 100    # Emergency stop, direct commands


@dataclass
class AnimationState:
    """Current state of animation system."""
    active_layer: AnimationLayer
    background_running: bool
    triggered_animation: Optional[str]
    is_blending: bool
    blend_progress: float


class AnimationCoordinator:
    """
    Coordinates multiple animation layers with priority system.

    Ensures only one animation source controls outputs at a time,
    with smooth transitions between layers when possible.

    Thread Safety:
        All public methods are thread-safe using internal RLock.

    Example:
        >>> coord = AnimationCoordinator(head_ctrl, led_ctrl, micro_engine)
        >>> coord.start_background()  # Start idle behaviors
        >>> coord.trigger_animation('nod', layer=AnimationLayer.TRIGGERED)
        >>> coord.emergency_stop()  # Override everything

    Attributes:
        head_controller: HeadController instance
        led_controller: Optional LED controller
        micro_engine: MicroExpressionEngine instance
        idle_behavior: IdleBehavior for background animations
    """

    def __init__(
        self,
        head_controller: 'HeadController',
        led_controller: Optional['LEDController'] = None,
        micro_engine: Optional['MicroExpressionEngine'] = None
    ) -> None:
        """
        Initialize animation coordinator.

        Args:
            head_controller: HeadController for head movements
            led_controller: Optional LED controller
            micro_engine: Optional MicroExpressionEngine
        """
        ...

    def start_background(self) -> bool:
        """
        Start background idle behaviors.

        Returns:
            True if background layer started
        """
        ...

    def stop_background(self) -> bool:
        """
        Stop background idle behaviors.

        Returns:
            True if background layer was running and stopped
        """
        ...

    def trigger_animation(
        self,
        animation_name: str,
        layer: AnimationLayer = AnimationLayer.TRIGGERED,
        blocking: bool = False,
        **params
    ) -> bool:
        """
        Trigger a named animation.

        Pauses lower-priority layers while animation runs.

        Args:
            animation_name: Name of animation ('nod', 'shake', 'curious', etc.)
            layer: Priority layer for this animation
            blocking: If True, wait for animation to complete
            **params: Animation-specific parameters

        Returns:
            True if animation was triggered

        Raises:
            ValueError: If animation_name is unknown
        """
        ...

    def trigger_emotion(
        self,
        emotion: 'EmotionAxes',
        duration_ms: int = 500,
        blocking: bool = False
    ) -> bool:
        """
        Trigger emotion-driven animation.

        Args:
            emotion: EmotionAxes to express
            duration_ms: Transition duration
            blocking: If True, wait for transition

        Returns:
            True if emotion animation started
        """
        ...

    def emergency_stop(self) -> None:
        """
        Immediately stop all animations.

        OVERRIDE layer - highest priority.
        Stops all layers and head controller.
        """
        ...

    def reset_from_emergency(self) -> bool:
        """
        Clear emergency stop and resume normal operation.

        Returns:
            True if successfully reset
        """
        ...

    def get_state(self) -> AnimationState:
        """Get current animation system state."""
        ...

    def is_animating(self) -> bool:
        """Check if any triggered animation is active."""
        ...

    def wait_for_completion(self, timeout_ms: Optional[int] = None) -> bool:
        """
        Wait for current triggered animation to complete.

        Args:
            timeout_ms: Maximum wait time (None = indefinite)

        Returns:
            True if animation completed, False if timeout
        """
        ...

    def set_on_animation_complete(
        self,
        callback: Optional[Callable[[str], None]]
    ) -> None:
        """
        Set callback for animation completion.

        Args:
            callback: Function called with animation name on completion
        """
        ...
```

### 5.4 EmotionBridge (`src/animation/emotion_bridge.py`)

```python
"""
Emotion Bridge - Maps emotions to coordinated behaviors.

Translates EmotionAxes into:
- Head poses (via HeadController)
- LED patterns and colors (via AxisToLEDMapper)
- Blink speed adjustments (via BlinkBehavior)
- Micro-expressions (via MicroExpressionEngine)

Design Philosophy:
    Separation of concerns - emotion system defines "what to feel",
    EmotionBridge defines "how to express it" through all outputs.
"""

from typing import Optional, Dict, Any, Callable
from dataclasses import dataclass


@dataclass
class EmotionExpression:
    """
    Complete expression configuration for an emotion.

    Bundles all the output parameters derived from EmotionAxes.
    """
    # Head pose
    target_pan: float
    target_tilt: float
    head_duration_ms: int

    # LED configuration
    pattern_name: str
    led_hsv: tuple  # (hue, saturation, value)
    pattern_speed: float

    # Timing
    blink_speed_multiplier: float

    # Micro-expressions to trigger
    micro_expression_preset: Optional[str]


class EmotionBridge:
    """
    Maps emotions to coordinated robot expressions.

    Takes EmotionAxes input and orchestrates all output systems
    to create unified emotional expression.

    Thread Safety:
        Thread-safe for concurrent calls. Uses AnimationCoordinator's
        internal synchronization.

    Example:
        >>> bridge = EmotionBridge(coord, head_ctrl, micro_engine, led_ctrl)
        >>> bridge.express_emotion(EMOTION_PRESETS['happy'], duration_ms=500)
        >>> bridge.transition_to_emotion(EMOTION_PRESETS['sleepy'], duration_ms=2000)

    Emotion to Head Mapping:
        - High arousal -> upward tilt (alert)
        - Low arousal -> downward tilt (sleepy)
        - High focus -> centered, still
        - Positive valence -> slight upward tilt
        - Negative valence -> slight downward tilt

    Emotion to Blink Speed Mapping:
        - Uses EmotionAxes.blink_speed directly
        - Range: 0.25x (sleepy) to 2.0x (anxious)
    """

    def __init__(
        self,
        animation_coordinator: 'AnimationCoordinator',
        head_controller: 'HeadController',
        micro_engine: 'MicroExpressionEngine',
        led_controller: Optional['LEDController'] = None,
        axis_to_led_mapper: Optional['AxisToLEDMapper'] = None
    ) -> None:
        """
        Initialize emotion bridge.

        Args:
            animation_coordinator: For animation layering
            head_controller: For head poses
            micro_engine: For micro-expressions
            led_controller: Optional LED controller
            axis_to_led_mapper: Optional AxisToLEDMapper (creates default if None)
        """
        ...

    def express_emotion(
        self,
        emotion: 'EmotionAxes',
        duration_ms: int = 500,
        blocking: bool = False
    ) -> bool:
        """
        Express an emotion through all output systems.

        Immediately transitions to the new emotion state.

        Args:
            emotion: EmotionAxes to express
            duration_ms: Transition duration for head/LED changes
            blocking: If True, wait for expression to complete

        Returns:
            True if expression started
        """
        ...

    def transition_to_emotion(
        self,
        target_emotion: 'EmotionAxes',
        duration_ms: int = 1000,
        easing: str = 'ease_in_out'
    ) -> bool:
        """
        Smoothly transition from current to target emotion.

        Interpolates between current and target EmotionAxes.

        Args:
            target_emotion: Target EmotionAxes
            duration_ms: Transition duration
            easing: Easing function name

        Returns:
            True if transition started
        """
        ...

    def express_preset(
        self,
        preset_name: str,
        duration_ms: int = 500,
        blocking: bool = False
    ) -> bool:
        """
        Express a preset emotion by name.

        Args:
            preset_name: Name from EMOTION_PRESETS
            duration_ms: Transition duration
            blocking: If True, wait for completion

        Returns:
            True if expression started

        Raises:
            KeyError: If preset_name not found
        """
        ...

    def get_expression_for_emotion(
        self,
        emotion: 'EmotionAxes'
    ) -> EmotionExpression:
        """
        Calculate expression parameters for an emotion.

        Args:
            emotion: EmotionAxes to map

        Returns:
            EmotionExpression with all output parameters
        """
        ...

    def _map_emotion_to_head_pose(
        self,
        emotion: 'EmotionAxes'
    ) -> tuple:
        """
        Map emotion to head pan/tilt angles.

        Mapping Rules:
            Pan: Neutral (focus-dependent micro-movements)
            Tilt:
                - arousal < -0.5 -> -15 degrees (droopy)
                - arousal > 0.5 -> +10 degrees (alert)
                - valence > 0.5 -> +5 degrees (happy lift)
                - valence < -0.5 -> -5 degrees (sad droop)

        Returns:
            (pan, tilt) angles in degrees
        """
        ...

    def _map_emotion_to_micro_expression(
        self,
        emotion: 'EmotionAxes'
    ) -> Optional[str]:
        """
        Select micro-expression preset based on emotion.

        Returns:
            Preset name or None if no micro-expression matches
        """
        ...

    def set_on_emotion_change(
        self,
        callback: Optional[Callable[['EmotionAxes', 'EmotionExpression'], None]]
    ) -> None:
        """
        Set callback for emotion changes.

        Args:
            callback: Function called with (emotion, expression) on change
        """
        ...

    def get_current_emotion(self) -> Optional['EmotionAxes']:
        """Get currently expressed emotion, or None if idle."""
        ...
```

---

## 6. Test Specifications

### 6.1 Test File Structure

```
firmware/tests/
  test_animation/
    __init__.py
    test_behaviors.py          # NEW - IdleBehavior, BlinkBehavior tests
    test_coordinator.py        # NEW - AnimationCoordinator tests
    test_emotion_bridge.py     # NEW - EmotionBridge tests
  test_integration/
    __init__.py
    test_day12_integration.py  # NEW - Full system integration tests
```

### 6.2 test_behaviors.py Specification

```python
"""
Tests for IdleBehavior and BlinkBehavior classes.

Minimum Tests: 15
Coverage Target: 90%
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch


class TestIdleBehaviorInit:
    """Initialization tests (~3 tests)"""

    def test_init_with_valid_controllers(self):
        """IdleBehavior initializes with valid controllers."""
        ...

    def test_init_default_intervals(self):
        """Default blink/glance intervals are reasonable."""
        ...

    def test_init_with_none_led_controller(self):
        """IdleBehavior works without LED controller."""
        ...


class TestIdleBehaviorTimingConfig:
    """Timing configuration tests (~4 tests)"""

    def test_blink_interval_range(self):
        """Blink interval must be 3-5 seconds by default."""
        ...

    def test_glance_interval_range(self):
        """Glance interval must be 5-10 seconds by default."""
        ...

    def test_set_blink_interval_valid(self):
        """set_blink_interval accepts valid range."""
        ...

    def test_set_blink_interval_invalid_raises(self):
        """set_blink_interval rejects invalid range."""
        ...


class TestIdleBehaviorRunLoop:
    """Run loop tests (~4 tests)"""

    @pytest.mark.asyncio
    async def test_run_increments_tick_count(self):
        """Run loop increments tick counter."""
        ...

    @pytest.mark.asyncio
    async def test_run_calls_blink_after_interval(self):
        """Run loop triggers blink after blink interval."""
        ...

    @pytest.mark.asyncio
    async def test_run_calls_glance_after_interval(self):
        """Run loop triggers glance after glance interval."""
        ...

    @pytest.mark.asyncio
    async def test_stop_terminates_loop(self):
        """stop() terminates the run loop."""
        ...


class TestIdleBehaviorPauseResume:
    """Pause/resume tests (~2 tests)"""

    @pytest.mark.asyncio
    async def test_pause_stops_behaviors(self):
        """pause() stops triggering behaviors."""
        ...

    @pytest.mark.asyncio
    async def test_resume_restarts_behaviors(self):
        """resume() restarts triggering behaviors."""
        ...


class TestBlinkBehavior:
    """BlinkBehavior tests (~5 tests)"""

    def test_init_with_micro_engine(self):
        """BlinkBehavior initializes with MicroExpressionEngine."""
        ...

    def test_do_blink_triggers_micro_expression(self):
        """do_blink() triggers BLINK micro-expression."""
        ...

    def test_do_slow_blink_uses_longer_duration(self):
        """do_slow_blink() uses 400ms duration."""
        ...

    def test_do_wink_left(self):
        """do_wink('left') triggers left wink."""
        ...

    def test_do_wink_invalid_side_raises(self):
        """do_wink with invalid side raises ValueError."""
        ...


# Fixtures
@pytest.fixture
def mock_head_controller():
    head = Mock()
    head.random_glance = Mock(return_value=True)
    head.get_state = Mock(return_value=Mock(is_moving=False))
    return head


@pytest.fixture
def mock_micro_engine():
    engine = Mock()
    engine.trigger = Mock(return_value=True)
    engine.trigger_preset = Mock(return_value=True)
    engine.is_active = Mock(return_value=False)
    return engine


@pytest.fixture
def mock_led_controller():
    return Mock()
```

### 6.3 test_coordinator.py Specification

```python
"""
Tests for AnimationCoordinator class.

Minimum Tests: 12
Coverage Target: 90%
"""

class TestAnimationCoordinatorInit:
    """Initialization tests (~2 tests)"""

    def test_init_with_all_controllers(self):
        """Coordinator initializes with all controllers."""
        ...

    def test_init_without_optional_controllers(self):
        """Coordinator works without optional LED controller."""
        ...


class TestAnimationCoordinatorBackground:
    """Background layer tests (~3 tests)"""

    def test_start_background_starts_idle(self):
        """start_background() starts IdleBehavior."""
        ...

    def test_stop_background_stops_idle(self):
        """stop_background() stops IdleBehavior."""
        ...

    def test_background_pauses_during_triggered(self):
        """Background pauses when triggered animation starts."""
        ...


class TestAnimationCoordinatorTrigger:
    """Triggered animation tests (~4 tests)"""

    def test_trigger_animation_known_name(self):
        """trigger_animation() accepts known animation names."""
        ...

    def test_trigger_animation_unknown_raises(self):
        """trigger_animation() raises for unknown names."""
        ...

    def test_trigger_animation_blocking_waits(self):
        """trigger_animation(blocking=True) waits for completion."""
        ...

    def test_trigger_emotion_starts_expression(self):
        """trigger_emotion() starts emotion expression."""
        ...


class TestAnimationCoordinatorPriority:
    """Priority/layer tests (~3 tests)"""

    def test_override_interrupts_triggered(self):
        """OVERRIDE layer interrupts TRIGGERED layer."""
        ...

    def test_triggered_interrupts_background(self):
        """TRIGGERED layer pauses BACKGROUND layer."""
        ...

    def test_emergency_stop_is_highest_priority(self):
        """emergency_stop() overrides everything."""
        ...
```

### 6.4 test_emotion_bridge.py Specification

```python
"""
Tests for EmotionBridge class.

Minimum Tests: 12
Coverage Target: 90%
"""

class TestEmotionBridgeInit:
    """Initialization tests (~2 tests)"""

    def test_init_with_all_components(self):
        """EmotionBridge initializes with all components."""
        ...

    def test_init_creates_default_mapper(self):
        """EmotionBridge creates AxisToLEDMapper if not provided."""
        ...


class TestEmotionBridgeMapping:
    """Emotion mapping tests (~4 tests)"""

    def test_map_happy_emotion_to_upward_tilt(self):
        """Happy emotion maps to slight upward head tilt."""
        ...

    def test_map_sad_emotion_to_downward_tilt(self):
        """Sad emotion maps to downward head tilt."""
        ...

    def test_map_excited_emotion_to_fast_blink(self):
        """Excited emotion maps to fast blink speed."""
        ...

    def test_map_sleepy_emotion_to_slow_blink(self):
        """Sleepy emotion maps to slow blink speed."""
        ...


class TestEmotionBridgeExpress:
    """Expression tests (~4 tests)"""

    def test_express_emotion_calls_head(self):
        """express_emotion() calls HeadController.look_at()."""
        ...

    def test_express_emotion_triggers_led_pattern(self):
        """express_emotion() sets LED pattern via AxisToLEDMapper."""
        ...

    def test_express_preset_uses_preset_dict(self):
        """express_preset() uses EMOTION_PRESETS."""
        ...

    def test_express_preset_unknown_raises(self):
        """express_preset() raises for unknown preset."""
        ...


class TestEmotionBridgeTransition:
    """Transition tests (~2 tests)"""

    def test_transition_interpolates_emotion(self):
        """transition_to_emotion() interpolates between states."""
        ...

    def test_transition_uses_easing(self):
        """transition_to_emotion() applies easing function."""
        ...
```

### 6.5 test_day12_integration.py Specification

```python
"""
Day 12 Integration Tests - Full System Coordination.

Tests the complete pipeline:
- IdleBehavior running in background
- Emotion changes triggering expressions
- Head + LED + MicroExpressions coordinated
- No race conditions under concurrent access

Minimum Tests: 15
"""

import pytest
import asyncio
import threading
import time
from unittest.mock import Mock, patch


class TestIdleSystemIntegration:
    """Test idle system runs correctly."""

    @pytest.mark.asyncio
    async def test_idle_system_runs_without_errors(self):
        """Complete idle system runs for 2 seconds without errors."""
        ...

    @pytest.mark.asyncio
    async def test_idle_blink_triggers_led_effect(self):
        """Idle blink triggers MicroExpressionEngine BLINK."""
        ...

    @pytest.mark.asyncio
    async def test_idle_glance_triggers_head_movement(self):
        """Idle glance triggers HeadController.random_glance()."""
        ...


class TestEmotionExpressionIntegration:
    """Test emotion expression coordination."""

    def test_emotion_change_updates_led(self):
        """Changing emotion updates LED pattern."""
        ...

    def test_emotion_change_updates_head(self):
        """Changing emotion updates head pose."""
        ...

    def test_emotion_change_triggers_micro_expression(self):
        """Changing emotion triggers appropriate micro-expression."""
        ...


class TestCoordinationIntegration:
    """Test animation coordination."""

    @pytest.mark.asyncio
    async def test_triggered_pauses_idle(self):
        """Triggered animation pauses idle behaviors."""
        ...

    @pytest.mark.asyncio
    async def test_idle_resumes_after_triggered(self):
        """Idle behaviors resume after triggered animation completes."""
        ...

    def test_concurrent_head_and_led(self):
        """Head and LED animate concurrently without conflict."""
        ...


class TestThreadSafetyIntegration:
    """Test thread safety under concurrent access."""

    def test_concurrent_emotion_changes(self):
        """Multiple threads can change emotions safely."""
        ...

    def test_concurrent_animation_triggers(self):
        """Multiple threads can trigger animations safely."""
        ...

    def test_emergency_stop_from_any_thread(self):
        """Emergency stop works from any thread."""
        ...


class TestPerformanceIntegration:
    """Test performance requirements."""

    def test_emotion_expression_latency(self):
        """Emotion expression starts within 10ms."""
        ...

    def test_idle_loop_overhead(self):
        """Idle loop overhead is less than 5ms per tick."""
        ...


class TestRapidEmotionChanges:
    """Test handling of rapid changes."""

    def test_rapid_emotion_changes_no_crash(self):
        """Rapid emotion changes don't crash system."""
        ...

    def test_rapid_emotion_changes_smooth_output(self):
        """Rapid emotion changes produce smooth LED output."""
        ...
```

---

## 7. Integration Points

### 7.1 File Locations

```
firmware/
  src/
    animation/
      __init__.py              # Update exports
      behaviors.py             # NEW: IdleBehavior, BlinkBehavior
      coordinator.py           # NEW: AnimationCoordinator
      emotion_bridge.py        # NEW: EmotionBridge
      emotion_axes.py          # EXISTING: EmotionAxes (Day 9)
      axis_to_led.py          # EXISTING: AxisToLEDMapper (Day 9)
      micro_expressions.py    # EXISTING: MicroExpressionEngine (Day 10)
      timing.py               # EXISTING: AnimationSequence/Player
      easing.py               # EXISTING: ease() function
    control/
      head_controller.py      # EXISTING: HeadController (Day 11)
    led/
      color_utils.py          # EXISTING: ColorTransition (Day 11)
  tests/
    test_animation/
      test_behaviors.py       # NEW
      test_coordinator.py     # NEW
      test_emotion_bridge.py  # NEW
    test_integration/
      test_day12_integration.py  # NEW
```

### 7.2 Import Updates

**`src/animation/__init__.py` additions:**
```python
from .behaviors import IdleBehavior, BlinkBehavior
from .coordinator import AnimationCoordinator, AnimationLayer, AnimationState
from .emotion_bridge import EmotionBridge, EmotionExpression
```

### 7.3 Configuration Updates

**`robot_config.yaml` additions:**
```yaml
# =================================================================
# IDLE BEHAVIOR (Day 12)
# =================================================================
idle:
  enabled: true

  blink:
    interval_min_s: 3.0
    interval_max_s: 5.0
    duration_ms: 150

  glance:
    interval_min_s: 5.0
    interval_max_s: 10.0
    max_deviation: 30.0
    hold_ms: 500

# =================================================================
# EMOTION BRIDGE (Day 12)
# =================================================================
emotion_bridge:
  head_mapping:
    arousal_tilt_scale: 15.0    # degrees per arousal unit
    valence_tilt_scale: 5.0     # degrees per valence unit

  blink_speed:
    min_multiplier: 0.25
    max_multiplier: 2.0
```

---

## 8. Agent Assignments

### 8.1 Agent Allocation

| Agent | Module | Deliverables |
|-------|--------|--------------|
| **Agent 1** | IdleBehavior | `behaviors.py` (IdleBehavior class), `test_behaviors.py` (IdleBehavior tests) |
| **Agent 2** | BlinkBehavior | `behaviors.py` (BlinkBehavior class), `test_behaviors.py` (BlinkBehavior tests) |
| **Agent 3** | AnimationCoordinator | `coordinator.py`, `test_coordinator.py` |
| **Agent 4** | EmotionBridge | `emotion_bridge.py`, `test_emotion_bridge.py` |
| **Agent 5** | Integration Tests | `test_day12_integration.py`, system validation |

### 8.2 Implementation Order

```
Phase 1 (Parallel):
  - Agent 1: IdleBehavior (no dependencies on new code)
  - Agent 2: BlinkBehavior (depends only on existing MicroExpressionEngine)

Phase 2 (Sequential):
  - Agent 3: AnimationCoordinator (depends on IdleBehavior)

Phase 3 (Sequential):
  - Agent 4: EmotionBridge (depends on AnimationCoordinator)

Phase 4 (Final):
  - Agent 5: Integration Tests (depends on all modules)
```

### 8.3 Agent-Specific Notes

**Agent 1 (IdleBehavior):**
- Use `asyncio` for the run loop
- 10Hz tick rate (100ms sleep)
- Call existing `MicroExpressionEngine.trigger_preset('blink_normal')` for blinks
- Call existing `HeadController.random_glance()` for glances

**Agent 2 (BlinkBehavior):**
- Use existing `MicroExpressionEngine` for LED effects
- Map blink types to micro-expression presets:
  - Normal blink: `'blink_normal'`
  - Slow blink: `'blink_slow'`
- Wink needs custom implementation (left/right eye differentiation)

**Agent 3 (AnimationCoordinator):**
- Use `threading.RLock` for thread safety
- Create internal `IdleBehavior` instance
- Manage async task lifecycle for idle loop

**Agent 4 (EmotionBridge):**
- Use existing `AxisToLEDMapper` for LED mappings
- Calculate head poses from EmotionAxes using documented formulas
- Coordinate all outputs through `AnimationCoordinator`

**Agent 5 (Integration Tests):**
- Follow patterns from `test_day9_integration.py`
- Include performance benchmarks
- Test thread safety with concurrent access

---

## 9. Success Criteria

### 9.1 Minimum Requirements

| Criterion | Target | Measurement |
|-----------|--------|-------------|
| New modules | 4 files | `behaviors.py`, `coordinator.py`, `emotion_bridge.py`, `test_day12_integration.py` |
| New tests | 55+ | Combined from all test files |
| Test coverage | 90% | For new modules |
| All tests passing | 100% | `pytest -v` |
| CHANGELOG updated | Yes | Day 12 entry complete |

### 9.2 Quality Gates

**Before marking Day 12 complete:**

1. [ ] All 55+ new tests passing
2. [ ] No regressions in existing tests (650+ total)
3. [ ] Idle system runs for 60 seconds without errors
4. [ ] Emotion changes trigger coordinated expressions
5. [ ] No race conditions under concurrent access test
6. [ ] Thread safety verified with concurrent tests
7. [ ] Performance: <10ms emotion expression latency
8. [ ] CHANGELOG.md updated with all tasks

### 9.3 Integration Verification Commands

```bash
# Run all Day 12 tests
cd firmware
pytest tests/test_animation/test_behaviors.py -v
pytest tests/test_animation/test_coordinator.py -v
pytest tests/test_animation/test_emotion_bridge.py -v
pytest tests/test_integration/test_day12_integration.py -v

# Run full test suite (should pass 700+ tests)
pytest -v

# Check test coverage
pytest --cov=src/animation --cov-report=term-missing tests/test_animation/

# Run performance benchmark
python tests/test_integration/test_day12_integration.py
```

---

## Appendix A: Existing Pattern Examples

### A.1 Async Task Pattern (from timing.py)

```python
async def run(self):
    """Run loop pattern used in existing code."""
    self._running = True
    while self._running:
        # ... tick logic ...
        await asyncio.sleep(0.1)  # 10Hz
```

### A.2 Thread Safety Pattern (from head_controller.py)

```python
def __init__(self):
    self._lock = threading.RLock()

def look_at(self, pan, tilt, ...):
    with self._lock:
        # ... protected code ...
```

### A.3 Dataclass Validation Pattern (from emotion_axes.py)

```python
@dataclass
class Config:
    value: float

    def __post_init__(self):
        if not 0.0 <= self.value <= 1.0:
            raise ValueError(f"value must be 0.0-1.0, got {self.value}")
```

---

## Appendix B: Test Fixture Patterns

### B.1 Mock Controller Fixture

```python
@pytest.fixture
def mock_head_controller():
    head = Mock()
    head.random_glance = Mock(return_value=True)
    head.look_at = Mock(return_value=True)
    head.get_state = Mock(return_value=Mock(is_moving=False, pan=0, tilt=0))
    head.emergency_stop = Mock()
    return head
```

### B.2 Async Test Pattern

```python
@pytest.mark.asyncio
async def test_async_behavior():
    behavior = IdleBehavior(mock_head, mock_engine, mock_led)
    task = asyncio.create_task(behavior.run())

    await asyncio.sleep(0.2)  # Let it run

    behavior.stop()
    await task  # Wait for clean exit

    assert behavior._tick_count > 0
```

---

**End of Architecture Specification**

*This document defines contracts only. Implementation is delegated to specialized agents.*

---

**Document Control:**
- Version 1.0: Initial specification (18 Jan 2026)
- Review Required: Before implementation begins
- Approval: Chief Architect (Agent 0)
