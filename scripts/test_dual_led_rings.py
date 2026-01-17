#!/usr/bin/env python3
"""
Dual LED Ring Test Script
Tests both WS2812B 16-LED rings simultaneously.

Wiring:
  Ring 1: GPIO 18 (Pin 12) - Already validated Day 7
  Ring 2: GPIO 12 (Pin 32) - New ring

Run with: sudo python3 test_dual_led_rings.py
"""

import time
import board
import neopixel

# Configuration
RING1_PIN = board.D18  # GPIO 18, Physical Pin 12
RING2_PIN = board.D12  # GPIO 12, Physical Pin 32
NUM_LEDS = 16
BRIGHTNESS = 0.3  # 30% brightness for safety

def test_individual_rings():
    """Test each ring individually"""
    print("\n" + "="*50)
    print("TEST 1: Individual Ring Test")
    print("="*50)

    # Initialize rings
    print("\nInitializing Ring 1 (GPIO 18)...")
    ring1 = neopixel.NeoPixel(RING1_PIN, NUM_LEDS, brightness=BRIGHTNESS, auto_write=False)

    print("Initializing Ring 2 (GPIO 12)...")
    ring2 = neopixel.NeoPixel(RING2_PIN, NUM_LEDS, brightness=BRIGHTNESS, auto_write=False)

    # Test Ring 1 - RED
    print("\n[Ring 1] Setting to RED...")
    ring1.fill((255, 0, 0))
    ring1.show()
    input(">>> Press ENTER if Ring 1 shows RED (or 'n' if not): ")

    # Test Ring 2 - GREEN
    print("\n[Ring 2] Setting to GREEN...")
    ring2.fill((0, 255, 0))
    ring2.show()
    input(">>> Press ENTER if Ring 2 shows GREEN (or 'n' if not): ")

    # Clear both
    ring1.fill((0, 0, 0))
    ring2.fill((0, 0, 0))
    ring1.show()
    ring2.show()

    return ring1, ring2

def test_both_rings_together(ring1, ring2):
    """Test both rings at the same time"""
    print("\n" + "="*50)
    print("TEST 2: Both Rings Together")
    print("="*50)

    # Ring 1 = BLUE, Ring 2 = YELLOW
    print("\nRing 1 → BLUE | Ring 2 → YELLOW")
    ring1.fill((0, 0, 255))
    ring2.fill((255, 255, 0))
    ring1.show()
    ring2.show()
    input(">>> Press ENTER if both colors correct: ")

    # Swap colors
    print("\nSwapping: Ring 1 → YELLOW | Ring 2 → BLUE")
    ring1.fill((255, 255, 0))
    ring2.fill((0, 0, 255))
    ring1.show()
    ring2.show()
    input(">>> Press ENTER to continue: ")

    return True

def test_alternating_chase(ring1, ring2):
    """Chase pattern alternating between rings"""
    print("\n" + "="*50)
    print("TEST 3: Alternating Chase Pattern")
    print("="*50)
    print("Watch for a 'ping-pong' effect between the two rings...")
    print("Press Ctrl+C to stop\n")

    try:
        while True:
            for i in range(NUM_LEDS):
                # Clear both
                ring1.fill((0, 0, 0))
                ring2.fill((0, 0, 0))

                # Light one LED on each ring (opposite positions)
                ring1[i] = (255, 0, 100)  # Pink
                ring2[(NUM_LEDS - 1) - i] = (0, 255, 100)  # Cyan

                ring1.show()
                ring2.show()
                time.sleep(0.05)
    except KeyboardInterrupt:
        print("\nChase stopped.")

    ring1.fill((0, 0, 0))
    ring2.fill((0, 0, 0))
    ring1.show()
    ring2.show()

def test_breathing_sync(ring1, ring2):
    """Synchronized breathing effect"""
    print("\n" + "="*50)
    print("TEST 4: Synchronized Breathing")
    print("="*50)
    print("Both rings should breathe together...")
    print("Press Ctrl+C to stop\n")

    try:
        while True:
            # Breathe up
            for b in range(10, 100, 5):
                brightness = b / 100.0
                ring1.fill((int(100 * brightness), int(150 * brightness), int(255 * brightness)))
                ring2.fill((int(100 * brightness), int(150 * brightness), int(255 * brightness)))
                ring1.show()
                ring2.show()
                time.sleep(0.03)

            # Breathe down
            for b in range(100, 10, -5):
                brightness = b / 100.0
                ring1.fill((int(100 * brightness), int(150 * brightness), int(255 * brightness)))
                ring2.fill((int(100 * brightness), int(150 * brightness), int(255 * brightness)))
                ring1.show()
                ring2.show()
                time.sleep(0.03)
    except KeyboardInterrupt:
        print("\nBreathing stopped.")

    ring1.fill((0, 0, 0))
    ring2.fill((0, 0, 0))
    ring1.show()
    ring2.show()

def count_working_leds(ring1, ring2):
    """Count working LEDs on each ring"""
    print("\n" + "="*50)
    print("TEST 5: LED Count Verification")
    print("="*50)

    print("\nLighting LEDs one by one on Ring 1...")
    working_r1 = 0
    for i in range(NUM_LEDS):
        ring1.fill((0, 0, 0))
        ring1[i] = (255, 255, 255)
        ring1.show()
        time.sleep(0.1)
        working_r1 += 1

    print(f"Ring 1: {working_r1}/{NUM_LEDS} LEDs lit")

    print("\nLighting LEDs one by one on Ring 2...")
    working_r2 = 0
    ring1.fill((0, 0, 0))
    ring1.show()
    for i in range(NUM_LEDS):
        ring2.fill((0, 0, 0))
        ring2[i] = (255, 255, 255)
        ring2.show()
        time.sleep(0.1)
        working_r2 += 1

    print(f"Ring 2: {working_r2}/{NUM_LEDS} LEDs lit")

    ring2.fill((0, 0, 0))
    ring2.show()

    return working_r1, working_r2

def main():
    print("""
╔══════════════════════════════════════════════════════════╗
║         DUAL LED RING TEST - OpenDuck Mini V3            ║
║                                                          ║
║  Ring 1: GPIO 18 (Physical Pin 12)                       ║
║  Ring 2: GPIO 12 (Physical Pin 32)                       ║
║                                                          ║
║  Both rings share 5V power and GND                       ║
╚══════════════════════════════════════════════════════════╝
    """)

    try:
        # Test 1: Individual rings
        ring1, ring2 = test_individual_rings()

        # Test 2: Both together
        test_both_rings_together(ring1, ring2)

        # Test 3: Alternating chase
        test_alternating_chase(ring1, ring2)

        # Test 4: Breathing sync
        test_breathing_sync(ring1, ring2)

        # Test 5: Count LEDs
        r1_count, r2_count = count_working_leds(ring1, ring2)

        # Final report
        print("\n" + "="*50)
        print("FINAL REPORT")
        print("="*50)
        print(f"Ring 1 (GPIO 18): {r1_count}/16 LEDs working")
        print(f"Ring 2 (GPIO 12): {r2_count}/16 LEDs working")

        if r1_count == 16 and r2_count == 16:
            print("\n✅ BOTH RINGS FULLY FUNCTIONAL!")
        else:
            print("\n⚠️  Some LEDs may not be working. Check solder joints.")

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        print("\nTroubleshooting:")
        print("1. Run with sudo: sudo python3 test_dual_led_rings.py")
        print("2. Check wiring matches the pin numbers above")
        print("3. Verify 5V and GND connections")
        raise

    finally:
        print("\nTest complete. LEDs turned off.")

if __name__ == "__main__":
    main()
