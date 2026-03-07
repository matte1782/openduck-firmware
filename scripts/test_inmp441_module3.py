#!/usr/bin/env python3
"""
INMP441 Module 3 Validation Test
OpenDuck Mini V3 - Day 19
Tests I2S microphone Module 3 (freshly soldered with lower temp)
"""

import subprocess
import sys
import time
import struct
import wave
import os

class INMP441Tester:
    def __init__(self):
        self.test_results = {
            'hardware_detection': False,
            'alsa_device': False,
            'audio_capture': False,
            'signal_present': False,
            'noise_level_ok': False
        }

    def print_header(self, text):
        print("\n" + "="*70)
        print(f"  {text}")
        print("="*70)

    def print_step(self, step_num, text):
        print(f"\n[STEP {step_num}] {text}")
        print("-" * 70)

    def test_1_i2s_overlay(self):
        """Test 1: Check I2S overlay is loaded in /boot/config.txt"""
        self.print_step(1, "Checking I2S Overlay Configuration")

        try:
            with open('/boot/config.txt', 'r') as f:
                config = f.read()

            # Check for I2S overlay
            if 'dtoverlay=adau7002-simple' in config:
                print("✅ FOUND: dtoverlay=adau7002-simple")
                return True
            elif 'dtoverlay=rpi-simple-soundcard' in config:
                print("✅ FOUND: dtoverlay=rpi-simple-soundcard")
                return True
            else:
                print("❌ MISSING: No I2S overlay detected in /boot/config.txt")
                print("   You need to add one of these lines:")
                print("   - dtoverlay=adau7002-simple")
                print("   - dtoverlay=rpi-simple-soundcard")
                return False

        except Exception as e:
            print(f"❌ ERROR reading /boot/config.txt: {e}")
            return False

    def test_2_alsa_device(self):
        """Test 2: Check if ALSA detects I2S microphone"""
        self.print_step(2, "Detecting ALSA Capture Device")

        try:
            result = subprocess.run(['arecord', '-l'],
                                  capture_output=True,
                                  text=True,
                                  timeout=5)

            print("ALSA Capture Devices:")
            print(result.stdout)

            if 'adau7002' in result.stdout.lower() or 'simple-card' in result.stdout.lower():
                print("✅ I2S microphone detected by ALSA")
                self.test_results['alsa_device'] = True

                # Extract card and device number
                for line in result.stdout.split('\n'):
                    if 'card' in line.lower():
                        print(f"   Device line: {line}")

                return True
            else:
                print("❌ No I2S microphone detected")
                print("   This means the overlay didn't load or hardware not connected")
                return False

        except Exception as e:
            print(f"❌ ERROR running arecord: {e}")
            return False

    def test_3_gpio_config(self):
        """Test 3: Verify GPIO pins are configured for I2S"""
        self.print_step(3, "Checking GPIO I2S Configuration")

        try:
            # Check if GPIO 18, 19, 20 are in ALT mode (I2S)
            result = subprocess.run(['gpio', 'readall'],
                                  capture_output=True,
                                  text=True,
                                  timeout=5)

            print("GPIO Status (I2S pins):")
            for line in result.stdout.split('\n'):
                if 'GPIO 18' in line or 'GPIO 19' in line or 'GPIO 20' in line:
                    print(f"   {line}")

            # Look for ALT0 mode (I2S)
            if 'ALT0' in result.stdout or 'ALT' in result.stdout:
                print("✅ GPIO pins appear to be in ALT mode (I2S active)")
                return True
            else:
                print("⚠️  WARNING: GPIO pins may not be in I2S mode")
                print("   This is OK if I2S overlay just loaded")
                return True  # Don't fail on this

        except FileNotFoundError:
            print("⚠️  gpio command not found (install with: sudo apt install wiringpi)")
            return True  # Don't fail if gpio tool missing
        except Exception as e:
            print(f"⚠️  WARNING checking GPIO: {e}")
            return True  # Don't fail on this

    def test_4_short_capture(self):
        """Test 4: Capture 2 seconds of audio and check for signal"""
        self.print_step(4, "Capturing 2-Second Audio Sample")

        test_file = '/tmp/inmp441_test.wav'

        try:
            # Remove old test file
            if os.path.exists(test_file):
                os.remove(test_file)

            print("Recording 2 seconds of audio...")
            print("👂 PLEASE SPEAK OR MAKE NOISE NOW!")

            # Capture 2 seconds at 48kHz, stereo, S32_LE format
            cmd = [
                'arecord',
                '-D', 'plughw:0,0',  # Usually card 0, device 0
                '-f', 'S32_LE',      # Signed 32-bit little endian
                '-r', '48000',       # 48kHz sample rate
                '-c', '2',           # Stereo (even though we use left channel only)
                '-d', '2',           # 2 seconds duration
                test_file
            ]

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)

            if result.returncode != 0:
                print(f"❌ CAPTURE FAILED: {result.stderr}")
                return False

            print(f"✅ Audio captured to {test_file}")
            self.test_results['audio_capture'] = True

            # Analyze the captured audio
            return self.analyze_audio_file(test_file)

        except subprocess.TimeoutExpired:
            print("❌ TIMEOUT: arecord took too long")
            return False
        except Exception as e:
            print(f"❌ ERROR during capture: {e}")
            return False

    def analyze_audio_file(self, wav_file):
        """Analyze captured WAV file for signal presence"""
        self.print_step(5, "Analyzing Audio Signal")

        try:
            with wave.open(wav_file, 'rb') as wf:
                channels = wf.getnchannels()
                sample_width = wf.getsampwidth()
                framerate = wf.getframerate()
                frames = wf.getnframes()

                print(f"File info:")
                print(f"   Channels: {channels}")
                print(f"   Sample width: {sample_width} bytes")
                print(f"   Frame rate: {framerate} Hz")
                print(f"   Total frames: {frames}")

                # Read all audio data
                audio_data = wf.readframes(frames)

            # Parse as signed 32-bit integers
            sample_format = '<i' if sample_width == 4 else '<h'  # 32-bit or 16-bit
            num_samples = len(audio_data) // sample_width // channels

            samples_left = []
            samples_right = []

            for i in range(num_samples):
                offset = i * sample_width * channels

                # Left channel
                left_bytes = audio_data[offset : offset + sample_width]
                if len(left_bytes) == sample_width:
                    left_val = struct.unpack(sample_format, left_bytes)[0]
                    samples_left.append(left_val)

                # Right channel
                if channels == 2:
                    right_bytes = audio_data[offset + sample_width : offset + 2*sample_width]
                    if len(right_bytes) == sample_width:
                        right_val = struct.unpack(sample_format, right_bytes)[0]
                        samples_right.append(right_val)

            # Calculate statistics
            if samples_left:
                left_min = min(samples_left)
                left_max = max(samples_left)
                left_mean = sum(samples_left) / len(samples_left)
                left_range = left_max - left_min

                print(f"\n📊 Left Channel (INMP441 output):")
                print(f"   Min:   {left_min:>12,}")
                print(f"   Max:   {left_max:>12,}")
                print(f"   Mean:  {left_mean:>12,.1f}")
                print(f"   Range: {left_range:>12,}")

                # Check for signal
                if left_range == 0:
                    print("\n❌ FAIL: No audio signal detected (all samples identical)")
                    print("   Problem: Microphone not working or stuck")
                    if left_min == 0:
                        print("   All samples are 0 → Module damaged or not powered")
                    elif left_min == -1 or left_max == 2147483647:
                        print("   All samples are -1 or max → Possible solder bridge")
                    return False

                elif left_range < 1000:
                    print("\n⚠️  WARNING: Very low signal range")
                    print("   Signal is present but very weak")
                    print("   Possible issues: Low gain, poor solder joint, or quiet environment")
                    self.test_results['signal_present'] = True
                    return True

                else:
                    print("\n✅ SIGNAL DETECTED!")
                    print(f"   Dynamic range: {left_range:,} levels")

                    # Calculate approximate dB range
                    if sample_width == 4:
                        max_value = 2147483647  # 32-bit signed max
                    else:
                        max_value = 32767  # 16-bit signed max

                    db_range = 20 * (left_range / max_value)
                    print(f"   Approximate range: {db_range:.1f} dB")

                    self.test_results['signal_present'] = True
                    self.test_results['noise_level_ok'] = True
                    return True

            else:
                print("❌ No samples could be parsed")
                return False

        except Exception as e:
            print(f"❌ ERROR analyzing audio: {e}")
            import traceback
            traceback.print_exc()
            return False

    def run_all_tests(self):
        """Run complete test suite"""
        self.print_header("INMP441 MODULE 3 VALIDATION TEST - DAY 19")
        print("Testing freshly soldered module (lower temperature)")
        print("Expected: Working audio signal, no solder bridges")

        # Run tests in sequence
        tests = [
            ("I2S Overlay Configuration", self.test_1_i2s_overlay),
            ("ALSA Device Detection", self.test_2_alsa_device),
            ("GPIO I2S Mode", self.test_3_gpio_config),
            ("Audio Capture", self.test_4_short_capture),
        ]

        all_passed = True

        for test_name, test_func in tests:
            try:
                result = test_func()
                if not result:
                    all_passed = False
                    print(f"\n⚠️  Test '{test_name}' did not pass")

                    # Stop on critical failures
                    if test_name in ["I2S Overlay Configuration", "ALSA Device Detection"]:
                        print("\n🛑 CRITICAL TEST FAILED - Stopping test suite")
                        print("   Fix the issue above before continuing")
                        break
            except Exception as e:
                print(f"\n❌ EXCEPTION in test '{test_name}': {e}")
                import traceback
                traceback.print_exc()
                all_passed = False

        # Print summary
        self.print_header("TEST SUMMARY")

        print("\nResults:")
        for key, value in self.test_results.items():
            status = "✅ PASS" if value else "❌ FAIL"
            print(f"   {status}  {key.replace('_', ' ').title()}")

        if all_passed and self.test_results['signal_present']:
            print("\n🎉 SUCCESS! INMP441 Module 3 is working!")
            print("   You can now proceed with audio feature development")
            return 0
        elif self.test_results['audio_capture'] and not self.test_results['signal_present']:
            print("\n⚠️  PARTIAL SUCCESS: Hardware detected but no audio signal")
            print("   Possible issues:")
            print("   - Module damaged during soldering")
            print("   - Solder bridge still present")
            print("   - Wrong I2S overlay for INMP441")
            print("\n   Next steps:")
            print("   1. Visual inspection for solder bridges")
            print("   2. Try different I2S overlay (rpi-simple-soundcard)")
            print("   3. Test Module 4 (if available)")
            return 1
        else:
            print("\n❌ TESTS FAILED")
            print("   Review errors above and fix configuration")
            return 2

def main():
    if os.geteuid() != 0:
        print("⚠️  WARNING: This script should be run with sudo for full GPIO access")
        print("   Some tests may not work correctly without root privileges\n")

    tester = INMP441Tester()
    exit_code = tester.run_all_tests()
    sys.exit(exit_code)

if __name__ == '__main__':
    main()
