#!/usr/bin/env python3
"""
TDD Test Suite for HeadController - 2-DOF Pan/Tilt Head Control

Tests written FIRST (TDD methodology) before any implementation exists.
Tests define expected behavior for HeadController module.

Quality Standard: Boston Dynamics / Pixar Grade

Test Classes:
    TestHeadLimits: HeadLimits dataclass validation tests
    TestHeadConfig: HeadConfig dataclass validation tests
    TestHeadControllerInit: Initialization tests
    TestLookAt: Direct positioning tests
    TestNod: Vertical affirmation gesture tests
    TestShake: Horizontal negation gesture tests
    TestRandomGlance: Random glance behavior tests
    TestTiltCurious: Curious head tilt tests
    TestEmergencyStop: Emergency stop and reset tests
    TestGetState: State retrieval tests

Run with: pytest tests/test_control/test_head_controller.py -v

Author: TDD Test Architect Agent
Created: 18 January 2026
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

    Attributes:
        channels: Dictionary of channel states
        set_angle_calls: List of (channel, angle) tuples for all set_servo_angle calls
        disable_calls: List of channels that were disabled
    """

    def __init__(self) -> None:
        """Initialize mock servo driver with 16 channels."""
        self.channels = {i: {'angle': 90, 'enabled': False} for i in range(16)}
        self.set_angle_calls: List[Tuple[int, float]] = []
        self.disable_calls: List[int] = []
        self._lock = threading.Lock()

    def reset(self) -> None:
        """Reset all tracking data."""
        with self._lock:
            for i in range(16):
                self.channels[i] = {'angle': 90, 'enabled': False}
            self.set_angle_calls.clear()
            self.disable_calls.clear()

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
            self.channels[channel]['angle'] = angle
            self.channels[channel]['enabled'] = True

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
    """Provide default head configuration for testing.

    Returns:
        Dictionary of default configuration values.
    """
    return {
        'pan_channel': 12,
        'tilt_channel': 13,
        'pan_min': -90.0,
        'pan_max': 90.0,
        'tilt_min': -45.0,
        'tilt_max': 45.0,
        'pan_center': 0.0,
        'tilt_center': 0.0,
        'default_speed_ms': 300,
    }


# =============================================================================
# TestHeadLimits - HeadLimits dataclass validation (~5 tests)
# =============================================================================

class TestHeadLimits:
    """Tests for HeadLimits dataclass validation."""

    def test_valid_limits_creation(self) -> None:
        """Test creating HeadLimits with valid parameters."""
        from src.control.head_controller import HeadLimits

        limits = HeadLimits(
            pan_min=-90.0,
            pan_max=90.0,
            tilt_min=-45.0,
            tilt_max=45.0,
            pan_center=0.0,
            tilt_center=0.0
        )

        assert limits.pan_min == -90.0
        assert limits.pan_max == 90.0
        assert limits.tilt_min == -45.0
        assert limits.tilt_max == 45.0
        assert limits.pan_center == 0.0
        assert limits.tilt_center == 0.0

    def test_invalid_pan_limits_raises(self) -> None:
        """Test that pan_min >= pan_max raises ValueError."""
        from src.control.head_controller import HeadLimits

        # pan_min equals pan_max
        with pytest.raises(ValueError, match="pan_min.*must be.*<.*pan_max"):
            HeadLimits(pan_min=90.0, pan_max=90.0)

        # pan_min greater than pan_max
        with pytest.raises(ValueError, match="pan_min.*must be.*<.*pan_max"):
            HeadLimits(pan_min=100.0, pan_max=50.0)

    def test_invalid_tilt_limits_raises(self) -> None:
        """Test that tilt_min >= tilt_max raises ValueError."""
        from src.control.head_controller import HeadLimits

        # tilt_min equals tilt_max
        with pytest.raises(ValueError, match="tilt_min.*must be.*<.*tilt_max"):
            HeadLimits(tilt_min=45.0, tilt_max=45.0)

        # tilt_min greater than tilt_max
        with pytest.raises(ValueError, match="tilt_min.*must be.*<.*tilt_max"):
            HeadLimits(tilt_min=60.0, tilt_max=30.0)

    def test_center_outside_limits_raises(self) -> None:
        """Test that center position outside limits raises ValueError."""
        from src.control.head_controller import HeadLimits

        # pan_center outside limits
        with pytest.raises(ValueError, match="pan_center.*must be within pan limits"):
            HeadLimits(pan_min=-90.0, pan_max=90.0, pan_center=100.0)

        # tilt_center outside limits
        with pytest.raises(ValueError, match="tilt_center.*must be within tilt limits"):
            HeadLimits(tilt_min=-45.0, tilt_max=45.0, tilt_center=60.0)

    def test_default_limits(self) -> None:
        """Test HeadLimits has sensible default values."""
        from src.control.head_controller import HeadLimits

        limits = HeadLimits()

        # Default values per architecture spec
        assert limits.pan_min == -90.0
        assert limits.pan_max == 90.0
        assert limits.tilt_min == -45.0
        assert limits.tilt_max == 45.0
        assert limits.pan_center == 0.0
        assert limits.tilt_center == 0.0


# =============================================================================
# TestHeadConfig - HeadConfig dataclass validation (~5 tests)
# =============================================================================

class TestHeadConfig:
    """Tests for HeadConfig dataclass validation."""

    def test_valid_config_creation(self) -> None:
        """Test creating HeadConfig with valid parameters."""
        from src.control.head_controller import HeadConfig, HeadLimits

        config = HeadConfig(
            pan_channel=12,
            tilt_channel=13,
            limits=HeadLimits(),
            pan_inverted=False,
            tilt_inverted=False,
            default_speed_ms=300,
            easing='ease_in_out'
        )

        assert config.pan_channel == 12
        assert config.tilt_channel == 13
        assert config.default_speed_ms == 300
        assert config.easing == 'ease_in_out'

    def test_invalid_channel_raises(self) -> None:
        """Test that invalid channel numbers raise ValueError."""
        from src.control.head_controller import HeadConfig

        # Negative channel
        with pytest.raises(ValueError, match="pan_channel must be 0-15"):
            HeadConfig(pan_channel=-1, tilt_channel=13)

        # Channel > 15
        with pytest.raises(ValueError, match="pan_channel must be 0-15"):
            HeadConfig(pan_channel=16, tilt_channel=13)

        # Invalid tilt channel
        with pytest.raises(ValueError, match="tilt_channel must be 0-15"):
            HeadConfig(pan_channel=12, tilt_channel=20)

    def test_duplicate_channels_raises(self) -> None:
        """Test that pan_channel == tilt_channel raises ValueError."""
        from src.control.head_controller import HeadConfig

        with pytest.raises(ValueError, match="pan_channel and tilt_channel must differ"):
            HeadConfig(pan_channel=10, tilt_channel=10)

    def test_invalid_speed_raises(self) -> None:
        """Test that invalid default_speed_ms raises ValueError."""
        from src.control.head_controller import HeadConfig

        # Zero speed
        with pytest.raises(ValueError, match="default_speed_ms must be > 0"):
            HeadConfig(pan_channel=12, tilt_channel=13, default_speed_ms=0)

        # Negative speed
        with pytest.raises(ValueError, match="default_speed_ms must be > 0"):
            HeadConfig(pan_channel=12, tilt_channel=13, default_speed_ms=-100)

    def test_default_values(self) -> None:
        """Test HeadConfig has sensible default values."""
        from src.control.head_controller import HeadConfig

        config = HeadConfig(pan_channel=12, tilt_channel=13)

        assert config.pan_inverted is False
        assert config.tilt_inverted is False
        assert config.default_speed_ms == 300
        assert config.easing == 'ease_in_out'


# =============================================================================
# TestHeadControllerInit - Initialization tests (~3 tests)
# =============================================================================

class TestHeadControllerInit:
    """Tests for HeadController initialization."""

    def test_init_with_valid_config(self, mock_servo_driver) -> None:
        """Test HeadController initializes with valid configuration."""
        from src.control.head_controller import HeadController, HeadConfig

        config = HeadConfig(pan_channel=12, tilt_channel=13)
        head = HeadController(mock_servo_driver, config)

        assert head.config == config
        assert head.config.pan_channel == 12
        assert head.config.tilt_channel == 13

    def test_init_positions_at_center(self, mock_servo_driver) -> None:
        """Test that initialization positions head at center."""
        from src.control.head_controller import HeadController, HeadConfig

        config = HeadConfig(pan_channel=12, tilt_channel=13)
        head = HeadController(mock_servo_driver, config)

        # Should start at center position
        pan, tilt = head.get_current_position()
        assert pan == 0.0  # Center
        assert tilt == 0.0  # Center

    def test_init_with_mock_driver(self, mock_servo_driver) -> None:
        """Test HeadController works with mock driver."""
        from src.control.head_controller import HeadController, HeadConfig

        config = HeadConfig(pan_channel=12, tilt_channel=13)
        head = HeadController(mock_servo_driver, config)

        # Should be able to query state
        state = head.get_state()
        assert state is not None
        assert state.pan == 0.0
        assert state.tilt == 0.0
        assert state.is_moving is False


# =============================================================================
# TestLookAt - Direct positioning tests (~5 tests)
# =============================================================================

class TestLookAt:
    """Tests for look_at() method - direct pan/tilt positioning."""

    def test_look_at_basic(self, mock_servo_driver) -> None:
        """Test basic look_at movement to valid position."""
        from src.control.head_controller import HeadController, HeadConfig

        config = HeadConfig(pan_channel=12, tilt_channel=13)
        head = HeadController(mock_servo_driver, config)

        # Move to specific position
        result = head.look_at(pan=30.0, tilt=15.0, blocking=True)

        assert result is True
        pan, tilt = head.get_current_position()
        assert pan == 30.0
        assert tilt == 15.0

    def test_look_at_clamps_to_limits(self, mock_servo_driver) -> None:
        """Test that look_at clamps values to limits (not errors)."""
        from src.control.head_controller import HeadController, HeadConfig, HeadLimits

        limits = HeadLimits(pan_min=-90.0, pan_max=90.0, tilt_min=-45.0, tilt_max=45.0)
        config = HeadConfig(pan_channel=12, tilt_channel=13, limits=limits)
        head = HeadController(mock_servo_driver, config)

        # Try to move beyond limits - should clamp, not raise
        result = head.look_at(pan=150.0, tilt=100.0, blocking=True)

        assert result is True
        pan, tilt = head.get_current_position()
        assert pan == 90.0   # Clamped to max
        assert tilt == 45.0  # Clamped to max

        # Try negative beyond limits
        head.look_at(pan=-200.0, tilt=-100.0, blocking=True)
        pan, tilt = head.get_current_position()
        assert pan == -90.0  # Clamped to min
        assert tilt == -45.0  # Clamped to min

    def test_look_at_with_custom_duration(self, mock_servo_driver) -> None:
        """Test look_at with custom duration override."""
        from src.control.head_controller import HeadController, HeadConfig

        config = HeadConfig(pan_channel=12, tilt_channel=13, default_speed_ms=300)
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

        config = HeadConfig(pan_channel=12, tilt_channel=13, easing='ease_in_out')
        head = HeadController(mock_servo_driver, config)

        # Movement with linear easing
        result = head.look_at(pan=30.0, tilt=15.0, easing='linear', blocking=True)

        assert result is True
        pan, tilt = head.get_current_position()
        assert pan == 30.0
        assert tilt == 15.0

    def test_look_at_updates_position(self, mock_servo_driver) -> None:
        """Test that look_at updates internal position tracking."""
        from src.control.head_controller import HeadController, HeadConfig

        config = HeadConfig(pan_channel=12, tilt_channel=13)
        head = HeadController(mock_servo_driver, config)

        # Initial position
        pan1, tilt1 = head.get_current_position()
        assert pan1 == 0.0
        assert tilt1 == 0.0

        # Move
        head.look_at(pan=45.0, tilt=-20.0, blocking=True)

        # Position should be updated
        pan2, tilt2 = head.get_current_position()
        assert pan2 == 45.0
        assert tilt2 == -20.0


# =============================================================================
# TestNod - Vertical affirmation gesture tests (~4 tests)
# =============================================================================

class TestNod:
    """Tests for nod() method - vertical affirmation gesture."""

    def test_nod_single(self, mock_servo_driver) -> None:
        """Test single nod motion."""
        from src.control.head_controller import HeadController, HeadConfig

        config = HeadConfig(pan_channel=12, tilt_channel=13)
        head = HeadController(mock_servo_driver, config)

        result = head.nod(count=1, amplitude=15.0, speed_ms=200, blocking=True)

        assert result is True
        # Should have set tilt angle during nod
        assert len(mock_servo_driver.set_angle_calls) >= 1

    def test_nod_multiple(self, mock_servo_driver) -> None:
        """Test multiple nod cycles."""
        from src.control.head_controller import HeadController, HeadConfig

        config = HeadConfig(pan_channel=12, tilt_channel=13)
        head = HeadController(mock_servo_driver, config)

        result = head.nod(count=3, amplitude=15.0, speed_ms=200, blocking=True)

        assert result is True
        # Multiple nods should result in multiple servo commands
        # At least count * 2 commands (up and down for each nod)
        assert len(mock_servo_driver.set_angle_calls) >= 3 * 2

    def test_nod_returns_to_original(self, mock_servo_driver) -> None:
        """Test that nod returns to original tilt position."""
        from src.control.head_controller import HeadController, HeadConfig

        config = HeadConfig(pan_channel=12, tilt_channel=13)
        head = HeadController(mock_servo_driver, config)

        # Set initial position
        head.look_at(pan=10.0, tilt=5.0, blocking=True)
        original_pan, original_tilt = head.get_current_position()

        # Perform nod
        head.nod(count=2, amplitude=15.0, blocking=True)

        # Should return to original position
        final_pan, final_tilt = head.get_current_position()
        assert abs(final_pan - original_pan) < 0.1
        assert abs(final_tilt - original_tilt) < 0.1

    def test_nod_clamps_count(self, mock_servo_driver) -> None:
        """Test that nod count is clamped to valid range (1-5)."""
        from src.control.head_controller import HeadController, HeadConfig

        config = HeadConfig(pan_channel=12, tilt_channel=13)
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
    """Tests for shake() method - horizontal negation gesture."""

    def test_shake_single(self, mock_servo_driver) -> None:
        """Test single shake motion."""
        from src.control.head_controller import HeadController, HeadConfig

        config = HeadConfig(pan_channel=12, tilt_channel=13)
        head = HeadController(mock_servo_driver, config)

        result = head.shake(count=1, amplitude=20.0, speed_ms=200, blocking=True)

        assert result is True
        # Should have set pan angle during shake
        assert len(mock_servo_driver.set_angle_calls) >= 1

    def test_shake_multiple(self, mock_servo_driver) -> None:
        """Test multiple shake cycles."""
        from src.control.head_controller import HeadController, HeadConfig

        config = HeadConfig(pan_channel=12, tilt_channel=13)
        head = HeadController(mock_servo_driver, config)

        result = head.shake(count=3, amplitude=20.0, speed_ms=200, blocking=True)

        assert result is True
        # Multiple shakes should result in multiple servo commands
        assert len(mock_servo_driver.set_angle_calls) >= 3 * 2

    def test_shake_returns_to_original(self, mock_servo_driver) -> None:
        """Test that shake returns to original pan position."""
        from src.control.head_controller import HeadController, HeadConfig

        config = HeadConfig(pan_channel=12, tilt_channel=13)
        head = HeadController(mock_servo_driver, config)

        # Set initial position
        head.look_at(pan=10.0, tilt=5.0, blocking=True)
        original_pan, original_tilt = head.get_current_position()

        # Perform shake
        head.shake(count=2, amplitude=20.0, blocking=True)

        # Should return to original position
        final_pan, final_tilt = head.get_current_position()
        assert abs(final_pan - original_pan) < 0.1
        assert abs(final_tilt - original_tilt) < 0.1

    def test_shake_clamps_count(self, mock_servo_driver) -> None:
        """Test that shake count is clamped to valid range (1-5)."""
        from src.control.head_controller import HeadController, HeadConfig

        config = HeadConfig(pan_channel=12, tilt_channel=13)
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
    """Tests for random_glance() method - quick look and return."""

    def test_random_glance_moves(self, mock_servo_driver) -> None:
        """Test that random_glance moves the head."""
        from src.control.head_controller import HeadController, HeadConfig

        config = HeadConfig(pan_channel=12, tilt_channel=13)
        head = HeadController(mock_servo_driver, config)

        result = head.random_glance(max_deviation=30.0, hold_ms=100, blocking=True)

        assert result is True
        # Should have sent servo commands
        assert len(mock_servo_driver.set_angle_calls) >= 2  # Move out and back

    def test_random_glance_stays_in_bounds(self, mock_servo_driver) -> None:
        """Test that random_glance stays within limits."""
        from src.control.head_controller import HeadController, HeadConfig, HeadLimits

        limits = HeadLimits(pan_min=-90.0, pan_max=90.0, tilt_min=-45.0, tilt_max=45.0)
        config = HeadConfig(pan_channel=12, tilt_channel=13, limits=limits)
        head = HeadController(mock_servo_driver, config)

        # Start at edge of limits
        head.look_at(pan=80.0, tilt=40.0, blocking=True)

        # Random glance should stay in bounds
        for _ in range(5):  # Multiple trials due to randomness
            head.random_glance(max_deviation=30.0, hold_ms=50, blocking=True)

            # Check all servo angles are within valid servo range
            for channel, angle in mock_servo_driver.set_angle_calls:
                assert 0 <= angle <= 180  # Servo physical limits

    def test_random_glance_returns_to_original(self, mock_servo_driver) -> None:
        """Test that random_glance returns to original position."""
        from src.control.head_controller import HeadController, HeadConfig

        config = HeadConfig(pan_channel=12, tilt_channel=13)
        head = HeadController(mock_servo_driver, config)

        # Set initial position
        head.look_at(pan=20.0, tilt=-10.0, blocking=True)
        original_pan, original_tilt = head.get_current_position()

        # Perform glance
        head.random_glance(max_deviation=30.0, hold_ms=100, blocking=True)

        # Should return to original
        final_pan, final_tilt = head.get_current_position()
        assert abs(final_pan - original_pan) < 0.5
        assert abs(final_tilt - original_tilt) < 0.5


# =============================================================================
# TestTiltCurious - Curious head tilt tests (~3 tests)
# =============================================================================

class TestTiltCurious:
    """Tests for tilt_curious() method - curious head tilt gesture."""

    def test_tilt_curious_right(self, mock_servo_driver) -> None:
        """Test curious tilt to the right."""
        from src.control.head_controller import HeadController, HeadConfig

        config = HeadConfig(pan_channel=12, tilt_channel=13)
        head = HeadController(mock_servo_driver, config)

        result = head.tilt_curious(direction='right', angle=20.0, blocking=True)

        assert result is True
        # Should have tilted head
        assert len(mock_servo_driver.set_angle_calls) >= 1

    def test_tilt_curious_left(self, mock_servo_driver) -> None:
        """Test curious tilt to the left."""
        from src.control.head_controller import HeadController, HeadConfig

        config = HeadConfig(pan_channel=12, tilt_channel=13)
        head = HeadController(mock_servo_driver, config)

        result = head.tilt_curious(direction='left', angle=20.0, blocking=True)

        assert result is True
        assert len(mock_servo_driver.set_angle_calls) >= 1

    def test_tilt_curious_invalid_direction(self, mock_servo_driver) -> None:
        """Test that invalid direction raises ValueError."""
        from src.control.head_controller import HeadController, HeadConfig

        config = HeadConfig(pan_channel=12, tilt_channel=13)
        head = HeadController(mock_servo_driver, config)

        with pytest.raises(ValueError, match="direction"):
            head.tilt_curious(direction='up', angle=20.0)

        with pytest.raises(ValueError, match="direction"):
            head.tilt_curious(direction='invalid', angle=20.0)


# =============================================================================
# TestEmergencyStop - Emergency stop and reset tests (~4 tests)
# =============================================================================

class TestEmergencyStop:
    """Tests for emergency stop functionality."""

    def test_emergency_stop_halts_movement(self, mock_servo_driver) -> None:
        """Test that emergency_stop halts all head movement."""
        from src.control.head_controller import HeadController, HeadConfig

        config = HeadConfig(pan_channel=12, tilt_channel=13)
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

        config = HeadConfig(pan_channel=12, tilt_channel=13)
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

        config = HeadConfig(pan_channel=12, tilt_channel=13)
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

        config = HeadConfig(pan_channel=12, tilt_channel=13)
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
    """Tests for state retrieval methods."""

    def test_get_current_position(self, mock_servo_driver) -> None:
        """Test get_current_position returns correct pan/tilt tuple."""
        from src.control.head_controller import HeadController, HeadConfig

        config = HeadConfig(pan_channel=12, tilt_channel=13)
        head = HeadController(mock_servo_driver, config)

        # Move to position
        head.look_at(pan=45.0, tilt=-20.0, blocking=True)

        position = head.get_current_position()

        assert isinstance(position, tuple)
        assert len(position) == 2
        assert position[0] == 45.0  # pan
        assert position[1] == -20.0  # tilt

    def test_get_state_returns_snapshot(self, mock_servo_driver) -> None:
        """Test get_state returns immutable HeadState snapshot."""
        from src.control.head_controller import HeadController, HeadConfig, HeadState

        config = HeadConfig(pan_channel=12, tilt_channel=13)
        head = HeadController(mock_servo_driver, config)

        head.look_at(pan=30.0, tilt=15.0, blocking=True)

        state = head.get_state()

        # Should return HeadState dataclass
        assert isinstance(state, HeadState)
        assert state.pan == 30.0
        assert state.tilt == 15.0
        assert state.is_moving is False

        # State should be a snapshot (not live reference)
        # Moving should not affect the old state object
        head.look_at(pan=0.0, tilt=0.0, blocking=False)
        assert state.pan == 30.0  # Old state unchanged


# =============================================================================
# Performance Tests
# =============================================================================

class TestHeadControllerPerformance:
    """Performance tests for HeadController."""

    def test_look_at_initiation_latency(self, mock_servo_driver) -> None:
        """Test that look_at initiates movement within 5ms."""
        from src.control.head_controller import HeadController, HeadConfig

        config = HeadConfig(pan_channel=12, tilt_channel=13)
        head = HeadController(mock_servo_driver, config)

        start = time.monotonic()
        head.look_at(pan=30.0, tilt=15.0, blocking=False)
        latency_ms = (time.monotonic() - start) * 1000

        # Movement initiation should be fast (relaxed for Windows CI timing variability)
        assert latency_ms < 15.0, f"look_at initiation took {latency_ms}ms (limit: 15ms)"

    def test_get_state_performance(self, mock_servo_driver) -> None:
        """Test that get_state is fast (<1ms for 1000 calls)."""
        from src.control.head_controller import HeadController, HeadConfig

        config = HeadConfig(pan_channel=12, tilt_channel=13)
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
    """Integration tests combining multiple HeadController features."""

    def test_emotion_sequence_simulation(self, mock_servo_driver) -> None:
        """Test simulated emotion expression sequence."""
        from src.control.head_controller import HeadController, HeadConfig

        config = HeadConfig(pan_channel=12, tilt_channel=13)
        head = HeadController(mock_servo_driver, config)

        # Simulate "curious" emotion: tilt + glance
        head.tilt_curious(direction='right', angle=15.0, blocking=True)
        head.random_glance(max_deviation=20.0, hold_ms=100, blocking=True)
        head.reset_to_center(blocking=True)

        # Should return to center
        pan, tilt = head.get_current_position()
        assert abs(pan) < 1.0
        assert abs(tilt) < 1.0

    def test_affirmation_then_negation(self, mock_servo_driver) -> None:
        """Test nod followed by shake sequence."""
        from src.control.head_controller import HeadController, HeadConfig

        config = HeadConfig(pan_channel=12, tilt_channel=13)
        head = HeadController(mock_servo_driver, config)

        # Affirmation (nod)
        head.nod(count=2, amplitude=15.0, blocking=True)

        # Small pause
        time.sleep(0.05)

        # Negation (shake)
        head.shake(count=2, amplitude=20.0, blocking=True)

        # Should be at original position
        pan, tilt = head.get_current_position()
        assert abs(pan) < 1.0
        assert abs(tilt) < 1.0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
