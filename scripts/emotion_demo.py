#!/usr/bin/env python3
"""
Emotion Demo Script - OpenDuck Mini V3
======================================
Day 10 - Pixar-Quality Emotion Showcase

Demonstrates all 8 emotions with proper transitions:
  1. IDLE     - Soft blue, 5s breathing, 30-70% brightness
  2. HAPPY    - Warm yellow, 1.5s pulse with sparkles, 60-100% brightness
  3. CURIOUS  - Teal cyan, 2s scanning rotation, 50-90% brightness
  4. ALERT    - Red-orange, 0.4s pulse with 2s flash, 70-100% brightness
  5. SAD      - Muted blue, 6s breathing with droop, 15-40% brightness
  6. SLEEPY   - Lavender, 8s breathing with blinks, 5-35% brightness
  7. EXCITED  - Orange, 0.8s spinning comet + rainbow sparkles, 80-100% brightness
  8. THINKING - Blue-white, 1.5s rotating segment + 0.6s pulses, 40-75% brightness

Hardware Configuration:
  Left Eye:  GPIO 18 (Pin 12), PWM Channel 0
  Right Eye: GPIO 13 (Pin 33), PWM Channel 1
  LEDs per ring: 16

Wire Colors:
  RED    = VCC (5V Power)
  BROWN  = DIN (Data Signal)
  ORANGE = GND (Ground)

Usage:
  sudo python3 emotion_demo.py              # Full demo cycle
  sudo python3 emotion_demo.py --emotion happy  # Test specific emotion
  sudo python3 emotion_demo.py --list       # List all emotions
  sudo python3 emotion_demo.py --benchmark  # Performance test

Based on: PIXAR_EMOTION_LED_PATTERNS.md
Disney Animation Principles: Slow In/Slow Out, Timing, Exaggeration, Appeal
"""

import time
import math
import random
import argparse
import sys
from dataclasses import dataclass
from enum import Enum
from typing import Tuple, List, Optional, Dict

# Raspberry Pi LED library
try:
    from rpi_ws281x import PixelStrip, Color
    PI_AVAILABLE = True
except ImportError:
    PI_AVAILABLE = False
    print("WARNING: rpi_ws281x not available - running in simulation mode")


# =============================================================================
# CONFIGURATION
# =============================================================================

# Hardware Setup
LEFT_EYE_PIN = 18       # GPIO 18, Physical Pin 12, PWM Channel 0
RIGHT_EYE_PIN = 13      # GPIO 13, Physical Pin 33, PWM Channel 1
NUM_LEDS = 16           # LEDs per ring
MAX_BRIGHTNESS = 60     # 0-255, power safety limit

# Animation Parameters
FRAME_RATE = 50         # Hz (50 FPS = 20ms frame time)
FRAME_TIME = 1.0 / FRAME_RATE

# Display time per emotion in demo cycle
EMOTION_DISPLAY_TIME = 5.0  # seconds

# Sparkle list growth limit (H-002: Prevent unbounded memory growth)
MAX_SPARKLES = 50


# =============================================================================
# EMOTION DEFINITIONS
# =============================================================================

class Emotion(Enum):
    """Robot emotional states with Pixar-quality visual expression."""
    IDLE = "idle"
    HAPPY = "happy"
    CURIOUS = "curious"
    ALERT = "alert"
    SAD = "sad"
    SLEEPY = "sleepy"
    EXCITED = "excited"
    THINKING = "thinking"


@dataclass
class EmotionConfig:
    """Configuration for emotion visual parameters."""
    primary_color: Tuple[int, int, int]     # RGB base color
    secondary_color: Tuple[int, int, int]   # RGB accent color
    brightness_min: float                    # 0.0 - 1.0
    brightness_max: float                    # 0.0 - 1.0
    cycle_duration: float                    # seconds
    description: str                         # For display


# Emotion configurations from PIXAR_EMOTION_LED_PATTERNS.md
EMOTION_CONFIGS: Dict[Emotion, EmotionConfig] = {
    Emotion.IDLE: EmotionConfig(
        primary_color=(100, 150, 255),       # Soft sky blue
        secondary_color=(80, 120, 230),      # Deeper blue
        brightness_min=0.30,
        brightness_max=0.70,
        cycle_duration=5.0,                  # 12 BPM breathing
        description="Calm, aware, breathing",
    ),
    Emotion.HAPPY: EmotionConfig(
        primary_color=(255, 200, 50),        # Warm golden yellow
        secondary_color=(255, 150, 30),      # Deeper orange
        brightness_min=0.60,
        brightness_max=1.00,
        cycle_duration=1.5,                  # Elevated heartbeat
        description="Joyful, warm, sparkling",
    ),
    Emotion.CURIOUS: EmotionConfig(
        primary_color=(50, 255, 180),        # Teal cyan
        secondary_color=(30, 200, 150),      # Deeper teal
        brightness_min=0.50,
        brightness_max=0.90,
        cycle_duration=2.0,                  # Scanning rotation
        description="Attentive, searching, focused",
    ),
    Emotion.ALERT: EmotionConfig(
        primary_color=(255, 80, 50),         # Warm red-orange
        secondary_color=(255, 40, 20),       # Deeper red
        brightness_min=0.70,
        brightness_max=1.00,
        cycle_duration=0.4,                  # Fast pulse (150 BPM)
        description="Sharp, urgent, warning",
    ),
    Emotion.SAD: EmotionConfig(
        primary_color=(80, 100, 180),        # Muted blue
        secondary_color=(60, 80, 150),       # Deeper muted blue
        brightness_min=0.15,
        brightness_max=0.40,
        cycle_duration=6.0,                  # Slow, low energy
        description="Withdrawn, dim, drooping",
    ),
    Emotion.SLEEPY: EmotionConfig(
        primary_color=(150, 120, 200),       # Soft lavender
        secondary_color=(120, 90, 170),      # Deeper purple
        brightness_min=0.05,
        brightness_max=0.35,
        cycle_duration=8.0,                  # Very slow breathing
        description="Drowsy, fading, peaceful",
    ),
    Emotion.EXCITED: EmotionConfig(
        primary_color=(255, 150, 50),        # Bright orange
        secondary_color=(255, 100, 30),      # Deeper orange
        brightness_min=0.80,
        brightness_max=1.00,
        cycle_duration=0.8,                  # Fast spinning
        description="Energetic, sparkling, dynamic",
    ),
    Emotion.THINKING: EmotionConfig(
        primary_color=(180, 180, 255),       # Soft blue-white
        secondary_color=(150, 150, 230),     # Deeper blue-white
        brightness_min=0.40,
        brightness_max=0.75,
        cycle_duration=1.5,                  # Steady rotation
        description="Processing, contemplating, pulsing",
    ),
}


# Transition timing matrix (seconds) from PIXAR_EMOTION_LED_PATTERNS.md
TRANSITION_TIMES: Dict[Tuple[Emotion, Emotion], float] = {
    # From IDLE
    (Emotion.IDLE, Emotion.HAPPY): 0.4,
    (Emotion.IDLE, Emotion.CURIOUS): 0.5,
    (Emotion.IDLE, Emotion.ALERT): 0.2,
    (Emotion.IDLE, Emotion.SAD): 0.8,
    (Emotion.IDLE, Emotion.SLEEPY): 1.2,
    (Emotion.IDLE, Emotion.EXCITED): 0.3,
    (Emotion.IDLE, Emotion.THINKING): 0.4,
    # From HAPPY
    (Emotion.HAPPY, Emotion.IDLE): 0.6,
    (Emotion.HAPPY, Emotion.CURIOUS): 0.4,
    (Emotion.HAPPY, Emotion.ALERT): 0.2,
    (Emotion.HAPPY, Emotion.EXCITED): 0.3,
    (Emotion.HAPPY, Emotion.THINKING): 0.5,
    # From CURIOUS
    (Emotion.CURIOUS, Emotion.IDLE): 0.5,
    (Emotion.CURIOUS, Emotion.HAPPY): 0.4,
    (Emotion.CURIOUS, Emotion.ALERT): 0.2,
    (Emotion.CURIOUS, Emotion.SAD): 0.6,
    (Emotion.CURIOUS, Emotion.THINKING): 0.3,
    # From ALERT
    (Emotion.ALERT, Emotion.IDLE): 0.5,
    (Emotion.ALERT, Emotion.CURIOUS): 0.4,
    (Emotion.ALERT, Emotion.HAPPY): 0.5,
    (Emotion.ALERT, Emotion.SAD): 0.6,
    (Emotion.ALERT, Emotion.THINKING): 0.4,
    # From SAD
    (Emotion.SAD, Emotion.IDLE): 1.0,
    (Emotion.SAD, Emotion.HAPPY): 0.6,
    (Emotion.SAD, Emotion.CURIOUS): 0.6,
    (Emotion.SAD, Emotion.ALERT): 0.2,
    (Emotion.SAD, Emotion.SLEEPY): 0.8,
    # From SLEEPY
    (Emotion.SLEEPY, Emotion.IDLE): 1.5,
    (Emotion.SLEEPY, Emotion.ALERT): 0.15,  # Startled awake
    (Emotion.SLEEPY, Emotion.CURIOUS): 0.8,
    # From EXCITED
    (Emotion.EXCITED, Emotion.IDLE): 0.8,
    (Emotion.EXCITED, Emotion.HAPPY): 0.4,
    (Emotion.EXCITED, Emotion.CURIOUS): 0.5,
    (Emotion.EXCITED, Emotion.ALERT): 0.2,
    (Emotion.EXCITED, Emotion.THINKING): 0.5,
    # From THINKING
    (Emotion.THINKING, Emotion.IDLE): 0.4,
    (Emotion.THINKING, Emotion.HAPPY): 0.5,
    (Emotion.THINKING, Emotion.SAD): 0.6,
    (Emotion.THINKING, Emotion.ALERT): 0.2,
    (Emotion.THINKING, Emotion.CURIOUS): 0.3,
    (Emotion.THINKING, Emotion.EXCITED): 0.4,
}


# =============================================================================
# EASING FUNCTIONS (Disney "Slow In / Slow Out")
# =============================================================================

def ease_in_out(t: float) -> float:
    """
    Smooth acceleration and deceleration.
    Disney Animation Principle: Slow In and Slow Out.
    """
    if t < 0.5:
        return 2 * t * t
    return 1 - pow(-2 * t + 2, 2) / 2


def ease_in(t: float) -> float:
    """Quick to respond, slow to settle."""
    return t * t


def ease_out(t: float) -> float:
    """Slow to start, quick to finish."""
    return 1 - (1 - t) ** 2


def lerp(a: float, b: float, t: float) -> float:
    """Linear interpolation between a and b."""
    return a + (b - a) * t


def lerp_color(c1: Tuple[int, int, int], c2: Tuple[int, int, int], t: float) -> Tuple[int, int, int]:
    """Linear interpolation between two RGB colors."""
    return (
        int(lerp(c1[0], c2[0], t)),
        int(lerp(c1[1], c2[1], t)),
        int(lerp(c1[2], c2[2], t)),
    )


# =============================================================================
# LED CONTROLLER
# =============================================================================

class LEDController:
    """
    Dual LED ring controller for OpenDuck eyes.
    Handles hardware initialization and pixel updates.
    """

    def __init__(self):
        self.left_eye: Optional[PixelStrip] = None
        self.right_eye: Optional[PixelStrip] = None
        self.num_leds = NUM_LEDS
        self.initialized = False

        # Pixel buffers (for simulation mode)
        self.left_buffer: List[Tuple[int, int, int]] = [(0, 0, 0)] * NUM_LEDS
        self.right_buffer: List[Tuple[int, int, int]] = [(0, 0, 0)] * NUM_LEDS

    def initialize(self) -> bool:
        """Initialize LED strips. Returns True on success."""
        if not PI_AVAILABLE:
            print("  [SIM] Simulating LED initialization")
            self.initialized = True
            return True

        try:
            print("Initializing LED rings...")

            # Left eye: GPIO 18, PWM Channel 0
            self.left_eye = PixelStrip(
                NUM_LEDS, LEFT_EYE_PIN, 800000, 10, False, MAX_BRIGHTNESS, 0
            )
            self.left_eye.begin()
            print(f"  Left eye  [OK] GPIO {LEFT_EYE_PIN}")

            # Right eye: GPIO 13, PWM Channel 1
            self.right_eye = PixelStrip(
                NUM_LEDS, RIGHT_EYE_PIN, 800000, 10, False, MAX_BRIGHTNESS, 1
            )
            self.right_eye.begin()
            print(f"  Right eye [OK] GPIO {RIGHT_EYE_PIN}")

            self.initialized = True
            return True

        except Exception as e:
            print(f"  [ERROR] LED initialization failed: {e}")
            return False

    def set_pixel(self, eye: str, index: int, r: int, g: int, b: int):
        """Set a single pixel color. eye='left' or 'right'."""
        r = max(0, min(255, int(r)))
        g = max(0, min(255, int(g)))
        b = max(0, min(255, int(b)))

        if eye == 'left':
            self.left_buffer[index] = (r, g, b)
            if self.left_eye:
                self.left_eye.setPixelColor(index, Color(r, g, b))
        else:
            self.right_buffer[index] = (r, g, b)
            if self.right_eye:
                self.right_eye.setPixelColor(index, Color(r, g, b))

    def set_all(self, r: int, g: int, b: int):
        """Set all pixels on both eyes to the same color."""
        for i in range(self.num_leds):
            self.set_pixel('left', i, r, g, b)
            self.set_pixel('right', i, r, g, b)

    def set_pixels_from_list(self, eye: str, pixels: List[Tuple[int, int, int]]):
        """Set all pixels from a list of RGB tuples."""
        for i, (r, g, b) in enumerate(pixels):
            self.set_pixel(eye, i, r, g, b)

    def show(self):
        """Push pixel data to hardware."""
        if self.left_eye:
            self.left_eye.show()
        if self.right_eye:
            self.right_eye.show()

    def clear(self):
        """Turn off all LEDs."""
        self.set_all(0, 0, 0)
        self.show()


# =============================================================================
# EMOTION PATTERN RENDERERS
# =============================================================================

class EmotionRenderer:
    """
    Renders Pixar-quality LED patterns for each emotion.
    Each pattern applies specific Disney Animation Principles.
    """

    def __init__(self, num_leds: int = 16):
        # H-003: Validate num_leds to prevent division by zero in _render_curious
        if num_leds <= 0:
            raise ValueError("num_leds must be positive")
        self.num_leds = num_leds

        # State for stateful patterns
        self.happy_sparkles: List[Dict] = []
        self.sleepy_next_blink = random.uniform(4, 6)
        self.sleepy_blink_timer = 0.0
        self.sleepy_in_blink = False
        self.excited_sparkles: List[Dict] = []

    def reset_state(self):
        """Reset pattern state for clean transitions."""
        self.happy_sparkles = []
        self.sleepy_next_blink = random.uniform(4, 6)
        self.sleepy_blink_timer = 0.0
        self.sleepy_in_blink = False
        self.excited_sparkles = []

    def render(self, emotion: Emotion, t: float) -> Tuple[List[Tuple[int, int, int]], List[Tuple[int, int, int]]]:
        """
        Render emotion pattern at time t.

        Returns:
            (left_pixels, right_pixels) - Lists of 16 RGB tuples each
        """
        if emotion == Emotion.IDLE:
            return self._render_idle(t)
        elif emotion == Emotion.HAPPY:
            return self._render_happy(t)
        elif emotion == Emotion.CURIOUS:
            return self._render_curious(t)
        elif emotion == Emotion.ALERT:
            return self._render_alert(t)
        elif emotion == Emotion.SAD:
            return self._render_sad(t)
        elif emotion == Emotion.SLEEPY:
            return self._render_sleepy(t)
        elif emotion == Emotion.EXCITED:
            return self._render_excited(t)
        elif emotion == Emotion.THINKING:
            return self._render_thinking(t)
        else:
            # Fallback: dim blue
            pixels = [(50, 50, 100)] * self.num_leds
            return pixels, pixels

    def _render_idle(self, t: float) -> Tuple[List, List]:
        """
        IDLE: Calm breathing with spatial variation.

        Disney Principle: SLOW IN AND SLOW OUT
        The brightness changes gradually accelerate from rest.
        """
        config = EMOTION_CONFIGS[Emotion.IDLE]
        r_base, g_base, b_base = config.primary_color

        # 5-second breathing cycle (Gaussian-like: exp(sin(x)))
        cycle_phase = (t % config.cycle_duration) / config.cycle_duration
        breath_raw = math.exp(math.sin(2 * math.pi * cycle_phase - math.pi / 2))
        breath = (breath_raw - 0.368) / 2.35  # Normalize to 0-1

        # Apply ease_in_out for extra smoothness
        breath_eased = ease_in_out(breath)

        left_pixels = []
        right_pixels = []

        for i in range(self.num_leds):
            # Subtle spatial wave (organic shimmer)
            spatial_offset = math.sin(i * math.pi / 8) * 0.05
            spatial_mod = spatial_offset * math.sin(t * 0.5)

            # Brightness: 30% to 70%
            brightness = config.brightness_min + (config.brightness_max - config.brightness_min) * breath_eased
            brightness += spatial_mod
            brightness = max(config.brightness_min, min(config.brightness_max, brightness))

            r = int(r_base * brightness)
            g = int(g_base * brightness)
            b = int(b_base * brightness)

            left_pixels.append((r, g, b))
            right_pixels.append((r, g, b))

        return left_pixels, right_pixels

    def _render_happy(self, t: float) -> Tuple[List, List]:
        """
        HAPPY: Warm pulsing with random sparkles.

        Disney Principles: EXAGGERATION + SECONDARY ACTION
        Colors more saturated, sparkles add life.
        """
        config = EMOTION_CONFIGS[Emotion.HAPPY]
        r_base, g_base, b_base = config.primary_color

        # 1.5s pulse (ease-out: quick rise, slow settle)
        pulse_phase = (t % config.cycle_duration) / config.cycle_duration
        if pulse_phase < 0.3:
            pulse = pulse_phase / 0.3  # Quick rise
        else:
            pulse = (1 - pulse_phase) / 0.7  # Slow settle
        pulse = max(0, min(1, pulse))

        # Brightness: 60% to 100%
        base_brightness = config.brightness_min + (config.brightness_max - config.brightness_min) * pulse

        # Manage sparkles (3-5 random LEDs twinkling)
        if random.random() < 0.15:  # ~7.5 sparkles/second at 50fps
            pos = random.randint(0, self.num_leds - 1)
            if pos not in [s['pos'] for s in self.happy_sparkles]:
                self.happy_sparkles.append({'pos': pos, 'timer': 0.2})

        # Decay sparkles
        new_sparkles = []
        for s in self.happy_sparkles:
            s['timer'] -= FRAME_TIME
            if s['timer'] > 0:
                new_sparkles.append(s)
        self.happy_sparkles = new_sparkles

        # H-002: Cap sparkle list growth to prevent unbounded memory usage
        if len(self.happy_sparkles) > MAX_SPARKLES:
            self.happy_sparkles = self.happy_sparkles[-MAX_SPARKLES:]

        left_pixels = []
        right_pixels = []

        for i in range(self.num_leds):
            sparkle_match = next((s for s in self.happy_sparkles if s['pos'] == i), None)

            if sparkle_match:
                # Sparkle: bright white-yellow
                intensity = sparkle_match['timer'] / 0.2  # Fade out
                r = int(255 * intensity + r_base * (1 - intensity) * base_brightness)
                g = int(255 * intensity + g_base * (1 - intensity) * base_brightness)
                b = int(200 * intensity + b_base * (1 - intensity) * base_brightness)
            else:
                # Base warm yellow
                r = int(r_base * base_brightness)
                g = int(g_base * base_brightness)
                b = int(b_base * base_brightness)

            r = min(255, r)
            g = min(255, g)
            b = min(255, b)

            left_pixels.append((r, g, b))
            right_pixels.append((r, g, b))

        return left_pixels, right_pixels

    def _render_curious(self, t: float) -> Tuple[List, List]:
        """
        CURIOUS: Rotating attention point scanning around.

        Disney Principle: FOLLOW THROUGH
        The attention spot leads, brightness trails behind.
        """
        config = EMOTION_CONFIGS[Emotion.CURIOUS]
        r_base, g_base, b_base = config.primary_color

        # 2-second rotation
        rotation_phase = (t % config.cycle_duration) / config.cycle_duration
        focus_position = rotation_phase * self.num_leds

        # Base breathing underneath
        breath = 0.5 + 0.2 * math.sin(t * math.pi / 2)

        left_pixels = []
        right_pixels = []

        for i in range(self.num_leds):
            # Circular distance from focus point
            distance = min(
                abs(i - focus_position),
                self.num_leds - abs(i - focus_position)
            )

            # Gaussian focus intensity (~3 LED spread)
            focus_intensity = math.exp(-(distance ** 2) / 4.5)

            # Combined brightness
            brightness = breath * 0.5 + focus_intensity * 0.5
            brightness = config.brightness_min + (config.brightness_max - config.brightness_min) * brightness

            # Color: brighter cyan at focus
            r = int((r_base + 50 * focus_intensity) * brightness)
            g = int((g_base - 55 * (1 - focus_intensity)) * brightness)
            b = int((b_base + 40 * focus_intensity) * brightness)

            left_pixels.append((min(255, r), min(255, g), min(255, b)))

            # Mirror for right eye (eyes converge on focus)
            mirror_i = (self.num_leds - 1 - i) % self.num_leds
            distance_r = min(
                abs(mirror_i - focus_position),
                self.num_leds - abs(mirror_i - focus_position)
            )
            focus_intensity_r = math.exp(-(distance_r ** 2) / 4.5)
            brightness_r = breath * 0.5 + focus_intensity_r * 0.5
            brightness_r = config.brightness_min + (config.brightness_max - config.brightness_min) * brightness_r

            r_r = int((r_base + 50 * focus_intensity_r) * brightness_r)
            g_r = int((g_base - 55 * (1 - focus_intensity_r)) * brightness_r)
            b_r = int((b_base + 40 * focus_intensity_r) * brightness_r)

            right_pixels.append((min(255, r_r), min(255, g_r), min(255, b_r)))

        return left_pixels, right_pixels

    def _render_alert(self, t: float) -> Tuple[List, List]:
        """
        ALERT: Rapid pulsing with periodic flashes.

        Disney Principle: TIMING
        Fast timing = urgent, dangerous.
        """
        config = EMOTION_CONFIGS[Emotion.ALERT]
        r_base, g_base, b_base = config.primary_color

        # Fast pulse (0.4s = 150 BPM)
        pulse_phase = (t % config.cycle_duration) / config.cycle_duration
        if pulse_phase < 0.15:
            pulse = pulse_phase / 0.15  # Sharp attack
        else:
            pulse = 1 - (pulse_phase - 0.15) / 0.85  # Slower decay

        # Periodic flash every 2 seconds
        flash_phase = t % 2.0
        flash_active = flash_phase < 0.1  # 100ms flash

        left_pixels = []
        right_pixels = []

        for i in range(self.num_leds):
            if flash_active:
                # Bright warning flash
                r, g, b = 255, 150, 100
                brightness = 1.0
            else:
                # Base alert pulse
                brightness = config.brightness_min + (config.brightness_max - config.brightness_min) * pulse
                r, g, b = r_base, g_base, b_base

            r = int(r * brightness)
            g = int(g * brightness)
            b = int(b * brightness)

            left_pixels.append((r, g, b))
            right_pixels.append((r, g, b))

        return left_pixels, right_pixels

    def _render_sad(self, t: float) -> Tuple[List, List]:
        """
        SAD: Slow breathing with top-heavy dimming (drooping).

        Disney Principle: APPEAL through VULNERABILITY
        Dim, withdrawn appearance evokes empathy.
        """
        config = EMOTION_CONFIGS[Emotion.SAD]
        r_base, g_base, b_base = config.primary_color

        # Slow breathing (6 seconds)
        breath_phase = (t % config.cycle_duration) / config.cycle_duration
        breath = 0.5 + 0.5 * math.sin(2 * math.pi * breath_phase - math.pi / 2)

        # Ease-in: slow to rise, quick to fall (reluctant)
        breath_eased = breath * breath

        left_pixels = []
        right_pixels = []

        for i in range(self.num_leds):
            # Droop effect: top LEDs dimmer (LED 8 at top, 0 at bottom)
            vertical_position = math.sin(i * math.pi / 8)  # -1 to 1
            droop_factor = 0.7 + 0.3 * (1 - vertical_position) / 2  # Top=0.7, Bottom=1.0

            # Very low brightness range
            brightness = (config.brightness_min + (config.brightness_max - config.brightness_min) * breath_eased) * droop_factor

            r = int(r_base * brightness)
            g = int(g_base * brightness)
            b = int(b_base * brightness)

            left_pixels.append((r, g, b))
            right_pixels.append((r, g, b))

        return left_pixels, right_pixels

    def _render_sleepy(self, t: float) -> Tuple[List, List]:
        """
        SLEEPY: Ultra-slow breathing with periodic long blinks.

        Disney Principles: TIMING + STRAIGHT AHEAD ACTION
        Slow timing = peaceful. Random blinks = organic.
        """
        config = EMOTION_CONFIGS[Emotion.SLEEPY]
        r_base, g_base, b_base = config.primary_color

        # Check for blink
        if not self.sleepy_in_blink:
            self.sleepy_next_blink -= FRAME_TIME
            if self.sleepy_next_blink <= 0:
                self.sleepy_in_blink = True
                self.sleepy_blink_timer = 0.4  # 400ms blink
        else:
            self.sleepy_blink_timer -= FRAME_TIME
            if self.sleepy_blink_timer <= 0:
                self.sleepy_in_blink = False
                self.sleepy_next_blink = random.uniform(4, 6)

        # Very slow breathing (8 seconds)
        breath_phase = (t % config.cycle_duration) / config.cycle_duration
        breath = 0.5 + 0.5 * math.sin(2 * math.pi * breath_phase - math.pi / 2)
        breath_eased = ease_in_out(breath)

        # Blink modulation
        if self.sleepy_in_blink:
            blink_phase = 1 - (self.sleepy_blink_timer / 0.4)
            if blink_phase < 0.5:
                blink_dim = 1 - (blink_phase * 2)  # Closing
            else:
                blink_dim = (blink_phase - 0.5) * 2  # Opening
            blink_dim = blink_dim * blink_dim  # Reluctant to open
        else:
            blink_dim = 1.0

        # Final brightness
        brightness = (config.brightness_min + (config.brightness_max - config.brightness_min) * breath_eased) * blink_dim

        left_pixels = []
        right_pixels = []

        for i in range(self.num_leds):
            r = int(r_base * brightness)
            g = int(g_base * brightness)
            b = int(b_base * brightness)

            left_pixels.append((r, g, b))
            right_pixels.append((r, g, b))

        return left_pixels, right_pixels

    def _render_excited(self, t: float) -> Tuple[List, List]:
        """
        EXCITED: Fast spinning comet with rainbow sparkle explosions.

        Disney Principles: EXAGGERATION + SQUASH AND STRETCH
        Everything amplified to maximum.
        """
        config = EMOTION_CONFIGS[Emotion.EXCITED]
        r_base, g_base, b_base = config.primary_color

        # Fast spin (0.8s rotation)
        spin_phase = (t % config.cycle_duration) / config.cycle_duration
        comet_pos = spin_phase * self.num_leds

        # Add new sparkles frequently
        if random.random() < 0.25:  # ~12 sparkles/second at 50fps
            self.excited_sparkles.append({
                'pos': random.randint(0, self.num_leds - 1),
                'timer': 0.15,
                'hue': random.random()  # Rainbow!
            })

        # Update sparkles
        new_sparkles = []
        for s in self.excited_sparkles:
            s['timer'] -= FRAME_TIME
            if s['timer'] > 0:
                new_sparkles.append(s)
        self.excited_sparkles = new_sparkles

        # H-002: Cap sparkle list growth to prevent unbounded memory usage
        if len(self.excited_sparkles) > MAX_SPARKLES:
            self.excited_sparkles = self.excited_sparkles[-MAX_SPARKLES:]

        left_pixels = []
        right_pixels = []

        for i in range(self.num_leds):
            # Check for sparkle
            sparkle = next((s for s in self.excited_sparkles if s['pos'] == i), None)

            if sparkle:
                # Rainbow sparkle
                intensity = sparkle['timer'] / 0.15
                hue = sparkle['hue']
                r, g, b = self._hsv_to_rgb(hue, 1.0, intensity)
                r = int(r * 255)
                g = int(g * 255)
                b = int(b * 255)
            else:
                # Spinning comet
                distance = min(
                    abs(i - comet_pos),
                    self.num_leds - abs(i - comet_pos)
                )

                # Comet with 4-LED tail
                if distance < 4:
                    comet_intensity = 1 - (distance / 4)
                    comet_intensity = comet_intensity ** 0.5
                    brightness = config.brightness_min + (config.brightness_max - config.brightness_min) * comet_intensity
                else:
                    brightness = config.brightness_min

                r = int(r_base * brightness)
                g = int(g_base * brightness * (1 - 0.3 * (comet_intensity if distance < 4 else 0)))
                b = int(b_base * brightness)

            left_pixels.append((min(255, r), min(255, g), min(255, b)))

            # Right eye: counter-rotating
            mirror_i = (self.num_leds - 1 - i) % self.num_leds
            comet_pos_r = self.num_leds - comet_pos
            distance_r = min(
                abs(mirror_i - comet_pos_r),
                self.num_leds - abs(mirror_i - comet_pos_r)
            )

            sparkle_r = next((s for s in self.excited_sparkles if s['pos'] == mirror_i), None)

            if sparkle_r:
                intensity = sparkle_r['timer'] / 0.15
                hue = sparkle_r['hue']
                r_r, g_r, b_r = self._hsv_to_rgb(hue, 1.0, intensity)
                r_r = int(r_r * 255)
                g_r = int(g_r * 255)
                b_r = int(b_r * 255)
            else:
                if distance_r < 4:
                    comet_intensity_r = 1 - (distance_r / 4)
                    comet_intensity_r = comet_intensity_r ** 0.5
                    brightness_r = config.brightness_min + (config.brightness_max - config.brightness_min) * comet_intensity_r
                else:
                    brightness_r = config.brightness_min

                r_r = int(r_base * brightness_r)
                g_r = int(g_base * brightness_r * (1 - 0.3 * (comet_intensity_r if distance_r < 4 else 0)))
                b_r = int(b_base * brightness_r)

            right_pixels.append((min(255, r_r), min(255, g_r), min(255, b_r)))

        return left_pixels, right_pixels

    def _render_thinking(self, t: float) -> Tuple[List, List]:
        """
        THINKING: Rotating segment with periodic brightness pulses.

        Disney Principles: TIMING (mechanical) + SECONDARY ACTION
        Linear timing suggests logical processing.
        """
        config = EMOTION_CONFIGS[Emotion.THINKING]
        r_base, g_base, b_base = config.primary_color

        # Steady rotation (1.5s cycle)
        rotation_phase = (t % config.cycle_duration) / config.cycle_duration
        segment_center = rotation_phase * self.num_leds

        # Periodic pulse every 0.6 seconds
        pulse_phase = (t % 0.6) / 0.6
        pulse = 0.5 + 0.5 * math.cos(2 * math.pi * pulse_phase)

        left_pixels = []
        right_pixels = []

        for i in range(self.num_leds):
            # Segment: 6-8 LEDs bright
            distance = min(
                abs(i - segment_center),
                self.num_leds - abs(i - segment_center)
            )

            if distance < 3:
                segment_brightness = 1.0
            elif distance < 4:
                segment_brightness = 1 - (distance - 3)
            else:
                segment_brightness = 0.3

            # Combine segment + pulse
            brightness = config.brightness_min + (config.brightness_max - config.brightness_min) * (segment_brightness * 0.7 + pulse * 0.3)

            # Color: whiter at segment, bluer in background
            if distance < 4:
                r = int(220 * brightness)
                g = int(220 * brightness)
                b = int(255 * brightness)
            else:
                r = int(150 * brightness)
                g = int(150 * brightness)
                b = int(230 * brightness)

            left_pixels.append((r, g, b))
            right_pixels.append((r, g, b))

        return left_pixels, right_pixels

    @staticmethod
    def _hsv_to_rgb(h: float, s: float, v: float) -> Tuple[float, float, float]:
        """Convert HSV (0-1 range) to RGB (0-1 range)."""
        if s == 0:
            return v, v, v

        i = int(h * 6)
        f = (h * 6) - i
        p = v * (1 - s)
        q = v * (1 - s * f)
        t = v * (1 - s * (1 - f))
        i = i % 6

        if i == 0:
            return v, t, p
        if i == 1:
            return q, v, p
        if i == 2:
            return p, v, t
        if i == 3:
            return p, q, v
        if i == 4:
            return t, p, v
        if i == 5:
            return v, p, q
        return v, v, v


# =============================================================================
# EMOTION DEMO ENGINE
# =============================================================================

class EmotionDemo:
    """
    Main demonstration engine for emotion showcase.
    Handles animation loop, transitions, and performance logging.
    """

    def __init__(self):
        self.led = LEDController()
        self.renderer = EmotionRenderer(NUM_LEDS)
        self.current_emotion = Emotion.IDLE
        self.frame_times: List[float] = []
        self.running = False

    def initialize(self) -> bool:
        """Initialize hardware."""
        print("=" * 70)
        print("     OpenDuck Mini V3 - Pixar-Quality Emotion Demo")
        print("=" * 70)
        print(f"  Left Eye:  GPIO {LEFT_EYE_PIN} (Pin 12) - PWM Channel 0")
        print(f"  Right Eye: GPIO {RIGHT_EYE_PIN} (Pin 33) - PWM Channel 1")
        print(f"  LEDs per ring: {NUM_LEDS}")
        print(f"  Frame rate: {FRAME_RATE} Hz")
        print("=" * 70)
        print()

        return self.led.initialize()

    def get_transition_time(self, from_emotion: Emotion, to_emotion: Emotion) -> float:
        """Get transition duration between two emotions."""
        key = (from_emotion, to_emotion)
        if key in TRANSITION_TIMES:
            return TRANSITION_TIMES[key]
        # Default: 0.5 seconds
        return 0.5

    def transition_to(self, target_emotion: Emotion):
        """
        Smoothly transition from current emotion to target.
        Uses color morphing with ease_in_out timing.
        """
        if target_emotion == self.current_emotion:
            return

        from_config = EMOTION_CONFIGS[self.current_emotion]
        to_config = EMOTION_CONFIGS[target_emotion]
        duration = self.get_transition_time(self.current_emotion, target_emotion)

        print(f"\n  Transition: {self.current_emotion.value} -> {target_emotion.value} ({duration:.2f}s)")

        start_time = time.monotonic()
        elapsed = 0.0

        while elapsed < duration:
            t_frame_start = time.monotonic()

            # Calculate progress with easing
            progress = elapsed / duration
            eased_progress = ease_in_out(progress)

            # Interpolate colors
            color = lerp_color(from_config.primary_color, to_config.primary_color, eased_progress)

            # Interpolate brightness
            brightness = lerp(
                (from_config.brightness_min + from_config.brightness_max) / 2,
                (to_config.brightness_min + to_config.brightness_max) / 2,
                eased_progress
            )

            # Apply to all LEDs
            r = int(color[0] * brightness)
            g = int(color[1] * brightness)
            b = int(color[2] * brightness)
            self.led.set_all(r, g, b)
            self.led.show()

            # Frame timing
            t_frame_end = time.monotonic()
            frame_time = t_frame_end - t_frame_start
            sleep_time = FRAME_TIME - frame_time
            if sleep_time > 0:
                time.sleep(sleep_time)

            elapsed = time.monotonic() - start_time

        # Reset renderer state for new emotion
        self.renderer.reset_state()
        self.current_emotion = target_emotion

    def display_emotion(self, emotion: Emotion, duration: float):
        """
        Display a single emotion for specified duration.
        Logs performance metrics.
        """
        config = EMOTION_CONFIGS[emotion]
        print(f"\n  [{emotion.value.upper()}] {config.description}")
        print(f"    Color: RGB{config.primary_color}")
        print(f"    Brightness: {config.brightness_min*100:.0f}% - {config.brightness_max*100:.0f}%")
        print(f"    Cycle: {config.cycle_duration:.1f}s")

        start_time = time.monotonic()
        elapsed = 0.0
        local_frame_times = []

        while elapsed < duration:
            t_frame_start = time.monotonic()

            # Render current emotion
            left_pixels, right_pixels = self.renderer.render(emotion, elapsed)

            # Apply to LEDs
            self.led.set_pixels_from_list('left', left_pixels)
            self.led.set_pixels_from_list('right', right_pixels)
            self.led.show()

            # Frame timing
            t_frame_end = time.monotonic()
            frame_time_ms = (t_frame_end - t_frame_start) * 1000
            local_frame_times.append(frame_time_ms)
            self.frame_times.append(frame_time_ms)

            sleep_time = FRAME_TIME - (t_frame_end - t_frame_start)
            if sleep_time > 0:
                time.sleep(sleep_time)

            elapsed = time.monotonic() - start_time

        # Log performance for this emotion
        if local_frame_times:
            avg = sum(local_frame_times) / len(local_frame_times)
            max_time = max(local_frame_times)
            print(f"    Performance: avg={avg:.3f}ms, max={max_time:.3f}ms")

    def run_single_emotion(self, emotion: Emotion, duration: float = 10.0):
        """Run a single emotion for testing."""
        print(f"\n  Testing: {emotion.value.upper()}")
        self.renderer.reset_state()
        self.display_emotion(emotion, duration)

    def run_demo_cycle(self):
        """
        Run the full 8-emotion demonstration cycle.
        Each emotion displayed for 5 seconds with transitions.
        """
        print("\n" + "=" * 70)
        print("                    STARTING DEMO CYCLE")
        print("=" * 70)

        # Demo sequence with natural emotional flow
        demo_sequence = [
            Emotion.IDLE,      # Start calm
            Emotion.CURIOUS,   # Something caught attention
            Emotion.THINKING,  # Processing...
            Emotion.HAPPY,     # Figured it out!
            Emotion.EXCITED,   # Great news!
            Emotion.ALERT,     # Wait, what's that?
            Emotion.SAD,       # False alarm, feeling down
            Emotion.SLEEPY,    # Time to rest
            Emotion.IDLE,      # Back to calm
        ]

        self.running = True
        self.renderer.reset_state()

        try:
            for i, emotion in enumerate(demo_sequence):
                if not self.running:
                    break

                print(f"\n  [{i+1}/{len(demo_sequence)}] Emotion: {emotion.value.upper()}")

                if i == 0:
                    # First emotion: no transition
                    self.current_emotion = emotion
                else:
                    # Transition from previous
                    self.transition_to(emotion)

                # Display emotion
                self.display_emotion(emotion, EMOTION_DISPLAY_TIME)

            print("\n" + "=" * 70)
            print("               DEMO CYCLE COMPLETE")
            print("=" * 70)

            # Print overall performance
            if self.frame_times:
                avg = sum(self.frame_times) / len(self.frame_times)
                max_time = max(self.frame_times)
                print(f"\n  Overall Performance:")
                print(f"    Total frames: {len(self.frame_times)}")
                print(f"    Avg frame time: {avg:.3f}ms")
                print(f"    Max frame time: {max_time:.3f}ms")
                print(f"    Target: {FRAME_TIME*1000:.1f}ms ({FRAME_RATE} FPS)")

        except KeyboardInterrupt:
            print("\n\n  Demo interrupted by user.")
            self.running = False

    def run_continuous(self):
        """Run continuous idle breathing."""
        print("\n  Running continuous IDLE... (Ctrl+C to exit)")
        self.running = True
        self.renderer.reset_state()

        start_time = time.monotonic()

        try:
            while self.running:
                t_frame_start = time.monotonic()
                elapsed = t_frame_start - start_time

                left_pixels, right_pixels = self.renderer.render(Emotion.IDLE, elapsed)
                self.led.set_pixels_from_list('left', left_pixels)
                self.led.set_pixels_from_list('right', right_pixels)
                self.led.show()

                t_frame_end = time.monotonic()
                sleep_time = FRAME_TIME - (t_frame_end - t_frame_start)
                if sleep_time > 0:
                    time.sleep(sleep_time)

        except KeyboardInterrupt:
            print("\n  Exiting...")
            self.running = False

    def run_benchmark(self):
        """Performance benchmark for all emotions."""
        print("\n" + "=" * 70)
        print("              EMOTION RENDERING BENCHMARK")
        print("=" * 70)

        results = {}

        for emotion in Emotion:
            print(f"\n  Benchmarking: {emotion.value}")
            self.renderer.reset_state()

            frame_times = []
            for i in range(250):  # 5 seconds at 50fps
                t_start = time.monotonic()
                self.renderer.render(emotion, i * FRAME_TIME)
                t_end = time.monotonic()
                frame_times.append((t_end - t_start) * 1000)

            avg = sum(frame_times) / len(frame_times)
            max_time = max(frame_times)
            min_time = min(frame_times)

            results[emotion] = {
                'avg': avg,
                'max': max_time,
                'min': min_time
            }

            print(f"    avg={avg:.4f}ms, max={max_time:.4f}ms, min={min_time:.4f}ms")

        print("\n" + "=" * 70)
        print("                    BENCHMARK SUMMARY")
        print("=" * 70)
        print(f"\n  {'Emotion':<12} {'Avg (ms)':<12} {'Max (ms)':<12} {'Status'}")
        print("  " + "-" * 50)

        for emotion, metrics in results.items():
            status = "PASS" if metrics['avg'] < 2.0 and metrics['max'] < 10.0 else "WARN"
            print(f"  {emotion.value:<12} {metrics['avg']:<12.4f} {metrics['max']:<12.4f} {status}")

        print("\n  Target: avg < 2.0ms, max < 10.0ms")

    def cleanup(self):
        """Clean shutdown."""
        print("\n  Turning off LEDs...")
        self.led.clear()
        print("  Goodbye!")


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================

def list_emotions():
    """Print list of all emotions with descriptions."""
    print("\nAvailable Emotions:")
    print("-" * 60)
    for emotion in Emotion:
        config = EMOTION_CONFIGS[emotion]
        print(f"  {emotion.value:<12} - {config.description}")
    print()


def main():
    parser = argparse.ArgumentParser(
        description="OpenDuck Mini V3 - Pixar-Quality Emotion Demo",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  sudo python3 emotion_demo.py              # Run full demo cycle
  sudo python3 emotion_demo.py --emotion happy   # Test HAPPY emotion
  sudo python3 emotion_demo.py --list       # List all emotions
  sudo python3 emotion_demo.py --benchmark  # Performance test
  sudo python3 emotion_demo.py --continuous # Continuous idle mode
        """
    )

    parser.add_argument(
        '--emotion', '-e',
        type=str,
        choices=[e.value for e in Emotion],
        help='Test a specific emotion'
    )
    parser.add_argument(
        '--duration', '-d',
        type=float,
        default=10.0,
        help='Duration for single emotion test (default: 10s)'
    )
    parser.add_argument(
        '--list', '-l',
        action='store_true',
        help='List all available emotions'
    )
    parser.add_argument(
        '--benchmark', '-b',
        action='store_true',
        help='Run performance benchmark'
    )
    parser.add_argument(
        '--continuous', '-c',
        action='store_true',
        help='Run continuous idle mode'
    )

    args = parser.parse_args()

    if args.list:
        list_emotions()
        return

    demo = EmotionDemo()

    if not demo.initialize():
        print("Failed to initialize. Exiting.")
        sys.exit(1)

    try:
        if args.benchmark:
            demo.run_benchmark()
        elif args.emotion:
            emotion = Emotion(args.emotion)
            demo.run_single_emotion(emotion, args.duration)
        elif args.continuous:
            demo.run_continuous()
        else:
            demo.run_demo_cycle()

    except KeyboardInterrupt:
        print("\n\nInterrupted by user.")

    finally:
        demo.cleanup()


if __name__ == "__main__":
    main()
