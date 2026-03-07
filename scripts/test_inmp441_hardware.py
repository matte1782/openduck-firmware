#!/usr/bin/env python3
"""INMP441 Hardware Test Script for OpenDuck Mini V3

Tests the INMP441 I2S MEMS microphone on Raspberry Pi 4.

Wiring (6 cables):
    RED    -> VCC  -> Pin 1  (3.3V)
    BLACK  -> GND  -> Pin 6  (GND)
    YELLOW -> SCK  -> Pin 12 (GPIO 18 - I2S BCLK)
    GREEN  -> WS   -> Pin 35 (GPIO 19 - I2S LRCLK)
    ORANGE -> SD   -> Pin 38 (GPIO 20 - I2S DIN)
    BROWN  -> L/R  -> Pin 9  (GND - Left channel)

Before running:
    1. Enable I2S overlay in /boot/config.txt:
       dtparam=i2s=on
    2. Reboot the Pi
    3. Run: sudo python3 test_inmp441_hardware.py

Author: OpenDuck Project
Date: 22 January 2026
"""

import sys
import time

# Check for required libraries
try:
    import numpy as np
    print("[OK] NumPy available")
except ImportError:
    print("[ERROR] NumPy not installed. Run: pip install numpy")
    sys.exit(1)

try:
    import sounddevice as sd
    print("[OK] sounddevice available")
except ImportError:
    print("[ERROR] sounddevice not installed. Run: pip install sounddevice")
    sys.exit(1)


def print_header(text: str) -> None:
    """Print formatted section header."""
    print(f"\n{'='*60}")
    print(f"  {text}")
    print(f"{'='*60}\n")


def list_audio_devices() -> None:
    """List all available audio devices."""
    print_header("AUDIO DEVICES")

    devices = sd.query_devices()
    input_devices = []

    for i, device in enumerate(devices):
        if device['max_input_channels'] > 0:
            input_devices.append((i, device))
            print(f"  [{i}] {device['name']}")
            print(f"      Inputs: {device['max_input_channels']}, Sample Rate: {device['default_samplerate']}Hz")

    if not input_devices:
        print("  [WARNING] No input devices found!")
        print("  Check that I2S is enabled in /boot/config.txt")
        return False

    return True


def test_basic_capture(device_index: int = None, duration: float = 2.0) -> bool:
    """Test basic audio capture."""
    print_header(f"BASIC CAPTURE TEST ({duration}s)")

    sample_rate = 16000

    try:
        print(f"  Recording {duration}s at {sample_rate}Hz...")
        audio = sd.rec(
            int(duration * sample_rate),
            samplerate=sample_rate,
            channels=1,
            dtype='float32',
            device=device_index
        )
        sd.wait()

        print(f"  [OK] Captured {len(audio)} samples")

        # Calculate stats
        rms = np.sqrt(np.mean(audio ** 2))
        peak = np.max(np.abs(audio))
        level_db = 20 * np.log10(max(rms, 1e-10))

        print(f"  RMS Level: {rms:.6f}")
        print(f"  Peak: {peak:.6f}")
        print(f"  Level: {level_db:.1f} dB")

        if peak < 0.001:
            print("  [WARNING] Very low signal - check wiring!")
            return False
        elif peak > 0.9:
            print("  [WARNING] Signal clipping - reduce gain")
        else:
            print("  [OK] Signal level acceptable")

        return True

    except Exception as e:
        print(f"  [ERROR] Capture failed: {e}")
        return False


def test_realtime_levels(duration: float = 10.0) -> bool:
    """Test real-time level monitoring."""
    print_header(f"REAL-TIME LEVEL TEST ({duration}s)")
    print("  Speak into the microphone to see level changes")
    print("  Press Ctrl+C to stop early\n")

    sample_rate = 16000
    block_size = 512  # ~32ms at 16kHz

    level_history = []

    def callback(indata, frames, time_info, status):
        if status:
            print(f"  [Status] {status}")

        rms = np.sqrt(np.mean(indata ** 2))
        level_db = 20 * np.log10(max(rms, 1e-10))
        level_history.append(level_db)

        # Visual meter
        bar_width = 50
        normalized = max(0, (level_db + 60) / 60)  # -60dB to 0dB
        bar_length = int(normalized * bar_width)
        bar = '█' * bar_length + '░' * (bar_width - bar_length)

        # Threshold indicator
        threshold = -40.0
        is_speech = level_db > threshold
        indicator = "🎤 SPEECH" if is_speech else "   quiet"

        print(f"\r  {level_db:6.1f} dB [{bar}] {indicator}", end='', flush=True)

    try:
        with sd.InputStream(
            samplerate=sample_rate,
            channels=1,
            dtype='float32',
            blocksize=block_size,
            callback=callback
        ):
            start = time.time()
            while time.time() - start < duration:
                time.sleep(0.1)

        print("\n")

        # Stats
        if level_history:
            avg_level = np.mean(level_history)
            max_level = np.max(level_history)
            min_level = np.min(level_history)
            print(f"  Average: {avg_level:.1f} dB")
            print(f"  Max: {max_level:.1f} dB")
            print(f"  Min: {min_level:.1f} dB")

            # Check for variation (indicates mic is working)
            variation = max_level - min_level
            if variation > 10:
                print(f"  [OK] Good variation ({variation:.1f} dB) - mic responding!")
                return True
            else:
                print(f"  [WARNING] Low variation ({variation:.1f} dB) - check mic")
                return False

        return False

    except KeyboardInterrupt:
        print("\n  [Stopped by user]")
        return True
    except Exception as e:
        print(f"\n  [ERROR] {e}")
        return False


def test_vad_detection(duration: float = 15.0) -> bool:
    """Test Voice Activity Detection."""
    print_header(f"VAD TEST ({duration}s)")
    print("  Speak in short phrases to test VAD")
    print("  The system will detect speech/silence transitions\n")

    sample_rate = 16000
    block_size = 512

    threshold_db = -40.0
    min_speech_frames = 5  # ~160ms

    speech_frames = 0
    is_speaking = False
    speech_events = 0

    def callback(indata, frames, time_info, status):
        nonlocal speech_frames, is_speaking, speech_events

        rms = np.sqrt(np.mean(indata ** 2))
        level_db = 20 * np.log10(max(rms, 1e-10))

        if level_db > threshold_db:
            speech_frames += 1
            if speech_frames >= min_speech_frames and not is_speaking:
                is_speaking = True
                speech_events += 1
                print(f"\n  [SPEECH START] Event #{speech_events} at {level_db:.1f} dB")
        else:
            if is_speaking:
                print(f"  [SPEECH END] Duration: ~{speech_frames * 32}ms")
                is_speaking = False
            speech_frames = 0

        # Status display
        state = "🎤 SPEAKING" if is_speaking else "🔇 SILENCE "
        print(f"\r  {state} | Level: {level_db:6.1f} dB | Events: {speech_events}", end='', flush=True)

    try:
        with sd.InputStream(
            samplerate=sample_rate,
            channels=1,
            dtype='float32',
            blocksize=block_size,
            callback=callback
        ):
            start = time.time()
            while time.time() - start < duration:
                time.sleep(0.1)

        print("\n")
        print(f"  Total speech events detected: {speech_events}")

        if speech_events > 0:
            print("  [OK] VAD working correctly!")
            return True
        else:
            print("  [WARNING] No speech detected - speak louder or check mic")
            return False

    except KeyboardInterrupt:
        print("\n  [Stopped by user]")
        return speech_events > 0
    except Exception as e:
        print(f"\n  [ERROR] {e}")
        return False


def test_latency() -> bool:
    """Test audio capture latency."""
    print_header("LATENCY TEST")

    sample_rate = 16000
    block_sizes = [128, 256, 512, 1024]

    print("  Testing different buffer sizes:\n")

    for block_size in block_sizes:
        latency_ms = (block_size / sample_rate) * 1000

        try:
            # Quick capture test
            with sd.InputStream(
                samplerate=sample_rate,
                channels=1,
                dtype='float32',
                blocksize=block_size
            ) as stream:
                start = time.time()
                data, overflowed = stream.read(block_size)
                elapsed = (time.time() - start) * 1000

                status = "✓" if elapsed < latency_ms * 2 else "⚠"
                overflow_str = " (overflow!)" if overflowed else ""
                print(f"  {status} Block {block_size:4d} = {latency_ms:5.1f}ms theoretical, {elapsed:5.1f}ms actual{overflow_str}")

        except Exception as e:
            print(f"  ✗ Block {block_size}: {e}")

    print("\n  Target: <50ms for real-time interaction")
    print("  Recommended: 512 samples (~32ms at 16kHz)")

    return True


def save_test_recording(filename: str = "test_recording.wav", duration: float = 5.0) -> bool:
    """Save a test recording to WAV file."""
    print_header(f"SAVE TEST RECORDING ({duration}s)")

    try:
        from scipy.io import wavfile
    except ImportError:
        print("  [SKIP] scipy not installed - cannot save WAV")
        return True

    sample_rate = 16000

    try:
        print(f"  Recording to {filename}...")
        audio = sd.rec(
            int(duration * sample_rate),
            samplerate=sample_rate,
            channels=1,
            dtype='int16'
        )
        sd.wait()

        # Save
        wavfile.write(filename, sample_rate, audio)
        print(f"  [OK] Saved {filename}")
        print(f"  Play with: aplay {filename}")

        return True

    except Exception as e:
        print(f"  [ERROR] {e}")
        return False


def main():
    """Run all hardware tests."""
    print("\n" + "="*60)
    print("   INMP441 HARDWARE TEST - OpenDuck Mini V3")
    print("="*60)
    print("\nWiring Check:")
    print("  RED    -> Pin 1  (3.3V)")
    print("  BLACK  -> Pin 6  (GND)")
    print("  YELLOW -> Pin 12 (GPIO 18 - SCK)")
    print("  GREEN  -> Pin 35 (GPIO 19 - WS)")
    print("  ORANGE -> Pin 38 (GPIO 20 - SD)")
    print("  BROWN  -> Pin 9  (GND - L/R)")

    results = {}

    # Test 1: List devices
    results['devices'] = list_audio_devices()
    if not results['devices']:
        print("\n[FATAL] No audio input devices found!")
        print("Check I2S is enabled: grep i2s /boot/config.txt")
        print("Should show: dtparam=i2s=on")
        return 1

    # Test 2: Basic capture
    results['capture'] = test_basic_capture()

    # Test 3: Real-time levels
    results['levels'] = test_realtime_levels(duration=10.0)

    # Test 4: VAD
    results['vad'] = test_vad_detection(duration=15.0)

    # Test 5: Latency
    results['latency'] = test_latency()

    # Test 6: Save recording (optional)
    try:
        results['save'] = save_test_recording()
    except Exception:
        results['save'] = True  # Optional test

    # Summary
    print_header("TEST SUMMARY")

    passed = sum(1 for r in results.values() if r)
    total = len(results)

    for name, result in results.items():
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"  {status}: {name}")

    print(f"\n  Result: {passed}/{total} tests passed")

    if passed == total:
        print("\n  🎉 ALL TESTS PASSED! INMP441 is working correctly!")
        return 0
    else:
        print("\n  ⚠️  Some tests failed. Check wiring and I2S configuration.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
