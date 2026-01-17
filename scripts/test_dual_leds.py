#!/usr/bin/env python3
"""
Dual LED Ring Test - OpenDuck Mini V3
=====================================
Ring 1: GPIO 18 (Pin 12) - PWM Channel 0
Ring 2: GPIO 13 (Pin 33) - PWM Channel 1

WIRING:
┌─────────────┬─────────────────┬─────────────────┐
│    Wire     │     Ring 1      │     Ring 2      │
├─────────────┼─────────────────┼─────────────────┤
│ VCC (Red)   │ Pin 2 (5V)      │ Pin 4 (5V)      │
├─────────────┼─────────────────┼─────────────────┤
│ GND (Black) │ Pin 6 (GND)     │ Pin 34 (GND)    │
├─────────────┼─────────────────┼─────────────────┤
│ DIN (Data)  │ Pin 12 (GPIO18) │ Pin 33 (GPIO13) │
└─────────────┴─────────────────┴─────────────────┘

Run with: sudo python3 test_dual_leds.py
"""
import time
from rpi_ws281x import PixelStrip, Color

# Configuration
RING1_PIN = 18  # GPIO 18, Physical Pin 12, PWM Channel 0
RING2_PIN = 13  # GPIO 13, Physical Pin 33, PWM Channel 1
NUM_LEDS = 16
BRIGHTNESS = 50

print("="*60)
print("       DUAL LED RING TEST - OpenDuck Mini V3")
print("="*60)
print("Ring 1: GPIO 18 (Pin 12) - PWM Channel 0")
print("Ring 2: GPIO 13 (Pin 33) - PWM Channel 1")
print("="*60)

# Initialize Ring 1
print("\nInitializing Ring 1 (GPIO 18)...")
ring1 = PixelStrip(NUM_LEDS, RING1_PIN, 800000, 10, False, BRIGHTNESS, 0)
ring1.begin()
print("Ring 1 OK!")

# Initialize Ring 2
print("Initializing Ring 2 (GPIO 13)...")
ring2 = PixelStrip(NUM_LEDS, RING2_PIN, 800000, 10, False, BRIGHTNESS, 1)
ring2.begin()
print("Ring 2 OK!")

def fill(strip, r, g, b):
    """Fill entire strip with one color"""
    for i in range(strip.numPixels()):
        strip.setPixelColor(i, Color(r, g, b))
    strip.show()

def clear_all():
    """Turn off all LEDs on both rings"""
    fill(ring1, 0, 0, 0)
    fill(ring2, 0, 0, 0)

try:
    # Test 1: Ring 1 RED
    print("\n[TEST 1] Ring 1 = RED")
    fill(ring1, 255, 0, 0)
    time.sleep(1.5)

    # Test 2: Ring 2 GREEN
    print("[TEST 2] Ring 2 = GREEN")
    fill(ring2, 0, 255, 0)
    time.sleep(1.5)

    # Test 3: Both BLUE
    print("[TEST 3] Both = BLUE")
    fill(ring1, 0, 0, 255)
    fill(ring2, 0, 0, 255)
    time.sleep(1.5)

    # Test 4: Different colors
    print("[TEST 4] Ring 1 = YELLOW, Ring 2 = PURPLE")
    fill(ring1, 255, 255, 0)
    fill(ring2, 128, 0, 255)
    time.sleep(1.5)

    # Test 5: Chase animation
    print("[TEST 5] Alternating Chase - Press Ctrl+C to stop")
    print("         (Pink dot on Ring 1, Cyan dot on Ring 2)")
    while True:
        for i in range(NUM_LEDS):
            clear_all()
            ring1.setPixelColor(i, Color(255, 0, 100))  # Pink
            ring2.setPixelColor((NUM_LEDS-1)-i, Color(0, 255, 100))  # Cyan
            ring1.show()
            ring2.show()
            time.sleep(0.04)

except KeyboardInterrupt:
    print("\n\nStopping...")

finally:
    clear_all()
    print("LEDs off. Test complete!")
    print("\n" + "="*60)
    print("If both rings worked, your wiring is correct!")
    print("="*60)
