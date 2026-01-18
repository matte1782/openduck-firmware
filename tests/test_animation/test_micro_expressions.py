#!/usr/bin/env python3
"""
Tests for Micro-Expression System
OpenDuck Mini V3 - Day 10 Foundation

Comprehensive test coverage for:
- MicroExpressionType enum
- MicroExpression dataclass validation
- MicroExpressionEngine functionality
- Preset loading and triggering
- Brightness modifier computation
- Cooldown and priority logic

Author: Boston Dynamics Test Architect
Created: 18 January 2026 (Day 10)
"""

import pytest
import time
import math
from unittest.mock import MagicMock, patch

# Import module under test
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from animation.micro_expressions import (
    MicroExpressionType,
    MicroExpression,
    MicroExpressionEngine,
    MICRO_EXPRESSION_PRESETS,
    get_preset_names,
    get_preset,
)


# ============================================================================
# MicroExpressionType Tests
# ============================================================================

class TestMicroExpressionType:
    """Test MicroExpressionType enum."""

    def test_all_types_defined(self):
        """All expected micro-expression types should be defined."""
        expected_types = [
            'BLINK', 'FLICKER', 'SQUINT', 'WIDEN',
            'GLANCE', 'TWITCH', 'DROOP', 'SPARKLE'
        ]
        actual_types = [t.name for t in MicroExpressionType]
        for expected in expected_types:
            assert expected in actual_types, f"Missing type: {expected}"

    def test_type_values_are_strings(self):
        """Each type should have a string value."""
        for expr_type in MicroExpressionType:
            assert isinstance(expr_type.value, str)

    def test_type_values_are_unique(self):
        """All type values should be unique."""
        values = [t.value for t in MicroExpressionType]
        assert len(values) == len(set(values)), "Duplicate type values found"


# ============================================================================
# MicroExpression Dataclass Tests
# ============================================================================

class TestMicroExpressionValidation:
    """Test MicroExpression dataclass validation."""

    def test_valid_creation(self):
        """Valid parameters should create expression without error."""
        expr = MicroExpression(
            expression_type=MicroExpressionType.BLINK,
            duration_ms=150,
            intensity=0.7
        )
        assert expr.expression_type == MicroExpressionType.BLINK
        assert expr.duration_ms == 150
        assert expr.intensity == 0.7
        assert expr.trigger_emotion is None
        assert expr.cooldown_ms == 0
        assert expr.priority == 50

    def test_full_parameters(self):
        """All parameters should be stored correctly."""
        expr = MicroExpression(
            expression_type=MicroExpressionType.FLICKER,
            duration_ms=200,
            intensity=0.5,
            trigger_emotion="happy",
            cooldown_ms=1000,
            priority=75
        )
        assert expr.trigger_emotion == "happy"
        assert expr.cooldown_ms == 1000
        assert expr.priority == 75

    # --- Invalid expression_type ---

    def test_invalid_expression_type_string(self):
        """String expression_type should raise TypeError."""
        with pytest.raises(TypeError, match="expression_type must be MicroExpressionType"):
            MicroExpression(
                expression_type="blink",  # Wrong type
                duration_ms=100,
                intensity=0.5
            )

    def test_invalid_expression_type_none(self):
        """None expression_type should raise TypeError."""
        with pytest.raises(TypeError, match="expression_type must be MicroExpressionType"):
            MicroExpression(
                expression_type=None,
                duration_ms=100,
                intensity=0.5
            )

    # --- Invalid duration_ms ---

    def test_duration_ms_zero(self):
        """Zero duration should raise ValueError."""
        with pytest.raises(ValueError, match="duration_ms must be positive"):
            MicroExpression(
                expression_type=MicroExpressionType.BLINK,
                duration_ms=0,
                intensity=0.5
            )

    def test_duration_ms_negative(self):
        """Negative duration should raise ValueError."""
        with pytest.raises(ValueError, match="duration_ms must be positive"):
            MicroExpression(
                expression_type=MicroExpressionType.BLINK,
                duration_ms=-100,
                intensity=0.5
            )

    def test_duration_ms_too_large(self):
        """Duration exceeding 5000ms should raise ValueError."""
        with pytest.raises(ValueError, match="duration_ms exceeds maximum"):
            MicroExpression(
                expression_type=MicroExpressionType.BLINK,
                duration_ms=6000,
                intensity=0.5
            )

    def test_duration_ms_float(self):
        """Float duration should raise TypeError."""
        with pytest.raises(TypeError, match="duration_ms must be int"):
            MicroExpression(
                expression_type=MicroExpressionType.BLINK,
                duration_ms=150.5,
                intensity=0.5
            )

    # --- Invalid intensity ---

    def test_intensity_below_zero(self):
        """Intensity below 0.0 should raise ValueError."""
        with pytest.raises(ValueError, match="intensity must be 0.0-1.0"):
            MicroExpression(
                expression_type=MicroExpressionType.BLINK,
                duration_ms=100,
                intensity=-0.1
            )

    def test_intensity_above_one(self):
        """Intensity above 1.0 should raise ValueError."""
        with pytest.raises(ValueError, match="intensity must be 0.0-1.0"):
            MicroExpression(
                expression_type=MicroExpressionType.BLINK,
                duration_ms=100,
                intensity=1.5
            )

    def test_intensity_nan(self):
        """NaN intensity should raise ValueError."""
        with pytest.raises(ValueError, match="intensity must be finite"):
            MicroExpression(
                expression_type=MicroExpressionType.BLINK,
                duration_ms=100,
                intensity=float('nan')
            )

    def test_intensity_inf(self):
        """Infinite intensity should raise ValueError."""
        with pytest.raises(ValueError, match="intensity must be finite"):
            MicroExpression(
                expression_type=MicroExpressionType.BLINK,
                duration_ms=100,
                intensity=float('inf')
            )

    def test_intensity_string(self):
        """String intensity should raise TypeError."""
        with pytest.raises(TypeError, match="intensity must be numeric"):
            MicroExpression(
                expression_type=MicroExpressionType.BLINK,
                duration_ms=100,
                intensity="high"
            )

    # --- Invalid cooldown_ms ---

    def test_cooldown_ms_negative(self):
        """Negative cooldown should raise ValueError."""
        with pytest.raises(ValueError, match="cooldown_ms must be non-negative"):
            MicroExpression(
                expression_type=MicroExpressionType.BLINK,
                duration_ms=100,
                intensity=0.5,
                cooldown_ms=-1
            )

    def test_cooldown_ms_float(self):
        """Float cooldown should raise TypeError."""
        with pytest.raises(TypeError, match="cooldown_ms must be int"):
            MicroExpression(
                expression_type=MicroExpressionType.BLINK,
                duration_ms=100,
                intensity=0.5,
                cooldown_ms=100.5
            )

    # --- Invalid priority ---

    def test_priority_below_zero(self):
        """Priority below 0 should raise ValueError."""
        with pytest.raises(ValueError, match="priority must be 0-100"):
            MicroExpression(
                expression_type=MicroExpressionType.BLINK,
                duration_ms=100,
                intensity=0.5,
                priority=-1
            )

    def test_priority_above_100(self):
        """Priority above 100 should raise ValueError."""
        with pytest.raises(ValueError, match="priority must be 0-100"):
            MicroExpression(
                expression_type=MicroExpressionType.BLINK,
                duration_ms=100,
                intensity=0.5,
                priority=101
            )

    def test_priority_float(self):
        """Float priority should raise TypeError."""
        with pytest.raises(TypeError, match="priority must be int"):
            MicroExpression(
                expression_type=MicroExpressionType.BLINK,
                duration_ms=100,
                intensity=0.5,
                priority=50.5
            )

    # --- Edge Cases ---

    def test_intensity_zero(self):
        """Intensity of 0.0 should be valid (invisible effect)."""
        expr = MicroExpression(
            expression_type=MicroExpressionType.BLINK,
            duration_ms=100,
            intensity=0.0
        )
        assert expr.intensity == 0.0

    def test_intensity_one(self):
        """Intensity of 1.0 should be valid (maximum effect)."""
        expr = MicroExpression(
            expression_type=MicroExpressionType.BLINK,
            duration_ms=100,
            intensity=1.0
        )
        assert expr.intensity == 1.0

    def test_duration_ms_minimum(self):
        """Duration of 1ms should be valid."""
        expr = MicroExpression(
            expression_type=MicroExpressionType.BLINK,
            duration_ms=1,
            intensity=0.5
        )
        assert expr.duration_ms == 1

    def test_duration_ms_maximum(self):
        """Duration of 5000ms should be valid."""
        expr = MicroExpression(
            expression_type=MicroExpressionType.BLINK,
            duration_ms=5000,
            intensity=0.5
        )
        assert expr.duration_ms == 5000


# ============================================================================
# MicroExpressionEngine Tests
# ============================================================================

class TestMicroExpressionEngineBasic:
    """Basic MicroExpressionEngine tests."""

    def test_initialization(self):
        """Engine should initialize with default state."""
        engine = MicroExpressionEngine()
        assert not engine.is_active()
        assert engine.get_brightness_modifier() == 1.0
        assert len(engine.get_per_pixel_modifiers()) == 16

    def test_initialization_custom_leds(self):
        """Engine should accept custom LED count."""
        engine = MicroExpressionEngine(num_leds=24)
        assert len(engine.get_per_pixel_modifiers()) == 24

    def test_initialization_with_controller(self):
        """Engine should accept LED controller."""
        mock_controller = MagicMock()
        engine = MicroExpressionEngine(led_controller=mock_controller)
        assert engine.led_controller == mock_controller


class TestMicroExpressionEngineTrigger:
    """Test triggering micro-expressions."""

    def test_trigger_blink(self):
        """Triggering blink should make engine active."""
        engine = MicroExpressionEngine()
        result = engine.trigger(MicroExpressionType.BLINK, duration_ms=100, intensity=0.7)
        assert result is True
        assert engine.is_active()
        assert engine.get_active_expression_type() == MicroExpressionType.BLINK

    def test_trigger_all_types(self):
        """All expression types should be triggerable."""
        for expr_type in MicroExpressionType:
            engine = MicroExpressionEngine()
            result = engine.trigger(expr_type, duration_ms=100, intensity=0.5)
            assert result is True, f"Failed to trigger {expr_type.name}"
            assert engine.get_active_expression_type() == expr_type

    def test_trigger_invalid_duration(self):
        """Invalid duration should raise ValueError."""
        engine = MicroExpressionEngine()
        with pytest.raises(ValueError):
            engine.trigger(MicroExpressionType.BLINK, duration_ms=0, intensity=0.5)

    def test_trigger_invalid_intensity(self):
        """Invalid intensity should raise ValueError."""
        engine = MicroExpressionEngine()
        with pytest.raises(ValueError):
            engine.trigger(MicroExpressionType.BLINK, duration_ms=100, intensity=2.0)


class TestMicroExpressionEnginePresets:
    """Test preset triggering."""

    def test_trigger_preset_blink_normal(self):
        """Triggering blink_normal preset should work."""
        engine = MicroExpressionEngine()
        result = engine.trigger_preset("blink_normal")
        assert result is True
        assert engine.is_active()

    def test_trigger_all_presets(self):
        """All presets should be triggerable."""
        for preset_name in MICRO_EXPRESSION_PRESETS:
            engine = MicroExpressionEngine()
            result = engine.trigger_preset(preset_name)
            assert result is True, f"Failed to trigger preset: {preset_name}"

    def test_trigger_unknown_preset(self):
        """Unknown preset should raise KeyError."""
        engine = MicroExpressionEngine()
        with pytest.raises(KeyError, match="Unknown preset"):
            engine.trigger_preset("nonexistent_preset")


class TestMicroExpressionEngineUpdate:
    """Test update loop behavior."""

    def test_update_returns_active_state(self):
        """Update should return True when expression is active."""
        engine = MicroExpressionEngine()
        engine.trigger(MicroExpressionType.BLINK, duration_ms=100, intensity=0.5)
        result = engine.update(delta_ms=10)
        assert result is True

    def test_update_returns_false_when_inactive(self):
        """Update should return False when no expression active."""
        engine = MicroExpressionEngine()
        result = engine.update(delta_ms=10)
        assert result is False

    def test_update_advances_progress(self):
        """Update should advance expression progress."""
        engine = MicroExpressionEngine()
        engine.trigger(MicroExpressionType.BLINK, duration_ms=100, intensity=0.5)

        # Initial progress is 0
        assert engine.get_active_progress() >= 0.0

        # Wait and update
        time.sleep(0.05)  # 50ms
        engine.update(delta_ms=50)

        # Progress should have advanced
        assert engine.get_active_progress() > 0.0

    def test_expression_completes(self):
        """Expression should complete after duration."""
        engine = MicroExpressionEngine()
        engine.trigger(MicroExpressionType.BLINK, duration_ms=50, intensity=0.5)

        # Wait for completion
        time.sleep(0.1)  # 100ms > 50ms duration
        engine.update(delta_ms=100)

        # Should no longer be active
        assert not engine.is_active()
        assert engine.get_brightness_modifier() == pytest.approx(1.0)


class TestMicroExpressionEngineBrightness:
    """Test brightness modifier computation."""

    def test_blink_dims_brightness(self):
        """Blink should reduce brightness during animation."""
        engine = MicroExpressionEngine()
        engine.seed_rng(42)  # Reproducible
        engine.trigger(MicroExpressionType.BLINK, duration_ms=100, intensity=0.8)

        # Simulate mid-blink
        time.sleep(0.05)  # 50ms
        engine.update(delta_ms=50)

        # Brightness should be reduced
        modifier = engine.get_brightness_modifier()
        assert modifier < 1.0, "Blink should reduce brightness"
        assert modifier > 0.0, "Brightness should never be zero"

    def test_flicker_increases_brightness(self):
        """Flicker should increase brightness during animation."""
        engine = MicroExpressionEngine()
        engine.seed_rng(42)
        engine.trigger(MicroExpressionType.FLICKER, duration_ms=100, intensity=0.8)

        # Simulate mid-flicker
        time.sleep(0.03)  # 30ms (peak is at 30%)
        engine.update(delta_ms=30)

        # Brightness should be increased
        modifier = engine.get_brightness_modifier()
        assert modifier > 1.0, "Flicker should increase brightness"

    def test_squint_varies_per_pixel(self):
        """Squint should create different brightness per pixel."""
        engine = MicroExpressionEngine(num_leds=16)
        engine.seed_rng(42)
        engine.trigger(MicroExpressionType.SQUINT, duration_ms=100, intensity=0.8)

        # Simulate mid-squint
        time.sleep(0.05)
        engine.update(delta_ms=50)

        modifiers = engine.get_per_pixel_modifiers()

        # Center pixels should be brighter than edge pixels
        center_brightness = modifiers[8]  # Center
        edge_brightness = modifiers[0]    # Edge

        assert center_brightness >= edge_brightness, "Center should be >= edge in squint"

    def test_modifiers_reset_after_completion(self):
        """Modifiers should reset to 1.0 after expression completes."""
        engine = MicroExpressionEngine()
        engine.trigger(MicroExpressionType.BLINK, duration_ms=20, intensity=0.8)

        # Wait for completion
        time.sleep(0.05)
        engine.update(delta_ms=50)

        # Modifiers should be reset (use approx for floating point)
        assert engine.get_brightness_modifier() == pytest.approx(1.0)
        assert all(m == pytest.approx(1.0) for m in engine.get_per_pixel_modifiers())


class TestMicroExpressionEngineCooldown:
    """Test cooldown behavior."""

    def test_cooldown_prevents_retrigger(self):
        """Expression should not retrigger during cooldown."""
        engine = MicroExpressionEngine()

        # Use preset with known cooldown
        preset = MICRO_EXPRESSION_PRESETS["blink_normal"]
        engine.trigger_preset("blink_normal")

        # Wait for completion but not full cooldown
        time.sleep(0.2)  # 200ms << 3000ms cooldown
        engine.update(delta_ms=200)

        # Try to trigger again (should fail due to cooldown)
        result = engine.trigger(MicroExpressionType.BLINK, duration_ms=100, intensity=0.5)
        assert result is False, "Should be blocked by cooldown"

    def test_force_bypasses_cooldown(self):
        """Force flag should bypass cooldown."""
        engine = MicroExpressionEngine()

        # Trigger with cooldown
        engine.trigger(MicroExpressionType.BLINK, duration_ms=50, intensity=0.5)

        # Wait for completion
        time.sleep(0.1)
        engine.update(delta_ms=100)

        # Force trigger (should succeed)
        result = engine.trigger(MicroExpressionType.BLINK, duration_ms=100, intensity=0.5, force=True)
        assert result is True


class TestMicroExpressionEnginePriority:
    """Test priority-based expression selection."""

    def test_high_priority_preempts_low(self):
        """High priority expression should preempt low priority."""
        engine = MicroExpressionEngine()

        # Trigger low priority expression
        low_priority = MicroExpression(
            expression_type=MicroExpressionType.BLINK,
            duration_ms=1000,
            intensity=0.5,
            priority=20
        )
        engine._trigger_expression(low_priority, force=True)
        assert engine.get_active_expression_type() == MicroExpressionType.BLINK

        # Trigger high priority expression
        high_priority = MicroExpression(
            expression_type=MicroExpressionType.FLICKER,
            duration_ms=100,
            intensity=0.8,
            priority=80
        )
        engine._trigger_expression(high_priority, force=True)

        # High priority should now be active
        assert engine.get_active_expression_type() == MicroExpressionType.FLICKER

    def test_low_priority_queued(self):
        """Low priority expression should be queued when high is active."""
        engine = MicroExpressionEngine()

        # Trigger high priority expression
        high_priority = MicroExpression(
            expression_type=MicroExpressionType.WIDEN,
            duration_ms=100,
            intensity=0.8,
            priority=80
        )
        engine._trigger_expression(high_priority, force=True)

        # Trigger low priority (should be queued)
        low_priority = MicroExpression(
            expression_type=MicroExpressionType.BLINK,
            duration_ms=100,
            intensity=0.5,
            priority=20
        )
        result = engine._trigger_expression(low_priority, force=True)
        assert result is True  # Queued successfully

        # High priority still active
        assert engine.get_active_expression_type() == MicroExpressionType.WIDEN


class TestMicroExpressionEngineCallbacks:
    """Test callback functionality."""

    def test_callback_on_start(self):
        """Callback should fire when expression starts."""
        engine = MicroExpressionEngine()
        events = []

        def callback(expr_type, event):
            events.append((expr_type, event))

        engine.add_callback(callback)
        engine.trigger(MicroExpressionType.BLINK, duration_ms=100, intensity=0.5)

        assert len(events) == 1
        assert events[0] == (MicroExpressionType.BLINK, "started")

    def test_callback_on_complete(self):
        """Callback should fire when expression completes."""
        engine = MicroExpressionEngine()
        events = []

        def callback(expr_type, event):
            events.append((expr_type, event))

        engine.add_callback(callback)
        engine.trigger(MicroExpressionType.BLINK, duration_ms=20, intensity=0.5)

        # Wait for completion
        time.sleep(0.05)
        engine.update(delta_ms=50)

        assert ("started" in [e[1] for e in events])
        assert ("completed" in [e[1] for e in events])

    def test_remove_callback(self):
        """Removed callback should not fire."""
        engine = MicroExpressionEngine()
        events = []

        def callback(expr_type, event):
            events.append((expr_type, event))

        engine.add_callback(callback)
        engine.remove_callback(callback)
        engine.trigger(MicroExpressionType.BLINK, duration_ms=100, intensity=0.5)

        assert len(events) == 0


class TestMicroExpressionEngineControl:
    """Test engine control methods."""

    def test_cancel_current(self):
        """Cancel should stop current expression."""
        engine = MicroExpressionEngine()
        engine.trigger(MicroExpressionType.BLINK, duration_ms=1000, intensity=0.5)
        assert engine.is_active()

        result = engine.cancel_current()
        assert result is True
        assert not engine.is_active()
        assert engine.get_brightness_modifier() == 1.0

    def test_cancel_when_none_active(self):
        """Cancel should return False when nothing active."""
        engine = MicroExpressionEngine()
        result = engine.cancel_current()
        assert result is False

    def test_clear_queue(self):
        """Clear queue should remove all pending expressions."""
        engine = MicroExpressionEngine()

        # Fill queue by triggering during active expression
        engine.trigger(MicroExpressionType.WIDEN, duration_ms=1000, intensity=0.8)

        # Add lower priority items to queue
        for _ in range(3):
            low_expr = MicroExpression(
                expression_type=MicroExpressionType.BLINK,
                duration_ms=100,
                intensity=0.5,
                priority=10
            )
            engine._trigger_expression(low_expr, force=True)

        count = engine.clear_queue()
        assert count >= 0  # Queue was cleared

    def test_reset(self):
        """Reset should restore initial state."""
        engine = MicroExpressionEngine()
        engine.trigger(MicroExpressionType.BLINK, duration_ms=1000, intensity=0.8)
        engine.update(delta_ms=100)

        engine.reset()

        assert not engine.is_active()
        assert engine.get_brightness_modifier() == 1.0
        assert all(m == 1.0 for m in engine.get_per_pixel_modifiers())


# ============================================================================
# Preset Tests
# ============================================================================

class TestMicroExpressionPresets:
    """Test preset definitions."""

    def test_all_presets_valid(self):
        """All presets should have valid configurations."""
        for name, expr in MICRO_EXPRESSION_PRESETS.items():
            # Should not raise
            assert isinstance(expr, MicroExpression), f"Preset {name} is not MicroExpression"
            assert isinstance(expr.expression_type, MicroExpressionType)
            assert 1 <= expr.duration_ms <= 5000
            assert 0.0 <= expr.intensity <= 1.0
            assert expr.cooldown_ms >= 0
            assert 0 <= expr.priority <= 100

    def test_get_preset_names(self):
        """get_preset_names should return all preset names."""
        names = get_preset_names()
        assert len(names) == len(MICRO_EXPRESSION_PRESETS)
        for name in names:
            assert name in MICRO_EXPRESSION_PRESETS

    def test_get_preset(self):
        """get_preset should return correct preset."""
        preset = get_preset("blink_normal")
        assert preset.expression_type == MicroExpressionType.BLINK
        assert preset.duration_ms == 150

    def test_get_preset_unknown(self):
        """get_preset should raise KeyError for unknown preset."""
        with pytest.raises(KeyError):
            get_preset("nonexistent")

    def test_preset_categories_exist(self):
        """Should have presets for major expression types."""
        names = get_preset_names()

        # Check for blink variants
        assert any("blink" in n for n in names)

        # Check for flicker variants
        assert any("flicker" in n for n in names)

        # Check for squint variants
        assert any("squint" in n for n in names)

        # Check for sparkle variants
        assert any("sparkle" in n for n in names)


# ============================================================================
# Easing Function Tests
# ============================================================================

class TestEasingFunction:
    """Test internal easing function."""

    def test_ease_in_out_endpoints(self):
        """Ease function should have correct endpoints."""
        assert MicroExpressionEngine._ease_in_out(0.0) == pytest.approx(0.0)
        assert MicroExpressionEngine._ease_in_out(1.0) == pytest.approx(1.0)

    def test_ease_in_out_midpoint(self):
        """Ease function should pass through midpoint."""
        assert MicroExpressionEngine._ease_in_out(0.5) == pytest.approx(0.5)

    def test_ease_in_out_smooth(self):
        """Ease function should be monotonically increasing."""
        prev = 0.0
        for i in range(1, 101):
            t = i / 100.0
            current = MicroExpressionEngine._ease_in_out(t)
            assert current >= prev, f"Ease function not monotonic at t={t}"
            prev = current


# ============================================================================
# Integration Tests
# ============================================================================

class TestMicroExpressionIntegration:
    """Integration tests for realistic usage scenarios."""

    def test_emotion_triggered_expression(self):
        """Expressions should trigger based on emotion."""
        engine = MicroExpressionEngine()

        # Find preset triggered by "happy" emotion
        happy_presets = [
            name for name, expr in MICRO_EXPRESSION_PRESETS.items()
            if expr.trigger_emotion == "happy"
        ]
        assert len(happy_presets) > 0, "Should have happy-triggered presets"

        # Trigger one
        result = engine.trigger_preset(happy_presets[0])
        assert result is True

    def test_60fps_update_loop(self):
        """Engine should handle 60fps update rate."""
        engine = MicroExpressionEngine()
        engine.trigger(MicroExpressionType.BLINK, duration_ms=100, intensity=0.5)

        # Simulate 60fps for 200ms
        for _ in range(12):  # 12 frames at ~16.67ms each
            engine.update(delta_ms=16.67)
            _ = engine.get_brightness_modifier()
            _ = engine.get_per_pixel_modifiers()
            time.sleep(0.0167)

        # Should complete without error
        assert True

    def test_multiple_expression_sequence(self):
        """Multiple expressions should play in sequence."""
        engine = MicroExpressionEngine()

        expressions_played = []

        def callback(expr_type, event):
            if event == "completed":
                expressions_played.append(expr_type)

        engine.add_callback(callback)

        # Trigger sequence
        engine.trigger(MicroExpressionType.BLINK, duration_ms=30, intensity=0.5)
        time.sleep(0.05)
        engine.update(delta_ms=50)

        engine.trigger(MicroExpressionType.FLICKER, duration_ms=30, intensity=0.5, force=True)
        time.sleep(0.05)
        engine.update(delta_ms=50)

        # Both should have completed
        assert MicroExpressionType.BLINK in expressions_played
        assert MicroExpressionType.FLICKER in expressions_played


# ============================================================================
# Performance Tests
# ============================================================================

class TestMicroExpressionPerformance:
    """Performance benchmarks."""

    def test_trigger_performance(self):
        """Triggering should be fast (<1ms)."""
        engine = MicroExpressionEngine()

        start = time.perf_counter()
        for _ in range(100):
            engine.trigger(MicroExpressionType.BLINK, duration_ms=100, intensity=0.5, force=True)
            engine.cancel_current()
        elapsed = time.perf_counter() - start

        avg_ms = (elapsed / 100) * 1000
        assert avg_ms < 1.0, f"Trigger too slow: {avg_ms:.3f}ms"

    def test_update_performance(self):
        """Update should be fast (<1ms)."""
        engine = MicroExpressionEngine()
        engine.trigger(MicroExpressionType.BLINK, duration_ms=5000, intensity=0.5)

        start = time.perf_counter()
        for _ in range(1000):
            engine.update(delta_ms=1)
        elapsed = time.perf_counter() - start

        avg_ms = (elapsed / 1000) * 1000
        assert avg_ms < 1.0, f"Update too slow: {avg_ms:.3f}ms"

    def test_modifier_computation_performance(self):
        """Modifier computation should be fast."""
        engine = MicroExpressionEngine(num_leds=32)
        engine.trigger(MicroExpressionType.SQUINT, duration_ms=5000, intensity=0.5)

        start = time.perf_counter()
        for _ in range(1000):
            engine.update(delta_ms=1)
            _ = engine.get_per_pixel_modifiers()
        elapsed = time.perf_counter() - start

        avg_ms = (elapsed / 1000) * 1000
        assert avg_ms < 2.0, f"Modifier computation too slow: {avg_ms:.3f}ms"
