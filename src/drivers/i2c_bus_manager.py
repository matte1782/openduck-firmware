"""I2C Bus Manager - Thread-safe Singleton for I2C Bus Access

This module provides a centralized, thread-safe manager for I2C bus access across
multiple devices. Implements singleton pattern to ensure only one I2C bus instance
exists, with mutex locking to prevent bus collisions.

Critical for embedded systems where multiple I2C devices (PCA9685, BNO085, etc.)
must share the same physical I2C bus without interference.

Design Pattern:
    - Singleton: Ensures single I2C bus instance
    - Context Manager: RAII-style lock acquisition/release
    - Thread-safe: Uses threading.RLock for reentrant locking

Hardware:
    - Raspberry Pi I2C Bus 1 (default)
    - SCL: GPIO 3 (Pin 5)
    - SDA: GPIO 2 (Pin 3)

Example:
    ```python
    # Get singleton instance
    manager = I2CBusManager.get_instance()

    # Safe bus access with automatic locking
    with manager.acquire_bus() as bus:
        # Perform I2C operations
        device = SomeI2CDevice(bus, address=0x40)
        device.write_data(...)
    # Lock automatically released
    ```

Prevents:
    - Bus collisions between simultaneous device access
    - Multiple I2C bus instances causing hardware conflicts
    - Race conditions in multi-threaded applications
"""

import threading
from contextlib import contextmanager
from typing import Optional

try:
    import board
    import busio
except ImportError:
    # Mock imports for development on non-Pi systems
    board = None
    busio = None


class I2CBusManager:
    """Thread-safe singleton manager for I2C bus access.

    Provides centralized I2C bus management with mutex locking to prevent
    bus collisions when multiple devices access the bus concurrently.

    Attributes:
        _instance: Singleton instance (class variable)
        _lock: Lock for thread-safe singleton initialization
        _bus: Shared I2C bus instance
        _bus_lock: Reentrant lock for bus access synchronization
    """

    # Class-level singleton state
    _instance: Optional['I2CBusManager'] = None
    _lock = threading.Lock()
    _bus: Optional['busio.I2C'] = None
    _bus_lock = threading.RLock()  # Reentrant lock for nested acquisition
    _lock_count = 0  # Track lock acquisition count
    _lock_count_lock = threading.Lock()  # Protect lock count updates

    @classmethod
    def get_instance(cls) -> 'I2CBusManager':
        """Get singleton instance of I2C bus manager.

        Thread-safe singleton pattern using double-checked locking with proper
        initialization protection.

        Returns:
            I2CBusManager: The singleton instance

        Raises:
            ImportError: If required hardware libraries not installed
            RuntimeError: If I2C bus initialization fails
        """
        # First check (unlocked) - fast path for already initialized
        if cls._instance is None:
            # Second check (locked) - thread-safe initialization
            with cls._lock:
                if cls._instance is None:
                    # Create instance and initialize bus atomically under lock
                    # This prevents partial object visibility to other threads
                    cls._instance = cls.__new__(cls)
                    cls._instance._initialize_bus()
        return cls._instance

    def _initialize_bus(self):
        """Initialize I2C bus hardware.

        Private method called only during singleton creation, protected by class lock.
        This ensures atomic initialization without race conditions.

        Raises:
            ImportError: If board/busio libraries not available
            RuntimeError: If I2C bus initialization fails
        """
        # Double-check bus initialization (protected by caller's lock)
        if I2CBusManager._bus is not None:
            return

        # Check hardware libraries available
        if board is None or busio is None:
            raise ImportError(
                "Required libraries not installed. Run: "
                "pip install adafruit-circuitpython-busdevice"
            )

        # Initialize I2C bus (only once, under lock protection)
        try:
            I2CBusManager._bus = busio.I2C(board.SCL, board.SDA)
        except Exception as e:
            raise RuntimeError(f"Failed to initialize I2C bus: {e}")

    def __init__(self):
        """Initialize I2C bus manager.

        NOTE: Do not call directly - use get_instance() instead.
        This constructor is deprecated and kept only for backward compatibility.

        The actual initialization is now done by _initialize_bus() which is
        called atomically under lock protection during singleton creation.
        """
        # Prevent direct instantiation - singleton must use get_instance()
        pass

    @contextmanager
    def acquire_bus(self):
        """Acquire exclusive access to I2C bus.

        Context manager that acquires bus lock before yielding bus instance,
        and automatically releases lock when exiting context.

        Ensures thread-safe, serialized access to I2C bus across all devices.

        Yields:
            busio.I2C: The I2C bus instance

        Example:
            ```python
            manager = I2CBusManager.get_instance()
            with manager.acquire_bus() as bus:
                # Exclusive bus access guaranteed here
                device.read_data(bus)
            # Lock automatically released
            ```
        """
        self._bus_lock.acquire()
        with self._lock_count_lock:
            I2CBusManager._lock_count += 1
        try:
            yield self._bus
        finally:
            with self._lock_count_lock:
                I2CBusManager._lock_count -= 1
            self._bus_lock.release()

    def get_bus(self) -> 'busio.I2C':
        """Get direct access to I2C bus.

        Provides non-locking access to bus for compatibility with existing code.
        WARNING: Direct access bypasses locking - prefer acquire_bus() for
        thread-safe operations.

        Returns:
            busio.I2C: The I2C bus instance
        """
        return self._bus

    def is_locked(self) -> bool:
        """Check if bus is currently locked.

        WARNING: Result may be stale immediately after return due to
        Time-Of-Check-Time-Of-Use (TOCTTOU) race condition.

        This method is for informational/debugging purposes only.
        DO NOT use for synchronization decisions.

        Returns:
            bool: True if bus is currently locked, False otherwise.
                  Note: Value may change before caller can act on it.
        """
        with self._lock_count_lock:
            return I2CBusManager._lock_count > 0

    @classmethod
    def reset(cls):
        """Reset singleton instance.

        FOR TESTING ONLY - Resets singleton state to allow fresh initialization.
        Should never be called in production code.
        """
        with cls._lock:
            if cls._bus is not None:
                try:
                    cls._bus.deinit()
                except:
                    pass
            cls._instance = None
            cls._bus = None
            with cls._lock_count_lock:
                cls._lock_count = 0


# Module-level convenience function
def get_i2c_bus_manager() -> I2CBusManager:
    """Get I2C bus manager singleton instance.

    Convenience function for cleaner imports:
    ```python
    from src.drivers.i2c_bus_manager import get_i2c_bus_manager
    manager = get_i2c_bus_manager()
    ```

    Returns:
        I2CBusManager: The singleton instance
    """
    return I2CBusManager.get_instance()
