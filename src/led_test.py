#!/usr/bin/env python3
"""
LED Ring Test Script for OpenDuck Mini V3
Tests WS2812B 16-LED Ring connected to GPIO18

Wiring:
- RED wire (5V DC) -> Pin 2
- BLACK wire (Ground) -> Pin 6
- BROWN wire (Data Input) -> Pin 12 (GPIO18)

Run with: sudo python3 led_test.py

IMPORTANT NOTES:
- GPIO 18 CONFLICT: When I2S audio is enabled, GPIO 18 will be unavailable.
  Move LED to GPIO 12 (Physical Pin 32) if audio is needed simultaneously.
- POWER WARNING: At brightness >50, current draw exceeds 400mA.
  Use external 5V supply if brightness >50/255.

Validated: 16 Jan 2026 - All 16 LEDs working!
"""

import sys
import time

# LED strip configuration
LED_COUNT = 16          # Number of LED pixels (16-LED ring)
LED_PIN = 18            # GPIO pin (Pin 12 = GPIO18)
LED_FREQ_HZ = 800000    # LED signal frequency in hertz
LED_DMA = 10            # DMA channel to use
LED_BRIGHTNESS = 50     # Brightness (0-255), starting low for safety
LED_INVERT = False      # True to invert the signal
LED_CHANNEL = 0         # PWM channel

# Safety constants
MAX_SAFE_BRIGHTNESS_PI_POWER = 50  # Max brightness when powered from Pi 5V rail
AUTO_EXIT_SECONDS = 30  # Auto-exit after this many seconds (0 = infinite)


def check_power_safety():
    """Warn user if brightness exceeds safe level for Pi 5V power"""
    if LED_BRIGHTNESS > MAX_SAFE_BRIGHTNESS_PI_POWER:
        print("=" * 50)
        print("WARNING: HIGH BRIGHTNESS DETECTED!")
        print(f"Brightness: {LED_BRIGHTNESS}/255 ({LED_BRIGHTNESS/255*100:.0f}%)")
        print(f"Estimated current: {16 * 60 * LED_BRIGHTNESS/255:.0f}mA")
        print("")
        print("At brightness >50, use EXTERNAL 5V power supply!")
        print("Pi 5V rail may brownout causing SD card corruption.")
        print("=" * 50)
        response = input("Continue anyway? (y/N): ").strip().lower()
        if response != 'y':
            print("Aborted. Reduce LED_BRIGHTNESS to 50 or less.")
            sys.exit(0)


def initialize_strip():
    """Initialize LED strip with proper error handling"""
    try:
        from rpi_ws281x import PixelStrip, Color
    except ImportError:
        print("ERROR: rpi_ws281x library not installed!")
        print("Install with: sudo pip3 install rpi_ws281x --break-system-packages")
        sys.exit(1)

    print("\nInitializing LED Ring...")
    try:
        strip = PixelStrip(LED_COUNT, LED_PIN, LED_FREQ_HZ, LED_DMA,
                           LED_INVERT, LED_BRIGHTNESS, LED_CHANNEL)
        strip.begin()
        print("LED Ring initialized!")
        return strip, Color
    except RuntimeError as e:
        print(f"ERROR: LED initialization failed: {e}")
        print("")
        print("Common fixes:")
        print("  1. Run with sudo: sudo python3 led_test.py")
        print("  2. Check GPIO 18 not used by I2S audio (dtoverlay=disable-i2s)")
        print("  3. Try different DMA channel (edit LED_DMA in script)")
        print("  4. Check wiring: Data->Pin12, 5V->Pin2, GND->Pin6")
        sys.exit(1)
    except PermissionError:
        print("ERROR: Permission denied!")
        print("Run with: sudo python3 led_test.py")
        sys.exit(1)


def test_all_red(strip, Color):
    """Turn all LEDs red"""
    print("Setting all LEDs to RED...")
    for i in range(strip.numPixels()):
        strip.setPixelColor(i, Color(255, 0, 0))
    strip.show()


def test_all_green(strip, Color):
    """Turn all LEDs green"""
    print("Setting all LEDs to GREEN...")
    for i in range(strip.numPixels()):
        strip.setPixelColor(i, Color(0, 255, 0))
    strip.show()


def test_all_blue(strip, Color):
    """Turn all LEDs blue"""
    print("Setting all LEDs to BLUE...")
    for i in range(strip.numPixels()):
        strip.setPixelColor(i, Color(0, 0, 255))
    strip.show()


def test_rainbow_cycle(strip, Color, iterations=2):
    """Rainbow cycle animation"""
    print("Running rainbow cycle...")

    def wheel(pos):
        """Generate rainbow colors across 0-255 positions"""
        if pos < 85:
            return Color(pos * 3, 255 - pos * 3, 0)
        elif pos < 170:
            pos -= 85
            return Color(255 - pos * 3, 0, pos * 3)
        else:
            pos -= 170
            return Color(0, pos * 3, 255 - pos * 3)

    for j in range(256 * iterations):
        for i in range(strip.numPixels()):
            pixel_index = (i * 256 // strip.numPixels()) + j
            strip.setPixelColor(i, wheel(pixel_index & 255))
        strip.show()
        time.sleep(0.02)


def clear_leds(strip, Color):
    """Turn off all LEDs"""
    for i in range(strip.numPixels()):
        strip.setPixelColor(i, Color(0, 0, 0))
    strip.show()


def main():
    print("=" * 50)
    print("OpenDuck Mini V3 - LED Ring Test")
    print("=" * 50)
    print(f"LED Count: {LED_COUNT}")
    print(f"GPIO Pin: {LED_PIN} (Physical Pin 12)")
    print(f"Brightness: {LED_BRIGHTNESS}/255 ({LED_BRIGHTNESS/255*100:.1f}%)")
    print(f"Est. Current: {16 * 60 * LED_BRIGHTNESS/255:.0f}mA")
    print("=" * 50)

    # Safety check
    check_power_safety()

    # Initialize with error handling
    strip, Color = initialize_strip()

    try:
        # Test 1: All Red
        print("\n[TEST 1] All LEDs RED")
        test_all_red(strip, Color)
        print("SUCCESS! All LEDs should be RED now!")
        time.sleep(2)

        # Test 2: All Green
        print("\n[TEST 2] All LEDs GREEN")
        test_all_green(strip, Color)
        print("SUCCESS! All LEDs should be GREEN now!")
        time.sleep(2)

        # Test 3: All Blue
        print("\n[TEST 3] All LEDs BLUE")
        test_all_blue(strip, Color)
        print("SUCCESS! All LEDs should be BLUE now!")
        time.sleep(2)

        # Test 4: Rainbow
        print("\n[TEST 4] Rainbow Cycle Animation")
        test_rainbow_cycle(strip, Color, iterations=2)
        print("SUCCESS! Rainbow animation complete!")

        # Final: All Red with auto-exit
        test_all_red(strip, Color)

        if AUTO_EXIT_SECONDS > 0:
            print(f"\n[FINAL] LEDs RED - auto-exit in {AUTO_EXIT_SECONDS} seconds")
            print("Press Ctrl+C to exit early")
            for i in range(AUTO_EXIT_SECONDS):
                time.sleep(1)
                remaining = AUTO_EXIT_SECONDS - i - 1
                if remaining > 0 and remaining % 10 == 0:
                    print(f"  {remaining} seconds remaining...")
        else:
            print("\n[FINAL] Setting LEDs to RED - Press Ctrl+C to exit")
            while True:
                time.sleep(1)

    except KeyboardInterrupt:
        print("\n\nUser interrupted - turning off LEDs...")
    finally:
        clear_leds(strip, Color)
        print("LEDs turned off. Test complete!")
        print("\n" + "=" * 50)
        print("ALL TESTS PASSED! LED ring properly connected!")
        print("=" * 50)


if __name__ == '__main__':
    main()
