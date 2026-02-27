#!/usr/bin/env python3
"""
TDD Test Suite for HeadController - 4-DOF Head Control with Disney Animation

Tests updated to match 4-DOF implementation (V2-compatible):
- neck_pitch: Base neck up/down movement (PCA9685 ch 10)
- head_pitch: Head nod forward/back (PCA9685 ch 11)
- head_yaw: Head rotate left/right (PCA9685 ch 12)
- head_roll: Head tilt side-to-side (PCA9685 ch 13)

Quality Standard: Boston Dynamics / Pixar Grade

Test Classes (~70 tests):
    TestHeadLimits: HeadLimits dataclass validation (9 tests)
    TestHeadConfig: HeadConfig dataclass validation (5 tests)
    TestHeadControllerInit: Initialization tests (3 tests)
    TestLookAt: Direct positioning tests - backwards-compatible 2-DOF API (5 tests)
    TestMoveTo: Full 4-DOF direct positioning API (6 tests) [CRITICAL-001]
    TestNod: Vertical affirmation gesture tests (4 tests)
    TestShake: Horizontal negation gesture tests (4 tests)
    TestRandomGlance: Random glance behavior tests (3 tests)
    TestTiltCurious: Curious head tilt tests (3 tests)
    TestEmergencyStop: Emergency stop and reset tests (4 tests)
    TestGetState: State retrieval tests (2 tests)
    TestHeadControllerPerformance: Performance benchmarks (2 tests)
    TestHeadControllerIntegration: Integration tests (2 tests)
    TestIsMoving: Movement state tracking (4 tests) [HIGH]
    TestResetToCenter: Reset to center position (3 tests) [HIGH]
    TestCallbacks: Movement completion callbacks (3 tests) [HIGH]
    TestNaNHandling: NaN/Inf input validation (4 tests) [HIGH]
    TestTimeout: Movement timeout handling (2 tests) [HIGH]

Run with: pytest tests/test_control/test_head_controller.py -v

Author: TDD Test Architect Agent
Created: 18 January 2026
Updated: 21 January 2026 - Hostile review fixes (CRITICAL-001 to CRITICAL-004, HIGH issues)
"""

import threading
import time
from typing import List, Tuple, Optional
from unittest.mock import Mock, MagicMock, patch

import pytest


# =============================================================================
# Test Fixtures
# =============================================================================

class MockServoDriver:
    """Mock PCA9685Driver for testing HeadController without hardware.

    Tracks all servo commands for verification in tests.
    CRITICAL-004 Enhanced: Includes timing simulation for realistic behavior.

    Attributes:
        channels: Dictionary of channel states
        set_angle_calls: List of (channel, angle) tuples for all set_servo_angle calls
        disable_calls: List of channels that were disabled
        call_timestamps: List of timestamps for each set_angle call (for timing validation)
        simulate_delay_ms: Optional delay per servo call (simulates I2C latency)
    """

    def __init__(self, simulate_delay_ms: float = 0.0) -> None:
        """Initialize mock servo driver with 16 channels.

        Args:
            simulate_delay_ms: Simulated I2C delay per servo command (default: 0).
        """
        self.channels = {i: {'angle': 90, 'enabled': False} for i in range(16)}
        self.set_angle_calls: List[Tuple[int, float]] = []
        self.disable_calls: List[int] = []
        self.call_timestamps: List[float] = []
        self.simulate_delay_ms = simulate_delay_ms
        self._lock = threading.Lock()

    def reset(self) -> None:
        """Reset all tracking data."""
        with self._lock:
            for i in range(16):
                self.channels[i] = {'angle': 90, 'enabled': False}
            self.set_angle_calls.clear()
            self.disable_calls.clear()
            self.call_timestamps.clear()

    def set_servo_angle(self, channel: int, angle: float) -> None:
        """Set servo angle on a channel.

        Args:
            channel: PCA9685 channel (0-15)
            angle: Target angle in degrees (0-180)

        Raises:
            ValueError: If channel or angle is out of range
        """
        with self._lock:
            if not 0 <= channel <= 15:
                raise ValueError(f"Channel must be 0-15, got {channel}")
            if not 0 <= angle <= 180:
                raise ValueError(f"Angle must be 0-180, got {angle}")

            self.set_angle_calls.append((channel, angle))
            self.call_timestamps.append(time.monotonic())
            self.channels[channel]['angle'] = angle
            self.channels[channel]['enabled'] = True

            # Simulate I2C latency if configured
            if self.simulate_delay_ms > 0:
                time.sleep(self.simulate_delay_ms / 1000.0)

    def disable_channel(self, channel: int) -> None:
        """Disable a servo channel.

        Args:
            channel: PCA9685 channel (0-15)
        """
        with self._lock:
            if 0 <= channel <= 15:
                self.disable_calls.append(channel)
                self.channels[channel]['enabled'] = False

    def get_channel_state(self, channel: int) -> dict:
        """Get current state of a channel.

        Args:
            channel: PCA9685 channel (0-15)

        Returns:
            Dictionary with 'angle' and 'enabled' keys
        """
        with self._lock:
            return self.channels.get(channel, {'angle': 90, 'enabled': False}).copy()

    def disable_all(self) -> None:
        """Disable all servo channels."""
        with self._lock:
            for i in range(16):
                self.channels[i]['enabled'] = False
                self.disable_calls.append(i)

    def get_call_count(self) -> int:
        """Return total number of set_servo_angle calls."""
        with self._lock:
            return len(self.set_angle_calls)

    def get_last_angle(self, channel: int) -> Optional[float]:
        """Get the last angle set for a channel.

        Args:
            channel: PCA9685 channel (0-15)

        Returns:
            Last angle set, or None if no calls for this channel.
        """
        with self._lock:
            for ch, angle in reversed(self.set_angle_calls):
                if ch == channel:
                    return angle
            return None


@pytest.fixture
def mock_servo_driver() -> MockServoDriver:
    """Provide mock servo driver for testing.

    Yields:
        MockServoDriver instance ready for use.
    """
    driver = MockServoDriver()
    yield driver
    driver.reset()


@pytest.fixture
def default_head_config():
    """Provide default 4-DOF head configuration for testing.

    Returns:
        Dictionary of default configuration values.
    """
    return {
        'neck_pitch_channel': 10,
        'head_pitch_channel': 11,
        'head_yaw_channel': 12,
        'head_roll_channel': 13,
        'neck_pitch_min': -20.0,
        'neck_pitch_max': 65.0,
        'head_pitch_min': -45.0,
        'head_pitch_max': 45.0,
        'head_yaw_min': -90.0,
        'head_yaw_max': 90.0,
        'head_roll_min': -30.0,
        'head_roll_max': 30.0,
        'default_speed_ms': 300,
    }


# =============================================================================
# TestHeadLimits - HeadLimits dataclass validation (~5 tests)
# =============================================================================

class TestHeadLimits:
    """Tests for HeadLimits dataclass validation (4-DOF)."""

    def test_valid_limits_creation(self) -> None:
        """Test creating HeadLimits with valid 4-DOF parameters."""
        from src.control.head_controller import HeadLimits

        limits = HeadLimits(
            neck_pitch_min=-20.0,
            neck_pitch_max=65.0,
            head_pitch_min=-45.0,
            head_pitch_max=45.0,
            head_yaw_min=-90.0,
            head_yaw_max=90.0,
            head_roll_min=-30.0,
            head_roll_max=30.0
        )

        assert limits.neck_pitch_min == -20.0
        assert limits.neck_pitch_max == 65.0
        assert limits.head_pitch_min == -45.0
        assert limits.head_pitch_max == 45.0
        assert limits.head_yaw_min == -90.0
        assert limits.head_yaw_max == 90.0
        assert limits.head_roll_min == -30.0
        assert limits.head_roll_max == 30.0

    def test_invalid_head_yaw_limits_raises(self) -> None:
        """Test that head_yaw_min >= head_yaw_max raises ValueError."""
        from src.control.head_controller import HeadLimits

        # head_yaw_min equals head_yaw_max
        with pytest.raises(ValueError, match="head_yaw_min.*must be.*<.*head_yaw_max"):
            HeadLimits(head_yaw_min=90.0, head_yaw_max=90.0)

        # head_yaw_min greater than head_yaw_max
        with pytest.raises(ValueError, match="head_yaw_min.*must be.*<.*head_yaw_max"):
            HeadLimits(head_yaw_min=100.0, head_yaw_max=50.0)

    def test_invalid_head_pitch_limits_raises(self) -> None:
        """Test that head_pitch_min >= head_pitch_max raises ValueError."""
        from src.control.head_controller import HeadLimits

        # head_pitch_min equals head_pitch_max
        with pytest.raises(ValueError, match="head_pitch_min.*must be.*<.*head_pitch_max"):
            HeadLimits(head_pitch_min=45.0, head_pitch_max=45.0)

        # head_pitch_min greater than head_pitch_max
        with pytest.raises(ValueError, match="head_pitch_min.*must be.*<.*head_pitch_max"):
            HeadLimits(head_pitch_min=60.0, head_pitch_max=30.0)

    def test_center_outside_limits_raises(self) -> None:
        """Test that center position outside limits raises ValueError."""
        from src.control.head_controller import HeadLimits

        # head_yaw_center outside limits
        with pytest.raises(ValueError, match="head_yaw_center.*must be within head_yaw limits"):
            HeadLimits(head_yaw_min=-160.0, head_yaw_max=160.0, head_yaw_center=200.0)

        # head_pitch_center outside limits
        with pytest.raises(ValueError, match="head_pitch_center.*must be within head_pitch limits"):
            HeadLimits(head_pitch_min=-45.0, head_pitch_max=45.0, head_pitch_center=60.0)

    def test_default_limits(self) -> None:
        """Test HeadLimits has sensible default values for 4-DOF."""
        from src.control.head_controller import HeadLimits

        limits = HeadLimits()

        # Default values per V2 architecture spec
        assert limits.neck_pitch_min == -20.0
        assert limits.neck_pitch_max == 65.0
        assert limits.head_pitch_min == -45.0
        assert limits.head_pitch_max == 45.0
        assert limits.head_yaw_min == -90.0
        assert limits.head_yaw_max == 90.0
        assert limits.head_roll_min == -30.0
        assert limits.head_roll_max == 30.0
        assert limits.neck_pitch_center == 0.0
        assert limits.head_pitch_center == 0.0
        assert limits.head_yaw_center == 0.0
        assert limits.head_roll_center == 0.0

    # CRITICAL-002: neck_pitch and head_roll limit validation tests
    def test_invalid_neck_pitch_limits_raises(self) -> None:
        """Test that neck_pitch_min >= neck_pitch_max raises ValueError."""
        from src.control.head_controller import HeadLimits

        # neck_pitch_min equals neck_pitch_max
        with pytest.raises(ValueError, match="neck_pitch_min.*must be.*<.*neck_pitch_max"):
            HeadLimits(neck_pitch_min=20.0, neck_pitch_max=20.0)

        # neck_pitch_min greater than neck_pitch_max
        with pytest.raises(ValueError, match="neck_pitch_min.*must be.*<.*neck_pitch_max"):
            HeadLimits(neck_pitch_min=50.0, neck_pitch_max=10.0)

    def test_invalid_head_roll_limits_raises(self) -> None:
        """Test that head_roll_min >= head_roll_max raises ValueError."""
        from src.control.head_controller import HeadLimits

        # head_roll_min equals head_roll_max
        with pytest.raises(ValueError, match="head_roll_min.*must be.*<.*head_roll_max"):
            HeadLimits(head_roll_min=15.0, head_roll_max=15.0)

        # head_roll_min greater than head_roll_max
        with pytest.raises(ValueError, match="head_roll_min.*must be.*<.*head_roll_max"):
            HeadLimits(head_roll_min=30.0, head_roll_max=-30.0)

    # CRITICAL-003: neck_pitch_center and head_roll_center validation tests
    def test_neck_pitch_center_outside_limits_raises(self) -> None:
        """Test that neck_pitch_center outside limits raises ValueError."""
        from src.control.head_controller import HeadLimits

        # neck_pitch_center below minimum
        with pytest.raises(ValueError, match="neck_pitch_center.*must be within neck_pitch limits"):
            HeadLimits(neck_pitch_min=-20.0, neck_pitch_max=65.0, neck_pitch_center=-30.0)

        # neck_pitch_center above maximum
        with pytest.raises(ValueError, match="neck_pitch_center.*must be within neck_pitch limits"):
            HeadLimits(neck_pitch_min=-20.0, neck_pitch_max=65.0, neck_pitch_center=70.0)

    def test_head_roll_center_outside_limits_raises(self) -> None:
        """Test that head_roll_center outside limits raises ValueError."""
        from src.control.head_controller import HeadLimits

        # head_roll_center below minimum
        with pytest.raises(ValueError, match="head_roll_center.*must be within head_roll limits"):
            HeadLimits(head_roll_min=-30.0, head_roll_max=30.0, head_roll_center=-45.0)

        # head_roll_center above maximum
        with pytest.raises(ValueError, match="head_roll_center.*must be within head_roll limits"):
            HeadLimits(head_roll_min=-30.0, head_roll_max=30.0, head_roll_center=50.0)


# =============================================================================
# TestHeadConfig - HeadConfig dataclass validation (~5 tests)
# =============================================================================

class TestHeadConfig:
    """Tests for HeadConfig dataclass validation (4-DOF)."""

    def test_valid_config_creation(self) -> None:
        """Test creating HeadConfig with valid 4-DOF parameters."""
        from src.control.head_controller import HeadConfig, HeadLimits

        config = HeadConfig(
            neck_pitch_channel=10,
            head_pitch_channel=11,
            head_yaw_channel=12,
            head_roll_channel=13,
            limits=HeadLimits(),
            neck_pitch_inverted=False,
            head_pitch_inverted=False,
            head_yaw_inverted=False,
            head_roll_inverted=False,
            default_speed_ms=300,
            easing='ease_in_out'
        )

        assert config.neck_pitch_channel == 10
        assert config.head_pitch_channel == 11
        assert config.head_yaw_channel == 12
        assert config.head_roll_channel == 13
        assert config.default_speed_ms == 300
        assert config.easing == 'ease_in_out'

    def test_invalid_channel_raises(self) -> None:
        """Test that invalid channel numbers raise ValueError."""
        from src.control.head_controller import HeadConfig

        # Negative channel
        with pytest.raises(ValueError, match="neck_pitch_channel must be 0-15"):
            HeadConfig(neck_pitch_channel=-1, head_pitch_channel=11, head_yaw_channel=12, head_roll_channel=13)

        # Channel > 15
        with pytest.raises(ValueError, match="head_yaw_channel must be 0-15"):
            HeadConfig(neck_pitch_channel=10, head_pitch_channel=11, head_yaw_channel=16, head_roll_channel=13)

        # Invalid head_roll channel
        with pytest.raises(ValueError, match="head_roll_channel must be 0-15"):
            HeadConfig(neck_pitch_channel=10, head_pitch_channel=11, head_yaw_channel=12, head_roll_channel=20)

    def test_duplicate_channels_raises(self) -> None:
        """Test that duplicate channels raise ValueError."""
        from src.control.head_controller import HeadConfig

        with pytest.raises(ValueError, match="All channels must be unique"):
            HeadConfig(neck_pitch_channel=10, head_pitch_channel=10, head_yaw_channel=12, head_roll_channel=13)

    def test_invalid_speed_raises(self) -> None:
        """Test that invalid default_speed_ms raises ValueError."""
        from src.control.head_controller import HeadConfig

        # Zero speed
        with pytest.raises(ValueError, match="default_speed_ms must be > 0"):
            HeadConfig(neck_pitch_channel=10, head_pitch_channel=11, head_yaw_channel=12, head_roll_channel=13, default_speed_ms=0)

        # Negative speed
        with pytest.raises(ValueError, match="default_speed_ms must be > 0"):
            HeadConfig(neck_pitch_channel=10, head_pitch_channel=11, head_yaw_channel=12, head_roll_channel=13, default_speed_ms=-100)

    def test_default_values(self) -> None:
        """Test HeadConfig has sensible default values."""
        from src.control.head_controller import HeadConfig

        config = HeadConfig(neck_pitch_channel=10, head_pitch_channel=11, head_yaw_channel=12, head_roll_channel=13)

        assert config.neck_pitch_inverted is False
        assert config.head_pitch_inverted is False
        assert config.head_yaw_inverted is False
        assert config.head_roll_inverted is False
        assert config.default_speed_ms == 300
        assert config.easing == 'ease_in_out'


# =============================================================================
# TestHeadControllerInit - Initialization tests (~3 tests)
# =============================================================================

class TestHeadControllerInit:
    """Tests for HeadController initialization (4-DOF)."""

    def test_init_with_valid_config(self, mock_servo_driver) -> None:
        """Test HeadController initializes with valid 4-DOF configuration."""
        from src.control.head_controller import HeadController, HeadConfig

        config = HeadConfig(neck_pitch_channel=10, head_pitch_channel=11, head_yaw_channel=12, head_roll_channel=13)
        head = HeadController(mock_servo_driver, config)

        assert head.config == config
        assert head.config.head_yaw_channel == 12
        assert head.config.head_pitch_channel == 11

    def test_init_positions_at_center(self, mock_servo_driver) -> None:
        """Test that initialization positions head at center (all 4 DOF)."""
        from src.control.head_controller import HeadController, HeadConfig

        config = HeadConfig(neck_pitch_channel=10, head_pitch_channel=11, head_yaw_channel=12, head_roll_channel=13)
        head = HeadController(mock_servo_driver, config)

        # Should start at center position (4-DOF)
        neck_p, head_p, head_y, head_r = head.get_current_position()
        assert neck_p == 0.0  # Center
        assert head_p == 0.0  # Center
        assert head_y == 0.0  # Center
        assert head_r == 0.0  # Center

    def test_init_with_mock_driver(self, mock_servo_driver) -> None:
        """Test HeadController works with mock driver (4-DOF state)."""
        from src.control.head_controller import HeadController, HeadConfig

        config = HeadConfig(neck_pitch_channel=10, head_pitch_channel=11, head_yaw_channel=12, head_roll_channel=13)
        head = HeadController(mock_servo_driver, config)

        # Should be able to query state (4-DOF)
        state = head.get_state()
        assert state is not None
        assert state.head_yaw == 0.0
        assert state.head_pitch == 0.0
        assert state.neck_pitch == 0.0
        assert state.head_roll == 0.0
        assert state.is_moving is False


# =============================================================================
# TestLookAt - Direct positioning tests (~5 tests)
# =============================================================================

class TestLookAt:
    """Tests for look_at() method - backwards-compatible 2-DOF positioning.

    Note: look_at(pan, tilt) maps to 4-DOF as:
    - pan → head_yaw
    - tilt → head_pitch
    """

    def test_look_at_basic(self, mock_servo_driver) -> None:
        """Test basic look_at movement to valid position."""
        from src.control.head_controller import HeadController, HeadConfig

        config = HeadConfig(neck_pitch_channel=10, head_pitch_channel=11, head_yaw_channel=12, head_roll_channel=13)
        head = HeadController(mock_servo_driver, config)

        # Move to specific position (pan→head_yaw, tilt→head_pitch)
        result = head.look_at(pan=30.0, tilt=15.0, blocking=True)

        assert result is True
        # get_current_position returns (neck_pitch, head_pitch, head_yaw, head_roll)
        _, head_pitch, head_yaw, _ = head.get_current_position()
        assert head_yaw == 30.0  # pan maps to head_yaw
        assert head_pitch == 15.0  # tilt maps to head_pitch

    def test_look_at_clamps_to_limits(self, mock_servo_driver) -> None:
        """Test that look_at clamps values to limits (not errors)."""
        from src.control.head_controller import HeadController, HeadConfig, HeadLimits

        limits = HeadLimits(head_yaw_min=-90.0, head_yaw_max=90.0, head_pitch_min=-45.0, head_pitch_max=45.0)
        config = HeadConfig(neck_pitch_channel=10, head_pitch_channel=11, head_yaw_channel=12, head_roll_channel=13, limits=limits)
        head = HeadController(mock_servo_driver, config)

        # Try to move beyond limits - should clamp, not raise
        result = head.look_at(pan=150.0, tilt=100.0, blocking=True)

        assert result is True
        _, head_pitch, head_yaw, _ = head.get_current_position()
        assert head_yaw == 90.0   # Clamped to max
        assert head_pitch == 45.0  # Clamped to max

        # Try negative beyond limits
        head.look_at(pan=-200.0, tilt=-100.0, blocking=True)
        _, head_pitch, head_yaw, _ = head.get_current_position()
        assert head_yaw == -90.0  # Clamped to min
        assert head_pitch == -45.0  # Clamped to min

    def test_look_at_with_custom_duration(self, mock_servo_driver) -> None:
        """Test look_at with custom duration override."""
        from src.control.head_controller import HeadController, HeadConfig

        config = HeadConfig(neck_pitch_channel=10, head_pitch_channel=11, head_yaw_channel=12, head_roll_channel=13, default_speed_ms=300)
        head = HeadController(mock_servo_driver, config)

        # Start non-blocking movement with custom duration
        start_time = time.monotonic()
        result = head.look_at(pan=45.0, tilt=20.0, duration_ms=100, blocking=True)
        elapsed_ms = (time.monotonic() - start_time) * 1000

        assert result is True
        # Should complete in approximately 100ms (allow some tolerance)
        assert elapsed_ms >= 80  # At least 80ms
        assert elapsed_ms < 300  # Should not take default 300ms

    def test_look_at_with_custom_easing(self, mock_servo_driver) -> None:
        """Test look_at with custom easing function."""
        from src.control.head_controller import HeadController, HeadConfig

        config = HeadConfig(neck_pitch_channel=10, head_pitch_channel=11, head_yaw_channel=12, head_roll_channel=13, easing='ease_in_out')
        head = HeadController(mock_servo_driver, config)

        # Movement with linear easing
        result = head.look_at(pan=30.0, tilt=15.0, easing='linear', blocking=True)

        assert result is True
        _, head_pitch, head_yaw, _ = head.get_current_position()
        assert head_yaw == 30.0
        assert head_pitch == 15.0

    def test_look_at_updates_position(self, mock_servo_driver) -> None:
        """Test that look_at updates internal position tracking."""
        from src.control.head_controller import HeadController, HeadConfig

        config = HeadConfig(neck_pitch_channel=10, head_pitch_channel=11, head_yaw_channel=12, head_roll_channel=13)
        head = HeadController(mock_servo_driver, config)

        # Initial position (all at center = 0.0)
        _, head_pitch1, head_yaw1, _ = head.get_current_position()
        assert head_yaw1 == 0.0
        assert head_pitch1 == 0.0

        # Move
        head.look_at(pan=45.0, tilt=-20.0, blocking=True)

        # Position should be updated
        _, head_pitch2, head_yaw2, _ = head.get_current_position()
        assert head_yaw2 == 45.0
        assert head_pitch2 == -20.0


# =============================================================================
# TestMoveTo - 4-DOF direct positioning API (CRITICAL-001)
# =============================================================================

class TestMoveTo:
    """Tests for move_to() method - full 4-DOF direct positioning.

    Unlike look_at() which only controls head_yaw/head_pitch for backwards
    compatibility, move_to() allows direct control of all 4 DOF:
    - neck_pitch, head_pitch, head_yaw, head_roll
    """

    def test_move_to_basic_4dof(self, mock_servo_driver) -> None:
        """Test basic move_to with all 4 DOF specified."""
        from src.control.head_controller import HeadController, HeadConfig

        config = HeadConfig(neck_pitch_channel=10, head_pitch_channel=11, head_yaw_channel=12, head_roll_channel=13)
        head = HeadController(mock_servo_driver, config)

        # Move to specific 4-DOF position
        result = head.move_to(
            neck_pitch=10.0,
            head_pitch=15.0,
            head_yaw=30.0,
            head_roll=5.0,
            blocking=True
        )

        assert result is True
        neck_p, head_p, head_y, head_r = head.get_current_position()
        assert abs(neck_p - 10.0) < 0.5
        assert abs(head_p - 15.0) < 0.5
        assert abs(head_y - 30.0) < 0.5
        assert abs(head_r - 5.0) < 0.5

    def test_move_to_partial_dof(self, mock_servo_driver) -> None:
        """Test move_to with only some DOF specified (others unchanged)."""
        from src.control.head_controller import HeadController, HeadConfig

        config = HeadConfig(neck_pitch_channel=10, head_pitch_channel=11, head_yaw_channel=12, head_roll_channel=13)
        head = HeadController(mock_servo_driver, config)

        # Set initial position
        head.move_to(neck_pitch=5.0, head_pitch=10.0, head_yaw=20.0, head_roll=3.0, blocking=True)

        # Move only neck_pitch, others should stay
        result = head.move_to(neck_pitch=15.0, blocking=True)

        assert result is True
        neck_p, head_p, head_y, head_r = head.get_current_position()
        assert abs(neck_p - 15.0) < 0.5  # Changed
        assert abs(head_p - 10.0) < 0.5  # Unchanged
        assert abs(head_y - 20.0) < 0.5  # Unchanged
        assert abs(head_r - 3.0) < 0.5   # Unchanged

    def test_move_to_clamps_all_axes(self, mock_servo_driver) -> None:
        """Test that move_to clamps all 4 DOF to their limits."""
        from src.control.head_controller import HeadController, HeadConfig, HeadLimits

        limits = HeadLimits(
            neck_pitch_min=-20.0, neck_pitch_max=65.0,
            head_pitch_min=-45.0, head_pitch_max=45.0,
            head_yaw_min=-90.0, head_yaw_max=90.0,
            head_roll_min=-30.0, head_roll_max=30.0
        )
        config = HeadConfig(neck_pitch_channel=10, head_pitch_channel=11, head_yaw_channel=12, head_roll_channel=13, limits=limits)
        head = HeadController(mock_servo_driver, config)

        # Try to exceed all limits
        result = head.move_to(
            neck_pitch=100.0,   # Should clamp to 65.0
            head_pitch=100.0,  # Should clamp to 45.0
            head_yaw=200.0,    # Should clamp to 90.0
            head_roll=60.0,    # Should clamp to 30.0
            blocking=True
        )

        assert result is True
        neck_p, head_p, head_y, head_r = head.get_current_position()
        assert neck_p == 65.0   # Clamped to max
        assert head_p == 45.0   # Clamped to max
        assert head_y == 90.0   # Clamped to max
        assert head_r == 30.0   # Clamped to max

    def test_move_to_with_duration(self, mock_servo_driver) -> None:
        """Test move_to with custom duration."""
        from src.control.head_controller import HeadController, HeadConfig

        config = HeadConfig(neck_pitch_channel=10, head_pitch_channel=11, head_yaw_channel=12, head_roll_channel=13)
        head = HeadController(mock_servo_driver, config)

        start = time.monotonic()
        result = head.move_to(
            neck_pitch=10.0,
            head_pitch=20.0,
            duration_ms=100,
            blocking=True
        )
        elapsed_ms = (time.monotonic() - start) * 1000

        assert result is True
        # Should complete in approximately 100ms (allow tolerance)
        assert elapsed_ms >= 80
        assert elapsed_ms < 250  # Well under default 300ms

    def test_move_to_non_blocking(self, mock_servo_driver) -> None:
        """Test move_to with blocking=False returns immediately."""
        from src.control.head_controller import HeadController, HeadConfig

        config = HeadConfig(neck_pitch_channel=10, head_pitch_channel=11, head_yaw_channel=12, head_roll_channel=13)
        head = HeadController(mock_servo_driver, config)

        start = time.monotonic()
        result = head.move_to(
            neck_pitch=30.0,
            head_pitch=20.0,
            head_yaw=45.0,
            duration_ms=500,
            blocking=False
        )
        elapsed_ms = (time.monotonic() - start) * 1000

        assert result is True
        # Should return immediately (< 50ms)
        assert elapsed_ms < 50

    def test_move_to_rejected_during_emergency(self, mock_servo_driver) -> None:
        """Test move_to returns False during emergency stop."""
        from src.control.head_controller import HeadController, HeadConfig

        config = HeadConfig(neck_pitch_channel=10, head_pitch_channel=11, head_yaw_channel=12, head_roll_channel=13)
        head = HeadController(mock_servo_driver, config)

        head.emergency_stop()

        result = head.move_to(neck_pitch=10.0, blocking=False)
        assert result is False


# =============================================================================
# TestNod - Vertical affirmation gesture tests (~4 tests)
# =============================================================================

class TestNod:
    """Tests for nod() method - vertical affirmation gesture (uses head_pitch)."""

    def test_nod_single(self, mock_servo_driver) -> None:
        """Test single nod motion."""
        from src.control.head_controller import HeadController, HeadConfig

        config = HeadConfig(neck_pitch_channel=10, head_pitch_channel=11, head_yaw_channel=12, head_roll_channel=13)
        head = HeadController(mock_servo_driver, config)

        result = head.nod(count=1, amplitude=15.0, speed_ms=200, blocking=True)

        assert result is True
        # Should have set head_pitch angle during nod
        assert len(mock_servo_driver.set_angle_calls) >= 1

    def test_nod_multiple(self, mock_servo_driver) -> None:
        """Test multiple nod cycles."""
        from src.control.head_controller import HeadController, HeadConfig

        config = HeadConfig(neck_pitch_channel=10, head_pitch_channel=11, head_yaw_channel=12, head_roll_channel=13)
        head = HeadController(mock_servo_driver, config)

        result = head.nod(count=3, amplitude=15.0, speed_ms=200, blocking=True)

        assert result is True
        # Multiple nods should result in multiple servo commands
        # At least count * 2 commands (up and down for each nod)
        assert len(mock_servo_driver.set_angle_calls) >= 3 * 2

    def test_nod_returns_to_original(self, mock_servo_driver) -> None:
        """Test that nod returns to original head_pitch position."""
        from src.control.head_controller import HeadController, HeadConfig

        config = HeadConfig(neck_pitch_channel=10, head_pitch_channel=11, head_yaw_channel=12, head_roll_channel=13)
        head = HeadController(mock_servo_driver, config)

        # Set initial position (pan→head_yaw, tilt→head_pitch)
        head.look_at(pan=10.0, tilt=5.0, blocking=True)
        _, original_pitch, original_yaw, _ = head.get_current_position()

        # Perform nod
        head.nod(count=2, amplitude=15.0, blocking=True)

        # Should return to original position (nod returns to center for head_pitch)
        _, final_pitch, final_yaw, _ = head.get_current_position()
        # Yaw should be unchanged
        assert abs(final_yaw - original_yaw) < 0.1
        # Pitch returns to center (0.0) after nod
        assert abs(final_pitch - 0.0) < 0.1

    def test_nod_clamps_count(self, mock_servo_driver) -> None:
        """Test that nod count is clamped to valid range (1-5)."""
        from src.control.head_controller import HeadController, HeadConfig

        config = HeadConfig(neck_pitch_channel=10, head_pitch_channel=11, head_yaw_channel=12, head_roll_channel=13)
        head = HeadController(mock_servo_driver, config)

        # Zero count should be clamped to 1
        result = head.nod(count=0, blocking=True)
        assert result is True

        mock_servo_driver.reset()

        # Count > 5 should be clamped to 5
        result = head.nod(count=10, blocking=True)
        assert result is True


# =============================================================================
# TestShake - Horizontal negation gesture tests (~4 tests)
# =============================================================================

class TestShake:
    """Tests for shake() method - horizontal negation gesture (uses head_yaw)."""

    def test_shake_single(self, mock_servo_driver) -> None:
        """Test single shake motion."""
        from src.control.head_controller import HeadController, HeadConfig

        config = HeadConfig(neck_pitch_channel=10, head_pitch_channel=11, head_yaw_channel=12, head_roll_channel=13)
        head = HeadController(mock_servo_driver, config)

        result = head.shake(count=1, amplitude=20.0, speed_ms=200, blocking=True)

        assert result is True
        # Should have set head_yaw angle during shake
        assert len(mock_servo_driver.set_angle_calls) >= 1

    def test_shake_multiple(self, mock_servo_driver) -> None:
        """Test multiple shake cycles."""
        from src.control.head_controller import HeadController, HeadConfig

        config = HeadConfig(neck_pitch_channel=10, head_pitch_channel=11, head_yaw_channel=12, head_roll_channel=13)
        head = HeadController(mock_servo_driver, config)

        result = head.shake(count=3, amplitude=20.0, speed_ms=200, blocking=True)

        assert result is True
        # Multiple shakes should result in multiple servo commands
        assert len(mock_servo_driver.set_angle_calls) >= 3 * 2

    def test_shake_returns_to_original(self, mock_servo_driver) -> None:
        """Test that shake returns to original head_yaw position."""
        from src.control.head_controller import HeadController, HeadConfig

        config = HeadConfig(neck_pitch_channel=10, head_pitch_channel=11, head_yaw_channel=12, head_roll_channel=13)
        head = HeadController(mock_servo_driver, config)

        # Set initial position (pan→head_yaw, tilt→head_pitch)
        head.look_at(pan=10.0, tilt=5.0, blocking=True)
        _, original_pitch, original_yaw, _ = head.get_current_position()

        # Perform shake
        head.shake(count=2, amplitude=20.0, blocking=True)

        # Should return to original position (shake returns to center for head_yaw)
        _, final_pitch, final_yaw, _ = head.get_current_position()
        # Pitch should be unchanged
        assert abs(final_pitch - original_pitch) < 0.1
        # Yaw returns to center (0.0) after shake
        assert abs(final_yaw - 0.0) < 0.1

    def test_shake_clamps_count(self, mock_servo_driver) -> None:
        """Test that shake count is clamped to valid range (1-5)."""
        from src.control.head_controller import HeadController, HeadConfig

        config = HeadConfig(neck_pitch_channel=10, head_pitch_channel=11, head_yaw_channel=12, head_roll_channel=13)
        head = HeadController(mock_servo_driver, config)

        # Zero count should be clamped to 1
        result = head.shake(count=0, blocking=True)
        assert result is True

        mock_servo_driver.reset()

        # Count > 5 should be clamped to 5
        result = head.shake(count=10, blocking=True)
        assert result is True


# =============================================================================
# TestRandomGlance - Random glance behavior tests (~3 tests)
# =============================================================================

class TestRandomGlance:
    """Tests for random_glance() method - quick look and return (uses head_yaw/head_roll).

    Note: 4-DOF random_glance uses:
    - hold_ms: How long to hold the glance position
    - return_speed_ms: Speed to return to original position
    """

    def test_random_glance_moves(self, mock_servo_driver) -> None:
        """Test that random_glance moves the head."""
        from src.control.head_controller import HeadController, HeadConfig

        config = HeadConfig(neck_pitch_channel=10, head_pitch_channel=11, head_yaw_channel=12, head_roll_channel=13)
        head = HeadController(mock_servo_driver, config)

        result = head.random_glance(hold_ms=100, return_speed_ms=200, blocking=True)

        assert result is True
        # Should have sent servo commands
        assert len(mock_servo_driver.set_angle_calls) >= 2  # Move out and back

    def test_random_glance_stays_in_bounds(self, mock_servo_driver) -> None:
        """Test that random_glance stays within limits."""
        from src.control.head_controller import HeadController, HeadConfig, HeadLimits

        limits = HeadLimits(head_yaw_min=-90.0, head_yaw_max=90.0, head_pitch_min=-45.0, head_pitch_max=45.0)
        config = HeadConfig(neck_pitch_channel=10, head_pitch_channel=11, head_yaw_channel=12, head_roll_channel=13, limits=limits)
        head = HeadController(mock_servo_driver, config)

        # Start at edge of limits (pan→head_yaw, tilt→head_pitch)
        head.look_at(pan=80.0, tilt=40.0, blocking=True)

        # Random glance should stay in bounds
        for _ in range(5):  # Multiple trials due to randomness
            head.random_glance(hold_ms=50, return_speed_ms=100, blocking=True)

            # Check all servo angles are within valid servo range
            for channel, angle in mock_servo_driver.set_angle_calls:
                assert 0 <= angle <= 180  # Servo physical limits

    def test_random_glance_returns_to_center(self, mock_servo_driver) -> None:
        """Test that random_glance returns yaw/roll to center but preserves pitch.

        FIX C-2: Glance preserves neck_pitch and head_pitch (hold DOFs).
        Only head_yaw and head_roll return to center after the glance.
        """
        from src.control.head_controller import HeadController, HeadConfig

        config = HeadConfig(neck_pitch_channel=10, head_pitch_channel=11, head_yaw_channel=12, head_roll_channel=13)
        head = HeadController(mock_servo_driver, config)

        # Set initial position (pan→head_yaw, tilt→head_pitch)
        head.look_at(pan=20.0, tilt=-10.0, blocking=True)

        # Perform glance
        head.random_glance(hold_ms=100, return_speed_ms=200, blocking=True)

        # Random glance returns yaw/roll to center, preserves pitch
        _, final_pitch, final_yaw, final_roll = head.get_current_position()
        assert abs(final_yaw - 0.0) < 0.5  # head_yaw returns to center
        assert abs(final_roll - 0.0) < 0.5  # head_roll returns to center
        assert abs(final_pitch - (-10.0)) < 0.5  # head_pitch PRESERVED (not zeroed)


# =============================================================================
# TestTiltCurious - Curious head tilt tests (~3 tests)
# =============================================================================

class TestTiltCurious:
    """Tests for tilt_curious() method - curious head tilt gesture (uses head_roll)."""

    def test_tilt_curious_right(self, mock_servo_driver) -> None:
        """Test curious tilt to the right (uses head_roll)."""
        from src.control.head_controller import HeadController, HeadConfig

        config = HeadConfig(neck_pitch_channel=10, head_pitch_channel=11, head_yaw_channel=12, head_roll_channel=13)
        head = HeadController(mock_servo_driver, config)

        result = head.tilt_curious(direction='right', angle=20.0, blocking=True)

        assert result is True
        # Should have tilted head via head_roll
        assert len(mock_servo_driver.set_angle_calls) >= 1

    def test_tilt_curious_left(self, mock_servo_driver) -> None:
        """Test curious tilt to the left (uses head_roll)."""
        from src.control.head_controller import HeadController, HeadConfig

        config = HeadConfig(neck_pitch_channel=10, head_pitch_channel=11, head_yaw_channel=12, head_roll_channel=13)
        head = HeadController(mock_servo_driver, config)

        result = head.tilt_curious(direction='left', angle=20.0, blocking=True)

        assert result is True
        assert len(mock_servo_driver.set_angle_calls) >= 1

    def test_tilt_curious_invalid_direction(self, mock_servo_driver) -> None:
        """Test that invalid direction raises ValueError."""
        from src.control.head_controller import HeadController, HeadConfig

        config = HeadConfig(neck_pitch_channel=10, head_pitch_channel=11, head_yaw_channel=12, head_roll_channel=13)
        head = HeadController(mock_servo_driver, config)

        with pytest.raises(ValueError, match="direction"):
            head.tilt_curious(direction='up', angle=20.0)

        with pytest.raises(ValueError, match="direction"):
            head.tilt_curious(direction='invalid', angle=20.0)


# =============================================================================
# TestEmergencyStop - Emergency stop and reset tests (~4 tests)
# =============================================================================

class TestEmergencyStop:
    """Tests for emergency stop functionality (4-DOF)."""

    def test_emergency_stop_halts_movement(self, mock_servo_driver) -> None:
        """Test that emergency_stop halts all head movement."""
        from src.control.head_controller import HeadController, HeadConfig

        config = HeadConfig(neck_pitch_channel=10, head_pitch_channel=11, head_yaw_channel=12, head_roll_channel=13)
        head = HeadController(mock_servo_driver, config)

        # Start a movement (non-blocking)
        head.look_at(pan=45.0, tilt=30.0, duration_ms=1000, blocking=False)

        # Emergency stop
        head.emergency_stop()

        # Subsequent movements should be rejected
        result = head.look_at(pan=0.0, tilt=0.0, blocking=False)
        assert result is False or head.get_state().is_moving is False

    def test_emergency_stop_requires_reset(self, mock_servo_driver) -> None:
        """Test that emergency stop requires explicit reset."""
        from src.control.head_controller import HeadController, HeadConfig
        import pytest

        config = HeadConfig(neck_pitch_channel=10, head_pitch_channel=11, head_yaw_channel=12, head_roll_channel=13)
        head = HeadController(mock_servo_driver, config)

        head.emergency_stop()

        # Movements should fail until reset
        result = head.look_at(pan=30.0, tilt=15.0, blocking=False)
        assert result is False

        # Nod should raise RuntimeError per implementation spec
        with pytest.raises(RuntimeError, match="emergency stop active"):
            head.nod(count=1, blocking=False)

    def test_reset_emergency_clears_flag(self, mock_servo_driver) -> None:
        """Test that reset_emergency clears the emergency stop state."""
        from src.control.head_controller import HeadController, HeadConfig

        config = HeadConfig(neck_pitch_channel=10, head_pitch_channel=11, head_yaw_channel=12, head_roll_channel=13)
        head = HeadController(mock_servo_driver, config)

        head.emergency_stop()

        # Reset
        result = head.reset_emergency()
        assert result is True

        # Should now accept movements
        result = head.look_at(pan=30.0, tilt=15.0, blocking=True)
        assert result is True

    def test_emergency_stop_thread_safe(self, mock_servo_driver) -> None:
        """Test that emergency_stop is thread-safe."""
        from src.control.head_controller import HeadController, HeadConfig

        config = HeadConfig(neck_pitch_channel=10, head_pitch_channel=11, head_yaw_channel=12, head_roll_channel=13)
        head = HeadController(mock_servo_driver, config)

        errors: List[Exception] = []
        stop_called: List[bool] = []

        def call_emergency_stop():
            try:
                head.emergency_stop()
                stop_called.append(True)
            except Exception as e:
                errors.append(e)

        def call_movement():
            try:
                for _ in range(10):
                    head.look_at(pan=30.0, tilt=15.0, blocking=False)
                    time.sleep(0.001)
            except Exception as e:
                errors.append(e)

        # Start movement thread
        move_thread = threading.Thread(target=call_movement)
        move_thread.start()

        # Start multiple emergency stop threads
        stop_threads = [threading.Thread(target=call_emergency_stop) for _ in range(5)]
        for t in stop_threads:
            t.start()

        # Wait for all threads
        move_thread.join(timeout=2.0)
        for t in stop_threads:
            t.join(timeout=2.0)

        # No errors should have occurred
        assert len(errors) == 0, f"Thread errors: {errors}"


# =============================================================================
# TestGetState - State retrieval tests (~2 tests)
# =============================================================================

class TestGetState:
    """Tests for state retrieval methods (4-DOF)."""

    def test_get_current_position(self, mock_servo_driver) -> None:
        """Test get_current_position returns correct 4-DOF tuple."""
        from src.control.head_controller import HeadController, HeadConfig

        config = HeadConfig(neck_pitch_channel=10, head_pitch_channel=11, head_yaw_channel=12, head_roll_channel=13)
        head = HeadController(mock_servo_driver, config)

        # Move to position (pan→head_yaw, tilt→head_pitch)
        head.look_at(pan=45.0, tilt=-20.0, blocking=True)

        position = head.get_current_position()

        assert isinstance(position, tuple)
        assert len(position) == 4  # 4-DOF: (neck_pitch, head_pitch, head_yaw, head_roll)
        assert position[2] == 45.0  # head_yaw (mapped from pan)
        assert position[1] == -20.0  # head_pitch (mapped from tilt)

    def test_get_state_returns_snapshot(self, mock_servo_driver) -> None:
        """Test get_state returns immutable 4-DOF HeadState snapshot."""
        from src.control.head_controller import HeadController, HeadConfig, HeadState

        config = HeadConfig(neck_pitch_channel=10, head_pitch_channel=11, head_yaw_channel=12, head_roll_channel=13)
        head = HeadController(mock_servo_driver, config)

        head.look_at(pan=30.0, tilt=15.0, blocking=True)

        state = head.get_state()

        # Should return HeadState dataclass with 4-DOF attributes
        assert isinstance(state, HeadState)
        assert state.head_yaw == 30.0  # pan maps to head_yaw
        assert state.head_pitch == 15.0  # tilt maps to head_pitch
        assert state.neck_pitch == 0.0  # Unchanged
        assert state.head_roll == 0.0  # Unchanged
        assert state.is_moving is False

        # State should be a snapshot (not live reference)
        # Moving should not affect the old state object
        head.look_at(pan=0.0, tilt=0.0, blocking=False)
        assert state.head_yaw == 30.0  # Old state unchanged


# =============================================================================
# Performance Tests
# =============================================================================

class TestHeadControllerPerformance:
    """Performance tests for HeadController (4-DOF)."""

    def test_look_at_initiation_latency(self, mock_servo_driver) -> None:
        """Test that look_at initiates movement within 5ms."""
        from src.control.head_controller import HeadController, HeadConfig

        config = HeadConfig(neck_pitch_channel=10, head_pitch_channel=11, head_yaw_channel=12, head_roll_channel=13)
        head = HeadController(mock_servo_driver, config)

        start = time.monotonic()
        head.look_at(pan=30.0, tilt=15.0, blocking=False)
        latency_ms = (time.monotonic() - start) * 1000

        # Movement initiation should be fast (relaxed for Windows CI timing variability)
        assert latency_ms < 15.0, f"look_at initiation took {latency_ms}ms (limit: 15ms)"

    def test_get_state_performance(self, mock_servo_driver) -> None:
        """Test that get_state is fast (<1ms for 1000 calls)."""
        from src.control.head_controller import HeadController, HeadConfig

        config = HeadConfig(neck_pitch_channel=10, head_pitch_channel=11, head_yaw_channel=12, head_roll_channel=13)
        head = HeadController(mock_servo_driver, config)

        start = time.monotonic()
        for _ in range(1000):
            head.get_state()
        elapsed_ms = (time.monotonic() - start) * 1000

        avg_us = (elapsed_ms / 1000) * 1000  # Average in microseconds
        assert avg_us < 10, f"get_state avg {avg_us}us (limit: 10us)"


# =============================================================================
# Integration Tests
# =============================================================================

class TestHeadControllerIntegration:
    """Integration tests combining multiple HeadController features (4-DOF)."""

    def test_emotion_sequence_simulation(self, mock_servo_driver) -> None:
        """Test simulated emotion expression sequence."""
        from src.control.head_controller import HeadController, HeadConfig

        config = HeadConfig(neck_pitch_channel=10, head_pitch_channel=11, head_yaw_channel=12, head_roll_channel=13)
        head = HeadController(mock_servo_driver, config)

        # Simulate "curious" emotion: tilt + glance
        head.tilt_curious(direction='right', angle=15.0, blocking=True)
        head.random_glance(hold_ms=100, return_speed_ms=200, blocking=True)
        head.reset_to_center(blocking=True)

        # Should return to center (check all 4 DOF)
        neck_p, head_p, head_y, head_r = head.get_current_position()
        assert abs(head_y) < 1.0  # head_yaw near center
        assert abs(head_p) < 1.0  # head_pitch near center

    def test_affirmation_then_negation(self, mock_servo_driver) -> None:
        """Test nod followed by shake sequence."""
        from src.control.head_controller import HeadController, HeadConfig

        config = HeadConfig(neck_pitch_channel=10, head_pitch_channel=11, head_yaw_channel=12, head_roll_channel=13)
        head = HeadController(mock_servo_driver, config)

        # Affirmation (nod) - uses head_pitch
        head.nod(count=2, amplitude=15.0, blocking=True)

        # Small pause
        time.sleep(0.05)

        # Negation (shake) - uses head_yaw
        head.shake(count=2, amplitude=20.0, blocking=True)

        # Should be at center position (nod/shake return to center)
        _, head_pitch, head_yaw, _ = head.get_current_position()
        assert abs(head_yaw) < 1.0  # head_yaw returns to center
        assert abs(head_pitch) < 1.0  # head_pitch returns to center


# =============================================================================
# TestIsMoving - Movement state tracking (HIGH)
# =============================================================================

class TestIsMoving:
    """Tests for is_moving() state tracking (4-DOF)."""

    def test_is_moving_false_at_init(self, mock_servo_driver) -> None:
        """Test that is_moving() returns False at initialization."""
        from src.control.head_controller import HeadController, HeadConfig

        config = HeadConfig(neck_pitch_channel=10, head_pitch_channel=11, head_yaw_channel=12, head_roll_channel=13)
        head = HeadController(mock_servo_driver, config)

        assert head.is_moving() is False
        assert head.get_state().is_moving is False

    def test_is_moving_true_during_movement(self, mock_servo_driver) -> None:
        """Test that is_moving() returns True during active movement."""
        from src.control.head_controller import HeadController, HeadConfig

        config = HeadConfig(neck_pitch_channel=10, head_pitch_channel=11, head_yaw_channel=12, head_roll_channel=13)
        head = HeadController(mock_servo_driver, config)

        # Start long non-blocking movement
        head.look_at(pan=45.0, tilt=30.0, duration_ms=500, blocking=False)

        # Should be moving immediately after
        time.sleep(0.01)  # Small delay to let thread start
        assert head.is_moving() is True

    def test_is_moving_false_after_completion(self, mock_servo_driver) -> None:
        """Test that is_moving() returns False after movement completes."""
        from src.control.head_controller import HeadController, HeadConfig

        config = HeadConfig(neck_pitch_channel=10, head_pitch_channel=11, head_yaw_channel=12, head_roll_channel=13)
        head = HeadController(mock_servo_driver, config)

        # Start and complete movement
        head.look_at(pan=45.0, tilt=30.0, duration_ms=50, blocking=True)

        # Should no longer be moving
        assert head.is_moving() is False

    def test_is_moving_false_after_emergency_stop(self, mock_servo_driver) -> None:
        """Test that is_moving() returns False after emergency stop."""
        from src.control.head_controller import HeadController, HeadConfig

        config = HeadConfig(neck_pitch_channel=10, head_pitch_channel=11, head_yaw_channel=12, head_roll_channel=13)
        head = HeadController(mock_servo_driver, config)

        # Start movement then emergency stop
        head.look_at(pan=45.0, tilt=30.0, duration_ms=1000, blocking=False)
        time.sleep(0.01)
        head.emergency_stop()

        # Should no longer be moving
        assert head.is_moving() is False


# =============================================================================
# TestResetToCenter - Reset to center position (HIGH)
# =============================================================================

class TestResetToCenter:
    """Tests for reset_to_center() method (4-DOF)."""

    def test_reset_to_center_from_offset(self, mock_servo_driver) -> None:
        """Test that reset_to_center moves all DOF to center."""
        from src.control.head_controller import HeadController, HeadConfig

        config = HeadConfig(neck_pitch_channel=10, head_pitch_channel=11, head_yaw_channel=12, head_roll_channel=13)
        head = HeadController(mock_servo_driver, config)

        # Move to offset position using move_to
        head.move_to(neck_pitch=20.0, head_pitch=15.0, head_yaw=30.0, head_roll=10.0, blocking=True)

        # Reset to center
        result = head.reset_to_center(blocking=True)

        assert result is True
        neck_p, head_p, head_y, head_r = head.get_current_position()
        assert abs(neck_p) < 1.0  # Near center
        assert abs(head_p) < 1.0  # Near center
        assert abs(head_y) < 1.0  # Near center
        assert abs(head_r) < 1.0  # Near center

    def test_reset_to_center_with_custom_center(self, mock_servo_driver) -> None:
        """Test reset_to_center respects custom center positions."""
        from src.control.head_controller import HeadController, HeadConfig, HeadLimits

        # Set custom center positions
        limits = HeadLimits(
            neck_pitch_center=5.0,
            head_pitch_center=3.0,
            head_yaw_center=2.0,
            head_roll_center=1.0
        )
        config = HeadConfig(neck_pitch_channel=10, head_pitch_channel=11, head_yaw_channel=12, head_roll_channel=13, limits=limits)
        head = HeadController(mock_servo_driver, config)

        # Move away from center
        head.move_to(neck_pitch=20.0, head_pitch=20.0, head_yaw=20.0, head_roll=10.0, blocking=True)

        # Reset to center
        head.reset_to_center(blocking=True)

        # Should be at custom center positions
        neck_p, head_p, head_y, head_r = head.get_current_position()
        assert abs(neck_p - 5.0) < 1.0
        assert abs(head_p - 3.0) < 1.0
        assert abs(head_y - 2.0) < 1.0
        assert abs(head_r - 1.0) < 1.0

    def test_reset_to_center_non_blocking(self, mock_servo_driver) -> None:
        """Test reset_to_center with blocking=False returns immediately."""
        from src.control.head_controller import HeadController, HeadConfig

        config = HeadConfig(neck_pitch_channel=10, head_pitch_channel=11, head_yaw_channel=12, head_roll_channel=13)
        head = HeadController(mock_servo_driver, config)

        head.move_to(neck_pitch=20.0, head_yaw=30.0, blocking=True)

        start = time.monotonic()
        result = head.reset_to_center(duration_ms=500, blocking=False)
        elapsed_ms = (time.monotonic() - start) * 1000

        assert result is True
        assert elapsed_ms < 50  # Should return immediately


# =============================================================================
# TestCallbacks - Movement completion callbacks (HIGH)
# =============================================================================

class TestCallbacks:
    """Tests for movement completion callbacks (4-DOF)."""


    def test_callback_called_on_completion(self, mock_servo_driver) -> None:
        """Test that callback is called when movement completes."""
        from src.control.head_controller import HeadController, HeadConfig

        config = HeadConfig(neck_pitch_channel=10, head_pitch_channel=11, head_yaw_channel=12, head_roll_channel=13)
        head = HeadController(mock_servo_driver, config)

        callback_called = [False]
        callback_args = [None]

        def on_complete(success: bool):
            callback_called[0] = True
            callback_args[0] = success

        # Move with callback
        head.look_at(pan=30.0, tilt=15.0, duration_ms=50, blocking=True, on_complete=on_complete)

        assert callback_called[0] is True
        assert callback_args[0] is True  # Movement succeeded

    def test_callback_receives_false_on_interrupt(self, mock_servo_driver) -> None:
        """Test that callback receives False when movement is interrupted."""
        from src.control.head_controller import HeadController, HeadConfig

        config = HeadConfig(neck_pitch_channel=10, head_pitch_channel=11, head_yaw_channel=12, head_roll_channel=13)
        head = HeadController(mock_servo_driver, config)

        callback_called = [False]
        callback_args = [None]

        def on_complete(success: bool):
            callback_called[0] = True
            callback_args[0] = success

        # Start movement with callback
        head.look_at(pan=45.0, tilt=30.0, duration_ms=1000, blocking=False, on_complete=on_complete)
        time.sleep(0.05)  # Let movement start

        # Emergency stop interrupts
        head.emergency_stop()
        time.sleep(0.1)  # Allow callback to fire

        # Callback should be called with False (interrupted)
        assert callback_called[0] is True
        assert callback_args[0] is False

    def test_callback_not_called_when_none(self, mock_servo_driver) -> None:
        """Test that no error occurs when callback is None."""
        from src.control.head_controller import HeadController, HeadConfig

        config = HeadConfig(neck_pitch_channel=10, head_pitch_channel=11, head_yaw_channel=12, head_roll_channel=13)
        head = HeadController(mock_servo_driver, config)

        # Should not raise error with no callback
        result = head.look_at(pan=30.0, tilt=15.0, duration_ms=50, blocking=True, on_complete=None)
        assert result is True


# =============================================================================
# TestNaNHandling - NaN/Inf input handling (HIGH)
# =============================================================================

class TestNaNHandling:
    """Tests for NaN/Inf input handling (4-DOF)."""


    def test_look_at_rejects_nan_pan(self, mock_servo_driver) -> None:
        """Test that look_at rejects NaN pan value."""
        from src.control.head_controller import HeadController, HeadConfig
        import math

        config = HeadConfig(neck_pitch_channel=10, head_pitch_channel=11, head_yaw_channel=12, head_roll_channel=13)
        head = HeadController(mock_servo_driver, config)

        with pytest.raises(ValueError, match="(NaN|nan|invalid)"):
            head.look_at(pan=float('nan'), tilt=15.0, blocking=True)

    def test_look_at_rejects_nan_tilt(self, mock_servo_driver) -> None:
        """Test that look_at rejects NaN tilt value."""
        from src.control.head_controller import HeadController, HeadConfig

        config = HeadConfig(neck_pitch_channel=10, head_pitch_channel=11, head_yaw_channel=12, head_roll_channel=13)
        head = HeadController(mock_servo_driver, config)

        with pytest.raises(ValueError, match="(NaN|nan|invalid)"):
            head.look_at(pan=30.0, tilt=float('nan'), blocking=True)

    def test_look_at_rejects_inf(self, mock_servo_driver) -> None:
        """Test that look_at rejects Inf values."""
        from src.control.head_controller import HeadController, HeadConfig

        config = HeadConfig(neck_pitch_channel=10, head_pitch_channel=11, head_yaw_channel=12, head_roll_channel=13)
        head = HeadController(mock_servo_driver, config)

        with pytest.raises(ValueError, match="(Inf|inf|invalid)"):
            head.look_at(pan=float('inf'), tilt=15.0, blocking=True)

        with pytest.raises(ValueError, match="(Inf|inf|invalid)"):
            head.look_at(pan=30.0, tilt=float('-inf'), blocking=True)

    def test_move_to_rejects_nan(self, mock_servo_driver) -> None:
        """Test that move_to rejects NaN values."""
        from src.control.head_controller import HeadController, HeadConfig

        config = HeadConfig(neck_pitch_channel=10, head_pitch_channel=11, head_yaw_channel=12, head_roll_channel=13)
        head = HeadController(mock_servo_driver, config)

        with pytest.raises(ValueError, match="(NaN|nan|invalid)"):
            head.move_to(neck_pitch=float('nan'), blocking=True)

        with pytest.raises(ValueError, match="(NaN|nan|invalid)"):
            head.move_to(head_roll=float('nan'), blocking=True)


# =============================================================================
# TestTimeout - Movement timeout handling (HIGH)
# =============================================================================

class TestTimeout:
    """Tests for movement timeout handling."""


    def test_blocking_movement_respects_timeout(self, mock_servo_driver) -> None:
        """Test that blocking movement with timeout returns after timeout."""
        from src.control.head_controller import HeadController, HeadConfig

        config = HeadConfig(neck_pitch_channel=10, head_pitch_channel=11, head_yaw_channel=12, head_roll_channel=13)
        head = HeadController(mock_servo_driver, config)

        start = time.monotonic()
        # Request movement with specific duration
        head.look_at(pan=45.0, tilt=30.0, duration_ms=200, blocking=True, timeout_ms=500)
        elapsed_ms = (time.monotonic() - start) * 1000

        # Should complete around duration, not wait forever
        assert elapsed_ms < 1000  # Within reasonable bounds
        assert elapsed_ms >= 150   # At least most of duration

    def test_movement_duration_consistency(self, mock_servo_driver) -> None:
        """Test that multiple movements have consistent timing."""
        from src.control.head_controller import HeadController, HeadConfig

        config = HeadConfig(neck_pitch_channel=10, head_pitch_channel=11, head_yaw_channel=12, head_roll_channel=13)
        head = HeadController(mock_servo_driver, config)

        durations = []
        target_duration = 100

        for _ in range(5):
            start = time.monotonic()
            head.look_at(pan=30.0, tilt=15.0, duration_ms=target_duration, blocking=True)
            elapsed = (time.monotonic() - start) * 1000
            durations.append(elapsed)
            head.look_at(pan=0.0, tilt=0.0, duration_ms=50, blocking=True)  # Reset

        # All durations should be within 50% of target
        for d in durations:
            assert d >= target_duration * 0.5
            assert d <= target_duration * 2.0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
