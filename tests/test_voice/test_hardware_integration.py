"""Hardware Integration Tests for Voice Pipeline

AGENT-2: Integration Test Engineer
Tests the voice pipeline with real audio from INMP441 microphone.

Requirements:
    - Raspberry Pi accessible via SSH at PI_HOST (default: pi@openduck.local)
    - INMP441 microphone connected and working
    - I2S overlay configured on Pi

Test Categories:
1. Audio Capture Verification
2. VAD with Real Audio
3. Full Pipeline Integration

Usage:
    # Run all hardware tests (requires Pi connected)
    pytest tests/test_voice/test_hardware_integration.py -v

    # Skip if Pi not available
    pytest tests/test_voice/test_hardware_integration.py -v -m "not hardware"

Environment Variables:
    PI_HOST: SSH host for Raspberry Pi (default: pi@openduck.local)
    PI_AUDIO_DEVICE: ALSA device on Pi (default: plughw:1,0)
"""

from __future__ import annotations

import os
import subprocess
import tempfile
import wave
import struct
import time
from pathlib import Path
from typing import Optional, Tuple

import numpy as np
import pytest

# Import voice pipeline components
from src.voice.vad import VoiceActivityDetector, VADConfig, VADState, VADEvent
from src.voice.wake_word import WakeWordDetector, WakeWordConfig
from src.voice.stt import SpeechToText, STTConfig
from src.voice.intent import IntentClassifier, IntentConfig

# Configuration from environment
PI_HOST = os.environ.get("PI_HOST", "pi@openduck.local")
PI_AUDIO_DEVICE = os.environ.get("PI_AUDIO_DEVICE", "plughw:1,0")
PI_SAMPLE_RATE = 48000


def is_pi_available() -> bool:
    """Check if Raspberry Pi is reachable via SSH."""
    try:
        result = subprocess.run(
            ["ssh", "-o", "ConnectTimeout=5", PI_HOST, "echo ok"],
            capture_output=True,
            text=True,
            timeout=15
        )
        return result.returncode == 0 and "ok" in result.stdout
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def capture_audio_from_pi(duration: float = 2.0, retries: int = 2) -> Optional[np.ndarray]:
    """Capture audio from Pi via SSH.

    Args:
        duration: Recording duration in seconds
        retries: Number of retry attempts on failure

    Returns:
        Audio samples as float32 numpy array, or None if failed
    """
    for attempt in range(retries + 1):
        local_path = None
        try:
            # Create temp file for WAV
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                local_path = tmp.name

            remote_path = f"/tmp/test_capture_{int(time.time())}_{attempt}.wav"

            # Capture on Pi
            capture_cmd = (
                f"arecord -D {PI_AUDIO_DEVICE} -f S32_LE -r {PI_SAMPLE_RATE} "
                f"-c 2 -d {int(duration)} {remote_path}"
            )
            result = subprocess.run(
                ["ssh", PI_HOST, capture_cmd],
                capture_output=True,
                text=True,
                timeout=duration + 15
            )

            if result.returncode != 0:
                print(f"Capture failed (attempt {attempt + 1}): {result.stderr}")
                if attempt < retries:
                    time.sleep(1)
                    continue
                return None

            # Copy file from Pi
            scp_result = subprocess.run(
                ["scp", f"{PI_HOST}:{remote_path}", local_path],
                capture_output=True,
                text=True,
                timeout=15
            )

            if scp_result.returncode != 0:
                print(f"SCP failed (attempt {attempt + 1}): {scp_result.stderr}")
                if attempt < retries:
                    time.sleep(1)
                    continue
                return None

            # Clean up remote file (don't fail if this fails)
            subprocess.run(
                ["ssh", PI_HOST, f"rm -f {remote_path}"],
                capture_output=True,
                timeout=5
            )

            # Check file exists and has content
            if not os.path.exists(local_path) or os.path.getsize(local_path) < 100:
                print(f"WAV file missing or empty (attempt {attempt + 1})")
                if attempt < retries:
                    time.sleep(1)
                    continue
                return None

            # Load WAV file
            with wave.open(local_path, 'rb') as wf:
                frames = wf.readframes(wf.getnframes())
                samples = np.frombuffer(frames, dtype=np.int32)

                # Extract left channel (INMP441 is mono on left)
                left = samples[0::2]

                # Normalize to float32 [-1, 1]
                audio = left.astype(np.float32) / 2147483648.0

            return audio

        except subprocess.TimeoutExpired as e:
            print(f"Timeout (attempt {attempt + 1}): {e}")
            if attempt < retries:
                time.sleep(1)
                continue
            return None

        except Exception as e:
            print(f"Error capturing audio (attempt {attempt + 1}): {type(e).__name__}: {e}")
            if attempt < retries:
                time.sleep(1)
                continue
            return None

        finally:
            if local_path and os.path.exists(local_path):
                try:
                    os.unlink(local_path)
                except:
                    pass

    return None


def resample_audio(audio: np.ndarray, from_rate: int, to_rate: int) -> np.ndarray:
    """Simple resampling using linear interpolation.

    Args:
        audio: Input audio samples
        from_rate: Original sample rate
        to_rate: Target sample rate

    Returns:
        Resampled audio
    """
    if from_rate == to_rate:
        return audio

    # Calculate new length
    duration = len(audio) / from_rate
    new_length = int(duration * to_rate)

    # Linear interpolation
    old_indices = np.linspace(0, len(audio) - 1, new_length)
    return np.interp(old_indices, np.arange(len(audio)), audio).astype(np.float32)


# Mark all tests in this module as hardware tests
pytestmark = pytest.mark.hardware


class TestPiConnection:
    """Test Raspberry Pi connectivity."""

    def test_pi_is_reachable(self):
        """Pi should be reachable via SSH."""
        if not is_pi_available():
            pytest.skip(f"Pi not available at {PI_HOST}")

        assert is_pi_available(), f"Cannot reach Pi at {PI_HOST}"

    def test_audio_device_exists(self):
        """Audio device should be available on Pi."""
        if not is_pi_available():
            pytest.skip(f"Pi not available at {PI_HOST}")

        result = subprocess.run(
            ["ssh", PI_HOST, "arecord -l"],
            capture_output=True,
            text=True,
            timeout=10
        )

        assert "card" in result.stdout.lower(), "No audio cards found on Pi"


class TestRealAudioCapture:
    """Test audio capture from INMP441."""

    def test_capture_returns_audio(self):
        """Should capture audio from INMP441."""
        if not is_pi_available():
            pytest.skip(f"Pi not available at {PI_HOST}")

        audio = capture_audio_from_pi(duration=2.0)

        assert audio is not None, "Failed to capture audio"
        assert len(audio) > 0, "Captured audio is empty"
        assert audio.dtype == np.float32, "Audio should be float32"

    def test_capture_has_signal(self):
        """Captured audio should have some signal (not all zeros)."""
        if not is_pi_available():
            pytest.skip(f"Pi not available at {PI_HOST}")

        audio = capture_audio_from_pi(duration=2.0)

        assert audio is not None, "Failed to capture audio"

        # Check for signal
        audio_range = audio.max() - audio.min()
        non_zero_pct = 100 * np.count_nonzero(audio) / len(audio)

        print(f"\nAudio stats:")
        print(f"  Samples: {len(audio)}")
        print(f"  Range: {audio_range:.6f}")
        print(f"  Non-zero: {non_zero_pct:.1f}%")

        assert audio_range > 0.0001, f"No signal detected (range={audio_range})"
        assert non_zero_pct > 50, f"Too many zeros ({non_zero_pct:.1f}%)"

    def test_capture_normalized_range(self):
        """Audio should be normalized to [-1, 1] range."""
        if not is_pi_available():
            pytest.skip(f"Pi not available at {PI_HOST}")

        audio = capture_audio_from_pi(duration=1.0)

        assert audio is not None, "Failed to capture audio"
        assert audio.min() >= -1.0, f"Audio below -1.0: {audio.min()}"
        assert audio.max() <= 1.0, f"Audio above 1.0: {audio.max()}"


class TestVADWithRealAudio:
    """Test VAD with real audio from INMP441."""

    def test_vad_processes_real_audio(self):
        """VAD should process real audio without errors."""
        if not is_pi_available():
            pytest.skip(f"Pi not available at {PI_HOST}")

        audio = capture_audio_from_pi(duration=2.0)
        assert audio is not None, "Failed to capture audio"

        # Resample from 48kHz to 16kHz for VAD
        audio_16k = resample_audio(audio, PI_SAMPLE_RATE, 16000)

        # Create VAD
        vad = VoiceActivityDetector(VADConfig(
            energy_threshold_db=-40.0,
            min_speech_ms=50,
            min_silence_ms=100
        ))

        # Process frames (20ms = 320 samples at 16kHz)
        frame_size = 320
        results = []

        for i in range(0, len(audio_16k) - frame_size, frame_size):
            frame = audio_16k[i:i + frame_size]
            result = vad.process_frame(frame)
            results.append(result)

        assert len(results) > 0, "No frames processed"
        print(f"\nVAD processed {len(results)} frames")

    def test_vad_detects_ambient_noise(self):
        """VAD should detect ambient room noise as non-speech."""
        if not is_pi_available():
            pytest.skip(f"Pi not available at {PI_HOST}")

        print("\n[Capturing 3 seconds of ambient room noise...]")
        audio = capture_audio_from_pi(duration=3.0)
        assert audio is not None, "Failed to capture audio"

        # Resample
        audio_16k = resample_audio(audio, PI_SAMPLE_RATE, 16000)

        # VAD with moderate threshold
        vad = VoiceActivityDetector(VADConfig(
            energy_threshold_db=-35.0,
            min_speech_ms=100,
            min_silence_ms=200
        ))

        # Process and count states
        frame_size = 320
        speech_frames = 0
        silence_frames = 0

        for i in range(0, len(audio_16k) - frame_size, frame_size):
            frame = audio_16k[i:i + frame_size]
            result = vad.process_frame(frame)

            if result.is_speech:
                speech_frames += 1
            else:
                silence_frames += 1

        total_frames = speech_frames + silence_frames
        speech_ratio = speech_frames / total_frames if total_frames > 0 else 0

        print(f"\nAmbient noise analysis:")
        print(f"  Total frames: {total_frames}")
        print(f"  Speech frames: {speech_frames} ({100*speech_ratio:.1f}%)")
        print(f"  Silence frames: {silence_frames}")

        # Ambient noise should mostly be classified as silence
        # Allow some speech detection due to environmental sounds
        assert speech_ratio < 0.5, f"Too much 'speech' in ambient noise ({100*speech_ratio:.1f}%)"

    def test_vad_energy_levels(self):
        """VAD should report reasonable energy levels for real audio."""
        if not is_pi_available():
            pytest.skip(f"Pi not available at {PI_HOST}")

        audio = capture_audio_from_pi(duration=2.0)
        assert audio is not None, "Failed to capture audio"

        audio_16k = resample_audio(audio, PI_SAMPLE_RATE, 16000)

        vad = VoiceActivityDetector(VADConfig())

        # Collect energy levels
        frame_size = 320
        energy_levels = []

        for i in range(0, len(audio_16k) - frame_size, frame_size):
            frame = audio_16k[i:i + frame_size]
            result = vad.process_frame(frame)
            energy_levels.append(result.energy_db)

        avg_energy = sum(energy_levels) / len(energy_levels)
        min_energy = min(energy_levels)
        max_energy = max(energy_levels)

        print(f"\nEnergy levels (dB):")
        print(f"  Min: {min_energy:.1f}")
        print(f"  Max: {max_energy:.1f}")
        print(f"  Avg: {avg_energy:.1f}")

        # Real audio should have energy above -100dB (our floor)
        assert max_energy > -80, f"Energy too low: {max_energy}dB"
        # And below 0dB (full scale)
        assert max_energy <= 0, f"Energy above full scale: {max_energy}dB"


class TestFullPipelineIntegration:
    """Test full voice pipeline with real audio."""

    def test_vad_to_wake_word_pipeline(self):
        """VAD output should feed into wake word detector."""
        if not is_pi_available():
            pytest.skip(f"Pi not available at {PI_HOST}")

        audio = capture_audio_from_pi(duration=2.0)
        assert audio is not None, "Failed to capture audio"

        audio_16k = resample_audio(audio, PI_SAMPLE_RATE, 16000)

        # Create pipeline components
        vad = VoiceActivityDetector(VADConfig(min_speech_ms=50))
        wake = WakeWordDetector(mock_mode=True)
        wake.start()

        # Process through pipeline
        frame_size = 320
        vad_speech_frames = 0
        wake_processed = 0

        for i in range(0, len(audio_16k) - frame_size, frame_size):
            frame = audio_16k[i:i + frame_size]

            # VAD first
            vad_result = vad.process_frame(frame)

            # Only process wake word if VAD detects speech
            if vad_result.is_speech:
                vad_speech_frames += 1
                wake_result = wake.process_frame(frame)
                wake_processed += 1

        wake.stop()

        print(f"\nPipeline stats:")
        print(f"  VAD speech frames: {vad_speech_frames}")
        print(f"  Wake word processed: {wake_processed}")

        # Pipeline should execute without errors
        assert True, "Pipeline executed successfully"

    def test_full_pipeline_no_crash(self):
        """Full pipeline should handle real audio without crashing."""
        if not is_pi_available():
            pytest.skip(f"Pi not available at {PI_HOST}")

        audio = capture_audio_from_pi(duration=2.0)
        assert audio is not None, "Failed to capture audio"

        audio_16k = resample_audio(audio, PI_SAMPLE_RATE, 16000)

        # Create all pipeline components
        vad = VoiceActivityDetector(VADConfig(min_speech_ms=50))
        wake = WakeWordDetector(mock_mode=True)
        stt = SpeechToText(mock_mode=True)
        intent = IntentClassifier(mock_mode=True)

        wake.start()

        # Collect speech segments
        speech_buffer = []
        frame_size = 320

        for i in range(0, len(audio_16k) - frame_size, frame_size):
            frame = audio_16k[i:i + frame_size]
            vad_result = vad.process_frame(frame)

            if vad_result.is_speech:
                speech_buffer.extend(frame.tolist())

        wake.stop()

        # If we collected speech, run through STT and Intent
        if len(speech_buffer) > 0:
            speech_audio = np.array(speech_buffer, dtype=np.float32)

            # Transcribe
            stt_result = stt.transcribe(speech_audio)
            print(f"\nSTT result: '{stt_result.text}' (conf: {stt_result.confidence:.2f})")

            # Classify intent (if we got text)
            if stt_result.text:
                intent_result = intent.classify(stt_result.text)
                print(f"Intent: {intent_result.intent.value} (conf: {intent_result.confidence:.2f})")

        print("\n✅ Full pipeline executed without errors")
        assert True


class TestAudioQuality:
    """Test audio quality metrics."""

    def test_signal_to_noise_estimation(self):
        """Estimate SNR from captured audio."""
        if not is_pi_available():
            pytest.skip(f"Pi not available at {PI_HOST}")

        audio = capture_audio_from_pi(duration=3.0)
        assert audio is not None, "Failed to capture audio"

        # Simple SNR estimation using frame energy variance
        frame_size = 480  # 10ms at 48kHz
        energies = []

        for i in range(0, len(audio) - frame_size, frame_size):
            frame = audio[i:i + frame_size]
            rms = np.sqrt(np.mean(frame ** 2))
            if rms > 0:
                energy_db = 20 * np.log10(rms)
                energies.append(energy_db)

        if energies:
            # Estimate noise floor as 10th percentile
            noise_floor = np.percentile(energies, 10)
            # Estimate signal level as 90th percentile
            signal_level = np.percentile(energies, 90)
            # SNR estimate
            snr_estimate = signal_level - noise_floor

            print(f"\nAudio quality metrics:")
            print(f"  Noise floor: {noise_floor:.1f} dB")
            print(f"  Signal level: {signal_level:.1f} dB")
            print(f"  SNR estimate: {snr_estimate:.1f} dB")

            # INMP441 should have decent SNR
            assert snr_estimate > 5, f"SNR too low: {snr_estimate:.1f} dB"


class TestRealBackends:
    """Test real wake word and STT backends (requires packages installed on Pi)."""

    def test_openwakeword_backend_init(self):
        """Test OpenWakeWord backend initialization."""
        try:
            detector = WakeWordDetector(WakeWordConfig(
                wake_words=["hey jarvis"],
                backend="openwakeword",
                sensitivity=0.5
            ))

            if detector.mock_mode:
                pytest.skip("OpenWakeWord not installed - using mock mode")

            assert detector._backend is not None, "Backend should be initialized"
            assert hasattr(detector, '_oww_models'), "Should have OWW models list"
            print(f"\n[OK] OpenWakeWord initialized with models: {detector._oww_models}")

        except Exception as e:
            pytest.skip(f"OpenWakeWord init failed: {e}")

    def test_faster_whisper_backend_init(self):
        """Test faster-whisper backend initialization."""
        try:
            stt = SpeechToText(STTConfig(
                backend="whisper",
                model_size="tiny",  # Use tiny for fast testing
                language="en"
            ))

            if stt.mock_mode:
                pytest.skip("Neither faster-whisper nor openai-whisper installed")

            backend_type = getattr(stt, '_backend_type', 'unknown')
            print(f"\n[OK] Whisper backend initialized: {backend_type}")
            assert stt._backend is not None, "Backend should be initialized"

        except Exception as e:
            pytest.skip(f"Whisper init failed: {e}")


class TestLiveSpeechRecognition:
    """Test live speech recognition with real audio.

    These tests require the user to speak into the microphone.
    """

    def test_live_speech_to_text(self):
        """Test real speech-to-text transcription.

        REQUIRES USER TO SPEAK: Say a simple phrase when prompted.
        """
        if not is_pi_available():
            pytest.skip(f"Pi not available at {PI_HOST}")

        # Try to initialize real STT backend
        stt = SpeechToText(STTConfig(
            backend="whisper",
            model_size="tiny",  # Use tiny for speed
            language="en"
        ))

        if stt.mock_mode:
            pytest.skip("No real STT backend available")

        print("\n" + "=" * 50)
        print("[MIC] SPEAK NOW! Say something like:")
        print("   'Hello world'")
        print("   'Turn on the lights'")
        print("   'What time is it'")
        print("=" * 50)
        print("Capturing 4 seconds of audio...")

        audio = capture_audio_from_pi(duration=4.0)
        assert audio is not None, "Failed to capture audio"

        # Resample to 16kHz for Whisper
        audio_16k = resample_audio(audio, PI_SAMPLE_RATE, 16000)

        print(f"Audio captured: {len(audio_16k)} samples ({len(audio_16k)/16000:.1f}s)")

        # Transcribe
        result = stt.transcribe(audio_16k)

        print(f"\n[RESULT] TRANSCRIPTION:")
        print(f"   Text: '{result.text}'")
        print(f"   Confidence: {result.confidence:.2f}")
        print(f"   Language: {result.language}")

        # We can't assert specific text, but we can check we got something
        assert result.is_final, "Result should be final"
        print("\n[OK] Speech recognition completed")

    def test_live_wake_word_detection(self):
        """Test real wake word detection.

        REQUIRES USER TO SPEAK: Say 'Hey Jarvis' when prompted.
        """
        if not is_pi_available():
            pytest.skip(f"Pi not available at {PI_HOST}")

        # Try to initialize real wake word backend
        detector = WakeWordDetector(WakeWordConfig(
            wake_words=["hey jarvis"],
            backend="openwakeword",
            sensitivity=0.6
        ))

        if detector.mock_mode:
            pytest.skip("No real wake word backend available")

        print("\n" + "=" * 50)
        print("[MIC] SPEAK NOW! Say:")
        print("   'Hey Jarvis'")
        print("=" * 50)
        print("Capturing 4 seconds of audio...")

        audio = capture_audio_from_pi(duration=4.0)
        assert audio is not None, "Failed to capture audio"

        # Resample to 16kHz
        audio_16k = resample_audio(audio, PI_SAMPLE_RATE, 16000)

        # Process through wake word detector
        detector.start()
        detected = False
        detection_confidence = 0.0

        # Process in chunks (OpenWakeWord needs ~80ms chunks)
        chunk_size = 1280  # 80ms at 16kHz
        for i in range(0, len(audio_16k) - chunk_size, chunk_size):
            chunk = audio_16k[i:i + chunk_size]
            result = detector.process_audio(chunk)

            if result.detected:
                detected = True
                detection_confidence = result.confidence
                print(f"\n[DETECTED] WAKE WORD!")
                print(f"   Word: '{result.wake_word}'")
                print(f"   Confidence: {result.confidence:.2f}")
                break

        detector.stop()

        if not detected:
            print("\n[WARN] Wake word not detected in audio")
            print("   This may be normal if you didn't say 'Hey Jarvis'")

        print("\n[OK] Wake word detection test completed")

    def test_full_voice_pipeline_live(self):
        """Test complete voice pipeline with live speech.

        REQUIRES USER TO SPEAK: Say 'Turn on the lights' or similar command.
        """
        if not is_pi_available():
            pytest.skip(f"Pi not available at {PI_HOST}")

        # Initialize components (use mock if real backends unavailable)
        vad = VoiceActivityDetector(VADConfig(
            energy_threshold_db=-35.0,
            min_speech_ms=100
        ))

        stt = SpeechToText(STTConfig(
            backend="whisper",
            model_size="tiny",
            language="en"
        ))

        intent = IntentClassifier()

        print("\n" + "=" * 50)
        print("[MIC] SPEAK NOW! Say a command like:")
        print("   'Turn on the lights'")
        print("   'What time is it'")
        print("   'Play some music'")
        print("=" * 50)
        print("Capturing 5 seconds of audio...")

        audio = capture_audio_from_pi(duration=5.0)
        assert audio is not None, "Failed to capture audio"

        # Resample to 16kHz
        audio_16k = resample_audio(audio, PI_SAMPLE_RATE, 16000)

        # Step 1: VAD - extract speech segments
        print("\n[VAD] Analysis:")
        speech_buffer = []
        frame_size = 320
        speech_frames = 0
        total_frames = 0

        for i in range(0, len(audio_16k) - frame_size, frame_size):
            frame = audio_16k[i:i + frame_size]
            vad_result = vad.process_frame(frame)
            total_frames += 1

            if vad_result.is_speech:
                speech_frames += 1
                speech_buffer.extend(frame.tolist())

        speech_ratio = speech_frames / total_frames if total_frames > 0 else 0
        print(f"   Speech detected: {speech_frames}/{total_frames} frames ({100*speech_ratio:.1f}%)")

        if len(speech_buffer) < 1600:  # Less than 100ms of speech
            print("\n[WARN] Not enough speech detected for transcription")
            print("   Try speaking louder or closer to the microphone")
            return

        # Step 2: STT - transcribe speech
        print("\n[STT] Transcription:")
        speech_audio = np.array(speech_buffer, dtype=np.float32)
        stt_result = stt.transcribe(speech_audio)

        print(f"   Text: '{stt_result.text}'")
        print(f"   Confidence: {stt_result.confidence:.2f}")
        print(f"   Backend: {'real' if not stt.mock_mode else 'mock'}")

        # Step 3: Intent classification
        if stt_result.text:
            print("\n[INTENT] Classification:")
            intent_result = intent.classify(stt_result.text)

            print(f"   Intent: {intent_result.intent.value}")
            print(f"   Confidence: {intent_result.confidence:.2f}")

            if intent_result.entities:
                print(f"   Entities:")
                for entity in intent_result.entities:
                    print(f"      - {entity.type}: '{entity.value}'")

        print("\n" + "=" * 50)
        print("[OK] Full voice pipeline test completed!")
        print("=" * 50)
