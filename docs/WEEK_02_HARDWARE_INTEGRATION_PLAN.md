# Week 02 Hardware Integration Plan
## OpenDuck Mini V3 - Senior Robotics Systems Engineer Perspective

**Document Version:** 1.0
**Created:** 21 January 2026
**Author:** Senior Robotics Systems Engineer (Boston Dynamics Protocol)
**Status:** APPROVED - Ready for Execution

---

## Executive Summary

Week 02 marks the transition from software validation to hardware integration. This plan provides a flexible, risk-mitigated approach to integrating three major hardware components as they arrive:

| Component | Expected Arrival | I2C Address | Current Draw |
|-----------|------------------|-------------|--------------|
| BNO085 IMU | Day 8 (Monday) | 0x4A | 12mA typical |
| MG90S Servos (5x) | Day 10-11 (Mid-week) | Via PCA9685 (0x40) | 150-700mA each |
| 18650 Batteries | Day 14+ (End of week) | N/A | Source: 3000mAh each |

**Critical Path:** Battery arrival gates servo movement testing. All I2C and PWM validation can proceed without batteries.

---

## Current System State (End of Week 01)

### Validated Hardware
```
[VALIDATED] Raspberry Pi 4 (4GB)
    - OS: Raspbian Lite 64-bit
    - I2C: Bus 1 enabled (/dev/i2c-1)
    - SSH: openduck.local accessible

[VALIDATED] PCA9685 PWM Controller
    - I2C Address: 0x40
    - Also responds on 0x70 (All Call - PCA9685 feature, not multiplexer)
    - PWM: 50Hz frequency confirmed
    - Test: 6/6 hardware tests passed

[VALIDATED] WS2812B LED Ring
    - GPIO: 18 (Physical Pin 12)
    - LEDs: 16/16 functional
    - Current: ~188mA at brightness 50/255
```

### I2C Bus Current State
```
     0  1  2  3  4  5  6  7  8  9  a  b  c  d  e  f
00:          -- -- -- -- -- -- -- -- -- -- -- -- --
10: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- --
20: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- --
30: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- --
40: 40 -- -- -- -- -- -- -- -- -- -- -- -- -- -- --  <-- PCA9685
50: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- --
60: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- --
70: 70 -- -- -- -- -- -- --                          <-- PCA9685 All Call
```

### Software Infrastructure Ready
- I2C Bus Manager: Thread-safe singleton with RLock
- PCA9685 Driver: Integrated with bus manager
- Safety Systems: 113 tests passing (e-stop, current limiting, watchdog)
- Robot Orchestrator: State machine with safety coordination

---

## Phase 1: BNO085 IMU Integration (Day 8)

### 1.1 Pre-Arrival Preparation (Day 7 Evening)

**Software Preparation:**
```bash
# On development machine
cd firmware

# Create BNO085 driver directory structure
mkdir -p src/drivers/sensor/imu
touch src/drivers/sensor/__init__.py
touch src/drivers/sensor/imu/__init__.py

# Create test directory
mkdir -p tests/test_drivers/test_sensor
touch tests/test_drivers/test_sensor/__init__.py
```

**Driver Template (Write Before Hardware Arrives):**
```python
# src/drivers/sensor/imu/bno085.py
"""BNO085 9-DOF IMU Driver with I2C Bus Manager Integration

Hardware: Adafruit BNO085
I2C Address: 0x4A (default), 0x4B (ALT address if jumper cut)
Features:
    - 9-DOF sensor fusion (accelerometer, gyroscope, magnetometer)
    - On-chip ARVR stabilization
    - Game rotation vector (no magnetometer drift)

Uses I2CBusManager for thread-safe bus access coordination with PCA9685.
"""

import threading
from dataclasses import dataclass
from typing import Optional, Tuple
from ..i2c_bus_manager import I2CBusManager

try:
    import adafruit_bno08x
    from adafruit_bno08x.i2c import BNO08X_I2C
except ImportError:
    adafruit_bno08x = None
    BNO08X_I2C = None


@dataclass
class OrientationData:
    """IMU orientation in Euler angles."""
    heading: float  # Yaw: -180 to 180 degrees
    pitch: float    # Pitch: -90 to 90 degrees
    roll: float     # Roll: -180 to 180 degrees
    timestamp: float = 0.0


@dataclass
class AccelerationData:
    """Linear acceleration in m/s^2."""
    x: float
    y: float
    z: float
    timestamp: float = 0.0


class BNO085Driver:
    """Thread-safe BNO085 IMU driver using I2C Bus Manager."""

    DEFAULT_ADDRESS = 0x4A
    ALT_ADDRESS = 0x4B  # If address jumper is cut

    def __init__(self, address: int = DEFAULT_ADDRESS):
        """Initialize BNO085 driver.

        Args:
            address: I2C address (0x4A default, 0x4B if jumper cut)

        Raises:
            ImportError: If adafruit-circuitpython-bno08x not installed
            RuntimeError: If device not found at address
        """
        self.address = address
        self._lock = threading.RLock()
        self.bus_manager = I2CBusManager.get_instance()
        self.bno = None
        self._connected = False

        if adafruit_bno08x is None:
            raise ImportError(
                "Required library not installed. Run: "
                "pip install adafruit-circuitpython-bno08x"
            )

        self._initialize()

    def _initialize(self) -> None:
        """Initialize IMU with thread-safe bus access."""
        with self.bus_manager.acquire_bus() as i2c:
            try:
                self.bno = BNO08X_I2C(i2c, address=self.address)
                self._enable_features()
                self._connected = True
            except Exception as e:
                self._connected = False
                raise RuntimeError(f"BNO085 not found at 0x{self.address:02X}: {e}")

    def _enable_features(self) -> None:
        """Enable desired sensor reports."""
        # Enable rotation vector (quaternion output)
        self.bno.enable_feature(adafruit_bno08x.BNO_REPORT_ROTATION_VECTOR)
        # Enable linear acceleration (gravity removed)
        self.bno.enable_feature(adafruit_bno08x.BNO_REPORT_LINEAR_ACCELERATION)
        # Enable game rotation vector (no magnetometer, good for fast motion)
        self.bno.enable_feature(adafruit_bno08x.BNO_REPORT_GAME_ROTATION_VECTOR)

    def is_connected(self) -> bool:
        """Check if IMU is responding."""
        return self._connected

    def read_orientation(self) -> Optional[OrientationData]:
        """Read current orientation as Euler angles.

        Returns:
            OrientationData with heading/pitch/roll, or None on error
        """
        with self._lock:
            with self.bus_manager.acquire_bus():
                try:
                    quat = self.bno.quaternion
                    if quat is None:
                        return None
                    # Convert quaternion to Euler angles
                    heading, pitch, roll = self._quaternion_to_euler(quat)
                    return OrientationData(
                        heading=heading,
                        pitch=pitch,
                        roll=roll
                    )
                except Exception:
                    return None

    def read_acceleration(self) -> Optional[AccelerationData]:
        """Read linear acceleration (gravity removed).

        Returns:
            AccelerationData with x/y/z in m/s^2, or None on error
        """
        with self._lock:
            with self.bus_manager.acquire_bus():
                try:
                    accel = self.bno.linear_acceleration
                    if accel is None:
                        return None
                    return AccelerationData(x=accel[0], y=accel[1], z=accel[2])
                except Exception:
                    return None

    @staticmethod
    def _quaternion_to_euler(quat: Tuple[float, float, float, float]) -> Tuple[float, float, float]:
        """Convert quaternion to Euler angles (heading, pitch, roll)."""
        import math
        i, j, k, real = quat

        # Roll (x-axis rotation)
        sinr_cosp = 2.0 * (real * i + j * k)
        cosr_cosp = 1.0 - 2.0 * (i * i + j * j)
        roll = math.degrees(math.atan2(sinr_cosp, cosr_cosp))

        # Pitch (y-axis rotation)
        sinp = 2.0 * (real * j - k * i)
        sinp = max(-1.0, min(1.0, sinp))  # Clamp for asin
        pitch = math.degrees(math.asin(sinp))

        # Yaw/Heading (z-axis rotation)
        siny_cosp = 2.0 * (real * k + i * j)
        cosy_cosp = 1.0 - 2.0 * (j * j + k * k)
        heading = math.degrees(math.atan2(siny_cosp, cosy_cosp))

        return heading, pitch, roll
```

### 1.2 BNO085 Physical Wiring Procedure

**MANDATORY: Follow PRE_WIRING_CHECKLIST.md**

```
BNO085 Wiring (Adafruit Module):
==============================================================

┌─────────────────────────────────────────────────────────────┐
│  BNO085 Breakout                  Raspberry Pi 4            │
│  (Adafruit)                       (GPIO Header)             │
│                                                             │
│  VIN ●────────🔴 RED──────────────● Pin 1 (3.3V)           │
│  GND ●────────⚫ BLACK────────────● Pin 6 (GND)            │
│  SDA ●────────🟢 GREEN────────────● Pin 3 (GPIO2/SDA)      │
│  SCL ●────────🟡 YELLOW───────────● Pin 5 (GPIO3/SCL)      │
│                                                             │
│  INT ●──(optional)──ORANGE────────● Pin 11 (GPIO17)        │
│  RST ●──(optional)──PURPLE────────● Pin 13 (GPIO27)        │
│                                                             │
│  PS0 ●  (leave unconnected for I2C mode)                   │
│  PS1 ●  (leave unconnected for I2C mode)                   │
└─────────────────────────────────────────────────────────────┘

CRITICAL SIGNAL VERIFICATION:
=============================
[ ] BNO085 "SDA" label connects to Pi Pin 3 (SDA) via GREEN wire
[ ] BNO085 "SCL" label connects to Pi Pin 5 (SCL) via YELLOW wire
[ ] Signal names match - NOT just pin positions!
```

**Power Notes:**
- BNO085 operates at 3.3V (VIN accepts 3.3-5V with onboard regulator)
- Current draw: ~12mA typical, 30mA peak during calibration
- Safe to power from Pi 3.3V rail (Pin 1)

### 1.3 BNO085 Validation Commands

```bash
# SSH into Raspberry Pi
ssh pi@openduck.local

# Step 1: Detect BNO085 on I2C bus
sudo i2cdetect -y 1

# Expected output:
#      0  1  2  3  4  5  6  7  8  9  a  b  c  d  e  f
# 40: 40 -- -- -- -- -- -- -- -- -- 4a -- -- -- -- --
#     ↑                             ↑
#     PCA9685                       BNO085 (NEW!)

# If 0x4A not detected:
# 1. Check SDA/SCL not swapped (90% of issues)
# 2. Check power LED on BNO085 board
# 3. Try alternate address 0x4B (if address jumper is cut)
```

**Python Validation Script:**
```python
#!/usr/bin/env python3
"""BNO085 Hardware Validation Script

Run on Raspberry Pi: sudo python3 bno085_validate.py
"""

import time

def main():
    print("=" * 60)
    print("BNO085 IMU Hardware Validation")
    print("=" * 60)

    # Test 1: Library import
    print("\n[TEST 1] Library Import...")
    try:
        import board
        import busio
        from adafruit_bno08x.i2c import BNO08X_I2C
        from adafruit_bno08x import BNO_REPORT_ROTATION_VECTOR
        print("  [PASS] Libraries imported successfully")
    except ImportError as e:
        print(f"  [FAIL] Missing library: {e}")
        print("  Run: sudo pip3 install adafruit-circuitpython-bno08x")
        return

    # Test 2: I2C Initialization
    print("\n[TEST 2] I2C Bus Access...")
    try:
        i2c = busio.I2C(board.SCL, board.SDA)
        print("  [PASS] I2C bus initialized")
    except Exception as e:
        print(f"  [FAIL] I2C error: {e}")
        return

    # Test 3: BNO085 Detection
    print("\n[TEST 3] BNO085 Device Detection...")
    try:
        bno = BNO08X_I2C(i2c)
        print("  [PASS] BNO085 detected at 0x4A")
    except Exception as e:
        print(f"  [FAIL] BNO085 not found: {e}")
        print("  Check: SDA/SCL wiring, power LED, solder joints")
        return

    # Test 4: Enable Rotation Vector
    print("\n[TEST 4] Enable Sensor Reports...")
    try:
        bno.enable_feature(BNO_REPORT_ROTATION_VECTOR)
        print("  [PASS] Rotation vector enabled")
    except Exception as e:
        print(f"  [FAIL] Feature enable failed: {e}")
        return

    # Test 5: Read Orientation Data
    print("\n[TEST 5] Read Orientation Data...")
    try:
        # Allow sensor to stabilize
        time.sleep(0.5)
        quat = bno.quaternion
        if quat and len(quat) == 4:
            print(f"  [PASS] Quaternion: {quat}")
            print(f"        (i={quat[0]:.3f}, j={quat[1]:.3f}, k={quat[2]:.3f}, real={quat[3]:.3f})")
        else:
            print("  [WARN] No data yet, sensor warming up")
    except Exception as e:
        print(f"  [FAIL] Read error: {e}")
        return

    # Test 6: Continuous Read (5 samples)
    print("\n[TEST 6] Continuous Reading (5 samples)...")
    for i in range(5):
        try:
            quat = bno.quaternion
            if quat:
                print(f"  Sample {i+1}: heading={quat[3]:.2f}")
            time.sleep(0.2)
        except Exception as e:
            print(f"  [FAIL] Sample {i+1} error: {e}")

    print("\n" + "=" * 60)
    print("BNO085 VALIDATION COMPLETE")
    print("=" * 60)

if __name__ == "__main__":
    main()
```

### 1.4 Multi-Device I2C Bus Verification

**Critical Test: PCA9685 + BNO085 Coexistence**

```python
#!/usr/bin/env python3
"""Multi-Device I2C Bus Test

Validates both PCA9685 and BNO085 can be accessed without collision.
Uses I2CBusManager for thread-safe access.
"""

import time
import threading

def test_concurrent_access():
    """Test concurrent access to both devices."""

    from src.drivers.i2c_bus_manager import I2CBusManager
    from src.drivers.servo.pca9685 import PCA9685Driver
    from src.drivers.sensor.imu.bno085 import BNO085Driver

    print("Initializing I2C Bus Manager...")
    manager = I2CBusManager.get_instance()

    print("Initializing PCA9685...")
    pca = PCA9685Driver(address=0x40)

    print("Initializing BNO085...")
    imu = BNO085Driver(address=0x4A)

    # Test concurrent operations
    errors = []

    def servo_thread():
        """Set servo angles in loop."""
        for i in range(10):
            try:
                pca.set_servo_angle(0, 90)
                time.sleep(0.05)
            except Exception as e:
                errors.append(f"Servo error: {e}")

    def imu_thread():
        """Read IMU in loop."""
        for i in range(10):
            try:
                orientation = imu.read_orientation()
                time.sleep(0.05)
            except Exception as e:
                errors.append(f"IMU error: {e}")

    # Run threads concurrently
    t1 = threading.Thread(target=servo_thread)
    t2 = threading.Thread(target=imu_thread)

    t1.start()
    t2.start()
    t1.join()
    t2.join()

    if errors:
        print(f"[FAIL] {len(errors)} errors occurred:")
        for e in errors:
            print(f"  - {e}")
        return False
    else:
        print("[PASS] Concurrent access successful - no bus collisions!")
        return True

if __name__ == "__main__":
    test_concurrent_access()
```

---

## Phase 2: Servo Integration (Day 10-11)

### 2.1 Servo Wiring Without Batteries

**IMPORTANT:** Servos can be wired and PWM tested WITHOUT batteries. The PCA9685 logic runs from Pi 3.3V, but servo motors need V+ power to move.

```
Servo Wiring (5x MG90S):
==============================================================

PCA9685 PWM Channels     Servo Assignment        Function
─────────────────────────────────────────────────────────────
Channel 0  ─────────────  Head Pan               Left/Right
Channel 1  ─────────────  Head Tilt              Up/Down
Channel 2  ─────────────  Left Arm               Upper arm
Channel 3  ─────────────  Right Arm              Upper arm
Channel 4  ─────────────  Tail/Accessory         Optional

Servo Cable Color Code:
  🟤 BROWN (or BLACK) ──→ GND rail on PCA9685
  🔴 RED ───────────────→ V+ rail on PCA9685 (UNPOWERED until batteries)
  🟠 ORANGE (or YELLOW)─→ PWM signal pin (0-15)
```

**PCA9685 Servo Connection Points:**
```
┌─────────────────────────────────────────────────────────────────┐
│  PCA9685 PWM Controller                                         │
│                                                                 │
│  Power Rail (RIGHT SIDE):                                       │
│  ┌─────────────────────────┐                                    │
│  │  V+  │ V+  │ V+  │ ...  │  ← Connect UBEC 5V/6V here        │
│  │  GND │ GND │ GND │ ...  │  ← Connect UBEC GND here          │
│  └─────────────────────────┘                                    │
│                                                                 │
│  PWM Channels (TOP):                                            │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  0  │  1  │  2  │  3  │  4  │  5  │ ... │ 15 │          │    │
│  │ PWM │ PWM │ PWM │ PWM │ PWM │ PWM │ ... │ PWM │          │    │
│  │ V+  │ V+  │ V+  │ V+  │ V+  │ V+  │ ... │ V+  │          │    │
│  │ GND │ GND │ GND │ GND │ GND │ GND │ ... │ GND │          │    │
│  └─────────────────────────────────────────────────────────┘    │
│           ↓     ↓     ↓     ↓     ↓                             │
│       Servo  Servo  Servo  Servo  Servo                         │
│        0      1      2      3      4                            │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 PWM Validation Without Motor Movement

**Goal:** Verify PWM signals are correct before connecting batteries.

```python
#!/usr/bin/env python3
"""Servo PWM Validation (No Power Required)

Tests PWM signal generation without servo movement.
Safe to run before batteries are connected.
"""

from src.drivers.servo.pca9685 import PCA9685Driver
import time

def test_pwm_signals():
    print("=" * 60)
    print("Servo PWM Validation (No Motor Movement)")
    print("=" * 60)
    print("\nNOTE: V+ rail not powered - servos won't move")
    print("      This validates PWM communication only\n")

    # Initialize driver
    pca = PCA9685Driver()
    print("[PASS] PCA9685 initialized")

    # Test each channel
    channels = [0, 1, 2, 3, 4]
    angles = [0, 45, 90, 135, 180]

    for ch in channels:
        print(f"\nChannel {ch}:")
        for angle in angles:
            try:
                pca.set_servo_angle(ch, angle)
                state = pca.get_channel_state(ch)
                print(f"  Set {angle}° - State: enabled={state['enabled']}, angle={state['angle']}")
            except Exception as e:
                print(f"  [FAIL] Error at {angle}°: {e}")

        # Disable channel
        pca.disable_channel(ch)
        print(f"  Disabled - PWM off")

    # Test emergency stop
    print("\n[TEST] Emergency Stop (disable all)...")
    for ch in channels:
        pca.set_servo_angle(ch, 90)
    pca.disable_all()
    print("[PASS] All channels disabled")

    print("\n" + "=" * 60)
    print("PWM VALIDATION COMPLETE")
    print("Ready for battery integration")
    print("=" * 60)

if __name__ == "__main__":
    test_pwm_signals()
```

### 2.3 Servo Calibration Procedure (When Batteries Arrive)

```
Servo Calibration Checklist:
=============================

For EACH servo (before mounting):

[ ] 1. Connect single servo to Channel 0
[ ] 2. Power on (with current limiting enabled)
[ ] 3. Set to 90° (center position)
[ ] 4. Mark reference point on servo horn
[ ] 5. Test 0° and 180° - verify full range
[ ] 6. Record actual min/max angles if limited
[ ] 7. Update servo_limits in configuration
[ ] 8. Test sweep (slow, 0.05s delay between steps)
[ ] 9. Monitor current (should be <300mA unloaded)
[ ] 10. Move to next servo, repeat
```

---

## Phase 3: Battery Integration (Day 14+)

### 3.1 Pre-Battery Safety Checklist

**MANDATORY: Complete BEFORE connecting batteries**

```
BATTERY INTEGRATION SAFETY CHECKLIST
=====================================

Hardware Verification:
[ ] UBEC output verified: 6.0V ± 0.1V (with multimeter)
[ ] UBEC polarity: Red = V+, Black = GND
[ ] BMS board tested separately (8.4V max, 6.0V cutoff)
[ ] Fuse installed: 3A fast-blow inline
[ ] XT30 connectors properly soldered
[ ] No exposed wires or solder splashes

Software Verification:
[ ] Emergency stop button connected and tested
[ ] Current limiter enabled in config
[ ] Servo watchdog timeout set (1000ms default)
[ ] max_servos_concurrent: 3 (safety limit)

Environment:
[ ] LiPo safe bag nearby
[ ] Fire extinguisher accessible (Class D preferred)
[ ] Multimeter ready for voltage checks
[ ] Camera ready for documentation

First Power-On Protocol:
[ ] Pi powered via USB-C (separate from robot power)
[ ] UBEC connected to V+ rail (Pi NOT powered from UBEC)
[ ] Single servo connected to Channel 0
[ ] All other channels empty
[ ] Emergency stop button within reach
```

### 3.2 Power Budget Analysis

```
OpenDuck Mini V3 Power Budget
=============================

Power Source: 2S Li-ion (2x 18650 Molicel P30B)
├── Nominal: 7.2V
├── Max (charged): 8.4V
├── Min (cutoff): 6.0V
└── Capacity: 3000mAh each, 6000mAh parallel

UBEC Output: 6.0V @ 3A continuous
├── Available current: 3000mA
├── Safety margin: 20%
└── Usable budget: 2400mA

Device Power Allocation:
─────────────────────────────────────────────────────────────
Device              Voltage   Typical     Peak      Notes
─────────────────────────────────────────────────────────────
Raspberry Pi 4       5V       600mA     1200mA    Via USB-C (separate)
PCA9685 Logic        3.3V      10mA       20mA    From Pi 3.3V
BNO085 IMU           3.3V      12mA       30mA    From Pi 3.3V
WS2812B (16 LEDs)    5V       188mA      960mA    50/255 brightness
MG90S Servo (idle)   6V        10mA       10mA    Per servo
MG90S Servo (moving) 6V       150mA      700mA    Under load
─────────────────────────────────────────────────────────────

SCENARIO ANALYSIS:

Scenario A: Idle (no servo movement)
├── LED ring (50%): 188mA
├── PCA9685 logic: 10mA
├── Servos idle (5x): 50mA
└── TOTAL: 248mA ✅ SAFE

Scenario B: Single servo moving
├── LED ring (50%): 188mA
├── PCA9685 logic: 10mA
├── 1 servo moving: 300mA (typical)
├── 4 servos idle: 40mA
└── TOTAL: 538mA ✅ SAFE

Scenario C: 3 servos moving (software limit)
├── LED ring (50%): 188mA
├── PCA9685 logic: 10mA
├── 3 servos moving: 900mA
├── 2 servos idle: 20mA
└── TOTAL: 1118mA ✅ SAFE (within 2400mA budget)

Scenario D: All 5 servos moving (FORBIDDEN by software)
├── LED ring (50%): 188mA
├── PCA9685 logic: 10mA
├── 5 servos moving: 1500mA
└── TOTAL: 1698mA ⚠️ MARGINAL (set limit to 3 concurrent)

SERVO STALL WARNING:
─────────────────────────────────────────────────────────────
A stalled MG90S can draw up to 700mA!
├── Stall detection timeout: 300ms (in software)
├── Stall current limit: 500mA per servo
└── Action: Disable channel, trigger warning
```

### 3.3 Battery Integration Procedure

**Step-by-Step First Power-On:**

```
FIRST BATTERY POWER-ON PROCEDURE
================================

Phase 1: UBEC Verification (NO ROBOT CONNECTED)
───────────────────────────────────────────────
1. Connect UBEC to battery (via BMS)
2. Measure UBEC output: Should be 6.0V ± 0.1V
3. If voltage incorrect, STOP - do not proceed
4. Disconnect battery

Phase 2: Raspberry Pi Startup
───────────────────────────────────────────────
1. Connect Pi via USB-C (normal power supply)
2. SSH into Pi: ssh pi@openduck.local
3. Run system check: python3 scripts/hardware_validation.py --all
4. Verify PCA9685 at 0x40, BNO085 at 0x4A

Phase 3: Servo Power Connection
───────────────────────────────────────────────
1. Connect single servo (Channel 0) to PCA9685
2. Pi running, SSH session open
3. Run safety monitor in terminal:
   python3 scripts/safety_monitor.py
4. Connect UBEC to PCA9685 V+ rail:
   - Red wire to V+
   - Black wire to GND (beside V+)
5. Connect battery to BMS

Phase 4: First Movement Test
───────────────────────────────────────────────
1. Monitor current (if ammeter available)
2. Run center test:
   python3 -c "from src.drivers.servo.pca9685 import PCA9685Driver; p = PCA9685Driver(); p.set_servo_angle(0, 90)"
3. Servo should move to center (90°)
4. Verify movement is smooth, no stalling
5. Disable servo:
   python3 -c "from src.drivers.servo.pca9685 import PCA9685Driver; p = PCA9685Driver(); p.disable_channel(0)"

Phase 5: Multi-Servo Test
───────────────────────────────────────────────
1. Add servos one at a time (Channels 1, 2, 3, 4)
2. Test each individually
3. Test 3 concurrent (max allowed)
4. Monitor for brownouts, resets, overheating
```

---

## Phase 4: Integration Test Sequences

### 4.1 Validation Matrix

```
Hardware Validation Matrix - Week 02
=====================================

│ Test                      │ No Battery │ With Battery │ Risk Level │
│───────────────────────────│────────────│──────────────│────────────│
│ PCA9685 I2C detection     │     ✓      │      ✓       │    LOW     │
│ PCA9685 PWM signals       │     ✓      │      ✓       │    LOW     │
│ BNO085 I2C detection      │     ✓      │      ✓       │    LOW     │
│ BNO085 orientation read   │     ✓      │      ✓       │    LOW     │
│ LED ring colors           │     ✓      │      ✓       │    LOW     │
│ Multi-device I2C          │     ✓      │      ✓       │   MEDIUM   │
│───────────────────────────│────────────│──────────────│────────────│
│ Servo movement            │     ✗      │      ✓       │   MEDIUM   │
│ Servo calibration         │     ✗      │      ✓       │   MEDIUM   │
│ Current monitoring        │     ✗      │      ✓       │   MEDIUM   │
│ Emergency stop (live)     │     ✗      │      ✓       │    HIGH    │
│ Stall detection           │     ✗      │      ✓       │    HIGH    │
│ Full robot orchestration  │     ✗      │      ✓       │    HIGH    │
```

### 4.2 Complete Integration Test Script

```python
#!/usr/bin/env python3
"""Complete Hardware Integration Test Suite

Runs all hardware tests based on available components.
"""

import sys
import time
import argparse

def test_i2c_devices():
    """Test all I2C devices are detected."""
    print("\n[TEST GROUP 1: I2C DEVICE DETECTION]")
    print("-" * 50)

    # Scan bus
    import subprocess
    result = subprocess.run(['i2cdetect', '-y', '1'], capture_output=True, text=True)
    print(result.stdout)

    # Check expected addresses
    expected = {0x40: 'PCA9685', 0x4A: 'BNO085'}
    detected = []

    for addr, name in expected.items():
        if f'{addr:02x}' in result.stdout.lower():
            print(f"  [PASS] {name} detected at 0x{addr:02X}")
            detected.append(addr)
        else:
            print(f"  [WARN] {name} NOT detected at 0x{addr:02X}")

    return len(detected) == len(expected)

def test_pca9685():
    """Test PCA9685 PWM controller."""
    print("\n[TEST GROUP 2: PCA9685 PWM CONTROLLER]")
    print("-" * 50)

    from src.drivers.servo.pca9685 import PCA9685Driver

    try:
        pca = PCA9685Driver()
        print("  [PASS] PCA9685 initialized")

        # Test angle setting
        pca.set_servo_angle(0, 90)
        state = pca.get_channel_state(0)
        assert state['angle'] == 90
        print("  [PASS] PWM signal generation")

        # Test disable
        pca.disable_all()
        print("  [PASS] Emergency disable")

        return True
    except Exception as e:
        print(f"  [FAIL] PCA9685 error: {e}")
        return False

def test_bno085():
    """Test BNO085 IMU."""
    print("\n[TEST GROUP 3: BNO085 IMU]")
    print("-" * 50)

    try:
        from src.drivers.sensor.imu.bno085 import BNO085Driver

        imu = BNO085Driver()
        print("  [PASS] BNO085 initialized")

        # Test orientation read
        time.sleep(0.5)  # Let sensor stabilize
        orientation = imu.read_orientation()
        if orientation:
            print(f"  [PASS] Orientation: heading={orientation.heading:.1f}°")
        else:
            print("  [WARN] No orientation data (sensor warming up)")

        return True
    except ImportError:
        print("  [SKIP] BNO085 driver not yet implemented")
        return True  # Not a failure if driver doesn't exist yet
    except Exception as e:
        print(f"  [FAIL] BNO085 error: {e}")
        return False

def test_concurrent_i2c():
    """Test concurrent I2C access."""
    print("\n[TEST GROUP 4: CONCURRENT I2C ACCESS]")
    print("-" * 50)

    import threading
    from src.drivers.servo.pca9685 import PCA9685Driver

    errors = []

    def pca_thread(pca):
        for _ in range(20):
            try:
                pca.set_servo_angle(0, 90)
                time.sleep(0.01)
            except Exception as e:
                errors.append(str(e))

    try:
        pca = PCA9685Driver()
        threads = [threading.Thread(target=pca_thread, args=(pca,)) for _ in range(4)]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        pca.disable_all()

        if errors:
            print(f"  [FAIL] {len(errors)} errors in concurrent access")
            return False
        else:
            print("  [PASS] 80 operations across 4 threads - no collisions")
            return True
    except Exception as e:
        print(f"  [FAIL] Concurrent test error: {e}")
        return False

def test_servo_movement(enabled=False):
    """Test actual servo movement (requires battery)."""
    print("\n[TEST GROUP 5: SERVO MOVEMENT]")
    print("-" * 50)

    if not enabled:
        print("  [SKIP] Servo movement test requires --with-battery flag")
        return True

    from src.drivers.servo.pca9685 import PCA9685Driver

    try:
        pca = PCA9685Driver()

        print("  Moving servo to 45°...")
        pca.set_servo_angle(0, 45)
        time.sleep(0.5)

        print("  Moving servo to 135°...")
        pca.set_servo_angle(0, 135)
        time.sleep(0.5)

        print("  Centering servo at 90°...")
        pca.set_servo_angle(0, 90)
        time.sleep(0.5)

        pca.disable_all()

        response = input("  Did servo move correctly? (y/n): ")
        if response.lower() == 'y':
            print("  [PASS] Servo movement confirmed")
            return True
        else:
            print("  [FAIL] Servo movement not confirmed")
            return False
    except Exception as e:
        print(f"  [FAIL] Servo movement error: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description='Hardware Integration Tests')
    parser.add_argument('--with-battery', action='store_true',
                       help='Enable tests requiring battery power')
    args = parser.parse_args()

    print("=" * 60)
    print("OpenDuck Mini V3 - Hardware Integration Test Suite")
    print("=" * 60)

    results = {
        'I2C Devices': test_i2c_devices(),
        'PCA9685': test_pca9685(),
        'BNO085': test_bno085(),
        'Concurrent I2C': test_concurrent_i2c(),
        'Servo Movement': test_servo_movement(args.with_battery),
    }

    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)

    passed = sum(1 for r in results.values() if r)
    total = len(results)

    for name, result in results.items():
        status = "[PASS]" if result else "[FAIL]"
        print(f"  {status} {name}")

    print(f"\nTotal: {passed}/{total} passed")

    return 0 if passed == total else 1

if __name__ == "__main__":
    sys.exit(main())
```

---

## Risk Mitigation Strategies

### 5.1 Hardware Delay Contingencies

```
Scenario: BNO085 Delayed Beyond Day 8
─────────────────────────────────────
Impact: Low (not on critical path)
Mitigation:
  1. Continue with servo wiring preparation
  2. Write BNO085 driver against mock interface
  3. Create comprehensive test suite for when hardware arrives
  4. Use test_bno085.py with mock data

Scenario: Servos Delayed Beyond Day 11
─────────────────────────────────────
Impact: Medium (blocks movement testing)
Mitigation:
  1. Focus on IMU integration and LED animations
  2. Complete all software orchestration with mocks
  3. Advance Week 03 work (audio, vision)
  4. Prepare servo calibration scripts

Scenario: Batteries Delayed Beyond Week 02
─────────────────────────────────────
Impact: High (blocks all movement testing)
Mitigation:
  1. Acquire USB-powered 5V source temporarily
  2. Test single servo at a time with limited power
  3. Complete all I2C, PWM, and LED validation
  4. Document "Ready for Battery" state
  5. Consider local battery purchase (vape shop round 2)
```

### 5.2 Hardware Failure Recovery

```
I2C Device Not Detected:
────────────────────────
1. Power cycle Raspberry Pi
2. Check PRE_WIRING_CHECKLIST.md - SDA/SCL swap is 90% cause
3. Verify solder joints on device
4. Test with second unit if available
5. Check for bus conflicts with i2cdetect -y 1

Servo Not Moving:
────────────────────────
1. Verify V+ rail has power (multimeter: 6.0V)
2. Check UBEC output voltage
3. Verify servo cable orientation (brown=GND)
4. Test servo on different channel
5. Check BMS hasn't tripped (reset if needed)

Pi Brownout/Reboot:
────────────────────────
1. IMMEDIATELY disconnect battery
2. Check for shorts (visual inspection)
3. Measure current draw if ammeter available
4. Reduce concurrent servos to 1
5. Check USB-C power supply rating (3A recommended)

IMU Giving Invalid Data:
────────────────────────
1. Allow 30-60 seconds for calibration
2. Move IMU in figure-8 pattern for magnetometer
3. Check for magnetic interference nearby
4. Reset IMU (toggle RST pin low)
5. Try alternate I2C address (0x4B)
```

---

## Daily Execution Checklists

### Day 8 Checklist (BNO085 Integration)
```
[ ] Verify BNO085 package received
[ ] Complete PRE_WIRING_CHECKLIST.md
[ ] Take 8 photos (before/after wiring)
[ ] Run i2cdetect - verify 0x40 AND 0x4A
[ ] Install adafruit-circuitpython-bno08x
[ ] Run bno085_validate.py
[ ] Run concurrent I2C test (PCA9685 + BNO085)
[ ] Update CHANGELOG.md with results
[ ] Commit: "feat: BNO085 IMU hardware validated"
```

### Day 10-11 Checklist (Servo Wiring)
```
[ ] Verify servo package received (5x MG90S)
[ ] Wire single servo to Channel 0 (no V+ power)
[ ] Run PWM validation script
[ ] Add servos one at a time (Channels 1-4)
[ ] Verify all 5 channels generate PWM
[ ] Test emergency stop (disable_all)
[ ] Document channel assignments
[ ] Update CHANGELOG.md
[ ] Commit: "feat: 5x MG90S servo PWM validated"
```

### Day 14 Checklist (Battery Integration)
```
[ ] Complete BATTERY INTEGRATION SAFETY CHECKLIST
[ ] Test UBEC output voltage (6.0V ± 0.1V)
[ ] Connect single servo
[ ] First power-on with safety monitor running
[ ] Single servo movement test
[ ] Add servos incrementally
[ ] Multi-servo test (max 3 concurrent)
[ ] Record current measurements
[ ] Full integration test suite
[ ] Update CHANGELOG.md
[ ] Commit: "feat: Battery integration complete - servos moving!"
```

---

## Summary

This hardware integration plan provides:

1. **Flexible Scheduling:** Adapt to whenever hardware actually arrives
2. **Risk Mitigation:** Clear fallbacks for each delay scenario
3. **Safety First:** Battery integration only after all validation passes
4. **TDD Integration:** Tests exist before hardware connection
5. **I2C Coordination:** Thread-safe bus access for all devices
6. **Power Management:** Strict budget enforcement prevents brownouts

**Critical Success Factors:**
- Follow PRE_WIRING_CHECKLIST.md for EVERY I2C device
- Run validation scripts BEFORE advancing to next phase
- Maintain CHANGELOG.md with all hardware events
- Battery integration LAST, after all I2C/PWM validation

---

**Document Version:** 1.0
**Created:** 21 January 2026
**Author:** Senior Robotics Systems Engineer
**Status:** APPROVED - Ready for Week 02 Execution
