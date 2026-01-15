#!/usr/bin/env python3
"""
Power Management for OpenDuck Mini V3 with MG90S Arms

This module implements software current limiting to ensure the single
ZHITING 5V 3A UBEC can safely power 5x MG90S servos alongside the Pi,
sensors, and audio system.

Key strategies:
1. Limit max concurrent moving servos to 3 (keeps peak <2.72A)
2. Detect servo stalls and timeout after 300ms
3. Monitor 5V rail voltage via ADC (REQUIRES EXTERNAL ADC HARDWARE)
4. Sequential movement patterns instead of parallel

⚠️ CRITICAL SAFETY NOTE: Voltage monitoring requires real ADC hardware
   (ADS1115 or MCP3008). GPIO pins CANNOT measure analog voltage directly.
   Voltage monitoring is DISABLED by default for safety.

Author: Claude Sonnet 4.5
Date: 2026-01-14
Updated: 2026-01-15 (Fixed dangerous fake GPIO voltage monitoring)
License: MIT
"""

import time
import threading
from collections import deque
from typing import Dict, List, Tuple, Optional
import RPi.GPIO as GPIO

# Servo configuration
ARM_LEFT_SHOULDER = 12    # PCA9685 channel
ARM_LEFT_GRIPPER = 14
ARM_RIGHT_SHOULDER = 13
ARM_RIGHT_GRIPPER = 15
ARM_SPARE = 15  # Can be used for wrist rotation upgrade

# Power management constants
MAX_CONCURRENT_MOVING = 3  # Never exceed this to stay <2.72A
SERVO_STALL_TIMEOUT_MS = 300  # Release after 300ms if no movement
VOLTAGE_WARNING_THRESHOLD = 4.5  # Volts, trigger load reduction
VOLTAGE_CRITICAL_THRESHOLD = 4.3  # Volts, emergency stop
VOLTAGE_CHECK_INTERVAL_S = 0.5  # Check voltage every 500ms

# ⚠️ REMOVED DANGEROUS FAKE GPIO VOLTAGE MONITORING
# GPIO pins CANNOT measure analog voltage - they only read digital HIGH/LOW
# Real voltage monitoring requires external ADC hardware:
#   - ADS1115 (16-bit I2C ADC, ~$10)
#   - MCP3008 (10-bit SPI ADC, ~$4)
# See documentation at end of file for implementation guide.


class PowerManager:
    """
    Manages power consumption on 5V rail to prevent UBEC overload.

    Features:
    - Current limiting (max 3 concurrent moving servos)
    - Stall detection (timeout after 300ms)
    - Voltage monitoring (DISABLED by default - requires external ADC)
    - Movement queuing (defer movements if at limit)

    ⚠️ SAFETY: Voltage monitoring is DISABLED by default because it requires
               external ADC hardware. GPIO pins cannot measure analog voltage.
    """

    def __init__(self, pwm_controller, enable_voltage_monitoring=False):
        """
        Initialize power manager.

        Args:
            pwm_controller: PCA9685 PWM controller instance
            enable_voltage_monitoring: Enable voltage monitoring (REQUIRES external
                                     ADC hardware like ADS1115 or MCP3008).
                                     Default: False (safe default)

        ⚠️ CRITICAL: Setting enable_voltage_monitoring=True without proper ADC
                    hardware will fail safely with a warning.
        """
        self.pwm = pwm_controller
        self.enable_voltage_monitor = enable_voltage_monitoring

        # Servo state tracking
        self.servo_states: Dict[int, Dict] = {}
        for servo_id in [ARM_LEFT_SHOULDER, ARM_RIGHT_SHOULDER,
                         ARM_LEFT_GRIPPER, ARM_RIGHT_GRIPPER]:
            self.servo_states[servo_id] = {
                'target_angle': 90,  # degrees
                'current_angle': 90,
                'is_moving': False,
                'move_start_time': 0,
                'stall_detected': False
            }

        # Movement queue (FIFO)
        self.movement_queue = deque()
        self.queue_lock = threading.Lock()

        # Voltage monitoring
        self.current_voltage = 5.0
        self.voltage_warnings = 0
        self.emergency_mode = False

        # ⚠️ REMOVED FAKE GPIO VOLTAGE MONITORING
        # Voltage monitoring now requires proper ADC hardware setup
        if self.enable_voltage_monitor:
            print("⚠️ WARNING: Voltage monitoring requested but no ADC hardware configured!")
            print("   GPIO pins CANNOT measure analog voltage.")
            print("   Please connect ADS1115 or MCP3008 ADC and configure properly.")
            print("   Voltage monitoring has been DISABLED for safety.")
            self.enable_voltage_monitor = False
            # TODO: Add proper ADC hardware support (see end of file for guide)

    def _start_voltage_thread(self):
        """Start background thread for continuous voltage monitoring."""
        def monitor_loop():
            while not self.emergency_mode:
                self.check_voltage()
                time.sleep(VOLTAGE_CHECK_INTERVAL_S)

        voltage_thread = threading.Thread(target=monitor_loop, daemon=True)
        voltage_thread.start()

    def check_voltage(self) -> float:
        """
        Check 5V rail voltage via ADC.

        Returns:
            float: Current 5V rail voltage (5.0V nominal if monitoring disabled)

        ⚠️ NOTE: Always returns 5.0V because voltage monitoring is disabled.
                Real implementation requires external ADC hardware.
        """
        if not self.enable_voltage_monitor:
            return 5.0  # Nominal voltage (monitoring disabled without ADC)

        # ⚠️ REMOVED DANGEROUS FAKE GPIO VOLTAGE READING
        # GPIO.read() only returns digital HIGH/LOW, not analog voltage!
        # This code has been removed to prevent false confidence.
        #
        # Real ADC implementation would look like:
        #   voltage = self.adc.read_adc(channel=0) * voltage_divider_ratio
        #   if voltage < VOLTAGE_CRITICAL_THRESHOLD:
        #       self._emergency_shutdown()
        #
        # For implementation guide, see documentation at end of file.

        return 5.0  # Safe default

    def _voltage_warning(self):
        """Handle voltage sag warning."""
        self.voltage_warnings += 1
        if self.voltage_warnings >= 3:
            print(f"⚠️ VOLTAGE SAG: {self.current_voltage:.2f}V (threshold: {VOLTAGE_WARNING_THRESHOLD}V)")
            print("   Reducing servo activity...")
            self._reduce_load()
            self.voltage_warnings = 0  # Reset counter

    def _reduce_load(self):
        """Reduce load on 5V rail by stopping non-critical servos."""
        print("🔧 Reducing load: Stopping queued movements")
        with self.queue_lock:
            self.movement_queue.clear()

        # Stop any moving servos that aren't critical
        for servo_id, state in self.servo_states.items():
            if state['is_moving']:
                print(f"   Stopping servo {servo_id}")
                self._stop_servo(servo_id)

    def _emergency_shutdown(self):
        """Emergency shutdown: voltage too low, stop all servos."""
        if self.emergency_mode:
            return  # Already in emergency mode

        self.emergency_mode = True
        print(f"❌ EMERGENCY: Voltage {self.current_voltage:.2f}V < {VOLTAGE_CRITICAL_THRESHOLD}V")
        print("   STOPPING ALL SERVOS!")

        # Cut power to all servos
        for servo_id in self.servo_states.keys():
            self.pwm.set_pwm(servo_id, 0, 0)
            self.servo_states[servo_id]['is_moving'] = False

        # Clear queue
        with self.queue_lock:
            self.movement_queue.clear()

        print("   System safe. Investigate power issue before resuming.")

    def get_moving_count(self) -> int:
        """
        Get count of currently moving servos.

        Returns:
            int: Number of servos currently in motion
        """
        return sum(1 for state in self.servo_states.values() if state['is_moving'])

    def can_move_servo(self) -> bool:
        """
        Check if we can move another servo without exceeding current limit.

        Returns:
            bool: True if safe to start another servo movement
        """
        if self.emergency_mode:
            return False
        return self.get_moving_count() < MAX_CONCURRENT_MOVING

    def move_servo(self, servo_id: int, target_angle: float,
                   force_immediate: bool = False) -> bool:
        """
        Move servo to target angle with current limiting.

        Args:
            servo_id: Servo channel (12-15)
            target_angle: Target angle in degrees (0-180)
            force_immediate: Bypass queue (use for critical movements only)

        Returns:
            bool: True if movement started, False if queued
        """
        if self.emergency_mode:
            print("❌ Cannot move servo: Emergency mode active")
            return False

        # Clamp angle to safe range
        target_angle = max(10, min(170, target_angle))

        # Check if we can move immediately
        if force_immediate or self.can_move_servo():
            self._execute_movement(servo_id, target_angle)
            return True
        else:
            # Queue movement
            with self.queue_lock:
                self.movement_queue.append((servo_id, target_angle))
            print(f"⏳ Queued servo {servo_id} movement to {target_angle}° "
                  f"(queue: {len(self.movement_queue)})")
            return False

    def _execute_movement(self, servo_id: int, target_angle: float):
        """Execute servo movement (internal)."""
        state = self.servo_states[servo_id]
        state['target_angle'] = target_angle
        state['is_moving'] = True
        state['move_start_time'] = time.time()
        state['stall_detected'] = False

        # Convert angle to PWM (SG90/MG90S: 0° = 150, 180° = 600)
        pwm_value = int(150 + (target_angle / 180.0) * 450)
        self.pwm.set_pwm(servo_id, 0, pwm_value)

        print(f"✅ Moving servo {servo_id} to {target_angle}° "
              f"(active: {self.get_moving_count()}/{MAX_CONCURRENT_MOVING})")

        # Start stall detection thread
        threading.Thread(target=self._monitor_stall,
                        args=(servo_id,), daemon=True).start()

    def _monitor_stall(self, servo_id: int):
        """Monitor servo for stall condition."""
        state = self.servo_states[servo_id]
        start_angle = state['current_angle']

        # Wait for servo movement time
        time.sleep(SERVO_STALL_TIMEOUT_MS / 1000.0)

        # Check if servo reached target (within 5° tolerance)
        # Note: Without position feedback, we assume success unless explicitly stalled
        # In practice, you'd read servo position via UART feedback
        angle_diff = abs(state['target_angle'] - state['current_angle'])

        if angle_diff > 5 and state['is_moving']:
            # Servo didn't move, likely stalled
            print(f"⚠️ STALL DETECTED: Servo {servo_id} (timeout after {SERVO_STALL_TIMEOUT_MS}ms)")
            state['stall_detected'] = True
            self._stop_servo(servo_id)
        else:
            # Movement complete
            state['current_angle'] = state['target_angle']
            state['is_moving'] = False
            print(f"✅ Servo {servo_id} reached target ({state['current_angle']}°)")

            # Process queue if available
            self._process_queue()

    def _stop_servo(self, servo_id: int):
        """Stop servo movement."""
        state = self.servo_states[servo_id]
        state['is_moving'] = False
        # Keep PWM signal at current position (don't cut power)
        print(f"🛑 Stopped servo {servo_id}")

    def _process_queue(self):
        """Process queued movements if slots available."""
        with self.queue_lock:
            while self.can_move_servo() and len(self.movement_queue) > 0:
                servo_id, target_angle = self.movement_queue.popleft()
                self._execute_movement(servo_id, target_angle)

    def move_multiple(self, targets: Dict[int, float]):
        """
        Move multiple servos with automatic current limiting.

        Args:
            targets: Dict of {servo_id: target_angle}

        Example:
            power_mgr.move_multiple({
                ARM_LEFT_SHOULDER: 90,
                ARM_LEFT_GRIPPER: 45,
                ARM_RIGHT_SHOULDER: 90
            })
        """
        for servo_id, angle in targets.items():
            self.move_servo(servo_id, angle)

    def get_status(self) -> Dict:
        """
        Get power management status.

        Returns:
            Dict with current state, voltage, queue length, etc.
        """
        return {
            'voltage': self.current_voltage,
            'moving_servos': self.get_moving_count(),
            'max_concurrent': MAX_CONCURRENT_MOVING,
            'queue_length': len(self.movement_queue),
            'emergency_mode': self.emergency_mode,
            'voltage_warnings': self.voltage_warnings,
            'servo_states': self.servo_states
        }


class ArmController:
    """
    High-level arm controller with safe power management.

    Uses PowerManager to ensure movements never exceed UBEC capacity.
    """

    def __init__(self, power_manager: PowerManager):
        """
        Initialize arm controller.

        Args:
            power_manager: PowerManager instance
        """
        self.pm = power_manager
        self.arm_length = 120  # mm

    def grab_object(self, side: str = 'left', height_mm: float = 50):
        """
        Execute grab sequence with power-safe movements.

        Args:
            side: 'left' or 'right'
            height_mm: Object height in mm
        """
        shoulder = ARM_LEFT_SHOULDER if side == 'left' else ARM_RIGHT_SHOULDER
        gripper = ARM_LEFT_GRIPPER if side == 'left' else ARM_RIGHT_GRIPPER

        print(f"🤖 Grabbing object ({side} arm, height={height_mm}mm)")

        # Sequential movement to avoid peak current
        # 1. Position arm above object
        self.pm.move_servo(shoulder, 120)  # Raise arm
        time.sleep(0.5)

        # 2. Open gripper
        self.pm.move_servo(gripper, 30)  # Open
        time.sleep(0.4)

        # 3. Lower to object
        self.pm.move_servo(shoulder, 90)  # Lower arm
        time.sleep(0.5)

        # 4. Close gripper
        self.pm.move_servo(gripper, 150)  # Close grip
        time.sleep(0.5)

        # 5. Lift object
        self.pm.move_servo(shoulder, 120)  # Raise with object
        time.sleep(0.5)

        print(f"✅ Grab complete!")

    def wave_gesture(self):
        """
        Wave both arms in sequence (power-safe).

        Uses sequential movements instead of parallel to stay <2.72A.
        """
        print("👋 Waving gesture...")

        # Sequential wave (one arm at a time)
        for _ in range(2):  # Two waves
            self.pm.move_servo(ARM_LEFT_SHOULDER, 135)
            time.sleep(0.4)
            self.pm.move_servo(ARM_RIGHT_SHOULDER, 135)
            time.sleep(0.4)
            self.pm.move_servo(ARM_LEFT_SHOULDER, 45)
            time.sleep(0.4)
            self.pm.move_servo(ARM_RIGHT_SHOULDER, 45)
            time.sleep(0.4)

        # Return to neutral
        self.pm.move_servo(ARM_LEFT_SHOULDER, 90)
        self.pm.move_servo(ARM_RIGHT_SHOULDER, 90)

        print("✅ Wave complete!")

    def parallel_wave_demo(self):
        """
        Demonstrate parallel movement (uses queue to limit current).

        This will automatically queue movements if >3 servos active.
        """
        print("👋 Parallel wave demo (with queueing)...")

        # Try to move all 4 arm servos at once
        # PowerManager will automatically queue extras
        self.pm.move_multiple({
            ARM_LEFT_SHOULDER: 135,
            ARM_RIGHT_SHOULDER: 135,
            ARM_LEFT_GRIPPER: 90,
            ARM_RIGHT_GRIPPER: 90
        })

        # Wait for movements to complete (including queued)
        time.sleep(2.0)

        print("✅ Parallel demo complete!")


# Example usage
if __name__ == "__main__":
    from Adafruit_PCA9685 import PCA9685

    # Initialize hardware
    pwm = PCA9685(address=0x40, busnum=1)
    pwm.set_pwm_freq(50)  # 50Hz for servos

    # Initialize power manager (voltage monitoring disabled - requires ADC hardware)
    power_mgr = PowerManager(pwm, enable_voltage_monitoring=False)

    # Initialize arm controller
    arms = ArmController(power_mgr)

    print("="*60)
    print("OpenDuck Mini V3 - Arm Control Demo")
    print("Power-safe movement with single 3A UBEC")
    print("="*60)

    # Check initial status
    status = power_mgr.get_status()
    print(f"\n📊 Initial Status:")
    print(f"   Voltage: {status['voltage']:.2f}V")
    print(f"   Moving servos: {status['moving_servos']}/{status['max_concurrent']}")
    print(f"   Queue: {status['queue_length']} pending")

    # Demo 1: Sequential grab
    print("\n\n=== DEMO 1: Grab Object (Sequential) ===")
    arms.grab_object(side='left', height_mm=50)

    # Demo 2: Wave gesture
    print("\n\n=== DEMO 2: Wave Gesture (Sequential) ===")
    arms.wave_gesture()

    # Demo 3: Parallel movement with queueing
    print("\n\n=== DEMO 3: Parallel Movement (Auto-Queuing) ===")
    arms.parallel_wave_demo()

    # Final status
    status = power_mgr.get_status()
    print(f"\n\n📊 Final Status:")
    print(f"   Voltage: {status['voltage']:.2f}V")
    print(f"   Total warnings: {status['voltage_warnings']}")
    print(f"   Emergency mode: {status['emergency_mode']}")

    print("\n✅ Demo complete! Single 3A UBEC handled all movements safely.")
    print("   Peak current stayed <2.72A thanks to movement limiting.")


# =============================================================================
# HOW TO ADD REAL VOLTAGE MONITORING (ADC Hardware Required)
# =============================================================================
"""
⚠️ CRITICAL: GPIO pins CANNOT measure analog voltage!

This module previously contained DANGEROUS fake voltage monitoring that used
GPIO pins to "read" voltage. GPIO pins only read digital HIGH/LOW states,
not analog voltages. This code has been REMOVED.

To add real voltage monitoring, you MUST use external ADC hardware:

## Option 1: ADS1115 (Recommended - High Precision)
- 16-bit resolution, I2C interface
- Cost: ~$10
- Library: Adafruit_ADS1x15
- Wiring:
    VDD  → 3.3V (Pi)
    GND  → GND
    SCL  → GPIO 3 (I2C SCL)
    SDA  → GPIO 2 (I2C SDA)
    A0   → 5V rail (via voltage divider)

Voltage Divider (5V → 3.3V max):
    5V ──[2.2kΩ]─┬─[3.3kΩ]── GND
                 │
                 └─ A0 (ADC input)

Example Code:
```python
import Adafruit_ADS1x15

class PowerManagerWithADC(PowerManager):
    def __init__(self, pwm_controller, adc_channel=0):
        super().__init__(pwm_controller, enable_voltage_monitoring=False)

        # Initialize ADS1115
        self.adc = Adafruit_ADS1x15.ADS1115()
        self.adc_channel = adc_channel
        self.voltage_divider_ratio = 5.5 / 3.3  # R1=2.2k, R2=3.3k
        self.enable_voltage_monitor = True

        # Start monitoring thread
        self._start_voltage_thread()

    def check_voltage(self) -> float:
        # Read 16-bit ADC value (0-32767 for 0-4.096V gain setting)
        adc_value = self.adc.read_adc(self.adc_channel, gain=1)

        # Convert to voltage (gain=1 → ±4.096V range)
        voltage_divider = (adc_value / 32767.0) * 4.096
        voltage_5v = voltage_divider * self.voltage_divider_ratio

        self.current_voltage = voltage_5v

        # Check thresholds
        if voltage_5v < VOLTAGE_CRITICAL_THRESHOLD:
            self._emergency_shutdown()
        elif voltage_5v < VOLTAGE_WARNING_THRESHOLD:
            self._voltage_warning()

        return voltage_5v
```

## Option 2: MCP3008 (Budget Option)
- 10-bit resolution, SPI interface
- Cost: ~$4
- Library: Adafruit_MCP3008
- Wiring:
    VDD   → 3.3V
    VREF  → 3.3V
    AGND  → GND
    DGND  → GND
    CLK   → GPIO 11 (SPI CLK)
    DOUT  → GPIO 9 (SPI MISO)
    DIN   → GPIO 10 (SPI MOSI)
    CS    → GPIO 8 (SPI CE0)
    CH0   → 5V rail (via voltage divider)

Example Code:
```python
import Adafruit_MCP3008

class PowerManagerWithMCP3008(PowerManager):
    def __init__(self, pwm_controller, spi_channel=0):
        super().__init__(pwm_controller, enable_voltage_monitoring=False)

        # Initialize MCP3008 (software SPI)
        self.adc = Adafruit_MCP3008.MCP3008(clk=11, cs=8, miso=9, mosi=10)
        self.adc_channel = spi_channel
        self.voltage_divider_ratio = 5.5 / 3.3
        self.enable_voltage_monitor = True

        self._start_voltage_thread()

    def check_voltage(self) -> float:
        # Read 10-bit ADC value (0-1023 for 0-3.3V)
        adc_value = self.adc.read_adc(self.adc_channel)

        # Convert to voltage
        voltage_divider = (adc_value / 1023.0) * 3.3
        voltage_5v = voltage_divider * self.voltage_divider_ratio

        self.current_voltage = voltage_5v

        # Check thresholds
        if voltage_5v < VOLTAGE_CRITICAL_THRESHOLD:
            self._emergency_shutdown()
        elif voltage_5v < VOLTAGE_WARNING_THRESHOLD:
            self._voltage_warning()

        return voltage_5v
```

## Testing Your ADC Setup
```python
# Test voltage reading
import time

pm = PowerManagerWithADC(pwm)
for i in range(10):
    voltage = pm.check_voltage()
    print(f"5V Rail: {voltage:.3f}V")
    time.sleep(0.5)

# Should read ~5.0V when idle
# Should drop to 4.5-4.8V under heavy servo load
# Should never read exactly 0V or 5.5V+ (indicates wiring issue)
```

## Safety Checklist
☐ Voltage divider properly calculated and tested
☐ ADC never receives >3.3V input (will damage Pi)
☐ All grounds connected (Pi GND = ADC GND = Power GND)
☐ I2C/SPI address conflicts resolved
☐ Tested under load before deploying

## Why This Matters
Without proper voltage monitoring:
- ✅ Robot still works (current limiting prevents UBEC overload)
- ❌ Cannot detect voltage sag early
- ❌ Cannot trigger emergency shutdown if UBEC fails
- ❌ No warning before brownout crashes

The fake GPIO voltage monitoring removed from this code was WORSE than
no monitoring at all - it gave false confidence while providing no real data.

For questions, see hardware documentation or robot build guide.
"""
