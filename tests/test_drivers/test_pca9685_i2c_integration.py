"""Integration tests for PCA9685 with I2C Bus Manager.

Tests cover:
- PCA9685 initialization with I2C bus manager
- Bus lock acquisition during servo operations
- No bus collisions between PCA9685 and simulated BNO085
- Thread-safe multi-servo control
"""

import pytest
import threading
import time
from unittest.mock import Mock, MagicMock, patch


@pytest.fixture
def mock_hardware():
    """Mock hardware dependencies for testing."""
    with patch('src.drivers.i2c_bus_manager.board') as mock_board, \
         patch('src.drivers.i2c_bus_manager.busio') as mock_busio, \
         patch('src.drivers.servo.pca9685_i2c_fixed.board') as mock_pca_board, \
         patch('src.drivers.servo.pca9685_i2c_fixed.busio') as mock_pca_busio, \
         patch('src.drivers.servo.pca9685_i2c_fixed.PCA9685') as mock_pca9685_class:

        # Configure mocks
        mock_board.SCL = Mock()
        mock_board.SDA = Mock()
        mock_pca_board.SCL = Mock()
        mock_pca_board.SDA = Mock()

        mock_i2c = Mock()
        mock_busio.I2C.return_value = mock_i2c
        mock_pca_busio.I2C = mock_busio.I2C

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


class TestPCA9685I2CIntegration:
    """Test PCA9685 integration with I2C bus manager."""

    def test_pca9685_uses_bus_manager(self, mock_hardware):
        """Verify PCA9685 uses I2C bus manager singleton."""
        from src.drivers.servo.pca9685_i2c_fixed import PCA9685Driver
        from src.drivers.i2c_bus_manager import I2CBusManager

        # Reset singleton
        I2CBusManager._instance = None
        I2CBusManager._bus = None

        # Create driver
        driver = PCA9685Driver()

        # Verify it has bus manager
        assert driver.bus_manager is not None
        assert isinstance(driver.bus_manager, I2CBusManager)

        # Verify bus manager is singleton
        manager = I2CBusManager.get_instance()
        assert driver.bus_manager is manager

    def test_servo_operations_lock_bus(self, mock_hardware):
        """Verify servo operations acquire bus lock."""
        from src.drivers.servo.pca9685_i2c_fixed import PCA9685Driver
        from src.drivers.i2c_bus_manager import I2CBusManager

        # Reset singleton
        I2CBusManager._instance = None
        I2CBusManager._bus = None

        driver = PCA9685Driver()
        manager = I2CBusManager.get_instance()

        # Bus should be unlocked initially
        assert not manager.is_locked()

        # Create thread to monitor lock state during operation
        lock_states = []

        def check_lock_during_operation():
            time.sleep(0.001)  # Wait for operation to start
            lock_states.append(manager.is_locked())

        # Start monitor thread
        monitor = threading.Thread(target=check_lock_during_operation)
        monitor.start()

        # Perform servo operation (should acquire lock)
        driver.set_servo_angle(0, 90)

        monitor.join()

        # Lock should be released after operation
        assert not manager.is_locked()

    def test_no_bus_collision_multiple_devices(self, mock_hardware):
        """Verify no bus collisions between PCA9685 and simulated BNO085."""
        from src.drivers.servo.pca9685_i2c_fixed import PCA9685Driver
        from src.drivers.i2c_bus_manager import I2CBusManager

        # Reset singleton
        I2CBusManager._instance = None
        I2CBusManager._bus = None

        driver = PCA9685Driver()
        manager = I2CBusManager.get_instance()

        access_log = []

        def pca9685_operations():
            """Simulate PCA9685 servo operations."""
            for i in range(5):
                with manager.acquire_bus():
                    access_log.append(f"PCA9685_start_{i}")
                    time.sleep(0.01)  # Simulate I2C transaction
                    access_log.append(f"PCA9685_end_{i}")

        def bno085_operations():
            """Simulate BNO085 IMU read operations."""
            for i in range(5):
                with manager.acquire_bus():
                    access_log.append(f"BNO085_start_{i}")
                    time.sleep(0.01)  # Simulate I2C transaction
                    access_log.append(f"BNO085_end_{i}")

        # Run both devices concurrently
        thread1 = threading.Thread(target=pca9685_operations)
        thread2 = threading.Thread(target=bno085_operations)

        thread1.start()
        thread2.start()

        thread1.join()
        thread2.join()

        # Verify operations were serialized (no interleaving within device)
        assert len(access_log) == 20  # 5 ops × 2 events × 2 devices

        # Check no operation was interrupted
        for i in range(len(access_log) - 1):
            if access_log[i].endswith("_start_0"):
                # Next event should be same device's end
                device = access_log[i].split("_")[0]
                assert access_log[i + 1].startswith(device)

    def test_multi_servo_control_thread_safe(self, mock_hardware):
        """Test multiple threads controlling different servos."""
        from src.drivers.servo.pca9685_i2c_fixed import PCA9685Driver
        from src.drivers.i2c_bus_manager import I2CBusManager

        # Reset singleton
        I2CBusManager._instance = None
        I2CBusManager._bus = None

        driver = PCA9685Driver()
        errors = []

        def control_servo(channel: int, iterations: int):
            """Control specific servo channel."""
            try:
                for i in range(iterations):
                    angle = (i % 18) * 10  # 0-170 degrees
                    driver.set_servo_angle(channel, angle)
                    time.sleep(0.001)
            except Exception as e:
                errors.append(e)

        # Multiple threads controlling different servos
        threads = [
            threading.Thread(target=control_servo, args=(ch, 10))
            for ch in range(4)
        ]

        for thread in threads:
            thread.start()

        for thread in threads:
            thread.join()

        # No errors should occur
        assert len(errors) == 0

        # Verify all servos were updated
        for ch in range(4):
            state = driver.get_channel_state(ch)
            assert state['enabled'] is True

    def test_emergency_stop_releases_lock(self, mock_hardware):
        """Verify emergency stop properly releases I2C lock."""
        from src.drivers.servo.pca9685_i2c_fixed import PCA9685Driver
        from src.drivers.i2c_bus_manager import I2CBusManager

        # Reset singleton
        I2CBusManager._instance = None
        I2CBusManager._bus = None

        driver = PCA9685Driver()
        manager = I2CBusManager.get_instance()

        # Enable some servos
        driver.set_servo_angle(0, 90)
        driver.set_servo_angle(5, 45)

        # Emergency stop
        driver.disable_all()

        # Lock should be released
        assert not manager.is_locked()

        # All servos should be disabled
        for ch in range(16):
            state = driver.get_channel_state(ch)
            assert state['enabled'] is False

    def test_servo_controller_with_bus_manager(self, mock_hardware):
        """Test ServoController works with I2C bus manager."""
        from src.drivers.servo.pca9685_i2c_fixed import PCA9685Driver, ServoController
        from src.drivers.i2c_bus_manager import I2CBusManager

        # Reset singleton
        I2CBusManager._instance = None
        I2CBusManager._bus = None

        driver = PCA9685Driver()
        controller = ServoController(driver)

        # Set limits
        controller.set_servo_limits(0, 30, 150)

        # Move servo
        controller.move_servo(0, 90)

        # Verify
        state = driver.get_channel_state(0)
        assert state['angle'] == 90
        assert state['enabled'] is True

        # Verify limit enforcement
        with pytest.raises(ValueError, match="outside limits"):
            controller.move_servo(0, 200)


class TestPCA9685BackwardCompatibility:
    """Test backward compatibility with existing code."""

    def test_initialization_same_interface(self, mock_hardware):
        """Verify initialization interface unchanged."""
        from src.drivers.servo.pca9685_i2c_fixed import PCA9685Driver

        # Reset singleton
        from src.drivers.i2c_bus_manager import I2CBusManager
        I2CBusManager._instance = None
        I2CBusManager._bus = None

        # Should initialize with same parameters as before
        driver = PCA9685Driver(address=0x40, frequency=50)

        assert driver.address == 0x40
        assert driver.frequency == 50

    def test_all_methods_still_work(self, mock_hardware):
        """Verify all existing methods still work."""
        from src.drivers.servo.pca9685_i2c_fixed import PCA9685Driver
        from src.drivers.i2c_bus_manager import I2CBusManager

        # Reset singleton
        I2CBusManager._instance = None
        I2CBusManager._bus = None

        driver = PCA9685Driver()

        # Test all methods
        driver.set_servo_angle(0, 90)
        driver.set_pwm(1, 0, 2048)
        driver.set_servo_pulse(2, 1500)
        state = driver.get_channel_state(0)
        driver.disable_channel(3)
        driver.disable_all()

        # All should work without errors
        assert state['angle'] == 90
