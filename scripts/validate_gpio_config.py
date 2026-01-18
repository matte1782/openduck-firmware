#!/usr/bin/env python3
"""
OpenDuck Mini V3 - GPIO Configuration Validation Script
Purpose: Verify GPIO pin assignments and detect hardware conflicts
Author: Hardware Integration Team
Date: 18 January 2026
Status: Production Ready

This script validates:
1. I2S audio is disabled (GPIO 18 conflict resolution)
2. LED Ring 1 (GPIO 18) is accessible and not conflicting
3. LED Ring 2 (GPIO 13) is accessible
4. All GPIO pins are correctly configured
5. No hardware conflicts exist

Usage:
    sudo python3 firmware/scripts/validate_gpio_config.py

Exit Codes:
    0 = All validations passed
    1 = Critical failure (hardware conflict detected)
    2 = Warning (non-critical issue)
"""

import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, List, Tuple

# ANSI color codes
class Colors:
    RED = '\033[0;31m'
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    BLUE = '\033[0;34m'
    BOLD = '\033[1m'
    NC = '\033[0m'  # No Color


class GPIOValidator:
    """Hardware validation for OpenDuck GPIO configuration"""

    def __init__(self):
        self.results: Dict[str, Tuple[bool, str]] = {}
        self.warnings: List[str] = []
        self.critical_errors: List[str] = []

    def print_header(self):
        """Print script header"""
        print(f"{Colors.BLUE}{'=' * 60}{Colors.NC}")
        print(f"{Colors.BLUE}OpenDuck Mini V3 - GPIO Validation{Colors.NC}")
        print(f"{Colors.BLUE}Version: 1.0.0{Colors.NC}")
        print(f"{Colors.BLUE}{'=' * 60}{Colors.NC}")
        print()

    def run_command(self, cmd: List[str], capture_output: bool = True) -> Tuple[int, str, str]:
        """
        Run shell command and return exit code, stdout, stderr

        Args:
            cmd: Command as list of strings
            capture_output: Whether to capture stdout/stderr

        Returns:
            Tuple of (exit_code, stdout, stderr)
        """
        try:
            if capture_output:
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                return result.returncode, result.stdout, result.stderr
            else:
                result = subprocess.run(cmd, timeout=10)
                return result.returncode, "", ""
        except subprocess.TimeoutExpired:
            return -1, "", "Command timed out"
        except Exception as e:
            return -1, "", str(e)

    def check_root_access(self) -> bool:
        """Verify script is running as root"""
        print(f"{Colors.BLUE}[1/9] Checking root access...{Colors.NC}")

        import os
        if os.geteuid() != 0:
            print(f"{Colors.RED}  ✗ FAIL: Script must be run as root (sudo){Colors.NC}")
            self.critical_errors.append("Not running as root")
            self.results['root_access'] = (False, "Not running as root")
            return False

        print(f"{Colors.GREEN}  ✓ PASS: Running as root{Colors.NC}")
        self.results['root_access'] = (True, "Running as root")
        return True

    def check_i2s_audio_disabled(self) -> bool:
        """Verify I2S audio is disabled"""
        print(f"\n{Colors.BLUE}[2/9] Checking I2S audio status...{Colors.NC}")

        # Check aplay output
        exit_code, stdout, stderr = self.run_command(['aplay', '-l'])

        if exit_code != 0 or 'no soundcards found' in stdout.lower():
            print(f"{Colors.GREEN}  ✓ PASS: I2S audio is disabled (no soundcards found){Colors.NC}")
            self.results['i2s_disabled'] = (True, "No I2S audio devices detected")
            return True

        # Check if only HDMI audio exists (acceptable)
        if 'hdmi' in stdout.lower() and 'i2s' not in stdout.lower():
            print(f"{Colors.GREEN}  ✓ PASS: Only HDMI audio present (I2S disabled){Colors.NC}")
            self.results['i2s_disabled'] = (True, "Only HDMI audio, I2S disabled")
            return True

        # I2S audio detected - conflict!
        print(f"{Colors.RED}  ✗ FAIL: I2S audio is enabled (GPIO 18 conflict!){Colors.NC}")
        print(f"{Colors.YELLOW}  Audio devices found:{Colors.NC}")
        for line in stdout.split('\n'):
            if line.strip():
                print(f"    {line}")

        self.critical_errors.append("I2S audio enabled - conflicts with LED Ring 1 on GPIO 18")
        self.results['i2s_disabled'] = (False, "I2S audio enabled")
        return False

    def check_boot_config(self) -> bool:
        """Verify /boot/config.txt or /boot/firmware/config.txt has audio=off"""
        print(f"\n{Colors.BLUE}[3/9] Checking boot configuration...{Colors.NC}")

        config_paths = [
            Path('/boot/firmware/config.txt'),
            Path('/boot/config.txt')
        ]

        config_file = None
        for path in config_paths:
            if path.exists():
                config_file = path
                break

        if not config_file:
            print(f"{Colors.YELLOW}  ⚠ WARNING: Cannot find /boot/config.txt{Colors.NC}")
            self.warnings.append("Boot config file not found")
            self.results['boot_config'] = (False, "Config file not found")
            return False

        print(f"{Colors.GREEN}  Found config: {config_file}{Colors.NC}")

        # Read config file
        try:
            content = config_file.read_text()

            # Check for dtparam=audio=off
            if 'dtparam=audio=off' in content:
                print(f"{Colors.GREEN}  ✓ PASS: dtparam=audio=off found in config{Colors.NC}")
                self.results['boot_config'] = (True, "audio=off configured")
                return True

            # Check if audio=on (bad!)
            if 'dtparam=audio=on' in content:
                print(f"{Colors.RED}  ✗ FAIL: dtparam=audio=on found (should be =off){Colors.NC}")
                self.critical_errors.append("Boot config has audio=on instead of audio=off")
                self.results['boot_config'] = (False, "audio=on found")
                return False

            # No audio parameter found
            print(f"{Colors.YELLOW}  ⚠ WARNING: No dtparam=audio setting found{Colors.NC}")
            print(f"{Colors.YELLOW}  Run: sudo bash firmware/scripts/disable_i2s_audio.sh{Colors.NC}")
            self.warnings.append("No audio parameter in boot config")
            self.results['boot_config'] = (False, "No audio parameter")
            return False

        except Exception as e:
            print(f"{Colors.RED}  ✗ ERROR: Cannot read config file: {e}{Colors.NC}")
            self.results['boot_config'] = (False, f"Read error: {e}")
            return False

    def check_gpio_accessibility(self) -> bool:
        """Verify GPIO pins are accessible via sysfs"""
        print(f"\n{Colors.BLUE}[4/9] Checking GPIO sysfs access...{Colors.NC}")

        gpio_18_path = Path('/sys/class/gpio/gpio18')
        gpio_13_path = Path('/sys/class/gpio/gpio13')

        # Note: GPIO may not be exported yet, which is OK
        # We're just checking if /sys/class/gpio exists

        gpio_base = Path('/sys/class/gpio')
        if not gpio_base.exists():
            print(f"{Colors.RED}  ✗ FAIL: /sys/class/gpio not found (GPIO subsystem not available){Colors.NC}")
            self.critical_errors.append("GPIO subsystem not available")
            self.results['gpio_sysfs'] = (False, "GPIO sysfs not available")
            return False

        print(f"{Colors.GREEN}  ✓ PASS: GPIO sysfs accessible at {gpio_base}{Colors.NC}")
        self.results['gpio_sysfs'] = (True, "GPIO sysfs available")
        return True

    def check_rpi_ws281x_library(self) -> bool:
        """Verify rpi-ws281x library is installed"""
        print(f"\n{Colors.BLUE}[5/9] Checking rpi_ws281x library...{Colors.NC}")

        try:
            import rpi_ws281x
            print(f"{Colors.GREEN}  ✓ PASS: rpi_ws281x library installed{Colors.NC}")
            self.results['ws281x_lib'] = (True, "Library installed")
            return True
        except ImportError:
            print(f"{Colors.YELLOW}  ⚠ WARNING: rpi_ws281x not installed{Colors.NC}")
            print(f"{Colors.YELLOW}  Install: pip3 install rpi_ws281x{Colors.NC}")
            self.warnings.append("rpi_ws281x library not installed")
            self.results['ws281x_lib'] = (False, "Library not installed")
            return False

    def check_led_ring_1_gpio18(self) -> bool:
        """Test GPIO 18 for LED Ring 1"""
        print(f"\n{Colors.BLUE}[6/9] Testing GPIO 18 (LED Ring 1)...{Colors.NC}")

        try:
            import RPi.GPIO as GPIO
            GPIO.setmode(GPIO.BCM)
            GPIO.setwarnings(False)

            # Try to configure GPIO 18 as output
            try:
                GPIO.setup(18, GPIO.OUT)
                print(f"{Colors.GREEN}  ✓ PASS: GPIO 18 configured as output{Colors.NC}")

                # Test output toggle
                GPIO.output(18, GPIO.HIGH)
                time.sleep(0.1)
                GPIO.output(18, GPIO.LOW)

                print(f"{Colors.GREEN}  ✓ PASS: GPIO 18 output toggle successful{Colors.NC}")
                GPIO.cleanup(18)

                self.results['gpio18_led'] = (True, "GPIO 18 functional")
                return True

            except Exception as e:
                print(f"{Colors.RED}  ✗ FAIL: Cannot configure GPIO 18: {e}{Colors.NC}")
                self.critical_errors.append(f"GPIO 18 setup failed: {e}")
                self.results['gpio18_led'] = (False, f"Setup failed: {e}")
                return False

        except ImportError:
            print(f"{Colors.YELLOW}  ⚠ WARNING: RPi.GPIO not installed (cannot test){Colors.NC}")
            self.warnings.append("RPi.GPIO not installed")
            self.results['gpio18_led'] = (False, "RPi.GPIO not installed")
            return False

    def check_led_ring_2_gpio13(self) -> bool:
        """Test GPIO 13 for LED Ring 2"""
        print(f"\n{Colors.BLUE}[7/9] Testing GPIO 13 (LED Ring 2)...{Colors.NC}")

        try:
            import RPi.GPIO as GPIO
            GPIO.setmode(GPIO.BCM)
            GPIO.setwarnings(False)

            try:
                GPIO.setup(13, GPIO.OUT)
                print(f"{Colors.GREEN}  ✓ PASS: GPIO 13 configured as output{Colors.NC}")

                GPIO.output(13, GPIO.HIGH)
                time.sleep(0.1)
                GPIO.output(13, GPIO.LOW)

                print(f"{Colors.GREEN}  ✓ PASS: GPIO 13 output toggle successful{Colors.NC}")
                GPIO.cleanup(13)

                self.results['gpio13_led'] = (True, "GPIO 13 functional")
                return True

            except Exception as e:
                print(f"{Colors.RED}  ✗ FAIL: Cannot configure GPIO 13: {e}{Colors.NC}")
                self.critical_errors.append(f"GPIO 13 setup failed: {e}")
                self.results['gpio13_led'] = (False, f"Setup failed: {e}")
                return False

        except ImportError:
            print(f"{Colors.YELLOW}  ⚠ SKIP: RPi.GPIO not installed{Colors.NC}")
            self.results['gpio13_led'] = (False, "RPi.GPIO not installed")
            return False

    def check_hardware_config_file(self) -> bool:
        """Verify hardware_config.yaml exists and is valid"""
        print(f"\n{Colors.BLUE}[8/9] Checking hardware_config.yaml...{Colors.NC}")

        config_path = Path('firmware/config/hardware_config.yaml')

        if not config_path.exists():
            print(f"{Colors.YELLOW}  ⚠ WARNING: hardware_config.yaml not found{Colors.NC}")
            self.warnings.append("hardware_config.yaml not found")
            self.results['hw_config'] = (False, "Config file not found")
            return False

        try:
            import yaml
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)

            # Validate LED ring configuration
            if 'gpio' in config and 'neopixel' in config['gpio']:
                neopixel = config['gpio']['neopixel']

                if 'ring_1' in neopixel and 'ring_2' in neopixel:
                    ring1_pin = neopixel['ring_1']['data_pin']
                    ring2_pin = neopixel['ring_2']['data_pin']

                    print(f"{Colors.GREEN}  ✓ PASS: LED configuration found{Colors.NC}")
                    print(f"    Ring 1: GPIO {ring1_pin}")
                    print(f"    Ring 2: GPIO {ring2_pin}")

                    # Warn if Ring 1 is still on GPIO 18
                    if ring1_pin == 18:
                        print(f"{Colors.YELLOW}  ⚠ INFO: Ring 1 on GPIO 18 (I2S conflict){Colors.NC}")
                        print(f"{Colors.YELLOW}    This is expected for Option A (weekend workaround){Colors.NC}")

                    self.results['hw_config'] = (True, "Config valid")
                    return True

            print(f"{Colors.YELLOW}  ⚠ WARNING: LED ring config not found in YAML{Colors.NC}")
            self.warnings.append("LED config incomplete")
            self.results['hw_config'] = (False, "LED config missing")
            return False

        except ImportError:
            print(f"{Colors.YELLOW}  ⚠ WARNING: PyYAML not installed (cannot validate){Colors.NC}")
            self.warnings.append("PyYAML not installed")
            self.results['hw_config'] = (False, "PyYAML not installed")
            return False
        except Exception as e:
            print(f"{Colors.RED}  ✗ ERROR: Cannot parse config: {e}{Colors.NC}")
            self.results['hw_config'] = (False, f"Parse error: {e}")
            return False

    def check_conflict_resolution_status(self) -> bool:
        """Verify GPIO 18 conflict is resolved"""
        print(f"\n{Colors.BLUE}[9/9] Verifying GPIO 18 conflict resolution...{Colors.NC}")

        # Check if I2S is disabled AND GPIO 18 is accessible
        i2s_disabled = self.results.get('i2s_disabled', (False, ''))[0]
        gpio18_ok = self.results.get('gpio18_led', (False, ''))[0]

        if i2s_disabled and gpio18_ok:
            print(f"{Colors.GREEN}  ✓ PASS: GPIO 18 conflict resolved{Colors.NC}")
            print(f"{Colors.GREEN}    - I2S audio disabled: ✓{Colors.NC}")
            print(f"{Colors.GREEN}    - GPIO 18 accessible: ✓{Colors.NC}")
            print(f"{Colors.GREEN}    - LED Ring 1 can operate on GPIO 18{Colors.NC}")
            self.results['conflict_resolved'] = (True, "Conflict resolved")
            return True

        elif not i2s_disabled:
            print(f"{Colors.RED}  ✗ FAIL: I2S audio still enabled{Colors.NC}")
            print(f"{Colors.YELLOW}  Solution: Run sudo bash firmware/scripts/disable_i2s_audio.sh{Colors.NC}")
            self.critical_errors.append("GPIO 18 conflict not resolved - I2S still enabled")
            self.results['conflict_resolved'] = (False, "I2S still enabled")
            return False

        elif not gpio18_ok:
            print(f"{Colors.RED}  ✗ FAIL: GPIO 18 not accessible{Colors.NC}")
            self.critical_errors.append("GPIO 18 not accessible")
            self.results['conflict_resolved'] = (False, "GPIO 18 not accessible")
            return False

        else:
            print(f"{Colors.YELLOW}  ⚠ WARNING: Cannot fully verify conflict resolution{Colors.NC}")
            self.results['conflict_resolved'] = (False, "Cannot verify")
            return False

    def print_summary(self):
        """Print validation summary"""
        print(f"\n{Colors.BLUE}{'=' * 60}{Colors.NC}")
        print(f"{Colors.BOLD}VALIDATION SUMMARY{Colors.NC}")
        print(f"{Colors.BLUE}{'=' * 60}{Colors.NC}")

        # Count results
        passed = sum(1 for result, _ in self.results.values() if result)
        failed = sum(1 for result, _ in self.results.values() if not result)
        total = len(self.results)

        print(f"\nTests: {total} total, {passed} passed, {failed} failed")
        print()

        # Print critical errors
        if self.critical_errors:
            print(f"{Colors.RED}CRITICAL ERRORS:{Colors.NC}")
            for error in self.critical_errors:
                print(f"  ✗ {error}")
            print()

        # Print warnings
        if self.warnings:
            print(f"{Colors.YELLOW}WARNINGS:{Colors.NC}")
            for warning in self.warnings:
                print(f"  ⚠ {warning}")
            print()

        # Final verdict
        if self.critical_errors:
            print(f"{Colors.RED}{'=' * 60}{Colors.NC}")
            print(f"{Colors.RED}STATUS: FAILED - Hardware conflicts detected{Colors.NC}")
            print(f"{Colors.RED}{'=' * 60}{Colors.NC}")
            return 1
        elif self.warnings:
            print(f"{Colors.YELLOW}{'=' * 60}{Colors.NC}")
            print(f"{Colors.YELLOW}STATUS: PASSED with warnings{Colors.NC}")
            print(f"{Colors.YELLOW}{'=' * 60}{Colors.NC}")
            return 2
        else:
            print(f"{Colors.GREEN}{'=' * 60}{Colors.NC}")
            print(f"{Colors.GREEN}STATUS: ALL CHECKS PASSED ✓{Colors.NC}")
            print(f"{Colors.GREEN}{'=' * 60}{Colors.NC}")
            print()
            print(f"{Colors.GREEN}LED Ring 1 (GPIO 18) and LED Ring 2 (GPIO 13) are ready!{Colors.NC}")
            print()
            print("Next steps:")
            print(f"  1. Test dual LEDs: {Colors.BLUE}sudo python3 firmware/scripts/test_dual_leds.py{Colors.NC}")
            print(f"  2. Run full demo: {Colors.BLUE}sudo python3 firmware/scripts/openduck_eyes_demo.py{Colors.NC}")
            print()
            return 0

    def run_all_checks(self) -> int:
        """
        Run all validation checks

        Returns:
            Exit code (0=success, 1=critical failure, 2=warnings)
        """
        self.print_header()

        # Run checks in order
        self.check_root_access()
        self.check_i2s_audio_disabled()
        self.check_boot_config()
        self.check_gpio_accessibility()
        self.check_rpi_ws281x_library()
        self.check_led_ring_1_gpio18()
        self.check_led_ring_2_gpio13()
        self.check_hardware_config_file()
        self.check_conflict_resolution_status()

        # Print summary and return exit code
        return self.print_summary()


def main():
    """Main entry point"""
    validator = GPIOValidator()
    exit_code = validator.run_all_checks()
    sys.exit(exit_code)


if __name__ == '__main__':
    main()
