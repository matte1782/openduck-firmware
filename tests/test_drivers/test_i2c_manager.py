"""Unit tests for I2C Bus Manager.

Tests cover:
- Singleton pattern enforcement
- Thread-safe bus access
- Context manager protocol
- Bus lock acquisition/release
- Multiple device coordination
"""

import pytest
import threading
import time
from unittest.mock import Mock, patch, MagicMock


@pytest.fixture
def mock_hardware():
    """Mock hardware dependencies for testing."""
    with patch('src.drivers.i2c_bus_manager.board') as mock_board, \
         patch('src.drivers.i2c_bus_manager.busio') as mock_busio:

        # Configure mocks
        mock_board.SCL = Mock()
        mock_board.SDA = Mock()
        mock_i2c = Mock()
        mock_busio.I2C.return_value = mock_i2c

        yield {
            'board': mock_board,
            'busio': mock_busio,
            'i2c': mock_i2c
        }


class TestI2CBusManagerSingleton:
    """Test singleton pattern implementation."""

    def test_singleton_same_instance(self, mock_hardware):
        """Verify only one I2C bus manager instance exists."""
        from src.drivers.i2c_bus_manager import I2CBusManager

        # Reset singleton for test isolation
        I2CBusManager._instance = None
        I2CBusManager._bus = None

        manager1 = I2CBusManager.get_instance()
        manager2 = I2CBusManager.get_instance()

        assert manager1 is manager2, "Singleton pattern violated - different instances returned"

    def test_singleton_thread_safe(self, mock_hardware):
        """Verify singleton is thread-safe during concurrent initialization."""
        from src.drivers.i2c_bus_manager import I2CBusManager

        # Reset singleton
        I2CBusManager._instance = None
        I2CBusManager._bus = None

        instances = []

        def get_manager():
            instances.append(I2CBusManager.get_instance())

        # Create multiple threads trying to get instance simultaneously
        threads = [threading.Thread(target=get_manager) for _ in range(10)]

        for thread in threads:
            thread.start()

        for thread in threads:
            thread.join()

        # All instances should be identical
        assert len(set(id(inst) for inst in instances)) == 1, \
            "Thread-safe singleton violated - multiple instances created"

    def test_multiple_get_instance_calls(self, mock_hardware):
        """Verify multiple get_instance() calls return same instance."""
        from src.drivers.i2c_bus_manager import I2CBusManager

        # Reset singleton
        I2CBusManager._instance = None
        I2CBusManager._bus = None

        # Multiple calls should return same instance
        manager1 = I2CBusManager.get_instance()
        manager2 = I2CBusManager.get_instance()
        manager3 = I2CBusManager.get_instance()

        # All should point to same singleton
        assert manager1 is manager2
        assert manager2 is manager3
        assert manager1 is manager3


class TestI2CBusLocking:
    """Test bus locking mechanisms."""

    def test_bus_lock_acquisition(self, mock_hardware):
        """Verify bus can be acquired and released."""
        from src.drivers.i2c_bus_manager import I2CBusManager

        # Reset singleton
        I2CBusManager._instance = None
        I2CBusManager._bus = None

        manager = I2CBusManager.get_instance()

        # Bus should be unlocked initially
        assert not manager.is_locked()

        # Acquire bus
        with manager.acquire_bus() as bus:
            # Bus should be locked
            assert manager.is_locked()
            assert bus is not None

        # Bus should be unlocked after context exit
        assert not manager.is_locked()

    def test_bus_lock_serialization(self, mock_hardware):
        """Verify bus access is serialized across threads."""
        from src.drivers.i2c_bus_manager import I2CBusManager

        # Reset singleton
        I2CBusManager._instance = None
        I2CBusManager._bus = None

        manager = I2CBusManager.get_instance()
        execution_order = []

        def device_operation(device_id: str, duration: float):
            """Simulate device I2C operation."""
            with manager.acquire_bus() as bus:
                execution_order.append(f"{device_id}_start")
                time.sleep(duration)
                execution_order.append(f"{device_id}_end")

        # Create threads for two devices accessing bus
        thread1 = threading.Thread(target=device_operation, args=("PCA9685", 0.05))
        thread2 = threading.Thread(target=device_operation, args=("BNO085", 0.05))

        thread1.start()
        time.sleep(0.01)  # Slight delay to ensure thread1 acquires first
        thread2.start()

        thread1.join()
        thread2.join()

        # Verify operations were serialized (no interleaving)
        # Should be: device1_start, device1_end, device2_start, device2_end
        # OR: device2_start, device2_end, device1_start, device1_end
        assert execution_order[0].endswith("_start")
        assert execution_order[1].endswith("_end")
        assert execution_order[2].endswith("_start")
        assert execution_order[3].endswith("_end")

        # Same device should complete before other starts
        device1_name = execution_order[0].split("_")[0]
        assert execution_order[1].startswith(device1_name)

    def test_nested_lock_acquisition(self, mock_hardware):
        """Verify nested lock acquisition from same thread works."""
        from src.drivers.i2c_bus_manager import I2CBusManager

        # Reset singleton
        I2CBusManager._instance = None
        I2CBusManager._bus = None

        manager = I2CBusManager.get_instance()

        # Nested acquisition should work (RLock behavior)
        with manager.acquire_bus() as bus1:
            assert manager.is_locked()
            with manager.acquire_bus() as bus2:
                assert manager.is_locked()
                assert bus1 is bus2
            assert manager.is_locked()

        assert not manager.is_locked()


class TestI2CBusManagerAPI:
    """Test manager API methods."""

    def test_get_bus_direct_access(self, mock_hardware):
        """Verify direct bus access for compatibility."""
        from src.drivers.i2c_bus_manager import I2CBusManager

        # Reset singleton
        I2CBusManager._instance = None
        I2CBusManager._bus = None

        manager = I2CBusManager.get_instance()
        bus = manager.get_bus()

        assert bus is not None
        assert bus is manager._bus

    def test_bus_initialization_once(self, mock_hardware):
        """Verify I2C bus is only initialized once."""
        from src.drivers.i2c_bus_manager import I2CBusManager

        # Reset singleton
        I2CBusManager._instance = None
        I2CBusManager._bus = None

        manager1 = I2CBusManager.get_instance()
        manager2 = I2CBusManager.get_instance()

        # busio.I2C should only be called once
        mock_hardware['busio'].I2C.assert_called_once()

    def test_exception_releases_lock(self, mock_hardware):
        """Verify lock is released even if exception occurs."""
        from src.drivers.i2c_bus_manager import I2CBusManager

        # Reset singleton
        I2CBusManager._instance = None
        I2CBusManager._bus = None

        manager = I2CBusManager.get_instance()

        # Simulate exception during bus operation
        try:
            with manager.acquire_bus() as bus:
                assert manager.is_locked()
                raise RuntimeError("Simulated I2C error")
        except RuntimeError:
            pass

        # Lock should be released
        assert not manager.is_locked()


class TestI2CBusManagerIntegration:
    """Integration tests simulating real device scenarios."""

    def test_multiple_devices_coordination(self, mock_hardware):
        """Test multiple devices sharing bus without collision."""
        from src.drivers.i2c_bus_manager import I2CBusManager

        # Reset singleton
        I2CBusManager._instance = None
        I2CBusManager._bus = None

        manager = I2CBusManager.get_instance()
        access_log = []

        def pca9685_write(channel: int, value: int):
            """Simulate PCA9685 servo write."""
            with manager.acquire_bus() as bus:
                access_log.append(f"PCA9685_write_ch{channel}")
                time.sleep(0.01)  # Simulate I2C transaction

        def bno085_read():
            """Simulate BNO085 IMU read."""
            with manager.acquire_bus() as bus:
                access_log.append("BNO085_read_imu")
                time.sleep(0.01)  # Simulate I2C transaction

        # Simulate concurrent device operations
        threads = [
            threading.Thread(target=pca9685_write, args=(0, 90)),
            threading.Thread(target=bno085_read),
            threading.Thread(target=pca9685_write, args=(1, 45)),
            threading.Thread(target=bno085_read),
        ]

        for thread in threads:
            thread.start()

        for thread in threads:
            thread.join()

        # Verify all operations completed
        assert len(access_log) == 4

        # Verify no corruption (all operations logged)
        assert access_log.count("BNO085_read_imu") == 2
        assert "PCA9685_write_ch0" in access_log
        assert "PCA9685_write_ch1" in access_log

    def test_high_frequency_access(self, mock_hardware):
        """Test manager under high-frequency access patterns."""
        from src.drivers.i2c_bus_manager import I2CBusManager

        # Reset singleton
        I2CBusManager._instance = None
        I2CBusManager._bus = None

        manager = I2CBusManager.get_instance()
        success_count = [0]

        def rapid_access(iterations: int):
            """Perform rapid bus access."""
            for _ in range(iterations):
                with manager.acquire_bus() as bus:
                    success_count[0] += 1

        # Multiple threads doing rapid access
        threads = [
            threading.Thread(target=rapid_access, args=(50,))
            for _ in range(4)
        ]

        for thread in threads:
            thread.start()

        for thread in threads:
            thread.join()

        # All 200 operations should succeed (4 threads × 50 iterations)
        assert success_count[0] == 200


class TestI2CBusManagerErrorHandling:
    """Test error handling scenarios."""

    def test_missing_hardware_libraries(self):
        """Test graceful handling when hardware libraries missing."""
        # Mock missing imports
        with patch('src.drivers.i2c_bus_manager.board', None), \
             patch('src.drivers.i2c_bus_manager.busio', None):

            from src.drivers.i2c_bus_manager import I2CBusManager

            # Reset singleton
            I2CBusManager._instance = None
            I2CBusManager._bus = None

            with pytest.raises(ImportError, match="Required libraries not installed"):
                I2CBusManager.get_instance()

    def test_i2c_initialization_failure(self, mock_hardware):
        """Test handling of I2C initialization failure."""
        from src.drivers.i2c_bus_manager import I2CBusManager

        # Reset singleton
        I2CBusManager._instance = None
        I2CBusManager._bus = None

        # Make I2C init fail
        mock_hardware['busio'].I2C.side_effect = RuntimeError("I2C bus not available")

        with pytest.raises(RuntimeError, match="Failed to initialize I2C bus"):
            I2CBusManager.get_instance()
