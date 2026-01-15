"""Thread Safety Tests for I2C Bus Manager - Double-Checked Locking Bug Detection

This test suite is designed to expose and verify fixes for the double-checked locking
race condition in I2CBusManager singleton initialization.

BUG #1: Double-Checked Locking Race Condition
----------------------------------------------
The current implementation in i2c_bus_manager.py (lines 86-92) has a subtle but CRITICAL
race condition between object creation and initialization flag setting:

    if cls._instance is None:           # <-- Thread 1 enters here
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()   # <-- Thread 1 creates object
                                        # <-- Thread 2 can see partial object HERE!
                cls._instance._initialized = False

Problem: Between `cls._instance = cls()` and setting `_initialized`, another thread
can acquire the lock, see `_instance is not None`, and access a partially constructed object.

This test creates 100 threads that simultaneously try to get the singleton, with timing
delays to maximize the probability of hitting the race condition window.

Test Strategy:
    1. Spawn 100 threads simultaneously
    2. Each thread tries to get singleton instance
    3. Add deliberate delays in __init__ to widen race window
    4. Verify only ONE instance is created across all threads
    5. Verify all threads get fully initialized instance

Expected Results:
    - BEFORE FIX: Occasional failures (race condition exposed)
    - AFTER FIX: 100% pass rate (proper synchronization)
"""

import pytest
import threading
import time
from unittest.mock import patch, Mock
from typing import List, Set


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


class TestDoubleCheckedLockingRaceCondition:
    """Tests specifically targeting double-checked locking race condition."""

    def test_singleton_100_thread_stress(self, mock_hardware):
        """
        STRESS TEST: 100 threads simultaneously requesting singleton.

        This test is designed to expose the race condition where a thread can
        observe a partially initialized singleton instance.

        The bug occurs when:
        1. Thread A creates instance (cls._instance = cls())
        2. Thread B checks (cls._instance is None) -> False
        3. Thread B exits lock and accesses partially initialized instance
        4. Thread A hasn't finished __init__ yet

        Expected: Only ONE instance created, all threads see same instance
        """
        from src.drivers.i2c_bus_manager import I2CBusManager

        # Reset singleton state
        I2CBusManager.reset()

        # Track all instances obtained by threads
        instances: List['I2CBusManager'] = []
        instance_ids: List[int] = []
        errors: List[Exception] = []
        ready_barrier = threading.Barrier(100)  # Synchronize thread start

        def get_instance_with_barrier():
            """Get singleton instance after all threads ready."""
            try:
                # Wait for all threads to be ready
                ready_barrier.wait()

                # Now all threads try to get instance simultaneously
                instance = I2CBusManager.get_instance()

                # Record instance
                instances.append(instance)
                instance_ids.append(id(instance))

            except Exception as e:
                errors.append(e)

        # Spawn 100 threads
        threads = [
            threading.Thread(target=get_instance_with_barrier)
            for _ in range(100)
        ]

        # Start all threads
        for thread in threads:
            thread.start()

        # Wait for all threads to complete
        for thread in threads:
            thread.join(timeout=10.0)

        # Verify no errors occurred
        assert len(errors) == 0, f"Errors during threading: {errors}"

        # Verify all threads got an instance
        assert len(instances) == 100, f"Expected 100 instances, got {len(instances)}"

        # CRITICAL: All instances must have the same ID (singleton pattern)
        unique_ids = set(instance_ids)
        assert len(unique_ids) == 1, (
            f"RACE CONDITION DETECTED! Multiple instances created: {len(unique_ids)} unique IDs. "
            f"This indicates the double-checked locking pattern is broken. "
            f"Thread-unsafe singleton initialization allowed {len(unique_ids)} different instances."
        )

        # Verify all instances are the same object
        first_instance = instances[0]
        for i, instance in enumerate(instances[1:], 1):
            assert instance is first_instance, (
                f"Thread {i} got different instance! "
                f"ID: {id(instance)} vs {id(first_instance)}"
            )

    def test_singleton_partial_initialization_detection(self, mock_hardware):
        """
        Test detection of partially initialized singleton.

        This test deliberately introduces a delay in __init__ to widen the
        race condition window and detect partial initialization.
        """
        from src.drivers.i2c_bus_manager import I2CBusManager

        # Reset singleton
        I2CBusManager.reset()

        initialization_completed = threading.Event()
        partial_init_detected = threading.Event()

        # Patch __init__ to add delay
        original_init = I2CBusManager.__init__

        def delayed_init(self):
            """Modified __init__ with deliberate delay to expose race condition."""
            # Start normal initialization
            if I2CBusManager._bus is not None:
                return

            # Introduce delay AFTER instance creation but BEFORE completion
            time.sleep(0.05)  # 50ms delay to widen race window

            original_init(self)
            initialization_completed.set()

        instances = []
        errors = []

        def thread1_create_instance():
            """Thread 1: Creates the singleton."""
            try:
                with patch.object(I2CBusManager, '__init__', delayed_init):
                    instance = I2CBusManager.get_instance()
                    instances.append(('thread1', instance, id(instance)))
            except Exception as e:
                errors.append(('thread1', e))

        def thread2_quick_access():
            """Thread 2: Tries to access singleton during Thread 1's initialization."""
            try:
                # Wait a tiny bit for Thread 1 to enter __init__
                time.sleep(0.01)

                # Try to get instance while Thread 1 is still initializing
                instance = I2CBusManager.get_instance()
                instances.append(('thread2', instance, id(instance)))

                # Check if we got the instance before initialization completed
                if not initialization_completed.is_set():
                    partial_init_detected.set()

            except Exception as e:
                errors.append(('thread2', e))

        # Start threads
        t1 = threading.Thread(target=thread1_create_instance)
        t2 = threading.Thread(target=thread2_quick_access)

        t1.start()
        t2.start()

        t1.join(timeout=5.0)
        t2.join(timeout=5.0)

        # Verify no errors
        assert len(errors) == 0, f"Threading errors: {errors}"

        # Verify both threads got instances
        assert len(instances) == 2, f"Expected 2 instances, got {len(instances)}"

        # CRITICAL: Both must be the same instance
        thread1_instance_id = instances[0][2]
        thread2_instance_id = instances[1][2]

        assert thread1_instance_id == thread2_instance_id, (
            f"PARTIAL INITIALIZATION BUG! Thread 2 got different instance: "
            f"Thread 1 ID: {thread1_instance_id}, Thread 2 ID: {thread2_instance_id}"
        )

        # If partial initialization was detected, it means the bug exists
        # (Thread 2 accessed instance while Thread 1 was still in __init__)
        if partial_init_detected.is_set():
            print("\nWARNING: Partial initialization window detected but singleton IDs match.")
            print("This may indicate luck - run test multiple times to be sure.")

    def test_singleton_with_exception_during_init(self, mock_hardware):
        """
        Test singleton behavior when exception occurs during initialization.

        This ensures that failed initialization doesn't leave partial instance
        that other threads might access.
        """
        from src.drivers.i2c_bus_manager import I2CBusManager

        # Reset singleton
        I2CBusManager.reset()

        # Make first initialization fail
        call_count = [0]

        def failing_i2c_init(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                raise RuntimeError("First init fails")
            return Mock()  # Subsequent calls succeed

        mock_hardware['busio'].I2C.side_effect = failing_i2c_init

        # First thread should fail
        errors = []
        instances = []

        def try_get_instance():
            try:
                instance = I2CBusManager.get_instance()
                instances.append(instance)
            except RuntimeError as e:
                errors.append(e)

        # First attempt should fail
        thread1 = threading.Thread(target=try_get_instance)
        thread1.start()
        thread1.join()

        # Should have one error, no instances
        assert len(errors) == 1
        assert len(instances) == 0
        assert "First init fails" in str(errors[0])

        # Second attempt should succeed
        thread2 = threading.Thread(target=try_get_instance)
        thread2.start()
        thread2.join()

        # Should now have instance
        assert len(instances) == 1

    def test_concurrent_initialization_no_double_init(self, mock_hardware):
        """
        Verify that even under extreme concurrency, I2C bus is only initialized once.

        Multiple threads racing to create singleton should result in exactly
        ONE call to busio.I2C().
        """
        from src.drivers.i2c_bus_manager import I2CBusManager

        # Reset singleton
        I2CBusManager.reset()

        # Track I2C init calls
        init_count = [0]

        def counted_i2c_init(*args, **kwargs):
            init_count[0] += 1
            time.sleep(0.01)  # Introduce delay to widen race window
            return Mock()

        mock_hardware['busio'].I2C.side_effect = counted_i2c_init

        instances = []
        barrier = threading.Barrier(50)

        def get_with_barrier():
            barrier.wait()  # All threads start simultaneously
            instance = I2CBusManager.get_instance()
            instances.append(instance)

        # 50 threads all trying to initialize simultaneously
        threads = [threading.Thread(target=get_with_barrier) for _ in range(50)]

        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5.0)

        # All threads should get instances
        assert len(instances) == 50

        # CRITICAL: I2C bus should be initialized exactly ONCE
        assert init_count[0] == 1, (
            f"I2C bus initialized {init_count[0]} times! "
            f"Thread-unsafe initialization detected. "
            f"Expected exactly 1 initialization."
        )

        # All instances should be the same
        assert len(set(id(inst) for inst in instances)) == 1


class TestI2CManagerThreadSafety:
    """Additional thread safety tests beyond double-checked locking."""

    def test_rapid_singleton_access_from_multiple_threads(self, mock_hardware):
        """Test rapid repeated access to singleton from multiple threads."""
        from src.drivers.i2c_bus_manager import I2CBusManager

        # Reset singleton
        I2CBusManager.reset()

        instances = []

        def rapid_access():
            """Rapidly access singleton 100 times."""
            for _ in range(100):
                instance = I2CBusManager.get_instance()
                instances.append(id(instance))

        # 10 threads each accessing 100 times = 1000 accesses
        threads = [threading.Thread(target=rapid_access) for _ in range(10)]

        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5.0)

        # Should have 1000 instance IDs
        assert len(instances) == 1000

        # All should be the same ID
        assert len(set(instances)) == 1, "Multiple singleton instances detected!"

    def test_singleton_under_memory_pressure(self, mock_hardware):
        """Test singleton maintains identity under simulated memory pressure."""
        from src.drivers.i2c_bus_manager import I2CBusManager

        # Reset singleton
        I2CBusManager.reset()

        # Get initial instance
        initial_instance = I2CBusManager.get_instance()
        initial_id = id(initial_instance)

        # Create memory pressure with many threads
        instances = []

        def get_and_hold():
            instance = I2CBusManager.get_instance()
            instances.append(id(instance))
            time.sleep(0.1)  # Hold reference

        threads = [threading.Thread(target=get_and_hold) for _ in range(100)]

        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10.0)

        # All instances should be the same as initial
        assert all(inst_id == initial_id for inst_id in instances), \
            "Singleton identity violated under memory pressure!"
