#!/usr/bin/env python3
"""Dual LED Test v2 - Tests each ring separately first"""
import time
from rpi_ws281x import PixelStrip, Color

NUM_LEDS = 16
BRIGHTNESS = 50

print("="*60)
print("   DUAL LED TEST v2 - Diagnostic Mode")
print("="*60)

def fill(strip, r, g, b):
    for i in range(strip.numPixels()):
        strip.setPixelColor(i, Color(r, g, b))
    strip.show()

try:
    # Test Ring 1 FIRST, alone
    print("\n[STEP 1] Testing Ring 1 ALONE (GPIO 18, Pin 12)")
    print("Initializing...")
    ring1 = PixelStrip(NUM_LEDS, 18, 800000, 10, False, BRIGHTNESS, 0)
    ring1.begin()
    print("Setting to RED...")
    fill(ring1, 255, 0, 0)
    result1 = input("Is Ring 1 RED? (y/n): ")

    if result1.lower() != 'y':
        print("ERROR: Ring 1 not working! Check wiring on Pin 12")
        fill(ring1, 0, 0, 0)
        exit(1)

    # Turn off Ring 1 before testing Ring 2
    fill(ring1, 0, 0, 0)
    time.sleep(0.5)

    # Test Ring 2
    print("\n[STEP 2] Testing Ring 2 ALONE (GPIO 13, Pin 33)")
    print("Initializing...")
    ring2 = PixelStrip(NUM_LEDS, 13, 800000, 10, False, BRIGHTNESS, 1)
    ring2.begin()
    print("Setting to GREEN...")
    fill(ring2, 0, 255, 0)
    result2 = input("Is Ring 2 GREEN? (y/n): ")

    if result2.lower() != 'y':
        print("ERROR: Ring 2 not working! Check wiring on Pin 33")
        fill(ring2, 0, 0, 0)
        exit(1)

    # Both working - run combined test
    print("\n[STEP 3] Both rings together!")
    print("Ring 1 = BLUE, Ring 2 = YELLOW")
    fill(ring1, 0, 0, 255)
    fill(ring2, 255, 255, 0)
    time.sleep(2)

    print("\n[STEP 4] Chase animation - Ctrl+C to stop")
    while True:
        for i in range(NUM_LEDS):
            fill(ring1, 0, 0, 0)
            fill(ring2, 0, 0, 0)
            ring1.setPixelColor(i, Color(255, 0, 100))
            ring2.setPixelColor((NUM_LEDS-1)-i, Color(0, 255, 100))
            ring1.show()
            ring2.show()
            time.sleep(0.04)

except KeyboardInterrupt:
    print("\nStopping...")
finally:
    try:
        fill(ring1, 0, 0, 0)
        fill(ring2, 0, 0, 0)
    except:
        pass
    print("Done!")
