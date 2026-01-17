#!/usr/bin/env python3
"""
OpenDuck Mini V3 - Professional Eye Animation Demo
===================================================
Boston Dynamics / Disney Animatronics Quality LED Eye System

Hardware Configuration:
  Ring 1 (Left Eye):  GPIO 18 (Pin 12), PWM Channel 0
  Ring 2 (Right Eye): GPIO 13 (Pin 33), PWM Channel 1

Wire Colors:
  RED    = VCC (5V Power)
  BROWN  = DIN (Data Signal)
  ORANGE = GND (Ground)

Run with: sudo python3 openduck_eyes_demo.py
"""

import time
import math
from rpi_ws281x import PixelStrip, Color

# =============================================================================
# CONFIGURATION
# =============================================================================

# Hardware Setup
LEFT_EYE_PIN = 18      # GPIO 18, Physical Pin 12
RIGHT_EYE_PIN = 13     # GPIO 13, Physical Pin 33
NUM_LEDS = 16
BRIGHTNESS = 60        # 0-255

# Animation Parameters
FRAME_RATE = 50        # Hz
FRAME_TIME = 1.0 / FRAME_RATE

# Color Palette (RGB)
COLORS = {
    'idle':      (100, 150, 255),   # Calm blue
    'happy':     (255, 220, 50),    # Warm yellow
    'curious':   (50, 255, 150),    # Teal green
    'alert':     (255, 100, 50),    # Orange
    'sleepy':    (150, 100, 200),   # Soft purple
    'excited':   (255, 50, 150),    # Pink
    'thinking':  (200, 200, 255),   # Light blue-white
    'off':       (0, 0, 0),
}

# =============================================================================
# INITIALIZATION
# =============================================================================

print("="*70)
print("     OpenDuck Mini V3 - Professional Eye Animation Demo")
print("="*70)
print(f"  Left Eye:  GPIO {LEFT_EYE_PIN} (Pin 12) - PWM Channel 0")
print(f"  Right Eye: GPIO {RIGHT_EYE_PIN} (Pin 33) - PWM Channel 1")
print(f"  LEDs per ring: {NUM_LEDS}")
print(f"  Frame rate: {FRAME_RATE} Hz")
print("="*70)

# Initialize LED strips
print("\nInitializing eyes...")
left_eye = PixelStrip(NUM_LEDS, LEFT_EYE_PIN, 800000, 10, False, BRIGHTNESS, 0)
left_eye.begin()
print("  Left eye  [OK]")

right_eye = PixelStrip(NUM_LEDS, RIGHT_EYE_PIN, 800000, 10, False, BRIGHTNESS, 1)
right_eye.begin()
print("  Right eye [OK]")

# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def set_all(strip, r, g, b):
    """Set all LEDs on a strip to one color"""
    for i in range(strip.numPixels()):
        strip.setPixelColor(i, Color(int(r), int(g), int(b)))
    strip.show()

def set_both(r, g, b):
    """Set both eyes to same color"""
    set_all(left_eye, r, g, b)
    set_all(right_eye, r, g, b)

def clear_both():
    """Turn off both eyes"""
    set_both(0, 0, 0)

def lerp(a, b, t):
    """Linear interpolation"""
    return a + (b - a) * t

def ease_in_out(t):
    """Smooth easing function"""
    if t < 0.5:
        return 2 * t * t
    return 1 - pow(-2 * t + 2, 2) / 2

# =============================================================================
# ANIMATION PATTERNS
# =============================================================================

def breathing(color, duration=4.0, cycles=2):
    """Slow breathing animation - Disney 'slow in, slow out' principle"""
    print(f"  Breathing animation ({cycles} cycles)...")
    r, g, b = color

    for _ in range(cycles):
        # Breathe in (dim to bright)
        steps = int(duration * FRAME_RATE / 2)
        for i in range(steps):
            t = ease_in_out(i / steps)
            brightness = 0.3 + 0.7 * t  # 30% to 100%
            set_both(r * brightness, g * brightness, b * brightness)
            time.sleep(FRAME_TIME)

        # Breathe out (bright to dim)
        for i in range(steps):
            t = ease_in_out(i / steps)
            brightness = 1.0 - 0.7 * t  # 100% to 30%
            set_both(r * brightness, g * brightness, b * brightness)
            time.sleep(FRAME_TIME)

def pulse(color, duration=2.0, pulses=4):
    """Quick pulse animation - like a heartbeat"""
    print(f"  Pulse animation ({pulses} pulses)...")
    r, g, b = color

    for _ in range(pulses):
        # Quick bright
        for i in range(5):
            t = i / 5
            set_both(r * t, g * t, b * t)
            time.sleep(0.02)

        # Slow fade
        for i in range(20):
            t = 1 - (i / 20)
            brightness = t * t  # Quadratic falloff
            set_both(r * brightness, g * brightness, b * brightness)
            time.sleep(0.03)

        time.sleep(0.2)

def spin(color, duration=3.0, reverse=False):
    """Rotating comet effect"""
    print(f"  Spin animation...")
    r, g, b = color
    frames = int(duration * FRAME_RATE)

    for frame in range(frames):
        pos = (frame * 2) % NUM_LEDS
        if reverse:
            pos = NUM_LEDS - 1 - pos

        # Clear
        for i in range(NUM_LEDS):
            left_eye.setPixelColor(i, Color(0, 0, 0))
            right_eye.setPixelColor(i, Color(0, 0, 0))

        # Draw comet with tail
        for tail in range(4):
            idx = (pos - tail) % NUM_LEDS
            idx_mirror = (NUM_LEDS - 1 - pos + tail) % NUM_LEDS
            brightness = 1.0 - (tail * 0.25)
            left_eye.setPixelColor(idx, Color(int(r*brightness), int(g*brightness), int(b*brightness)))
            right_eye.setPixelColor(idx_mirror, Color(int(r*brightness), int(g*brightness), int(b*brightness)))

        left_eye.show()
        right_eye.show()
        time.sleep(FRAME_TIME)

def rainbow_cycle(duration=5.0):
    """Full spectrum color cycle"""
    print(f"  Rainbow cycle...")
    frames = int(duration * FRAME_RATE)

    for frame in range(frames):
        for i in range(NUM_LEDS):
            # Calculate hue based on position and time
            hue = ((i * 256 // NUM_LEDS) + (frame * 5)) % 256
            r, g, b = hsv_to_rgb(hue / 255, 1.0, 1.0)
            left_eye.setPixelColor(i, Color(int(r*255), int(g*255), int(b*255)))
            right_eye.setPixelColor(NUM_LEDS - 1 - i, Color(int(r*255), int(g*255), int(b*255)))

        left_eye.show()
        right_eye.show()
        time.sleep(FRAME_TIME)

def hsv_to_rgb(h, s, v):
    """Convert HSV to RGB (0-1 range)"""
    if s == 0:
        return v, v, v

    i = int(h * 6)
    f = (h * 6) - i
    p = v * (1 - s)
    q = v * (1 - s * f)
    t = v * (1 - s * (1 - f))
    i = i % 6

    if i == 0: return v, t, p
    if i == 1: return q, v, p
    if i == 2: return p, v, t
    if i == 3: return p, q, v
    if i == 4: return t, p, v
    if i == 5: return v, p, q

def blink(color, blinks=3):
    """Quick blink animation"""
    print(f"  Blink animation ({blinks} blinks)...")
    r, g, b = color

    for _ in range(blinks):
        set_both(r, g, b)
        time.sleep(0.1)
        set_both(0, 0, 0)
        time.sleep(0.1)

    set_both(r, g, b)
    time.sleep(0.3)

def wink():
    """Wink - one eye dims briefly"""
    print(f"  Wink animation...")
    r, g, b = COLORS['happy']

    set_both(r, g, b)
    time.sleep(0.3)

    # Left eye dims (wink)
    for i in range(10):
        t = i / 10
        set_all(left_eye, r * (1-t), g * (1-t), b * (1-t))
        time.sleep(0.02)

    time.sleep(0.15)

    # Left eye returns
    for i in range(10):
        t = i / 10
        set_all(left_eye, r * t, g * t, b * t)
        time.sleep(0.02)

    time.sleep(0.3)

def emotion_transition(from_color, to_color, duration=1.0):
    """Smooth transition between emotions"""
    frames = int(duration * FRAME_RATE)
    r1, g1, b1 = from_color
    r2, g2, b2 = to_color

    for frame in range(frames):
        t = ease_in_out(frame / frames)
        r = lerp(r1, r2, t)
        g = lerp(g1, g2, t)
        b = lerp(b1, b2, t)
        set_both(r, g, b)
        time.sleep(FRAME_TIME)

# =============================================================================
# MAIN DEMO SEQUENCE
# =============================================================================

def run_demo():
    """Run the full demonstration sequence"""
    print("\n" + "="*70)
    print("                    STARTING DEMO SEQUENCE")
    print("="*70)

    try:
        # 1. Wake up
        print("\n[1/8] Wake Up Sequence")
        emotion_transition(COLORS['off'], COLORS['sleepy'], 1.5)
        breathing(COLORS['sleepy'], duration=3, cycles=1)
        emotion_transition(COLORS['sleepy'], COLORS['idle'], 1.0)

        # 2. Idle breathing
        print("\n[2/8] Idle State - Breathing")
        breathing(COLORS['idle'], duration=4, cycles=2)

        # 3. Alert!
        print("\n[3/8] Alert Response")
        emotion_transition(COLORS['idle'], COLORS['alert'], 0.3)
        pulse(COLORS['alert'], pulses=3)
        emotion_transition(COLORS['alert'], COLORS['idle'], 0.8)

        # 4. Curious
        print("\n[4/8] Curious - Looking Around")
        emotion_transition(COLORS['idle'], COLORS['curious'], 0.5)
        spin(COLORS['curious'], duration=3)

        # 5. Happy
        print("\n[5/8] Happy Response")
        emotion_transition(COLORS['curious'], COLORS['happy'], 0.5)
        blink(COLORS['happy'], blinks=3)
        wink()

        # 6. Excited
        print("\n[6/8] Excited - Rainbow!")
        rainbow_cycle(duration=5)

        # 7. Thinking
        print("\n[7/8] Thinking...")
        emotion_transition(COLORS['excited'], COLORS['thinking'], 0.8)
        pulse(COLORS['thinking'], pulses=5)

        # 8. Return to idle
        print("\n[8/8] Return to Idle")
        emotion_transition(COLORS['thinking'], COLORS['idle'], 1.0)
        breathing(COLORS['idle'], duration=4, cycles=2)

        print("\n" + "="*70)
        print("               DEMO COMPLETE - Press Ctrl+C to exit")
        print("="*70)

        # Continuous idle
        while True:
            breathing(COLORS['idle'], duration=4, cycles=1)

    except KeyboardInterrupt:
        print("\n\nShutting down...")

# =============================================================================
# ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    try:
        run_demo()
    finally:
        print("Turning off eyes...")
        clear_both()
        print("Goodbye!")
