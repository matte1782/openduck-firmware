#!/usr/bin/env python3
"""
Full Emotion Demo Script - OpenDuck Mini V3
============================================
Week 02 Day 10 - Complete 17-Emotion Showcase

Demonstrates ALL 17 emotions with proper transitions:

PRIMARY EMOTIONS (8):
  1. IDLE     - Soft blue, breathing, approachable calm
  2. HAPPY    - Warm yellow, pulsing with sparkles
  3. CURIOUS  - Teal cyan, scanning rotation
  4. ALERT    - Red-orange, rapid pulsing with flashes
  5. SAD      - Muted blue, slow droop gradient
  6. SLEEPY   - Lavender, fighting-sleep blinks
  7. EXCITED  - Orange, spinning comet + rainbow
  8. THINKING - Blue-white, step-wise rotation

SOCIAL EMOTIONS (4):
  9. PLAYFUL     - Magenta-cyan, bouncy sparkles
 10. AFFECTIONATE - Pink, warm heartbeat rhythm
 11. EMPATHETIC  - Soft teal, synchronized breathing
 12. GRATEFUL    - Gold, appreciative surge

COMPOUND EMOTIONS (5):
 13. CONFUSED    - Yellow-cyan, uncertain wobble
 14. SURPRISED   - White flash, widening startle
 15. ANXIOUS     - Teal-red, jittery tension
 16. FRUSTRATED  - Orange-red, building pressure
 17. PROUD       - Gold-amber, standing tall

Hardware Configuration:
  Left Eye:  GPIO 18 (Pin 12), PWM Channel 0
  Right Eye: GPIO 13 (Pin 33), PWM Channel 1
  LEDs per ring: 16

Usage:
  sudo python3 emotion_demo_full.py              # Full 17-emotion cycle
  sudo python3 emotion_demo_full.py --primary    # Primary emotions only
  sudo python3 emotion_demo_full.py --social     # Social emotions only
  sudo python3 emotion_demo_full.py --compound   # Compound emotions only
  sudo python3 emotion_demo_full.py --benchmark  # Performance test all 17

Author: Integration Engineer (Agent 5)
Created: 18 January 2026
"""

import time
import math
import random
import argparse
import sys
from pathlib import Path
from dataclasses import dataclass
from enum import Enum
from typing import Tuple, List, Optional, Dict

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

# Raspberry Pi LED library
try:
    from rpi_ws281x import PixelStrip, Color
    PI_AVAILABLE = True
except ImportError:
    PI_AVAILABLE = False
    print("INFO: rpi_ws281x not available - running in simulation mode")

# Import from our emotion systems
try:
    from led.patterns.social_emotions import (
        PlayfulPattern, AffectionatePattern, EmpatheticPattern, GratefulPattern,
        SOCIAL_PATTERN_REGISTRY, SOCIAL_EMOTION_COLORS
    )
    from animation.emotion_patterns.compound_emotions import (
        ConfusedPattern, SurprisedPattern, AnxiousPattern, FrustratedPattern, ProudPattern,
        COMPOUND_EMOTION_CONFIGS
    )
    from animation.micro_expressions_enhanced import (
        EnhancedMicroExpressionEngine, EMOTION_MICRO_PARAMS
    )
    IMPORTS_AVAILABLE = True
except ImportError as e:
    print(f"WARNING: Could not import emotion patterns: {e}")
    IMPORTS_AVAILABLE = False


# =============================================================================
# CONFIGURATION
# =============================================================================

LEFT_EYE_PIN = 18
RIGHT_EYE_PIN = 13
NUM_LEDS = 16
MAX_BRIGHTNESS = 60
FRAME_RATE = 50
FRAME_TIME = 1.0 / FRAME_RATE
EMOTION_DISPLAY_TIME = 4.0  # Shorter for 17 emotions


# =============================================================================
# EMOTION DEFINITIONS - ALL 17
# =============================================================================

class EmotionCategory(Enum):
    PRIMARY = "primary"
    SOCIAL = "social"
    COMPOUND = "compound"


@dataclass
class EmotionSpec:
    """Specification for an emotion."""
    name: str
    category: EmotionCategory
    primary_color: Tuple[int, int, int]
    description: str
    cycle_duration: float = 2.0
    brightness_min: float = 0.3
    brightness_max: float = 1.0


# Complete emotion registry - all 17 emotions
EMOTION_REGISTRY: Dict[str, EmotionSpec] = {
    # Primary Emotions (8)
    "idle": EmotionSpec("idle", EmotionCategory.PRIMARY, (100, 160, 255),
                        "Calm, alive, micro-movements", 5.0, 0.30, 0.70),
    "happy": EmotionSpec("happy", EmotionCategory.PRIMARY, (255, 210, 80),
                         "Joyful, warm, anticipation sparkles", 1.2, 0.60, 1.00),
    "curious": EmotionSpec("curious", EmotionCategory.PRIMARY, (30, 240, 200),
                           "Attentive, searching, variable focus", 2.5, 0.50, 0.90),
    "alert": EmotionSpec("alert", EmotionCategory.PRIMARY, (255, 70, 40),
                         "Sharp, urgent, ramp-up warning", 0.35, 0.70, 1.00),
    "sad": EmotionSpec("sad", EmotionCategory.PRIMARY, (70, 90, 160),
                       "Withdrawn, drooping, occasional sighs", 8.0, 0.15, 0.40),
    "sleepy": EmotionSpec("sleepy", EmotionCategory.PRIMARY, (140, 110, 190),
                          "Drowsy, fighting sleep, irregular blinks", 10.0, 0.05, 0.35),
    "excited": EmotionSpec("excited", EmotionCategory.PRIMARY, (255, 140, 40),
                           "Energetic, rainbow bursts, barely contained", 0.6, 0.80, 1.00),
    "thinking": EmotionSpec("thinking", EmotionCategory.PRIMARY, (170, 190, 255),
                            "Processing, step-wise, visible computation", 1.8, 0.40, 0.75),

    # Social Emotions (4)
    "playful": EmotionSpec("playful", EmotionCategory.SOCIAL, (255, 100, 200),
                           "Bouncy, mischievous, sparkly chaos", 0.8, 0.50, 1.00),
    "affectionate": EmotionSpec("affectionate", EmotionCategory.SOCIAL, (255, 150, 180),
                                "Warm heartbeat, pink glow of love", 0.83, 0.40, 1.00),
    "empathetic": EmotionSpec("empathetic", EmotionCategory.SOCIAL, (100, 180, 170),
                              "Synchronized breathing, calming presence", 5.0, 0.30, 0.70),
    "grateful": EmotionSpec("grateful", EmotionCategory.SOCIAL, (255, 200, 80),
                            "Golden appreciation surge, thankful glow", 3.0, 0.40, 1.00),

    # Compound Emotions (5)
    "confused": EmotionSpec("confused", EmotionCategory.COMPOUND, (255, 220, 130),
                            "Uncertain wobble, mixed signals", 1.5, 0.35, 0.75),
    "surprised": EmotionSpec("surprised", EmotionCategory.COMPOUND, (255, 255, 200),
                             "White flash startle, wide eyes", 0.5, 0.60, 1.00),
    "anxious": EmotionSpec("anxious", EmotionCategory.COMPOUND, (100, 180, 180),
                           "Jittery tension, elevated pulse", 0.8, 0.50, 0.90),
    "frustrated": EmotionSpec("frustrated", EmotionCategory.COMPOUND, (255, 130, 80),
                              "Building pressure, warming anger", 1.2, 0.50, 0.95),
    "proud": EmotionSpec("proud", EmotionCategory.COMPOUND, (255, 180, 50),
                         "Standing tall, golden achievement", 2.5, 0.50, 1.00),
}


# =============================================================================
# LED CONTROLLER
# =============================================================================

class LEDController:
    """Dual LED ring controller for OpenDuck eyes."""

    def __init__(self):
        self.left_eye = None
        self.right_eye = None
        self.num_leds = NUM_LEDS
        self.initialized = False
        self.left_buffer = [(0, 0, 0)] * NUM_LEDS
        self.right_buffer = [(0, 0, 0)] * NUM_LEDS

    def initialize(self) -> bool:
        if not PI_AVAILABLE:
            print("  [SIM] Simulating LED initialization")
            self.initialized = True
            return True

        try:
            self.left_eye = PixelStrip(NUM_LEDS, LEFT_EYE_PIN, 800000, 10, False, MAX_BRIGHTNESS, 0)
            self.left_eye.begin()
            self.right_eye = PixelStrip(NUM_LEDS, RIGHT_EYE_PIN, 800000, 10, False, MAX_BRIGHTNESS, 1)
            self.right_eye.begin()
            self.initialized = True
            return True
        except Exception as e:
            print(f"  [ERROR] LED initialization failed: {e}")
            return False

    def set_pixel(self, eye: str, index: int, r: int, g: int, b: int):
        r, g, b = max(0, min(255, int(r))), max(0, min(255, int(g))), max(0, min(255, int(b)))
        if eye == 'left':
            self.left_buffer[index] = (r, g, b)
            if self.left_eye:
                self.left_eye.setPixelColor(index, Color(r, g, b))
        else:
            self.right_buffer[index] = (r, g, b)
            if self.right_eye:
                self.right_eye.setPixelColor(index, Color(r, g, b))

    def set_pixels_from_list(self, eye: str, pixels: List[Tuple[int, int, int]]):
        for i, (r, g, b) in enumerate(pixels):
            self.set_pixel(eye, i, r, g, b)

    def show(self):
        if self.left_eye:
            self.left_eye.show()
        if self.right_eye:
            self.right_eye.show()

    def clear(self):
        for i in range(self.num_leds):
            self.set_pixel('left', i, 0, 0, 0)
            self.set_pixel('right', i, 0, 0, 0)
        self.show()


# =============================================================================
# UNIFIED EMOTION RENDERER
# =============================================================================

class UnifiedEmotionRenderer:
    """
    Renders all 17 emotions with consistent interface.
    Uses specialized patterns for social and compound emotions.
    """

    def __init__(self, num_leds: int = 16):
        self.num_leds = num_leds

        # Initialize pattern renderers
        self.social_patterns = {}
        self.compound_patterns = {}

        if IMPORTS_AVAILABLE:
            self.social_patterns = {
                "playful": PlayfulPattern(num_leds),
                "affectionate": AffectionatePattern(num_leds),
                "empathetic": EmpatheticPattern(num_leds),
                "grateful": GratefulPattern(num_leds),
            }
            self.compound_patterns = {
                "confused": ConfusedPattern(num_leds),
                "surprised": SurprisedPattern(num_leds),
                "anxious": AnxiousPattern(num_leds),
                "frustrated": FrustratedPattern(num_leds),
                "proud": ProudPattern(num_leds),
            }
            self.micro_engine = EnhancedMicroExpressionEngine(num_leds)
        else:
            self.micro_engine = None

        # State for primary emotion patterns
        self.sparkles = []
        self.frame = 0

    def reset_state(self):
        """Reset all pattern states."""
        self.sparkles = []
        self.frame = 0
        for p in self.social_patterns.values():
            if hasattr(p, 'reset'):
                p.reset()
        for p in self.compound_patterns.values():
            if hasattr(p, 'reset'):
                p.reset()
        if self.micro_engine:
            self.micro_engine.reset()

    def render(self, emotion_name: str, t: float) -> Tuple[List, List]:
        """Render emotion at time t, returning (left_pixels, right_pixels)."""
        spec = EMOTION_REGISTRY.get(emotion_name)
        if not spec:
            return self._render_fallback(t)

        # Route to appropriate renderer
        if spec.category == EmotionCategory.SOCIAL and emotion_name in self.social_patterns:
            return self._render_social(emotion_name, t, spec)
        elif spec.category == EmotionCategory.COMPOUND and emotion_name in self.compound_patterns:
            return self._render_compound(emotion_name, t)
        else:
            return self._render_primary(emotion_name, t, spec)

    def _render_social(self, name: str, t: float, spec: EmotionSpec) -> Tuple[List, List]:
        """Render social emotion using specialized pattern."""
        pattern = self.social_patterns[name]
        # NOTE: Intentional access to protected _frame attribute.
        # PatternBase._frame is the internal frame counter used by _compute_frame().
        # No public setter exists; this is the standard pattern for driving animations.
        pattern._frame = int(t * FRAME_RATE)

        # Get color from spec
        color = spec.primary_color
        pixels = pattern._compute_frame(color)

        # Apply micro-expressions if available
        if self.micro_engine:
            self.micro_engine.set_emotion(name)
            self.micro_engine.update(FRAME_TIME * 1000)
            pixels = self.micro_engine.apply_to_pixels(pixels)

        return pixels, pixels  # Same for both eyes

    def _render_compound(self, name: str, t: float) -> Tuple[List, List]:
        """Render compound emotion using specialized pattern."""
        pattern = self.compound_patterns[name]
        left, right = pattern.render(t)

        # Apply micro-expressions if available
        if self.micro_engine:
            self.micro_engine.set_emotion(name)
            self.micro_engine.update(FRAME_TIME * 1000)
            left = self.micro_engine.apply_to_pixels(left)
            right = self.micro_engine.apply_to_pixels(right)

        return left, right

    def _render_primary(self, name: str, t: float, spec: EmotionSpec) -> Tuple[List, List]:
        """Render primary emotion with basic patterns."""
        r_base, g_base, b_base = spec.primary_color

        # Calculate breathing/pulse based on cycle
        cycle_phase = (t % spec.cycle_duration) / spec.cycle_duration
        breath = 0.5 + 0.5 * math.sin(2 * math.pi * cycle_phase - math.pi / 2)
        brightness = spec.brightness_min + (spec.brightness_max - spec.brightness_min) * breath

        # Add emotion-specific effects
        if name == "curious":
            # Rotating focus
            focus_pos = cycle_phase * self.num_leds
            pixels = []
            for i in range(self.num_leds):
                distance = min(abs(i - focus_pos), self.num_leds - abs(i - focus_pos))
                focus_intensity = math.exp(-(distance ** 2) / 4.5)
                local_brightness = brightness * (0.5 + 0.5 * focus_intensity)
                pixels.append((
                    int(r_base * local_brightness),
                    int(g_base * local_brightness),
                    int(b_base * local_brightness)
                ))
            return pixels, pixels

        elif name == "excited":
            # Spinning comet
            comet_pos = cycle_phase * self.num_leds
            pixels = []
            for i in range(self.num_leds):
                distance = min(abs(i - comet_pos), self.num_leds - abs(i - comet_pos))
                if distance < 4:
                    intensity = 1 - (distance / 4)
                else:
                    intensity = 0.2
                local_brightness = brightness * intensity
                pixels.append((
                    int(r_base * local_brightness),
                    int(g_base * local_brightness),
                    int(b_base * local_brightness)
                ))
            return pixels, pixels

        elif name == "alert":
            # Fast pulse with flash
            pulse = (1 - cycle_phase) if cycle_phase > 0.15 else cycle_phase / 0.15
            flash_active = (t % 2.0) < 0.1
            if flash_active:
                brightness = 1.0
            else:
                brightness = spec.brightness_min + (spec.brightness_max - spec.brightness_min) * pulse

            pixels = [(int(r_base * brightness), int(g_base * brightness), int(b_base * brightness))] * self.num_leds
            return pixels, pixels

        else:
            # Default breathing
            pixels = [(int(r_base * brightness), int(g_base * brightness), int(b_base * brightness))] * self.num_leds
            return pixels, pixels

    def _render_fallback(self, t: float) -> Tuple[List, List]:
        """Fallback dim blue pattern."""
        pixels = [(50, 50, 100)] * self.num_leds
        return pixels, pixels


# =============================================================================
# FULL EMOTION DEMO
# =============================================================================

class FullEmotionDemo:
    """Demonstration of all 17 emotions."""

    def __init__(self):
        self.led = LEDController()
        self.renderer = UnifiedEmotionRenderer(NUM_LEDS)
        self.frame_times = []
        self.running = False

    def initialize(self) -> bool:
        print("=" * 70)
        print("   OpenDuck Mini V3 - Full 17-Emotion Demo")
        print("=" * 70)
        print(f"  Left Eye:  GPIO {LEFT_EYE_PIN}")
        print(f"  Right Eye: GPIO {RIGHT_EYE_PIN}")
        print(f"  LEDs: {NUM_LEDS} | FPS: {FRAME_RATE}")
        print("=" * 70)
        return self.led.initialize()

    def display_emotion(self, emotion_name: str, duration: float):
        """Display emotion for specified duration."""
        spec = EMOTION_REGISTRY.get(emotion_name)
        if not spec:
            print(f"  Unknown emotion: {emotion_name}")
            return

        category_label = f"[{spec.category.value.upper()}]"
        print(f"\n  {category_label} {emotion_name.upper()}: {spec.description}")

        start_time = time.monotonic()
        local_frame_times = []

        while (time.monotonic() - start_time) < duration:
            t_frame_start = time.monotonic()
            elapsed = t_frame_start - start_time

            left_pixels, right_pixels = self.renderer.render(emotion_name, elapsed)
            self.led.set_pixels_from_list('left', left_pixels)
            self.led.set_pixels_from_list('right', right_pixels)
            self.led.show()

            t_frame_end = time.monotonic()
            frame_time_ms = (t_frame_end - t_frame_start) * 1000
            local_frame_times.append(frame_time_ms)
            self.frame_times.append(frame_time_ms)

            sleep_time = FRAME_TIME - (t_frame_end - t_frame_start)
            if sleep_time > 0:
                time.sleep(sleep_time)

        if local_frame_times:
            avg = sum(local_frame_times) / len(local_frame_times)
            print(f"    Performance: avg={avg:.3f}ms")

    def run_primary_demo(self):
        """Demo primary emotions only."""
        print("\n--- PRIMARY EMOTIONS (8) ---")
        primary = ["idle", "happy", "curious", "alert", "sad", "sleepy", "excited", "thinking"]
        for emotion in primary:
            self.renderer.reset_state()
            self.display_emotion(emotion, EMOTION_DISPLAY_TIME)

    def run_social_demo(self):
        """Demo social emotions only."""
        print("\n--- SOCIAL EMOTIONS (4) ---")
        social = ["playful", "affectionate", "empathetic", "grateful"]
        for emotion in social:
            self.renderer.reset_state()
            self.display_emotion(emotion, EMOTION_DISPLAY_TIME)

    def run_compound_demo(self):
        """Demo compound emotions only."""
        print("\n--- COMPOUND EMOTIONS (5) ---")
        compound = ["confused", "surprised", "anxious", "frustrated", "proud"]
        for emotion in compound:
            self.renderer.reset_state()
            self.display_emotion(emotion, EMOTION_DISPLAY_TIME)

    def run_full_demo(self):
        """Run complete 17-emotion showcase."""
        print("\n" + "=" * 70)
        print("           FULL 17-EMOTION SHOWCASE")
        print("=" * 70)

        # Natural story progression through all emotions
        demo_sequence = [
            # Wake up sequence
            "idle",        # Start calm
            "curious",     # Something caught attention
            "thinking",    # Processing...

            # Positive discovery
            "happy",       # Figured it out!
            "excited",     # Great news!
            "playful",     # Let's have fun!

            # Social bonding
            "affectionate", # I care about you
            "grateful",     # Thank you

            # Challenge emerges
            "alert",       # Wait, what's that?
            "confused",    # I don't understand
            "anxious",     # Feeling worried
            "frustrated",  # Can't solve it

            # Breakthrough
            "surprised",   # Eureka moment!
            "proud",       # I did it!

            # Wind down
            "empathetic",  # Understanding
            "sad",         # Reflecting
            "sleepy",      # Time to rest

            # Back to start
            "idle",        # Rest
        ]

        self.running = True
        self.renderer.reset_state()

        try:
            total = len(demo_sequence)
            for i, emotion in enumerate(demo_sequence):
                if not self.running:
                    break
                print(f"\n[{i+1}/{total}]", end="")
                self.display_emotion(emotion, EMOTION_DISPLAY_TIME)

            print("\n" + "=" * 70)
            print("           DEMO COMPLETE")
            print("=" * 70)

            if self.frame_times:
                avg = sum(self.frame_times) / len(self.frame_times)
                max_time = max(self.frame_times)
                print(f"\n  Performance Summary:")
                print(f"    Total frames: {len(self.frame_times)}")
                print(f"    Avg frame time: {avg:.3f}ms")
                print(f"    Max frame time: {max_time:.3f}ms")
                print(f"    Target: {FRAME_TIME*1000:.1f}ms ({FRAME_RATE} FPS)")

        except KeyboardInterrupt:
            print("\n\nDemo interrupted.")
            self.running = False

    def run_benchmark(self):
        """Benchmark all 17 emotions."""
        print("\n" + "=" * 70)
        print("           17-EMOTION PERFORMANCE BENCHMARK")
        print("=" * 70)

        results = {}

        for name, spec in EMOTION_REGISTRY.items():
            self.renderer.reset_state()
            frame_times = []

            for i in range(100):  # 2 seconds at 50fps
                t_start = time.monotonic()
                self.renderer.render(name, i * FRAME_TIME)
                t_end = time.monotonic()
                frame_times.append((t_end - t_start) * 1000)

            avg = sum(frame_times) / len(frame_times)
            max_time = max(frame_times)
            results[name] = (avg, max_time, spec.category.value)

        print(f"\n  {'Emotion':<15} {'Category':<10} {'Avg (ms)':<12} {'Max (ms)':<12} {'Status'}")
        print("  " + "-" * 60)

        for name, (avg, max_t, cat) in sorted(results.items(), key=lambda x: x[1][2]):
            status = "PASS" if avg < 2.5 and max_t < 10.0 else "WARN"
            print(f"  {name:<15} {cat:<10} {avg:<12.4f} {max_t:<12.4f} {status}")

        print("\n  Target: avg < 2.5ms, max < 10.0ms")
        pass_count = sum(1 for _, (avg, max_t, _) in results.items() if avg < 2.5 and max_t < 10.0)
        print(f"  Result: {pass_count}/17 emotions PASS")

    def cleanup(self):
        print("\n  Turning off LEDs...")
        self.led.clear()
        print("  Goodbye!")


# =============================================================================
# MAIN
# =============================================================================

def list_emotions():
    """Print all 17 emotions grouped by category."""
    print("\n" + "=" * 60)
    print("         ALL 17 EMOTIONS")
    print("=" * 60)

    for category in EmotionCategory:
        print(f"\n{category.value.upper()} EMOTIONS:")
        print("-" * 40)
        for name, spec in EMOTION_REGISTRY.items():
            if spec.category == category:
                print(f"  {name:<15} - {spec.description}")


def main():
    parser = argparse.ArgumentParser(
        description="OpenDuck Mini V3 - Full 17-Emotion Demo",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  sudo python3 emotion_demo_full.py              # Full 17-emotion demo
  sudo python3 emotion_demo_full.py --primary    # Primary emotions only
  sudo python3 emotion_demo_full.py --social     # Social emotions only
  sudo python3 emotion_demo_full.py --compound   # Compound emotions only
  sudo python3 emotion_demo_full.py --benchmark  # Performance benchmark
  sudo python3 emotion_demo_full.py --list       # List all emotions
        """
    )

    parser.add_argument('--primary', action='store_true', help='Primary emotions only')
    parser.add_argument('--social', action='store_true', help='Social emotions only')
    parser.add_argument('--compound', action='store_true', help='Compound emotions only')
    parser.add_argument('--benchmark', '-b', action='store_true', help='Performance benchmark')
    parser.add_argument('--list', '-l', action='store_true', help='List all emotions')

    args = parser.parse_args()

    if args.list:
        list_emotions()
        return

    demo = FullEmotionDemo()

    if not demo.initialize():
        print("Failed to initialize. Exiting.")
        sys.exit(1)

    try:
        if args.benchmark:
            demo.run_benchmark()
        elif args.primary:
            demo.run_primary_demo()
        elif args.social:
            demo.run_social_demo()
        elif args.compound:
            demo.run_compound_demo()
        else:
            demo.run_full_demo()
    except KeyboardInterrupt:
        print("\n\nInterrupted.")
    finally:
        demo.cleanup()


if __name__ == "__main__":
    main()
