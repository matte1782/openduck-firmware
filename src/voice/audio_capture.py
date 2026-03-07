"""Audio Capture for OpenDuck Mini V3

This module provides audio capture from INMP441 I2S microphone.
Designed to run on Raspberry Pi with I2S overlay configured.

Hardware Setup:
    INMP441 → Raspberry Pi 4
    - VDD → Pin 1 (3.3V)
    - GND → Pin 6 (GND)
    - L/R → Pin 9 (GND for left channel)
    - SCK → Pin 12 (GPIO 18)
    - WS  → Pin 35 (GPIO 19)
    - SD  → Pin 38 (GPIO 20)

Requirements:
    - I2S overlay: dtoverlay=adau7002-simple in /boot/config.txt
    - ALSA utils: arecord command available

Example:
    ```python
    from src.voice.audio_capture import AudioCapture, CaptureConfig

    # Create capture instance
    capture = AudioCapture(CaptureConfig(duration_seconds=3.0))

    # Capture audio
    audio = capture.capture()
    print(f"Captured {len(audio)} samples")

    # Or capture to file
    capture.capture_to_file("/tmp/recording.wav")
    ```
"""

from __future__ import annotations

import logging
import os
import subprocess
import tempfile
import wave
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple

import numpy as np

_logger = logging.getLogger(__name__)


@dataclass
class CaptureConfig:
    """Configuration for audio capture.

    Attributes:
        sample_rate: Sample rate in Hz (default: 48000 for INMP441)
        channels: Number of channels (default: 2 for stereo I2S)
        duration_seconds: Recording duration (default: 3.0)
        device: ALSA device string (default: "plughw:1,0")
        format: Audio format (default: "S32_LE" for INMP441)
        use_left_channel: Extract left channel only (default: True)
    """
    sample_rate: int = 48000
    channels: int = 2
    duration_seconds: float = 3.0
    device: str = "plughw:1,0"
    format: str = "S32_LE"
    use_left_channel: bool = True

    def __post_init__(self) -> None:
        """Validate configuration."""
        if self.sample_rate <= 0:
            raise ValueError(f"sample_rate must be positive, got {self.sample_rate}")
        if self.duration_seconds <= 0:
            raise ValueError(f"duration_seconds must be positive, got {self.duration_seconds}")
        if self.channels not in (1, 2):
            raise ValueError(f"channels must be 1 or 2, got {self.channels}")


class AudioCapture:
    """Audio capture from INMP441 I2S microphone.

    Provides methods to capture audio from the INMP441 microphone
    connected via I2S to a Raspberry Pi.

    Attributes:
        config: Capture configuration
    """

    def __init__(self, config: Optional[CaptureConfig] = None) -> None:
        """Initialize audio capture.

        Args:
            config: Capture configuration (uses defaults if None)
        """
        self.config = config or CaptureConfig()
        _logger.info(
            f"AudioCapture initialized: device={self.config.device}, "
            f"rate={self.config.sample_rate}, duration={self.config.duration_seconds}s"
        )

    def capture(self) -> np.ndarray:
        """Capture audio and return as numpy array.

        Returns:
            Audio samples as float32 numpy array, normalized to [-1, 1]

        Raises:
            RuntimeError: If capture fails
        """
        # Create temporary file for capture
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            # Capture to temp file
            self.capture_to_file(tmp_path)

            # Load and return audio
            audio, _ = self.load_wav(tmp_path)
            return audio

        finally:
            # Clean up temp file
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    def capture_to_file(self, filepath: str) -> None:
        """Capture audio directly to a WAV file.

        Args:
            filepath: Output WAV file path

        Raises:
            RuntimeError: If arecord command fails
        """
        cmd = [
            "arecord",
            "-D", self.config.device,
            "-f", self.config.format,
            "-r", str(self.config.sample_rate),
            "-c", str(self.config.channels),
            "-d", str(int(self.config.duration_seconds)),
            filepath
        ]

        _logger.debug(f"Running: {' '.join(cmd)}")

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.config.duration_seconds + 5
            )

            if result.returncode != 0:
                raise RuntimeError(
                    f"arecord failed with code {result.returncode}: {result.stderr}"
                )

            _logger.info(f"Audio captured to {filepath}")

        except subprocess.TimeoutExpired:
            raise RuntimeError(
                f"arecord timed out after {self.config.duration_seconds + 5}s"
            )
        except FileNotFoundError:
            raise RuntimeError(
                "arecord not found. Install alsa-utils: sudo apt install alsa-utils"
            )

    def load_wav(self, filepath: str) -> Tuple[np.ndarray, int]:
        """Load a WAV file and return audio samples.

        Args:
            filepath: Path to WAV file

        Returns:
            Tuple of (audio samples as float32, sample rate)
        """
        with wave.open(filepath, 'rb') as wf:
            n_channels = wf.getnchannels()
            sample_width = wf.getsampwidth()
            sample_rate = wf.getframerate()
            n_frames = wf.getnframes()

            frames = wf.readframes(n_frames)

        # Parse based on sample width
        if sample_width == 4:  # 32-bit
            samples = np.frombuffer(frames, dtype=np.int32)
            max_val = 2147483648.0
        elif sample_width == 2:  # 16-bit
            samples = np.frombuffer(frames, dtype=np.int16)
            max_val = 32768.0
        else:
            raise ValueError(f"Unsupported sample width: {sample_width}")

        # Extract left channel if stereo and configured
        if n_channels == 2 and self.config.use_left_channel:
            samples = samples[0::2]

        # Convert to float32 normalized
        audio = samples.astype(np.float32) / max_val

        _logger.debug(
            f"Loaded {filepath}: {len(audio)} samples, "
            f"range [{audio.min():.3f}, {audio.max():.3f}]"
        )

        return audio, sample_rate

    def get_device_info(self) -> dict:
        """Get information about available audio devices.

        Returns:
            Dictionary with device information
        """
        try:
            result = subprocess.run(
                ["arecord", "-l"],
                capture_output=True,
                text=True,
                timeout=5
            )
            return {
                "devices": result.stdout,
                "error": result.stderr if result.returncode != 0 else None
            }
        except Exception as e:
            return {"error": str(e)}

    def test_capture(self, duration: float = 1.0) -> dict:
        """Quick test capture to verify hardware is working.

        Args:
            duration: Test duration in seconds

        Returns:
            Dictionary with test results
        """
        original_duration = self.config.duration_seconds
        self.config.duration_seconds = duration

        try:
            audio = self.capture()

            results = {
                "success": True,
                "samples": len(audio),
                "duration": len(audio) / self.config.sample_rate,
                "min": float(audio.min()),
                "max": float(audio.max()),
                "range": float(audio.max() - audio.min()),
                "rms": float(np.sqrt(np.mean(audio ** 2))),
                "non_zero_pct": float(100 * np.count_nonzero(audio) / len(audio)),
                "has_signal": float(audio.max() - audio.min()) > 0.001
            }

            return results

        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

        finally:
            self.config.duration_seconds = original_duration


# Convenience function for quick capture
def capture_audio(duration: float = 3.0, device: str = "plughw:1,0") -> np.ndarray:
    """Quick audio capture function.

    Args:
        duration: Recording duration in seconds
        device: ALSA device string

    Returns:
        Audio samples as float32 numpy array
    """
    config = CaptureConfig(duration_seconds=duration, device=device)
    capture = AudioCapture(config)
    return capture.capture()
