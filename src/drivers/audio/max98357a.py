"""MAX98357A I2S DAC/Amplifier Driver for OpenDuck Mini V3

This module provides a hardware abstraction layer for the MAX98357A I2S
Class D mono amplifier. The MAX98357A converts I2S digital audio to
amplified analog output (3W into 4 ohms).

The MAX98357A is a "dumb" amplifier - it has no configuration registers
or I2C interface. All control is through the I2S data stream and the
GAIN/SD pin. This driver provides a clean API for audio playback.

Hardware:
    - MAX98357A I2S Amplifier (Adafruit or compatible)
    - I2S interface (BCLK, LRCLK, DIN)
    - 3.3V logic compatible
    - 2.5W @ 4 ohm, 1.3W @ 8 ohm output power

Connections:
    - VIN -> 5V (Pi Pin 2 or 4) - NOT 3.3V!
    - GND -> GND (Pi Pin 6)
    - DIN -> GPIO 21 (Pi Pin 40) - I2S Data Out
    - BCLK -> GPIO 18 (Pi Pin 12) - I2S Bit Clock
    - LRCLK -> GPIO 19 (Pi Pin 35) - I2S Word Select
    - GAIN -> GND (15dB gain) or VIN (12dB) or unconnected (9dB)
    - SD -> Not connected (enabled) or GND (shutdown)

Key Features:
    - Simple I2S audio playback
    - Thread-safe via I2S Bus Manager
    - Supports 16kHz (TTS) and 44.1kHz (audio) sample rates
    - Volume control via software scaling
    - Mock mode for development without hardware

Thread Safety:
    All operations use I2SBusManager to prevent bus collisions with
    microphone input. Safe for multi-threaded use.

Example:
    ```python
    from src.drivers.audio.max98357a import MAX98357ADriver

    # Initialize speaker
    speaker = MAX98357ADriver()

    # Play audio data (16-bit PCM)
    audio_samples = [...]  # List of 16-bit samples
    speaker.play_samples(audio_samples)

    # Play WAV file
    speaker.play_wav_file("/path/to/audio.wav")

    # Set volume (0.0 to 1.0)
    speaker.set_volume(0.7)
    ```

Author: Day 17 Implementation
Date: 22 January 2026
"""

import struct
import threading
import time
import wave
from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path
from typing import Optional, Union, List

from .i2s_bus import (
    I2SBusManager,
    I2SConfig,
    I2SDirection,
    SPEAKER_CONFIG_16KHZ,
    SPEAKER_CONFIG_44KHZ,
)


class PlaybackState(Enum):
    """Playback state enumeration.

    Attributes:
        STOPPED: No playback active
        PLAYING: Audio is being played
        PAUSED: Playback paused (can resume)
        ERROR: Playback error occurred
    """
    STOPPED = auto()
    PLAYING = auto()
    PAUSED = auto()
    ERROR = auto()


@dataclass
class MAX98357AConfig:
    """Configuration for MAX98357A amplifier.

    Attributes:
        sample_rate: Output sample rate (16000 or 44100)
        volume: Initial volume level (0.0 to 1.0)
        buffer_size: Audio buffer size in frames
    """
    sample_rate: int = 16000
    volume: float = 0.8
    buffer_size: int = 1024

    def __post_init__(self):
        """Validate configuration."""
        if self.sample_rate not in (16000, 44100):
            raise ValueError(f"sample_rate must be 16000 or 44100, got {self.sample_rate}")
        if not 0.0 <= self.volume <= 1.0:
            raise ValueError(f"volume must be 0.0-1.0, got {self.volume}")
        if not 64 <= self.buffer_size <= 8192:
            raise ValueError(f"buffer_size must be 64-8192, got {self.buffer_size}")


class MAX98357ADriver:
    """Driver for MAX98357A I2S amplifier.

    Provides thread-safe audio playback through the MAX98357A amplifier
    using the I2S Bus Manager for bus coordination.

    Attributes:
        config: Driver configuration
        _volume: Current volume level (0.0-1.0)
        _state: Current playback state
        _bus_manager: I2S bus manager singleton
    """

    def __init__(self, config: Optional[MAX98357AConfig] = None):
        """Initialize MAX98357A driver.

        Args:
            config: Optional configuration. Uses defaults if not provided.

        Raises:
            RuntimeError: If I2S bus manager cannot be initialized.
        """
        self.config = config or MAX98357AConfig()
        self._volume = self.config.volume
        self._state = PlaybackState.STOPPED
        self._lock = threading.Lock()

        # Playback control
        self._stop_requested = threading.Event()
        self._playback_thread: Optional[threading.Thread] = None

        # Get I2S bus manager singleton
        self._bus_manager = I2SBusManager.get_instance()

        # Select I2S configuration based on sample rate
        if self.config.sample_rate == 16000:
            self._i2s_config = SPEAKER_CONFIG_16KHZ
        else:
            self._i2s_config = SPEAKER_CONFIG_44KHZ

    @property
    def volume(self) -> float:
        """Get current volume level.

        Returns:
            Volume level from 0.0 (silent) to 1.0 (full).
        """
        return self._volume

    @volume.setter
    def volume(self, value: float) -> None:
        """Set volume level.

        Args:
            value: Volume level from 0.0 to 1.0.

        Raises:
            ValueError: If volume is outside valid range.
        """
        if not 0.0 <= value <= 1.0:
            raise ValueError(f"volume must be 0.0-1.0, got {value}")
        self._volume = value

    def set_volume(self, level: float) -> None:
        """Set playback volume.

        Args:
            level: Volume level from 0.0 (mute) to 1.0 (full).

        Raises:
            ValueError: If level is outside valid range.
        """
        self.volume = level

    def get_state(self) -> PlaybackState:
        """Get current playback state.

        Returns:
            Current PlaybackState.
        """
        with self._lock:
            return self._state

    def _set_state(self, state: PlaybackState) -> None:
        """Set playback state (internal use).

        Args:
            state: New playback state.
        """
        with self._lock:
            self._state = state

    def _apply_volume(self, samples: bytes) -> bytes:
        """Apply volume scaling to audio samples.

        Args:
            samples: Raw 16-bit PCM audio data.

        Returns:
            Volume-scaled audio data.
        """
        if self._volume >= 0.99:
            return samples

        if self._volume <= 0.01:
            return bytes(len(samples))

        # Unpack, scale, repack 16-bit samples
        num_samples = len(samples) // 2
        values = struct.unpack(f'<{num_samples}h', samples)
        scaled = [int(v * self._volume) for v in values]
        # Clamp to 16-bit range
        scaled = [max(-32768, min(32767, v)) for v in scaled]
        return struct.pack(f'<{num_samples}h', *scaled)

    def play_samples(
        self,
        samples: Union[bytes, List[int]],
        blocking: bool = True
    ) -> bool:
        """Play audio samples.

        Args:
            samples: Audio data as bytes (16-bit PCM) or list of int16 values.
            blocking: If True, wait for playback to complete.

        Returns:
            True if playback started successfully.

        Raises:
            RuntimeError: If already playing.
            ValueError: If samples format is invalid.
        """
        if self.get_state() == PlaybackState.PLAYING:
            raise RuntimeError("Already playing audio")

        # Convert list to bytes if needed
        if isinstance(samples, list):
            samples = struct.pack(f'<{len(samples)}h', *samples)

        if len(samples) == 0:
            return True

        if len(samples) % 2 != 0:
            raise ValueError("samples must contain 16-bit values (even byte count)")

        self._stop_requested.clear()

        if blocking:
            self._play_samples_blocking(samples)
            return True
        else:
            self._playback_thread = threading.Thread(
                target=self._play_samples_blocking,
                args=(samples,),
                daemon=True
            )
            self._playback_thread.start()
            return True

    def _play_samples_blocking(self, samples: bytes) -> None:
        """Play samples synchronously (internal).

        Args:
            samples: Raw 16-bit PCM audio data.
        """
        self._set_state(PlaybackState.PLAYING)

        try:
            # Apply volume
            scaled = self._apply_volume(samples)

            # Play through I2S
            with self._bus_manager.acquire_bus(I2SDirection.OUTPUT, self._i2s_config) as stream:
                # Write in chunks
                chunk_size = self.config.buffer_size * 2  # 2 bytes per sample
                offset = 0

                while offset < len(scaled) and not self._stop_requested.is_set():
                    chunk = scaled[offset:offset + chunk_size]
                    stream.write(chunk)
                    offset += len(chunk)

                    # Small delay to prevent buffer underrun
                    time.sleep(0.001)

        except Exception as e:
            self._set_state(PlaybackState.ERROR)
            raise RuntimeError(f"Playback failed: {e}")
        finally:
            if not self._stop_requested.is_set():
                self._set_state(PlaybackState.STOPPED)

    def play_wav_file(self, filepath: Union[str, Path], blocking: bool = True) -> bool:
        """Play a WAV audio file.

        Args:
            filepath: Path to WAV file.
            blocking: If True, wait for playback to complete.

        Returns:
            True if playback started successfully.

        Raises:
            FileNotFoundError: If WAV file doesn't exist.
            ValueError: If WAV format is unsupported.
        """
        filepath = Path(filepath)
        if not filepath.exists():
            raise FileNotFoundError(f"WAV file not found: {filepath}")

        with wave.open(str(filepath), 'rb') as wav:
            # Validate format
            if wav.getsampwidth() != 2:
                raise ValueError(f"Only 16-bit WAV supported, got {wav.getsampwidth()*8}-bit")

            channels = wav.getnchannels()
            sample_rate = wav.getframerate()

            # Read all frames
            frames = wav.readframes(wav.getnframes())

        # Convert stereo to mono if needed
        if channels == 2:
            frames = self._stereo_to_mono(frames)

        # Resample if needed
        if sample_rate != self.config.sample_rate:
            frames = self._resample(frames, sample_rate, self.config.sample_rate)

        return self.play_samples(frames, blocking=blocking)

    def _stereo_to_mono(self, samples: bytes) -> bytes:
        """Convert stereo audio to mono by averaging channels.

        Args:
            samples: Stereo 16-bit PCM data (L, R, L, R, ...).

        Returns:
            Mono 16-bit PCM data.
        """
        num_frames = len(samples) // 4  # 4 bytes per stereo frame
        stereo = struct.unpack(f'<{num_frames * 2}h', samples)
        mono = [(stereo[i] + stereo[i + 1]) // 2 for i in range(0, len(stereo), 2)]
        return struct.pack(f'<{num_frames}h', *mono)

    def _resample(self, samples: bytes, from_rate: int, to_rate: int) -> bytes:
        """Simple linear resampling.

        Args:
            samples: Source audio data.
            from_rate: Source sample rate.
            to_rate: Target sample rate.

        Returns:
            Resampled audio data.

        Note:
            This is a simple implementation. For production, use scipy.signal.resample.
        """
        if from_rate == to_rate:
            return samples

        # Unpack samples
        num_samples = len(samples) // 2
        values = struct.unpack(f'<{num_samples}h', samples)

        # Calculate output length
        ratio = to_rate / from_rate
        out_length = int(num_samples * ratio)

        # Linear interpolation
        resampled = []
        for i in range(out_length):
            src_idx = i / ratio
            idx_low = int(src_idx)
            idx_high = min(idx_low + 1, num_samples - 1)
            frac = src_idx - idx_low
            value = int(values[idx_low] * (1 - frac) + values[idx_high] * frac)
            resampled.append(value)

        return struct.pack(f'<{out_length}h', *resampled)

    def play_tone(
        self,
        frequency: float,
        duration_ms: int,
        blocking: bool = True
    ) -> bool:
        """Play a sine wave tone.

        Args:
            frequency: Tone frequency in Hz.
            duration_ms: Duration in milliseconds.
            blocking: If True, wait for tone to complete.

        Returns:
            True if playback started successfully.
        """
        import math

        num_samples = int(self.config.sample_rate * duration_ms / 1000)
        samples = []

        for i in range(num_samples):
            t = i / self.config.sample_rate
            value = int(16000 * math.sin(2 * math.pi * frequency * t))
            samples.append(value)

        return self.play_samples(samples, blocking=blocking)

    def play_beep(self, blocking: bool = True) -> bool:
        """Play a short beep sound.

        Args:
            blocking: If True, wait for beep to complete.

        Returns:
            True if playback started successfully.
        """
        return self.play_tone(800, 100, blocking=blocking)

    def stop(self) -> None:
        """Stop current playback."""
        self._stop_requested.set()

        if self._playback_thread and self._playback_thread.is_alive():
            self._playback_thread.join(timeout=1.0)

        self._set_state(PlaybackState.STOPPED)

    def is_playing(self) -> bool:
        """Check if audio is currently playing.

        Returns:
            True if playback is active.
        """
        return self.get_state() == PlaybackState.PLAYING


def create_max98357a_driver(
    sample_rate: int = 16000,
    volume: float = 0.8
) -> MAX98357ADriver:
    """Factory function to create MAX98357A driver.

    Args:
        sample_rate: Output sample rate (16000 or 44100).
        volume: Initial volume (0.0-1.0).

    Returns:
        Configured MAX98357ADriver instance.
    """
    config = MAX98357AConfig(sample_rate=sample_rate, volume=volume)
    return MAX98357ADriver(config)
