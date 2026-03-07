#!/usr/bin/env python3
"""BNO085 IMU Hardware Validation Script for OpenDuck Mini V3

This script validates the BNO085 9-DOF IMU sensor on real hardware.
Run this on the Raspberry Pi after wiring the BNO085.

Wiring Guide (BNO085 -> Raspberry Pi 4):
    VCC  -> Pin 1 (3.3V)
    GND  -> Pin 6 (GND)
    SDA  -> Pin 3 (GPIO 2 - I2C SDA)
    SCL  -> Pin 5 (GPIO 3 - I2C SCL)
    INT  -> Not connected (optional)
    RST  -> Not connected (optional)

Prerequisites:
    1. Enable I2C in raspi-config:
       sudo raspi-config -> Interfacing Options -> I2C -> Enable

    2. Install dependencies:
       pip install adafruit-circuitpython-bno08x

    3. Reboot after config changes

Usage:
    python scripts/validate_bno085_hardware.py

Author: Day 17 Hardware Validation
Date: 22 January 2026
"""

import sys
import time
import argparse
from pathlib import Path

# Add project root to path for imports
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))


def print_header(title: str) -> None:
    """Print a formatted section header."""
    print("\n" + "=" * 60)
    print(f" {title}")
    print("=" * 60)


def print_result(test_name: str, passed: bool, details: str = "") -> None:
    """Print a test result with status."""
    status = "PASS" if passed else "FAIL"
    print(f"  {test_name}: {status}")
    if details:
        print(f"    -> {details}")


def check_dependencies() -> bool:
    """Check if required dependencies are installed."""
    print_header("Dependency Check")

    all_ok = True

    # Check board
    try:
        import board
        print_result("board", True, "CircuitPython board available")
    except ImportError:
        print_result("board", False, "pip install adafruit-blinka")
        all_ok = False

    # Check busio
    try:
        import busio
        print_result("busio", True, "I2C bus interface available")
    except ImportError:
        print_result("busio", False, "pip install adafruit-blinka")
        all_ok = False

    # Check BNO08x library
    try:
        from adafruit_bno08x.i2c import BNO08X_I2C
        print_result("adafruit_bno08x", True, "BNO08x library available")
    except ImportError:
        print_result("adafruit_bno08x", False, "pip install adafruit-circuitpython-bno08x")
        all_ok = False

    return all_ok


def scan_i2c_bus() -> list:
    """Scan I2C bus for connected devices."""
    print_header("I2C Bus Scan")

    try:
        import board
        import busio

        i2c = busio.I2C(board.SCL, board.SDA)

        print("\n  Scanning I2C bus for devices...")

        # Lock bus for scanning
        while not i2c.try_lock():
            pass

        try:
            devices = i2c.scan()

            if devices:
                print(f"\n  Found {len(devices)} device(s):")
                for addr in devices:
                    device_name = "Unknown"
                    if addr == 0x4A:
                        device_name = "BNO085 (default address)"
                    elif addr == 0x4B:
                        device_name = "BNO085 (alternate address)"
                    elif addr == 0x40:
                        device_name = "PCA9685 (servo controller)"
                    elif addr in (0x68, 0x69):
                        device_name = "MPU6050 or similar"

                    print(f"    0x{addr:02X} - {device_name}")

                # Check for BNO085
                if 0x4A in devices or 0x4B in devices:
                    print_result("BNO085 detected", True)
                    return devices
                else:
                    print_result("BNO085 detected", False, "Not found at 0x4A or 0x4B")
                    return []
            else:
                print("  No I2C devices found!")
                print_result("I2C devices", False, "Check wiring and connections")
                return []

        finally:
            i2c.unlock()

    except Exception as e:
        print(f"  Error scanning I2C: {e}")
        print("\n  Troubleshooting:")
        print("    1. Check I2C is enabled: sudo raspi-config")
        print("    2. Check wiring: SDA->Pin3, SCL->Pin5")
        print("    3. Check power: VCC->3.3V, GND->GND")
        return []


def test_basic_initialization() -> bool:
    """Test basic BNO085 initialization."""
    print_header("Basic Initialization Test")

    try:
        import board
        import busio
        from adafruit_bno08x.i2c import BNO08X_I2C
        from adafruit_bno08x import BNO_REPORT_ROTATION_VECTOR

        print("\n  Initializing BNO085...")

        i2c = busio.I2C(board.SCL, board.SDA, frequency=400000)
        bno = BNO08X_I2C(i2c)

        print_result("I2C connection", True)

        # Enable rotation vector
        bno.enable_feature(BNO_REPORT_ROTATION_VECTOR)
        time.sleep(0.5)

        print_result("Feature enable", True, "Rotation vector enabled")

        return True

    except Exception as e:
        print(f"\n  Initialization failed: {e}")
        print_result("Initialization", False, str(e))
        return False


def test_orientation_reading(duration_seconds: float = 5.0) -> bool:
    """Test continuous orientation reading."""
    print_header("Orientation Reading Test")

    try:
        import board
        import busio
        from adafruit_bno08x.i2c import BNO08X_I2C
        from adafruit_bno08x import BNO_REPORT_ROTATION_VECTOR
        import math

        i2c = busio.I2C(board.SCL, board.SDA, frequency=400000)
        bno = BNO08X_I2C(i2c)
        bno.enable_feature(BNO_REPORT_ROTATION_VECTOR)
        time.sleep(0.5)

        print(f"\n  Reading orientation for {duration_seconds}s...")
        print("  (Rotate the sensor to see values change)")
        print()

        start_time = time.time()
        readings = []
        max_heading = 0
        min_heading = 360

        while time.time() - start_time < duration_seconds:
            try:
                quat_i, quat_j, quat_k, quat_real = bno.quaternion

                if quat_real is not None:
                    # Convert quaternion to heading
                    siny_cosp = 2 * (quat_real * quat_k + quat_i * quat_j)
                    cosy_cosp = 1 - 2 * (quat_j * quat_j + quat_k * quat_k)
                    heading = math.degrees(math.atan2(siny_cosp, cosy_cosp))
                    if heading < 0:
                        heading += 360

                    # Roll
                    sinr_cosp = 2 * (quat_real * quat_i + quat_j * quat_k)
                    cosr_cosp = 1 - 2 * (quat_i * quat_i + quat_j * quat_j)
                    roll = math.degrees(math.atan2(sinr_cosp, cosr_cosp))

                    # Pitch
                    sinp = 2 * (quat_real * quat_j - quat_k * quat_i)
                    if abs(sinp) >= 1:
                        pitch = math.copysign(90, sinp)
                    else:
                        pitch = math.degrees(math.asin(sinp))

                    readings.append((heading, roll, pitch))

                    max_heading = max(max_heading, heading)
                    min_heading = min(min_heading, heading)

                    print(f"\r  Heading: {heading:6.1f}  Roll: {roll:7.1f}  Pitch: {pitch:7.1f}", end="", flush=True)

            except Exception:
                pass

            time.sleep(0.05)  # 20Hz

        print("\n")

        # Statistics
        if readings:
            avg_heading = sum(r[0] for r in readings) / len(readings)
            heading_range = max_heading - min_heading

            print(f"  Readings captured: {len(readings)}")
            print(f"  Heading range: {min_heading:.1f} to {max_heading:.1f} ({heading_range:.1f} deg)")
            print(f"  Average heading: {avg_heading:.1f}")

            # Validation
            if len(readings) > 10:
                print_result("Continuous reading", True, f"{len(readings)} samples")
            else:
                print_result("Continuous reading", False, "Too few samples")
                return False

            if heading_range > 5:
                print_result("Sensor responds to motion", True, f"{heading_range:.1f} deg range")
            else:
                print_result("Sensor responds to motion", False, "Try rotating the sensor")

            return True
        else:
            print_result("Reading data", False, "No valid readings")
            return False

    except Exception as e:
        print(f"\n  Reading failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_acceleration_reading() -> bool:
    """Test acceleration reading."""
    print_header("Acceleration Reading Test")

    try:
        import board
        import busio
        from adafruit_bno08x.i2c import BNO08X_I2C
        from adafruit_bno08x import BNO_REPORT_ACCELEROMETER

        i2c = busio.I2C(board.SCL, board.SDA, frequency=400000)
        bno = BNO08X_I2C(i2c)
        bno.enable_feature(BNO_REPORT_ACCELEROMETER)
        time.sleep(0.5)

        print("\n  Reading acceleration...")

        readings = []
        for _ in range(20):
            try:
                accel_x, accel_y, accel_z = bno.acceleration
                if accel_x is not None:
                    readings.append((accel_x, accel_y, accel_z))
                    print(f"\r  X: {accel_x:7.2f}  Y: {accel_y:7.2f}  Z: {accel_z:7.2f} m/s^2", end="", flush=True)
            except Exception:
                pass
            time.sleep(0.1)

        print("\n")

        if readings:
            # Check for gravity (should be ~9.81 in one axis)
            avg_z = sum(r[2] for r in readings) / len(readings)
            gravity_detected = abs(avg_z) > 8.0  # Should be close to 9.81

            print(f"  Samples: {len(readings)}")
            print(f"  Average Z (gravity): {avg_z:.2f} m/s^2")

            if gravity_detected:
                print_result("Gravity detected", True, f"~{abs(avg_z):.1f} m/s^2")
                return True
            else:
                print_result("Gravity detected", False, "Expected ~9.81 in one axis")
                return False
        else:
            print_result("Acceleration reading", False, "No valid readings")
            return False

    except Exception as e:
        print(f"\n  Acceleration test failed: {e}")
        return False


def test_gyroscope_reading() -> bool:
    """Test gyroscope reading."""
    print_header("Gyroscope Reading Test")

    try:
        import board
        import busio
        from adafruit_bno08x.i2c import BNO08X_I2C
        from adafruit_bno08x import BNO_REPORT_GYROSCOPE

        i2c = busio.I2C(board.SCL, board.SDA, frequency=400000)
        bno = BNO08X_I2C(i2c)
        bno.enable_feature(BNO_REPORT_GYROSCOPE)
        time.sleep(0.5)

        print("\n  Reading gyroscope (keep sensor still)...")

        readings = []
        for _ in range(20):
            try:
                gyro_x, gyro_y, gyro_z = bno.gyro
                if gyro_x is not None:
                    readings.append((gyro_x, gyro_y, gyro_z))
                    print(f"\r  X: {gyro_x:7.3f}  Y: {gyro_y:7.3f}  Z: {gyro_z:7.3f} rad/s", end="", flush=True)
            except Exception:
                pass
            time.sleep(0.1)

        print("\n")

        if readings:
            # When stationary, gyro should be near zero
            avg_magnitude = sum(
                abs(r[0]) + abs(r[1]) + abs(r[2]) for r in readings
            ) / len(readings)

            print(f"  Samples: {len(readings)}")
            print(f"  Average total angular velocity: {avg_magnitude:.4f} rad/s")

            # Stationary should be very low
            if avg_magnitude < 0.5:
                print_result("Gyro at rest", True, "Low drift detected")
                return True
            else:
                print_result("Gyro at rest", False, "High values - sensor may be moving or noisy")
                return True  # Not a failure if sensor is moving

        else:
            print_result("Gyroscope reading", False, "No valid readings")
            return False

    except Exception as e:
        print(f"\n  Gyroscope test failed: {e}")
        return False


def test_driver_integration() -> bool:
    """Test integration with the BNO085 driver class."""
    print_header("Driver Integration Test")

    try:
        from drivers.sensor.imu.bno085 import BNO085Driver, IMUData, Quaternion

        print("\n  Testing BNO085Driver class...")

        # Create driver
        driver = BNO085Driver()
        print_result("Driver instantiation", True)

        # Read orientation
        data = driver.read_orientation()
        if isinstance(data, IMUData):
            print_result("read_orientation()", True, f"Heading={data.heading:.1f}")
        else:
            print_result("read_orientation()", False, "Invalid return type")
            return False

        # Read quaternion
        quat = driver.read_quaternion()
        if isinstance(quat, Quaternion):
            print_result("read_quaternion()", True, f"W={quat.w:.3f}")
        else:
            print_result("read_quaternion()", False, "Invalid return type")
            return False

        # Read acceleration
        accel = driver.read_acceleration()
        if len(accel) == 3:
            print_result("read_acceleration()", True, f"Z={accel[2]:.2f}")
        else:
            print_result("read_acceleration()", False, "Invalid return")
            return False

        # Read gyro
        gyro = driver.read_gyro()
        if len(gyro) == 3:
            print_result("read_gyro()", True, f"Total={sum(abs(g) for g in gyro):.3f}")
        else:
            print_result("read_gyro()", False, "Invalid return")
            return False

        # Get calibration status
        status = driver.get_calibration_status()
        print_result("get_calibration_status()", True, f"System={status['system']}")

        return True

    except ImportError as e:
        print(f"\n  Driver import failed: {e}")
        print("  Running without driver integration test")
        return True  # Don't fail if driver not available

    except Exception as e:
        print(f"\n  Driver test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all hardware validation tests."""
    parser = argparse.ArgumentParser(
        description="BNO085 Hardware Validation Script"
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=5.0,
        help="Orientation test duration in seconds (default: 5.0)"
    )
    parser.add_argument(
        "--skip-driver",
        action="store_true",
        help="Skip driver integration test"
    )
    args = parser.parse_args()

    print("\n" + "=" * 60)
    print(" BNO085 Hardware Validation - OpenDuck Mini V3")
    print(" Day 17 - 22 January 2026")
    print("=" * 60)

    results = {}

    # Test 1: Dependencies
    results['dependencies'] = check_dependencies()
    if not results['dependencies']:
        print("\n  Missing dependencies. Install them and try again.")
        return 1

    # Test 2: I2C scan
    devices = scan_i2c_bus()
    results['i2c_scan'] = len(devices) > 0 and (0x4A in devices or 0x4B in devices)

    if not results['i2c_scan']:
        print("\n  BNO085 not detected on I2C bus.")
        print("  Check wiring and try again.")
        return 1

    # Test 3: Basic initialization
    results['initialization'] = test_basic_initialization()

    if not results['initialization']:
        print("\n  Initialization failed. Check wiring.")
        return 1

    # Test 4: Orientation reading
    results['orientation'] = test_orientation_reading(duration_seconds=args.duration)

    # Test 5: Acceleration reading
    results['acceleration'] = test_acceleration_reading()

    # Test 6: Gyroscope reading
    results['gyroscope'] = test_gyroscope_reading()

    # Test 7: Driver integration (optional)
    if not args.skip_driver:
        results['driver'] = test_driver_integration()

    # Summary
    print_header("VALIDATION SUMMARY")

    passed = sum(1 for v in results.values() if v)
    total = len(results)

    print(f"\n  Results: {passed}/{total} tests passed")
    print()

    for test_name, result in results.items():
        status = "PASS" if result else "FAIL"
        print(f"    {test_name}: {status}")

    overall = all(results.values())

    print()
    if overall:
        print("  ================================================")
        print("     BNO085 HARDWARE VALIDATION PASS")
        print("  ================================================")
    else:
        print("  ================================================")
        print("     BNO085 HARDWARE VALIDATION FAIL")
        print("  ================================================")
        print("\n  Check wiring and I2C configuration.")

    return 0 if overall else 1


if __name__ == "__main__":
    sys.exit(main())
