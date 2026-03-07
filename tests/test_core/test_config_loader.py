"""Tests for ConfigLoader — robot_config.yaml loader and validator.

Tests cover:
- Loading from dict (unit tests, no file I/O)
- Loading from file (integration)
- Missing key detection for every required field
- Type validation (int vs float vs bool vs str)
- Hex address parsing (0x40 as int and string)
- Factory methods (make_head_config, make_head_limits)
- Edge cases (empty file, non-dict root, None values)
"""

import os
import tempfile
from pathlib import Path

import pytest
import yaml

from src.core.config_loader import (
    ConfigLoader,
    ConfigError,
    HeadChannels,
    HeadLimitsConfig,
    HeadServoFlags,
    HeadAnimationConfig,
    ArmLimitsConfig,
    ArmCollisionZone,
    LedEyeConfig,
    SafetyConfig,
    I2CConfig,
)


# =============================================================================
# FIXTURES
# =============================================================================

def _minimal_config() -> dict:
    """Return a minimal valid config dict matching robot_config.yaml structure."""
    return {
        "head": {
            "enabled": True,
            "neck_pitch_channel": 0,
            "head_pitch_channel": 1,
            "head_yaw_channel": 2,
            "head_roll_channel": 3,
            "limits": {
                "neck_pitch_min": -20,
                "neck_pitch_max": 65,
                "head_pitch_min": -45,
                "head_pitch_max": 45,
                "head_yaw_min": -90,
                "head_yaw_max": 90,
                "head_roll_min": -30,
                "head_roll_max": 30,
            },
            "servo_config": {
                "neck_pitch_inverted": False,
                "head_pitch_inverted": False,
                "head_yaw_inverted": False,
                "head_roll_inverted": False,
            },
            "animation": {
                "default_speed_ms": 300,
                "easing": "ease_in_out",
                "nod_amplitude": 15,
                "shake_amplitude": 20,
                "tilt_amplitude": 10,
                "glance_max_deviation": 30,
                "glance_hold_ms": 500,
            },
            "safety": {
                "velocity_limit_deg_per_sec": 180,
                "soft_limit_margin": 10,
            },
        },
        "arms": {
            "enabled": True,
            "limits": {
                "shoulder_yaw_min": -120,
                "shoulder_yaw_max": 120,
                "shoulder_pitch_min": -10,
                "shoulder_pitch_max": 90,
                "elbow_min": 0,
                "elbow_max": 135,
            },
            "collision_zone": {
                "forward_yaw_min": -30,
                "forward_yaw_max": 30,
                "forward_pitch_max": 30,
            },
        },
        "leds": {
            "enabled": True,
            "left_eye": {"pin": 10, "count": 16, "brightness": 0.8},
            "right_eye": {"pin": 13, "count": 16, "brightness": 0.8},
        },
        "i2c": {
            "bus": 1,
            "pca9685": {"address": 0x40, "frequency": 50},
        },
        "safety": {
            "emergency_stop_pin": 26,
            "watchdog_timeout_ms": 1000,
            "startup_delay_ms": 500,
        },
    }


@pytest.fixture
def valid_config():
    return _minimal_config()


@pytest.fixture
def config(valid_config):
    return ConfigLoader(valid_config)


# =============================================================================
# BASIC LOADING
# =============================================================================


class TestConfigLoaderInit:
    def test_loads_valid_config(self, valid_config):
        cfg = ConfigLoader(valid_config)
        assert cfg is not None

    def test_rejects_non_dict(self):
        with pytest.raises(ConfigError, match="must be a dict"):
            ConfigLoader("not a dict")

    def test_rejects_list(self):
        with pytest.raises(ConfigError, match="must be a dict"):
            ConfigLoader([1, 2, 3])

    def test_rejects_none(self):
        with pytest.raises(ConfigError, match="must be a dict"):
            ConfigLoader(None)

    def test_repr(self, config):
        r = repr(config)
        assert "head=ON" in r
        assert "arms=ON" in r
        assert "leds=ON" in r
        assert "0x40" in r


# =============================================================================
# FILE LOADING
# =============================================================================


class TestFromFile:
    def test_loads_real_config(self):
        """Load the actual robot_config.yaml from the project."""
        config_path = Path(__file__).parent.parent.parent / "configs" / "robot_config.yaml"
        if not config_path.exists():
            pytest.skip("robot_config.yaml not found")
        cfg = ConfigLoader.from_file(str(config_path))
        assert cfg.head_channels.neck_pitch == 0
        assert cfg.safety_pin == 26

    def test_loads_from_temp_file(self, valid_config):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False, encoding="utf-8"
        ) as f:
            yaml.dump(valid_config, f)
            f.flush()
            cfg = ConfigLoader.from_file(f.name)
        os.unlink(f.name)
        assert cfg.head_channels.neck_pitch == 0

    def test_file_not_found(self):
        with pytest.raises(ConfigError, match="not found"):
            ConfigLoader.from_file("/nonexistent/path.yaml")

    def test_empty_file(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False, encoding="utf-8"
        ) as f:
            f.write("")
            f.flush()
        try:
            with pytest.raises(ConfigError, match="empty"):
                ConfigLoader.from_file(f.name)
        finally:
            os.unlink(f.name)

    def test_invalid_yaml(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False, encoding="utf-8"
        ) as f:
            f.write("{{invalid: yaml: [")
            f.flush()
        try:
            with pytest.raises(ConfigError, match="Invalid YAML"):
                ConfigLoader.from_file(f.name)
        finally:
            os.unlink(f.name)


# =============================================================================
# HEAD SECTION
# =============================================================================


class TestHeadConfig:
    def test_channels(self, config):
        ch = config.head_channels
        assert isinstance(ch, HeadChannels)
        assert ch.neck_pitch == 0
        assert ch.head_pitch == 1
        assert ch.head_yaw == 2
        assert ch.head_roll == 3

    def test_limits(self, config):
        lim = config.head_limits
        assert isinstance(lim, HeadLimitsConfig)
        assert lim.neck_pitch_min == -20.0
        assert lim.neck_pitch_max == 65.0
        assert lim.head_yaw_min == -90.0
        assert lim.head_yaw_max == 90.0

    def test_servo_flags(self, config):
        flags = config.head_servo_flags
        assert isinstance(flags, HeadServoFlags)
        assert flags.neck_pitch_inverted is False
        assert flags.head_roll_inverted is False

    def test_animation(self, config):
        anim = config.head_animation
        assert isinstance(anim, HeadAnimationConfig)
        assert anim.default_speed_ms == 300
        assert anim.easing == "ease_in_out"
        assert anim.nod_amplitude == 15.0

    def test_head_enabled(self, config):
        assert config.head_enabled is True

    def test_head_disabled(self, valid_config):
        valid_config["head"]["enabled"] = False
        cfg = ConfigLoader(valid_config)
        assert cfg.head_enabled is False

    def test_missing_head_section(self, valid_config):
        del valid_config["head"]
        with pytest.raises(ConfigError, match="head"):
            ConfigLoader(valid_config)

    def test_missing_channel(self, valid_config):
        del valid_config["head"]["neck_pitch_channel"]
        with pytest.raises(ConfigError, match="neck_pitch_channel"):
            ConfigLoader(valid_config)

    def test_missing_limit(self, valid_config):
        del valid_config["head"]["limits"]["head_yaw_min"]
        with pytest.raises(ConfigError, match="head_yaw_min"):
            ConfigLoader(valid_config)

    def test_missing_servo_flag(self, valid_config):
        del valid_config["head"]["servo_config"]["head_roll_inverted"]
        with pytest.raises(ConfigError, match="head_roll_inverted"):
            ConfigLoader(valid_config)

    def test_missing_animation_key(self, valid_config):
        del valid_config["head"]["animation"]["easing"]
        with pytest.raises(ConfigError, match="easing"):
            ConfigLoader(valid_config)

    def test_channel_wrong_type(self, valid_config):
        valid_config["head"]["neck_pitch_channel"] = "zero"
        with pytest.raises(ConfigError, match="must be int"):
            ConfigLoader(valid_config)

    def test_limit_wrong_type(self, valid_config):
        valid_config["head"]["limits"]["neck_pitch_min"] = "bad"
        with pytest.raises(ConfigError, match="must be numeric"):
            ConfigLoader(valid_config)

    def test_servo_flag_wrong_type(self, valid_config):
        valid_config["head"]["servo_config"]["neck_pitch_inverted"] = 1
        with pytest.raises(ConfigError, match="must be bool"):
            ConfigLoader(valid_config)


# =============================================================================
# ARM SECTION
# =============================================================================


class TestArmConfig:
    def test_limits(self, config):
        lim = config.arm_limits
        assert isinstance(lim, ArmLimitsConfig)
        assert lim.shoulder_yaw_min == -120.0
        assert lim.shoulder_yaw_max == 120.0
        assert lim.elbow_max == 135.0

    def test_collision_zone(self, config):
        cz = config.arm_collision_zone
        assert isinstance(cz, ArmCollisionZone)
        assert cz.forward_yaw_min == -30.0
        assert cz.forward_yaw_max == 30.0
        assert cz.forward_pitch_max == 30.0

    def test_arms_enabled(self, config):
        assert config.arms_enabled is True

    def test_missing_arms_section(self, valid_config):
        del valid_config["arms"]
        with pytest.raises(ConfigError, match="arms"):
            ConfigLoader(valid_config)

    def test_missing_limit(self, valid_config):
        del valid_config["arms"]["limits"]["elbow_max"]
        with pytest.raises(ConfigError, match="elbow_max"):
            ConfigLoader(valid_config)

    def test_missing_collision_zone(self, valid_config):
        del valid_config["arms"]["collision_zone"]
        with pytest.raises(ConfigError, match="collision_zone"):
            ConfigLoader(valid_config)


# =============================================================================
# LED SECTION
# =============================================================================


class TestLedConfig:
    def test_left_eye(self, config):
        left = config.led_left
        assert isinstance(left, LedEyeConfig)
        assert left.pin == 10
        assert left.count == 16
        assert left.brightness == 0.8

    def test_right_eye(self, config):
        right = config.led_right
        assert isinstance(right, LedEyeConfig)
        assert right.pin == 13
        assert right.count == 16

    def test_leds_enabled(self, config):
        assert config.leds_enabled is True

    def test_missing_left_eye(self, valid_config):
        del valid_config["leds"]["left_eye"]
        with pytest.raises(ConfigError, match="left_eye"):
            ConfigLoader(valid_config)

    def test_missing_pin(self, valid_config):
        del valid_config["leds"]["left_eye"]["pin"]
        with pytest.raises(ConfigError, match="pin"):
            ConfigLoader(valid_config)


# =============================================================================
# I2C SECTION
# =============================================================================


class TestI2CConfig:
    def test_i2c(self, config):
        i2c = config.i2c
        assert isinstance(i2c, I2CConfig)
        assert i2c.bus == 1
        assert i2c.pca9685_address == 0x40
        assert i2c.pca9685_frequency == 50

    def test_pca9685_address_shortcut(self, config):
        assert config.pca9685_address == 0x40

    def test_pca9685_frequency_shortcut(self, config):
        assert config.pca9685_frequency == 50

    def test_hex_string_address(self, valid_config):
        valid_config["i2c"]["pca9685"]["address"] = "0x41"
        cfg = ConfigLoader(valid_config)
        assert cfg.pca9685_address == 0x41

    def test_invalid_hex_string(self, valid_config):
        valid_config["i2c"]["pca9685"]["address"] = "not_hex"
        with pytest.raises(ConfigError, match="invalid hex"):
            ConfigLoader(valid_config)

    def test_address_wrong_type(self, valid_config):
        valid_config["i2c"]["pca9685"]["address"] = [0x40]
        with pytest.raises(ConfigError, match="must be int or hex"):
            ConfigLoader(valid_config)

    def test_missing_pca9685(self, valid_config):
        del valid_config["i2c"]["pca9685"]
        with pytest.raises(ConfigError, match="pca9685"):
            ConfigLoader(valid_config)


# =============================================================================
# SAFETY SECTION
# =============================================================================


class TestSafetyConfig:
    def test_safety(self, config):
        s = config.safety
        assert isinstance(s, SafetyConfig)
        assert s.emergency_stop_pin == 26
        assert s.watchdog_timeout_ms == 1000
        assert s.startup_delay_ms == 500

    def test_safety_pin_shortcut(self, config):
        assert config.safety_pin == 26

    def test_watchdog_shortcut(self, config):
        assert config.watchdog_timeout_ms == 1000

    def test_missing_estop_pin(self, valid_config):
        del valid_config["safety"]["emergency_stop_pin"]
        with pytest.raises(ConfigError, match="emergency_stop_pin"):
            ConfigLoader(valid_config)


# =============================================================================
# FACTORY METHODS
# =============================================================================


class TestFactoryMethods:
    def test_make_head_config_keys(self, config):
        hc = config.make_head_config()
        assert hc["neck_pitch_channel"] == 0
        assert hc["head_pitch_channel"] == 1
        assert hc["head_yaw_channel"] == 2
        assert hc["head_roll_channel"] == 3
        assert hc["neck_pitch_inverted"] is False
        assert hc["default_speed_ms"] == 300
        assert hc["easing"] == "ease_in_out"

    def test_make_head_limits_keys(self, config):
        hl = config.make_head_limits()
        assert hl["neck_pitch_min"] == -20.0
        assert hl["neck_pitch_max"] == 65.0
        assert hl["head_yaw_min"] == -90.0
        assert hl["head_yaw_max"] == 90.0
        assert hl["head_roll_min"] == -30.0
        assert hl["head_roll_max"] == 30.0

    def test_head_config_compatible_with_headconfig(self, config):
        """Verify factory output matches HeadConfig constructor signature."""
        hc = config.make_head_config()
        expected_keys = {
            "neck_pitch_channel", "head_pitch_channel",
            "head_yaw_channel", "head_roll_channel",
            "neck_pitch_inverted", "head_pitch_inverted",
            "head_yaw_inverted", "head_roll_inverted",
            "default_speed_ms", "easing",
            "limits",
        }
        assert set(hc.keys()) == expected_keys

    def test_head_limits_compatible_with_headlimits(self, config):
        """Verify factory output matches HeadLimits constructor signature."""
        hl = config.make_head_limits()
        expected_keys = {
            "neck_pitch_min", "neck_pitch_max",
            "head_pitch_min", "head_pitch_max",
            "head_yaw_min", "head_yaw_max",
            "head_roll_min", "head_roll_max",
        }
        assert set(hl.keys()) == expected_keys


# =============================================================================
# FROZEN DATACLASSES
# =============================================================================


class TestFrozenDataclasses:
    def test_head_channels_immutable(self, config):
        with pytest.raises(AttributeError):
            config.head_channels.neck_pitch = 99

    def test_head_limits_immutable(self, config):
        with pytest.raises(AttributeError):
            config.head_limits.neck_pitch_min = 999

    def test_arm_limits_immutable(self, config):
        with pytest.raises(AttributeError):
            config.arm_limits.elbow_max = 999

    def test_led_config_immutable(self, config):
        with pytest.raises(AttributeError):
            config.led_left.pin = 99

    def test_safety_config_immutable(self, config):
        with pytest.raises(AttributeError):
            config.safety.emergency_stop_pin = 99

    def test_i2c_config_immutable(self, config):
        with pytest.raises(AttributeError):
            config.i2c.bus = 99


# =============================================================================
# CROSS-VALIDATION WITH REAL CONFIG
# =============================================================================


class TestRealConfigValidation:
    """Validate that the config loader produces values matching the actual
    robot_config.yaml — catches drift between code and config file."""

    @pytest.fixture
    def real_config(self):
        config_path = Path(__file__).parent.parent.parent / "configs" / "robot_config.yaml"
        if not config_path.exists():
            pytest.skip("robot_config.yaml not found")
        return ConfigLoader.from_file(str(config_path))

    def test_head_channels_match_physical_wiring(self, real_config):
        """Channels must match Day 49 correction: ch 0-3."""
        ch = real_config.head_channels
        assert ch.neck_pitch == 0
        assert ch.head_pitch == 1
        assert ch.head_yaw == 2
        assert ch.head_roll == 3

    def test_estop_pin_is_26(self, real_config):
        """GPIO 26, not 21 (Day 1 conflict fix)."""
        assert real_config.safety_pin == 26

    def test_pca9685_address_is_0x40(self, real_config):
        assert real_config.pca9685_address == 0x40

    def test_led_pins_not_conflicting_with_i2s(self, real_config):
        """GPIO 18, 19, 20 are I2S — LED pins must not overlap."""
        i2s_pins = {18, 19, 20}
        assert real_config.led_left.pin not in i2s_pins
        assert real_config.led_right.pin not in i2s_pins

    def test_arm_collision_zone_values(self, real_config):
        """Forward zone from CAD Error 1 analysis."""
        cz = real_config.arm_collision_zone
        assert cz.forward_yaw_min == -30.0
        assert cz.forward_yaw_max == 30.0
        assert cz.forward_pitch_max == 30.0


# =============================================================================
# RANGE VALIDATION
# =============================================================================


class TestRangeValidation:
    """HR2: Verify range validation catches out-of-bounds values."""

    def test_channel_too_high(self):
        cfg = _minimal_config()
        cfg["head"]["neck_pitch_channel"] = 16
        with pytest.raises(ConfigError, match="out of range"):
            ConfigLoader(cfg)

    def test_channel_negative(self):
        cfg = _minimal_config()
        cfg["head"]["head_yaw_channel"] = -1
        with pytest.raises(ConfigError, match="out of range"):
            ConfigLoader(cfg)

    def test_led_brightness_over_1(self):
        cfg = _minimal_config()
        cfg["leds"]["left_eye"]["brightness"] = 1.5
        with pytest.raises(ConfigError, match="out of range"):
            ConfigLoader(cfg)

    def test_led_brightness_negative(self):
        cfg = _minimal_config()
        cfg["leds"]["right_eye"]["brightness"] = -0.1
        with pytest.raises(ConfigError, match="out of range"):
            ConfigLoader(cfg)

    def test_led_pin_too_high(self):
        cfg = _minimal_config()
        cfg["leds"]["left_eye"]["pin"] = 28
        with pytest.raises(ConfigError, match="out of range"):
            ConfigLoader(cfg)

    def test_i2c_address_too_high(self):
        cfg = _minimal_config()
        cfg["i2c"]["pca9685"]["address"] = 0x80
        with pytest.raises(ConfigError, match="out of range"):
            ConfigLoader(cfg)

    def test_pwm_frequency_too_low(self):
        cfg = _minimal_config()
        cfg["i2c"]["pca9685"]["frequency"] = 0
        with pytest.raises(ConfigError, match="out of range"):
            ConfigLoader(cfg)

    def test_pwm_frequency_too_high(self):
        cfg = _minimal_config()
        cfg["i2c"]["pca9685"]["frequency"] = 2000
        with pytest.raises(ConfigError, match="out of range"):
            ConfigLoader(cfg)

    def test_safety_gpio_too_high(self):
        cfg = _minimal_config()
        cfg["safety"]["emergency_stop_pin"] = 28
        with pytest.raises(ConfigError, match="out of range"):
            ConfigLoader(cfg)

    def test_watchdog_zero(self):
        cfg = _minimal_config()
        cfg["safety"]["watchdog_timeout_ms"] = 0
        with pytest.raises(ConfigError, match="out of range"):
            ConfigLoader(cfg)

    def test_valid_boundary_values(self):
        """Boundary values should pass validation."""
        cfg = _minimal_config()
        cfg["head"]["neck_pitch_channel"] = 15  # max valid
        cfg["leds"]["left_eye"]["brightness"] = 1.0  # max valid
        cfg["leds"]["left_eye"]["pin"] = 2  # min valid (GPIO 0-1 reserved)
        cfg["i2c"]["pca9685"]["address"] = 0x7F  # max valid
        cfg["i2c"]["pca9685"]["frequency"] = 24  # min valid
        ConfigLoader(cfg)  # should not raise

    def test_head_limits_min_equals_max(self):
        cfg = _minimal_config()
        cfg["head"]["limits"]["head_yaw_min"] = 0
        cfg["head"]["limits"]["head_yaw_max"] = 0
        with pytest.raises(ConfigError, match="must be <"):
            ConfigLoader(cfg)

    def test_head_limits_inverted(self):
        cfg = _minimal_config()
        cfg["head"]["limits"]["neck_pitch_min"] = 65
        cfg["head"]["limits"]["neck_pitch_max"] = -20
        with pytest.raises(ConfigError, match="must be <"):
            ConfigLoader(cfg)

    def test_arm_limits_inverted(self):
        cfg = _minimal_config()
        cfg["arms"]["limits"]["elbow_min"] = 135
        cfg["arms"]["limits"]["elbow_max"] = 0
        with pytest.raises(ConfigError, match="must be <"):
            ConfigLoader(cfg)

    def test_arm_limits_shoulder_inverted(self):
        cfg = _minimal_config()
        cfg["arms"]["limits"]["shoulder_yaw_min"] = 120
        cfg["arms"]["limits"]["shoulder_yaw_max"] = -120
        with pytest.raises(ConfigError, match="must be <"):
            ConfigLoader(cfg)

    def test_startup_delay_negative(self):
        cfg = _minimal_config()
        cfg["safety"]["startup_delay_ms"] = -100
        with pytest.raises(ConfigError, match="out of range"):
            ConfigLoader(cfg)

    def test_startup_delay_too_large(self):
        cfg = _minimal_config()
        cfg["safety"]["startup_delay_ms"] = 999999
        with pytest.raises(ConfigError, match="out of range"):
            ConfigLoader(cfg)

    def test_bus_servo_ids_empty_when_tbd(self):
        """bus_servo_ids returns empty list when IDs are TBD strings."""
        cfg = _minimal_config()
        loader = ConfigLoader(cfg)
        assert loader.bus_servo_ids == []

    def test_bus_servo_ids_returns_ints(self):
        """bus_servo_ids returns IDs when set to integers."""
        cfg = _minimal_config()
        cfg["arms"]["left_arm"] = {
            "shoulder_yaw_id": 2, "shoulder_pitch_id": 3, "elbow_id": 4,
        }
        cfg["arms"]["right_arm"] = {
            "shoulder_yaw_id": 5, "shoulder_pitch_id": 6, "elbow_id": 7,
        }
        loader = ConfigLoader(cfg)
        assert sorted(loader.bus_servo_ids) == [2, 3, 4, 5, 6, 7]
