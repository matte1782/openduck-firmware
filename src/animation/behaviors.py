#!/usr/bin/env python3
"""
Idle and Blink Behaviors - OpenDuck Mini V3
Day 12: Background Personality System

Implements Disney's principle: "Even when waiting, characters are alive."

This module provides background behaviors that give the robot personality
when idle, including automatic blinking and random glances. Based on
NAO/Aldebaran idle behavior patterns and Pixar animation principles.

Research Foundation:
    - NAO/Aldebaran Robotics: Idle behavior patterns
    - Disney 12 Principles: Secondary Action, Appeal, Timing
    - Anki Cozmo: Continuous subtle behaviors
    - Boston Dynamics Spot: Background motion system

Classes:
    IdleBehavior: Background idle behaviors (blinks, glances)
    BlinkBehavior: Eye blink animations using LED dimming

Author: Agent 2 - NAO/Aldebaran Behavior Developer
Created: 18 January 2026 (Day 12)
Quality Standard: Pixar / Disney Animation Grade
"""

from typing import Optional, Callable, TYPE_CHECKING
import asyncio
import random
import time
import logging

from .micro_expressions import (
    MicroExpressionEngine,
    MicroExpressionType,
    MICRO_EXPRESSION_PRESETS,
)

# Type checking imports to avoid circular dependencies
if TYPE_CHECKING:
    from ..control.head_controller import HeadController

# Logger for this module
_logger = logging.getLogger(__name__)


# =============================================================================
# CONSTANTS
# =============================================================================

# Idle behavior timing defaults (in seconds)
DEFAULT_BLINK_INTERVAL_MIN = 3.0
DEFAULT_BLINK_INTERVAL_MAX = 5.0
DEFAULT_GLANCE_INTERVAL_MIN = 5.0
DEFAULT_GLANCE_INTERVAL_MAX = 10.0

# Loop timing
IDLE_LOOP_TICK_RATE_HZ = 10  # 10Hz = 100ms per tick
IDLE_LOOP_TICK_S = 1.0 / IDLE_LOOP_TICK_RATE_HZ

# Blink timing defaults (in milliseconds)
NORMAL_BLINK_MS = 150
SLOW_BLINK_MS = 400
WINK_MS = 200
DOUBLE_BLINK_GAP_MS = 100


# =============================================================================
# IDLE BEHAVIOR CLASS
# =============================================================================

class IdleBehavior:
    """
    Background idle behaviors that give the robot personality.

    Runs blinks, glances, and subtle movements when robot is idle.
    Implements Disney's principle that characters are never truly still.

    Disney Animation Principles Applied:
    ------------------------------------
    - SECONDARY ACTION: Small supporting movements enhance life
    - APPEAL: Natural variation makes robot endearing
    - TIMING: Appropriate intervals feel natural, not mechanical

    NAO/Aldebaran Pattern Reference:
    --------------------------------
    - Automatic blinking (3-5 second intervals)
    - Random glances (5-10 second intervals)
    - Breathing/subtle movement (optional, future expansion)

    Thread Safety:
        FIX H-NEW-002: Explicitly documented threading model.
        This class is designed for single-threaded async operation.
        The async run() method, pause(), resume(), and stop() methods
        MUST be called from the same event loop / thread.

        AnimationCoordinator should call IdleBehavior methods from its
        coordination thread only. If multiple threads need access,
        wrap calls in external synchronization (e.g., asyncio.run_coroutine_threadsafe).

    Example:
        >>> from src.animation.behaviors import IdleBehavior
        >>> idle = IdleBehavior(head_controller, micro_engine, led_controller)
        >>> task = asyncio.create_task(idle.run())
        >>> # Later...
        >>> idle.stop()
        >>> await task

    Attributes:
        head: HeadController instance for head movements (can be None)
        micro_engine: MicroExpressionEngine for LED effects (can be None)
        led_controller: Optional LED controller for direct LED control
    """

    def __init__(
        self,
        head_controller: Optional['HeadController'] = None,
        micro_engine: Optional[MicroExpressionEngine] = None,
        led_controller: Optional[object] = None,
        blink_interval_min: float = DEFAULT_BLINK_INTERVAL_MIN,
        blink_interval_max: float = DEFAULT_BLINK_INTERVAL_MAX,
        glance_interval_min: float = DEFAULT_GLANCE_INTERVAL_MIN,
        glance_interval_max: float = DEFAULT_GLANCE_INTERVAL_MAX
    ) -> None:
        """
        Initialize idle behavior system.

        Controllers can be None for testing without hardware.

        Args:
            head_controller: HeadController for head movements (can be None)
            micro_engine: MicroExpressionEngine for LED blink effects (can be None)
            led_controller: Optional direct LED controller (can be None)
            blink_interval_min: Minimum seconds between blinks (default 3.0)
            blink_interval_max: Maximum seconds between blinks (default 5.0)
            glance_interval_min: Minimum seconds between glances (default 5.0)
            glance_interval_max: Maximum seconds between glances (default 10.0)
        """
        # Store controllers (can be None for testing)
        self._head = head_controller
        self._micro_engine = micro_engine
        self._led_controller = led_controller

        # Timing configuration (in seconds)
        self._blink_interval_min: float = blink_interval_min
        self._blink_interval_max: float = blink_interval_max
        self._glance_interval_min: float = glance_interval_min
        self._glance_interval_max: float = glance_interval_max

        # State tracking
        self._running: bool = False
        self._paused: bool = False
        self._tick_count: int = 0

        # Random number generator (can be seeded for testing)
        # MUST be initialized before _schedule_next_* calls
        self._rng = random.Random()

        # Next action timing (absolute time in seconds)
        self._next_blink_time: float = 0.0
        self._next_glance_time: float = 0.0

        # Initialize random timers
        self._schedule_next_blink()
        self._schedule_next_glance()

        _logger.debug("IdleBehavior initialized")

    # =========================================================================
    # PROPERTIES - Timing Configuration
    # =========================================================================

    @property
    def blink_interval_min(self) -> float:
        """Minimum seconds between blinks (default 3.0)."""
        return self._blink_interval_min

    @property
    def blink_interval_max(self) -> float:
        """Maximum seconds between blinks (default 5.0)."""
        return self._blink_interval_max

    @property
    def glance_interval_min(self) -> float:
        """Minimum seconds between glances (default 5.0)."""
        return self._glance_interval_min

    @property
    def glance_interval_max(self) -> float:
        """Maximum seconds between glances (default 10.0)."""
        return self._glance_interval_max

    @property
    def head(self) -> Optional['HeadController']:
        """HeadController instance (may be None)."""
        return self._head

    @property
    def micro_engine(self) -> Optional[MicroExpressionEngine]:
        """MicroExpressionEngine instance (may be None)."""
        return self._micro_engine

    @property
    def led_controller(self) -> Optional[object]:
        """LED controller instance (may be None)."""
        return self._led_controller

    # =========================================================================
    # PUBLIC METHODS - Main Loop Control
    # =========================================================================

    async def run(self) -> None:
        """
        Main idle behavior loop.

        Call this as an async task. Call stop() to terminate.
        Loop runs at 10Hz (100ms intervals).

        Example:
            >>> task = asyncio.create_task(idle.run())
            >>> # ... later ...
            >>> idle.stop()
            >>> await task
        """
        self._running = True
        self._tick_count = 0
        _logger.info("IdleBehavior loop started")

        try:
            while self._running:
                # Tick timing
                tick_start = time.monotonic()
                self._tick_count += 1

                # Skip behaviors if paused
                if not self._paused:
                    current_time = time.monotonic()

                    # Check if it's time to blink
                    if current_time >= self._next_blink_time:
                        await self._do_blink()
                        self._schedule_next_blink()

                    # Check if it's time to glance
                    if current_time >= self._next_glance_time:
                        self._do_glance()
                        self._schedule_next_glance()

                # Maintain 10Hz tick rate
                elapsed = time.monotonic() - tick_start
                sleep_time = IDLE_LOOP_TICK_S - elapsed
                if sleep_time > 0:
                    await asyncio.sleep(sleep_time)
                else:
                    # Tick overrun - still yield to other tasks
                    await asyncio.sleep(0)

        except asyncio.CancelledError:
            _logger.info("IdleBehavior loop cancelled")
            raise
        finally:
            self._running = False
            _logger.info("IdleBehavior loop stopped")

    def stop(self) -> None:
        """
        Stop the idle behavior loop gracefully.

        Sets the running flag to False; the loop will exit on next tick.
        """
        self._running = False
        _logger.debug("IdleBehavior stop requested")

    def pause(self) -> None:
        """
        Pause idle behaviors temporarily.

        Use this during triggered animations to prevent interference.
        The loop continues running but skips blink/glance triggers.
        """
        self._paused = True
        _logger.debug("IdleBehavior paused")

    def resume(self) -> None:
        """
        Resume idle behaviors after pause.

        Reschedules next blink and glance to avoid immediate triggers.
        """
        self._paused = False
        # Reschedule to avoid immediate trigger after resume
        self._schedule_next_blink()
        self._schedule_next_glance()
        _logger.debug("IdleBehavior resumed")

    # =========================================================================
    # PUBLIC METHODS - State Query
    # =========================================================================

    def is_running(self) -> bool:
        """Check if idle loop is currently running."""
        return self._running

    def is_paused(self) -> bool:
        """Check if idle behaviors are paused."""
        return self._paused

    def get_tick_count(self) -> int:
        """Get number of ticks since loop started (for testing)."""
        return self._tick_count

    # =========================================================================
    # PUBLIC METHODS - Configuration
    # =========================================================================

    def set_blink_interval(self, min_s: float, max_s: float) -> None:
        """
        Set blink interval range.

        Args:
            min_s: Minimum seconds between blinks (must be > 0)
            max_s: Maximum seconds between blinks (must be >= min_s)

        Raises:
            ValueError: If interval values invalid
        """
        if min_s <= 0:
            raise ValueError(f"min_s must be > 0, got {min_s}")
        if max_s < min_s:
            raise ValueError(f"max_s ({max_s}) must be >= min_s ({min_s})")

        self._blink_interval_min = min_s
        self._blink_interval_max = max_s
        _logger.debug(f"Blink interval set to {min_s}-{max_s}s")

    def set_glance_interval(self, min_s: float, max_s: float) -> None:
        """
        Set glance interval range.

        Args:
            min_s: Minimum seconds between glances (must be > 0)
            max_s: Maximum seconds between glances (must be >= min_s)

        Raises:
            ValueError: If interval values invalid
        """
        if min_s <= 0:
            raise ValueError(f"min_s must be > 0, got {min_s}")
        if max_s < min_s:
            raise ValueError(f"max_s ({max_s}) must be >= min_s ({min_s})")

        self._glance_interval_min = min_s
        self._glance_interval_max = max_s
        _logger.debug(f"Glance interval set to {min_s}-{max_s}s")

    def seed_rng(self, seed: int) -> None:
        """
        Seed the random number generator for reproducible tests.

        Args:
            seed: Random seed value
        """
        self._rng.seed(seed)

    # =========================================================================
    # PRIVATE METHODS - Behavior Triggers
    # =========================================================================

    async def _do_blink(self) -> None:
        """
        Perform LED blink via MicroExpressionEngine.

        Uses the 'blink_normal' preset for natural eye blink animation.
        """
        if self._micro_engine is None:
            _logger.debug("Blink triggered (no micro_engine)")
            return

        try:
            # Trigger blink via MicroExpressionEngine
            success = self._micro_engine.trigger_preset('blink_normal')
            if success:
                _logger.debug("Blink triggered via MicroExpressionEngine")
            else:
                _logger.debug("Blink blocked by cooldown")
        except Exception as e:
            _logger.warning(f"Blink trigger failed: {e}")

    def _do_glance(self) -> None:
        """
        Perform random head glance via HeadController.

        Uses HeadController.random_glance() for natural looking behavior.
        """
        if self._head is None:
            _logger.debug("Glance triggered (no head_controller)")
            return

        try:
            # Use existing random_glance method (non-blocking)
            success = self._head.random_glance(
                max_deviation=30.0,
                hold_ms=500,
                blocking=False
            )
            if success:
                _logger.debug("Glance triggered via HeadController")
            else:
                _logger.debug("Glance failed (head busy or emergency stop)")
        except Exception as e:
            _logger.warning(f"Glance trigger failed: {e}")

    # =========================================================================
    # PRIVATE METHODS - Timing Scheduling
    # =========================================================================

    def _get_next_blink_interval(self) -> float:
        """Get random interval for next blink (for testing/external use)."""
        return self._rng.uniform(
            self._blink_interval_min,
            self._blink_interval_max
        )

    def _get_next_glance_interval(self) -> float:
        """Get random interval for next glance (for testing/external use)."""
        return self._rng.uniform(
            self._glance_interval_min,
            self._glance_interval_max
        )

    def _schedule_next_blink(self) -> None:
        """Schedule the next blink at a random future time."""
        interval = self._get_next_blink_interval()
        self._next_blink_time = time.monotonic() + interval

    def _schedule_next_glance(self) -> None:
        """Schedule the next glance at a random future time."""
        interval = self._get_next_glance_interval()
        self._next_glance_time = time.monotonic() + interval


# =============================================================================
# BLINK BEHAVIOR CLASS
# =============================================================================

class BlinkBehavior:
    """
    Eye blink animations using eyelid servos or LED dimming.

    Provides natural blink animations using MicroExpressionEngine.
    Can also drive eyelid servos if available (future expansion).

    Blink Types:
        - Normal blink: 150ms, 70% dim
        - Slow blink: 400ms, 80% dim (sleepy)
        - Wink: Single eye, 200ms
        - Double blink: Two quick blinks (surprised)

    Thread Safety:
        Not thread-safe. External synchronization needed.

    Example:
        >>> blink = BlinkBehavior(micro_engine)
        >>> blink.do_blink()        # Normal blink
        >>> blink.do_slow_blink()   # Sleepy slow blink
        >>> blink.do_wink('left')   # Single eye wink

    Disney Principles Applied:
    --------------------------
    - TIMING: Blink duration conveys emotion (fast=alert, slow=sleepy)
    - SECONDARY ACTION: Blinks support primary emotion
    - APPEAL: Natural variation in blink patterns
    """

    # Default timing constants (milliseconds)
    NORMAL_BLINK_MS = NORMAL_BLINK_MS
    SLOW_BLINK_MS = SLOW_BLINK_MS
    WINK_MS = WINK_MS
    DOUBLE_BLINK_GAP_MS = DOUBLE_BLINK_GAP_MS

    def __init__(
        self,
        micro_engine: Optional[MicroExpressionEngine] = None,
        animator: Optional[object] = None,
        eyelid_controller: Optional[object] = None,
        led_controller: Optional[object] = None
    ) -> None:
        """
        Initialize blink behavior.

        Can use LEDs (via MicroExpressionEngine) or servo eyelids.
        Controllers can be None for testing.

        Args:
            micro_engine: MicroExpressionEngine for LED effects (can be None)
            animator: Optional AnimationPlayer for servo eyelids (alias for eyelid_controller)
            eyelid_controller: Optional servo controller for physical eyelids
            led_controller: Optional LED controller for direct LED control
        """
        self._micro_engine = micro_engine
        # animator is an alias for eyelid_controller for API compatibility
        self._animator = animator if animator is not None else eyelid_controller
        self._eyelid_controller = eyelid_controller
        self._led_controller = led_controller

        # Blink speed multiplier (adjusted by emotion)
        self._speed_multiplier: float = 1.0

        # Current blink durations (can be modified)
        self._normal_blink_ms: int = self.NORMAL_BLINK_MS
        self._slow_blink_ms: int = self.SLOW_BLINK_MS
        self._wink_ms: int = self.WINK_MS

        _logger.debug("BlinkBehavior initialized")

    # =========================================================================
    # PROPERTIES
    # =========================================================================

    @property
    def micro_engine(self) -> Optional[MicroExpressionEngine]:
        """MicroExpressionEngine instance (may be None)."""
        return self._micro_engine

    @property
    def animator(self) -> Optional[object]:
        """AnimationPlayer instance for servo eyelids (may be None)."""
        return self._animator

    @property
    def blink_duration_ms(self) -> int:
        """Current normal blink duration in milliseconds."""
        return int(self._normal_blink_ms / self._speed_multiplier)

    @property
    def slow_blink_duration_ms(self) -> int:
        """Current slow blink duration in milliseconds."""
        return int(self._slow_blink_ms / self._speed_multiplier)

    @property
    def wink_duration_ms(self) -> int:
        """Current wink duration in milliseconds."""
        return int(self._wink_ms / self._speed_multiplier)

    # =========================================================================
    # PUBLIC METHODS - Blink Actions
    # =========================================================================

    def do_blink(self) -> bool:
        """
        Execute normal blink.

        Normal blink is ~150ms duration with 70% brightness dim.
        Uses MicroExpressionEngine 'blink_normal' preset.

        Returns:
            True if blink was triggered successfully
        """
        if self._micro_engine is None:
            _logger.debug("Blink executed (no micro_engine)")
            return True

        try:
            # Use preset for consistent behavior
            success = self._micro_engine.trigger_preset('blink_normal', force=True)
            _logger.debug(f"Normal blink triggered: {success}")
            return success
        except Exception as e:
            _logger.warning(f"Normal blink failed: {e}")
            return False

    def do_slow_blink(self) -> bool:
        """
        Execute slow, sleepy blink.

        Slow blink is ~400ms duration with 80% brightness dim.
        Conveys tiredness or contentment.

        Returns:
            True if blink was triggered successfully
        """
        if self._micro_engine is None:
            _logger.debug("Slow blink executed (no micro_engine)")
            return True

        try:
            # Use slow blink preset
            success = self._micro_engine.trigger_preset('blink_slow', force=True)
            _logger.debug(f"Slow blink triggered: {success}")
            return success
        except Exception as e:
            _logger.warning(f"Slow blink failed: {e}")
            return False

    def do_wink(self, side: str = 'left') -> bool:
        """
        Execute single eye wink.

        Winks one eye while keeping the other open.
        Playful, mischievous expression.

        Args:
            side: 'left' or 'right' eye to wink

        Returns:
            True if wink was triggered successfully

        Raises:
            ValueError: If side is not 'left' or 'right'
        """
        if side not in ('left', 'right'):
            raise ValueError(f"side must be 'left' or 'right', got '{side}'")

        if self._micro_engine is None:
            _logger.debug(f"Wink ({side}) executed (no micro_engine)")
            return True

        try:
            # Use glance preset as base for asymmetric effect
            # Wink = strong glance to one side
            preset_name = f'glance_{side}'
            success = self._micro_engine.trigger_preset(preset_name, force=True)
            _logger.debug(f"Wink ({side}) triggered: {success}")
            return success
        except KeyError:
            # Fallback: use manual trigger with glance type
            try:
                success = self._micro_engine.trigger(
                    MicroExpressionType.GLANCE,
                    duration_ms=self._wink_ms,
                    intensity=0.8,
                    force=True
                )
                _logger.debug(f"Wink ({side}) triggered via manual: {success}")
                return success
            except Exception as e:
                _logger.warning(f"Wink trigger failed: {e}")
                return False
        except Exception as e:
            _logger.warning(f"Wink trigger failed: {e}")
            return False

    async def do_double_blink(self) -> bool:
        """
        Execute two quick blinks in succession (surprised expression).

        Double blink conveys surprise or disbelief.
        Uses rapid blink preset if available.

        Returns:
            True if double blink was triggered successfully
        """
        if self._micro_engine is None:
            _logger.debug("Double blink executed (no micro_engine)")
            return True

        try:
            # First blink
            success1 = self._micro_engine.trigger_preset('blink_rapid', force=True)

            # Wait for first blink to complete + gap
            await asyncio.sleep(
                (MICRO_EXPRESSION_PRESETS['blink_rapid'].duration_ms +
                 self.DOUBLE_BLINK_GAP_MS) / 1000.0
            )

            # Second blink
            success2 = self._micro_engine.trigger_preset('blink_rapid', force=True)

            success = success1 and success2
            _logger.debug(f"Double blink triggered: {success}")
            return success
        except Exception as e:
            _logger.warning(f"Double blink failed: {e}")
            return False

    # =========================================================================
    # PUBLIC METHODS - Configuration
    # =========================================================================

    def set_blink_speed(self, multiplier: float) -> None:
        """
        Adjust blink speed based on emotion.

        Higher multiplier = faster blinks (excited, alert)
        Lower multiplier = slower blinks (sleepy, relaxed)

        Args:
            multiplier: Speed multiplier (0.25 = slow, 2.0 = fast)
                       Clamped to range [0.25, 4.0]

        Note:
            Called by EmotionBridge when emotion changes.
        """
        # Clamp to reasonable range
        multiplier = max(0.25, min(4.0, multiplier))
        self._speed_multiplier = multiplier
        _logger.debug(f"Blink speed multiplier set to {multiplier}")

    def reset_blink_speed(self) -> None:
        """Reset blink speed multiplier to default (1.0)."""
        self._speed_multiplier = 1.0
        _logger.debug("Blink speed multiplier reset to 1.0")


# =============================================================================
# MODULE-LEVEL FUNCTIONS
# =============================================================================

def create_idle_behavior(
    head_controller: Optional['HeadController'] = None,
    micro_engine: Optional[MicroExpressionEngine] = None,
    led_controller: Optional[object] = None,
    blink_interval: tuple = (3.0, 5.0),
    glance_interval: tuple = (5.0, 10.0)
) -> IdleBehavior:
    """
    Factory function to create configured IdleBehavior.

    Args:
        head_controller: HeadController for head movements
        micro_engine: MicroExpressionEngine for LED effects
        led_controller: Optional LED controller
        blink_interval: (min, max) seconds between blinks
        glance_interval: (min, max) seconds between glances

    Returns:
        Configured IdleBehavior instance
    """
    idle = IdleBehavior(head_controller, micro_engine, led_controller)
    idle.set_blink_interval(*blink_interval)
    idle.set_glance_interval(*glance_interval)
    return idle


def create_blink_behavior(
    micro_engine: Optional[MicroExpressionEngine] = None,
    eyelid_controller: Optional[object] = None
) -> BlinkBehavior:
    """
    Factory function to create configured BlinkBehavior.

    Args:
        micro_engine: MicroExpressionEngine for LED effects
        eyelid_controller: Optional servo controller for physical eyelids

    Returns:
        Configured BlinkBehavior instance
    """
    return BlinkBehavior(micro_engine, eyelid_controller)
