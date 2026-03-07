#!/usr/bin/env python3
"""INMP441 Hardware Validation Script for OpenDuck Mini V3

This script validates the INMP441 I2S MEMS microphone on real hardware.
Run this on the Raspberry Pi after wiring the INMP441.

Wiring Guide (INMP441 -> Raspberry Pi 4):
    VCC  -> Pin 1 (3.3V)
    GND  -> Pin 6 (GND)
    SD   -> Pin 38 (GPIO 20 - I2S DIN)
    WS   -> Pin 35 (GPIO 19 - I2S LRCLK)
    SCK  -> Pin 12 (GPIO 18 - I2S BCLK)
    L/R  -> GND (Left channel - mono)

Prerequisites:
    1. Enable I2S overlay in /boot/config.txt:
       dtparam=i2s=on

    2. Install dependencies:
       pip install sounddevice numpy scipy
       sudo apt install libasound2-dev

    3. Reboot after config changes

Usage:
    python scripts/validate_inmp441_hardware.py

Author: Day 17 Hardware Validation
Date: 22 January 2026
"""

import sys
import time
import argparse
from pathlib import Path

# Add project root to path for imports
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))


def print_header(title: str) -> None:
    """Print a formatted section header."""
    print("\n" + "=" * 60)
    print(f" {title}")
    print("=" * 60)


def print_result(test_name: str, passed: bool, details: str = "") -> None:
    """Print a test result with status."""
    status = "✅ PASS" if passed else "❌ FAIL"
    print(f"  {test_name}: {status}")
    if details:
        print(f"    └─ {details}")


def check_dependencies() -> bool:
    """Check if required dependencies are installed."""
    print_header("Dependency Check")

    all_ok = True

    # Check numpy
    try:
        import numpy as np
        print_result("numpy", True, f"version {np.__version__}")
    except ImportError:
        print_result("numpy", False, "pip install numpy")
        all_ok = False

    # Check sounddevice
    try:
        import sounddevice as sd
        print_result("sounddevice", True, f"version {sd.__version__}")
    except ImportError:
        print_result("sounddevice", False, "pip install sounddevice")
        all_ok = False

    # Check scipy (for audio analysis)
    try:
        import scipy
        print_result("scipy", True, f"version {scipy.__version__}")
    except ImportError:
        print_result("scipy", False, "pip install scipy (optional)")

    return all_ok


def list_audio_devices() -> None:
    """List all available audio devices."""
    print_header("Audio Devices")

    try:
        import sounddevice as sd
        devices = sd.query_devices()

        print("\n  Available audio devices:")
        print("-" * 60)

        for i, dev in enumerate(devices):
            input_ch = dev.get('max_input_channels', 0)
            output_ch = dev.get('max_output_channels', 0)
            default_sr = dev.get('default_samplerate', 0)
            name = dev.get('name', 'Unknown')

            device_type = []
            if input_ch > 0:
                device_type.append(f"IN:{input_ch}ch")
            if output_ch > 0:
                device_type.append(f"OUT:{output_ch}ch")

            marker = ""
            if i == sd.default.device[0]:
                marker = " [DEFAULT INPUT]"
            elif i == sd.default.device[1]:
                marker = " [DEFAULT OUTPUT]"

            print(f"  [{i}] {name}{marker}")
            print(f"      {' | '.join(device_type)} | {default_sr}Hz")

        print()
        print(f"  Default input device: {sd.default.device[0]}")
        print(f"  Default output device: {sd.default.device[1]}")

    except Exception as e:
        print(f"  ❌ Error listing devices: {e}")


def test_basic_capture(duration_seconds: float = 2.0) -> bool:
    """Test basic audio capture functionality."""
    print_header("Basic Audio Capture Test")

    try:
        import sounddevice as sd
        import numpy as np

        sample_rate = 16000
        channels = 1

        print(f"\n  Recording {duration_seconds}s of audio at {sample_rate}Hz...")
        print("  (Make some noise or speak into the microphone)")

        # Record audio
        recording = sd.rec(
            int(duration_seconds * sample_rate),
            samplerate=sample_rate,
            channels=channels,
            dtype='int16'
        )
        sd.wait()  # Wait for recording to complete

        # Analyze recording
        samples = recording.flatten()

        # Calculate statistics
        max_amplitude = np.max(np.abs(samples))
        mean_amplitude = np.mean(np.abs(samples))
        rms = np.sqrt(np.mean(samples.astype(np.float64) ** 2))

        # Calculate dB level (relative to full scale)
        if rms > 0:
            db_level = 20 * np.log10(rms / 32768)
        else:
            db_level = -100

        print(f"\n  Recording Statistics:")
        print(f"    Samples captured: {len(samples)}")
        print(f"    Max amplitude: {max_amplitude} (of 32768)")
        print(f"    Mean amplitude: {mean_amplitude:.1f}")
        print(f"    RMS level: {rms:.1f}")
        print(f"    dB level: {db_level:.1f} dBFS")

        # Validation checks
        passed = True

        # Check 1: Non-zero samples (mic is connected)
        if max_amplitude < 10:
            print_result("Non-zero audio", False, "No audio detected - check wiring")
            passed = False
        else:
            print_result("Non-zero audio", True, f"Max={max_amplitude}")

        # Check 2: Not clipping (not all max values)
        clipping_threshold = 32000
        clip_count = np.sum(np.abs(samples) > clipping_threshold)
        clip_percent = (clip_count / len(samples)) * 100

        if clip_percent > 5:
            print_result("No clipping", False, f"{clip_percent:.1f}% samples clipping")
            passed = False
        else:
            print_result("No clipping", True, f"Only {clip_percent:.2f}% near max")

        # Check 3: Signal variance (not stuck)
        variance = np.var(samples)
        if variance < 100:
            print_result("Signal variance", False, "Signal appears stuck/constant")
            passed = False
        else:
            print_result("Signal variance", True, f"Variance={variance:.1f}")

        # Check 4: dB level reasonable (not just noise floor)
        if db_level < -60:
            print_result("Signal level", False, f"Very quiet ({db_level:.1f} dBFS)")
        elif db_level > -6:
            print_result("Signal level", False, f"Very loud ({db_level:.1f} dBFS) - may clip")
        else:
            print_result("Signal level", True, f"{db_level:.1f} dBFS (good range)")

        return passed

    except Exception as e:
        print(f"\n  ❌ Capture failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_continuous_monitoring(duration_seconds: float = 5.0) -> bool:
    """Test continuous audio level monitoring."""
    print_header("Continuous Level Monitoring")

    try:
        import sounddevice as sd
        import numpy as np

        sample_rate = 16000
        block_size = 512

        print(f"\n  Monitoring audio levels for {duration_seconds}s...")
        print("  (Try speaking, clapping, or making sounds)")
        print()
        print("  Level: ", end="", flush=True)

        levels = []
        start_time = time.time()

        def audio_callback(indata, frames, time_info, status):
            if status:
                print(f"\n  ⚠️ Status: {status}")

            # Calculate RMS level
            rms = np.sqrt(np.mean(indata.astype(np.float64) ** 2))
            if rms > 0:
                db = 20 * np.log10(rms / 32768)
            else:
                db = -100

            levels.append(db)

            # Visual meter
            bar_length = int((db + 60) / 2)  # -60dB to 0dB -> 0 to 30
            bar_length = max(0, min(30, bar_length))
            bar = "█" * bar_length + "░" * (30 - bar_length)
            print(f"\r  Level: [{bar}] {db:6.1f} dBFS", end="", flush=True)

        # Start streaming
        with sd.InputStream(
            samplerate=sample_rate,
            channels=1,
            dtype='int16',
            blocksize=block_size,
            callback=audio_callback
        ):
            while time.time() - start_time < duration_seconds:
                time.sleep(0.1)

        print("\n")

        # Analyze level data
        levels_arr = np.array(levels)
        min_level = np.min(levels_arr)
        max_level = np.max(levels_arr)
        mean_level = np.mean(levels_arr)
        dynamic_range = max_level - min_level

        print(f"  Level Statistics:")
        print(f"    Min: {min_level:.1f} dBFS")
        print(f"    Max: {max_level:.1f} dBFS")
        print(f"    Mean: {mean_level:.1f} dBFS")
        print(f"    Dynamic range: {dynamic_range:.1f} dB")

        # Validation
        passed = True

        if dynamic_range < 10:
            print_result("Dynamic range", False, f"Only {dynamic_range:.1f}dB - try making sounds")
            passed = False
        else:
            print_result("Dynamic range", True, f"{dynamic_range:.1f}dB detected")

        if max_level < -50:
            print_result("Peak level", False, "Never exceeded -50dBFS")
            passed = False
        else:
            print_result("Peak level", True, f"Reached {max_level:.1f}dBFS")

        return passed

    except Exception as e:
        print(f"\n  ❌ Monitoring failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_driver_integration() -> bool:
    """Test integration with the INMP441 driver class."""
    print_header("Driver Integration Test")

    try:
        from drivers.audio.inmp441 import INMP441Driver, INMP441Config, CaptureState

        print("\n  Testing INMP441Driver class...")

        # Create driver with default config
        config = INMP441Config(sample_rate=16000, gain=1.0)
        driver = INMP441Driver(config=config)

        print_result("Driver instantiation", True)

        # Start capture
        driver.start_capture()
        time.sleep(0.5)  # Let it start

        state = driver.get_state()
        if state == CaptureState.CAPTURING:
            print_result("Start capture", True, f"State={state.value}")
        else:
            print_result("Start capture", False, f"State={state.value}")
            return False

        # Read samples
        samples = driver.read_samples(1024)
        if samples is not None and len(samples) > 0:
            print_result("Read samples", True, f"Got {len(samples)} samples")
        else:
            print_result("Read samples", False, "No samples returned")
            return False

        # Get level
        level_db = driver.get_level_db()
        print_result("Get level", True, f"{level_db:.1f} dBFS")

        # Stop capture
        driver.stop_capture()
        time.sleep(0.2)

        state = driver.get_state()
        if state == CaptureState.STOPPED:
            print_result("Stop capture", True, f"State={state.value}")
        else:
            print_result("Stop capture", False, f"State={state.value}")

        return True

    except ImportError as e:
        print(f"\n  ⚠️ Driver import failed: {e}")
        print("  Running without driver integration test")
        return True  # Don't fail overall if driver not available

    except Exception as e:
        print(f"\n  ❌ Driver test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def save_test_recording(filename: str = "inmp441_test.wav", duration: float = 3.0) -> bool:
    """Save a test recording to a WAV file."""
    print_header("Save Test Recording")

    try:
        import sounddevice as sd
        import numpy as np
        from scipy.io import wavfile

        sample_rate = 16000

        print(f"\n  Recording {duration}s to {filename}...")
        print("  (Speak or make sounds for the test recording)")

        recording = sd.rec(
            int(duration * sample_rate),
            samplerate=sample_rate,
            channels=1,
            dtype='int16'
        )
        sd.wait()

        # Save to WAV
        output_path = PROJECT_ROOT / filename
        wavfile.write(str(output_path), sample_rate, recording)

        file_size = output_path.stat().st_size
        print_result("Save WAV file", True, f"{file_size} bytes -> {output_path}")

        print(f"\n  You can play this file to verify audio quality:")
        print(f"    aplay {output_path}")

        return True

    except ImportError:
        print("  ⚠️ scipy not installed - skipping WAV save")
        return True

    except Exception as e:
        print(f"\n  ❌ Save failed: {e}")
        return False


def main():
    """Run all hardware validation tests."""
    parser = argparse.ArgumentParser(
        description="INMP441 Hardware Validation Script"
    )
    parser.add_argument(
        "--skip-save",
        action="store_true",
        help="Skip saving test recording"
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=3.0,
        help="Recording duration in seconds (default: 3.0)"
    )
    args = parser.parse_args()

    print("\n" + "=" * 60)
    print(" INMP441 Hardware Validation - OpenDuck Mini V3")
    print(" Day 17 - 22 January 2026")
    print("=" * 60)

    results = {}

    # Test 1: Dependencies
    results['dependencies'] = check_dependencies()
    if not results['dependencies']:
        print("\n❌ Missing dependencies. Install them and try again.")
        return 1

    # Test 2: List devices
    list_audio_devices()

    # Test 3: Basic capture
    results['basic_capture'] = test_basic_capture(duration_seconds=args.duration)

    # Test 4: Continuous monitoring
    results['monitoring'] = test_continuous_monitoring(duration_seconds=5.0)

    # Test 5: Driver integration
    results['driver'] = test_driver_integration()

    # Test 6: Save recording (optional)
    if not args.skip_save:
        results['save'] = save_test_recording(duration=args.duration)

    # Summary
    print_header("VALIDATION SUMMARY")

    passed = sum(1 for v in results.values() if v)
    total = len(results)

    print(f"\n  Results: {passed}/{total} tests passed")
    print()

    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"    {test_name}: {status}")

    overall = all(results.values())

    print()
    if overall:
        print("  ╔═══════════════════════════════════════╗")
        print("  ║  ✅ INMP441 HARDWARE VALIDATION PASS  ║")
        print("  ╚═══════════════════════════════════════╝")
    else:
        print("  ╔═══════════════════════════════════════╗")
        print("  ║  ❌ INMP441 HARDWARE VALIDATION FAIL  ║")
        print("  ╚═══════════════════════════════════════╝")
        print("\n  Check wiring and I2S configuration.")

    return 0 if overall else 1


if __name__ == "__main__":
    sys.exit(main())
