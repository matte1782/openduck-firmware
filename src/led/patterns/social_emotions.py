#!/usr/bin/env python3
"""
Social Emotion Patterns for OpenDuck Mini V3
Boston Dynamics / Pixar / DeepMind Quality Standard

Implements 4 connection-building social emotions that create genuine human-robot bonds:
1. PlayfulPattern - Mischievous, bouncy, asymmetric eye movements
2. AffectionatePattern - Warm heartbeat pulse with soft pink glow
3. EmpatheticPattern - Mirroring, supportive presence
4. GratefulPattern - Appreciative warm glow with brightness surge

Research References:
- Anki Cozmo/Vector Emotion Engine design principles
- Color Psychology: Pink for love/warmth, gold for gratitude
- Social robotics HRI research on emotional bonding
- Disney 12 Principles of Animation for character appeal

Disney Animation Principles Applied:
- ANTICIPATION: Pre-motion cues before main action
- SECONDARY ACTION: Sparkles, micro-variations support main emotion
- TIMING: Speed matches emotional energy
- EXAGGERATION: Colors more saturated for emotional clarity
- APPEAL: Each emotion is likable and invites engagement

Author: Social Emotion Implementation Specialist (Agent 2)
Created: 18 January 2026
Performance Target: <2.5ms average frame time, <10ms maximum
"""

import math
import random
import time
from typing import List, Optional, Tuple
from dataclasses import dataclass

from .base import PatternBase, PatternConfig, RGB


# =============================================================================
# Constants
# =============================================================================

# Maximum sparkles to prevent unbounded memory growth (H-002 compliance)
MAX_SPARKLES = 50

# Frame rate assumption for timing calculations
FRAME_RATE_HZ = 50

# Color Psychology Research-Backed Values
# Pink: Warmth, affection, nurturing (Ceyise Studios, 2024)
# Gold/Amber: Gratitude, appreciation, warmth
# Rainbow/Varied: Playfulness, joy, mischief

COLOR_AFFECTIONATE_PRIMARY = (255, 150, 180)    # Warm pink-coral
COLOR_AFFECTIONATE_SECONDARY = (255, 200, 210)  # Soft pink highlight
COLOR_GRATEFUL_PRIMARY = (255, 200, 100)        # Golden amber
COLOR_GRATEFUL_SECONDARY = (255, 240, 180)      # Bright gold flash
COLOR_EMPATHETIC_PRIMARY = (180, 180, 220)      # Soft lavender-blue
COLOR_EMPATHETIC_SECONDARY = (200, 200, 240)    # Light supportive blue
COLOR_PLAYFUL_PRIMARY = (255, 180, 100)         # Warm orange base


@dataclass
class Sparkle:
    """
    Single sparkle particle for playful/grateful patterns.

    Attributes:
        pixel_index: LED position (0-15)
        intensity: Current brightness (0.0-1.0)
        color: RGB tuple for sparkle color
        lifetime_remaining: Frames until sparkle expires
        decay_rate: How fast intensity decreases per frame
    """
    pixel_index: int
    intensity: float
    color: RGB
    lifetime_remaining: int
    decay_rate: float


# =============================================================================
# PlayfulPattern - Mischievous, bouncy, asymmetric
# =============================================================================

class PlayfulPattern(PatternBase):
    """
    Playful/Funny emotion pattern - bouncy, mischievous energy.

    Creates the feeling of a puppy wanting to play through:
    - Asymmetric eye movements (one eye "winking")
    - Bouncy, unpredictable timing variations
    - Rainbow sparkle bursts
    - Quick attention-grabbing movements

    Psychology: Play signal that reduces social tension and invites interaction.
    Based on Anki Cozmo emotion engine design principles.

    Disney Principles Applied:
    - EXAGGERATION: Bright, saturated colors for fun
    - TIMING: Variable speed creates unpredictability
    - SECONDARY ACTION: Sparkles add excitement
    - ANTICIPATION: Brief pause before bounce

    Performance:
        Target: <2.5ms average, <10ms maximum
        Sparkle list capped at MAX_SPARKLES for memory safety
    """

    NAME = "playful"
    DESCRIPTION = "Bouncy, mischievous playful emotion with sparkles"
    DEFAULT_SPEED = 1.0

    # Timing parameters (research: playful states have elevated blink rate ~1.4x)
    CYCLE_FRAMES = 60           # ~1.2 seconds per main cycle at 50Hz
    BOUNCE_DURATION = 15        # Frames for bounce animation
    SPARKLE_CHANCE = 0.15       # Probability of new sparkle per frame
    SPARKLE_LIFETIME = 12       # Frames sparkle lives
    MAX_ASYMMETRY = 0.4         # Maximum brightness difference between eyes

    # Intensity levels
    BASE_INTENSITY = 0.5        # Baseline brightness
    BOUNCE_PEAK = 1.0           # Peak during bounce

    # Rainbow colors for sparkles (bright, saturated for fun)
    SPARKLE_COLORS: List[RGB] = [
        (255, 100, 100),    # Red
        (255, 200, 100),    # Orange
        (255, 255, 100),    # Yellow
        (100, 255, 100),    # Green
        (100, 200, 255),    # Cyan
        (150, 100, 255),    # Purple
        (255, 150, 200),    # Pink
    ]

    def __init__(self, num_pixels: int = 16, config: Optional[PatternConfig] = None):
        """
        Initialize playful pattern.

        Args:
            num_pixels: Number of LEDs per eye (default: 16)
            config: Optional PatternConfig (speed affects bounce rate)

        Raises:
            ValueError: If num_pixels <= 0
        """
        super().__init__(num_pixels, config)
        self._sparkles: List[Sparkle] = []
        self._asymmetry_phase: float = 0.0
        self._bounce_timer: int = 0
        self._random_seed: int = int(time.monotonic() * 1000) % 65536
        random.seed(self._random_seed)

        # Pre-allocate right eye buffer for asymmetric rendering
        self._right_eye_buffer: List[RGB] = [(0, 0, 0)] * num_pixels

    def _compute_frame(self, base_color: RGB) -> List[RGB]:
        """
        Compute playful bouncy frame with asymmetry and sparkles.

        Implements the mischievous bouncy feel through variable timing
        and asymmetric brightness between implied "left" and "right" eyes.

        Args:
            base_color: Base RGB color (warm orange recommended)

        Returns:
            List of RGB tuples for left eye pixels
            (right eye available via render_both_eyes())
        """
        # Update asymmetry phase for winking effect
        # Using irregular sine for unpredictability (Disney: TIMING)
        self._asymmetry_phase += 0.08 * self.config.speed
        asymmetry = math.sin(self._asymmetry_phase * 2.3) * self.MAX_ASYMMETRY

        # Calculate bounce envelope (Disney: ANTICIPATION + EXAGGERATION)
        progress = self.get_progress(self.CYCLE_FRAMES)
        bounce = self._bounce_envelope(progress)

        # Base intensity with bounce
        intensity = self.BASE_INTENSITY + bounce * (self.BOUNCE_PEAK - self.BASE_INTENSITY)

        # Apply asymmetry (one eye slightly brighter for winking effect)
        left_intensity = intensity * (1.0 + asymmetry * 0.5)
        left_intensity = max(0.3, min(1.0, left_intensity))

        # Fill base pixels with bouncy intensity
        scaled = self._scale_color(base_color, min(left_intensity, 1.0))
        for i in range(self.num_pixels):
            self._pixel_buffer[i] = scaled

        # Update and render sparkles (Disney: SECONDARY ACTION)
        self._update_sparkles()
        self._maybe_spawn_sparkle()
        self._render_sparkles_to_buffer()

        return self._pixel_buffer

    def render_both_eyes(self, base_color: RGB) -> Tuple[List[RGB], List[RGB]]:
        """
        Render asymmetric left and right eye patterns.

        The playful pattern creates asymmetry between eyes for
        the mischievous "winking" effect.

        Args:
            base_color: Base RGB color

        Returns:
            Tuple of (left_eye_pixels, right_eye_pixels)
        """
        left = self._compute_frame(base_color)

        # Right eye with inverted asymmetry
        progress = self.get_progress(self.CYCLE_FRAMES)
        bounce = self._bounce_envelope(progress)
        asymmetry = math.sin(self._asymmetry_phase * 2.3) * self.MAX_ASYMMETRY

        right_intensity = (self.BASE_INTENSITY +
                         bounce * (self.BOUNCE_PEAK - self.BASE_INTENSITY))
        right_intensity = right_intensity * (1.0 - asymmetry * 0.5)
        right_intensity = max(0.3, min(1.0, right_intensity))

        scaled = self._scale_color(base_color, right_intensity)
        for i in range(self.num_pixels):
            self._right_eye_buffer[i] = scaled

        return (list(self._pixel_buffer), list(self._right_eye_buffer))

    def _bounce_envelope(self, progress: float) -> float:
        """
        Calculate bouncy envelope with anticipation dip.

        Creates the playful bounce feel:
        1. Slight dip (anticipation)
        2. Quick rise to peak
        3. Overshoot and settle

        Disney Principle: ANTICIPATION before action.

        Args:
            progress: Cycle progress (0.0 to 1.0)

        Returns:
            Envelope value (0.0 to 1.0)
        """
        # Multi-bounce using sine waves at different frequencies
        # Primary bounce
        primary = math.sin(progress * math.pi * 2) ** 2
        # Secondary bounce (faster, smaller amplitude)
        secondary = math.sin(progress * math.pi * 4) ** 2 * 0.3
        # Tertiary bounce (even faster, tiny)
        tertiary = math.sin(progress * math.pi * 6) ** 2 * 0.1

        return min(1.0, primary + secondary + tertiary)

    def _update_sparkles(self) -> None:
        """Update all active sparkles, removing expired ones."""
        surviving: List[Sparkle] = []
        for sparkle in self._sparkles:
            sparkle.lifetime_remaining -= 1
            sparkle.intensity *= (1.0 - sparkle.decay_rate)
            if sparkle.lifetime_remaining > 0 and sparkle.intensity > 0.05:
                surviving.append(sparkle)
        self._sparkles = surviving

    def _maybe_spawn_sparkle(self) -> None:
        """Possibly spawn a new sparkle particle."""
        if len(self._sparkles) >= MAX_SPARKLES:
            return

        if random.random() < self.SPARKLE_CHANCE * self.config.speed:
            pixel = random.randint(0, self.num_pixels - 1)
            color = random.choice(self.SPARKLE_COLORS)
            self._sparkles.append(Sparkle(
                pixel_index=pixel,
                intensity=1.0,
                color=color,
                lifetime_remaining=self.SPARKLE_LIFETIME,
                decay_rate=0.08,
            ))

    def _render_sparkles_to_buffer(self) -> None:
        """Render active sparkles onto pixel buffer."""
        for sparkle in self._sparkles:
            idx = sparkle.pixel_index
            if 0 <= idx < self.num_pixels:
                # Additive blend sparkle onto existing color
                existing = self._pixel_buffer[idx]
                sparkle_scaled = self._scale_color(sparkle.color, sparkle.intensity)
                blended = (
                    min(255, existing[0] + sparkle_scaled[0] // 2),
                    min(255, existing[1] + sparkle_scaled[1] // 2),
                    min(255, existing[2] + sparkle_scaled[2] // 2),
                )
                self._pixel_buffer[idx] = blended

    def reset(self) -> None:
        """Reset pattern state."""
        super().reset()
        self._sparkles.clear()
        self._asymmetry_phase = 0.0


# =============================================================================
# AffectionatePattern - Warm heartbeat with soft pink glow
# =============================================================================

class AffectionatePattern(PatternBase):
    """
    Affectionate/Love emotion pattern - warm, nurturing heartbeat.

    Creates the feeling of warm affection through:
    - Slow heartbeat pulse rhythm (72 BPM = 0.83s cycle)
    - Warm pink-coral color palette
    - Soft, enveloping glow
    - "Looking at you adoringly" steady brightness

    Psychology: Triggers oxytocin-associated bonding response.
    Color Psychology: Pink relates to unconditional love and nurturing.

    Disney Principles Applied:
    - TIMING: Slow heartbeat matches comfortable human rhythm
    - SLOW IN/SLOW OUT: Smooth transitions in pulse
    - APPEAL: Warm, inviting, never threatening

    Performance:
        Target: <2ms average frame time (simple pattern)
    """

    NAME = "affectionate"
    DESCRIPTION = "Warm heartbeat pulse with pink glow for affection"
    DEFAULT_SPEED = 1.0

    # Heartbeat timing (72 BPM = comfortable, warm rhythm)
    # 72 BPM = 60/72 = 0.833 seconds per beat = ~42 frames at 50Hz
    CYCLE_FRAMES = 42           # One heartbeat cycle
    PULSE_DURATION = 8          # Frames for main pulse
    REST_DURATION = 34          # Frames between pulses

    # Intensity levels
    BASE_INTENSITY = 0.5        # Warm baseline (never cold)
    PULSE_PEAK = 1.0            # Full brightness at pulse peak
    MIN_INTENSITY = 0.4         # Never go too dim (always warm)

    def __init__(self, num_pixels: int = 16, config: Optional[PatternConfig] = None):
        """
        Initialize affectionate pattern.

        Args:
            num_pixels: Number of LEDs per eye (default: 16)
            config: Optional PatternConfig (speed affects heartbeat rate)
        """
        super().__init__(num_pixels, config)

    def _compute_frame(self, base_color: RGB) -> List[RGB]:
        """
        Compute warm heartbeat pulse frame.

        Implements gentle heartbeat rhythm that creates feeling
        of warmth and nurturing presence.

        Args:
            base_color: Base RGB color (warm pink recommended)

        Returns:
            List of RGB tuples for pixels
        """
        # Calculate position within heartbeat cycle
        frame_in_cycle = int(self._frame * self.config.speed) % self.CYCLE_FRAMES

        # Determine intensity based on pulse phase
        if frame_in_cycle < self.PULSE_DURATION:
            # Main pulse with smooth envelope
            t = frame_in_cycle / self.PULSE_DURATION
            envelope = self._heartbeat_envelope(t)
            intensity = self.BASE_INTENSITY + envelope * (self.PULSE_PEAK - self.BASE_INTENSITY)
        else:
            # Rest period - gentle background warmth
            # Slight breathing during rest (Disney: SECONDARY ACTION)
            rest_progress = (frame_in_cycle - self.PULSE_DURATION) / self.REST_DURATION
            breath = math.sin(rest_progress * math.pi) * 0.1
            intensity = self.BASE_INTENSITY + breath

        # Ensure minimum warmth (never cold)
        intensity = max(self.MIN_INTENSITY, min(1.0, intensity))

        # Apply intensity to all pixels
        scaled = self._scale_color(base_color, intensity)
        for i in range(self.num_pixels):
            self._pixel_buffer[i] = scaled

        return self._pixel_buffer

    def _heartbeat_envelope(self, t: float) -> float:
        """
        Generate smooth heartbeat pulse envelope.

        Uses sine envelope for organic, natural feel.
        Disney Principle: SLOW IN/SLOW OUT.

        Args:
            t: Progress through pulse (0.0 to 1.0)

        Returns:
            Envelope value (0.0 at edges, 1.0 at peak)
        """
        # Sine envelope: 0 -> 1 -> 0 smoothly
        return math.sin(t * math.pi)

    def get_heart_rate_bpm(self) -> float:
        """
        Get effective heart rate in BPM.

        Returns:
            Heart rate in beats per minute
        """
        # Base rate: CYCLE_FRAMES at 50Hz
        base_bpm = (FRAME_RATE_HZ / self.CYCLE_FRAMES) * 60
        return base_bpm * self.config.speed


# =============================================================================
# EmpatheticPattern - Mirroring, supportive presence
# =============================================================================

class EmpatheticPattern(PatternBase):
    """
    Empathetic emotion pattern - mirroring, supportive presence.

    Creates the feeling of being understood through:
    - Synchronized breathing rhythm (matches calm human breath)
    - Soft, supportive color palette
    - Gentle following/mirroring visual cues
    - "I understand" dimming response

    Psychology: Triggers connection through perceived understanding.
    Mirroring is a fundamental social bonding mechanism.

    Disney Principles Applied:
    - TIMING: Breathing rhythm that feels supportive
    - FOLLOW THROUGH: Gentle settling after actions
    - APPEAL: Non-threatening, receptive presence

    Performance:
        Target: <2ms average frame time
    """

    NAME = "empathetic"
    DESCRIPTION = "Soft mirroring pattern showing understanding and support"
    DEFAULT_SPEED = 1.0

    # Breathing timing (12 breaths per minute = supportive, calm)
    # 12 BPM = 5 seconds per breath = 250 frames at 50Hz
    CYCLE_FRAMES = 250          # One full breath cycle
    INHALE_FRAMES = 100         # 2 seconds inhale
    EXHALE_FRAMES = 150         # 3 seconds exhale (longer = more calming)

    # Intensity levels (softer than other patterns - receptive)
    BASE_INTENSITY = 0.4        # Soft baseline
    PEAK_INTENSITY = 0.7        # Gentle peak (not overwhelming)
    MIN_INTENSITY = 0.3         # Always present

    # Mirror response parameters
    MIRROR_WAVE_SPEED = 0.02    # Slow wave for "following" effect

    def __init__(self, num_pixels: int = 16, config: Optional[PatternConfig] = None):
        """
        Initialize empathetic pattern.

        Args:
            num_pixels: Number of LEDs per eye (default: 16)
            config: Optional PatternConfig (speed affects breathing rate)
        """
        super().__init__(num_pixels, config)
        self._wave_phase: float = 0.0

    def _compute_frame(self, base_color: RGB) -> List[RGB]:
        """
        Compute empathetic mirroring frame.

        Implements gentle breathing with subtle spatial variation
        that creates "following" effect.

        Args:
            base_color: Base RGB color (soft lavender-blue recommended)

        Returns:
            List of RGB tuples for pixels
        """
        # Calculate breath phase
        frame_in_cycle = int(self._frame * self.config.speed) % self.CYCLE_FRAMES

        if frame_in_cycle < self.INHALE_FRAMES:
            # Inhale phase - gentle rise
            t = frame_in_cycle / self.INHALE_FRAMES
            breath = self._ease_in_out(t)
            base_breath = self.BASE_INTENSITY + breath * (self.PEAK_INTENSITY - self.BASE_INTENSITY)
        else:
            # Exhale phase - slow release
            t = (frame_in_cycle - self.INHALE_FRAMES) / self.EXHALE_FRAMES
            breath = 1.0 - self._ease_in_out(t)
            base_breath = self.BASE_INTENSITY + breath * (self.PEAK_INTENSITY - self.BASE_INTENSITY)

        # Update wave phase for spatial variation
        self._wave_phase += self.MIRROR_WAVE_SPEED * self.config.speed

        # Render with subtle spatial variation (mirroring effect)
        for i in range(self.num_pixels):
            # Spatial wave creates gentle "following" effect
            # H-001: O(1) angle normalization
            pixel_angle = (i / self.num_pixels) * 2 * math.pi
            wave_offset = math.sin(pixel_angle + self._wave_phase) * 0.1

            pixel_intensity = base_breath + wave_offset
            pixel_intensity = max(self.MIN_INTENSITY, min(self.PEAK_INTENSITY, pixel_intensity))

            self._pixel_buffer[i] = self._scale_color(base_color, pixel_intensity)

        return self._pixel_buffer

    @staticmethod
    def _ease_in_out(t: float) -> float:
        """
        Smooth ease-in-out function.

        Disney Principle: SLOW IN/SLOW OUT.

        Args:
            t: Progress (0.0 to 1.0)

        Returns:
            Eased value (0.0 to 1.0)
        """
        # Smoothstep: 3t^2 - 2t^3
        t = max(0.0, min(1.0, t))
        return t * t * (3 - 2 * t)


# =============================================================================
# GratefulPattern - Appreciative warm glow with brightness surge
# =============================================================================

class GratefulPattern(PatternBase):
    """
    Grateful emotion pattern - appreciative warm glow.

    Creates the feeling of gratitude through:
    - Brief brightness surge (like a bow of thanks)
    - Golden/amber warm tones
    - Gentle settling after surge
    - "Thank you" visual signature

    Psychology: Communicates appreciation and acknowledgment.
    Golden colors associated with warmth, value, appreciation.

    Disney Principles Applied:
    - ANTICIPATION: Slight dim before surge
    - FOLLOW THROUGH: Gentle settle after surge
    - EXAGGERATION: Bright surge for clear communication
    - TIMING: Quick surge, slow settle

    Performance:
        Target: <2ms average frame time
    """

    NAME = "grateful"
    DESCRIPTION = "Appreciative warm glow with brightness surge"
    DEFAULT_SPEED = 1.0

    # Timing parameters
    CYCLE_FRAMES = 120          # ~2.4 seconds per gratitude cycle
    ANTICIPATION_FRAMES = 10    # Brief dim before surge
    SURGE_FRAMES = 15           # Quick brightness surge
    HOLD_FRAMES = 10            # Brief hold at peak
    SETTLE_FRAMES = 85          # Long gentle settle

    # Intensity levels
    BASE_INTENSITY = 0.5        # Warm baseline
    ANTICIPATION_DIP = 0.4      # Slight dim before surge
    SURGE_PEAK = 1.0            # Full brightness surge

    def __init__(self, num_pixels: int = 16, config: Optional[PatternConfig] = None):
        """
        Initialize grateful pattern.

        Args:
            num_pixels: Number of LEDs per eye (default: 16)
            config: Optional PatternConfig (speed affects cycle rate)
        """
        super().__init__(num_pixels, config)
        self._top_to_bottom_phase: float = 0.0

    def _compute_frame(self, base_color: RGB) -> List[RGB]:
        """
        Compute grateful appreciation surge frame.

        Implements the "thank you" visual with:
        1. Anticipation dip
        2. Quick bright surge
        3. Brief hold
        4. Long gentle settle (like a bow)

        Args:
            base_color: Base RGB color (golden amber recommended)

        Returns:
            List of RGB tuples for pixels
        """
        frame_in_cycle = int(self._frame * self.config.speed) % self.CYCLE_FRAMES

        # Phase boundaries
        antic_end = self.ANTICIPATION_FRAMES
        surge_end = antic_end + self.SURGE_FRAMES
        hold_end = surge_end + self.HOLD_FRAMES
        # settle continues to CYCLE_FRAMES

        if frame_in_cycle < antic_end:
            # Anticipation dip (Disney: ANTICIPATION)
            t = frame_in_cycle / self.ANTICIPATION_FRAMES
            intensity = self.BASE_INTENSITY - t * (self.BASE_INTENSITY - self.ANTICIPATION_DIP)

        elif frame_in_cycle < surge_end:
            # Quick surge (Disney: EXAGGERATION)
            t = (frame_in_cycle - antic_end) / self.SURGE_FRAMES
            t_eased = self._ease_out(t)  # Quick rise
            intensity = self.ANTICIPATION_DIP + t_eased * (self.SURGE_PEAK - self.ANTICIPATION_DIP)

        elif frame_in_cycle < hold_end:
            # Brief hold at peak
            intensity = self.SURGE_PEAK

        else:
            # Long gentle settle (Disney: FOLLOW THROUGH)
            t = (frame_in_cycle - hold_end) / self.SETTLE_FRAMES
            t_eased = self._ease_in_out(t)
            intensity = self.SURGE_PEAK - t_eased * (self.SURGE_PEAK - self.BASE_INTENSITY)

        # Optional: Top-to-bottom wave during surge (like a bow)
        self._top_to_bottom_phase = frame_in_cycle / self.CYCLE_FRAMES

        # Apply intensity with subtle top-to-bottom variation during surge
        for i in range(self.num_pixels):
            pixel_intensity = intensity

            # During surge phase, add top-to-bottom wave (bow effect)
            if antic_end <= frame_in_cycle < hold_end:
                # Pixels at "top" (index 0) light up slightly before "bottom"
                # H-001: Handle num_pixels=1 edge case (avoid 0/0 division)
                if self.num_pixels <= 1:
                    pixel_position = 0.0
                else:
                    pixel_position = i / (self.num_pixels - 1)
                wave_offset = (1.0 - pixel_position) * 0.1 * math.sin(
                    (frame_in_cycle - antic_end) / self.SURGE_FRAMES * math.pi
                )
                pixel_intensity = min(1.0, intensity + wave_offset)

            self._pixel_buffer[i] = self._scale_color(base_color, pixel_intensity)

        return self._pixel_buffer

    @staticmethod
    def _ease_out(t: float) -> float:
        """
        Ease-out function for quick rise.

        Args:
            t: Progress (0.0 to 1.0)

        Returns:
            Eased value (0.0 to 1.0)
        """
        t = max(0.0, min(1.0, t))
        return 1 - (1 - t) ** 2

    @staticmethod
    def _ease_in_out(t: float) -> float:
        """
        Smooth ease-in-out function.

        Args:
            t: Progress (0.0 to 1.0)

        Returns:
            Eased value (0.0 to 1.0)
        """
        t = max(0.0, min(1.0, t))
        return t * t * (3 - 2 * t)


# =============================================================================
# Color Configuration for Social Emotions
# =============================================================================

SOCIAL_EMOTION_COLORS = {
    'playful': {
        'primary': COLOR_PLAYFUL_PRIMARY,      # Warm orange base
        'psychology': 'Bright, varied colors signal play and reduce social tension',
    },
    'affectionate': {
        'primary': COLOR_AFFECTIONATE_PRIMARY,  # Warm pink-coral
        'secondary': COLOR_AFFECTIONATE_SECONDARY,
        'psychology': 'Pink triggers nurturing response, warmth, unconditional love',
    },
    'empathetic': {
        'primary': COLOR_EMPATHETIC_PRIMARY,    # Soft lavender-blue
        'secondary': COLOR_EMPATHETIC_SECONDARY,
        'psychology': 'Soft cool tones convey receptiveness and understanding',
    },
    'grateful': {
        'primary': COLOR_GRATEFUL_PRIMARY,      # Golden amber
        'secondary': COLOR_GRATEFUL_SECONDARY,
        'psychology': 'Gold conveys appreciation, value, and warm gratitude',
    },
}


# =============================================================================
# Pattern Registry for Social Emotions
# =============================================================================

SOCIAL_PATTERN_REGISTRY = {
    'playful': PlayfulPattern,
    'affectionate': AffectionatePattern,
    'empathetic': EmpatheticPattern,
    'grateful': GratefulPattern,
}


__all__ = [
    'PlayfulPattern',
    'AffectionatePattern',
    'EmpatheticPattern',
    'GratefulPattern',
    'Sparkle',
    'SOCIAL_EMOTION_COLORS',
    'SOCIAL_PATTERN_REGISTRY',
    'MAX_SPARKLES',
]
