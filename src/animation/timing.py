#!/usr/bin/env python3
"""
Keyframe Animation System

Provides keyframe-based animation for servo positions, LED colors,
and other animatable properties.

Core concepts:
- Keyframe: A snapshot of values at a specific time
- AnimationSequence: Collection of keyframes with interpolation
- Timeline: Current playback position in milliseconds

Author: Boston Dynamics Animation Systems Engineer
Created: 18 January 2026
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple
import time

from .easing import ease, EASING_LUTS


@dataclass
class Keyframe:
    """A single keyframe in an animation sequence.

    Attributes:
        time_ms: Time position in milliseconds from sequence start
        color: RGB color tuple (0-255 per channel) - optional
        brightness: Overall brightness (0.0-1.0) - optional
        position: 2D position offset (x, y) for comet/pattern positioning - optional
        easing: Easing function name for interpolation TO this keyframe
        metadata: Additional custom properties
    """
    time_ms: int
    color: Optional[Tuple[int, int, int]] = None
    brightness: Optional[float] = None
    position: Optional[Tuple[float, float]] = None
    easing: str = 'ease_in_out'
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Validate keyframe data."""
        if self.time_ms < 0:
            raise ValueError(f"time_ms must be >= 0, got {self.time_ms}")
        if self.easing not in EASING_LUTS:
            raise ValueError(f"Unknown easing type: {self.easing}")
        if self.brightness is not None:
            if not 0.0 <= self.brightness <= 1.0:
                raise ValueError(f"brightness must be 0.0-1.0, got {self.brightness}")
        if self.color is not None:
            if len(self.color) != 3:
                raise ValueError(f"color must be RGB tuple (3 values), got {len(self.color)}")
            for c in self.color:
                if not 0 <= c <= 255:
                    raise ValueError(f"color values must be 0-255, got {c}")


class AnimationSequence:
    """A sequence of keyframes with interpolation.

    Supports:
    - Adding keyframes at arbitrary times
    - Getting interpolated position/color/brightness at any time
    - Multiple easing types per keyframe
    - Looping and single-shot playback

    Example:
        seq = AnimationSequence("fade_in")
        seq.add_keyframe(0, color=(0, 0, 0), brightness=0.0)
        seq.add_keyframe(1000, color=(255, 255, 255), brightness=1.0, easing='ease_out')

        # Get interpolated values at 500ms
        values = seq.get_values(500)
        # values = {'color': (127, 127, 127), 'brightness': 0.7}
    """

    def __init__(self, name: str, loop: bool = False):
        """Initialize animation sequence.

        Args:
            name: Descriptive name for the sequence
            loop: If True, sequence loops; if False, holds last keyframe
        """
        self.name = name
        self.loop = loop
        self.keyframes: List[Keyframe] = []
        self._duration_ms: int = 0

    def add_keyframe(
        self,
        time_ms: int,
        color: Optional[Tuple[int, int, int]] = None,
        brightness: Optional[float] = None,
        position: Optional[Tuple[float, float]] = None,
        easing: str = 'ease_in_out',
        **metadata
    ) -> 'AnimationSequence':
        """Add a keyframe to the sequence.

        Args:
            time_ms: Time position in milliseconds
            color: RGB color tuple (0-255 per channel)
            brightness: Overall brightness (0.0-1.0)
            position: 2D position offset (x, y)
            easing: Easing function for interpolation TO this keyframe
            **metadata: Additional custom properties

        Returns:
            Self for method chaining
        """
        kf = Keyframe(
            time_ms=time_ms,
            color=color,
            brightness=brightness,
            position=position,
            easing=easing,
            metadata=metadata
        )
        self.keyframes.append(kf)

        # Keep keyframes sorted by time
        self.keyframes.sort(key=lambda k: k.time_ms)

        # Update duration
        self._duration_ms = max(self._duration_ms, time_ms)

        return self

    def get_values(self, time_ms: int) -> Dict[str, Any]:
        """Get interpolated values at given time.

        Args:
            time_ms: Time position in milliseconds

        Returns:
            Dictionary of interpolated property values (color, brightness, position, etc.)
        """
        if not self.keyframes:
            return {}

        # Handle looping
        if self.loop and self._duration_ms > 0:
            time_ms = time_ms % self._duration_ms

        # Clamp time to valid range
        time_ms = max(0, time_ms)

        # Find surrounding keyframes
        prev_kf = self.keyframes[0]
        next_kf = self.keyframes[-1]

        for i, kf in enumerate(self.keyframes):
            if kf.time_ms >= time_ms:
                next_kf = kf
                prev_kf = self.keyframes[max(0, i - 1)]
                break

        # If we're exactly at a keyframe, return its values
        if prev_kf.time_ms == time_ms:
            return self._extract_values(prev_kf)
        if next_kf.time_ms == time_ms:
            return self._extract_values(next_kf)

        # Calculate interpolation factor
        if prev_kf.time_ms == next_kf.time_ms:
            t = 1.0
        else:
            t = (time_ms - prev_kf.time_ms) / (next_kf.time_ms - prev_kf.time_ms)
            t = max(0.0, min(1.0, t))

        # Apply easing (use next keyframe's easing)
        eased_t = ease(t, next_kf.easing)

        # Interpolate values
        result: Dict[str, Any] = {}

        # Interpolate color
        if prev_kf.color is not None and next_kf.color is not None:
            result['color'] = self._interpolate_color(prev_kf.color, next_kf.color, eased_t)
        elif next_kf.color is not None:
            result['color'] = next_kf.color
        elif prev_kf.color is not None:
            result['color'] = prev_kf.color

        # Interpolate brightness
        if prev_kf.brightness is not None and next_kf.brightness is not None:
            result['brightness'] = self._interpolate_float(
                prev_kf.brightness, next_kf.brightness, eased_t
            )
        elif next_kf.brightness is not None:
            result['brightness'] = next_kf.brightness
        elif prev_kf.brightness is not None:
            result['brightness'] = prev_kf.brightness

        # Interpolate position
        if prev_kf.position is not None and next_kf.position is not None:
            result['position'] = self._interpolate_position(
                prev_kf.position, next_kf.position, eased_t
            )
        elif next_kf.position is not None:
            result['position'] = next_kf.position
        elif prev_kf.position is not None:
            result['position'] = prev_kf.position

        # Add metadata from next keyframe
        result.update(next_kf.metadata)

        return result

    @staticmethod
    def _extract_values(kf: Keyframe) -> Dict[str, Any]:
        """Extract all values from a keyframe."""
        result = {}
        if kf.color is not None:
            result['color'] = kf.color
        if kf.brightness is not None:
            result['brightness'] = kf.brightness
        if kf.position is not None:
            result['position'] = kf.position
        result.update(kf.metadata)
        return result

    @staticmethod
    def _interpolate_color(
        color1: Tuple[int, int, int],
        color2: Tuple[int, int, int],
        t: float
    ) -> Tuple[int, int, int]:
        """Linearly interpolate between two RGB colors."""
        return (
            int(color1[0] + (color2[0] - color1[0]) * t),
            int(color1[1] + (color2[1] - color1[1]) * t),
            int(color1[2] + (color2[2] - color1[2]) * t),
        )

    @staticmethod
    def _interpolate_float(val1: float, val2: float, t: float) -> float:
        """Linearly interpolate between two float values."""
        return val1 + (val2 - val1) * t

    @staticmethod
    def _interpolate_position(
        pos1: Tuple[float, float],
        pos2: Tuple[float, float],
        t: float
    ) -> Tuple[float, float]:
        """Linearly interpolate between two 2D positions."""
        return (
            pos1[0] + (pos2[0] - pos1[0]) * t,
            pos1[1] + (pos2[1] - pos1[1]) * t,
        )

    @property
    def duration_ms(self) -> int:
        """Get total duration of the sequence in milliseconds."""
        return self._duration_ms

    def get_keyframe_count(self) -> int:
        """Get number of keyframes in sequence."""
        return len(self.keyframes)

    def clear(self):
        """Remove all keyframes."""
        self.keyframes.clear()
        self._duration_ms = 0


class AnimationPlayer:
    """Plays animation sequences in real-time.

    Handles timing, playback control, and value updates using time.monotonic()
    for precise frame-perfect timing.

    Example:
        player = AnimationPlayer(sequence, target_fps=50)
        player.play()

        while player.is_playing():
            values = player.update()
            # Apply values to LEDs/servos
            player.wait_for_next_frame()  # Frame-perfect timing
    """

    def __init__(self, sequence: AnimationSequence, target_fps: int = 50):
        """Initialize player with a sequence.

        Args:
            sequence: AnimationSequence to play
            target_fps: Target frame rate (default: 50Hz)
        """
        self.sequence = sequence
        self.target_fps = target_fps
        self.frame_time = 1.0 / target_fps
        self._playing = False
        self._start_time: float = 0.0
        self._pause_time: float = 0.0
        self._speed: float = 1.0
        self._next_frame_time: float = 0.0

    def play(self, speed: float = 1.0):
        """Start or resume playback.

        Args:
            speed: Playback speed multiplier (1.0 = normal)
        """
        self._speed = speed

        if not self._playing:
            if self._pause_time > 0:
                # Resume from pause
                pause_duration = time.monotonic() - self._pause_time
                self._start_time += pause_duration
            else:
                # Fresh start
                self._start_time = time.monotonic()

            self._next_frame_time = time.monotonic()
            self._playing = True

    def pause(self):
        """Pause playback."""
        if self._playing:
            self._pause_time = time.monotonic()
            self._playing = False

    def stop(self):
        """Stop playback and reset to beginning."""
        self._playing = False
        self._start_time = 0.0
        self._pause_time = 0.0

    def is_playing(self) -> bool:
        """Check if currently playing."""
        return self._playing

    def get_current_time_ms(self) -> int:
        """Get current playback position in milliseconds."""
        if self._playing:
            elapsed = time.monotonic() - self._start_time
            return int(elapsed * 1000 * self._speed)
        elif self._pause_time > 0:
            elapsed = self._pause_time - self._start_time
            return int(elapsed * 1000 * self._speed)
        return 0

    def update(self) -> Dict[str, Any]:
        """Update and get current interpolated values.

        Returns:
            Dictionary of current property values
        """
        current_ms = self.get_current_time_ms()

        # Check if sequence completed (non-looping)
        if not self.sequence.loop and current_ms >= self.sequence.duration_ms:
            self._playing = False
            current_ms = self.sequence.duration_ms

        return self.sequence.get_values(current_ms)

    def wait_for_next_frame(self):
        """Wait until next frame boundary for frame-perfect timing.

        Uses time.monotonic() to eliminate jitter and maintain precise frame rate.
        """
        now = time.monotonic()
        sleep_time = self._next_frame_time - now

        if sleep_time > 0:
            time.sleep(sleep_time)
            self._next_frame_time += self.frame_time
        else:
            # Frame overrun - reset to prevent death spiral
            self._next_frame_time = time.monotonic() + self.frame_time

    def seek(self, time_ms: int):
        """Seek to specific time position.

        Args:
            time_ms: Target time in milliseconds
        """
        if self._playing:
            self._start_time = time.monotonic() - (time_ms / 1000 / self._speed)
        else:
            # If paused, adjust pause time
            self._pause_time = self._start_time + (time_ms / 1000 / self._speed)
