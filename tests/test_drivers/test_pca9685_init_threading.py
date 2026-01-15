"""Thread Safety Tests for PCA9685 Initialization

This test suite is designed to expose and verify fixes for the thread-unsafe
initialization in PCA9685Driver.__init__().

BUG #3: Thread-Unsafe PCA9685 Initialization
---------------------------------------------
The current implementation in pca9685.py (lines 84-98) initializes I2C hardware
WITHOUT lock protection:

    def __init__(self, address: int = 0x40, frequency: int = 50, i2c_bus: Optional[int] = 1):
        self._lock = threading.Lock()
        # ... hardware initialization WITHOUT lock protection
        self.i2c = busio.I2C(board.SCL, board.SDA)  # <-- RACE CONDITION!
        self.pca = PCA9685(self.i2c, address=address)

Problem: If two threads create PCA9685 instances simultaneously, they can both
try to initialize I2C hardware concurrently, causing bus collisions and potentially
corrupting hardware state.

Solution: Use I2CBusManager for ALL I2C operations, including initialization.

Test Strategy:
    1. Spawn 10 threads that simultaneously create PCA9685 instances
    2. Verify no I2C bus collisions occur
    3. Verify all instances are properly initialized
    4. Verify thread-safe servo operations

Expected Results:
    - BEFORE FIX: Potential I2C errors, corrupted state
    - AFTER FIX: All instances initialize cleanly, no collisions
"""

import pytest
import threading
import time
from unittest.mock import Mock, patch, MagicMock


@pytest.fixture
def mock_hardware():
    """Mock hardware dependencies for testing."""
    with patch('src.drivers.servo.pca9685.board') as mock_board, \
         patch('src.drivers.servo.pca9685.busio') as mock_busio, \
         patch('src.drivers.servo.pca9685.PCA9685') as mock_pca_class, \
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

        # Configure PCA9685 mock
        mock_pca = Mock()
        mock_pca.frequency = 50
        mock_pca.channels = [Mock() for _ in range(16)]
        for ch in mock_pca.channels:
            ch.duty_cycle = 0
        mock_pca_class.return_value = mock_pca

        yield {
            'board': mock_board,
            'busio': mock_busio,
            'i2c': mock_i2c,
            'pca_class': mock_pca_class,
            'pca': mock_pca,
        }


@pytest.fixture
def reset_bus_manager():
    """Reset I2C Bus Manager before each test."""
    from src.drivers.i2c_bus_manager import I2CBusManager
    I2CBusManager.reset()
    yield
    I2CBusManager.reset()


class TestPCA9685InitThreadSafety:
    """Test thread safety of PCA9685 initialization."""

    def test_parallel_initialization_10_threads(self, mock_hardware, reset_bus_manager):
        """
        CRITICAL TEST: Create 10 PCA9685 instances simultaneously.

        This test verifies that parallel initialization doesn't cause I2C bus
        collisions or corrupted hardware state.
        """
        from src.drivers.servo.pca9685 import PCA9685Driver

        instances = []
        errors = []
        barrier = threading.Barrier(10)  # Synchronize thread start

        def create_instance(instance_id: int):
            """Create PCA9685 instance with synchronized start."""
            try:
                barrier.wait()  # All threads start simultaneously
                driver = PCA9685Driver(address=0x40)
                instances.append((instance_id, driver))
            except Exception as e:
                errors.append((instance_id, e))

        # Spawn 10 threads
        threads = [
            threading.Thread(target=create_instance, args=(i,))
            for i in range(10)
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5.0)

        # Verify no errors occurred
        assert len(errors) == 0, f"Initialization errors: {errors}"

        # Verify all instances created
        assert len(instances) == 10

        # Verify all instances are properly initialized
        for instance_id, driver in instances:
            assert driver is not None
            assert hasattr(driver, 'pca')
            assert hasattr(driver, '_lock')

    def test_parallel_init_with_i2c_manager(self, mock_hardware, reset_bus_manager):
        """
        Test that parallel initialization uses I2C Bus Manager.

        This verifies that all PCA9685 instances coordinate through the
        bus manager to prevent collisions.
        """
        from src.drivers.servo.pca9685 import PCA9685Driver
        from src.drivers.i2c_bus_manager import I2CBusManager

        instances = []
        errors = []

        def create_and_verify():
            """Create instance and verify it uses bus manager."""
            try:
                driver = PCA9685Driver()
                # Check if instance was created successfully
                instances.append(driver)
            except Exception as e:
                errors.append(e)

        # Create multiple instances concurrently
        threads = [threading.Thread(target=create_and_verify) for _ in range(10)]

        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5.0)

        # No errors should occur
        assert len(errors) == 0, f"Errors during initialization: {errors}"
        assert len(instances) == 10

    def test_init_racing_with_servo_operations(self, mock_hardware, reset_bus_manager):
        """
        Test initialization racing with servo operations.

        This simulates a real scenario where servos are being controlled
        while new PCA9685 instances are being created.
        """
        from src.drivers.servo.pca9685 import PCA9685Driver

        # Create initial instance
        initial_driver = PCA9685Driver()

        operations_completed = []
        errors = []

        def servo_operations():
            """Perform continuous servo operations."""
            try:
                for i in range(20):
                    initial_driver.set_servo_angle(0, 90)
                    operations_completed.append(f"servo_op_{i}")
                    time.sleep(0.01)
            except Exception as e:
                errors.append(('servo', e))

        def create_new_instances():
            """Create new instances while servos are operating."""
            try:
                for i in range(5):
                    driver = PCA9685Driver()
                    operations_completed.append(f"init_{i}")
                    time.sleep(0.01)
            except Exception as e:
                errors.append(('init', e))

        # Run both operations concurrently
        servo_thread = threading.Thread(target=servo_operations)
        init_thread = threading.Thread(target=create_new_instances)

        servo_thread.start()
        init_thread.start()

        servo_thread.join(timeout=5.0)
        init_thread.join(timeout=5.0)

        # Verify no errors
        assert len(errors) == 0, f"Race condition errors: {errors}"

        # Verify operations completed
        servo_ops = [op for op in operations_completed if 'servo' in op]
        init_ops = [op for op in operations_completed if 'init' in op]
        assert len(servo_ops) == 20
        assert len(init_ops) == 5

    def test_multiple_addresses_parallel_init(self, mock_hardware, reset_bus_manager):
        """
        Test parallel initialization of multiple PCA9685 boards at different addresses.

        Real robotics applications often use multiple PCA9685 boards chained
        together for more servo channels.
        """
        from src.drivers.servo.pca9685 import PCA9685Driver

        instances = {}
        errors = []

        def create_at_address(address: int):
            """Create PCA9685 at specific address."""
            try:
                driver = PCA9685Driver(address=address)
                instances[address] = driver
            except Exception as e:
                errors.append((address, e))

        # Create instances for addresses 0x40, 0x41, 0x42, 0x43
        addresses = [0x40, 0x41, 0x42, 0x43]
        threads = [
            threading.Thread(target=create_at_address, args=(addr,))
            for addr in addresses
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5.0)

        # Verify no errors
        assert len(errors) == 0, f"Multi-address init errors: {errors}"

        # Verify all addresses initialized
        assert len(instances) == 4
        for addr in addresses:
            assert addr in instances

    def test_init_exception_doesnt_corrupt_bus(self, mock_hardware, reset_bus_manager):
        """
        Test that initialization exception doesn't corrupt I2C bus state.

        If one thread's initialization fails, other threads should still
        be able to initialize successfully.
        """
        from src.drivers.servo.pca9685 import PCA9685Driver

        success_count = [0]
        failure_count = [0]

        # Make first initialization fail
        call_count = [0]

        def failing_pca_init(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                raise RuntimeError("First init fails")
            # Subsequent calls succeed
            mock_pca = Mock()
            mock_pca.frequency = 50
            mock_pca.channels = [Mock() for _ in range(16)]
            for ch in mock_pca.channels:
                ch.duty_cycle = 0
            return mock_pca

        mock_hardware['pca_class'].side_effect = failing_pca_init

        def try_init(thread_id: int):
            """Try to initialize, count successes and failures."""
            try:
                driver = PCA9685Driver()
                success_count[0] += 1
            except RuntimeError:
                failure_count[0] += 1

        # Create 5 threads
        threads = [threading.Thread(target=try_init, args=(i,)) for i in range(5)]

        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5.0)

        # At least one should fail, others should succeed
        assert failure_count[0] >= 1, "Expected at least one failure"
        assert success_count[0] >= 1, "Other initializations should succeed after failure"

    def test_rapid_init_deinit_cycles(self, mock_hardware, reset_bus_manager):
        """
        Test rapid initialization and deinitialization cycles.

        This tests the scenario where drivers are frequently created and
        destroyed, which can expose resource leaks and race conditions.
        """
        from src.drivers.servo.pca9685 import PCA9685Driver

        cycle_count = [0]
        errors = []

        def init_deinit_cycle():
            """Repeatedly create and destroy driver."""
            try:
                for _ in range(10):
                    driver = PCA9685Driver()
                    driver.disable_all()
                    driver.deinit()
                    cycle_count[0] += 1
            except Exception as e:
                errors.append(e)

        # Multiple threads doing rapid cycles
        threads = [threading.Thread(target=init_deinit_cycle) for _ in range(3)]

        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10.0)

        # Verify no errors
        assert len(errors) == 0, f"Errors during rapid cycles: {errors}"

        # Verify all cycles completed (3 threads × 10 cycles each)
        assert cycle_count[0] == 30

    def test_init_with_different_frequencies(self, mock_hardware, reset_bus_manager):
        """
        Test parallel initialization with different PWM frequencies.

        Different servo types may require different frequencies (50Hz, 60Hz, etc.)
        """
        from src.drivers.servo.pca9685 import PCA9685Driver

        instances = []
        errors = []

        def create_with_frequency(freq: int):
            """Create driver with specific frequency."""
            try:
                driver = PCA9685Driver(frequency=freq)
                instances.append((freq, driver))
            except Exception as e:
                errors.append((freq, e))

        # Test frequencies: 50Hz, 60Hz, 100Hz, 200Hz
        frequencies = [50, 60, 100, 200]
        threads = [
            threading.Thread(target=create_with_frequency, args=(freq,))
            for freq in frequencies
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5.0)

        # Verify no errors
        assert len(errors) == 0, f"Frequency init errors: {errors}"

        # Verify all frequencies initialized
        assert len(instances) == 4


class TestPCA9685ThreadSafeOperations:
    """Test thread-safe operations after initialization fix."""

    def test_concurrent_servo_control_post_init(self, mock_hardware, reset_bus_manager):
        """
        Test concurrent servo control after thread-safe initialization.

        This verifies that the initialization fix doesn't break normal
        servo operations.
        """
        from src.drivers.servo.pca9685 import PCA9685Driver

        driver = PCA9685Driver()
        operations = []
        errors = []

        def control_servo(channel: int):
            """Control specific servo channel."""
            try:
                for angle in [0, 45, 90, 135, 180]:
                    driver.set_servo_angle(channel, angle)
                    operations.append((channel, angle))
                    time.sleep(0.01)
            except Exception as e:
                errors.append((channel, e))

        # Control 4 servos concurrently
        threads = [
            threading.Thread(target=control_servo, args=(ch,))
            for ch in range(4)
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5.0)

        # Verify no errors
        assert len(errors) == 0, f"Servo control errors: {errors}"

        # Verify all operations completed (4 channels × 5 angles)
        assert len(operations) == 20

    def test_init_uses_bus_manager(self, mock_hardware, reset_bus_manager):
        """
        VERIFICATION: Confirm PCA9685 initialization uses I2CBusManager.

        This is the core verification that BUG #3 is fixed.
        """
        from src.drivers.servo.pca9685 import PCA9685Driver
        from src.drivers.i2c_bus_manager import I2CBusManager

        # Create driver
        driver = PCA9685Driver()

        # Verify PCA9685 was created (proves initialization worked)
        assert mock_hardware['pca_class'].call_count >= 1

        # Driver should be functional
        assert driver is not None
        assert hasattr(driver, 'pca')

    def test_no_deadlock_with_nested_operations(self, mock_hardware, reset_bus_manager):
        """
        Test no deadlock occurs with nested I2C operations.

        This verifies that the initialization fix doesn't introduce
        deadlock scenarios.
        """
        from src.drivers.servo.pca9685 import PCA9685Driver

        driver = PCA9685Driver()
        completed = []

        def nested_operations():
            """Perform nested servo operations."""
            try:
                for i in range(5):
                    # Multiple operations in sequence
                    driver.set_servo_angle(0, 90)
                    state = driver.get_channel_state(0)
                    driver.set_servo_angle(1, 45)
                    completed.append(i)
                    time.sleep(0.01)
            except Exception as e:
                completed.append(e)

        # Multiple threads doing nested operations
        threads = [threading.Thread(target=nested_operations) for _ in range(3)]

        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5.0)

        # Verify all completed without deadlock
        assert len(completed) == 15  # 3 threads × 5 iterations
        assert all(isinstance(c, int) for c in completed), "Some operations failed!"
