"""Thread safety tests for PCA9685 PWM driver.

CRITICAL Issue #1 from hostile review: Race conditions in PCA9685 driver

Tests cover:
- Concurrent servo angle setting across multiple threads
- Channel state consistency under concurrent access
- PWM register access serialization
- Lock-free read operations (get_channel_state)
- Deadlock prevention in disable_all
"""

import pytest
import threading
import time
from unittest.mock import Mock, MagicMock, patch


@pytest.fixture
def mock_hardware():
    """Mock hardware dependencies for testing."""
    with patch('src.drivers.servo.pca9685.board') as mock_board, \
         patch('src.drivers.servo.pca9685.busio') as mock_busio, \
         patch('src.drivers.servo.pca9685.PCA9685') as mock_pca9685_class, \
         patch('src.drivers.i2c_bus_manager.board') as mock_mgr_board, \
         patch('src.drivers.i2c_bus_manager.busio') as mock_mgr_busio:

        # Configure mocks
        mock_board.SCL = Mock()
        mock_board.SDA = Mock()
        mock_mgr_board.SCL = Mock()
        mock_mgr_board.SDA = Mock()

        mock_i2c = Mock()
        mock_busio.I2C.return_value = mock_i2c
        mock_mgr_busio.I2C.return_value = mock_i2c

        mock_pca = MagicMock()
        mock_pca9685_class.return_value = mock_pca

        # Mock channels with thread-safe access simulation
        mock_pca.channels = {i: Mock(duty_cycle=0) for i in range(16)}

        # Reset I2C Bus Manager before each test
        from src.drivers.i2c_bus_manager import I2CBusManager
        I2CBusManager.reset()

        yield {
            'board': mock_board,
            'busio': mock_busio,
            'pca9685_class': mock_pca9685_class,
            'pca': mock_pca,
            'i2c': mock_i2c
        }

        # Cleanup
        I2CBusManager.reset()


class TestPCA9685ThreadSafety:
    """Test cases for PCA9685Driver thread safety."""

    def test_concurrent_servo_angle_setting(self, mock_hardware):
        """Test multiple threads setting servo angles simultaneously.

        Race condition: Multiple threads modifying self.channels dict and
        calling self.pca.channels[].duty_cycle without synchronization.
        """
        from src.drivers.servo.pca9685 import PCA9685Driver

        driver = PCA9685Driver()
        errors = []
        angles_set = []

        def set_angle(channel, angle):
            try:
                driver.set_servo_angle(channel, angle)
                angles_set.append((channel, angle))
            except Exception as e:
                errors.append((channel, angle, e))

        # Create 16 threads, each setting a different channel
        threads = [
            threading.Thread(target=set_angle, args=(i, 90 + i))
            for i in range(16)
        ]

        # Start all threads simultaneously
        for t in threads:
            t.start()

        # Wait for all to complete
        for t in threads:
            t.join()

        # Verify no exceptions occurred
        assert len(errors) == 0, f"Thread safety violations detected: {errors}"

        # Verify all channels were set correctly
        assert len(angles_set) == 16, "Not all channels were set"
        for channel in range(16):
            state = driver.get_channel_state(channel)
            expected_angle = 90 + channel
            assert state['angle'] == expected_angle, \
                f"Channel {channel} angle mismatch: expected {expected_angle}, got {state['angle']}"
            assert state['enabled'] is True

    def test_channel_state_consistency_under_concurrent_writes(self, mock_hardware):
        """Test channel state remains consistent under concurrent writes.

        Race condition: Thread A reads state, Thread B modifies, Thread A writes
        stale data back, causing inconsistency.
        """
        from src.drivers.servo.pca9685 import PCA9685Driver

        driver = PCA9685Driver()
        errors = []
        iterations = 100

        def rapid_set_angle(channel, base_angle):
            """Rapidly set angles in a loop to expose race conditions."""
            try:
                for i in range(iterations):
                    angle = base_angle + (i % 10)
                    driver.set_servo_angle(channel, angle)
            except Exception as e:
                errors.append(e)

        # Two threads hammering the same channel
        threads = [
            threading.Thread(target=rapid_set_angle, args=(0, 90)),
            threading.Thread(target=rapid_set_angle, args=(0, 80)),
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Verify no crashes or exceptions
        assert len(errors) == 0, f"Race condition detected: {errors}"

        # Verify channel state is valid (angle should be one of the set values)
        state = driver.get_channel_state(0)
        assert state['enabled'] is True
        assert 80 <= state['angle'] <= 99, \
            f"Channel state corrupted: angle={state['angle']}"

    def test_concurrent_pwm_register_access(self, mock_hardware):
        """Test concurrent PWM register writes are serialized.

        Race condition: Simultaneous writes to self.pca.channels[].duty_cycle
        may cause hardware register corruption.
        """
        from src.drivers.servo.pca9685 import PCA9685Driver

        driver = PCA9685Driver()
        errors = []

        def set_pwm(channel, value):
            try:
                driver.set_pwm(channel, 0, value)
            except Exception as e:
                errors.append(e)

        # Concurrent writes to different channels
        threads = [
            threading.Thread(target=set_pwm, args=(i, 2048))
            for i in range(16)
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Verify all writes completed without errors
        assert len(errors) == 0, f"PWM writes failed: {errors}"

    def test_dict_corruption_race_condition(self, mock_hardware):
        """Test that dict modifications don't cause corruption.

        Real race condition: Python dicts are not thread-safe for modifications.
        Multiple threads modifying self.channels[ch]['angle'] can cause:
        - Lost updates
        - KeyError
        - Dict corruption in extreme cases
        """
        from src.drivers.servo.pca9685 import PCA9685Driver

        driver = PCA9685Driver()
        errors = []
        channel = 0  # All threads modify same channel to maximize contention

        def hammer_channel():
            """Rapidly modify the same channel to expose dict race conditions."""
            try:
                for i in range(100):
                    # This line has a race: read dict, modify, write back
                    driver.set_servo_angle(channel, 90 + (i % 90))
            except Exception as e:
                errors.append(e)

        # Multiple threads modifying the same channel
        threads = [threading.Thread(target=hammer_channel) for _ in range(10)]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Without locks, this may fail with dict corruption or lost updates
        assert len(errors) == 0, f"Dict corruption detected: {errors}"

        # Verify state is still valid
        state = driver.get_channel_state(channel)
        assert isinstance(state, dict)
        assert 'angle' in state
        assert 'enabled' in state

    def test_concurrent_disable_operations(self, mock_hardware):
        """Test concurrent disable operations are safe.

        Race condition: disable_all() calls disable_channel() 16 times,
        concurrent calls may corrupt state.
        """
        from src.drivers.servo.pca9685 import PCA9685Driver

        driver = PCA9685Driver()
        errors = []

        # Set all channels active
        for i in range(16):
            driver.set_servo_angle(i, 90)

        def disable_operation():
            try:
                driver.disable_all()
            except Exception as e:
                errors.append(e)

        # Multiple threads calling disable_all simultaneously
        threads = [threading.Thread(target=disable_operation) for _ in range(5)]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Verify no exceptions
        assert len(errors) == 0, f"Concurrent disable failed: {errors}"

        # Verify all channels disabled
        for i in range(16):
            state = driver.get_channel_state(i)
            assert state['enabled'] is False, \
                f"Channel {i} not disabled after concurrent disable_all"

    def test_read_operations_during_writes(self, mock_hardware):
        """Test read operations (get_channel_state) work during concurrent writes.

        This tests that reads don't deadlock or return corrupted data.
        """
        from src.drivers.servo.pca9685 import PCA9685Driver

        driver = PCA9685Driver()
        errors = []
        read_states = []

        def writer(channel, angle):
            try:
                for _ in range(50):
                    driver.set_servo_angle(channel, angle)
                    time.sleep(0.001)
            except Exception as e:
                errors.append(('write', e))

        def reader(channel):
            try:
                for _ in range(50):
                    state = driver.get_channel_state(channel)
                    read_states.append(state)
                    time.sleep(0.001)
            except Exception as e:
                errors.append(('read', e))

        # Concurrent readers and writers
        threads = [
            threading.Thread(target=writer, args=(0, 90)),
            threading.Thread(target=writer, args=(1, 120)),
            threading.Thread(target=reader, args=(0,)),
            threading.Thread(target=reader, args=(1,)),
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Verify no errors
        assert len(errors) == 0, f"Read/write concurrency failed: {errors}"

        # Verify reads returned valid data
        assert len(read_states) > 0, "No states were read"
        for state in read_states:
            assert 'angle' in state
            assert 'enabled' in state

    def test_set_servo_pulse_thread_safety(self, mock_hardware):
        """Test set_servo_pulse is thread-safe.

        Alternative API to set_servo_angle must also be thread-safe.
        """
        from src.drivers.servo.pca9685 import PCA9685Driver

        driver = PCA9685Driver()
        errors = []

        def set_pulse(channel, pulse):
            try:
                driver.set_servo_pulse(channel, pulse)
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=set_pulse, args=(i, 1500))
            for i in range(16)
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"set_servo_pulse not thread-safe: {errors}"

    def test_no_deadlock_in_nested_operations(self, mock_hardware):
        """Test that disable_all (which calls disable_channel) doesn't deadlock.

        If locks are not reentrant or improperly implemented, this will hang.
        """
        from src.drivers.servo.pca9685 import PCA9685Driver

        driver = PCA9685Driver()
        errors = []
        completed = [False]

        def nested_disable():
            try:
                # Set some channels
                for i in range(8):
                    driver.set_servo_angle(i, 90)
                # Disable all (calls disable_channel internally)
                driver.disable_all()
                # Try disabling a specific channel after
                driver.disable_channel(0)
                completed[0] = True
            except Exception as e:
                errors.append(e)

        thread = threading.Thread(target=nested_disable)
        thread.start()
        thread.join(timeout=2.0)  # Should complete quickly

        # Verify it completed without deadlock
        assert thread.is_alive() is False, "Deadlock detected in nested operations"
        assert completed[0] is True, "Operation did not complete"
        assert len(errors) == 0, f"Errors in nested operations: {errors}"

    def test_stress_mixed_operations(self, mock_hardware):
        """Stress test with mixed concurrent operations.

        Real-world scenario: multiple operations happening simultaneously.
        """
        from src.drivers.servo.pca9685 import PCA9685Driver

        driver = PCA9685Driver()
        errors = []
        operations_completed = [0]
        lock = threading.Lock()

        def worker(worker_id):
            try:
                for i in range(20):
                    if i % 4 == 0:
                        driver.set_servo_angle(worker_id % 16, 90)
                    elif i % 4 == 1:
                        driver.set_servo_pulse(worker_id % 16, 1500)
                    elif i % 4 == 2:
                        driver.disable_channel(worker_id % 16)
                    else:
                        driver.get_channel_state(worker_id % 16)

                    with lock:
                        operations_completed[0] += 1
            except Exception as e:
                errors.append((worker_id, e))

        # 10 concurrent workers performing mixed operations
        threads = [threading.Thread(target=worker, args=(i,)) for i in range(10)]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Verify success
        assert len(errors) == 0, f"Stress test failures: {errors}"
        assert operations_completed[0] == 200, \
            f"Not all operations completed: {operations_completed[0]}/200"


class TestServoControllerThreadSafety:
    """Test thread safety of ServoController which uses PCA9685Driver."""

    def test_concurrent_controller_operations(self, mock_hardware):
        """Test ServoController operations are thread-safe.

        ServoController calls driver methods, so thread safety must propagate.
        """
        from src.drivers.servo.pca9685 import PCA9685Driver, ServoController

        driver = PCA9685Driver()
        controller = ServoController(driver)
        errors = []

        # Set limits for safety
        for i in range(16):
            controller.set_servo_limits(i, 0, 180)

        def move_servo_concurrent(channel, angle):
            try:
                controller.move_servo(channel, angle)
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=move_servo_concurrent, args=(i, 90))
            for i in range(16)
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Controller thread safety failed: {errors}"

    def test_move_multiple_thread_safety(self, mock_hardware):
        """Test move_multiple is thread-safe when called concurrently."""
        from src.drivers.servo.pca9685 import PCA9685Driver, ServoController

        driver = PCA9685Driver()
        controller = ServoController(driver)
        errors = []

        def move_multiple():
            try:
                moves = {i: 90 for i in range(8)}
                controller.move_multiple(moves)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=move_multiple) for _ in range(5)]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"move_multiple not thread-safe: {errors}"
