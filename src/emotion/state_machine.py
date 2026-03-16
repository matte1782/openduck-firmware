"""
Emotion State Machine for OpenDuck Mini V3

Manages emotion state transitions and coordinates LED/servo outputs.

Author: Boston Dynamics Emotion Engineer
Created: 22 January 2026
"""

import logging
import threading
import time
from typing import Any, Dict, Optional, Tuple, Union

from .states import EmotionState
from .config import EmotionConfig
from .definitions import EMOTION_DEFINITIONS

_logger = logging.getLogger(__name__)


class EmotionStateMachine:
    """State machine for managing robot emotions.

    Coordinates LED patterns and servo movements based on current
    emotional state. Supports smooth transitions between states.

    Thread Safety:
        All state modifications are protected by a threading lock.
        State queries (current_state, is_transitioning) are safe to
        call from any thread.
    """

    def __init__(
        self,
        led_controller: Any,
        servo_controller: Any,
        config: Optional[Union[EmotionConfig, Dict[str, Any]]] = None,
        auto_idle: bool = False
    ):
        """Initialize emotion state machine.

        Args:
            led_controller: Controller for LED patterns/colors
            servo_controller: Controller for servo movements
            config: Optional configuration (uses defaults if None)
            auto_idle: If True, automatically return to IDLE after timeout
        """
        self._led_controller = led_controller
        self._servo_controller = servo_controller

        # Handle dict config (for backwards compatibility with tests)
        if isinstance(config, dict):
            self._config = EmotionConfig(
                transition_duration_ms=config.get('transition_duration_ms', 500),
                idle_timeout_ms=config.get('idle_timeout_ms', 5000),
                default_brightness=config.get('default_brightness', 0.8),
                max_intensity=config.get('max_intensity', 1.0)
            )
        else:
            self._config = config if config is not None else EmotionConfig()

        self._auto_idle = auto_idle

        # State tracking
        self._current_state = EmotionState.IDLE
        self._previous_state: Optional[EmotionState] = None
        self._target_state: Optional[EmotionState] = None
        self._transitioning = False
        self._intensity: float = 1.0

        # Thread safety (RLock for potential future reentrancy in auto-idle)
        self._lock = threading.RLock()

        # Timing
        self._last_state_change = time.monotonic()
        self._transition_start_time: Optional[float] = None
        self._transition_progress: float = 0.0

        # Auto-idle timer
        self._auto_idle_timer: Optional[threading.Timer] = None

        _logger.debug(f"EmotionStateMachine initialized in {self._current_state}")

    @property
    def current_state(self) -> EmotionState:
        """Get current emotion state."""
        with self._lock:
            return self._current_state

    def is_transitioning(self) -> bool:
        """Check if currently transitioning between states."""
        with self._lock:
            return self._transitioning

    def transition_to(
        self,
        state: EmotionState,
        intensity: float = 1.0,
        blocking: bool = False
    ) -> bool:
        """Transition to a new emotion state.

        Args:
            state: Target emotion state
            intensity: Emotion intensity (0.0-1.0)
            blocking: If True, wait for transition to complete

        Returns:
            True if transition started successfully
        """
        with self._lock:
            if self._current_state == state and not self._transitioning:
                return True  # Already in target state

            # Record previous state
            self._previous_state = self._current_state

            # Start transition
            self._transitioning = True
            self._intensity = max(0.0, min(1.0, intensity))

            # Update state
            self._current_state = state
            self._last_state_change = time.monotonic()

            _logger.debug(
                f"Transitioning from {self._previous_state} to {state} "
                f"(intensity={self._intensity:.2f})"
            )

        # Complete transition (could be async in future)
        self._complete_transition()

        return True

    def _complete_transition(self) -> None:
        """Complete the state transition by updating outputs."""
        with self._lock:
            self._transitioning = False
            self._target_state = None
            # Reset state change time to NOW so auto-idle timer starts fresh
            self._last_state_change = time.monotonic()
            _logger.debug(f"Transition complete: now in {self._current_state}")

    def get_state_duration(self) -> float:
        """Get time since last state change in seconds."""
        with self._lock:
            return time.monotonic() - self._last_state_change

    def reset_to_idle(self) -> bool:
        """Reset to IDLE state."""
        return self.transition_to(EmotionState.IDLE)

    # =========================================================================
    # Public API Methods (for test compatibility)
    # =========================================================================

    @property
    def intensity(self) -> float:
        """Get current emotion intensity."""
        with self._lock:
            return self._intensity

    @property
    def previous_state(self) -> Optional[EmotionState]:
        """Get previous emotion state before current transition."""
        with self._lock:
            return self._previous_state

    def set_emotion(
        self,
        state: EmotionState,
        intensity: float = 1.0
    ) -> None:
        """Set the current emotion state.

        This is the main entry point for changing emotions.

        Args:
            state: Target emotion state (must be EmotionState enum)
            intensity: Emotion intensity (0.0-1.0), default 1.0

        Raises:
            ValueError: If state is not a valid EmotionState
            ValueError: If intensity is out of range
        """
        # Validate state is an EmotionState enum
        if not isinstance(state, EmotionState):
            raise ValueError(
                f"Invalid emotion state: {state}. Must be an EmotionState enum."
            )

        # Validate intensity range
        if not (0.0 <= intensity <= 1.0):
            raise ValueError(
                f"Intensity must be 0.0-1.0, got {intensity}"
            )

        with self._lock:
            # Skip if already in target state (and not transitioning)
            if self._current_state == state and not self._transitioning:
                _logger.debug(f"Already in {state}, skipping")
                return

            # Cancel any pending auto-idle timer
            self._cancel_auto_idle_timer()

            # Record previous state
            self._previous_state = self._current_state

            # Start transition
            self._transitioning = True
            self._target_state = state
            self._intensity = max(0.0, min(1.0, intensity))
            self._transition_start_time = time.monotonic()
            self._transition_progress = 0.0

            _logger.debug(
                f"Starting transition from {self._previous_state} to {state} "
                f"(intensity={self._intensity:.2f})"
            )

        # Apply the emotion (updates LED/servo)
        self._apply_emotion()

    def get_current_emotion(self) -> EmotionState:
        """Get the current emotion state.

        Returns:
            Current EmotionState
        """
        with self._lock:
            return self._current_state

    def set_intensity(self, intensity: float) -> None:
        """Update emotion intensity without changing state.

        Args:
            intensity: New intensity value (0.0-1.0)
        """
        with self._lock:
            # Clamp intensity to valid range
            self._intensity = max(0.0, min(1.0, intensity))

        # Re-apply emotion with new intensity
        self._apply_emotion()

    def update(self, delta_time: float = 0.02) -> EmotionState:
        """Update the state machine (call each frame).

        Progresses any active transitions and checks for auto-idle timeout.

        Args:
            delta_time: Time since last update in seconds (default 20ms)

        Returns:
            Current EmotionState
        """
        should_auto_idle = False

        with self._lock:
            # Progress transition if active
            if self._transitioning and self._transition_start_time is not None:
                elapsed_ms = (time.monotonic() - self._transition_start_time) * 1000
                duration_ms = self._config.transition_duration_ms

                if elapsed_ms >= duration_ms:
                    # Transition complete
                    self._complete_transition()
                else:
                    # Update progress
                    self._transition_progress = elapsed_ms / duration_ms

            # Check auto-idle timeout (synchronous check)
            if self._auto_idle and not self._transitioning:
                if self._current_state != EmotionState.IDLE:
                    state_duration = time.monotonic() - self._last_state_change
                    if state_duration * 1000 >= self._config.idle_timeout_ms:
                        should_auto_idle = True

        # Trigger auto-idle outside of lock to avoid deadlock
        if should_auto_idle:
            self.set_emotion(EmotionState.IDLE)

        with self._lock:
            return self._current_state

    def wait_for_transition(self, timeout: float = 5.0) -> bool:
        """Wait for current transition to complete.

        Args:
            timeout: Maximum time to wait in seconds

        Returns:
            True if transition completed, False if timeout
        """
        start_time = time.monotonic()

        while True:
            with self._lock:
                if not self._transitioning:
                    return True

            # Check timeout
            if time.monotonic() - start_time >= timeout:
                _logger.warning("Timeout waiting for transition to complete")
                return False

            # Progress the transition
            self.update()
            time.sleep(0.01)  # 10ms sleep

    # =========================================================================
    # Internal Methods
    # =========================================================================

    def _apply_emotion(self) -> None:
        """Apply current emotion state to LED and servo controllers.

        This method is safe - it catches and logs any controller errors
        rather than raising exceptions.
        """
        with self._lock:
            state = self._target_state if self._target_state else self._current_state
            intensity = self._intensity

        # Get emotion definition
        state_name = state.name.lower()
        definition = EMOTION_DEFINITIONS.get(state_name, EMOTION_DEFINITIONS['idle'])

        # Apply to LED controller (if available)
        if self._led_controller is not None:
            try:
                # Set LED pattern
                if hasattr(self._led_controller, 'set_pattern'):
                    self._led_controller.set_pattern(definition['pattern'])

                # Set LED color
                if hasattr(self._led_controller, 'set_color'):
                    self._led_controller.set_color(definition['color'])

                # Set brightness (modulated by intensity)
                if hasattr(self._led_controller, 'set_brightness'):
                    brightness = self._config.default_brightness * intensity
                    self._led_controller.set_brightness(brightness)

            except Exception as e:
                _logger.error(f"LED controller error: {e}")

        # Apply to servo controller (if available)
        if self._servo_controller is not None:
            try:
                # Set servo position
                if hasattr(self._servo_controller, 'set_position'):
                    position = definition.get('servo_position', 0.0)
                    self._servo_controller.set_position(position)

            except Exception as e:
                _logger.error(f"Servo controller error: {e}")

        # Update current state (transition is effectively instant for now)
        with self._lock:
            if self._target_state:
                self._current_state = self._target_state
                self._last_state_change = time.monotonic()

    def _start_auto_idle_timer(self) -> None:
        """Start timer to return to IDLE after idle_timeout_ms."""
        with self._lock:
            self._cancel_auto_idle_timer()

            if self._auto_idle and self._current_state != EmotionState.IDLE:
                timeout_sec = self._config.idle_timeout_ms / 1000.0
                self._auto_idle_timer = threading.Timer(
                    timeout_sec,
                    self._on_auto_idle_timeout
                )
                self._auto_idle_timer.daemon = True
                self._auto_idle_timer.start()
                _logger.debug(f"Auto-idle timer started ({timeout_sec:.2f}s)")

    def _cancel_auto_idle_timer(self) -> None:
        """Cancel any pending auto-idle timer.

        Thread Safety: Joins the timer thread to prevent memory leaks
        from accumulated cancelled timers under rapid emotion changes.
        """
        timer = None
        with self._lock:
            if self._auto_idle_timer is not None:
                timer = self._auto_idle_timer
                self._auto_idle_timer = None

        # Join outside lock to prevent deadlock
        if timer is not None:
            timer.cancel()
            timer.join(timeout=0.1)  # Wait up to 100ms for thread cleanup
            if timer.is_alive():
                _logger.warning("Auto-idle timer thread still alive after cancel")
            else:
                _logger.debug("Auto-idle timer cancelled and joined")

    def _on_auto_idle_timeout(self) -> None:
        """Callback when auto-idle timer fires."""
        _logger.debug("Auto-idle timeout triggered")
        with self._lock:
            if self._current_state != EmotionState.IDLE:
                self._auto_idle_timer = None
        # Set emotion outside lock to avoid potential deadlock
        self.set_emotion(EmotionState.IDLE)

    def _schedule_auto_idle(self) -> None:
        """Schedule a return to IDLE state."""
        # This is called from within update(), so we trigger it async
        if self._auto_idle_timer is None:
            self._start_auto_idle_timer()

    def __del__(self) -> None:
        """Cleanup on destruction."""
        self._cancel_auto_idle_timer()
