"""Voice Pipeline for OpenDuck Mini V3

This package provides the complete voice input pipeline:
- VAD (Voice Activity Detection)
- Wake Word Detection (with production-grade pipeline)
- STT (Speech-to-Text)
- Intent Classification

Architecture:
    INMP441 Mic → Audio Capture → VAD → Wake Word → STT → Intent → Action

Production Pipeline (recommended):
    ```python
    from src.voice import WakeWordPipeline, PipelineConfig

    # Create production pipeline with all optimizations
    config = PipelineConfig(
        threshold=0.82,          # Higher threshold for <1% FPR
        confirm_window=5,        # Multi-frame confirmation
        confirm_required=3,      # Require 3/5 frames
        cooldown_seconds=3.0     # Prevent rapid re-triggers
    )
    pipeline = WakeWordPipeline(config)
    pipeline.on_wake_word = lambda r: print(f"Detected: {r.wake_word}!")
    pipeline.start()
    ```

Individual components can also be used standalone:
    ```python
    from src.voice import VoiceActivityDetector, VADConfig
    from src.voice import WakeWordDetector, WakeWordConfig
    from src.voice import SpeechToText, STTConfig
    from src.voice import IntentClassifier, IntentConfig

    # Create components
    vad = VoiceActivityDetector(VADConfig(energy_threshold_db=-35))
    wake = WakeWordDetector(WakeWordConfig(wake_words=["hey openduck"]))
    stt = SpeechToText(STTConfig(language="en"))
    intent = IntentClassifier(IntentConfig(confidence_threshold=0.6))
    ```
"""

# VAD exports
from src.voice.vad import (
    VADConfig,
    VADState,
    VADEvent,
    VADResult,
    VoiceActivityDetector,
)

# Wake Word exports
from src.voice.wake_word import (
    WakeWordConfig,
    WakeWordResult,
    WakeWordDetector,
)

# STT exports
from src.voice.stt import (
    STTConfig,
    STTResult,
    STTBackend,
    SpeechToText,
)

# Intent exports
from src.voice.intent import (
    IntentConfig,
    IntentResult,
    Intent,
    Entity,
    IntentClassifier,
)

# Production Pipeline exports
from src.voice.pipeline import (
    PipelineConfig,
    PipelineState,
    DetectionResult,
    AudioPreprocessor,
    NoiseCalibrator,
    MultiFrameConfirmer,
    WakeWordPipeline,
)

__all__ = [
    # VAD
    'VADConfig',
    'VADState',
    'VADEvent',
    'VADResult',
    'VoiceActivityDetector',
    # Wake Word
    'WakeWordConfig',
    'WakeWordResult',
    'WakeWordDetector',
    # STT
    'STTConfig',
    'STTResult',
    'STTBackend',
    'SpeechToText',
    # Intent
    'IntentConfig',
    'IntentResult',
    'Intent',
    'Entity',
    'IntentClassifier',
    # Production Pipeline
    'PipelineConfig',
    'PipelineState',
    'DetectionResult',
    'AudioPreprocessor',
    'NoiseCalibrator',
    'MultiFrameConfirmer',
    'WakeWordPipeline',
]
