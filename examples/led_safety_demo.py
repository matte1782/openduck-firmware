#!/usr/bin/env python3
"""LED Safety System Demonstration - OpenDuck Mini V3.

This example demonstrates how to use the LED safety system to protect
hardware from overcurrent and ensure safe LED operation.

Features demonstrated:
1. Automatic brightness clamping based on power source
2. Real-time current monitoring
3. Safety level warnings
4. Emergency shutdown handling
5. GPIO validation before operations

Run with: sudo python3 examples/led_safety_demo.py

Hardware Requirements:
- 2× WS2812B 16-LED rings connected to GPIO 18 and GPIO 13
- Powered from Raspberry Pi 5V rail OR external 5V UBEC
"""

import sys
import time
import logging
from typing import Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import LED safety system
try:
    from src.safety.led_safety import (
        LEDSafetyManager,
        LEDRingProfile,
        PowerSource,
        SafetyLevel,
    )
except ImportError:
    logger.error("Failed to import LED safety module. Ensure you're in the firmware directory.")
    sys.exit(1)

# Import WS2812B driver
try:
    from rpi_ws281x import PixelStrip, Color
    HAS_LED_DRIVER = True
except ImportError:
    logger.warning("rpi_ws281x library not installed - running in demo mode without hardware")
    HAS_LED_DRIVER = False
    # Mock classes for demo mode
    class Color:
        def __init__(self, r, g, b):
            self.r, self.g, self.b = r, g, b
    class PixelStrip:
        def __init__(self, *args, **kwargs):
            pass
        def begin(self):
            pass
        def setPixelColor(self, i, color):
            pass
        def show(self):
            pass
        def numPixels(self):
            return 16


# Configuration
RING1_PIN = 18  # GPIO 18, Physical Pin 12, PWM Channel 0
RING2_PIN = 13  # GPIO 13, Physical Pin 33, PWM Channel 1
NUM_LEDS = 16
INITIAL_BRIGHTNESS = 50

# Ask user about power source
POWER_SOURCE = PowerSource.PI_5V_RAIL  # Default to safe mode


def print_banner():
    """Print demonstration banner."""
    print("=" * 70)
    print(" " * 15 + "LED SAFETY SYSTEM DEMONSTRATION")
    print(" " * 20 + "OpenDuck Mini V3")
    print("=" * 70)
    print()


def configure_power_source() -> PowerSource:
    """Interactively configure power source."""
    print("Power Source Configuration")
    print("-" * 70)
    print("How are your LED rings powered?")
    print("  1. Raspberry Pi 5V rail (Pins 2/4) - SAFE, brightness limited to 50%")
    print("  2. External 5V UBEC (direct connection) - Full brightness allowed")
    print()

    while True:
        try:
            choice = input("Select power source [1/2] (default: 1): ").strip()
            if not choice:
                choice = "1"

            if choice == "1":
                return PowerSource.PI_5V_RAIL
            elif choice == "2":
                confirm = input(
                    "WARNING: Ensure external 5V is connected! Continue? [y/N]: "
                ).strip().lower()
                if confirm == 'y':
                    return PowerSource.EXTERNAL_5V
                else:
                    print("Defaulting to Pi 5V rail for safety.")
                    return PowerSource.PI_5V_RAIL
            else:
                print("Invalid choice. Please enter 1 or 2.")
        except KeyboardInterrupt:
            print("\n\nAborted by user.")
            sys.exit(0)


def initialize_safety_system(power_source: PowerSource) -> LEDSafetyManager:
    """Initialize LED safety manager and register rings.

    Args:
        power_source: Power source configuration

    Returns:
        Configured LEDSafetyManager instance
    """
    logger.info("Initializing LED safety system...")

    # Create safety manager
    manager = LEDSafetyManager(power_source=power_source)

    # Register Ring 1 (Left Eye)
    ring1_profile = LEDRingProfile(
        num_leds=NUM_LEDS,
        current_per_led_ma=60.0,
        gpio_pin=RING1_PIN,
        pwm_channel=0,
        name="Left Eye"
    )
    manager.register_ring("ring1", ring1_profile)
    logger.info("Registered Ring 1: %s (GPIO %d)", ring1_profile.name, ring1_profile.gpio_pin)

    # Register Ring 2 (Right Eye)
    ring2_profile = LEDRingProfile(
        num_leds=NUM_LEDS,
        current_per_led_ma=60.0,
        gpio_pin=RING2_PIN,
        pwm_channel=1,
        name="Right Eye"
    )
    manager.register_ring("ring2", ring2_profile)
    logger.info("Registered Ring 2: %s (GPIO %d)", ring2_profile.name, ring2_profile.gpio_pin)

    # Print diagnostics
    print_diagnostics(manager)

    return manager


def initialize_led_strips(manager: LEDSafetyManager, brightness: int):
    """Initialize LED strips with safety validation.

    Args:
        manager: LED safety manager
        brightness: Requested brightness (will be validated/clamped)

    Returns:
        Tuple of (ring1, ring2, safe_brightness, Color)
    """
    logger.info("Initializing LED strips...")

    # Validate GPIO available
    for ring_id in ["ring1", "ring2"]:
        valid, reason = manager.validate_gpio_available(ring_id)
        if not valid:
            logger.error("GPIO validation failed for %s: %s", ring_id, reason)
            sys.exit(1)

    # Validate brightness and get safe level
    allowed, safe_brightness = manager.validate_brightness("ring1", brightness)
    if not allowed:
        logger.warning(
            "Brightness clamped: requested=%d, safe=%d",
            brightness, safe_brightness
        )
        print(f"\n⚠️  SAFETY: Brightness reduced from {brightness} to {safe_brightness}")
        print(f"    Reason: Power source is {manager.power_source.name}")
        print()

    # Initialize strips
    try:
        ring1 = PixelStrip(NUM_LEDS, RING1_PIN, 800000, 10, False, safe_brightness, 0)
        ring1.begin()
        logger.info("Ring 1 initialized (brightness=%d)", safe_brightness)

        ring2 = PixelStrip(NUM_LEDS, RING2_PIN, 800000, 10, False, safe_brightness, 1)
        ring2.begin()
        logger.info("Ring 2 initialized (brightness=%d)", safe_brightness)

        return ring1, ring2, safe_brightness, Color

    except Exception as e:
        logger.error("LED initialization failed: %s", e)
        if not HAS_LED_DRIVER:
            logger.info("Running in demo mode - hardware not required")
            return None, None, safe_brightness, Color
        sys.exit(1)


def print_diagnostics(manager: LEDSafetyManager):
    """Print safety system diagnostics."""
    diag = manager.get_diagnostics()

    print("\n" + "=" * 70)
    print("LED SAFETY SYSTEM DIAGNOSTICS")
    print("=" * 70)
    print(f"Power Source:        {diag['power_source']}")
    print(f"Max Brightness:      {diag['max_brightness']}/255 ({diag['max_brightness']/255*100:.0f}%)")
    print(f"Registered Rings:    {diag['registered_rings']}")
    print(f"GPIO Available:      {diag['gpio_available']}")
    print(f"Emergency Shutdown:  {diag['emergency_shutdown']}")
    print()

    print("Current Limits:")
    limits = diag['current_limits']
    print(f"  Max Allowed:       {limits['max_allowed_ma']:.0f} mA")
    print(f"  Pi Rail Max:       {limits['pi_rail_max_ma']:.0f} mA")
    print(f"  Pi Reserve:        {limits['pi_reserve_ma']:.0f} mA")
    print(f"  Warning at:        {limits['warning_threshold']*100:.0f}% of max")
    print(f"  Critical at:       {limits['critical_threshold']*100:.0f}% of max")
    print()

    print("Registered Rings:")
    for ring_id, details in diag['ring_details'].items():
        print(f"  {ring_id} ({details['name']}):")
        print(f"    GPIO:            {details['gpio_pin']}")
        print(f"    PWM Channel:     {details['pwm_channel']}")
        print(f"    LEDs:            {details['num_leds']}")
        print(f"    Max Current:     {details['max_current_ma']:.0f} mA")
    print("=" * 70 + "\n")


def print_current_estimate(manager: LEDSafetyManager, brightness: int):
    """Print current consumption estimate.

    Args:
        manager: LED safety manager
        brightness: Current brightness level
    """
    estimate = manager.estimate_current({"ring1": brightness, "ring2": brightness})

    # Safety level indicator
    level_indicators = {
        SafetyLevel.SAFE: "✓",
        SafetyLevel.WARNING: "⚠",
        SafetyLevel.CRITICAL: "⚠",
        SafetyLevel.EMERGENCY: "✗"
    }
    indicator = level_indicators.get(estimate.safety_level, "?")

    print(f"\n{indicator} Current Estimate (Brightness={brightness}):")
    print(f"  Total:           {estimate.total_ma:.0f} mA")
    print(f"  Ring 1:          {estimate.per_ring_ma['ring1']:.0f} mA")
    print(f"  Ring 2:          {estimate.per_ring_ma['ring2']:.0f} mA")
    print(f"  Max Allowed:     {estimate.max_allowed_ma:.0f} mA")
    print(f"  Headroom:        {estimate.headroom_ma:.0f} mA")
    print(f"  Safety Level:    {estimate.safety_level.name}")

    if estimate.safety_level == SafetyLevel.EMERGENCY:
        print("\n  ⚠️  DANGER: Current exceeds safe limits!")
        print("      Reduce brightness or switch to external power.")
    elif estimate.safety_level == SafetyLevel.CRITICAL:
        print("\n  ⚠️  WARNING: Approaching current limit!")


def fill(strip, r, g, b):
    """Fill entire strip with one color."""
    if strip is None:
        return
    for i in range(strip.numPixels()):
        strip.setPixelColor(i, Color(r, g, b))
    strip.show()


def clear_all(ring1, ring2):
    """Turn off all LEDs on both rings."""
    fill(ring1, 0, 0, 0)
    fill(ring2, 0, 0, 0)


def demo_safe_operation(manager, ring1, ring2, safe_brightness):
    """Demonstrate safe LED operation with monitoring.

    Args:
        manager: LED safety manager
        ring1: Ring 1 PixelStrip
        ring2: Ring 2 PixelStrip
        safe_brightness: Safe brightness level
    """
    print("\n" + "=" * 70)
    print("DEMO 1: SAFE OPERATION")
    print("=" * 70)
    print("Operating at safe brightness with current monitoring.\n")

    # Print current estimate
    print_current_estimate(manager, safe_brightness)

    print("\n[TEST 1] Both rings RED")
    fill(ring1, 255, 0, 0)
    fill(ring2, 255, 0, 0)
    time.sleep(2)

    print("[TEST 2] Both rings GREEN")
    fill(ring1, 0, 255, 0)
    fill(ring2, 0, 255, 0)
    time.sleep(2)

    print("[TEST 3] Both rings BLUE")
    fill(ring1, 0, 0, 255)
    fill(ring2, 0, 0, 255)
    time.sleep(2)

    print("[TEST 4] Both rings WHITE (maximum current at this brightness)")
    fill(ring1, 255, 255, 255)
    fill(ring2, 255, 255, 255)
    time.sleep(2)

    clear_all(ring1, ring2)
    print("\nSafe operation complete!\n")


def demo_brightness_validation(manager):
    """Demonstrate brightness validation for different levels.

    Args:
        manager: LED safety manager
    """
    print("\n" + "=" * 70)
    print("DEMO 2: BRIGHTNESS VALIDATION")
    print("=" * 70)
    print("Testing brightness limits for current power source.\n")

    test_levels = [25, 50, 75, 100, 150, 200, 255]

    for brightness in test_levels:
        allowed, safe = manager.validate_brightness("ring1", brightness)
        status = "✓ ALLOWED" if allowed else "✗ CLAMPED"
        print(f"Brightness {brightness:3d} → {safe:3d}  {status}")

    print()


def demo_current_estimates(manager):
    """Demonstrate current estimation at various brightness levels.

    Args:
        manager: LED safety manager
    """
    print("\n" + "=" * 70)
    print("DEMO 3: CURRENT ESTIMATION")
    print("=" * 70)
    print("Estimated current draw at different brightness levels.\n")

    test_levels = [25, 50, 100, 150, 255]

    for brightness in test_levels:
        print_current_estimate(manager, brightness)
        print()


def demo_emergency_shutdown(manager, ring1, ring2):
    """Demonstrate emergency shutdown.

    Args:
        manager: LED safety manager
        ring1: Ring 1 PixelStrip
        ring2: Ring 2 PixelStrip
    """
    print("\n" + "=" * 70)
    print("DEMO 4: EMERGENCY SHUTDOWN")
    print("=" * 70)
    print("Simulating emergency shutdown scenario.\n")

    print("[TEST] Setting rings to purple...")
    fill(ring1, 255, 0, 255)
    fill(ring2, 255, 0, 255)
    time.sleep(1)

    print("[EMERGENCY] Triggering shutdown...")
    manager.emergency_shutdown("demo_test")

    # Turn off LEDs
    clear_all(ring1, ring2)
    print("LEDs disabled.")

    # Try to use LEDs (should be blocked)
    valid, reason = manager.validate_gpio_available("ring1")
    print(f"\nGPIO validation: {valid}")
    if not valid:
        print(f"Reason: {reason}")

    # Reset shutdown
    print("\n[RESET] Clearing emergency shutdown...")
    manager.reset_emergency_shutdown()

    valid, reason = manager.validate_gpio_available("ring1")
    print(f"GPIO validation: {valid}")
    if valid:
        print("System ready for operation again.")

    print()


def main():
    """Main demonstration program."""
    print_banner()

    # Configure power source
    power_source = configure_power_source()
    print()

    # Initialize safety system
    manager = initialize_safety_system(power_source)

    # Initialize LED hardware
    ring1, ring2, safe_brightness, Color_cls = initialize_led_strips(
        manager, INITIAL_BRIGHTNESS
    )

    try:
        # Demo 1: Safe operation
        demo_safe_operation(manager, ring1, ring2, safe_brightness)

        # Demo 2: Brightness validation
        demo_brightness_validation(manager)

        # Demo 3: Current estimates
        demo_current_estimates(manager)

        # Demo 4: Emergency shutdown
        demo_emergency_shutdown(manager, ring1, ring2)

        print("=" * 70)
        print("ALL DEMONSTRATIONS COMPLETE")
        print("=" * 70)
        print("\nKey Takeaways:")
        print("  1. Brightness is automatically clamped based on power source")
        print("  2. Real-time current monitoring prevents overcurrent")
        print("  3. Emergency shutdown provides fail-safe protection")
        print("  4. GPIO validation ensures safe operation")
        print("\nLED safety system is ready for production use!")
        print("=" * 70 + "\n")

    except KeyboardInterrupt:
        print("\n\nDemo interrupted by user.")

    finally:
        # Cleanup
        logger.info("Cleaning up...")
        clear_all(ring1, ring2)
        print("LEDs turned off. Goodbye!")


if __name__ == '__main__':
    main()
