#!/usr/bin/env python3
"""STS3215 Hardware Validation Script — Day 49.

6-phase validation of STS3215 driver on real hardware.
Run on Raspberry Pi after deploying firmware:

    scp -r firmware/ pi@openduck.local:~/robot_jarvis/
    ssh pi@openduck.local
    cd ~/robot_jarvis/firmware
    python3 scripts/validate_sts3215.py

Prerequisites:
    - FE-URT-1 connected (/dev/ttyUSB0)
    - 2S Li-ion battery charged and connected (7.4V)
    - STS3215 servos powered and daisy-chained
    - pyserial installed: pip3 install pyserial --break-system-packages

Expected: 16 servos with IDs 2-17 on the bus.
"""

import sys
import time
import threading
import logging

# Add firmware root to path
sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parent.parent))

from src.drivers.servo.sts3215 import STS3215Config, STS3215Driver

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)

# Expected servo IDs (from CLAUDE.md hardware reference)
EXPECTED_IDS = list(range(2, 18))  # IDs 2-17, 16 servos
SCAN_RANGE = range(1, 20)  # Scan slightly wider to catch misconfigured IDs

# Test servo for movement tests (pick first expected ID)
TEST_SERVO_ID = 2
# Additional servos for multi-move test
MULTI_SERVO_IDS = [2, 3, 4]

# Position tolerance for readback verification (degrees)
POSITION_TOLERANCE = 5.0

# Voltage bounds (2S Li-ion: 6.0V dead - 8.4V full)
VOLTAGE_MIN = 6.0
VOLTAGE_MAX = 8.5

# Temperature bounds (room temp to warm)
TEMP_MIN = 10
TEMP_MAX = 70


class ValidationResult:
    def __init__(self):
        self.phases = {}
        self.total_pass = 0
        self.total_fail = 0

    def record(self, phase: str, test: str, passed: bool, detail: str = ""):
        key = f"Phase {phase}: {test}"
        status = "PASS" if passed else "FAIL"
        self.phases[key] = (passed, detail)
        if passed:
            self.total_pass += 1
        else:
            self.total_fail += 1
        icon = "✓" if passed else "✗"
        msg = f"  [{icon}] {test}"
        if detail:
            msg += f" — {detail}"
        print(msg)

    def summary(self):
        total = self.total_pass + self.total_fail
        print(f"\n{'='*60}")
        print(f"RESULTS: {self.total_pass}/{total} passed, {self.total_fail} failed")
        if self.total_fail == 0:
            print("VERDICT: ✓ ALL PASS — STS3215 driver validated on hardware")
        else:
            print("VERDICT: ✗ FAILURES DETECTED")
            for key, (passed, detail) in self.phases.items():
                if not passed:
                    print(f"  FAILED: {key} — {detail}")
        print(f"{'='*60}")
        return self.total_fail == 0


def phase_1_bus_scan(driver: STS3215Driver, results: ValidationResult):
    """Phase 1: Bus scan — discover all servos."""
    print(f"\n{'='*60}")
    print("PHASE 1: Bus Scan")
    print(f"{'='*60}")

    found = driver.scan_bus(SCAN_RANGE)
    found_set = set(found)
    expected_set = set(EXPECTED_IDS)

    results.record("1", f"Found {len(found)} servos",
                   len(found) > 0,
                   f"IDs: {found}")

    results.record("1", f"Expected IDs {EXPECTED_IDS[0]}-{EXPECTED_IDS[-1]} present",
                   expected_set.issubset(found_set),
                   f"Missing: {sorted(expected_set - found_set)}" if not expected_set.issubset(found_set) else "all present")

    unexpected = found_set - expected_set
    if unexpected:
        print(f"  [!] Unexpected IDs found: {sorted(unexpected)}")

    return found


def phase_2_telemetry(driver: STS3215Driver, servo_ids: list[int], results: ValidationResult):
    """Phase 2: Read voltage and temperature from all servos."""
    print(f"\n{'='*60}")
    print("PHASE 2: Voltage + Temperature Telemetry")
    print(f"{'='*60}")

    for sid in servo_ids:
        try:
            voltage = driver.read_voltage(sid)
            v_ok = VOLTAGE_MIN <= voltage <= VOLTAGE_MAX
            results.record("2", f"ID {sid} voltage: {voltage:.1f}V",
                          v_ok,
                          f"out of range [{VOLTAGE_MIN}-{VOLTAGE_MAX}V]" if not v_ok else "")
        except IOError as e:
            results.record("2", f"ID {sid} voltage read", False, str(e))

        try:
            temp = driver.read_temperature(sid)
            t_ok = TEMP_MIN <= temp <= TEMP_MAX
            results.record("2", f"ID {sid} temperature: {temp}°C",
                          t_ok,
                          f"out of range [{TEMP_MIN}-{TEMP_MAX}°C]" if not t_ok else "")
        except IOError as e:
            results.record("2", f"ID {sid} temperature read", False, str(e))


def phase_3_single_servo_move(driver: STS3215Driver, results: ValidationResult):
    """Phase 3: Single servo move — ID TEST_SERVO_ID: 90->180->90, readback."""
    print(f"\n{'='*60}")
    print(f"PHASE 3: Single Servo Move (ID {TEST_SERVO_ID})")
    print(f"{'='*60}")

    # Enable torque
    ok = driver.torque_enable(TEST_SERVO_ID)
    results.record("3", f"Torque enable ID {TEST_SERVO_ID}", ok)

    positions = [90.0, 180.0, 90.0]
    for target in positions:
        ok = driver.set_position(TEST_SERVO_ID, target)
        results.record("3", f"Command move to {target}°", ok)

        # Wait for servo to reach position
        time.sleep(1.5)

        try:
            actual = driver.read_position(TEST_SERVO_ID)
            diff = abs(actual - target)
            pos_ok = diff <= POSITION_TOLERANCE
            results.record("3", f"Readback: {actual:.1f}° (target {target}°, error {diff:.1f}°)",
                          pos_ok,
                          f"tolerance ±{POSITION_TOLERANCE}°" if not pos_ok else "")
        except IOError as e:
            results.record("3", f"Position readback at {target}°", False, str(e))

    # Disable torque after test
    driver.torque_disable(TEST_SERVO_ID)


def phase_4_multi_servo_move(driver: STS3215Driver, results: ValidationResult):
    """Phase 4: Multi servo — move IDs 2,3,4 simultaneously."""
    print(f"\n{'='*60}")
    print(f"PHASE 4: Multi Servo Move (IDs {MULTI_SERVO_IDS})")
    print(f"{'='*60}")

    # Enable torque on all
    for sid in MULTI_SERVO_IDS:
        driver.torque_enable(sid)

    # Move all to 135°
    target = 135.0
    for sid in MULTI_SERVO_IDS:
        ok = driver.set_position(sid, target)
        results.record("4", f"Command ID {sid} to {target}°", ok)

    time.sleep(2.0)  # Wait for all to settle

    # Readback all
    for sid in MULTI_SERVO_IDS:
        try:
            actual = driver.read_position(sid)
            diff = abs(actual - target)
            pos_ok = diff <= POSITION_TOLERANCE
            results.record("4", f"ID {sid} readback: {actual:.1f}° (error {diff:.1f}°)",
                          pos_ok)
        except IOError as e:
            results.record("4", f"ID {sid} readback", False, str(e))

    # Move all back to center (180°)
    for sid in MULTI_SERVO_IDS:
        driver.set_position(sid, 180.0)
    time.sleep(1.5)

    # Disable torque
    for sid in MULTI_SERVO_IDS:
        driver.torque_disable(sid)

    results.record("4", "Multi-servo sequence complete", True)


def phase_5_torque_disable_all(driver: STS3215Driver, servo_ids: list[int], results: ValidationResult):
    """Phase 5: torque_disable_all — broadcast, no exceptions."""
    print(f"\n{'='*60}")
    print("PHASE 5: torque_disable_all (Broadcast E-Stop)")
    print(f"{'='*60}")

    # Enable torque on a few servos first
    for sid in MULTI_SERVO_IDS:
        driver.torque_enable(sid)
    time.sleep(0.1)

    # Time the broadcast disable
    start = time.perf_counter()
    try:
        driver.torque_disable_all(servo_ids)
        elapsed_ms = (time.perf_counter() - start) * 1000
        results.record("5", f"torque_disable_all completed in {elapsed_ms:.1f}ms",
                      True)
        results.record("5", f"Latency < 10ms",
                      elapsed_ms < 10,
                      f"{elapsed_ms:.1f}ms" if elapsed_ms >= 10 else "")
    except Exception as e:
        results.record("5", "torque_disable_all raised exception", False, str(e))


def phase_6_concurrent_threads(driver: STS3215Driver, results: ValidationResult):
    """Phase 6: 3 concurrent threads pinging different IDs."""
    print(f"\n{'='*60}")
    print("PHASE 6: Concurrent Thread Access")
    print(f"{'='*60}")

    thread_results = []
    errors = []

    def thread_ping(sid, count=10):
        for _ in range(count):
            try:
                ok = driver.ping(sid)
                thread_results.append((sid, ok))
            except Exception as e:
                errors.append((sid, str(e)))

    threads = [
        threading.Thread(target=thread_ping, args=(2,)),
        threading.Thread(target=thread_ping, args=(3,)),
        threading.Thread(target=thread_ping, args=(4,)),
    ]

    start = time.perf_counter()
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)
    elapsed = time.perf_counter() - start

    total_pings = len(thread_results)
    successful = sum(1 for _, ok in thread_results if ok)
    results.record("6", f"{total_pings}/30 pings completed",
                  total_pings == 30,
                  f"in {elapsed:.1f}s")
    results.record("6", f"{successful}/{total_pings} pings successful",
                  successful == total_pings)
    results.record("6", f"Thread errors: {len(errors)}",
                  len(errors) == 0,
                  str(errors[:3]) if errors else "")


def main():
    print("="*60)
    print("STS3215 Hardware Validation — Day 49")
    print("="*60)

    config = STS3215Config(
        port="/dev/ttyUSB0",
        baudrate=1_000_000,
        timeout=0.05,
    )

    try:
        driver = STS3215Driver(config=config)
    except (RuntimeError, ValueError) as e:
        print(f"\nFATAL: Cannot initialize driver: {e}")
        print("Check: FE-URT-1 connected? Battery powered?")
        return 1

    if driver.mock_mode:
        print("\nWARNING: Running in MOCK mode — pyserial not installed!")
        print("Install: pip3 install pyserial --break-system-packages")
        return 1

    results = ValidationResult()

    try:
        # Phase 1: Bus scan
        found_ids = phase_1_bus_scan(driver, results)

        if not found_ids:
            print("\nFATAL: No servos found. Check wiring and battery power.")
            driver.deinit()
            return 1

        # Phase 2: Telemetry (use found IDs, not expected — test what's there)
        phase_2_telemetry(driver, found_ids, results)

        # Phase 3-4: Movement tests (only if test servos found)
        if TEST_SERVO_ID in found_ids:
            phase_3_single_servo_move(driver, results)
        else:
            print(f"\n  SKIP Phase 3: Servo ID {TEST_SERVO_ID} not found on bus")

        if all(sid in found_ids for sid in MULTI_SERVO_IDS):
            phase_4_multi_servo_move(driver, results)
        else:
            print(f"\n  SKIP Phase 4: Not all multi-servo IDs {MULTI_SERVO_IDS} found")

        # Phase 5: E-stop broadcast
        phase_5_torque_disable_all(driver, found_ids, results)

        # Phase 6: Concurrent threads
        phase_6_concurrent_threads(driver, results)

    finally:
        # Always disable all servos and close port
        try:
            driver.torque_disable_all(EXPECTED_IDS)
        except Exception:
            pass
        driver.deinit()

    all_pass = results.summary()
    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())
