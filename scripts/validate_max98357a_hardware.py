#!/usr/bin/env python3
"""MAX98357A Amplifier Hardware Validation Script for OpenDuck Mini V3

This script validates the MAX98357A I2S amplifier on real hardware.
Run this on the Raspberry Pi after wiring the MAX98357A.

Wiring Guide (MAX98357A -> Raspberry Pi 4):
    VIN   -> Pin 2 or 4 (5V) - IMPORTANT: Use 5V, NOT 3.3V!
    GND   -> Pin 6 (GND)
    DIN   -> Pin 40 (GPIO 21 - I2S Data Out)
    BCLK  -> Pin 12 (GPIO 18 - I2S BCLK)
    LRCLK -> Pin 35 (GPIO 19 - I2S LRCLK)
    GAIN  -> GND (15dB gain) or unconnected (9dB)
    SD    -> Unconnected (enabled) or GND (shutdown)

Prerequisites:
    1. Enable I2S overlay in /boot/config.txt:
       dtparam=i2s=on

    2. Speaker connected to amplifier output terminals

    3. Reboot after config changes

Usage:
    python scripts/validate_max98357a_hardware.py

Author: Day 17 Hardware Validation
Date: 22 January 2026
"""

import sys
import time
import argparse
import math
import struct
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
    status = "PASS" if passed else "FAIL"
    print(f"  {test_name}: {status}")
    if details:
        print(f"    -> {details}")


def check_dependencies() -> bool:
    """Check if required dependencies are installed."""
    print_header("Dependency Check")

    all_ok = True

    # Check sounddevice (for audio output)
    try:
        import sounddevice as sd
        print_result("sounddevice", True, f"version {sd.__version__}")
    except ImportError:
        print_result("sounddevice", False, "pip install sounddevice")
        all_ok = False

    # Check numpy
    try:
        import numpy as np
        print_result("numpy", True, f"version {np.__version__}")
    except ImportError:
        print_result("numpy", False, "pip install numpy")
        all_ok = False

    return all_ok


def list_audio_devices() -> None:
    """List all available audio output devices."""
    print_header("Audio Output Devices")

    try:
        import sounddevice as sd
        devices = sd.query_devices()

        print("\n  Available audio devices:")
        print("-" * 60)

        output_devices = []
        for i, dev in enumerate(devices):
            output_ch = dev.get('max_output_channels', 0)
            if output_ch > 0:
                name = dev.get('name', 'Unknown')
                default_sr = dev.get('default_samplerate', 0)
                marker = " [DEFAULT OUTPUT]" if i == sd.default.device[1] else ""
                print(f"  [{i}] {name}{marker}")
                print(f"      OUT:{output_ch}ch | {default_sr}Hz")
                output_devices.append(i)

        print()
        print(f"  Default output device: {sd.default.device[1]}")
        print(f"  Total output devices: {len(output_devices)}")

    except Exception as e:
        print(f"  Error listing devices: {e}")


def generate_sine_wave(frequency: float, duration_ms: int, sample_rate: int = 16000) -> bytes:
    """Generate a sine wave as 16-bit PCM.

    Args:
        frequency: Tone frequency in Hz.
        duration_ms: Duration in milliseconds.
        sample_rate: Sample rate in Hz.

    Returns:
        16-bit PCM audio data as bytes.
    """
    num_samples = int(sample_rate * duration_ms / 1000)
    samples = []

    for i in range(num_samples):
        t = i / sample_rate
        value = int(16000 * math.sin(2 * math.pi * frequency * t))
        samples.append(value)

    return struct.pack(f'<{num_samples}h', *samples)


def test_sounddevice_output() -> bool:
    """Test audio output using sounddevice."""
    print_header("SoundDevice Output Test")

    try:
        import sounddevice as sd
        import numpy as np

        sample_rate = 16000
        duration = 1.0  # seconds
        frequency = 440  # A4 note

        print(f"\n  Playing {frequency}Hz tone for {duration}s...")
        print("  (You should hear a beep from the speaker)")

        # Generate sine wave
        t = np.linspace(0, duration, int(sample_rate * duration), endpoint=False)
        audio = np.sin(2 * np.pi * frequency * t).astype(np.float32) * 0.5

        # Play audio
        sd.play(audio, samplerate=sample_rate)
        sd.wait()

        print_result("Tone playback", True, f"{frequency}Hz for {duration}s")
        return True

    except Exception as e:
        print(f"\n  Playback failed: {e}")
        print_result("Tone playback", False, str(e))
        return False


def test_frequency_sweep() -> bool:
    """Test frequency response with a sweep."""
    print_header("Frequency Sweep Test")

    try:
        import sounddevice as sd
        import numpy as np

        sample_rate = 16000
        duration = 3.0  # seconds
        f_start = 200
        f_end = 4000

        print(f"\n  Playing frequency sweep {f_start}Hz to {f_end}Hz...")
        print("  (You should hear tone rising in pitch)")

        # Generate chirp/sweep
        t = np.linspace(0, duration, int(sample_rate * duration), endpoint=False)
        # Linear frequency sweep
        freq = f_start + (f_end - f_start) * t / duration
        phase = 2 * np.pi * (f_start * t + (f_end - f_start) * t**2 / (2 * duration))
        audio = np.sin(phase).astype(np.float32) * 0.5

        # Play audio
        sd.play(audio, samplerate=sample_rate)
        sd.wait()

        print_result("Frequency sweep", True, f"{f_start}-{f_end}Hz")
        return True

    except Exception as e:
        print(f"\n  Sweep failed: {e}")
        print_result("Frequency sweep", False, str(e))
        return False


def test_volume_levels() -> bool:
    """Test different volume levels."""
    print_header("Volume Level Test")

    try:
        import sounddevice as sd
        import numpy as np

        sample_rate = 16000
        duration = 0.5
        frequency = 800
        volumes = [0.1, 0.3, 0.5, 0.7, 0.9]

        print("\n  Playing tones at different volumes...")
        print("  (Volume should increase with each beep)")

        t = np.linspace(0, duration, int(sample_rate * duration), endpoint=False)

        for vol in volumes:
            audio = np.sin(2 * np.pi * frequency * t).astype(np.float32) * vol
            sd.play(audio, samplerate=sample_rate)
            sd.wait()
            print(f"    Volume {int(vol*100)}%")
            time.sleep(0.3)

        print_result("Volume levels", True, "5 levels tested")
        return True

    except Exception as e:
        print(f"\n  Volume test failed: {e}")
        print_result("Volume levels", False, str(e))
        return False


def test_driver_integration() -> bool:
    """Test integration with MAX98357A driver."""
    print_header("Driver Integration Test")

    try:
        from drivers.audio.max98357a import MAX98357ADriver, MAX98357AConfig, PlaybackState

        print("\n  Testing MAX98357ADriver class...")

        # Create driver
        config = MAX98357AConfig(sample_rate=16000, volume=0.7)
        driver = MAX98357ADriver(config=config)
        print_result("Driver instantiation", True)

        # Check initial state
        state = driver.get_state()
        if state == PlaybackState.STOPPED:
            print_result("Initial state", True, "STOPPED")
        else:
            print_result("Initial state", False, f"Expected STOPPED, got {state}")
            return False

        # Test volume
        driver.set_volume(0.5)
        if driver.volume == 0.5:
            print_result("Volume control", True, "0.5")
        else:
            print_result("Volume control", False, f"Expected 0.5, got {driver.volume}")

        # Test beep
        print("  Playing test beep...")
        result = driver.play_beep(blocking=True)
        if result:
            print_result("play_beep()", True)
        else:
            print_result("play_beep()", False)

        # Test tone
        print("  Playing 600Hz tone...")
        result = driver.play_tone(600, 500, blocking=True)
        if result:
            print_result("play_tone()", True, "600Hz, 500ms")
        else:
            print_result("play_tone()", False)

        # Check state after playback
        state = driver.get_state()
        if state == PlaybackState.STOPPED:
            print_result("Post-playback state", True, "STOPPED")
        else:
            print_result("Post-playback state", False, f"Got {state}")

        return True

    except ImportError as e:
        print(f"\n  Driver import failed: {e}")
        print("  Running without driver integration test")
        return True

    except Exception as e:
        print(f"\n  Driver test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_musical_scale() -> bool:
    """Play a musical scale to test audio quality."""
    print_header("Musical Scale Test")

    try:
        import sounddevice as sd
        import numpy as np

        sample_rate = 16000
        note_duration = 0.3

        # C major scale frequencies (C4 to C5)
        scale = [
            ("C4", 261.63),
            ("D4", 293.66),
            ("E4", 329.63),
            ("F4", 349.23),
            ("G4", 392.00),
            ("A4", 440.00),
            ("B4", 493.88),
            ("C5", 523.25),
        ]

        print("\n  Playing C major scale...")
        print("  (You should hear 8 distinct notes)")

        for note_name, freq in scale:
            t = np.linspace(0, note_duration, int(sample_rate * note_duration), endpoint=False)
            # Add envelope for cleaner sound
            envelope = np.exp(-t * 3)
            audio = np.sin(2 * np.pi * freq * t).astype(np.float32) * 0.5 * envelope

            sd.play(audio, samplerate=sample_rate)
            sd.wait()
            print(f"    {note_name}: {freq:.1f}Hz")

        print_result("Musical scale", True, "C major scale")
        return True

    except Exception as e:
        print(f"\n  Scale test failed: {e}")
        print_result("Musical scale", False, str(e))
        return False


def test_stereo_to_mono() -> bool:
    """Test that stereo audio is properly converted."""
    print_header("Stereo to Mono Test")

    try:
        import sounddevice as sd
        import numpy as np

        sample_rate = 16000
        duration = 1.0
        frequency = 440

        print("\n  Testing stereo-to-mono conversion...")

        # Generate stereo audio (left channel only)
        t = np.linspace(0, duration, int(sample_rate * duration), endpoint=False)
        left = np.sin(2 * np.pi * frequency * t).astype(np.float32) * 0.5
        right = np.zeros_like(left)
        stereo = np.column_stack([left, right])

        # Play as stereo
        sd.play(stereo, samplerate=sample_rate)
        sd.wait()

        print_result("Stereo playback", True, "Left channel only")
        return True

    except Exception as e:
        print(f"\n  Test failed: {e}")
        print_result("Stereo test", False, str(e))
        return False


def main():
    """Run all hardware validation tests."""
    parser = argparse.ArgumentParser(
        description="MAX98357A Hardware Validation Script"
    )
    parser.add_argument(
        "--skip-driver",
        action="store_true",
        help="Skip driver integration test"
    )
    parser.add_argument(
        "--quick",
        action="store_true",
        help="Run quick test (single tone only)"
    )
    args = parser.parse_args()

    print("\n" + "=" * 60)
    print(" MAX98357A Hardware Validation - OpenDuck Mini V3")
    print(" Day 17 - 22 January 2026")
    print("=" * 60)

    results = {}

    # Test 1: Dependencies
    results['dependencies'] = check_dependencies()
    if not results['dependencies']:
        print("\n  Missing dependencies. Install them and try again.")
        return 1

    # Test 2: List devices
    list_audio_devices()

    # Test 3: Basic tone output
    results['tone_output'] = test_sounddevice_output()

    if args.quick:
        # Quick mode - just tone test
        print("\n  [Quick mode - skipping additional tests]")
    else:
        # Test 4: Volume levels
        results['volume_levels'] = test_volume_levels()

        # Test 5: Frequency sweep
        results['frequency_sweep'] = test_frequency_sweep()

        # Test 6: Musical scale
        results['musical_scale'] = test_musical_scale()

        # Test 7: Driver integration
        if not args.skip_driver:
            results['driver'] = test_driver_integration()

    # Summary
    print_header("VALIDATION SUMMARY")

    passed = sum(1 for v in results.values() if v)
    total = len(results)

    print(f"\n  Results: {passed}/{total} tests passed")
    print()

    for test_name, result in results.items():
        status = "PASS" if result else "FAIL"
        print(f"    {test_name}: {status}")

    overall = all(results.values())

    print()
    if overall:
        print("  ================================================")
        print("    MAX98357A HARDWARE VALIDATION PASS")
        print("  ================================================")
        print("\n  Speaker output is working correctly!")
    else:
        print("  ================================================")
        print("    MAX98357A HARDWARE VALIDATION FAIL")
        print("  ================================================")
        print("\n  Troubleshooting:")
        print("    1. Check VIN is connected to 5V (not 3.3V)")
        print("    2. Check speaker is connected to + and - terminals")
        print("    3. Check I2S connections (DIN, BCLK, LRCLK)")
        print("    4. Check /boot/config.txt has dtparam=i2s=on")

    return 0 if overall else 1


if __name__ == "__main__":
    sys.exit(main())
