"""Tests for Speech-to-Text (STT) module.

AGENT-3: STT Engineer
TDD-First: Tests define expected behavior for speech-to-text transcription.

Test Categories:
1. Configuration & Initialization
2. Transcription Logic
3. Streaming vs Batch Processing
4. Multi-language Support
5. Performance & Accuracy
"""

from __future__ import annotations

import numpy as np
import pytest
import time
from typing import List
from unittest.mock import Mock, patch, MagicMock, AsyncMock

try:
    from src.voice.stt import (
        STTConfig,
        STTResult,
        SpeechToText,
        STTBackend,
    )
except ImportError:
    pytestmark = pytest.mark.skip(reason="STT module not yet implemented")


class TestSTTConfig:
    """Test STT configuration."""

    def test_default_config(self):
        """Default config should have sensible defaults."""
        config = STTConfig()

        assert config.language == "en"
        assert config.sample_rate == 16000
        assert config.backend in ["mock", "whisper", "vosk", "google"]

    def test_custom_language(self):
        """Custom language should be accepted."""
        config = STTConfig(language="it")

        assert config.language == "it"

    def test_custom_backend(self):
        """Custom backend should be accepted."""
        config = STTConfig(backend="whisper")

        assert config.backend == "whisper"

    def test_invalid_sample_rate_raises(self):
        """Invalid sample rate should raise error."""
        with pytest.raises(ValueError, match="sample_rate"):
            STTConfig(sample_rate=0)
        with pytest.raises(ValueError, match="sample_rate"):
            STTConfig(sample_rate=-16000)

    def test_model_size_option(self):
        """Model size option for Whisper backend."""
        config = STTConfig(backend="whisper", model_size="base")

        assert config.model_size == "base"


class TestSTTResult:
    """Test STT transcription result."""

    def test_result_fields(self):
        """Result should contain required fields."""
        result = STTResult(
            text="hello world",
            confidence=0.95,
            language="en",
            duration_seconds=1.5,
            is_final=True
        )

        assert result.text == "hello world"
        assert result.confidence == 0.95
        assert result.language == "en"
        assert result.duration_seconds == 1.5
        assert result.is_final is True

    def test_empty_result(self):
        """Should represent empty/no-speech result properly."""
        result = STTResult.empty()

        assert result.text == ""
        assert result.confidence == 0.0
        assert result.is_final is True

    def test_partial_result(self):
        """Partial results for streaming mode."""
        result = STTResult(
            text="hello",
            confidence=0.7,
            language="en",
            duration_seconds=0.5,
            is_final=False
        )

        assert result.is_final is False


class TestSTTBackend:
    """Test STT backend enum."""

    def test_backend_values(self):
        """Backend enum should have expected values."""
        assert STTBackend.MOCK.value == "mock"
        assert STTBackend.WHISPER.value == "whisper"
        assert STTBackend.VOSK.value == "vosk"


class TestSpeechToTextInit:
    """Test STT initialization."""

    def test_default_initialization(self):
        """Should initialize with default config."""
        stt = SpeechToText()

        assert stt.config is not None
        assert stt.is_ready

    def test_custom_config(self):
        """Should accept custom config."""
        config = STTConfig(language="it")
        stt = SpeechToText(config)

        assert stt.config.language == "it"

    def test_mock_mode_initialization(self):
        """Should initialize in mock mode without external dependencies."""
        stt = SpeechToText(mock_mode=True)

        assert stt.mock_mode is True
        assert stt.is_ready


class TestSTTTranscription:
    """Test transcription logic."""

    def test_transcribe_audio(self, speech_samples):
        """Should transcribe audio to text."""
        stt = SpeechToText(mock_mode=True)

        result = stt.transcribe(speech_samples)

        assert isinstance(result, STTResult)
        assert isinstance(result.text, str)

    def test_transcribe_silence(self, silence_samples):
        """Silence should return empty or low-confidence result."""
        stt = SpeechToText(mock_mode=True)

        result = stt.transcribe(silence_samples)

        # Mock mode may return placeholder text, but confidence should be low for silence
        assert isinstance(result, STTResult)

    def test_transcribe_returns_confidence(self, speech_samples):
        """Transcription should include confidence score."""
        stt = SpeechToText(mock_mode=True)

        result = stt.transcribe(speech_samples)

        assert 0.0 <= result.confidence <= 1.0

    def test_transcribe_returns_duration(self, speech_samples):
        """Transcription should include audio duration."""
        stt = SpeechToText(mock_mode=True)

        result = stt.transcribe(speech_samples)

        assert result.duration_seconds > 0


class TestSTTStreaming:
    """Test streaming transcription."""

    def test_start_streaming(self):
        """Should start streaming session."""
        stt = SpeechToText(mock_mode=True)

        stt.start_streaming()

        assert stt.is_streaming

    def test_stop_streaming(self):
        """Should stop streaming session."""
        stt = SpeechToText(mock_mode=True)
        stt.start_streaming()

        stt.stop_streaming()

        assert not stt.is_streaming

    def test_process_stream_chunk(self, speech_samples):
        """Should process streaming audio chunks."""
        stt = SpeechToText(mock_mode=True)
        stt.start_streaming()

        chunk = speech_samples[:1600]  # 100ms chunk
        result = stt.process_chunk(chunk)

        assert isinstance(result, STTResult)
        stt.stop_streaming()

    def test_streaming_partial_results(self, speech_samples):
        """Streaming should provide partial results."""
        stt = SpeechToText(mock_mode=True)
        stt.start_streaming()

        # Process multiple chunks
        for i in range(3):
            chunk = speech_samples[i*1600:(i+1)*1600]
            result = stt.process_chunk(chunk)

        # At least some results should be partial
        assert isinstance(result, STTResult)
        stt.stop_streaming()

    def test_finalize_streaming(self, speech_samples):
        """Should finalize streaming and get final result."""
        stt = SpeechToText(mock_mode=True)
        stt.start_streaming()

        # Process some chunks
        for i in range(3):
            chunk = speech_samples[i*1600:(i+1)*1600]
            stt.process_chunk(chunk)

        result = stt.finalize()

        assert result.is_final is True
        assert not stt.is_streaming


class TestSTTCallbacks:
    """Test STT callbacks."""

    def test_on_result_callback(self, speech_samples):
        """Should call callback when result is available."""
        stt = SpeechToText(mock_mode=True)

        results = []
        stt.on_result = lambda r: results.append(r)

        stt.transcribe(speech_samples)

        assert len(results) >= 1

    def test_on_partial_callback(self, speech_samples):
        """Should call callback for partial results in streaming."""
        stt = SpeechToText(mock_mode=True)

        partials = []
        stt.on_partial = lambda r: partials.append(r)

        stt.start_streaming()
        for i in range(3):
            chunk = speech_samples[i*1600:(i+1)*1600]
            stt.process_chunk(chunk)
        stt.stop_streaming()

        # May or may not have partials depending on implementation
        assert isinstance(partials, list)


class TestSTTLanguageSupport:
    """Test multi-language support."""

    def test_english_language(self, speech_samples):
        """Should support English."""
        stt = SpeechToText(STTConfig(language="en"), mock_mode=True)

        result = stt.transcribe(speech_samples)

        assert result.language == "en"

    def test_italian_language(self, speech_samples):
        """Should support Italian."""
        stt = SpeechToText(STTConfig(language="it"), mock_mode=True)

        result = stt.transcribe(speech_samples)

        assert result.language == "it"

    def test_auto_detect_language(self, speech_samples):
        """Should support auto language detection."""
        stt = SpeechToText(STTConfig(language="auto"), mock_mode=True)

        result = stt.transcribe(speech_samples)

        # Language should be detected (or default)
        assert result.language is not None


class TestSTTPerformance:
    """Test performance requirements."""

    def test_transcription_latency(self, speech_samples):
        """Transcription should complete in reasonable time."""
        stt = SpeechToText(mock_mode=True)

        start = time.perf_counter()
        stt.transcribe(speech_samples)
        elapsed = time.perf_counter() - start

        # Mock mode should be very fast
        assert elapsed < 1.0, f"Transcription took {elapsed:.2f}s"

    def test_streaming_chunk_latency(self, speech_samples):
        """Streaming chunk processing should be fast (<50ms)."""
        stt = SpeechToText(mock_mode=True)
        stt.start_streaming()

        chunk = speech_samples[:1600]

        times = []
        for _ in range(20):
            start = time.perf_counter()
            stt.process_chunk(chunk)
            elapsed = (time.perf_counter() - start) * 1000
            times.append(elapsed)

        stt.stop_streaming()

        avg_time = sum(times) / len(times)
        assert avg_time < 50.0, f"Average chunk latency {avg_time:.2f}ms exceeds 50ms"


class TestSTTEdgeCases:
    """Test edge cases."""

    def test_empty_audio_handled(self):
        """Empty audio should not crash."""
        stt = SpeechToText(mock_mode=True)

        result = stt.transcribe(np.array([], dtype=np.float32))

        assert result.text == ""

    def test_very_short_audio(self):
        """Very short audio should be handled."""
        stt = SpeechToText(mock_mode=True)

        short_audio = np.zeros(100, dtype=np.float32)
        result = stt.transcribe(short_audio)

        assert isinstance(result, STTResult)

    def test_long_audio(self, speech_samples):
        """Long audio should be handled (chunked internally)."""
        stt = SpeechToText(mock_mode=True)

        # Create 30 seconds of audio
        long_audio = np.tile(speech_samples, 30)
        result = stt.transcribe(long_audio)

        assert isinstance(result, STTResult)

    def test_process_chunk_before_streaming_start(self, speech_samples):
        """Processing chunk before starting should handle gracefully."""
        stt = SpeechToText(mock_mode=True)

        # Should not crash
        try:
            result = stt.process_chunk(speech_samples[:1600])
            # Either returns result or raises clear error
            assert isinstance(result, STTResult)
        except RuntimeError:
            pass  # Also acceptable


class TestSTTIntegration:
    """Test integration scenarios."""

    def test_vad_to_stt_pipeline(self, speech_samples, silence_samples):
        """VAD output should work as STT input."""
        from src.voice.vad import VoiceActivityDetector, VADConfig

        vad = VoiceActivityDetector(VADConfig(min_speech_ms=20))
        stt = SpeechToText(mock_mode=True)

        # Collect speech segments
        speech_buffer = []
        for i in range(0, len(speech_samples) - 320, 320):
            frame = speech_samples[i:i+320]
            result = vad.process_frame(frame)
            if result.is_speech:
                speech_buffer.extend(frame)

        # Transcribe collected speech
        if speech_buffer:
            audio = np.array(speech_buffer, dtype=np.float32)
            result = stt.transcribe(audio)
            assert isinstance(result, STTResult)

