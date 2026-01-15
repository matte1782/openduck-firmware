#!/usr/bin/env python3
"""
Sensor test utility for OpenDuck Mini V3
Validates all sensors are functioning correctly

Tests:
    - IMU (BNO085): 9-DOF orientation sensor with sensor fusion
    - Servo Driver: PCA9685 communication
    - Battery Voltage: Manual check (ADC driver TBD in v1.1)

Usage:
    python test_sensors.py [--verbose] [--continuous]

Safety:
    - Keep robot stationary during IMU tests
    - Battery should be connected for servo driver tests
    - Do not move servos during this test
"""
import sys
import time
import argparse
from pathlib import Path

# Add parent src directory to Python path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

def test_i2c_bus():
    """Test I2C bus availability"""
    print("\n" + "=" * 60)
    print("TEST 1: I2C Bus Detection")
    print("=" * 60)

    try:
        import smbus2
        bus = smbus2.SMBus(1)
        print("✓ I2C bus initialized (bus 1)")

        # Scan for devices
        print("\nScanning I2C bus for devices...")
        devices_found = []
        for addr in range(0x03, 0x78):
            try:
                bus.read_byte(addr)
                devices_found.append(addr)
                print(f"  Found device at: 0x{addr:02X}")
            except:
                pass

        if devices_found:
            print(f"\n✓ Found {len(devices_found)} I2C device(s)")
            return True, devices_found
        else:
            print("\n✗ No I2C devices found")
            print("  Check connections and verify I2C is enabled:")
            print("  sudo raspi-config > Interface Options > I2C")
            return False, []

    except Exception as e:
        print(f"✗ I2C bus error: {e}")
        return False, []

def test_bno085():
    """Test BNO085 9-DOF IMU sensor"""
    print("\n" + "=" * 60)
    print("TEST 2: BNO085 9-DOF IMU Sensor")
    print("=" * 60)

    try:
        from drivers.sensor.imu.bno085 import BNO085Driver
        print("✓ BNO085 driver imported")

        # Initialize sensor
        print("Initializing BNO085 (address 0x4A or 0x4B)...")
        imu = BNO085Driver()
        print("✓ BNO085 initialized")

        # Read orientation
        print("\nReading orientation (absolute)...")
        orientation = imu.read_orientation()
        print(f"  Heading: {orientation.heading:6.1f}° (0=North)")
        print(f"  Roll:    {orientation.roll:6.1f}° (-180 to 180)")
        print(f"  Pitch:   {orientation.pitch:6.1f}° (-90 to 90)")

        # Check if robot is upright
        if -10.0 < orientation.roll < 10.0 and -10.0 < orientation.pitch < 10.0:
            print("✓ Robot appears level")
        else:
            print(f"⚠️  Robot may not be level (roll={orientation.roll:.1f}°, pitch={orientation.pitch:.1f}°)")

        # Read accelerometer
        print("\nReading accelerometer...")
        accel_x, accel_y, accel_z = imu.read_acceleration()
        print(f"  X: {accel_x:7.3f} m/s²")
        print(f"  Y: {accel_y:7.3f} m/s²")
        print(f"  Z: {accel_z:7.3f} m/s²")

        # Read gyroscope
        print("\nReading gyroscope (robot should be stationary)...")
        gyro_x, gyro_y, gyro_z = imu.read_gyro()
        print(f"  X: {gyro_x:7.2f} °/s")
        print(f"  Y: {gyro_y:7.2f} °/s")
        print(f"  Z: {gyro_z:7.2f} °/s")

        # Check if robot is stationary
        max_gyro = max(abs(gyro_x), abs(gyro_y), abs(gyro_z))
        if max_gyro < 5.0:
            print("✓ Robot is stationary (gyro < 5°/s)")
        else:
            print(f"⚠️  Robot may be moving (max gyro = {max_gyro:.2f}°/s)")

        # Read quaternion
        print("\nReading quaternion...")
        quat = imu.read_quaternion()
        print(f"  W: {quat.w:7.4f}")
        print(f"  X: {quat.x:7.4f}")
        print(f"  Y: {quat.y:7.4f}")
        print(f"  Z: {quat.z:7.4f}")

        # Verify quaternion magnitude (should be ~1.0)
        magnitude = (quat.w**2 + quat.x**2 + quat.y**2 + quat.z**2)**0.5
        if 0.98 < magnitude < 1.02:
            print(f"✓ Quaternion normalized (magnitude = {magnitude:.4f})")
        else:
            print(f"⚠️  Quaternion not normalized (magnitude = {magnitude:.4f})")

        print("\n✓ BNO085 test PASSED")
        return True

    except ImportError as e:
        print(f"✗ Cannot import BNO085 driver: {e}")
        print("  Ensure firmware/src/drivers/sensor/imu/bno085.py exists")
        return False
    except Exception as e:
        print(f"✗ BNO085 test FAILED: {e}")
        print("  Check:")
        print("  - BNO085 is connected to I2C bus")
        print("  - I2C address is correct (0x4A or 0x4B)")
        print("  - Power supply is stable (3.3V)")
        print("  - adafruit-circuitpython-bno08x library is installed")
        return False

def test_battery_voltage():
    """Test battery voltage monitoring (manual check)"""
    print("\n" + "=" * 60)
    print("TEST 3: Battery Voltage Monitoring")
    print("=" * 60)

    print("⚠️  Hardware ADC driver not yet implemented (planned for v1.1)")
    print("\n📋 Manual voltage check required:")
    print("  1. Use multimeter to measure battery voltage")
    print("  2. Expected range: 6.0V - 8.4V (2S LiPo)")
    print("  3. Voltage thresholds:")
    print("     - < 6.0V: CRITICAL (shutdown)")
    print("     - 6.0-6.4V: Low (warning)")
    print("     - 6.4-8.4V: Normal")
    print("     - > 8.4V: Overcharged (danger)")

    # Ask user for manual confirmation
    try:
        response = input("\nHave you checked battery voltage with multimeter? (y/n): ")
        if response.lower() == 'y':
            voltage_str = input("Enter measured voltage (V): ")
            voltage = float(voltage_str)

            if voltage < 6.0:
                print(f"✗ CRITICAL: Battery voltage too low ({voltage:.2f}V)")
                print("  ⚠️  CHARGE BATTERY IMMEDIATELY")
                return False
            elif voltage < 6.4:
                print(f"⚠️  WARNING: Battery low ({voltage:.2f}V)")
                return True
            elif voltage <= 8.4:
                print(f"✓ Battery voltage normal ({voltage:.2f}V)")
                return True
            else:
                print(f"⚠️  Battery voltage high ({voltage:.2f}V)")
                return True
        else:
            print("⚠️  Battery voltage not checked (SKIPPED)")
            return False
    except ValueError:
        print("✗ Invalid voltage value")
        return False
    except KeyboardInterrupt:
        print("\n⚠️  Test interrupted")
        return False

def test_pca9685():
    """Test PCA9685 servo driver (communication only, no servo movement)"""
    print("\n" + "=" * 60)
    print("TEST 4: PCA9685 Servo Driver")
    print("=" * 60)

    try:
        from drivers.servo.pca9685 import PCA9685Driver
        print("✓ PCA9685 driver imported")

        # Initialize driver
        print("Initializing PCA9685 (address 0x40)...")
        driver = PCA9685Driver(frequency=50)
        print("✓ PCA9685 initialized at 50Hz")

        # Put driver in sleep mode (no servo movement)
        print("\nPutting driver in sleep mode (no servo movement)...")
        driver.sleep()
        print("✓ Sleep mode activated")

        # Wake driver
        print("\nWaking driver...")
        driver.wake()
        print("✓ Driver awake")

        # Sleep again for safety
        driver.sleep()
        print("✓ Driver returned to sleep mode")

        # Cleanup
        driver.deinit()
        print("✓ Driver deinitialized")

        print("\n✓ PCA9685 test PASSED")
        print("  (Communication verified, no servos moved)")
        return True

    except ImportError as e:
        print(f"✗ Cannot import PCA9685 driver: {e}")
        print("  Ensure firmware/src/drivers/servo/pca9685.py exists")
        return False
    except Exception as e:
        print(f"✗ PCA9685 test FAILED: {e}")
        print("  Check:")
        print("  - PCA9685 is connected to I2C bus")
        print("  - Power supply is connected to PCA9685")
        print("  - I2C address is correct (usually 0x40)")
        return False

def continuous_monitoring():
    """Continuous sensor monitoring mode"""
    print("\n" + "=" * 60)
    print("CONTINUOUS MONITORING MODE")
    print("=" * 60)
    print("Press Ctrl+C to stop\n")

    try:
        from drivers.sensor.imu.bno085 import BNO085Driver

        imu = BNO085Driver()

        print("Time     | Heading | Roll   | Pitch  |  Accel (m/s²)      | Gyro (°/s)      ")
        print("-" * 90)

        start_time = time.time()
        while True:
            elapsed = time.time() - start_time

            # Read sensors
            orientation = imu.read_orientation()
            accel_x, accel_y, accel_z = imu.read_acceleration()
            gyro_x, gyro_y, gyro_z = imu.read_gyro()

            # Print formatted data
            print(f"{elapsed:7.1f}s | {orientation.heading:6.1f}° | {orientation.roll:6.1f}° | {orientation.pitch:6.1f}° | "
                  f"{accel_x:6.2f} {accel_y:6.2f} {accel_z:6.2f} | "
                  f"{gyro_x:5.0f} {gyro_y:5.0f} {gyro_z:5.0f}")

            time.sleep(1.0)

    except KeyboardInterrupt:
        print("\n\nMonitoring stopped by user")
    except Exception as e:
        print(f"\n\nError during monitoring: {e}")

def main():
    """Main test routine"""
    parser = argparse.ArgumentParser(description="OpenDuck Mini V3 Sensor Tests")
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose output"
    )
    parser.add_argument(
        "--continuous",
        action="store_true",
        help="Continuous monitoring mode (Ctrl+C to stop)"
    )
    args = parser.parse_args()

    print("=" * 60)
    print("  OpenDuck Mini V3 - Sensor Test Suite")
    print("=" * 60)
    print("\n⚠️  Ensure:")
    print("  - Robot is on stable surface")
    print("  - Battery is connected")
    print("  - Robot is stationary")
    print()

    if not args.continuous:
        input("Press ENTER to start tests...")

    # Run tests
    results = {}

    # Test 1: I2C Bus
    i2c_ok, devices = test_i2c_bus()
    results['i2c'] = i2c_ok

    # Test 2: BNO085 IMU
    if i2c_ok and (0x4A in devices or 0x4B in devices):
        results['bno085'] = test_bno085()
    else:
        print("\n⚠️  Skipping BNO085 test (not detected on I2C bus)")
        results['bno085'] = False

    # Test 3: Battery Voltage (manual check)
    if not args.continuous:
        results['battery'] = test_battery_voltage()
    else:
        print("\n⚠️  Skipping battery test in continuous mode")
        results['battery'] = False

    # Test 4: PCA9685 Servo Driver
    if i2c_ok and 0x40 in devices:
        results['pca9685'] = test_pca9685()
    else:
        print("\n⚠️  Skipping PCA9685 test (not detected on I2C bus)")
        results['pca9685'] = False

    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    passed = sum(results.values())
    total = len(results)

    for test, result in results.items():
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{test.upper():15} : {status}")

    print("=" * 60)
    print(f"Results: {passed}/{total} tests passed")

    if passed == total:
        print("✓ All tests PASSED - Hardware ready")
        exit_code = 0
    else:
        print("✗ Some tests FAILED - Check connections")
        exit_code = 1

    # Continuous monitoring mode
    if args.continuous and results.get('bno085'):
        continuous_monitoring()

    sys.exit(exit_code)

if __name__ == "__main__":
    main()
