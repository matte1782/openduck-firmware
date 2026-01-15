#!/usr/bin/env python3
"""
Servo calibration utility for OpenDuck Mini V3
Interactive tool to find optimal PWM values for each servo

Usage:
    python calibrate_servos.py [--servo SERVO_ID]

Safety:
    - Keep robot on a stable, non-slip surface
    - Ensure battery is fully charged (> 7.4V)
    - Have emergency stop button accessible
    - Clear area around robot of obstacles
"""
import sys
import time
import argparse
from pathlib import Path

# Add parent src directory to Python path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

try:
    from drivers.servo.pca9685 import PCA9685Driver
except ImportError:
    print("ERROR: Cannot import PCA9685Driver. Ensure firmware/src/drivers/servo/pca9685.py exists")
    sys.exit(1)

# Servo configuration for quadruped
SERVO_CONFIG = {
    # Front Left Leg (FL)
    0: {"name": "FL_HIP", "joint": "hip", "leg": "front_left"},
    1: {"name": "FL_SHOULDER", "joint": "shoulder", "leg": "front_left"},
    2: {"name": "FL_KNEE", "joint": "knee", "leg": "front_left"},

    # Front Right Leg (FR)
    4: {"name": "FR_HIP", "joint": "hip", "leg": "front_right"},
    5: {"name": "FR_SHOULDER", "joint": "shoulder", "leg": "front_right"},
    6: {"name": "FR_KNEE", "joint": "knee", "leg": "front_right"},

    # Rear Left Leg (RL)
    8: {"name": "RL_HIP", "joint": "hip", "leg": "rear_left"},
    9: {"name": "RL_SHOULDER", "joint": "shoulder", "leg": "rear_left"},
    10: {"name": "RL_KNEE", "joint": "knee", "leg": "rear_left"},

    # Rear Right Leg (RR)
    12: {"name": "RR_HIP", "joint": "hip", "leg": "rear_right"},
    13: {"name": "RR_SHOULDER", "joint": "shoulder", "leg": "rear_right"},
    14: {"name": "RR_KNEE", "joint": "knee", "leg": "rear_right"},
}

def print_header():
    """Print calibration tool header"""
    print("=" * 60)
    print("  OpenDuck Mini V3 - Servo Calibration Tool")
    print("=" * 60)
    print()
    print("⚠️  SAFETY CHECKLIST:")
    print("  [ ] Robot on stable, non-slip surface")
    print("  [ ] Battery fully charged (> 7.4V)")
    print("  [ ] Emergency stop button accessible")
    print("  [ ] Clear area around robot")
    print()
    input("Press ENTER when safety checks complete...")
    print()

def calibrate_servo(driver, servo_id, config):
    """
    Interactive calibration for a single servo

    Args:
        driver: PCA9685Driver instance
        servo_id: Servo channel number (0-15)
        config: Servo configuration dict

    Returns:
        dict: Calibration results {min_pulse, max_pulse, center_pulse}
    """
    print(f"\n{'=' * 60}")
    print(f"Calibrating Servo #{servo_id}: {config['name']}")
    print(f"  Joint: {config['joint']}")
    print(f"  Leg: {config['leg']}")
    print(f"{'=' * 60}\n")

    # Default PWM values for MG90S servos
    default_min = 500   # microseconds
    default_max = 2500  # microseconds
    default_center = 1500  # microseconds

    calibration = {
        "min_pulse": default_min,
        "center_pulse": default_center,
        "max_pulse": default_max,
    }

    # Step 1: Find minimum position
    print("Step 1: Finding MINIMUM position (0 degrees)")
    print("  Starting at default min (500µs)...")
    driver.set_pulse_width(servo_id, default_min)
    time.sleep(1)

    print("\n  Commands:")
    print("    '+' = increase pulse width by 10µs")
    print("    '-' = decrease pulse width by 10µs")
    print("    '++' = increase pulse width by 50µs")
    print("    '--' = decrease pulse width by 50µs")
    print("    'done' = confirm minimum position")
    print()

    current_pulse = default_min
    while True:
        cmd = input(f"  Current: {current_pulse}µs > ").strip().lower()

        if cmd == "+":
            current_pulse += 10
        elif cmd == "-":
            current_pulse -= 10
        elif cmd == "++":
            current_pulse += 50
        elif cmd == "--":
            current_pulse -= 50
        elif cmd == "done":
            calibration["min_pulse"] = current_pulse
            print(f"  ✓ Minimum position set: {current_pulse}µs\n")
            break
        else:
            print("  Invalid command. Use: +, -, ++, --, done")
            continue

        # Apply bounds
        current_pulse = max(200, min(3000, current_pulse))
        driver.set_pulse_width(servo_id, current_pulse)
        time.sleep(0.1)

    # Step 2: Find center position
    print("Step 2: Finding CENTER position (90 degrees)")
    print("  Moving to default center (1500µs)...")
    driver.set_pulse_width(servo_id, default_center)
    time.sleep(1)

    current_pulse = default_center
    while True:
        cmd = input(f"  Current: {current_pulse}µs > ").strip().lower()

        if cmd == "+":
            current_pulse += 10
        elif cmd == "-":
            current_pulse -= 10
        elif cmd == "++":
            current_pulse += 50
        elif cmd == "--":
            current_pulse -= 50
        elif cmd == "done":
            calibration["center_pulse"] = current_pulse
            print(f"  ✓ Center position set: {current_pulse}µs\n")
            break
        else:
            print("  Invalid command. Use: +, -, ++, --, done")
            continue

        current_pulse = max(200, min(3000, current_pulse))
        driver.set_pulse_width(servo_id, current_pulse)
        time.sleep(0.1)

    # Step 3: Find maximum position
    print("Step 3: Finding MAXIMUM position (180 degrees)")
    print("  Moving to default max (2500µs)...")
    driver.set_pulse_width(servo_id, default_max)
    time.sleep(1)

    current_pulse = default_max
    while True:
        cmd = input(f"  Current: {current_pulse}µs > ").strip().lower()

        if cmd == "+":
            current_pulse += 10
        elif cmd == "-":
            current_pulse -= 10
        elif cmd == "++":
            current_pulse += 50
        elif cmd == "--":
            current_pulse -= 50
        elif cmd == "done":
            calibration["max_pulse"] = current_pulse
            print(f"  ✓ Maximum position set: {current_pulse}µs\n")
            break
        else:
            print("  Invalid command. Use: +, -, ++, --, done")
            continue

        current_pulse = max(200, min(3000, current_pulse))
        driver.set_pulse_width(servo_id, current_pulse)
        time.sleep(0.1)

    # Return to center position
    print("  Returning to center position...")
    driver.set_pulse_width(servo_id, calibration["center_pulse"])
    time.sleep(0.5)

    return calibration

def save_calibration(results, output_file="servo_calibration.yaml"):
    """
    Save calibration results to YAML file

    Args:
        results: Dict of calibration results
        output_file: Output filename
    """
    import yaml

    output_path = Path(__file__).parent.parent / "configs" / output_file

    # Format for YAML output
    calibration_data = {
        "calibration_date": time.strftime("%Y-%m-%d %H:%M:%S"),
        "servos": {}
    }

    for servo_id, data in results.items():
        config = SERVO_CONFIG[servo_id]
        calibration_data["servos"][servo_id] = {
            "name": config["name"],
            "joint": config["joint"],
            "leg": config["leg"],
            "min_pulse_us": data["min_pulse"],
            "center_pulse_us": data["center_pulse"],
            "max_pulse_us": data["max_pulse"],
        }

    with open(output_path, "w") as f:
        yaml.dump(calibration_data, f, default_flow_style=False, sort_keys=False)

    print(f"\n✓ Calibration saved to: {output_path}")

def main():
    """Main calibration routine"""
    parser = argparse.ArgumentParser(description="OpenDuck Mini V3 Servo Calibration")
    parser.add_argument(
        "--servo",
        type=int,
        choices=list(SERVO_CONFIG.keys()),
        help="Calibrate specific servo ID (omit to calibrate all)"
    )
    parser.add_argument(
        "--output",
        type=str,
        default="servo_calibration.yaml",
        help="Output calibration file name"
    )
    args = parser.parse_args()

    print_header()

    # Initialize PCA9685 driver
    print("Initializing PCA9685 servo driver...")
    try:
        driver = PCA9685Driver(frequency=50)  # 50Hz for servos
        print("✓ Driver initialized\n")
    except Exception as e:
        print(f"ERROR: Failed to initialize driver: {e}")
        print("  - Check I2C connection")
        print("  - Verify PCA9685 address (default 0x40)")
        print("  - Ensure I2C is enabled: sudo raspi-config > Interface Options > I2C")
        sys.exit(1)

    # Determine which servos to calibrate
    if args.servo is not None:
        servos_to_calibrate = [args.servo]
    else:
        servos_to_calibrate = sorted(SERVO_CONFIG.keys())
        print(f"Calibrating all {len(servos_to_calibrate)} servos...\n")

    # Calibration results
    results = {}

    try:
        for servo_id in servos_to_calibrate:
            config = SERVO_CONFIG[servo_id]
            results[servo_id] = calibrate_servo(driver, servo_id, config)

            # Prompt to continue or stop
            if servo_id != servos_to_calibrate[-1]:
                print("\nPress ENTER to calibrate next servo (or Ctrl+C to stop)...")
                input()

        # Save calibration results
        print("\n" + "=" * 60)
        print("Calibration Summary")
        print("=" * 60)
        for servo_id, data in results.items():
            config = SERVO_CONFIG[servo_id]
            print(f"{config['name']:15} | Min: {data['min_pulse']:4}µs | "
                  f"Center: {data['center_pulse']:4}µs | Max: {data['max_pulse']:4}µs")
        print("=" * 60)

        save_choice = input("\nSave calibration? (y/n): ").strip().lower()
        if save_choice == "y":
            save_calibration(results, args.output)
        else:
            print("Calibration not saved.")

    except KeyboardInterrupt:
        print("\n\n⚠️  Calibration interrupted by user")
        print("Returning all servos to safe position (center)...")
        for servo_id in servos_to_calibrate:
            driver.set_pulse_width(servo_id, 1500)
        time.sleep(0.5)

    finally:
        # Cleanup
        print("\nShutting down driver...")
        driver.sleep()
        print("✓ Calibration complete")

if __name__ == "__main__":
    main()
