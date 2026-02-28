#!/usr/bin/env python3
"""Day 46 Phase 5: Full Integration Test
All components running simultaneously:
- 5× MG90S via PCA9685 (I2C @ 0x40)
- BNO085 IMU (I2C @ 0x4a)
- INMP441 Microphone (I2S @ plughw:3,0)
- IMX500 Camera (CSI)
Tests for bus contention, power issues, and data corruption.
"""
import time
import threading
import subprocess
import struct
import io
import sys

# Stats
stats = {
    "servo_moves": 0,
    "servo_errors": 0,
    "imu_reads": 0,
    "imu_errors": 0,
    "audio_ok": False,
    "camera_ok": False,
}
running = True
DURATION = 30


def servo_loop():
    global running
    from adafruit_servokit import ServoKit
    try:
        kit = ServoKit(channels=16)
        print("[SERVO] 5× MG90S initialized on ch0-4")
    except Exception as e:
        print(f"[SERVO] INIT FAILED: {e}")
        stats["servo_errors"] += 1
        return

    channels = [0, 1, 2, 3, 4]
    angles = {0: 0, 1: 36, 2: 72, 3: 108, 4: 144}
    dirs = {ch: 1 for ch in channels}

    while running:
        for ch in channels:
            try:
                kit.servo[ch].angle = angles[ch]
                stats["servo_moves"] += 1
            except Exception as e:
                stats["servo_errors"] += 1
            angles[ch] += 5 * dirs[ch]
            if angles[ch] >= 180:
                angles[ch] = 180
                dirs[ch] = -1
            elif angles[ch] <= 0:
                angles[ch] = 0
                dirs[ch] = 1
        time.sleep(0.05)

    for ch in channels:
        try:
            kit.servo[ch].angle = None
        except:
            pass


def imu_loop():
    global running
    import board
    import busio
    from adafruit_bno08x.i2c import BNO08X_I2C
    from adafruit_bno08x import BNO_REPORT_ROTATION_VECTOR

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
                mag = sum(q * q for q in quat) ** 0.5
                if abs(mag - 1.0) > 0.5:
                    stats["imu_errors"] += 1
            time.sleep(0.02)
        except Exception as e:
            stats["imu_errors"] += 1
            time.sleep(0.1)


def audio_loop():
    try:
        result = subprocess.run(
            ["arecord", "-D", "plughw:3,0", "-f", "S32_LE", "-r", "48000",
             "-c", "1", "-d", str(DURATION), "/tmp/integration_audio.wav"],
            capture_output=True, text=True, timeout=DURATION + 10
        )
        if result.returncode == 0:
            stats["audio_ok"] = True
            print("[AUDIO] Recording complete")
        else:
            print(f"[AUDIO] FAILED: {result.stderr[:100]}")
    except Exception as e:
        print(f"[AUDIO] EXCEPTION: {e}")


def camera_loop():
    try:
        from picamera2 import Picamera2
        picam2 = Picamera2()
        config = picam2.create_preview_configuration(main={"size": (640, 480), "format": "RGB888"})
        picam2.configure(config)
        picam2.start()
        print("[CAMERA] IMX500 started @ 640x480")

        frames = 0
        while running:
            buf = io.BytesIO()
            picam2.capture_file(buf, format='jpeg')
            frames += 1
            time.sleep(0.1)  # 10 FPS

        picam2.stop()
        stats["camera_ok"] = True
        print(f"[CAMERA] Captured {frames} frames")
    except Exception as e:
        print(f"[CAMERA] EXCEPTION: {e}")


def main():
    global running
    print("=" * 60)
    print("  FULL INTEGRATION TEST — OpenDuck Mini V3")
    print("=" * 60)
    print(f"Duration: {DURATION}s")
    print("Components: 5× MG90S + BNO085 + INMP441 + IMX500")
    print()

    threads = [
        threading.Thread(target=servo_loop, daemon=True, name="servo"),
        threading.Thread(target=imu_loop, daemon=True, name="imu"),
        threading.Thread(target=audio_loop, daemon=True, name="audio"),
        threading.Thread(target=camera_loop, daemon=True, name="camera"),
    ]

    for t in threads:
        t.start()

    start = time.time()
    try:
        while time.time() - start < DURATION + 2:
            elapsed = time.time() - start
            print(
                f"[{elapsed:5.1f}s] "
                f"servo={stats['servo_moves']}(e{stats['servo_errors']}) "
                f"imu={stats['imu_reads']}(e{stats['imu_errors']}) "
                f"audio={'REC' if not stats['audio_ok'] else 'OK'} "
                f"cam={'RUN' if not stats['camera_ok'] else 'OK'}",
                end="\r",
            )
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nInterrupted")

    running = False
    time.sleep(2)

    # Audio analysis
    audio_clean = False
    try:
        import wave
        with wave.open("/tmp/integration_audio.wav", 'rb') as wf:
            frames = wf.readframes(wf.getnframes())
            n = len(frames) // 4
            if n > 0:
                samples = struct.unpack(f"<{n}i", frames)
                max_amp = max(abs(s) for s in samples)
                zeros = sum(1 for s in samples if s == 0)
                zero_pct = (zeros / n) * 100
                audio_clean = zero_pct < 90 and max_amp > 1000
    except:
        pass

    # Report
    elapsed = time.time() - start
    print(f"\n\n{'=' * 60}")
    print(f"  INTEGRATION TEST RESULTS ({elapsed:.1f}s)")
    print(f"{'=' * 60}")
    print()
    print(f"  SERVO (5× MG90S via PCA9685)")
    print(f"    Moves:  {stats['servo_moves']}")
    print(f"    Errors: {stats['servo_errors']}")
    print(f"    Status: {'PASS' if stats['servo_errors'] == 0 else 'FAIL'}")
    print()
    print(f"  IMU (BNO085 @ 0x4a)")
    print(f"    Reads:  {stats['imu_reads']}")
    print(f"    Errors: {stats['imu_errors']} (corruption >0.5 mag)")
    err_rate = (stats['imu_errors'] / max(stats['imu_reads'], 1)) * 100
    print(f"    Rate:   {err_rate:.1f}%")
    print(f"    Status: {'PASS' if err_rate < 5 else 'FAIL'}")
    print()
    print(f"  AUDIO (INMP441 @ I2S)")
    print(f"    Recorded: {'YES' if stats['audio_ok'] else 'NO'}")
    print(f"    Clean:    {'YES' if audio_clean else 'NO'}")
    print(f"    Status:   {'PASS' if stats['audio_ok'] and audio_clean else 'FAIL'}")
    print()
    print(f"  CAMERA (IMX500 @ CSI)")
    print(f"    Status: {'PASS' if stats['camera_ok'] else 'FAIL'}")
    print()

    all_pass = (
        stats['servo_errors'] == 0
        and err_rate < 5
        and stats['audio_ok']
        and audio_clean
        and stats['camera_ok']
    )

    print(f"{'=' * 60}")
    if all_pass:
        print("  VERDICT: ✅ ALL SYSTEMS GO — OpenDuck Mini hardware validated!")
    else:
        fails = []
        if stats['servo_errors'] > 0: fails.append("SERVO")
        if err_rate >= 5: fails.append("IMU")
        if not (stats['audio_ok'] and audio_clean): fails.append("AUDIO")
        if not stats['camera_ok']: fails.append("CAMERA")
        print(f"  VERDICT: ❌ ISSUES IN: {', '.join(fails)}")
    print(f"{'=' * 60}")

    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())
