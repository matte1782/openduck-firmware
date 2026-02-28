#!/usr/bin/env python3
"""Day 46 Phase 1: I2C Bus Stress Test
PCA9685 servo sweep + BNO085 quaternion reads simultaneously on bus 1.
Tests for bus contention, data corruption, and lockups.
"""
import time
import threading
import sys

# --- PCA9685 + Servo ---
from adafruit_servokit import ServoKit

# --- BNO085 ---
import board
import busio
from adafruit_bno08x.i2c import BNO08X_I2C
from adafruit_bno08x import BNO_REPORT_ROTATION_VECTOR

DURATION = 60  # seconds
SERVO_CHANNEL = 0

# Shared stats
stats = {
    "servo_moves": 0,
    "servo_errors": 0,
    "imu_reads": 0,
    "imu_errors": 0,
    "imu_last_quat": None,
}
running = True


def servo_loop():
    """Continuously sweep servo 0-180-0 on PCA9685."""
    global running
    try:
        kit = ServoKit(channels=16)
        print("[SERVO] ServoKit initialized @ 0x40")
    except Exception as e:
        print(f"[SERVO] INIT FAILED: {e}")
        stats["servo_errors"] += 1
        return

    angle = 0
    direction = 1  # 1=up, -1=down
    step = 5

    while running:
        try:
            kit.servo[SERVO_CHANNEL].angle = angle
            stats["servo_moves"] += 1
            angle += step * direction
            if angle >= 180:
                angle = 180
                direction = -1
            elif angle <= 0:
                angle = 0
                direction = 1
            time.sleep(0.05)  # 20Hz sweep
        except Exception as e:
            stats["servo_errors"] += 1
            print(f"[SERVO] ERROR at move {stats['servo_moves']}: {e}")
            time.sleep(0.1)


def imu_loop():
    """Continuously read quaternions from BNO085."""
    global running
    try:
        i2c = busio.I2C(board.SCL, board.SDA, frequency=400000)
        bno = BNO08X_I2C(i2c)
        bno.enable_feature(BNO_REPORT_ROTATION_VECTOR)
        print("[IMU] BNO085 initialized @ 0x4a")
    except Exception as e:
        print(f"[IMU] INIT FAILED: {e}")
        stats["imu_errors"] += 1
        return

    while running:
        try:
            quat = bno.quaternion
            if quat is not None:
                stats["imu_reads"] += 1
                stats["imu_last_quat"] = quat
                # Sanity check: quaternion magnitude should be ~1.0
                mag = sum(q * q for q in quat) ** 0.5
                if abs(mag - 1.0) > 0.15:
                    stats["imu_warnings"] += 1
                    if abs(mag - 1.0) > 0.5:
                        stats["imu_corrupted"] += 1
                        print(f"[IMU] CORRUPTED: quat magnitude {mag:.3f} (expected ~1.0)")
            time.sleep(0.02)  # 50Hz read
        except Exception as e:
            stats["imu_errors"] += 1
            print(f"[IMU] ERROR at read {stats['imu_reads']}: {e}")
            time.sleep(0.1)


def main():
    global running
    print(f"=== I2C Bus Stress Test ===")
    print(f"Duration: {DURATION}s")
    print(f"PCA9685 @ 0x40 — servo sweep ch{SERVO_CHANNEL}")
    print(f"BNO085  @ 0x4a — quaternion reads")
    print(f"Starting...\n")

    t_servo = threading.Thread(target=servo_loop, daemon=True)
    t_imu = threading.Thread(target=imu_loop, daemon=True)

    t_servo.start()
    t_imu.start()

    start = time.time()
    try:
        while time.time() - start < DURATION:
            elapsed = time.time() - start
            q = stats["imu_last_quat"]
            qstr = f"({q[0]:.2f},{q[1]:.2f},{q[2]:.2f},{q[3]:.2f})" if q else "waiting..."
            print(
                f"[{elapsed:5.1f}s] servo_moves={stats['servo_moves']} "
                f"imu_reads={stats['imu_reads']} "
                f"servo_err={stats['servo_errors']} "
                f"imu_err={stats['imu_errors']} "
                f"quat={qstr}",
                end="\r",
            )
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")

    running = False
    time.sleep(0.5)

    # Final report
    elapsed = time.time() - start
    print(f"\n\n{'='*50}")
    print(f"=== STRESS TEST RESULTS ({elapsed:.1f}s) ===")
    print(f"{'='*50}")
    print(f"Servo moves:  {stats['servo_moves']}")
    print(f"Servo errors: {stats['servo_errors']}")
    print(f"IMU reads:    {stats['imu_reads']}")
    print(f"IMU errors:   {stats['imu_errors']}")

    total_ops = stats["servo_moves"] + stats["imu_reads"]
    total_err = stats["servo_errors"] + stats["imu_errors"]
    if total_ops > 0:
        error_rate = (total_err / total_ops) * 100
        print(f"Error rate:   {error_rate:.3f}%")
    else:
        print("Error rate:   N/A (no operations)")

    if total_err == 0:
        print("\nVERDICT: ✅ PASS — I2C bus stable under concurrent load")
    elif total_err < 5:
        print(f"\nVERDICT: ⚠️  MARGINAL — {total_err} errors, may need investigation")
    else:
        print(f"\nVERDICT: ❌ FAIL — {total_err} errors, bus contention confirmed")

    return 0 if total_err == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
