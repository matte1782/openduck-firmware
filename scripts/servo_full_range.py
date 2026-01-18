#!/usr/bin/env python3
"""
Servo Full Range Test - 0 to 180 degrees
OpenDuck Mini V3

Tests the complete range with your calibrated values.
"""

import RPi.GPIO as GPIO
import time

SERVO_PIN = 18

# Your calibrated values
MIN_DUTY = 2.5    # 0 degrees
CENTER_DUTY = 7.5 # 90 degrees
MAX_DUTY = 12.5   # 180 degrees

print("=" * 50)
print("  FULL RANGE TEST: 0° → 90° → 180° → 90° → 0°")
print("=" * 50)

GPIO.setmode(GPIO.BCM)
GPIO.setup(SERVO_PIN, GPIO.OUT)
pwm = GPIO.PWM(SERVO_PIN, 50)
pwm.start(0)

try:
    # Step 1: Go to 0 degrees
    print("\n[1/5] Moving to 0° (MIN)...")
    pwm.ChangeDutyCycle(MIN_DUTY)
    time.sleep(2)

    # Step 2: Go to 90 degrees
    print("[2/5] Moving to 90° (CENTER)...")
    pwm.ChangeDutyCycle(CENTER_DUTY)
    time.sleep(2)

    # Step 3: Go to 180 degrees SLOWLY
    print("[3/5] Moving to 180° (MAX) - SLOWLY...")
    for dc in range(75, 126, 5):  # 7.5 to 12.5 in steps
        pwm.ChangeDutyCycle(dc / 10.0)
        print(f"       {dc/10.0}% = ~{int((dc/10.0 - 2.5) * 18)}°")
        time.sleep(0.5)

    print("\n       >>> NOW AT 180 DEGREES <<<")
    time.sleep(3)

    # Step 4: Back to center
    print("\n[4/5] Moving to 90° (CENTER)...")
    pwm.ChangeDutyCycle(CENTER_DUTY)
    time.sleep(2)

    # Step 5: Back to 0
    print("[5/5] Moving to 0° (MIN)...")
    pwm.ChangeDutyCycle(MIN_DUTY)
    time.sleep(2)

    print("\n" + "=" * 50)
    print("  TEST COMPLETE!")
    print("  Did servo reach all positions? (0°, 90°, 180°)")
    print("=" * 50)

except KeyboardInterrupt:
    print("\nInterrupted!")

finally:
    pwm.ChangeDutyCycle(0)
    pwm.stop()
    GPIO.cleanup()
    print("Done!")
