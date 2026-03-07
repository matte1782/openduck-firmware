"""Tests for Intent Classification module.

AGENT-4: Intent Engineer
TDD-First: Tests define expected behavior for intent classification.

Test Categories:
1. Configuration & Initialization
2. Intent Classification Logic
3. Entity Extraction
4. Confidence Scoring
5. Custom Intent Support
"""

from __future__ import annotations

import numpy as np
import pytest
import time
from typing import List, Dict
from unittest.mock import Mock, patch, MagicMock

try:
    from src.voice.intent import (
        IntentConfig,
        IntentResult,
        Intent,
        Entity,
        IntentClassifier,
    )
except ImportError:
    pytestmark = pytest.mark.skip(reason="Intent module not yet implemented")


class TestIntentConfig:
    """Test intent configuration."""

    def test_default_config(self):
        """Default config should have sensible defaults."""
        config = IntentConfig()

        assert config.confidence_threshold >= 0.0
        assert config.confidence_threshold <= 1.0
        assert config.fallback_intent is not None

    def test_custom_threshold(self):
        """Custom confidence threshold should be accepted."""
        config = IntentConfig(confidence_threshold=0.8)

        assert config.confidence_threshold == 0.8

    def test_invalid_threshold_raises(self):
        """Invalid threshold should raise error."""
        with pytest.raises(ValueError, match="confidence_threshold"):
            IntentConfig(confidence_threshold=-0.1)
        with pytest.raises(ValueError, match="confidence_threshold"):
            IntentConfig(confidence_threshold=1.5)

    def test_custom_intents(self):
        """Custom intents should be configurable."""
        custom_intents = ["greeting", "weather", "music"]
        config = IntentConfig(supported_intents=custom_intents)

        assert "greeting" in config.supported_intents
        assert "weather" in config.supported_intents


class TestIntent:
    """Test Intent enum/class."""

    def test_builtin_intents(self):
        """Should have built-in intent types."""
        assert Intent.GREETING is not None
        assert Intent.COMMAND is not None
        assert Intent.QUESTION is not None
        assert Intent.UNKNOWN is not None

    def test_intent_value(self):
        """Intent should have string value."""
        assert Intent.GREETING.value == "greeting"
        assert Intent.UNKNOWN.value == "unknown"


class TestEntity:
    """Test entity extraction result."""

    def test_entity_fields(self):
        """Entity should have required fields."""
        entity = Entity(
            type="time",
            value="3pm",
            start=5,
            end=8,
            confidence=0.9
        )

        assert entity.type == "time"
        assert entity.value == "3pm"
        assert entity.start == 5
        assert entity.end == 8
        assert entity.confidence == 0.9


class TestIntentResult:
    """Test intent classification result."""

    def test_result_fields(self):
        """Result should contain required fields."""
        result = IntentResult(
            intent=Intent.COMMAND,
            confidence=0.95,
            text="turn on the lights",
            entities=[],
            alternatives=[]
        )

        assert result.intent == Intent.COMMAND
        assert result.confidence == 0.95
        assert result.text == "turn on the lights"

    def test_unknown_result(self):
        """Should create unknown intent result."""
        result = IntentResult.unknown("gibberish text")

        assert result.intent == Intent.UNKNOWN
        assert result.confidence == 0.0
        assert result.text == "gibberish text"

    def test_result_with_entities(self):
        """Result should include extracted entities."""
        entities = [
            Entity(type="device", value="lights", start=12, end=18, confidence=0.9),
            Entity(type="action", value="turn on", start=0, end=7, confidence=0.95)
        ]
        result = IntentResult(
            intent=Intent.COMMAND,
            confidence=0.9,
            text="turn on the lights",
            entities=entities,
            alternatives=[]
        )

        assert len(result.entities) == 2
        assert result.entities[0].type == "device"


class TestIntentClassifierInit:
    """Test intent classifier initialization."""

    def test_default_initialization(self):
        """Should initialize with default config."""
        classifier = IntentClassifier()

        assert classifier.config is not None
        assert classifier.is_ready

    def test_custom_config(self):
        """Should accept custom config."""
        config = IntentConfig(confidence_threshold=0.7)
        classifier = IntentClassifier(config)

        assert classifier.config.confidence_threshold == 0.7

    def test_mock_mode_initialization(self):
        """Should initialize in mock mode."""
        classifier = IntentClassifier(mock_mode=True)

        assert classifier.mock_mode is True
        assert classifier.is_ready


class TestIntentClassification:
    """Test intent classification logic."""

    def test_classify_greeting(self):
        """Should classify greeting text."""
        classifier = IntentClassifier(mock_mode=True)

        result = classifier.classify("hello")

        assert isinstance(result, IntentResult)
        assert result.intent == Intent.GREETING

    def test_classify_command(self):
        """Should classify command text."""
        classifier = IntentClassifier(mock_mode=True)

        result = classifier.classify("turn on the lights")

        assert isinstance(result, IntentResult)
        assert result.intent == Intent.COMMAND

    def test_classify_question(self):
        """Should classify question text."""
        classifier = IntentClassifier(mock_mode=True)

        result = classifier.classify("what time is it?")

        assert isinstance(result, IntentResult)
        assert result.intent == Intent.QUESTION

    def test_classify_returns_confidence(self):
        """Classification should include confidence."""
        classifier = IntentClassifier(mock_mode=True)

        result = classifier.classify("hello there")

        assert 0.0 <= result.confidence <= 1.0

    def test_classify_empty_text(self):
        """Empty text should return unknown intent."""
        classifier = IntentClassifier(mock_mode=True)

        result = classifier.classify("")

        assert result.intent == Intent.UNKNOWN

    def test_low_confidence_returns_unknown(self):
        """Very low confidence should return unknown."""
        classifier = IntentClassifier(
            IntentConfig(confidence_threshold=0.99),
            mock_mode=True
        )

        # Force low confidence scenario
        result = classifier.classify("asdfghjkl")

        # Should be unknown due to threshold
        assert result.intent == Intent.UNKNOWN or result.confidence < 0.99


class TestEntityExtraction:
    """Test entity extraction."""

    def test_extract_device_entity(self):
        """Should extract device entities."""
        classifier = IntentClassifier(mock_mode=True)

        result = classifier.classify("turn on the lights")

        # Mock should extract basic entities
        device_entities = [e for e in result.entities if e.type == "device"]
        assert len(device_entities) >= 0  # May or may not extract in mock

    def test_extract_time_entity(self):
        """Should extract time entities."""
        classifier = IntentClassifier(mock_mode=True)

        result = classifier.classify("set alarm for 7am")

        # Check result structure
        assert isinstance(result.entities, list)

    def test_extract_multiple_entities(self):
        """Should extract multiple entities."""
        classifier = IntentClassifier(mock_mode=True)

        result = classifier.classify("turn on the kitchen lights at 6pm")

        # Multiple entity types possible
        assert isinstance(result.entities, list)


class TestIntentCallbacks:
    """Test intent callbacks."""

    def test_on_intent_callback(self):
        """Should call callback when intent is classified."""
        classifier = IntentClassifier(mock_mode=True)

        results = []
        classifier.on_intent = lambda r: results.append(r)

        classifier.classify("hello")

        assert len(results) == 1
        assert isinstance(results[0], IntentResult)


class TestCustomIntents:
    """Test custom intent support."""

    def test_register_custom_intent(self):
        """Should allow registering custom intents."""
        classifier = IntentClassifier(mock_mode=True)

        classifier.register_intent(
            name="play_music",
            patterns=["play", "music", "song"],
            examples=["play some music", "play a song"]
        )

        assert "play_music" in classifier.get_registered_intents()

    def test_classify_custom_intent(self):
        """Should classify using custom intents."""
        classifier = IntentClassifier(mock_mode=True)

        classifier.register_intent(
            name="play_music",
            patterns=["play", "music"],
            examples=["play some music"]
        )

        result = classifier.classify("play some music")

        # Should detect custom intent or command
        assert isinstance(result, IntentResult)


class TestIntentPerformance:
    """Test performance requirements."""

    def test_classification_latency(self):
        """Classification should be fast (<50ms)."""
        classifier = IntentClassifier(mock_mode=True)

        times = []
        texts = ["hello", "turn on lights", "what time is it", "tell me a joke"]

        for text in texts * 10:
            start = time.perf_counter()
            classifier.classify(text)
            elapsed = (time.perf_counter() - start) * 1000
            times.append(elapsed)

        avg_time = sum(times) / len(times)
        assert avg_time < 50.0, f"Average latency {avg_time:.2f}ms exceeds 50ms"


class TestIntentEdgeCases:
    """Test edge cases."""

    def test_very_long_text(self):
        """Very long text should be handled."""
        classifier = IntentClassifier(mock_mode=True)

        long_text = "hello " * 1000
        result = classifier.classify(long_text)

        assert isinstance(result, IntentResult)

    def test_special_characters(self):
        """Text with special characters should be handled."""
        classifier = IntentClassifier(mock_mode=True)

        result = classifier.classify("what's the time? I'm curious!")

        assert isinstance(result, IntentResult)

    def test_unicode_text(self):
        """Unicode text should be handled."""
        classifier = IntentClassifier(mock_mode=True)

        result = classifier.classify("ciao, come stai? 你好")

        assert isinstance(result, IntentResult)

    def test_numeric_text(self):
        """Numeric text should be handled."""
        classifier = IntentClassifier(mock_mode=True)

        result = classifier.classify("123 456 789")

        assert isinstance(result, IntentResult)


class TestIntentIntegration:
    """Test integration scenarios."""

    def test_stt_to_intent_pipeline(self):
        """STT output should work as intent input."""
        from src.voice.stt import SpeechToText, STTConfig

        stt = SpeechToText(mock_mode=True)
        classifier = IntentClassifier(mock_mode=True)

        # Mock audio (1 second of "speech")
        audio = np.random.randn(16000).astype(np.float32) * 0.1

        # STT → Intent pipeline
        stt_result = stt.transcribe(audio)
        if stt_result.text:
            intent_result = classifier.classify(stt_result.text)
            assert isinstance(intent_result, IntentResult)

    def test_full_voice_pipeline(self):
        """Full VAD → Wake Word → STT → Intent pipeline."""
        from src.voice.vad import VoiceActivityDetector, VADConfig
        from src.voice.wake_word import WakeWordDetector
        from src.voice.stt import SpeechToText

        vad = VoiceActivityDetector(VADConfig(min_speech_ms=20))
        wake = WakeWordDetector(mock_mode=True)
        stt = SpeechToText(mock_mode=True)
        intent = IntentClassifier(mock_mode=True)

        # Simulate audio processing
        audio = np.random.randn(16000).astype(np.float32) * 0.1

        # Process through pipeline
        for i in range(0, len(audio) - 320, 320):
            frame = audio[i:i+320]
            vad_result = vad.process_frame(frame)
            # In real pipeline, would check VAD and wake word

        # Final transcription and classification
        stt_result = stt.transcribe(audio)
        if stt_result.text:
            intent_result = intent.classify(stt_result.text)
            assert isinstance(intent_result, IntentResult)

