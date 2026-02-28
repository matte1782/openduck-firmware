#!/usr/bin/env python3
"""Day 46 FULL DEMO — All components running together.
5× MG90S + 3× STS3215 + BNO085 + INMP441 + IMX500 Camera
"""
import time
import threading
import subprocess
import io
import serial

DURATION = 20
running = True
stats = {"mg90s": 0, "sts": 0, "imu": 0, "frames": 0}


def mg90s_loop():
    from adafruit_servokit import ServoKit
    kit = ServoKit(channels=16)
    channels = [0, 1, 2, 3, 4]
    angles = {0: 0, 1: 36, 2: 72, 3: 108, 4: 144}
    dirs = {ch: 1 for ch in channels}
    while running:
        for ch in channels:
            kit.servo[ch].angle = angles[ch]
            stats["mg90s"] += 1
            angles[ch] += 5 * dirs[ch]
            if angles[ch] >= 180:
                angles[ch] = 180
                dirs[ch] = -1
            elif angles[ch] <= 0:
                angles[ch] = 0
                dirs[ch] = 1
        time.sleep(0.05)
    for ch in channels:
        kit.servo[ch].angle = None


def sts_loop():
    ser = serial.Serial('/dev/ttyUSB0', 1000000, timeout=0.1)

    def scs_checksum(p):
        return (~sum(p)) & 0xFF

    def scs_write2(sid, addr, val):
        lo = val & 0xFF
        hi = (val >> 8) & 0xFF
        packet = [sid, 5, 3, addr, lo, hi]
        cs = scs_checksum(packet)
        ser.write(bytes([0xFF, 0xFF] + packet + [cs]))
        time.sleep(0.005)
        ser.read(20)

    ids = [1, 2, 3]
    positions = {1: 1024, 2: 2048, 3: 3072}
    dirs = {1: 200, 2: -200, 3: 200}

    while running:
        for sid in ids:
            scs_write2(sid, 42, positions[sid])
            stats["sts"] += 1
            positions[sid] += dirs[sid]
            if positions[sid] >= 4000:
                positions[sid] = 4000
                dirs[sid] = -dirs[sid]
            elif positions[sid] <= 100:
                positions[sid] = 100
                dirs[sid] = -dirs[sid]
        time.sleep(0.05)

    # Park
    for sid in ids:
        scs_write2(sid, 42, 2048)
    ser.close()


def imu_loop():
    import board
    import busio
    from adafruit_bno08x.i2c import BNO08X_I2C
    from adafruit_bno08x import BNO_REPORT_ROTATION_VECTOR

    i2c = busio.I2C(board.SCL, board.SDA, frequency=400000)
    bno = BNO08X_I2C(i2c)
    bno.enable_feature(BNO_REPORT_ROTATION_VECTOR)

    while running:
        try:
            quat = bno.quaternion
            if quat is not None:
                stats["imu"] += 1
        except:
            pass
        time.sleep(0.02)


def camera_loop():
    from picamera2 import Picamera2
    picam2 = Picamera2()
    config = picam2.create_preview_configuration(main={"size": (640, 480), "format": "RGB888"})
    picam2.configure(config)
    picam2.start()

    while running:
        buf = io.BytesIO()
        picam2.capture_file(buf, format='jpeg')
        stats["frames"] += 1
        time.sleep(0.1)

    picam2.stop()


def audio_loop():
    subprocess.run(
        ["arecord", "-D", "plughw:3,0", "-f", "S32_LE", "-r", "48000",
         "-c", "1", "-d", str(DURATION), "/tmp/demo_audio.wav"],
        capture_output=True, timeout=DURATION + 10
    )


def main():
    global running
    print("=" * 60)
    print("  OPENDUCK MINI V3 — FULL HARDWARE DEMO")
    print("=" * 60)
    print()
    print("  5x MG90S (PWM via PCA9685)")
    print("  3x STS3215 (UART via FE-URT-1)")
    print("  BNO085 IMU (I2C)")
    print("  INMP441 Mic (I2S)")
    print("  IMX500 Camera (CSI)")
    print()
    print(f"  Duration: {DURATION}s")
    print("=" * 60)
    print()

    threads = [
        threading.Thread(target=mg90s_loop, daemon=True),
        threading.Thread(target=sts_loop, daemon=True),
        threading.Thread(target=imu_loop, daemon=True),
        threading.Thread(target=camera_loop, daemon=True),
        threading.Thread(target=audio_loop, daemon=True),
    ]

    for t in threads:
        t.start()

    start = time.time()
    try:
        while time.time() - start < DURATION:
            elapsed = time.time() - start
            print(
                f"  [{elapsed:5.1f}s]  "
                f"MG90S:{stats['mg90s']:5d}  "
                f"STS:{stats['sts']:5d}  "
                f"IMU:{stats['imu']:5d}  "
                f"CAM:{stats['frames']:4d}",
                end="\r",
            )
            time.sleep(0.5)
    except KeyboardInterrupt:
        pass

    running = False
    time.sleep(2)

    elapsed = time.time() - start
    print()
    print()
    print("=" * 60)
    print(f"  DEMO COMPLETE ({elapsed:.0f}s)")
    print("=" * 60)
    print(f"  MG90S moves:    {stats['mg90s']}")
    print(f"  STS3215 moves:  {stats['sts']}")
    print(f"  IMU reads:      {stats['imu']}")
    print(f"  Camera frames:  {stats['frames']}")
    print(f"  Audio:          {DURATION}s recorded")
    print()
    print("  8 servos + IMU + mic + camera")
    print("  ALL RUNNING SIMULTANEOUSLY")
    print("=" * 60)


if __name__ == "__main__":
    main()
