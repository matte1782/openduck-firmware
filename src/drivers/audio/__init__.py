"""Audio drivers (I2S amplifier and microphone).

This module provides drivers for the OpenDuck Mini V3 audio subsystem:
- INMP441Driver: I2S MEMS microphone for voice capture
- AudioCapturePipeline: Continuous capture with ring buffer and VAD
- VoiceActivityDetector: Simple energy-based speech detection
- I2SBusManager: Thread-safe singleton for I2S bus access
- MAX98357A: I2S amplifier for audio output (planned)

Three complementary APIs are provided:

1. INMP441Driver (inmp441.py):
   - Queue-based sample buffering
   - Direct read_samples() interface
   - Wait-for-sound functionality
   - Good for simple capture tasks

2. AudioCapturePipeline (audio_capture.py):
   - Ring buffer for continuous capture (<50ms latency)
   - Background thread with callbacks
   - Voice Activity Detection (VAD) foundation
   - Good for real-time speech processing

3. I2SBusManager (i2s_bus.py):
   - Thread-safe singleton for I2S bus access
   - Low-level I2S configuration
   - Good for custom audio implementations

Example (Simple capture):
    ```python
    from src.drivers.audio import INMP441Driver

    mic = INMP441Driver()
    mic.start_capture()
    samples = mic.read_samples(1024)
    level = mic.get_level_db()
    mic.stop_capture()
    ```

Example (Pipeline with VAD):
    ```python
    from src.drivers.audio import AudioCapturePipeline, AudioCaptureConfig

    config = AudioCaptureConfig(vad_threshold_db=-35.0)
    pipeline = AudioCapturePipeline(config)
    pipeline.start()

    audio = pipeline.get_audio(duration_ms=500)
    if pipeline.vad.is_speech(audio.samples):
        print("Speech detected!")

    pipeline.stop()
    ```

I2S Bus Example:
    ```python
    from src.drivers.audio import (
        get_i2s_bus_manager, I2SDirection, MIC_CONFIG_16KHZ
    )

    # Get singleton instance
    manager = get_i2s_bus_manager()

    # Acquire bus for microphone input
    with manager.acquire_bus(I2SDirection.INPUT, MIC_CONFIG_16KHZ) as stream:
        audio_data = stream.read(1024)
    ```
"""

# INMP441 microphone driver
from .inmp441 import (
    INMP441Driver,
    INMP441Config,
    AudioSample as INMP441AudioSample,
    CaptureState,
    create_inmp441_driver,
)

# Audio capture pipeline with ring buffer and VAD
from .audio_capture import (
    AudioCapturePipeline,
    AudioCaptureConfig,
    AudioCaptureState,
    AudioRingBuffer,
    AudioSample,
    VoiceActivityDetector,
    create_capture_pipeline,
)

# I2S bus manager
from .i2s_bus import (
    I2SBusManager,
    I2SConfig,
    I2SDirection,
    I2SPinConfig,
    MockI2SStream,
    get_i2s_bus_manager,
    MIC_CONFIG_16KHZ,
    SPEAKER_CONFIG_44KHZ,
    SPEAKER_CONFIG_16KHZ,
)

__all__ = [
    # INMP441 microphone driver
    "INMP441Driver",
    "INMP441Config",
    "INMP441AudioSample",
    "CaptureState",
    "create_inmp441_driver",
    # Audio capture pipeline
    "AudioCapturePipeline",
    "AudioCaptureConfig",
    "AudioCaptureState",
    "AudioRingBuffer",
    "AudioSample",
    "VoiceActivityDetector",
    "create_capture_pipeline",
    # I2S bus manager
    "I2SBusManager",
    "I2SConfig",
    "I2SDirection",
    "I2SPinConfig",
    "MockI2SStream",
    "get_i2s_bus_manager",
    "MIC_CONFIG_16KHZ",
    "SPEAKER_CONFIG_44KHZ",
    "SPEAKER_CONFIG_16KHZ",
]
