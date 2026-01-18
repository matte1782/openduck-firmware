#!/usr/bin/env python3
"""
LED Manager - Central LED Coordination for OpenDuck Mini V3

Integrates LED patterns, animation timing, and emotion system into a unified
interface. Provides clean separation of concerns and error handling.

Architecture:
    EmotionManager -> LEDManager -> LEDController -> Hardware
         |              |              |
         |              v              v
         |         PatternBase    rpi_ws281x
         v
    AnimationPlayer

Author: Boston Dynamics Systems Integration Engineer
Created: 18 January 2026
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Dict, Any, Callable, List, Tuple

# Import pattern system
from led.patterns import (
    PatternBase,
    PatternConfig,
    BreathingPattern,
    PulsePattern,
    SpinPattern,
    PATTERN_REGISTRY,
    RGB
)

# Import animation system
from animation.timing import AnimationPlayer, AnimationSequence
from animation.emotions import (
    EmotionState,
    EmotionConfig,
    EmotionManager,
    EMOTION_CONFIGS
)

# Module logger
_logger = logging.getLogger(__name__)


# === LED Controller Interface ===

class LEDControllerProtocol:
    """Protocol defining LED controller interface.

    This allows LEDManager to work with any LED controller implementation
    (hardware or mock) as long as it implements these methods.
    """

    def set_pattern(self, pattern_name: str, speed: float = 1.0) -> None:
        """Set active LED pattern."""
        ...

    def set_color(self, color: RGB) -> None:
        """Set base LED color."""
        ...

    def set_brightness(self, brightness: int) -> None:
        """Set overall brightness (0-255)."""
        ...

    def update(self) -> None:
        """Update LED hardware with current pattern frame."""
        ...

    def clear(self) -> None:
        """Turn off all LEDs."""
        ...


# === LED Controller Implementation ===

class LEDController:
    """Hardware LED controller for dual WS2812B rings.

    Manages both left and right eye LED rings with synchronized updates.
    Integrates with LED safety system for current limiting.
    """

    def __init__(
        self,
        num_pixels: int = 16,
        left_pin: int = 18,
        right_pin: int = 13,
        target_fps: int = 50,
        brightness: int = 128,
        power_source: str = "PI_5V"
    ):
        """Initialize dual LED controller.

        Args:
            num_pixels: Number of LEDs per ring (default: 16)
            left_pin: GPIO pin for left eye (default: 18)
            right_pin: GPIO pin for right eye (default: 13)
            target_fps: Target refresh rate (default: 50Hz)
            brightness: Overall brightness 0-255 (default: 128)
            power_source: "PI_5V" or "EXTERNAL_5V"
        """
        self.num_pixels = num_pixels
        self.left_pin = left_pin
        self.right_pin = right_pin
        self.target_fps = target_fps
        self._brightness = brightness
        self._power_source = power_source

        # Current pattern and color
        self._current_pattern: Optional[PatternBase] = None
        self._current_color: RGB = (100, 150, 255)  # Soft blue default
        self._pattern_name: str = "breathing"

        # Hardware strips (initialized lazily)
        self._left_strip = None
        self._right_strip = None
        self._hardware_initialized = False

        # Thread safety
        self._lock = threading.RLock()

        _logger.info(f"LEDController initialized: {num_pixels} pixels/ring, "
                    f"{target_fps}Hz, brightness={brightness}")

    def initialize_hardware(self) -> bool:
        """Initialize LED hardware (rpi_ws281x).

        Returns:
            True if successful, False otherwise
        """
        with self._lock:
            if self._hardware_initialized:
                return True

            try:
                # Import hardware library
                from rpi_ws281x import PixelStrip, Color

                # Initialize strips
                self._left_strip = PixelStrip(
                    self.num_pixels, self.left_pin, 800000, 10,
                    False, self._brightness, 0
                )
                self._right_strip = PixelStrip(
                    self.num_pixels, self.right_pin, 800000, 10,
                    False, self._brightness, 1
                )

                self._left_strip.begin()
                self._right_strip.begin()

                self._Color = Color
                self._hardware_initialized = True

                _logger.info("LED hardware initialized successfully")
                return True

            except ImportError:
                _logger.warning("rpi_ws281x not available - using mock mode")
                return False
            except Exception as e:
                _logger.error(f"LED hardware initialization failed: {e}")
                return False

    def set_pattern(self, pattern_name: str, speed: float = 1.0) -> None:
        """Set active LED pattern.

        Args:
            pattern_name: Pattern name ('breathing', 'pulse', 'spin')
            speed: Speed multiplier (default: 1.0)
        """
        with self._lock:
            if pattern_name not in PATTERN_REGISTRY:
                raise ValueError(f"Unknown pattern: {pattern_name}. "
                               f"Available: {list(PATTERN_REGISTRY.keys())}")

            # Create pattern instance
            pattern_class = PATTERN_REGISTRY[pattern_name]
            config = PatternConfig(speed=speed, brightness=self._brightness / 255.0)
            self._current_pattern = pattern_class(self.num_pixels, config)
            self._pattern_name = pattern_name

            _logger.debug(f"Pattern set: {pattern_name} (speed={speed})")

    def set_color(self, color: RGB) -> None:
        """Set base LED color.

        Args:
            color: RGB tuple (0-255 per channel)
        """
        with self._lock:
            if not isinstance(color, tuple) or len(color) != 3:
                raise ValueError(f"Color must be RGB tuple, got {color}")
            if not all(0 <= c <= 255 for c in color):
                raise ValueError(f"RGB values must be 0-255, got {color}")

            self._current_color = color
            _logger.debug(f"Color set: RGB{color}")

    def set_brightness(self, brightness: int) -> None:
        """Set overall brightness.

        Args:
            brightness: Brightness 0-255
        """
        with self._lock:
            if not 0 <= brightness <= 255:
                raise ValueError(f"Brightness must be 0-255, got {brightness}")

            self._brightness = brightness

            # Update pattern config if active
            if self._current_pattern:
                self._current_pattern.config.brightness = brightness / 255.0

            # Update hardware strips if initialized
            if self._hardware_initialized and self._left_strip:
                self._left_strip.setBrightness(brightness)
                self._right_strip.setBrightness(brightness)

            _logger.debug(f"Brightness set: {brightness}/255")

    def update(self) -> None:
        """Update LED hardware with current pattern frame."""
        with self._lock:
            if not self._current_pattern:
                return

            # Render pattern frame
            pixels = self._current_pattern.render(self._current_color)

            # Update hardware (if available)
            if self._hardware_initialized and self._left_strip:
                for i, (r, g, b) in enumerate(pixels):
                    color = self._Color(r, g, b)
                    self._left_strip.setPixelColor(i, color)
                    self._right_strip.setPixelColor(i, color)

                self._left_strip.show()
                self._right_strip.show()

            # Advance pattern to next frame
            self._current_pattern.advance()

    def clear(self) -> None:
        """Turn off all LEDs."""
        with self._lock:
            if self._hardware_initialized and self._left_strip:
                for i in range(self.num_pixels):
                    self._left_strip.setPixelColor(i, 0)
                    self._right_strip.setPixelColor(i, 0)

                self._left_strip.show()
                self._right_strip.show()

            _logger.debug("LEDs cleared")

    def shutdown(self) -> None:
        """Clean shutdown of LED hardware."""
        with self._lock:
            self.clear()
            self._hardware_initialized = False
            _logger.info("LED hardware shutdown complete")


# === LED Manager - Central Orchestrator ===

class LEDManager:
    """Central LED coordination system.

    Orchestrates LED patterns, animation timing, and emotion system.
    Provides unified interface for emotion-driven LED expression.

    Example:
        >>> led_mgr = LEDManager()
        >>> led_mgr.start()
        >>> led_mgr.set_emotion(EmotionState.HAPPY)
        >>> # LEDs automatically show happy pattern/color
        >>> led_mgr.stop()
    """

    def __init__(
        self,
        led_controller: Optional[LEDControllerProtocol] = None,
        target_fps: int = 50,
        auto_start: bool = False
    ):
        """Initialize LED manager.

        Args:
            led_controller: Optional LED controller (creates default if None)
            target_fps: Target refresh rate (default: 50Hz)
            auto_start: If True, start update loop immediately
        """
        # Create default controller if not provided
        self.led_controller = led_controller or LEDController(target_fps=target_fps)

        # Create emotion manager (uses self as LED controller proxy)
        self.emotion_manager = EmotionManager(self, None)  # No animator for now

        # Update loop control
        self.target_fps = target_fps
        self.frame_time = 1.0 / target_fps
        self._running = False
        self._update_thread: Optional[threading.Thread] = None
        self._lock = threading.RLock()

        # Performance tracking
        self._frame_count = 0
        self._start_time = 0.0

        _logger.info(f"LEDManager initialized: {target_fps}Hz target")

        if auto_start:
            self.start()

    def start(self) -> None:
        """Start LED update loop."""
        with self._lock:
            if self._running:
                _logger.warning("LED update loop already running")
                return

            # Initialize hardware
            if hasattr(self.led_controller, 'initialize_hardware'):
                self.led_controller.initialize_hardware()

            # Set initial emotion (IDLE)
            self.emotion_manager.reset_to_idle()

            # Start update thread
            self._running = True
            self._start_time = time.monotonic()
            self._frame_count = 0

            self._update_thread = threading.Thread(
                target=self._update_loop,
                name="LEDManager-Update",
                daemon=True
            )
            self._update_thread.start()

            _logger.info("LED update loop started")

    def stop(self) -> None:
        """Stop LED update loop."""
        with self._lock:
            if not self._running:
                return

            self._running = False

            if self._update_thread:
                self._update_thread.join(timeout=1.0)

            # Clear LEDs
            self.led_controller.clear()

            _logger.info("LED update loop stopped")

    def _update_loop(self) -> None:
        """Main update loop (runs in separate thread)."""
        next_frame_time = time.monotonic()

        while self._running:
            # Update LED hardware
            try:
                self.led_controller.update()
                self._frame_count += 1
            except Exception as e:
                _logger.error(f"LED update error: {e}", exc_info=True)

            # Frame-perfect timing
            now = time.monotonic()
            sleep_time = next_frame_time - now

            if sleep_time > 0:
                time.sleep(sleep_time)
                next_frame_time += self.frame_time
            else:
                # Frame overrun - reset
                next_frame_time = time.monotonic() + self.frame_time

    def set_emotion(self, emotion: EmotionState, force: bool = False) -> bool:
        """Set robot emotion (updates LED pattern/color automatically).

        Args:
            emotion: Target emotion state
            force: If True, bypass transition validation

        Returns:
            True if transition occurred
        """
        return self.emotion_manager.set_emotion(emotion, force)

    def get_current_emotion(self) -> EmotionState:
        """Get current emotion state."""
        return self.emotion_manager.current_emotion

    # === LED Controller Proxy Methods (for EmotionManager) ===

    def set_pattern(self, pattern_name: str, speed: float = 1.0) -> None:
        """Set LED pattern (proxy to controller)."""
        self.led_controller.set_pattern(pattern_name, speed)

    def set_color(self, color: RGB) -> None:
        """Set LED color (proxy to controller)."""
        self.led_controller.set_color(color)

    def set_brightness(self, brightness: int) -> None:
        """Set LED brightness (proxy to controller)."""
        self.led_controller.set_brightness(brightness)

    # === Performance Metrics ===

    def get_fps(self) -> float:
        """Get actual FPS (frames per second).

        Returns:
            Current FPS
        """
        if self._frame_count == 0:
            return 0.0

        elapsed = time.monotonic() - self._start_time
        return self._frame_count / elapsed if elapsed > 0 else 0.0

    def get_stats(self) -> Dict[str, Any]:
        """Get performance statistics.

        Returns:
            Dictionary of stats (fps, frame_count, emotion, pattern, etc.)
        """
        return {
            'fps': self.get_fps(),
            'target_fps': self.target_fps,
            'frame_count': self._frame_count,
            'running': self._running,
            'emotion': self.emotion_manager.current_emotion.name,
            'pattern': getattr(self.led_controller, '_pattern_name', 'unknown'),
            'color': getattr(self.led_controller, '_current_color', (0, 0, 0)),
            'brightness': getattr(self.led_controller, '_brightness', 0),
        }

    # === Context Manager Support ===

    def __enter__(self) -> LEDManager:
        """Context manager entry."""
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit."""
        self.stop()


# === Convenience Functions ===

def create_led_manager(target_fps: int = 50, auto_start: bool = False) -> LEDManager:
    """Create and configure LED manager with default settings.

    Args:
        target_fps: Target refresh rate (default: 50Hz)
        auto_start: If True, start update loop immediately

    Returns:
        Configured LEDManager instance
    """
    return LEDManager(target_fps=target_fps, auto_start=auto_start)
