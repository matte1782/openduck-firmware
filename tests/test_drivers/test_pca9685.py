"""Unit tests for PCA9685 PWM driver.

Tests cover:
- Driver initialization
- Angle to pulse width conversion
- Channel state management
- Servo limit enforcement
- Multi-servo coordination
"""

import pytest
from unittest.mock import Mock, MagicMock, patch


# Mock hardware modules for testing on development machine
@pytest.fixture
def mock_hardware():
    """Mock hardware dependencies for testing."""
    with patch('src.drivers.servo.pca9685.board') as mock_board, \
         patch('src.drivers.servo.pca9685.busio') as mock_busio, \
         patch('src.drivers.servo.pca9685.PCA9685') as mock_pca9685_class:

        # Configure mocks
        mock_board.SCL = Mock()
        mock_board.SDA = Mock()
        mock_i2c = Mock()
        mock_busio.I2C.return_value = mock_i2c

        mock_pca = MagicMock()
        mock_pca9685_class.return_value = mock_pca

        # Mock channels
        mock_pca.channels = {i: Mock(duty_cycle=0) for i in range(16)}

        yield {
            'board': mock_board,
            'busio': mock_busio,
            'pca9685_class': mock_pca9685_class,
            'pca': mock_pca,
            'i2c': mock_i2c
        }


class TestPCA9685Driver:
    """Test cases for PCA9685Driver class."""

    def test_initialization_default(self, mock_hardware):
        """Test driver initializes with default parameters."""
        from src.drivers.servo.pca9685 import PCA9685Driver

        driver = PCA9685Driver()

        assert driver.address == 0x40
        assert driver.frequency == 50
        assert len(driver.channels) == 16

        # Verify I2C setup
        mock_hardware['busio'].I2C.assert_called_once()
        mock_hardware['pca9685_class'].assert_called_once()

    def test_initialization_custom_address(self, mock_hardware):
        """Test driver initializes with custom I2C address."""
        from src.drivers.servo.pca9685 import PCA9685Driver

        driver = PCA9685Driver(address=0x41, frequency=60)

        assert driver.address == 0x41
        assert driver.frequency == 60

    def test_angle_to_pulse_conversion(self, mock_hardware):
        """Test angle to pulse width conversion."""
        from src.drivers.servo.pca9685 import PCA9685Driver

        driver = PCA9685Driver()

        # Test boundary values
        assert driver._angle_to_pulse(0) == 1000    # 0° -> 1000μs
        assert driver._angle_to_pulse(90) == 1500   # 90° -> 1500μs
        assert driver._angle_to_pulse(180) == 2000  # 180° -> 2000μs

    def test_set_servo_angle_valid(self, mock_hardware):
        """Test setting servo to valid angle."""
        from src.drivers.servo.pca9685 import PCA9685Driver

        driver = PCA9685Driver()
        driver.set_servo_angle(0, 90)

        # Verify channel state updated
        assert driver.channels[0]['angle'] == 90
        assert driver.channels[0]['enabled'] is True

    def test_set_servo_angle_invalid_channel(self, mock_hardware):
        """Test setting servo on invalid channel raises error."""
        from src.drivers.servo.pca9685 import PCA9685Driver

        driver = PCA9685Driver()

        with pytest.raises(ValueError, match="Channel must be 0-15"):
            driver.set_servo_angle(16, 90)

    def test_set_servo_angle_invalid_angle(self, mock_hardware):
        """Test setting servo to invalid angle raises error."""
        from src.drivers.servo.pca9685 import PCA9685Driver

        driver = PCA9685Driver()

        with pytest.raises(ValueError, match="Angle must be 0-180"):
            driver.set_servo_angle(0, 200)

    def test_disable_channel(self, mock_hardware):
        """Test disabling a servo channel."""
        from src.drivers.servo.pca9685 import PCA9685Driver

        driver = PCA9685Driver()
        driver.set_servo_angle(0, 90)
        driver.disable_channel(0)

        assert driver.channels[0]['enabled'] is False

    def test_disable_all_channels(self, mock_hardware):
        """Test disabling all channels."""
        from src.drivers.servo.pca9685 import PCA9685Driver

        driver = PCA9685Driver()

        # Enable some channels
        driver.set_servo_angle(0, 90)
        driver.set_servo_angle(5, 45)
        driver.set_servo_angle(10, 135)

        # Disable all
        driver.disable_all()

        # Verify all disabled
        for i in range(16):
            assert driver.channels[i]['enabled'] is False

    def test_get_channel_state(self, mock_hardware):
        """Test retrieving channel state."""
        from src.drivers.servo.pca9685 import PCA9685Driver

        driver = PCA9685Driver()
        driver.set_servo_angle(3, 120)

        state = driver.get_channel_state(3)

        assert state['angle'] == 120
        assert state['enabled'] is True


class TestServoController:
    """Test cases for ServoController class."""

    def test_servo_limits_enforcement(self, mock_hardware):
        """Test servo angle limits are enforced."""
        from src.drivers.servo.pca9685 import PCA9685Driver, ServoController

        driver = PCA9685Driver()
        controller = ServoController(driver)

        # Set limits
        controller.set_servo_limits(0, 30, 150)

        # Valid angle should work
        controller.move_servo(0, 90)

        # Invalid angle should raise error
        with pytest.raises(ValueError, match="outside limits"):
            controller.move_servo(0, 200)

    def test_move_multiple_servos(self, mock_hardware):
        """Test moving multiple servos simultaneously."""
        from src.drivers.servo.pca9685 import PCA9685Driver, ServoController

        driver = PCA9685Driver()
        controller = ServoController(driver)

        moves = {0: 45, 1: 90, 2: 135}
        controller.move_multiple(moves)

        # Verify all moved
        assert driver.channels[0]['angle'] == 45
        assert driver.channels[1]['angle'] == 90
        assert driver.channels[2]['angle'] == 135

    def test_sweep_motion(self, mock_hardware):
        """Test servo sweep through range."""
        from src.drivers.servo.pca9685 import PCA9685Driver, ServoController

        driver = PCA9685Driver()
        controller = ServoController(driver)

        # Sweep servo from 0 to 180 in 4 steps
        controller.sweep(0, 0, 180, 4, 0.01)

        # Verify final position
        state = driver.get_channel_state(0)
        assert state['enabled'] is True
        # Final angle should be near 180
        assert 170 <= state['angle'] <= 180
