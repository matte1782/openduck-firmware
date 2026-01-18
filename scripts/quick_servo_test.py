#!/usr/bin/env python3
"""
Quick Servo Test - Direct Pi Power (30 seconds max!)
OpenDuck Mini V3

WARNING: Only test ONE servo, no load, brief test!
Pi 5V pin can only supply ~300mA safely.

Author: OpenDuck Team
Created: 18 January 2026
"""

import RPi.GPIO as GPIO
import time

# Configuration
SERVO_PIN = 18  # GPIO 18 (Pin 12)

print("=" * 50)
print("  QUICK SERVO TEST - Pi Direct Power")
print("=" * 50)
print("\nWARNING: Keep test under 30 seconds!")
print("         One servo only, no load!\n")

try:
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(SERVO_PIN, GPIO.OUT)

    pwm = GPIO.PWM(SERVO_PIN, 50)  # 50Hz for servos
    pwm.start(0)

    # Test sequence
    print("[1/4] Moving to CENTER (90 degrees)...")
    pwm.ChangeDutyCycle(7.5)  # ~90 degrees
    time.sleep(2)

    print("[2/4] Moving to MIN (0 degrees)...")
    pwm.ChangeDutyCycle(2.5)  # ~0 degrees
    time.sleep(2)

    print("[3/4] Moving to MAX (180 degrees)...")
    pwm.ChangeDutyCycle(12.5)  # ~180 degrees
    time.sleep(2)

    print("[4/4] Back to CENTER...")
    pwm.ChangeDutyCycle(7.5)
    time.sleep(1)

    pwm.ChangeDutyCycle(0)  # Stop signal
    pwm.stop()

    print("\n" + "=" * 50)
    print("  TEST COMPLETE - Servo is working!")
    print("=" * 50)
    print("\nDisconnect servo now to save Pi power.")

except KeyboardInterrupt:
    print("\nTest interrupted!")

finally:
    GPIO.cleanup()
    print("GPIO cleaned up. Done!")
