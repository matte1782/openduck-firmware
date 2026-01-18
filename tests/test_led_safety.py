"""Tests for LED Safety System.

Tests comprehensive fail-safe mechanisms for WS2812B LED rings including:
- Current limiting and estimation
- Brightness validation and clamping
- GPIO state validation
- Emergency shutdown handling
- Power source switching
"""

import pytest
import threading
import time
from typing import Any, Optional

from src.safety.led_safety import (
    LEDSafetyManager,
    LEDRingProfile,
    PowerSource,
    SafetyLevel,
    CurrentEstimate,
)


class MockGPIO:
    """Mock GPIO provider for testing."""

    BCM = 11
    OUT = 0

    def __init__(self):
        self.mode_set = False
        self.pins_setup = []

    def setmode(self, mode: int) -> None:
        self.mode_set = True

    def setup(self, pin: int, direction: int) -> None:
        self.pins_setup.append((pin, direction))

    def cleanup(self, pin: Optional[int] = None) -> None:
        if pin is not None:
            self.pins_setup = [(p, d) for p, d in self.pins_setup if p != pin]
        else:
            self.pins_setup = []


# Fixtures

@pytest.fixture
def mock_gpio():
    """Provide mock GPIO for testing."""
    return MockGPIO()


@pytest.fixture
def manager_pi_power(mock_gpio):
    """LED safety manager with Pi 5V rail power."""
    return LEDSafetyManager(
        power_source=PowerSource.PI_5V_RAIL,
        gpio_provider=mock_gpio
    )


@pytest.fixture
def manager_external_power(mock_gpio):
    """LED safety manager with external 5V power."""
    return LEDSafetyManager(
        power_source=PowerSource.EXTERNAL_5V,
        gpio_provider=mock_gpio
    )


@pytest.fixture
def ring1_profile():
    """LED Ring 1 profile (Left Eye)."""
    return LEDRingProfile(
        num_leds=16,
        current_per_led_ma=60.0,
        gpio_pin=18,
        pwm_channel=0,
        name="Left Eye"
    )


@pytest.fixture
def ring2_profile():
    """LED Ring 2 profile (Right Eye)."""
    return LEDRingProfile(
        num_leds=16,
        current_per_led_ma=60.0,
        gpio_pin=13,
        pwm_channel=1,
        name="Right Eye"
    )


# Test LEDRingProfile

class TestLEDRingProfile:
    """Test LED ring profile validation."""

    def test_valid_profile(self, ring1_profile):
        """Test valid profile creation."""
        assert ring1_profile.num_leds == 16
        assert ring1_profile.current_per_led_ma == 60.0
        assert ring1_profile.gpio_pin == 18
        assert ring1_profile.pwm_channel == 0
        assert ring1_profile.name == "Left Eye"

    def test_max_current_calculation(self, ring1_profile):
        """Test maximum current calculation."""
        expected = 16 * 60.0  # 960mA
        assert ring1_profile.max_current_ma == expected

    def test_invalid_num_leds(self):
        """Test validation of num_leds."""
        with pytest.raises(ValueError, match="num_leds must be positive"):
            LEDRingProfile(num_leds=0)

        with pytest.raises(ValueError, match="num_leds must be positive"):
            LEDRingProfile(num_leds=-5)

    def test_invalid_current_per_led(self):
        """Test validation of current_per_led_ma."""
        with pytest.raises(ValueError, match="current_per_led_ma must be positive"):
            LEDRingProfile(current_per_led_ma=0)

        with pytest.raises(ValueError, match="current_per_led_ma must be positive"):
            LEDRingProfile(current_per_led_ma=-10.0)

    def test_invalid_gpio_pin(self):
        """Test validation of GPIO pin."""
        with pytest.raises(ValueError, match="gpio_pin must be 0-27"):
            LEDRingProfile(gpio_pin=28)

        with pytest.raises(ValueError, match="gpio_pin must be 0-27"):
            LEDRingProfile(gpio_pin=-1)

    def test_invalid_pwm_channel(self):
        """Test validation of PWM channel."""
        with pytest.raises(ValueError, match="pwm_channel must be 0 or 1"):
            LEDRingProfile(pwm_channel=2)

        with pytest.raises(ValueError, match="pwm_channel must be 0 or 1"):
            LEDRingProfile(pwm_channel=-1)


# Test LEDSafetyManager Initialization

class TestLEDSafetyManagerInit:
    """Test LED safety manager initialization."""

    def test_init_pi_power(self, manager_pi_power):
        """Test initialization with Pi power source."""
        assert manager_pi_power.power_source == PowerSource.PI_5V_RAIL
        assert manager_pi_power.max_brightness_pi_power == 50
        assert manager_pi_power.gpio_available is True
        assert manager_pi_power.emergency_shutdown_active is False

    def test_init_external_power(self, manager_external_power):
        """Test initialization with external power source."""
        assert manager_external_power.power_source == PowerSource.EXTERNAL_5V
        assert manager_external_power.gpio_available is True

    def test_init_no_gpio(self):
        """Test initialization without GPIO (simulation mode).

        When gpio_provider=None AND RPi.GPIO is not importable,
        the manager should run in simulation mode with gpio_available=False.
        """
        import sys
        from unittest.mock import patch

        # Mock RPi.GPIO to raise ImportError (simulates non-Pi environment)
        with patch.dict(sys.modules, {'RPi': None, 'RPi.GPIO': None}):
            # Force ImportError when trying to import RPi.GPIO
            with patch('builtins.__import__', side_effect=lambda name, *args:
                       (_ for _ in ()).throw(ImportError(f"No module named '{name}'"))
                       if 'RPi' in name else __builtins__.__import__(name, *args)):
                manager = LEDSafetyManager(gpio_provider=None)
                assert manager.gpio_available is False

    def test_init_custom_limits(self, mock_gpio):
        """Test initialization with custom limits."""
        manager = LEDSafetyManager(
            gpio_provider=mock_gpio,
            custom_pi_max_current_ma=1500.0,
            custom_brightness_limit=75
        )
        assert manager.max_brightness_pi_power == 75

    def test_init_invalid_custom_current(self, mock_gpio):
        """Test invalid custom current limit."""
        with pytest.raises(ValueError, match="custom_pi_max_current_ma must be 0-3000mA"):
            LEDSafetyManager(
                gpio_provider=mock_gpio,
                custom_pi_max_current_ma=5000.0
            )

    def test_init_invalid_custom_brightness(self, mock_gpio):
        """Test invalid custom brightness limit."""
        with pytest.raises(ValueError, match="custom_brightness_limit must be 0-255"):
            LEDSafetyManager(
                gpio_provider=mock_gpio,
                custom_brightness_limit=300
            )


# Test Ring Registration

class TestRingRegistration:
    """Test LED ring registration and management."""

    def test_register_ring(self, manager_pi_power, ring1_profile):
        """Test registering a ring."""
        manager_pi_power.register_ring("ring1", ring1_profile)
        diag = manager_pi_power.get_diagnostics()
        assert diag["registered_rings"] == 1
        assert "ring1" in diag["ring_details"]

    def test_register_duplicate_ring(self, manager_pi_power, ring1_profile):
        """Test registering duplicate ring raises error."""
        manager_pi_power.register_ring("ring1", ring1_profile)
        with pytest.raises(ValueError, match="already registered"):
            manager_pi_power.register_ring("ring1", ring1_profile)

    def test_register_multiple_rings(
        self, manager_pi_power, ring1_profile, ring2_profile
    ):
        """Test registering multiple rings."""
        manager_pi_power.register_ring("ring1", ring1_profile)
        manager_pi_power.register_ring("ring2", ring2_profile)
        diag = manager_pi_power.get_diagnostics()
        assert diag["registered_rings"] == 2

    def test_unregister_ring(self, manager_pi_power, ring1_profile):
        """Test unregistering a ring."""
        manager_pi_power.register_ring("ring1", ring1_profile)
        assert manager_pi_power.unregister_ring("ring1") is True
        diag = manager_pi_power.get_diagnostics()
        assert diag["registered_rings"] == 0

    def test_unregister_nonexistent_ring(self, manager_pi_power):
        """Test unregistering nonexistent ring returns False."""
        assert manager_pi_power.unregister_ring("ring1") is False


# Test GPIO Validation

class TestGPIOValidation:
    """Test GPIO state validation."""

    def test_gpio_available_normal(self, manager_pi_power, ring1_profile):
        """Test GPIO validation in normal state."""
        manager_pi_power.register_ring("ring1", ring1_profile)
        valid, reason = manager_pi_power.validate_gpio_available("ring1")
        assert valid is True
        assert reason == ""

    def test_gpio_unregistered_ring(self, manager_pi_power):
        """Test GPIO validation for unregistered ring."""
        valid, reason = manager_pi_power.validate_gpio_available("ring1")
        assert valid is False
        assert "not registered" in reason

    def test_gpio_emergency_shutdown(self, manager_pi_power, ring1_profile):
        """Test GPIO validation during emergency shutdown."""
        manager_pi_power.register_ring("ring1", ring1_profile)
        manager_pi_power.emergency_shutdown("test")

        valid, reason = manager_pi_power.validate_gpio_available("ring1")
        assert valid is False
        assert "Emergency shutdown" in reason

    def test_gpio_simulation_mode(self, ring1_profile):
        """Test GPIO validation in simulation mode (no GPIO)."""
        manager = LEDSafetyManager(gpio_provider=None)
        manager.register_ring("ring1", ring1_profile)

        valid, reason = manager.validate_gpio_available("ring1")
        assert valid is True  # Allowed in simulation mode


# Test Brightness Validation

class TestBrightnessValidation:
    """Test brightness validation and clamping."""

    def test_brightness_clamp_pi_power(self, manager_pi_power, ring1_profile):
        """Test brightness clamping on Pi power."""
        manager_pi_power.register_ring("ring1", ring1_profile)

        # Request full brightness
        allowed, safe = manager_pi_power.validate_brightness("ring1", 255)
        assert allowed is False
        assert safe == 50  # Clamped to safe level

    def test_brightness_safe_pi_power(self, manager_pi_power, ring1_profile):
        """Test safe brightness on Pi power."""
        manager_pi_power.register_ring("ring1", ring1_profile)

        allowed, safe = manager_pi_power.validate_brightness("ring1", 50)
        assert allowed is True
        assert safe == 50

    def test_brightness_external_power(self, manager_external_power, ring1_profile):
        """Test brightness on external power (no clamping)."""
        manager_external_power.register_ring("ring1", ring1_profile)

        allowed, safe = manager_external_power.validate_brightness("ring1", 255)
        assert allowed is True
        assert safe == 255

    def test_brightness_force_override(self, manager_pi_power, ring1_profile):
        """Test force override bypasses safety limits."""
        manager_pi_power.register_ring("ring1", ring1_profile)

        allowed, safe = manager_pi_power.validate_brightness(
            "ring1", 255, force=True
        )
        assert allowed is True
        assert safe == 255  # Force allowed unsafe brightness

    def test_brightness_clamp_to_range(self, manager_pi_power, ring1_profile):
        """Test brightness clamped to 0-255 range."""
        manager_pi_power.register_ring("ring1", ring1_profile)

        # Test negative
        allowed, safe = manager_pi_power.validate_brightness("ring1", -10)
        assert safe == 0

        # Test over max (on external power)
        manager_pi_power.set_power_source(PowerSource.EXTERNAL_5V)
        allowed, safe = manager_pi_power.validate_brightness("ring1", 300)
        assert safe == 255

    def test_brightness_unregistered_ring(self, manager_pi_power):
        """Test brightness validation for unregistered ring raises error."""
        with pytest.raises(ValueError, match="not registered"):
            manager_pi_power.validate_brightness("ring1", 128)


# Test Current Estimation

class TestCurrentEstimation:
    """Test current draw estimation."""

    def test_estimate_single_ring_full(self, manager_pi_power, ring1_profile):
        """Test current estimation for single ring at full brightness."""
        manager_pi_power.register_ring("ring1", ring1_profile)

        estimate = manager_pi_power.estimate_current({"ring1": 255})

        # Full brightness: 16 LEDs × 60mA = 960mA
        assert estimate.total_ma == pytest.approx(960.0, rel=0.01)
        assert estimate.per_ring_ma["ring1"] == pytest.approx(960.0, rel=0.01)

    def test_estimate_single_ring_half(self, manager_pi_power, ring1_profile):
        """Test current estimation for single ring at half brightness."""
        manager_pi_power.register_ring("ring1", ring1_profile)

        estimate = manager_pi_power.estimate_current({"ring1": 128})

        # Half brightness: 960mA × (128/255) = ~482mA
        expected = 960.0 * (128 / 255)
        assert estimate.total_ma == pytest.approx(expected, rel=0.01)

    def test_estimate_dual_rings(
        self, manager_pi_power, ring1_profile, ring2_profile
    ):
        """Test current estimation for dual rings."""
        manager_pi_power.register_ring("ring1", ring1_profile)
        manager_pi_power.register_ring("ring2", ring2_profile)

        estimate = manager_pi_power.estimate_current({"ring1": 128, "ring2": 128})

        # Each ring: ~482mA, total: ~964mA
        expected_per_ring = 960.0 * (128 / 255)
        expected_total = expected_per_ring * 2

        assert estimate.total_ma == pytest.approx(expected_total, rel=0.01)
        assert estimate.per_ring_ma["ring1"] == pytest.approx(expected_per_ring, rel=0.01)
        assert estimate.per_ring_ma["ring2"] == pytest.approx(expected_per_ring, rel=0.01)

    def test_estimate_zero_brightness(self, manager_pi_power, ring1_profile):
        """Test current estimation at zero brightness."""
        manager_pi_power.register_ring("ring1", ring1_profile)

        estimate = manager_pi_power.estimate_current({"ring1": 0})
        assert estimate.total_ma == 0.0

    def test_estimate_safety_levels_pi_power(
        self, manager_pi_power, ring1_profile, ring2_profile
    ):
        """Test safety level assessment on Pi power."""
        manager_pi_power.register_ring("ring1", ring1_profile)
        manager_pi_power.register_ring("ring2", ring2_profile)

        # Safe level (both at brightness 50)
        estimate = manager_pi_power.estimate_current({"ring1": 50, "ring2": 50})
        assert estimate.safety_level == SafetyLevel.SAFE
        assert estimate.headroom_ma > 0

        # Warning level (both at brightness 100)
        estimate = manager_pi_power.estimate_current({"ring1": 100, "ring2": 100})
        # Total: ~752mA, max: 1000mA, utilization: 75% (WARNING threshold: 80%)
        # Should still be SAFE, approaching WARNING

        # Emergency level (both at full brightness)
        estimate = manager_pi_power.estimate_current({"ring1": 255, "ring2": 255})
        # Total: 1920mA, max: 1000mA -> EMERGENCY
        assert estimate.safety_level == SafetyLevel.EMERGENCY
        assert estimate.headroom_ma < 0

    def test_estimate_unregistered_ring(self, manager_pi_power):
        """Test current estimation for unregistered ring raises error."""
        with pytest.raises(ValueError, match="not registered"):
            manager_pi_power.estimate_current({"ring1": 128})


# Test Emergency Shutdown

class TestEmergencyShutdown:
    """Test emergency shutdown functionality."""

    def test_emergency_shutdown_activate(self, manager_pi_power):
        """Test activating emergency shutdown."""
        assert manager_pi_power.emergency_shutdown_active is False

        result = manager_pi_power.emergency_shutdown("test")
        assert result is True
        assert manager_pi_power.emergency_shutdown_active is True

    def test_emergency_shutdown_duplicate(self, manager_pi_power):
        """Test duplicate emergency shutdown returns False."""
        manager_pi_power.emergency_shutdown("test1")
        result = manager_pi_power.emergency_shutdown("test2")
        assert result is False  # Already active

    def test_emergency_shutdown_blocks_gpio(
        self, manager_pi_power, ring1_profile
    ):
        """Test emergency shutdown blocks GPIO operations."""
        manager_pi_power.register_ring("ring1", ring1_profile)
        manager_pi_power.emergency_shutdown("test")

        valid, reason = manager_pi_power.validate_gpio_available("ring1")
        assert valid is False
        assert "Emergency shutdown" in reason

    def test_emergency_shutdown_reset(self, manager_pi_power):
        """Test resetting emergency shutdown."""
        manager_pi_power.emergency_shutdown("test")
        assert manager_pi_power.emergency_shutdown_active is True

        result = manager_pi_power.reset_emergency_shutdown()
        assert result is True
        assert manager_pi_power.emergency_shutdown_active is False

    def test_emergency_shutdown_reset_when_not_active(self, manager_pi_power):
        """Test reset when not in shutdown returns False."""
        result = manager_pi_power.reset_emergency_shutdown()
        assert result is False


# Test Power Source Switching

class TestPowerSourceSwitching:
    """Test power source configuration changes."""

    def test_switch_to_external_power(self, manager_pi_power, ring1_profile):
        """Test switching from Pi to external power."""
        manager_pi_power.register_ring("ring1", ring1_profile)

        # Initially Pi power - brightness clamped
        allowed, safe = manager_pi_power.validate_brightness("ring1", 255)
        assert safe == 50

        # Switch to external power
        manager_pi_power.set_power_source(PowerSource.EXTERNAL_5V)
        assert manager_pi_power.power_source == PowerSource.EXTERNAL_5V

        # Now full brightness allowed
        allowed, safe = manager_pi_power.validate_brightness("ring1", 255)
        assert safe == 255

    def test_switch_to_pi_power(self, manager_external_power, ring1_profile):
        """Test switching from external to Pi power."""
        manager_external_power.register_ring("ring1", ring1_profile)

        # Initially external - full brightness
        allowed, safe = manager_external_power.validate_brightness("ring1", 255)
        assert safe == 255

        # Switch to Pi power
        manager_external_power.set_power_source(PowerSource.PI_5V_RAIL)
        assert manager_external_power.power_source == PowerSource.PI_5V_RAIL

        # Now brightness clamped
        allowed, safe = manager_external_power.validate_brightness("ring1", 255)
        assert safe == 50


# Test Diagnostics

class TestDiagnostics:
    """Test diagnostic information retrieval."""

    def test_diagnostics_empty(self, manager_pi_power):
        """Test diagnostics with no rings registered."""
        diag = manager_pi_power.get_diagnostics()

        assert diag["power_source"] == "PI_5V_RAIL"
        assert diag["max_brightness"] == 50
        assert diag["registered_rings"] == 0
        assert diag["gpio_available"] is True
        assert diag["emergency_shutdown"] is False

    def test_diagnostics_with_rings(
        self, manager_pi_power, ring1_profile, ring2_profile
    ):
        """Test diagnostics with registered rings."""
        manager_pi_power.register_ring("ring1", ring1_profile)
        manager_pi_power.register_ring("ring2", ring2_profile)

        diag = manager_pi_power.get_diagnostics()

        assert diag["registered_rings"] == 2
        assert "ring1" in diag["ring_details"]
        assert "ring2" in diag["ring_details"]
        assert diag["ring_details"]["ring1"]["name"] == "Left Eye"
        assert diag["ring_details"]["ring2"]["name"] == "Right Eye"

    def test_diagnostics_current_limits(self, manager_pi_power):
        """Test current limit information in diagnostics."""
        diag = manager_pi_power.get_diagnostics()

        limits = diag["current_limits"]
        assert "max_allowed_ma" in limits
        assert "pi_rail_max_ma" in limits
        assert "warning_threshold" in limits
        assert limits["pi_rail_max_ma"] == 1200.0
        assert limits["pi_reserve_ma"] == 200.0


# Test Thread Safety

class TestThreadSafety:
    """Test thread safety of LED safety manager."""

    def test_concurrent_brightness_validation(
        self, manager_pi_power, ring1_profile
    ):
        """Test concurrent brightness validation calls."""
        manager_pi_power.register_ring("ring1", ring1_profile)

        results = []

        def validate_brightness():
            for _ in range(100):
                allowed, safe = manager_pi_power.validate_brightness("ring1", 255)
                results.append((allowed, safe))

        # Start 10 threads
        threads = [threading.Thread(target=validate_brightness) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All results should be consistent
        assert len(results) == 1000
        for allowed, safe in results:
            assert allowed is False
            assert safe == 50

    def test_concurrent_emergency_shutdown(self, manager_pi_power):
        """Test concurrent emergency shutdown calls."""
        results = []

        def trigger_shutdown(reason):
            result = manager_pi_power.emergency_shutdown(reason)
            results.append(result)
            time.sleep(0.001)

        # Start 10 threads
        threads = [
            threading.Thread(target=trigger_shutdown, args=(f"test{i}",))
            for i in range(10)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Only one should succeed
        assert sum(results) == 1
        assert manager_pi_power.emergency_shutdown_active is True


# Test Edge Cases

class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_zero_led_ring(self):
        """Test ring with zero LEDs raises error."""
        with pytest.raises(ValueError):
            LEDRingProfile(num_leds=0)

    def test_brightness_boundary_values(self, manager_pi_power, ring1_profile):
        """Test brightness at boundary values."""
        manager_pi_power.register_ring("ring1", ring1_profile)

        # Minimum
        allowed, safe = manager_pi_power.validate_brightness("ring1", 0)
        assert safe == 0

        # At limit
        allowed, safe = manager_pi_power.validate_brightness("ring1", 50)
        assert safe == 50
        assert allowed is True

        # Just over limit
        allowed, safe = manager_pi_power.validate_brightness("ring1", 51)
        assert safe == 50
        assert allowed is False

    def test_current_estimate_at_limits(
        self, manager_pi_power, ring1_profile, ring2_profile
    ):
        """Test current estimation at exactly power limits."""
        manager_pi_power.register_ring("ring1", ring1_profile)
        manager_pi_power.register_ring("ring2", ring2_profile)

        # Calculate brightness for exactly 1000mA (max allowed on Pi)
        # 1000mA / 1920mA (max both rings) = 52.08% → brightness ~133
        estimate = manager_pi_power.estimate_current({"ring1": 133, "ring2": 133})

        # Should be just at or slightly over CRITICAL threshold
        assert estimate.safety_level in (SafetyLevel.CRITICAL, SafetyLevel.EMERGENCY)

    def test_repr(self, manager_pi_power, ring1_profile):
        """Test string representation."""
        manager_pi_power.register_ring("ring1", ring1_profile)
        repr_str = repr(manager_pi_power)

        assert "LEDSafetyManager" in repr_str
        assert "PI_5V_RAIL" in repr_str
        assert "rings=1" in repr_str
