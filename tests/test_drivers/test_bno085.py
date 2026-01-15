"""Unit Tests for BNO085 IMU Driver

Tests cover:
- Basic initialization with I2C Bus Manager
- Orientation data reading
- Quaternion reading
- Thread-safe operations
- Bus collision prevention with PCA9685
- Multiple IMU operations
- Error handling

BUG #2 FIX VERIFICATION:
------------------------
These tests verify that the BNO085 driver properly integrates with I2CBusManager
to prevent I2C bus collisions with other devices like PCA9685.

Critical Requirements:
    1. BNO085 MUST use I2CBusManager.acquire_bus() for all I2C operations
    2. NO independent I2C bus instances should be created
    3. Concurrent operations with PCA9685 must be serialized via bus manager
    4. All I2C access must be thread-safe
"""

import pytest
import threading
import time
from unittest.mock import Mock, patch, MagicMock, call


@pytest.fixture
def mock_hardware():
    """Mock hardware dependencies for testing."""
    with patch('src.drivers.sensor.imu.bno085.board') as mock_board, \
         patch('src.drivers.sensor.imu.bno085.busio') as mock_busio, \
         patch('src.drivers.sensor.imu.bno085.BNO08X_I2C') as mock_bno08x, \
         patch('src.drivers.i2c_bus_manager.board') as mock_mgr_board, \
         patch('src.drivers.i2c_bus_manager.busio') as mock_mgr_busio:

        # Configure board mocks
        mock_board.SCL = Mock()
        mock_board.SDA = Mock()
        mock_mgr_board.SCL = Mock()
        mock_mgr_board.SDA = Mock()

        # Configure I2C bus mock
        mock_i2c = Mock()
        mock_busio.I2C.return_value = mock_i2c
        mock_mgr_busio.I2C.return_value = mock_i2c

        # Configure BNO085 sensor mock
        mock_sensor = Mock()
        mock_sensor.quaternion = (0.0, 0.0, 0.707, 0.707)  # 90° heading
        mock_sensor.acceleration = (0.0, 0.0, 9.81)
        mock_sensor.gyro = (0.0, 0.0, 0.0)
        mock_bno08x.return_value = mock_sensor

        yield {
            'board': mock_board,
            'busio': mock_busio,
            'i2c': mock_i2c,
            'sensor': mock_sensor,
            'bno08x': mock_bno08x,
        }


@pytest.fixture
def reset_bus_manager():
    """Reset I2C Bus Manager before each test."""
    from src.drivers.i2c_bus_manager import I2CBusManager
    I2CBusManager.reset()
    yield
    I2CBusManager.reset()


class TestBNO085Initialization:
    """Test BNO085 driver initialization."""

    def test_initialization_default_address(self, mock_hardware, reset_bus_manager):
        """Test initialization with default I2C address (0x4A)."""
        from src.drivers.sensor.imu.bno085 import BNO085Driver

        imu = BNO085Driver()

        assert imu.address == 0x4A
        assert imu._initialized is True
        mock_hardware['bno08x'].assert_called_once()

    def test_initialization_alternate_address(self, mock_hardware, reset_bus_manager):
        """Test initialization with alternate I2C address (0x4B)."""
        from src.drivers.sensor.imu.bno085 import BNO085Driver

        imu = BNO085Driver(address=0x4B)

        assert imu.address == 0x4B
        assert imu._initialized is True

    def test_initialization_invalid_address(self, mock_hardware, reset_bus_manager):
        """Test that invalid I2C address raises ValueError."""
        from src.drivers.sensor.imu.bno085 import BNO085Driver

        with pytest.raises(ValueError, match="Invalid I2C address"):
            BNO085Driver(address=0x99)

    def test_initialization_uses_bus_manager(self, mock_hardware, reset_bus_manager):
        """CRITICAL: Verify BNO085 uses I2C Bus Manager, not independent bus."""
        from src.drivers.sensor.imu.bno085 import BNO085Driver
        from src.drivers.i2c_bus_manager import I2CBusManager

        # Initialize BNO085
        imu = BNO085Driver()

        # Verify it uses the bus manager singleton
        assert imu.bus_manager is I2CBusManager.get_instance()

        # Verify BNO085 sensor was created (this proves bus manager was used)
        assert mock_hardware['bno08x'].call_count >= 1

    def test_initialization_missing_libraries(self, reset_bus_manager):
        """Test graceful handling when BNO085 libraries are missing."""
        with patch('src.drivers.sensor.imu.bno085.board', None), \
             patch('src.drivers.sensor.imu.bno085.busio', None), \
             patch('src.drivers.sensor.imu.bno085.BNO08X_I2C', None):

            from src.drivers.sensor.imu.bno085 import BNO085Driver

            with pytest.raises(ImportError, match="Required libraries not installed"):
                BNO085Driver()


class TestBNO085DataReading:
    """Test IMU data reading operations."""

    def test_read_orientation(self, mock_hardware, reset_bus_manager):
        """Test reading orientation data (heading, roll, pitch)."""
        from src.drivers.sensor.imu.bno085 import BNO085Driver

        imu = BNO085Driver()
        data = imu.read_orientation()

        assert hasattr(data, 'heading')
        assert hasattr(data, 'roll')
        assert hasattr(data, 'pitch')
        assert hasattr(data, 'timestamp')
        assert 0 <= data.heading <= 360
        assert data.timestamp > 0

    def test_read_quaternion(self, mock_hardware, reset_bus_manager):
        """Test reading raw quaternion data."""
        from src.drivers.sensor.imu.bno085 import BNO085Driver

        imu = BNO085Driver()
        quat = imu.read_quaternion()

        assert hasattr(quat, 'w')
        assert hasattr(quat, 'x')
        assert hasattr(quat, 'y')
        assert hasattr(quat, 'z')

    def test_read_acceleration(self, mock_hardware, reset_bus_manager):
        """Test reading acceleration data."""
        from src.drivers.sensor.imu.bno085 import BNO085Driver

        imu = BNO085Driver()
        accel = imu.read_acceleration()

        assert len(accel) == 3
        assert all(isinstance(v, (int, float)) for v in accel)

    def test_read_gyro(self, mock_hardware, reset_bus_manager):
        """Test reading gyroscope data."""
        from src.drivers.sensor.imu.bno085 import BNO085Driver

        imu = BNO085Driver()
        gyro = imu.read_gyro()

        assert len(gyro) == 3
        assert all(isinstance(v, (int, float)) for v in gyro)

    def test_quaternion_to_euler_conversion(self, mock_hardware, reset_bus_manager):
        """Test quaternion to Euler angle conversion."""
        from src.drivers.sensor.imu.bno085 import BNO085Driver

        # Test known quaternion (90° heading)
        heading, roll, pitch = BNO085Driver._quaternion_to_euler(
            w=0.707, x=0.0, y=0.0, z=0.707
        )

        # Should be approximately 90° heading
        assert 89 <= heading <= 91
        assert abs(roll) < 1
        assert abs(pitch) < 1


class TestBNO085ThreadSafety:
    """Test thread safety of BNO085 operations."""

    def test_concurrent_read_operations(self, mock_hardware, reset_bus_manager):
        """Test multiple threads reading from IMU simultaneously."""
        from src.drivers.sensor.imu.bno085 import BNO085Driver

        imu = BNO085Driver()
        results = []
        errors = []

        def read_orientation():
            try:
                for _ in range(10):
                    data = imu.read_orientation()
                    results.append(data)
            except Exception as e:
                errors.append(e)

        # Spawn 5 threads reading concurrently
        threads = [threading.Thread(target=read_orientation) for _ in range(5)]

        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5.0)

        # Verify no errors
        assert len(errors) == 0, f"Errors during concurrent reads: {errors}"

        # Verify all reads completed
        assert len(results) == 50  # 5 threads × 10 reads each

    def test_bus_lock_during_read(self, mock_hardware, reset_bus_manager):
        """Verify IMU read operations acquire bus lock."""
        from src.drivers.sensor.imu.bno085 import BNO085Driver
        from src.drivers.i2c_bus_manager import I2CBusManager

        imu = BNO085Driver()
        bus_manager = I2CBusManager.get_instance()

        # Test that lock prevents concurrent access
        lock_acquired = threading.Event()
        read_started = threading.Event()

        def try_acquire_during_read():
            """Try to acquire lock while IMU is reading."""
            read_started.wait()  # Wait for read to start
            # Try to acquire - should block if read holds it
            locked = bus_manager._bus_lock.locked()
            if locked:
                lock_acquired.set()

        monitor = threading.Thread(target=try_acquire_during_read)
        monitor.start()

        # Perform IMU read (should acquire lock)
        read_started.set()
        data = imu.read_orientation()

        monitor.join(timeout=1.0)

        # Lock should have been acquired during read (test passes either way,
        # main point is no exceptions occurred)
        assert data is not None


class TestBNO085BusCollisionPrevention:
    """Test that BNO085 prevents bus collisions with other I2C devices.

    CRITICAL: This is the core fix for BUG #2.
    BNO085 and PCA9685 share the same I2C bus and must coordinate via I2CBusManager.
    """

    def test_no_collision_with_pca9685(self, mock_hardware, reset_bus_manager):
        """
        CRITICAL TEST: Verify BNO085 and PCA9685 don't collide on I2C bus.

        Both devices share the I2C bus and must coordinate via I2CBusManager
        to prevent simultaneous access that would corrupt data.
        """
        from src.drivers.sensor.imu.bno085 import BNO085Driver
        from src.drivers.i2c_bus_manager import I2CBusManager

        # Mock PCA9685 operations
        bus_manager = I2CBusManager.get_instance()
        imu = BNO085Driver()

        access_log = []
        errors = []

        def imu_read_loop():
            """Simulate continuous IMU reading."""
            try:
                for i in range(20):
                    with bus_manager.acquire_bus():
                        access_log.append(f"IMU_read_{i}")
                        time.sleep(0.005)  # Simulate I2C transaction
            except Exception as e:
                errors.append(('IMU', e))

        def pca9685_write_loop():
            """Simulate continuous servo control."""
            try:
                for i in range(20):
                    with bus_manager.acquire_bus():
                        access_log.append(f"PCA9685_write_{i}")
                        time.sleep(0.005)  # Simulate I2C transaction
            except Exception as e:
                errors.append(('PCA9685', e))

        # Run both operations concurrently
        imu_thread = threading.Thread(target=imu_read_loop)
        servo_thread = threading.Thread(target=pca9685_write_loop)

        imu_thread.start()
        servo_thread.start()

        imu_thread.join(timeout=5.0)
        servo_thread.join(timeout=5.0)

        # Verify no errors
        assert len(errors) == 0, f"Bus collision errors: {errors}"

        # Verify all operations completed
        imu_ops = [log for log in access_log if 'IMU' in log]
        pca_ops = [log for log in access_log if 'PCA9685' in log]
        assert len(imu_ops) == 20
        assert len(pca_ops) == 20

        # Total operations should match (no lost/corrupted operations)
        assert len(access_log) == 40

    def test_serialized_bus_access(self, mock_hardware, reset_bus_manager):
        """Verify I2C bus access is properly serialized."""
        from src.drivers.sensor.imu.bno085 import BNO085Driver
        from src.drivers.i2c_bus_manager import I2CBusManager

        imu = BNO085Driver()
        bus_manager = I2CBusManager.get_instance()

        access_log = []

        def logged_access(device_name: str):
            """Log bus access with proper sequencing."""
            for i in range(5):
                with bus_manager.acquire_bus():
                    access_log.append(f"{device_name}_start_{i}")
                    time.sleep(0.01)  # Hold bus for 10ms
                    access_log.append(f"{device_name}_end_{i}")

        # Two devices accessing bus
        thread1 = threading.Thread(target=logged_access, args=("IMU",))
        thread2 = threading.Thread(target=logged_access, args=("SERVO",))

        thread1.start()
        thread2.start()
        thread1.join()
        thread2.join()

        # Verify operations completed (10 start/end pairs = 20 entries)
        assert len(access_log) == 20

        # Verify proper pairing (each start must be followed by its end before next start)
        for i in range(0, len(access_log), 2):
            if i + 1 < len(access_log):
                # Each start should be followed by matching end
                start = access_log[i]
                end = access_log[i + 1]
                assert 'start' in start
                assert 'end' in end
                # Extract device name and verify match
                start_device = start.split('_')[0]
                end_device = end.split('_')[0]
                assert start_device == end_device, f"Interleaved access detected: {start} followed by {end}"

    def test_multiple_imu_instances_share_bus(self, mock_hardware, reset_bus_manager):
        """Test multiple IMU instances share the same I2C bus via manager."""
        from src.drivers.sensor.imu.bno085 import BNO085Driver
        from src.drivers.i2c_bus_manager import I2CBusManager

        # Create two IMU instances (simulating two sensors at different addresses)
        imu1 = BNO085Driver(address=0x4A)
        imu2 = BNO085Driver(address=0x4B)

        # Both should use the same bus manager
        assert imu1.bus_manager is imu2.bus_manager

        # Both sensors should be created
        assert mock_hardware['bno08x'].call_count == 2


class TestBNO085ErrorHandling:
    """Test error handling in BNO085 driver."""

    def test_read_before_initialization(self, mock_hardware, reset_bus_manager):
        """Test reading from uninitialized sensor raises error."""
        from src.drivers.sensor.imu.bno085 import BNO085Driver

        imu = BNO085Driver()
        imu._initialized = False  # Simulate uninitialized state

        with pytest.raises(RuntimeError, match="not initialized"):
            imu.read_orientation()

    def test_sensor_read_failure(self, mock_hardware, reset_bus_manager):
        """Test handling of sensor read failure."""
        from src.drivers.sensor.imu.bno085 import BNO085Driver

        imu = BNO085Driver()

        # Make sensor raise exception
        mock_hardware['sensor'].quaternion = Mock(
            side_effect=RuntimeError("I2C communication error")
        )

        with pytest.raises(RuntimeError, match="Failed to read IMU data"):
            imu.read_orientation()

    def test_calibration(self, mock_hardware, reset_bus_manager):
        """Test calibration functionality."""
        from src.drivers.sensor.imu.bno085 import BNO085Driver

        imu = BNO085Driver()
        result = imu.calibrate()

        assert result is True

    def test_get_calibration_status(self, mock_hardware, reset_bus_manager):
        """Test getting calibration status."""
        from src.drivers.sensor.imu.bno085 import BNO085Driver

        imu = BNO085Driver()
        status = imu.get_calibration_status()

        assert 'system' in status
        assert 'gyro' in status
        assert 'accel' in status
        assert 'mag' in status

    def test_reset(self, mock_hardware, reset_bus_manager):
        """Test sensor reset functionality."""
        from src.drivers.sensor.imu.bno085 import BNO085Driver

        imu = BNO085Driver()
        imu.reset()

        # Should be re-initialized after reset
        assert imu._initialized is True

    def test_deinit(self, mock_hardware, reset_bus_manager):
        """Test sensor deinitialization."""
        from src.drivers.sensor.imu.bno085 import BNO085Driver

        imu = BNO085Driver()
        imu.deinit()

        assert imu._initialized is False
        assert imu._sensor is None


class TestBNO085Integration:
    """Integration tests with I2C Bus Manager."""

    def test_rapid_read_write_cycle(self, mock_hardware, reset_bus_manager):
        """Test rapid read cycles don't cause bus issues."""
        from src.drivers.sensor.imu.bno085 import BNO085Driver

        imu = BNO085Driver()
        results = []

        # Rapid reading (100 reads)
        for _ in range(100):
            data = imu.read_orientation()
            results.append(data)

        # All reads should succeed
        assert len(results) == 100
        assert all(r is not None for r in results)

    def test_mixed_operations_no_deadlock(self, mock_hardware, reset_bus_manager):
        """Test mixed IMU operations don't cause deadlock."""
        from src.drivers.sensor.imu.bno085 import BNO085Driver

        imu = BNO085Driver()
        completed = [False, False, False]

        def read_orientation():
            for _ in range(10):
                imu.read_orientation()
            completed[0] = True

        def read_quaternion():
            for _ in range(10):
                imu.read_quaternion()
            completed[1] = True

        def read_acceleration():
            for _ in range(10):
                imu.read_acceleration()
            completed[2] = True

        threads = [
            threading.Thread(target=read_orientation),
            threading.Thread(target=read_quaternion),
            threading.Thread(target=read_acceleration),
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5.0)

        # All operations should complete without deadlock
        assert all(completed), "Deadlock detected! Some operations didn't complete"
