#!/usr/bin/env python3
"""
Servo Calibration - Find actual PWM range
OpenDuck Mini V3

Interactively find min/max duty cycle for your servo.
MG90S typically works in 2.5-10% range (not full 2.5-12.5%)

Author: OpenDuck Team
Created: 18 January 2026
"""

import RPi.GPIO as GPIO
import time

SERVO_PIN = 18

print("=" * 50)
print("  SERVO CALIBRATION TOOL")
print("=" * 50)
print("\nCommands:")
print("  + / -    : Adjust by 0.5%")
print("  ++ / --  : Adjust by 0.1%")
print("  c        : Go to center (7.5%)")
print("  min      : Go to current min")
print("  max      : Go to current max")
print("  save     : Print final values")
print("  q        : Quit")
print("=" * 50)

GPIO.setmode(GPIO.BCM)
GPIO.setup(SERVO_PIN, GPIO.OUT)
pwm = GPIO.PWM(SERVO_PIN, 50)

# Start at center
current_dc = 7.5
pwm.start(current_dc)

# Track discovered limits
found_min = 2.5
found_max = 10.0

try:
    while True:
        cmd = input(f"\nDuty Cycle: {current_dc:.1f}% | Range: [{found_min:.1f}% - {found_max:.1f}%] > ").strip().lower()

        if cmd == 'q':
            break
        elif cmd == '+':
            current_dc = min(13.0, current_dc + 0.5)
        elif cmd == '-':
            current_dc = max(2.0, current_dc - 0.5)
        elif cmd == '++':
            current_dc = min(13.0, current_dc + 0.1)
        elif cmd == '--':
            current_dc = max(2.0, current_dc - 0.1)
        elif cmd == 'c':
            current_dc = 7.5
        elif cmd == 'min':
            current_dc = found_min
        elif cmd == 'max':
            current_dc = found_max
        elif cmd == 'setmin':
            found_min = current_dc
            print(f"  MIN set to {found_min:.1f}%")
            continue
        elif cmd == 'setmax':
            found_max = current_dc
            print(f"  MAX set to {found_max:.1f}%")
            continue
        elif cmd == 'save':
            print("\n" + "=" * 50)
            print("  YOUR SERVO CALIBRATION VALUES:")
            print("=" * 50)
            print(f"  MIN_DUTY_CYCLE = {found_min:.1f}  # 0 degrees")
            print(f"  MAX_DUTY_CYCLE = {found_max:.1f}  # max degrees")
            print(f"  CENTER = 7.5  # ~90 degrees")
            print(f"  RANGE = ~{int((found_max - found_min) / 0.055)}° estimated")
            print("=" * 50)
            continue
        elif cmd == 'help':
            print("  setmin : Save current as minimum")
            print("  setmax : Save current as maximum")
            continue
        else:
            print("  Unknown command. Type 'help' for options.")
            continue

        pwm.ChangeDutyCycle(current_dc)
        print(f"  -> Moved to {current_dc:.1f}%")
        time.sleep(0.3)

except KeyboardInterrupt:
    print("\n\nInterrupted!")

finally:
    pwm.ChangeDutyCycle(0)
    pwm.stop()
    GPIO.cleanup()
    print("\nFinal calibration:")
    print(f"  MIN: {found_min:.1f}%")
    print(f"  MAX: {found_max:.1f}%")
    print("Done!")
