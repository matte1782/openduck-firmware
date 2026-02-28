#!/usr/bin/env python3
"""MG90S Servo Quick Test via PCA9685

Minimal test to validate MG90S servo on PCA9685 channel 0.

Wiring checklist:
  - PCA9685 SDA → Pi Pin 3 (GPIO 2)
  - PCA9685 SCL → Pi Pin 5 (GPIO 3)
  - PCA9685 VCC → Pi Pin 1 (3.3V) for logic
  - PCA9685 GND → Pi Pin 6 (GND)
  - PCA9685 V+ SCREW TERMINAL → Pi Pin 2 (5V) for servo power
  - MG90S on channel 0: Brown=GND, Red=V+, Yellow=Signal (outer to inner)

Usage:
    python3 test_mg90s.py
    python3 test_mg90s.py --channel 1    # test different channel
"""

import argparse
import time

from adafruit_servokit import ServoKit


def main():
    parser = argparse.ArgumentParser(description="MG90S servo test")
    parser.add_argument("--channel", type=int, default=0, help="PCA9685 channel (0-15)")
    args = parser.parse_args()

    ch = args.channel
    print(f"MG90S Test - PCA9685 channel {ch}")
    print("=" * 40)

    # Init PCA9685 with 16 channels at default 0x40
    kit = ServoKit(channels=16)

    # Set pulse range for MG90S (typical 500-2400µs)
    kit.servo[ch].set_pulse_width_range(500, 2400)

    # Test 1: Center
    print(f"\n[1] Moving to 90° (center)...")
    kit.servo[ch].angle = 90
    time.sleep(1)
    print("    Done. Servo should be at center position.")

    # Test 2: Sweep
    print(f"\n[2] Sweeping 0° → 180°...")
    for angle in range(0, 181, 10):
        kit.servo[ch].angle = angle
        print(f"    {angle}°", end="\r")
        time.sleep(0.15)
    print(f"    180° ✓")

    time.sleep(0.5)

    print(f"\n[3] Sweeping 180° → 0°...")
    for angle in range(180, -1, -10):
        kit.servo[ch].angle = angle
        print(f"    {angle}° ", end="\r")
        time.sleep(0.15)
    print(f"    0° ✓")

    # Test 3: Back to center and release
    print(f"\n[4] Returning to 90° and releasing...")
    kit.servo[ch].angle = 90
    time.sleep(0.5)
    kit.servo[ch].angle = None  # release PWM signal
    print("    Released.")

    print(f"\n{'=' * 40}")
    print("✓ MG90S test COMPLETE")
    print("If servo moved smoothly through full range, hardware is validated.")


if __name__ == "__main__":
    main()
