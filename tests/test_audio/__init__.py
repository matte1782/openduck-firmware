"""Audio subsystem unit tests.

Tests cover:
- I2S Bus Manager (singleton, thread-safety, context manager)
- INMP441 Microphone Driver (capture, levels, mock mode)
- Audio Capture Pipeline (ring buffer, VAD, callbacks)
"""
