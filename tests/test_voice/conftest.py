"""Shared fixtures for voice pipeline tests.

Provides mock audio data, sample generators, and common test utilities
for VAD, Wake Word, STT, and Intent testing.
"""

from __future__ import annotations

import numpy as np
import pytest
from dataclasses import dataclass
from typing import List, Optional, Generator
import math


@dataclass
class MockAudioConfig:
    """Configuration for mock audio generation."""
    sample_rate: int = 16000
    channels: int = 1
    dtype: np.dtype = np.float32


@pytest.fixture
def audio_config() -> MockAudioConfig:
    """Provide standard audio configuration."""
    return MockAudioConfig()


@pytest.fixture
def silence_samples(audio_config: MockAudioConfig) -> np.ndarray:
    """Generate 1 second of silence (very low noise floor)."""
    # Silence with tiny noise (simulates real mic noise floor)
    duration_samples = audio_config.sample_rate
    noise_floor_db = -70  # Very quiet
    amplitude = 10 ** (noise_floor_db / 20)
    return np.random.uniform(-amplitude, amplitude, duration_samples).astype(np.float32)


@pytest.fixture
def speech_samples(audio_config: MockAudioConfig) -> np.ndarray:
    """Generate 1 second of simulated speech (sine wave + harmonics)."""
    duration_samples = audio_config.sample_rate
    t = np.linspace(0, 1, duration_samples, dtype=np.float32)

    # Simulate speech with fundamental + harmonics (vowel-like)
    fundamental = 150  # Hz (average male voice)
    speech = (
        0.5 * np.sin(2 * np.pi * fundamental * t) +
        0.25 * np.sin(2 * np.pi * fundamental * 2 * t) +
        0.125 * np.sin(2 * np.pi * fundamental * 3 * t) +
        0.0625 * np.sin(2 * np.pi * fundamental * 4 * t)
    )

    # Add amplitude envelope (attack-sustain-release)
    envelope = np.ones_like(t)
    attack_samples = int(0.05 * audio_config.sample_rate)
    release_samples = int(0.1 * audio_config.sample_rate)
    envelope[:attack_samples] = np.linspace(0, 1, attack_samples)
    envelope[-release_samples:] = np.linspace(1, 0, release_samples)

    return (speech * envelope * 0.3).astype(np.float32)  # -10dB nominal


@pytest.fixture
def loud_samples(audio_config: MockAudioConfig) -> np.ndarray:
    """Generate 1 second of loud audio (clipping level)."""
    duration_samples = audio_config.sample_rate
    t = np.linspace(0, 1, duration_samples, dtype=np.float32)
    return (0.9 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)


@pytest.fixture
def mixed_audio(audio_config: MockAudioConfig) -> np.ndarray:
    """Generate audio with silence-speech-silence pattern (3 seconds)."""
    sr = audio_config.sample_rate

    # 1s silence + 1s speech + 1s silence
    silence1 = np.zeros(sr, dtype=np.float32) + np.random.uniform(-0.001, 0.001, sr).astype(np.float32)

    t = np.linspace(0, 1, sr, dtype=np.float32)
    speech = (0.3 * np.sin(2 * np.pi * 200 * t) *
              np.sin(2 * np.pi * 3 * t)).astype(np.float32)  # Modulated speech-like

    silence2 = np.zeros(sr, dtype=np.float32) + np.random.uniform(-0.001, 0.001, sr).astype(np.float32)

    return np.concatenate([silence1, speech, silence2])


@pytest.fixture
def wake_word_samples(audio_config: MockAudioConfig) -> np.ndarray:
    """Generate simulated 'hey openduck' audio pattern (1.5 seconds)."""
    sr = audio_config.sample_rate
    duration = int(1.5 * sr)
    t = np.linspace(0, 1.5, duration, dtype=np.float32)

    # Simulate "hey" (0-0.3s), pause (0.3-0.4s), "openduck" (0.4-1.3s)
    audio = np.zeros(duration, dtype=np.float32)

    # "hey" segment
    hey_start = 0
    hey_end = int(0.3 * sr)
    audio[hey_start:hey_end] = 0.25 * np.sin(2 * np.pi * 250 * t[hey_start:hey_end])

    # "openduck" segment
    od_start = int(0.4 * sr)
    od_end = int(1.3 * sr)
    audio[od_start:od_end] = 0.3 * np.sin(2 * np.pi * 180 * t[od_start:od_end])

    return audio


def generate_audio_frames(
    audio: np.ndarray,
    frame_size_ms: int = 20,
    sample_rate: int = 16000
) -> Generator[np.ndarray, None, None]:
    """Split audio into frames for streaming simulation.

    Args:
        audio: Full audio array
        frame_size_ms: Frame size in milliseconds
        sample_rate: Sample rate in Hz

    Yields:
        Audio frames of specified size
    """
    frame_samples = int(sample_rate * frame_size_ms / 1000)

    for i in range(0, len(audio), frame_samples):
        frame = audio[i:i + frame_samples]
        if len(frame) == frame_samples:
            yield frame


def calculate_rms_db(samples: np.ndarray) -> float:
    """Calculate RMS level in dB for audio samples.

    Args:
        samples: Audio samples (float32, normalized -1 to 1)

    Returns:
        RMS level in dB (0 dB = full scale)
    """
    if len(samples) == 0:
        return -100.0

    rms = np.sqrt(np.mean(samples ** 2))
    if rms < 1e-10:
        return -100.0

    return 20 * np.log10(rms)


def calculate_energy(samples: np.ndarray) -> float:
    """Calculate energy (sum of squares) for audio samples.

    Args:
        samples: Audio samples

    Returns:
        Energy value
    """
    return float(np.sum(samples ** 2))
