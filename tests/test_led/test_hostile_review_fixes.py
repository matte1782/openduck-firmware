#!/usr/bin/env python3
"""
Tests for HIGH Priority Safety Fixes from Hostile Review

This test suite validates fixes for:
- HIGH-5: Modulo by zero in SpinPattern._compute_frame()
- HIGH-6: No validation of RGB color values
- HIGH-7: Power source change doesn't invalidate brightness

Run with: pytest tests/test_led/test_hostile_review_fixes.py -v

Author: Boston Dynamics Safety Systems Engineer
Created: 18 January 2026
"""

import pytest
import logging
import sys
from pathlib import Path

# Add firmware/src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'src'))

from led.patterns import PatternBase, PatternConfig, BreathingPattern, SpinPattern
from safety.led_safety import LEDSafetyManager, LEDRingProfile, PowerSource


# =============================================================================
# HIGH-5: Modulo by Zero Protection
# =============================================================================

class TestHigh5ModuloByZero:
    """Test that num_pixels=0 is rejected in PatternBase.__init__()."""

    def test_zero_pixels_rejected(self):
        """Pattern with 0 pixels raises ValueError."""
        with pytest.raises(ValueError, match="num_pixels must be positive, got 0"):
            BreathingPattern(num_pixels=0)

    def test_negative_pixels_rejected(self):
        """Pattern with negative pixels raises ValueError."""
        with pytest.raises(ValueError, match="num_pixels must be positive, got -5"):
            SpinPattern(num_pixels=-5)

    def test_spin_pattern_zero_pixels(self):
        """SpinPattern specifically rejects 0 pixels (prevents modulo by zero)."""
        with pytest.raises(ValueError, match="num_pixels must be positive"):
            SpinPattern(num_pixels=0)

    def test_one_pixel_allowed(self):
        """Pattern with 1 pixel is allowed (edge case)."""
        pattern = SpinPattern(num_pixels=1)
        assert pattern.num_pixels == 1

        # Should render without error
        pixels = pattern.render((255, 0, 0))
        assert len(pixels) == 1
        assert all(0 <= c <= 255 for c in pixels[0])

    def test_large_pixel_count(self):
        """Pattern with large pixel count works correctly."""
        pattern = SpinPattern(num_pixels=256)
        assert pattern.num_pixels == 256

        pixels = pattern.render((100, 100, 100))
        assert len(pixels) == 256


# =============================================================================
# HIGH-6: RGB Color Validation
# =============================================================================

class TestHigh6RGBValidation:
    """Test that RGB color values are validated in _scale_color()."""

    def test_valid_rgb_accepted(self):
        """Valid RGB values are accepted."""
        result = PatternBase._scale_color((100, 150, 200), 1.0)
        assert result == (100, 150, 200)

    def test_rgb_negative_red_rejected(self):
        """Negative red channel rejected."""
        with pytest.raises(ValueError, match="RGB values must be 0-255"):
            PatternBase._scale_color((-1, 100, 100), 1.0)

    def test_rgb_negative_green_rejected(self):
        """Negative green channel rejected."""
        with pytest.raises(ValueError, match="RGB values must be 0-255"):
            PatternBase._scale_color((100, -50, 100), 1.0)

    def test_rgb_negative_blue_rejected(self):
        """Negative blue channel rejected."""
        with pytest.raises(ValueError, match="RGB values must be 0-255"):
            PatternBase._scale_color((100, 100, -255), 1.0)

    def test_rgb_over_255_red_rejected(self):
        """Red channel over 255 rejected."""
        with pytest.raises(ValueError, match="RGB values must be 0-255"):
            PatternBase._scale_color((256, 100, 100), 1.0)

    def test_rgb_over_255_green_rejected(self):
        """Green channel over 255 rejected."""
        with pytest.raises(ValueError, match="RGB values must be 0-255"):
            PatternBase._scale_color((100, 300, 100), 1.0)

    def test_rgb_over_255_blue_rejected(self):
        """Blue channel over 255 rejected."""
        with pytest.raises(ValueError, match="RGB values must be 0-255"):
            PatternBase._scale_color((100, 100, 1000), 1.0)

    def test_rgb_boundary_values(self):
        """Boundary RGB values (0 and 255) are accepted."""
        # Minimum
        result = PatternBase._scale_color((0, 0, 0), 1.0)
        assert result == (0, 0, 0)

        # Maximum
        result = PatternBase._scale_color((255, 255, 255), 1.0)
        assert result == (255, 255, 255)

        # Mixed
        result = PatternBase._scale_color((0, 128, 255), 1.0)
        assert result == (0, 128, 255)

    def test_factor_negative_rejected(self):
        """Negative factor rejected."""
        with pytest.raises(ValueError, match="factor must be 0.0-2.0"):
            PatternBase._scale_color((100, 100, 100), -0.5)

    def test_factor_over_2_rejected(self):
        """Factor over 2.0 rejected."""
        with pytest.raises(ValueError, match="factor must be 0.0-2.0"):
            PatternBase._scale_color((100, 100, 100), 3.0)

    def test_factor_boundary_values(self):
        """Boundary factor values (0.0 and 2.0) are accepted."""
        # Minimum
        result = PatternBase._scale_color((100, 100, 100), 0.0)
        assert result == (0, 0, 0)

        # Maximum
        result = PatternBase._scale_color((100, 100, 100), 2.0)
        assert result == (200, 200, 200)

    def test_factor_clamping_at_255(self):
        """Factor scaling clamps at 255 (doesn't overflow)."""
        # 200 * 2.0 = 400, should clamp to 255
        result = PatternBase._scale_color((200, 200, 200), 2.0)
        assert result == (255, 255, 255)

    def test_render_with_invalid_color_rejected(self):
        """Pattern.render() with invalid base color raises ValueError."""
        pattern = BreathingPattern(16)

        # Negative color
        with pytest.raises(ValueError, match="RGB values must be 0-255"):
            pattern.render((-10, 100, 100))

        # Over 255 color
        with pytest.raises(ValueError, match="RGB values must be 0-255"):
            pattern.render((100, 300, 100))


# =============================================================================
# HIGH-7: Power Source Change Warning
# =============================================================================

class MockGPIO:
    """Mock GPIO provider for testing."""
    BCM = 11
    OUT = 0

    def setmode(self, mode: int) -> None:
        pass

    def setup(self, pin: int, direction: int) -> None:
        pass

    def cleanup(self, pin=None) -> None:
        pass


class TestHigh7PowerSourceWarning:
    """Test that power source changes issue warnings when becoming more restrictive."""

    @pytest.fixture
    def manager(self):
        """LED safety manager with external power (permissive)."""
        return LEDSafetyManager(
            power_source=PowerSource.EXTERNAL_5V,
            gpio_provider=MockGPIO()
        )

    @pytest.fixture
    def ring_profile(self):
        """Standard LED ring profile."""
        return LEDRingProfile(
            num_leds=16,
            current_per_led_ma=60.0,
            gpio_pin=18,
            pwm_channel=0,
            name="Test Ring"
        )

    def test_switch_external_to_pi_logs_warning(self, manager, ring_profile, caplog):
        """Switching from EXTERNAL_5V to PI_5V_RAIL logs warning."""
        manager.register_ring("ring1", ring_profile)

        # Switch to more restrictive power source
        with caplog.at_level(logging.WARNING):
            manager.set_power_source(PowerSource.PI_5V_RAIL)

        # Check warning was logged
        assert any("more restrictive" in record.message for record in caplog.records)
        assert any("255" in record.message and "50" in record.message for record in caplog.records)

    def test_switch_pi_to_external_logs_info(self, ring_profile, caplog):
        """Switching from PI_5V_RAIL to EXTERNAL_5V logs info (not warning)."""
        # Start with Pi power (restrictive)
        manager = LEDSafetyManager(
            power_source=PowerSource.PI_5V_RAIL,
            gpio_provider=MockGPIO()
        )
        manager.register_ring("ring1", ring_profile)

        # Switch to less restrictive power source
        with caplog.at_level(logging.INFO):
            manager.set_power_source(PowerSource.EXTERNAL_5V)

        # Should be INFO level, not WARNING
        warning_messages = [r.message for r in caplog.records if r.levelname == "WARNING"]
        assert not any("more restrictive" in msg for msg in warning_messages)

    def test_brightness_clamped_after_power_switch(self, manager, ring_profile):
        """Brightness is clamped when switching to restrictive power source."""
        manager.register_ring("ring1", ring_profile)

        # Initially on EXTERNAL_5V - full brightness allowed
        allowed, safe = manager.validate_brightness("ring1", 255)
        assert allowed is True
        assert safe == 255

        # Switch to Pi power (restrictive)
        manager.set_power_source(PowerSource.PI_5V_RAIL)

        # Now brightness should be clamped
        allowed, safe = manager.validate_brightness("ring1", 255)
        assert allowed is False
        assert safe == 50

    def test_switch_unknown_to_pi_logs_info(self, ring_profile, caplog):
        """Switching from UNKNOWN to PI_5V_RAIL logs info (same restrictiveness)."""
        # Start with UNKNOWN power (defaults to Pi level)
        manager = LEDSafetyManager(
            power_source=PowerSource.UNKNOWN,
            gpio_provider=MockGPIO()
        )
        manager.register_ring("ring1", ring_profile)

        # Switch to Pi power (same restrictiveness)
        with caplog.at_level(logging.INFO):
            manager.set_power_source(PowerSource.PI_5V_RAIL)

        # Should NOT be a restrictive warning (same max brightness)
        warning_messages = [r.message for r in caplog.records if r.levelname == "WARNING"]
        assert not any("more restrictive" in msg for msg in warning_messages)

    def test_switch_unknown_to_external_logs_info(self, ring_profile, caplog):
        """Switching from UNKNOWN to EXTERNAL_5V logs info (less restrictive)."""
        # Start with UNKNOWN power
        manager = LEDSafetyManager(
            power_source=PowerSource.UNKNOWN,
            gpio_provider=MockGPIO()
        )
        manager.register_ring("ring1", ring_profile)

        # Switch to external power (less restrictive)
        with caplog.at_level(logging.INFO):
            manager.set_power_source(PowerSource.EXTERNAL_5V)

        # Should be INFO, not WARNING
        warning_messages = [r.message for r in caplog.records if r.levelname == "WARNING"]
        assert not any("more restrictive" in msg for msg in warning_messages)

    def test_warning_message_content(self, manager, ring_profile, caplog):
        """Warning message contains meaningful information."""
        manager.register_ring("ring1", ring_profile)

        with caplog.at_level(logging.WARNING):
            manager.set_power_source(PowerSource.PI_5V_RAIL)

        # Find the warning message
        warning_msg = None
        for record in caplog.records:
            if record.levelname == "WARNING" and "more restrictive" in record.message:
                warning_msg = record.message
                break

        assert warning_msg is not None
        # Check it contains old and new power source names
        assert "EXTERNAL_5V" in warning_msg
        assert "PI_5V_RAIL" in warning_msg
        # Check it mentions brightness reduction
        assert "255" in warning_msg
        assert "50" in warning_msg
        # Check it warns about clamping
        assert "clamp" in warning_msg.lower()


# =============================================================================
# Integration Tests
# =============================================================================

class TestIntegration:
    """Integration tests combining all three fixes."""

    def test_zero_pixels_caught_before_modulo(self):
        """Zero pixels caught by __init__ before modulo division."""
        # This would cause ZeroDivisionError in _compute_frame() without fix
        with pytest.raises(ValueError, match="num_pixels must be positive"):
            pattern = SpinPattern(num_pixels=0)

    def test_invalid_rgb_caught_in_render(self):
        """Invalid RGB caught during render before hardware damage."""
        pattern = BreathingPattern(16)

        # This would send invalid data to WS2812B without validation
        with pytest.raises(ValueError, match="RGB values must be 0-255"):
            pattern.render((300, -50, 1000))

    def test_power_switch_warns_before_brightness_issue(self, caplog):
        """Power source switch warns before brightness causes overcurrent."""
        manager = LEDSafetyManager(
            power_source=PowerSource.EXTERNAL_5V,
            gpio_provider=MockGPIO()
        )

        ring = LEDRingProfile(num_leds=16, gpio_pin=18, pwm_channel=0, name="Test")
        manager.register_ring("ring1", ring)

        # Switch to restrictive power - should warn
        with caplog.at_level(logging.WARNING):
            manager.set_power_source(PowerSource.PI_5V_RAIL)

        # Verify warning occurred
        assert any("more restrictive" in r.message for r in caplog.records)

        # Verify brightness is now clamped (prevents overcurrent)
        allowed, safe = manager.validate_brightness("ring1", 255)
        assert safe == 50  # Clamped to safe level

    def test_all_safety_constraints_enforced(self):
        """All three safety fixes work together."""
        # HIGH-5: Zero pixels rejected
        with pytest.raises(ValueError):
            SpinPattern(num_pixels=0)

        # HIGH-6: Invalid RGB rejected
        with pytest.raises(ValueError):
            PatternBase._scale_color((256, 100, 100), 1.0)

        # HIGH-7: Power source change warns
        manager = LEDSafetyManager(
            power_source=PowerSource.EXTERNAL_5V,
            gpio_provider=MockGPIO()
        )
        ring = LEDRingProfile(num_leds=16, gpio_pin=18, pwm_channel=0, name="Test")
        manager.register_ring("ring1", ring)

        # This should log warning
        manager.set_power_source(PowerSource.PI_5V_RAIL)
        assert manager.power_source == PowerSource.PI_5V_RAIL


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
