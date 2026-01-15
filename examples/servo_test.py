#!/usr/bin/env python3
"""PCA9685 and Servo Test Script

Simple test script to validate PCA9685 driver and servo control.
Run this after Pi setup to verify hardware is working.

Usage:
    python examples/servo_test.py

Requirements:
    - Raspberry Pi 4 with I2C enabled
    - PCA9685 connected to I2C bus (address 0x40)
    - At least 1 MG90S servo on channel 0
    - Power system connected (UBEC 6V for servos)
"""

import sys
import time
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from drivers.servo.pca9685 import PCA9685Driver, ServoController


def test_single_servo():
    """Test single servo sweep."""
    print("=" * 60)
    print("TEST 1: Single Servo Sweep")
    print("=" * 60)
    print("Testing servo on channel 0...")
    print("Servo should sweep from 0° to 180° and back")
    print()

    try:
        # Initialize driver
        driver = PCA9685Driver(address=0x40, frequency=50)
        print("✓ PCA9685 initialized at 0x40")

        # Sweep forward
        print("\nSweeping 0° → 180° (step=10°):")
        for angle in range(0, 181, 10):
            driver.set_servo_angle(0, angle)
            print(f"  Angle: {angle:3d}°", end='\r')
            time.sleep(0.1)
        print()

        time.sleep(0.5)

        # Sweep backward
        print("\nSweeping 180° → 0° (step=10°):")
        for angle in range(180, -1, -10):
            driver.set_servo_angle(0, angle)
            print(f"  Angle: {angle:3d}°", end='\r')
            time.sleep(0.1)
        print()

        # Return to center
        driver.set_servo_angle(0, 90)
        print("\n✓ Test complete - servo at 90°")

        driver.disable_channel(0)
        print("✓ Servo disabled")

    except Exception as e:
        print(f"\n✗ Error: {e}")
        return False

    return True


def test_multiple_servos():
    """Test multiple servo coordination."""
    print("\n" + "=" * 60)
    print("TEST 2: Multiple Servo Coordination")
    print("=" * 60)
    print("Testing servos on channels 0, 1, 2...")
    print("Servos should move in synchronized pattern")
    print()

    try:
        driver = PCA9685Driver(address=0x40, frequency=50)
        controller = ServoController(driver)
        print("✓ Servo controller initialized")

        # Set all to center
        print("\nMoving all servos to 90° (center)...")
        controller.move_multiple({0: 90, 1: 90, 2: 90}, delay=1.0)
        print("✓ All servos at center")

        # Wave pattern
        print("\nWave pattern (5 cycles):")
        for cycle in range(5):
            print(f"  Cycle {cycle + 1}/5", end='\r')
            controller.move_multiple({0: 45, 1: 90, 2: 135}, delay=0.3)
            controller.move_multiple({0: 135, 1: 90, 2: 45}, delay=0.3)
        print()

        # Return all to center
        controller.move_multiple({0: 90, 1: 90, 2: 90}, delay=0.5)
        print("✓ Wave pattern complete")

        # Disable all
        driver.disable_all()
        print("✓ All servos disabled")

    except Exception as e:
        print(f"\n✗ Error: {e}")
        return False

    return True


def test_servo_limits():
    """Test servo limit enforcement."""
    print("\n" + "=" * 60)
    print("TEST 3: Servo Limit Enforcement")
    print("=" * 60)
    print("Testing software angle limits...")
    print()

    try:
        driver = PCA9685Driver(address=0x40, frequency=50)
        controller = ServoController(driver)

        # Set limits
        controller.set_servo_limits(0, 30, 150)
        print("✓ Limits set: 30° - 150° for channel 0")

        # Test valid angles
        print("\nTesting valid angles:")
        for angle in [30, 90, 150]:
            controller.move_servo(0, angle)
            print(f"  ✓ Moved to {angle}°")
            time.sleep(0.3)

        # Test invalid angle
        print("\nTesting invalid angle (180°, exceeds 150° limit):")
        try:
            controller.move_servo(0, 180)
            print("  ✗ ERROR: Should have raised exception!")
            return False
        except ValueError as e:
            print(f"  ✓ Correctly rejected: {e}")

        driver.disable_channel(0)
        print("\n✓ Limit enforcement working correctly")

    except Exception as e:
        print(f"\n✗ Error: {e}")
        return False

    return True


def test_emergency_stop():
    """Test emergency stop functionality."""
    print("\n" + "=" * 60)
    print("TEST 4: Emergency Stop")
    print("=" * 60)
    print("Testing emergency disable all channels...")
    print()

    try:
        driver = PCA9685Driver(address=0x40, frequency=50)

        # Enable multiple servos
        print("Enabling servos on channels 0-4 at various angles...")
        driver.set_servo_angle(0, 45)
        driver.set_servo_angle(1, 90)
        driver.set_servo_angle(2, 135)
        driver.set_servo_angle(3, 60)
        driver.set_servo_angle(4, 120)
        print("✓ 5 servos enabled")

        # Check states
        enabled_count = sum(1 for ch in range(5) if driver.channels[ch]['enabled'])
        print(f"  {enabled_count} channels active")

        # Emergency stop
        print("\nExecuting emergency stop...")
        driver.disable_all()

        # Verify all disabled
        enabled_count = sum(1 for ch in range(16) if driver.channels[ch]['enabled'])
        print(f"✓ Emergency stop complete: {enabled_count} channels active (should be 0)")

        if enabled_count != 0:
            print("  ✗ ERROR: Some channels still enabled!")
            return False

    except Exception as e:
        print(f"\n✗ Error: {e}")
        return False

    return True


def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("OpenDuck Mini V3 - Servo Test Suite")
    print("=" * 60)
    print("This script tests PCA9685 driver and servo control.")
    print()
    print("Hardware requirements:")
    print("  - PCA9685 on I2C address 0x40")
    print("  - Servo on channel 0 (minimum)")
    print("  - Servos on channels 1-2 (for multi-servo test)")
    print()
    input("Press ENTER to start tests (Ctrl+C to cancel)...")

    results = []

    # Run tests
    results.append(("Single Servo Sweep", test_single_servo()))
    results.append(("Multiple Servo Coordination", test_multiple_servos()))
    results.append(("Servo Limit Enforcement", test_servo_limits()))
    results.append(("Emergency Stop", test_emergency_stop()))

    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)

    for test_name, passed in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{test_name:.<50} {status}")

    passed_count = sum(1 for _, passed in results if passed)
    total_count = len(results)

    print()
    print(f"Results: {passed_count}/{total_count} tests passed")

    if passed_count == total_count:
        print("\n✓ All tests PASSED! Hardware is working correctly.")
        return 0
    else:
        print(f"\n✗ {total_count - passed_count} test(s) FAILED. Check hardware connections.")
        return 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nFatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
