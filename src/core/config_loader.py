"""Configuration Loader for OpenDuck Mini V3.

Loads and validates robot_config.yaml, producing typed dataclass instances
for each subsystem. This is the single source of truth for all hardware
parameters — no hardcoded defaults elsewhere in the codebase.

Usage:
    >>> from src.core.config_loader import ConfigLoader
    >>> config = ConfigLoader.from_file("configs/robot_config.yaml")
    >>> head_cfg = config.head_config()
    >>> config.safety_pin  # 26
    >>> config.pca9685_address  # 0x40
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

_logger = logging.getLogger(__name__)


class ConfigError(Exception):
    """Raised when configuration is invalid or missing."""

    def __init__(self, message: str, key: Optional[str] = None) -> None:
        self.key = key
        super().__init__(message)


@dataclass(frozen=True)
class HeadChannels:
    """PCA9685 channel assignments for head servos."""
    neck_pitch: int
    head_pitch: int
    head_yaw: int
    head_roll: int


@dataclass(frozen=True)
class HeadLimitsConfig:
    """Joint limits for 4-DOF head (degrees)."""
    neck_pitch_min: float
    neck_pitch_max: float
    head_pitch_min: float
    head_pitch_max: float
    head_yaw_min: float
    head_yaw_max: float
    head_roll_min: float
    head_roll_max: float


@dataclass(frozen=True)
class HeadServoFlags:
    """Servo inversion flags for head."""
    neck_pitch_inverted: bool
    head_pitch_inverted: bool
    head_yaw_inverted: bool
    head_roll_inverted: bool


@dataclass(frozen=True)
class HeadAnimationConfig:
    """Animation parameters for head movements."""
    default_speed_ms: int
    easing: str
    nod_amplitude: float
    shake_amplitude: float
    tilt_amplitude: float
    glance_max_deviation: float
    glance_hold_ms: int


@dataclass(frozen=True)
class ArmLimitsConfig:
    """Joint limits for 3-DOF arm (degrees)."""
    shoulder_yaw_min: float
    shoulder_yaw_max: float
    shoulder_pitch_min: float
    shoulder_pitch_max: float
    elbow_min: float
    elbow_max: float


@dataclass(frozen=True)
class ArmCollisionZone:
    """Forward-zone collision avoidance parameters."""
    forward_yaw_min: float
    forward_yaw_max: float
    forward_pitch_max: float


@dataclass(frozen=True)
class LedEyeConfig:
    """Configuration for a single LED eye ring."""
    pin: int
    count: int
    brightness: float


@dataclass(frozen=True)
class SafetyConfig:
    """Safety system configuration."""
    emergency_stop_pin: int
    watchdog_timeout_ms: int
    startup_delay_ms: int


@dataclass(frozen=True)
class I2CConfig:
    """I2C bus and device configuration."""
    bus: int
    pca9685_address: int
    pca9685_frequency: int


def _require(data: Dict[str, Any], key: str, parent: str = "") -> Any:
    """Get a required key from a dict, raising ConfigError if missing."""
    if key not in data:
        path = f"{parent}.{key}" if parent else key
        raise ConfigError(f"Missing required config key: '{path}'", key=path)
    return data[key]


def _require_int(data: Dict[str, Any], key: str, parent: str = "") -> int:
    """Get a required integer value."""
    val = _require(data, key, parent)
    if isinstance(val, bool) or not isinstance(val, int):
        path = f"{parent}.{key}" if parent else key
        raise ConfigError(f"'{path}' must be int, got {type(val).__name__}: {val!r}", key=path)
    return val


def _require_number(data: Dict[str, Any], key: str, parent: str = "") -> float:
    """Get a required numeric value (int or float)."""
    val = _require(data, key, parent)
    if isinstance(val, bool) or not isinstance(val, (int, float)):
        path = f"{parent}.{key}" if parent else key
        raise ConfigError(f"'{path}' must be numeric, got {type(val).__name__}: {val!r}", key=path)
    return float(val)


def _require_bool(data: Dict[str, Any], key: str, parent: str = "") -> bool:
    """Get a required boolean value."""
    val = _require(data, key, parent)
    if not isinstance(val, bool):
        path = f"{parent}.{key}" if parent else key
        raise ConfigError(f"'{path}' must be bool, got {type(val).__name__}: {val!r}", key=path)
    return val


def _require_str(data: Dict[str, Any], key: str, parent: str = "") -> str:
    """Get a required non-empty string value."""
    val = _require(data, key, parent)
    if not isinstance(val, str):
        path = f"{parent}.{key}" if parent else key
        raise ConfigError(f"'{path}' must be str, got {type(val).__name__}: {val!r}", key=path)
    if not val:
        path = f"{parent}.{key}" if parent else key
        raise ConfigError(f"'{path}' must be non-empty string", key=path)
    return val


def _require_section(data: Dict[str, Any], key: str, parent: str = "") -> Dict[str, Any]:
    """Get a required dict section."""
    val = _require(data, key, parent)
    if not isinstance(val, dict):
        path = f"{parent}.{key}" if parent else key
        raise ConfigError(f"'{path}' must be a section (dict), got {type(val).__name__}", key=path)
    return val


def _validate_range(
    value: float, lo: float, hi: float, name: str,
) -> None:
    """Validate that value is within [lo, hi], raising ConfigError if not."""
    if not (lo <= value <= hi):
        raise ConfigError(
            f"'{name}' = {value} out of range [{lo}, {hi}]", key=name,
        )


class ConfigLoader:
    """Loads and validates robot_config.yaml.

    Provides typed accessors for all subsystem configurations.
    Immutable after construction — thread-safe for reads.
    """

    def __init__(self, raw: Dict[str, Any]) -> None:
        """Initialize from parsed YAML dict.

        Args:
            raw: Parsed YAML dictionary (top-level keys: head, arms, leds, etc.)

        Raises:
            ConfigError: If required keys are missing or values are invalid.
        """
        if not isinstance(raw, dict):
            raise ConfigError(f"Config must be a dict, got {type(raw).__name__}")

        self._raw = raw
        self._head_channels: Optional[HeadChannels] = None
        self._head_limits: Optional[HeadLimitsConfig] = None
        self._head_servo_flags: Optional[HeadServoFlags] = None
        self._head_animation: Optional[HeadAnimationConfig] = None
        self._arm_limits: Optional[ArmLimitsConfig] = None
        self._arm_collision: Optional[ArmCollisionZone] = None
        self._led_left: Optional[LedEyeConfig] = None
        self._led_right: Optional[LedEyeConfig] = None
        self._safety: Optional[SafetyConfig] = None
        self._i2c: Optional[I2CConfig] = None

        # Validate all sections eagerly so errors are caught at load time
        self._parse_all()

    @classmethod
    def from_file(cls, path: str) -> ConfigLoader:
        """Load config from a YAML file.

        Args:
            path: Path to robot_config.yaml (absolute or relative).

        Returns:
            Validated ConfigLoader instance.

        Raises:
            ConfigError: If file not found, not valid YAML, or validation fails.
        """
        config_path = Path(path)
        if not config_path.is_file():
            raise ConfigError(f"Config file not found: {config_path}")

        try:
            with open(config_path, "r", encoding="utf-8") as f:
                raw = yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise ConfigError(f"Invalid YAML in {config_path}: {e}") from e

        if raw is None:
            raise ConfigError(f"Config file is empty: {config_path}")

        _logger.info("Loaded config from %s", config_path)
        return cls(raw)

    def _parse_all(self) -> None:
        """Parse and validate all config sections."""
        self._parse_head()
        self._parse_arms()
        self._parse_leds()
        self._parse_i2c()
        self._parse_safety()

    # =========================================================================
    # HEAD
    # =========================================================================

    def _parse_head(self) -> None:
        """Parse head section."""
        head = _require_section(self._raw, "head")

        self._head_enabled = head.get("enabled", True)

        ch_neck = _require_int(head, "neck_pitch_channel", "head")
        ch_pitch = _require_int(head, "head_pitch_channel", "head")
        ch_yaw = _require_int(head, "head_yaw_channel", "head")
        ch_roll = _require_int(head, "head_roll_channel", "head")
        for name, val in [
            ("head.neck_pitch_channel", ch_neck),
            ("head.head_pitch_channel", ch_pitch),
            ("head.head_yaw_channel", ch_yaw),
            ("head.head_roll_channel", ch_roll),
        ]:
            _validate_range(val, 0, 15, name)

        self._head_channels = HeadChannels(
            neck_pitch=ch_neck,
            head_pitch=ch_pitch,
            head_yaw=ch_yaw,
            head_roll=ch_roll,
        )

        limits = _require_section(head, "limits", "head")
        lim_vals = {
            "neck_pitch_min": _require_number(limits, "neck_pitch_min", "head.limits"),
            "neck_pitch_max": _require_number(limits, "neck_pitch_max", "head.limits"),
            "head_pitch_min": _require_number(limits, "head_pitch_min", "head.limits"),
            "head_pitch_max": _require_number(limits, "head_pitch_max", "head.limits"),
            "head_yaw_min": _require_number(limits, "head_yaw_min", "head.limits"),
            "head_yaw_max": _require_number(limits, "head_yaw_max", "head.limits"),
            "head_roll_min": _require_number(limits, "head_roll_min", "head.limits"),
            "head_roll_max": _require_number(limits, "head_roll_max", "head.limits"),
        }
        for dof in ("neck_pitch", "head_pitch", "head_yaw", "head_roll"):
            lo, hi = lim_vals[f"{dof}_min"], lim_vals[f"{dof}_max"]
            if lo >= hi:
                raise ConfigError(
                    f"head.limits.{dof}_min ({lo}) must be < {dof}_max ({hi})",
                    key=f"head.limits.{dof}",
                )
            if not (lo <= 0.0 <= hi):
                raise ConfigError(
                    f"head.limits.{dof} range [{lo}, {hi}] must contain 0.0 "
                    f"(center position)",
                    key=f"head.limits.{dof}",
                )
        self._head_limits = HeadLimitsConfig(**lim_vals)

        servo_cfg = _require_section(head, "servo_config", "head")
        self._head_servo_flags = HeadServoFlags(
            neck_pitch_inverted=_require_bool(servo_cfg, "neck_pitch_inverted", "head.servo_config"),
            head_pitch_inverted=_require_bool(servo_cfg, "head_pitch_inverted", "head.servo_config"),
            head_yaw_inverted=_require_bool(servo_cfg, "head_yaw_inverted", "head.servo_config"),
            head_roll_inverted=_require_bool(servo_cfg, "head_roll_inverted", "head.servo_config"),
        )

        anim = _require_section(head, "animation", "head")
        self._head_animation = HeadAnimationConfig(
            default_speed_ms=_require_int(anim, "default_speed_ms", "head.animation"),
            easing=_require_str(anim, "easing", "head.animation"),
            nod_amplitude=_require_number(anim, "nod_amplitude", "head.animation"),
            shake_amplitude=_require_number(anim, "shake_amplitude", "head.animation"),
            tilt_amplitude=_require_number(anim, "tilt_amplitude", "head.animation"),
            glance_max_deviation=_require_number(anim, "glance_max_deviation", "head.animation"),
            glance_hold_ms=_require_int(anim, "glance_hold_ms", "head.animation"),
        )

    # =========================================================================
    # ARMS
    # =========================================================================

    def _parse_arms(self) -> None:
        """Parse arms section."""
        arms = _require_section(self._raw, "arms")

        self._arms_enabled = arms.get("enabled", True)

        limits = _require_section(arms, "limits", "arms")
        arm_lim_vals = {
            "shoulder_yaw_min": _require_number(limits, "shoulder_yaw_min", "arms.limits"),
            "shoulder_yaw_max": _require_number(limits, "shoulder_yaw_max", "arms.limits"),
            "shoulder_pitch_min": _require_number(limits, "shoulder_pitch_min", "arms.limits"),
            "shoulder_pitch_max": _require_number(limits, "shoulder_pitch_max", "arms.limits"),
            "elbow_min": _require_number(limits, "elbow_min", "arms.limits"),
            "elbow_max": _require_number(limits, "elbow_max", "arms.limits"),
        }
        for dof in ("shoulder_yaw", "shoulder_pitch", "elbow"):
            lo, hi = arm_lim_vals[f"{dof}_min"], arm_lim_vals[f"{dof}_max"]
            if lo >= hi:
                raise ConfigError(
                    f"arms.limits.{dof}_min ({lo}) must be < {dof}_max ({hi})",
                    key=f"arms.limits.{dof}",
                )
        self._arm_limits = ArmLimitsConfig(**arm_lim_vals)

        coll = _require_section(arms, "collision_zone", "arms")
        self._arm_collision = ArmCollisionZone(
            forward_yaw_min=_require_number(coll, "forward_yaw_min", "arms.collision_zone"),
            forward_yaw_max=_require_number(coll, "forward_yaw_max", "arms.collision_zone"),
            forward_pitch_max=_require_number(coll, "forward_pitch_max", "arms.collision_zone"),
        )

    # =========================================================================
    # LEDS
    # =========================================================================

    def _parse_leds(self) -> None:
        """Parse leds section."""
        leds = _require_section(self._raw, "leds")

        self._leds_enabled = leds.get("enabled", True)

        left = _require_section(leds, "left_eye", "leds")
        left_pin = _require_int(left, "pin", "leds.left_eye")
        left_count = _require_int(left, "count", "leds.left_eye")
        left_brightness = _require_number(left, "brightness", "leds.left_eye")
        _validate_range(left_pin, 2, 27, "leds.left_eye.pin")
        _validate_range(left_count, 1, 1000, "leds.left_eye.count")
        _validate_range(left_brightness, 0.0, 1.0, "leds.left_eye.brightness")
        self._led_left = LedEyeConfig(
            pin=left_pin,
            count=left_count,
            brightness=left_brightness,
        )

        right = _require_section(leds, "right_eye", "leds")
        right_pin = _require_int(right, "pin", "leds.right_eye")
        right_count = _require_int(right, "count", "leds.right_eye")
        right_brightness = _require_number(right, "brightness", "leds.right_eye")
        _validate_range(right_pin, 2, 27, "leds.right_eye.pin")
        _validate_range(right_count, 1, 1000, "leds.right_eye.count")
        _validate_range(right_brightness, 0.0, 1.0, "leds.right_eye.brightness")
        self._led_right = LedEyeConfig(
            pin=right_pin,
            count=right_count,
            brightness=right_brightness,
        )

    # =========================================================================
    # I2C
    # =========================================================================

    def _parse_i2c(self) -> None:
        """Parse i2c section."""
        i2c = _require_section(self._raw, "i2c")

        pca = _require_section(i2c, "pca9685", "i2c")

        address_raw = _require(pca, "address", "i2c.pca9685")
        if isinstance(address_raw, int):
            address = address_raw
        elif isinstance(address_raw, str):
            try:
                address = int(address_raw, 0)
            except ValueError:
                raise ConfigError(
                    f"'i2c.pca9685.address' invalid hex: {address_raw!r}",
                    key="i2c.pca9685.address",
                )
        else:
            raise ConfigError(
                f"'i2c.pca9685.address' must be int or hex string, got {type(address_raw).__name__}",
                key="i2c.pca9685.address",
            )

        _validate_range(address, 0x00, 0x7F, "i2c.pca9685.address")
        freq = _require_int(pca, "frequency", "i2c.pca9685")
        _validate_range(freq, 24, 1526, "i2c.pca9685.frequency")

        self._i2c = I2CConfig(
            bus=_require_int(i2c, "bus", "i2c"),
            pca9685_address=address,
            pca9685_frequency=freq,
        )

    # =========================================================================
    # SAFETY
    # =========================================================================

    def _parse_safety(self) -> None:
        """Parse safety section."""
        safety = _require_section(self._raw, "safety")
        estop_pin = _require_int(safety, "emergency_stop_pin", "safety")
        _validate_range(estop_pin, 0, 27, "safety.emergency_stop_pin")
        watchdog_ms = _require_int(safety, "watchdog_timeout_ms", "safety")
        _validate_range(watchdog_ms, 1, 60000, "safety.watchdog_timeout_ms")
        startup_ms = _require_int(safety, "startup_delay_ms", "safety")
        _validate_range(startup_ms, 0, 30000, "safety.startup_delay_ms")
        self._safety = SafetyConfig(
            emergency_stop_pin=estop_pin,
            watchdog_timeout_ms=watchdog_ms,
            startup_delay_ms=startup_ms,
        )

    # =========================================================================
    # PUBLIC ACCESSORS
    # =========================================================================

    @property
    def head_enabled(self) -> bool:
        return self._head_enabled

    @property
    def head_channels(self) -> HeadChannels:
        assert self._head_channels is not None
        return self._head_channels

    @property
    def head_limits(self) -> HeadLimitsConfig:
        assert self._head_limits is not None
        return self._head_limits

    @property
    def head_servo_flags(self) -> HeadServoFlags:
        assert self._head_servo_flags is not None
        return self._head_servo_flags

    @property
    def head_animation(self) -> HeadAnimationConfig:
        assert self._head_animation is not None
        return self._head_animation

    @property
    def arms_enabled(self) -> bool:
        return self._arms_enabled

    @property
    def arm_limits(self) -> ArmLimitsConfig:
        assert self._arm_limits is not None
        return self._arm_limits

    @property
    def arm_collision_zone(self) -> ArmCollisionZone:
        assert self._arm_collision is not None
        return self._arm_collision

    @property
    def leds_enabled(self) -> bool:
        return self._leds_enabled

    @property
    def led_left(self) -> LedEyeConfig:
        assert self._led_left is not None
        return self._led_left

    @property
    def led_right(self) -> LedEyeConfig:
        assert self._led_right is not None
        return self._led_right

    @property
    def safety(self) -> SafetyConfig:
        assert self._safety is not None
        return self._safety

    @property
    def i2c(self) -> I2CConfig:
        assert self._i2c is not None
        return self._i2c

    # =========================================================================
    # FACTORY METHODS — produce subsystem config objects
    # =========================================================================

    def make_head_config(self) -> Dict[str, Any]:
        """Produce kwargs dict suitable for HeadConfig dataclass.

        Includes limits (from make_head_limits) so callers don't need
        to manually inject them.

        Returns:
            Dict with keys matching HeadConfig constructor parameters,
            including 'limits' as a HeadLimits instance.

        Example:
            >>> from src.control.head_controller import HeadConfig
            >>> head_config = HeadConfig(**config.make_head_config())
        """
        from src.control.head_controller import HeadLimits

        ch = self.head_channels
        flags = self.head_servo_flags
        anim = self.head_animation

        return {
            "neck_pitch_channel": ch.neck_pitch,
            "head_pitch_channel": ch.head_pitch,
            "head_yaw_channel": ch.head_yaw,
            "head_roll_channel": ch.head_roll,
            "neck_pitch_inverted": flags.neck_pitch_inverted,
            "head_pitch_inverted": flags.head_pitch_inverted,
            "head_yaw_inverted": flags.head_yaw_inverted,
            "head_roll_inverted": flags.head_roll_inverted,
            "default_speed_ms": anim.default_speed_ms,
            "easing": anim.easing,
            "limits": HeadLimits(**self.make_head_limits()),
        }

    def make_head_limits(self) -> Dict[str, float]:
        """Produce kwargs dict suitable for HeadLimits dataclass.

        Returns:
            Dict with keys matching HeadLimits constructor parameters.

        Example:
            >>> from src.control.head_controller import HeadLimits
            >>> limits = HeadLimits(**config.make_head_limits())
        """
        lim = self.head_limits
        return {
            "neck_pitch_min": lim.neck_pitch_min,
            "neck_pitch_max": lim.neck_pitch_max,
            "head_pitch_min": lim.head_pitch_min,
            "head_pitch_max": lim.head_pitch_max,
            "head_yaw_min": lim.head_yaw_min,
            "head_yaw_max": lim.head_yaw_max,
            "head_roll_min": lim.head_roll_min,
            "head_roll_max": lim.head_roll_max,
        }

    @property
    def pca9685_address(self) -> int:
        return self.i2c.pca9685_address

    @property
    def pca9685_frequency(self) -> int:
        return self.i2c.pca9685_frequency

    @property
    def safety_pin(self) -> int:
        return self.safety.emergency_stop_pin

    @property
    def watchdog_timeout_ms(self) -> int:
        return self.safety.watchdog_timeout_ms

    @property
    def bus_servo_ids(self) -> list:
        """Get list of STS3215 servo IDs from config.

        Returns empty list if arm servo IDs are not yet assigned (TBD).
        """
        ids = []
        arms = self._raw.get("arms", {})
        for arm_key in ("left_arm", "right_arm"):
            arm = arms.get(arm_key, {})
            for id_key in ("shoulder_yaw_id", "shoulder_pitch_id", "elbow_id"):
                val = arm.get(id_key)
                if isinstance(val, bool):
                    _logger.warning(
                        "Servo ID arms.%s.%s is bool, skipping", arm_key, id_key,
                    )
                elif isinstance(val, int):
                    ids.append(val)
                elif val is not None and val != "TBD":
                    _logger.warning(
                        "Servo ID arms.%s.%s = %r is not int, skipping",
                        arm_key, id_key, val,
                    )
        return ids

    def __repr__(self) -> str:
        return (
            f"ConfigLoader(head={'ON' if self.head_enabled else 'OFF'}, "
            f"arms={'ON' if self.arms_enabled else 'OFF'}, "
            f"leds={'ON' if self.leds_enabled else 'OFF'}, "
            f"pca9685=0x{self.pca9685_address:02X})"
        )
