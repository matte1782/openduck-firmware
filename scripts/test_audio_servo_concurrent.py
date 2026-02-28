#!/usr/bin/env python3
"""Day 46 Phase 3: Audio + Servo Concurrent Test
INMP441 recording while 3x MG90S sweep on PCA9685.
Checks for I2S audio corruption caused by I2C servo traffic.
"""
import time
import threading
import subprocess
import struct
import sys

from adafruit_servokit import ServoKit

CHANNELS = [0, 1, 2]
DURATION = 15  # seconds
AUDIO_FILE = "/tmp/phase3_test.wav"

stats = {
    "servo_moves": 0,
    "servo_errors": 0,
    "audio_ok": False,
    "audio_error": None,
}
running = True


def servo_loop():
    global running
    try:
        kit = ServoKit(channels=16)
        print("[SERVO] Initialized")
    except Exception as e:
        print(f"[SERVO] INIT FAILED: {e}")
        stats["servo_errors"] += 1
        return

    angles = {0: 0, 1: 60, 2: 120}
    dirs = {0: 1, 1: 1, 2: -1}

    while running:
        for ch in CHANNELS:
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

    # Park and disable
    for ch in CHANNELS:
        try:
            kit.servo[ch].angle = None
        except:
            pass


def record_audio():
    """Record audio using arecord while servos move."""
    try:
        result = subprocess.run(
            ["arecord", "-D", "plughw:3,0", "-f", "S32_LE", "-r", "48000",
             "-c", "1", "-d", str(DURATION), AUDIO_FILE],
            capture_output=True, text=True, timeout=DURATION + 10
        )
        if result.returncode == 0:
            stats["audio_ok"] = True
            print(f"[AUDIO] Recording saved: {AUDIO_FILE}")
        else:
            stats["audio_error"] = result.stderr
            print(f"[AUDIO] FAILED: {result.stderr}")
    except Exception as e:
        stats["audio_error"] = str(e)
        print(f"[AUDIO] EXCEPTION: {e}")


def analyze_audio():
    """Check recorded audio for silence or corruption."""
    try:
        import wave
        with wave.open(AUDIO_FILE, 'rb') as wf:
            frames = wf.readframes(wf.getnframes())
            n_samples = len(frames) // 4  # S32_LE = 4 bytes
            if n_samples == 0:
                print("[ANALYSIS] No samples recorded!")
                return False

            # Read as 32-bit signed integers
            samples = struct.unpack(f"<{n_samples}i", frames)

            # Stats
            max_val = max(abs(s) for s in samples)
            avg_val = sum(abs(s) for s in samples) // n_samples
            zero_count = sum(1 for s in samples if s == 0)
            zero_pct = (zero_count / n_samples) * 100

            print(f"[ANALYSIS] Samples: {n_samples}")
            print(f"[ANALYSIS] Max amplitude: {max_val}")
            print(f"[ANALYSIS] Avg amplitude: {avg_val}")
            print(f"[ANALYSIS] Zero samples: {zero_count} ({zero_pct:.1f}%)")
            print(f"[ANALYSIS] Duration: {n_samples/48000:.1f}s")

            if zero_pct > 90:
                print("[ANALYSIS] WARNING: >90% zeros — possible dead mic or wiring issue")
                return False
            if max_val < 1000:
                print("[ANALYSIS] WARNING: Very low amplitude — mic may not be capturing")
                return False
            return True
    except Exception as e:
        print(f"[ANALYSIS] Error: {e}")
        return False


def main():
    global running
    print("=== Audio + Servo Concurrent Test ===")
    print(f"Duration: {DURATION}s")
    print(f"Servos: channels {CHANNELS}")
    print(f"Audio: INMP441 @ plughw:3,0")
    print()

    t_servo = threading.Thread(target=servo_loop, daemon=True)
    t_audio = threading.Thread(target=record_audio, daemon=True)

    t_servo.start()
    t_audio.start()

    start = time.time()
    try:
        while time.time() - start < DURATION + 2:
            elapsed = time.time() - start
            print(
                f"[{elapsed:5.1f}s] servo_moves={stats['servo_moves']} "
                f"servo_err={stats['servo_errors']} "
                f"audio={'recording...' if not stats['audio_ok'] else 'done'}",
                end="\r",
            )
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nInterrupted")

    running = False
    t_audio.join(timeout=5)
    time.sleep(0.5)

    # Analyze
    print("\n")
    audio_clean = analyze_audio()

    # Final report
    elapsed = time.time() - start
    print(f"\n{'='*50}")
    print(f"=== PHASE 3 RESULTS ({elapsed:.1f}s) ===")
    print(f"{'='*50}")
    print(f"Servo moves:  {stats['servo_moves']}")
    print(f"Servo errors: {stats['servo_errors']}")
    print(f"Audio recorded: {'YES' if stats['audio_ok'] else 'NO'}")
    print(f"Audio clean:    {'YES' if audio_clean else 'NO'}")

    if stats['servo_errors'] == 0 and stats['audio_ok'] and audio_clean:
        print("\nVERDICT: ✅ PASS — Audio + Servo concurrent OK")
    else:
        issues = []
        if stats['servo_errors'] > 0:
            issues.append(f"{stats['servo_errors']} servo errors")
        if not stats['audio_ok']:
            issues.append("audio recording failed")
        if not audio_clean:
            issues.append("audio may be corrupted")
        print(f"\nVERDICT: ❌ FAIL — {', '.join(issues)}")

    return 0 if (stats['servo_errors'] == 0 and stats['audio_ok'] and audio_clean) else 1


if __name__ == "__main__":
    sys.exit(main())
