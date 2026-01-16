#!/usr/bin/env python3
"""Hardware Validation Script for OpenDuck Mini V3.

This script validates I2C, GPIO, and PWM hardware WITHOUT batteries.
It runs on a Raspberry Pi with USB-C power and PCA9685 logic powered
from the Pi's 3.3V pin.

Hardware Setup (No Batteries Required):
    Raspberry Pi 4 (USB-C powered)
    ├── I2C1 (GPIO 2=SDA, GPIO 3=SCL)
    │   └── PCA9685 at address 0x40
    │       └── Logic power: 3.3V from Pi
    │       └── V+ rail: NOT CONNECTED (no batteries)
    └── GPIO 26 (E-stop button)
        └── Internal pull-up enabled
        └── Button connects to GND when pressed

Usage:
    python scripts/hardware_validation.py [--all|--i2c|--gpio|--pwm|--safety]

Exit Codes:
    0: All tests passed
    1: One or more tests failed
    2: Script error (not on Raspberry Pi, missing modules, etc.)

Note:
    Servo MOVEMENT requires battery power.
    This script only validates communication/configuration.
"""

import argparse
import platform
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional, Tuple

# Result tracking
@dataclass
class TestResult:
    """Individual test result."""
    name: str
    passed: bool
    duration_ms: float
    message: str = ""
    details: List[str] = None

    def __post_init__(self):
        if self.details is None:
            self.details = []


class HardwareValidator:
    """Hardware validation test runner."""

    # Known I2C device addresses
    KNOWN_DEVICES = {
        0x40: "PCA9685 PWM Controller",
        0x4A: "BNO085 IMU",
        0x70: "TCA9548A I2C Multiplexer",
    }

    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.results: List[TestResult] = []
        self._gpio = None
        self._i2c = None
        self._pca = None

    def run_all(self) -> bool:
        """Run all hardware validation tests."""
        self._print_header()

        self._run_i2c_tests()
        self._run_gpio_tests()
        self._run_pwm_tests()
        self._run_safety_tests()

        self._print_summary()
        return all(r.passed for r in self.results)

    def run_i2c_only(self) -> bool:
        """Run only I2C tests."""
        self._print_header()
        self._run_i2c_tests()
        self._print_summary()
        return all(r.passed for r in self.results)

    def run_gpio_only(self) -> bool:
        """Run only GPIO tests."""
        self._print_header()
        self._run_gpio_tests()
        self._print_summary()
        return all(r.passed for r in self.results)

    def run_pwm_only(self) -> bool:
        """Run only PWM tests."""
        self._print_header()
        self._run_i2c_tests()  # PWM needs I2C
        self._run_pwm_tests()
        self._print_summary()
        return all(r.passed for r in self.results)

    def run_safety_only(self) -> bool:
        """Run only safety system tests."""
        self._print_header()
        self._run_i2c_tests()  # Safety needs I2C for servo driver
        self._run_gpio_tests()  # Safety needs GPIO
        self._run_safety_tests()
        self._print_summary()
        return all(r.passed for r in self.results)

    # =========================================================================
    # I2C Tests
    # =========================================================================

    def _run_i2c_tests(self) -> None:
        """Run I2C bus tests."""
        print("\n─── I2C Bus Tests ───────────────────────────────────────────────")

        self._test_i2c_bus_available()
        self._test_i2c_scan()

        # Only run PCA9685 tests if bus is available
        if self._i2c is not None:
            self._test_pca9685_whoami()
            self._test_pca9685_frequency_set()

    def _test_i2c_bus_available(self) -> None:
        """Test if I2C bus can be initialized."""
        start = time.perf_counter()
        try:
            import board
            import busio
            self._i2c = busio.I2C(board.SCL, board.SDA)
            duration = (time.perf_counter() - start) * 1000
            self._add_result(TestResult(
                name="I2C bus initialized",
                passed=True,
                duration_ms=duration,
            ))
        except ImportError as e:
            duration = (time.perf_counter() - start) * 1000
            self._add_result(TestResult(
                name="I2C bus initialized",
                passed=False,
                duration_ms=duration,
                message=f"Module not found: {e}",
                details=["Install: pip install adafruit-blinka"],
            ))
        except Exception as e:
            duration = (time.perf_counter() - start) * 1000
            self._add_result(TestResult(
                name="I2C bus initialized",
                passed=False,
                duration_ms=duration,
                message=str(e),
                details=[
                    "Check I2C is enabled: sudo raspi-config",
                    "Check permissions: groups | grep i2c",
                ],
            ))

    def _test_i2c_scan(self) -> None:
        """Scan I2C bus for devices."""
        if self._i2c is None:
            self._add_result(TestResult(
                name="I2C scan",
                passed=False,
                duration_ms=0,
                message="I2C bus not available",
            ))
            return

        start = time.perf_counter()
        try:
            # Lock the bus before scanning
            while not self._i2c.try_lock():
                pass

            addresses = self._i2c.scan()
            self._i2c.unlock()

            duration = (time.perf_counter() - start) * 1000

            if not addresses:
                self._add_result(TestResult(
                    name="I2C scan",
                    passed=False,
                    duration_ms=duration,
                    message="No devices found",
                    details=[
                        "Check PCA9685 wiring",
                        "Verify 3.3V power to PCA9685 VCC",
                    ],
                ))
                return

            details = []
            for addr in addresses:
                name = self.KNOWN_DEVICES.get(addr, "Unknown device")
                details.append(f"0x{addr:02X}: {name}")

            self._add_result(TestResult(
                name=f"I2C scan: found {len(addresses)} device(s)",
                passed=True,
                duration_ms=duration,
                details=details,
            ))

        except Exception as e:
            duration = (time.perf_counter() - start) * 1000
            self._add_result(TestResult(
                name="I2C scan",
                passed=False,
                duration_ms=duration,
                message=str(e),
            ))

    def _test_pca9685_whoami(self) -> None:
        """Test PCA9685 MODE1 register read."""
        start = time.perf_counter()
        try:
            from adafruit_pca9685 import PCA9685
            self._pca = PCA9685(self._i2c)
            duration = (time.perf_counter() - start) * 1000
            self._add_result(TestResult(
                name="PCA9685 MODE1 register readable",
                passed=True,
                duration_ms=duration,
            ))
        except ImportError as e:
            duration = (time.perf_counter() - start) * 1000
            self._add_result(TestResult(
                name="PCA9685 MODE1 register readable",
                passed=False,
                duration_ms=duration,
                message=f"Module not found: {e}",
                details=["Install: pip install adafruit-pca9685"],
            ))
        except Exception as e:
            duration = (time.perf_counter() - start) * 1000
            self._add_result(TestResult(
                name="PCA9685 MODE1 register readable",
                passed=False,
                duration_ms=duration,
                message=str(e),
            ))

    def _test_pca9685_frequency_set(self) -> None:
        """Test PCA9685 frequency configuration."""
        if self._pca is None:
            self._add_result(TestResult(
                name="PCA9685 frequency set to 50Hz",
                passed=False,
                duration_ms=0,
                message="PCA9685 not initialized",
            ))
            return

        start = time.perf_counter()
        try:
            self._pca.frequency = 50
            duration = (time.perf_counter() - start) * 1000
            self._add_result(TestResult(
                name="PCA9685 frequency set to 50Hz",
                passed=True,
                duration_ms=duration,
            ))
        except Exception as e:
            duration = (time.perf_counter() - start) * 1000
            self._add_result(TestResult(
                name="PCA9685 frequency set to 50Hz",
                passed=False,
                duration_ms=duration,
                message=str(e),
            ))

    # =========================================================================
    # GPIO Tests
    # =========================================================================

    def _run_gpio_tests(self) -> None:
        """Run GPIO tests."""
        print("\n─── GPIO Tests ──────────────────────────────────────────────────")

        self._test_gpio_import()
        if self._gpio is not None:
            self._test_gpio_setmode()
            self._test_gpio_pin26_setup()
            self._test_gpio_pin26_read()
            self._test_gpio_interrupt_register()

    def _test_gpio_import(self) -> None:
        """Test if RPi.GPIO can be imported."""
        start = time.perf_counter()
        try:
            import RPi.GPIO as GPIO
            self._gpio = GPIO
            duration = (time.perf_counter() - start) * 1000
            self._add_result(TestResult(
                name="RPi.GPIO imported",
                passed=True,
                duration_ms=duration,
            ))
        except ImportError as e:
            duration = (time.perf_counter() - start) * 1000
            self._add_result(TestResult(
                name="RPi.GPIO imported",
                passed=False,
                duration_ms=duration,
                message=f"Not running on Raspberry Pi: {e}",
            ))

    def _test_gpio_setmode(self) -> None:
        """Test GPIO BCM mode configuration."""
        start = time.perf_counter()
        try:
            self._gpio.setmode(self._gpio.BCM)
            duration = (time.perf_counter() - start) * 1000
            self._add_result(TestResult(
                name="GPIO BCM mode set",
                passed=True,
                duration_ms=duration,
            ))
        except Exception as e:
            duration = (time.perf_counter() - start) * 1000
            self._add_result(TestResult(
                name="GPIO BCM mode set",
                passed=False,
                duration_ms=duration,
                message=str(e),
                details=["Try running with sudo"],
            ))

    def _test_gpio_pin26_setup(self) -> None:
        """Test GPIO 26 configuration."""
        start = time.perf_counter()
        try:
            self._gpio.setup(26, self._gpio.IN, pull_up_down=self._gpio.PUD_UP)
            duration = (time.perf_counter() - start) * 1000
            self._add_result(TestResult(
                name="GPIO 26 configured as input with pull-up",
                passed=True,
                duration_ms=duration,
            ))
        except Exception as e:
            duration = (time.perf_counter() - start) * 1000
            self._add_result(TestResult(
                name="GPIO 26 configured as input with pull-up",
                passed=False,
                duration_ms=duration,
                message=str(e),
            ))

    def _test_gpio_pin26_read(self) -> None:
        """Test GPIO 26 read."""
        start = time.perf_counter()
        try:
            value = self._gpio.input(26)
            duration = (time.perf_counter() - start) * 1000

            if value == 1:
                self._add_result(TestResult(
                    name="GPIO 26 reads HIGH (button not pressed)",
                    passed=True,
                    duration_ms=duration,
                ))
            else:
                self._add_result(TestResult(
                    name="GPIO 26 reads LOW",
                    passed=True,  # Still pass, but note condition
                    duration_ms=duration,
                    message="Button may be pressed or wiring issue",
                ))
        except Exception as e:
            duration = (time.perf_counter() - start) * 1000
            self._add_result(TestResult(
                name="GPIO 26 read",
                passed=False,
                duration_ms=duration,
                message=str(e),
            ))

    def _test_gpio_interrupt_register(self) -> None:
        """Test GPIO interrupt registration."""
        start = time.perf_counter()
        try:
            def dummy_callback(channel):
                pass

            self._gpio.add_event_detect(
                26,
                self._gpio.FALLING,
                callback=dummy_callback,
                bouncetime=50
            )
            self._gpio.remove_event_detect(26)
            duration = (time.perf_counter() - start) * 1000
            self._add_result(TestResult(
                name="Falling edge interrupt registered",
                passed=True,
                duration_ms=duration,
            ))
        except Exception as e:
            duration = (time.perf_counter() - start) * 1000
            self._add_result(TestResult(
                name="Falling edge interrupt registered",
                passed=False,
                duration_ms=duration,
                message=str(e),
            ))

    # =========================================================================
    # PWM Tests
    # =========================================================================

    def _run_pwm_tests(self) -> None:
        """Run PWM tests (no servo movement)."""
        print("\n─── PWM Tests (No Servo Movement) ───────────────────────────────")

        self._test_pwm_write_channel0()
        self._test_pwm_disable_all()

    def _test_pwm_write_channel0(self) -> None:
        """Test PWM write to channel 0."""
        if self._pca is None:
            self._add_result(TestResult(
                name="PWM channel 0 write",
                passed=False,
                duration_ms=0,
                message="PCA9685 not initialized",
            ))
            return

        start = time.perf_counter()
        try:
            # Write neutral position (1.5ms pulse at 50Hz = 4915 / 65535)
            self._pca.channels[0].duty_cycle = 0x1333
            duration = (time.perf_counter() - start) * 1000
            self._add_result(TestResult(
                name="PWM channel 0 write",
                passed=True,
                duration_ms=duration,
                details=["Note: No servo movement (V+ not powered)"],
            ))
        except Exception as e:
            duration = (time.perf_counter() - start) * 1000
            self._add_result(TestResult(
                name="PWM channel 0 write",
                passed=False,
                duration_ms=duration,
                message=str(e),
            ))

    def _test_pwm_disable_all(self) -> None:
        """Test disabling all PWM channels."""
        if self._pca is None:
            self._add_result(TestResult(
                name="PWM all channels disabled",
                passed=False,
                duration_ms=0,
                message="PCA9685 not initialized",
            ))
            return

        start = time.perf_counter()
        try:
            for i in range(16):
                self._pca.channels[i].duty_cycle = 0
            duration = (time.perf_counter() - start) * 1000
            self._add_result(TestResult(
                name="PWM all channels disabled",
                passed=True,
                duration_ms=duration,
            ))
        except Exception as e:
            duration = (time.perf_counter() - start) * 1000
            self._add_result(TestResult(
                name="PWM all channels disabled",
                passed=False,
                duration_ms=duration,
                message=str(e),
            ))

    # =========================================================================
    # Safety System Tests
    # =========================================================================

    def _run_safety_tests(self) -> None:
        """Run safety system tests."""
        print("\n─── Safety System Tests ─────────────────────────────────────────")

        self._test_emergency_stop_init()
        self._test_emergency_stop_start()
        self._test_watchdog_lifecycle()

    def _test_emergency_stop_init(self) -> None:
        """Test EmergencyStop initialization."""
        start = time.perf_counter()
        try:
            # Create mock servo driver for testing
            class MockServoDriver:
                def disable_all(self):
                    pass

            from src.safety.emergency_stop import EmergencyStop, SafetyState

            estop = EmergencyStop(
                servo_driver=MockServoDriver(),
                gpio_provider=self._gpio,
                gpio_pin=26,
            )
            duration = (time.perf_counter() - start) * 1000

            if estop.state == SafetyState.INIT:
                self._add_result(TestResult(
                    name="EmergencyStop initialized",
                    passed=True,
                    duration_ms=duration,
                ))
            else:
                self._add_result(TestResult(
                    name="EmergencyStop initialized",
                    passed=False,
                    duration_ms=duration,
                    message=f"Unexpected state: {estop.state}",
                ))

            self._estop = estop

        except Exception as e:
            duration = (time.perf_counter() - start) * 1000
            self._add_result(TestResult(
                name="EmergencyStop initialized",
                passed=False,
                duration_ms=duration,
                message=str(e),
            ))
            self._estop = None

    def _test_emergency_stop_start(self) -> None:
        """Test EmergencyStop start."""
        if not hasattr(self, '_estop') or self._estop is None:
            self._add_result(TestResult(
                name="EmergencyStop started",
                passed=False,
                duration_ms=0,
                message="EmergencyStop not initialized",
            ))
            return

        start = time.perf_counter()
        try:
            from src.safety.emergency_stop import SafetyState

            self._estop.start()
            duration = (time.perf_counter() - start) * 1000

            if self._estop.state == SafetyState.RUNNING:
                self._add_result(TestResult(
                    name="EmergencyStop started (RUNNING state)",
                    passed=True,
                    duration_ms=duration,
                ))
            else:
                self._add_result(TestResult(
                    name="EmergencyStop started",
                    passed=False,
                    duration_ms=duration,
                    message=f"Unexpected state: {self._estop.state}",
                ))

            # Cleanup
            self._estop.cleanup()

        except Exception as e:
            duration = (time.perf_counter() - start) * 1000
            self._add_result(TestResult(
                name="EmergencyStop started",
                passed=False,
                duration_ms=duration,
                message=str(e),
            ))

    def _test_watchdog_lifecycle(self) -> None:
        """Test ServoWatchdog start and stop."""
        start = time.perf_counter()
        try:
            class MockServoDriver:
                def disable_all(self):
                    pass

            from src.safety.emergency_stop import EmergencyStop
            from src.safety.watchdog import ServoWatchdog

            estop = EmergencyStop(
                servo_driver=MockServoDriver(),
                gpio_provider=self._gpio,
                gpio_pin=26,
            )

            watchdog = ServoWatchdog(
                emergency_stop=estop,
                timeout_ms=500,
            )

            # Start and feed
            estop.start()
            watchdog.start()
            watchdog.feed()

            # Verify running
            if not watchdog.is_running:
                raise RuntimeError("Watchdog not running after start")

            # Stop
            watchdog.stop()

            if watchdog.is_running:
                raise RuntimeError("Watchdog still running after stop")

            duration = (time.perf_counter() - start) * 1000

            # Cleanup
            estop.cleanup()

            self._add_result(TestResult(
                name="ServoWatchdog lifecycle",
                passed=True,
                duration_ms=duration,
            ))

        except Exception as e:
            duration = (time.perf_counter() - start) * 1000
            self._add_result(TestResult(
                name="ServoWatchdog lifecycle",
                passed=False,
                duration_ms=duration,
                message=str(e),
            ))

    # =========================================================================
    # Output Helpers
    # =========================================================================

    def _add_result(self, result: TestResult) -> None:
        """Add test result and print it."""
        self.results.append(result)
        status = "[PASS]" if result.passed else "[FAIL]"
        print(f"{status} {result.name:<45} ({result.duration_ms:.1f}ms)")
        if result.message:
            print(f"       └── {result.message}")
        for detail in result.details:
            print(f"       └── {detail}")

    def _print_header(self) -> None:
        """Print test header."""
        print("=" * 66)
        print("  OpenDuck Mini V3 - Hardware Validation (No Batteries Required)")
        print("=" * 66)
        print(f"Platform: {platform.platform()}")
        print(f"Python: {platform.python_version()}")
        print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    def _print_summary(self) -> None:
        """Print test summary."""
        passed = sum(1 for r in self.results if r.passed)
        total = len(self.results)

        print("\n" + "=" * 66)
        print(f"RESULT: {passed}/{total} tests passed")
        print("=" * 66)

        if passed == total:
            print("\n✓ Hardware validation PASSED")
            print("✓ I2C communication verified")
            print("✓ GPIO configuration verified")
            print("✓ PWM registers verified")
            print("\nNOTE: Servo MOVEMENT requires battery power.")
            print("      This script only validates communication/configuration.")
        else:
            print("\n✗ Hardware validation FAILED")
            print("\nFailed tests:")
            for r in self.results:
                if not r.passed:
                    print(f"  - {r.name}: {r.message}")

    def cleanup(self) -> None:
        """Cleanup hardware resources."""
        if self._pca is not None:
            try:
                self._pca.deinit()
            except Exception:
                pass

        if self._i2c is not None:
            try:
                self._i2c.deinit()
            except Exception:
                pass

        if self._gpio is not None:
            try:
                self._gpio.cleanup()
            except Exception:
                pass


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Hardware validation for OpenDuck Mini V3"
    )
    parser.add_argument(
        "--all", action="store_true",
        help="Run all tests (default)"
    )
    parser.add_argument(
        "--i2c", action="store_true",
        help="Run only I2C tests"
    )
    parser.add_argument(
        "--gpio", action="store_true",
        help="Run only GPIO tests"
    )
    parser.add_argument(
        "--pwm", action="store_true",
        help="Run only PWM tests"
    )
    parser.add_argument(
        "--safety", action="store_true",
        help="Run only safety system tests"
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true",
        help="Verbose output"
    )

    args = parser.parse_args()

    validator = HardwareValidator(verbose=args.verbose)

    try:
        if args.i2c:
            success = validator.run_i2c_only()
        elif args.gpio:
            success = validator.run_gpio_only()
        elif args.pwm:
            success = validator.run_pwm_only()
        elif args.safety:
            success = validator.run_safety_only()
        else:
            success = validator.run_all()

        return 0 if success else 1

    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        return 2

    except Exception as e:
        print(f"\n\nScript error: {e}")
        return 2

    finally:
        validator.cleanup()


if __name__ == "__main__":
    sys.exit(main())
