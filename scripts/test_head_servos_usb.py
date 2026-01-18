#!/usr/bin/env python3
"""
Day 11 Head Servo Test - USB Power via PCA9685
OpenDuck Mini V3

Tests the pan/tilt head servos using USB phone charger power (5V 2A)
routed through cut USB cable to PCA9685 screw terminals.

Hardware Setup:
    USB Phone Charger (5V 2A)
    ├── Cut USB cable (red/black wires)
    │   └── Red (+5V) → PCA9685 V+ screw terminal
    │   └── Black (GND) → PCA9685 GND screw terminal
    │
    PCA9685 PWM Controller (I2C addr: 0x40)
    ├── VCC → Pi 3.3V (logic power)
    ├── GND → Pi GND
    ├── SDA → Pi GPIO 2 (Pin 3)
    ├── SCL → Pi GPIO 3 (Pin 5)
    ├── Channel 12 → Pan servo (signal wire)
    └── Channel 13 → Tilt servo (signal wire)

Safety:
    - USB power limited to 2A (safe for 2 SG90 servos)
    - PCA9685 handles PWM generation (reduces Pi load)
    - Ctrl+C emergency stop supported

Author: OpenDuck Team
Created: 19 January 2026 (Day 11)
"""

import argparse
import sys
import time
from typing import Optional

# Try to import hardware libraries
try:
    import board
    import busio
    from adafruit_pca9685 import PCA9685
    HARDWARE_AVAILABLE = True
except ImportError:
    HARDWARE_AVAILABLE = False
    print("WARNING: Running in simulation mode (not on Raspberry Pi)")


# Configuration from robot_config.yaml
PAN_CHANNEL = 12   # Head pan servo
TILT_CHANNEL = 13  # Head tilt servo
PWM_FREQUENCY = 50  # 50Hz for servos

# =============================================================================
# FIX H-007: SERVO ANGLE DOCUMENTATION
# =============================================================================
# These are PHYSICAL servo angles (0-180 degree range).
# HeadController uses LOGICAL angles centered at 0:
#   - Pan logical: -45 to +45 degrees (left/right from center)
#   - Tilt logical: -20 to +20 degrees (down/up from center)
#
# Conversion: servo_angle = 90 + logical_angle
#   - Logical -45 -> Servo 45 (PAN_MIN)
#   - Logical 0   -> Servo 90 (CENTER)
#   - Logical +45 -> Servo 135 (PAN_MAX)
#
# This test script uses physical angles directly for hardware validation.
# =============================================================================

# Physical servo angle limits
PAN_MIN = 45.0      # Logical: -45 (full left)
PAN_CENTER = 90.0   # Logical: 0 (center)
PAN_MAX = 135.0     # Logical: +45 (full right)

TILT_MIN = 70.0     # Logical: -20 (down)
TILT_CENTER = 90.0  # Logical: 0 (center)
TILT_MAX = 110.0    # Logical: +20 (up)

# PWM pulse width in microseconds
SERVO_MIN_PULSE = 1000   # 0 degrees
SERVO_MAX_PULSE = 2000   # 180 degrees


def angle_to_duty_cycle(angle: float, frequency: int = 50) -> int:
    """Convert angle (0-180) to PCA9685 duty cycle (0-65535).

    Args:
        angle: Target angle in degrees (0-180)
        frequency: PWM frequency in Hz

    Returns:
        Duty cycle value for PCA9685 (0-65535)
    """
    # Clamp angle
    angle = max(0, min(180, angle))

    # Calculate pulse width in microseconds
    pulse_width = SERVO_MIN_PULSE + (SERVO_MAX_PULSE - SERVO_MIN_PULSE) * (angle / 180)

    # Convert to duty cycle
    # Period in microseconds = 1,000,000 / frequency
    period_us = 1_000_000 // frequency
    duty_cycle = int((pulse_width / period_us) * 65535)

    return duty_cycle


class HeadServoTester:
    """Test harness for head servos via PCA9685."""

    def __init__(self, simulate: bool = False):
        """Initialize tester.

        Args:
            simulate: If True, run in simulation mode (no hardware)
        """
        self.simulate = simulate or not HARDWARE_AVAILABLE
        self.i2c = None
        self.pca = None

        if not self.simulate:
            self._init_hardware()

    def _init_hardware(self) -> None:
        """Initialize I2C and PCA9685."""
        try:
            print("Initializing I2C bus...")
            self.i2c = busio.I2C(board.SCL, board.SDA)

            print("Initializing PCA9685 at 0x40...")
            self.pca = PCA9685(self.i2c)
            self.pca.frequency = PWM_FREQUENCY

            # Initialize both channels to center position
            print(f"Setting pan (ch {PAN_CHANNEL}) to center...")
            self._set_angle(PAN_CHANNEL, PAN_CENTER)

            print(f"Setting tilt (ch {TILT_CHANNEL}) to center...")
            self._set_angle(TILT_CHANNEL, TILT_CENTER)

            print("Hardware initialized successfully!")

        except Exception as e:
            print(f"ERROR: Failed to initialize hardware: {e}")
            raise

    def _set_angle(self, channel: int, angle: float) -> None:
        """Set servo angle on channel.

        Args:
            channel: PCA9685 channel (0-15)
            angle: Target angle in degrees (0-180)
        """
        if self.simulate:
            print(f"  [SIM] Channel {channel} -> {angle:.1f} degrees")
            return

        duty_cycle = angle_to_duty_cycle(angle, PWM_FREQUENCY)
        self.pca.channels[channel].duty_cycle = duty_cycle

    def _disable_channel(self, channel: int) -> None:
        """Disable servo channel (stop PWM signal).

        Args:
            channel: PCA9685 channel (0-15)
        """
        if self.simulate:
            print(f"  [SIM] Channel {channel} disabled")
            return

        self.pca.channels[channel].duty_cycle = 0

    def test_pan_range(self) -> bool:
        """Test pan servo full range of motion.

        Returns:
            True if test completed (user confirmation)
        """
        print("\n" + "=" * 60)
        print("  PAN SERVO TEST (Channel 12)")
        print("=" * 60)
        print(f"Range: {PAN_MIN}° to {PAN_MAX}° (center: {PAN_CENTER}°)")
        print()

        positions = [
            (PAN_CENTER, "CENTER", 2),
            (PAN_MIN, "LEFT (min)", 2),
            (PAN_CENTER, "CENTER", 1),
            (PAN_MAX, "RIGHT (max)", 2),
            (PAN_CENTER, "CENTER", 1),
        ]

        for angle, name, wait in positions:
            print(f"  Moving to {name} ({angle}°)...")
            self._set_angle(PAN_CHANNEL, angle)
            time.sleep(wait)

        print("\nPan test complete!")
        return True

    def test_tilt_range(self) -> bool:
        """Test tilt servo full range of motion.

        Returns:
            True if test completed
        """
        print("\n" + "=" * 60)
        print("  TILT SERVO TEST (Channel 13)")
        print("=" * 60)
        print(f"Range: {TILT_MIN}° to {TILT_MAX}° (center: {TILT_CENTER}°)")
        print()

        positions = [
            (TILT_CENTER, "CENTER", 2),
            (TILT_MIN, "DOWN (min)", 2),
            (TILT_CENTER, "CENTER", 1),
            (TILT_MAX, "UP (max)", 2),
            (TILT_CENTER, "CENTER", 1),
        ]

        for angle, name, wait in positions:
            print(f"  Moving to {name} ({angle}°)...")
            self._set_angle(TILT_CHANNEL, angle)
            time.sleep(wait)

        print("\nTilt test complete!")
        return True

    def test_combined_movement(self) -> bool:
        """Test combined pan+tilt movement.

        Returns:
            True if test completed
        """
        print("\n" + "=" * 60)
        print("  COMBINED MOVEMENT TEST")
        print("=" * 60)
        print("Testing coordinated head movements...")
        print()

        # Define movement sequence
        movements = [
            # (pan, tilt, name, wait)
            (PAN_CENTER, TILT_CENTER, "Center", 2),
            (PAN_MIN, TILT_MIN, "Bottom-Left", 2),
            (PAN_MAX, TILT_MIN, "Bottom-Right", 2),
            (PAN_MAX, TILT_MAX, "Top-Right", 2),
            (PAN_MIN, TILT_MAX, "Top-Left", 2),
            (PAN_CENTER, TILT_CENTER, "Center", 2),
        ]

        for pan, tilt, name, wait in movements:
            print(f"  Moving to {name} (pan={pan}°, tilt={tilt}°)...")
            self._set_angle(PAN_CHANNEL, pan)
            self._set_angle(TILT_CHANNEL, tilt)
            time.sleep(wait)

        print("\nCombined movement test complete!")
        return True

    def test_nod_gesture(self) -> bool:
        """Test nodding gesture (vertical movement).

        Returns:
            True if test completed
        """
        print("\n" + "=" * 60)
        print("  NOD GESTURE TEST")
        print("=" * 60)
        print("Robot should nod 3 times...")
        print()

        # Center first
        self._set_angle(PAN_CHANNEL, PAN_CENTER)
        self._set_angle(TILT_CHANNEL, TILT_CENTER)
        time.sleep(1)

        for i in range(3):
            print(f"  Nod {i+1}/3...")
            self._set_angle(TILT_CHANNEL, TILT_MIN)
            time.sleep(0.3)
            self._set_angle(TILT_CHANNEL, TILT_CENTER)
            time.sleep(0.3)

        print("\nNod gesture complete!")
        return True

    def test_shake_gesture(self) -> bool:
        """Test head shake gesture (horizontal movement).

        Returns:
            True if test completed
        """
        print("\n" + "=" * 60)
        print("  HEAD SHAKE GESTURE TEST")
        print("=" * 60)
        print("Robot should shake head 3 times...")
        print()

        # Center first
        self._set_angle(PAN_CHANNEL, PAN_CENTER)
        self._set_angle(TILT_CHANNEL, TILT_CENTER)
        time.sleep(1)

        for i in range(3):
            print(f"  Shake {i+1}/3...")
            self._set_angle(PAN_CHANNEL, PAN_MIN + 15)  # Slight left
            time.sleep(0.25)
            self._set_angle(PAN_CHANNEL, PAN_MAX - 15)  # Slight right
            time.sleep(0.25)
            self._set_angle(PAN_CHANNEL, PAN_CENTER)
            time.sleep(0.2)

        print("\nHead shake gesture complete!")
        return True

    def run_all_tests(self) -> bool:
        """Run all head servo tests.

        Returns:
            True if all tests completed successfully
        """
        print("\n" + "#" * 60)
        print("  DAY 11 HEAD SERVO VALIDATION")
        print("  OpenDuck Mini V3")
        print("#" * 60)

        if self.simulate:
            print("\n  [SIMULATION MODE - No hardware connected]")

        try:
            self.test_pan_range()
            self.test_tilt_range()
            self.test_combined_movement()
            self.test_nod_gesture()
            self.test_shake_gesture()

            print("\n" + "=" * 60)
            print("  ALL TESTS COMPLETE!")
            print("=" * 60)

            return True

        except KeyboardInterrupt:
            print("\n\n! Emergency stop (Ctrl+C)")
            return False

    def cleanup(self) -> None:
        """Cleanup hardware resources."""
        print("\nCleaning up...")

        if self.pca is not None:
            # Disable both channels
            self._disable_channel(PAN_CHANNEL)
            self._disable_channel(TILT_CHANNEL)

            try:
                self.pca.deinit()
            except Exception:
                pass

        if self.i2c is not None:
            try:
                self.i2c.deinit()
            except Exception:
                pass

        print("Cleanup complete!")


def main() -> int:
    """Main entry point.

    Returns:
        0 on success, 1 on failure, 2 on script error
    """
    parser = argparse.ArgumentParser(
        description="Day 11 Head Servo Test - USB Power via PCA9685"
    )
    parser.add_argument(
        "--simulate", "-s", action="store_true",
        help="Run in simulation mode (no hardware)"
    )
    parser.add_argument(
        "--pan-only", action="store_true",
        help="Test only pan servo"
    )
    parser.add_argument(
        "--tilt-only", action="store_true",
        help="Test only tilt servo"
    )
    parser.add_argument(
        "--gestures", action="store_true",
        help="Test only gestures (nod/shake)"
    )

    args = parser.parse_args()

    print("=" * 60)
    print("  Day 11 Head Servo Test")
    print("  Power: USB phone charger (5V 2A) via PCA9685")
    print("=" * 60)
    print()
    print("Hardware checklist:")
    print("  [ ] USB phone charger plugged in (5V 2A)")
    print("  [ ] Cut USB cable connected to PCA9685 V+ and GND")
    print("  [ ] PCA9685 logic power from Pi 3.3V")
    print("  [ ] PCA9685 I2C connected (SDA/SCL)")
    print("  [ ] Pan servo on channel 12")
    print("  [ ] Tilt servo on channel 13")
    print()

    if not args.simulate and not HARDWARE_AVAILABLE:
        print("ERROR: Hardware libraries not available.")
        print("       Install with: pip install adafruit-pca9685")
        return 2

    tester = HeadServoTester(simulate=args.simulate)

    try:
        if args.pan_only:
            success = tester.test_pan_range()
        elif args.tilt_only:
            success = tester.test_tilt_range()
        elif args.gestures:
            success = tester.test_nod_gesture() and tester.test_shake_gesture()
        else:
            success = tester.run_all_tests()

        return 0 if success else 1

    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        return 1

    except Exception as e:
        print(f"\n\nScript error: {e}")
        import traceback
        traceback.print_exc()
        return 2

    finally:
        tester.cleanup()


if __name__ == "__main__":
    sys.exit(main())
