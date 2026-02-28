#!/usr/bin/env python3
"""Day 46 Phase 2: Multi-Servo Power Test
3x MG90S on PCA9685 channels 0-2, simultaneous sweep.
Monitors for brownout (servo stutter, I2C errors).
"""
import time
import sys
from adafruit_servokit import ServoKit

CHANNELS = [0, 1, 2]
DURATION = 30  # seconds
STEP = 5
DELAY = 0.05  # 20Hz

def main():
    print("=== Multi-Servo Power Test ===")
    print(f"Channels: {CHANNELS}")
    print(f"Duration: {DURATION}s")
    print()

    try:
        kit = ServoKit(channels=16)
        print("[OK] ServoKit initialized @ 0x40")
    except Exception as e:
        print(f"[FAIL] ServoKit init: {e}")
        return 1

    # Verify all channels respond
    print("Verifying channels...")
    for ch in CHANNELS:
        try:
            kit.servo[ch].angle = 90
            print(f"  Channel {ch}: centered at 90°")
        except Exception as e:
            print(f"  Channel {ch}: FAILED - {e}")
            return 1
    time.sleep(1)

    angles = {ch: 0 for ch in CHANNELS}
    directions = {ch: 1 for ch in CHANNELS}
    moves = 0
    errors = 0
    stutter_count = 0

    # Offset each servo so they don't all move in sync (more realistic load)
    angles[0] = 0
    angles[1] = 60
    angles[2] = 120

    print(f"\nStarting simultaneous sweep...")
    start = time.time()

    try:
        while time.time() - start < DURATION:
            for ch in CHANNELS:
                try:
                    kit.servo[ch].angle = angles[ch]
                    moves += 1
                except Exception as e:
                    errors += 1
                    print(f"\n[ERROR] ch{ch} at {angles[ch]}°: {e}")

                angles[ch] += STEP * directions[ch]
                if angles[ch] >= 180:
                    angles[ch] = 180
                    directions[ch] = -1
                elif angles[ch] <= 0:
                    angles[ch] = 0
                    directions[ch] = 1

            elapsed = time.time() - start
            print(
                f"[{elapsed:5.1f}s] moves={moves} errors={errors} "
                f"ch0={angles[0]:3d}° ch1={angles[1]:3d}° ch2={angles[2]:3d}°",
                end="\r",
            )
            time.sleep(DELAY)

    except KeyboardInterrupt:
        print("\n\nInterrupted")

    # Park servos at 90
    for ch in CHANNELS:
        try:
            kit.servo[ch].angle = 90
        except:
            pass

    elapsed = time.time() - start
    print(f"\n\n{'='*50}")
    print(f"=== MULTI-SERVO RESULTS ({elapsed:.1f}s) ===")
    print(f"{'='*50}")
    print(f"Total moves:  {moves}")
    print(f"Errors:       {errors}")
    print(f"Moves/sec:    {moves/elapsed:.1f}")

    if errors == 0:
        print("\nVERDICT: ✅ PASS — 3 servos stable on Pi 5V")
        print("(But watch for physical stutter — if servos were jerky, brownout is happening)")
    else:
        print(f"\nVERDICT: ❌ FAIL — {errors} errors, likely brownout")
        print("ACTION: Connect external 5V UBEC to PCA9685 V+ screw terminal")

    return 0 if errors == 0 else 1

if __name__ == "__main__":
    sys.exit(main())
