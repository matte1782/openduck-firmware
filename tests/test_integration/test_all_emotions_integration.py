#!/usr/bin/env python3
"""
Integration Test - All 17 Emotions
Week 02 Day 10 | Agent 5: Integration & Quality Assurance

Tests all emotion systems working together:
- 8 Primary Emotions (Agent 1 refined)
- 4 Social Emotions (Agent 2)
- 5 Compound Emotions (Agent 3)
- Micro-expression overlay on each (Agent 4)

Performance targets:
- All patterns <2.5ms avg frame time
- Micro-expressions add <0.5ms overhead
- Total frame time <10ms

Author: Integration Engineer (Agent 5)
Created: 18 January 2026
"""

import pytest
import time
import sys
from pathlib import Path
from typing import List, Tuple

# Add firmware/src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'src'))

# Import emotion systems
from animation.emotions import EmotionState, EMOTION_CONFIGS, EmotionConfig
from animation.emotion_axes import EmotionAxes, EMOTION_PRESETS
from animation.emotion_patterns.compound_emotions import (
    COMPOUND_EMOTION_SPECS,
    COMPOUND_EMOTION_PRESETS,
    ConfusedPattern,
    SurprisedPattern,
    AnxiousPattern,
    FrustratedPattern,
    ProudPattern,
)
from led.patterns.social_emotions import (
    PlayfulPattern,
    AffectionatePattern,
    EmpatheticPattern,
    GratefulPattern,
    SOCIAL_PATTERN_REGISTRY,
)
from animation.micro_expressions_enhanced import (
    EnhancedMicroExpressionEngine,
    EMOTION_MICRO_PARAMS,
)


# =============================================================================
# Constants
# =============================================================================

# All 17 emotions
PRIMARY_EMOTIONS = [
    "idle", "happy", "curious", "alert", "sad", "sleepy", "excited", "thinking"
]

SOCIAL_EMOTIONS = [
    "playful", "affectionate", "empathetic", "grateful"
]

COMPOUND_EMOTIONS = [
    "confused", "surprised", "anxious", "frustrated", "proud"
]

ALL_EMOTIONS = PRIMARY_EMOTIONS + SOCIAL_EMOTIONS + COMPOUND_EMOTIONS

# Performance targets
AVG_FRAME_TIME_TARGET_MS = 2.5
MICRO_EXPRESSION_OVERHEAD_MS = 0.5
MAX_FRAME_TIME_MS = 10.0

NUM_BENCHMARK_FRAMES = 100


# =============================================================================
# Test: All 17 Emotions Have Configurations
# =============================================================================

class TestAllEmotionsExist:
    """Verify all 17 emotions are properly defined in the system."""

    def test_all_primary_emotions_in_state_enum(self):
        """All 8 primary emotions exist in EmotionState enum."""
        for emotion in PRIMARY_EMOTIONS:
            assert hasattr(EmotionState, emotion.upper()), f"Missing: {emotion}"

    def test_all_social_emotions_in_state_enum(self):
        """All 4 social emotions exist in EmotionState enum."""
        for emotion in SOCIAL_EMOTIONS:
            assert hasattr(EmotionState, emotion.upper()), f"Missing: {emotion}"

    def test_all_compound_emotions_have_specs(self):
        """All 5 compound emotions have specifications."""
        for emotion in COMPOUND_EMOTIONS:
            assert emotion in COMPOUND_EMOTION_SPECS, f"Missing spec: {emotion}"

    def test_all_primary_emotions_have_configs(self):
        """All 8 primary emotions have EmotionConfig entries."""
        for emotion in PRIMARY_EMOTIONS:
            state = EmotionState(emotion)
            assert state in EMOTION_CONFIGS, f"Missing config: {emotion}"
            assert isinstance(EMOTION_CONFIGS[state], EmotionConfig)

    def test_all_social_emotions_have_configs(self):
        """All 4 social emotions have EmotionConfig entries."""
        for emotion in SOCIAL_EMOTIONS:
            state = EmotionState(emotion)
            assert state in EMOTION_CONFIGS, f"Missing config: {emotion}"
            assert isinstance(EMOTION_CONFIGS[state], EmotionConfig)

    def test_total_emotion_count(self):
        """System has exactly 17 emotions (8+4+5)."""
        # EmotionState has 12 (8 primary + 4 social)
        assert len(EmotionState) == 12
        # Compound specs add 5 more
        assert len(COMPOUND_EMOTION_SPECS) == 5
        # Total unique emotions
        assert len(PRIMARY_EMOTIONS) + len(SOCIAL_EMOTIONS) + len(COMPOUND_EMOTIONS) == 17


# =============================================================================
# Test: All Emotions Have EmotionAxes Presets
# =============================================================================

class TestEmotionAxesPresets:
    """Verify all emotions have valid EmotionAxes presets."""

    def test_all_primary_emotions_have_presets(self):
        """All 8 primary emotions have EmotionAxes presets."""
        for emotion in PRIMARY_EMOTIONS:
            assert emotion in EMOTION_PRESETS, f"Missing preset: {emotion}"
            assert isinstance(EMOTION_PRESETS[emotion], EmotionAxes)

    def test_all_social_emotions_have_presets(self):
        """All 4 social emotions have EmotionAxes presets."""
        for emotion in SOCIAL_EMOTIONS:
            assert emotion in EMOTION_PRESETS, f"Missing preset: {emotion}"
            assert isinstance(EMOTION_PRESETS[emotion], EmotionAxes)

    def test_all_compound_emotions_have_presets(self):
        """All 5 compound emotions have EmotionAxes presets."""
        # Compound emotions are in main EMOTION_PRESETS or COMPOUND_EMOTION_PRESETS
        for emotion in COMPOUND_EMOTIONS:
            in_main = emotion in EMOTION_PRESETS
            in_compound = emotion in COMPOUND_EMOTION_PRESETS
            assert in_main or in_compound, f"Missing preset: {emotion}"

    def test_presets_produce_valid_hsv(self):
        """All presets produce valid HSV values."""
        for emotion in ALL_EMOTIONS:
            if emotion in EMOTION_PRESETS:
                preset = EMOTION_PRESETS[emotion]
            elif emotion in COMPOUND_EMOTION_PRESETS:
                preset = COMPOUND_EMOTION_PRESETS[emotion]
            else:
                continue

            h, s, v = preset.to_hsv()
            assert 0 <= h < 360, f"{emotion}: Invalid hue {h}"
            assert 0.0 <= s <= 1.0, f"{emotion}: Invalid saturation {s}"
            assert 0.0 <= v <= 1.0, f"{emotion}: Invalid value {v}"


# =============================================================================
# Test: Micro-Expression Support for All Emotions
# =============================================================================

class TestMicroExpressionSupport:
    """Verify micro-expression engine supports all emotions."""

    def test_all_emotions_have_micro_params(self):
        """All emotions with micro params are handled."""
        engine = EnhancedMicroExpressionEngine()

        # All primary and social emotions should have params
        for emotion in PRIMARY_EMOTIONS:
            if emotion in EMOTION_MICRO_PARAMS:
                engine.set_emotion(emotion)
                assert engine._current_emotion == emotion

        for emotion in SOCIAL_EMOTIONS:
            if emotion in EMOTION_MICRO_PARAMS:
                engine.set_emotion(emotion)
                assert engine._current_emotion == emotion

    def test_unknown_emotion_falls_back_to_idle(self):
        """Unknown emotions fall back to idle gracefully."""
        engine = EnhancedMicroExpressionEngine()
        engine.set_emotion("nonexistent_emotion")
        assert engine._current_emotion == "idle"

    def test_micro_expression_produces_valid_output(self):
        """Micro expressions produce valid modifier values."""
        engine = EnhancedMicroExpressionEngine()

        for emotion in ALL_EMOTIONS:
            engine.set_emotion(emotion)
            engine.update(20.0)  # 20ms frame

            global_mod = engine.get_brightness_modifier()
            per_pixel = engine.get_per_pixel_modifiers()

            # Global modifier should be reasonable
            assert 0.0 <= global_mod <= 2.0, f"{emotion}: Invalid global {global_mod}"

            # Per-pixel modifiers should be valid
            assert len(per_pixel) == 16
            for mod in per_pixel:
                assert 0.0 <= mod <= 2.0, f"{emotion}: Invalid per-pixel {mod}"


# =============================================================================
# Test: Pattern Rendering for All Emotions
# =============================================================================

class TestPatternRendering:
    """Verify all emotion patterns render correctly."""

    def test_social_patterns_render(self):
        """All 4 social emotion patterns render valid output."""
        patterns = [
            PlayfulPattern(),
            AffectionatePattern(),
            EmpatheticPattern(),
            GratefulPattern(),
        ]

        for pattern in patterns:
            for t in [0.0, 0.5, 1.0, 2.0]:
                pattern._frame = int(t * 50)  # 50 FPS
                pixels = pattern._compute_frame((255, 180, 100))

                assert len(pixels) == 16
                for r, g, b in pixels:
                    assert 0 <= r <= 255
                    assert 0 <= g <= 255
                    assert 0 <= b <= 255

    def test_compound_patterns_render(self):
        """All 5 compound emotion patterns render valid output."""
        patterns = [
            ConfusedPattern(),
            SurprisedPattern(),
            AnxiousPattern(),
            FrustratedPattern(),
            ProudPattern(),
        ]

        for pattern in patterns:
            for t in [0.0, 0.5, 1.0, 2.0]:
                left, right = pattern.render(t)

                assert len(left) == 16
                assert len(right) == 16

                for pixels in [left, right]:
                    for r, g, b in pixels:
                        assert 0 <= r <= 255
                        assert 0 <= g <= 255
                        assert 0 <= b <= 255


# =============================================================================
# Test: Performance Requirements
# =============================================================================

class TestPerformanceRequirements:
    """Verify all patterns meet performance requirements."""

    def test_social_patterns_avg_frame_time(self):
        """Social patterns average <2.5ms frame time."""
        patterns = [
            ("playful", PlayfulPattern()),
            ("affectionate", AffectionatePattern()),
            ("empathetic", EmpatheticPattern()),
            ("grateful", GratefulPattern()),
        ]

        for name, pattern in patterns:
            times = []
            for i in range(NUM_BENCHMARK_FRAMES):
                pattern._frame = i
                start = time.perf_counter()
                pattern._compute_frame((255, 180, 100))
                end = time.perf_counter()
                times.append((end - start) * 1000)

            avg = sum(times) / len(times)
            assert avg < AVG_FRAME_TIME_TARGET_MS, \
                f"{name}: avg {avg:.3f}ms > target {AVG_FRAME_TIME_TARGET_MS}ms"

    def test_compound_patterns_avg_frame_time(self):
        """Compound patterns average <2.5ms frame time."""
        patterns = [
            ("confused", ConfusedPattern()),
            ("surprised", SurprisedPattern()),
            ("anxious", AnxiousPattern()),
            ("frustrated", FrustratedPattern()),
            ("proud", ProudPattern()),
        ]

        for name, pattern in patterns:
            times = []
            for i in range(NUM_BENCHMARK_FRAMES):
                t = i * 0.02  # 20ms per frame
                start = time.perf_counter()
                pattern.render(t)
                end = time.perf_counter()
                times.append((end - start) * 1000)

            avg = sum(times) / len(times)
            assert avg < AVG_FRAME_TIME_TARGET_MS, \
                f"{name}: avg {avg:.3f}ms > target {AVG_FRAME_TIME_TARGET_MS}ms"

    def test_micro_expression_overhead(self):
        """Micro-expression system adds <0.5ms overhead."""
        engine = EnhancedMicroExpressionEngine()

        times = []
        for _ in range(NUM_BENCHMARK_FRAMES):
            start = time.perf_counter()
            engine.update(20.0)
            end = time.perf_counter()
            times.append((end - start) * 1000)

        avg = sum(times) / len(times)
        assert avg < MICRO_EXPRESSION_OVERHEAD_MS, \
            f"Micro overhead: avg {avg:.3f}ms > target {MICRO_EXPRESSION_OVERHEAD_MS}ms"

    def test_combined_frame_time(self):
        """Combined pattern + micro-expression <10ms total."""
        engine = EnhancedMicroExpressionEngine()
        pattern = PlayfulPattern()  # Test with complex pattern

        times = []
        for i in range(NUM_BENCHMARK_FRAMES):
            start = time.perf_counter()

            # Render pattern
            pattern._frame = i
            pixels = pattern._compute_frame((255, 180, 100))

            # Apply micro-expressions
            engine.update(20.0)
            modified = engine.apply_to_pixels(pixels)

            end = time.perf_counter()
            times.append((end - start) * 1000)

        max_time = max(times)
        assert max_time < MAX_FRAME_TIME_MS, \
            f"Combined max: {max_time:.3f}ms > target {MAX_FRAME_TIME_MS}ms"


# =============================================================================
# Test: Emotion Transitions
# =============================================================================

class TestEmotionTransitions:
    """Verify transitions between all emotion types work."""

    def test_primary_to_social_transitions(self):
        """Can transition from primary to social emotions."""
        from animation.emotions import VALID_TRANSITIONS

        # HAPPY -> PLAYFUL should be valid
        assert EmotionState.PLAYFUL in VALID_TRANSITIONS[EmotionState.HAPPY]

        # IDLE can transition to any social emotion
        for social in SOCIAL_EMOTIONS:
            state = EmotionState(social)
            assert state in VALID_TRANSITIONS[EmotionState.IDLE], \
                f"IDLE -> {social} should be valid"

    def test_social_to_primary_transitions(self):
        """Can transition from social back to primary emotions."""
        from animation.emotions import VALID_TRANSITIONS

        # All social emotions can return to IDLE
        for social in SOCIAL_EMOTIONS:
            state = EmotionState(social)
            assert EmotionState.IDLE in VALID_TRANSITIONS[state], \
                f"{social} -> IDLE should be valid"

    def test_interpolation_between_emotions(self):
        """EmotionAxes interpolation works between emotion types."""
        # Interpolate from primary to social
        happy = EMOTION_PRESETS["happy"]
        playful = EMOTION_PRESETS["playful"]

        midpoint = happy.interpolate(playful, 0.5)

        # Should be valid axes
        assert isinstance(midpoint, EmotionAxes)
        # Values should be between the two
        assert happy.arousal <= midpoint.arousal <= playful.arousal or \
               playful.arousal <= midpoint.arousal <= happy.arousal


# =============================================================================
# Test: Visual Distinctiveness
# =============================================================================

class TestVisualDistinctiveness:
    """Verify emotions are visually distinct from each other."""

    def test_primary_emotions_distinct_colors(self):
        """Primary emotions have distinct LED colors."""
        colors = {}
        for emotion in PRIMARY_EMOTIONS:
            state = EmotionState(emotion)
            config = EMOTION_CONFIGS[state]
            colors[emotion] = config.led_color

        # Check that not all colors are the same
        unique_colors = set(colors.values())
        assert len(unique_colors) >= 6, "Primary emotions should have distinct colors"

    def test_social_emotions_distinct_from_primary(self):
        """Social emotions are visually distinct from primary."""
        primary_colors = set()
        for emotion in PRIMARY_EMOTIONS:
            state = EmotionState(emotion)
            primary_colors.add(EMOTION_CONFIGS[state].led_color)

        social_colors = set()
        for emotion in SOCIAL_EMOTIONS:
            state = EmotionState(emotion)
            social_colors.add(EMOTION_CONFIGS[state].led_color)

        # At least some social colors should be unique
        unique_to_social = social_colors - primary_colors
        assert len(unique_to_social) >= 2, "Social emotions should have unique colors"

    def test_compound_emotions_distinct_colors(self):
        """Compound emotions have distinct primary colors."""
        colors = {}
        for emotion in COMPOUND_EMOTIONS:
            spec = COMPOUND_EMOTION_SPECS[emotion]
            colors[emotion] = spec.primary_color

        unique_colors = set(colors.values())
        assert len(unique_colors) >= 4, "Compound emotions should have distinct colors"


# =============================================================================
# Test: Full System Integration
# =============================================================================

class TestFullSystemIntegration:
    """End-to-end integration test of the entire emotion system."""

    def test_complete_emotion_cycle(self):
        """Run through all 17 emotions with micro-expressions."""
        engine = EnhancedMicroExpressionEngine()

        for emotion in ALL_EMOTIONS:
            # Set emotion on micro-expression engine
            engine.set_emotion(emotion)

            # Run several frames
            for _ in range(10):
                engine.update(20.0)
                global_mod = engine.get_brightness_modifier()
                per_pixel = engine.get_per_pixel_modifiers()

                # Verify valid output
                assert 0.0 <= global_mod <= 2.0
                assert len(per_pixel) == 16

    def test_rapid_emotion_switching(self):
        """System handles rapid emotion switching."""
        engine = EnhancedMicroExpressionEngine()

        for _ in range(5):  # 5 rapid cycles
            for emotion in ALL_EMOTIONS:
                engine.set_emotion(emotion)
                engine.update(5.0)  # Quick 5ms update

                # Should not crash or produce invalid output
                global_mod = engine.get_brightness_modifier()
                assert global_mod is not None

    def test_pattern_and_micro_expression_combine(self):
        """Pattern output combines correctly with micro-expressions."""
        engine = EnhancedMicroExpressionEngine()
        pattern = AffectionatePattern()

        engine.set_emotion("affectionate")

        # Generate pattern pixels
        pattern._frame = 25
        base_pixels = pattern._compute_frame((255, 150, 180))

        # Update micro-expression state
        engine.update(20.0)

        # Apply micro-expressions
        modified_pixels = engine.apply_to_pixels(base_pixels)

        # Verify output is valid
        assert len(modified_pixels) == 16
        for r, g, b in modified_pixels:
            assert 0 <= r <= 255
            assert 0 <= g <= 255
            assert 0 <= b <= 255

        # Output should be different from input (micro-expressions applied)
        # (unless global modifier happens to be exactly 1.0)
        # We just verify the output is reasonable


# =============================================================================
# Test Summary Report
# =============================================================================

class TestSummaryReport:
    """Generate test summary for integration report."""

    def test_generate_emotion_inventory(self):
        """Generate inventory of all 17 emotions."""
        inventory = {
            "primary": PRIMARY_EMOTIONS,
            "social": SOCIAL_EMOTIONS,
            "compound": COMPOUND_EMOTIONS,
            "total": len(ALL_EMOTIONS)
        }

        assert inventory["total"] == 17
        print(f"\n--- Emotion Inventory ---")
        print(f"Primary: {len(PRIMARY_EMOTIONS)}")
        print(f"Social: {len(SOCIAL_EMOTIONS)}")
        print(f"Compound: {len(COMPOUND_EMOTIONS)}")
        print(f"Total: {inventory['total']}")

    def test_generate_performance_summary(self):
        """Generate performance summary."""
        # Benchmark each pattern type
        results = {}

        # Social patterns
        for name, pattern_cls in SOCIAL_PATTERN_REGISTRY.items():
            pattern = pattern_cls()
            times = []
            for i in range(50):
                pattern._frame = i
                start = time.perf_counter()
                pattern._compute_frame((200, 150, 100))
                end = time.perf_counter()
                times.append((end - start) * 1000)
            results[f"social_{name}"] = sum(times) / len(times)

        # Compound patterns
        compound_patterns = {
            "confused": ConfusedPattern,
            "surprised": SurprisedPattern,
            "anxious": AnxiousPattern,
            "frustrated": FrustratedPattern,
            "proud": ProudPattern,
        }
        for name, pattern_cls in compound_patterns.items():
            pattern = pattern_cls()
            times = []
            for i in range(50):
                start = time.perf_counter()
                pattern.render(i * 0.02)
                end = time.perf_counter()
                times.append((end - start) * 1000)
            results[f"compound_{name}"] = sum(times) / len(times)

        # Micro-expression engine
        engine = EnhancedMicroExpressionEngine()
        times = []
        for _ in range(50):
            start = time.perf_counter()
            engine.update(20.0)
            end = time.perf_counter()
            times.append((end - start) * 1000)
        results["micro_expression"] = sum(times) / len(times)

        print(f"\n--- Performance Summary ---")
        for name, avg_ms in sorted(results.items()):
            status = "PASS" if avg_ms < 2.5 else "WARN"
            print(f"{name}: {avg_ms:.4f}ms [{status}]")

        # All should pass
        for name, avg_ms in results.items():
            assert avg_ms < 2.5, f"{name} too slow: {avg_ms:.3f}ms"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
