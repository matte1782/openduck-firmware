#!/usr/bin/env python3
"""
Day 9 Hardware Validation - LED Pattern Test
OpenDuck Mini V3

Tests fire, cloud, dream Perlin patterns on actual WS2812B LED rings.
Run this on Raspberry Pi via SSH.

Usage:
    python3 test_led_patterns_hardware.py

Requirements:
    - WS2812B LED rings connected to GPIO 18 (left) and GPIO 13 (right)
    - sudo (for hardware PWM access)
    - rpi_ws281x library installed

Hardware Configuration:
    Ring 1 (Left Eye):  GPIO 18 (Pin 12), PWM Channel 0
    Ring 2 (Right Eye): GPIO 13 (Pin 33), PWM Channel 1

Author: Boston Dynamics Hardware Validation Team
Created: 18 January 2026
"""

import sys
import time

# Check if running on Pi
try:
    from rpi_ws281x import PixelStrip, Color
    ON_PI = True
except ImportError:
    print("ERROR: rpi_ws281x not found. Run on Raspberry Pi.")
    print("Install: sudo pip3 install rpi_ws281x --break-system-packages")
    sys.exit(1)

# Check noise library
try:
    from noise import pnoise2
    NOISE_AVAILABLE = True
except ImportError:
    print("ERROR: noise library not found.")
    print("Install: sudo pip3 install noise --break-system-packages")
    sys.exit(1)

# Add firmware/src to path
sys.path.insert(0, '/home/pi/robot_jarvis/firmware/src')

# LED Configuration - Dual Ring Setup
LED_COUNT = 16
LED_FREQ_HZ = 800000
LED_DMA = 10
LED_BRIGHTNESS = 50   # 0-255 (start low for safety)
LED_INVERT = False

# Left Eye (Ring 1)
LEFT_EYE_PIN = 18     # GPIO 18 (PWM0)
LEFT_EYE_CHANNEL = 0

# Right Eye (Ring 2)
RIGHT_EYE_PIN = 13    # GPIO 13 (PWM1), Pin 33
RIGHT_EYE_CHANNEL = 1


def init_led_strips():
    """Initialize both WS2812B LED rings."""
    left_eye = PixelStrip(
        LED_COUNT, LEFT_EYE_PIN, LED_FREQ_HZ, LED_DMA,
        LED_INVERT, LED_BRIGHTNESS, LEFT_EYE_CHANNEL
    )
    left_eye.begin()

    right_eye = PixelStrip(
        LED_COUNT, RIGHT_EYE_PIN, LED_FREQ_HZ, LED_DMA,
        LED_INVERT, LED_BRIGHTNESS, RIGHT_EYE_CHANNEL
    )
    right_eye.begin()

    return left_eye, right_eye


def clear_strips(left_eye, right_eye):
    """Turn off all LEDs on both rings."""
    for i in range(LED_COUNT):
        left_eye.setPixelColor(i, Color(0, 0, 0))
        right_eye.setPixelColor(i, Color(0, 0, 0))
    left_eye.show()
    right_eye.show()


def test_pattern(left_eye, right_eye, pattern, name, duration=5, base_color=(255, 100, 50)):
    """Test a pattern for specified duration on both eyes."""
    print(f"\n{'='*60}")
    print(f"Testing: {name}")
    print(f"Duration: {duration} seconds")
    print(f"Base Color: RGB{base_color}")
    print(f"Eyes: BOTH (Left GPIO 18, Right GPIO 13)")
    print(f"{'='*60}")

    frame_count = 0
    start_time = time.time()
    frame_times = []

    try:
        while time.time() - start_time < duration:
            frame_start = time.perf_counter()

            # Render pattern
            pixels = pattern.render(base_color)

            # Apply to both LED rings
            for i, (r, g, b) in enumerate(pixels):
                color = Color(int(r), int(g), int(b))
                left_eye.setPixelColor(i, color)
                right_eye.setPixelColor(i, color)

            left_eye.show()
            right_eye.show()

            # Advance pattern
            pattern.advance()

            frame_end = time.perf_counter()
            frame_times.append((frame_end - frame_start) * 1000)
            frame_count += 1

            # Target 50Hz (20ms per frame)
            elapsed = frame_end - frame_start
            if elapsed < 0.02:
                time.sleep(0.02 - elapsed)

    except KeyboardInterrupt:
        print("\nInterrupted by user")

    # Statistics
    if frame_times:
        avg_ms = sum(frame_times) / len(frame_times)
        max_ms = max(frame_times)
        min_ms = min(frame_times)
        fps = frame_count / duration

        print(f"\nResults:")
        print(f"  Frames: {frame_count}")
        print(f"  FPS: {fps:.1f}")
        print(f"  Avg render: {avg_ms:.3f}ms")
        print(f"  Min render: {min_ms:.3f}ms")
        print(f"  Max render: {max_ms:.3f}ms")
        print(f"  Target: <2ms avg, <15ms max")

        if avg_ms < 2.0 and max_ms < 15.0:
            print(f"  ✅ PASS: Performance within budget")
        else:
            print(f"  ❌ FAIL: Performance exceeds budget")

    return frame_times


def main():
    print("="*60)
    print("OpenDuck Mini V3 - Day 9 Hardware Validation")
    print("LED Pattern Test Suite (DUAL EYE)")
    print("="*60)

    # Initialize both LED rings
    print("\nInitializing LED rings...")
    print(f"  Left Eye:  GPIO {LEFT_EYE_PIN} (Pin 12), PWM Channel {LEFT_EYE_CHANNEL}")
    print(f"  Right Eye: GPIO {RIGHT_EYE_PIN} (Pin 33), PWM Channel {RIGHT_EYE_CHANNEL}")
    left_eye, right_eye = init_led_strips()
    clear_strips(left_eye, right_eye)
    print("✅ Both LED rings initialized")

    # Import patterns
    print("\nLoading patterns...")
    try:
        from led.patterns.fire import FirePattern
        from led.patterns.cloud import CloudPattern
        from led.patterns.dream import DreamPattern
        print("✅ All patterns loaded")
    except ImportError as e:
        print(f"❌ Failed to import patterns: {e}")
        clear_strips(left_eye, right_eye)
        sys.exit(1)

    # Create pattern instances
    fire = FirePattern(LED_COUNT)
    cloud = CloudPattern(LED_COUNT)
    dream = DreamPattern(LED_COUNT)

    all_results = {}

    try:
        # Test each pattern
        print("\n" + "="*60)
        print("Starting pattern tests (5 seconds each)")
        print("Press Ctrl+C to skip to next pattern")
        print("="*60)

        # Fire pattern (warm orange)
        all_results['fire'] = test_pattern(
            left_eye, right_eye, fire, "FIRE PATTERN",
            duration=5, base_color=(255, 100, 30)
        )
        clear_strips(left_eye, right_eye)
        time.sleep(1)

        # Cloud pattern (cool blue-white)
        all_results['cloud'] = test_pattern(
            left_eye, right_eye, cloud, "CLOUD PATTERN",
            duration=5, base_color=(150, 180, 255)
        )
        clear_strips(left_eye, right_eye)
        time.sleep(1)

        # Dream pattern (purple/lavender)
        all_results['dream'] = test_pattern(
            left_eye, right_eye, dream, "DREAM PATTERN",
            duration=5, base_color=(180, 100, 255)
        )
        clear_strips(left_eye, right_eye)

        # Final summary
        print("\n" + "="*60)
        print("HARDWARE VALIDATION SUMMARY")
        print("="*60)

        all_pass = True
        for name, times in all_results.items():
            if times:
                avg = sum(times) / len(times)
                max_t = max(times)
                status = "✅ PASS" if avg < 2.0 and max_t < 15.0 else "❌ FAIL"
                print(f"  {name.upper()}: avg={avg:.3f}ms, max={max_t:.3f}ms {status}")
                if avg >= 2.0 or max_t >= 15.0:
                    all_pass = False

        print("\n" + "="*60)
        if all_pass:
            print("✅ ALL PATTERNS PASSED HARDWARE VALIDATION")
        else:
            print("❌ SOME PATTERNS FAILED - Review above")
        print("="*60)

    except Exception as e:
        print(f"\n❌ Error during test: {e}")
        import traceback
        traceback.print_exc()

    finally:
        # Always clean up
        print("\nCleaning up...")
        clear_strips(left_eye, right_eye)
        print("Both eyes turned off")


if __name__ == "__main__":
    main()
