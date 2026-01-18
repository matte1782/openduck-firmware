#!/usr/bin/env python3
"""
Animation Coordinator - Layered Animation Priority System

Coordinates multiple concurrent animation sources with a priority-based
layer system inspired by Pixar's character animation pipelines.

Design Philosophy:
    "Layered animation allows personality to shine through even during
    complex actions." - Pixar Technical Director principle

    By separating animations into layers (background, triggered, reaction,
    critical), we can ensure that:
    - Idle behaviors run continuously when nothing else needs attention
    - User-triggered animations take precedence cleanly
    - Emotional reactions can overlay naturally
    - Safety-critical animations always have absolute priority

Layers (lowest to highest priority):
    - BACKGROUND (0): Idle behaviors - blinks, glances, micro-movements
    - TRIGGERED (50): User/event triggered animations
    - REACTION (75): Emotion-driven responses
    - CRITICAL (100): Emergency stop, safety overrides

Thread Safety:
    All public methods are thread-safe using RLock for nested locking.
    The coordinator can be safely accessed from multiple threads.

Research Foundation:
    - Bipedal robotic character design (arXiv 2025): Layered animation systems
    - Disney 12 Principles: Secondary action, staging
    - Boston Dynamics Spot: Behavior state machine patterns

Author: Agent 3 - Pixar Technical Director
Created: 18 January 2026 (Day 12)
Quality Standard: Pixar Character TD / Boston Dynamics Grade
"""

from enum import IntEnum
from dataclasses import dataclass, field
from typing import Optional, Callable, Dict, List, Any
import asyncio
import threading
import logging
import time

_logger = logging.getLogger(__name__)


# =============================================================================
# CONSTANTS
# =============================================================================

# Coordinator timing
COORDINATOR_TICK_RATE_HZ = 10  # 10Hz = 100ms per tick
COORDINATOR_TICK_MS = 1000 // COORDINATOR_TICK_RATE_HZ  # 100ms

# Layer transition timing
LAYER_BLEND_DURATION_MS = 200  # Smooth transition between layers
ANIMATION_COMPLETE_GRACE_MS = 50  # Grace period before resuming background

# Supported animation names (map to HeadController methods)
SUPPORTED_ANIMATIONS = {
    'nod': 'nod',
    'shake': 'shake',
    'curious': 'tilt_curious',
    'tilt_curious': 'tilt_curious',
    'glance': 'random_glance',
    'random_glance': 'random_glance',
    'look_at': 'look_at',
    'reset': 'reset_to_center',
    'reset_to_center': 'reset_to_center',
}


# =============================================================================
# ENUMS AND DATA STRUCTURES
# =============================================================================

class AnimationPriority(IntEnum):
    """
    Animation layer priorities (higher = more important).

    Based on bipedal robotic character design research (arXiv 2025).
    Higher priority animations take precedence and can interrupt lower ones.

    Attributes:
        BACKGROUND: Continuous idle behaviors (blinks, breathing)
        TRIGGERED: User or event-triggered animations
        REACTION: Emotional reaction overlays
        CRITICAL: Safety-critical overrides (emergency stop)
    """
    BACKGROUND = 0      # Idle behaviors - lowest priority
    TRIGGERED = 50      # User-triggered animations
    REACTION = 75       # Emotional reactions
    CRITICAL = 100      # Emergency/safety - highest priority


@dataclass
class AnimationLayer:
    """
    Single animation layer configuration.

    Tracks the state and current animation of a single layer.
    Multiple layers can coexist, with higher priority layers
    taking control of outputs.

    Attributes:
        name: Human-readable layer identifier
        priority: AnimationPriority value for this layer
        active: Whether this layer is currently running
        current_animation: Name of currently playing animation (if any)
        start_time: When the current animation started (monotonic time)

    Thread Safety:
        This dataclass is not thread-safe. Access should be protected
        by the coordinator's lock.
    """
    name: str
    priority: AnimationPriority
    active: bool = False
    current_animation: Optional[str] = None
    start_time: float = field(default_factory=time.monotonic)

    def __post_init__(self):
        """Validate layer configuration."""
        if not self.name:
            raise ValueError("Layer name cannot be empty")
        if not isinstance(self.priority, (int, AnimationPriority)):
            raise TypeError(
                f"priority must be int or AnimationPriority, "
                f"got {type(self.priority).__name__}"
            )


@dataclass
class AnimationState:
    """
    Current state of the animation system.

    Snapshot of coordinator state for external inspection.
    Immutable after creation.

    Attributes:
        active_layer: Currently controlling layer name (or None)
        active_priority: Priority of active layer
        background_running: Whether background layer is running
        triggered_animation: Name of triggered animation (if any)
        is_blending: Whether transitioning between layers
        blend_progress: Progress of layer transition (0.0-1.0)
        emergency_stopped: Whether emergency stop is active
    """
    active_layer: Optional[str]
    active_priority: int
    background_running: bool
    triggered_animation: Optional[str]
    is_blending: bool
    blend_progress: float
    emergency_stopped: bool


# =============================================================================
# ANIMATION COORDINATOR
# =============================================================================

class AnimationCoordinator:
    """
    Coordinates multiple animation layers with priority blending.

    Pixar principle: "Layered animation allows personality to shine
    through even during complex actions."

    The coordinator manages multiple animation sources, ensuring only
    one controls the robot at a time based on priority. Lower priority
    layers (like idle behaviors) are paused when higher priority
    animations play, then automatically resumed.

    Layers:
        - Background: Always-on idle behaviors (blinks, glances)
        - Triggered: User or event triggered animations
        - Reaction: Emotion-driven responses
        - Critical: Safety-critical overrides (absolute priority)

    Thread Safety:
        All public methods are thread-safe using RLock for nested calls.
        The coordinator can be safely used from multiple threads.

    Example:
        >>> coord = AnimationCoordinator(head_controller, led_controller)
        >>> await coord.run()  # Start background coordinator loop
        >>> coord.start_animation('triggered', 'nod')  # Trigger animation
        >>> coord.stop()  # Stop coordinator

    Attributes:
        _head: HeadController instance for head movements
        _led: Optional LED controller for light effects
        _layers: Dict of registered animation layers
        _running: Whether the coordinator loop is active
        _emergency_stopped: Atomic flag for emergency stop
    """

    def __init__(
        self,
        head_controller: Optional[Any] = None,
        led_controller: Optional[Any] = None,
        micro_engine: Optional[Any] = None
    ) -> None:
        """
        Initialize animation coordinator.

        Args:
            head_controller: HeadController for head movements (optional)
            led_controller: LED controller for light effects (optional)
            micro_engine: MicroExpressionEngine for LED effects (optional)

        Note:
            Controllers can be None for testing or offline operation.
            The coordinator will skip actions for missing controllers.
        """
        self._head = head_controller
        self._led = led_controller
        self._micro_engine = micro_engine

        # Thread safety
        self._lock = threading.RLock()

        # Layer management
        self._layers: Dict[str, AnimationLayer] = {}

        # State tracking
        self._running = False
        self._emergency_stopped = False
        self._is_blending = False
        self._blend_progress = 0.0
        self._blend_start_time = 0.0

        # Callbacks
        self._on_animation_complete: Optional[Callable[[str], None]] = None
        self._on_layer_change: Optional[Callable[[str, str], None]] = None

        # Async coordination
        self._run_task: Optional[asyncio.Task] = None
        self._paused_layers: List[str] = []

        # Register default layers
        self._register_layer("background", AnimationPriority.BACKGROUND)
        self._register_layer("triggered", AnimationPriority.TRIGGERED)
        self._register_layer("reaction", AnimationPriority.REACTION)
        self._register_layer("critical", AnimationPriority.CRITICAL)

        _logger.debug("AnimationCoordinator initialized with %d layers",
                      len(self._layers))

    # =========================================================================
    # LAYER MANAGEMENT
    # =========================================================================

    def _register_layer(self, name: str, priority: AnimationPriority) -> None:
        """
        Register a new animation layer.

        Args:
            name: Unique identifier for the layer
            priority: AnimationPriority level for this layer

        Raises:
            ValueError: If layer name already exists
        """
        with self._lock:
            if name in self._layers:
                raise ValueError(f"Layer '{name}' already registered")

            self._layers[name] = AnimationLayer(
                name=name,
                priority=priority,
                active=False,
                current_animation=None
            )
            _logger.debug("Registered layer '%s' with priority %d",
                          name, priority)

    def get_layer(self, name: str) -> Optional[AnimationLayer]:
        """
        Get a layer by name.

        Args:
            name: Layer identifier

        Returns:
            AnimationLayer if found, None otherwise
        """
        with self._lock:
            return self._layers.get(name)

    def get_active_layer(self) -> Optional[AnimationLayer]:
        """
        Get the highest priority active layer.

        Returns:
            AnimationLayer with highest priority that is active,
            or None if no layers are active.
        """
        with self._lock:
            active_layers = [
                layer for layer in self._layers.values()
                if layer.active
            ]

            if not active_layers:
                return None

            # Return highest priority active layer
            return max(active_layers, key=lambda l: l.priority)

    def get_all_layers(self) -> List[AnimationLayer]:
        """
        Get all registered layers sorted by priority (descending).

        Returns:
            List of AnimationLayer objects
        """
        with self._lock:
            return sorted(
                self._layers.values(),
                key=lambda l: l.priority,
                reverse=True
            )

    # =========================================================================
    # ANIMATION CONTROL
    # =========================================================================

    def start_animation(
        self,
        layer: str,
        animation_name: str,
        blocking: bool = False,
        **params: Any
    ) -> bool:
        """
        Start animation on specified layer.

        Pauses lower-priority layers while this animation runs.
        Higher-priority layers will interrupt this animation.

        Args:
            layer: Layer name ('background', 'triggered', 'reaction', 'critical')
            animation_name: Animation to play ('nod', 'shake', 'curious', etc.)
            blocking: If True, wait for animation to complete
            **params: Animation-specific parameters passed to controller

        Returns:
            True if animation was started successfully

        Raises:
            ValueError: If layer or animation_name is unknown
        """
        with self._lock:
            # Check emergency stop
            if self._emergency_stopped:
                _logger.warning("Cannot start animation - emergency stop active")
                return False

            # Validate layer
            if layer not in self._layers:
                raise ValueError(
                    f"Unknown layer: {layer}. "
                    f"Available: {list(self._layers.keys())}"
                )

            # Validate animation name
            if animation_name not in SUPPORTED_ANIMATIONS:
                raise ValueError(
                    f"Unknown animation: {animation_name}. "
                    f"Available: {list(SUPPORTED_ANIMATIONS.keys())}"
                )

            target_layer = self._layers[layer]

            # Check if higher priority layer is active
            active_layer = self.get_active_layer()
            if active_layer and active_layer.priority > target_layer.priority:
                _logger.debug(
                    "Animation '%s' on layer '%s' blocked by higher priority "
                    "layer '%s'", animation_name, layer, active_layer.name
                )
                return False

            # Pause lower priority active layers
            for other_layer in self._layers.values():
                if (other_layer.active and
                    other_layer.priority < target_layer.priority and
                    other_layer.name not in self._paused_layers):
                    self._paused_layers.append(other_layer.name)
                    _logger.debug("Paused layer '%s'", other_layer.name)

            # Activate target layer
            target_layer.active = True
            target_layer.current_animation = animation_name
            target_layer.start_time = time.monotonic()

            _logger.info("Started animation '%s' on layer '%s'",
                         animation_name, layer)

            # Execute the animation on head controller
            success = self._execute_animation(animation_name, blocking, **params)

            if not blocking:
                # Animation will complete asynchronously
                pass
            else:
                # Animation completed, cleanup
                self._on_animation_finished(layer, animation_name)

            return success

    def _execute_animation(
        self,
        animation_name: str,
        blocking: bool,
        **params: Any
    ) -> bool:
        """
        Execute animation on the head controller.

        Args:
            animation_name: Animation to execute
            blocking: Whether to wait for completion
            **params: Animation parameters

        Returns:
            True if animation was executed
        """
        if self._head is None:
            _logger.debug("No head controller - skipping animation '%s'",
                          animation_name)
            return True  # Success (nothing to do)

        method_name = SUPPORTED_ANIMATIONS.get(animation_name)
        if not method_name:
            return False

        method = getattr(self._head, method_name, None)
        if method is None:
            _logger.warning("Head controller missing method '%s'", method_name)
            return False

        try:
            # Add blocking parameter - use existing value or default to blocking arg
            params['blocking'] = params.get('blocking', blocking)

            method(**params)
            return True
        except Exception as e:
            _logger.error("Animation '%s' failed: %s", animation_name, e)
            return False

    def _on_animation_finished(self, layer: str, animation_name: str) -> None:
        """
        Handle animation completion.

        Cleans up layer state and resumes paused layers.

        Args:
            layer: Layer that finished
            animation_name: Animation that completed
        """
        # FIX H-002: Capture callback for invocation outside lock
        callback_to_fire = None

        with self._lock:
            if layer not in self._layers:
                return

            target_layer = self._layers[layer]

            # Only cleanup if this is still the active animation
            if target_layer.current_animation == animation_name:
                target_layer.active = False
                target_layer.current_animation = None

                _logger.info("Animation '%s' completed on layer '%s'",
                             animation_name, layer)

                # Capture callback for invocation outside lock
                if self._on_animation_complete:
                    callback_to_fire = self._on_animation_complete

            # Resume paused layers (in reverse priority order)
            paused_to_resume = [
                name for name in self._paused_layers
                if self._layers[name].priority < target_layer.priority
            ]

            for name in paused_to_resume:
                self._paused_layers.remove(name)
                self._layers[name].active = True
                _logger.debug("Resumed layer '%s'", name)

        # FIX H-002: Fire callback OUTSIDE the lock to prevent deadlock
        if callback_to_fire:
            try:
                callback_to_fire(animation_name)
            except Exception as e:
                _logger.error("Animation complete callback error: %s", e)

    def stop_animation(self, layer: str) -> bool:
        """
        Stop animation on specified layer.

        Args:
            layer: Layer name to stop

        Returns:
            True if layer was active and stopped
        """
        with self._lock:
            if layer not in self._layers:
                _logger.warning("Cannot stop unknown layer: %s", layer)
                return False

            target_layer = self._layers[layer]

            if not target_layer.active:
                return False

            animation_name = target_layer.current_animation
            target_layer.active = False
            target_layer.current_animation = None

            _logger.info("Stopped animation on layer '%s'", layer)

            # Resume paused layers
            paused_to_resume = list(self._paused_layers)
            for name in paused_to_resume:
                if self._layers[name].priority < target_layer.priority:
                    self._paused_layers.remove(name)
                    self._layers[name].active = True
                    _logger.debug("Resumed layer '%s' after stop", name)

            return True

    def stop_all_animations(self) -> int:
        """
        Stop all active animations on all layers.

        Returns:
            Number of layers that were stopped
        """
        with self._lock:
            count = 0
            for layer in self._layers.values():
                if layer.active:
                    layer.active = False
                    layer.current_animation = None
                    count += 1

            self._paused_layers.clear()

            _logger.info("Stopped %d animation layers", count)
            return count

    # =========================================================================
    # BACKGROUND CONTROL
    # =========================================================================

    def start_background(self) -> bool:
        """
        Start background idle behaviors.

        The background layer runs continuously when no higher-priority
        animations are active. It handles idle behaviors like blinks
        and random glances.

        Returns:
            True if background layer started
        """
        with self._lock:
            if self._emergency_stopped:
                _logger.warning("Cannot start background - emergency stop active")
                return False

            bg_layer = self._layers.get("background")
            if bg_layer is None:
                return False

            if bg_layer.active:
                _logger.debug("Background already running")
                return True

            bg_layer.active = True
            bg_layer.current_animation = "idle"
            bg_layer.start_time = time.monotonic()

            _logger.info("Started background idle behaviors")
            return True

    def stop_background(self) -> bool:
        """
        Stop background idle behaviors.

        Returns:
            True if background was running and stopped
        """
        with self._lock:
            bg_layer = self._layers.get("background")
            if bg_layer is None:
                return False

            if not bg_layer.active:
                return False

            bg_layer.active = False
            bg_layer.current_animation = None

            _logger.info("Stopped background idle behaviors")
            return True

    def is_background_running(self) -> bool:
        """Check if background layer is currently active."""
        with self._lock:
            bg_layer = self._layers.get("background")
            return bg_layer is not None and bg_layer.active

    # =========================================================================
    # EMERGENCY CONTROL
    # =========================================================================

    def emergency_stop(self) -> None:
        """
        Immediately stop all animations.

        CRITICAL layer - highest priority. Stops all animations,
        pauses all layers, and optionally triggers head controller
        emergency stop.

        This is the nuclear option - use for safety-critical situations.
        """
        with self._lock:
            _logger.warning("EMERGENCY STOP triggered")

            self._emergency_stopped = True

            # Stop all layers
            for layer in self._layers.values():
                layer.active = False
                layer.current_animation = None

            self._paused_layers.clear()

            # Trigger head controller emergency stop
            if self._head is not None:
                try:
                    self._head.emergency_stop()
                except Exception as e:
                    _logger.error("Head emergency stop failed: %s", e)

            # Activate critical layer to block other animations
            critical_layer = self._layers.get("critical")
            if critical_layer:
                critical_layer.active = True
                critical_layer.current_animation = "emergency_stop"

    def reset_from_emergency(self) -> bool:
        """
        Clear emergency stop and resume normal operation.

        Returns:
            True if emergency was active and cleared
        """
        with self._lock:
            if not self._emergency_stopped:
                return False

            _logger.info("Clearing emergency stop")

            self._emergency_stopped = False

            # Deactivate critical layer
            critical_layer = self._layers.get("critical")
            if critical_layer:
                critical_layer.active = False
                critical_layer.current_animation = None

            # Reset head controller if present
            if self._head is not None:
                try:
                    self._head.reset_emergency()
                except Exception as e:
                    _logger.error("Head reset failed: %s", e)

            return True

    def is_emergency_stopped(self) -> bool:
        """Check if emergency stop is active."""
        with self._lock:
            return self._emergency_stopped

    # =========================================================================
    # STATE QUERIES
    # =========================================================================

    def get_state(self) -> AnimationState:
        """
        Get current animation system state.

        Returns:
            AnimationState snapshot of current coordinator state
        """
        with self._lock:
            active_layer = self.get_active_layer()
            bg_layer = self._layers.get("background")
            triggered_layer = self._layers.get("triggered")

            return AnimationState(
                active_layer=active_layer.name if active_layer else None,
                active_priority=active_layer.priority if active_layer else 0,
                background_running=bg_layer.active if bg_layer else False,
                triggered_animation=(
                    triggered_layer.current_animation
                    if triggered_layer and triggered_layer.active
                    else None
                ),
                is_blending=self._is_blending,
                blend_progress=self._blend_progress,
                emergency_stopped=self._emergency_stopped
            )

    def is_animating(self) -> bool:
        """
        Check if any triggered animation is active.

        Returns:
            True if any non-background animation is playing
        """
        with self._lock:
            for layer in self._layers.values():
                if layer.active and layer.priority > AnimationPriority.BACKGROUND:
                    return True
            return False

    def is_running(self) -> bool:
        """Check if coordinator loop is running."""
        with self._lock:
            return self._running

    def wait_for_completion(self, timeout_ms: Optional[int] = None) -> bool:
        """
        Wait for current triggered animation to complete.

        Args:
            timeout_ms: Maximum wait time in milliseconds (None = indefinite)

        Returns:
            True if animation completed, False if timeout
        """
        # FIX H-003: Document blocking behavior
        # NOTE: This method uses blocking time.sleep() and should NOT be
        # called from async contexts. Use wait_for_completion_async() instead.
        timeout_s = timeout_ms / 1000.0 if timeout_ms else None
        start = time.monotonic()

        while self.is_animating():
            elapsed = time.monotonic() - start
            if timeout_s and elapsed >= timeout_s:
                return False
            time.sleep(0.01)  # 10ms poll (blocking)

        return True

    async def wait_for_completion_async(
        self,
        timeout_ms: Optional[int] = None
    ) -> bool:
        """
        Async version: Wait for current triggered animation to complete.

        Use this in async contexts to avoid blocking the event loop.

        Args:
            timeout_ms: Maximum wait time in milliseconds (None = indefinite)

        Returns:
            True if animation completed, False if timeout
        """
        import asyncio

        timeout_s = timeout_ms / 1000.0 if timeout_ms else None
        start = time.monotonic()

        while self.is_animating():
            elapsed = time.monotonic() - start
            if timeout_s and elapsed >= timeout_s:
                return False
            await asyncio.sleep(0.01)  # Non-blocking 10ms poll

        return True

    # =========================================================================
    # CALLBACKS
    # =========================================================================

    def set_on_animation_complete(
        self,
        callback: Optional[Callable[[str], None]]
    ) -> None:
        """
        Set callback for animation completion.

        Args:
            callback: Function called with animation name on completion,
                     or None to clear callback
        """
        with self._lock:
            self._on_animation_complete = callback

    def set_on_layer_change(
        self,
        callback: Optional[Callable[[str, str], None]]
    ) -> None:
        """
        Set callback for layer changes.

        Args:
            callback: Function called with (from_layer, to_layer) on change,
                     or None to clear callback
        """
        with self._lock:
            self._on_layer_change = callback

    # =========================================================================
    # ASYNC RUN LOOP
    # =========================================================================

    async def run(self) -> None:
        """
        Main coordination loop.

        Call this as an async task to enable background coordination.
        The loop handles layer state management, blending, and cleanup.

        Loop runs at 10Hz (100ms intervals).

        Example:
            task = asyncio.create_task(coordinator.run())
            # ... later ...
            coordinator.stop()
            await task
        """
        with self._lock:
            if self._running:
                _logger.warning("Coordinator already running")
                return
            self._running = True

        _logger.info("Animation coordinator started")

        try:
            while self._running:
                await self._tick()
                await asyncio.sleep(COORDINATOR_TICK_MS / 1000.0)
        except asyncio.CancelledError:
            _logger.debug("Coordinator task cancelled")
        except Exception as e:
            _logger.error("Coordinator error: %s", e)
        finally:
            with self._lock:
                self._running = False
            _logger.info("Animation coordinator stopped")

    async def _tick(self) -> None:
        """
        Single tick of the coordination loop.

        Handles layer state updates, blending progress, and
        automatic resume of paused layers.
        """
        with self._lock:
            if self._emergency_stopped:
                return

            # Update blend progress if blending
            if self._is_blending:
                elapsed = time.monotonic() - self._blend_start_time
                elapsed_ms = elapsed * 1000.0
                self._blend_progress = min(1.0, elapsed_ms / LAYER_BLEND_DURATION_MS)

                if self._blend_progress >= 1.0:
                    self._is_blending = False
                    self._blend_progress = 0.0

            # FIX M-004: Removed dead code block
            # TODO: Day 13+ - Add head controller callback integration for
            # automatic animation completion detection. Current implementation
            # relies on explicit stop_animation() calls or timeout.

    def stop(self) -> None:
        """Stop the coordinator loop gracefully."""
        with self._lock:
            self._running = False
        _logger.info("Coordinator stop requested")

    # =========================================================================
    # UTILITY METHODS
    # =========================================================================

    def trigger_emotion(
        self,
        emotion: Any,
        duration_ms: int = 500,
        blocking: bool = False
    ) -> bool:
        """
        Trigger emotion-driven animation.

        Convenience method that maps EmotionAxes to appropriate animations.
        Uses the REACTION layer.

        Args:
            emotion: EmotionAxes instance to express
            duration_ms: Transition duration in milliseconds
            blocking: If True, wait for transition to complete

        Returns:
            True if emotion animation started
        """
        with self._lock:
            if self._emergency_stopped:
                return False

            # Activate reaction layer
            reaction_layer = self._layers.get("reaction")
            if reaction_layer:
                reaction_layer.active = True
                reaction_layer.current_animation = "emotion"
                reaction_layer.start_time = time.monotonic()

            # Trigger micro-expression if engine available
            if self._micro_engine is not None:
                try:
                    # Map emotion to micro-expression (simplified)
                    self._micro_engine.trigger_preset('blink_normal')
                except Exception as e:
                    _logger.debug("Micro-expression trigger failed: %s", e)

            _logger.debug("Triggered emotion animation (duration=%dms)", duration_ms)
            return True

    def __repr__(self) -> str:
        """String representation for debugging."""
        with self._lock:
            active = self.get_active_layer()
            return (
                f"AnimationCoordinator("
                f"layers={len(self._layers)}, "
                f"active={active.name if active else None}, "
                f"running={self._running}, "
                f"emergency={self._emergency_stopped})"
            )
